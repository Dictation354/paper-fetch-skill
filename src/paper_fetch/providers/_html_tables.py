"""Compatibility re-export for shared HTML table rendering helpers."""

from __future__ import annotations

from ..extraction.html.tables import (
    TABLE_PLACEHOLDER_PREFIX,
    CleanMarkdownFn,
    RenderInlineTextFn,
    escape_markdown_table_cell,
    expanded_table_matrix,
    flatten_table_header_rows,
    inject_inline_table_blocks,
    normalize_table_inline_text,
    render_aligned_markdown_table,
    render_table_inline_node,
    render_table_inline_text,
    render_table_markdown,
    table_cell_data,
    table_header_row_count,
    table_headers_and_data,
    table_placeholder,
    table_rows,
    wrap_table_text_fragment,
)

__all__ = [
    "TABLE_PLACEHOLDER_PREFIX",
    "CleanMarkdownFn",
    "RenderInlineTextFn",
    "escape_markdown_table_cell",
    "expanded_table_matrix",
    "flatten_table_header_rows",
    "inject_inline_table_blocks",
    "normalize_table_inline_text",
    "render_aligned_markdown_table",
    "render_table_inline_node",
    "render_table_inline_text",
    "render_table_markdown",
    "table_cell_data",
    "table_header_row_count",
    "table_headers_and_data",
    "table_placeholder",
    "table_rows",
    "wrap_table_text_fragment",
]
