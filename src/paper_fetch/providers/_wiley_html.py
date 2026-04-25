"""Wiley provider-owned browser-workflow rules."""

from __future__ import annotations

import re
from typing import Any, Mapping

from ..quality.html_profiles import (
    WILEY_NOISE_PROFILE,
    WILEY_SITE_RULE_OVERRIDES,
    wiley_blocking_fallback_signals,
    wiley_positive_signals,
)
from ..utils import dedupe_authors, normalize_text
from ._browser_workflow_shared import (
    build_base_urls,
    preferred_html_candidate_from_landing_page,
)
from ._html_references import extract_numbered_references_from_html

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None

HOSTS: tuple[str, ...] = ("onlinelibrary.wiley.com", "wiley.com", "www.wiley.com")
BASE_HOSTS: tuple[str, ...] = ("onlinelibrary.wiley.com",)
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


def _looks_like_author_name(text: str) -> bool:
    normalized = normalize_text(text)
    return bool(normalized) and any(character.isalpha() for character in normalized)


def _is_ignored_author_text(text: str) -> bool:
    normalized = normalize_text(text).lower()
    if not normalized:
        return True
    if normalized in WILEY_IGNORED_AUTHOR_TEXT:
        return True
    if normalized.startswith(("http://", "https://")) or "orcid.org" in normalized:
        return True
    if "search for more papers by this author" in normalized:
        return True
    if normalized.startswith("contribution:"):
        return True
    if normalized.startswith("email:") or "@" in normalized:
        return True
    if normalized.startswith("department of ") or normalized.startswith("institute of "):
        return True
    return False


def _extract_meta_authors(html_text: str) -> list[str]:
    if BeautifulSoup is None:
        return []
    soup = BeautifulSoup(html_text, "html.parser")
    authors: list[str] = []
    for meta in soup.find_all("meta"):
        if Tag is not None and not isinstance(meta, Tag):
            continue
        key = normalize_text(str(meta.get("name") or meta.get("property") or "")).lower()
        if key != "citation_author":
            continue
        candidate = normalize_text(str(meta.get("content") or ""))
        if _looks_like_author_name(candidate):
            authors.append(candidate)
    return dedupe_authors(authors)


def _node_author_text(node: Any) -> str:
    if Tag is None or not isinstance(node, Tag):
        return ""
    span = node.find("span")
    candidate = normalize_text(span.get_text(" ", strip=True) if isinstance(span, Tag) else node.get_text(" ", strip=True))
    candidate = re.sub(r"\s*Search for more papers by this author\s*$", "", candidate, flags=re.IGNORECASE).strip()
    return normalize_text(candidate)


def _extract_dom_authors(html_text: str) -> list[str]:
    if BeautifulSoup is None:
        return []
    soup = BeautifulSoup(html_text, "html.parser")
    authors: list[str] = []
    seen_nodes: set[int] = set()
    for selector in WILEY_AUTHOR_SELECTOR_CANDIDATES:
        for node in soup.select(selector):
            if Tag is not None and not isinstance(node, Tag):
                continue
            if id(node) in seen_nodes:
                continue
            seen_nodes.add(id(node))
            candidate = _node_author_text(node)
            if _is_ignored_author_text(candidate):
                continue
            if _looks_like_author_name(candidate):
                authors.append(candidate)
    return dedupe_authors(authors)


def extract_authors(html_text: str) -> list[str]:
    meta_authors = _extract_meta_authors(html_text)
    if meta_authors:
        return meta_authors
    return _extract_dom_authors(html_text)


def build_html_candidates(doi: str, landing_page_url: str | None = None) -> list[str]:
    path_templates = ("/doi/full/{doi}", "/doi/{doi}")
    candidates: list[str] = []
    preferred_candidate = preferred_html_candidate_from_landing_page(
        doi,
        landing_page_url,
        hosts=HOSTS,
    )
    if preferred_candidate:
        candidates.append(preferred_candidate)
    for base in build_base_urls(hosts=HOSTS, base_hosts=BASE_HOSTS, landing_page_url=landing_page_url):
        for template in path_templates:
            candidate = f"{base}{template.format(doi=doi)}"
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def build_pdf_candidates(doi: str, crossref_pdf_url: str | None) -> list[str]:
    candidates: list[str] = []

    def append(candidate: str | None) -> None:
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    for base in build_base_urls(hosts=HOSTS, base_hosts=BASE_HOSTS):
        append(f"{base}/doi/epdf/{doi}")
    append(crossref_pdf_url)
    for base in build_base_urls(hosts=HOSTS, base_hosts=BASE_HOSTS):
        append(f"{base}/doi/pdf/{doi}")
        append(f"{base}/doi/pdfdirect/{doi}")
        append(f"{base}/wol1/doi/{doi}/fullpdf")
    return candidates


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


def extract_markdown(
    html_text: str,
    source_url: str,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    from . import _science_pnas

    return _science_pnas.extract_science_pnas_markdown(
        html_text,
        source_url,
        "wiley",
        metadata=metadata,
    )


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
