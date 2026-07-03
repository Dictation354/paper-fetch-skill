"""Canonical Markdown pipe table formatting helpers."""

from __future__ import annotations

import re

from ...utils import normalize_text

TABLE_CELL_LINE_BREAK_PATTERN = re.compile(r"\s*\n+\s*")


def normalize_table_block_text(text: str) -> str:
    return normalize_text(TABLE_CELL_LINE_BREAK_PATTERN.sub(" ", text))


def normalize_table_cell_markdown_text(text: str) -> str:
    return TABLE_CELL_LINE_BREAK_PATTERN.sub("<br>", normalize_text(text))


def escape_markdown_table_cell(text: str) -> str:
    return normalize_table_cell_markdown_text(text).replace("|", r"\|")


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
