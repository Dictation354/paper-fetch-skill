"""MDPI author extraction helpers."""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag

from ..extraction.html.parsing import choose_parser
from ..utils import dedupe_authors, normalize_text
from ._html_authors import extract_meta_authors


def _append_unique(values: list[str], candidate: str | None) -> None:
    normalized = normalize_text(candidate)
    if normalized and normalized not in values:
        values.append(normalized)


def extract_authors(html_text: str) -> list[str]:
    authors = extract_meta_authors(
        html_text,
        keys={"citation_author", "dc.creator"},
    )
    if authors:
        return authors
    soup = BeautifulSoup(html_text, choose_parser())
    candidates: list[str] = []
    for selector in (".art-authors a", ".authors a", "[itemprop='author']"):
        for node in soup.select(selector):
            if isinstance(node, Tag):
                _append_unique(candidates, node.get_text(" ", strip=True))
    return dedupe_authors(candidates)


__all__ = [
    "extract_authors",
]
