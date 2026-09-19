"""AMS reference extraction helpers."""

from __future__ import annotations

from ..extraction.html.parsing import choose_parser
from ..quality.html_signals import (
    AMS_TEXT_MARKER_SIGNAL_SET,
    evaluate_text_marker_blocking_signals,
)
from ..utils import normalize_text
from ._reference_doi import reference_doi
from ._html_references import extract_numbered_references_from_html

from bs4 import BeautifulSoup


def extract_references(html_text: str) -> list[dict[str, str | None]]:
    numbered_references = extract_numbered_references_from_html(html_text)
    if numbered_references:
        return numbered_references
    soup = BeautifulSoup(html_text, choose_parser())
    references: list[dict[str, str | None]] = []
    # AMS provides an author-date bibliography, including legacy DOI suffixes
    # containing angle brackets. Read the actual link rather than regex/OCR.
    for node in soup.select("#contentRoot .reference > p.citationText"):
        doi = next(
            (
                value
                for a in node.select("a[href]")
                if "doi.org/" in str(a["href"])
                if (value := reference_doi(str(a["href"])))
            ),
            None,
        )
        raw = normalize_text(node.get_text(" ", strip=True))
        references.append({"raw": raw, "doi": doi or reference_doi(raw)})
    if references:
        return references
    seen: set[str] = set()
    for node in soup.select("meta[name='citation_reference']"):
        raw = normalize_text(str(node.get("content") or ""))
        if not raw or raw in seen:
            continue
        seen.add(raw)
        references.append({"raw": raw})
    return references


def blocking_fallback_signals(html_text: str) -> list[str]:
    return evaluate_text_marker_blocking_signals(html_text, AMS_TEXT_MARKER_SIGNAL_SET)


__all__ = [
    "blocking_fallback_signals",
    "extract_references",
]
