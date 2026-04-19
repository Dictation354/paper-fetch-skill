"""Shared browser-workflow DOM and Markdown post-processing helpers."""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping

from ..models import normalize_markdown_text
from ..utils import normalize_text
from ._html_availability import BACK_MATTER_TOKENS, _heading_category, _normalize_heading, node_identity_text
from ._html_citations import clean_citation_markers
from ._html_tables import inject_inline_table_blocks as _shared_inject_inline_table_blocks

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None

FIGURE_LABEL_PATTERN = re.compile(r"\bfig(?:ure)?\.?\s*(\d+[A-Za-z]?)\b", flags=re.IGNORECASE)
MARKDOWN_FIGURE_BLOCK_PATTERN = re.compile(r"^\*\*(Figure\s+\d+[A-Za-z]?\.?)\*\*(?:\s+.*)?$", flags=re.IGNORECASE)
MARKDOWN_IMAGE_BLOCK_PATTERN = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")


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


def move_wiley_abbreviations_to_end(container: Tag) -> None:
    soup = _soup_root(container)
    if soup is None:
        return
    headings = [
        node
        for node in container.find_all(re.compile(r"^h[1-6]$"))
        if _normalize_heading(_short_text(node)) == "abbreviations"
    ]
    if not headings:
        return

    heading = headings[0]
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
            or _heading_category("h2", child_heading_text) == "references_or_back_matter"
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


def _canonical_figure_label(text: str) -> str | None:
    normalized = normalize_text(text)
    if not normalized:
        return None
    match = FIGURE_LABEL_PATTERN.search(normalized)
    if not match:
        return None
    return f"figure {match.group(1).lower()}"


def _inline_figure_markdown_entries(
    figure_assets: list[Mapping[str, Any]] | None,
) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for asset in figure_assets or []:
        url = normalize_text(
            str(
                asset.get("path")
                or asset.get("full_size_url")
                or asset.get("url")
                or asset.get("preview_url")
                or asset.get("source_url")
                or asset.get("original_url")
                or ""
            )
        )
        if not url:
            continue
        aliases: list[str] = []
        for field in ("full_size_url", "url", "preview_url", "source_url", "original_url", "path"):
            candidate = normalize_text(str(asset.get(field) or ""))
            if candidate and candidate not in aliases:
                aliases.append(candidate)
        entries.append(
            {
                "url": url,
                "heading": normalize_text(str(asset.get("heading") or "Figure")) or "Figure",
                "label_key": _canonical_figure_label(
                    normalize_text(str(asset.get("heading") or ""))
                    or normalize_text(str(asset.get("caption") or ""))
                )
                or "",
                "aliases": "\n".join(aliases),
            }
        )
    return entries


def inject_inline_figure_links(
    markdown_text: str,
    *,
    figure_assets: list[Mapping[str, Any]] | None,
    clean_markdown_fn: Callable[[str], str],
) -> str:
    entries = _inline_figure_markdown_entries(figure_assets)
    if not entries:
        return markdown_text
    has_labeled_entries = any(entry.get("label_key") for entry in entries)

    blocks = [normalize_markdown_text(block) for block in re.split(r"\n\s*\n", markdown_text) if normalize_text(block)]
    if not blocks:
        return markdown_text

    injected: list[str] = []
    figure_index = 0
    used_entry_indexes: set[int] = set()
    indexed_entries_by_label: dict[str, list[int]] = {}
    indexed_entries_by_url: dict[str, list[int]] = {}
    for index, entry in enumerate(entries):
        label_key = normalize_text(entry.get("label_key") or "").lower()
        if label_key:
            indexed_entries_by_label.setdefault(label_key, []).append(index)
        for candidate in normalize_text(entry.get("aliases") or "").split("\n"):
            normalized_candidate = normalize_text(candidate)
            if normalized_candidate:
                indexed_entries_by_url.setdefault(normalized_candidate, []).append(index)

    def take_entry(index: int) -> dict[str, str] | None:
        nonlocal figure_index
        if index in used_entry_indexes:
            return None
        used_entry_indexes.add(index)
        if index >= figure_index:
            figure_index = index + 1
        return entries[index]

    def take_entry_for_label(label_key: str | None) -> dict[str, str] | None:
        nonlocal figure_index
        normalized_label = normalize_text(label_key or "").lower()
        if normalized_label and has_labeled_entries:
            for index in indexed_entries_by_label.get(normalized_label, []):
                entry = take_entry(index)
                if entry is not None:
                    return entry
            return None
        while figure_index < len(entries):
            index = figure_index
            figure_index += 1
            entry = take_entry(index)
            if entry is not None:
                return entry
        return None

    def take_entry_for_image(alt_text: str | None, url: str | None) -> dict[str, str] | None:
        normalized_url = normalize_text(url)
        if normalized_url:
            for index in indexed_entries_by_url.get(normalized_url, []):
                entry = take_entry(index)
                if entry is not None:
                    return entry
        return take_entry_for_label(_canonical_figure_label(normalize_text(alt_text or "")))

    for block in blocks:
        normalized_block = normalize_text(block)
        image_match = MARKDOWN_IMAGE_BLOCK_PATTERN.match(normalized_block)
        if image_match:
            alt_text = normalize_text(image_match.group(1))
            current_url = normalize_text(image_match.group(2))
            entry = take_entry_for_image(alt_text, current_url)
            if entry is not None:
                heading = alt_text or normalize_text(entry.get("heading") or "Figure") or "Figure"
                injected.append(f"![{heading}]({entry['url']})")
            else:
                injected.append(block)
            continue
        match = MARKDOWN_FIGURE_BLOCK_PATTERN.match(normalized_block)
        if match:
            label = match.group(1).rstrip(".")
            entry = take_entry_for_label(_canonical_figure_label(label))
            if entry is not None:
                image_block = f"![{label}]({entry['url']})"
                if not injected or normalize_text(injected[-1]) != image_block:
                    injected.append(image_block)
                injected.append(block)
                continue
        injected.append(block)
    return clean_markdown_fn("\n\n".join(injected))


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
    normalized = normalize_equation_markdown_blocks(markdown_text)
    normalized = clean_citation_markers(normalized)
    if markdown_postprocess is not None:
        normalized = markdown_postprocess(normalized)
    return normalized
