"""Shared citation marker cleanup for HTML-derived Markdown."""

from __future__ import annotations

import re
import urllib.parse

from ..utils import normalize_text

NUMERIC_CITATION_SENTINEL_PREFIX = "@@PF_CITE:"
NUMERIC_CITATION_SENTINEL_PATTERN = re.compile(r"@@PF_CITE:(?P<payload>[^@\n]+)@@")
NUMERIC_CITATION_ITEM_PATTERN = re.compile(r"(?P<start>\d{1,3})(?:\s*[–-]\s*(?P<end>\d{1,3}))?")
REFERENCE_PREFIX_SENTINEL_PATTERN = re.compile(
    rf"(?i)\brefs?\.\s*(?P<sentinel>{re.escape(NUMERIC_CITATION_SENTINEL_PREFIX)}[^@\n]+@@)"
)
PARENTHETICAL_CITATION_PATTERN = re.compile(r"\((?P<inner>[^()\n]{1,160})\)")
ADJACENT_SENTINEL_RUN_PATTERN = re.compile(
    rf"{re.escape(NUMERIC_CITATION_SENTINEL_PREFIX)}[^@\n]+@@(?:\s*[,–-]\s*{re.escape(NUMERIC_CITATION_SENTINEL_PREFIX)}[^@\n]+@@)+"
)
INLINE_SUP_SUB_TEXT_PATTERN = re.compile(r"<(?P<tag>sub|sup)>(?P<body>[^<>]*)</(?P=tag)>")
INLINE_ARTICLE_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((?:/(?:article|articles)/[^)]+|#[^)]+)\)")
LABEL_PATTERN = re.compile(r"\b((?:Extended Data|Fig|Figs|Tab|Tabs|Eq|Eqs|Ref|Refs))\s+(\d+[A-Za-z]?)\b")
FIGURE_LINE_PATTERN = re.compile(r"(?im)^(?:extended data\s+)?fig\.\s*[a-z0-9.-]+:.*$")
REFERENCE_FRAGMENT_PATTERN = re.compile(
    r"(?:"
    r"(?:.*(?:ref|bib|cite)[-_\w]*)"
    r"|(?:core-collateral-r\d+[a-z0-9-]*)"
    r"|(?:r\d+[a-z0-9-]*)"
    r"|(?:cr\d+[a-z0-9-]*)"
    r")$",
    flags=re.IGNORECASE,
)


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
    return NUMERIC_CITATION_SENTINEL_PATTERN.sub(lambda match: match.group("payload"), text)


def _coalesce_sentinel_run(text: str) -> str:
    expanded = _replace_sentinels_with_payloads(text).replace("*", "")
    sentinel = make_numeric_citation_sentinel(expanded)
    return sentinel or text


def _normalize_inline_sup_sub_spacing(text: str) -> str:
    def normalize_match(match: re.Match[str]) -> str:
        tag = match.group("tag")
        body = match.group("body")
        stripped = body.strip()
        if not stripped:
            return ""
        trailing_space = " " if body and body[-1].isspace() else ""
        return f"<{tag}>{stripped}</{tag}>{trailing_space}"

    return INLINE_SUP_SUB_TEXT_PATTERN.sub(normalize_match, text)


def normalize_inline_citation_markdown(text: str) -> str:
    if not text:
        return ""

    normalized = text
    normalized = REFERENCE_PREFIX_SENTINEL_PATTERN.sub(lambda match: match.group("sentinel"), normalized)
    normalized = ADJACENT_SENTINEL_RUN_PATTERN.sub(lambda match: _coalesce_sentinel_run(match.group(0)), normalized)

    def replace_parenthetical(match: re.Match[str]) -> str:
        inner = match.group("inner")
        if NUMERIC_CITATION_SENTINEL_PREFIX not in inner and "*" not in inner:
            return match.group(0)
        normalized_inner = _replace_sentinels_with_payloads(inner).replace("*", "")
        sentinel = make_numeric_citation_sentinel(normalized_inner)
        return sentinel or match.group(0)

    normalized = PARENTHETICAL_CITATION_PATTERN.sub(replace_parenthetical, normalized)
    normalized = ADJACENT_SENTINEL_RUN_PATTERN.sub(lambda match: _coalesce_sentinel_run(match.group(0)), normalized)

    def render_sentinel(match: re.Match[str]) -> str:
        payload = numeric_citation_payload(match.group("payload"))
        if payload is None:
            return match.group(0)
        return f"<sup>{payload}</sup>"

    normalized = NUMERIC_CITATION_SENTINEL_PATTERN.sub(render_sentinel, normalized)
    normalized = _normalize_inline_sup_sub_spacing(normalized)
    normalized = re.sub(r"\s+(<(?:(?:sub|sup)\b[^>]*)>)", r"\1", normalized)
    normalized = re.sub(r"(</(?:sub|sup)>)\s+([,.;:!?])", r"\1\2", normalized)
    normalized = re.sub(r"\s+([,.;:!?])", r"\1", normalized)
    normalized = re.sub(r"([(\[])\s+", r"\1", normalized)
    normalized = re.sub(r"\s+([)\]])", r"\1", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    return normalized.strip()


def is_citation_text(text: str) -> bool:
    return numeric_citation_payload(text) is not None


def is_reference_href(href: str) -> bool:
    normalized_href = normalize_text(href)
    if not normalized_href:
        return False
    parsed = urllib.parse.urlparse(normalized_href)
    fragment = normalize_text(parsed.fragment or "")
    if fragment:
        return bool(REFERENCE_FRAGMENT_PATTERN.search(fragment))
    if not normalized_href.startswith("#"):
        return False
    return bool(REFERENCE_FRAGMENT_PATTERN.search(normalized_href[1:]))


def is_citation_link(href: str, text: str) -> bool:
    return is_citation_text(text) and is_reference_href(href)


def _join_label_reference(match: re.Match[str]) -> str:
    return f"{match.group(1)}{match.group(2)}"


def clean_citation_markers(
    text: str,
    *,
    unwrap_inline_links: bool = False,
    normalize_labels: bool = False,
    drop_figure_lines: bool = False,
) -> str:
    if not text:
        return ""

    cleaned = text
    if drop_figure_lines:
        cleaned = FIGURE_LINE_PATTERN.sub("", cleaned)
        cleaned = re.sub(r"(?im)^\s*source data\s*$", "", cleaned)
    if unwrap_inline_links:
        cleaned = INLINE_ARTICLE_LINK_PATTERN.sub(r"\1", cleaned)
    if normalize_labels:
        cleaned = LABEL_PATTERN.sub(_join_label_reference, cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"([(\[])\s+", r"\1", cleaned)
    cleaned = re.sub(r"\s+([)\]])", r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return cleaned.strip()
