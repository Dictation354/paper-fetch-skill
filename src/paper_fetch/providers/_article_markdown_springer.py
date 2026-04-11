"""Springer/JATS-specific Markdown rendering helpers."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping

from ..utils import first_non_empty
from ._article_markdown_common import (
    XLINK_HREF,
    XLINK_TITLE,
    add_figure_once,
    add_table_once,
    child_text,
    fallback_figure_heading,
    fallback_table_heading,
    first_child,
    first_descendant,
    normalize_table_cell_text,
    normalize_text,
    path_relative_to,
    render_inline_text,
    resolve_springer_asset_link,
    xml_local_name,
)
from ._article_markdown_math import render_display_formula


def build_springer_asset_lookup(
    assets: list[dict[str, Any]],
    *,
    asset_types: set[str],
) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for asset in assets:
        if asset.get("asset_type") not in asset_types or not asset.get("path"):
            continue
        source_href = (asset.get("source_href") or "").strip()
        if source_href:
            lookup[source_href] = asset
            lookup[Path(source_href).name] = asset
    return lookup


def build_jats_section_locations(
    root: ET.Element,
) -> dict[int, str]:
    locations: dict[int, str] = {}

    def walk(element: ET.Element, *, location: str = "body") -> None:
        local_name = xml_local_name(element.tag)
        next_location = location
        if local_name == "body":
            next_location = "body"
        elif local_name in {"app-group", "app"} and location != "supplementary":
            next_location = "appendix"
        elif local_name == "supplementary-material":
            next_location = "supplementary"
        locations[id(element)] = next_location
        for child in list(element):
            if isinstance(child.tag, str):
                walk(child, location=next_location)

    walk(root)
    return locations


def resolve_jats_graphic_href(element: ET.Element | None) -> str:
    if element is None:
        return ""
    for node in element.iter():
        if not isinstance(node.tag, str):
            continue
        if xml_local_name(node.tag) not in {"graphic", "inline-graphic"}:
            continue
        href = (node.get(XLINK_HREF) or node.get("href") or "").strip()
        if href:
            return href
    return ""


def resolve_jats_table_key(element: ET.Element | None) -> str:
    if element is None:
        return ""
    table_id = normalize_text(element.get("id"))
    if table_id:
        return table_id
    href = resolve_jats_graphic_href(element)
    if href:
        return normalize_text(href)
    return ""


def extract_jats_xref_refs(element: ET.Element, ref_type: str) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    normalized_ref_type = ref_type.strip().lower()
    for node in element.iter():
        if not isinstance(node.tag, str) or xml_local_name(node.tag) != "xref":
            continue
        if (node.get("ref-type") or "").strip().lower() != normalized_ref_type:
            continue
        rid = normalize_text(node.get("rid"))
        if rid and rid not in seen:
            refs.append(rid)
            seen.add(rid)
    return refs


def extract_jats_figure_refs(element: ET.Element) -> list[str]:
    refs = extract_jats_xref_refs(element, "fig")
    seen = set(refs)
    for child in list(element):
        if not isinstance(child.tag, str) or xml_local_name(child.tag) != "fig":
            continue
        fig_id = normalize_text(child.get("id"))
        if fig_id and fig_id not in seen:
            refs.append(fig_id)
            seen.add(fig_id)
    return refs


def extract_jats_table_refs(element: ET.Element) -> list[str]:
    refs = extract_jats_xref_refs(element, "table")
    seen = set(refs)
    for child in list(element):
        if not isinstance(child.tag, str):
            continue
        local_name = xml_local_name(child.tag)
        if local_name == "table-wrap":
            table_key = resolve_jats_table_key(child)
            if table_key and table_key not in seen:
                refs.append(table_key)
                seen.add(table_key)
        elif local_name == "table-wrap-group":
            for table_wrap in list(child):
                if not isinstance(table_wrap.tag, str) or xml_local_name(table_wrap.tag) != "table-wrap":
                    continue
                table_key = resolve_jats_table_key(table_wrap)
                if table_key and table_key not in seen:
                    refs.append(table_key)
                    seen.add(table_key)
    return refs


def collect_jats_table_rows(parent: ET.Element | None) -> list[list[str]]:
    if parent is None:
        return []

    rows: list[list[str]] = []
    for row in list(parent):
        if not isinstance(row.tag, str) or xml_local_name(row.tag) != "tr":
            continue
        cells: list[str] = []
        for cell in list(row):
            if not isinstance(cell.tag, str) or xml_local_name(cell.tag) not in {"td", "th"}:
                continue
            cells.append(normalize_table_cell_text(render_inline_text(cell)))
        if cells:
            rows.append(cells)
    return rows


def jats_table_has_spans(table: ET.Element) -> bool:
    for node in table.iter():
        if not isinstance(node.tag, str) or xml_local_name(node.tag) not in {"td", "th"}:
            continue
        for attr_name in {"rowspan", "colspan"}:
            attr_value = (node.get(attr_name) or "").strip()
            if attr_value and attr_value != "1":
                return True
    return False


def render_jats_table_rows(table: ET.Element | None) -> list[list[str]]:
    if table is None:
        return []

    if jats_table_has_spans(table):
        return []

    header_rows = collect_jats_table_rows(first_child(table, "thead"))
    body_rows = collect_jats_table_rows(first_child(table, "tbody"))

    if not header_rows and not body_rows:
        direct_rows = collect_jats_table_rows(table)
        if not direct_rows:
            return []
        header, *rest = direct_rows
        return [header, *rest]

    header = header_rows[0] if header_rows else (body_rows.pop(0) if body_rows else [])
    if not header:
        return []

    column_count = max(len(header), *(len(row) for row in body_rows), 1)

    def pad_row(row: list[str]) -> list[str]:
        return row + [""] * (column_count - len(row))

    return [pad_row(header), *(pad_row(row) for row in body_rows)]


def extract_jats_table_footnotes(table_wrap: ET.Element) -> list[str]:
    foot = first_child(table_wrap, "table-wrap-foot")
    if foot is None:
        return []
    footnotes: list[str] = []
    for node in list(foot):
        if not isinstance(node.tag, str):
            continue
        if xml_local_name(node.tag) == "p":
            text = render_inline_text(node)
            if text:
                footnotes.append(text)
    if not footnotes:
        text = render_inline_text(foot)
        if text:
            footnotes.append(text)
    return footnotes


JATS_ELEMENT_HANDLERS = {
    "sec": "section",
    "p": "paragraph",
    "fig": "figure",
    "table-wrap": "table",
    "table-wrap-group": "table_group",
    "disp-formula": "formula",
    "list": "list",
    "boxed-text": "container",
    "statement": "container",
    "notes": "container",
}


def get_jats_element_handler(local_name: str) -> str:
    return JATS_ELEMENT_HANDLERS.get(local_name, "ignore")


def render_jats_list_block(element: ET.Element) -> list[str]:
    lines: list[str] = []
    for item in list(element):
        if not isinstance(item.tag, str) or xml_local_name(item.tag) != "list-item":
            continue
        parts: list[str] = []
        for node in list(item):
            if not isinstance(node.tag, str):
                continue
            local_name = xml_local_name(node.tag)
            if local_name == "p":
                text = render_inline_text(
                    node,
                    skip_local_names={"fig", "table-wrap", "table-wrap-group", "disp-formula"},
                )
                if text:
                    parts.append(text)
        if not parts:
            text = render_inline_text(
                item,
                skip_local_names={"fig", "table-wrap", "table-wrap-group", "disp-formula"},
            )
            if text:
                parts.append(text)
        if parts:
            lines.append(f"- {' '.join(parts)}")
    if lines and lines[-1] != "":
        lines.append("")
    return lines


def render_jats_container_block(
    element: ET.Element,
    *,
    heading_level: int,
    figure_lookup: Mapping[str, Mapping[str, str]],
    table_lookup: Mapping[str, Mapping[str, Any]],
    used_figure_keys: set[str],
    used_table_keys: set[str],
) -> list[str]:
    lines: list[str] = []
    title = child_text(element, "title")
    child_lines = render_jats_blocks(
        element,
        heading_level=heading_level + 1,
        figure_lookup=figure_lookup,
        table_lookup=table_lookup,
        used_figure_keys=used_figure_keys,
        used_table_keys=used_table_keys,
    )
    if title and child_lines:
        lines.extend([f"{'#' * heading_level} {title}", ""])
    lines.extend(child_lines)
    return lines


def render_jats_blocks(
    parent: ET.Element | None,
    *,
    heading_level: int,
    figure_lookup: Mapping[str, Mapping[str, str]] | None = None,
    table_lookup: Mapping[str, Mapping[str, Any]] | None = None,
    used_figure_keys: set[str] | None = None,
    used_table_keys: set[str] | None = None,
) -> list[str]:
    if parent is None:
        return []

    lines: list[str] = []
    lookup = figure_lookup or {}
    table_entries = table_lookup or {}
    used_keys = used_figure_keys if used_figure_keys is not None else set()
    used_table_entries = used_table_keys if used_table_keys is not None else set()
    for child in list(parent):
        if not isinstance(child.tag, str):
            continue
        local_name = xml_local_name(child.tag)
        handler = get_jats_element_handler(local_name)
        if local_name == "title":
            continue
        if handler == "paragraph":
            text = render_inline_text(child, skip_local_names={"fig", "table-wrap", "table-wrap-group", "disp-formula"})
            if text:
                lines.extend([text, ""])
            for figure_ref in extract_jats_figure_refs(child):
                add_figure_once(lines, lookup.get(figure_ref), used_keys)
            for table_ref in extract_jats_table_refs(child):
                add_table_once(lines, table_entries.get(table_ref), used_table_entries)
            for formula_node in list(child):
                if not isinstance(formula_node.tag, str):
                    continue
                formula_local_name = xml_local_name(formula_node.tag)
                if formula_local_name == "disp-formula":
                    lines.extend(render_display_formula(formula_node))
                elif formula_local_name == "table-wrap":
                    add_table_once(lines, table_entries.get(resolve_jats_table_key(formula_node)), used_table_entries)
                elif formula_local_name == "table-wrap-group":
                    for table_wrap in list(formula_node):
                        if not isinstance(table_wrap.tag, str) or xml_local_name(table_wrap.tag) != "table-wrap":
                            continue
                        add_table_once(
                            lines,
                            table_entries.get(resolve_jats_table_key(table_wrap)),
                            used_table_entries,
                        )
            continue
        if handler == "section":
            title = child_text(child, "title")
            if title:
                lines.extend([f"{'#' * heading_level} {title}", ""])
            lines.extend(
                render_jats_blocks(
                    child,
                    heading_level=heading_level + 1,
                    figure_lookup=lookup,
                    table_lookup=table_entries,
                    used_figure_keys=used_keys,
                    used_table_keys=used_table_entries,
                )
            )
            continue
        if handler == "figure":
            figure_key = normalize_text(child.get("id")) or normalize_text(resolve_jats_graphic_href(child))
            add_figure_once(lines, lookup.get(figure_key), used_keys)
            continue
        if handler == "table":
            add_table_once(lines, table_entries.get(resolve_jats_table_key(child)), used_table_entries)
            continue
        if handler == "table_group":
            for table_wrap in list(child):
                if not isinstance(table_wrap.tag, str) or xml_local_name(table_wrap.tag) != "table-wrap":
                    continue
                add_table_once(lines, table_entries.get(resolve_jats_table_key(table_wrap)), used_table_entries)
            continue
        if handler == "formula":
            lines.extend(render_display_formula(child))
            continue
        if handler == "list":
            lines.extend(render_jats_list_block(child))
            continue
        if handler == "container":
            lines.extend(
                render_jats_container_block(
                    child,
                    heading_level=heading_level,
                    figure_lookup=lookup,
                    table_lookup=table_entries,
                    used_figure_keys=used_keys,
                    used_table_keys=used_table_entries,
                )
            )
    return lines


def springer_table_registry(
    root: ET.Element,
    assets: list[dict[str, Any]],
    markdown_path: Path,
    doi: str,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], set[str]]:
    image_assets = build_springer_asset_lookup(assets, asset_types={"image", "table_asset"})
    section_locations = build_jats_section_locations(root)

    lookup: dict[str, dict[str, Any]] = {}
    entries: list[dict[str, Any]] = []
    reserved_image_paths: set[str] = set()
    for table_wrap in root.iter():
        if not isinstance(table_wrap.tag, str) or xml_local_name(table_wrap.tag) != "table-wrap":
            continue
        table_key = resolve_jats_table_key(table_wrap)
        label = child_text(table_wrap, "label") or fallback_table_heading(table_wrap.get("id"))
        caption = render_inline_text(first_child(table_wrap, "caption"))
        footnotes = extract_jats_table_footnotes(table_wrap)
        table_node = first_descendant(table_wrap, "table")
        table_rows = render_jats_table_rows(table_node)
        href = resolve_jats_graphic_href(table_wrap)
        asset = image_assets.get(href) or image_assets.get(Path(href).name)
        link = resolve_springer_asset_link(markdown_path, asset, href, doi, asset_bucket="image")
        if asset and asset.get("path"):
            reserved_image_paths.add(str(asset["path"]))
        section = normalize_text(
            str((asset.get("section") if asset else None) or section_locations.get(id(table_wrap), "body") or "body")
        ) or "body"

        entry: dict[str, Any]
        if table_rows:
            entry = {
                "key": table_key or f"table:{len(entries) + 1}",
                "kind": "structured",
                "heading": label,
                "caption": caption,
                "rows": table_rows,
                "footnotes": footnotes,
                "link": link,
                "section": section,
            }
        elif table_node is not None and link:
            entry = {
                "key": table_key or link,
                "kind": "fallback",
                "heading": label,
                "caption": caption,
                "footnotes": footnotes,
                "link": link,
                "fallback_message": "Table content could not be fully converted to Markdown; the original table image is retained below.",
                "section": section,
            }
        elif table_node is not None:
            entry = {
                "key": table_key or f"table:{len(entries) + 1}",
                "kind": "fallback",
                "heading": label,
                "caption": caption,
                "footnotes": footnotes,
                "link": "",
                "fallback_message": "Table content could not be fully converted to Markdown; no original table image was available.",
                "section": section,
            }
        elif link:
            entry = {
                "key": table_key or link,
                "kind": "image",
                "heading": label,
                "caption": caption,
                "footnotes": footnotes,
                "link": link,
                "section": section,
            }
        else:
            entry = {
                "key": table_key or f"table:{len(entries) + 1}",
                "kind": "fallback",
                "heading": label,
                "caption": caption,
                "footnotes": footnotes,
                "link": "",
                "fallback_message": "Table content could not be fully converted to Markdown; no original table image was available.",
                "section": section,
            }
        entries.append(entry)
        for key in {
            table_key,
            normalize_text(table_wrap.get("id")),
            normalize_text(href),
            normalize_text(Path(href).name),
        }:
            if key:
                lookup[key] = entry
    return lookup, entries, reserved_image_paths


def springer_figure_registry(
    root: ET.Element,
    assets: list[dict[str, Any]],
    markdown_path: Path,
    doi: str,
    *,
    excluded_asset_paths: set[str] | None = None,
) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    image_assets = build_springer_asset_lookup(assets, asset_types={"image"})
    excluded_paths = excluded_asset_paths or set()
    section_locations = build_jats_section_locations(root)

    lookup: dict[str, dict[str, str]] = {}
    entries: list[dict[str, str]] = []
    used_asset_paths: set[str] = set()
    for fig in root.iter():
        if not isinstance(fig.tag, str) or xml_local_name(fig.tag) != "fig":
            continue
        label = child_text(fig, "label") or fallback_figure_heading(fig.get("id"))
        caption = render_inline_text(first_child(fig, "caption"))
        href = resolve_jats_graphic_href(fig)
        asset = image_assets.get(href) or image_assets.get(Path(href).name)
        asset_path = str(asset["path"]) if asset and asset.get("path") else ""
        link = resolve_springer_asset_link(markdown_path, asset, href, doi, asset_bucket="image")
        if (
            (asset_path and asset_path in used_asset_paths)
            or (asset_path and asset_path in excluded_paths)
            or not link
        ):
            continue
        if asset_path:
            used_asset_paths.add(asset_path)
        entry = {
            "key": normalize_text(fig.get("id")) or normalize_text(href) or link,
            "heading": label,
            "caption": caption,
            "link": link,
            "path": asset_path or "",
            "section": normalize_text(
                str((asset.get("section") if asset else None) or section_locations.get(id(fig), "body") or "body")
            )
            or "body",
        }
        entries.append(entry)
        for key in {
            normalize_text(fig.get("id")),
            normalize_text(href),
            normalize_text(Path(href).name),
        }:
            if key:
                lookup[key] = entry

    for asset in assets:
        asset_path = str(asset.get("path") or "")
        if (
            asset.get("asset_type") != "image"
            or not asset_path
            or asset_path in used_asset_paths
            or asset_path in excluded_paths
        ):
            continue
        entries.append(
            {
                "key": asset_path,
                "heading": Path(asset_path).name,
                "caption": "",
                "link": path_relative_to(markdown_path.parent, asset_path),
                "path": asset_path,
                "section": normalize_text(str(asset.get("section") or "body")) or "body",
            }
        )
    return lookup, entries


def springer_supplement_entries(root: ET.Element, assets: list[dict[str, Any]], markdown_path: Path, doi: str) -> list[dict[str, str]]:
    supplementary_assets = build_springer_asset_lookup(assets, asset_types={"supplementary"})

    entries: list[dict[str, str]] = []
    used_paths: set[str] = set()
    for supplementary in root.iter():
        if not isinstance(supplementary.tag, str) or xml_local_name(supplementary.tag) != "supplementary-material":
            continue
        media = first_descendant(supplementary, "media")
        if media is None:
            continue
        href = (media.get(XLINK_HREF) or media.get("href") or "").strip()
        asset = supplementary_assets.get(href) or supplementary_assets.get(Path(href).name)
        link = resolve_springer_asset_link(markdown_path, asset, href, doi, asset_bucket="esm")
        asset_path = str(asset["path"]) if asset and asset.get("path") else ""
        if (asset_path and asset_path in used_paths) or not link:
            continue
        if asset_path:
            used_paths.add(asset_path)
        caption_text = render_inline_text(first_child(media, "caption")) or render_inline_text(first_child(supplementary, "caption"))
        label_text = child_text(supplementary, "label") or child_text(supplementary, "title")
        xlink_title = normalize_text(supplementary.get(XLINK_TITLE))
        fallback_name = Path(asset_path or href).name
        heading = first_non_empty(caption_text, label_text, xlink_title, fallback_name)
        extra_caption = ""
        for candidate in [label_text, xlink_title, caption_text]:
            normalized_candidate = normalize_text(candidate)
            if normalized_candidate and normalized_candidate != heading:
                extra_caption = normalized_candidate
                break
        entries.append(
            {
                "heading": heading,
                "caption": extra_caption,
                "link": link,
                "path": asset_path,
                "section": "supplementary",
            }
        )

    for asset in assets:
        asset_path = str(asset.get("path") or "")
        if asset.get("asset_type") != "supplementary" or not asset_path or asset_path in used_paths:
            continue
        entries.append(
            {
                "heading": Path(asset_path).name,
                "caption": "",
                "link": path_relative_to(markdown_path.parent, asset_path),
                "path": asset_path,
                "section": "supplementary",
            }
        )
    return entries
