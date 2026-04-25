"""PNAS provider-owned browser-workflow rules."""

from __future__ import annotations

import re
from typing import Any, Mapping

from ..quality.html_profiles import (
    PNAS_NOISE_PROFILE,
    PNAS_SITE_RULE_OVERRIDES,
    pnas_blocking_fallback_signals,
    pnas_positive_signals,
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

HOSTS: tuple[str, ...] = ("www.pnas.org", "pnas.org")
BASE_HOSTS: tuple[str, ...] = HOSTS
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


def _looks_like_author_name(text: str) -> bool:
    normalized = normalize_text(text)
    return bool(normalized) and any(character.isalpha() for character in normalized)


def _is_ignored_author_text(text: str) -> bool:
    normalized = normalize_text(text).lower()
    if not normalized:
        return True
    if normalized in PNAS_IGNORED_AUTHOR_TEXT:
        return True
    if normalized.startswith(("http://", "https://")) or "orcid.org" in normalized:
        return True
    if PNAS_AUTHOR_COUNT_PATTERN.fullmatch(normalized):
        return True
    if "@" in normalized or normalized.startswith("mailto:"):
        return True
    if "show all authors" in normalized or "hide all authors" in normalized:
        return True
    return False


def _extract_dom_authors(html_text: str) -> list[str]:
    if BeautifulSoup is None:
        return []
    soup = BeautifulSoup(html_text, "html.parser")
    authors: list[str] = []
    for node in soup.select(".contributors [property='author'], #tab-contributors [property='author']"):
        if Tag is not None and not isinstance(node, Tag):
            continue
        given_node = node.select_one("[property='givenName']")
        family_node = node.select_one("[property='familyName']")
        name = normalize_text(
            " ".join(
                part
                for part in (
                    given_node.get_text(" ", strip=True) if isinstance(given_node, Tag) else "",
                    family_node.get_text(" ", strip=True) if isinstance(family_node, Tag) else "",
                )
                if normalize_text(part)
            )
        )
        if not name:
            name_node = node.select_one("[property='name']")
            if isinstance(name_node, Tag):
                name = normalize_text(name_node.get_text(" ", strip=True))
        if not name:
            fragments = [
                fragment
                for fragment in (normalize_text(item) for item in node.stripped_strings)
                if fragment and not _is_ignored_author_text(fragment)
            ]
            name = normalize_text(" ".join(fragments))
        if _looks_like_author_name(name):
            authors.append(name)
    return dedupe_authors(authors)


def _extract_meta_authors(html_text: str) -> list[str]:
    if BeautifulSoup is None:
        return []
    soup = BeautifulSoup(html_text, "html.parser")
    authors: list[str] = []
    for meta in soup.find_all("meta"):
        if Tag is not None and not isinstance(meta, Tag):
            continue
        key = normalize_text(str(meta.get("name") or meta.get("property") or "")).lower()
        if key not in {"citation_author", "dc.creator"}:
            continue
        candidate = normalize_text(str(meta.get("content") or ""))
        if _looks_like_author_name(candidate):
            authors.append(candidate)
    return dedupe_authors(authors)


def extract_authors(html_text: str) -> list[str]:
    dom_authors = _extract_dom_authors(html_text)
    if dom_authors:
        return dom_authors
    return _extract_meta_authors(html_text)


def build_html_candidates(doi: str, landing_page_url: str | None = None) -> list[str]:
    path_templates = ("/doi/{doi}", "/doi/full/{doi}")
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

    append(crossref_pdf_url)
    for base in build_base_urls(hosts=HOSTS, base_hosts=BASE_HOSTS, landing_page_url=crossref_pdf_url):
        for template in ("/doi/epdf/{doi}", "/doi/pdf/{doi}?download=true", "/doi/pdf/{doi}"):
            append(f"{base}{template.format(doi=doi)}")
    return candidates


def positive_signals(html_text: str) -> tuple[list[str], list[str], list[str]]:
    return pnas_positive_signals(html_text)


def select_content_nodes(
    container: Any,
    *,
    structural_abstract_nodes,
    nodes_from_selectors,
    content_abstract_selectors,
    content_body_selectors,
    select_data_availability_nodes,
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
    data_availability_nodes = select_data_availability_nodes(container, body_nodes)
    selected.extend(abstract_nodes)
    selected.extend(body_nodes)
    selected.extend(data_availability_nodes)
    return dedupe_top_level_nodes(selected)


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
        "pnas",
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
