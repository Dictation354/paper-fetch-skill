"""Shared HTML lookup heuristics used by resolve and HTML fallback."""

from __future__ import annotations

import re

from .utils import normalize_text

HTML_LOOKUP_CHALLENGE_TITLE_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"just a moment(?:\.{3}|…)?",
        r"one moment(?:, please| while we are preparing your request)?(?:\.{3}|…)?",
        r"please wait(?: while we check your browser)?(?:\.{3}|…)?",
        r"attention required!?(?: \| cloudflare)?",
        r"security check|checking your connection in a security check",
        r"bot check(?: before you may continue browsing)?",
        r"verif(?:y|ying) (?:that )?you are human|verifying you because attention required",
        r"(?:checking|verifying) your browser(?: before accessing.*)?",
        r"preparing your (?:download|article).*",
        r"redirecting(?:\.{3}|…)?|redirecting to .+(?:\.{3}|…)|client challenge",
        r"sign[ -]in|log[ -]?in|access denied|subscribe|cookie consent",
    )
)


def is_html_redirect_title(value: str | None) -> bool:
    return normalize_text(value).casefold().startswith("redirecting to ")


def is_html_lookup_challenge_title(value: str | None) -> bool:
    normalized = normalize_text(value).casefold()
    return any(
        pattern.fullmatch(normalized)
        for pattern in HTML_LOOKUP_CHALLENGE_TITLE_PATTERNS
    )


def is_usable_html_lookup_title(
    value: str | None, *, min_normalized_chars: int = 0
) -> bool:
    normalized = normalize_text(value)
    return (
        bool(normalized)
        and len(normalized) >= min_normalized_chars
        and not (is_html_lookup_challenge_title(normalized))
    )
