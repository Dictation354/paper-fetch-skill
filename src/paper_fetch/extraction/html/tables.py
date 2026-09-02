"""Shared HTML table rendering helpers for publisher-specific extraction flows."""

from __future__ import annotations

import re
from typing import Any
from collections.abc import Callable, Mapping, Sequence

from ..table_grid import (
    TableCell,
    TableConversionReason,
    TableRow,
    normalize_table,
)
from ..markdown_render import table_format as markdown_table_format
from ...models import normalize_markdown_text
from ...utils import normalize_text
from .inline import (
    render_html_inline_node,
    wrap_html_inline_text_fragment,
)
from .shared import attr_text

from bs4 import Tag

TABLE_PLACEHOLDER_PREFIX = "PAPER_FETCH_TABLE_PLACEHOLDER_"

RenderInlineTextFn = Callable[[Any], str]
CleanMarkdownFn = Callable[[str], str]


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
        rowspan_valid = int(rowspan_text) >= 1
    except ValueError:
        rowspan = 1
        rowspan_valid = False
    try:
        colspan = max(1, int(colspan_text))
        colspan_valid = int(colspan_text) >= 1
    except ValueError:
        colspan = 1
        colspan_valid = False
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
        "span_valid": rowspan_valid and colspan_valid,
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


def _table_cell_to_ir(cell: Mapping[str, Any]) -> TableCell:
    reasons = (
        ()
        if bool(cell.get("span_valid", True))
        else (TableConversionReason.INVALID_SPAN,)
    )
    return TableCell(
        text=str(cell.get("text") or ""),
        rowspan=max(1, int(cell.get("rowspan") or 1)),
        colspan=max(1, int(cell.get("colspan") or 1)),
        is_header=bool(cell.get("is_header")),
        is_header_candidate=bool(cell.get("is_header_candidate")),
        column_start=(
            int(cell["column_start"]) if cell.get("column_start") is not None else None
        ),
        reasons=reasons,
    )


def _table_rows_to_ir(
    rows: Sequence[Sequence[Mapping[str, Any]]],
) -> tuple[TableRow, ...]:
    return tuple(
        TableRow(
            cells=tuple(_table_cell_to_ir(cell) for cell in row),
            role="header"
            if row and all(cell.get("is_header") for cell in row)
            else "body",
        )
        for row in rows
    )


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
    normalized = normalize_table(
        _table_rows_to_ir(rows),
        header_row_indices=tuple(range(header_row_count)),
        lift_leading_full_width_groups=False,
    )
    data_rows = [
        [
            {
                "text": text,
                "is_header": False,
                "is_header_candidate": False,
                "rowspan": 1,
                "colspan": 1,
                "span_valid": True,
            }
            for text in row
        ]
        for row in normalized.rows
    ]
    return list(normalized.headers), data_rows, normalized.is_rectangular


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
    return markdown_table_format.normalize_table_block_text(text)


def normalize_table_cell_markdown_text(text: str) -> str:
    return markdown_table_format.normalize_table_cell_markdown_text(text)


def escape_markdown_table_cell(text: str) -> str:
    return markdown_table_format.escape_markdown_table_cell(text)


def render_aligned_markdown_table(matrix: list[list[str]]) -> list[str]:
    return markdown_table_format.render_aligned_markdown_table(matrix)


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
    table_entries: Sequence[Mapping[str, str]] | None,
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
