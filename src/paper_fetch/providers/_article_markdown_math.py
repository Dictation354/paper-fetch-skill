"""MathML and formula rendering helpers for article Markdown."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import re
import urllib.parse
import xml.etree.ElementTree as ET

from ..markdown.images import render_markdown_image
from ..formula.convert import convert_mathml_element_to_latex, normalize_latex_macros
from ._article_markdown_xml import (
    child_text,
    first_descendant,
    normalize_compact_text,
    render_literal_inline_text,
    xml_local_name,
)

XLINK_HREF = "{http://www.w3.org/1999/xlink}href"

_MATHML_IDENTIFIER_LATEX = {
    "α": r"\alpha",
    "β": r"\beta",
    "γ": r"\gamma",
    "δ": r"\delta",
    "ϵ": r"\epsilon",
    "ε": r"\varepsilon",
    "ζ": r"\zeta",
    "η": r"\eta",
    "θ": r"\theta",
    "ϑ": r"\vartheta",
    "ι": r"\iota",
    "κ": r"\kappa",
    "λ": r"\lambda",
    "μ": r"\mu",
    "ν": r"\nu",
    "ξ": r"\xi",
    "π": r"\pi",
    "ρ": r"\rho",
    "σ": r"\sigma",
    "τ": r"\tau",
    "υ": r"\upsilon",
    "ϕ": r"\phi",
    "φ": r"\varphi",
    "χ": r"\chi",
    "ψ": r"\psi",
    "ω": r"\omega",
    "Γ": r"\Gamma",
    "Δ": r"\Delta",
    "Θ": r"\Theta",
    "Λ": r"\Lambda",
    "Ξ": r"\Xi",
    "Π": r"\Pi",
    "Σ": r"\Sigma",
    "Φ": r"\Phi",
    "Ψ": r"\Psi",
    "Ω": r"\Omega",
}


def _mathml_sequence_separator(
    previous_name: str,
    current_name: str,
    value: str,
) -> str:
    if current_name == "mtext" and previous_name in {"mi", "mn"}:
        return r"\,"
    if current_name == "mi" and previous_name == "mn":
        return r"\, "
    if current_name == "mo" and previous_name == "mn" and value in {"(", "[", "{"}:
        return r"\,"
    if (
        current_name in {"mfenced", "mrow"}
        and previous_name == "mn"
        and value.startswith(("(", "[", "{"))
    ):
        return r"\,"
    return ""


def _render_mathml_sequence(
    nodes: list[ET.Element],
    render_node: Callable[[ET.Element | None], str],
) -> str:
    rendered: list[str] = []
    previous_name = ""
    for child in nodes:
        value = render_node(child)
        current_name = xml_local_name(child.tag) if isinstance(child.tag, str) else ""
        if value and rendered:
            rendered.append(
                _mathml_sequence_separator(previous_name, current_name, value)
            )
        rendered.append(value)
        if value:
            previous_name = current_name
    return "".join(rendered)


def _render_large_operator_lower_bound(value: str) -> str:
    """Preserve conventional thin spacing for compound index conditions."""

    if any(operator in value for operator in (" = ", " < ", " > ", r" \leq ")):
        return rf"\, {value}"
    return value


@dataclass
class FormulaRenderResult:
    lines: list[str]
    fallback_kind: str | None = None
    note: str | None = None
    label: str | None = None
    image_url: str | None = None


def render_tex_math(element: ET.Element | None) -> str:
    raw = normalize_compact_text(
        "".join(element.itertext()) if element is not None else ""
    )
    if raw.startswith(r"\(") and raw.endswith(r"\)"):
        return raw[2:-2].strip()
    if raw.startswith(r"\[") and raw.endswith(r"\]"):
        return raw[2:-2].strip()
    return raw


def render_external_mathml_expression(
    element: ET.Element | None, *, display_mode: bool
) -> str:
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
            return _render_mathml_sequence(children, render_node)
        if local_name == "semantics":
            for child in children:
                child_name = xml_local_name(child.tag)
                if child_name not in {"annotation", "annotation-xml"}:
                    return render_node(child)
            return ""
        if local_name in {"annotation", "annotation-xml"}:
            return ""
        if local_name in {"mi", "mn"}:
            text = normalize_compact_text("".join(node.itertext()))
            if text in _MATHML_IDENTIFIER_LATEX:
                return _MATHML_IDENTIFIER_LATEX[text]
            return text
        if local_name == "mtext":
            text = normalize_compact_text("".join(node.itertext())).rstrip("\\")
            return rf"\text{{{text}}}" if text else ""
        if local_name == "mo":
            operator = normalize_compact_text("".join(node.itertext()))
            compact = {
                "(": "(",
                ")": ")",
                "[": "[",
                "]": "]",
                "{": "{",
                "}": "}",
                ",": ",",
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
                "≡": r" \equiv ",
                "≠": r" \neq ",
                "≈": r" \approx ",
                "∼": r" \sim ",
                "→": r" \to ",
            }
            large_operators = {
                "∑": r"\sum",
                "∏": r"\prod",
                "∫": r"\int",
                "∬": r"\iint",
                "∭": r"\iiint",
                "∞": r"\infty",
            }
            if operator in compact:
                return compact[operator]
            return large_operators.get(operator, spaced.get(operator, operator))
        if local_name == "msub":
            if len(children) >= 2:
                return (
                    f"{render_script_base(children[0])}_{{{render_node(children[1])}}}"
                )
        if local_name == "msup":
            if len(children) >= 2:
                return (
                    f"{render_script_base(children[0])}^{{{render_node(children[1])}}}"
                )
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
                return (
                    rf"\sqrt[{render_node(children[1])}]{{{render_node(children[0])}}}"
                )
        if local_name == "mspace":
            width = normalize_compact_text(str(node.get("width") or ""))
            return "" if width.startswith(("0", "-")) else r"\,"
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
                base = render_node(children[0])
                accent = normalize_compact_text("".join(children[1].itertext()))
                if accent in {"^", "ˆ", "̂"}:
                    return rf"\hat{{{base}}}"
                if accent in {"¯", "‾", "̄"}:
                    return rf"\bar{{{base}}}"
                if accent in {".", "˙", "̇"}:
                    return rf"\overset{{\cdot}}{{{base}}}"
                if base.startswith(("\\sum", "\\prod", "\\int")):
                    return rf"{base}\limits^{{{render_node(children[1])}}}"
                return rf"\overset{{{render_node(children[1])}}}{{{render_node(children[0])}}}"
        if local_name == "munder":
            if len(children) >= 2:
                base = render_node(children[0])
                if base.startswith(("\\sum", "\\prod", "\\int")):
                    lower_bound = _render_large_operator_lower_bound(
                        render_node(children[1])
                    )
                    return rf"{base}\limits_{{{lower_bound}}}"
                return rf"\underset{{{render_node(children[1])}}}{{{render_node(children[0])}}}"
        if local_name == "munderover":
            if len(children) >= 3:
                base = render_node(children[0])
                if base.startswith(("\\sum", "\\prod", "\\int")):
                    lower_bound = _render_large_operator_lower_bound(
                        render_node(children[1])
                    )
                    return rf"{base}\limits_{{{lower_bound}}}^{{{render_node(children[2])}}}"
                return rf"\overset{{{render_node(children[2])}}}{{\underset{{{render_node(children[1])}}}{{{render_node(children[0])}}}}}"
        if local_name == "mtable":
            rows = []
            for row in children:
                if xml_local_name(row.tag) != "mtr":
                    continue
                cells = [
                    render_node(cell) for cell in list(row) if isinstance(cell.tag, str)
                ]
                rows.append(" , ".join(cells))
            return (
                r"\begin{matrix} " + r" \\ ".join(rows) + r" \end{matrix}"
                if rows
                else ""
            )
        if local_name == "mtr":
            return " , ".join(render_node(child) for child in children)
        if local_name == "mtd":
            return _render_mathml_sequence(children, render_node)

        return normalize_compact_text("".join(node.itertext()))

    def render_script_base(node: ET.Element | None) -> str:
        expression = render_node(node)
        if not expression or node is None or not isinstance(node.tag, str):
            return expression

        if xml_local_name(node.tag) in {"mi", "mn", "mo", "mtext"}:
            return expression
        return f"{{{expression}}}"

    expression = normalize_latex_macros(render_node(element))

    def append_command_separator(match: re.Match[str]) -> str:
        return match.group(0) + " "

    for command in set(_MATHML_IDENTIFIER_LATEX.values()):
        expression = re.sub(
            re.escape(command) + r"(?=[A-Za-z])",
            append_command_separator,
            expression,
        )
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


def formula_graphic_url(element: ET.Element | None, *, source_url: str = "") -> str:
    graphic = first_descendant(element, "graphic")
    if graphic is None:
        return ""
    href = normalize_compact_text(
        str(graphic.get(XLINK_HREF) or graphic.get("href") or "")
    )
    if not href:
        return ""
    return urllib.parse.urljoin(source_url, href)


def render_display_formula_result(
    element: ET.Element | None, *, source_url: str = ""
) -> FormulaRenderResult:
    if element is None:
        return FormulaRenderResult(lines=[])

    label = child_text(element, "label")
    if not label:
        label = render_literal_inline_text(first_descendant(element, "label"))
    math_node = first_descendant(element, "math")
    tex_node = first_descendant(element, "tex-math")
    fallback_kind: str | None = None
    note: str | None = None
    if math_node is not None:
        expression = render_external_mathml_expression(math_node, display_mode=True)
        if not expression:
            expression = render_mathml_expression(math_node)
            if expression:
                fallback_kind = "fallback"
                note = "Formula used the internal MathML fallback renderer."
    else:
        expression = ""
    if not expression and tex_node is not None:
        expression = render_tex_math(tex_node)
        if expression:
            fallback_kind = "fallback"
            note = "Formula used the publisher tex-math fallback."
    image_url = ""
    if not expression:
        image_url = formula_graphic_url(element, source_url=source_url)
        if image_url:
            fallback_kind = "fallback"
            note = "Formula used the publisher formula image fallback."
    if not expression:
        expression = normalize_compact_text(
            render_literal_inline_text(element, skip_local_names={"label"})
        )
        if expression:
            fallback_kind = "fallback"
            note = "Formula used normalized literal text fallback."

    if not expression:
        placeholder_label = normalize_compact_text(label)
        expression = (
            f"[Formula unavailable: {placeholder_label}]"
            if placeholder_label
            else "[Formula unavailable]"
        )
        fallback_kind = "missing"
        note = "Formula could not be converted; an explicit placeholder was inserted."

    lines: list[str] = []
    if label:
        lines.extend([label, ""])
    if image_url:
        lines.extend(
            [render_markdown_image("formula", label or "Formula", image_url), ""]
        )
    elif fallback_kind == "missing":
        lines.extend([expression, ""])
    else:
        lines.extend(["$$", expression, "$$", ""])
    if note and label:
        note = f"{normalize_compact_text(label)}: {note}"
    return FormulaRenderResult(
        lines=lines,
        fallback_kind=fallback_kind,
        note=note,
        label=normalize_compact_text(label),
        image_url=image_url or None,
    )
