"""HTML extraction interfaces used outside provider modules."""

from __future__ import annotations

from ...publisher_identity import extract_doi as extract_doi_from_text
from .assets import FIGURE_KIND, download_assets, extract_html_assets
from ._metadata import merge_html_metadata, parse_html_metadata
from ._runtime import clean_markdown, decode_html, extract_article_markdown
from .landing import LandingHtmlFetchResult, fetch_landing_html
from .renderer import (
    HtmlMarkdownRenderer,
    RenderedHtmlFragment,
    clean_rendered_markdown,
    render_html_markdown,
    render_provider_html_fragment,
)
from .shared import (
    append_text_block,
    attr_text,
    class_tokens,
    direct_child_tags,
    html_text_snippet,
    html_title_snippet,
    image_magic_type,
    short_text,
    soup_root,
)


__all__ = [
    "FIGURE_KIND",
    "HtmlMarkdownRenderer",
    "LandingHtmlFetchResult",
    "RenderedHtmlFragment",
    "append_text_block",
    "attr_text",
    "class_tokens",
    "clean_markdown",
    "clean_rendered_markdown",
    "decode_html",
    "direct_child_tags",
    "download_assets",
    "extract_article_markdown",
    "extract_doi_from_text",
    "extract_html_assets",
    "fetch_landing_html",
    "html_text_snippet",
    "html_title_snippet",
    "image_magic_type",
    "merge_html_metadata",
    "parse_html_metadata",
    "render_html_markdown",
    "render_provider_html_fragment",
    "short_text",
    "soup_root",
]
