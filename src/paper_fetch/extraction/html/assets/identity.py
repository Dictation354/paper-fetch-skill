"""Asset identity and scope helpers."""

from __future__ import annotations

from typing import Any, Mapping

from ....models import normalize_text

def html_asset_identity_key(asset: Mapping[str, Any]) -> str:
    for field in ("figure_page_url", "original_url", "download_url", "full_size_url", "preview_url", "url", "source_url", "path"):
        candidate = normalize_text(str(asset.get(field) or ""))
        if candidate:
            return candidate
    return ""


def html_asset_is_supplementary(asset: Mapping[str, Any]) -> bool:
    kind = normalize_text(str(asset.get("kind") or asset.get("asset_type") or "")).lower()
    section = normalize_text(str(asset.get("section") or "")).lower()
    return kind == "supplementary" or section == "supplementary"


def split_body_and_supplementary_assets(
    assets: list[dict[str, Any]] | list[dict[str, str]],
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
    "html_asset_identity_key",
    "html_asset_is_supplementary",
    "split_body_and_supplementary_assets",
]
