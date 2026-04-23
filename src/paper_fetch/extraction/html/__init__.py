"""HTML extraction interfaces used outside provider modules."""

from __future__ import annotations

from ...publisher_identity import extract_doi as extract_doi_from_text
from ._assets import download_figure_assets, extract_html_assets
from ._metadata import merge_html_metadata, parse_html_metadata
from ._runtime import clean_markdown, decode_html, extract_article_markdown


__all__ = [
    "clean_markdown",
    "decode_html",
    "download_figure_assets",
    "extract_article_markdown",
    "extract_doi_from_text",
    "extract_html_assets",
    "merge_html_metadata",
    "parse_html_metadata",
]
