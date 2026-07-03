"""Formula, table, and block normalization helpers."""

from __future__ import annotations

import re
import os
import urllib.parse
from typing import Any
from collections.abc import Callable

from ...common_patterns import (
    FIGURE_BASENAME_PATTERN,
    FIGURE_LABEL_PATTERN,
    SHORT_FIGURE_BASENAME_PATTERN,
    TABLE_LABEL_PATTERN,
)
from ...extraction.html.inline import (
    normalize_html_inline_text,
    render_html_inline_node,
)
from ...extraction.html.semantics import (
    ABSTRACT_ATTR_TOKENS as ABSTRACT_TOKENS,
    ANCILLARY_TOKENS,
    BACK_MATTER_TOKENS,
    BODY_CONTAINER_TOKENS,
    node_identity_text,
    normalize_heading,
)
from ...extraction.html.shared import (
    attr_text,
    direct_child_tags as _direct_child_tags,
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
from ...markdown.citations import numeric_citation_payload_from_html_node
from ...markdown.images import render_markdown_image
from ...utils import normalize_text
from .._atypon_browser_workflow_profiles import publisher_profile as _publisher_profile
from .formulas import (
    EQUATION_NUMBER_PATTERN,
    _clone_shallow_tag,
    _direct_child_with_parent,
    _display_formula_nodes,
    _display_formula_replacement,
    _equation_label,
    _formula_image_markdown,
    _formula_image_url_from_node,
    _inline_math_replacement_target,
    _insert_split_paragraph,
    _is_display_formula_math,
    _is_non_table_paragraph_node,
    _latex_from_math_node,
    _looks_like_formula_image_node,
    _mathml_element_from_node,
    _normalize_display_formula_blocks,
    _normalize_iop_inline_tex_formula_nodes,
    _normalize_inline_formula_image_nodes,
    _normalize_inline_math_nodes,
    _split_paragraph_display_formula_blocks,
)
from .profile import (
    HEADING_TAG_PATTERN,
    _abstract_nodes,
    _ancestor_identity_text,
    _dedupe_top_level_nodes,
    _is_descendant,
)

from bs4 import NavigableString, Tag


def _normalize_table_inline_text(value: str) -> str:
    return normalize_table_inline_text(value)


def _numeric_citation_payload_from_inline_node(node: Any) -> str | None:
    return numeric_citation_payload_from_html_node(
        node,
        wrapper_tags=("sup", "i", "em"),
    )


def _wrap_table_text_fragment(text: str, marker: str | None) -> str:
    return wrap_table_text_fragment(text, marker)


def _render_table_inline_node(node: Any, *, text_style: str | None = None) -> str:
    return render_table_inline_node(node, text_style=text_style)


def _render_table_inline_text(node: Any) -> str:
    return render_table_inline_text(node)


def _normalize_non_table_inline_text(value: str) -> str:
    return normalize_html_inline_text(value, policy="body")


def _render_non_table_inline_fragment(
    node: Any, *, text_style: str | None = None
) -> str:
    return _render_non_table_inline_node(node, text_style=text_style)


def _render_non_table_inline_node(node: Any, *, text_style: str | None = None) -> str:
    return render_html_inline_node(
        node,
        policy="body",
        text_style=text_style,
        citation_payload_from_node=_numeric_citation_payload_from_inline_node,
        raw_markdown_from_node=_non_table_raw_markdown_from_node,
    )


def _non_table_raw_markdown_from_node(node: Any) -> str | None:
    if (
        isinstance(node, Tag)
        and normalize_text(node.name or "").lower() == "img"
        and _looks_like_formula_image_node(node)
    ):
        return _formula_image_markdown(node)
    return None


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
            and not normalized_fragment.startswith(
                (".", ",", ";", ":", ")", "]", "}", "%", "<br>")
            )
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


def _normalize_non_table_inline_blocks(container: Tag) -> None:
    candidates = [
        node
        for node in container.find_all(["p", "li", "div"])
        if isinstance(node, Tag)
        and node.parent is not None
        and _is_non_table_paragraph_node(node)
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


def _figure_identifier_values(node: Tag) -> list[str]:
    values: list[str] = []

    def append(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                append(item)
            return
        normalized = normalize_text(str(value or ""))
        if normalized and normalized not in values:
            values.append(normalized)

    for attr in ("id", "data-content-id", "data-id"):
        append(node.get(attr))

    for image in node.find_all("img"):
        if not isinstance(image, Tag):
            continue
        for attr in (
            "id",
            "src",
            "data-src",
            "data-lg-src",
            "data-full-size",
            "data-fullsize",
            "data-image-full",
            "data-image-src",
            "data-download-url",
        ):
            append(image.get(attr))
        anchor = image.find_parent("a", href=True)
        current: Any = anchor
        while isinstance(current, Tag):
            if current is node:
                append(anchor.get("href") if isinstance(anchor, Tag) else "")
                break
            current = current.parent if isinstance(current.parent, Tag) else None
        picture = image.find_parent("picture")
        if not isinstance(picture, Tag):
            continue
        for source in picture.find_all("source"):
            if not isinstance(source, Tag):
                continue
            for attr in ("srcset", "data-srcset"):
                raw_srcset = source.get(attr)
                if not raw_srcset:
                    continue
                for part in str(raw_srcset).split(","):
                    append(part.strip().split(None, 1)[0])
    return values


def _figure_label_from_identifier(value: str) -> str:
    raw_value = normalize_text(value)
    if not raw_value:
        return ""
    parsed_path = urllib.parse.urlparse(raw_value).path or raw_value
    basename = normalize_text(
        os.path.basename(urllib.parse.unquote(parsed_path))
    ).lower()
    match = FIGURE_BASENAME_PATTERN.search(
        basename
    ) or SHORT_FIGURE_BASENAME_PATTERN.search(basename)
    if match:
        return f"Figure {match.group(1)}."
    return ""


def _figure_label_from_node_identifier(node: Tag) -> str:
    for value in _figure_identifier_values(node):
        label = _figure_label_from_identifier(value)
        if label:
            return label
    return ""


def _caption_label(node: Tag, *, kind: str) -> str:
    label_pattern = FIGURE_LABEL_PATTERN if kind == "Figure" else TABLE_LABEL_PATTERN
    selectors: tuple[str, ...] = (
        ".figure__title",
        "header .label",
        ".label",
        "figcaption .heading",
        ".caption .heading",
        "figcaption .label",
        "caption .label",
    )
    if kind == "Table":
        selectors = (".tableWrapLabel", *selectors)
    for candidate in (node.select_one(selector) for selector in selectors):
        if isinstance(candidate, Tag):
            text = _short_text(candidate)
            match = label_pattern.search(text)
            if match:
                return f"{kind} {match.group(1)}."
    if kind == "Figure":
        label = _figure_label_from_node_identifier(node)
        if label:
            return label
    caption_text = _caption_text(node)
    match = label_pattern.match(caption_text)
    if match:
        return f"{kind} {match.group(1)}."
    fallback_text = re.sub(
        r"^\s*open\s+in\s+viewer\s+",
        "",
        _short_text(node),
        flags=re.IGNORECASE,
    )
    match = label_pattern.match(fallback_text)
    if match:
        return f"{kind} {match.group(1)}."
    return kind


def _caption_text(node: Tag) -> str:
    for selector in (
        ".figure__caption-text",
        "figcaption",
        ".figure__caption",
        "[role='doc-caption']",
        ".caption",
    ):
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
    for selector in (
        ".tableWrapCaption",
        ".article-table-caption",
        ".caption",
        "figcaption",
        "caption",
        "header",
    ):
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
    for selector in (".tableWrap", ".table-wrap", ".article-table"):
        try:
            matches = container.select(selector)
        except Exception:
            continue
        for match in matches:
            if not isinstance(match, Tag):
                continue
            if _is_glossary_table(match):
                continue
            identity = _ancestor_identity_text(match)
            if any(token in identity for token in BACK_MATTER_TOKENS):
                continue
            if match.find("img") is not None or match.find("table") is not None:
                nodes.append(match)

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


def _is_front_matter_teaser_figure(
    node: Tag, *, abstract_anchor: Tag | None = None
) -> bool:
    if _caption_label(node, kind="Figure") != "Figure":
        return False
    if any(token in _ancestor_identity_text(node) for token in ABSTRACT_TOKENS):
        return True
    if abstract_anchor is None:
        return False
    return abstract_anchor in node.find_all_next()


def _drop_front_matter_teaser_figures(container: Tag) -> None:
    abstract_anchor = _first_abstract_node(container)
    if abstract_anchor is None:
        return
    for node in list(container.find_all("figure")):
        if isinstance(node, Tag) and _is_front_matter_teaser_figure(
            node, abstract_anchor=abstract_anchor
        ):
            node.decompose()


def _drop_table_blocks(container: Tag) -> None:
    for node in list(_table_like_nodes(container)):
        if isinstance(node, Tag):
            node.decompose()


def _figure_like_nodes(
    container: Tag,
    *,
    is_front_matter_teaser_figure: Callable[..., bool] | None = None,
) -> list[Tag]:
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
                match is table_node
                or _is_descendant(match, table_node)
                or _is_descendant(table_node, match)
                for table_node in table_nodes
            ):
                continue
            if (
                is_front_matter_teaser_figure is not None
                and is_front_matter_teaser_figure(
                    match, abstract_anchor=abstract_anchor
                )
            ):
                continue
            identity = _ancestor_identity_text(match)
            if any(token in identity for token in BACK_MATTER_TOKENS):
                continue
            if any(token in identity for token in ANCILLARY_TOKENS) and not any(
                token in identity for token in BODY_CONTAINER_TOKENS
            ):
                continue
            if match.find("table") is not None:
                continue
            if isinstance(match, Tag):
                nodes.append(match)
    return _dedupe_top_level_nodes(nodes)


BOXED_TEXT_LABEL_PATTERN = re.compile(
    r"^(?P<label>Box\s+\d+[A-Za-z]?\.?)\s*(?P<caption>.*)$", flags=re.IGNORECASE
)


def _boxed_text_replacement_target(node: Tag) -> Tag:
    parent = node.parent
    if isinstance(parent, Tag) and "figure-wrap" in node_identity_text(parent):
        return parent
    return node


def _normalize_boxed_text_blocks(container: Tag) -> None:
    soup = _soup_root(container)
    if soup is None:
        return

    seen_targets: set[int] = set()
    for node in list(container.select("figure.boxed-text")):
        if not isinstance(node, Tag) or node.parent is None:
            continue
        target = _boxed_text_replacement_target(node)
        if id(target) in seen_targets or target.parent is None:
            continue
        seen_targets.add(id(target))

        lines: list[str] = []
        caption_node = node.find("figcaption")
        caption = (
            _render_caption_text(caption_node) if isinstance(caption_node, Tag) else ""
        )
        match = BOXED_TEXT_LABEL_PATTERN.match(caption)
        if match is not None:
            label = normalize_text(match.group("label"))
            caption_body = normalize_text(match.group("caption"))
            lines.append(f"**{label}** {caption_body}".strip())
        elif caption:
            lines.append(caption)

        for paragraph in _direct_child_tags(node):
            if attr_text(paragraph.get("role")).lower() != "paragraph":
                continue
            text = _render_non_table_inline_text(paragraph)
            if text:
                lines.append(text)
        if not lines:
            continue

        replacement = soup.new_tag("div")
        for line in lines:
            paragraph = soup.new_tag("p")
            paragraph.string = line
            replacement.append(paragraph)
        target.replace_with(replacement)


def _table_cell_data(cell: Tag) -> dict[str, Any]:
    return table_cell_data(cell, render_inline_text=_render_table_inline_text)


def _table_rows(table: Tag) -> list[list[dict[str, Any]]]:
    return table_rows(table, render_inline_text=_render_table_inline_text)


def _table_header_row_count(table: Tag, rows: list[list[dict[str, Any]]]) -> int:
    return table_header_row_count(table, rows)


def _expanded_table_matrix(
    rows: list[list[dict[str, Any]]],
) -> list[list[dict[str, Any]]] | None:
    return expanded_table_matrix(rows)


def _flatten_table_header_rows(rows: list[list[dict[str, Any]]]) -> list[str]:
    return flatten_table_header_rows(rows)


def _table_headers_and_data(
    table: Tag,
) -> tuple[list[str], list[list[dict[str, Any]]], bool]:
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


def _table_image_url(node: Tag) -> str:
    if not isinstance(node, Tag):
        return ""
    images = [image for image in node.find_all("img") if isinstance(image, Tag)]
    for image in images:
        candidate = normalize_text(
            str(
                image.get("data-full-size")
                or image.get("data-fullsize")
                or image.get("data-image-full")
                or image.get("data-download-url")
                or ""
            )
        )
        if candidate:
            return candidate
    for image in images:
        candidate = normalize_text(
            str(
                image.get("data-src")
                or image.get("data-image-src")
                or image.get("src")
                or ""
            )
        )
        if candidate:
            return candidate
    return ""


def _render_table_image_markdown(node: Tag, *, label: str, caption: str) -> str:
    image_url = _table_image_url(node)
    if not image_url:
        return ""
    heading_parts: list[str] = []
    normalized_label = normalize_text(label)
    normalized_caption = normalize_text(caption)
    if normalized_label:
        heading_parts.append(f"**{normalized_label}**")
    if normalized_caption:
        heading_parts.append(normalized_caption)
    heading_line = " ".join(heading_parts).strip()
    image_line = render_markdown_image("table", normalized_label or "Table", image_url)
    lines = [heading_line, "", image_line] if heading_line else [image_line]
    return "\n".join(lines)


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
            rendered_markdown = _render_table_image_markdown(
                node,
                label=label,
                caption=caption,
            )
        if not rendered_markdown:
            continue
        placeholder = _table_placeholder(len(entries) + 1)
        block = soup.new_tag("p")
        block.string = placeholder
        node.replace_with(block)
        entries.append({"placeholder": placeholder, "markdown": rendered_markdown})
    return entries


def _normalize_figure_blocks(container: Tag, publisher: str) -> None:
    soup = _soup_root(container)
    if soup is None:
        return
    profile = _publisher_profile(publisher)
    for node in _figure_like_nodes(
        container,
        is_front_matter_teaser_figure=profile.is_front_matter_teaser_figure,
    ):
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
    profile = _publisher_profile(publisher)
    hook = profile.dom_hooks.before_block_normalization
    if hook is not None:
        hook(container)
    _normalize_abstract_blocks(container)
    _normalize_display_formula_blocks(container)
    if normalize_text(publisher).lower() == "iop":
        _normalize_iop_inline_tex_formula_nodes(container)
    _normalize_inline_math_nodes(container)
    _normalize_inline_formula_image_nodes(container)
    _normalize_boxed_text_blocks(container)
    table_entries = _normalize_table_blocks(container)
    _normalize_figure_blocks(container, publisher)
    _normalize_non_table_inline_blocks(container)
    hook = profile.dom_hooks.after_block_normalization
    if hook is not None:
        hook(container)
    return table_entries


__all__ = [
    "EQUATION_NUMBER_PATTERN",
    "FIGURE_LABEL_PATTERN",
    "TABLE_LABEL_PATTERN",
    "_caption_label",
    "_caption_text",
    "_clone_shallow_tag",
    "_direct_child_with_parent",
    "_display_formula_nodes",
    "_display_formula_replacement",
    "_drop_front_matter_teaser_figures",
    "_drop_table_blocks",
    "_equation_label",
    "_escape_markdown_table_cell",
    "_expanded_table_matrix",
    "_figure_like_nodes",
    "_first_abstract_node",
    "_flatten_table_header_rows",
    "_formula_image_markdown",
    "_formula_image_url_from_node",
    "_inline_math_replacement_target",
    "_insert_split_paragraph",
    "_is_display_formula_math",
    "_is_front_matter_teaser_figure",
    "_is_glossary_table",
    "_is_non_table_paragraph_node",
    "_join_non_table_text_fragments",
    "_latex_from_math_node",
    "_looks_like_formula_image_node",
    "_mathml_element_from_node",
    "_normalize_abstract_blocks",
    "_normalize_boxed_text_blocks",
    "_normalize_display_formula_blocks",
    "_normalize_figure_blocks",
    "_normalize_inline_formula_image_nodes",
    "_normalize_inline_math_nodes",
    "_normalize_iop_inline_tex_formula_nodes",
    "_normalize_non_table_inline_blocks",
    "_normalize_non_table_inline_text",
    "_normalize_special_blocks",
    "_normalize_table_blocks",
    "_normalize_table_inline_text",
    "_numeric_citation_payload_from_inline_node",
    "_render_aligned_markdown_table",
    "_render_caption_text",
    "_render_non_table_inline_fragment",
    "_render_non_table_inline_node",
    "_render_non_table_inline_text",
    "_render_table_inline_node",
    "_render_table_inline_text",
    "_render_table_markdown",
    "_split_paragraph_display_formula_blocks",
    "_strip_caption_label",
    "_table_caption_text",
    "_table_cell_data",
    "_table_header_row_count",
    "_table_headers_and_data",
    "_table_like_nodes",
    "_table_placeholder",
    "_table_rows",
    "_wrap_table_text_fragment",
]
