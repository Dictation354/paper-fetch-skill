"""AMS Markdown normalization helpers."""

from __future__ import annotations

import re
from typing import Any

from ..common_patterns import FIGURE_LABEL_PATTERN, TABLE_LABEL_PATTERN
from ..utils import normalize_text
from ._ams_authors import extract_authors
from ._ams_references import extract_references

AMS_PROSE_PARENTHESIS_PATTERN = re.compile(
    r"(</(?:sub|sup)>)(\((?P<inner>[^()\n]{1,120})\))",
    flags=re.IGNORECASE,
)


def _ams_parenthetical_looks_like_math_argument(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return True
    token_match = re.fullmatch(
        r"[\w\u0370-\u03ffµμ]+\s*(?:[,;]\s*[\w\u0370-\u03ffµμ]+)*",
        normalized,
        flags=re.IGNORECASE,
    )
    if token_match:
        tokens = re.findall(r"[\w\u0370-\u03ffµμ]+", normalized)
        return bool(tokens) and all(
            len(token) == 1 or token.isdigit() for token in tokens
        )
    return bool(re.fullmatch(r"[0-9\s,.;:+\-−*/=<>^_{}\[\]\\|]+", normalized))


def _restore_ams_prose_parenthesis_match(match: re.Match[str]) -> str:
    inner = match.group("inner")
    if _ams_parenthetical_looks_like_math_argument(inner):
        return match.group(0)
    if re.search(r"[A-Za-z\u0370-\u03ffµμ]{2,}", normalize_text(inner)):
        return f"{match.group(1)} {match.group(2)}"
    return match.group(0)


def _ams_markdown_heading(block: str) -> tuple[int, str] | None:
    match = re.match(
        r"^(#{1,6})\s+(.+?)\s*$",
        normalize_text(block.splitlines()[0] if block.splitlines() else ""),
    )
    return (
        (len(match.group(1)), normalize_text(match.group(2)).rstrip(".:"))
        if match
        else None
    )


def _is_ams_markdown_heading(block: str, target: str) -> bool:
    heading = _ams_markdown_heading(block)
    if heading is None:
        return False
    normalized = normalize_text(heading[1]).lower()
    return normalized == target or (
        target == "appendix" and normalized.startswith("appendix ")
    )


def _ams_section_end_index(blocks: list[str], start: int) -> int:
    start_level = (_ams_markdown_heading(blocks[start]) or (None, ""))[0]
    index = start + 1
    while start_level is not None and index < len(blocks):
        level = (_ams_markdown_heading(blocks[index]) or (None, ""))[0]
        if level is not None and level <= start_level:
            break
        index += 1
    return index


def _reorder_ams_backmatter_sections(markdown_text: str) -> str:
    blocks = [
        block for block in re.split(r"\n\s*\n", markdown_text) if normalize_text(block)
    ]
    data_start = next(
        (
            i
            for i, block in enumerate(blocks)
            if _is_ams_markdown_heading(block, "data availability statement")
        ),
        -1,
    )
    appendix_start = next(
        (
            i
            for i, block in enumerate(blocks)
            if _is_ams_markdown_heading(block, "appendix")
        ),
        -1,
    )
    if data_start < 0 or appendix_start < 0 or data_start < appendix_start:
        return markdown_text
    data_end = _ams_section_end_index(blocks, data_start)
    data_section = blocks[data_start:data_end]
    del blocks[data_start:data_end]
    appendix_start = next(
        (
            i
            for i, block in enumerate(blocks)
            if _is_ams_markdown_heading(block, "appendix")
        ),
        len(blocks),
    )
    ack_start = next(
        (
            i
            for i, block in enumerate(blocks)
            if _is_ams_markdown_heading(block, "acknowledgments")
        ),
        -1,
    )
    insert_at = (
        _ams_section_end_index(blocks, ack_start)
        if 0 <= ack_start < appendix_start
        else appendix_start
    )
    blocks[insert_at:insert_at] = data_section
    return "\n\n".join(blocks)


def _normalize_ams_markdown_text(markdown_text: str) -> str:
    text = re.sub(r"\bFig\s+\.\s+", "Fig. ", markdown_text)
    text = re.sub(r"\bFigure\s+\.\s+", "Figure ", text)
    text = re.sub(r"\bTable\s+\.\s+", "Table ", text)
    for pattern, replacement in (
        (r"<(sup|sub)>\s*<\1>(.*?)</\1>\s*</\1>", r"<\1>\2</\1>"),
        (
            r"<sub>\s*([^<>]*?)\s*</sub>\s*<sub>\s*([,;])\s*</sub>\s*<sub>\s*([^<>]*?)\s*</sub>",
            r"<sub>\1\2\3</sub>",
        ),
        (
            r"<sub>\s*([^<>]*?)\s*</sub>\s*<sub>\s*([,;][^<>]*?)\s*</sub>",
            r"<sub>\1\2</sub>",
        ),
        (r"</sup>\s*<sup>\s*([,;])\s*</sup>\s*<sup>", r"</sup>\1<sup>"),
        (r"(\*[\w\u0370-\u03ffµμ]+\*)\s+<(sub|sup)>", r"\1<\2>"),
    ):
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = AMS_PROSE_PARENTHESIS_PATTERN.sub(_restore_ams_prose_parenthesis_match, text)
    return _reorder_ams_backmatter_sections(text)


def _normalize_ams_label_text(text: str, *, kind: str | None = None) -> str:
    normalized = normalize_text(text)
    if not normalized:
        return ""
    if kind in {None, "figure"}:
        normalized = FIGURE_LABEL_PATTERN.sub(
            lambda m: (
                f"{'Figure' if m.group(0).lower().startswith('figure') else 'Fig.'} {m.group(1)}."
            ),
            normalized,
        )
    if kind in {None, "table"}:
        normalized = TABLE_LABEL_PATTERN.sub(
            lambda m: f"Table {m.group(1)}.", normalized
        )
    return normalized


def ams_normalize_markdown(markdown_text: str) -> str:
    return _normalize_ams_markdown_text(markdown_text)


def ams_classify_heading(heading: str, title: str | None) -> str | None:
    del title
    normalized_heading = normalize_text(heading).rstrip(".").lower()
    return (
        "body_heading"
        if normalized_heading
        in {"acknowledgment", "acknowledgments", "acknowledgement", "acknowledgements"}
        else None
    )


def ams_keep_unknown_abstract_block(block: str) -> bool:
    del block
    return False


def _is_acknowledgment_heading(value: Any) -> bool:
    normalized = normalize_text(str(value or "")).rstrip(".: ").lower()
    return normalized in {
        "acknowledgment",
        "acknowledgments",
        "acknowledgement",
        "acknowledgements",
    }


def _is_ams_data_availability_heading(value: Any) -> bool:
    normalized = normalize_text(str(value or "")).rstrip(".: ").lower()
    return normalized in {"data availability", "data availability statement"}


def _normalize_ams_section_hints(section_hints: Any) -> list[dict[str, Any]]:
    normalized_hints: list[dict[str, Any]] = []
    for index, hint in enumerate(section_hints or []):
        if not isinstance(hint, dict):
            continue
        normalized_hint = dict(hint)
        heading = normalize_text(str(normalized_hint.get("heading") or "")).rstrip(
            ".: "
        )
        if heading:
            normalized_hint["heading"] = heading
        if _is_acknowledgment_heading(normalized_hint.get("heading")):
            normalized_hint["kind"] = "body"
        if _is_ams_data_availability_heading(normalized_hint.get("heading")):
            normalized_hint["kind"] = "data_availability"
        normalized_hint.setdefault("order", index)
        normalized_hints.append(normalized_hint)
    return normalized_hints


def normalize_article_model(article: Any) -> Any:
    for section in getattr(article, "sections", []) or []:
        text = getattr(section, "text", "")
        if isinstance(text, str) and text:
            section.text = _normalize_ams_markdown_text(text)
    return article


def finalize_extraction(
    html_text: str,
    source_url: str,
    markdown_text: str,
    extraction: dict[str, Any],
    *,
    metadata: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    del source_url, metadata
    extraction = dict(extraction)
    extraction["section_hints"] = _normalize_ams_section_hints(
        extraction.get("section_hints")
    )
    authors = extraction.get("extracted_authors")
    if not authors:
        extracted_authors = extract_authors(html_text)
        extraction["extracted_authors"] = extracted_authors
    references = extract_references(html_text)
    if references:
        extraction["references"] = references
    markdown_text = _normalize_ams_markdown_text(markdown_text)
    return markdown_text, extraction


__all__ = [
    "_normalize_ams_label_text",
    "_normalize_ams_markdown_text",
    "ams_classify_heading",
    "ams_keep_unknown_abstract_block",
    "ams_normalize_markdown",
    "finalize_extraction",
    "normalize_article_model",
]
