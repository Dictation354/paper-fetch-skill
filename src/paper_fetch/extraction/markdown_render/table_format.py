"""Canonical Markdown pipe table formatting helpers."""

from __future__ import annotations

import re

from ...utils import normalize_text
from ...markdown.math import normalize_prose_preserving_math

TABLE_CELL_LINE_BREAK_PATTERN = re.compile(r"\s*\n+\s*")


def normalize_table_block_text(text: str) -> str:
    return normalize_prose_preserving_math(
        text,
        lambda prose: normalize_text(TABLE_CELL_LINE_BREAK_PATTERN.sub(" ", prose)),
    )


def normalize_table_cell_markdown_text(text: str) -> str:
    normalized = normalize_prose_preserving_math(text, normalize_text)
    # Pipe tables encode physical line breaks even inside opaque formulas.
    return normalized.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def escape_markdown_table_cell(text: str) -> str:
    return re.sub(
        r"(\\*)\|",
        lambda match: match[0] if len(match[1]) % 2 else match[1] + r"\|",
        normalize_table_cell_markdown_text(text),
    )


def render_aligned_markdown_table(matrix: list[list[str]]) -> list[str]:
    if not matrix:
        return []

    width = max(len(row) for row in matrix)
    if width <= 0:
        return []

    normalized_rows = [row + [""] * max(0, width - len(row)) for row in matrix]
    escaped_rows = [
        [escape_markdown_table_cell(cell) for cell in row] for row in normalized_rows
    ]
    column_widths = [
        max(3, max(len(row[index]) for row in escaped_rows)) for index in range(width)
    ]

    def format_row(row: list[str]) -> str:
        padded = [
            f" {cell.ljust(column_widths[index])} " for index, cell in enumerate(row)
        ]
        return "|" + "|".join(padded) + "|"

    header = format_row(escaped_rows[0])
    separator = (
        "|"
        + "|".join(f" {'-' * column_widths[index]} " for index in range(width))
        + "|"
    )
    body = [format_row(row) for row in escaped_rows[1:]]
    return [header, separator, *body]
