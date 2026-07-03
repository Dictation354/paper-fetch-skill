"""Formula rendering helpers."""

from __future__ import annotations

from typing import Any

from ...extraction.html.formula_rules import (
    formula_image_url_from_node,
    is_tex_formula_script_node,
    is_display_formula_node,
    is_formula_container,
    looks_like_formula_image,
    mathml_element_from_html_node,
)
from ...formula.convert import normalize_latex
from ...markdown.images import render_markdown_image
from ...providers._article_markdown_math import (
    render_external_mathml_expression,
    render_mathml_expression,
)
from ...utils import normalize_text
from ._ir import MarkdownFormula

from bs4 import Tag
import contextlib


def render_formula(formula: MarkdownFormula) -> list[str]:
    lines: list[str] = []
    label = normalize_text(formula.label)
    latex = normalize_latex(formula.latex)
    if label:
        lines.extend([label, ""])
    if latex:
        lines.extend(
            ["$$", latex, "$$", ""] if formula.display_mode else [f"${latex}$", ""]
        )
    elif formula.fallback_image_url:
        lines.extend(
            [
                render_markdown_image(
                    "formula", formula.label, formula.fallback_image_url
                ),
                "",
            ]
        )
    else:
        lines.extend(["[Formula unavailable]", ""])
    return lines


def is_mathjax_tex_node(node: Any) -> bool:
    if not isinstance(node, Tag):
        return False
    name = normalize_text(node.name or "").lower()
    if name == "tex-math":
        return True
    classes = getattr(node, "attrs", {}).get("class") or []
    if isinstance(classes, str):
        class_values = classes.split()
    else:
        class_values = [str(value) for value in classes]
    normalized_classes = {normalize_text(value).lower() for value in class_values}
    return bool(normalized_classes & {"mathjax-tex", "tex", "tex2jax_ignore"})


def _class_tokens(node: Any) -> set[str]:
    if not isinstance(node, Tag):
        return set()
    classes = getattr(node, "attrs", {}).get("class") or []
    if isinstance(classes, str):
        values = classes.split()
    else:
        values = [str(value) for value in classes]
    return {normalize_text(value).lower() for value in values if normalize_text(value)}


def _is_inline_tex_formula_container(node: Any) -> bool:
    classes = _class_tokens(node)
    if not classes & {"inline-equation", "inline-eqn"}:
        return False
    if classes & {"display-equation", "display-eqn", "display-formula", "disp-formula"}:
        return False
    return isinstance(node, Tag) and any(
        is_tex_formula_script_node(script) for script in node.find_all("script")
    )


def normalize_tex_formula_text(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    delimiter_pairs = (
        ("$$", "$$"),
        (r"\(", r"\)"),
        (r"\[", r"\]"),
        ("$", "$"),
    )
    for opener, closer in delimiter_pairs:
        if (
            text.startswith(opener)
            and text.endswith(closer)
            and len(text) > len(opener) + len(closer)
        ):
            latex = normalize_latex(text[len(opener) : -len(closer)].strip())
            return f"{opener}{latex}{closer}" if latex else ""
    return normalize_latex(text)


def _is_delimited_inline_latex(value: str) -> bool:
    text = normalize_text(value)
    delimiter_pairs = (
        ("$$", "$$"),
        (r"\(", r"\)"),
        (r"\[", r"\]"),
        ("$", "$"),
    )
    return any(
        text.startswith(opener)
        and text.endswith(closer)
        and len(text) > len(opener) + len(closer)
        for opener, closer in delimiter_pairs
    )


def render_inline_latex_markdown(value: str | None) -> str:
    latex = normalize_text(value)
    if not latex:
        return ""
    return latex if _is_delimited_inline_latex(latex) else f"${latex}$"


def html_formula_latex_from_node(node: Any) -> str:
    if not isinstance(node, Tag):
        return ""
    candidates: list[Any] = []
    if is_tex_formula_script_node(node):
        candidates.append(node)
    if is_mathjax_tex_node(node):
        candidates.append(node)
    candidates.extend(
        candidate
        for candidate in node.find_all("script")
        if is_tex_formula_script_node(candidate)
    )
    candidates.extend(
        candidate
        for candidate in node.find_all("tex-math")
        if isinstance(candidate, Tag)
    )
    with contextlib.suppress(Exception):
        candidates.extend(
            candidate
            for candidate in node.select(".mathjax-tex, .tex, .tex2jax_ignore")
            if isinstance(candidate, Tag)
        )
    seen: set[int] = set()
    for candidate in candidates:
        identity = id(candidate)
        if identity in seen:
            continue
        seen.add(identity)
        latex = normalize_tex_formula_text(candidate.get_text("", strip=False))
        if latex:
            return latex
    return ""


def first_html_formula_image_url(node: Any) -> str:
    return formula_image_url_from_node(node)


def is_html_formula_container(node: Any) -> bool:
    return is_formula_container(node)


def is_html_display_formula_node(node: Any) -> bool:
    return is_display_formula_node(node)


def is_html_formula_image_node(node: Any) -> bool:
    return looks_like_formula_image(node)


def render_html_formula_image_node(node: Any) -> str:
    url = first_html_formula_image_url(node)
    if not url:
        return ""
    return render_markdown_image("formula", "", url)


def render_html_mathml_node(node: Any) -> str:
    element = mathml_element_from_html_node(node)
    if element is None:
        return ""
    display_mode = is_html_display_formula_node(node)
    expression = normalize_text(
        render_external_mathml_expression(element, display_mode=display_mode)
    )
    if not expression:
        expression = normalize_text(render_mathml_expression(element))
    if not expression:
        return ""
    return f"\n\n$$\n{expression}\n$$\n\n" if display_mode else f"${expression}$"


def render_html_formula_container(node: Any) -> str:
    mathml = render_html_mathml_node(node)
    if mathml:
        return mathml
    latex = html_formula_latex_from_node(node)
    if latex:
        display_mode = is_html_display_formula_node(
            node
        ) and not _is_inline_tex_formula_container(node)
        return (
            f"\n\n$$\n{latex}\n$$\n\n"
            if display_mode
            else render_inline_latex_markdown(latex)
        )
    image_url = first_html_formula_image_url(node)
    if image_url:
        rendered = render_markdown_image("formula", "", image_url)
        return f"\n\n{rendered}\n\n" if is_html_display_formula_node(node) else rendered
    if is_html_formula_container(node):
        return "[Formula unavailable]"
    return ""
