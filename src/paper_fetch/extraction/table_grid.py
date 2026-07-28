"""Provider-neutral table grid normalization.

Publisher adapters should preserve source cell roles and spans in ``TableCell``
records, then project the result returned by :func:`normalize_table` into their
existing Markdown/table-entry contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Final
from collections.abc import Iterable, Sequence

from ..utils import normalize_text


MAX_TABLE_ROWS: Final = 1_000
MAX_TABLE_COLUMNS: Final = 256
MAX_TABLE_SLOTS: Final = 100_000


class TableConversionStatus(StrEnum):
    """Internal conversion outcome ordered from exact to unrecoverable."""

    EXACT = "exact"
    NORMALIZED = "normalized"
    LAYOUT_DEGRADED = "layout_degraded"
    FALLBACK = "fallback"
    SEMANTIC_LOSS = "semantic_loss"


class TableConversionReason(StrEnum):
    """Stable internal reason codes used by adapters and tests."""

    FULL_WIDTH_GROUP_NORMALIZED = "full_width_group_normalized"
    MULTIROW_HEADER_FLATTENED = "multirow_header_flattened"
    MERGED_SPAN_EXPANDED = "merged_span_expanded"
    INVALID_SPAN = "invalid_span"
    INVALID_DECLARED_WIDTH = "invalid_declared_width"
    INVALID_COLUMN_SPEC = "invalid_column_spec"
    UNKNOWN_COLUMN_NAME = "unknown_column_name"
    OVERLAPPING_SPAN = "overlapping_span"
    SPAN_OUT_OF_BOUNDS = "span_out_of_bounds"
    RAGGED_GRID = "ragged_grid"
    DIMENSION_LIMIT = "dimension_limit"


@dataclass(frozen=True)
class TableCell:
    """One source table cell before rectangular expansion."""

    text: str
    rowspan: int = 1
    colspan: int = 1
    is_header: bool = False
    is_header_candidate: bool = False
    column_start: int | None = None
    reasons: tuple[TableConversionReason, ...] = ()


@dataclass(frozen=True)
class TableRow:
    """One source row with an explicit semantic role where available."""

    cells: tuple[TableCell, ...]
    role: str = "body"


@dataclass(frozen=True)
class ExpandedTableGrid:
    """Rectangular cell grid, or failure reasons when expansion is unsafe."""

    matrix: tuple[tuple[TableCell, ...], ...] | None
    reasons: tuple[TableConversionReason, ...] = ()

    @property
    def is_rectangular(self) -> bool:
        return self.matrix is not None


@dataclass(frozen=True)
class NormalizedTable:
    """Canonical table projection consumed by Markdown adapters."""

    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    prefix_rows: tuple[str, ...] = ()
    status: TableConversionStatus = TableConversionStatus.EXACT
    reasons: tuple[TableConversionReason, ...] = ()
    is_rectangular: bool = True

    @property
    def layout_degraded(self) -> bool:
        return self.status in {
            TableConversionStatus.LAYOUT_DEGRADED,
            TableConversionStatus.FALLBACK,
            TableConversionStatus.SEMANTIC_LOSS,
        }


def _unique_reasons(
    *reason_groups: Iterable[TableConversionReason],
) -> tuple[TableConversionReason, ...]:
    ordered: list[TableConversionReason] = []
    seen: set[TableConversionReason] = set()
    for group in reason_groups:
        for reason in group:
            if reason in seen:
                continue
            ordered.append(reason)
            seen.add(reason)
    return tuple(ordered)


def _normalized_cell(
    cell: TableCell,
) -> tuple[TableCell, tuple[TableConversionReason, ...]]:
    reasons = list(cell.reasons)
    rowspan = cell.rowspan
    colspan = cell.colspan
    column_start = cell.column_start
    if rowspan < 1:
        rowspan = 1
        reasons.append(TableConversionReason.INVALID_SPAN)
    if colspan < 1:
        colspan = 1
        reasons.append(TableConversionReason.INVALID_SPAN)
    if column_start is not None and column_start < 0:
        column_start = None
        reasons.append(TableConversionReason.INVALID_COLUMN_SPEC)
    return (
        TableCell(
            text=cell.text,
            rowspan=rowspan,
            colspan=colspan,
            is_header=cell.is_header,
            is_header_candidate=cell.is_header_candidate,
            column_start=column_start,
            reasons=_unique_reasons(reasons),
        ),
        _unique_reasons(reasons),
    )


def _grid_failure(
    reasons: Iterable[TableConversionReason],
) -> ExpandedTableGrid:
    return ExpandedTableGrid(matrix=None, reasons=_unique_reasons(reasons))


def expand_table_grid(
    rows: Sequence[TableRow],
    *,
    declared_width: int | None = None,
    reasons: Iterable[TableConversionReason] = (),
) -> ExpandedTableGrid:
    """Expand merged cells into a validated rectangular occupancy grid."""

    collected_reasons = list(reasons)
    if not rows:
        return _grid_failure(collected_reasons)
    if len(rows) > MAX_TABLE_ROWS:
        collected_reasons.append(TableConversionReason.DIMENSION_LIMIT)
        return _grid_failure(collected_reasons)
    if declared_width is not None and (
        declared_width < 1 or declared_width > MAX_TABLE_COLUMNS
    ):
        collected_reasons.append(TableConversionReason.INVALID_DECLARED_WIDTH)
        if declared_width > MAX_TABLE_COLUMNS:
            collected_reasons.append(TableConversionReason.DIMENSION_LIMIT)
            return _grid_failure(collected_reasons)
        declared_width = None

    grid: dict[tuple[int, int], TableCell] = {}
    max_width = 0
    for row_index, row in enumerate(rows):
        cursor = 0
        for source_cell in row.cells:
            cell, cell_reasons = _normalized_cell(source_cell)
            collected_reasons.extend(cell_reasons)
            if cell.column_start is None:
                while (row_index, cursor) in grid:
                    cursor += 1
                start_column = cursor
            else:
                start_column = cell.column_start
            end_column = start_column + cell.colspan
            end_row = row_index + cell.rowspan
            if (
                end_column > MAX_TABLE_COLUMNS
                or len(grid) + (cell.rowspan * cell.colspan) > MAX_TABLE_SLOTS
            ):
                collected_reasons.append(TableConversionReason.DIMENSION_LIMIT)
                return _grid_failure(collected_reasons)
            if declared_width is not None and end_column > declared_width:
                collected_reasons.append(TableConversionReason.SPAN_OUT_OF_BOUNDS)
                return _grid_failure(collected_reasons)
            if end_row > len(rows):
                collected_reasons.append(TableConversionReason.SPAN_OUT_OF_BOUNDS)
                return _grid_failure(collected_reasons)
            occupied = [
                (target_row, target_column)
                for target_row in range(row_index, end_row)
                for target_column in range(start_column, end_column)
            ]
            if any(position in grid for position in occupied):
                collected_reasons.append(TableConversionReason.OVERLAPPING_SPAN)
                return _grid_failure(collected_reasons)
            expanded_cell = TableCell(
                text=cell.text,
                is_header=cell.is_header,
                is_header_candidate=cell.is_header_candidate,
            )
            for position in occupied:
                grid[position] = expanded_cell
            cursor = end_column
            max_width = max(max_width, end_column)

    width = declared_width or max_width
    if width < 1:
        return _grid_failure(collected_reasons)
    if width > MAX_TABLE_COLUMNS or width * len(rows) > MAX_TABLE_SLOTS:
        collected_reasons.append(TableConversionReason.DIMENSION_LIMIT)
        return _grid_failure(collected_reasons)

    matrix: list[tuple[TableCell, ...]] = []
    for row_index in range(len(rows)):
        expanded_row: list[TableCell] = []
        for column_index in range(width):
            grid_cell = grid.get((row_index, column_index))
            if grid_cell is None:
                collected_reasons.append(TableConversionReason.RAGGED_GRID)
                return _grid_failure(collected_reasons)
            expanded_row.append(grid_cell)
        matrix.append(tuple(expanded_row))
    return ExpandedTableGrid(
        matrix=tuple(matrix),
        reasons=_unique_reasons(collected_reasons),
    )


def flatten_header_rows(rows: Sequence[Sequence[TableCell]]) -> tuple[str, ...]:
    """Flatten a rectangular multi-row header into stable Markdown labels."""

    if not rows:
        return ()
    normalized_rows = list(rows)
    if len(normalized_rows) > 1:
        first_texts = [_header_text(cell.text) for cell in normalized_rows[0]]
        next_texts = [_header_text(cell.text) for cell in normalized_rows[1]]
        if (
            first_texts
            and all(first_texts)
            and len(set(first_texts)) == 1
            and any(next_texts)
        ):
            normalized_rows = normalized_rows[1:]
    width = len(normalized_rows[0])
    headers: list[str] = []
    for column_index in range(width):
        parts: list[str] = []
        for row in normalized_rows:
            if column_index >= len(row):
                return ()
            text = _header_text(row[column_index].text)
            if text and (not parts or parts[-1] != text):
                parts.append(text)
        headers.append(" / ".join(parts))
    return tuple(headers)


def _header_text(text: str) -> str:
    return normalize_text(re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE))


def _row_looks_like_header(row: TableRow) -> bool:
    if row.role == "header":
        return True
    if not row.cells:
        return False
    if all(cell.is_header for cell in row.cells):
        return True
    return any(cell.is_header or cell.is_header_candidate for cell in row.cells)


def _fallback_table(
    rows: Sequence[TableRow],
    *,
    reasons: Iterable[TableConversionReason],
    prefix_rows: Sequence[str] = (),
    header_indices: Sequence[int] = (),
) -> NormalizedTable:
    header_set = set(header_indices)
    headers: tuple[str, ...] = ()
    fallback_rows: list[tuple[str, ...]] = []
    for index, row in enumerate(rows):
        texts = tuple(normalize_text(cell.text) for cell in row.cells)
        if index in header_set and not headers:
            headers = texts
            continue
        if any(texts):
            fallback_rows.append(texts)
    return NormalizedTable(
        headers=headers,
        rows=tuple(fallback_rows),
        prefix_rows=tuple(prefix_rows),
        status=TableConversionStatus.FALLBACK,
        reasons=_unique_reasons(reasons),
        is_rectangular=False,
    )


def normalize_table(
    rows: Sequence[TableRow],
    *,
    declared_width: int | None = None,
    header_row_indices: Sequence[int] = (),
    reasons: Iterable[TableConversionReason] = (),
    lift_leading_full_width_groups: bool = True,
) -> NormalizedTable:
    """Normalize source rows into headers/body rows and conversion diagnostics."""

    if not rows:
        return NormalizedTable(headers=(), rows=())
    grid = expand_table_grid(
        rows,
        declared_width=declared_width,
        reasons=reasons,
    )
    if grid.matrix is None:
        return _fallback_table(
            rows,
            reasons=grid.reasons,
            header_indices=header_row_indices,
        )

    matrix = grid.matrix
    width = len(matrix[0])
    full_width_groups = {
        index
        for index, row in enumerate(rows)
        if len(row.cells) == 1
        and row.cells[0].rowspan == 1
        and row.cells[0].column_start in {None, 0}
        and row.cells[0].colspan >= width
        and normalize_text(row.cells[0].text)
    }

    prefix_indices: list[int] = []
    if lift_leading_full_width_groups:
        index = 0
        while index in full_width_groups and index + 1 < len(rows):
            next_index = index + 1
            while next_index in full_width_groups and next_index + 1 < len(rows):
                next_index += 1
            if not _row_looks_like_header(rows[next_index]):
                break
            prefix_indices.append(index)
            index += 1

    explicit_headers = [
        index
        for index in header_row_indices
        if 0 <= index < len(rows)
        and index not in full_width_groups
        and index not in prefix_indices
    ]
    resolved_header_indices: list[int]
    if explicit_headers:
        resolved_header_indices = explicit_headers
    else:
        resolved_header_indices = []
        for index, row in enumerate(rows):
            if index in prefix_indices or index in full_width_groups:
                continue
            if _row_looks_like_header(row):
                resolved_header_indices.append(index)
                continue
            break

    headers = (
        flatten_header_rows([matrix[index] for index in resolved_header_indices])
        if resolved_header_indices
        else tuple("" for _ in range(width))
    )
    if not headers:
        return _fallback_table(
            rows,
            reasons=(*grid.reasons, TableConversionReason.RAGGED_GRID),
            prefix_rows=[
                normalize_text(rows[index].cells[0].text) for index in prefix_indices
            ],
            header_indices=resolved_header_indices,
        )

    output_rows: list[tuple[str, ...]] = []
    skipped_indices = set(prefix_indices) | set(resolved_header_indices)
    for index, matrix_row in enumerate(matrix):
        if index in skipped_indices:
            continue
        if index in full_width_groups:
            group_text = normalize_text(rows[index].cells[0].text)
            output_rows.append((group_text, *("" for _ in range(width - 1))))
            continue
        output_rows.append(tuple(normalize_text(cell.text) for cell in matrix_row))

    result_reasons = list(grid.reasons)
    if prefix_indices or full_width_groups:
        result_reasons.append(TableConversionReason.FULL_WIDTH_GROUP_NORMALIZED)
    if len(resolved_header_indices) > 1:
        result_reasons.append(TableConversionReason.MULTIROW_HEADER_FLATTENED)
    has_non_group_span = any(
        (cell.rowspan > 1 or cell.colspan > 1)
        for index, row in enumerate(rows)
        if index not in full_width_groups
        for cell in row.cells
    )
    if has_non_group_span:
        result_reasons.append(TableConversionReason.MERGED_SPAN_EXPANDED)

    normalized_reasons = _unique_reasons(result_reasons)
    degraded_reasons = {
        TableConversionReason.MERGED_SPAN_EXPANDED,
        TableConversionReason.INVALID_SPAN,
        TableConversionReason.INVALID_DECLARED_WIDTH,
        TableConversionReason.INVALID_COLUMN_SPEC,
        TableConversionReason.UNKNOWN_COLUMN_NAME,
    }
    if any(reason in degraded_reasons for reason in normalized_reasons):
        status = TableConversionStatus.LAYOUT_DEGRADED
    elif normalized_reasons:
        status = TableConversionStatus.NORMALIZED
    else:
        status = TableConversionStatus.EXACT
    return NormalizedTable(
        headers=headers,
        rows=tuple(output_rows),
        prefix_rows=tuple(
            normalize_text(rows[index].cells[0].text) for index in prefix_indices
        ),
        status=status,
        reasons=normalized_reasons,
    )
