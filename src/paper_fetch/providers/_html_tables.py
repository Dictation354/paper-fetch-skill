"""Shared HTML table rendering helpers for publisher-specific extraction flows."""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping

from ..models import normalize_markdown_text
from ..utils import normalize_text

try:
    from bs4 import NavigableString, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    NavigableString = None
    Tag = None

TABLE_PLACEHOLDER_PREFIX = "PAPER_FETCH_TABLE_PLACEHOLDER_"

RenderInlineTextFn = Callable[[Any], str]
CleanMarkdownFn = Callable[[str], str]


def normalize_table_inline_text(value: str) -> str:
    text = value.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\s*(<br>)\s*", r"\1", text)
    text = re.sub(r"<(sub|sup)>\s+", r"<\1>", text)
    text = re.sub(r"\s+</(sub|sup)>", r"</\1>", text)
    text = re.sub(r"\s+(<(?:sub|sup)>)", r"\1", text)
    text = re.sub(r"(</sub>)\s+\(", r"\1(", text)
    text = re.sub(r"(</(?:sub|sup)>)\s+([,.;:%\]\}])", r"\1\2", text)
    return text.strip()


def wrap_table_text_fragment(text: str, marker: str | None) -> str:
    value = text.replace("\xa0", " ")
    has_leading_space = bool(value[:1].isspace())
    has_trailing_space = bool(value[-1:].isspace())
    normalized = re.sub(r"\s+", " ", value).strip()
    if not normalized:
        return ""
    if marker:
        normalized = f"{marker}{normalized}{marker}"
    if has_leading_space:
        normalized = f" {normalized}"
    if has_trailing_space:
        normalized = f"{normalized} "
    return normalized


def render_table_inline_node(node: Any, *, text_style: str | None = None) -> str:
    if node is None:
        return ""
    if NavigableString is not None and isinstance(node, NavigableString):
        return wrap_table_text_fragment(str(node), text_style)
    if not isinstance(node, Tag):
        return ""

    parts: list[str] = []
    for child in node.children:
        if NavigableString is not None and isinstance(child, NavigableString):
            parts.append(wrap_table_text_fragment(str(child), text_style))
            continue
        if not isinstance(child, Tag):
            continue

        name = normalize_text(child.name or "").lower()
        if name in {"i", "em"}:
            parts.append(render_table_inline_node(child, text_style="*"))
        elif name in {"b", "strong"}:
            parts.append(render_table_inline_node(child, text_style="**"))
        elif name == "sub":
            text = render_table_inline_node(child)
            if text:
                parts.append(f"<sub>{text}</sub>")
        elif name == "sup":
            text = render_table_inline_node(child)
            if text:
                parts.append(f"<sup>{text}</sup>")
        elif name == "br":
            parts.append("<br>")
        else:
            parts.append(render_table_inline_node(child, text_style=text_style))

    return normalize_table_inline_text("".join(parts))


def render_table_inline_text(node: Any) -> str:
    return render_table_inline_node(node)


def table_cell_data(cell: Tag, *, render_inline_text: RenderInlineTextFn = render_table_inline_text) -> dict[str, Any]:
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
    return {
        "text": render_inline_text(cell),
        "is_header": normalize_text(cell.name or "").lower() == "th",
        "rowspan": rowspan,
        "colspan": colspan,
    }


def table_rows(table: Tag, *, render_inline_text: RenderInlineTextFn = render_table_inline_text) -> list[list[dict[str, Any]]]:
    rows: list[list[dict[str, Any]]] = []
    for row in table.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        cells = [cell for cell in row.find_all(["th", "td"], recursive=False) if isinstance(cell, Tag)]
        if not cells:
            cells = [cell for cell in row.find_all(["th", "td"]) if isinstance(cell, Tag)]
        if not cells:
            continue
        rows.append([table_cell_data(cell, render_inline_text=render_inline_text) for cell in cells])
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
    return 0


def expanded_table_matrix(rows: list[list[dict[str, Any]]]) -> list[list[dict[str, Any]]] | None:
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
            cell = grid.get((row_index, col_index))
            if cell is None:
                return None
            expanded_row.append(cell)
        expanded_rows.append(expanded_row)
    return expanded_rows


def flatten_table_header_rows(rows: list[list[dict[str, Any]]]) -> list[str]:
    if not rows:
        return []
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
        headers.append(" / ".join(parts) or f"Column {col_index + 1}")
    return headers


def table_headers_and_data(
    table: Tag,
    *,
    render_inline_text: RenderInlineTextFn = render_table_inline_text,
) -> tuple[list[str], list[list[dict[str, Any]]], bool]:
    rows = table_rows(table, render_inline_text=render_inline_text)
    if not rows:
        return [], [], False
    header_row_count = table_header_row_count(table, rows)
    matrix = expanded_table_matrix(rows)
    if matrix is not None:
        if header_row_count:
            header_rows = matrix[:header_row_count]
            headers = flatten_table_header_rows(header_rows)
            data_rows = matrix[header_row_count:]
        else:
            headers = [f"Column {index + 1}" for index in range(len(matrix[0]))]
            data_rows = matrix
        return headers, data_rows, True

    if header_row_count:
        headers = [normalize_text(str(cell["text"])) or f"Column {index + 1}" for index, cell in enumerate(rows[0])]
        data_rows = rows[header_row_count:]
    else:
        width = max(len(row) for row in rows)
        headers = [f"Column {index + 1}" for index in range(width)]
        data_rows = rows
    return headers, data_rows, False


def escape_markdown_table_cell(text: str) -> str:
    return normalize_text(text).replace("|", r"\|")


def render_aligned_markdown_table(matrix: list[list[str]]) -> list[str]:
    if not matrix:
        return []

    width = max(len(row) for row in matrix)
    normalized_rows = [row + [""] * max(0, width - len(row)) for row in matrix]
    escaped_rows = [[escape_markdown_table_cell(cell) for cell in row] for row in normalized_rows]
    column_widths = [
        max(3, max(len(row[index]) for row in escaped_rows))
        for index in range(width)
    ]

    def format_row(row: list[str]) -> str:
        padded = [f" {cell.ljust(column_widths[index])} " for index, cell in enumerate(row)]
        return "|" + "|".join(padded) + "|"

    header = format_row(escaped_rows[0])
    separator = "|" + "|".join(f" {'-' * column_widths[index]} " for index in range(width)) + "|"
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

    heading_line = f"**{label}** {caption}".strip()
    headers, data_rows, is_simple = table_headers_and_data(table, render_inline_text=render_inline_text)
    if not headers:
        return heading_line

    lines = [heading_line, ""]
    if is_simple:
        header_row = [header or f"Column {index + 1}" for index, header in enumerate(headers)]
        body_rows: list[list[str]] = []
        for row in data_rows:
            cells = [normalize_text(str(cell.get("text") or "")) for cell in row]
            body_rows.append(cells + [""] * max(0, len(header_row) - len(cells)))
        lines.extend(render_aligned_markdown_table([header_row, *body_rows]))
        return "\n".join(lines)

    for row in data_rows:
        parts: list[str] = []
        for index, cell in enumerate(row):
            value = normalize_text(str(cell.get("text") or ""))
            if not value:
                continue
            header = headers[index] if index < len(headers) else f"Column {index + 1}"
            parts.append(f"{header}: {value}")
        if parts:
            lines.append(f"- {'; '.join(parts)}")
    if len(lines) == 2:
        lines.append("- " + "; ".join(headers))
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
        normalize_text(str(entry.get("placeholder") or "")): normalize_markdown_text(str(entry.get("markdown") or ""))
        for entry in table_entries
        if normalize_text(str(entry.get("placeholder") or "")) and normalize_text(str(entry.get("markdown") or ""))
    }
    if not replacement_by_placeholder:
        return markdown_text

    blocks = [normalize_markdown_text(block) for block in re.split(r"\n\s*\n", markdown_text) if normalize_text(block)]
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
