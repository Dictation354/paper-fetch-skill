"""Shared section-aware HTML-to-Markdown helpers."""

from __future__ import annotations

from ..markdown.math import protect_markdown_math, restore_markdown_math
from ..formula.convert import normalize_latex
from ..formula.validation import formula_document

import re
from copy import deepcopy
from urllib.parse import urljoin
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
from ..markdown.images import render_markdown_image

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

INLINE_IMAGE_SPACING_PATTERN = re.compile(r"(?<=[^\s])(!\[)")
LINE_EDGE_WHITESPACE_PATTERN = re.compile(r" *\n *")
MARKDOWN_BLANK_RUN_PATTERN = re.compile(r"\n{3,}")
ORDERED_LIST_PREFIX_PATTERN = re.compile(
    r"^\s*(?:\(?\d+[A-Za-z]?\)?|[ivxlcdm]+)[.)]\s+", flags=re.IGNORECASE
)
UNORDERED_LIST_PREFIX_PATTERN = re.compile(r"^\s*[•◦▪▫‣⁃∙●○◾◽◼□■]\s*")
MARKDOWN_LIST_ITEM_PATTERN = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def _render_heading_inline_node(node: Any, *, text_style: str | None = None) -> str:
    if isinstance(node, Tag):
        node = deepcopy(node)
        for label in node.select("span"):
            if (
                re.fullmatch(r"\d+(?:\.\d+)*\.?", label.get_text(strip=True))
                and label.next_sibling is not None
                and not str(label.next_sibling).startswith(" ")
            ):
                label.insert_after(" ")
    return render_html_inline_node(
        node,
        policy="heading",
        text_style=text_style,
        raw_markdown_from_node=_raw_inline_markdown_from_node,
    )


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
        if isinstance(child, Comment):
            continue
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
    preserve_heading_levels: bool = False,
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
        preserve_heading_levels=preserve_heading_levels,
    )
    if not rendered_content:
        return
    if heading:
        source_heading = section.find(HEADING_TAG_PATTERN)
        heading_level = (
            int(source_heading.name[1])
            if preserve_heading_levels and source_heading is not None
            else level
        )
        lines.extend([f"{'#' * max(2, min(heading_level, 6))} {heading}", ""])
    lines.extend(rendered_content)


@formula_document
def render_container_markdown(
    node: Any,
    lines: list[str],
    *,
    level: int,
    skip_first_heading: str | None = None,
    section_content_selectors: tuple[str, ...] = ("div.c-article-section__content",),
    preserve_heading_levels: bool = False,
) -> None:
    if node is None:
        return

    pending_inline: list[Any] = []

    def flush_inline() -> None:
        if not pending_inline:
            return
        span = BeautifulSoup("<span></span>", "html.parser").span
        for inline in pending_inline:
            span.append(deepcopy(inline))
        text = render_clean_text_from_html(span, collapse_prose_line_breaks=True)
        pending_inline.clear()
        if text:
            lines.extend([text, ""])

    for child in node.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            if _is_linebreak_sensitive_markdown_block(str(child)):
                flush_inline()
                text = normalize_prose_markdown_line_breaks(str(child))
                if text:
                    lines.extend([text, ""])
                continue
            pending_inline.append(child)
            continue
        if not isinstance(child, Tag):
            continue
        if child.get("data-paper-fetch-markdown") is not None:
            if child.name == "span":
                pending_inline.append(child)
            else:
                flush_inline()
                lines.extend([child.get_text("\n\n", strip=False), ""])
            continue
        if child.name in {"header", "footer"}:
            continue
        if child.name in HTML_DROP_TAGS or should_drop_html_element(child):
            continue
        if (
            child.name
            in {
                "a",
                "span",
                "i",
                "em",
                "b",
                "strong",
                "sub",
                "sup",
                "br",
                "code",
                "monospace",
                "inline-formula",
                "tex-math",
                "math",
                "img",
            }
            and not _is_display_formula_node(child)
            and child.get("role") not in {"list", "listitem"}
            and (
                child.name in {"math", "tex-math", "inline-formula"}
                or child.find(["p", "div", "ul", "ol", "h2", "h3", "h4", "section"])
                is None
            )
        ):
            pending_inline.append(child)
            continue
        flush_inline()
        if _is_mathjax_tex_node(child) or _is_formula_container(child):
            text = render_clean_text_from_html(child)
            if text:
                lines.extend([text, ""])
            continue
        if child.name == "section":
            render_section_markdown(
                child,
                lines,
                level=level,
                section_content_selectors=section_content_selectors,
                preserve_heading_levels=preserve_heading_levels,
            )
            continue
        if _is_div_section_container(child):
            render_section_markdown(
                child,
                lines,
                level=level,
                section_content_selectors=section_content_selectors,
                preserve_heading_levels=preserve_heading_levels,
            )
            continue
        if child.name and HEADING_TAG_PATTERN.match(child.name):
            heading_text = render_heading_text_from_html(child)
            if skip_first_heading and normalize_section_title(
                heading_text
            ) == normalize_section_title(skip_first_heading):
                continue
            if heading_text:
                heading_level = int(child.name[1]) if preserve_heading_levels else level
                lines.extend(
                    [f"{'#' * max(2, min(heading_level, 6))} {heading_text}", ""]
                )
            continue
        if (
            child.name in {"p", "blockquote"}
            and child.find(["ul", "ol", "table", "div", "p", "figure", "section"])
            is not None
        ):
            render_container_markdown(child, lines, level=level)
            continue
        if child.name in {"p", "blockquote"}:
            text = render_clean_text_from_html(child, collapse_prose_line_breaks=True)
            if text:
                lines.extend([text, ""])
            continue
        if child.name == "pre":
            text = child.get_text("", strip=False).strip("\n")
            fence = "`" * max(
                3, max((len(m[0]) + 1 for m in re.finditer(r"`+", text)), default=0)
            )
            if text:
                lines.extend([fence, text, fence, ""])
            continue
        if child.name in {"ul", "ol"} or child.get("role") == "list":
            lines.extend(_render_html_list(child, level=level))
            continue
        if _is_figure_container(child):
            render_figure_markdown(child, lines)
            continue
        if child.name == "figure":
            continue
        if child.name == "table":
            from ..extraction.html.tables import render_table_markdown

            text = render_table_markdown(
                child,
                label="",
                caption="",
                render_inline_text=render_clean_text_from_html,
            )
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
                preserve_heading_levels=preserve_heading_levels,
            )
            continue
        if (
            child.find(["p", "div", "ul", "ol", "h2", "h3", "h4", "h5", "section"])
            is not None
        ):
            render_container_markdown(
                child,
                lines,
                level=level,
                preserve_heading_levels=preserve_heading_levels,
            )
            continue
        text = render_clean_text_from_html(child)
        if text:
            lines.extend([text, ""])
    flush_inline()


def _render_html_list(node: Tag, *, level: int) -> list[str]:
    lines = []
    try:
        number = int(node.get("start", "1"))
    except ValueError:
        number = 1
    ordered = node.name == "ol"
    items = (
        node.find_all("li", recursive=False)
        if node.name in {"ul", "ol"}
        else node.find_all(attrs={"role": "listitem"}, recursive=False)
    )
    for item in items:
        try:
            number = int(item.get("value", number))
        except ValueError:
            number = 1
        item = deepcopy(item)
        if "label-provided" in node.get("class", []):
            supplied = item.find("span", recursive=False)
            if supplied is not None:
                item["data-list-item-label"] = supplied.get_text(strip=True)
                supplied.decompose()
        label_node = item.select_one(".ltx_tag_item, .indices-id, :scope > .label")
        source_label = (
            label_node.get_text("", strip=True) if label_node is not None else ""
        )
        indices_label = label_node is not None and "indices-id" in label_node.get(
            "class", []
        )
        if label_node is not None:
            label = label_node.get_text("", strip=True)
            if ordered and re.fullmatch(r"[\[(]?\d+[.)\]]?", label):
                number_match = re.search(r"\d+", label)
                assert number_match is not None
                number = int(number_match[0])
                label_node.decompose()
            elif (
                indices_label
                or item.get("data-list-item-label")
                or (not ordered and label in {"•", "—", "–", "-", "▪"})
            ):
                label_node.decompose()
        blocks = []
        if item.get("data-paper-fetch-markdown") is not None:
            blocks.append(item.get_text("\n\n", strip=False))
        else:
            render_container_markdown(item, blocks, level=level)
        while blocks and not blocks[-1]:
            blocks.pop()
        if not blocks:
            continue
        explicit = str(item.get("data-list-item-label") or "")
        if (
            indices_label
            and not explicit
            and not re.fullmatch(r"\d+[.)]?", source_label)
        ):
            explicit = source_label
        marker = f"{number}." if ordered and not explicit else "-"
        blocks = [
            line for block in blocks for line in (block.splitlines() if block else [""])
        ]
        first, *rest = blocks
        first = (
            ORDERED_LIST_PREFIX_PATTERN.sub("", first)
            if ordered
            else UNORDERED_LIST_PREFIX_PATTERN.sub("", first)
        )
        if explicit and not re.fullmatch(r"\d+[.)]?", explicit):
            first = explicit + " " + first
        lines.append(f"{marker} {first}")
        indent = " " * (len(marker) + 1)
        lines.extend(indent + value if value else "" for value in rest)
        number += 1
    if lines:
        lines.append("")
    return lines


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
    if isinstance(node, Tag) and any(
        set(parent.get("class", []))
        & {
            "notes",
            "table-wrap-foot",
            "html-table_foot",
            "data-availability",
            "code-availability",
        }
        for parent in node.parents
        if isinstance(parent, Tag)
    ):
        return None
    # Preserve source links, including wrappers containing linked citations.
    if isinstance(node, Tag) and (node.get("href") or node.find("a", href=True)):
        return None
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
    text, protected = protect_markdown_math(text)
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
    return restore_markdown_math(normalize_text("".join(collapsed)), protected)


def render_clean_text_from_html(
    node: Any, *, collapse_prose_line_breaks: bool = False
) -> str:
    rendered, protected = protect_markdown_math(render_clean_html_node(node))
    rendered = INLINE_IMAGE_SPACING_PATTERN.sub(r" \1", rendered)
    rendered = INLINE_WHITESPACE_PATTERN.sub(" ", rendered)
    rendered = LINE_EDGE_WHITESPACE_PATTERN.sub("\n", rendered)
    rendered = MARKDOWN_BLANK_RUN_PATTERN.sub("\n\n", rendered)
    if collapse_prose_line_breaks:
        rendered = normalize_prose_markdown_line_breaks(rendered)
    return restore_markdown_math(normalize_text(rendered), protected)


def render_retained_text_from_html(node: Any, *, source_url: str = "") -> str:
    """Opt in to links and emphasis for publisher-selected retained content.

    Keep the ordinary block/formula renderer and never mutate the source DOM.
    Publishers remain responsible for removing UI and selecting the section.
    """
    clone = deepcopy(node)
    if isinstance(clone, Tag):
        for link in clone.select("a[href]"):
            link["href"] = urljoin(source_url, str(link["href"]))
    return render_clean_text_from_html(clone, collapse_prose_line_breaks=True)


def render_clean_html_node(node: Any) -> str:
    if node is None or isinstance(node, Comment):
        return ""
    if isinstance(node, NavigableString):
        from ..extraction.html.inline import escape_markdown_text

        return escape_markdown_text(str(node))
    if not isinstance(node, Tag):
        return ""
    if node.get("data-paper-fetch-markdown") is not None:
        return node.get_text("\n\n", strip=False)
    if node.name in HTML_DROP_TAGS:
        return ""
    if _is_mathjax_tex_node(node):
        return _render_html_tex_node(node)
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
    if node.get("data-paper-fetch-markdown") is not None:
        return node.get_text("\n\n", strip=False)
    if (
        node.name == "a"
        and node.get("href")
        and not str(node["href"]).startswith("javascript:")
    ):
        content = deepcopy(node)
        content.name = "span"
        label = render_html_inline_node(
            content, raw_markdown_from_node=_raw_inline_markdown_from_node
        )
        if node["href"] == "#":
            return label
        from urllib.parse import quote

        href = quote(str(node["href"]), safe="/:#?=&%+@;,~!$*'[]")
        return f"[{label}]({href})"
    if node.name == "img" and (
        re.search(r"_IEq\d+", str(node.get("src") or ""), re.I)
        or set(node.get("class", [])) & {"inline-equation", "inline-formula"}
    ):
        return render_markdown_image("formula", "Formula", str(node["src"]))
    if node.name == "img" and (node.get(INLINE_FIGURE_SRC_ATTR) or node.get("src")):
        return render_markdown_image(
            "figure" if node.get(INLINE_FIGURE_SRC_ATTR) else "image",
            str(node.get(INLINE_FIGURE_ALT_ATTR) or node.get("alt") or "Image"),
            str(node.get(INLINE_FIGURE_SRC_ATTR) or node["src"]),
        )
    if _is_mathjax_tex_node(node):
        return _render_html_tex_node(node) or None
    if normalize_text(node.name or "").lower() == "math":
        return _render_mathml_node(node) or None
    if _is_formula_image_node(node):
        return _render_formula_image_node(node) or None
    if _is_formula_container(node):
        return _render_formula_container(node) or None
    return None


def _drop_inline_node(node: Any) -> bool:
    return isinstance(node, Tag) and node.name in HTML_DROP_TAGS


def _render_html_tex_node(node: Tag) -> str:
    from ..extraction.markdown_render.formulas import html_formula_latex_from_node

    latex = html_formula_latex_from_node(node)
    if not latex:
        return ""
    if _is_display_formula_node(node):
        return f"\n\n$$\n{normalize_latex(latex)}\n$$\n\n"
    return _render_inline_latex_markdown(latex)


def _render_clean_inline_node(node: Any) -> str:
    return render_html_inline_node(
        node,
        policy="body",
        citation_payload_from_node=_numeric_citation_payload_from_html,
        raw_markdown_from_node=_raw_inline_markdown_from_node,
        drop_node=_drop_inline_node,
        render_text_styles=True,
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
                    render_text_styles=True,
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


def render_html_fragment_markdown(html_text: str, source_url: str) -> str:
    """Render a publisher-selected fragment with the shared structural renderer."""
    soup = BeautifulSoup(html_text, "lxml")
    for anchor in soup.select("a[href]"):
        if not str(anchor["href"]).startswith("#"):
            anchor["href"] = urljoin(source_url, str(anchor["href"]))
    lines: list[str] = []
    render_container_markdown(
        soup.body or soup, lines, level=2, preserve_heading_levels=True
    )
    return "\n".join(lines)
