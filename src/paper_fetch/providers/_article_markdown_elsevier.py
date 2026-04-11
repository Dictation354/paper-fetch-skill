"""Elsevier XML-specific Markdown rendering helpers."""

from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping

from ._article_markdown_common import (
    add_figure_once,
    add_table_once,
    child_text,
    fallback_table_heading,
    first_child,
    first_descendant,
    normalize_table_cell_text,
    normalize_text,
    path_relative_to,
    render_inline_text,
    xml_local_name,
)
from ._article_markdown_math import render_display_formula
from ._elsevier_xml_rules import (
    ELSEVIER_IMAGE_ASSET_TYPES,
    get_elsevier_element_rule,
    infer_elsevier_asset_group_key,
    should_ignore_elsevier_section_title,
)

ELSEVIER_BLOCK_LOCAL_NAMES = {"display", "figure", "table", "e-component", "formula"}


def collect_elsevier_table_rows(parent: ET.Element | None) -> list[list[str]]:
    if parent is None:
        return []

    rows: list[list[str]] = []
    for row in list(parent):
        if not isinstance(row.tag, str) or xml_local_name(row.tag) != "row":
            continue
        cells: list[str] = []
        for entry in list(row):
            if not isinstance(entry.tag, str) or xml_local_name(entry.tag) != "entry":
                continue
            cells.append(normalize_table_cell_text(render_inline_text(entry)))
        if cells:
            rows.append(cells)
    return rows


def elsevier_table_has_spans(table: ET.Element) -> bool:
    for node in table.iter():
        if not isinstance(node.tag, str) or xml_local_name(node.tag) != "entry":
            continue
        if node.get("namest") or node.get("nameend") or node.get("morerows"):
            return True
    return False


def resolve_elsevier_asset_link(markdown_path: Path, asset: Mapping[str, Any] | None) -> str:
    if asset and asset.get("path"):
        return path_relative_to(markdown_path.parent, str(asset["path"]))
    if asset and asset.get("source_url"):
        return normalize_text(str(asset["source_url"]))
    return ""


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


def render_elsevier_table_rows(table: ET.Element | None) -> list[list[str]]:
    if table is None:
        return []
    if elsevier_table_has_spans(table):
        return []

    tgroup = first_child(table, "tgroup")
    if tgroup is None:
        tgroup = first_descendant(table, "tgroup")
    header_rows = collect_elsevier_table_rows(first_child(tgroup, "thead"))
    body_rows = collect_elsevier_table_rows(first_child(tgroup, "tbody"))
    if not header_rows and tgroup is not None:
        for child in list(tgroup):
            if not isinstance(child.tag, str) or xml_local_name(child.tag) != "row":
                continue
            row_cells = [
                normalize_table_cell_text(render_inline_text(entry))
                for entry in list(child)
                if isinstance(entry.tag, str) and xml_local_name(entry.tag) == "entry"
            ]
            if row_cells:
                body_rows.append(row_cells)

    header = header_rows[0] if header_rows else (body_rows.pop(0) if body_rows else [])
    if not header:
        return []

    column_count = max(len(header), *(len(row) for row in body_rows), 1)

    def pad_row(row: list[str]) -> list[str]:
        return row + [""] * (column_count - len(row))

    return [pad_row(header), *(pad_row(row) for row in body_rows)]


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


def classify_elsevier_display_block(element: ET.Element) -> str:
    if first_descendant(element, "figure") is not None:
        return "figure"
    if first_descendant(element, "table") is not None:
        return "table"
    if first_descendant(element, "e-component") is not None:
        return "supplementary"
    if first_descendant(element, "formula") is not None:
        return "formula"
    if first_descendant(element, "math") is not None or first_descendant(element, "tex-math") is not None:
        return "formula"
    return "ignore"


def figure_reference_token(heading: str) -> str | None:
    normalized = normalize_text(heading)
    match = re.search(r"(?:fig(?:ure)?\.?\s*)([a-z]?\d+)", normalized, flags=re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return None


def paragraph_mentions_figure(text: str, heading: str) -> bool:
    token = figure_reference_token(heading)
    if not token:
        return False
    pattern = re.compile(
        rf"\bfig(?:ure)?\.?\s*{re.escape(token)}(?:[a-z](?!\w))?",
        flags=re.IGNORECASE,
    )
    return bool(pattern.search(text))


def table_reference_token(heading: str) -> str | None:
    normalized = normalize_text(heading)
    match = re.search(r"(?:tab(?:le)?\.?\s*)([a-z]?\d+)", normalized, flags=re.IGNORECASE)
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


def should_render_elsevier_figure_entry(
    entry: Mapping[str, str] | None,
    *,
    inside_appendix: bool,
) -> bool:
    if not entry:
        return False
    return inside_appendix or entry.get("section") != "appendix"


def add_elsevier_figure_once(
    lines: list[str],
    entry: Mapping[str, str] | None,
    used_figure_keys: set[str],
    *,
    inside_appendix: bool,
) -> None:
    if not should_render_elsevier_figure_entry(entry, inside_appendix=inside_appendix):
        return
    add_figure_once(lines, entry, used_figure_keys)


def append_text_to_fragment(root: ET.Element, text: str | None) -> None:
    if not text:
        return
    if len(root):
        last_child = root[-1]
        last_child.tail = (last_child.tail or "") + text
        return
    root.text = (root.text or "") + text


def render_elsevier_paragraph_fragments(element: ET.Element) -> list[tuple[str, ET.Element]]:
    fragments: list[tuple[str, ET.Element]] = []
    current = ET.Element("fragment")
    current.text = element.text or ""

    for child in list(element):
        if not isinstance(child.tag, str):
            append_text_to_fragment(current, child.tail)
            continue

        local_name = xml_local_name(child.tag)
        if local_name in ELSEVIER_BLOCK_LOCAL_NAMES:
            if render_inline_text(current):
                fragments.append(("text", current))
            fragments.append(("block", child))
            current = ET.Element("fragment")
            current.text = child.tail or ""
            continue

        clone = copy.deepcopy(child)
        clone.tail = child.tail or ""
        current.append(clone)

    if render_inline_text(current):
        fragments.append(("text", current))
    return fragments


def extract_elsevier_figure_refs(element: ET.Element) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for node in element.iter():
        if not isinstance(node.tag, str) or xml_local_name(node.tag) != "cross-ref":
            continue
        refid = normalize_text(node.get("refid"))
        if refid and refid not in seen:
            refs.append(refid)
            seen.add(refid)
    return refs


def extract_elsevier_table_refs(element: ET.Element) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for node in element.iter():
        if not isinstance(node.tag, str):
            continue
        local_name = xml_local_name(node.tag)
        if local_name in {"cross-ref", "float-anchor"}:
            refid = normalize_text(node.get("refid"))
            if refid and refid not in seen:
                refs.append(refid)
                seen.add(refid)
            continue
        if local_name != "table":
            continue
        table_key = resolve_elsevier_table_key(node)
        if table_key and table_key not in seen:
            refs.append(table_key)
            seen.add(table_key)
    return refs


def extract_elsevier_display_figure_refs(element: ET.Element) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for node in element.iter():
        if not isinstance(node.tag, str) or xml_local_name(node.tag) != "figure":
            continue
        figure_id = normalize_text(node.get("id"))
        if figure_id and figure_id not in seen:
            refs.append(figure_id)
            seen.add(figure_id)
        for child in list(node):
            if not isinstance(child.tag, str) or xml_local_name(child.tag) != "link":
                continue
            locator = normalize_text(child.get("locator"))
            if locator and locator not in seen:
                refs.append(locator)
                seen.add(locator)
            break
    return refs


def extract_elsevier_display_table_refs(element: ET.Element) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for node in element.iter():
        if not isinstance(node.tag, str) or xml_local_name(node.tag) != "table":
            continue
        for key in {
            resolve_elsevier_table_key(node),
            normalize_text(node.get("id")),
            resolve_elsevier_table_locator(node),
        }:
            if key and key not in seen:
                refs.append(key)
                seen.add(key)
    return refs


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


def render_elsevier_display_block(
    element: ET.Element,
    *,
    figure_lookup: Mapping[str, Mapping[str, str]],
    used_figure_keys: set[str],
    table_lookup: Mapping[str, Mapping[str, Any]],
    used_table_keys: set[str],
    inside_appendix: bool = False,
) -> list[str]:
    display_kind = classify_elsevier_display_block(element)
    if display_kind == "figure":
        figure_refs = extract_elsevier_display_figure_refs(element)
        lines: list[str] = []
        for figure_ref in figure_refs:
            add_elsevier_figure_once(
                lines,
                figure_lookup.get(figure_ref),
                used_figure_keys,
                inside_appendix=inside_appendix,
            )
        return lines
    if display_kind == "table":
        table_refs = extract_elsevier_display_table_refs(element)
        lines: list[str] = []
        for table_ref in table_refs:
            add_elsevier_table_once(
                lines,
                table_lookup.get(table_ref),
                used_table_keys,
                inside_appendix=inside_appendix,
            )
        return lines
    if display_kind == "supplementary":
        return []
    if display_kind == "formula":
        return render_display_formula(element)
    return []


def render_elsevier_blocks(
    parent: ET.Element | None,
    *,
    heading_level: int,
    figure_lookup: Mapping[str, Mapping[str, str]] | None = None,
    figure_entries: list[Mapping[str, str]] | None = None,
    used_figure_keys: set[str] | None = None,
    table_lookup: Mapping[str, Mapping[str, Any]] | None = None,
    used_table_keys: set[str] | None = None,
    inside_appendix: bool = False,
) -> list[str]:
    if parent is None:
        return []

    lines: list[str] = []
    lookup = figure_lookup or {}
    entries = figure_entries or []
    used_keys = used_figure_keys if used_figure_keys is not None else set()
    table_entries = table_lookup or {}
    used_table_entries = used_table_keys if used_table_keys is not None else set()
    for child in list(parent):
        if not isinstance(child.tag, str):
            continue
        local_name = xml_local_name(child.tag)
        rule = get_elsevier_element_rule(local_name)

        if rule.handler == "section":
            title = child_text(child, "section-title") or child_text(child, "title")
            if should_ignore_elsevier_section_title(title):
                continue
            child_lines = render_elsevier_blocks(
                child,
                heading_level=heading_level + 1,
                figure_lookup=lookup,
                figure_entries=entries,
                used_figure_keys=used_keys,
                table_lookup=table_entries,
                used_table_keys=used_table_entries,
                inside_appendix=inside_appendix,
            )
            normalized_title = normalize_text(title)
            if normalized_title and normalized_title.lower() != "main text" and child_lines:
                lines.extend([f"{'#' * heading_level} {normalized_title}", ""])
            lines.extend(child_lines)
            continue

        if rule.handler == "container":
            lines.extend(
                render_elsevier_blocks(
                    child,
                    heading_level=heading_level,
                    figure_lookup=lookup,
                    figure_entries=entries,
                    used_figure_keys=used_keys,
                    table_lookup=table_entries,
                    used_table_keys=used_table_entries,
                    inside_appendix=inside_appendix or local_name in {"appendices", "appendix"},
                )
            )
            continue

        if rule.handler == "paragraph":
            for fragment_kind, fragment in render_elsevier_paragraph_fragments(child):
                if fragment_kind == "text":
                    text = render_inline_text(fragment)
                    if text:
                        lines.extend([text, ""])
                    for figure_ref in extract_elsevier_figure_refs(fragment):
                        add_elsevier_figure_once(
                            lines,
                            lookup.get(figure_ref),
                            used_keys,
                            inside_appendix=inside_appendix,
                        )
                    for table_ref in extract_elsevier_table_refs(fragment):
                        add_elsevier_table_once(
                            lines,
                            table_entries.get(table_ref),
                            used_table_entries,
                            inside_appendix=inside_appendix,
                        )
                    for entry in entries:
                        if entry["key"] in used_keys:
                            continue
                        if not should_render_elsevier_figure_entry(entry, inside_appendix=inside_appendix):
                            continue
                        if text and paragraph_mentions_figure(text, entry["heading"]):
                            add_figure_once(lines, entry, used_keys)
                    seen_table_keys: set[str] = set()
                    for entry in table_entries.values():
                        entry_key = str(entry["key"])
                        if entry_key in seen_table_keys:
                            continue
                        seen_table_keys.add(entry_key)
                        if entry_key in used_table_entries:
                            continue
                        if not should_render_elsevier_table_entry(entry, inside_appendix=inside_appendix):
                            continue
                        if text and paragraph_mentions_table(text, str(entry.get("heading") or "")):
                            add_elsevier_table_once(
                                lines,
                                entry,
                                used_table_entries,
                                inside_appendix=inside_appendix,
                            )
                    continue

                nested = fragment
                nested_name = xml_local_name(nested.tag)
                nested_rule = get_elsevier_element_rule(nested_name)
                if nested_rule.handler == "display":
                    lines.extend(
                        render_elsevier_display_block(
                            nested,
                            figure_lookup=lookup,
                            used_figure_keys=used_keys,
                            table_lookup=table_entries,
                            used_table_keys=used_table_entries,
                            inside_appendix=inside_appendix,
                        )
                    )
                elif nested_rule.handler == "figure":
                    for figure_ref in extract_elsevier_display_figure_refs(nested):
                        add_elsevier_figure_once(
                            lines,
                            lookup.get(figure_ref),
                            used_keys,
                            inside_appendix=inside_appendix,
                        )
                elif nested_rule.handler == "table":
                    add_elsevier_table_once(
                        lines,
                        table_entries.get(resolve_elsevier_table_key(nested)),
                        used_table_entries,
                        inside_appendix=inside_appendix,
                    )
                elif nested_rule.handler == "formula":
                    lines.extend(render_display_formula(nested))
            continue

        if rule.handler == "display":
            lines.extend(
                render_elsevier_display_block(
                    child,
                    figure_lookup=lookup,
                    used_figure_keys=used_keys,
                    table_lookup=table_entries,
                    used_table_keys=used_table_entries,
                    inside_appendix=inside_appendix,
                )
            )
            continue

        if rule.handler == "figure":
            for figure_ref in extract_elsevier_display_figure_refs(child):
                add_elsevier_figure_once(
                    lines,
                    lookup.get(figure_ref),
                    used_keys,
                    inside_appendix=inside_appendix,
                )
            continue

        if rule.handler == "table":
            add_elsevier_table_once(
                lines,
                table_entries.get(resolve_elsevier_table_key(child)),
                used_table_entries,
                inside_appendix=inside_appendix,
            )
            continue

        if rule.handler == "formula":
            lines.extend(render_display_formula(child))
    return lines


def build_elsevier_asset_lookup(
    assets: list[dict[str, Any]],
    *,
    asset_types: set[str],
) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for asset in assets:
        asset_type = str(asset.get("asset_type") or "")
        if asset_type not in asset_types:
            continue
        source_ref = normalize_text(str(asset.get("source_ref") or ""))
        if source_ref:
            lookup[source_ref] = asset
        group_key = normalize_text(infer_elsevier_asset_group_key(str(asset.get("source_ref") or "")))
        if group_key:
            lookup[group_key] = asset
    return lookup


def elsevier_table_registry(
    root: ET.Element,
    assets: list[dict[str, Any]],
    markdown_path: Path,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    table_assets = build_elsevier_asset_lookup(assets, asset_types={"table_asset"})

    appendix_table_ids: set[str] = set()
    appendix_table_locators: set[str] = set()
    for container in root.iter():
        if not isinstance(container.tag, str) or xml_local_name(container.tag) not in {"appendices", "appendix"}:
            continue
        for table in container.iter():
            if not isinstance(table.tag, str) or xml_local_name(table.tag) != "table":
                continue
            table_id = normalize_text(table.get("id"))
            if table_id:
                appendix_table_ids.add(table_id)
            locator = resolve_elsevier_table_locator(table)
            if locator:
                appendix_table_locators.add(locator)

    lookup: dict[str, dict[str, Any]] = {}
    entries: list[dict[str, Any]] = []
    used_links: set[str] = set()
    for table in root.iter():
        if not isinstance(table.tag, str) or xml_local_name(table.tag) != "table":
            continue

        table_id = normalize_text(table.get("id"))
        locator = resolve_elsevier_table_locator(table)
        table_key = resolve_elsevier_table_key(table)
        label = child_text(table, "label") or fallback_table_heading(table_id)
        caption = render_inline_text(first_child(table, "caption"))
        footnotes = extract_elsevier_table_footnotes(table)
        rows = render_elsevier_table_rows(table)
        asset = table_assets.get(locator) or table_assets.get(table_id)
        link = resolve_elsevier_asset_link(markdown_path, asset)
        if link and link in used_links:
            link = ""
        if link:
            used_links.add(link)

        if rows:
            entry: dict[str, Any] = {
                "key": table_key or f"table:{len(entries) + 1}",
                "kind": "structured",
                "heading": label,
                "caption": caption,
                "rows": rows,
                "footnotes": footnotes,
                "link": link,
            }
        elif link:
            entry = {
                "key": table_key or link,
                "kind": "fallback",
                "heading": label,
                "caption": caption,
                "footnotes": footnotes,
                "link": link,
                "fallback_message": "Table content could not be fully converted to Markdown; the original table image is retained below.",
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
            }

        entry["section"] = (
            "appendix"
            if table_id in appendix_table_ids or locator in appendix_table_locators
            else "body"
        )
        entries.append(entry)

        for key in {table_key, table_id, locator}:
            if key:
                lookup[key] = entry

    return lookup, entries


def elsevier_figure_registry(
    root: ET.Element,
    assets: list[dict[str, Any]],
    markdown_path: Path,
) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    image_assets = build_elsevier_asset_lookup(
        assets,
        asset_types=set(ELSEVIER_IMAGE_ASSET_TYPES) - {"graphical_abstract"},
    )

    lookup: dict[str, dict[str, str]] = {}
    entries: list[dict[str, str]] = []
    used_asset_paths: set[str] = set()
    appendix_figure_ids: set[str] = set()
    appendix_figure_locators: set[str] = set()
    for container in root.iter():
        if not isinstance(container.tag, str) or xml_local_name(container.tag) not in {"appendices", "appendix"}:
            continue
        for figure in container.iter():
            if not isinstance(figure.tag, str) or xml_local_name(figure.tag) != "figure":
                continue
            figure_id = normalize_text(figure.get("id"))
            if figure_id:
                appendix_figure_ids.add(figure_id)
            for node in list(figure):
                if not isinstance(node.tag, str) or xml_local_name(node.tag) != "link":
                    continue
                locator = normalize_text(node.get("locator"))
                if locator:
                    appendix_figure_locators.add(locator)
                break
    for figure in root.iter():
        if not isinstance(figure.tag, str) or xml_local_name(figure.tag) != "figure":
            continue
        label = child_text(figure, "label") or "Figure"
        caption = render_inline_text(first_child(figure, "caption"))
        figure_id = normalize_text(figure.get("id"))
        locator = ""
        for node in list(figure):
            if isinstance(node.tag, str) and xml_local_name(node.tag) == "link":
                locator = (node.get("locator") or "").strip()
                if locator:
                    break
        asset = image_assets.get(locator) or image_assets.get(normalize_text(locator))
        asset_path = str(asset.get("path") or "") if asset else ""
        if not asset or not asset_path or asset_path in used_asset_paths:
            continue
        used_asset_paths.add(asset_path)
        asset_type = str(asset.get("asset_type") or "")
        entry = {
            "key": asset_path,
            "heading": label,
            "caption": caption,
            "link": path_relative_to(markdown_path.parent, asset_path),
            "path": asset_path,
            "section": (
                "appendix"
                if asset_type == "appendix_image"
                or figure_id in appendix_figure_ids
                or normalize_text(locator) in appendix_figure_locators
                else "body"
            ),
        }
        entries.append(entry)
        for key in {figure_id, normalize_text(locator)}:
            if key:
                lookup[key] = entry

    for asset in assets:
        if (
            asset.get("asset_type") not in {"image", "appendix_image"}
            or not asset.get("path")
            or asset["path"] in used_asset_paths
        ):
            continue
        entries.append(
            {
                "key": str(asset["path"]),
                "heading": Path(asset["path"]).name,
                "caption": "",
                "link": path_relative_to(markdown_path.parent, asset["path"]),
                "path": str(asset["path"]),
                "section": "appendix" if asset.get("asset_type") == "appendix_image" else "body",
            }
        )
    return lookup, entries


def elsevier_supplement_entries(root: ET.Element, assets: list[dict[str, Any]], markdown_path: Path) -> list[dict[str, str]]:
    supplementary_assets: dict[str, dict[str, Any]] = {}
    for asset in assets:
        if asset.get("asset_type") != "supplementary" or not asset.get("path"):
            continue
        source_ref = (asset.get("source_ref") or "").strip()
        if source_ref:
            supplementary_assets[source_ref] = asset
            supplementary_assets[normalize_text(source_ref)] = asset

    entries: list[dict[str, str]] = []
    used_paths: set[str] = set()
    for component in root.iter():
        if not isinstance(component.tag, str) or xml_local_name(component.tag) != "e-component":
            continue
        label = child_text(component, "label")
        caption = render_inline_text(first_child(component, "caption"))
        locator = ""
        for node in list(component):
            if isinstance(node.tag, str) and xml_local_name(node.tag) == "link":
                locator = (node.get("locator") or "").strip()
                if locator:
                    break
        asset = supplementary_assets.get(locator) or supplementary_assets.get(normalize_text(locator))
        if not asset or asset["path"] in used_paths:
            continue
        used_paths.add(asset["path"])
        entries.append(
            {
                "heading": label or Path(asset["path"]).name,
                "caption": caption,
                "link": path_relative_to(markdown_path.parent, asset["path"]),
                "path": str(asset["path"]),
                "section": "supplementary",
            }
        )

    for asset in assets:
        if asset.get("asset_type") != "supplementary" or not asset.get("path") or asset["path"] in used_paths:
            continue
        entries.append(
            {
                "heading": Path(asset["path"]).name,
                "caption": "",
                "link": path_relative_to(markdown_path.parent, asset["path"]),
                "path": str(asset["path"]),
                "section": "supplementary",
            }
        )
    return entries
