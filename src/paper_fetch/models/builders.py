"""Article builder helpers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Mapping

from ..markdown.citations import normalize_inline_citation_markdown
from ..publisher_identity import normalize_doi
from ..tracing import TraceEvent, source_trail_from_trace, trace_from_markers
from ..utils import normalize_text, safe_text
from .markdown import (
    NUMBERED_REFERENCE_PATTERN,
    normalize_abstract_text,
    normalize_authors,
    normalize_inline_html_text,
    normalize_markdown_text,
    strip_leading_markdown_title_heading,
    strip_markdown_images,
)
from .quality import apply_quality_assessment, classify_content
from .render import rewrite_markdown_asset_links
from .schema import (
    ArticleModel,
    Asset,
    ExtractedAbstractBlock,
    Metadata,
    Quality,
    Reference,
    Section,
    SectionHint,
    SemanticLosses,
    SourceKind,
)
from .sections import (
    _abstract_sections_from_blocks,
    _abstract_sections_from_lines,
    _has_old_nature_methods_summary_structure,
    _normalize_inline_citations_in_section,
    _promote_stripped_methods_summary_section,
    _section_matches_explicit_abstract,
    _strip_leading_explicit_abstract_paragraphs,
    first_abstract_text,
    lines_to_sections,
    split_leading_inline_abstract,
)
from .tokens import build_token_estimate_breakdown

def local_asset_link(value: Any) -> str | None:
    normalized = safe_text(value)
    if not normalized:
        return None
    if normalized.startswith(("http://", "https://", "//")):
        return None
    return normalized


def _optional_int(value: Any) -> int | None:
    try:
        integer = int(value)
    except (TypeError, ValueError):
        return None
    return integer if integer >= 0 else None


def _asset_from_entry(
    entry: Mapping[str, Any],
    *,
    kind: str,
    heading_fallback: str,
    render_state: str | None = None,
) -> "Asset":
    link = entry.get("link")
    url = local_asset_link(link if link is not None else entry.get("url") or entry.get("source_url"))
    original_url = next(
        (
            safe_text(entry.get(field))
            for field in (
                "original_url",
                "preview_url",
                "source_url",
                "download_url",
                "full_size_url",
                "url",
                "link",
            )
            if safe_text(entry.get(field)) and not local_asset_link(entry.get(field))
        ),
        "",
    )
    return Asset(
        kind=kind,
        heading=safe_text(entry.get("heading") or heading_fallback) or heading_fallback,
        caption=safe_text(entry.get("caption")) or None,
        url=url,
        path=safe_text(entry.get("path")) or None,
        section=safe_text(entry.get("section")) or None,
        render_state=safe_text(entry.get("render_state") or render_state) or None,
        anchor_key=safe_text(entry.get("anchor_key") or entry.get("key")) or None,
        download_tier=safe_text(entry.get("download_tier")) or None,
        download_url=safe_text(entry.get("download_url")) or None,
        original_url=original_url or None,
        content_type=safe_text(entry.get("content_type")) or None,
        downloaded_bytes=_optional_int(entry.get("downloaded_bytes")),
        width=_optional_int(entry.get("width")),
        height=_optional_int(entry.get("height")),
    )


def build_metadata(metadata: Mapping[str, Any]) -> Metadata:
    return Metadata(
        title=normalize_inline_html_text(metadata.get("title")) or None,
        authors=normalize_authors(metadata.get("authors")),
        abstract=normalize_abstract_text(metadata.get("abstract")) or None,
        journal=normalize_inline_html_text(metadata.get("journal_title") or metadata.get("journal")) or None,
        published=normalize_inline_html_text(metadata.get("published")) or None,
        keywords=[
            normalize_inline_html_text(item)
            for item in (metadata.get("keywords") or [])
            if normalize_inline_html_text(item)
        ],
        license_urls=[
            safe_text(item)
            for item in (metadata.get("license_urls") or [])
            if safe_text(item)
        ],
        landing_page_url=safe_text(metadata.get("landing_page_url")) or None,
    )


def metadata_only_article(
    *,
    source: SourceKind,
    metadata: Mapping[str, Any],
    doi: str | None = None,
    warnings: list[str] | None = None,
    source_trail: list[str] | None = None,
    trace: list[TraceEvent] | None = None,
) -> ArticleModel:
    article_metadata = build_metadata(metadata)
    references = build_references(metadata.get("references"))
    effective_trace = list(trace or trace_from_markers(source_trail))
    token_estimate_breakdown = build_token_estimate_breakdown(
        abstract_text=article_metadata.abstract,
        sections=[],
        references=references,
    )
    token_estimate = token_estimate_breakdown.abstract + token_estimate_breakdown.body
    article = ArticleModel(
        doi=doi or safe_text(metadata.get("doi")) or None,
        source=source,
        metadata=article_metadata,
        sections=[],
        references=references,
        assets=[],
        quality=Quality(
            has_fulltext=False,
            token_estimate=token_estimate,
            has_abstract=bool(article_metadata.abstract),
            warnings=list(warnings or []),
            source_trail=list(source_trail or source_trail_from_trace(effective_trace)),
            trace=effective_trace,
            token_estimate_breakdown=token_estimate_breakdown,
        ),
    )
    return apply_quality_assessment(article)


def build_references(raw_references: Any) -> list[Reference]:
    references: list[Reference] = []
    if not isinstance(raw_references, list):
        return references
    for item in raw_references:
        if isinstance(item, Mapping):
            raw = _normalized_reference_raw(item)
            if not raw:
                continue
            references.append(
                Reference(
                    raw=raw,
                    doi=normalize_doi(safe_text(item.get("doi"))) or None,
                    title=safe_text(item.get("title")) or None,
                    year=safe_text(item.get("year")) or None,
                )
            )
        else:
            raw = safe_text(item)
            if raw:
                references.append(Reference(raw=raw))
    return references


def _normalized_reference_raw(item: Mapping[str, Any]) -> str:
    raw = safe_text(item.get("raw") or item.get("unstructured") or item.get("title"))
    label = safe_text(item.get("label") or item.get("index") or item.get("number"))
    title = safe_text(item.get("title") or item.get("article-title"))
    author_values = item.get("authors") or item.get("author") or item.get("creators")
    if isinstance(author_values, str):
        authors = [safe_text(author_values)]
    elif isinstance(author_values, Sequence) and not isinstance(author_values, (bytes, bytearray)):
        authors = [safe_text(value) for value in author_values if safe_text(value)]
    else:
        authors = []
    author_text = ", ".join(authors[:6])
    if title and author_text and (not raw or raw == title):
        raw = f"{author_text}. {title}"
    if not raw:
        return ""
    if not label or NUMBERED_REFERENCE_PATTERN.match(raw):
        return raw
    if label[-1] in {".", ")"}:
        return f"{label} {raw}"
    if label.isdigit():
        return f"{label}. {raw}"
    return f"[{label}] {raw}"


def article_from_structure(
    *,
    source: SourceKind,
    metadata: Mapping[str, Any],
    doi: str | None,
    abstract_lines: list[str],
    abstract_sections: Sequence[ExtractedAbstractBlock | Mapping[str, Any] | Section] | None = None,
    body_lines: list[str],
    figure_entries: list[Mapping[str, Any]],
    table_entries: list[Mapping[str, Any]],
    supplement_entries: list[Mapping[str, Any]],
    conversion_notes: list[str],
    references: list[Reference] | None = None,
    warnings: list[str] | None = None,
    source_trail: list[str] | None = None,
    trace: list[TraceEvent] | None = None,
    availability_diagnostics: Mapping[str, Any] | None = None,
    semantic_losses: SemanticLosses | Mapping[str, Any] | None = None,
    quality_flags: Sequence[str] | None = None,
    inline_figure_keys: Sequence[str] | None = None,
    inline_table_keys: Sequence[str] | None = None,
    allow_downgrade_from_diagnostics: bool = False,
) -> ArticleModel:
    article_metadata = build_metadata(metadata)
    effective_trace = list(trace or trace_from_markers(source_trail))
    explicit_abstract_sections = _abstract_sections_from_blocks(abstract_sections) or _abstract_sections_from_lines(abstract_lines)
    abstract_text = first_abstract_text(abstract_text=None, sections=explicit_abstract_sections)
    if abstract_text and not normalize_text(article_metadata.abstract):
        article_metadata.abstract = abstract_text
    elif abstract_text:
        article_metadata.abstract = abstract_text

    sections = [*explicit_abstract_sections, *lines_to_sections(body_lines, fallback_heading="", preserve_images=True)]
    if conversion_notes:
        sections.append(
            Section(
                heading="Conversion Notes",
                level=2,
                kind="diagnostics",
                text=normalize_text("\n".join(conversion_notes)),
            )
        )

    assets: list[Asset] = []
    consumed_figure_keys = {normalize_text(key) for key in inline_figure_keys or [] if normalize_text(key)}
    consumed_table_keys = {normalize_text(key) for key in inline_table_keys or [] if normalize_text(key)}
    for entry in figure_entries:
        key = normalize_text(entry.get("key"))
        assets.append(_asset_from_entry(entry, kind="figure", heading_fallback="Figure", render_state="inline" if key in consumed_figure_keys else "appendix"))
    for entry in table_entries:
        key = normalize_text(entry.get("key"))
        assets.append(_asset_from_entry(entry, kind="table", heading_fallback="Table", render_state="inline" if key in consumed_table_keys else "appendix"))
    for entry in supplement_entries:
        assets.append(_asset_from_entry(entry, kind="supplementary", heading_fallback="Supplementary Material"))

    normalized_references = list(references or build_references(metadata.get("references")))
    token_estimate_breakdown = build_token_estimate_breakdown(
        abstract_text=article_metadata.abstract,
        sections=sections,
        references=normalized_references,
    )
    token_estimate = token_estimate_breakdown.abstract + token_estimate_breakdown.body

    content_kind = classify_content(sections=sections, abstract_text=article_metadata.abstract)
    article = ArticleModel(
        doi=doi or safe_text(metadata.get("doi")) or None,
        source=source,
        metadata=article_metadata,
        sections=sections,
        references=normalized_references,
        assets=assets,
        quality=Quality(
            has_fulltext=content_kind == "fulltext",
            token_estimate=token_estimate,
            content_kind=content_kind,
            has_abstract=bool(article_metadata.abstract),
            warnings=list(warnings or []),
            source_trail=list(source_trail or source_trail_from_trace(effective_trace)),
            trace=effective_trace,
            token_estimate_breakdown=token_estimate_breakdown,
        ),
    )
    diagnostics_payload = availability_diagnostics
    has_provider_diagnostics = diagnostics_payload is not None
    if diagnostics_payload is None:
        from ..quality.html_availability import assess_structured_article_fulltext_availability

        diagnostics_payload = assess_structured_article_fulltext_availability(article, title=article_metadata.title).to_dict()
    return apply_quality_assessment(
        article,
        availability_diagnostics=diagnostics_payload,
        semantic_losses=semantic_losses,
        extra_flags=quality_flags,
        allow_downgrade_from_diagnostics=allow_downgrade_from_diagnostics and has_provider_diagnostics,
    )


def article_from_markdown(
    *,
    source: SourceKind,
    metadata: Mapping[str, Any],
    doi: str | None,
    markdown_text: str,
    abstract_sections: Sequence[ExtractedAbstractBlock | Mapping[str, Any] | Section] | None = None,
    section_hints: Sequence[SectionHint | Mapping[str, Any]] | None = None,
    assets: list[Mapping[str, Any]] | None = None,
    warnings: list[str] | None = None,
    source_trail: list[str] | None = None,
    trace: list[TraceEvent] | None = None,
    availability_diagnostics: Mapping[str, Any] | None = None,
    semantic_losses: SemanticLosses | Mapping[str, Any] | None = None,
    quality_flags: Sequence[str] | None = None,
    allow_downgrade_from_diagnostics: bool = False,
) -> ArticleModel:
    article_metadata = build_metadata(metadata)
    effective_trace = list(trace or trace_from_markers(source_trail))
    normalized_assets = [
        _asset_from_entry(
            item,
            kind=safe_text(item.get("kind") or item.get("asset_type") or "asset") or "asset",
            heading_fallback="Asset",
        )
        for item in (assets or [])
    ]
    normalized = normalize_inline_citation_markdown(
        strip_leading_markdown_title_heading(markdown_text, title=article_metadata.title)
    )
    normalized = rewrite_markdown_asset_links(normalized, normalized_assets)
    normalized = normalize_markdown_text(normalized)
    parsed_sections = lines_to_sections(
        normalized.splitlines(),
        fallback_heading="",
        preserve_images=True,
        section_hints=section_hints,
    )
    parsed_sections = [_normalize_inline_citations_in_section(section) for section in parsed_sections]
    normalize_methods_summary = _has_old_nature_methods_summary_structure(parsed_sections, section_hints)
    explicit_abstract_sections = [
        _normalize_inline_citations_in_section(section)
        for section in _abstract_sections_from_blocks(abstract_sections)
    ]
    sections = list(explicit_abstract_sections)
    extracted_abstract = first_abstract_text(abstract_text=None, sections=explicit_abstract_sections)
    for section in parsed_sections:
        if explicit_abstract_sections and normalize_text(section.kind).lower() == "abstract":
            continue
        if _section_matches_explicit_abstract(section, explicit_abstract_sections):
            continue
        original_section = section
        section = _strip_leading_explicit_abstract_paragraphs(section, explicit_abstract_sections)
        section = _promote_stripped_methods_summary_section(
            original_section,
            section,
            normalize_methods_summary=normalize_methods_summary,
        )
        if section is None:
            continue
        section = _normalize_inline_citations_in_section(section)
        if section.kind == "abstract" and not extracted_abstract:
            extracted_abstract = strip_markdown_images(section.text)
        sections.append(section)
    inline_abstract, sections = split_leading_inline_abstract(sections)
    if inline_abstract:
        extracted_abstract = normalize_inline_citation_markdown(inline_abstract)
    article_metadata.abstract = normalize_inline_citation_markdown(extracted_abstract or article_metadata.abstract) or None
    references = build_references(metadata.get("references"))
    token_estimate_breakdown = build_token_estimate_breakdown(
        abstract_text=article_metadata.abstract,
        sections=sections,
        references=references,
    )
    token_estimate = token_estimate_breakdown.abstract + token_estimate_breakdown.body
    content_kind = classify_content(sections=sections, abstract_text=article_metadata.abstract)
    article = ArticleModel(
        doi=doi or safe_text(metadata.get("doi")) or None,
        source=source,
        metadata=article_metadata,
        sections=sections,
        references=references,
        assets=normalized_assets,
        quality=Quality(
            has_fulltext=content_kind == "fulltext",
            token_estimate=token_estimate,
            content_kind=content_kind,
            has_abstract=bool(article_metadata.abstract),
            warnings=list(warnings or []),
            source_trail=list(source_trail or source_trail_from_trace(effective_trace)),
            trace=effective_trace,
            token_estimate_breakdown=token_estimate_breakdown,
        ),
    )
    diagnostics_payload = availability_diagnostics
    has_provider_diagnostics = diagnostics_payload is not None
    if diagnostics_payload is None:
        from ..quality.html_availability import assess_plain_text_fulltext_availability

        diagnostics_payload = assess_plain_text_fulltext_availability(
            normalized,
            article_metadata.__dict__,
            title=article_metadata.title,
            section_hints=section_hints,
        ).to_dict()
    return apply_quality_assessment(
        article,
        availability_diagnostics=diagnostics_payload,
        semantic_losses=semantic_losses,
        extra_flags=quality_flags,
        allow_downgrade_from_diagnostics=allow_downgrade_from_diagnostics and has_provider_diagnostics,
    )


__all__ = [
    "local_asset_link",
    "build_metadata",
    "metadata_only_article",
    "build_references",
    "article_from_structure",
    "article_from_markdown",
]
