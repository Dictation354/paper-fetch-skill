"""HTML asset download orchestration and two-stage HTTP/browser scheduling."""

from __future__ import annotations

import contextlib
import time
import urllib.parse
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from ....asset_budget import AssetBudget, AssetBudgetExceeded, current_asset_budget
from ....http import HttpTransport, RequestFailure
from ....http.headers import header_value
from ....image_tools import (
    ImageConversionFailure,
    convert_source_image_path_to_png,
)
from ....models.schema import AssetProfile
from ....provider_catalog import (
    compile_route_execution_policy,
    compile_route_execution_policy_for_kind,
    effective_route_asset_scope,
)
from ....reason_codes import ASSET_CANCELLED, ASSET_FILE_LIMIT_EXCEEDED
from ....utils import empty_asset_results, normalize_text, sanitize_filename
from ._kind import (
    FIGURE_KIND,
    SUPPLEMENTARY_KIND,
    AssetDownloadKind,
)
from ._kind import (
    is_preview_candidate as _is_preview_candidate,
)
from ._kind import (
    requires_image_payload as _requires_image_payload,
)
from ._kind import (
    resolved_full_size_url as _resolved_full_size_url,
)
from .conversion import (
    conversion_failure_attempt,
    save_asset_resolution,
)
from .conversion import (
    converted_figure_response as _converted_figure_response_with_converter,
)
from .dom import (
    _CLOUDFLARE_CHALLENGE_TOKENS,
    SUPPLEMENTARY_BLOCKING_BODY_TOKENS,
    SUPPLEMENTARY_BLOCKING_TITLE_TOKENS,
)
from .figures import FigurePageFetcher, figure_download_candidates
from .identity import html_asset_identity_key, html_asset_is_supplementary
from .recovery import (
    AssetFetchPolicy,
    CandidateResolutionLoopState,
    FileDocumentFetcher,
    ImageDocumentFetcher,
    blocked_response_attempt,
    browser_asset_recovery_allowed,
    browser_first_candidate_recovery,
    browser_preview_upgrade,
    budget_failure_resolution,
    preview_fallback_provenance,
    recover_failed_candidate,
    request_failure_attempt,
    requires_caller_thread,
    should_use_document_fetcher_for_candidate,
    unsupported_scheme_failure,
)
from .state import (
    AssetDeferredBrowserWork,
    AssetDownloadAttempt,
    AssetDownloadCandidate,
    AssetDownloadResolution,
    AssetFetchResponse,
    AssetHostRecoveryCircuit,
    AssetHostRouteDecision,
    asset_failure,
    empty_asset_timing,
    resolution_from_attempt,
    resolve_and_collect_downloads_as_completed,
)
from .streaming import (
    AssetRequestContext,
    request_asset_candidate,
    rollback_response_reservation,
    with_asset_timing,
)


def _active_path_converter(*args: Any, **kwargs: Any) -> Any:
    return convert_source_image_path_to_png(*args, **kwargs)


def _converted_figure_response(
    response: AssetFetchResponse,
    *,
    source_url: str,
    asset_budget: AssetBudget | None = None,
) -> tuple[AssetFetchResponse, str]:
    return _converted_figure_response_with_converter(
        response,
        source_url=source_url,
        asset_budget=asset_budget,
        path_converter=_active_path_converter,
    )


@dataclass(frozen=True)
class AssetResolutionOptions:
    """Dependencies and runtime state for resolving one HTML asset."""

    transport: HttpTransport
    request: AssetRequestContext
    document_fetcher: ImageDocumentFetcher | FileDocumentFetcher | None = None
    candidate_url_resolver: Callable[[Mapping[str, Any]], list[str]] | None = None
    fallback_candidate_url_resolver: Callable[[Mapping[str, Any]], list[str]] | None = (
        None
    )
    host_recovery_circuit: AssetHostRecoveryCircuit | None = None
    defer_browser_to_caller_thread: bool = False


@dataclass(frozen=True)
class AssetDownloadOptions:
    """Optional fetch, safety, and execution controls for ``download_assets``."""

    headers: Mapping[str, str] | None = None
    candidate_headers_filter: (
        Callable[[str, Mapping[str, str]], Mapping[str, str]] | None
    ) = None
    sensitive_headers: tuple[str, ...] = ()
    browser_context_seed: Mapping[str, Any] | None = None
    figure_page_fetcher: FigurePageFetcher | None = None
    candidate_builder: Callable[..., list[str]] | None = None
    fallback_candidate_builder: Callable[..., list[str]] | None = None
    document_fetcher: ImageDocumentFetcher | FileDocumentFetcher | None = None
    image_document_fetcher: ImageDocumentFetcher | None = None
    file_document_fetcher: FileDocumentFetcher | None = None
    asset_download_concurrency: int | None = None
    fetch_policy: AssetFetchPolicy = "browser_first"
    asset_budget: AssetBudget | None = None
    route_concurrency_cap: int | None = None
    allowed_hosts: Sequence[str] | None = None
    provider_name: str | None = None
    route_name: str | None = None
    artifact_store: Any | None = None
    runtime_context: Any | None = None
    host_recovery_circuit: AssetHostRecoveryCircuit | None = None
    _fallback_candidate_builder: Callable[..., list[str]] | None = None

    def __post_init__(self) -> None:
        if (
            self.fallback_candidate_builder is None
            and self._fallback_candidate_builder is not None
        ):
            object.__setattr__(
                self,
                "fallback_candidate_builder",
                self._fallback_candidate_builder,
            )


def _resolution_preview_fields(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    candidate_urls: list[str],
) -> tuple[str, str]:
    if kind.name != "figure":
        return "", ""
    preview_url = normalize_text(
        str(
            asset.get("preview_url")
            or asset.get("url")
            or asset.get("original_url")
            or asset.get("link")
            or ""
        )
    )
    full_size_url = _resolved_full_size_url(
        asset, preview_url=preview_url, candidate_urls=candidate_urls
    )
    return preview_url, full_size_url


@dataclass(frozen=True)
class _DeferredCandidatePause:
    candidate_urls: tuple[str, ...]
    candidate_index: int
    direct_attempt: AssetDownloadAttempt
    conversion_degraded: bool
    full_size_access_failed: bool


def _iter_staged_candidates(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    *,
    initial_candidates: list[str],
    start_index: int,
    fetch_policy: AssetFetchPolicy,
    fallback_resolver: Callable[[Mapping[str, Any]], list[str]] | None,
    asset_budget: AssetBudget,
    loop_state: CandidateResolutionLoopState,
    materialized_candidates: list[str],
) -> Iterator[tuple[int, str]]:
    for index in range(start_index, len(initial_candidates)):
        yield index, initial_candidates[index]

    if fetch_policy == "browser_only" or fallback_resolver is None:
        return
    if asset_budget.internally_cancelled:
        return
    asset_budget.raise_if_cancelled()
    remaining = list(dict.fromkeys(fallback_resolver(asset)))
    _, loop_state.full_size_url = _resolution_preview_fields(
        kind, asset, [*initial_candidates, *remaining]
    )
    seen = set(initial_candidates)
    for url in remaining:
        if url not in seen:
            seen.add(url)
            next_index = len(materialized_candidates)
            materialized_candidates.append(url)
            yield next_index, url


def _resolve_candidate_loop(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    *,
    initial_candidates: list[str],
    start_index: int = 0,
    options: AssetResolutionOptions,
    loop_state: CandidateResolutionLoopState,
) -> AssetDownloadResolution | _DeferredCandidatePause:
    transport = options.transport
    request_context = options.request.for_asset(kind, asset)
    active_budget = request_context.asset_budget
    document_fetcher = options.document_fetcher
    fetch_policy = request_context.fetch_policy

    if not initial_candidates and options.fallback_candidate_url_resolver is None:
        failure = (
            kind.failure_template(
                asset,
                "",
                reason="Supplementary asset did not include a downloadable URL.",
            )
            if kind.name == "supplementary"
            else None
        )
        return resolution_from_attempt(
            asset=asset,
            attempt=(
                AssetDownloadAttempt(
                    candidate=AssetDownloadCandidate(""),
                    failure=asset_failure(failure),
                )
                if failure is not None
                else None
            ),
            preview_url=loop_state.preview_url,
            full_size_url=loop_state.full_size_url,
        )

    materialized_candidates = list(initial_candidates)
    for candidate_index, candidate_url in _iter_staged_candidates(
        kind,
        asset,
        initial_candidates=initial_candidates,
        start_index=start_index,
        fetch_policy=fetch_policy,
        fallback_resolver=options.fallback_candidate_url_resolver,
        asset_budget=active_budget,
        loop_state=loop_state,
        materialized_candidates=materialized_candidates,
    ):
        candidate = AssetDownloadCandidate(candidate_url)
        parsed = urllib.parse.urlparse(candidate_url)
        if parsed.scheme not in {"http", "https"}:
            loop_state.last_attempt = AssetDownloadAttempt(
                candidate=candidate,
                failure=asset_failure(
                    unsupported_scheme_failure(kind, asset, candidate_url)
                ),
            )
            continue

        if fetch_policy == "browser_only" or (
            fetch_policy == "browser_first"
            and should_use_document_fetcher_for_candidate(
                kind,
                candidate_url,
                document_fetcher,
            )
        ):
            recovery = browser_first_candidate_recovery(
                kind,
                asset,
                candidate,
                transport=transport,
                request_context=request_context,
                document_fetcher=document_fetcher,
                preview_url=loop_state.preview_url,
                full_size_url=loop_state.full_size_url,
            )
            if (resolved := loop_state.apply(recovery, candidate)) is not None:
                return resolved
            continue

        try:
            response = request_asset_candidate(
                kind,
                transport,
                candidate_url,
                request_context=request_context,
            )
        except AssetBudgetExceeded as exc:
            return budget_failure_resolution(
                kind,
                asset,
                exc,
                candidate,
                preview_url=loop_state.preview_url,
                full_size_url=loop_state.full_size_url,
            )
        except RequestFailure as exc:
            failed_attempt = request_failure_attempt(kind, asset, candidate, exc)
            recovery_allowed = browser_asset_recovery_allowed(
                status=exc.status_code,
                content_type=header_value(exc.headers, "content-type"),
                reason=str(exc),
                error_category=str(getattr(exc, "error_category", "") or ""),
            )
            if (
                options.defer_browser_to_caller_thread
                and recovery_allowed
                and should_use_document_fetcher_for_candidate(
                    kind,
                    candidate_url,
                    document_fetcher,
                )
            ):
                return _DeferredCandidatePause(
                    candidate_urls=tuple(materialized_candidates),
                    candidate_index=candidate_index,
                    direct_attempt=failed_attempt,
                    conversion_degraded=loop_state.conversion_degraded,
                    full_size_access_failed=loop_state.full_size_access_failed,
                )
            recovery = recover_failed_candidate(
                kind,
                asset,
                candidate,
                transport=transport,
                request_context=request_context,
                document_fetcher=document_fetcher,
                last_attempt=failed_attempt,
                preview_url=loop_state.preview_url,
                full_size_url=loop_state.full_size_url,
                recovery_allowed=recovery_allowed,
            )
            if (resolved := loop_state.apply(recovery, candidate)) is not None:
                return resolved
            continue

        body = response.get("body", b"")
        if not isinstance(body, bytes | bytearray):
            body = b""
        content_type = header_value(response.get("headers"), "content-type")
        block_reason = kind.response_block_reason(content_type, bytes(body))
        if block_reason:
            rollback_response_reservation(response)
            failed_attempt = blocked_response_attempt(
                kind,
                asset,
                candidate,
                response,
                candidate_url,
                block_reason,
            )
            recovery_allowed = browser_asset_recovery_allowed(
                status=int(response.get("status_code") or 0) or None,
                content_type=content_type,
                reason=block_reason,
            )
            if (
                options.defer_browser_to_caller_thread
                and recovery_allowed
                and should_use_document_fetcher_for_candidate(
                    kind,
                    candidate_url,
                    document_fetcher,
                )
            ):
                return _DeferredCandidatePause(
                    candidate_urls=tuple(materialized_candidates),
                    candidate_index=candidate_index,
                    direct_attempt=failed_attempt,
                    conversion_degraded=loop_state.conversion_degraded,
                    full_size_access_failed=loop_state.full_size_access_failed,
                )
            recovery = recover_failed_candidate(
                kind,
                asset,
                candidate,
                transport=transport,
                request_context=request_context,
                document_fetcher=document_fetcher,
                last_attempt=failed_attempt,
                preview_url=loop_state.preview_url,
                full_size_url=loop_state.full_size_url,
                recovery_allowed=recovery_allowed,
            )
            if (resolved := loop_state.apply(recovery, candidate)) is not None:
                return resolved
            continue

        if (
            fetch_policy == "browser_first"
            and kind.upgrade_targets is not None
            and document_fetcher is not None
            and _requires_image_payload(asset)
            and _is_preview_candidate(
                candidate_url,
                preview_url=loop_state.preview_url,
                full_size_url=loop_state.full_size_url,
            )
        ):
            upgrade = browser_preview_upgrade(
                kind,
                asset,
                candidate_url=candidate_url,
                response=response,
                transport=transport,
                request_context=request_context,
                document_fetcher=document_fetcher,
                preview_url=loop_state.preview_url,
                full_size_url=loop_state.full_size_url,
            )
            if (
                resolved := loop_state.apply(
                    upgrade,
                    candidate,
                    preserve_last_attempt=True,
                )
            ) is not None:
                return resolved

        try:
            if fetch_policy == "direct_then_browser":
                response = response.copy()
                response.final_fetcher = "direct_http"
            response, _ = (
                _converted_figure_response(
                    response,
                    source_url=candidate_url,
                    asset_budget=active_budget,
                )
                if kind.name == "figure"
                else (response.copy(), "")
            )
        except ImageConversionFailure as exc:
            loop_state.conversion_degraded = True
            loop_state.mark_non_preview_failure(candidate_url)
            loop_state.last_attempt = conversion_failure_attempt(
                kind,
                asset,
                candidate,
                response,
                exc,
            )
            continue
        except AssetBudgetExceeded as exc:
            return budget_failure_resolution(
                kind,
                asset,
                exc,
                candidate,
                preview_url=loop_state.preview_url,
                full_size_url=loop_state.full_size_url,
                response=response,
            )

        return resolution_from_attempt(
            asset=asset,
            attempt=AssetDownloadAttempt(
                candidate=candidate,
                response=response,
                source_url=candidate_url,
            ),
            preview_url=loop_state.preview_url,
            full_size_url=loop_state.full_size_url,
            provenance=tuple(
                dict.fromkeys(
                    [
                        *(
                            ["conversion_degraded"]
                            if loop_state.conversion_degraded
                            else []
                        ),
                        *preview_fallback_provenance(
                            candidate_url,
                            preview_url=loop_state.preview_url,
                            full_size_url=loop_state.full_size_url,
                            full_size_access_failed=loop_state.full_size_access_failed,
                        ),
                    ]
                )
            ),
        )

    return resolution_from_attempt(
        asset=asset,
        attempt=loop_state.last_attempt,
        preview_url=loop_state.preview_url,
        full_size_url=loop_state.full_size_url,
        provenance=(("conversion_degraded",) if loop_state.conversion_degraded else ()),
    )


def _resolution_with_diagnostics(
    resolved: AssetDownloadResolution,
    *,
    candidate_resolution_seconds: float,
    route_diagnostics: Mapping[str, Any] | None = None,
) -> AssetDownloadResolution:
    if resolved.response is not None:
        timed = with_asset_timing(
            resolved.response, "candidate_resolution", candidate_resolution_seconds
        )
        if route_diagnostics:
            timed.route_diagnostics = {
                **timed.route_diagnostics,
                **dict(route_diagnostics),
            }
        return replace(resolved, response=timed)
    if resolved.failure is not None:
        failure_timing = dict(resolved.failure.timing)
        failure_timing["candidate_resolution"] = max(
            0.0, float(failure_timing.get("candidate_resolution", 0.0))
        ) + max(0.0, candidate_resolution_seconds)
        merged_route = (
            {**resolved.failure.route_diagnostics, **dict(route_diagnostics)}
            if route_diagnostics
            else dict(resolved.failure.route_diagnostics)
        )
        return replace(
            resolved,
            failure=replace(
                resolved.failure,
                timing=failure_timing,
                route_diagnostics=merged_route,
            ),
        )
    return resolved


def _browser_resolution_succeeded(
    resolved: AssetDownloadResolution,
    decision: AssetHostRouteDecision,
) -> bool:
    if resolved.response is None:
        return False
    if decision.route == "browser":
        return True
    final_fetcher = normalize_text(resolved.response.final_fetcher)
    browser_backend = normalize_text(resolved.response.browser_backend)
    return bool(browser_backend or (final_fetcher and final_fetcher != "direct_http"))


def _finalize_circuit_route_diagnostics(
    resolved: AssetDownloadResolution,
    *,
    circuit: AssetHostRecoveryCircuit | None,
    decision: AssetHostRouteDecision | None,
    candidate_seconds: float,
) -> AssetDownloadResolution:
    route_diagnostics: dict[str, Any] | None = None
    if circuit is not None and decision is not None:
        browser_succeeded = _browser_resolution_succeeded(resolved, decision)
        circuit.observe(
            decision,
            browser_recovery_succeeded=browser_succeeded,
        )
        route_diagnostics = {
            "host": decision.host,
            "route": "browser" if browser_succeeded else "direct",
            "probe": decision.probe,
            "reason": (
                "verified_browser_recovery_reused"
                if decision.route == "browser"
                else "direct_failure_browser_recovery_succeeded"
                if browser_succeeded
                else "first_asset_probe"
                if decision.probe
                else "direct_route_reused"
            ),
        }
        if browser_succeeded and resolved.response is not None:
            response = resolved.response.copy()
            if not normalize_text(response.final_fetcher):
                response.final_fetcher = (
                    normalize_text(response.browser_backend) or "selected_browser"
                )
            resolved = replace(resolved, response=response)

    return _resolution_with_diagnostics(
        resolved,
        candidate_resolution_seconds=candidate_seconds,
        route_diagnostics=route_diagnostics,
    )


def resolve_asset_download(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    *,
    options: AssetResolutionOptions,
) -> AssetDownloadResolution:
    """Resolve one asset with timed candidates and article-local host routing."""

    candidate_resolver = options.candidate_url_resolver or kind.candidate_url_resolver
    candidate_started_at = time.monotonic()
    candidate_urls = list(candidate_resolver(asset))
    candidate_seconds = time.monotonic() - candidate_started_at
    fallback_resolver = options.fallback_candidate_url_resolver

    def timed_fallback(current_asset: Mapping[str, Any]) -> list[str]:
        nonlocal candidate_seconds
        started = time.monotonic()
        try:
            return list(fallback_resolver(current_asset)) if fallback_resolver else []
        finally:
            candidate_seconds += time.monotonic() - started

    prepared_options = replace(
        options,
        candidate_url_resolver=lambda _asset: list(candidate_urls),
        fallback_candidate_url_resolver=timed_fallback if fallback_resolver else None,
    )
    preview_url, full_size_url = _resolution_preview_fields(kind, asset, candidate_urls)

    decision: AssetHostRouteDecision | None = None
    circuit = options.host_recovery_circuit
    if (
        circuit is not None
        and options.request.fetch_policy == "direct_then_browser"
        and options.document_fetcher is not None
    ):
        circuit_candidate = next(
            (
                candidate
                for candidate in candidate_urls
                if urllib.parse.urlparse(candidate).scheme in {"http", "https"}
                and should_use_document_fetcher_for_candidate(
                    kind,
                    candidate,
                    options.document_fetcher,
                )
            ),
            "",
        )
        if circuit_candidate:
            decision = circuit.begin(circuit_candidate)
            if decision.route in {"browser", "pending_browser"}:
                if options.defer_browser_to_caller_thread:
                    return AssetDownloadResolution(
                        asset=dict(asset),
                        preview_url=preview_url,
                        full_size_url=full_size_url,
                        deferred_browser=AssetDeferredBrowserWork(
                            candidate_urls=tuple(candidate_urls),
                            candidate_index=0,
                            candidate_seconds=candidate_seconds,
                            decision=decision,
                        ),
                    )
                if decision.route == "browser":
                    prepared_options = replace(
                        prepared_options,
                        request=replace(
                            prepared_options.request,
                            fetch_policy="browser_first",
                        ),
                    )

    loop_state = CandidateResolutionLoopState(
        kind=kind,
        asset=asset,
        preview_url=preview_url,
        full_size_url=full_size_url,
    )
    try:
        outcome = _resolve_candidate_loop(
            kind,
            asset,
            initial_candidates=candidate_urls,
            options=prepared_options,
            loop_state=loop_state,
        )
    except BaseException:
        if circuit is not None and decision is not None:
            circuit.abandon(decision)
        raise

    if isinstance(outcome, _DeferredCandidatePause):
        if circuit is not None and decision is not None:
            circuit.defer_to_browser(decision)
        direct_timing = (
            dict(outcome.direct_attempt.failure.timing)
            if outcome.direct_attempt.failure is not None
            else {}
        )
        return AssetDownloadResolution(
            asset=dict(asset),
            preview_url=loop_state.preview_url,
            full_size_url=loop_state.full_size_url,
            deferred_browser=AssetDeferredBrowserWork(
                candidate_urls=outcome.candidate_urls,
                candidate_index=outcome.candidate_index,
                candidate_seconds=candidate_seconds,
                direct_attempt=outcome.direct_attempt,
                decision=decision,
                conversion_degraded=outcome.conversion_degraded,
                full_size_access_failed=outcome.full_size_access_failed,
                timing=direct_timing,
            ),
        )

    return _finalize_circuit_route_diagnostics(
        outcome,
        circuit=circuit,
        decision=decision,
        candidate_seconds=candidate_seconds,
    )


def _resume_deferred_browser_resolution(
    kind: AssetDownloadKind,
    deferred_resolution: AssetDownloadResolution,
    *,
    options: AssetResolutionOptions,
) -> AssetDownloadResolution:
    """Execute Stage 2 caller-thread browser recovery for a deferred Stage 1 item."""

    deferred = deferred_resolution.deferred_browser
    assert deferred is not None
    asset = deferred_resolution.asset
    candidate_urls = list(deferred.candidate_urls)
    candidate_seconds = deferred.candidate_seconds
    fallback_resolver = options.fallback_candidate_url_resolver

    def timed_fallback(current_asset: Mapping[str, Any]) -> list[str]:
        nonlocal candidate_seconds
        started = time.monotonic()
        try:
            return list(fallback_resolver(current_asset)) if fallback_resolver else []
        finally:
            candidate_seconds += time.monotonic() - started

    caller_options = replace(
        options,
        defer_browser_to_caller_thread=False,
        fallback_candidate_url_resolver=(
            timed_fallback
            if fallback_resolver is not None
            and deferred.candidate_index < len(candidate_urls)
            else None
        ),
    )
    circuit = caller_options.host_recovery_circuit
    decision = deferred.decision

    try:
        if deferred.direct_attempt is not None:
            loop_state = CandidateResolutionLoopState(
                kind=kind,
                asset=asset,
                preview_url=deferred_resolution.preview_url,
                full_size_url=deferred_resolution.full_size_url,
                last_attempt=deferred.direct_attempt,
                conversion_degraded=deferred.conversion_degraded,
                full_size_access_failed=deferred.full_size_access_failed,
            )
            current_url = candidate_urls[deferred.candidate_index]
            current_candidate = AssetDownloadCandidate(current_url)
            recovery = recover_failed_candidate(
                kind,
                asset,
                current_candidate,
                transport=caller_options.transport,
                request_context=caller_options.request.for_asset(kind, asset),
                document_fetcher=caller_options.document_fetcher,
                last_attempt=deferred.direct_attempt,
                preview_url=loop_state.preview_url,
                full_size_url=loop_state.full_size_url,
                recovery_allowed=True,
            )
            resolved = loop_state.apply(recovery, current_candidate)
            if resolved is None:
                outcome = _resolve_candidate_loop(
                    kind,
                    asset,
                    initial_candidates=candidate_urls,
                    start_index=deferred.candidate_index + 1,
                    options=caller_options,
                    loop_state=loop_state,
                )
                assert isinstance(outcome, AssetDownloadResolution)
                resolved = outcome
            return _finalize_circuit_route_diagnostics(
                resolved,
                circuit=circuit,
                decision=decision,
                candidate_seconds=candidate_seconds,
            )

        verified_browser = bool(
            decision is not None
            and (
                decision.route == "browser"
                or (
                    circuit is not None
                    and circuit.route_for_url(f"https://{decision.host}/") == "browser"
                )
            )
        )
        effective_decision = (
            AssetHostRouteDecision(
                host=decision.host,
                route="browser" if verified_browser else "direct",
                probe=False,
            )
            if decision is not None
            else None
        )
        effective_options = (
            replace(
                caller_options,
                request=replace(
                    caller_options.request,
                    fetch_policy="browser_first",
                ),
            )
            if verified_browser
            else caller_options
        )
        loop_state = CandidateResolutionLoopState(
            kind=kind,
            asset=asset,
            preview_url=deferred_resolution.preview_url,
            full_size_url=deferred_resolution.full_size_url,
            conversion_degraded=deferred.conversion_degraded,
            full_size_access_failed=deferred.full_size_access_failed,
        )
        outcome = _resolve_candidate_loop(
            kind,
            asset,
            initial_candidates=candidate_urls,
            start_index=deferred.candidate_index,
            options=effective_options,
            loop_state=loop_state,
        )
        assert isinstance(outcome, AssetDownloadResolution)
        return _finalize_circuit_route_diagnostics(
            outcome,
            circuit=circuit,
            decision=effective_decision,
            candidate_seconds=candidate_seconds,
        )
    except BaseException:
        if circuit is not None and decision is not None:
            circuit.abandon(decision)
        raise


def _asset_items_for_kind(
    kind: AssetDownloadKind,
    assets: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    items = [dict(asset) for asset in assets]
    if kind.name == "supplementary":
        return [asset for asset in items if html_asset_is_supplementary(asset)]
    return items


def asset_work_key(kind: AssetDownloadKind, asset: Mapping[str, Any]) -> str:
    """Stable logical-file admission key, shared with bounded provider schedulers."""

    return "|".join(
        (
            kind.name,
            normalize_text(str(asset.get("source_ref") or "")),
            normalize_text(
                str(
                    asset.get("original_url")
                    or asset.get("url")
                    or asset.get("link")
                    or asset.get("filename_hint")
                    or ""
                )
            ),
            normalize_text(str(asset.get("heading") or "")),
        )
    )


def download_assets(
    kind: AssetDownloadKind,
    transport: HttpTransport,
    *,
    article_id: str,
    assets: Sequence[Mapping[str, Any]],
    output_dir: Path | None,
    user_agent: str,
    asset_profile: AssetProfile | None = "all",
    options: AssetDownloadOptions | None = None,
) -> dict[str, list[dict[str, Any]]]:
    if output_dir is None or not assets:
        return empty_asset_results()
    active_options = options or AssetDownloadOptions()
    figure_page_fetcher = (
        None
        if active_options.fetch_policy == "browser_only"
        else active_options.figure_page_fetcher
    )
    provider_name = active_options.provider_name
    runtime_context = active_options.runtime_context

    asset_execution_policy = None
    if provider_name:
        with contextlib.suppress(ValueError):
            asset_execution_policy = (
                compile_route_execution_policy(provider_name, active_options.route_name)
                if active_options.route_name
                else compile_route_execution_policy_for_kind(provider_name, "assets")
            )
    asset_route_name = (
        asset_execution_policy.route if asset_execution_policy is not None else None
    )

    active_asset_profile = effective_route_asset_scope(
        asset_profile,
        provider_name=provider_name,
        route_name=asset_route_name,
    )
    if kind.name == "figure" and active_asset_profile == "none":
        return empty_asset_results()
    if kind.name == "supplementary" and active_asset_profile != "all":
        return empty_asset_results()

    asset_items = _asset_items_for_kind(kind, assets)
    if not asset_items:
        return empty_asset_results()

    asset_dir = output_dir / f"{sanitize_filename(article_id)}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    route_concurrency_cap = active_options.route_concurrency_cap
    if route_concurrency_cap is None and asset_execution_policy is not None:
        route_concurrency_cap = asset_execution_policy.asset_concurrency_cap
    runtime_budget = (
        getattr(runtime_context, "asset_budget", None)
        if runtime_context is not None
        else None
    )
    active_budget = (
        active_options.asset_budget
        or runtime_budget
        or current_asset_budget()
        or AssetBudget(route_concurrency_cap=route_concurrency_cap)
    )
    artifact_store = active_options.artifact_store
    if artifact_store is None and runtime_context is not None:
        artifact_store = getattr(runtime_context, "artifact_store", None)

    work_keys = [asset_work_key(kind, asset) for asset in asset_items]
    admitted = active_budget.admit_work(work_keys)
    rejected_failures = [
        {
            **kind.failure_template(
                asset,
                normalize_text(
                    str(asset.get("original_url") or asset.get("url") or "")
                ),
                reason=ASSET_FILE_LIMIT_EXCEEDED,
            ),
            "max_files": active_budget.max_files,
            "asset_timing": empty_asset_timing(status="failed"),
        }
        for asset, is_admitted in zip(asset_items, admitted, strict=True)
        if not is_admitted
    ]
    admitted_pairs = [
        (asset, work_key)
        for asset, work_key, is_admitted in zip(
            asset_items, work_keys, admitted, strict=True
        )
        if is_admitted
    ]
    if not admitted_pairs:
        return {"assets": [], "asset_failures": rejected_failures}
    asset_items = [pair[0] for pair in admitted_pairs]
    admitted_work_keys = [pair[1] for pair in admitted_pairs]

    used_names_by_dir: dict[Path, set[str]] = {}
    browser_cookies = tuple(
        dict(cookie)
        for cookie in (
            (active_options.browser_context_seed or {}).get("browser_cookies") or []
        )
        if isinstance(cookie, Mapping)
    )
    normalized_allowed_hosts = tuple(active_options.allowed_hosts or ()) or None
    active_document_fetcher = active_options.document_fetcher
    if active_document_fetcher is None:
        active_document_fetcher = (
            active_options.image_document_fetcher
            if kind.file_document_fetcher_kind == "image"
            else active_options.file_document_fetcher
        )
    caller_thread_browser = requires_caller_thread(active_document_fetcher)
    two_stage_caller_thread_recovery = (
        caller_thread_browser and active_options.fetch_policy == "direct_then_browser"
    )

    active_host_recovery_circuit = active_options.host_recovery_circuit
    if active_host_recovery_circuit is None and active_document_fetcher is not None:
        cache_key = (
            "asset_download",
            "host_recovery",
            normalize_text(str(provider_name or "")),
            normalize_text(article_id),
        )
        get_or_set_session_cache = getattr(
            runtime_context, "get_or_set_session_cache", None
        )
        if callable(get_or_set_session_cache):
            active_host_recovery_circuit = get_or_set_session_cache(
                cache_key,
                AssetHostRecoveryCircuit,
                copy_value=False,
            )
        else:
            active_host_recovery_circuit = AssetHostRecoveryCircuit()

    active_candidate_builder = (
        active_options.candidate_builder or figure_download_candidates
    )

    def candidate_url_resolver(asset: Mapping[str, Any]) -> list[str]:
        if kind.name != "figure":
            return kind.candidate_url_resolver(asset)
        if active_options.fetch_policy == "browser_only":
            asset = {
                key: value for key, value in asset.items() if key != "figure_page_url"
            }
        return active_candidate_builder(
            transport,
            asset=asset,
            user_agent=user_agent,
            figure_page_fetcher=figure_page_fetcher,
        )

    def fallback_candidate_url_resolver(asset: Mapping[str, Any]) -> list[str]:
        builder = active_options.fallback_candidate_builder
        return (
            builder(
                transport,
                asset=asset,
                user_agent=user_agent,
                figure_page_fetcher=figure_page_fetcher,
            )
            if builder is not None
            else []
        )

    # Each discovery/download pass has its own scope; source retries do not
    # accumulate totals from a previous pass. Identity is independent of attempts.
    scope = f"{article_id}:{kind.name}:{uuid4()}"
    identities = [
        html_asset_identity_key(asset) or admitted_work_keys[index]
        for index, asset in enumerate(asset_items)
    ]
    categories = [
        value
        if (value := str(asset.get("kind") or kind.name))
        in {"figure", "formula", "table", "supplementary"}
        else kind.name
        for asset in asset_items
    ]
    finished: dict[str, bool] = {}

    def report_assets(index: int | None = None, succeeded: bool = False) -> None:
        if index is not None:
            finished[identities[index]] = succeeded
        if runtime_context is None:
            return
        counts = []
        for category in dict.fromkeys(categories):
            keys = {
                key
                for key, group in zip(identities, categories, strict=True)
                if group == category
            }
            counts.append(
                {
                    "kind": category,
                    "total": len(keys),
                    "completed": len(keys & finished.keys()),
                    "failed": sum(not finished[key] for key in keys & finished.keys()),
                }
            )
        runtime_context.report_progress("assets", scope=scope, counts=counts)

    if runtime_context is not None:
        runtime_context.raise_if_cancelled()
        runtime_context.report_progress("stage", stage="assets")
    report_assets()

    request_context = AssetRequestContext(
        headers=active_options.headers,
        candidate_headers_filter=active_options.candidate_headers_filter,
        sensitive_headers=active_options.sensitive_headers,
        user_agent=user_agent,
        browser_context_seed=active_options.browser_context_seed,
        browser_cookies=browser_cookies,
        fetch_policy=active_options.fetch_policy,
        asset_budget=active_budget,
        staging_dir=asset_dir,
        allowed_hosts=normalized_allowed_hosts,
        provider_name=provider_name,
        route_name=asset_route_name,
        path_converter=_active_path_converter,
    )
    resolution_options = AssetResolutionOptions(
        transport=transport,
        request=request_context,
        document_fetcher=active_document_fetcher,
        candidate_url_resolver=candidate_url_resolver,
        fallback_candidate_url_resolver=(
            fallback_candidate_url_resolver
            if kind.name == "figure"
            and active_options.fallback_candidate_builder is not None
            else None
        ),
        host_recovery_circuit=active_host_recovery_circuit,
        defer_browser_to_caller_thread=two_stage_caller_thread_recovery,
    )

    effective_concurrency = (
        1
        if caller_thread_browser and not two_stage_caller_thread_recovery
        else active_options.asset_download_concurrency
    )

    collected = resolve_and_collect_downloads_as_completed(
        asset_items,
        completion_callback=report_assets,
        resolver=lambda asset: resolve_asset_download(
            kind,
            asset,
            options=resolution_options,
        ),
        caller_thread_resolver=(
            (
                lambda deferred_res: _resume_deferred_browser_resolution(
                    kind,
                    deferred_res,
                    options=resolution_options,
                )
            )
            if two_stage_caller_thread_recovery
            else None
        ),
        asset_download_concurrency=effective_concurrency,
        force_worker_thread=(
            kind.name == "figure"
            and active_document_fetcher is not None
            and not caller_thread_browser
        ),
        saver=lambda resolved: save_asset_resolution(
            kind,
            resolved,
            asset_dir=asset_dir,
            used_names_by_dir=used_names_by_dir,
            artifact_store=artifact_store,
        ),
        asset_budget=active_budget,
        route_concurrency_cap=route_concurrency_cap,
        terminal_failure_factory=lambda asset, diagnostic: {
            **kind.failure_template(
                asset,
                normalize_text(
                    str(asset.get("original_url") or asset.get("url") or "")
                ),
                reason=normalize_text(str(diagnostic.get("reason") or ""))
                or ASSET_CANCELLED,
            ),
            **dict(diagnostic),
        },
    )
    collected["asset_failures"].extend(rejected_failures)
    return collected


__all__ = [
    "FIGURE_KIND",
    "SUPPLEMENTARY_BLOCKING_BODY_TOKENS",
    "SUPPLEMENTARY_BLOCKING_TITLE_TOKENS",
    "SUPPLEMENTARY_KIND",
    "_CLOUDFLARE_CHALLENGE_TOKENS",
    "AssetDownloadOptions",
    "AssetFetchPolicy",
    "AssetResolutionOptions",
    "FileDocumentFetcher",
    "ImageDocumentFetcher",
    "asset_work_key",
    "browser_asset_recovery_allowed",
    "download_assets",
    "resolve_asset_download",
    "save_asset_resolution",
]
