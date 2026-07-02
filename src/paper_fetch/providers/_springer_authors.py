"""Springer author extraction helpers."""

from __future__ import annotations

from typing import Any

from bs4 import Tag

from ..utils import dedupe_authors, normalize_text
from ._html_authors import (
    AuthorExtractionPipeline,
    AuthorStep,
    GENERIC_AUTHOR_NOISE_TEXT,
    extract_jsonld_authors as extract_common_jsonld_authors,
    extract_meta_authors as extract_common_meta_authors,
    extract_selector_authors as extract_common_selector_authors,
    looks_like_author_name,
    looks_like_collective_author_text,
)

SPRINGER_ARTICLE_JSONLD_TYPES = frozenset(
    {
        "article",
        "newsarticle",
        "medicalscholarlyarticle",
        "scholarlyarticle",
        "webpage",
    }
)
SPRINGER_IGNORED_AUTHOR_TEXT = {
    *GENERIC_AUTHOR_NOISE_TEXT,
    "authors and affiliations",
    "view author information",
}


def _looks_like_collective_author_text(text: str) -> bool:
    return looks_like_collective_author_text(text)


def _normalize_display_author_name(name: str) -> str:
    normalized = normalize_text(name)
    if not normalized or normalized.count(",") != 1:
        return normalized
    left, right = [part.strip() for part in normalized.split(",", 1)]
    if not left or not right:
        return normalized
    if not (looks_like_author_name(left) and looks_like_author_name(right)):
        return normalized
    if _looks_like_collective_author_text(left) or _looks_like_collective_author_text(
        right
    ):
        return normalized
    return normalize_text(f"{right} {left}")


def _normalize_display_authors(authors: list[str]) -> list[str]:
    return dedupe_authors(
        [
            _normalize_display_author_name(author)
            for author in authors
            if normalize_text(author)
        ]
    )


def normalize_display_authors(authors: list[str]) -> list[str]:
    return _normalize_display_authors(authors)


def _extract_meta_authors(html_text: str) -> list[str]:
    return _normalize_display_authors(
        extract_common_meta_authors(html_text, keys={"citation_author"})
    )


def _extract_jsonld_authors(html_text: str) -> list[str]:
    return _normalize_display_authors(
        extract_common_jsonld_authors(
            html_text,
            article_types=SPRINGER_ARTICLE_JSONLD_TYPES,
            author_paths=("mainEntity.author",),
        )
    )


def _node_author_text(node: Any) -> str:
    return (
        normalize_text(node.get_text(" ", strip=True)) if isinstance(node, Tag) else ""
    )


def _extract_dom_authors(html_text: str) -> list[str]:
    return _normalize_display_authors(
        extract_common_selector_authors(
            html_text,
            selectors=(
                "[data-test='author-name']",
                ".c-article-author-list [itemprop='name']",
                ".c-article-author-list li",
                ".authors__name",
            ),
            ignored_text=SPRINGER_IGNORED_AUTHOR_TEXT,
            node_text=_node_author_text,
            reject_email=True,
            reject_affiliation_prefixes=("author information",),
        )
    )


_AUTHOR_PIPELINE = AuthorExtractionPipeline(
    AuthorStep("meta", _extract_meta_authors),
    AuthorStep("jsonld", _extract_jsonld_authors),
    AuthorStep("dom", _extract_dom_authors),
)


def extract_authors(html_text: str) -> list[str]:
    return _AUTHOR_PIPELINE(html_text)


__all__ = [
    "_AUTHOR_PIPELINE",
    "extract_authors",
    "normalize_display_authors",
]
