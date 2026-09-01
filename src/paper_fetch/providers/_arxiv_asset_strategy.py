"""arXiv source-first figure download orchestration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..extraction.html import assets as html_assets
from ..http import HttpTransport
from ..models import AssetProfile
from ..reason_codes import (
    OFFICIAL_FULL_SIZE_ACCESS_RESTRICTED,
    OFFICIAL_FULL_SIZE_NOT_EXPOSED,
)
from ..runtime import RuntimeContext
from ..utils import normalize_text
from ._arxiv_assets import (
    ARXIV_ASSET_RETRY_POLICY,
    _arxiv_asset_download_concurrency,
    _arxiv_asset_matches_failure,
    _asset_has_download_candidate,
    download_arxiv_source_figure_assets,
)
from ._asset_retry import (
    assets_for_network_retry,
    merge_asset_failures,
    merge_asset_retry_results,
)


@dataclass(frozen=True)
class ArxivHtmlAssetDownloadPlan:
    arxiv_id: str
    article_id: str
    article_html: str
    source_url: str
    extracted_assets: Sequence[Mapping[str, Any]]
    output_dir: Path
    user_agent: str
    asset_profile: AssetProfile
    runtime_context: RuntimeContext
    image_headers: Mapping[str, str]


def _download_arxiv_source_assets(
    transport: HttpTransport,
    plan: ArxivHtmlAssetDownloadPlan,
    *,
    placeholders: Sequence[Mapping[str, Any]] | None = None,
    admit_placeholders: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    return download_arxiv_source_figure_assets(
        transport,
        arxiv_id=plan.arxiv_id,
        article_id=plan.article_id,
        article_html=plan.article_html,
        source_url=plan.source_url,
        output_dir=plan.output_dir,
        user_agent=plan.user_agent,
        runtime_context=plan.runtime_context,
        placeholders=placeholders,
        admit_placeholders=admit_placeholders,
    )


def _preview_fallback_assets(
    extracted_assets: Sequence[Mapping[str, Any]],
    source_failures: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    fallback_assets: list[dict[str, Any]] = []
    for extracted in extracted_assets:
        matching_failure = next(
            (
                failure
                for failure in source_failures
                if _arxiv_asset_matches_failure(extracted, failure)
            ),
            None,
        )
        if matching_failure is None:
            continue
        reason = normalize_text(str(matching_failure.get("reason") or ""))
        quality_reason = (
            OFFICIAL_FULL_SIZE_ACCESS_RESTRICTED
            if reason
            in {
                "arxiv_source_fetch_failed",
                "timeout",
                "publisher_access_denied",
            }
            or reason.startswith("asset_bytes_")
            else OFFICIAL_FULL_SIZE_NOT_EXPOSED
        )
        fallback = dict(extracted)
        fallback["provenance"] = list(
            dict.fromkeys(
                [
                    *list(fallback.get("provenance") or []),
                    quality_reason,
                ]
            )
        )
        fallback_assets.append(fallback)
    return fallback_assets


def download_arxiv_html_figure_assets(
    transport: HttpTransport,
    plan: ArxivHtmlAssetDownloadPlan,
) -> dict[str, list[dict[str, Any]]]:
    """Prefer official source figures, then retain an audited HTML preview fallback."""

    extracted_assets = [
        dict(item)
        for item in plan.extracted_assets
        if _asset_has_download_candidate(item)
    ]
    if not extracted_assets:
        return _download_arxiv_source_assets(transport, plan)

    source_result = _download_arxiv_source_assets(
        transport,
        plan,
        placeholders=extracted_assets,
        admit_placeholders=False,
    )
    fallback_assets = _preview_fallback_assets(
        extracted_assets,
        [dict(item) for item in source_result.get("asset_failures") or []],
    )
    if not fallback_assets:
        return source_result

    concurrency = _arxiv_asset_download_concurrency(plan.runtime_context.env)
    initial_result = html_assets.download_assets(
        html_assets.FIGURE_KIND,
        transport,
        article_id=plan.article_id,
        assets=fallback_assets,
        output_dir=plan.output_dir,
        user_agent=plan.user_agent,
        asset_profile=plan.asset_profile,
        options=html_assets.AssetDownloadOptions(
            headers=plan.image_headers,
            asset_download_concurrency=concurrency,
            provider_name="arxiv",
            runtime_context=plan.runtime_context,
        ),
    )
    retry_assets = assets_for_network_retry(
        fallback_assets,
        initial_result.get("asset_failures") or [],
        policy=ARXIV_ASSET_RETRY_POLICY,
    )
    if not retry_assets:
        return {
            "assets": [
                *list(source_result.get("assets") or []),
                *list(initial_result.get("assets") or []),
            ],
            "asset_failures": list(initial_result.get("asset_failures") or []),
        }

    retry_result = html_assets.download_assets(
        html_assets.FIGURE_KIND,
        transport,
        article_id=plan.article_id,
        assets=retry_assets,
        output_dir=plan.output_dir,
        user_agent=plan.user_agent,
        asset_profile=plan.asset_profile,
        options=html_assets.AssetDownloadOptions(
            headers=plan.image_headers,
            asset_download_concurrency=1,
            provider_name="arxiv",
            runtime_context=plan.runtime_context,
        ),
    )
    return {
        "assets": [
            *list(source_result.get("assets") or []),
            *merge_asset_retry_results(
                initial_result.get("assets") or [],
                retry_result.get("assets") or [],
                policy=ARXIV_ASSET_RETRY_POLICY,
            ),
        ],
        "asset_failures": merge_asset_failures(
            initial_result.get("asset_failures") or [],
            retry_result.get("asset_failures") or [],
            policy=ARXIV_ASSET_RETRY_POLICY,
            retried_assets=retry_assets,
        ),
    }
