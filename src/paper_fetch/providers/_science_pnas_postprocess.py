"""Shared browser-workflow DOM and Markdown post-processing helpers."""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping

from ..extraction.html.figure_links import inject_inline_figure_links as _shared_inject_inline_figure_links
from ..extraction.html.semantics import BACK_MATTER_TOKENS, heading_category, node_identity_text, normalize_heading
from ..markdown.citations import clean_citation_markers, normalize_inline_citation_markdown
from ..utils import normalize_text
from ._html_tables import inject_inline_table_blocks as _shared_inject_inline_table_blocks

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None

NUMBERED_SECTION_HEADING_PATTERN = re.compile(r"^\d+(?:\.\d+)*\s+\S")


def _soup_root(node: Tag | None) -> BeautifulSoup | None:
    current = node
    while current is not None:
        if isinstance(current, BeautifulSoup):
            return current
        current = current.parent if isinstance(current.parent, Tag) or isinstance(current.parent, BeautifulSoup) else None
    return None


def _short_text(node: Tag | None) -> str:
    if node is None:
        return ""
    return normalize_text(node.get_text(" ", strip=True))


def _append_text_block(parent: Tag, text: str, *, tag_name: str = "p", soup: BeautifulSoup | None = None) -> None:
    root = soup or _soup_root(parent)
    if root is None:
        return
    block = root.new_tag(tag_name)
    block.string = normalize_text(text)
    parent.append(block)


def _heading_nodes(container: Tag) -> list[Tag]:
    return [node for node in container.find_all(re.compile(r"^h[1-6]$")) if isinstance(node, Tag)]


def _is_frontmatter_wiley_abbreviations_heading(container: Tag, heading: Tag) -> bool:
    headings = _heading_nodes(container)
    try:
        heading_index = headings.index(heading)
    except ValueError:
        return False

    abstract_index = next(
        (index for index, node in enumerate(headings) if normalize_heading(_short_text(node)) == "abstract"),
        None,
    )
    first_numbered_body_index = next(
        (
            index
            for index, node in enumerate(headings)
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

    heading = next(
        (
            node
            for node in _heading_nodes(container)
            if normalize_heading(_short_text(node)) == "abbreviations"
            and _is_frontmatter_wiley_abbreviations_heading(container, node)
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
        child_heading = child.find(re.compile(r"^h[1-6]$"))
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
    text = re.sub(r"(\S)(\*\*Equation\s+\d+[A-Za-z]?\.\*\*)", r"\1\n\n\2", markdown_text)
    text = re.sub(r"(?<=\S)(\$\$)", r"\n\n\1", text)

    def normalize_display_math(match: re.Match[str]) -> str:
        body = match.group(1).strip()
        return f"$$\n{body}\n$$"

    text = re.sub(r"\$\$\s*(.+?)\s*\$\$", normalize_display_math, text, flags=re.DOTALL)
    return re.sub(r"(?<=\$\$)(?=[^\s\n])", "\n\n", text)


def merge_science_citation_italics(markdown_text: str) -> str:
    token_pattern = r"(?:\d+[A-Za-z]*|[A-Za-z]+\d+[A-Za-z0-9]*)"
    patterns = (
        re.compile(rf"\*(?P<left>{token_pattern})\*\*(?P<sep>[–,;])\*\s*\*(?P<right>{token_pattern})\*"),
        re.compile(rf"\*(?P<left>{token_pattern})\*(?P<sep>\s*[–,;]\s*)\*(?P<right>{token_pattern})\*"),
    )

    def render_separator(separator_text: str) -> str:
        separator = normalize_text(separator_text)
        if separator in {",", ";"}:
            return f"{separator} "
        return separator

    merged = markdown_text
    changed = True
    while changed:
        changed = False
        for pattern in patterns:
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
