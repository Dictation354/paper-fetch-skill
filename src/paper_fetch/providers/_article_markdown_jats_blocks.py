"""JATS block conversion helpers for article Markdown rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import urllib.parse
import xml.etree.ElementTree as ET

from ..extraction.table_grid import (
    TableConversionReason,
    TableConversionStatus,
    normalize_table,
)
from ..extraction.xml_tables import parse_xml_table
from ..extraction.markdown_render import MarkdownList, render_list
from ._article_markdown_common import (
    XLINK_HREF,
    XLINK_TITLE,
    child_text,
    first_child,
    first_descendant,
    iter_children,
    iter_descendants,
    normalize_table_cell_text,
    render_inline_text,
    xml_local_name,
)
from ..utils import normalize_text

JATS_BLOCK_LOCAL_NAMES = {
    "disp-formula",
    "fig",
    "list",
    "supplementary-material",
    "table",
    "table-wrap",
}


@dataclass(frozen=True)
class _JatsTableRenderResult:
    headers: list[str]
    rows: list[list[str]]
    prefix_rows: list[str]
    status: TableConversionStatus = TableConversionStatus.EXACT
    reasons: tuple[TableConversionReason, ...] = ()
    layout_degraded: bool = False

    @property
    def render_kind(self) -> str:
        if self.status in {
            TableConversionStatus.FALLBACK,
            TableConversionStatus.SEMANTIC_LOSS,
        }:
            return "structured_list"
        return "structured"


def _attribute_text(element: ET.Element | None, *names: str) -> str:
    if element is None:
        return ""
    for name in names:
        value = normalize_text(str(element.get(name) or ""))
        if value:
            return value
    return ""


def _element_id(element: ET.Element | None) -> str:
    return _attribute_text(element, "id", "{http://www.w3.org/XML/1998/namespace}id")


def _href(element: ET.Element | None) -> str:
    return _attribute_text(element, XLINK_HREF, "href")


def _urljoin(base_url: str, value: str | None) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    return urllib.parse.urljoin(base_url, normalized)


def _render_paragraph_texts(parent: ET.Element | None) -> list[str]:
    texts: list[str] = []
    for child in iter_children(parent):
        local_name = xml_local_name(child.tag)
        if local_name == "title":
            continue
        if local_name == "p":
            text = render_inline_text(child, skip_local_names=JATS_BLOCK_LOCAL_NAMES)
            if text:
                texts.append(text)
            continue
        if local_name in {"sec", "notes", "ack", "app"}:
            nested = _render_paragraph_texts(child)
            texts.extend(nested)
    return texts


def _heading_text(section: ET.Element) -> str:
    title = normalize_text(child_text(section, "title"))
    label = normalize_text(child_text(section, "label"))
    if title and label:
        return normalize_text(f"{label} {title}")
    return title or label


def _caption_text(container: ET.Element | None) -> str:
    caption = first_child(container, "caption")
    if caption is None:
        return ""
    paragraphs = _render_paragraph_texts(caption)
    if paragraphs:
        return normalize_text("\n\n".join(paragraphs))
    return normalize_text(render_inline_text(caption))


def _graphic_url(figure: ET.Element, source_url: str) -> str:
    for node in iter_descendants(figure, "graphic"):
        url = _urljoin(source_url, _href(node))
        if url:
            return url
    return ""


def _figure_entry(figure: ET.Element, source_url: str) -> dict[str, Any] | None:
    url = _graphic_url(figure, source_url)
    label = normalize_text(child_text(figure, "label")) or "Figure"
    figure_id = _element_id(figure)
    caption = _caption_text(figure)
    key = figure_id or url or label
    if not key:
        return None
    entry: dict[str, Any] = {
        "kind": "figure",
        "key": key,
        "anchor_key": key,
        "heading": label,
        "caption": caption,
        "section": "body",
        "render_state": "inline",
    }
    if url:
        entry.update({"link": url, "original_url": url})
    return entry


def _table_node(table_wrap: ET.Element) -> ET.Element | None:
    if xml_local_name(table_wrap.tag) == "table":
        return table_wrap
    return first_descendant(table_wrap, "table")


def _render_structured_table(table: ET.Element) -> _JatsTableRenderResult:
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
    return _JatsTableRenderResult(
        headers=list(normalized.headers),
        rows=[list(row) for row in normalized.rows],
        prefix_rows=list(normalized.prefix_rows),
        status=normalized.status,
        reasons=normalized.reasons,
        layout_degraded=normalized.layout_degraded,
    )


def _table_footnotes(table_wrap: ET.Element) -> list[str]:
    notes: list[str] = []
    seen: set[str] = set()
    for local_name in ("table-wrap-foot", "fn"):
        for node in iter_descendants(table_wrap, local_name):
            text = normalize_text(
                "\n\n".join(_render_paragraph_texts(node)) or render_inline_text(node)
            )
            if text and text not in seen:
                notes.append(text)
                seen.add(text)
    return notes


def _table_entry(table_wrap: ET.Element) -> tuple[dict[str, Any] | None, bool]:
    label = normalize_text(child_text(table_wrap, "label")) or "Table"
    caption = _caption_text(table_wrap)
    table = _table_node(table_wrap)
    key = _element_id(table_wrap) or _element_id(table) or label
    if table is not None:
        render_result = _render_structured_table(table)
        headers = render_result.headers
        rows = render_result.rows
        lossy = render_result.layout_degraded
    else:
        render_result = None
        headers = []
        rows = []
        lossy = False
    if rows:
        entry: dict[str, Any] = {
            "kind": "table",
            "table_render_kind": (
                render_result.render_kind if render_result is not None else "structured"
            ),
            "key": key,
            "anchor_key": key,
            "heading": label,
            "caption": caption,
            "headers": headers,
            "rows": rows,
            "footnotes": _table_footnotes(table_wrap),
            "section": "body",
            "render_state": "inline",
        }
        if render_result is not None and render_result.prefix_rows:
            entry["_table_prefix_rows"] = render_result.prefix_rows
        if lossy:
            if (
                render_result is not None
                and render_result.status == TableConversionStatus.FALLBACK
            ):
                message = (
                    "Irregular table structure could not be represented as a reliable Markdown grid; "
                    "cell text was retained as a readable list."
                )
            else:
                message = (
                    "Merged table spans were semantically expanded into rectangular Markdown cells; "
                    "rowspan/colspan layout fidelity was reduced."
                )
            entry["lossy_message"] = message
            entry["conversion_notes"] = [message]
        return entry, lossy
    if caption:
        return {
            "kind": "table",
            "table_render_kind": "fallback",
            "key": key,
            "anchor_key": key,
            "heading": label,
            "caption": caption,
            "footnotes": _table_footnotes(table_wrap),
            "section": "body",
            "render_state": "inline",
            "fallback_message": "Table content could not be converted to Markdown; caption text was retained.",
            "conversion_notes": [
                "Table content could not be converted to Markdown; caption text was retained."
            ],
        }, True
    return None, False


def _supplementary_entries(root: ET.Element, source_url: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        if xml_local_name(node.tag) not in {
            "inline-supplementary-material",
            "supplementary-material",
        }:
            continue
        url = _urljoin(source_url, _href(node))
        if not url:
            continue
        text = normalize_text(render_inline_text(node))
        title = (
            normalize_text(str(node.get(XLINK_TITLE) or node.get("content-type") or ""))
            or text
            or "Supplementary material"
        )
        key = url or _element_id(node) or title
        if not key or key in seen:
            continue
        seen.add(key)
        entry: dict[str, Any] = {
            "kind": "supplementary",
            "key": key,
            "anchor_key": key,
            "heading": title,
            "caption": text if text and text != title else "",
            "section": "supplementary",
        }
        if url:
            entry.update({"link": url, "original_url": url})
        entries.append(entry)
    return entries


def _render_list(node: ET.Element, *, ordered: bool) -> list[str]:
    items = [
        normalize_text(
            " ".join(_render_paragraph_texts(item)) or render_inline_text(item)
        )
        for item in iter_children(node, "list-item")
    ]
    return render_list(MarkdownList(items=items, ordered=ordered))


def _render_supplementary_materials(node: ET.Element, source_url: str) -> list[str]:
    bullets: list[str] = []
    for entry in _supplementary_entries(node, source_url):
        link = normalize_text(str(entry.get("link") or entry.get("url") or ""))
        heading = normalize_text(str(entry.get("heading") or "Supplementary material"))
        caption = normalize_text(str(entry.get("caption") or ""))
        if link:
            bullet = f"- [{heading}]({link})"
        else:
            bullet = f"- {heading}"
        if caption and caption != heading:
            bullet = f"{bullet}: {caption}"
        bullets.append(bullet)
    return ["## Supplementary Materials", "", *bullets, ""] if bullets else []
