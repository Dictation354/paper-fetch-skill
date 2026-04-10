"""Generate clean Markdown from XML full text plus downloaded assets."""

from __future__ import annotations

import copy
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from elsevier_xml_rules import (
    ELSEVIER_IMAGE_ASSET_TYPES,
    get_elsevier_element_rule,
    infer_elsevier_asset_group_key,
    should_ignore_elsevier_section_title,
)
from fetch_common import first_non_empty, sanitize_filename
from formula_conversion import convert_mathml_element_to_latex
from publisher_identity import normalize_doi

XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
XLINK_TITLE = "{http://www.w3.org/1999/xlink}title"
ELSEVIER_BLOCK_LOCAL_NAMES = {"display", "figure", "table", "e-component", "formula"}


@dataclass
class ArticleStructure:
    title: str
    doi: str
    journal_title: str
    published: str
    landing_page: str
    xml_path: Path
    abstract_lines: list[str]
    body_lines: list[str]
    figure_entries: list[dict[str, Any]]
    table_entries: list[dict[str, Any]]
    supplement_entries: list[dict[str, str]]
    conversion_notes: list[str]
    used_figure_keys: set[str]
    used_table_keys: set[str]


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


def render_tex_math(element: ET.Element | None) -> str:
    raw = normalize_compact_text("".join(element.itertext()) if element is not None else "")
    if raw.startswith(r"\(") and raw.endswith(r"\)"):
        return raw[2:-2].strip()
    if raw.startswith(r"\[") and raw.endswith(r"\]"):
        return raw[2:-2].strip()
    return raw


def render_external_mathml_expression(element: ET.Element | None, *, display_mode: bool) -> str:
    if element is None:
        return ""
    result = convert_mathml_element_to_latex(element, display_mode=display_mode)
    if result.status == "ok" and result.latex:
        return result.latex
    return render_mathml_expression(element)


def render_mathml_expression(element: ET.Element | None) -> str:
    if element is None:
        return ""

    def render_node(node: ET.Element | None) -> str:
        if node is None or not isinstance(node.tag, str):
            return ""

        local_name = xml_local_name(node.tag)
        children = [child for child in list(node) if isinstance(child.tag, str)]

        if local_name in {"math", "mrow", "mstyle", "mpadded", "mphantom"}:
            return "".join(render_node(child) for child in children)
        if local_name == "semantics":
            for child in children:
                child_name = xml_local_name(child.tag)
                if child_name not in {"annotation", "annotation-xml"}:
                    return render_node(child)
            return ""
        if local_name in {"annotation", "annotation-xml"}:
            return ""
        if local_name in {"mi", "mn", "mtext"}:
            return normalize_compact_text("".join(node.itertext()))
        if local_name == "mo":
            operator = normalize_compact_text("".join(node.itertext()))
            compact = {
                "(": "(",
                ")": ")",
                "[": "[",
                "]": "]",
                "{": "{",
                "}": "}",
                ",": ", ",
                ":": ": ",
                ";": "; ",
            }
            spaced = {
                "=": " = ",
                "+": " + ",
                "-": " - ",
                "−": " - ",
                "±": " ± ",
                "×": r" \times ",
                "*": r" \times ",
                "·": r" \cdot ",
                "/": " / ",
                "<": " < ",
                ">": " > ",
                "≤": r" \leq ",
                "≥": r" \geq ",
                "∈": r" \in ",
            }
            if operator in compact:
                return compact[operator]
            return spaced.get(operator, operator)
        if local_name == "msub":
            if len(children) >= 2:
                return f"{render_script_base(children[0])}_{{{render_node(children[1])}}}"
        if local_name == "msup":
            if len(children) >= 2:
                return f"{render_script_base(children[0])}^{{{render_node(children[1])}}}"
        if local_name == "msubsup":
            if len(children) >= 3:
                return f"{render_script_base(children[0])}_{{{render_node(children[1])}}}^{{{render_node(children[2])}}}"
        if local_name == "mfrac":
            if len(children) >= 2:
                return rf"\frac{{{render_node(children[0])}}}{{{render_node(children[1])}}}"
        if local_name == "msqrt":
            return rf"\sqrt{{{''.join(render_node(child) for child in children)}}}"
        if local_name == "mroot":
            if len(children) >= 2:
                return rf"\sqrt[{render_node(children[1])}]{{{render_node(children[0])}}}"
        if local_name == "mfenced":
            open_char = node.get("open", "(")
            close_char = node.get("close", ")")
            separators = list((node.get("separators") or ",").strip() or ",")
            rendered_children = [render_node(child) for child in children]
            joined = ""
            for index, child_text in enumerate(rendered_children):
                if index:
                    separator = separators[min(index - 1, len(separators) - 1)]
                    joined += f"{separator} "
                joined += child_text
            return f"{open_char}{joined}{close_char}"
        if local_name == "mover":
            if len(children) >= 2:
                return rf"\overset{{{render_node(children[1])}}}{{{render_node(children[0])}}}"
        if local_name == "munder":
            if len(children) >= 2:
                return rf"\underset{{{render_node(children[1])}}}{{{render_node(children[0])}}}"
        if local_name == "munderover":
            if len(children) >= 3:
                return rf"\overset{{{render_node(children[2])}}}{{\underset{{{render_node(children[1])}}}{{{render_node(children[0])}}}}}"
        if local_name == "mtable":
            rows = []
            for row in children:
                if xml_local_name(row.tag) != "mtr":
                    continue
                cells = [render_node(cell) for cell in list(row) if isinstance(cell.tag, str)]
                rows.append(" , ".join(cells))
            return r"\begin{matrix} " + r" \\ ".join(rows) + r" \end{matrix}" if rows else ""
        if local_name == "mtr":
            return " , ".join(render_node(child) for child in children)
        if local_name == "mtd":
            return "".join(render_node(child) for child in children)

        return normalize_compact_text("".join(node.itertext()))

    def render_script_base(node: ET.Element | None) -> str:
        expression = render_node(node)
        if not expression or node is None or not isinstance(node.tag, str):
            return expression

        if xml_local_name(node.tag) in {"mi", "mn", "mo", "mtext"}:
            return expression
        return f"{{{expression}}}"

    expression = render_node(element)
    expression = re.sub(r"\s+", " ", expression).strip()
    expression = re.sub(r"\(\s+", "(", expression)
    expression = re.sub(r"\s+\)", ")", expression)
    expression = re.sub(r"\[\s+", "[", expression)
    expression = re.sub(r"\s+\]", "]", expression)
    expression = re.sub(r"\{\s+", "{", expression)
    expression = re.sub(r"\s+\}", "}", expression)
    return expression


def render_inline_formula(element: ET.Element | None) -> str:
    if element is None:
        return ""
    math_node = first_descendant(element, "math")
    if math_node is not None:
        return render_external_mathml_expression(math_node, display_mode=False)
    tex_node = first_descendant(element, "tex-math")
    if tex_node is not None:
        return render_tex_math(tex_node)
    return normalize_compact_text("".join(element.itertext()))


def render_display_formula(element: ET.Element | None) -> list[str]:
    if element is None:
        return []

    label = child_text(element, "label")
    if not label:
        label = render_inline_text(first_descendant(element, "label"))
    math_node = first_descendant(element, "math")
    tex_node = first_descendant(element, "tex-math")
    if math_node is not None:
        expression = render_external_mathml_expression(math_node, display_mode=True)
    elif tex_node is not None:
        expression = render_tex_math(tex_node)
    else:
        expression = normalize_compact_text(render_inline_text(element, skip_local_names={"label"}))

    if not expression:
        return []

    lines: list[str] = []
    if label:
        lines.extend([label, ""])
    lines.extend(["$$", expression, "$$", ""])
    return lines


def normalize_table_cell_text(value: str) -> str:
    text = normalize_text(value)
    text = text.replace("\n", "<br>")
    return text.replace("|", r"\|")


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


def build_springer_asset_lookup(
    assets: list[dict[str, Any]],
    *,
    asset_type: str,
) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for asset in assets:
        if asset.get("asset_type") != asset_type or not asset.get("path"):
            continue
        source_href = (asset.get("source_href") or "").strip()
        if source_href:
            lookup[source_href] = asset
            lookup[Path(source_href).name] = asset
    return lookup


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


def springer_table_registry(
    root: ET.Element,
    assets: list[dict[str, Any]],
    markdown_path: Path,
    doi: str,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], set[str]]:
    image_assets = build_springer_asset_lookup(assets, asset_type="image")

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
            }
        elif link:
            entry = {
                "key": table_key or link,
                "kind": "image",
                "heading": label,
                "caption": caption,
                "footnotes": footnotes,
                "link": link,
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
    image_assets = build_springer_asset_lookup(assets, asset_type="image")
    excluded_paths = excluded_asset_paths or set()

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
        link = resolve_springer_asset_link(markdown_path, asset, href, doi, asset_bucket="image")
        if (
            (asset and asset.get("path") and str(asset["path"]) in used_asset_paths)
            or (asset and asset.get("path") and str(asset["path"]) in excluded_paths)
            or not link
        ):
            continue
        if asset and asset.get("path"):
            used_asset_paths.add(str(asset["path"]))
        entry = {
            "key": normalize_text(fig.get("id")) or normalize_text(href) or link,
            "heading": label,
            "caption": caption,
            "link": link,
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
            }
        )
    return lookup, entries


def springer_supplement_entries(root: ET.Element, assets: list[dict[str, Any]], markdown_path: Path, doi: str) -> list[dict[str, str]]:
    supplementary_assets = build_springer_asset_lookup(assets, asset_type="supplementary")

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
            }
        )
    return entries


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
            }
        )
    return entries


def build_article_structure(
    *,
    provider: str,
    metadata: Mapping[str, Any],
    xml_body: bytes,
    xml_path: Path,
    assets: list[dict[str, Any]],
) -> ArticleStructure | None:
    try:
        root = ET.fromstring(xml_body)
    except ET.ParseError:
        return None

    title = normalize_text(str(metadata.get("title") or "")) or "Untitled Article"
    doi = normalize_text(str(metadata.get("doi") or ""))
    journal_title = normalize_text(str(metadata.get("journal_title") or ""))
    published = normalize_text(str(metadata.get("published") or ""))
    landing_page = normalize_text(str(metadata.get("landing_page_url") or ""))

    lines = [f"# {title}", ""]
    if doi:
        lines.append(f"- DOI: `{doi}`")
    lines.append(f"- Provider: `{provider}`")
    if journal_title:
        lines.append(f"- Journal: {journal_title}")
    if published:
        lines.append(f"- Published: {published}")
    lines.append(f"- XML: [{xml_path.name}]({path_relative_to(xml_path.parent, xml_path)})")
    if landing_page:
        lines.append(f"- Landing Page: {landing_page}")
    lines.append("")

    used_figure_keys: set[str] = set()
    used_table_keys: set[str] = set()
    if provider == "springer":
        article = first_descendant(root, "article")
        if article is None:
            article = root
        abstract_node = first_descendant(article, "abstract")
        body_node = first_descendant(article, "body")
        abstract_lines = render_jats_blocks(abstract_node, heading_level=3)
        table_lookup, table_entries, reserved_image_paths = springer_table_registry(
            article,
            assets,
            xml_path.with_suffix(".md"),
            doi,
        )
        figure_lookup, figure_entries = springer_figure_registry(
            article,
            assets,
            xml_path.with_suffix(".md"),
            doi,
            excluded_asset_paths=reserved_image_paths,
        )
        body_lines = render_jats_blocks(
            body_node,
            heading_level=3,
            figure_lookup=figure_lookup,
            table_lookup=table_lookup,
            used_figure_keys=used_figure_keys,
            used_table_keys=used_table_keys,
        )
        supplement_entries = springer_supplement_entries(article, assets, xml_path.with_suffix(".md"), doi)
    elif provider == "elsevier":
        abstract_node = first_descendant(root, "abstract")
        body_node = first_descendant(root, "body")
        abstract_lines = render_elsevier_blocks(abstract_node, heading_level=3)
        if not abstract_lines:
            fallback_abstract = normalize_text(str(metadata.get("abstract") or child_text(first_descendant(root, "coredata"), "description")))
            if fallback_abstract:
                abstract_lines = [fallback_abstract, ""]
        table_lookup, table_entries = elsevier_table_registry(root, assets, xml_path.with_suffix(".md"))
        figure_lookup, figure_entries = elsevier_figure_registry(root, assets, xml_path.with_suffix(".md"))
        body_lines = render_elsevier_blocks(
            body_node,
            heading_level=3,
            figure_lookup=figure_lookup,
            figure_entries=figure_entries,
            used_figure_keys=used_figure_keys,
            table_lookup=table_lookup,
            used_table_keys=used_table_keys,
        )
        supplement_entries = elsevier_supplement_entries(root, assets, xml_path.with_suffix(".md"))
    else:
        return None

    if abstract_lines:
        lines.extend(["## Abstract", ""])
        lines.extend(abstract_lines)

    if body_lines:
        lines.extend(["## Full Text", ""])
        lines.extend(body_lines)

    remaining_figure_entries = [
        entry
        for entry in figure_entries
        if entry["key"] not in used_figure_keys and (provider != "elsevier" or entry.get("section") == "body")
    ]
    if remaining_figure_entries:
        lines.extend(["## Additional Figures", ""])
        for entry in remaining_figure_entries:
            lines.extend([f"### {entry['heading']}", ""])
            lines.extend(render_figure_block(entry))

    remaining_table_entries = [entry for entry in table_entries if entry["key"] not in used_table_keys]
    if provider == "elsevier":
        remaining_table_entries = [entry for entry in remaining_table_entries if entry.get("section") == "body"]
    if remaining_table_entries:
        lines.extend(["## Additional Tables", ""])
        for entry in remaining_table_entries:
            lines.extend(render_table_block(entry))

    if supplement_entries:
        lines.extend(["## Supplementary Materials", ""])
        for entry in supplement_entries:
            bullet = f"- [{entry['heading']}]({entry['link']})"
            if entry["caption"]:
                bullet = f"{bullet}: {entry['caption']}"
            lines.append(bullet)
        lines.append("")

    conversion_notes = collect_conversion_notes(table_entries=table_entries)
    return ArticleStructure(
        title=title,
        doi=doi,
        journal_title=journal_title,
        published=published,
        landing_page=landing_page,
        xml_path=xml_path,
        abstract_lines=abstract_lines,
        body_lines=body_lines,
        figure_entries=figure_entries,
        table_entries=table_entries,
        supplement_entries=supplement_entries,
        conversion_notes=conversion_notes,
        used_figure_keys=used_figure_keys,
        used_table_keys=used_table_keys,
    )


def build_markdown_document(
    *,
    provider: str,
    metadata: Mapping[str, Any],
    xml_body: bytes,
    xml_path: Path,
    assets: list[dict[str, Any]],
) -> str | None:
    structure = build_article_structure(
        provider=provider,
        metadata=metadata,
        xml_body=xml_body,
        xml_path=xml_path,
        assets=assets,
    )
    if structure is None:
        return None

    lines = [f"# {structure.title}", ""]
    if structure.doi:
        lines.append(f"- DOI: `{structure.doi}`")
    lines.append(f"- Provider: `{provider}`")
    if structure.journal_title:
        lines.append(f"- Journal: {structure.journal_title}")
    if structure.published:
        lines.append(f"- Published: {structure.published}")
    lines.append(f"- XML: [{structure.xml_path.name}]({path_relative_to(structure.xml_path.parent, structure.xml_path)})")
    if structure.landing_page:
        lines.append(f"- Landing Page: {structure.landing_page}")
    lines.append("")

    if structure.abstract_lines:
        lines.extend(["## Abstract", ""])
        lines.extend(structure.abstract_lines)

    if structure.body_lines:
        lines.extend(["## Full Text", ""])
        lines.extend(structure.body_lines)

    remaining_figure_entries = [
        entry
        for entry in structure.figure_entries
        if entry["key"] not in structure.used_figure_keys and (provider != "elsevier" or entry.get("section") == "body")
    ]
    if remaining_figure_entries:
        lines.extend(["## Additional Figures", ""])
        for entry in remaining_figure_entries:
            lines.extend([f"### {entry['heading']}", ""])
            lines.extend(render_figure_block(entry))

    remaining_table_entries = [entry for entry in structure.table_entries if str(entry["key"]) not in structure.used_table_keys]
    if provider == "elsevier":
        remaining_table_entries = [entry for entry in remaining_table_entries if entry.get("section") == "body"]
    if remaining_table_entries:
        lines.extend(["## Additional Tables", ""])
        for entry in remaining_table_entries:
            lines.extend(render_table_block(entry))

    if structure.supplement_entries:
        lines.extend(["## Supplementary Materials", ""])
        for entry in structure.supplement_entries:
            bullet = f"- [{entry['heading']}]({entry['link']})"
            if entry["caption"]:
                bullet = f"{bullet}: {entry['caption']}"
            lines.append(bullet)
        lines.append("")

    if structure.conversion_notes:
        lines.extend(["## Conversion Notes", ""])
        lines.extend(structure.conversion_notes)
        lines.append("")

    return normalize_lines(lines)


def write_article_markdown(
    *,
    provider: str,
    metadata: Mapping[str, Any],
    xml_body: bytes,
    output_dir: Path | None,
    xml_path: str | None,
    assets: list[dict[str, Any]] | None = None,
) -> str | None:
    if output_dir is None or not xml_path:
        return None

    xml_output_path = Path(xml_path)
    markdown_path = make_markdown_path(output_dir, str(metadata.get("doi") or ""), metadata.get("title"))
    document = build_markdown_document(
        provider=provider,
        metadata=metadata,
        xml_body=xml_body,
        xml_path=xml_output_path,
        assets=list(assets or []),
    )
    if document is None:
        return None
    markdown_path.write_text(document, encoding="utf-8")
    return str(markdown_path)
