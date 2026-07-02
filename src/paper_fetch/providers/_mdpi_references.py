"""MDPI reference and keyword extraction helpers."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from ..extraction.html.parsing import choose_parser
from ..models.markdown import NUMBERED_REFERENCE_PATTERN
from ..utils import normalize_text

_REFERENCE_SELECTORS = (
    "#html-references_list li",
    "section#html-references_list li",
)
_REFERENCE_UI_BRACKET_TOKEN_RE = re.compile(
    r"\[\s*(?:Google Scholar|CrossRef|PubMed|Green Version)\s*\]",
    flags=re.IGNORECASE,
)


def _append_unique(values: list[str], candidate: str | None) -> None:
    normalized = normalize_text(candidate)
    if normalized and normalized not in values:
        values.append(normalized)


def _remove_reference_ui_tokens(text: str) -> str:
    cleaned = _REFERENCE_UI_BRACKET_TOKEN_RE.sub("", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned


def _clean_reference_raw_text(text: str | None) -> str:
    return normalize_text(_remove_reference_ui_tokens(normalize_text(text)))


def _reference_label_from_node(node: Tag) -> str:
    label = normalize_text(str(node.get("data-content") or "")).strip()
    if not label:
        return ""
    if label.isdigit():
        return f"{label}."
    if NUMBERED_REFERENCE_PATTERN.match(f"{label} "):
        return label
    return ""


def _prepend_reference_label(text: str, label: str) -> str:
    if not text or not label or NUMBERED_REFERENCE_PATTERN.match(text):
        return text
    return f"{label} {text}"


def extract_references(html_text: str) -> list[dict[str, str | None]]:
    soup = BeautifulSoup(html_text, choose_parser())
    references: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for selector in _REFERENCE_SELECTORS:
        for node in soup.select(selector):
            if not isinstance(node, Tag):
                continue
            text = _clean_reference_raw_text(node.get_text(" ", strip=True))
            text = _prepend_reference_label(text, _reference_label_from_node(node))
            if not text or text in seen:
                continue
            seen.add(text)
            references.append({"raw": text})
    if references:
        return references
    for node in soup.select("meta[name='citation_reference']"):
        text = _clean_reference_raw_text(str(node.get("content") or ""))
        if text and text not in seen:
            seen.add(text)
            references.append({"raw": text})
    return references


def extract_keywords(html_text: str) -> list[str]:
    soup = BeautifulSoup(html_text, choose_parser())
    keywords: list[str] = []
    for container in soup.select("#html-keywords"):
        if not isinstance(container, Tag):
            continue
        for title_node in list(container.select("#html-keywords-title")):
            title_node.decompose()
        for node in container.find_all("a"):
            if isinstance(node, Tag):
                _append_unique(keywords, node.get_text(" ", strip=True))
        if keywords:
            continue
        text = normalize_text(container.get_text(" ", strip=True))
        text = re.sub(r"^Keywords\s*:?\s*", "", text, flags=re.IGNORECASE)
        for part in re.split(r"\s*;\s*", text):
            _append_unique(keywords, part)
    return keywords


__all__ = [
    "extract_keywords",
    "extract_references",
]
