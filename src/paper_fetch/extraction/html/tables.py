"""Shared HTML table rendering helpers for publisher-specific extraction flows."""

from __future__ import annotations

import re
from typing import Any
from collections.abc import Callable, Mapping

from ...models import normalize_markdown_text
from ...utils import normalize_text
from .inline import (
    normalize_html_inline_text,
    render_html_inline_node,
    wrap_html_inline_text_fragment,
)
from .shared import attr_text

from bs4 import Tag

TABLE_PLACEHOLDER_PREFIX = "PAPER_FETCH_TABLE_PLACEHOLDER_"
TABLE_CELL_LINE_BREAK_PATTERN = re.compile(r"\s*\n+\s*")

RenderInlineTextFn = Callable[[Any], str]
CleanMarkdownFn = Callable[[str], str]


def normalize_table_inline_text(value: str) -> str:
    return normalize_html_inline_text(value, policy="table_cell")


def wrap_table_text_fragment(text: str, marker: str | None) -> str:
    return wrap_html_inline_text_fragment(text, marker)


def render_table_inline_node(node: Any, *, text_style: str | None = None) -> str:
    return render_html_inline_node(node, policy="table_cell", text_style=text_style)


def render_table_inline_text(node: Any) -> str:
    return render_table_inline_node(node)


def table_cell_data(
    cell: Tag, *, render_inline_text: RenderInlineTextFn = render_table_inline_text
) -> dict[str, Any]:
    rowspan_text = normalize_text(str(cell.get("rowspan") or "1")) or "1"
    colspan_text = normalize_text(str(cell.get("colspan") or "1")) or "1"
    try:
        rowspan = max(1, int(rowspan_text))
    except ValueError:
        rowspan = 1
    try:
        colspan = max(1, int(colspan_text))
    except ValueError:
        colspan = 1
    class_values: Any = cell.get("class") or []
    if isinstance(class_values, str):
        classes = {
            normalize_text(item).lower()
            for item in class_values.split()
            if normalize_text(item)
        }
    else:
        classes = {
            normalize_text(str(item)).lower()
            for item in class_values
            if normalize_text(str(item))
        }
    is_header = normalize_text(cell.name or "").lower() == "th"
    has_bold_text = cell.find(["b", "strong"]) is not None or bool(
        cell.select(".ltx_font_bold")
    )
    is_header_candidate = (
        is_header
        or attr_text(cell.get("scope"))
        or bool(classes & {"ltx_th", "ltx_th_column", "ltx_th_row"})
        or (has_bold_text and "ltx_border_tt" in classes)
    )
    return {
        "text": render_inline_text(cell),
        "is_header": is_header,
        "is_header_candidate": bool(is_header_candidate),
        "rowspan": rowspan,
        "colspan": colspan,
    }


def table_rows(
    table: Tag, *, render_inline_text: RenderInlineTextFn = render_table_inline_text
) -> list[list[dict[str, Any]]]:
    rows: list[list[dict[str, Any]]] = []
    for row in table.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        cells = [
            cell
            for cell in row.find_all(["th", "td"], recursive=False)
            if isinstance(cell, Tag)
        ]
        if not cells:
            cells = [
                cell for cell in row.find_all(["th", "td"]) if isinstance(cell, Tag)
            ]
        if not cells:
            continue
        rows.append(
            [
                table_cell_data(cell, render_inline_text=render_inline_text)
                for cell in cells
            ]
        )
    return rows


def table_header_row_count(table: Tag, rows: list[list[dict[str, Any]]]) -> int:
    thead = table.find("thead")
    if isinstance(thead, Tag):
        return len([row for row in thead.find_all("tr") if isinstance(row, Tag)])
    leading_all_header_rows = 0
    for row in rows:
        if row and all(cell.get("is_header") for cell in row):
            leading_all_header_rows += 1
            continue
        break
    if leading_all_header_rows:
        return leading_all_header_rows
    if rows and rows[0] and any(cell.get("is_header") for cell in rows[0]):
        return 1
    if (
        rows
        and rows[0]
        and len(rows) > 1
        and all(normalize_text(str(cell.get("text") or "")) for cell in rows[0])
        and all(cell.get("is_header_candidate") for cell in rows[0])
    ):
        return 1
    return 0


def table_row_declared_width(row: list[dict[str, Any]]) -> int:
    return sum(max(1, int(cell.get("colspan") or 1)) for cell in row)


def row_looks_like_column_header(row: list[dict[str, Any]]) -> bool:
    if not row or not all(normalize_text(str(cell.get("text") or "")) for cell in row):
        return False
    return any(cell.get("is_header") or cell.get("is_header_candidate") for cell in row)


def leading_full_width_spanner_rows(
    rows: list[list[dict[str, Any]]],
) -> tuple[list[str], list[list[dict[str, Any]]]]:
    lifted: list[str] = []
    index = 0
    while index + 1 < len(rows):
        row = rows[index]
        next_row = rows[index + 1]
        if len(row) != 1:
            break
        cell = row[0]
        text = normalize_table_block_text(str(cell.get("text") or ""))
        colspan = max(1, int(cell.get("colspan") or 1))
        next_width = table_row_declared_width(next_row)
        if not text or colspan <= 1 or next_width <= 1 or colspan < next_width:
            break
        if not row_looks_like_column_header(next_row):
            break
        lifted.append(text)
        index += 1
    return lifted, rows[index:]


def expanded_table_matrix(
    rows: list[list[dict[str, Any]]],
) -> list[list[dict[str, Any]]] | None:
    if not rows:
        return None
    grid: dict[tuple[int, int], dict[str, Any]] = {}
    max_width = 0

    for row_index, row in enumerate(rows):
        col_index = 0
        for cell in row:
            while (row_index, col_index) in grid:
                col_index += 1
            rowspan = max(1, int(cell.get("rowspan") or 1))
            colspan = max(1, int(cell.get("colspan") or 1))
            for row_offset in range(rowspan):
                for col_offset in range(colspan):
                    grid[(row_index + row_offset, col_index + col_offset)] = {
                        "text": cell.get("text") or "",
                        "is_header": bool(cell.get("is_header")),
                        "rowspan": 1,
                        "colspan": 1,
                    }
            col_index += colspan
            max_width = max(max_width, col_index)

    if max_width <= 0:
        return None

    expanded_rows: list[list[dict[str, Any]]] = []
    for row_index in range(len(rows)):
        expanded_row: list[dict[str, Any]] = []
        for col_index in range(max_width):
            grid_cell = grid.get((row_index, col_index))
            if grid_cell is None:
                return None
            expanded_row.append(grid_cell)
        expanded_rows.append(expanded_row)
    return expanded_rows


def flatten_table_header_rows(rows: list[list[dict[str, Any]]]) -> list[str]:
    if not rows:
        return []
    rows = normalize_table_header_rows(rows)
    width = len(rows[0])
    headers: list[str] = []
    for col_index in range(width):
        parts: list[str] = []
        for row in rows:
            if col_index >= len(row):
                return []
            text = normalize_text(str(row[col_index].get("text") or ""))
            if not text:
                continue
            if not parts or text != parts[-1]:
                parts.append(text)
        headers.append(" / ".join(parts))
    return headers


def normalize_table_header_rows(
    rows: list[list[dict[str, Any]]],
) -> list[list[dict[str, Any]]]:
    if len(rows) <= 1:
        return rows
    first_row = rows[0]
    first_texts = [normalize_text(str(cell.get("text") or "")) for cell in first_row]
    if not first_texts or any(not text for text in first_texts):
        return rows
    if len(set(first_texts)) != 1:
        return rows
    next_row_texts = [normalize_text(str(cell.get("text") or "")) for cell in rows[1]]
    if not any(next_row_texts):
        return rows
    return rows[1:]


def table_headers_and_data(
    table: Tag,
    *,
    render_inline_text: RenderInlineTextFn = render_table_inline_text,
) -> tuple[list[str], list[list[dict[str, Any]]], bool]:
    rows = table_rows(table, render_inline_text=render_inline_text)
    lifted_spanners, rows = leading_full_width_spanner_rows(rows)
    return table_headers_and_data_from_rows(table, rows, use_thead=not lifted_spanners)


def table_headers_and_data_from_rows(
    table: Tag,
    rows: list[list[dict[str, Any]]],
    *,
    use_thead: bool,
) -> tuple[list[str], list[list[dict[str, Any]]], bool]:
    if not rows:
        return [], [], False
    header_row_count = (
        table_header_row_count(table, rows)
        if use_thead
        else table_header_row_count_without_thead(rows)
    )
    matrix = expanded_table_matrix(rows)
    if matrix is not None:
        if header_row_count:
            header_rows = matrix[:header_row_count]
            headers = flatten_table_header_rows(header_rows)
            data_rows = matrix[header_row_count:]
        else:
            headers = ["" for _index in range(len(matrix[0]))]
            data_rows = matrix
        return headers, data_rows, True

    if header_row_count:
        headers = [normalize_text(str(cell["text"])) for cell in rows[0]]
        data_rows = rows[header_row_count:]
    else:
        width = max(len(row) for row in rows)
        headers = ["" for _index in range(width)]
        data_rows = rows
    return headers, data_rows, False


def table_header_row_count_without_thead(rows: list[list[dict[str, Any]]]) -> int:
    leading_all_header_rows = 0
    for row in rows:
        if row and all(cell.get("is_header") for cell in row):
            leading_all_header_rows += 1
            continue
        break
    if leading_all_header_rows:
        return leading_all_header_rows
    if rows and rows[0] and any(cell.get("is_header") for cell in rows[0]):
        return 1
    if (
        rows
        and rows[0]
        and len(rows) > 1
        and all(normalize_text(str(cell.get("text") or "")) for cell in rows[0])
        and all(cell.get("is_header_candidate") for cell in rows[0])
    ):
        return 1
    return 0


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


def render_table_markdown(
    table_node: Tag,
    *,
    label: str,
    caption: str,
    render_inline_text: RenderInlineTextFn = render_table_inline_text,
) -> str:
    table = table_node.find("table") if table_node.name != "table" else table_node
    if not isinstance(table, Tag):
        return ""

    heading_parts: list[str] = []
    normalized_label = normalize_text(label)
    normalized_caption = normalize_text(caption)
    if normalized_label:
        heading_parts.append(f"**{normalized_label}**")
    if normalized_caption:
        heading_parts.append(normalized_caption)
    heading_line = " ".join(heading_parts).strip()
    lines = [heading_line, ""] if heading_line else []
    rows = table_rows(table, render_inline_text=render_inline_text)
    lifted_spanners, rows = leading_full_width_spanner_rows(rows)
    for spanner in lifted_spanners:
        if heading_line and normalize_text(spanner) == normalize_text(heading_line):
            continue
        lines.extend([spanner, ""])

    headers, data_rows, is_simple = table_headers_and_data_from_rows(
        table,
        rows,
        use_thead=not lifted_spanners,
    )
    if not headers:
        return "\n".join(lines).rstrip()

    if is_simple:
        header_row = [header for header in headers]
        body_rows: list[list[str]] = []
        for row in data_rows:
            cells = [normalize_text(str(cell.get("text") or "")) for cell in row]
            nonempty_cells = [cell for cell in cells if cell]
            if len(nonempty_cells) > 1 and len(set(nonempty_cells)) == 1:
                cells = [nonempty_cells[0], *[""] * (len(cells) - 1)]
            body_rows.append(cells + [""] * max(0, len(header_row) - len(cells)))
        lines.extend(render_aligned_markdown_table([header_row, *body_rows]))
        return "\n".join(lines)

    for row in data_rows:
        parts: list[str] = []
        for index, cell in enumerate(row):
            value = normalize_table_cell_markdown_text(str(cell.get("text") or ""))
            if not value:
                continue
            header = headers[index] if index < len(headers) else ""
            parts.append(f"{header}: {value}" if header else value)
        if parts:
            lines.append(f"- {'; '.join(parts)}")
    if not any(line.startswith("- ") for line in lines):
        fallback_headers = [header for header in headers if normalize_text(header)]
        if fallback_headers:
            lines.append("- " + "; ".join(fallback_headers))
    return "\n".join(lines)


def table_placeholder(index: int) -> str:
    return f"{TABLE_PLACEHOLDER_PREFIX}{index:04d}"


def inject_inline_table_blocks(
    markdown_text: str,
    *,
    table_entries: list[Mapping[str, str]] | None,
    clean_markdown_fn: CleanMarkdownFn,
) -> str:
    if not table_entries:
        return markdown_text
    replacement_by_placeholder = {
        normalize_text(str(entry.get("placeholder") or "")): normalize_markdown_text(
            str(entry.get("markdown") or "")
        )
        for entry in table_entries
        if normalize_text(str(entry.get("placeholder") or ""))
        and normalize_text(str(entry.get("markdown") or ""))
    }
    if not replacement_by_placeholder:
        return markdown_text

    blocks = [
        normalize_markdown_text(block)
        for block in re.split(r"\n\s*\n", markdown_text)
        if normalize_text(block)
    ]
    if not blocks:
        return markdown_text

    injected: list[str] = []
    for block in blocks:
        replacement = replacement_by_placeholder.get(normalize_text(block))
        if replacement is None:
            injected.append(block)
            continue
        injected.extend(
            normalize_markdown_text(part)
            for part in re.split(r"\n\s*\n", replacement)
            if normalize_text(part)
        )
    return clean_markdown_fn("\n\n".join(injected))
