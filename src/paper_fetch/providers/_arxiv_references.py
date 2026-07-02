"""arXiv reference extraction and semantic block rendering."""

from __future__ import annotations

import copy
from typing import Any
import re

from ..extraction.html.semantics import SECTION_HEADING_PATTERN
from ..extraction.html.tables import render_table_markdown, table_placeholder
from ..models.markdown import normalize_markdown_text
from ..utils import normalize_text
from ._arxiv_html import (
    ArxivSemanticPreparation,
    Tag,
    _arxiv_ar5iv_selectors,
    _arxiv_node_classes,
    _arxiv_node_has_class,
    _arxiv_select,
    _arxiv_select_one,
)
from ._html_section_markdown import (
    render_clean_text_from_html,
    render_heading_text_from_html,
)
from ._reference_doi import reference_doi_match as _reference_doi_match

_REFERENCE_YEAR_PATTERN = re.compile(r"\b((?:18|19|20)\d{2})\b")
_ARXIV_TABLE_ID_PATTERN = re.compile(
    r"(?:^|[.])T(?P<number>\d+[A-Za-z]?)\b", flags=re.IGNORECASE
)
_ARXIV_ALGORITHM_ID_PATTERN = re.compile(
    r"(?:^|[.])algorithm(?P<number>\d+)\b", flags=re.IGNORECASE
)
_ARXIV_CAPTION_LABEL_PATTERN = re.compile(
    r"^(?P<label>(?:Table|Algorithm)\s+\d+[A-Za-z]?)[.:]?\s*(?P<caption>.*)$",
    flags=re.IGNORECASE,
)


def _extract_reference_doi(node: Any) -> str | None:
    if not isinstance(node, Tag):
        return None
    for anchor in node.find_all("a", href=True):
        href = normalize_text(str(anchor.get("href") or ""))
        match = _reference_doi_match(href)
        if match is not None:
            return normalize_text(match.group(0).rstrip(").,;"))
    text = normalize_text(node.get_text(" ", strip=True))
    match = _reference_doi_match(text)
    if match is None:
        return None
    return normalize_text(match.group(0).rstrip(").,;"))


def _extract_reference_year(text: str, node: Any) -> str | None:
    if isinstance(node, Tag):
        year_node = _arxiv_select_one(node, "reference_year")
        year_text = normalize_text(
            year_node.get_text(" ", strip=True) if isinstance(year_node, Tag) else ""
        )
        year_match = _REFERENCE_YEAR_PATTERN.search(year_text)
        if year_match is not None:
            return year_match.group(1)
    matches = list(_REFERENCE_YEAR_PATTERN.finditer(text))
    return matches[-1].group(1) if matches else None


def _extract_reference_title(node: Any) -> str | None:
    if not isinstance(node, Tag):
        return None
    title_node = _arxiv_select_one(node, "reference_title")
    title = normalize_text(
        title_node.get_text(" ", strip=True) if isinstance(title_node, Tag) else ""
    )
    return title or None


def _clean_arxiv_reference_node(node: Any) -> Any:
    if not isinstance(node, Tag):
        return None
    clone = copy.deepcopy(node)
    if not isinstance(clone, Tag):
        return None

    for selector in _arxiv_ar5iv_selectors("reference_noise"):
        for match in clone.select(selector):
            match.decompose()
    for block in _arxiv_select(clone, "reference_blocks"):
        block_text = normalize_text(block.get_text(" ", strip=True)).lower()
        if _arxiv_select_one(block, "reference_links") is not None:
            block.decompose()
            continue
        if block_text.startswith(("external links", "cited by")):
            block.decompose()
    return clone


def _normalize_reference_text(text: str) -> str:
    normalized = normalize_text(text)
    normalized = re.sub(r"\s+([,.;:)])", r"\1", normalized)
    normalized = re.sub(r"([(])\s+", r"\1", normalized)
    return normalize_text(normalized)


def _arxiv_reference_text(node: Any) -> str:
    clone = _clean_arxiv_reference_node(node)
    if not isinstance(clone, Tag):
        return ""
    return _normalize_reference_text(clone.get_text(" ", strip=True))


def _candidate_arxiv_bibliography_containers(root: Any) -> list[Any]:
    if not isinstance(root, Tag):
        return []
    containers: list[Any] = []
    seen: set[int] = set()
    for selector in _arxiv_ar5iv_selectors("bibliography_containers"):
        for container in root.select(selector):
            if isinstance(container, Tag) and id(container) not in seen:
                seen.add(id(container))
                containers.append(container)
    if containers:
        return containers
    for candidate in root.find_all(["section", "div"]):
        if not isinstance(candidate, Tag):
            continue
        heading = candidate.find(SECTION_HEADING_PATTERN)
        if not isinstance(heading, Tag):
            continue
        title = (
            normalize_text(render_heading_text_from_html(heading)).lower().strip(" .:")
        )
        if title in {"references", "bibliography"} and id(candidate) not in seen:
            seen.add(id(candidate))
            containers.append(candidate)
    return containers


def _candidate_arxiv_bibitems(root: Any) -> list[Any]:
    if not isinstance(root, Tag):
        return []
    containers = _candidate_arxiv_bibliography_containers(root)
    scopes = containers or [root]

    items: list[Any] = []
    seen_items: set[int] = set()
    for scope in scopes:
        for selector in _arxiv_ar5iv_selectors("bibliography_items"):
            for item in scope.select(selector):
                if isinstance(item, Tag) and id(item) not in seen_items:
                    seen_items.add(id(item))
                    items.append(item)
        if items:
            continue
        for item in scope.find_all("li"):
            if isinstance(item, Tag) and id(item) not in seen_items:
                seen_items.add(id(item))
                items.append(item)
    return items


def _extract_arxiv_html_references(root: Any) -> list[dict[str, str | None]]:
    references: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for node in _candidate_arxiv_bibitems(root):
        raw = _arxiv_reference_text(node)
        if not raw or raw in seen:
            continue
        seen.add(raw)
        references.append(
            {
                "raw": raw,
                "doi": _extract_reference_doi(node),
                "title": _extract_reference_title(node),
                "year": _extract_reference_year(raw, node),
            }
        )
    return references


def _is_arxiv_table_figure(node: Any) -> bool:
    return (
        isinstance(node, Tag)
        and node.name == "figure"
        and _arxiv_node_has_class(node, "ltx_table")
        and node.find("table") is not None
    )


def _is_arxiv_tabular_table(node: Any) -> bool:
    return (
        isinstance(node, Tag)
        and node.name == "table"
        and _arxiv_node_has_class(node, "ltx_tabular")
    )


def _is_arxiv_listing_node(node: Any) -> bool:
    return (
        isinstance(node, Tag)
        and node.name == "div"
        and _arxiv_node_has_class(node, "ltx_listing")
    )


def _is_arxiv_algorithm_figure(node: Any) -> bool:
    if not isinstance(node, Tag) or node.name != "figure":
        return False
    classes = _arxiv_node_classes(node)
    if "ltx_algorithm" not in classes and "ltx_float" not in classes:
        return False
    return _arxiv_select_one(node, "algorithm_listing") is not None


def _is_arxiv_inline_figure_container(node: Any) -> bool:
    if not isinstance(node, Tag) or node.name != "figure":
        return False
    classes = _arxiv_node_classes(node)
    if classes.intersection(
        {"ltx_table", "ltx_algorithm", "ltx_equation", "ltx_listing"}
    ):
        return False
    return not _is_arxiv_table_figure(node) and not _is_arxiv_algorithm_figure(node)


def _arxiv_parent_identities(node: Any) -> set[int]:
    identities: set[int] = set()
    current = getattr(node, "parent", None)
    while isinstance(current, Tag):
        identities.add(id(current))
        current = getattr(current, "parent", None)
    return identities


def _arxiv_topmost_figure_ancestor(node: Any, article: Any) -> Any:
    if not isinstance(node, Tag):
        return None
    topmost = None
    current = getattr(node, "parent", None)
    while isinstance(current, Tag) and current is not article:
        if current.name == "figure":
            topmost = current
        current = getattr(current, "parent", None)
    return topmost


def _replace_arxiv_semantic_node_with_placeholder(
    node: Any, article: Any, soup: Any, placeholder: str
) -> None:
    if not isinstance(node, Tag):
        return
    placeholder_node = soup.new_string(f"\n\n{placeholder}\n\n")
    if node.name == "figure":
        node.replace_with(placeholder_node)
        return
    figure_anchor = _arxiv_topmost_figure_ancestor(node, article)
    if isinstance(figure_anchor, Tag):
        figure_anchor.insert_before(placeholder_node)
        node.decompose()
        return
    node.replace_with(placeholder_node)


def _arxiv_label_from_identifier(node: Any, *, default_label: str) -> str:
    if not isinstance(node, Tag):
        return default_label
    current: Any = node
    while isinstance(current, Tag):
        node_id = normalize_text(str(current.get("id") or ""))
        table_match = _ARXIV_TABLE_ID_PATTERN.search(node_id)
        if table_match is not None and default_label.lower() == "table":
            return f"Table {table_match.group('number')}."
        algorithm_match = _ARXIV_ALGORITHM_ID_PATTERN.search(node_id)
        if algorithm_match is not None and default_label.lower() == "algorithm":
            return f"Algorithm {algorithm_match.group('number')}."
        current = getattr(current, "parent", None)
    return default_label


def _normalize_arxiv_caption_text(text: str) -> str:
    return normalize_text(str(text or "").replace("\n", " "))


def _arxiv_caption_label_and_text(node: Any, *, default_label: str) -> tuple[str, str]:
    caption = ""
    if isinstance(node, Tag):
        caption_node = node.find("figcaption")
        if isinstance(caption_node, Tag):
            caption = _normalize_arxiv_caption_text(
                render_clean_text_from_html(caption_node)
            )
    label = _arxiv_label_from_identifier(node, default_label=default_label)
    if caption:
        match = _ARXIV_CAPTION_LABEL_PATTERN.match(caption)
        if match is not None and match.group("label").lower().startswith(
            default_label.lower()
        ):
            raw_label = normalize_text(match.group("label"))
            number = raw_label.split(None, 1)[1] if " " in raw_label else ""
            label = f"{default_label} {number}.".strip() if number else label
            caption = _normalize_arxiv_caption_text(match.group("caption"))
    return label, caption


def _arxiv_table_markdown_has_body(markdown_text: str) -> bool:
    normalized = normalize_text(markdown_text)
    if not normalized:
        return False
    lines = [
        line.strip() for line in markdown_text.splitlines() if normalize_text(line)
    ]
    return any(line.startswith("|") for line in lines) or any(
        line.startswith("- ") for line in lines
    )


def _arxiv_table_markdown_is_key_value_fallback(markdown_text: str) -> bool:
    lines = [
        line.strip() for line in markdown_text.splitlines() if normalize_text(line)
    ]
    return any(line.startswith("- ") for line in lines) and not any(
        line.startswith("|") for line in lines
    )


def _render_arxiv_table_block(node: Any) -> tuple[str, bool, bool]:
    if not isinstance(node, Tag):
        return "", False, False
    label, caption = _arxiv_caption_label_and_text(node, default_label="Table")
    if label == "Table" and not caption:
        label = ""
    markdown = render_table_markdown(
        node,
        label=label,
        caption=caption,
        render_inline_text=render_clean_text_from_html,
    )
    rendered = _arxiv_table_markdown_has_body(markdown)
    return (
        normalize_markdown_text(markdown),
        rendered,
        _arxiv_table_markdown_is_key_value_fallback(markdown),
    )


def _clean_arxiv_listing_line_node(line_node: Any) -> Any:
    if not isinstance(line_node, Tag):
        return None
    clone = copy.deepcopy(line_node)
    if not isinstance(clone, Tag):
        return None
    for selector in _arxiv_ar5iv_selectors("listing_noise"):
        for node in clone.select(selector):
            node.decompose()
    return clone


def _render_arxiv_listing_lines(listing_node: Any) -> list[str]:
    if not isinstance(listing_node, Tag):
        return []
    lines: list[str] = []
    for line_node in _arxiv_select(listing_node, "listing_lines"):
        clone = _clean_arxiv_listing_line_node(line_node)
        text = render_clean_text_from_html(clone) if clone is not None else ""
        text = normalize_text(text.replace("\n", " "))
        if text:
            lines.append(text)
    if lines:
        return lines
    text = normalize_text(render_clean_text_from_html(listing_node).replace("\n", "\n"))
    return [line for line in text.splitlines() if normalize_text(line)]


def _render_arxiv_listing_block(node: Any) -> tuple[str, bool]:
    if not isinstance(node, Tag):
        return "", False
    listing = (
        _arxiv_select_one(node, "algorithm_listing") if node.name == "figure" else node
    )
    if not isinstance(listing, Tag):
        return "", False
    label, caption = _arxiv_caption_label_and_text(node, default_label="Algorithm")
    heading_line = f"**{label}** {caption}".strip()
    code_lines = _render_arxiv_listing_lines(listing)
    if not code_lines:
        return normalize_markdown_text(heading_line), False
    escaped_lines = [line.replace("```", "'''") for line in code_lines]
    return normalize_markdown_text(
        "\n".join([heading_line, "", "```text", *escaped_lines, "```"])
    ), True


def _prepare_arxiv_semantic_blocks(article: Any, soup: Any) -> ArxivSemanticPreparation:
    if not isinstance(article, Tag):
        return ArxivSemanticPreparation(entries=[], diagnostics={}, warnings=[])

    entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    selected_ancestor_ids: set[int] = set()
    table_total = 0
    listing_total = 0
    table_rendered = 0
    listing_rendered = 0
    table_key_value_fallback = 0
    semantic_loss_count = 0

    for node in list(article.find_all(True)):
        if id(node) in selected_ancestor_ids or selected_ancestor_ids.intersection(
            _arxiv_parent_identities(node)
        ):
            continue

        kind = ""
        markdown = ""
        rendered = False
        key_value_fallback = False
        if _is_arxiv_algorithm_figure(node):
            kind = "listing"
            listing_total += 1
            markdown, rendered = _render_arxiv_listing_block(node)
        elif _is_arxiv_table_figure(node):
            kind = "table"
            table_total += 1
            markdown, rendered, key_value_fallback = _render_arxiv_table_block(node)
        elif _is_arxiv_tabular_table(node) and not any(
            _is_arxiv_table_figure(parent) for parent in node.parents
        ):
            kind = "table"
            table_total += 1
            markdown, rendered, key_value_fallback = _render_arxiv_table_block(node)
        elif _is_arxiv_listing_node(node) and not any(
            _is_arxiv_algorithm_figure(parent) for parent in node.parents
        ):
            kind = "listing"
            listing_total += 1
            markdown, rendered = _render_arxiv_listing_block(node)

        if not kind:
            continue
        if not rendered:
            semantic_loss_count += 1
            warnings.append(
                f"arXiv HTML {kind} block could not be rendered with semantic content."
            )
            continue

        placeholder = table_placeholder(len(entries))
        entries.append(
            {
                "kind": kind,
                "placeholder": placeholder,
                "markdown": markdown,
                "key_value_fallback": key_value_fallback,
            }
        )
        if kind == "table":
            table_rendered += 1
            if key_value_fallback:
                table_key_value_fallback += 1
        else:
            listing_rendered += 1
        selected_ancestor_ids.add(id(node))
        _replace_arxiv_semantic_node_with_placeholder(node, article, soup, placeholder)

    diagnostics = {
        "table_block_count": table_total,
        "table_block_rendered_count": table_rendered,
        "table_key_value_fallback_count": table_key_value_fallback,
        "listing_block_count": listing_total,
        "listing_block_rendered_count": listing_rendered,
        "semantic_block_count": table_total + listing_total,
        "semantic_block_rendered_count": table_rendered + listing_rendered,
        "semantic_block_loss_count": semantic_loss_count,
    }
    return ArxivSemanticPreparation(
        entries=entries, diagnostics=diagnostics, warnings=warnings
    )
