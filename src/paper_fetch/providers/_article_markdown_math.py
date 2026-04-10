"""MathML and formula rendering helpers for article Markdown."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..formula.convert import convert_mathml_element_to_latex
from ._article_markdown_common import (
    child_text,
    first_descendant,
    normalize_compact_text,
    render_inline_text,
    xml_local_name,
)


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
            for index, child_text_value in enumerate(rendered_children):
                if index:
                    separator = separators[min(index - 1, len(separators) - 1)]
                    joined += f"{separator} "
                joined += child_text_value
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
