"""Markdown normalization and inline text helpers."""

from __future__ import annotations

import html
import re
from typing import Any

from ..utils import normalize_text, safe_text

MARKDOWN_FENCE_PATTERN = re.compile(r"^\s*(```+|~~~+)")


MARKDOWN_TABLE_RULE_PATTERN = re.compile(r"^\s*[-+:| ]{3,}\s*$")


MARKDOWN_LIST_MARKER_PATTERN = re.compile(r"^(\s{0,3}(?:[-*+]|\d+[.)])\s+)(.*)$")


ABSTRACT_PREFIX_PATTERN = re.compile(r"^(?:[Aa]bstract|[Ss]ummary)\b[:.\-\s]+(?=[A-Z])")


INLINE_HTML_TAG_PATTERN = re.compile(r"</?(?:sub|sup|br)\b[^>]*>", flags=re.IGNORECASE)


INLINE_MARKDOWN_ABSTRACT_PREFIX_PATTERN = re.compile(r"^\*\*(?:Abstract|Summary)\.?\*\*\s*", re.IGNORECASE)


MARKDOWN_ABSTRACT_PREFIX_PATTERN = re.compile(r"^(?:\*\*|__)(?:[Aa]bstract|[Ss]ummary)\.?(?:\*\*|__)\s*")


MARKDOWN_IMAGE_URL_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\([^)]+\)")


MARKDOWN_IMAGE_LINK_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


MARKDOWN_BLOCK_IMAGE_ALT_PATTERN = re.compile(
    r"^\s*(?:fig(?:ure)?\.?|(?:extended data|supplementary)?\s*table|supplementary\s+fig(?:ure)?\.?)\b",
    flags=re.IGNORECASE,
)


MARKDOWN_STANDALONE_IMAGE_ALT_PATTERN = re.compile(
    r"^\s*(?:fig(?:ure)?\.?|(?:extended data|supplementary)?\s*table|supplementary\s+fig(?:ure)?\.?|formula|equation)\b",
    flags=re.IGNORECASE,
)


TABLE_LIKE_FIGURE_ASSET_PATTERN = re.compile(
    r"^(?:(?:extended data|supplementary)\s+)?table\s+\d+[A-Za-z]?\b",
    flags=re.IGNORECASE,
)


NUMBERED_REFERENCE_PATTERN = re.compile(r"^\s*(?:\[\d+[A-Za-z]?\]|\d+[A-Za-z]?[.)])\s+")


INLINE_WHITESPACE_PATTERN = re.compile(r"[ \t\r\f\v]+")


SLASH_RUN_PATTERN = re.compile(r"/+")


CANONICAL_MATCH_NON_WORD_PATTERN = re.compile(r"[\W_]+", flags=re.UNICODE)


INLINE_HTML_NEWLINE_WHITESPACE_PATTERN = re.compile(r"\s*\n\s*")


INLINE_HTML_BR_WHITESPACE_PATTERN = re.compile(r"\s*(<br\s*/?>)\s*", flags=re.IGNORECASE)


INLINE_HTML_OPEN_SUBSUP_WHITESPACE_PATTERN = re.compile(r"\s*<(sub|sup)>\s*", flags=re.IGNORECASE)


INLINE_HTML_CLOSE_SUBSUP_WHITESPACE_PATTERN = re.compile(r"\s+</(sub|sup)>", flags=re.IGNORECASE)


INLINE_HTML_BEFORE_SUBSUP_PATTERN = re.compile(r"\s+(<(?:sub|sup)>)", flags=re.IGNORECASE)


INLINE_HTML_AFTER_SUBSUP_NEWLINE_PATTERN = re.compile(r"(</(?:sub|sup)>)\s*\n\s*", flags=re.IGNORECASE)


INLINE_HTML_AFTER_SUBSUP_WORD_PATTERN = re.compile(r"(</(?:sub|sup)>)(?=[A-Za-z0-9])", flags=re.IGNORECASE)


INLINE_HTML_AFTER_SUBSUP_PUNCT_PATTERN = re.compile(r"(</(?:sub|sup)>)\s+([,.;:%\]\}\+\)])", flags=re.IGNORECASE)


def normalize_markdown_text(value: str | None) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    normalized_lines: list[str] = []
    in_fence = False
    blank_run = 0
    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        if MARKDOWN_FENCE_PATTERN.match(line):
            normalized_lines.append(line.strip())
            in_fence = not in_fence
            blank_run = 0
            continue

        if in_fence or should_preserve_markdown_line(line):
            normalized_line = line
        else:
            normalized_line = normalize_markdown_prose_line(line)

        if normalized_line:
            normalized_lines.append(normalized_line)
            blank_run = 0
            continue

        if in_fence or blank_run < 2:
            normalized_lines.append("")
        blank_run += 1

    normalized = "\n".join(normalized_lines).strip()
    normalized = _collapse_display_math_padding(normalized)
    return _normalize_markdown_image_block_boundaries(normalized)


def _is_block_markdown_image_alt(alt_text: str) -> bool:
    return bool(MARKDOWN_BLOCK_IMAGE_ALT_PATTERN.match(normalize_text(alt_text)))


def _is_standalone_markdown_image_alt(alt_text: str) -> bool:
    return bool(MARKDOWN_STANDALONE_IMAGE_ALT_PATTERN.match(normalize_text(alt_text)))


def _is_standalone_markdown_image_line(line: str) -> bool:
    match = MARKDOWN_IMAGE_LINK_PATTERN.fullmatch(line.strip())
    return bool(match and _is_standalone_markdown_image_alt(match.group(1)))


def _split_markdown_image_adjacency_line(line: str) -> list[str]:
    matches = list(MARKDOWN_IMAGE_LINK_PATTERN.finditer(line))
    if not matches:
        return [line]

    stripped = line.strip()
    if MARKDOWN_IMAGE_LINK_PATTERN.fullmatch(stripped):
        return [line]

    split_required = False
    for match in matches:
        prefix = line[: match.start()]
        suffix = line[match.end() :]
        if _is_block_markdown_image_alt(match.group(1)):
            split_required = True
            break
        if (
            _is_standalone_markdown_image_alt(match.group(1))
            and re.search(r"\b(?:equation|formula)\b", normalize_text(prefix), flags=re.IGNORECASE)
            and not normalize_text(suffix)
        ):
            split_required = True
            break
        if normalize_text(prefix).endswith("$$") or normalize_text(suffix).startswith("$$"):
            split_required = True
            break
    if not split_required:
        return [line]

    pieces: list[str] = []
    cursor = 0
    for match in matches:
        prefix = line[cursor : match.start()]
        if normalize_text(prefix):
            pieces.append(prefix.rstrip())
        pieces.append(match.group(0))
        cursor = match.end()
    suffix = line[cursor:]
    if normalize_text(suffix):
        pieces.append(suffix.strip())
    return pieces or [line]


def _normalize_markdown_image_block_boundaries(text: str) -> str:
    if not text:
        return ""

    split_lines: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if MARKDOWN_FENCE_PATTERN.match(line):
            split_lines.append(line.strip())
            in_fence = not in_fence
            continue
        if in_fence:
            split_lines.append(line)
            continue
        split_lines.extend(_split_markdown_image_adjacency_line(line))

    bounded_lines: list[str] = []
    for index, line in enumerate(split_lines):
        if _is_standalone_markdown_image_line(line):
            if bounded_lines and bounded_lines[-1].strip():
                bounded_lines.append("")
            bounded_lines.append(line.strip())
            next_line = split_lines[index + 1] if index + 1 < len(split_lines) else ""
            if normalize_text(next_line):
                bounded_lines.append("")
            continue
        bounded_lines.append(line)

    return "\n".join(bounded_lines).strip()


def _collapse_display_math_padding(text: str) -> str:
    if not text:
        return ""

    collapsed_lines: list[str] = []
    math_lines: list[str] = []
    in_fence = False
    in_display_math = False

    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        if MARKDOWN_FENCE_PATTERN.match(line):
            if in_display_math:
                math_lines.append(line)
                continue
            collapsed_lines.append(line.strip())
            in_fence = not in_fence
            continue

        if not in_fence and line.strip() == "$$":
            if in_display_math:
                while math_lines and not math_lines[-1].strip():
                    math_lines.pop()
                collapsed_lines.extend(math_lines)
                collapsed_lines.append("$$")
                math_lines = []
                in_display_math = False
            else:
                collapsed_lines.append("$$")
                math_lines = []
                in_display_math = True
            continue

        if in_display_math:
            if not math_lines and not line.strip():
                continue
            math_lines.append(line)
            continue

        collapsed_lines.append(line)

    if in_display_math:
        collapsed_lines.extend(math_lines)

    return "\n".join(collapsed_lines).strip()


def should_preserve_markdown_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if line.startswith(("    ", "\t")):
        return True
    if stripped.startswith("|") or stripped.endswith("|"):
        return True
    return bool(MARKDOWN_TABLE_RULE_PATTERN.match(stripped))


def normalize_markdown_prose_line(line: str) -> str:
    expanded = line.replace("\xa0", " ")
    list_match = MARKDOWN_LIST_MARKER_PATTERN.match(expanded)
    if list_match:
        marker, body = list_match.groups()
        body = INLINE_WHITESPACE_PATTERN.sub(" ", body).strip()
        return f"{marker}{body}" if body else marker.rstrip()

    leading_match = re.match(r"^\s*", expanded)
    leading = leading_match.group(0) if leading_match else ""
    body = INLINE_WHITESPACE_PATTERN.sub(" ", expanded[len(leading):]).strip()
    if not body:
        return ""
    return f"{leading}{body}" if leading else body


def strip_markdown_images(text: str) -> str:
    stripped = MARKDOWN_IMAGE_PATTERN.sub("", text)
    return normalize_markdown_text(stripped)


def _canonical_match_text(value: str) -> str:
    return CANONICAL_MATCH_NON_WORD_PATTERN.sub("", normalize_text(value).lower())


def normalize_authors(value: Any) -> list[str]:
    if isinstance(value, list):
        return [normalize_inline_html_text(item) for item in value if normalize_inline_html_text(item)]
    if isinstance(value, str):
        parts = [normalize_inline_html_text(part) for part in re.split(r"\s*;\s*|\s*,\s*", value)]
        return [part for part in parts if part]
    return []


def normalize_abstract_text(value: Any) -> str:
    text = normalize_inline_html_text(value)
    if not text:
        return ""
    text = MARKDOWN_ABSTRACT_PREFIX_PATTERN.sub("", text, count=1).lstrip()
    return ABSTRACT_PREFIX_PATTERN.sub("", text, count=1).lstrip()


def normalize_inline_html_text(value: Any) -> str:
    text = html.unescape(safe_text(value))
    if not text:
        return ""
    if not INLINE_HTML_TAG_PATTERN.search(text):
        return text
    text = INLINE_HTML_NEWLINE_WHITESPACE_PATTERN.sub(" ", text)
    text = INLINE_HTML_BR_WHITESPACE_PATTERN.sub(r"\1", text)
    text = INLINE_HTML_OPEN_SUBSUP_WHITESPACE_PATTERN.sub(r"<\1>", text)
    text = INLINE_HTML_CLOSE_SUBSUP_WHITESPACE_PATTERN.sub(r"</\1>", text)
    text = INLINE_HTML_BEFORE_SUBSUP_PATTERN.sub(r"\1", text)
    text = INLINE_HTML_AFTER_SUBSUP_NEWLINE_PATTERN.sub(r"\1 ", text)
    text = INLINE_HTML_AFTER_SUBSUP_WORD_PATTERN.sub(r"\1 ", text)
    text = INLINE_HTML_AFTER_SUBSUP_PUNCT_PATTERN.sub(r"\1\2", text)
    return text.strip()


def strip_leading_markdown_title_heading(markdown_text: str, *, title: str | None) -> str:
    normalized_markdown = normalize_markdown_text(markdown_text)
    normalized_title = normalize_text(title)
    if not normalized_markdown or not normalized_title:
        return normalized_markdown

    lines = normalized_markdown.splitlines()
    line_index = 0
    while line_index < len(lines) and not normalize_text(lines[line_index]):
        line_index += 1
    if line_index >= len(lines):
        return normalized_markdown

    match = re.match(r"^(#+)\s*(.*?)\s*$", lines[line_index].strip())
    if match is None or len(match.group(1)) != 1:
        return normalized_markdown
    heading_text = normalize_text(match.group(2))
    if _canonical_match_text(heading_text) != _canonical_match_text(normalized_title):
        return normalized_markdown

    trimmed_lines = list(lines[:line_index]) + list(lines[line_index + 1 :])
    while line_index < len(trimmed_lines) and not normalize_text(trimmed_lines[line_index]):
        trimmed_lines.pop(line_index)
    return normalize_markdown_text("\n".join(trimmed_lines))


__all__ = [
    "MARKDOWN_FENCE_PATTERN",
    "MARKDOWN_TABLE_RULE_PATTERN",
    "MARKDOWN_LIST_MARKER_PATTERN",
    "ABSTRACT_PREFIX_PATTERN",
    "INLINE_HTML_TAG_PATTERN",
    "INLINE_MARKDOWN_ABSTRACT_PREFIX_PATTERN",
    "MARKDOWN_ABSTRACT_PREFIX_PATTERN",
    "MARKDOWN_IMAGE_URL_PATTERN",
    "MARKDOWN_IMAGE_PATTERN",
    "MARKDOWN_IMAGE_LINK_PATTERN",
    "MARKDOWN_BLOCK_IMAGE_ALT_PATTERN",
    "MARKDOWN_STANDALONE_IMAGE_ALT_PATTERN",
    "TABLE_LIKE_FIGURE_ASSET_PATTERN",
    "NUMBERED_REFERENCE_PATTERN",
    "INLINE_WHITESPACE_PATTERN",
    "SLASH_RUN_PATTERN",
    "CANONICAL_MATCH_NON_WORD_PATTERN",
    "INLINE_HTML_NEWLINE_WHITESPACE_PATTERN",
    "INLINE_HTML_BR_WHITESPACE_PATTERN",
    "INLINE_HTML_OPEN_SUBSUP_WHITESPACE_PATTERN",
    "INLINE_HTML_CLOSE_SUBSUP_WHITESPACE_PATTERN",
    "INLINE_HTML_BEFORE_SUBSUP_PATTERN",
    "INLINE_HTML_AFTER_SUBSUP_NEWLINE_PATTERN",
    "INLINE_HTML_AFTER_SUBSUP_WORD_PATTERN",
    "INLINE_HTML_AFTER_SUBSUP_PUNCT_PATTERN",
    "normalize_markdown_text",
    "should_preserve_markdown_line",
    "normalize_markdown_prose_line",
    "strip_markdown_images",
    "normalize_authors",
    "normalize_abstract_text",
    "normalize_inline_html_text",
    "strip_leading_markdown_title_heading",
]
