"""Shared inline-text normalization for HTML Markdown renderers."""

from __future__ import annotations

import re
from typing import Literal

InlineTextPolicy = Literal["body", "heading", "table_cell"]

HTML_NO_SPACE_AFTER_CHARS = set("([{/+-–—−")
HTML_NO_SPACE_BEFORE_CHARS = set(")]},.;:!?%/+-–—−")


def normalize_html_inline_text(value: str, *, policy: InlineTextPolicy = "body") -> str:
    """Normalize whitespace around inline HTML fragments rendered as Markdown."""

    text = value.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\s*(<br>)\s*", r"\1", text)
    text = re.sub(r"<(sub|sup)>\s+", r"<\1>", text)
    text = re.sub(r"\s+</(sub|sup)>", r"</\1>", text)
    text = re.sub(r"\s+(<(?:sub|sup)>)", r"\1", text)
    text = re.sub(r"(</sub>)\s+\(", r"\1(", text)
    punctuation = r"[,.;:%\]\}]" if policy == "table_cell" else r"[,.;:%\]\}\+\)]"
    text = re.sub(rf"(</(?:sub|sup)>)\s+({punctuation})", r"\1\2", text)
    return text.strip()


def wrap_html_inline_text_fragment(text: str, marker: str | None = None) -> str:
    value = text.replace("\xa0", " ")
    has_leading_space = bool(value[:1].isspace())
    has_trailing_space = bool(value[-1:].isspace())
    normalized = re.sub(r"\s+", " ", value).strip()
    if not normalized:
        return ""
    if marker:
        normalized = f"{marker}{normalized}{marker}"
    if has_leading_space:
        normalized = f" {normalized}"
    if has_trailing_space:
        normalized = f"{normalized} "
    return normalized


def _visible_inline_edge(text: str, *, last: bool) -> str:
    normalized = re.sub(r"</?(?:sub|sup)>", "", text)
    normalized = re.sub(r"[*_`]+", "", normalized).strip()
    if not normalized:
        return ""
    return normalized[-1] if last else normalized[0]


def needs_inline_fragment_space(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left[-1:].isspace() or right[:1].isspace():
        return False
    if right.startswith(("<sub>", "<sup>", "</sub>", "</sup>")):
        return False
    if left.endswith(("<br>", "<sub>", "<sup>")):
        return False
    left_edge = _visible_inline_edge(left, last=True)
    right_edge = _visible_inline_edge(right, last=False)
    if not left_edge or not right_edge:
        return False
    if left_edge in HTML_NO_SPACE_AFTER_CHARS or right_edge in HTML_NO_SPACE_BEFORE_CHARS:
        return False
    return right_edge.isalnum() or right_edge in {"*", "_", "<"}


def join_inline_fragments(parts: list[str]) -> str:
    if not parts:
        return ""
    joined = parts[0]
    for part in parts[1:]:
        if needs_inline_fragment_space(joined, part):
            joined += " "
        joined += part
    return joined


def first_significant_char(text: str) -> str:
    for char in text:
        if not char.isspace():
            return char
    return ""


def last_significant_char(text: str) -> str:
    for char in reversed(text):
        if not char.isspace():
            return char
    return ""


def needs_space_between_inline_text(
    left: str,
    right: str,
    *,
    previous_is_tight: bool = False,
    current_is_tight: bool = False,
    right_is_markdown_image: bool = False,
) -> bool:
    if not left or not right:
        return False
    if left[-1].isspace() or right[0].isspace():
        return False
    if right_is_markdown_image:
        return True
    if previous_is_tight or current_is_tight:
        return False

    left_char = last_significant_char(left)
    right_char = first_significant_char(right)
    if not left_char or not right_char:
        return False
    if left_char in HTML_NO_SPACE_AFTER_CHARS:
        return False
    if right_char in HTML_NO_SPACE_BEFORE_CHARS:
        return False
    return left_char.isalnum() and right_char.isalnum()
