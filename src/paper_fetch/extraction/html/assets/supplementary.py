"""Supplementary asset discovery and scoped asset extraction helpers."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from ....models import AssetProfile, normalize_text
from ..parsing import choose_parser
from .figures import extract_figure_assets
from .formulas import extract_formula_assets

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None

SUPPLEMENTARY_TEXT_TOKENS = (
    "supplementary",
    "extended data",
    "source data",
    "peer review",
    "supporting information",
)


SUPPLEMENTARY_FILE_TOKENS = (
    ".pdf",
    ".csv",
    ".xlsx",
    ".xls",
    ".zip",
    ".txt",
    ".json",
    ".xml",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".tif",
    ".tiff",
)


def _supplementary_anchor_is_supported(anchor: Any) -> bool:
    if Tag is None or not isinstance(anchor, Tag):
        return False

    href = normalize_text(str(anchor.get("href") or ""))
    if not href or href.startswith("#"):
        return False
    text = normalize_text(anchor.get_text(" ", strip=True)).lower()
    data_test = normalize_text(str(anchor.get("data-test") or "")).lower()
    data_track_action = normalize_text(str(anchor.get("data-track-action") or "")).lower()
    if data_test == "supp-info-link" or data_track_action == "view supplementary info":
        return True
    if any(token in text for token in SUPPLEMENTARY_TEXT_TOKENS):
        return True
    lowered_href = href.lower()
    return any(token in lowered_href for token in SUPPLEMENTARY_FILE_TOKENS)


def _supplementary_asset_from_anchor(anchor: Any, source_url: str) -> dict[str, str] | None:
    if Tag is None or not isinstance(anchor, Tag):
        return None
    if not _supplementary_anchor_is_supported(anchor):
        return None

    href = normalize_text(str(anchor.get("href") or ""))
    heading = normalize_text(anchor.get_text(" ", strip=True)) or "Supplementary Material"
    heading = re.sub(r"\s*\(\s*download\s+pdf\s*\)\s*$", "", heading, flags=re.IGNORECASE)
    absolute_href = urllib.parse.urljoin(source_url, href)
    return {
        "kind": "supplementary",
        "heading": heading,
        "caption": "",
        "section": "supplementary",
        "url": absolute_href,
    }


def extract_supplementary_assets(html_text: str, source_url: str) -> list[dict[str, str]]:
    if BeautifulSoup is None:
        return []

    soup = BeautifulSoup(html_text, choose_parser())
    assets_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    for anchor in soup.find_all("a", href=True):
        asset = _supplementary_asset_from_anchor(anchor, source_url)
        if asset is None:
            continue
        url = normalize_text(asset.get("url") or "")
        key = (url or normalize_text(asset.get("heading") or ""), "supplementary", normalize_text(asset.get("heading") or ""))
        existing = assets_by_key.get(key)
        if existing is None:
            assets_by_key[key] = asset
            continue
        if url and not normalize_text(existing.get("url") or ""):
            existing["url"] = url
    return list(assets_by_key.values())


def extract_html_assets(
    html_text: str,
    source_url: str,
    *,
    asset_profile: AssetProfile,
) -> list[dict[str, str]]:
    return extract_scoped_html_assets(
        html_text,
        source_url,
        asset_profile=asset_profile,
        supplementary_html_text=html_text,
    )


def extract_scoped_html_assets(
    body_html_text: str,
    source_url: str,
    *,
    asset_profile: AssetProfile,
    supplementary_html_text: str | None = None,
) -> list[dict[str, str]]:
    assets = extract_figure_assets(body_html_text, source_url)
    assets.extend(extract_formula_assets(body_html_text, source_url))
    if asset_profile == "all":
        supplementary_scope = body_html_text if supplementary_html_text is None else supplementary_html_text
        assets.extend(extract_supplementary_assets(supplementary_scope, source_url))
    return assets


__all__ = [
    "SUPPLEMENTARY_TEXT_TOKENS",
    "SUPPLEMENTARY_FILE_TOKENS",
    "extract_supplementary_assets",
    "extract_html_assets",
    "extract_scoped_html_assets",
]
