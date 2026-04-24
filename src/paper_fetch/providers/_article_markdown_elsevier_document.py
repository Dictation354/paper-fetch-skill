"""Document assembly for Elsevier XML-derived article Markdown."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import xml.etree.ElementTree as ET

from ..models import Reference, SemanticLosses
from ..publisher_identity import extract_doi, normalize_doi
from ._article_markdown_common import (
    child_text,
    collect_conversion_notes,
    first_child,
    first_descendant,
    make_markdown_path,
    normalize_lines,
    normalize_text,
    path_relative_to,
    render_figure_block,
    render_table_block,
    xml_local_name,
)
from ._article_markdown_elsevier import (
    elsevier_figure_registry,
    elsevier_supplement_entries,
    elsevier_table_registry,
    render_elsevier_blocks,
)
from ..utils import dedupe_authors


@dataclass
class ArticleStructure:
    title: str
    doi: str
    journal_title: str
    published: str
    landing_page: str
    authors: list[str]
    xml_path: Path
    abstract_lines: list[str]
    body_lines: list[str]
    figure_entries: list[dict[str, Any]]
    table_entries: list[dict[str, Any]]
    supplement_entries: list[dict[str, str]]
    conversion_notes: list[str]
    references: list[Reference]
    semantic_losses: SemanticLosses
    used_figure_keys: set[str]
    used_table_keys: set[str]


def _iter_elements_by_local_name(root: ET.Element, local_name: str) -> list[ET.Element]:
    return [
        element
        for element in root.iter()
        if isinstance(element.tag, str) and xml_local_name(element.tag) == local_name
    ]


def _extract_author_name(author_node: ET.Element) -> str:
    given_name = normalize_text(child_text(author_node, "given-name"))
    surname = normalize_text(child_text(author_node, "surname"))
    if given_name or surname:
        return normalize_text(" ".join(item for item in (given_name, surname) if item))
    indexed_name = normalize_text(child_text(author_node, "indexed-name"))
    if indexed_name:
        return indexed_name
    return normalize_text(child_text(author_node, "collaboration"))


def extract_article_authors(root: ET.Element) -> list[str]:
    authors: list[str] = []
    for author_group in _iter_elements_by_local_name(root, "author-group"):
        for child in list(author_group):
            if not isinstance(child.tag, str):
                continue
            local_name = xml_local_name(child.tag)
            if local_name == "author":
                author_name = _extract_author_name(child)
                if author_name:
                    authors.append(author_name)
            elif local_name == "collaboration":
                collaboration_name = normalize_text("".join(child.itertext()))
                if collaboration_name:
                    authors.append(collaboration_name)
    return dedupe_authors(authors)


def _child_text(element: ET.Element | None, local_name: str) -> str:
    return normalize_text(child_text(element, local_name))


def _first_descendant_text(element: ET.Element | None, local_name: str) -> str:
    node = first_descendant(element, local_name)
    return normalize_text("".join(node.itertext())) if node is not None else ""


def _extract_reference_authors(contribution: ET.Element | None) -> list[str]:
    authors_node = first_child(contribution, "authors")
    if authors_node is None:
        return []

    authors: list[str] = []
    for child in list(authors_node):
        if not isinstance(child.tag, str):
            continue
        local_name = xml_local_name(child.tag)
        if local_name == "author":
            author_name = _extract_author_name(child)
            if author_name:
                authors.append(author_name)
            continue
        if local_name == "collaboration":
            collaboration_name = normalize_text("".join(child.itertext()))
            if collaboration_name:
                authors.append(collaboration_name)
    return dedupe_authors(authors)


def _extract_reference_title(contribution: ET.Element | None) -> str:
    title_node = first_child(contribution, "title")
    return _child_text(title_node, "maintitle") or _first_descendant_text(contribution, "maintitle")


def _extract_reference_source(host: ET.Element | None) -> str:
    series_node = first_descendant(host, "series")
    title_node = first_child(series_node, "title")
    return _child_text(title_node, "maintitle") or _first_descendant_text(host, "maintitle")


def _format_reference_body(
    *,
    authors: list[str],
    title: str,
    source: str,
    volume: str,
    issue: str,
    year: str,
    first_page: str,
    last_page: str,
    doi: str,
    source_text: str,
) -> str:
    parts: list[str] = []
    if authors:
        parts.append(", ".join(authors))
    if year:
        parts.append(year)
    if title:
        parts.append(title)

    publication = source
    if volume:
        publication = f"{publication}, {volume}" if publication else volume
    if issue:
        publication = f"{publication}({issue})" if publication else f"({issue})"
    pages = ""
    if first_page and last_page:
        pages = f"{first_page}-{last_page}"
    elif first_page:
        pages = first_page
    if pages:
        publication = f"{publication}: {pages}" if publication else pages
    if publication:
        parts.append(publication)
    if doi:
        parts.append(doi)

    body = ". ".join(part.rstrip(".") for part in parts if part).strip()
    return body or source_text


def extract_elsevier_references(root: ET.Element) -> list[Reference]:
    references: list[Reference] = []
    for index, bib_reference in enumerate(_iter_elements_by_local_name(root, "bib-reference"), start=1):
        label = _child_text(bib_reference, "label")
        sb_reference = first_child(bib_reference, "reference")
        if sb_reference is None:
            sb_reference = first_descendant(bib_reference, "reference")
        contribution = first_child(sb_reference, "contribution")
        host = first_child(sb_reference, "host")
        source_text = _child_text(bib_reference, "source-text")
        doi = normalize_doi(_first_descendant_text(sb_reference, "doi")) or (extract_doi(source_text) or "")
        title = _extract_reference_title(contribution)
        year = _first_descendant_text(host, "date")
        body = _format_reference_body(
            authors=_extract_reference_authors(contribution),
            title=title,
            source=_extract_reference_source(host),
            volume=_first_descendant_text(host, "volume-nr"),
            issue=_first_descendant_text(host, "issue-nr"),
            year=year,
            first_page=_first_descendant_text(host, "first-page"),
            last_page=_first_descendant_text(host, "last-page"),
            doi=doi,
            source_text=source_text,
        )
        if not body:
            continue
        raw = f"{index}. {body}"
        if label and not body.startswith(label):
            raw = f"{raw} [{label}]"
        references.append(
            Reference(
                raw=raw,
                doi=doi or None,
                title=title or None,
                year=year or None,
            )
        )
    return references


def build_article_structure(
    *,
    provider: str,
    metadata: Mapping[str, Any],
    xml_body: bytes,
    xml_path: Path,
    assets: list[dict[str, Any]],
) -> ArticleStructure | None:
    try:
        root = ET.fromstring(xml_body)
    except ET.ParseError:
        return None

    title = normalize_text(str(metadata.get("title") or "")) or "Untitled Article"
    doi = normalize_text(str(metadata.get("doi") or ""))
    journal_title = normalize_text(str(metadata.get("journal_title") or ""))
    published = normalize_text(str(metadata.get("published") or ""))
    landing_page = normalize_text(str(metadata.get("landing_page_url") or ""))
    authors = extract_article_authors(root)
    references: list[Reference] = []

    used_figure_keys: set[str] = set()
    used_table_keys: set[str] = set()
    formula_renders = []
    if provider == "elsevier":
        abstract_node = first_descendant(root, "abstract")
        body_node = first_descendant(root, "body")
        abstract_lines = render_elsevier_blocks(
            abstract_node,
            heading_level=3,
            formula_renders=formula_renders,
        )
        if not abstract_lines:
            fallback_abstract = normalize_text(
                str(metadata.get("abstract") or child_text(first_descendant(root, "coredata"), "description"))
            )
            if fallback_abstract:
                abstract_lines = [fallback_abstract, ""]
        table_lookup, table_entries = elsevier_table_registry(root, assets, xml_path.with_suffix(".md"))
        figure_lookup, figure_entries = elsevier_figure_registry(root, assets, xml_path.with_suffix(".md"))
        body_lines = render_elsevier_blocks(
            body_node,
            heading_level=3,
            figure_lookup=figure_lookup,
            figure_entries=figure_entries,
            used_figure_keys=used_figure_keys,
            table_lookup=table_lookup,
            used_table_keys=used_table_keys,
            formula_renders=formula_renders,
        )
        supplement_entries = elsevier_supplement_entries(root, assets, xml_path.with_suffix(".md"))
        references = extract_elsevier_references(root)
    else:
        return None

    semantic_losses = SemanticLosses(
        table_fallback_count=sum(1 for entry in table_entries if normalize_text(str(entry.get("kind") or "")) == "fallback"),
        table_layout_degraded_count=sum(1 for entry in table_entries if normalize_text(str(entry.get("lossy_message") or ""))),
        formula_fallback_count=sum(1 for result in formula_renders if getattr(result, "fallback_kind", None) == "fallback"),
        formula_missing_count=sum(1 for result in formula_renders if getattr(result, "fallback_kind", None) == "missing"),
    )
    conversion_notes = collect_conversion_notes(
        table_entries=table_entries,
        formula_notes=[str(result.note) for result in formula_renders if normalize_text(str(result.note or ""))],
    )
    return ArticleStructure(
        title=title,
        doi=doi,
        journal_title=journal_title,
        published=published,
        landing_page=landing_page,
        authors=authors,
        xml_path=xml_path,
        abstract_lines=abstract_lines,
        body_lines=body_lines,
        figure_entries=figure_entries,
        table_entries=table_entries,
        supplement_entries=supplement_entries,
        conversion_notes=conversion_notes,
        references=references,
        semantic_losses=semantic_losses,
        used_figure_keys=used_figure_keys,
        used_table_keys=used_table_keys,
    )


def build_markdown_document(
    *,
    provider: str,
    metadata: Mapping[str, Any],
    xml_body: bytes,
    xml_path: Path,
    assets: list[dict[str, Any]],
) -> str | None:
    if provider != "elsevier":
        return None

    structure = build_article_structure(
        provider=provider,
        metadata=metadata,
        xml_body=xml_body,
        xml_path=xml_path,
        assets=assets,
    )
    if structure is None:
        return None

    lines = [f"# {structure.title}", ""]
    if structure.doi:
        lines.append(f"- DOI: `{structure.doi}`")
    lines.append(f"- Provider: `{provider}`")
    if structure.journal_title:
        lines.append(f"- Journal: {structure.journal_title}")
    if structure.published:
        lines.append(f"- Published: {structure.published}")
    lines.append(f"- XML: [{structure.xml_path.name}]({path_relative_to(structure.xml_path.parent, structure.xml_path)})")
    if structure.landing_page:
        lines.append(f"- Landing Page: {structure.landing_page}")
    lines.append("")

    if structure.abstract_lines:
        lines.extend(["## Abstract", ""])
        lines.extend(structure.abstract_lines)

    if structure.body_lines:
        if lines and normalize_text(lines[-1]):
            lines.append("")
        lines.extend(structure.body_lines)

    remaining_figure_entries = [
        entry
        for entry in structure.figure_entries
        if entry["key"] not in structure.used_figure_keys and entry.get("section") == "body"
    ]
    if remaining_figure_entries:
        lines.extend(["## Additional Figures", ""])
        for entry in remaining_figure_entries:
            lines.extend([f"### {entry['heading']}", ""])
            lines.extend(render_figure_block(entry))

    remaining_table_entries = [
        entry
        for entry in structure.table_entries
        if str(entry["key"]) not in structure.used_table_keys and entry.get("section") == "body"
    ]
    if remaining_table_entries:
        lines.extend(["## Additional Tables", ""])
        for entry in remaining_table_entries:
            lines.extend(render_table_block(entry))

    if structure.supplement_entries:
        lines.extend(["## Supplementary Materials", ""])
        for entry in structure.supplement_entries:
            bullet = f"- [{entry['heading']}]({entry['link']})"
            if entry["caption"]:
                bullet = f"{bullet}: {entry['caption']}"
            lines.append(bullet)
        lines.append("")

    if structure.conversion_notes:
        lines.extend(["## Conversion Notes", ""])
        lines.extend(structure.conversion_notes)
        lines.append("")

    return normalize_lines(lines)


def write_article_markdown(
    *,
    provider: str,
    metadata: Mapping[str, Any],
    xml_body: bytes,
    output_dir: Path | None,
    xml_path: str | None,
    assets: list[dict[str, Any]] | None = None,
) -> str | None:
    if output_dir is None or not xml_path:
        return None

    xml_output_path = Path(xml_path)
    markdown_path = make_markdown_path(output_dir, str(metadata.get("doi") or ""), metadata.get("title"))
    document = build_markdown_document(
        provider=provider,
        metadata=metadata,
        xml_body=xml_body,
        xml_path=xml_output_path,
        assets=list(assets or []),
    )
    if document is None:
        return None
    markdown_path.write_text(document, encoding="utf-8")
    return str(markdown_path)
