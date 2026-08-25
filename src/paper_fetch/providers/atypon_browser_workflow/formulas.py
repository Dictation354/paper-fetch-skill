"""Formula normalization helpers for Atypon browser workflow Markdown."""

from __future__ import annotations

import copy
import re
from typing import Any

from ...extraction.html.formula_rules import (
    display_formula_nodes,
    formula_image_url_from_node,
    is_display_formula_node,
    is_tex_formula_script_node,
    looks_like_formula_image,
    mathml_element_from_html_node,
)
from ...extraction.markdown_render.formulas import (
    html_formula_latex_from_node,
    render_inline_latex_markdown,
)
from ...extraction.html.shared import (
    append_text_block as _append_text_block,
    short_text as _short_text,
    soup_root as _soup_root,
)
from ...markdown.images import render_markdown_image
from ...utils import normalize_text
from .._article_markdown_math import render_external_mathml_expression
from .profile import _dedupe_top_level_nodes

from bs4 import BeautifulSoup, NavigableString, Tag

EQUATION_NUMBER_PATTERN = re.compile(r"(\d+[A-Za-z]?)")
EQUATION_LABEL_ONLY_PATTERN = re.compile(
    r"^(?:equation\s*)?\(?\s*\d+[A-Za-z]?\s*\)?[.:]?$",
    flags=re.IGNORECASE,
)


def _is_non_table_paragraph_node(node: Tag) -> bool:
    name = normalize_text(node.name or "").lower()
    if name in {"p", "li"}:
        return True
    if (
        name == "div"
        and normalize_text(
            str((getattr(node, "attrs", None) or {}).get("role") or "")
        ).lower()
        == "paragraph"
    ):
        return True
    return False


def _mathml_element_from_node(node: Tag | None):
    return mathml_element_from_html_node(node)


def _structured_latex_from_math_node(node: Tag, *, display_mode: bool) -> str:
    element = _mathml_element_from_node(node)
    if element is not None:
        expression = normalize_text(
            render_external_mathml_expression(element, display_mode=display_mode)
        )
        if expression:
            return expression
    expression = normalize_text(html_formula_latex_from_node(node))
    if expression:
        return expression
    return ""


def _latex_from_math_node(node: Tag, *, display_mode: bool) -> str:
    expression = _structured_latex_from_math_node(node, display_mode=display_mode)
    if expression:
        return expression
    return _short_text(node)


def _formula_image_url_from_node(node: Tag) -> str:
    return formula_image_url_from_node(node, include_adjacent=True)


def _looks_like_formula_image_node(node: Tag) -> bool:
    return looks_like_formula_image(node, _formula_image_url_from_node(node))


def _formula_image_markdown(node: Tag) -> str:
    url = _formula_image_url_from_node(node)
    return render_markdown_image("formula", "", url)


def _display_formula_text_fallback(node: Tag) -> str:
    text = _short_text(node)
    if not text or EQUATION_LABEL_ONLY_PATTERN.fullmatch(text):
        return ""
    return text


def _display_formula_nodes(container: Tag) -> list[Tag]:
    return _dedupe_top_level_nodes(
        [node for node in display_formula_nodes(container) if isinstance(node, Tag)]
    )


def _equation_label(node: Tag) -> str:
    attrs = getattr(node, "attrs", None) or {}
    explicit_label = normalize_text(str(attrs.get("data-equation-label") or ""))
    if explicit_label:
        return explicit_label
    if normalize_text(str(attrs.get("data-no-equation-label") or "")).lower() in {
        "1",
        "true",
        "yes",
    }:
        return ""

    candidates: list[str] = []
    for candidate in (
        node.select_one(".label"),
        node.find_previous_sibling(class_="label"),
    ):
        if isinstance(candidate, Tag):
            candidates.append(_short_text(candidate))
    node_id = normalize_text(str(attrs.get("id") or ""))
    if node_id:
        id_match = re.search(
            r"(?:disp|eqn?|equation)[-_]?0*([0-9]+[A-Za-z]?)$",
            node_id,
            flags=re.IGNORECASE,
        )
        if id_match:
            return f"Equation {id_match.group(1)}."
        candidates.append(node_id)
    for text in candidates:
        match = EQUATION_NUMBER_PATTERN.search(text)
        if match:
            return f"Equation {match.group(1)}."
    return ""


def _display_formula_replacement(node: Tag, soup: BeautifulSoup) -> Tag | None:
    latex = _structured_latex_from_math_node(node, display_mode=True)
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
    text_fallback = _display_formula_text_fallback(node)
    if text_fallback:
        for line in ("$$", text_fallback, "$$"):
            _append_text_block(replacement, line, soup=soup)
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


def _insert_split_paragraph(
    parent: Tag, children: list[Any], soup: BeautifulSoup
) -> None:
    segment = _clone_shallow_tag(parent, soup)
    for child in children:
        if (
            NavigableString is not None and isinstance(child, NavigableString)
        ) or isinstance(child, Tag):
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
        matched_formula_node = formula_nodes.get(id(child))
        if matched_formula_node is None:
            pending_children.append(child)
            continue
        replacement = _display_formula_replacement(matched_formula_node, soup)
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


def _has_class_token(node: Tag, token: str) -> bool:
    raw_classes = (getattr(node, "attrs", None) or {}).get("class") or []
    if isinstance(raw_classes, str):
        class_values = raw_classes.split()
    else:
        class_values = [str(value) for value in raw_classes]
    return token in {normalize_text(value).lower() for value in class_values}


def _inline_latex_markdown(value: str) -> str:
    return render_inline_latex_markdown(value)


def _latex_from_tex_script_container(node: Tag) -> str:
    for script in node.find_all("script"):
        if not isinstance(script, Tag) or not is_tex_formula_script_node(script):
            continue
        latex = normalize_text(html_formula_latex_from_node(script))
        if latex:
            return latex
    return ""


def _normalize_iop_inline_tex_formula_nodes(container: Tag) -> None:
    nodes = _dedupe_top_level_nodes(
        [node for node in container.select(".inline-eqn") if isinstance(node, Tag)]
    )
    for node in nodes:
        if not isinstance(node, Tag) or node.parent is None:
            continue
        if _is_display_formula_math(node) or _has_class_token(node, "display-eqn"):
            continue
        markdown = _inline_latex_markdown(_latex_from_tex_script_container(node))
        if markdown:
            node.replace_with(markdown)


def _normalize_inline_formula_image_nodes(container: Tag) -> None:
    for image in list(container.find_all("img")):
        if not isinstance(image, Tag) or image.parent is None:
            continue
        if not _looks_like_formula_image_node(image):
            continue
        latex = _latex_from_nearest_formula_container(image)
        if latex:
            image.replace_with(_inline_latex_markdown(latex))
            continue
        image.replace_with(_formula_image_markdown(image))


def _latex_from_nearest_formula_container(node: Tag) -> str:
    current: Tag | None = node
    depth = 0
    while isinstance(current, Tag) and depth < 6:
        latex = normalize_text(html_formula_latex_from_node(current))
        if latex:
            return latex
        current = current.parent if isinstance(current.parent, Tag) else None
        depth += 1
    return ""
