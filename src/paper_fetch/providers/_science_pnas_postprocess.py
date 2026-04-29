"""Shared browser-workflow DOM and Markdown post-processing helpers."""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping

from ..extraction.html.shared import (
    append_text_block as _append_text_block,
    short_text as _short_text,
    soup_root as _soup_root,
)
from ..extraction.html.figure_links import inject_inline_figure_links as _shared_inject_inline_figure_links
from ..extraction.html.semantics import BACK_MATTER_TOKENS, heading_category, node_identity_text, normalize_heading
from ..extraction.html.tables import inject_inline_table_blocks as _shared_inject_inline_table_blocks
from ..markdown.citations import clean_citation_markers, normalize_inline_citation_markdown
from ..utils import normalize_text

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None

NUMBERED_SECTION_HEADING_PATTERN = re.compile(r"^\d+(?:\.\d+)*\s+\S")
HEADING_TAG_PATTERN = re.compile(r"^h[1-6]$")
EQUATION_HEADING_JOIN_PATTERN = re.compile(r"(\S)(\*\*Equation\s+\d+[A-Za-z]?\.\*\*)")
DISPLAY_MATH_OPEN_PATTERN = re.compile(r"(?<=\S)(\$\$)")
DISPLAY_MATH_BLOCK_PATTERN = re.compile(r"\$\$\s*(.+?)\s*\$\$", flags=re.DOTALL)
DISPLAY_MATH_TRAILING_PATTERN = re.compile(r"(?<=\$\$)(?=[^\s\n])")
SCIENCE_CITATION_TOKEN_PATTERN = r"(?:\d+[A-Za-z]*|[A-Za-z]+\d+[A-Za-z0-9]*)"
SCIENCE_CITATION_ITALIC_PATTERNS = (
    re.compile(rf"\*(?P<left>{SCIENCE_CITATION_TOKEN_PATTERN})\*\*(?P<sep>[–,;])\*\s*\*(?P<right>{SCIENCE_CITATION_TOKEN_PATTERN})\*"),
    re.compile(rf"\*(?P<left>{SCIENCE_CITATION_TOKEN_PATTERN})\*(?P<sep>\s*[–,;]\s*)\*(?P<right>{SCIENCE_CITATION_TOKEN_PATTERN})\*"),
)


def _heading_nodes(container: Tag) -> list[Tag]:
    return [node for node in container.find_all(HEADING_TAG_PATTERN) if isinstance(node, Tag)]


def _is_frontmatter_wiley_abbreviations_heading(
    container: Tag,
    heading: Tag,
    *,
    headings: list[Tag] | None = None,
) -> bool:
    active_headings = headings if headings is not None else _heading_nodes(container)
    try:
        heading_index = active_headings.index(heading)
    except ValueError:
        return False

    abstract_index = next(
        (index for index, node in enumerate(active_headings) if normalize_heading(_short_text(node)) == "abstract"),
        None,
    )
    first_numbered_body_index = next(
        (
            index
            for index, node in enumerate(active_headings)
            if NUMBERED_SECTION_HEADING_PATTERN.match(normalize_heading(_short_text(node)))
        ),
        None,
    )
    return (
        abstract_index is not None
        and first_numbered_body_index is not None
        and abstract_index < heading_index < first_numbered_body_index
    )


def move_wiley_abbreviations_to_end(container: Tag) -> None:
    soup = _soup_root(container)
    if soup is None:
        return

    headings = _heading_nodes(container)
    heading = next(
        (
            node
            for node in headings
            if normalize_heading(_short_text(node)) == "abbreviations"
            and _is_frontmatter_wiley_abbreviations_heading(container, node, headings=headings)
        ),
        None,
    )
    if heading is None:
        return

    parent = heading.parent if isinstance(heading.parent, Tag) else None
    if parent is None:
        return
    glossary = heading.find_next_sibling()
    if not isinstance(glossary, Tag) or "list-paired" not in node_identity_text(glossary):
        return

    appendix = soup.new_tag("section")
    appendix["class"] = ["article-section__content", "article-section__appendix"]
    appendix_heading = soup.new_tag("h2")
    appendix_heading.string = "Abbreviations"
    appendix.append(appendix_heading)
    glossary_pairs: list[tuple[str, str]] = []
    for row in glossary.select("tr"):
        if not isinstance(row, Tag):
            continue
        cells = [cell for cell in row.find_all(["th", "td"], recursive=False) if isinstance(cell, Tag)]
        if len(cells) < 2:
            cells = [cell for cell in row.find_all(["th", "td"]) if isinstance(cell, Tag)]
        if len(cells) < 2:
            continue
        term = _short_text(cells[0])
        expansion = _short_text(cells[1])
        if term and expansion:
            glossary_pairs.append((term, expansion))
    if glossary_pairs:
        for term, expansion in glossary_pairs:
            _append_text_block(appendix, f"{term}: {expansion}", soup=soup)
        glossary.decompose()
    else:
        appendix.append(glossary.extract())

    target_parent = parent if parent.parent is not None else container
    heading.extract()
    if not _short_text(parent):
        parent.decompose()

    insert_before: Tag | None = None
    for child in target_parent.find_all(recursive=False):
        if child is appendix or not isinstance(child, Tag):
            continue
        child_heading = child.find(HEADING_TAG_PATTERN)
        child_heading_text = _short_text(child_heading) if isinstance(child_heading, Tag) else ""
        if (
            any(token in node_identity_text(child) for token in BACK_MATTER_TOKENS)
            or heading_category("h2", child_heading_text) == "references_or_back_matter"
        ):
            insert_before = child
            break

    if insert_before is not None:
        insert_before.insert_before(appendix)
    else:
        target_parent.append(appendix)


def normalize_equation_markdown_blocks(markdown_text: str) -> str:
    text = EQUATION_HEADING_JOIN_PATTERN.sub(r"\1\n\n\2", markdown_text)
    text = DISPLAY_MATH_OPEN_PATTERN.sub(r"\n\n\1", text)

    def normalize_display_math(match: re.Match[str]) -> str:
        body = match.group(1).strip()
        return f"$$\n{body}\n$$"

    text = DISPLAY_MATH_BLOCK_PATTERN.sub(normalize_display_math, text)
    return DISPLAY_MATH_TRAILING_PATTERN.sub("\n\n", text)


def merge_science_citation_italics(markdown_text: str) -> str:
    def render_separator(separator_text: str) -> str:
        separator = normalize_text(separator_text)
        if separator in {",", ";"}:
            return f"{separator} "
        return separator

    merged = markdown_text
    changed = True
    while changed:
        changed = False
        for pattern in SCIENCE_CITATION_ITALIC_PATTERNS:
            merged, replacements = pattern.subn(
                lambda match: f"*{match.group('left')}{render_separator(match.group('sep'))}{match.group('right')}*",
                merged,
            )
            changed = changed or replacements > 0
    return merged


def inject_inline_figure_links(
    markdown_text: str,
    *,
    figure_assets: list[Mapping[str, Any]] | None,
    clean_markdown_fn: Callable[[str], str],
) -> str:
    return _shared_inject_inline_figure_links(
        markdown_text,
        figure_assets=figure_assets,
        clean_markdown_fn=clean_markdown_fn,
    )


def rewrite_inline_figure_links(
    markdown_text: str,
    *,
    figure_assets: list[Mapping[str, Any]] | None,
    clean_markdown_fn: Callable[[str], str],
) -> str:
    return inject_inline_figure_links(
        markdown_text,
        figure_assets=figure_assets,
        clean_markdown_fn=clean_markdown_fn,
    )


def inject_inline_table_blocks(
    markdown_text: str,
    *,
    table_entries: list[Mapping[str, str]] | None,
    clean_markdown_fn: Callable[[str], str],
) -> str:
    return _shared_inject_inline_table_blocks(
        markdown_text,
        table_entries=table_entries,
        clean_markdown_fn=clean_markdown_fn,
    )


def normalize_browser_workflow_markdown(
    markdown_text: str,
    *,
    markdown_postprocess: Callable[[str], str] | None = None,
) -> str:
    # Shared cleanup runs for every browser-workflow publisher before any
    # provider-specific markdown hook, such as Science citation italic repair.
    normalized = normalize_equation_markdown_blocks(markdown_text)
    normalized = clean_citation_markers(normalized)
    if markdown_postprocess is not None:
        normalized = markdown_postprocess(normalized)
    return normalize_inline_citation_markdown(normalized)
