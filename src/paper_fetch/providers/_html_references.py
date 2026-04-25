"""HTML reference extraction helpers for numbered end-reference lists."""

from __future__ import annotations

import re
from typing import Any

from ..utils import normalize_text

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None

DOI_URL_PATTERN = re.compile(r"https?://(?:dx\.)?doi\.org/(?P<doi>10\.\S+)", flags=re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\((?P<year>(?:18|19|20)\d{2})\)")
NUMBERED_BIBLIOGRAPHY_SELECTORS = (
    "section[role='doc-bibliography'] [role='listitem'][data-has='label']",
    "#bibliography [role='listitem'][data-has='label']",
    "section[data-title='References'] li[data-counter]",
    "section[data-title='References'] ol > li",
    "section[data-title='References and Notes'] ol > li",
    "section.article-section__references li[data-bib-id]",
    "li[data-bib-id]",
)
REFERENCE_CONTENT_SELECTORS = (
    ".c-article-references__text",
    ".citation-content",
    ".citation",
    ".reference",
    "p",
)
REFERENCE_NOISE_SELECTORS = (
    ".extra-links",
    ".getFTR",
    ".citedBySection",
    ".related-links",
    ".reference-links",
    ".article__reference-links",
    "[aria-hidden='true']",
    ".visually-hidden",
    ".sr-only",
)


def _normalized_label(value: Any) -> str:
    return normalize_text(value).rstrip()


def _reference_label(node: Any, *, fallback_index: int) -> str | None:
    if Tag is None or not isinstance(node, Tag):
        return None

    explicit_label = _normalized_label(node.get("data-counter"))
    if explicit_label:
        return explicit_label

    label_node = node.select_one(".label")
    label_text = _normalized_label(label_node.get_text(" ", strip=True) if isinstance(label_node, Tag) else "")
    if label_text:
        return label_text

    parent = node.parent if isinstance(getattr(node, "parent", None), Tag) else None
    if isinstance(parent, Tag) and normalize_text(parent.name).lower() == "ol":
        return f"{fallback_index}."
    if normalize_text(str(node.get("data-bib-id") or "")):
        return f"{fallback_index}."
    return None


def _reference_content_node(node: Any) -> Any:
    if Tag is None or not isinstance(node, Tag):
        return None
    for selector in REFERENCE_CONTENT_SELECTORS:
        match = node.select_one(selector)
        if isinstance(match, Tag):
            return match
    return node


def _reference_text(node: Any) -> str:
    content_node = _reference_content_node(node)
    if Tag is None or not isinstance(content_node, Tag):
        return ""
    active_node = content_node
    if BeautifulSoup is not None:
        clone_soup = BeautifulSoup(str(content_node), "html.parser")
        clone = clone_soup.find()
        if isinstance(clone, Tag):
            for selector in REFERENCE_NOISE_SELECTORS:
                for match in clone.select(selector):
                    match.decompose()
            active_node = clone
    text = normalize_text(active_node.get_text(" ", strip=True))
    text = re.sub(r"\b(?:Article|ADS|Crossref|PubMed|Web of Science|Google Scholar|CAS)\b(?:\s*\|?\s*)*$", "", text)
    return normalize_text(text)


def _reference_doi(node: Any) -> str | None:
    if Tag is None or not isinstance(node, Tag):
        return None
    for anchor in node.find_all("a", href=True):
        href = normalize_text(anchor.get("href"))
        match = DOI_URL_PATTERN.search(href)
        if match is not None:
            return normalize_text(match.group("doi").rstrip(").,;"))
    return None


def _reference_year(text: str) -> str | None:
    matches = list(YEAR_PATTERN.finditer(text))
    if not matches:
        return None
    return matches[-1].group("year")


def _candidate_reference_nodes(soup: Any) -> list[Any]:
    if BeautifulSoup is None or soup is None:
        return []

    for selector in NUMBERED_BIBLIOGRAPHY_SELECTORS:
        try:
            matches = [node for node in soup.select(selector) if isinstance(node, Tag)]
        except Exception:
            matches = []
        if matches:
            return matches
    return []


def extract_numbered_references_from_html(html_text: str) -> list[dict[str, str | None]]:
    if BeautifulSoup is None or not normalize_text(html_text):
        return []

    soup = BeautifulSoup(html_text, "html.parser")
    references: list[dict[str, str | None]] = []
    seen: set[tuple[str, str]] = set()

    for index, node in enumerate(_candidate_reference_nodes(soup), start=1):
        label = _reference_label(node, fallback_index=index)
        raw = _reference_text(node)
        if not raw:
            continue
        key = (label or "", raw)
        if key in seen:
            continue
        seen.add(key)
        references.append(
            {
                "label": label or None,
                "raw": raw,
                "doi": _reference_doi(node),
                "year": _reference_year(raw),
            }
        )

    return references
