"""Shared HTML lookup heuristics used by resolve and HTML fallback."""

from __future__ import annotations

from .utils import normalize_text

HTML_LOOKUP_TITLE_DENYLIST = (
    "redirecting",
    "sign in",
    "just a moment",
    "cookie",
    "subscribe",
    "access denied",
)


def is_usable_html_lookup_title(value: str | None, *, min_normalized_chars: int = 0) -> bool:
    normalized = normalize_text(value).lower()
    if len(normalized) < min_normalized_chars:
        return False
    return bool(normalized) and not any(token in normalized for token in HTML_LOOKUP_TITLE_DENYLIST)
