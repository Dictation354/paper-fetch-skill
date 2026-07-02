"""Table rendering helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...markdown.images import render_markdown_image
from ...utils import normalize_text
from ._ir import MarkdownTable


def normalize_table_cell_text(value: str) -> str:
    text = normalize_text(value)
    text = text.replace("\n", "<br>")
    return text.replace("|", r"\|")


def table_from_entry(entry: Mapping[str, Any]) -> MarkdownTable:
    rows = [list(row) for row in entry.get("rows") or []]
    return MarkdownTable(
        label=str(entry.get("heading") or ""),
        caption=str(entry.get("caption") or ""),
        headers=list(rows[0]) if rows else [],
        rows=rows,
        footnotes=tuple(
            str(note)
            for note in entry.get("footnotes", [])
            if normalize_text(str(note))
        ),
        page_url=normalize_text(str(entry.get("page_url") or "")) or None,
        locator=normalize_text(str(entry.get("locator") or "")) or None,
        image_fallback_url=normalize_text(str(entry.get("link") or "")) or None,
    )


def render_table(table: MarkdownTable) -> list[str]:
    lines = [table.label, ""]
    if table.caption:
        lines.extend([table.caption, ""])
    if table.rows:
        lines.append("| " + " | ".join(table.rows[0]) + " |")
        lines.append("| " + " | ".join(["---"] * len(table.rows[0])) + " |")
        for row in table.rows[1:]:
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
    elif table.image_fallback_url:
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
        )
    )


def render_structured_table_block(entry: Mapping[str, Any]) -> list[str]:
    if entry.get("rows"):
        return render_table(table_from_entry(entry))
    return render_image_table_block(
        {
            **entry,
            "fallback_message": "Table content could not be fully converted to Markdown; original table resource is retained below.",
        }
    )


def render_table_block(entry: Mapping[str, Any]) -> list[str]:
    if not entry:
        return []
    render_kind = normalize_text(
        str(entry.get("table_render_kind") or entry.get("kind") or "")
    ).lower()
    if render_kind == "structured":
        return render_structured_table_block(entry)
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
