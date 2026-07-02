"""Shared HTML lookup heuristics used by resolve and HTML fallback."""

from __future__ import annotations

from .extraction.html.signals import (
    ACCESS_DENIED_TOKEN,
    CLOUDFLARE_CHALLENGE_TITLE_TOKENS,
    LOGIN_GATE_TOKENS,
)
from .utils import normalize_text

HTML_LOOKUP_TITLE_DENYLIST = (
    "redirecting",
    LOGIN_GATE_TOKENS[0],
    CLOUDFLARE_CHALLENGE_TITLE_TOKENS[0],
    "cookie",
    "subscribe",
    ACCESS_DENIED_TOKEN,
)


def is_usable_html_lookup_title(
    value: str | None, *, min_normalized_chars: int = 0
) -> bool:
    normalized = normalize_text(value).lower()
    if len(normalized) < min_normalized_chars:
        return False
    return bool(normalized) and not any(
        token in normalized for token in HTML_LOOKUP_TITLE_DENYLIST
    )
