"""Asset helpers for provider browser workflows."""

from __future__ import annotations

from typing import Any
from collections.abc import Callable, Mapping

from ...extraction.html.assets import (
    browser_asset_recovery_allowed,
    extract_full_size_figure_image_url,
    extract_scoped_html_assets,
    html_asset_identity_key,
    looks_like_full_size_asset_url,
)
from ...utils import dedupe_normalized, normalize_text
from .._asset_retry import (
    AssetRetryPolicy,
    assets_for_network_retry,
    is_retryable_asset_failure,
    merge_asset_failures,
    merge_asset_retry_results,
)
from .._atypon_browser_workflow_profiles import publisher_profile
from . import html_extraction as _html_extraction


def _cached_browser_workflow_assets(*args, **kwargs):
    client = args[0] if args else None
    provider_name = normalize_text(getattr(client, "name", "")).lower()
    profile = publisher_profile(provider_name)
    kwargs.setdefault(
        "scoped_asset_extractor",
        profile.scoped_asset_extractor or extract_scoped_html_assets,
    )
    return _html_extraction._cached_browser_workflow_assets(*args, **kwargs)


def _download_asset_result_key(asset: Mapping[str, Any]) -> str:
    key = normalize_text(html_asset_identity_key(asset))
    if key:
        return key
    parts = [
        normalize_text(str(asset.get("kind") or "")),
        normalize_text(str(asset.get("heading") or "")),
        normalize_text(str(asset.get("caption") or "")),
        normalize_text(str(asset.get("download_url") or "")),
        normalize_text(str(asset.get("source_url") or "")),
    ]
    return "|".join(part for part in parts if part)


def _browser_workflow_asset_retry_key(asset: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        _download_asset_retry_scope(asset),
        _download_asset_result_key(asset),
    )


def _download_asset_match_tokens(asset: Mapping[str, Any]) -> set[str]:
    tokens = {
        normalize_text(str(asset.get(field) or ""))
        for field in (
            "heading",
            "caption",
            "url",
            "download_url",
            "original_url",
            "source_url",
            "figure_page_url",
        )
    }
    return {token for token in tokens if token}


def _download_asset_retry_scope(asset: Mapping[str, Any]) -> str:
    kind = normalize_text(
        str(asset.get("kind") or asset.get("asset_type") or "")
    ).lower()
    section = normalize_text(str(asset.get("section") or "")).lower()
    if kind == "supplementary" or section == "supplementary":
        return "supplementary"
    return "body"


def _download_failure_match_tokens(failure: Mapping[str, Any]) -> set[str]:
    tokens = {
        normalize_text(str(failure.get(field) or ""))
        for field in (
            "heading",
            "caption",
            "url",
            "download_url",
            "original_url",
            "source_url",
            "figure_page_url",
        )
    }
    return {token for token in tokens if token}


_BROWSER_WORKFLOW_RETRYABLE_ASSET_REASON_TOKENS = (
    "browser_context_error",
    "cloudflare_challenge",
    "file_fetch_error",
    "image_fetch_error",
    "image_fetch_timeout",
)
_BROWSER_WORKFLOW_RETRYABLE_ASSET_STATUSES = frozenset({403, 408, 425, 429})


def _browser_workflow_retryable_asset_status(status: Any) -> bool:
    try:
        parsed = int(status)
    except (TypeError, ValueError):
        return False
    return parsed in _BROWSER_WORKFLOW_RETRYABLE_ASSET_STATUSES or 500 <= parsed < 600


def _browser_workflow_retryable_asset_failure(failure: Mapping[str, Any]) -> bool:
    diagnostic = failure.get("diagnostic")
    details = diagnostic if isinstance(diagnostic, Mapping) else {}
    status_value = failure.get("status", failure.get("status_code"))
    if status_value is None:
        status_value = details.get("status", details.get("status_code"))
    try:
        status = int(status_value) if status_value is not None else None
    except (TypeError, ValueError):
        status = None
    if status in {404, 410, 429}:
        return False
    content_type = normalize_text(
        str(failure.get("content_type") or details.get("content_type") or "")
    )
    reason = normalize_text(str(failure.get("reason") or details.get("reason") or ""))
    error_category = normalize_text(
        str(failure.get("error_category") or details.get("error_category") or "")
    )
    if browser_asset_recovery_allowed(
        status=status,
        content_type=content_type,
        reason=reason,
        error_category=error_category,
    ):
        return True
    if is_retryable_asset_failure(failure):
        return True
    if status is not None and not _browser_workflow_retryable_asset_status(status):
        return False
    reason = reason.lower()
    return bool(
        reason
        and any(
            token in reason for token in _BROWSER_WORKFLOW_RETRYABLE_ASSET_REASON_TOKENS
        )
    )


def _browser_workflow_asset_matches_failure(
    asset: Mapping[str, Any],
    failure: Mapping[str, Any],
) -> bool:
    if _download_asset_retry_scope(asset) != _download_asset_retry_scope(failure):
        return False
    asset_tokens = _download_asset_match_tokens(asset)
    failure_tokens = _download_failure_match_tokens(failure)
    return bool(asset_tokens and failure_tokens and asset_tokens & failure_tokens)


BROWSER_WORKFLOW_ASSET_RETRY_POLICY = AssetRetryPolicy(
    name="browser_workflow",
    key_fn=_browser_workflow_asset_retry_key,
    retryable_failure=_browser_workflow_retryable_asset_failure,
    failure_match=_browser_workflow_asset_matches_failure,
)


def _assets_matching_download_failures(
    assets: list[dict[str, Any]],
    failures: list[Mapping[str, Any]],
    *,
    retry_scope: str,
) -> list[dict[str, Any]]:
    return assets_for_network_retry(
        [
            asset
            for asset in assets
            if _download_asset_retry_scope(asset) == retry_scope
        ],
        [
            failure
            for failure in failures
            if _download_asset_retry_scope(failure) == retry_scope
        ],
        policy=BROWSER_WORKFLOW_ASSET_RETRY_POLICY,
    )


def _browser_workflow_image_download_candidates(
    _transport,
    *,
    asset: Mapping[str, Any],
    user_agent: str,
    figure_page_fetcher: Callable[[str], tuple[str, str] | None] | None = None,
) -> list[str]:
    del user_agent
    download_url = normalize_text(str(asset.get("download_url") or ""))
    direct_full_size_url = normalize_text(str(asset.get("full_size_url") or ""))
    primary_url = normalize_text(str(asset.get("url") or ""))
    preview_url = normalize_text(str(asset.get("preview_url") or "")) or primary_url
    candidates: list[str] = []

    if download_url:
        candidates.append(download_url)
    if direct_full_size_url:
        candidates.append(direct_full_size_url)

    figure_page_url = normalize_text(str(asset.get("figure_page_url") or ""))
    if figure_page_url and not direct_full_size_url and figure_page_fetcher is not None:
        try:
            page_result = figure_page_fetcher(figure_page_url)
        except Exception:
            page_result = None
        if page_result is not None:
            page_html, page_url = page_result
            full_size_url = extract_full_size_figure_image_url(page_html, page_url)
            if full_size_url:
                candidates.append(full_size_url)

    if primary_url and looks_like_full_size_asset_url(primary_url):
        candidates.append(primary_url)
    if preview_url:
        candidates.append(preview_url)

    return dedupe_normalized(candidates)


def _merge_download_attempt_results(
    initial: Mapping[str, Any],
    retry: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    merged_downloads = merge_asset_retry_results(
        list(initial.get("assets") or []),
        list(retry.get("assets") or []),
        policy=BROWSER_WORKFLOW_ASSET_RETRY_POLICY,
    )
    resolved_tokens = (
        set().union(
            *(_download_asset_match_tokens(asset) for asset in merged_downloads)
        )
        if merged_downloads
        else set()
    )
    failure_candidates = merge_asset_failures(
        list(initial.get("asset_failures") or []),
        list(retry.get("asset_failures") or []),
        policy=BROWSER_WORKFLOW_ASSET_RETRY_POLICY,
    )
    unresolved_failures = []
    for failure in failure_candidates:
        failure_tokens = _download_failure_match_tokens(failure)
        if failure_tokens and failure_tokens & resolved_tokens:
            continue
        unresolved_failures.append(dict(failure))

    return {
        "assets": merged_downloads,
        "asset_failures": unresolved_failures,
    }
