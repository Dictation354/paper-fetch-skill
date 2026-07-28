"""HTML reference extraction helpers for numbered end-reference lists."""

from __future__ import annotations

import copy
import re
from typing import Any

from ..extraction.html.parsing import choose_parser
from ..publisher_identity import DOI_CORE_PATTERN
from ..utils import normalize_text

from bs4 import BeautifulSoup, Tag

DOI_URL_PATTERN = re.compile(
    rf"https?://(?:dx\.)?doi\.org/(?P<doi>{DOI_CORE_PATTERN})",
    flags=re.IGNORECASE,
)
YEAR_PATTERN = re.compile(r"\((?P<year>(?:18|19|20)\d{2})\)")
REFERENCE_LINKOUT_LABELS = (
    "Article",
    "ADS",
    "COPAC",
    "Crossref",
    "Google Scholar",
    "Google Preview",
    "OpenURL",
    "PubMed",
    "Search ADS",
    "Web of Science",
    "WorldCat",
    "CAS",
)
REFERENCE_LINKOUT_LABEL_PATTERN = re.compile(
    rf"\b(?:{'|'.join(re.escape(label) for label in REFERENCE_LINKOUT_LABELS)})\b(?:\s*\|?\s*)*$"
)
NUMBERED_BIBLIOGRAPHY_SELECTORS = (
    ".ref-list .js-splitview-ref-item",
    ".ref-list .ref",
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
    ".mixed-citation",
    ".citation",
    ".ref-content",
    ".reference",
    "p",
)
REFERENCE_NOISE_SELECTORS = (
    ".citation-links",
    ".extra-links",
    ".getFTR",
    ".citedBySection",
    ".related-links",
    ".reference-links",
    ".article__reference-links",
    ".refLink-parent",
    ".google-scholar-ref-link",
    ".google-preview-ref-link",
    ".crossref-ref-link",
    ".crossref-doi",
    ".adsDoiReference",
    ".pubmed-ref-link",
    ".xslopenurl",
    ".openurl",
    "script",
    "noscript",
    "[aria-hidden='true']",
    ".visually-hidden",
    ".sr-only",
)
REFERENCE_CONTENT_CLASS_TOKENS = frozenset(
    {
        "c-article-references__text",
        "citation-content",
        "mixed-citation",
        "citation",
        "ref-content",
        "reference",
    }
)


def _normalized_label(value: Any) -> str:
    return normalize_text(value).rstrip()


def _reference_label(node: Any, *, fallback_index: int) -> str | None:
    if not isinstance(node, Tag):
        return None

    explicit_label = _normalized_label(node.get("data-counter"))
    if explicit_label:
        return explicit_label

    label_node = node.select_one(".label, .ref-label")
    label_text = _normalized_label(
        label_node.get_text(" ", strip=True) if isinstance(label_node, Tag) else ""
    )
    if label_text:
        return label_text

    parent = node.parent if isinstance(getattr(node, "parent", None), Tag) else None
    if isinstance(parent, Tag) and normalize_text(parent.name).lower() == "ol":
        return f"{fallback_index}."
    if normalize_text(str(node.get("data-bib-id") or "")):
        return f"{fallback_index}."
    class_values = getattr(node, "attrs", {}).get("class") or []
    if isinstance(class_values, str):
        classes = {item.lower() for item in class_values.split()}
    else:
        classes = {normalize_text(str(item)).lower() for item in class_values}
    if classes & {"js-splitview-ref-item", "ref"}:
        return f"{fallback_index}."
    return None


def _node_matches_reference_content(node: Tag) -> bool:
    class_values = getattr(node, "attrs", {}).get("class") or []
    if isinstance(class_values, str):
        classes = {
            normalize_text(item).lower()
            for item in class_values.split()
            if normalize_text(item)
        }
    else:
        classes = {
            normalize_text(str(item)).lower()
            for item in class_values
            if normalize_text(str(item))
        }
    return bool(classes & REFERENCE_CONTENT_CLASS_TOKENS)


def _reference_content_node(node: Any) -> Any:
    if not isinstance(node, Tag):
        return None
    if _node_matches_reference_content(node):
        return node
    for selector in REFERENCE_CONTENT_SELECTORS:
        match = node.select_one(selector)
        if isinstance(match, Tag):
            return match
    return node


def _clean_reference_text(text: str) -> str:
    text = REFERENCE_LINKOUT_LABEL_PATTERN.sub("", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    text = re.sub(r"([(\[])\s+", r"\1", text)
    text = re.sub(r"\s+([)\]])", r"\1", text)
    text = re.sub(r"\s+([–-])\s+", r"\1", text)
    return normalize_text(text)


def _reference_text(node: Any) -> str:
    content_node = _reference_content_node(node)
    if not isinstance(content_node, Tag):
        return ""
    active_node = content_node
    clone = copy.deepcopy(content_node)
    if isinstance(clone, Tag):
        for selector in REFERENCE_NOISE_SELECTORS:
            for match in clone.select(selector):
                match.decompose()
        active_node = clone
    text = normalize_text(active_node.get_text(" ", strip=True))
    return _clean_reference_text(text)


def _reference_doi(node: Any) -> str | None:
    if not isinstance(node, Tag):
        return None
    for anchor in node.find_all("a", href=True):
        href = normalize_text(anchor.get("href"))
        match = DOI_URL_PATTERN.search(href)
        if match is not None:
            return normalize_text(match.group("doi").rstrip(").,;"))
    return None


def _reference_year(node: Any, text: str) -> str | None:
    if isinstance(node, Tag):
        year_node = node.select_one(".year")
        if isinstance(year_node, Tag):
            year_match = re.search(
                r"\b((?:18|19|20)\d{2})\b",
                normalize_text(year_node.get_text(" ", strip=True)),
            )
            if year_match is not None:
                return year_match.group(1)
    matches = list(YEAR_PATTERN.finditer(text))
    if not matches:
        return None
    return matches[-1].group("year")


def _candidate_reference_nodes(soup: Any) -> list[Any]:
    if soup is None:
        return []

    for selector in NUMBERED_BIBLIOGRAPHY_SELECTORS:
        try:
            matches = [node for node in soup.select(selector) if isinstance(node, Tag)]
        except Exception:
            matches = []
        if matches:
            return matches
    return []


def extract_numbered_references_from_html(
    html_text: str,
) -> list[dict[str, str | None]]:
    if not normalize_text(html_text):
        return []

    soup = BeautifulSoup(html_text, choose_parser())
    return extract_numbered_references_from_soup(soup)


def extract_numbered_references_from_soup(soup: Any) -> list[dict[str, str | None]]:
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
                "year": _reference_year(node, raw),
            }
        )

    return references
