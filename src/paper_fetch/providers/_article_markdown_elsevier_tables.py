"""Elsevier XML table conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET
from typing import Any
from collections.abc import Mapping

from ..extraction.table_grid import (
    TableConversionReason,
    TableConversionStatus,
    normalize_table,
)
from ..extraction.xml_tables import parse_xml_table
from ._article_markdown_common import (
    add_table_once,
    normalize_table_cell_text,
    normalize_text,
    render_inline_text,
    xml_local_name,
)


@dataclass
class ElsevierTableRenderResult:
    headers: list[str]
    rows: list[list[str]]
    prefix_rows: list[str]
    status: TableConversionStatus = TableConversionStatus.EXACT
    reasons: tuple[TableConversionReason, ...] = ()
    note: str | None = None

    @property
    def lossy(self) -> bool:
        return self.status in {
            TableConversionStatus.LAYOUT_DEGRADED,
            TableConversionStatus.FALLBACK,
            TableConversionStatus.SEMANTIC_LOSS,
        }

    @property
    def render_kind(self) -> str:
        if self.status in {
            TableConversionStatus.FALLBACK,
            TableConversionStatus.SEMANTIC_LOSS,
        }:
            return "structured_list"
        return "structured"


def render_elsevier_table_result(table: ET.Element | None) -> ElsevierTableRenderResult:
    if table is None:
        return ElsevierTableRenderResult(headers=[], rows=[], prefix_rows=[])

    parsed = parse_xml_table(
        table,
        render_cell_text=lambda cell: normalize_table_cell_text(
            render_inline_text(cell)
        ),
    )
    normalized = normalize_table(
        parsed.rows,
        declared_width=parsed.declared_width,
        header_row_indices=tuple(
            index for index, row in enumerate(parsed.rows) if row.role == "header"
        ),
        reasons=parsed.reasons,
    )
    note: str | None = None
    if normalized.status == TableConversionStatus.LAYOUT_DEGRADED:
        note = (
            "Merged table spans were semantically expanded into rectangular Markdown cells; "
            "rowspan/colspan layout fidelity was reduced."
        )
    elif normalized.status == TableConversionStatus.FALLBACK:
        note = (
            "Irregular table structure could not be represented as a reliable Markdown grid; "
            "cell text was retained as a readable list."
        )
    return ElsevierTableRenderResult(
        headers=list(normalized.headers),
        rows=[list(row) for row in normalized.rows],
        prefix_rows=list(normalized.prefix_rows),
        status=normalized.status,
        reasons=normalized.reasons,
        note=note,
    )


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
