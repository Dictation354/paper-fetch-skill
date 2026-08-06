"""Shared XML/JATS/CALS adapters for the provider-neutral table grid."""

from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator

from .table_grid import (
    TableCell,
    TableConversionReason,
    TableRow,
)
from ..utils import normalize_text


RenderXmlCellText = Callable[[ET.Element], str]


@dataclass(frozen=True)
class ParsedXmlTable:
    rows: tuple[TableRow, ...]
    declared_width: int | None = None
    reasons: tuple[TableConversionReason, ...] = ()


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    if ":" in tag:
        return tag.rsplit(":", 1)[-1]
    return tag


def _unique_reasons(
    reasons: list[TableConversionReason],
) -> tuple[TableConversionReason, ...]:
    return tuple(dict.fromkeys(reasons))


def _first_descendant(root: ET.Element, name: str) -> ET.Element | None:
    for node in root.iter():
        if isinstance(node.tag, str) and _local_name(node.tag) == name:
            return node
    return None


def _column_specification(
    table_root: ET.Element,
) -> tuple[int | None, dict[str, int], tuple[TableConversionReason, ...]]:
    tgroup = _first_descendant(table_root, "tgroup")
    if tgroup is None:
        return None, {}, ()
    reasons: list[TableConversionReason] = []
    declared_width: int | None = None
    raw_width = normalize_text(tgroup.get("cols"))
    if raw_width:
        try:
            parsed_width = int(raw_width)
        except ValueError:
            parsed_width = 0
        if parsed_width > 0:
            declared_width = parsed_width
        else:
            reasons.append(TableConversionReason.INVALID_DECLARED_WIDTH)

    columns: dict[str, int] = {}
    next_column = 0
    for node in list(tgroup):
        if not isinstance(node.tag, str) or _local_name(node.tag) != "colspec":
            continue
        raw_colnum = normalize_text(node.get("colnum"))
        column = next_column
        if raw_colnum:
            try:
                parsed_colnum = int(raw_colnum)
            except ValueError:
                parsed_colnum = 0
            if parsed_colnum > 0:
                column = parsed_colnum - 1
            else:
                reasons.append(TableConversionReason.INVALID_COLUMN_SPEC)
        name = normalize_text(node.get("colname"))
        if name:
            if name in columns:
                reasons.append(TableConversionReason.INVALID_COLUMN_SPEC)
            else:
                columns[name] = column
        next_column = max(next_column + 1, column + 1)
    if columns:
        inferred_width = max(columns.values()) + 1
        declared_width = max(declared_width or 0, inferred_width)
    return declared_width, columns, _unique_reasons(reasons)


def _row_nodes(root: ET.Element) -> Iterator[tuple[ET.Element, bool]]:
    def walk(
        node: ET.Element, *, in_header: bool, is_root: bool
    ) -> Iterator[tuple[ET.Element, bool]]:
        if not isinstance(node.tag, str):
            return
        name = _local_name(node.tag)
        if not is_root and name == "table":
            return
        next_in_header = in_header or name == "thead"
        if name in {"row", "tr"}:
            yield node, next_in_header
            return
        for child in list(node):
            yield from walk(child, in_header=next_in_header, is_root=False)

    yield from walk(root, in_header=False, is_root=True)


def _tgroup_nodes(root: ET.Element) -> Iterator[ET.Element]:
    """Yield top-level CALS groups owned by ``root`` in source order."""

    def walk(node: ET.Element, *, is_root: bool) -> Iterator[ET.Element]:
        if not isinstance(node.tag, str):
            return
        name = _local_name(node.tag)
        if not is_root and name == "table":
            return
        if name == "tgroup":
            yield node
            return
        for child in list(node):
            yield from walk(child, is_root=False)

    yield from walk(root, is_root=True)


def _positive_attribute(
    node: ET.Element,
    attribute: str,
    *,
    default: int = 1,
    increment: int = 0,
) -> tuple[int, tuple[TableConversionReason, ...]]:
    raw = node.get(attribute)
    if raw is None:
        return default, ()
    try:
        value = int(normalize_text(raw)) + increment
    except ValueError:
        return default, (TableConversionReason.INVALID_SPAN,)
    if value < 1:
        return default, (TableConversionReason.INVALID_SPAN,)
    return value, ()


def _parse_xml_table_root(
    table_root: ET.Element,
    *,
    render_cell_text: RenderXmlCellText,
) -> ParsedXmlTable:
    declared_width, columns, table_reasons = _column_specification(table_root)
    collected_reasons = list(table_reasons)
    rows: list[TableRow] = []
    for row_node, explicit_header in _row_nodes(table_root):
        cells: list[TableCell] = []
        for cell_node in list(row_node):
            if not isinstance(cell_node.tag, str):
                continue
            name = _local_name(cell_node.tag)
            if name not in {"entry", "td", "th"}:
                continue
            cell_reasons: list[TableConversionReason] = []
            rowspan, rowspan_reasons = _positive_attribute(cell_node, "rowspan")
            if (
                cell_node.get("rowspan") is None
                and cell_node.get("morerows") is not None
            ):
                rowspan, rowspan_reasons = _positive_attribute(
                    cell_node,
                    "morerows",
                    increment=1,
                )
            colspan, colspan_reasons = _positive_attribute(cell_node, "colspan")
            cell_reasons.extend(rowspan_reasons)
            cell_reasons.extend(colspan_reasons)

            start_column: int | None = None
            start_name = normalize_text(
                cell_node.get("namest") or cell_node.get("colname")
            )
            end_name = normalize_text(cell_node.get("nameend"))
            if start_name:
                start_column = columns.get(start_name)
                if start_column is None:
                    cell_reasons.append(TableConversionReason.UNKNOWN_COLUMN_NAME)
            if end_name:
                end_column = columns.get(end_name)
                if (
                    start_column is None
                    or end_column is None
                    or end_column < start_column
                ):
                    cell_reasons.append(TableConversionReason.UNKNOWN_COLUMN_NAME)
                else:
                    colspan = end_column - start_column + 1

            is_header = explicit_header or name == "th"
            unique_cell_reasons = _unique_reasons(cell_reasons)
            collected_reasons.extend(unique_cell_reasons)
            cells.append(
                TableCell(
                    text=render_cell_text(cell_node),
                    rowspan=rowspan,
                    colspan=colspan,
                    is_header=is_header,
                    is_header_candidate=is_header,
                    column_start=start_column,
                    reasons=unique_cell_reasons,
                )
            )
        if cells:
            rows.append(
                TableRow(
                    cells=tuple(cells),
                    role="header" if explicit_header else "body",
                )
            )
    return ParsedXmlTable(
        rows=tuple(rows),
        declared_width=declared_width,
        reasons=_unique_reasons(collected_reasons),
    )


def parse_xml_table_groups(
    table_root: ET.Element,
    *,
    render_cell_text: RenderXmlCellText,
) -> tuple[ParsedXmlTable, ...]:
    """Parse each CALS ``tgroup`` with its own column specification.

    HTML-like and JATS tables without a ``tgroup`` remain one logical group.
    Nested tables are excluded from their containing table's group discovery.
    """

    tgroups = tuple(_tgroup_nodes(table_root))
    if not tgroups:
        return (
            _parse_xml_table_root(
                table_root,
                render_cell_text=render_cell_text,
            ),
        )
    return tuple(
        _parse_xml_table_root(tgroup, render_cell_text=render_cell_text)
        for tgroup in tgroups
    )


def parse_xml_table(
    table_root: ET.Element,
    *,
    render_cell_text: RenderXmlCellText,
) -> ParsedXmlTable:
    """Parse XML rows using the legacy single-table compatibility contract."""

    return _parse_xml_table_root(
        table_root,
        render_cell_text=render_cell_text,
    )
