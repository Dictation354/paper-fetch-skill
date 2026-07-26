"""Elsevier XML table conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET
from typing import Any
from collections.abc import Mapping

from ._article_markdown_common import (
    add_table_once,
    first_child,
    first_descendant,
    normalize_table_cell_text,
    normalize_text,
    render_inline_text,
    xml_local_name,
)


@dataclass
class ElsevierTableRenderResult:
    rows: list[list[str]]
    lossy: bool = False
    note: str | None = None


def _elsevier_table_rows_in_order(
    tgroup: ET.Element | None,
) -> tuple[list[ET.Element], list[ET.Element]]:
    header_rows: list[ET.Element] = []
    body_rows: list[ET.Element] = []
    if tgroup is None:
        return header_rows, body_rows
    thead = first_child(tgroup, "thead")
    tbody = first_child(tgroup, "tbody")
    if thead is not None:
        header_rows.extend(
            child
            for child in list(thead)
            if isinstance(child.tag, str) and xml_local_name(child.tag) == "row"
        )
    if tbody is not None:
        body_rows.extend(
            child
            for child in list(tbody)
            if isinstance(child.tag, str) and xml_local_name(child.tag) == "row"
        )
    if not header_rows and not body_rows:
        body_rows.extend(
            child
            for child in list(tgroup)
            if isinstance(child.tag, str) and xml_local_name(child.tag) == "row"
        )
    return header_rows, body_rows


def _elsevier_table_column_map(tgroup: ET.Element | None) -> tuple[int, dict[str, int]]:
    if tgroup is None:
        return 0, {}
    columns: list[str] = []
    for child in list(tgroup):
        if not isinstance(child.tag, str) or xml_local_name(child.tag) != "colspec":
            continue
        colname = normalize_text(child.get("colname"))
        if colname:
            columns.append(colname)
    cols_attr = int(normalize_text(tgroup.get("cols")) or 0)
    col_count = max(cols_attr, len(columns))
    return col_count, {name: index for index, name in enumerate(columns)}


def render_elsevier_table_result(table: ET.Element | None) -> ElsevierTableRenderResult:
    if table is None:
        return ElsevierTableRenderResult(rows=[])

    tgroup = first_child(table, "tgroup")
    if tgroup is None:
        tgroup = first_descendant(table, "tgroup")
    header_row_nodes, body_row_nodes = _elsevier_table_rows_in_order(tgroup)
    row_nodes = [*header_row_nodes, *body_row_nodes]
    if not row_nodes:
        return ElsevierTableRenderResult(rows=[])

    col_count, col_index_by_name = _elsevier_table_column_map(tgroup)
    if col_count <= 0:
        col_count = max(
            len(
                [
                    entry
                    for entry in list(row)
                    if isinstance(entry.tag, str)
                    and xml_local_name(entry.tag) == "entry"
                ]
            )
            for row in row_nodes
        )
    if col_count <= 0:
        return ElsevierTableRenderResult(rows=[])

    active_rowspans: list[dict[str, Any] | None] = [None] * col_count
    rendered_rows: list[list[str]] = []
    lossy = False

    for row in row_nodes:
        rendered: list[str | None] = [None] * col_count
        for index in range(col_count):
            active_span = active_rowspans[index]
            if active_span is not None and int(active_span.get("remaining") or 0) > 0:
                rendered[index] = str(active_span.get("text") or "")
                active_span["remaining"] = int(active_span.get("remaining") or 0) - 1
                if int(active_span.get("remaining") or 0) <= 0:
                    active_rowspans[index] = None

        cursor = 0
        entries = [
            entry
            for entry in list(row)
            if isinstance(entry.tag, str) and xml_local_name(entry.tag) == "entry"
        ]
        if not entries:
            continue

        for entry in entries:
            while cursor < col_count and rendered[cursor] is not None:
                cursor += 1
            start_idx = cursor
            named_start = normalize_text(entry.get("namest"))
            named_end = normalize_text(entry.get("nameend"))
            if named_start:
                if named_start not in col_index_by_name:
                    return ElsevierTableRenderResult(rows=[])
                start_idx = col_index_by_name[named_start]
            if start_idx >= col_count:
                return ElsevierTableRenderResult(rows=[])
            end_idx = start_idx
            if named_end:
                if named_end not in col_index_by_name:
                    return ElsevierTableRenderResult(rows=[])
                end_idx = col_index_by_name[named_end]
            if end_idx < start_idx or end_idx >= col_count:
                return ElsevierTableRenderResult(rows=[])
            if any(
                rendered[index] is not None for index in range(start_idx, end_idx + 1)
            ):
                return ElsevierTableRenderResult(rows=[])

            rowspan = int(normalize_text(entry.get("morerows")) or 0) + 1
            colspan = end_idx - start_idx + 1
            if rowspan > 1 or colspan > 1:
                lossy = True

            text = normalize_table_cell_text(render_inline_text(entry))
            rendered[start_idx] = text
            for index in range(start_idx + 1, end_idx + 1):
                rendered[index] = text
            if rowspan > 1:
                for index in range(start_idx, end_idx + 1):
                    active_rowspans[index] = {
                        "remaining": max(
                            int((active_rowspans[index] or {}).get("remaining") or 0),
                            rowspan - 1,
                        ),
                        "text": text,
                    }
            cursor = end_idx + 1

        rendered_rows.append([cell if cell is not None else "" for cell in rendered])

    if not rendered_rows:
        return ElsevierTableRenderResult(rows=[])
    note = None
    if lossy:
        note = (
            "Merged table spans were semantically expanded into rectangular Markdown cells; "
            "rowspan/colspan layout fidelity was reduced."
        )
    return ElsevierTableRenderResult(rows=rendered_rows, lossy=lossy, note=note)


def resolve_elsevier_table_locator(table: ET.Element | None) -> str:
    if table is None:
        return ""
    for node in table.iter():
        if not isinstance(node.tag, str) or xml_local_name(node.tag) != "link":
            continue
        locator = normalize_text(node.get("locator"))
        if locator:
            return locator
    return ""


def resolve_elsevier_table_key(table: ET.Element | None) -> str:
    if table is None:
        return ""
    table_id = normalize_text(table.get("id"))
    if table_id:
        return table_id
    locator = resolve_elsevier_table_locator(table)
    if locator:
        return locator
    return ""


def extract_elsevier_table_footnotes(table: ET.Element) -> list[str]:
    footnotes: list[str] = []
    seen: set[str] = set()
    for node in list(table):
        if not isinstance(node.tag, str):
            continue
        if xml_local_name(node.tag) not in {"legend", "table-footnote"}:
            continue
        text = render_inline_text(node)
        normalized = normalize_text(text)
        if normalized and normalized not in seen:
            footnotes.append(normalized)
            seen.add(normalized)
    return footnotes


def table_reference_token(heading: str) -> str | None:
    normalized = normalize_text(heading)
    match = re.search(
        r"(?:tab(?:le)?\.?\s*)([a-z]?\d+)", normalized, flags=re.IGNORECASE
    )
    if match:
        return match.group(1).lower()
    return None


def paragraph_mentions_table(text: str, heading: str) -> bool:
    token = table_reference_token(heading)
    if not token:
        return False
    pattern = re.compile(
        rf"\btab(?:le)?\.?\s*{re.escape(token)}(?:[a-z](?!\w))?",
        flags=re.IGNORECASE,
    )
    return bool(pattern.search(text))


def should_render_elsevier_table_entry(
    entry: Mapping[str, Any] | None,
    *,
    inside_appendix: bool,
) -> bool:
    if not entry:
        return False
    return inside_appendix or entry.get("section") != "appendix"


def add_elsevier_table_once(
    lines: list[str],
    entry: Mapping[str, Any] | None,
    used_table_keys: set[str],
    *,
    inside_appendix: bool,
) -> None:
    if not should_render_elsevier_table_entry(entry, inside_appendix=inside_appendix):
        return
    add_table_once(lines, entry, used_table_keys)
