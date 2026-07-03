"""Shared section-aware HTML-to-Markdown helpers."""

from __future__ import annotations

import re
from typing import Any

from ..common_patterns import HEADING_TAG_PATTERN, INLINE_WHITESPACE_PATTERN
from ..extraction.html.inline import (
    InlineToken,
    html_inline_tokens,
    needs_space_between_inline_text,
    render_html_inline_node,
    render_inline_tokens,
)
from ..extraction.markdown_render.figures import (
    FIGURE_ACTION_TRAILING_LINK_PATTERN as FIGURE_ACTION_TRAILING_LINK_PATTERN,
    FIGURE_DESCRIPTION_SELECTORS as FIGURE_DESCRIPTION_SELECTORS,
    FIGURE_ID_PATTERN as FIGURE_ID_PATTERN,
    FIGURE_LABEL_PATTERN as FIGURE_LABEL_PATTERN,
    INLINE_FIGURE_ALT_ATTR as INLINE_FIGURE_ALT_ATTR,
    INLINE_FIGURE_SRC_ATTR as INLINE_FIGURE_SRC_ATTR,
    is_html_figure_container as _is_figure_container,
    render_html_figure_markdown,
)
from ..extraction.markdown_render.formulas import (
    is_html_formula_container as _is_formula_container,
    is_html_display_formula_node as _is_display_formula_node,
    is_html_formula_image_node as _is_formula_image_node,
    is_mathjax_tex_node as _is_mathjax_tex_node,
    normalize_tex_formula_text as _normalize_tex_formula_text,
    render_inline_latex_markdown as _render_inline_latex_markdown,
    render_html_formula_container as _render_formula_container,
    render_html_formula_image_node as _render_formula_image_node,
    render_html_mathml_node as _render_mathml_node,
)
from ..extraction.html.semantics import normalize_section_title
from ..extraction.html._runtime import (
    HTML_BLOCK_TAGS,
    HTML_DROP_TAGS,
    should_drop_html_element,
)
from ..models import normalize_text
from ..markdown.citations import numeric_citation_payload_from_html_node

from bs4 import NavigableString, Tag

INLINE_IMAGE_SPACING_PATTERN = re.compile(r"(?<=[^\s])(!\[)")
LINE_EDGE_WHITESPACE_PATTERN = re.compile(r" *\n *")
MARKDOWN_BLANK_RUN_PATTERN = re.compile(r"\n{3,}")
ORDERED_LIST_PREFIX_PATTERN = re.compile(
    r"^\s*(?:\(?\d+[A-Za-z]?\)?|[ivxlcdm]+)[.)]\s+", flags=re.IGNORECASE
)
UNORDERED_LIST_PREFIX_PATTERN = re.compile(r"^\s*[•◦▪▫‣⁃∙●○◾◽◼□■]\s*")
MARKDOWN_LIST_ITEM_PATTERN = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def _render_heading_inline_node(node: Any, *, text_style: str | None = None) -> str:
    return render_html_inline_node(node, policy="heading", text_style=text_style)


def render_heading_text_from_html(node: Any) -> str:
    return _render_heading_inline_node(node)


def extract_section_title(section: Any) -> str:
    if section is None:
        return ""
    heading = section.find(HEADING_TAG_PATTERN)
    if heading is None:
        return ""
    return render_heading_text_from_html(heading)


def _select_first(node: Any, selectors: tuple[str, ...]) -> Any:
    if node is None:
        return None
    for selector in selectors:
        match = node.select_one(selector)
        if match is not None:
            return match
    return None


def section_has_direct_renderable_content(
    section: Any,
    *,
    section_content_selectors: tuple[str, ...] = ("div.c-article-section__content",),
) -> bool:
    if section is None:
        return False
    content_root = _select_first(section, section_content_selectors) or section
    for child in content_root.children:
        if isinstance(child, NavigableString):
            if normalize_text(str(child)):
                return True
            continue
        if not isinstance(child, Tag):
            continue
        if child.name in {"header", "footer"}:
            continue
        if child.name in HTML_DROP_TAGS or should_drop_html_element(child):
            continue
        if child.name in {"p", "blockquote", "pre", "ul", "ol", "figure", "table"}:
            return True
        if _is_figure_container(child):
            return True
        if child.name in {"div", "article", "main"}:
            if child.find(
                "section", recursive=False
            ) is None and render_clean_text_from_html(child):
                return True
    return False


def render_section_markdown(
    section: Any,
    lines: list[str],
    *,
    level: int,
    force_heading: str | None = None,
    section_content_selectors: tuple[str, ...] = ("div.c-article-section__content",),
) -> None:
    heading = force_heading or extract_section_title(section)
    content_root = _select_first(section, section_content_selectors) or section
    rendered_content: list[str] = []
    render_container_markdown(
        content_root,
        rendered_content,
        level=level + 1,
        skip_first_heading=heading or None,
        section_content_selectors=section_content_selectors,
    )
    if not rendered_content:
        return
    if heading:
        lines.extend([f"{'#' * max(2, min(level, 6))} {heading}", ""])
    lines.extend(rendered_content)


def render_container_markdown(
    node: Any,
    lines: list[str],
    *,
    level: int,
    skip_first_heading: str | None = None,
    section_content_selectors: tuple[str, ...] = ("div.c-article-section__content",),
) -> None:
    if node is None:
        return

    for child in node.children:
        if isinstance(child, NavigableString):
            text = normalize_prose_markdown_line_breaks(str(child))
            if text:
                lines.extend([text, ""])
            continue
        if not isinstance(child, Tag):
            continue
        if child.name in {"header", "footer"}:
            continue
        if child.name in HTML_DROP_TAGS or should_drop_html_element(child):
            continue
        if child.name == "section":
            render_section_markdown(
                child,
                lines,
                level=level,
                section_content_selectors=section_content_selectors,
            )
            continue
        if _is_div_section_container(child):
            render_section_markdown(
                child,
                lines,
                level=level,
                section_content_selectors=section_content_selectors,
            )
            continue
        if child.name and HEADING_TAG_PATTERN.match(child.name):
            heading_text = render_heading_text_from_html(child)
            if skip_first_heading and normalize_section_title(
                heading_text
            ) == normalize_section_title(skip_first_heading):
                continue
            if heading_text:
                lines.extend([f"{'#' * max(2, min(level, 6))} {heading_text}", ""])
            continue
        if child.name in {"p", "blockquote"}:
            text = render_clean_text_from_html(child, collapse_prose_line_breaks=True)
            if text:
                lines.extend([text, ""])
            continue
        if child.name == "pre":
            text = normalize_text(child.get_text("\n", strip=False))
            if text:
                lines.extend([text, ""])
            continue
        if child.name in {"ul", "ol"}:
            start = 1
            if child.name == "ol":
                try:
                    start = int(normalize_text(str(child.get("start") or "1")) or "1")
                except ValueError:
                    start = 1
            for index, item in enumerate(child.find_all("li", recursive=False)):
                text = render_clean_text_from_html(
                    item, collapse_prose_line_breaks=True
                )
                if text:
                    if child.name == "ol":
                        text = ORDERED_LIST_PREFIX_PATTERN.sub("", text)
                        lines.append(f"{start + index}. {text}")
                    else:
                        text = UNORDERED_LIST_PREFIX_PATTERN.sub("", text)
                        lines.append(f"- {text}")
            if lines and lines[-1]:
                lines.append("")
            continue
        if _is_figure_container(child):
            render_figure_markdown(child, lines)
            continue
        if child.name == "figure":
            continue
        if child.name == "table":
            text = render_clean_text_from_html(child)
            if text:
                lines.extend([text, ""])
            continue
        if child.name in {"div", "article", "main"}:
            render_container_markdown(
                child,
                lines,
                level=level,
                skip_first_heading=skip_first_heading,
                section_content_selectors=section_content_selectors,
            )
            continue
        text = render_clean_text_from_html(child)
        if text:
            lines.extend([text, ""])


def _is_div_section_container(node: Any) -> bool:
    if not isinstance(node, Tag) or normalize_text(node.name or "").lower() != "div":
        return False
    class_values = getattr(node, "attrs", {}).get("class") or []
    if isinstance(class_values, str):
        classes = {item.lower() for item in class_values.split()}
    else:
        classes = {normalize_text(str(item)).lower() for item in class_values}
    return (
        bool(classes & {"section", "section_2"})
        and node.find(HEADING_TAG_PATTERN) is not None
    )


def render_figure_markdown(node: Any, lines: list[str]) -> None:
    render_html_figure_markdown(
        node, lines, render_clean_text=render_clean_text_from_html
    )


def _numeric_citation_payload_from_html(node: Any) -> str | None:
    return numeric_citation_payload_from_html_node(
        node,
        wrapper_tags=("sup", "i", "em"),
    )


def _is_linebreak_sensitive_markdown_block(block: str) -> bool:
    lines = [line.strip() for line in block.splitlines() if normalize_text(line)]
    if len(lines) <= 1:
        return False
    if any(
        line.startswith(("$$", "|", "```", "~~~", "![", "#"))
        or MARKDOWN_LIST_ITEM_PATTERN.match(line)
        for line in lines
    ):
        return True
    return "$$\n" in block or "\n$$" in block


def normalize_prose_markdown_line_breaks(text: str) -> str:
    normalized = MARKDOWN_BLANK_RUN_PATTERN.sub(
        "\n\n", text.replace("\r\n", "\n").replace("\r", "\n")
    )
    parts = re.split(r"(\n\s*\n)", normalized)
    collapsed: list[str] = []
    for part in parts:
        if not part:
            continue
        if re.fullmatch(r"\n\s*\n", part):
            collapsed.append("\n\n")
            continue
        if _is_linebreak_sensitive_markdown_block(part):
            collapsed.append(normalize_text(part))
            continue
        collapsed.append(normalize_text(re.sub(r"\s*\n\s*", " ", part)))
    return normalize_text("".join(collapsed))


def render_clean_text_from_html(
    node: Any, *, collapse_prose_line_breaks: bool = False
) -> str:
    rendered = render_clean_html_node(node)
    rendered = INLINE_IMAGE_SPACING_PATTERN.sub(r" \1", rendered)
    rendered = INLINE_WHITESPACE_PATTERN.sub(" ", rendered)
    rendered = LINE_EDGE_WHITESPACE_PATTERN.sub("\n", rendered)
    rendered = MARKDOWN_BLANK_RUN_PATTERN.sub("\n\n", rendered)
    if collapse_prose_line_breaks:
        rendered = normalize_prose_markdown_line_breaks(rendered)
    return normalize_text(rendered)


def render_clean_html_node(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""
    if node.name in HTML_DROP_TAGS:
        return ""
    if _is_mathjax_tex_node(node):
        latex = _normalize_tex_formula_text(node.get_text("", strip=False))
        return (
            latex
            if _is_display_formula_node(node)
            else _render_inline_latex_markdown(latex)
        )
    if normalize_text(node.name or "").lower() == "math":
        return _render_mathml_node(node)
    if _is_formula_image_node(node):
        return _render_formula_image_node(node)
    if _is_formula_container(node):
        rendered_formula = _render_formula_container(node)
        if rendered_formula:
            return rendered_formula
    if node.name == "br":
        return "\n"
    if node.name == "figure":
        caption = node.find("figcaption")
        return render_clean_html_node(caption)
    if _is_inline_html_node(node):
        return _render_clean_inline_node(node)

    rendered = render_clean_children(node)
    if not rendered.strip():
        return ""
    if node.name in {"li"}:
        return f"\n\n{rendered}\n\n"
    if node.name in HTML_BLOCK_TAGS:
        return f"\n\n{rendered}\n\n"
    return rendered


def _is_inline_html_node(node: Any) -> bool:
    if not isinstance(node, Tag):
        return False
    name = normalize_text(node.name or "").lower()
    return (
        bool(name) and name not in HTML_BLOCK_TAGS and name not in {"figure", "table"}
    )


def _raw_inline_markdown_from_node(node: Any) -> str | None:
    if not isinstance(node, Tag):
        return None
    if _is_mathjax_tex_node(node):
        latex = _normalize_tex_formula_text(node.get_text("", strip=False))
        if not latex:
            return None
        return (
            latex
            if _is_display_formula_node(node)
            else _render_inline_latex_markdown(latex)
        )
    if normalize_text(node.name or "").lower() == "math":
        return _render_mathml_node(node) or None
    if _is_formula_image_node(node):
        return _render_formula_image_node(node) or None
    if _is_formula_container(node):
        return _render_formula_container(node) or None
    return None


def _drop_inline_node(node: Any) -> bool:
    return isinstance(node, Tag) and node.name in HTML_DROP_TAGS


def _render_clean_inline_node(node: Any) -> str:
    return render_html_inline_node(
        node,
        policy="body",
        citation_payload_from_node=_numeric_citation_payload_from_html,
        raw_markdown_from_node=_raw_inline_markdown_from_node,
        drop_node=_drop_inline_node,
        render_text_styles=False,
        break_render="\n",
    )


def _render_clean_inline_tokens(tokens: list[InlineToken]) -> str:
    return render_inline_tokens(tokens, policy="body", break_render="\n")


def render_clean_children(node: Any) -> str:
    text = ""
    inline_tokens: list[InlineToken] = []

    def flush_inline_tokens() -> None:
        nonlocal text, inline_tokens
        if not inline_tokens:
            return
        rendered_inline = _render_clean_inline_tokens(inline_tokens)
        if rendered_inline:
            if needs_space_between_inline_text(
                text,
                rendered_inline,
                right_is_markdown_image=rendered_inline.startswith("!["),
            ):
                text += " "
            text += rendered_inline
        inline_tokens = []

    for child in node.children:
        if isinstance(child, NavigableString):
            inline_tokens.extend(html_inline_tokens(child))
            continue
        if not isinstance(child, Tag):
            continue
        if _is_inline_html_node(child):
            inline_tokens.extend(
                html_inline_tokens(
                    child,
                    citation_payload_from_node=_numeric_citation_payload_from_html,
                    raw_markdown_from_node=_raw_inline_markdown_from_node,
                    drop_node=_drop_inline_node,
                    render_text_styles=False,
                )
            )
            continue
        flush_inline_tokens()
        rendered = render_clean_html_node(child)
        if not rendered:
            continue
        if needs_space_between_inline_text(
            text,
            rendered,
            right_is_markdown_image=rendered.startswith("!["),
        ):
            text += " "
        text += rendered
    flush_inline_tokens()
    return text
