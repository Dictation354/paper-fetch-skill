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
from ..extraction.xml_tables import ParsedXmlTable, parse_xml_table_groups
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
    table_conversion_note,
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


def _graphic_alternatives(
    container: ET.Element,
    source_url: str,
) -> list[dict[str, Any]]:
    alternatives: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in container.iter():
        if not isinstance(node.tag, str):
            continue
        local_name = xml_local_name(node.tag)
        if local_name not in {"graphic", "inline-graphic", "media"}:
            continue
        url = _urljoin(source_url, _href(node))
        if not url or url in seen:
            continue
        seen.add(url)
        mimetype = _attribute_text(node, "mimetype", "mime-type")
        mime_subtype = _attribute_text(node, "mime-subtype")
        if mimetype and mime_subtype and "/" not in mimetype:
            mimetype = f"{mimetype}/{mime_subtype}"
        alternatives.append(
            {
                "url": url,
                "original_url": url,
                "content_type": mimetype or None,
                "media_type": local_name,
                "specific_use": _attribute_text(node, "specific-use", "content-type")
                or None,
                "source_id": _element_id(node) or None,
                "panel_index": len(alternatives) + 1,
            }
        )
    return alternatives


def _figure_entry(figure: ET.Element, source_url: str) -> dict[str, Any] | None:
    alternatives = _graphic_alternatives(figure, source_url)
    url = normalize_text(alternatives[0]["url"]) if alternatives else ""
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
        entry.update(
            {
                "link": url,
                "original_url": url,
                "alternatives": alternatives,
            }
        )
    return entry


def _table_node(table_wrap: ET.Element) -> ET.Element | None:
    if xml_local_name(table_wrap.tag) == "table":
        return table_wrap
    return first_descendant(table_wrap, "table")


def _render_parsed_structured_table(
    parsed: ParsedXmlTable,
) -> _JatsTableRenderResult:
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


def _render_structured_table_groups(
    table: ET.Element,
) -> list[_JatsTableRenderResult]:
    parsed_groups = parse_xml_table_groups(
        table,
        render_cell_text=lambda cell: normalize_table_cell_text(
            render_inline_text(cell)
        ),
    )
    return [_render_parsed_structured_table(parsed) for parsed in parsed_groups]


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


def _table_entry(
    table_wrap: ET.Element,
    source_url: str = "",
) -> tuple[dict[str, Any] | None, bool]:
    label = normalize_text(child_text(table_wrap, "label")) or "Table"
    caption = _caption_text(table_wrap)
    table = _table_node(table_wrap)
    key = _element_id(table_wrap) or _element_id(table) or label
    graphic_alternatives = _graphic_alternatives(table_wrap, source_url)
    if table is not None:
        render_results = _render_structured_table_groups(table)
        rendered_groups = [result for result in render_results if result.rows]
        lossy = any(result.layout_degraded for result in rendered_groups)
    else:
        render_results = []
        rendered_groups = []
        lossy = False
    if rendered_groups:
        primary_group = rendered_groups[0]
        fallback_count = sum(
            1 for result in rendered_groups if result.render_kind == "structured_list"
        )
        layout_degraded_count = sum(
            1 for result in rendered_groups if result.layout_degraded
        )
        conversion_notes = list(
            dict.fromkeys(
                note
                for result in rendered_groups
                if result.layout_degraded
                for note in [table_conversion_note(result.status)]
                if note
            )
        )
        entry: dict[str, Any] = {
            "kind": "table",
            "table_render_kind": (
                "grouped" if len(rendered_groups) > 1 else primary_group.render_kind
            ),
            "key": key,
            "anchor_key": key,
            "heading": label,
            "caption": caption,
            "headers": primary_group.headers,
            "rows": primary_group.rows,
            "footnotes": _table_footnotes(table_wrap),
            "section": "body",
            "render_state": "inline",
            "_table_fallback_count": fallback_count,
            "_table_layout_degraded_count": layout_degraded_count,
        }
        if len(rendered_groups) > 1:
            entry["_table_groups"] = [
                {
                    "table_render_kind": result.render_kind,
                    "headers": result.headers,
                    "rows": result.rows,
                    **(
                        {"_table_prefix_rows": result.prefix_rows}
                        if result.prefix_rows
                        else {}
                    ),
                }
                for result in rendered_groups
            ]
        elif primary_group.prefix_rows:
            entry["_table_prefix_rows"] = primary_group.prefix_rows
        if graphic_alternatives:
            entry["link"] = graphic_alternatives[0]["url"]
            entry["original_url"] = graphic_alternatives[0]["url"]
            entry["alternatives"] = graphic_alternatives
        if lossy:
            if conversion_notes:
                entry["lossy_message"] = conversion_notes[0]
                entry["conversion_notes"] = conversion_notes
        return entry, lossy
    if caption or graphic_alternatives:
        fallback_message = (
            "Table was supplied as a graphic; its image asset and caption were retained."
            if graphic_alternatives
            else "Table content could not be converted to Markdown; caption text was retained."
        )
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
            "fallback_message": fallback_message,
            "conversion_notes": [fallback_message],
            "_table_fallback_count": 1,
            "_table_layout_degraded_count": 0,
            **(
                {
                    "link": graphic_alternatives[0]["url"],
                    "original_url": graphic_alternatives[0]["url"],
                    "alternatives": graphic_alternatives,
                }
                if graphic_alternatives
                else {}
            ),
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
        text = normalize_text(render_inline_text(node))
        base_title = (
            normalize_text(str(node.get(XLINK_TITLE) or node.get("content-type") or ""))
            or text
            or "Supplementary material"
        )
        link_nodes = [
            candidate
            for candidate in node.iter()
            if isinstance(candidate.tag, str)
            and xml_local_name(candidate.tag)
            in {
                "ext-link",
                "graphic",
                "inline-supplementary-material",
                "media",
                "supplementary-material",
            }
            and _href(candidate)
        ]
        if _href(node) and node not in link_nodes:
            link_nodes.insert(0, node)
        for link_index, link_node in enumerate(link_nodes, start=1):
            source_href = _href(link_node)
            url = _urljoin(source_url, source_href)
            if not url or url in seen:
                continue
            seen.add(url)
            title = (
                _attribute_text(link_node, XLINK_TITLE, "content-type") or base_title
            )
            key = url or _element_id(link_node) or _element_id(node) or title
            entry: dict[str, Any] = {
                "kind": "supplementary",
                "key": key,
                "anchor_key": key,
                "heading": title,
                "caption": text if text and text != title else "",
                "section": "supplementary",
                "link": url,
                "original_url": url,
                "source_href": source_href,
                "content_type": _attribute_text(link_node, "mimetype", "mime-type")
                or None,
                "attachment_index": link_index,
            }
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
