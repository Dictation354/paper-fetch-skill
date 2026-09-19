"""Springer Markdown extraction helpers."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup
from ..extraction.html.parsing import choose_parser

from ..extraction.html._runtime import clean_markdown
from ..extraction.html.figure_links import inject_inline_figure_links
from ..extraction.html.renderer import render_html_markdown
from .html_springer_nature import extract_springer_nature_markdown
from ._springer_assets import extract_figure_assets
from ._springer_authors import extract_authors
from ._springer_dom import (
    _clean_springer_preview_markdown,
    _remove_springer_ai_alt_disclaimers as _remove_springer_ai_alt_disclaimers,
    extract_html_extraction_sidecars,
)
from ._html_references import (
    extract_numbered_references_from_soup,
    _reference_text,
    _reference_doi,
    _reference_year,
)


def extract_article_markdown(cleaned_html: str, source_url: str) -> str:
    def render_springer_html(html_text: str, active_source_url: str) -> str:
        return extract_springer_nature_markdown(html_text, active_source_url) or ""

    custom_markdown = render_html_markdown(
        cleaned_html,
        source_url,
        cleaned_html=True,
        renderer=render_springer_html,
    )
    markdown_text = custom_markdown or render_html_markdown(
        cleaned_html,
        source_url,
        cleaned_html=True,
    )
    return _inject_remote_figure_links(markdown_text, cleaned_html, source_url)


def _inject_remote_figure_links(
    markdown_text: str,
    cleaned_html: str,
    source_url: str,
) -> str:
    if not markdown_text:
        return markdown_text
    figure_assets = extract_figure_assets(cleaned_html, source_url)
    if not figure_assets:
        return markdown_text
    return inject_inline_figure_links(
        markdown_text,
        figure_assets=figure_assets,
        # Bare box/inline images have independent URLs and must not consume
        # the next numbered figure merely because they have no figure label.
        match_unlabeled_images_by_order=False,
        clean_markdown_fn=lambda value: clean_markdown(
            value,
            noise_profile="springer_nature",
        ),
    )


def extract_html_payload(
    html_text: str,
    source_url: str,
    *,
    title: str | None = None,
) -> dict[str, Any]:
    extraction_sidecars = extract_html_extraction_sidecars(
        html_text, source_url, title=title
    )
    markdown_text = _clean_springer_preview_markdown(
        extract_article_markdown(extraction_sidecars["cleaned_html"], source_url)
    )
    extracted_authors = extract_authors(html_text)
    reference_soup = BeautifulSoup(html_text, choose_parser())
    extracted_references = extract_numbered_references_from_soup(reference_soup)
    if not extracted_references:
        # Springer Classic uses an unnumbered author-date bibliography. Preserve
        # that list without inventing numeric callouts for its author-year cites.
        for node in reference_soup.select(".c-article-references__item"):
            raw = _reference_text(node)
            if raw:
                extracted_references.append(
                    {
                        "label": None,
                        "raw": raw,
                        "doi": _reference_doi(node),
                        "year": _reference_year(node, raw),
                    }
                )
    return {
        "markdown_text": markdown_text,
        "abstract_sections": list(extraction_sidecars["abstract_sections"]),
        "section_hints": list(extraction_sidecars["section_hints"]),
        "cleaned_html": extraction_sidecars["cleaned_html"],
        "extracted_authors": extracted_authors,
        "references": extracted_references,
    }


__all__ = [
    "_remove_springer_ai_alt_disclaimers",
    "clean_markdown",
    "extract_article_markdown",
    "extract_html_payload",
]
