"""Shared XML/text/path helpers for article Markdown rendering."""

from __future__ import annotations

import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping

from ..utils import normalize_text, sanitize_filename

XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
XLINK_TITLE = "{http://www.w3.org/1999/xlink}title"
INLINE_SPLIT_SUBSCRIPT_PATTERN = re.compile(
    r"\*(?P<base>[A-Za-zΑ-Ωα-ω])\*\s*\n\s*(?:\*(?P<italic_sub>[A-Za-z0-9]+)\*|(?P<plain_sub>[A-Za-z0-9]{1,6}))"
)


def xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def normalize_compact_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_inline_markup_text(value: str | None) -> str:
    text = normalize_text(value)
    if not text:
        return ""

    text = INLINE_SPLIT_SUBSCRIPT_PATTERN.sub(
        lambda match: f"*{match.group('base')}*<sub>{match.group('italic_sub') or match.group('plain_sub')}</sub>",
        text,
    )
    text = re.sub(r"\s*(<(?:sub|sup)>)\s*", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+</(sub|sup)>", r"</\1>", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+(<(?:sub|sup)>)", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"(</(?:sub|sup)>)\s*\n\s*", r"\1 ", text, flags=re.IGNORECASE)
    text = re.sub(r"(</(?:sub|sup)>)(?=[A-Za-z0-9])", r"\1 ", text, flags=re.IGNORECASE)
    text = re.sub(r"(</(?:sub|sup)>)\s+([,.;:%\]\}\+\)])", r"\1\2", text, flags=re.IGNORECASE)
    return text.strip()


def render_inline_text(element: ET.Element | None, *, skip_local_names: set[str] | None = None) -> str:
    if element is None:
        return ""

    from ._article_markdown_math import (
        render_external_mathml_expression,
        render_inline_formula,
        render_tex_math,
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
                expression = render_external_mathml_expression(child, display_mode=False)
                if expression:
                    parts.append(f"${expression}$")
            elif local_name == "inline-formula":
                expression = render_inline_formula(child)
                if expression:
                    parts.append(f"${expression}$")
            elif local_name == "tex-math":
                expression = render_tex_math(child)
                if expression:
                    parts.append(f"${expression}$")
            if local_name == "sup":
                parts.append(f"<sup>{render_inline_text(child, skip_local_names=skip_names)}</sup>")
            elif local_name == "sub":
                parts.append(f"<sub>{render_inline_text(child, skip_local_names=skip_names)}</sub>")
            elif local_name in {"bold"}:
                parts.append(f"**{render_inline_text(child, skip_local_names=skip_names)}**")
            elif local_name in {"italic"}:
                parts.append(f"*{render_inline_text(child, skip_local_names=skip_names)}*")
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


def first_child(element: ET.Element | None, local_name: str) -> ET.Element | None:
    if element is None:
        return None
    for child in list(element):
        if isinstance(child.tag, str) and xml_local_name(child.tag) == local_name:
            return child
    return None


def child_text(element: ET.Element | None, local_name: str) -> str:
    return render_inline_text(first_child(element, local_name))


def first_descendant(element: ET.Element, local_name: str) -> ET.Element | None:
    for node in element.iter():
        if isinstance(node.tag, str) and xml_local_name(node.tag) == local_name:
            return node
    return None


def path_relative_to(base_dir: Path, target_path: str | Path) -> str:
    relative = Path(os.path.relpath(Path(target_path), start=base_dir))
    return urllib.parse.quote(relative.as_posix(), safe="/._-")


def make_markdown_path(output_dir: Path, doi: str, title: str | None) -> Path:
    return output_dir / f"{sanitize_filename(doi or title or 'article')}.md"


def fallback_figure_heading(raw_value: str | None) -> str:
    normalized = normalize_text(raw_value)
    if not normalized:
        return "Figure"
    match = re.fullmatch(r"fig(?:ure)?[_\s-]*([0-9]+)", normalized, flags=re.IGNORECASE)
    if match:
        return f"Figure {match.group(1)}"
    return normalized


def fallback_table_heading(raw_value: str | None) -> str:
    normalized = normalize_text(raw_value)
    if not normalized:
        return "Table"
    match = re.fullmatch(r"tab(?:le)?[_\s-]*([0-9]+)", normalized, flags=re.IGNORECASE)
    if match:
        return f"Table {match.group(1)}"
    return normalized


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


def normalize_table_cell_text(value: str) -> str:
    text = normalize_text(value)
    text = text.replace("\n", "<br>")
    return text.replace("|", r"\|")


def render_figure_block(entry: Mapping[str, str]) -> list[str]:
    lines = [f"![{entry['heading']}]({entry['link']})", ""]
    if entry.get("caption"):
        lines.extend([entry["caption"], ""])
    return lines


def add_figure_once(lines: list[str], entry: Mapping[str, str] | None, used_figure_keys: set[str]) -> None:
    if not entry:
        return
    key = entry["key"]
    if key in used_figure_keys:
        return
    used_figure_keys.add(key)
    lines.extend(render_figure_block(entry))


def render_image_table_block(entry: Mapping[str, Any]) -> list[str]:
    lines = [entry["heading"], ""]
    if entry.get("caption"):
        lines.extend([str(entry["caption"]), ""])
    if entry.get("link"):
        lines.extend([f"![{entry['heading']}]({entry['link']})", ""])
    for footnote in entry.get("footnotes", []):
        text = normalize_text(str(footnote))
        if text:
            lines.extend([text, ""])
    return lines


def render_structured_table_block(entry: Mapping[str, Any]) -> list[str]:
    lines = [entry["heading"], ""]
    if entry.get("caption"):
        lines.extend([str(entry["caption"]), ""])
    rows = entry.get("rows") or []
    if not rows:
        return render_image_table_block(
            {
                **entry,
                "fallback_message": "Table content could not be fully converted to Markdown; original table resource is retained below.",
            }
        )
    lines.append("| " + " | ".join(rows[0]) + " |")
    lines.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    for footnote in entry.get("footnotes", []):
        text = normalize_text(str(footnote))
        if text:
            lines.extend([text, ""])
    return lines


def render_table_block(entry: Mapping[str, Any]) -> list[str]:
    if not entry:
        return []
    if entry.get("kind") == "structured":
        return render_structured_table_block(entry)
    return render_image_table_block(entry)


def collect_conversion_notes(*, table_entries: list[Mapping[str, Any]] | None = None) -> list[str]:
    notes: list[str] = []
    seen: set[tuple[str, str]] = set()

    for entry in table_entries or []:
        message = normalize_text(str(entry.get("fallback_message") or ""))
        if not message:
            continue
        heading = normalize_text(str(entry.get("heading") or ""))
        key = (heading, message)
        if key in seen:
            continue
        seen.add(key)
        if heading:
            notes.append(f"- {heading}: {message}")
        else:
            notes.append(f"- {message}")

    return notes


def add_table_once(lines: list[str], entry: Mapping[str, Any] | None, used_table_keys: set[str]) -> None:
    if not entry:
        return
    key = str(entry["key"])
    if key in used_table_keys:
        return
    used_table_keys.add(key)
    lines.extend(render_table_block(entry))
