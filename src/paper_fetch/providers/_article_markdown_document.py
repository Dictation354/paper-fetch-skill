"""Document assembly for XML-derived article Markdown."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import xml.etree.ElementTree as ET

from ._article_markdown_common import (
    child_text,
    collect_conversion_notes,
    first_descendant,
    make_markdown_path,
    normalize_lines,
    normalize_text,
    path_relative_to,
    render_figure_block,
    render_table_block,
)
from ._article_markdown_elsevier import (
    elsevier_figure_registry,
    elsevier_supplement_entries,
    elsevier_table_registry,
    render_elsevier_blocks,
)
from ._article_markdown_springer import (
    render_jats_blocks,
    springer_figure_registry,
    springer_supplement_entries,
    springer_table_registry,
)


@dataclass
class ArticleStructure:
    title: str
    doi: str
    journal_title: str
    published: str
    landing_page: str
    xml_path: Path
    abstract_lines: list[str]
    body_lines: list[str]
    figure_entries: list[dict[str, Any]]
    table_entries: list[dict[str, Any]]
    supplement_entries: list[dict[str, str]]
    conversion_notes: list[str]
    used_figure_keys: set[str]
    used_table_keys: set[str]


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

    used_figure_keys: set[str] = set()
    used_table_keys: set[str] = set()
    if provider == "springer":
        article = first_descendant(root, "article")
        if article is None:
            article = root
        abstract_node = first_descendant(article, "abstract")
        body_node = first_descendant(article, "body")
        abstract_lines = render_jats_blocks(abstract_node, heading_level=3)
        table_lookup, table_entries, reserved_image_paths = springer_table_registry(
            article,
            assets,
            xml_path.with_suffix(".md"),
            doi,
        )
        figure_lookup, figure_entries = springer_figure_registry(
            article,
            assets,
            xml_path.with_suffix(".md"),
            doi,
            excluded_asset_paths=reserved_image_paths,
        )
        body_lines = render_jats_blocks(
            body_node,
            heading_level=3,
            figure_lookup=figure_lookup,
            table_lookup=table_lookup,
            used_figure_keys=used_figure_keys,
            used_table_keys=used_table_keys,
        )
        supplement_entries = springer_supplement_entries(article, assets, xml_path.with_suffix(".md"), doi)
    elif provider == "elsevier":
        abstract_node = first_descendant(root, "abstract")
        body_node = first_descendant(root, "body")
        abstract_lines = render_elsevier_blocks(abstract_node, heading_level=3)
        if not abstract_lines:
            fallback_abstract = normalize_text(str(metadata.get("abstract") or child_text(first_descendant(root, "coredata"), "description")))
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
        )
        supplement_entries = elsevier_supplement_entries(root, assets, xml_path.with_suffix(".md"))
    else:
        return None

    conversion_notes = collect_conversion_notes(table_entries=table_entries)
    return ArticleStructure(
        title=title,
        doi=doi,
        journal_title=journal_title,
        published=published,
        landing_page=landing_page,
        xml_path=xml_path,
        abstract_lines=abstract_lines,
        body_lines=body_lines,
        figure_entries=figure_entries,
        table_entries=table_entries,
        supplement_entries=supplement_entries,
        conversion_notes=conversion_notes,
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
        lines.extend(["## Full Text", ""])
        lines.extend(structure.body_lines)

    remaining_figure_entries = [
        entry
        for entry in structure.figure_entries
        if entry["key"] not in structure.used_figure_keys and (provider != "elsevier" or entry.get("section") == "body")
    ]
    if remaining_figure_entries:
        lines.extend(["## Additional Figures", ""])
        for entry in remaining_figure_entries:
            lines.extend([f"### {entry['heading']}", ""])
            lines.extend(render_figure_block(entry))

    remaining_table_entries = [entry for entry in structure.table_entries if str(entry["key"]) not in structure.used_table_keys]
    if provider == "elsevier":
        remaining_table_entries = [entry for entry in remaining_table_entries if entry.get("section") == "body"]
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
