"""PNAS provider-owned browser-workflow rules."""

from __future__ import annotations

import re
from functools import partial
from typing import Any, Mapping

from ..quality.html_profiles import (
    PNAS_NOISE_PROFILE,
    PNAS_SITE_RULE_OVERRIDES,
    pnas_blocking_fallback_signals,
    pnas_positive_signals,
)
from ._browser_workflow_authors import (
    AuthorExtractionPipeline,
    extract_meta_authors,
    extract_property_authors,
)
from ._html_references import extract_numbered_references_from_html

HOSTS: tuple[str, ...] = ("www.pnas.org", "pnas.org")
BASE_HOSTS: tuple[str, ...] = HOSTS
HTML_PATH_TEMPLATES: tuple[str, ...] = ("/doi/{doi}", "/doi/full/{doi}")
PDF_PATH_TEMPLATES: tuple[str, ...] = ("/doi/epdf/{doi}", "/doi/pdf/{doi}?download=true", "/doi/pdf/{doi}")
CROSSREF_PDF_POSITION = 0
NOISE_PROFILE = PNAS_NOISE_PROFILE
SITE_RULE_OVERRIDES: dict[str, Any] = PNAS_SITE_RULE_OVERRIDES
PNAS_AUTHOR_COUNT_PATTERN = re.compile(r"^\+\s*\d+\s+authors?$", flags=re.IGNORECASE)
PNAS_IGNORED_AUTHOR_TEXT = {
    "authors info & affiliations",
    "view all articles by this author",
    "expand all",
    "collapse all",
    "orcid",
}


def blocking_fallback_signals(html_text: str) -> list[str]:
    return pnas_blocking_fallback_signals(html_text)


def _extract_dom_authors(html_text: str) -> list[str]:
    return extract_property_authors(
        html_text,
        selectors=".contributors [property='author'], #tab-contributors [property='author']",
        ignored_text=PNAS_IGNORED_AUTHOR_TEXT,
        count_pattern=PNAS_AUTHOR_COUNT_PATTERN,
        reject_email=True,
    )


_AUTHOR_EXTRACTION_PIPELINE = AuthorExtractionPipeline(
    _extract_dom_authors,
    partial(extract_meta_authors, keys={"citation_author", "dc.creator"}),
)


def extract_authors(html_text: str) -> list[str]:
    return _AUTHOR_EXTRACTION_PIPELINE(html_text)


def positive_signals(html_text: str) -> tuple[list[str], list[str], list[str]]:
    return pnas_positive_signals(html_text)


def select_content_nodes(
    container: Any,
    *,
    structural_abstract_nodes,
    nodes_from_selectors,
    content_abstract_selectors,
    content_body_selectors,
    select_availability_nodes,
    dedupe_top_level_nodes,
    is_tag,
) -> list[Any]:
    del content_body_selectors

    body_nodes: list[Any] = []
    for selector in (
        "#bodymatter [data-extent='bodymatter'][property='articleBody']",
        "#bodymatter [property='articleBody']",
        "#bodymatter [data-extent='bodymatter']",
        "#bodymatter",
    ):
        try:
            body_nodes = [node for node in container.select(selector) if is_tag(node)]
        except Exception:
            body_nodes = []
        if body_nodes:
            break
    if not body_nodes:
        return []

    selected: list[Any] = []
    abstract_nodes = structural_abstract_nodes(container) or nodes_from_selectors(container, content_abstract_selectors)
    availability_nodes = select_availability_nodes(container, body_nodes)
    selected.extend(abstract_nodes)
    selected.extend(body_nodes)
    selected.extend(availability_nodes)
    return dedupe_top_level_nodes(selected)


def finalize_extraction(
    html_text: str,
    source_url: str,
    markdown_text: str,
    extraction: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    del source_url, metadata
    finalized = dict(extraction)
    extracted_authors = extract_authors(html_text)
    if extracted_authors:
        finalized["extracted_authors"] = extracted_authors
    extracted_references = extract_numbered_references_from_html(html_text)
    if extracted_references:
        finalized["references"] = extracted_references
    return markdown_text, finalized
