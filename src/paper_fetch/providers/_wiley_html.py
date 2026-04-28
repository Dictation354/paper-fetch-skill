"""Wiley provider-owned browser-workflow rules."""

from __future__ import annotations

import re
from functools import partial
from typing import Any, Mapping

from ..quality.html_profiles import (
    WILEY_NOISE_PROFILE,
    WILEY_SITE_RULE_OVERRIDES,
    wiley_blocking_fallback_signals,
    wiley_positive_signals,
)
from ..utils import normalize_text
from ._browser_workflow_authors import AuthorExtractionPipeline, extract_meta_authors, extract_selector_authors
from ._html_references import extract_numbered_references_from_html

try:
    from bs4 import Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    Tag = None

HOSTS: tuple[str, ...] = ("onlinelibrary.wiley.com", "wiley.com", "www.wiley.com")
BASE_HOSTS: tuple[str, ...] = ("onlinelibrary.wiley.com",)
HTML_PATH_TEMPLATES: tuple[str, ...] = ("/doi/full/{doi}", "/doi/{doi}")
PDF_PATH_TEMPLATES: tuple[str, ...] = (
    "/doi/epdf/{doi}",
    "/doi/pdf/{doi}",
    "/doi/pdfdirect/{doi}",
    "/wol1/doi/{doi}/fullpdf",
)
CROSSREF_PDF_POSITION = 1
NOISE_PROFILE = WILEY_NOISE_PROFILE
SITE_RULE_OVERRIDES: dict[str, Any] = WILEY_SITE_RULE_OVERRIDES
WILEY_IGNORED_AUTHOR_TEXT = {
    "orcid",
    "search for more papers by this author",
}
WILEY_AUTHOR_SELECTOR_CANDIDATES = (
    ".loa-authors-trunc a.author-name",
    ".loa-authors-trunc p.author-name",
    ".accordion-tabbed a.author-name",
    ".accordion-tabbed p.author-name",
)


def blocking_fallback_signals(html_text: str) -> list[str]:
    return wiley_blocking_fallback_signals(html_text)


def _node_author_text(node: Any) -> str:
    if Tag is None or not isinstance(node, Tag):
        return ""
    span = node.find("span")
    candidate = normalize_text(
        span.get_text(" ", strip=True) if isinstance(span, Tag) else node.get_text(" ", strip=True)
    )
    candidate = re.sub(
        r"\s*Search for more papers by this author\s*$",
        "",
        candidate,
        flags=re.IGNORECASE,
    ).strip()
    return normalize_text(candidate)


def _extract_dom_authors(html_text: str) -> list[str]:
    return extract_selector_authors(
        html_text,
        selectors=WILEY_AUTHOR_SELECTOR_CANDIDATES,
        ignored_text=WILEY_IGNORED_AUTHOR_TEXT,
        node_text=_node_author_text,
        reject_email=True,
        reject_affiliation_prefixes=("contribution:", "department of ", "institute of "),
    )


_AUTHOR_EXTRACTION_PIPELINE = AuthorExtractionPipeline(
    partial(extract_meta_authors, keys={"citation_author"}),
    _extract_dom_authors,
)


def extract_authors(html_text: str) -> list[str]:
    return _AUTHOR_EXTRACTION_PIPELINE(html_text)


def positive_signals(html_text: str) -> tuple[list[str], list[str], list[str]]:
    return wiley_positive_signals(html_text)


def dom_postprocess(container: Any) -> None:
    from ._science_pnas_postprocess import move_wiley_abbreviations_to_end

    move_wiley_abbreviations_to_end(container)


def refine_selected_container(
    node: Any,
    *,
    direct_child_tags,
    class_tokens,
    container_completeness_score,
    score_container,
) -> Any:
    article_candidates = [
        candidate
        for candidate in [node, *list(node.find_all("article"))]
        if normalize_text(getattr(candidate, "name", "")).lower() == "article"
    ]
    if not article_candidates:
        return node

    def has_direct_abstract_child(candidate: Any) -> bool:
        for child in direct_child_tags(candidate):
            tokens = class_tokens(child)
            if {"abstract-group", "metis-abstract"} <= tokens:
                return True
            if "article-section__abstract" in tokens:
                return True
            if child.select_one(".article-section__abstract") is not None:
                return True
        return False

    def has_direct_body_child(candidate: Any) -> bool:
        for child in direct_child_tags(candidate):
            if "article-section__full" in class_tokens(child):
                return True
        return False

    def candidate_key(candidate: Any) -> tuple[int, int, int, int, int, float]:
        has_direct_abstract = has_direct_abstract_child(candidate)
        has_direct_body = has_direct_body_child(candidate)
        return (
            1 if has_direct_abstract and has_direct_body else 0,
            1 if has_direct_abstract else 0,
            1 if has_direct_body else 0,
            1 if normalize_text(candidate.get("lang") or "") else 0,
            container_completeness_score(candidate),
            score_container(candidate),
        )

    best_candidate = max(article_candidates, key=candidate_key)
    return best_candidate if candidate_key(best_candidate) > candidate_key(node) else node


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
