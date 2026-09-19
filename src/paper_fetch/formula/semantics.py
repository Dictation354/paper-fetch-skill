"""Preserve readable MathML error children and explicit spacing dimensions."""

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


def prepare_mathml_semantics(raw: str) -> tuple[str, dict[str, str]]:
    if "merror" not in raw and "mspace" not in raw:
        return raw, {}
    root = parse_mathml_fragment(raw)
    replacements: dict[str, str] = {}
    changed = False
    for node in root.iter():
        local = node.tag.rsplit("}", 1)[-1]
        namespace = node.tag[: -len(local)]
        if local == "merror":
            # Preserve only children actually present; raw_mathml on the result
            # remains the unmodified source, including its upstream error tag.
            node.tag = namespace + "mrow"
            changed = True
        elif local == "mspace":
            latex = mathml_space_latex(node.get("width", ""))
            if latex is None:
                continue
            token = f"PAPERFETCHMATHSPACE{len(replacements)}TOKEN"
            while token in raw:
                token += "X"
            node.tag = namespace + "mtext"
            node.attrib.clear()
            node.text = token
            replacements[token] = latex
            changed = True
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
