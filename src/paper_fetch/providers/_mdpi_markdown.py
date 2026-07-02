"""MDPI Markdown extraction helpers."""

from __future__ import annotations

import re
from typing import Any
from collections.abc import Mapping

from bs4 import BeautifulSoup, Tag

from ..extraction.html.parsing import choose_parser
from ..extraction.html.renderer import clean_rendered_markdown, render_html_markdown
from ..extraction.html.semantics import collect_html_section_hints
from ..extraction.html.shared import short_text
from ..extraction.html.signals import HtmlExtractionFailure
from ..extraction.markdown_render.figures import (
    INLINE_FIGURE_ALT_ATTR,
    INLINE_FIGURE_SRC_ATTR,
)
from ..quality.html_availability import (
    HtmlQualityAssessor,
    availability_failure_message,
)
from ..utils import normalize_text
from ._html_section_markdown import render_container_markdown
from ._mdpi_authors import extract_authors
from ._mdpi_dom import (
    MDPI_MARKDOWN_PROMO_TOKENS,
    MDPI_NOISE_PROFILE,
    _article_container_html,
    _mdpi_image_url,
)
from ._mdpi_references import (
    _remove_reference_ui_tokens,
    extract_keywords,
    extract_references,
)

_NOISY_MARKDOWN_LINES = {
    "browse figures",
    "download pdf",
    "download supplementary material",
    "download xml",
    "google scholar",
    "crossref",
    "pubmed",
    "share",
    "cite",
    "need help?",
}


def _inject_mdpi_inline_figure_sources(container: Tag, source_url: str) -> None:
    for figure in container.find_all("figure"):
        if not isinstance(figure, Tag):
            continue
        caption_node = figure.find("figcaption")
        caption = short_text(caption_node) if isinstance(caption_node, Tag) else ""
        for image in figure.find_all("img"):
            if not isinstance(image, Tag):
                continue
            image_url = _mdpi_image_url(image, source_url)
            if not image_url:
                continue
            image[INLINE_FIGURE_SRC_ATTR] = image_url
            image[INLINE_FIGURE_ALT_ATTR] = (
                caption or normalize_text(str(image.get("alt") or "Figure")) or "Figure"
            )


def _render_mdpi_article_markdown(article_html: str, source_url: str) -> str:
    soup = BeautifulSoup(article_html, choose_parser())
    article = soup.find("article")
    if not isinstance(article, Tag):
        return ""
    _inject_mdpi_inline_figure_sources(article, source_url)
    title_node = article.find("h1")
    title = short_text(title_node) if isinstance(title_node, Tag) else ""
    lines: list[str] = []
    render_container_markdown(
        article,
        lines,
        level=2,
        skip_first_heading=title or None,
        section_content_selectors=(),
    )
    return "\n".join(lines)


def _abstract_section_payload(abstract_text: str | None) -> list[dict[str, str]]:
    normalized = normalize_text(abstract_text)
    if not normalized:
        return []
    return [{"heading": "Abstract", "text": normalized}]


def _normalize_mdpi_markdown(markdown_text: str) -> str:
    blocks = re.split(r"\n\s*\n", markdown_text)
    kept: list[str] = []
    for block in blocks:
        normalized = normalize_text(block)
        lowered = normalized.lower()
        if not normalized:
            continue
        if lowered in _NOISY_MARKDOWN_LINES:
            continue
        if any(token in lowered for token in MDPI_MARKDOWN_PROMO_TOKENS):
            if len(normalized) < 220:
                continue
        kept.append(block.strip())
    text = "\n\n".join(kept)
    text = _remove_reference_ui_tokens(text)
    return clean_rendered_markdown(text, noise_profile=MDPI_NOISE_PROFILE)


def extract_markdown(
    html_text: str,
    source_url: str,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    keywords = extract_keywords(html_text)
    article_html, title, abstract_text, container_text_length = _article_container_html(
        html_text,
        metadata,
    )
    article_soup = BeautifulSoup(article_html, choose_parser())
    article = article_soup.find("article")
    if not isinstance(article, Tag):
        raise HtmlExtractionFailure(
            "article_container_not_found",
            "Could not identify the normalized MDPI article container.",
        )
    section_hints = collect_html_section_hints(article, title=title)
    markdown = render_html_markdown(
        article_html,
        source_url,
        trafilatura_backend=None,
        noise_profile=MDPI_NOISE_PROFILE,
        renderer=_render_mdpi_article_markdown,
    )
    if title and f"# {title}" not in markdown:
        markdown = f"# {title}\n\n{markdown}".strip()
    markdown = _normalize_mdpi_markdown(markdown)

    quality_metadata = dict(metadata or {})
    if title and not quality_metadata.get("title"):
        quality_metadata["title"] = title
    diagnostics = HtmlQualityAssessor("mdpi").assess(
        markdown,
        quality_metadata,
        html_text=article_html,
        title=title,
        final_url=source_url,
        container_tag="article",
        container_text_length=container_text_length,
        section_hints=section_hints,
    )
    if not diagnostics.accepted:
        raise HtmlExtractionFailure(
            diagnostics.reason,
            availability_failure_message(diagnostics),
        )

    extraction_payload = {
        "title": title,
        "abstract_text": abstract_text,
        "abstract_sections": _abstract_section_payload(abstract_text),
        "section_hints": section_hints,
        "container_tag": "article",
        "container_text_length": container_text_length,
        "availability_diagnostics": diagnostics.to_dict(),
        "extracted_authors": extract_authors(html_text),
        "keywords": keywords,
        "references": extract_references(html_text),
    }
    return markdown, extraction_payload


__all__ = [
    "_normalize_mdpi_markdown",
    "extract_markdown",
]
