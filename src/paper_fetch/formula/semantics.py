"""Preserve MathML source tokens, glyph variants, fences and explicit spacing."""

from __future__ import annotations

from decimal import Decimal
import re
import xml.etree.ElementTree as ET

from ..xml_security import parse_mathml_fragment

_DIMENSION = re.compile(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(em|ex|pt|pc|in|cm|mm|px)?$")
_NAMED_SPACES = {
    name + "mathspace": index
    for index, name in enumerate(
        (
            "veryverythin",
            "verythin",
            "thin",
            "medium",
            "thick",
            "verythick",
            "veryverythick",
        ),
        start=1,
    )
}


def mathml_space_latex(width: str) -> str | None:
    value = width.strip()
    negative = value.startswith("negative")
    named = value.removeprefix("negative")
    if named in _NAMED_SPACES:
        return rf"\mkern{(-1 if negative else 1) * _NAMED_SPACES[named]}mu "
    match = _DIMENSION.fullmatch(value)
    if match is None:
        return None
    number = Decimal(match[1])
    unit = match[2] or "em"
    if unit == "px":
        number *= Decimal("0.75")
        unit = "bp"
    amount = format(number.normalize(), "f")
    return rf"\hspace{{{amount}{unit}}}"


_MATH_FUNCTIONS = frozenset(
    {
        "sin",
        "cos",
        "tan",
        "cot",
        "sec",
        "csc",
        "sinh",
        "cosh",
        "tanh",
        "arcsin",
        "arccos",
        "arctan",
        "exp",
        "log",
        "ln",
        "lim",
        "min",
        "max",
        "det",
        "dim",
        "gcd",
        "sup",
        "inf",
        "arg",
        "Pr",
    }
)


def mathml_token_latex(
    text: str, expression: str, variant: str | None, *, operator: bool = False
) -> str:
    """Keep source token typography; never reinterpret an arbitrary TeX string."""
    if "\\" in text:
        return expression
    if text in {"%", "_", "#", "&", "{", "}"} and expression == text:
        expression = "\\" + text
    if text in _MATH_FUNCTIONS and variant not in {"italic", "bold-italic"}:
        return "\\" + text + " "
    if operator and (not variant or not text.isalpha()):
        return expression
    wrappers = {
        "normal": "mathrm",
        "bold": "mathbf",
        "italic": "mathit",
        "bold-italic": "boldsymbol",
        "script": "mathcal",
        "bold-script": "mathcal",
        "double-struck": "mathbb",
        "fraktur": "mathfrak",
        "bold-fraktur": "mathfrak",
        "sans-serif": "mathsf",
        "monospace": "mathtt",
    }
    wrapper = wrappers.get(variant or "")
    if wrapper is None and variant is None and len(text) > 1 and not operator:
        wrapper = "mathrm"
    if wrapper:
        result = f"\\{wrapper}{{{expression}}}"
        if variant in {"bold-script", "bold-fraktur"}:
            result = f"\\boldsymbol{{{result}}}"
        return result
    return expression


def _styled_mathml_text_latex(text: str, variant: str | None) -> str | None:
    commands = {
        "italic": "textit",
        "bold": "textbf",
        "sans-serif": "textsf",
        "monospace": "texttt",
    }
    command = commands.get(variant or "")
    if command is None and variant != "bold-italic":
        return None
    escapes = {
        "\\": r"\textbackslash{}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    literal = "".join(
        escapes.get(char, "\\" + char if char in "{}%_#&$" else char) for char in text
    )
    if variant == "bold-italic":
        return r"\textbf{\textit{" + literal + "}}"
    assert command is not None
    return "\\" + command + "{" + literal + "}"


def prepare_mathml_semantics(raw: str) -> tuple[str, dict[str, str]]:
    if not any(
        name in raw
        for name in ("merror", "mspace", "mtext", "mi", "mo", "mn", "mfenced")
    ):
        return raw, {}
    root = parse_mathml_fragment(raw)
    replacements: dict[str, str] = {}
    changed = False
    inherited_variants: dict[int, str | None] = {}

    def variants(node, inherited=None):
        inherited = node.get("mathvariant", inherited)
        inherited_variants[id(node)] = inherited
        for child in node:
            variants(child, inherited)

    variants(root)

    def preserve(node, namespace, latex):
        token = f"PAPERFETCHMATHSPACE{len(replacements)}TOKEN"
        while token in raw:
            token += "X"
        node.tag = namespace + "mtext"
        node.attrib.clear()
        node.text = token
        replacements[token] = latex

    parents = {child: parent for parent in root.iter() for child in parent}
    for node in list(root.iter()):
        local = node.tag.rsplit("}", 1)[-1]
        namespace = node.tag[: -len(local)]
        if (
            local == "mfenced"
            and "separators" in node.attrib
            and not node.get("separators", "").strip()
        ):
            # A single row child prevents backends from inventing separators.
            row = ET.Element(namespace + "mrow")
            row.extend(list(node))
            node[:] = [row]
            changed = True
        elif local in {"mi", "mo", "mn"} and not list(node):
            if local == "mn" and inherited_variants[id(node)] in {None, "normal"}:
                continue
            text = (node.text or "").strip()
            latex = None
            if local == "mo" and (node.text or "") and not text:
                latex = r"\ {}"
            elif (
                local == "mo"
                and text == "°"
                and (parent := parents.get(node)) is not None
                and parent.tag.rsplit("}", 1)[-1] in {"msup", "msubsup"}
            ):
                latex = r"\circ"
            elif local == "mo" and text == "~":
                latex = r"\sim "
            elif text:
                styled = mathml_token_latex(
                    text, text, inherited_variants[id(node)], operator=local == "mo"
                )
                if styled != text:
                    latex = styled
            if latex is not None:
                preserve(node, namespace, latex)
                changed = True
        elif local == "merror":
            # Preserve only children actually present; raw_mathml on the result
            # remains the unmodified source, including its upstream error tag.
            node.tag = namespace + "mrow"
            changed = True
        elif local == "mtext" and not list(node) and not (node.text or "").strip():
            # Source indentation is not an operator name or a string of tildes.
            node.tag = namespace + "mrow"
            node.text = None
            changed = True
        elif local == "mtext" and not list(node):
            latex = _styled_mathml_text_latex(
                node.text or "", inherited_variants[id(node)]
            )
            if latex is not None:
                preserve(node, namespace, latex)
                changed = True
        elif local == "mspace":
            latex = mathml_space_latex(node.get("width", ""))
            if latex is None:
                continue
            preserve(node, namespace, latex)
            changed = True
    if changed:
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1] in {"mstyle", "mrow", "math"}:
                node.attrib.pop("mathvariant", None)
    return (ET.tostring(root, encoding="unicode") if changed else raw), replacements


def restore_mathml_spacing(latex: str, replacements: dict[str, str]) -> str | None:
    for token, spacing in replacements.items():
        pattern = re.compile(
            r"\\(?:text|mathrm|operatorname)\s*\{\s*" + re.escape(token) + r"\s*\}"
        )

        def replacement(_match: re.Match[str], value: str = spacing) -> str:
            return value

        latex, count = pattern.subn(replacement, latex)
        if count != 1 or token in latex:
            return None
    return latex
