"""Table rendering helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...markdown.images import render_markdown_image
from ...utils import normalize_text
from ._ir import MarkdownTable
from .table_format import (
    normalize_table_cell_markdown_text,
    render_aligned_markdown_table,
)


def normalize_table_cell_text(value: str) -> str:
    return normalize_table_cell_markdown_text(value)


def _cell_texts(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    try:
        return [str(cell) for cell in value]
    except TypeError:
        return [str(value)]


def _row_texts(value: Any) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in value or []:
        rows.append(_cell_texts(row))
    return rows


def _same_row(left: list[str], right: list[str]) -> bool:
    if len(left) != len(right):
        return False
    return [normalize_text(cell) for cell in left] == [
        normalize_text(cell) for cell in right
    ]


def _table_matrix(table: MarkdownTable) -> list[list[str]]:
    headers = _cell_texts(table.headers)
    rows = _row_texts(table.rows)
    if headers:
        body_rows = rows[1:] if rows and _same_row(headers, rows[0]) else rows
        return [headers, *body_rows]
    return rows


def table_from_entry(entry: Mapping[str, Any]) -> MarkdownTable:
    rows = _row_texts(entry.get("rows"))
    return MarkdownTable(
        label=str(entry.get("heading") or ""),
        caption=str(entry.get("caption") or ""),
        headers=_cell_texts(entry.get("headers")),
        rows=rows,
        footnotes=tuple(
            str(note)
            for note in entry.get("footnotes", [])
            if normalize_text(str(note))
        ),
        image_fallback_url=normalize_text(str(entry.get("link") or "")) or None,
        fallback_message=normalize_text(str(entry.get("fallback_message") or "")),
    )


def _entry_prefix_rows(entry: Mapping[str, Any]) -> list[str]:
    return [
        normalize_text(str(value))
        for value in entry.get("_table_prefix_rows", []) or []
        if normalize_text(str(value))
    ]


def _insert_prefix_rows(
    lines: list[str],
    table: MarkdownTable,
    prefix_rows: list[str],
) -> list[str]:
    if not prefix_rows:
        return lines
    insert_at = 2 + (2 if table.caption else 0)
    prefix_lines = [line for prefix in prefix_rows for line in (prefix, "")]
    return [*lines[:insert_at], *prefix_lines, *lines[insert_at:]]


def render_table(table: MarkdownTable) -> list[str]:
    lines = [table.label, ""]
    if table.caption:
        lines.extend([table.caption, ""])
    matrix = _table_matrix(table)
    if matrix:
        lines.extend(render_aligned_markdown_table(matrix))
        lines.append("")
    if table.fallback_message:
        lines.extend([table.fallback_message, ""])
    if not matrix and table.image_fallback_url:
        lines.extend(
            [render_markdown_image("table", table.label, table.image_fallback_url), ""]
        )
    for footnote in table.footnotes:
        text = normalize_text(str(footnote))
        if text:
            lines.extend([text, ""])
    return lines


def render_image_table_block(entry: Mapping[str, Any]) -> list[str]:
    return render_table(
        MarkdownTable(
            label=str(entry["heading"]),
            caption=str(entry.get("caption") or ""),
            headers=[],
            rows=[],
            footnotes=tuple(
                str(note)
                for note in entry.get("footnotes", [])
                if normalize_text(str(note))
            ),
            image_fallback_url=normalize_text(str(entry.get("link") or "")) or None,
            fallback_message=normalize_text(str(entry.get("fallback_message") or "")),
        )
    )


def render_structured_table_block(entry: Mapping[str, Any]) -> list[str]:
    if entry.get("rows"):
        table = table_from_entry(entry)
        return _insert_prefix_rows(
            render_table(table),
            table,
            _entry_prefix_rows(entry),
        )
    return render_image_table_block(
        {
            **entry,
            "fallback_message": normalize_text(str(entry.get("fallback_message") or ""))
            or "Table content could not be fully converted to Markdown; original table resource is retained below.",
        }
    )


def _render_structured_list_rows(
    headers: list[str],
    rows: list[list[str]],
) -> list[str]:
    if headers and rows and _same_row(headers, rows[0]):
        rows = rows[1:]
    lines: list[str] = []
    rendered_row = False
    for row in rows:
        parts: list[str] = []
        for index, raw_value in enumerate(row):
            value = normalize_table_cell_text(raw_value)
            if not value:
                continue
            header = headers[index] if index < len(headers) else ""
            parts.append(f"{header}: {value}" if header else value)
        if parts:
            lines.append(f"- {'; '.join(parts)}")
            rendered_row = True
    if not rendered_row and headers:
        nonempty_headers = [header for header in headers if normalize_text(header)]
        if nonempty_headers:
            lines.append("- " + "; ".join(nonempty_headers))
    if rendered_row or headers:
        lines.append("")
    return lines


def render_structured_list_table_block(entry: Mapping[str, Any]) -> list[str]:
    """Render an irregular table without implying a reliable GFM grid."""

    table = table_from_entry(entry)
    lines = [table.label, ""]
    if table.caption:
        lines.extend([table.caption, ""])
    for prefix in _entry_prefix_rows(entry):
        lines.extend([prefix, ""])

    headers = _cell_texts(table.headers)
    rows = _row_texts(table.rows)
    lines.extend(_render_structured_list_rows(headers, rows))
    if table.fallback_message:
        lines.extend([table.fallback_message, ""])
    if table.image_fallback_url:
        lines.extend(
            [render_markdown_image("table", table.label, table.image_fallback_url), ""]
        )
    for footnote in table.footnotes:
        text = normalize_text(footnote)
        if text:
            lines.extend([text, ""])
    return lines


def render_grouped_table_block(entry: Mapping[str, Any]) -> list[str]:
    """Render ordered logical table groups under one label and caption."""

    table = table_from_entry(entry)
    lines = [table.label, ""]
    if table.caption:
        lines.extend([table.caption, ""])

    has_list_group = False
    raw_groups = entry.get("_table_groups") or []
    for raw_group in raw_groups:
        if not isinstance(raw_group, Mapping):
            continue
        for prefix in _entry_prefix_rows(raw_group):
            lines.extend([prefix, ""])
        headers = _cell_texts(raw_group.get("headers"))
        rows = _row_texts(raw_group.get("rows"))
        render_kind = normalize_text(
            str(raw_group.get("table_render_kind") or "structured")
        ).lower()
        if render_kind == "structured_list":
            has_list_group = True
            lines.extend(_render_structured_list_rows(headers, rows))
        else:
            group_table = MarkdownTable(
                label="",
                caption="",
                headers=headers,
                rows=rows,
            )
            matrix = _table_matrix(group_table)
            if matrix:
                lines.extend(render_aligned_markdown_table(matrix))
                lines.append("")
        fallback_message = normalize_text(str(raw_group.get("fallback_message") or ""))
        if fallback_message:
            lines.extend([fallback_message, ""])

    if table.fallback_message:
        lines.extend([table.fallback_message, ""])
    if table.image_fallback_url and has_list_group:
        lines.extend(
            [render_markdown_image("table", table.label, table.image_fallback_url), ""]
        )
    for footnote in table.footnotes:
        text = normalize_text(footnote)
        if text:
            lines.extend([text, ""])
    return lines


def render_table_block(entry: Mapping[str, Any]) -> list[str]:
    if not entry:
        return []
    if entry.get("_table_groups"):
        return render_grouped_table_block(entry)
    render_kind = normalize_text(
        str(entry.get("table_render_kind") or entry.get("kind") or "")
    ).lower()
    if render_kind == "structured":
        return render_structured_table_block(entry)
    if render_kind == "structured_list":
        return render_structured_list_table_block(entry)
    return render_image_table_block(entry)


def add_table_once(
    lines: list[str], entry: Mapping[str, Any] | None, used_table_keys: set[str]
) -> None:
    if not entry:
        return
    key = str(entry["key"])
    if key in used_table_keys:
        return
    used_table_keys.add(key)
    lines.extend(render_table_block(entry))
