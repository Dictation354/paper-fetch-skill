"""HTML extraction interfaces used outside provider modules."""

from __future__ import annotations

from ...publisher_identity import extract_doi as extract_doi_from_text
from ._assets import download_figure_assets, extract_html_assets
from ._metadata import merge_html_metadata, parse_html_metadata
from ._runtime import clean_markdown, decode_html, extract_article_markdown
from .landing import LandingHtmlFetchResult, fetch_landing_html
from .shared import (
    append_text_block,
    class_tokens,
    direct_child_tags,
    html_text_snippet,
    html_title_snippet,
    image_magic_type,
    short_text,
    soup_root,
)


__all__ = [
    "clean_markdown",
    "decode_html",
    "download_figure_assets",
    "extract_article_markdown",
    "extract_doi_from_text",
    "extract_html_assets",
    "fetch_landing_html",
    "append_text_block",
    "class_tokens",
    "direct_child_tags",
    "html_text_snippet",
    "html_title_snippet",
    "image_magic_type",
    "LandingHtmlFetchResult",
    "merge_html_metadata",
    "parse_html_metadata",
    "short_text",
    "soup_root",
]
