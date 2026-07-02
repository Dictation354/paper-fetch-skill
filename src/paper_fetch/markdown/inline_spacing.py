"""Shared cleanup for inline HTML subscript and superscript tag bodies."""

from __future__ import annotations

import re

INLINE_SUP_SUB_TEXT_PATTERN = re.compile(
    r"<(?P<tag>sub|sup)>(?P<body>[^<>]*)</(?P=tag)>"
)


def normalize_inline_sup_sub_tag_bodies(text: str) -> str:
    """Strip tag body padding while preserving meaningful trailing separation."""

    def normalize_match(match: re.Match[str]) -> str:
        tag = match.group("tag")
        body = match.group("body")
        stripped = body.strip()
        if not stripped:
            return ""
        trailing_space = " " if body and body[-1].isspace() else ""
        return f"<{tag}>{stripped}</{tag}>{trailing_space}"

    normalized = INLINE_SUP_SUB_TEXT_PATTERN.sub(normalize_match, text)
    return re.sub(r"(</(?:sub|sup)>)[ \t]{2,}", r"\1 ", normalized)
