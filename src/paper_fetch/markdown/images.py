"""Shared Markdown image rendering helpers."""

from __future__ import annotations

import re

from ..utils import normalize_text

_FORMULA_KIND_PATTERN = re.compile(r"^(?:formula|equation)$", flags=re.IGNORECASE)
_IMAGE_LABEL_NUMBER_PATTERN = (
    r"([A-Za-z]?\d+[A-Za-z]?(?:\.\d+[A-Za-z]?)*|[A-Za-z]\.\d+[A-Za-z]?)"
)
_FIGURE_LABEL_PATTERN = re.compile(
    rf"\bfig(?:ure)?\s*\.?\s*{_IMAGE_LABEL_NUMBER_PATTERN}",
    flags=re.IGNORECASE,
)
_TABLE_LABEL_PATTERN = re.compile(
    rf"\btable\s*\.?\s*{_IMAGE_LABEL_NUMBER_PATTERN}",
    flags=re.IGNORECASE,
)
_LISTING_LABEL_PATTERN = re.compile(
    rf"\blisting\s*\.?\s*{_IMAGE_LABEL_NUMBER_PATTERN}",
    flags=re.IGNORECASE,
)


def _first_label_number(
    kind: str,
    *,
    heading: str | None,
    fallback: str | None,
) -> str | None:
    if kind == "table":
        pattern = _TABLE_LABEL_PATTERN
    elif kind == "listing":
        pattern = _LISTING_LABEL_PATTERN
    else:
        pattern = _FIGURE_LABEL_PATTERN
    for candidate in (heading, fallback):
        match = pattern.search(normalize_text(candidate))
        if match is not None:
            return match.group(1)
    return None


def short_image_alt(
    kind: str | None, heading: str | None = None, fallback: str | None = None
) -> str:
    """Return a compact, caption-free alt label for generated image Markdown."""

    normalized_kind = normalize_text(kind).lower()
    if normalized_kind == "figure":
        number = _first_label_number("figure", heading=heading, fallback=fallback)
        if number:
            return f"Figure {number}"
        listing_number = _first_label_number(
            "listing", heading=heading, fallback=fallback
        )
        if listing_number:
            return f"Listing {listing_number}"
        return "Figure"
    if normalized_kind == "listing":
        number = _first_label_number("listing", heading=heading, fallback=fallback)
        return f"Listing {number}" if number else "Listing"
    if normalized_kind == "table":
        number = _first_label_number("table", heading=heading, fallback=fallback)
        return f"Table {number}" if number else "Table"
    if _FORMULA_KIND_PATTERN.match(normalized_kind):
        return "Formula"
    return "Image"


def render_markdown_image(
    kind: str | None, heading: str | None, url: str | None
) -> str:
    image_url = normalize_text(url)
    if not image_url:
        return ""
    return f"![{short_image_alt(kind, heading)}]({image_url})"


__all__ = [
    "render_markdown_image",
    "short_image_alt",
]
