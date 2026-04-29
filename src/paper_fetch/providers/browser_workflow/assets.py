"""Asset helpers for provider browser workflows."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from ...extraction.html.assets import (
    extract_full_size_figure_image_url,
    extract_scoped_html_assets,
    html_asset_identity_key,
    looks_like_full_size_asset_url,
)
from ...utils import normalize_text
from .. import _browser_workflow_html_extraction as _html_extraction
from .. import _wiley_html


def _cached_browser_workflow_assets(*args, **kwargs):
    client = args[0] if args else None
    provider_name = normalize_text(getattr(client, "name", "")).lower()
    if provider_name == "wiley":
        kwargs.setdefault(
            "scoped_asset_extractor", _wiley_html.extract_scoped_html_assets
        )
    elif provider_name in {"science", "pnas"}:
        from ..science_pnas import asset_scopes as science_pnas_asset_scopes

        kwargs.setdefault(
            "scoped_asset_extractor",
            science_pnas_asset_scopes.extract_scoped_html_assets,
        )
    else:
        kwargs.setdefault("scoped_asset_extractor", extract_scoped_html_assets)
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


def _assets_matching_download_failures(
    assets: list[dict[str, Any]],
    failures: list[Mapping[str, Any]],
    *,
    retry_scope: str,
) -> list[dict[str, Any]]:
    failure_token_sets = [
        _download_failure_match_tokens(failure)
        for failure in failures
        if _download_asset_retry_scope(failure) == retry_scope
    ]
    failure_token_sets = [tokens for tokens in failure_token_sets if tokens]
    if not failure_token_sets:
        return []

    matched_assets: list[dict[str, Any]] = []
    for asset in assets:
        if _download_asset_retry_scope(asset) != retry_scope:
            continue
        asset_tokens = _download_asset_match_tokens(asset)
        if asset_tokens and any(asset_tokens & tokens for tokens in failure_token_sets):
            matched_assets.append(dict(asset))
    return matched_assets


def _browser_workflow_image_download_candidates(
    _transport,
    *,
    asset: Mapping[str, Any],
    user_agent: str,
    figure_page_fetcher: Callable[[str], tuple[str, str] | None] | None = None,
) -> list[str]:
    del user_agent
    direct_full_size_url = normalize_text(str(asset.get("full_size_url") or ""))
    primary_url = normalize_text(str(asset.get("url") or ""))
    preview_url = normalize_text(str(asset.get("preview_url") or "")) or primary_url
    candidates: list[str] = []

    if direct_full_size_url:
        candidates.append(direct_full_size_url)

    figure_page_url = normalize_text(str(asset.get("figure_page_url") or ""))
    if figure_page_url and figure_page_fetcher is not None:
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

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def _merge_download_attempt_results(
    initial: Mapping[str, Any],
    retry: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    downloads_by_key: dict[str, dict[str, Any]] = {}
    for result in (initial, retry):
        for asset in list(result.get("assets") or []):
            key = _download_asset_result_key(asset)
            downloads_by_key[key or str(len(downloads_by_key))] = dict(asset)

    merged_downloads = list(downloads_by_key.values())
    resolved_tokens = (
        set().union(
            *(_download_asset_match_tokens(asset) for asset in merged_downloads)
        )
        if merged_downloads
        else set()
    )
    failure_candidates = list(retry.get("asset_failures") or []) or list(
        initial.get("asset_failures") or []
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
