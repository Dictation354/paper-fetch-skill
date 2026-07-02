"""Shared citation marker cleanup for HTML-derived Markdown."""

from __future__ import annotations

import re
from collections.abc import Sequence

from ..extraction.citation_anchors import looks_like_reference_href
from ..utils import normalize_text
from .inline_spacing import normalize_inline_sup_sub_tag_bodies

NUMERIC_CITATION_SENTINEL_PREFIX = "@@PF_CITE:"
NUMERIC_CITATION_SENTINEL_PATTERN = re.compile(r"@@PF_CITE:(?P<payload>[^@\n]+)@@")
INLINE_TOKEN_MARKER_PATTERN = re.compile(
    rf"{re.escape(NUMERIC_CITATION_SENTINEL_PREFIX)}|</?(?:sub|sup)\b|<br\s*/?>",
    flags=re.IGNORECASE,
)
FENCED_CODE_BLOCK_PATTERN = re.compile(r"(?ms)(^```.*?^```|^~~~.*?^~~~)")
NUMERIC_CITATION_ITEM_PATTERN = re.compile(
    r"(?P<start>\d{1,3})(?:\s*[–-]\s*(?P<end>\d{1,3}))?"
)
REFERENCE_PREFIX_SENTINEL_PATTERN = re.compile(
    rf"(?i)\brefs?\.\s*(?P<sentinel>{re.escape(NUMERIC_CITATION_SENTINEL_PREFIX)}[^@\n]+@@)"
)
# The 160-character cap is a conservative guardrail to avoid swallowing
# unrelated parentheticals across long prose spans.
PARENTHETICAL_CITATION_PATTERN = re.compile(r"\((?P<inner>[^()\n]{1,160})\)")
ADJACENT_SENTINEL_RUN_PATTERN = re.compile(
    rf"{re.escape(NUMERIC_CITATION_SENTINEL_PREFIX)}[^@\n]+@@(?:\s*[,–-]\s*{re.escape(NUMERIC_CITATION_SENTINEL_PREFIX)}[^@\n]+@@)+"
)
COMMON_LABEL_PATTERN = re.compile(
    r"\b((?:Fig|Figs|Tab|Tabs|Eq|Eqs|Ref|Refs))\.?\s+(\d+[A-Za-z]?)\b",
    flags=re.IGNORECASE,
)
# Tuple wrappers are intentional extension points for provider-specific
# additions such as Springer/Nature Extended Data labels and source-data lines.
COMMON_LABEL_PATTERNS = (COMMON_LABEL_PATTERN,)
COMMON_FIGURE_LINE_PATTERN = re.compile(r"(?im)^fig\.\s*[a-z0-9.-]+:.*$")
COMMON_FIGURE_LINE_PATTERNS = (COMMON_FIGURE_LINE_PATTERN,)


def numeric_citation_payload(text: str) -> str | None:
    normalized = normalize_text(text).replace("−", "–").replace("—", "–")
    if not normalized:
        return None
    parts = [part.strip() for part in normalized.split(",")]
    if not parts:
        return None
    rendered_parts: list[str] = []
    for part in parts:
        if not part:
            return None
        match = NUMERIC_CITATION_ITEM_PATTERN.fullmatch(part)
        if match is None:
            return None
        start = match.group("start")
        end = match.group("end")
        rendered_parts.append(f"{start}–{end}" if end else start)
    return ", ".join(rendered_parts)


def make_numeric_citation_sentinel(text: str) -> str | None:
    payload = numeric_citation_payload(text)
    if payload is None:
        return None
    return f"{NUMERIC_CITATION_SENTINEL_PREFIX}{payload}@@"


def _replace_sentinels_with_payloads(text: str) -> str:
    return NUMERIC_CITATION_SENTINEL_PATTERN.sub(
        lambda match: match.group("payload"), text
    )


def _coalesce_sentinel_run(text: str) -> str:
    expanded = _replace_sentinels_with_payloads(text).replace("*", "")
    sentinel = make_numeric_citation_sentinel(expanded)
    return sentinel or text


def _normalize_inline_token_lines(text: str) -> str:
    from ..extraction.html.inline import inline_markdown_tokens, render_inline_tokens

    def normalize_part(part: str) -> str:
        lines = part.splitlines(keepends=True)
        rendered_lines: list[str] = []
        for line in lines:
            newline = ""
            body = line
            if line.endswith("\r\n"):
                body = line[:-2]
                newline = "\r\n"
            elif line.endswith("\n"):
                body = line[:-1]
                newline = "\n"
            if INLINE_TOKEN_MARKER_PATTERN.search(body):
                body = render_inline_tokens(
                    inline_markdown_tokens(body, parse_citations=True),
                    policy="body",
                    collapse_newlines=False,
                    break_render="<br>",
                    strip=False,
                )
            rendered_lines.append(f"{body}{newline}")
        return "".join(rendered_lines)

    parts = FENCED_CODE_BLOCK_PATTERN.split(text)
    if len(parts) == 1:
        return normalize_part(text)
    normalized_parts: list[str] = []
    for part in parts:
        if not part:
            continue
        if FENCED_CODE_BLOCK_PATTERN.fullmatch(part):
            normalized_parts.append(part)
        else:
            normalized_parts.append(normalize_part(part))
    return "".join(normalized_parts)


def normalize_inline_citation_markdown(text: str) -> str:
    if not text:
        return ""

    normalized = text
    normalized = REFERENCE_PREFIX_SENTINEL_PATTERN.sub(
        lambda match: match.group("sentinel"), normalized
    )
    normalized = ADJACENT_SENTINEL_RUN_PATTERN.sub(
        lambda match: _coalesce_sentinel_run(match.group(0)), normalized
    )

    def replace_parenthetical(match: re.Match[str]) -> str:
        inner = match.group("inner")
        if NUMERIC_CITATION_SENTINEL_PREFIX not in inner and "*" not in inner:
            return match.group(0)
        normalized_inner = _replace_sentinels_with_payloads(inner).replace("*", "")
        sentinel = make_numeric_citation_sentinel(normalized_inner)
        return sentinel or match.group(0)

    normalized = PARENTHETICAL_CITATION_PATTERN.sub(replace_parenthetical, normalized)
    normalized = ADJACENT_SENTINEL_RUN_PATTERN.sub(
        lambda match: _coalesce_sentinel_run(match.group(0)), normalized
    )

    def render_sentinel(match: re.Match[str]) -> str:
        payload = numeric_citation_payload(match.group("payload"))
        if payload is None:
            return match.group(0)
        return f"<sup>{payload}</sup>"

    normalized = _normalize_inline_token_lines(normalized)
    normalized = NUMERIC_CITATION_SENTINEL_PATTERN.sub(render_sentinel, normalized)
    normalized = normalize_inline_sup_sub_tag_bodies(normalized)
    normalized = re.sub(r"(</(?:sub|sup)>)\s+([,.;:?]|!(?!\[))", r"\1\2", normalized)
    normalized = re.sub(r"\s+([,.;:?]|!(?!\[))", r"\1", normalized)
    normalized = re.sub(r"([(\[])\s+", r"\1", normalized)
    normalized = re.sub(r"\s+([)\]])", r"\1", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    return normalized.strip()


def is_citation_text(text: str) -> bool:
    return numeric_citation_payload(text) is not None


def is_reference_href(href: str) -> bool:
    return looks_like_reference_href(href)


def is_citation_link(href: str, text: str) -> bool:
    return is_citation_text(text) and is_reference_href(href)


def _join_label_reference(match: re.Match[str]) -> str:
    return f"{match.group(1)}{match.group(2)}"


def clean_citation_markers(
    text: str,
    *,
    unwrap_inline_links: bool = False,
    inline_link_patterns: Sequence[re.Pattern[str]] | None = None,
    normalize_labels: bool = False,
    label_patterns: Sequence[re.Pattern[str]] | None = None,
    drop_figure_lines: bool = False,
    figure_line_patterns: Sequence[re.Pattern[str]] | None = None,
) -> str:
    if not text:
        return ""

    cleaned = text
    if drop_figure_lines:
        for pattern in figure_line_patterns or COMMON_FIGURE_LINE_PATTERNS:
            cleaned = pattern.sub("", cleaned)
    if unwrap_inline_links:
        for pattern in inline_link_patterns or ():
            cleaned = pattern.sub(r"\1", cleaned)
    if normalize_labels:
        for pattern in label_patterns or COMMON_LABEL_PATTERNS:
            cleaned = pattern.sub(_join_label_reference, cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"([(\[])\s+", r"\1", cleaned)
    cleaned = re.sub(r"\s+([)\]])", r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return cleaned.strip()
