"""Shared XML/text/path helpers for article Markdown rendering."""

from __future__ import annotations

import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping

from ..publisher_identity import normalize_doi
from ..utils import sanitize_filename

XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
XLINK_TITLE = "{http://www.w3.org/1999/xlink}title"


def xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def normalize_text(value: str | None) -> str:
    text = (value or "").replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_compact_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


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
    return normalize_text("".join(parts))


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


def build_springer_static_asset_url(doi: str, source_href: str, *, asset_bucket: str) -> str:
    href = normalize_text(source_href)
    if not href:
        return ""
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith("//"):
        return f"https:{href}"

    article_segment = urllib.parse.quote(f"art:{normalize_doi(doi)}", safe="")
    resource_segment = urllib.parse.quote(href.lstrip("/"), safe="/")
    return f"https://static-content.springer.com/{asset_bucket}/{article_segment}/{resource_segment}"


def resolve_springer_asset_link(
    markdown_path: Path,
    asset: Mapping[str, Any] | None,
    source_href: str,
    doi: str,
    *,
    asset_bucket: str,
) -> str:
    if asset and asset.get("path"):
        return path_relative_to(markdown_path.parent, str(asset["path"]))
    if doi:
        return build_springer_static_asset_url(doi, source_href, asset_bucket=asset_bucket)
    return normalize_text(source_href)


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
