"""Supplementary asset discovery and scoped asset extraction helpers."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any
from collections.abc import Mapping

from ....models.schema import AssetProfile
from ....utils import normalize_text
from ..parsing import choose_parser
from ..provider_rules import provider_supplementary_text_tokens
from .figures import extract_figure_assets
from .formulas import extract_formula_assets

from bs4 import BeautifulSoup, Tag

GENERIC_SUPPLEMENTARY_TEXT_TOKENS = (
    "supplementary",
    "supplemental",
    "supporting information",
    "supporting material",
)


GENERIC_SUPPLEMENTARY_FILE_SUFFIXES = (
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


def supplementary_text_tokens_for_profile(
    noise_profile: str | None = None,
) -> tuple[str, ...]:
    return (
        *GENERIC_SUPPLEMENTARY_TEXT_TOKENS,
        *(provider_supplementary_text_tokens(noise_profile) if noise_profile else ()),
    )


def supplementary_file_suffixes(
    *, extra_suffixes: tuple[str, ...] = ()
) -> tuple[str, ...]:
    return tuple(dict.fromkeys([*GENERIC_SUPPLEMENTARY_FILE_SUFFIXES, *extra_suffixes]))


def has_supplementary_file_suffix(
    url: str, *, extra_suffixes: tuple[str, ...] = ()
) -> bool:
    lowered_url = normalize_text(str(url or "")).lower()
    return any(
        token in lowered_url
        for token in supplementary_file_suffixes(extra_suffixes=extra_suffixes)
    )


def _supplementary_anchor_is_supported(
    anchor: Any, *, noise_profile: str | None = None
) -> bool:
    if not isinstance(anchor, Tag):
        return False

    href = normalize_text(str(anchor.get("href") or ""))
    if not href or href.startswith("#"):
        return False
    text = normalize_text(anchor.get_text(" ", strip=True)).lower()
    if any(
        token in text for token in supplementary_text_tokens_for_profile(noise_profile)
    ):
        return True
    lowered_href = href.lower()
    if "/article-supplement/" in lowered_href:
        return True
    return has_supplementary_file_suffix(lowered_href)


def _supplementary_asset_from_anchor(
    anchor: Any,
    source_url: str,
    *,
    noise_profile: str | None = None,
) -> dict[str, str] | None:
    if not isinstance(anchor, Tag):
        return None
    if not _supplementary_anchor_is_supported(anchor, noise_profile=noise_profile):
        return None

    href = normalize_text(str(anchor.get("href") or ""))
    heading = (
        normalize_text(anchor.get_text(" ", strip=True)) or "Supplementary Material"
    )
    heading = re.sub(
        r"\s*\(\s*download\s+pdf\s*\)\s*$", "", heading, flags=re.IGNORECASE
    )
    absolute_href = urllib.parse.urljoin(source_url, href)
    return {
        "kind": "supplementary",
        "heading": heading,
        "caption": "",
        "section": "supplementary",
        "url": absolute_href,
    }


def extract_supplementary_assets(
    html_text: str,
    source_url: str,
    *,
    noise_profile: str | None = None,
) -> list[dict[str, str]]:

    soup = BeautifulSoup(html_text, choose_parser())
    assets_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    for anchor in soup.find_all("a", href=True):
        asset = _supplementary_asset_from_anchor(
            anchor, source_url, noise_profile=noise_profile
        )
        if asset is None:
            continue
        url = normalize_text(asset.get("url") or "")
        key = (
            url or normalize_text(asset.get("heading") or ""),
            "supplementary",
            normalize_text(asset.get("heading") or ""),
        )
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
    noise_profile: str | None = None,
) -> list[dict[str, str]]:
    return extract_scoped_html_assets(
        html_text,
        source_url,
        asset_profile=asset_profile,
        supplementary_html_text=html_text,
        noise_profile=noise_profile,
    )


def _asset_url_candidates(asset: Mapping[str, Any]) -> set[str]:
    candidates: set[str] = set()
    for field in (
        "url",
        "preview_url",
        "full_size_url",
        "download_url",
        "original_url",
        "source_url",
    ):
        candidate = normalize_text(str(asset.get(field) or ""))
        if candidate:
            candidates.add(candidate)
    return candidates


def extract_scoped_html_assets(
    body_html_text: str,
    source_url: str,
    *,
    asset_profile: AssetProfile,
    supplementary_html_text: str | None = None,
    noise_profile: str | None = None,
) -> list[dict[str, str]]:
    formula_assets = extract_formula_assets(
        body_html_text,
        source_url,
        noise_profile=noise_profile,
    )
    formula_url_candidates = (
        set().union(*(_asset_url_candidates(asset) for asset in formula_assets))
        if formula_assets
        else set()
    )
    assets = [
        asset
        for asset in extract_figure_assets(body_html_text, source_url)
        if not (_asset_url_candidates(asset) & formula_url_candidates)
    ]
    assets.extend(formula_assets)
    if asset_profile == "all":
        supplementary_scope = (
            body_html_text
            if supplementary_html_text is None
            else supplementary_html_text
        )
        assets.extend(
            extract_supplementary_assets(
                supplementary_scope,
                source_url,
                noise_profile=noise_profile,
            )
        )
    return assets


__all__ = [
    "GENERIC_SUPPLEMENTARY_FILE_SUFFIXES",
    "GENERIC_SUPPLEMENTARY_TEXT_TOKENS",
    "extract_html_assets",
    "extract_scoped_html_assets",
    "extract_supplementary_assets",
    "has_supplementary_file_suffix",
    "supplementary_file_suffixes",
    "supplementary_text_tokens_for_profile",
]
