"""Shared policy engine for provider HTML asset discovery."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Mapping

from ..extraction.html import assets as html_assets

AssetExtractor = Callable[[str, str], list[dict[str, str]]]
AssetFinalizer = Callable[[list[dict[str, str]]], list[dict[str, str]]]
SupplementaryScopeFallback = Literal["body", "empty"]


@dataclass(frozen=True)
class HtmlAssetExtractionPolicy:
    figure_extractor: AssetExtractor = html_assets.extract_figure_assets
    formula_extractor: AssetExtractor = html_assets.extract_formula_assets
    supplementary_extractor: AssetExtractor = html_assets.extract_supplementary_assets
    supplementary_scope_fallback: SupplementaryScopeFallback = "body"
    source_data_extractor: AssetExtractor | None = None
    finalizer: AssetFinalizer | None = None


def _scope_html(
    *,
    body_html_text: str,
    supplementary_html_text: str | None,
    fallback: SupplementaryScopeFallback,
) -> str:
    if supplementary_html_text is not None:
        return supplementary_html_text
    if fallback == "body":
        return body_html_text
    return ""


def extract_scoped_assets_with_policy(
    body_html_text: str,
    source_url: str,
    *,
    asset_profile: str,
    policy: HtmlAssetExtractionPolicy,
    supplementary_html_text: str | None = None,
    source_data_html_text: str | None = None,
) -> list[dict[str, str]]:
    assets = policy.figure_extractor(body_html_text, source_url)
    assets.extend(policy.formula_extractor(body_html_text, source_url))
    if asset_profile == "all":
        supplementary_scope = _scope_html(
            body_html_text=body_html_text,
            supplementary_html_text=supplementary_html_text,
            fallback=policy.supplementary_scope_fallback,
        )
        if supplementary_scope:
            assets.extend(policy.supplementary_extractor(supplementary_scope, source_url))
        if source_data_html_text and policy.source_data_extractor is not None:
            assets.extend(policy.source_data_extractor(source_data_html_text, source_url))
    if policy.finalizer is not None:
        return policy.finalizer(assets)
    return assets


def merge_assets_by_identity(
    assets: list[dict[str, str]],
    *,
    key_builder: Callable[[Mapping[str, Any]], str] = html_assets.html_asset_identity_key,
) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    by_key: dict[str, int] = {}
    for asset in assets:
        key = key_builder(asset)
        if not key:
            merged.append(dict(asset))
            continue
        existing_index = by_key.get(key)
        if existing_index is None:
            by_key[key] = len(merged)
            merged.append(dict(asset))
            continue
        existing = merged[existing_index]
        for field, value in asset.items():
            if value and not existing.get(field):
                existing[field] = value
    return merged
