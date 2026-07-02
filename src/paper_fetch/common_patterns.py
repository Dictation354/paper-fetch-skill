"""Shared compiled regular expressions used across extraction paths."""

from __future__ import annotations

import re

HEADING_TAG_PATTERN = re.compile(r"^h[1-6]$")
HEADING_LEVEL_PATTERN = re.compile(r"^h([1-6])$")
INLINE_WHITESPACE_PATTERN = re.compile(r"[ \t\r\f\v]+")
WORD_TOKEN_PATTERN = re.compile(r"\b[\w][\w'-]*\b", flags=re.UNICODE)
REFERENCE_TOKEN_VOCABULARY = (
    "ref",
    "refs",
    "reference",
    "bib",
    "bibr",
    "bibliography",
    "cite",
    "citation",
    "cr",
)
EXTENDED_DATA_LABEL = "extended data"
EXTENDED_DATA_FIGURE_LABEL = "Extended Data Fig"
EXTENDED_DATA_TABLE_LABEL = "Extended Data Table"
EXTENDED_DATA_PREFIX_PATTERN = r"extended\s+data"
EXTENDED_DATA_FIGURE_PREFIX_PATTERN = rf"{EXTENDED_DATA_PREFIX_PATTERN}\s+fig"
EXTENDED_DATA_TABLE_PREFIX_PATTERN = rf"{EXTENDED_DATA_PREFIX_PATTERN}\s+table"
LABEL_NUMBER_PATTERN = r"([A-Za-z]?\d+[A-Za-z]?)"
FIGURE_LABEL_PREFIX_PATTERN = r"fig(?:ure)?"
TABLE_LABEL_PREFIX_PATTERN = r"table"
FIGURE_LABEL_CORE_PATTERN = (
    rf"{FIGURE_LABEL_PREFIX_PATTERN}\s*\.?\s*{LABEL_NUMBER_PATTERN}\s*\.?"
)
TABLE_LABEL_CORE_PATTERN = (
    rf"{TABLE_LABEL_PREFIX_PATTERN}\s*\.?\s*{LABEL_NUMBER_PATTERN}\s*\.?"
)
FIGURE_LABEL_PATTERN = re.compile(
    rf"\b{FIGURE_LABEL_CORE_PATTERN}",
    flags=re.IGNORECASE,
)
TABLE_LABEL_PATTERN = re.compile(
    rf"\b{TABLE_LABEL_CORE_PATTERN}",
    flags=re.IGNORECASE,
)
FIGURE_BASENAME_PATTERN = re.compile(
    r"(?:^|[^a-z])fig(?:ure)?[_-]?0*([A-Za-z]?\d+[A-Za-z]?)(?=$|[^a-z0-9])",
    flags=re.IGNORECASE,
)
SHORT_FIGURE_BASENAME_PATTERN = re.compile(
    r"(?:^|[^a-z])f[_-]?0*([A-Za-z]?\d+[A-Za-z]?)(?=$|[^a-z0-9])",
    flags=re.IGNORECASE,
)
EXTENDED_DATA_PREFIX_RE = re.compile(
    rf"^{EXTENDED_DATA_PREFIX_PATTERN}\b", flags=re.IGNORECASE
)


def is_extended_data_prefix(value: str | None) -> bool:
    return bool(EXTENDED_DATA_PREFIX_RE.match(str(value or "").strip()))


def table_label_prefix_for_match(value: str | None) -> str:
    return EXTENDED_DATA_TABLE_LABEL if is_extended_data_prefix(value) else "Table"
