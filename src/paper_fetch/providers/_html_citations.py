"""Shared citation marker cleanup for HTML-derived Markdown."""

from __future__ import annotations

import re

from ..models import normalize_text

REFERENCE_RANGE_PATTERN = re.compile(
    r"(?<=[A-Za-z)])\^?\s*\d+\s*[–-]\s*\d+(?=[.,;:]?(?:$|\s+(?![a-z])))"
)
REFERENCE_LIST_PATTERN = re.compile(
    r"(?<=[A-Za-z)])\^?\s*\d+(?:\s*,\s*\d+){1,}(?=[.,;:]?(?:$|\s+(?![a-z])))"
)
INLINE_ARTICLE_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((?:/(?:article|articles)/[^)]+|#[^)]+)\)")
LABEL_PATTERN = re.compile(r"\b((?:Extended Data|Fig|Figs|Tab|Tabs|Eq|Eqs|Ref|Refs))\s+(\d+[A-Za-z]?)\b")
FIGURE_LINE_PATTERN = re.compile(r"(?im)^(?:extended data\s+)?fig\.\s*[a-z0-9.-]+:.*$")


def is_citation_text(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    return bool(re.fullmatch(r"[\d,\-\u2013\u2014\s]+", normalized))


def is_citation_link(href: str, text: str) -> bool:
    normalized_href = normalize_text(href).lower()
    normalized_text = normalize_text(text)
    if "#ref-" in normalized_href or "#bib" in normalized_href or "#cite" in normalized_href:
        return True
    if is_citation_text(normalized_text) and normalized_href.startswith("#"):
        return True
    return False


def _join_label_reference(match: re.Match[str]) -> str:
    return f"{match.group(1)}{match.group(2)}"


def clean_citation_markers(
    text: str,
    *,
    unwrap_inline_links: bool = False,
    normalize_labels: bool = False,
    drop_figure_lines: bool = False,
) -> str:
    if not text:
        return ""

    cleaned = text
    if drop_figure_lines:
        cleaned = FIGURE_LINE_PATTERN.sub("", cleaned)
        cleaned = re.sub(r"(?im)^\s*source data\s*$", "", cleaned)
    cleaned = REFERENCE_RANGE_PATTERN.sub("", cleaned)
    cleaned = REFERENCE_LIST_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\((?:ref|refs)\.\)", "", cleaned, flags=re.IGNORECASE)
    if unwrap_inline_links:
        cleaned = INLINE_ARTICLE_LINK_PATTERN.sub(r"\1", cleaned)
    if normalize_labels:
        cleaned = LABEL_PATTERN.sub(_join_label_reference, cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"([(\[])\s+", r"\1", cleaned)
    cleaned = re.sub(r"\s+([)\]])", r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return cleaned.strip()
