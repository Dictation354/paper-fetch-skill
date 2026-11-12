"""IOP bounded HTTP scheduling and caller-thread browser recovery."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextvars import copy_context
from dataclasses import replace
from pathlib import Path
import time
from typing import Any
from collections.abc import Callable, Mapping
from ..asset_budget import AssetBudget, current_asset_budget
from ..provider_catalog import compile_route_execution_policy_for_kind
from ..extraction.html.assets import FIGURE_KIND, AssetDownloadOptions
from ..extraction.html.assets.download import asset_work_key
from ..extraction.html.assets.state import AssetHostRecoveryCircuit
from ..utils import empty_asset_results
from .browser_workflow.shared import BrowserWorkflowDeps
from .browser_workflow.asset_download import (
    _raise_if_cancelled,
    _asset_failure_allows_browser_recovery,
    _annotate_split_browser_recovery,
    _matching_failure,
    _attempt_from_failure,
)


def _download_iop_body_assets(
    assets: list[dict[str, Any]],
    *,
    deps: BrowserWorkflowDeps,
    transport: Any,
    common_kwargs: Mapping[str, Any],
    options: AssetDownloadOptions,
    image_document_fetcher: Any,
    configured_concurrency: int | None,
    merge_results: Callable[..., Any],
) -> tuple[Mapping[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Run bounded HTTP work; consume and recover on the browser's caller thread."""
    route = compile_route_execution_policy_for_kind("iop", "assets")
    budget = (
        options.asset_budget
        or current_asset_budget()
        or AssetBudget(route_concurrency_cap=route.asset_concurrency_cap)
    )
    options = replace(options, asset_budget=budget, asset_download_concurrency=1)
    budget.admit_work([asset_work_key(FIGURE_KIND, asset) for asset in assets])
    workers = min(
        2,
        budget.effective_concurrency(
            configured_concurrency, route_concurrency_cap=route.asset_concurrency_cap
        ),
    )
    queued_at = time.monotonic()
    results: dict[int, Mapping[str, Any]] = {}
    direct_failures: list[dict[str, Any]] = []
    browser_failures: list[dict[str, Any]] = []
    browser_hosts: set[str] = set()
    pending = list(enumerate(assets))
    futures: dict[Any, int] = {}
    executor = ThreadPoolExecutor(max_workers=workers)

    def host(asset: Mapping[str, Any]) -> str:
        return AssetHostRecoveryCircuit.host_for_url(
            str(
                asset.get("original_url")
                or asset.get("full_size_url")
                or asset.get("url")
                or ""
            )
        )

    def download(index: int, *, browser: bool) -> Mapping[str, Any]:
        _raise_if_cancelled(options.runtime_context)
        budget.raise_if_cancelled()
        started = time.monotonic()
        result = deps.download_assets(
            FIGURE_KIND,
            transport,
            assets=[assets[index]],
            options=replace(
                options,
                # HTTP workers must never call a page/figure browser fetcher or
                # wait on the serial first-probe circuit.
                figure_page_fetcher=options.figure_page_fetcher if browser else None,
                image_document_fetcher=image_document_fetcher if browser else None,
                host_recovery_circuit=options.host_recovery_circuit
                if browser
                else None,
                fetch_policy="browser_first" if browser else "direct_then_browser",
            ),
            **common_kwargs,
        )
        for outcome in [*result.get("assets", []), *result.get("asset_failures", [])]:
            timing = outcome.get("asset_timing")
            if isinstance(timing, Mapping):
                outcome["asset_timing"] = {
                    **timing,
                    "queue_ms": round(
                        float(timing.get("queue_ms", 0)) + (started - queued_at) * 1000,
                        3,
                    ),
                    "total_ms": round((time.monotonic() - queued_at) * 1000, 3),
                }
        return result

    def recover(index: int, direct: Mapping[str, Any]) -> Mapping[str, Any]:
        eligible = [
            dict(f)
            for f in direct.get("asset_failures", [])
            if _asset_failure_allows_browser_recovery(f)
        ]
        if not eligible or image_document_fetcher is None:
            return direct
        direct_failures.extend(eligible)
        browser_result = download(index, browser=True)
        browser_failures.extend(
            dict(f) for f in browser_result.get("asset_failures", [])
        )
        browser_result = _annotate_split_browser_recovery(browser_result, eligible)
        for failure in browser_result.get("asset_failures", []):
            direct_failure = _matching_failure(failure, eligible)
            if direct_failure is not None:
                failure["recovery_attempts"] = [
                    _attempt_from_failure("direct", direct_failure),
                    _attempt_from_failure("browser", failure),
                ]
        for outcome in [
            *browser_result.get("assets", []),
            *browser_result.get("asset_failures", []),
        ]:
            direct_failure = _matching_failure(outcome, eligible)
            if direct_failure is None:
                continue
            original_timing = direct_failure.get("asset_timing") or {}
            timing = outcome.get("asset_timing") or {}
            if timing:
                outcome["asset_timing"] = {
                    **timing,
                    **{
                        key: round(float(timing.get(key, 0)) + float(value), 3)
                        for key, value in original_timing.items()
                        if key.endswith("_ms") and key not in {"total_ms", "queue_ms"}
                    },
                    "queue_ms": original_timing.get("queue_ms", 0),
                }
        if browser_result.get("assets"):
            for asset in browser_result["assets"]:
                verified_url = str(
                    asset.get("source_url")
                    or asset.get("original_url")
                    or assets[index].get("original_url")
                    or assets[index].get("url")
                    or ""
                )
                verified_host = AssetHostRecoveryCircuit.host_for_url(verified_url)
                browser_hosts.add(verified_host)
                if options.host_recovery_circuit is not None:
                    decision = options.host_recovery_circuit.begin(verified_url)
                    options.host_recovery_circuit.observe(
                        decision, browser_recovery_succeeded=True
                    )
        return merge_results(direct, browser_result)

    try:
        while pending or futures:
            _raise_if_cancelled(options.runtime_context)
            if budget.internally_cancelled:
                # Reuse the downloader's budget-terminal diagnostics for queued
                # assets without submitting additional HTTP work.
                for index, _asset in pending:
                    results[index] = deps.download_assets(
                        FIGURE_KIND,
                        transport,
                        assets=[assets[index]],
                        options=replace(
                            options,
                            figure_page_fetcher=None,
                            image_document_fetcher=None,
                            host_recovery_circuit=None,
                        ),
                        **common_kwargs,
                    )
                pending.clear()
            else:
                budget.raise_if_cancelled()
            # Do not replenish the pool until completed failures have been
            # consumed. Recovery pauses submissions; in-flight HTTP can finish.
            completed = [future for future in futures if future.done()]
            if not completed:
                while pending and len(futures) < workers:
                    index, asset = pending.pop(0)
                    if host(asset) in browser_hosts:
                        results[index] = download(index, browser=True)
                    else:
                        future = executor.submit(
                            copy_context().run, download, index, browser=False
                        )
                        futures[future] = index
                if futures:
                    done, _ = wait(futures, timeout=0.1, return_when=FIRST_COMPLETED)
                    completed = list(done)
            for future in completed:
                index = futures.pop(future)
                direct = future.result()
                results[index] = direct
                if not budget.internally_cancelled:
                    results[index] = recover(index, direct)
        merged = empty_asset_results()
        for index in range(len(assets)):
            merged = merge_results(merged, results.get(index, empty_asset_results()))
        return merged, direct_failures, browser_failures
    except BaseException:
        budget.cancel("asset_cancelled", diagnostic={"boundary": "iop_asset_worker"})
        for future in futures:
            future.cancel()
        raise
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
        if budget.cancelled:
            budget.rollback_active()
            completed_results = [*results.values()]
            for future in futures:
                if (
                    future.done()
                    and not future.cancelled()
                    and future.exception() is None
                ):
                    completed_results.append(future.result())
            for result in completed_results:
                for asset in result.get("assets", []):
                    path = asset.get("path")
                    if path:
                        Path(path).unlink(missing_ok=True)
