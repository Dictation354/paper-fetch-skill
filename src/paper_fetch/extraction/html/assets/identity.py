"""Asset identity and scope helpers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from collections.abc import Mapping

from ....models import normalize_text


def html_asset_identity_key(asset: Mapping[str, Any]) -> str:
    for field in (
        "figure_page_url",
        "original_url",
        "download_url",
        "full_size_url",
        "preview_url",
        "url",
        "source_url",
        "path",
    ):
        candidate = normalize_text(str(asset.get(field) or ""))
        if candidate:
            return candidate
    return ""


def html_asset_is_supplementary(asset: Mapping[str, Any]) -> bool:
    kind = normalize_text(
        str(asset.get("kind") or asset.get("asset_type") or "")
    ).lower()
    section = normalize_text(str(asset.get("section") or "")).lower()
    return kind == "supplementary" or section == "supplementary"


def merge_extracted_and_downloaded_assets(
    extracted_assets: Sequence[Mapping[str, Any]] | None,
    downloaded_assets: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Merge by identity while letting downloaded fields override extraction."""

    merged: list[dict[str, Any]] = []
    by_identity: dict[str, dict[str, Any]] = {}
    for item in extracted_assets or ():
        asset = dict(item)
        merged.append(asset)
        identity = html_asset_identity_key(asset)
        if identity:
            by_identity[identity] = asset
    for item in downloaded_assets or ():
        asset = dict(item)
        identity = html_asset_identity_key(asset)
        existing = by_identity.get(identity) if identity else None
        if existing is not None:
            existing.update(asset)
            continue
        merged.append(asset)
        if identity:
            by_identity[identity] = asset
    return merged


def filter_assets_for_profile(
    assets: Sequence[Mapping[str, Any]] | None,
    *,
    asset_profile: str,
) -> list[dict[str, Any]]:
    if asset_profile == "none":
        return []
    return [
        dict(item)
        for item in assets or ()
        if asset_profile == "all" or not html_asset_is_supplementary(item)
    ]


def split_body_and_supplementary_assets(
    assets: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    body_assets: list[dict[str, Any]] = []
    supplementary_assets: list[dict[str, Any]] = []
    for item in assets or []:
        asset = dict(item)
        if html_asset_is_supplementary(asset):
            supplementary_assets.append(asset)
        else:
            body_assets.append(asset)
    return body_assets, supplementary_assets


__all__ = [
    "filter_assets_for_profile",
    "html_asset_identity_key",
    "html_asset_is_supplementary",
    "merge_extracted_and_downloaded_assets",
    "split_body_and_supplementary_assets",
]
