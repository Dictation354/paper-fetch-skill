"""Shared XML/text/path helpers for article Markdown rendering."""

from __future__ import annotations

import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from collections.abc import Mapping, Sequence

from ._article_markdown_xml import (
    child_text,
    first_child,
    first_descendant,
    normalize_compact_text,
    xml_local_name,
)
from ..extraction.table_grid import TableConversionStatus
from ..extraction.markdown_render.figures import add_figure_once, render_figure_block
from ..extraction.markdown_render.tables import (
    add_table_once,
    normalize_table_cell_text,
    render_image_table_block,
    render_structured_table_block,
    render_table_block,
)
from ..utils import format_paper_stem, normalize_text

XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
XLINK_TITLE = "{http://www.w3.org/1999/xlink}title"
INLINE_SPLIT_SUBSCRIPT_PATTERN = re.compile(
    r"\*(?P<base>[A-Za-zΑ-Ωα-ω]{1,8})\*\s*\n\s*(?:\*(?P<italic_sub>[A-Za-z0-9]+)\*|(?P<plain_sub>[A-Za-z0-9]{1,6}))"
)

__all__ = [
    "XLINK_HREF",
    "XLINK_TITLE",
    "add_figure_once",
    "add_table_once",
    "child_text",
    "collect_conversion_notes",
    "fallback_table_heading",
    "first_child",
    "first_descendant",
    "iter_children",
    "iter_descendants",
    "make_markdown_path",
    "normalize_compact_text",
    "normalize_inline_markup_text",
    "normalize_lines",
    "normalize_table_cell_text",
    "normalize_text",
    "path_relative_to",
    "render_figure_block",
    "render_image_table_block",
    "render_inline_text",
    "render_structured_table_block",
    "render_table_block",
    "table_conversion_note",
    "table_entry_semantic_count",
    "xml_local_name",
]


def iter_children(
    element: ET.Element | None, local_name: str | None = None
) -> list[ET.Element]:
    if element is None:
        return []
    return [
        child
        for child in list(element)
        if isinstance(child.tag, str)
        and (local_name is None or xml_local_name(child.tag) == local_name)
    ]


def iter_descendants(element: ET.Element | None, local_name: str) -> list[ET.Element]:
    if element is None:
        return []
    return [
        node
        for node in element.iter()
        if isinstance(node.tag, str) and xml_local_name(node.tag) == local_name
    ]


def normalize_inline_markup_text(value: str | None) -> str:
    text = normalize_text(value)
    if not text:
        return ""

    text = INLINE_SPLIT_SUBSCRIPT_PATTERN.sub(
        lambda match: (
            f"*{match.group('base')}*<sub>{match.group('italic_sub') or match.group('plain_sub')}</sub>"
        ),
        text,
    )
    text = re.sub(r"\s*(<(?:sub|sup)>)\s*", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+</(sub|sup)>", r"</\1>", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+(<(?:sub|sup)>)", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"(</(?:sub|sup)>)\s*\n\s*", r"\1 ", text, flags=re.IGNORECASE)
    text = re.sub(r"(</(?:sub|sup)>)(?=[A-Za-z0-9])", r"\1 ", text, flags=re.IGNORECASE)
    text = re.sub(
        r"(</(?:sub|sup)>)\s+([,.;:%\]\}\+\)])", r"\1\2", text, flags=re.IGNORECASE
    )
    text = re.sub(r"\s*\n\s*([,.;:%\]\}\)])", r"\1", text)
    text = re.sub(r"([(\[{])\s*\n\s*", r"\1", text)
    text = re.sub(r"(?<=[A-Za-z0-9>])\s*\n\s*(?=[A-Za-z0-9*_<])", " ", text)
    return text.strip()


def render_inline_text(
    element: ET.Element | None,
    *,
    skip_local_names: set[str] | None = None,
    formula_renders: list[Any] | None = None,
    source_url: str = "",
) -> str:
    if element is None:
        return ""

    from ._article_markdown_math import (
        formula_inline_markdown,
        render_inline_formula_result,
        render_mathml_formula_result,
        render_tex_formula_result,
    )

    skip_names = skip_local_names or set()
    parts: list[str] = []

    def visit(node: ET.Element) -> None:
        if node.text:
            parts.append(node.text)

        for child in list(node):
            if not isinstance(child.tag, str):
                if child.tail:
                    parts.append(child.tail)
                continue

            local_name = xml_local_name(child.tag)
            if local_name in skip_names:
                if child.tail:
                    parts.append(child.tail)
                continue
            if local_name == "math":
                formula_result = render_mathml_formula_result(
                    child,
                    display_mode=False,
                )
                if formula_renders is not None:
                    formula_renders.append(formula_result)
                rendered_formula = formula_inline_markdown(formula_result)
                if rendered_formula:
                    parts.append(rendered_formula)
            elif local_name == "inline-formula":
                formula_result = render_inline_formula_result(
                    child,
                    source_url=source_url,
                )
                if formula_renders is not None:
                    formula_renders.append(formula_result)
                rendered_formula = formula_inline_markdown(formula_result)
                if rendered_formula:
                    parts.append(rendered_formula)
            elif local_name == "tex-math":
                formula_result = render_tex_formula_result(child)
                if formula_renders is not None:
                    formula_renders.append(formula_result)
                rendered_formula = formula_inline_markdown(formula_result)
                if rendered_formula:
                    parts.append(rendered_formula)
            if local_name == "sup":
                parts.append(
                    "<sup>"
                    f"{render_inline_text(child, skip_local_names=skip_names, formula_renders=formula_renders, source_url=source_url)}"
                    "</sup>"
                )
            elif local_name == "sub":
                parts.append(
                    "<sub>"
                    f"{render_inline_text(child, skip_local_names=skip_names, formula_renders=formula_renders, source_url=source_url)}"
                    "</sub>"
                )
            elif local_name in {"bold"}:
                parts.append(
                    "**"
                    f"{render_inline_text(child, skip_local_names=skip_names, formula_renders=formula_renders, source_url=source_url)}"
                    "**"
                )
            elif local_name in {"italic"}:
                parts.append(
                    "*"
                    f"{render_inline_text(child, skip_local_names=skip_names, formula_renders=formula_renders, source_url=source_url)}"
                    "*"
                )
            elif local_name in {"break", "br"}:
                parts.append("\n")
            elif local_name in {"math", "inline-formula", "tex-math"}:
                pass
            else:
                visit(child)

            if child.tail:
                parts.append(child.tail)

    visit(element)
    return normalize_inline_markup_text("".join(parts))


def path_relative_to(base_dir: Path, target_path: str | Path) -> str:
    relative = Path(os.path.relpath(Path(target_path), start=base_dir))
    return urllib.parse.quote(relative.as_posix(), safe="/._-")


def make_markdown_path(
    output_dir: Path,
    doi: str,
    title: str | None,
    *,
    authors: list[str] | None = None,
    year: str | None = None,
) -> Path:
    return output_dir / f"{format_paper_stem(authors, year, title, doi=doi)}.md"


def fallback_table_heading(raw_value: str | None) -> str:
    normalized = normalize_text(raw_value)
    if not normalized:
        return "Table"
    match = re.fullmatch(r"tab(?:le)?[_\s-]*([0-9]+)", normalized, flags=re.IGNORECASE)
    if match:
        return f"Table {match.group(1)}"
    return normalized


def table_conversion_note(status: TableConversionStatus) -> str | None:
    """Return a user-facing note only when table conversion really degraded."""

    if status == TableConversionStatus.LAYOUT_DEGRADED:
        return (
            "Source table span or column metadata was invalid or inconsistent and "
            "was repaired during Markdown conversion; cell text was retained, but "
            "the source layout could not be verified exactly."
        )
    if status == TableConversionStatus.FALLBACK:
        return (
            "Irregular table structure could not be represented as a reliable "
            "Markdown grid; cell text was retained as a readable list."
        )
    if status == TableConversionStatus.SEMANTIC_LOSS:
        return "Some table content could not be preserved during Markdown conversion."
    return None


def table_entry_semantic_count(
    entry: Mapping[str, Any],
    field: str,
    *,
    fallback: bool = False,
) -> int:
    """Read a non-negative internal table quality count with legacy fallback."""

    value = entry.get(field)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return max(value, 0)
    return int(fallback)


def normalize_lines(lines: list[str]) -> str:
    cleaned: list[str] = []
    previous_blank = False
    for line in lines:
        text = line.rstrip()
        if not text:
            if previous_blank:
                continue
            cleaned.append("")
            previous_blank = True
            continue
        cleaned.append(text)
        previous_blank = False
    return "\n".join(cleaned).strip() + "\n"


def collect_conversion_notes(
    *,
    table_entries: Sequence[Mapping[str, Any]] | None = None,
    formula_notes: list[str] | None = None,
) -> list[str]:
    notes: list[str] = []
    seen: set[tuple[str, str]] = set()

    for entry in table_entries or []:
        heading = normalize_text(str(entry.get("heading") or ""))
        messages = []
        for message in [
            *(entry.get("conversion_notes") or []),
            entry.get("lossy_message"),
            entry.get("fallback_message"),
        ]:
            if message is None:
                continue
            normalized_message = normalize_text(str(message))
            if normalized_message:
                messages.append(normalized_message)
        for message in messages:
            key = (heading, message)
            if key in seen:
                continue
            seen.add(key)
            if heading:
                notes.append(f"- {heading}: {message}")
            else:
                notes.append(f"- {message}")

    for note in formula_notes or []:
        normalized = normalize_text(note)
        if not normalized:
            continue
        key = ("", normalized)
        if key in seen:
            continue
        seen.add(key)
        notes.append(f"- {normalized}")

    return notes
