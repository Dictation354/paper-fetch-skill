"""Formula, table, and block normalization helpers."""

from __future__ import annotations

import copy
import re
from typing import Any

from ...extraction.html.formula_rules import (
    display_formula_nodes,
    formula_image_url_from_node,
    is_display_formula_node,
    looks_like_formula_image,
    mathml_element_from_html_node,
)
from ...extraction.html.inline import normalize_html_inline_text
from ...extraction.html.semantics import (
    ABSTRACT_ATTR_TOKENS as ABSTRACT_TOKENS,
    ANCILLARY_TOKENS,
    BACK_MATTER_TOKENS,
    node_identity_text,
    normalize_heading,
)
from ...extraction.html.shared import (
    append_text_block as _append_text_block,
    class_tokens as _class_tokens,
    short_text as _short_text,
    soup_root as _soup_root,
)
from ...extraction.html.tables import (
    escape_markdown_table_cell,
    expanded_table_matrix,
    flatten_table_header_rows,
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
from ...markdown.citations import is_citation_link, make_numeric_citation_sentinel, numeric_citation_payload
from ...utils import normalize_text
from .._article_markdown_math import render_external_mathml_expression
from .._science_pnas_profiles import publisher_profile as _publisher_profile
from .profile import (
    HEADING_TAG_PATTERN,
    _abstract_nodes,
    _ancestor_identity_text,
    _dedupe_top_level_nodes,
    _drop_promotional_blocks,
    _is_descendant,
)

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    NavigableString = None
    Tag = None

FIGURE_LABEL_PATTERN = re.compile(r"\bfig(?:ure)?\.?\s*(\d+[A-Za-z]?)\b", flags=re.IGNORECASE)


TABLE_LABEL_PATTERN = re.compile(r"\btable\.?\s*(\d+[A-Za-z]?)\b", flags=re.IGNORECASE)


EQUATION_NUMBER_PATTERN = re.compile(r"(\d+[A-Za-z]?)")


def _normalize_table_inline_text(value: str) -> str:
    return normalize_table_inline_text(value)


def _has_explicit_bibliography_marker(node: Tag) -> bool:
    attrs = getattr(node, "attrs", None) or {}
    if "citation-ref" in attrs:
        return True
    if normalize_text(str(attrs.get("data-test") or "")).lower() == "citation-ref":
        return True
    if normalize_text(str(attrs.get("role") or "")).lower() == "doc-biblioref":
        return True
    if normalize_text(str(attrs.get("data-xml-rid") or "")):
        return True
    class_tokens = _class_tokens(node)
    return bool({"biblink", "to-citation"} & class_tokens)


def _numeric_citation_payload_from_inline_node(node: Any) -> str | None:
    if not isinstance(node, Tag):
        return None
    text = normalize_text(node.get_text(" ", strip=True))
    payload = numeric_citation_payload(text)
    if payload is None:
        return None
    href = normalize_text(str(node.get("href") or ""))
    if node.name == "a" and (_has_explicit_bibliography_marker(node) or is_citation_link(href, text)):
        return payload
    if node.name in {"sup", "i", "em"}:
        anchors = [match for match in node.find_all("a") if isinstance(match, Tag)]
        if anchors and all(_numeric_citation_payload_from_inline_node(anchor) for anchor in anchors):
            return payload
    return None


def _wrap_table_text_fragment(text: str, marker: str | None) -> str:
    return wrap_table_text_fragment(text, marker)


def _render_table_inline_node(node: Any, *, text_style: str | None = None) -> str:
    return render_table_inline_node(node, text_style=text_style)


def _render_table_inline_text(node: Any) -> str:
    return render_table_inline_text(node)


def _normalize_non_table_inline_text(value: str) -> str:
    return normalize_html_inline_text(value, policy="body")


def _render_non_table_inline_fragment(node: Any, *, text_style: str | None = None) -> str:
    if NavigableString is not None and isinstance(node, NavigableString):
        return _wrap_table_text_fragment(str(node), text_style)
    if not isinstance(node, Tag):
        return ""

    name = normalize_text(node.name or "").lower()
    payload = _numeric_citation_payload_from_inline_node(node)
    if payload is not None:
        return make_numeric_citation_sentinel(payload) or ""
    if name == "img" and _looks_like_formula_image_node(node):
        return _formula_image_markdown(node)
    if name == "a":
        return _render_non_table_inline_node(node, text_style=text_style)
    if name in {"i", "em"}:
        return _render_non_table_inline_node(node, text_style="*")
    if name in {"b", "strong"}:
        return _render_non_table_inline_node(node, text_style="**")
    if name == "sub":
        text = _render_non_table_inline_node(node)
        return f"<sub>{text}</sub>" if text else ""
    if name == "sup":
        text = _render_non_table_inline_node(node)
        return f"<sup>{text}</sup>" if text else ""
    if name == "br":
        return "<br>"
    return _render_non_table_inline_node(node, text_style=text_style)


def _render_non_table_inline_node(node: Any, *, text_style: str | None = None) -> str:
    if node is None:
        return ""
    if NavigableString is not None and isinstance(node, NavigableString):
        return _wrap_table_text_fragment(str(node), text_style)
    if not isinstance(node, Tag):
        return ""

    parts: list[str] = []
    for child in node.children:
        rendered_child = _render_non_table_inline_fragment(child, text_style=text_style)
        if rendered_child:
            parts.append(rendered_child)

    return _normalize_non_table_inline_text("".join(parts))


def _render_non_table_inline_text(node: Any) -> str:
    return _render_non_table_inline_node(node)


def _join_non_table_text_fragments(fragments: list[str]) -> str:
    joined = ""
    for fragment in fragments:
        normalized_fragment = normalize_text(fragment)
        if not normalized_fragment:
            continue
        if (
            joined
            and not joined.endswith((" ", "\n", "<br>", "(", "[", "{", "/"))
            and not normalized_fragment.startswith((".", ",", ";", ":", ")", "]", "}", "%", "<br>"))
        ):
            joined += " "
        joined += normalized_fragment
    return _normalize_non_table_inline_text(joined)


def _render_caption_text(node: Tag) -> str:
    fragments: list[str] = []
    direct_tag_children = 0
    for child in node.children:
        if NavigableString is not None and isinstance(child, NavigableString):
            text = _wrap_table_text_fragment(str(child), None)
        elif isinstance(child, Tag):
            direct_tag_children += 1
            text = _render_non_table_inline_fragment(child)
        else:
            text = ""
        if text:
            fragments.append(text)
    if direct_tag_children > 1:
        return _join_non_table_text_fragments(fragments)
    return _render_non_table_inline_text(node)


def _is_non_table_paragraph_node(node: Tag) -> bool:
    name = normalize_text(node.name or "").lower()
    if name in {"p", "li"}:
        return True
    if name == "div" and normalize_text(str((getattr(node, "attrs", None) or {}).get("role") or "")).lower() == "paragraph":
        return True
    return False


def _normalize_non_table_inline_blocks(container: Tag) -> None:
    candidates = [
        node
        for node in container.find_all(["p", "li", "div"])
        if isinstance(node, Tag) and node.parent is not None and _is_non_table_paragraph_node(node)
    ]
    for node in _dedupe_top_level_nodes(candidates):
        if node.find_parent("table") is not None:
            continue
        rendered = _render_non_table_inline_text(node)
        if not rendered:
            continue
        node.clear()
        node.append(rendered)


def _normalize_abstract_blocks(container: Tag) -> None:
    soup = _soup_root(container)
    if soup is None:
        return
    for node in _abstract_nodes(container):
        if node.name not in {"section", "div"}:
            node.name = "section"
        heading = node.find(HEADING_TAG_PATTERN)
        if isinstance(heading, Tag):
            heading.name = "h2"
            if not normalize_heading(_short_text(heading)):
                heading.string = "Abstract"
            continue
        heading = soup.new_tag("h2")
        heading.string = "Abstract"
        node.insert(0, heading)


def _mathml_element_from_node(node: Tag | None):
    return mathml_element_from_html_node(node)


def _latex_from_math_node(node: Tag, *, display_mode: bool) -> str:
    element = _mathml_element_from_node(node)
    if element is not None:
        expression = normalize_text(render_external_mathml_expression(element, display_mode=display_mode))
        if expression:
            return expression
    return _short_text(node)


def _formula_image_url_from_node(node: Tag) -> str:
    return formula_image_url_from_node(node, include_adjacent=True)


def _looks_like_formula_image_node(node: Tag) -> bool:
    return looks_like_formula_image(node, _formula_image_url_from_node(node))


def _formula_image_markdown(node: Tag) -> str:
    url = _formula_image_url_from_node(node)
    return f"![Formula]({url})" if url else ""


def _display_formula_nodes(container: Tag) -> list[Tag]:
    return _dedupe_top_level_nodes(
        [node for node in display_formula_nodes(container) if isinstance(node, Tag)]
    )


def _equation_label(node: Tag) -> str:
    candidates: list[str] = []
    for candidate in (
        node.select_one(".label"),
        node.find_previous_sibling(class_="label"),
    ):
        if isinstance(candidate, Tag):
            candidates.append(_short_text(candidate))
    node_id = normalize_text(str((getattr(node, "attrs", None) or {}).get("id") or ""))
    if node_id:
        id_match = re.search(r"(?:^|[-_])(?:disp|eq|equation)[-_]?0*([0-9]+[A-Za-z]?)$", node_id, flags=re.IGNORECASE)
        if id_match:
            return f"Equation {id_match.group(1)}."
        candidates.append(node_id)
    for text in candidates:
        match = EQUATION_NUMBER_PATTERN.search(text)
        if match:
            return f"Equation {match.group(1)}."
    return ""


def _display_formula_replacement(node: Tag, soup: BeautifulSoup) -> Tag | None:
    latex = _latex_from_math_node(node, display_mode=True)
    replacement = soup.new_tag("div")
    label = _equation_label(node)
    if label:
        _append_text_block(replacement, f"**{label}**", soup=soup)
    if latex:
        for line in ("$$", latex, "$$"):
            _append_text_block(replacement, line, soup=soup)
        return replacement
    image_markdown = _formula_image_markdown(node)
    if image_markdown:
        _append_text_block(replacement, image_markdown, soup=soup)
        return replacement
    _append_text_block(replacement, "[Formula unavailable]", soup=soup)
    return replacement


def _direct_child_with_parent(node: Tag, parent: Tag) -> Tag | None:
    current: Tag | None = node
    while isinstance(current, Tag) and current.parent is not None:
        if current.parent is parent:
            return current
        current = current.parent if isinstance(current.parent, Tag) else None
    return None


def _clone_shallow_tag(node: Tag, soup: BeautifulSoup) -> Tag:
    clone = soup.new_tag(node.name)
    clone.attrs = copy.deepcopy(getattr(node, "attrs", None) or {})
    return clone


def _insert_split_paragraph(parent: Tag, children: list[Any], soup: BeautifulSoup) -> None:
    segment = _clone_shallow_tag(parent, soup)
    for child in children:
        if (NavigableString is not None and isinstance(child, NavigableString)) or isinstance(child, Tag):
            segment.append(child.extract())
    if normalize_text(segment.get_text(" ", strip=True)):
        parent.insert_before(segment)
        return
    segment.decompose()


def _split_paragraph_display_formula_blocks(parent: Tag, soup: BeautifulSoup) -> bool:
    formula_nodes: dict[int, Tag] = {}
    for formula_node in _display_formula_nodes(parent):
        direct_child = _direct_child_with_parent(formula_node, parent)
        if isinstance(direct_child, Tag):
            formula_nodes[id(direct_child)] = formula_node
    if not formula_nodes:
        return False

    pending_children: list[Any] = []
    for child in list(parent.contents):
        formula_node = formula_nodes.get(id(child))
        if formula_node is None:
            pending_children.append(child)
            continue
        replacement = _display_formula_replacement(formula_node, soup)
        if pending_children:
            _insert_split_paragraph(parent, pending_children, soup)
            pending_children = []
        if replacement is not None:
            parent.insert_before(replacement)
    if pending_children:
        _insert_split_paragraph(parent, pending_children, soup)
    parent.decompose()
    return True


def _normalize_display_formula_blocks(container: Tag) -> None:
    soup = _soup_root(container)
    if soup is None:
        return
    handled_parents: set[int] = set()
    nodes = _display_formula_nodes(container)
    for node in nodes:
        if not isinstance(node, Tag) or not isinstance(node.parent, Tag):
            continue
        parent = node.parent
        if not _is_non_table_paragraph_node(parent) or id(parent) in handled_parents:
            continue
        if _split_paragraph_display_formula_blocks(parent, soup):
            handled_parents.add(id(parent))

    for node in nodes:
        if not isinstance(node, Tag) or node.parent is None:
            continue
        replacement = _display_formula_replacement(node, soup)
        if replacement is None:
            continue
        node.replace_with(replacement)


def _is_display_formula_math(node: Tag) -> bool:
    return is_display_formula_node(node)


def _inline_math_replacement_target(node: Tag) -> Tag:
    for current in (
        node.find_parent("mjx-container"),
        node.find_parent("mjx-assistive-mml"),
    ):
        if isinstance(current, Tag):
            return current
    return node


def _normalize_inline_math_nodes(container: Tag) -> None:
    for math_node in list(container.find_all("math")):
        if not isinstance(math_node, Tag) or math_node.parent is None:
            continue
        if _is_display_formula_math(math_node):
            continue
        latex = _latex_from_math_node(math_node, display_mode=False)
        if not latex:
            continue
        _inline_math_replacement_target(math_node).replace_with(f"${latex}$")


def _normalize_inline_formula_image_nodes(container: Tag) -> None:
    for image in list(container.find_all("img")):
        if not isinstance(image, Tag) or image.parent is None:
            continue
        if not _looks_like_formula_image_node(image):
            continue
        image.replace_with(_formula_image_markdown(image))


def _caption_label(node: Tag, *, kind: str) -> str:
    label_pattern = FIGURE_LABEL_PATTERN if kind == "Figure" else TABLE_LABEL_PATTERN
    for candidate in (
        node.select_one("header .label"),
        node.select_one(".label"),
    ):
        if isinstance(candidate, Tag):
            text = _short_text(candidate)
            match = label_pattern.search(text)
            if match:
                return f"{kind} {match.group(1)}."
    match = label_pattern.search(_short_text(node))
    if match:
        return f"{kind} {match.group(1)}."
    return kind


def _caption_text(node: Tag) -> str:
    for selector in (".figure__caption-text", "figcaption", ".figure__caption", "[role='doc-caption']", ".caption"):
        candidate = node.select_one(selector)
        if isinstance(candidate, Tag):
            text = _render_caption_text(candidate)
            if text:
                return text
    return ""


def _strip_caption_label(text: str, label: str) -> str:
    label_text = normalize_text(label).rstrip(".")
    if not label_text:
        return text
    variants = [label_text]
    if label_text.lower().startswith("figure "):
        variants.append(f"Fig. {label_text.split(' ', 1)[1]}")
    for variant in variants:
        text = re.sub(rf"^{re.escape(variant)}\.?\s*", "", text, flags=re.IGNORECASE)
    return normalize_text(text).lstrip(".:;,-) ]")


def _table_caption_text(node: Tag, label: str) -> str:
    for selector in (".article-table-caption", ".caption", "figcaption", "caption", "header"):
        candidate = node.select_one(selector)
        if isinstance(candidate, Tag):
            text = _strip_caption_label(_render_caption_text(candidate), label)
            if text:
                return text
    return ""


def _is_glossary_table(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        if "list-paired" in node_identity_text(current):
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False


def _table_like_nodes(container: Tag) -> list[Tag]:
    nodes: list[Tag] = []
    for table in container.find_all("table"):
        if not isinstance(table, Tag):
            continue
        if _is_glossary_table(table):
            continue
        identity = _ancestor_identity_text(table)
        if any(token in identity for token in BACK_MATTER_TOKENS + ANCILLARY_TOKENS):
            continue
        best: Tag = table
        current = table.parent if isinstance(table.parent, Tag) else None
        depth = 0
        while isinstance(current, Tag) and current is not container and depth < 8:
            current_identity = node_identity_text(current)
            if (
                current.name == "figure"
                or "figure-wrap" in current_identity
                or "table-wrap" in current_identity
                or "article-table" in current_identity
                or current_identity.startswith("table ")
                or " table " in f" {current_identity} "
            ):
                best = current
            current = current.parent if isinstance(current.parent, Tag) else None
            depth += 1
        nodes.append(best)
    return _dedupe_top_level_nodes(nodes)


def _first_abstract_node(container: Tag) -> Tag | None:
    nodes = _abstract_nodes(container)
    return nodes[0] if nodes else None


def _is_front_matter_teaser_figure(node: Tag, *, publisher: str, abstract_anchor: Tag | None = None) -> bool:
    if publisher != "science":
        return False
    if _caption_label(node, kind="Figure") != "Figure":
        return False
    if any(token in _ancestor_identity_text(node) for token in ABSTRACT_TOKENS):
        return True
    if abstract_anchor is None:
        return False
    return abstract_anchor in node.find_all_next()


def _drop_front_matter_teaser_figures(container: Tag, publisher: str) -> None:
    abstract_anchor = _first_abstract_node(container)
    if abstract_anchor is None:
        return
    for node in list(container.find_all("figure")):
        if isinstance(node, Tag) and _is_front_matter_teaser_figure(node, publisher=publisher, abstract_anchor=abstract_anchor):
            node.decompose()


def _drop_table_blocks(container: Tag) -> None:
    for node in list(_table_like_nodes(container)):
        if isinstance(node, Tag):
            node.decompose()


def _figure_like_nodes(container: Tag) -> list[Tag]:
    table_nodes = _table_like_nodes(container)
    abstract_anchor = _first_abstract_node(container)
    nodes: list[Tag] = []
    for selector in (".figure-wrap", "figure"):
        try:
            matches = container.select(selector)
        except Exception:
            continue
        for match in matches:
            if not isinstance(match, Tag):
                continue
            if any(
                match is table_node or _is_descendant(match, table_node) or _is_descendant(table_node, match)
                for table_node in table_nodes
            ):
                continue
            if _is_front_matter_teaser_figure(match, publisher="science", abstract_anchor=abstract_anchor):
                continue
            if any(token in _ancestor_identity_text(match) for token in BACK_MATTER_TOKENS + ANCILLARY_TOKENS):
                continue
            if match.find("table") is not None:
                continue
            if isinstance(match, Tag):
                nodes.append(match)
    return _dedupe_top_level_nodes(nodes)


def _table_cell_data(cell: Tag) -> dict[str, Any]:
    return table_cell_data(cell, render_inline_text=_render_table_inline_text)


def _table_rows(table: Tag) -> list[list[dict[str, Any]]]:
    return table_rows(table, render_inline_text=_render_table_inline_text)


def _table_header_row_count(table: Tag, rows: list[list[dict[str, Any]]]) -> int:
    return table_header_row_count(table, rows)


def _expanded_table_matrix(rows: list[list[dict[str, Any]]]) -> list[list[dict[str, Any]]] | None:
    return expanded_table_matrix(rows)


def _flatten_table_header_rows(rows: list[list[dict[str, Any]]]) -> list[str]:
    return flatten_table_header_rows(rows)


def _table_headers_and_data(table: Tag) -> tuple[list[str], list[list[dict[str, Any]]], bool]:
    return table_headers_and_data(table, render_inline_text=_render_table_inline_text)


def _escape_markdown_table_cell(text: str) -> str:
    return escape_markdown_table_cell(text)


def _render_aligned_markdown_table(matrix: list[list[str]]) -> list[str]:
    return render_aligned_markdown_table(matrix)


def _render_table_markdown(table_node: Tag, *, label: str, caption: str) -> str:
    return render_table_markdown(
        table_node,
        label=label,
        caption=caption,
        render_inline_text=_render_table_inline_text,
    )


def _table_placeholder(index: int) -> str:
    return table_placeholder(index)


def _normalize_table_blocks(container: Tag) -> list[dict[str, str]]:
    soup = _soup_root(container)
    if soup is None:
        return []

    entries: list[dict[str, str]] = []
    for node in _table_like_nodes(container):
        if not isinstance(node, Tag) or node.parent is None:
            continue
        label = _caption_label(node, kind="Table")
        caption = _table_caption_text(node, label)
        rendered_markdown = _render_table_markdown(node, label=label, caption=caption)
        if not rendered_markdown:
            continue
        placeholder = _table_placeholder(len(entries) + 1)
        block = soup.new_tag("p")
        block.string = placeholder
        node.replace_with(block)
        entries.append({"placeholder": placeholder, "markdown": rendered_markdown})
    return entries


def _normalize_figure_blocks(container: Tag) -> None:
    soup = _soup_root(container)
    if soup is None:
        return
    for node in _figure_like_nodes(container):
        if not isinstance(node, Tag) or node.parent is None:
            continue
        label = _caption_label(node, kind="Figure")
        caption = _strip_caption_label(_caption_text(node), label)
        if not caption and label == "Figure":
            continue
        block = soup.new_tag("p")
        block.string = f"**{label}** {caption}".strip()
        node.replace_with(block)


def _normalize_special_blocks(container: Tag, publisher: str) -> list[dict[str, str]]:
    _drop_promotional_blocks(container, publisher)
    _normalize_abstract_blocks(container)
    _drop_front_matter_teaser_figures(container, publisher)
    _normalize_display_formula_blocks(container)
    _normalize_inline_math_nodes(container)
    _normalize_inline_formula_image_nodes(container)
    table_entries = _normalize_table_blocks(container)
    _normalize_figure_blocks(container)
    _normalize_non_table_inline_blocks(container)
    profile = _publisher_profile(publisher)
    if profile.dom_postprocess is not None:
        profile.dom_postprocess(container)
    return table_entries


__all__ = [
    "FIGURE_LABEL_PATTERN",
    "TABLE_LABEL_PATTERN",
    "EQUATION_NUMBER_PATTERN",
    "_normalize_table_inline_text",
    "_has_explicit_bibliography_marker",
    "_numeric_citation_payload_from_inline_node",
    "_wrap_table_text_fragment",
    "_render_table_inline_node",
    "_render_table_inline_text",
    "_normalize_non_table_inline_text",
    "_render_non_table_inline_fragment",
    "_render_non_table_inline_node",
    "_render_non_table_inline_text",
    "_join_non_table_text_fragments",
    "_render_caption_text",
    "_is_non_table_paragraph_node",
    "_normalize_non_table_inline_blocks",
    "_normalize_abstract_blocks",
    "_mathml_element_from_node",
    "_latex_from_math_node",
    "_formula_image_url_from_node",
    "_looks_like_formula_image_node",
    "_formula_image_markdown",
    "_display_formula_nodes",
    "_equation_label",
    "_display_formula_replacement",
    "_direct_child_with_parent",
    "_clone_shallow_tag",
    "_insert_split_paragraph",
    "_split_paragraph_display_formula_blocks",
    "_normalize_display_formula_blocks",
    "_is_display_formula_math",
    "_inline_math_replacement_target",
    "_normalize_inline_math_nodes",
    "_normalize_inline_formula_image_nodes",
    "_caption_label",
    "_caption_text",
    "_strip_caption_label",
    "_table_caption_text",
    "_is_glossary_table",
    "_table_like_nodes",
    "_first_abstract_node",
    "_is_front_matter_teaser_figure",
    "_drop_front_matter_teaser_figures",
    "_drop_table_blocks",
    "_figure_like_nodes",
    "_table_cell_data",
    "_table_rows",
    "_table_header_row_count",
    "_expanded_table_matrix",
    "_flatten_table_header_rows",
    "_table_headers_and_data",
    "_escape_markdown_table_cell",
    "_render_aligned_markdown_table",
    "_render_table_markdown",
    "_table_placeholder",
    "_normalize_table_blocks",
    "_normalize_figure_blocks",
    "_normalize_special_blocks",
]
