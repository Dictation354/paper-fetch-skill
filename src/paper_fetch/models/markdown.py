"""Markdown normalization and inline text helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
import html
import re
import urllib.parse
from typing import Any

from ..common_patterns import EXTENDED_DATA_LABEL, INLINE_WHITESPACE_PATTERN
from ..utils import normalize_text, safe_text

MARKDOWN_FENCE_PATTERN = re.compile(r"^\s*(```+|~~~+)")


MARKDOWN_TABLE_RULE_PATTERN = re.compile(r"^\s*[-+:| ]{3,}\s*$")


MARKDOWN_LIST_MARKER_PATTERN = re.compile(r"^(\s{0,3}(?:[-*+]|\d+[.)])\s+)(.*)$")

ABSTRACT_PREFIX_VOCAB = ("Abstract", "Summary")
_ABSTRACT_PREFIX_TITLE_CASE_PATTERN = "|".join(
    f"[{token[0].upper()}{token[0].lower()}]{re.escape(token[1:])}"
    for token in ABSTRACT_PREFIX_VOCAB
)
_ABSTRACT_PREFIX_PATTERN = "|".join(re.escape(token) for token in ABSTRACT_PREFIX_VOCAB)

ABSTRACT_PREFIX_PATTERN = re.compile(
    rf"^(?:{_ABSTRACT_PREFIX_TITLE_CASE_PATTERN})\b[:.\-\s]+(?=[A-Z])"
)


INLINE_HTML_TAG_PATTERN = re.compile(r"</?(?:sub|sup|br)\b[^>]*>", flags=re.IGNORECASE)


INLINE_MARKDOWN_ABSTRACT_PREFIX_PATTERN = re.compile(
    rf"^\*\*(?:{_ABSTRACT_PREFIX_PATTERN})\.?\*\*\s*",
    re.IGNORECASE,
)


MARKDOWN_ABSTRACT_PREFIX_PATTERN = re.compile(
    rf"^(?:\*\*|__)(?:{_ABSTRACT_PREFIX_TITLE_CASE_PATTERN})\.?(?:\*\*|__)\s*"
)


_MARKDOWN_IMAGE_ALT_PATTERN = r"[^\]]*"
_MARKDOWN_IMAGE_URL_TARGET_PATTERN = r"[^)]+"

MARKDOWN_IMAGE_URL_PATTERN = re.compile(
    rf"!\[{_MARKDOWN_IMAGE_ALT_PATTERN}\]\(({_MARKDOWN_IMAGE_URL_TARGET_PATTERN})\)"
)


MARKDOWN_IMAGE_PATTERN = re.compile(
    rf"!\[{_MARKDOWN_IMAGE_ALT_PATTERN}\]\({_MARKDOWN_IMAGE_URL_TARGET_PATTERN}\)"
)


MARKDOWN_IMAGE_LINK_PATTERN = re.compile(
    rf"!\[({_MARKDOWN_IMAGE_ALT_PATTERN})\]\(({_MARKDOWN_IMAGE_URL_TARGET_PATTERN})\)"
)


@dataclass(frozen=True)
class MarkdownImageMatch:
    start: int
    end: int
    alt: str
    url: str
    title: str
    attrs: str
    attrs_start: int | None
    text: str


_MARKDOWN_BLOCK_IMAGE_ALT_PATTERN = rf"fig(?:ure)?\.?|(?:{re.escape(EXTENDED_DATA_LABEL)}|supplementary)?\s*table|supplementary\s+fig(?:ure)?\.?"

MARKDOWN_BLOCK_IMAGE_ALT_PATTERN = re.compile(
    rf"^\s*(?:{_MARKDOWN_BLOCK_IMAGE_ALT_PATTERN})\b",
    flags=re.IGNORECASE,
)


MARKDOWN_STANDALONE_IMAGE_ALT_PATTERN = re.compile(
    rf"^\s*(?:{_MARKDOWN_BLOCK_IMAGE_ALT_PATTERN}|formula|equation)\b",
    flags=re.IGNORECASE,
)


TABLE_LIKE_FIGURE_ASSET_PATTERN = re.compile(
    r"^(?:supplementary\s+)?table\s+\d+[A-Za-z]?\b",
    flags=re.IGNORECASE,
)


NATURE_TABLE_LIKE_FIGURE_ASSET_PATTERN = re.compile(
    rf"^{re.escape(EXTENDED_DATA_LABEL)}\s+table\s+\d+[A-Za-z]?\b",
    flags=re.IGNORECASE,
)


NUMBERED_REFERENCE_PATTERN = re.compile(r"^\s*(?:\[\d+[A-Za-z]?\]|\d+[A-Za-z]?[.)])\s+")


SLASH_RUN_PATTERN = re.compile(r"/+")


CANONICAL_MATCH_NON_WORD_PATTERN = re.compile(r"[\W_]+", flags=re.UNICODE)


INLINE_HTML_NEWLINE_WHITESPACE_PATTERN = re.compile(r"\s*\n\s*")


INLINE_HTML_BR_WHITESPACE_PATTERN = re.compile(
    r"\s*(<br\s*/?>)\s*", flags=re.IGNORECASE
)


INLINE_HTML_OPEN_SUBSUP_WHITESPACE_PATTERN = re.compile(
    r"\s*<(sub|sup)>\s*", flags=re.IGNORECASE
)


INLINE_HTML_CLOSE_SUBSUP_WHITESPACE_PATTERN = re.compile(
    r"\s+</(sub|sup)>", flags=re.IGNORECASE
)


INLINE_HTML_BEFORE_SUBSUP_PATTERN = re.compile(
    r"\s+(<(?:sub|sup)>)", flags=re.IGNORECASE
)


INLINE_HTML_AFTER_SUBSUP_NEWLINE_PATTERN = re.compile(
    r"(</(?:sub|sup)>)\s*\n\s*", flags=re.IGNORECASE
)


INLINE_HTML_AFTER_SUBSUP_WORD_PATTERN = re.compile(
    r"(</(?:sub|sup)>)(?=[A-Za-z0-9])", flags=re.IGNORECASE
)


INLINE_HTML_AFTER_SUBSUP_PUNCT_PATTERN = re.compile(
    r"(</(?:sub|sup)>)\s+([,.;:%\]\}\+\)])", flags=re.IGNORECASE
)


def image_reference_candidates(value: str | None) -> set[str]:
    normalized = normalize_text(value).strip("<>")
    if not normalized:
        return set()

    parsed = urllib.parse.urlsplit(normalized)
    path = parsed.path or normalized
    candidates = {
        normalized,
        path,
        urllib.parse.unquote(normalized),
        urllib.parse.unquote(path),
    }
    cleaned: set[str] = set()
    for candidate in candidates:
        text = normalize_text(candidate).replace("\\", "/")
        text = SLASH_RUN_PATTERN.sub("/", text).strip()
        text = text.removeprefix("./")
        if text:
            cleaned.add(text)
            cleaned.add(text.lstrip("/"))
    return cleaned


def image_reference_basename(value: str) -> str:
    return value.rstrip("/").rsplit("/", 1)[-1]


def image_references_match(left: set[str], right: set[str]) -> bool:
    if left & right:
        return True
    for left_item in left:
        for right_item in right:
            if left_item.endswith(f"/{right_item}") or right_item.endswith(
                f"/{left_item}"
            ):
                return True
    left_basenames = {
        image_reference_basename(item)
        for item in left
        if image_reference_basename(item)
    }
    right_basenames = {
        image_reference_basename(item)
        for item in right
        if image_reference_basename(item)
    }
    return bool(left_basenames & right_basenames)


def _find_balanced_markdown_delimiter(
    text: str, start: int, opener: str, closer: str
) -> int:
    depth = 1
    index = start + 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def _split_markdown_image_destination(raw_destination: str) -> tuple[str, str]:
    destination = raw_destination.strip()
    if not destination:
        return "", ""
    if destination.startswith("<"):
        close_index = destination.find(">")
        if close_index > 0:
            url = destination[1:close_index]
            title = destination[close_index + 1 :].strip()
            return url, title
    match = re.match(
        r"(?P<url>\S+)(?:\s+(?P<title>.*))?\s*$", destination, flags=re.DOTALL
    )
    if match is None:
        return destination, ""
    return match.group("url") or "", (match.group("title") or "").strip()


def _parse_markdown_image_at(text: str, start: int) -> MarkdownImageMatch | None:
    if not text.startswith("![", start):
        return None

    alt_open = start + 1
    alt_close = _find_balanced_markdown_delimiter(text, alt_open, "[", "]")
    if alt_close < 0:
        return None
    if alt_close + 1 >= len(text) or text[alt_close + 1] != "(":
        return None

    destination_open = alt_close + 1
    destination_close = _find_balanced_markdown_delimiter(
        text, destination_open, "(", ")"
    )
    if destination_close < 0:
        return None

    attrs = ""
    attrs_start: int | None = None
    end = destination_close + 1
    attr_probe = end
    while attr_probe < len(text) and text[attr_probe] in " \t":
        attr_probe += 1
    if attr_probe < len(text) and text[attr_probe] == "{":
        attr_close = text.find("}", attr_probe + 1)
        if attr_close >= 0 and "\n" not in text[attr_probe : attr_close + 1]:
            attrs_start = attr_probe
            attrs = text[attr_probe : attr_close + 1]
            end = attr_close + 1

    url, title = _split_markdown_image_destination(
        text[destination_open + 1 : destination_close]
    )
    return MarkdownImageMatch(
        start=start,
        end=end,
        alt=text[alt_open + 1 : alt_close],
        url=url,
        title=title,
        attrs=attrs,
        attrs_start=attrs_start,
        text=text[start:end],
    )


def iter_markdown_images(markdown_text: str) -> Iterator[MarkdownImageMatch]:
    text = str(markdown_text or "")
    index = 0
    while index < len(text):
        start = text.find("![", index)
        if start < 0:
            return
        match = _parse_markdown_image_at(text, start)
        if match is None:
            index = start + 2
            continue
        yield match
        index = match.end


def replace_markdown_images(
    markdown_text: str,
    replace: Callable[[MarkdownImageMatch], str],
) -> str:
    text = str(markdown_text or "")
    pieces: list[str] = []
    cursor = 0
    for image in iter_markdown_images(text):
        pieces.append(text[cursor : image.start])
        pieces.append(replace(image))
        cursor = image.end
    if cursor == 0:
        return text
    pieces.append(text[cursor:])
    return "".join(pieces)


def markdown_image_fullmatch(markdown_text: str) -> MarkdownImageMatch | None:
    text = str(markdown_text or "")
    image = _parse_markdown_image_at(text, 0)
    if image is not None and image.end == len(text):
        return image
    return None


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
    match = markdown_image_fullmatch(line.strip())
    return bool(match and _is_standalone_markdown_image_alt(match.alt))


def _split_markdown_image_adjacency_line(line: str) -> list[str]:
    matches = list(iter_markdown_images(line))
    if not matches:
        return [line]

    stripped = line.strip()
    if markdown_image_fullmatch(stripped):
        return [line]

    split_required = False
    for match in matches:
        prefix = line[: match.start]
        suffix = line[match.end :]
        if _is_block_markdown_image_alt(match.alt):
            split_required = True
            break
        if (
            _is_standalone_markdown_image_alt(match.alt)
            and re.search(
                r"\b(?:equation|formula)\b", normalize_text(prefix), flags=re.IGNORECASE
            )
            and not normalize_text(suffix)
        ):
            split_required = True
            break
        if normalize_text(prefix).endswith("$$") or normalize_text(suffix).startswith(
            "$$"
        ):
            split_required = True
            break
    if not split_required:
        return [line]

    pieces: list[str] = []
    cursor = 0
    for match in matches:
        prefix = line[cursor : match.start]
        if normalize_text(prefix):
            pieces.append(prefix.rstrip())
        pieces.append(match.text)
        cursor = match.end
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
    body = INLINE_WHITESPACE_PATTERN.sub(" ", expanded[len(leading) :]).strip()
    if not body:
        return ""
    return f"{leading}{body}" if leading else body


def strip_markdown_images(text: str) -> str:
    stripped = replace_markdown_images(text, lambda _image: "")
    return normalize_markdown_text(stripped)


def _canonical_match_text(value: str) -> str:
    return CANONICAL_MATCH_NON_WORD_PATTERN.sub("", normalize_text(value).lower())


def normalize_authors(value: Any) -> list[str]:
    if isinstance(value, list):
        return [
            normalize_inline_html_text(item)
            for item in value
            if normalize_inline_html_text(item)
        ]
    if isinstance(value, str):
        parts = [
            normalize_inline_html_text(part)
            for part in re.split(r"\s*;\s*|\s*,\s*", value)
        ]
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


def strip_leading_markdown_title_heading(
    markdown_text: str, *, title: str | None
) -> str:
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
    while line_index < len(trimmed_lines) and not normalize_text(
        trimmed_lines[line_index]
    ):
        trimmed_lines.pop(line_index)
    return normalize_markdown_text("\n".join(trimmed_lines))


__all__ = [
    "ABSTRACT_PREFIX_PATTERN",
    "CANONICAL_MATCH_NON_WORD_PATTERN",
    "INLINE_HTML_AFTER_SUBSUP_NEWLINE_PATTERN",
    "INLINE_HTML_AFTER_SUBSUP_PUNCT_PATTERN",
    "INLINE_HTML_AFTER_SUBSUP_WORD_PATTERN",
    "INLINE_HTML_BEFORE_SUBSUP_PATTERN",
    "INLINE_HTML_BR_WHITESPACE_PATTERN",
    "INLINE_HTML_CLOSE_SUBSUP_WHITESPACE_PATTERN",
    "INLINE_HTML_NEWLINE_WHITESPACE_PATTERN",
    "INLINE_HTML_OPEN_SUBSUP_WHITESPACE_PATTERN",
    "INLINE_HTML_TAG_PATTERN",
    "INLINE_MARKDOWN_ABSTRACT_PREFIX_PATTERN",
    "INLINE_WHITESPACE_PATTERN",
    "MARKDOWN_ABSTRACT_PREFIX_PATTERN",
    "MARKDOWN_BLOCK_IMAGE_ALT_PATTERN",
    "MARKDOWN_FENCE_PATTERN",
    "MARKDOWN_IMAGE_LINK_PATTERN",
    "MARKDOWN_IMAGE_PATTERN",
    "MARKDOWN_IMAGE_URL_PATTERN",
    "MARKDOWN_LIST_MARKER_PATTERN",
    "MARKDOWN_STANDALONE_IMAGE_ALT_PATTERN",
    "MARKDOWN_TABLE_RULE_PATTERN",
    "NATURE_TABLE_LIKE_FIGURE_ASSET_PATTERN",
    "NUMBERED_REFERENCE_PATTERN",
    "SLASH_RUN_PATTERN",
    "TABLE_LIKE_FIGURE_ASSET_PATTERN",
    "MarkdownImageMatch",
    "image_reference_basename",
    "image_reference_candidates",
    "image_references_match",
    "iter_markdown_images",
    "markdown_image_fullmatch",
    "normalize_abstract_text",
    "normalize_authors",
    "normalize_inline_html_text",
    "normalize_markdown_prose_line",
    "normalize_markdown_text",
    "replace_markdown_images",
    "should_preserve_markdown_line",
    "strip_leading_markdown_title_heading",
    "strip_markdown_images",
]
