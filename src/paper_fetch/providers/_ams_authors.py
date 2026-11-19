"""AMS author extraction helpers."""

from __future__ import annotations

from functools import partial
from typing import Any

from bs4 import Tag

from ..utils import normalize_text
from ._html_authors import (
    ATYPON_AUTHOR_NOISE_TEXT,
    AuthorExtractionPipeline,
    AuthorStep,
    extract_meta_authors,
    extract_property_authors,
    extract_selector_authors,
)


def _ams_node_text(node: Any) -> str:
    if not isinstance(node, Tag):
        return ""
    return normalize_text(node.get_text(" ", strip=True))


def _extract_ams_property_authors(html_text: str) -> list[str]:
    return extract_property_authors(
        html_text,
        selectors="[property='author']",
        ignored_text=ATYPON_AUTHOR_NOISE_TEXT,
        reject_email=True,
    )


def _extract_ams_selector_authors(html_text: str) -> list[str]:
    return extract_selector_authors(
        html_text,
        selectors=(
            "[property='author'] [property='name']",
            ".article__authors a",
            ".authors a",
        ),
        ignored_text=ATYPON_AUTHOR_NOISE_TEXT,
        node_text=_ams_node_text,
        reject_email=True,
        reject_affiliation=True,
    )


_AUTHOR_PIPELINE = AuthorExtractionPipeline(
    AuthorStep(
        "meta",
        partial(extract_meta_authors, keys={"citation_author", "dc.creator"}),
    ),
    AuthorStep("property", _extract_ams_property_authors),
    AuthorStep("selector", _extract_ams_selector_authors),
)


def extract_authors(html_text: str) -> list[str]:
    return _AUTHOR_PIPELINE(html_text)


__all__ = [
    "_AUTHOR_PIPELINE",
    "extract_authors",
]
