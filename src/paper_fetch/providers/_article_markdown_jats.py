"""Generic NLM/JATS XML extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from collections.abc import Mapping
import re
import xml.etree.ElementTree as ET

from ..models import SemanticLosses
from ..publisher_identity import extract_doi, normalize_doi
from ..reason_codes import (
    STRUCTURED_ARTICLE_NOT_FULLTEXT,
    STRUCTURED_MISSING_BODY_SECTIONS,
)
from ..utils import dedupe_authors, normalize_text
from ..xml_security import XmlParseFailure, parse_xml
from ._article_markdown_common import (
    child_text,
    collect_conversion_notes,
    first_child,
    first_descendant,
    iter_children,
    iter_descendants,
    _normalize_xml_character_data,
    normalize_lines,
    render_figure_block,
    render_inline_text,
    render_table_block,
    table_entry_semantic_count,
    xml_local_name,
)
from ._article_markdown_jats_blocks import (
    JATS_BLOCK_LOCAL_NAMES,
    _figure_entry,
    _heading_text,
    _href,
    _render_list,
    _render_paragraph_texts,
    _render_supplementary_materials,
    _supplementary_entries,
    _table_entry,
)
from ._article_markdown_math import FormulaRenderResult, render_display_formula_result


@dataclass(frozen=True)
class JatsExtraction:
    metadata: dict[str, Any]
    abstract_sections: list[dict[str, Any]]
    markdown_text: str
    assets: list[dict[str, Any]]
    references: list[dict[str, Any]]
    semantic_losses: SemanticLosses
    conversion_notes: list[str] = field(default_factory=list)
    article_type: str | None = None
    body_section_count: int = 0
    body_paragraph_count: int = 0
    body_char_count: int = 0


@dataclass(frozen=True)
class JatsBodyAvailability:
    accepted: bool
    reason: str
    article_type: str | None
    short_article_policy: bool
    body_section_count: int
    body_paragraph_count: int
    body_char_count: int
    min_body_chars: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "article_type": self.article_type,
            "short_article_policy": self.short_article_policy,
            "body_metrics": {
                "body_section_count": self.body_section_count,
                "body_paragraph_count": self.body_paragraph_count,
                "body_char_count": self.body_char_count,
                "min_body_chars": self.min_body_chars,
            },
        }


_SHORT_JATS_ARTICLE_TYPE_TOKENS = frozenset(
    {
        "brief-report",
        "commentary",
        "correction",
        "editorial",
        "letter",
        "news",
        "reply",
    }
)
_SHORT_JATS_MIN_BODY_CHARS = 120


def assess_jats_body_availability(
    extraction: JatsExtraction,
    *,
    min_body_chars: int,
) -> JatsBodyAvailability:
    """Assess only JATS body prose; abstracts and references never satisfy it."""

    article_type = normalize_text(extraction.article_type).lower() or None
    short_policy = bool(
        article_type
        and any(token in article_type for token in _SHORT_JATS_ARTICLE_TYPE_TOKENS)
    )
    effective_min_chars = (
        min(max(1, int(min_body_chars)), _SHORT_JATS_MIN_BODY_CHARS)
        if short_policy
        else max(1, int(min_body_chars))
    )
    has_body_structure = extraction.body_section_count > 0 or (
        short_policy and extraction.body_paragraph_count > 0
    )
    accepted = bool(
        has_body_structure
        and extraction.body_paragraph_count > 0
        and extraction.body_char_count >= effective_min_chars
    )
    if accepted:
        reason = (
            "structured_short_article_body"
            if short_policy
            else "structured_body_sections"
        )
    elif not has_body_structure or extraction.body_paragraph_count <= 0:
        reason = STRUCTURED_MISSING_BODY_SECTIONS
    else:
        reason = STRUCTURED_ARTICLE_NOT_FULLTEXT
    return JatsBodyAvailability(
        accepted=accepted,
        reason=reason,
        article_type=article_type,
        short_article_policy=short_policy,
        body_section_count=extraction.body_section_count,
        body_paragraph_count=extraction.body_paragraph_count,
        body_char_count=extraction.body_char_count,
        min_body_chars=effective_min_chars,
    )


def _text_from_first_descendant(element: ET.Element | None, local_name: str) -> str:
    return normalize_text(render_inline_text(first_descendant(element, local_name)))


def _extract_contrib_name(contrib: ET.Element) -> str:
    name = first_child(contrib, "name")
    if name is not None:
        given = normalize_text(
            child_text(name, "given-names") or child_text(name, "given-name")
        )
        surname = normalize_text(child_text(name, "surname"))
        if given or surname:
            return normalize_text(" ".join(item for item in (given, surname) if item))
    return normalize_text(
        child_text(contrib, "collab") or child_text(contrib, "collaboration")
    )


def extract_jats_authors(root: ET.Element) -> list[str]:
    authors: list[str] = []
    for contrib in iter_descendants(root, "contrib"):
        contrib_type = normalize_text(str(contrib.get("contrib-type") or "")).lower()
        if contrib_type and contrib_type != "author":
            continue
        name = _extract_contrib_name(contrib)
        if name:
            authors.append(name)
    return dedupe_authors(authors)


def _article_meta(root: ET.Element) -> ET.Element | None:
    front = first_child(root, "front")
    return first_descendant(front, "article-meta")


def _journal_meta(root: ET.Element) -> ET.Element | None:
    front = first_child(root, "front")
    return first_descendant(front, "journal-meta")


def _article_id(article_meta: ET.Element | None, pub_id_type: str) -> str:
    for node in iter_children(article_meta, "article-id"):
        if normalize_text(str(node.get("pub-id-type") or "")).lower() == pub_id_type:
            return normalize_text("".join(node.itertext()))
    return ""


def _publication_date(article_meta: ET.Element | None) -> str:
    pub_dates = iter_children(article_meta, "pub-date")
    if not pub_dates:
        return ""
    preferred = pub_dates[0]
    for candidate in pub_dates:
        pub_type = normalize_text(
            str(candidate.get("pub-type") or candidate.get("date-type") or "")
        ).lower()
        if pub_type in {"epub", "ppub", "collection"}:
            preferred = candidate
            break
    parts = [
        normalize_text(child_text(preferred, "day")),
        normalize_text(child_text(preferred, "month")),
        normalize_text(child_text(preferred, "year")),
    ]
    return normalize_text(" ".join(part for part in parts if part))


def _license_urls(article_meta: ET.Element | None) -> list[str]:
    urls: list[str] = []
    permissions = first_child(article_meta, "permissions")
    for node in iter_descendants(permissions, "ext-link"):
        href = _href(node)
        if href and href not in urls:
            urls.append(href)
    return urls


def extract_jats_metadata(
    root: ET.Element,
    *,
    base_metadata: Mapping[str, Any] | None = None,
    source_url: str = "",
) -> dict[str, Any]:
    base = dict(base_metadata or {})
    article_meta = _article_meta(root)
    journal_meta = _journal_meta(root)
    title = _text_from_first_descendant(article_meta, "article-title")
    response_doi = normalize_doi(_article_id(article_meta, "doi"))
    doi = response_doi or normalize_doi(str(base.get("doi") or ""))
    journal_title = _text_from_first_descendant(journal_meta, "journal-title")
    abstract_node = first_child(article_meta, "abstract")
    abstract_text = normalize_text("\n\n".join(_render_paragraph_texts(abstract_node)))
    article_type = normalize_text(
        str(root.get("article-type") or base.get("article_type") or "")
    )

    metadata = dict(base)
    metadata.update(
        {
            "title": title or normalize_text(str(base.get("title") or "")) or None,
            "doi": doi or normalize_doi(str(base.get("doi") or "")) or None,
            "journal_title": journal_title
            or normalize_text(str(base.get("journal_title") or ""))
            or None,
            "published": _publication_date(article_meta)
            or normalize_text(str(base.get("published") or ""))
            or None,
            "authors": extract_jats_authors(root) or list(base.get("authors") or []),
            "abstract": abstract_text
            or normalize_text(str(base.get("abstract") or ""))
            or None,
            "landing_page_url": normalize_text(
                str(base.get("landing_page_url") or source_url or "")
            )
            or None,
            "license_urls": list(
                dict.fromkeys(
                    [
                        *list(base.get("license_urls") or []),
                        *_license_urls(article_meta),
                    ]
                )
            ),
            "references": list(base.get("references") or []),
            "article_type": article_type or None,
            "identity_evidence": {
                key: value
                for key, value in {
                    "doi": response_doi or None,
                    "title": title or None,
                }.items()
                if value
            },
        }
    )
    return metadata


def _render_inline_child_without_tail(
    child: ET.Element,
    *,
    source_url: str = "",
    formula_renders: list[FormulaRenderResult] | None = None,
) -> str:
    tail = child.tail
    child.tail = None
    try:
        rendered = render_inline_text(
            child,
            skip_local_names=JATS_BLOCK_LOCAL_NAMES,
            formula_renders=formula_renders,
            source_url=source_url,
        )
    finally:
        child.tail = tail
    local_name = xml_local_name(child.tag)
    if local_name == "italic" and rendered:
        return f"*{rendered}*"
    if local_name == "bold" and rendered:
        return f"**{rendered}**"
    if local_name == "sub" and rendered:
        return f"<sub>{rendered}</sub>"
    if local_name == "sup" and rendered:
        return f"<sup>{rendered}</sup>"
    return rendered


def _flush_paragraph_parts(lines: list[str], parts: list[str]) -> None:
    text = normalize_text("".join(parts))
    parts.clear()
    if text:
        lines.extend([text, ""])


def _append_embedded_block(
    node: ET.Element,
    *,
    lines: list[str],
    source_url: str,
    assets: list[dict[str, Any]],
    table_entries: list[dict[str, Any]],
    formula_renders: list[FormulaRenderResult],
) -> bool:
    local_name = xml_local_name(node.tag)
    if local_name == "fig":
        entry = _figure_entry(node, source_url)
        if entry is not None:
            assets.append(entry)
            if entry.get("link"):
                lines.extend(render_figure_block(entry))
        return True
    if local_name in {"table-wrap", "table"}:
        entry, _lossy = _table_entry(node, source_url)
        if entry is not None:
            table_entries.append(entry)
            assets.append(entry)
            lines.extend(render_table_block(entry))
        return True
    if local_name == "disp-formula":
        result = render_display_formula_result(node, source_url=source_url)
        if result.lines:
            formula_renders.append(result)
            entry = _formula_asset_entry(result)
            if entry is not None:
                assets.append(entry)
            lines.extend(result.lines)
        return True
    if local_name == "list":
        list_type = normalize_text(str(node.get("list-type") or "")).lower()
        lines.extend(
            _render_list(node, ordered=list_type in {"order", "ordered", "decimal"})
        )
        return True
    return False


def _render_paragraph_block(
    paragraph: ET.Element,
    *,
    source_url: str,
    assets: list[dict[str, Any]],
    table_entries: list[dict[str, Any]],
    formula_renders: list[FormulaRenderResult],
) -> list[str]:
    embedded_blocks = {
        id(child)
        for child in iter_children(paragraph)
        if xml_local_name(child.tag) in JATS_BLOCK_LOCAL_NAMES
    }
    if not embedded_blocks:
        text = render_inline_text(
            paragraph,
            skip_local_names=JATS_BLOCK_LOCAL_NAMES,
            formula_renders=formula_renders,
            source_url=source_url,
        )
        return [text, ""] if text else []

    lines: list[str] = []
    paragraph_parts: list[str] = [_normalize_xml_character_data(paragraph.text)]
    for child in iter_children(paragraph):
        if id(child) in embedded_blocks:
            _flush_paragraph_parts(lines, paragraph_parts)
            _append_embedded_block(
                child,
                lines=lines,
                source_url=source_url,
                assets=assets,
                table_entries=table_entries,
                formula_renders=formula_renders,
            )
        else:
            paragraph_parts.append(
                _render_inline_child_without_tail(
                    child,
                    source_url=source_url,
                    formula_renders=formula_renders,
                )
            )
        if child.tail:
            paragraph_parts.append(_normalize_xml_character_data(child.tail))
    _flush_paragraph_parts(lines, paragraph_parts)
    return lines


def _render_blocks(
    parent: ET.Element | None,
    *,
    heading_level: int,
    source_url: str,
    assets: list[dict[str, Any]],
    table_entries: list[dict[str, Any]],
    formula_renders: list[FormulaRenderResult],
) -> list[str]:
    if parent is None:
        return []

    lines: list[str] = []
    for child in iter_children(parent):
        local_name = xml_local_name(child.tag)
        if local_name in {"title", "label"}:
            continue
        if local_name == "sec":
            child_lines = _render_blocks(
                child,
                heading_level=heading_level + 1,
                source_url=source_url,
                assets=assets,
                table_entries=table_entries,
                formula_renders=formula_renders,
            )
            heading = _heading_text(child)
            if heading and child_lines:
                lines.extend([f"{'#' * heading_level} {heading}", ""])
            lines.extend(child_lines)
            continue
        if local_name == "p":
            lines.extend(
                _render_paragraph_block(
                    child,
                    source_url=source_url,
                    assets=assets,
                    table_entries=table_entries,
                    formula_renders=formula_renders,
                )
            )
            continue
        if local_name == "fig":
            entry = _figure_entry(child, source_url)
            if entry is not None:
                assets.append(entry)
                if entry.get("link"):
                    lines.extend(render_figure_block(entry))
                elif entry.get("caption"):
                    lines.extend([f"**{entry['heading']}** {entry['caption']}", ""])
            continue
        if local_name in {"table-wrap", "table"}:
            entry, _lossy = _table_entry(child, source_url)
            if entry is not None:
                table_entries.append(entry)
                assets.append(entry)
                lines.extend(render_table_block(entry))
            continue
        if local_name == "disp-formula":
            _append_embedded_block(
                child,
                lines=lines,
                source_url=source_url,
                assets=assets,
                table_entries=table_entries,
                formula_renders=formula_renders,
            )
            continue
        if local_name == "list":
            list_type = normalize_text(str(child.get("list-type") or "")).lower()
            lines.extend(
                _render_list(
                    child, ordered=list_type in {"order", "ordered", "decimal"}
                )
            )
            continue
        if local_name in {"notes", "ack", "app"}:
            heading = normalize_text(child_text(child, "title")) or _note_heading(child)
            child_lines = _render_blocks(
                child,
                heading_level=heading_level + 1,
                source_url=source_url,
                assets=assets,
                table_entries=table_entries,
                formula_renders=formula_renders,
            )
            if heading and child_lines:
                lines.extend([f"{'#' * heading_level} {heading}", ""])
            lines.extend(child_lines)
            continue
        lines.extend(
            _render_blocks(
                child,
                heading_level=heading_level,
                source_url=source_url,
                assets=assets,
                table_entries=table_entries,
                formula_renders=formula_renders,
            )
        )
    return lines


def _formula_asset_entry(result: FormulaRenderResult) -> dict[str, Any] | None:
    if result.assets:
        return dict(result.assets[0])
    image_url = normalize_text(str(result.image_url or ""))
    if not image_url:
        return None
    label = normalize_text(str(result.label or ""))
    heading = f"Formula {label}" if label else "Formula"
    key = image_url or heading
    return {
        "kind": "formula",
        "key": key,
        "anchor_key": key,
        "heading": heading,
        "caption": "",
        "link": image_url,
        "original_url": image_url,
        "section": "body",
        "render_state": "inline",
    }


def _note_heading(node: ET.Element) -> str:
    notes_type = normalize_text(str(node.get("notes-type") or "")).lower()
    known = {
        "dataavailability": "Data availability",
        "codeavailability": "Code availability",
        "authorcontribution": "Author contributions",
        "competinginterests": "Competing interests",
        "financialsupport": "Financial support",
        "reviewstatement": "Review statement",
    }
    return known.get(notes_type, "")


def _back_matter_lines(
    root: ET.Element,
    *,
    source_url: str,
    assets: list[dict[str, Any]],
    table_entries: list[dict[str, Any]],
    formula_renders: list[FormulaRenderResult],
) -> list[str]:
    back = first_child(root, "back")
    if back is None:
        return []
    lines: list[str] = []
    for child in iter_children(back):
        local_name = xml_local_name(child.tag)
        if local_name in {"notes", "ack"}:
            child_lines = _render_blocks(
                child,
                heading_level=3,
                source_url=source_url,
                assets=assets,
                table_entries=table_entries,
                formula_renders=formula_renders,
            )
            heading = normalize_text(child_text(child, "title")) or _note_heading(child)
            if heading and child_lines:
                lines.extend([f"## {heading}", ""])
            lines.extend(child_lines)
        elif local_name == "app-group":
            supplement_lines = _render_supplementary_materials(child, source_url)
            if supplement_lines:
                lines.extend(supplement_lines)
    return lines


def _reference_year(ref: ET.Element) -> str:
    for node in iter_descendants(ref, "year"):
        year = normalize_text("".join(node.itertext()))
        if year:
            return year
    match = re.search(r"\b(19|20)\d{2}\b", normalize_text(" ".join(ref.itertext())))
    return match.group(0) if match else ""


def _reference_title(ref: ET.Element) -> str:
    for local_name in ("article-title", "chapter-title", "source"):
        title = _text_from_first_descendant(ref, local_name)
        if title:
            return title
    return ""


def _reference_doi(ref: ET.Element) -> str:
    for node in iter_descendants(ref, "pub-id"):
        if normalize_text(str(node.get("pub-id-type") or "")).lower() == "doi":
            doi = normalize_doi("".join(node.itertext()))
            if doi:
                return doi
    for node in iter_descendants(ref, "ext-link"):
        for value in (_href(node), "".join(node.itertext())):
            extracted_doi = extract_doi(value)
            if extracted_doi:
                return normalize_doi(extracted_doi) or ""
    fallback_doi = extract_doi(" ".join(ref.itertext()))
    return normalize_doi(fallback_doi) if fallback_doi else ""


def extract_jats_references(root: ET.Element) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    for index, ref in enumerate(iter_descendants(root, "ref"), start=1):
        label = normalize_text(child_text(ref, "label"))
        citation = first_child(ref, "mixed-citation")
        if citation is None:
            citation = first_child(ref, "element-citation")
        body = normalize_text(
            render_inline_text(citation)
            if citation is not None
            else " ".join(ref.itertext())
        )
        if label:
            label_text = label.strip("[](). ")
            body = normalize_text(
                re.sub(rf"^\[?\s*{re.escape(label_text)}\s*\]?\.?\s*", "", body)
            )
        if not body:
            continue
        raw_label = label or str(index)
        raw = f"{raw_label}. {body}" if raw_label.isdigit() else f"[{raw_label}] {body}"
        references.append(
            {
                "raw": raw,
                "doi": _reference_doi(ref) or None,
                "title": _reference_title(ref) or None,
                "year": _reference_year(ref) or None,
            }
        )
    return references


def parse_jats_xml(
    xml_body: bytes,
    *,
    source_url: str = "",
    base_metadata: Mapping[str, Any] | None = None,
    xml_root: ET.Element | None = None,
) -> JatsExtraction | None:
    try:
        root = (
            xml_root
            if xml_root is not None
            else parse_xml(
                xml_body,
                source="JATS XML payload",
                allow_external_doctype=True,
            )
        )
    except XmlParseFailure:
        return None
    if not isinstance(root.tag, str) or xml_local_name(root.tag) != "article":
        return None

    metadata = extract_jats_metadata(
        root, base_metadata=base_metadata, source_url=source_url
    )
    article_meta = _article_meta(root)
    abstract_node = first_child(article_meta, "abstract")
    abstract_text = normalize_text("\n\n".join(_render_paragraph_texts(abstract_node)))
    abstract_sections = (
        [{"heading": "Abstract", "text": abstract_text, "kind": "abstract", "order": 0}]
        if abstract_text
        else []
    )

    assets: list[dict[str, Any]] = []
    table_entries: list[dict[str, Any]] = []
    formula_renders: list[FormulaRenderResult] = []
    body = first_child(root, "body")
    body_sections = iter_descendants(body, "sec")
    body_paragraphs = iter_descendants(body, "p")
    body_char_count = sum(
        len(normalize_text(" ".join(paragraph.itertext())))
        for paragraph in body_paragraphs
    )
    body_lines = _render_blocks(
        body,
        heading_level=2,
        source_url=source_url,
        assets=assets,
        table_entries=table_entries,
        formula_renders=formula_renders,
    )
    back_lines = _back_matter_lines(
        root,
        source_url=source_url,
        assets=assets,
        table_entries=table_entries,
        formula_renders=formula_renders,
    )
    for result in formula_renders:
        for formula_asset in result.assets:
            asset_key = normalize_text(
                str(formula_asset.get("key") or formula_asset.get("link") or "")
            )
            if asset_key and any(
                normalize_text(str(item.get("key") or item.get("link") or ""))
                == asset_key
                for item in assets
            ):
                continue
            assets.append(dict(formula_asset))
    supplement_entries = _supplementary_entries(root, source_url)
    for entry in supplement_entries:
        if not any(
            normalize_text(str(item.get("key") or ""))
            == normalize_text(str(entry.get("key") or ""))
            for item in assets
        ):
            assets.append(entry)
    markdown_text = normalize_lines([*body_lines, *back_lines])
    references = extract_jats_references(root)
    if references:
        metadata["references"] = references

    conversion_notes = collect_conversion_notes(
        table_entries=table_entries,
        formula_notes=[
            str(result.note)
            for result in formula_renders
            if normalize_text(str(result.note or ""))
        ],
    )
    semantic_losses = SemanticLosses(
        table_fallback_count=sum(
            table_entry_semantic_count(
                entry,
                "_table_fallback_count",
            )
            for entry in table_entries
        ),
        table_layout_degraded_count=sum(
            table_entry_semantic_count(
                entry,
                "_table_layout_degraded_count",
            )
            for entry in table_entries
        ),
        formula_fallback_count=sum(
            1
            for result in formula_renders
            if getattr(result, "fallback_kind", None) == "fallback"
        ),
        formula_missing_count=sum(
            1
            for result in formula_renders
            if getattr(result, "fallback_kind", None) == "missing"
        ),
    )
    return JatsExtraction(
        metadata=metadata,
        abstract_sections=abstract_sections,
        markdown_text=markdown_text,
        assets=assets,
        references=references,
        semantic_losses=semantic_losses,
        conversion_notes=conversion_notes,
        article_type=normalize_text(str(metadata.get("article_type") or "")) or None,
        body_section_count=len(body_sections),
        body_paragraph_count=len(body_paragraphs),
        body_char_count=body_char_count,
    )


def build_jats_markdown_document(
    extraction: JatsExtraction,
    *,
    xml_path: Path | None = None,
    provider_label: str = "jats",
) -> str:
    lines = [
        f"# {normalize_text(str(extraction.metadata.get('title') or 'Untitled Article'))}",
        "",
    ]
    doi = normalize_text(str(extraction.metadata.get("doi") or ""))
    if doi:
        lines.append(f"- DOI: `{doi}`")
    lines.append(f"- Provider: `{provider_label}`")
    journal = normalize_text(
        str(
            extraction.metadata.get("journal_title")
            or extraction.metadata.get("journal")
            or ""
        )
    )
    if journal:
        lines.append(f"- Journal: {journal}")
    published = normalize_text(str(extraction.metadata.get("published") or ""))
    if published:
        lines.append(f"- Published: {published}")
    if xml_path is not None:
        lines.append(f"- XML: {xml_path.name}")
    lines.append("")
    if extraction.abstract_sections:
        lines.extend(
            ["## Abstract", "", str(extraction.abstract_sections[0]["text"]), ""]
        )
    if extraction.markdown_text:
        lines.extend(extraction.markdown_text.splitlines())
        lines.append("")
    if extraction.conversion_notes:
        lines.extend(["## Conversion Notes", "", *extraction.conversion_notes, ""])
    return normalize_lines(lines)


__all__ = [
    "JatsBodyAvailability",
    "JatsExtraction",
    "assess_jats_body_availability",
    "build_jats_markdown_document",
    "extract_jats_authors",
    "extract_jats_metadata",
    "extract_jats_references",
    "parse_jats_xml",
]
