"""IEEE direct-first asset recovery through the selected browser backend."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any
from collections.abc import Callable, Mapping

from ..extraction.html import decode_html
from ..extraction.html.assets.figures import figure_download_candidates
from ..http.headers import header_value
from ..publisher_identity import normalize_doi
from ..runtime import RuntimeContext
from ..utils import normalize_text
from ._ieee_metadata import IeeeLandingAttempt, _landing_metadata_has_multimedia_scope
from ._ieee_url import IEEE_BASE_URL, IEEE_MULTIMEDIA_URL_TEMPLATE
from .browser_runtime.types import BrowserRuntimeConfig
from .browser_workflow.asset_download import (
    BrowserAssetDownloadPlan,
    BrowserAssetRecoveryContext,
    download_browser_backed_related_assets,
)
from .browser_workflow.fetchers import _MemoizedImageDocumentFetcher
from .browser_workflow.shared import default_browser_workflow_deps


def download_ieee_assets_with_browser(
    *,
    transport: Any,
    article_id: str,
    output_dir: Path,
    asset_profile: str,
    body_assets: list[dict[str, Any]],
    supplementary_assets: list[dict[str, Any]],
    merged_metadata: Mapping[str, Any],
    article_number: str,
    canonical_landing_url: str,
    seed_urls: list[str],
    concurrency: int,
    user_agent: str,
    content: Any,
    browser_runtime_config: BrowserRuntimeConfig,
    runtime_context: RuntimeContext | None,
    download_assets_fn: Callable[..., Any],
    split_assets_fn: Callable[..., Any],
) -> dict[str, list[dict[str, Any]]]:
    from . import _ieee_supplementary as supplementary

    deps = replace(
        default_browser_workflow_deps(),
        download_assets=download_assets_fn,
        split_body_and_supplementary_assets=split_assets_fn,
    )
    seed = dict(content.browser_context_seed if content.browser_context_seed else {})
    discovery_failures: list[dict[str, Any]] = []
    if (
        asset_profile == "all"
        and article_number
        and _landing_metadata_has_multimedia_scope(merged_metadata)
    ):
        multimedia_url = IEEE_MULTIMEDIA_URL_TEMPLATE.format(
            article_number=article_number
        )
        discovery_attempt = IeeeLandingAttempt(
            normalized_doi=normalize_doi(article_id),
            landing_url=canonical_landing_url,
            response_url=canonical_landing_url,
            html_text="",
            merged_metadata=dict(merged_metadata),
            article_number=article_number,
            landing_metadata=dict(merged_metadata),
            browser_context_seed=seed,
        )
        discovered_assets = supplementary.fetch_ieee_multimedia_assets(
            transport,
            discovery_attempt,
            multimedia_url=multimedia_url,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": canonical_landing_url,
                "User-Agent": user_agent,
                "Origin": IEEE_BASE_URL,
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        if not discovered_assets:
            discovery_fetcher = deps._build_shared_browser_file_fetcher(
                browser_context_seed_getter=lambda: seed,
                seed_urls_getter=lambda: seed_urls,
                browser_user_agent=normalize_text(
                    str(seed.get("browser_user_agent") or "")
                )
                or None,
                headless=browser_runtime_config.headless,
                runtime_context=runtime_context,
                use_runtime_shared_browser=True,
                browser_config=browser_runtime_config,
                thread_local=False,
            )
            try:
                response = discovery_fetcher(
                    multimedia_url, {"referer_url": canonical_landing_url}
                )
                if response:
                    payload = json.loads(
                        decode_html(
                            bytes(response.get("body") or b""),
                            content_type=header_value(
                                response.get("headers"), "content-type"
                            ),
                        )
                    )
                    if isinstance(payload, Mapping):
                        discovered_assets = supplementary._supplementary_assets_from_ieee_multimedia_payload(
                            payload,
                            normalize_text(str(response.get("url") or ""))
                            or multimedia_url,
                        )
            except (TypeError, ValueError):
                discovered_assets = []
            finally:
                discovery_fetcher.close()
            if not discovered_assets:
                failure_for = getattr(discovery_fetcher, "failure_for", None)
                failure = failure_for(multimedia_url) if callable(failure_for) else None
                discovery_failures.append(
                    {
                        "kind": "supplementary",
                        "source_url": multimedia_url,
                        "reason": "multimedia_discovery_failed",
                        "diagnostic": {
                            "stage": "multimedia_discovery",
                            "browser_backend": browser_runtime_config.backend,
                            "browser_attempted": True,
                            **(dict(failure) if isinstance(failure, Mapping) else {}),
                        },
                    }
                )
        if discovered_assets:
            existing_keys = {
                supplementary._supplementary_asset_key(existing)
                for existing in supplementary_assets
            }
            supplementary_assets = [
                *supplementary_assets,
                *[
                    asset
                    for asset in discovered_assets
                    if supplementary._supplementary_asset_key(asset)
                    not in existing_keys
                ],
            ]

    if not body_assets and not supplementary_assets:
        return {"assets": [], "asset_failures": discovery_failures}

    plan = BrowserAssetDownloadPlan(
        article_id=article_id,
        output_dir=output_dir,
        asset_profile=asset_profile,
        body_assets=body_assets,
        supplementary_assets=supplementary_assets if asset_profile == "all" else [],
        fetch_policy="direct_then_browser",
        candidate_builder=figure_download_candidates,
    )
    recovery = BrowserAssetRecoveryContext(
        runtime=browser_runtime_config,
        provider="ieee",
        user_agent=user_agent,
        browser_context_seed=seed,
        browser_cookies=list(seed.get("browser_cookies") or []),
        active_seed_urls=seed_urls,
        runtime_context=runtime_context,
    )

    def image_fetcher_factory(**request: Any):
        if not request.get("attempt_body_assets"):
            return None
        fetcher = _MemoizedImageDocumentFetcher(
            deps._build_shared_browser_image_fetcher(
                browser_context_seed_getter=request["browser_context_seed_getter"],
                seed_urls_getter=request["seed_urls_getter"],
                browser_user_agent=request.get("browser_user_agent"),
                headless=request.get("headless", True),
                runtime_context=runtime_context,
                use_runtime_shared_browser=True,
                binary_path=request.get("binary_path"),
                cdp_endpoint=request.get("cdp_endpoint"),
                profile_dir=request.get("profile_dir"),
                user_data_dir=request.get("user_data_dir"),
                browser_config=request.get("browser_config"),
            )
        )
        fetcher.browser_backend = browser_runtime_config.backend
        return fetcher

    def file_fetcher_factory(**request: Any):
        if not request.get("attempt_supplementary_assets"):
            return None
        fetcher = deps._build_shared_browser_file_fetcher(
            browser_context_seed_getter=request["browser_context_seed_getter"],
            seed_urls_getter=request["seed_urls_getter"],
            browser_user_agent=request.get("browser_user_agent"),
            headless=request.get("headless", True),
            runtime_context=runtime_context,
            use_runtime_shared_browser=True,
            binary_path=request.get("binary_path"),
            cdp_endpoint=request.get("cdp_endpoint"),
            profile_dir=request.get("profile_dir"),
            user_data_dir=request.get("user_data_dir"),
            browser_config=request.get("browser_config"),
            thread_local=True,
        )
        fetcher.browser_backend = browser_runtime_config.backend
        return fetcher

    recovered = download_browser_backed_related_assets(
        plan,
        recovery,
        image_fetcher_factory=image_fetcher_factory,
        file_fetcher_factory=file_fetcher_factory,
        opener_requester={
            "transport": transport,
            "asset_download_concurrency": (
                1 if browser_runtime_config.backend == "camoufox" else concurrency
            ),
            "serial_browser_assets": browser_runtime_config.backend == "camoufox",
        },
        deps=deps,
    )
    recovered["asset_failures"] = [
        *list(recovered.get("asset_failures") or []),
        *discovery_failures,
    ]
    return recovered


__all__ = ["download_ieee_assets_with_browser"]
