"""Compatibility facade for MDPI provider HTML helpers."""

from __future__ import annotations

from typing import Any

from . import _mdpi_dom as _impl

from ._mdpi_authors import (
    extract_authors as extract_authors,
)

from ._mdpi_references import (
    extract_references as extract_references,
    extract_keywords as extract_keywords,
)

from ._mdpi_assets import (
    mark_inline_assets as mark_inline_assets,
    extract_pdf_urls as extract_pdf_urls,
    mdpi_pdf_url_from_landing_url as mdpi_pdf_url_from_landing_url,
    extract_asset_html_scopes as extract_asset_html_scopes,
    extract_scoped_html_assets as extract_scoped_html_assets,
)

from ._mdpi_markdown import (
    extract_markdown as extract_markdown,
    _normalize_mdpi_markdown as _normalize_mdpi_markdown,
)

from ._mdpi_dom import (
    MDPI_NOISE_PROFILE as MDPI_NOISE_PROFILE,
    MDPI_MARKDOWN_PROMO_TOKENS as MDPI_MARKDOWN_PROMO_TOKENS,
    MDPI_FRONT_MATTER_EXACT_TEXTS as MDPI_FRONT_MATTER_EXACT_TEXTS,
    MDPI_FRONT_MATTER_CONTAINS_TOKENS as MDPI_FRONT_MATTER_CONTAINS_TOKENS,
    MDPI_POST_CONTENT_BREAK_TOKENS as MDPI_POST_CONTENT_BREAK_TOKENS,
    MDPI_EXTRACTION_CLEANUP_SELECTORS as MDPI_EXTRACTION_CLEANUP_SELECTORS,
    MDPI_SUPPLEMENTARY_TEXT_TOKENS as MDPI_SUPPLEMENTARY_TEXT_TOKENS,
    MDPI_SITE_RULE_OVERRIDES as MDPI_SITE_RULE_OVERRIDES,
    _article_container_html as _article_container_html,
)


def __getattr__(name: str) -> Any:
    return getattr(_impl, name)


__all__ = [
    "MDPI_EXTRACTION_CLEANUP_SELECTORS",
    "MDPI_FRONT_MATTER_CONTAINS_TOKENS",
    "MDPI_FRONT_MATTER_EXACT_TEXTS",
    "MDPI_MARKDOWN_PROMO_TOKENS",
    "MDPI_NOISE_PROFILE",
    "MDPI_POST_CONTENT_BREAK_TOKENS",
    "MDPI_SITE_RULE_OVERRIDES",
    "MDPI_SUPPLEMENTARY_TEXT_TOKENS",
    "_article_container_html",
    "_normalize_mdpi_markdown",
    "extract_asset_html_scopes",
    "extract_authors",
    "extract_keywords",
    "extract_markdown",
    "extract_pdf_urls",
    "extract_references",
    "extract_scoped_html_assets",
    "mark_inline_assets",
    "mdpi_pdf_url_from_landing_url",
]
