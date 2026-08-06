"""MathML and formula rendering helpers for article Markdown."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
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
    lines: list[str] = field(default_factory=list)
    method: str = "unavailable"
    status: str = "missing"
    fallback_kind: str | None = None
    note: str | None = None
    label: str | None = None
    image_url: str | None = None
    expression: str | None = None
    assets: list[dict[str, str]] = field(default_factory=list)


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


def _mathml_formula_result(
    element: ET.Element | None,
    *,
    display_mode: bool,
) -> FormulaRenderResult:
    if element is None:
        return FormulaRenderResult()
    conversion = convert_mathml_element_to_latex(
        element,
        display_mode=display_mode,
    )
    if conversion.status == "ok" and conversion.latex:
        return FormulaRenderResult(
            method=f"mathml:{conversion.backend}",
            status="ok",
            expression=conversion.latex,
        )
    expression = render_mathml_expression(element)
    if expression:
        return FormulaRenderResult(
            method="internal_mathml",
            status="fallback",
            fallback_kind="fallback",
            note="Formula used the internal MathML fallback renderer.",
            expression=expression,
        )
    return FormulaRenderResult(
        method=f"mathml:{conversion.backend}",
        status="missing",
        fallback_kind="missing",
        note="Formula MathML conversion failed and exposed no usable fallback.",
    )


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


def _formula_image_asset(image_url: str, label: str | None) -> dict[str, str]:
    normalized_label = normalize_compact_text(label)
    heading = f"Formula {normalized_label}" if normalized_label else "Formula"
    return {
        "kind": "formula",
        "key": image_url,
        "anchor_key": image_url,
        "heading": heading,
        "caption": "",
        "link": image_url,
        "original_url": image_url,
        "section": "body",
        "render_state": "inline",
    }


def render_inline_formula_result(
    element: ET.Element | None,
    *,
    source_url: str = "",
) -> FormulaRenderResult:
    if element is None:
        return FormulaRenderResult()
    label = child_text(element, "label") or None
    math_node = first_descendant(element, "math")
    if math_node is not None:
        result = _mathml_formula_result(math_node, display_mode=False)
        result.label = normalize_compact_text(label)
        if result.expression:
            return result
    tex_node = first_descendant(element, "tex-math")
    if tex_node is not None:
        expression = render_tex_math(tex_node)
        if expression:
            return FormulaRenderResult(
                method="tex-math",
                status="fallback",
                fallback_kind="fallback",
                note="Formula used the publisher tex-math fallback.",
                label=normalize_compact_text(label),
                expression=expression,
            )
    image_url = formula_graphic_url(element, source_url=source_url)
    if image_url:
        return FormulaRenderResult(
            method="graphic",
            status="fallback",
            fallback_kind="fallback",
            note="Formula used the publisher formula image fallback.",
            label=normalize_compact_text(label),
            image_url=image_url,
            assets=[_formula_image_asset(image_url, label)],
        )
    literal = normalize_compact_text(
        render_literal_inline_text(element, skip_local_names={"label"})
    )
    if literal:
        return FormulaRenderResult(
            method="literal_text",
            status="fallback",
            fallback_kind="fallback",
            note="Formula used normalized literal text fallback.",
            label=normalize_compact_text(label),
            expression=literal,
        )
    placeholder = (
        f"[Formula unavailable: {normalize_compact_text(label)}]"
        if normalize_compact_text(label)
        else "[Formula unavailable]"
    )
    return FormulaRenderResult(
        method="unavailable",
        status="missing",
        fallback_kind="missing",
        note="Formula could not be converted; an explicit placeholder was inserted.",
        label=normalize_compact_text(label),
        expression=placeholder,
    )


def formula_inline_markdown(result: FormulaRenderResult) -> str:
    if result.image_url:
        return render_markdown_image(
            "formula",
            result.label or "Formula",
            result.image_url,
        )
    expression = normalize_compact_text(result.expression)
    if not expression:
        return ""
    return expression if result.status == "missing" else f"${expression}$"


def render_inline_formula(element: ET.Element | None) -> str:
    """Compatibility wrapper returning the un-delimited inline expression."""

    result = render_inline_formula_result(element)
    if result.image_url:
        return formula_inline_markdown(result)
    return normalize_compact_text(result.expression)


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
    element: ET.Element | None,
    *,
    source_url: str = "",
    fallback_image_url: str = "",
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
    method = "unavailable"
    status = "missing"
    if math_node is not None:
        math_result = _mathml_formula_result(math_node, display_mode=True)
        expression = normalize_compact_text(math_result.expression)
        method = math_result.method
        status = math_result.status
        fallback_kind = math_result.fallback_kind
        note = math_result.note
    else:
        expression = ""
    if not expression and tex_node is not None:
        expression = render_tex_math(tex_node)
        if expression:
            fallback_kind = "fallback"
            method = "tex-math"
            status = "fallback"
            note = "Formula used the publisher tex-math fallback."
    image_url = ""
    if not expression:
        image_url = formula_graphic_url(
            element, source_url=source_url
        ) or normalize_compact_text(fallback_image_url)
        if image_url:
            fallback_kind = "fallback"
            method = "graphic"
            status = "fallback"
            note = "Formula used the publisher formula image fallback."
    if not expression and not image_url:
        expression = normalize_compact_text(
            render_literal_inline_text(element, skip_local_names={"label"})
        )
        if expression:
            fallback_kind = "fallback"
            method = "literal_text"
            status = "fallback"
            note = "Formula used normalized literal text fallback."

    if not expression and not image_url:
        placeholder_label = normalize_compact_text(label)
        expression = (
            f"[Formula unavailable: {placeholder_label}]"
            if placeholder_label
            else "[Formula unavailable]"
        )
        fallback_kind = "missing"
        method = "unavailable"
        status = "missing"
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
        method=method,
        status=status,
        fallback_kind=fallback_kind,
        note=note,
        label=normalize_compact_text(label),
        image_url=image_url or None,
        expression=expression,
        assets=[_formula_image_asset(image_url, label)] if image_url else [],
    )


def render_mathml_formula_result(
    element: ET.Element | None,
    *,
    display_mode: bool = False,
) -> FormulaRenderResult:
    return _mathml_formula_result(element, display_mode=display_mode)


def render_tex_formula_result(element: ET.Element | None) -> FormulaRenderResult:
    expression = render_tex_math(element)
    if expression:
        return FormulaRenderResult(
            method="tex-math",
            status="fallback",
            fallback_kind="fallback",
            note="Formula used the publisher tex-math fallback.",
            expression=expression,
        )
    return FormulaRenderResult(
        method="unavailable",
        status="missing",
        fallback_kind="missing",
        note="Formula tex-math content was empty.",
        expression="[Formula unavailable]",
    )
