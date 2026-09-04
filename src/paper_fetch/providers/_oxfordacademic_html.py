"""Oxford Academic HTML extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from collections.abc import Mapping
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Comment, Tag

from ..extraction.html import assets as html_assets
from ..extraction.html._metadata import merge_html_metadata, parse_html_metadata
from ..extraction.html.language import collect_html_abstract_blocks
from ..extraction.html.parsing import choose_parser
from ..extraction.html.renderer import clean_rendered_markdown
from ..extraction.html.semantics import collect_html_section_hints
from ..extraction.html.tables import render_table_markdown
from ..models import AssetProfile
from ..provider_catalog import host_matches_domain
from ..publisher_identity import normalize_doi
from ..utils import extend_unique, normalize_text
from ._html_section_markdown import (
    render_clean_text_from_html,
    render_container_markdown,
)
from ._html_references import extract_numbered_references_from_html
from ._pdf_candidates import (
    extract_pdf_candidate_urls_from_html,
    extract_pdf_url_from_metadata_links,
)


OXFORDACADEMIC_NOISE_PROFILE = "oxfordacademic"
# SITE_UI_COPY_REGRESSION_MARKER: Oxford Academic action and metrics labels;
# rerun extraction rules when article toolbar copy changes.
# ProviderBundle wires this tuple into ProviderCleanupRules / CleanupPolicy.
OXFORDACADEMIC_MARKDOWN_PROMO_TOKENS = (
    "Download PDF",
    "Download Citation",
    "Download slide",
    "Download all slides",
    "Article metrics",
    "Article Metrics",
)
OXFORDACADEMIC_FRONT_MATTER_EXACT_TEXTS = (
    "Oxford Academic",
    "Published by Oxford University Press",
)
OXFORDACADEMIC_FRONT_MATTER_CONTAINS_TOKENS = (
    "Discover the most relevant content quickly",
    "Download all slides",
    "Search for other works by this author",
)
OXFORDACADEMIC_FRONT_MATTER_PUBLICATION_KEYWORDS = (
    "oxford academic",
    "oxford university press",
    "bioinformatics",
)
OXFORDACADEMIC_EXTRACTION_CLEANUP_SELECTORS = (
    ".article-metadata-panel",
    ".article-tools",
    ".article-view-links",
    ".citation-links",
    ".content-metadata",
    ".fig-view-orig",
    ".info-card-author",
    ".info-card-search",
    ".js-article-page-toolbar",
    ".al-author-info-wrap",
    ".refLink-parent",
    ".recommendedArticles",
    ".relatedContent",
    ".social-share",
    ".table-modal",
    ".toolbar",
    ".widget-ArticleTools",
    ".widget-EditorInformation",
)
OXFORDACADEMIC_SITE_RULE_OVERRIDES: dict[str, Any] = {
    "candidate_selectors": [
        ".article-body",
        ".widget-ArticleFulltext",
        "article",
        "[role='main']",
    ],
    "remove_selectors": list(OXFORDACADEMIC_EXTRACTION_CLEANUP_SELECTORS),
    "drop_keywords": {
        "article-tools",
        "article-metrics",
        "citation",
        "recommended",
        "related",
        "social-share",
        "toolbar",
    },
    "drop_text": {
        "Article metrics",
        "Article Metrics",
        "Download PDF",
        "Download Citation",
        "Download slide",
        "Download all slides",
        "Google Scholar",
    },
}
OXFORDACADEMIC_SUPPLEMENTARY_TEXT_TOKENS = (
    "Supplementary data",
    "Supplementary material",
    "Supplementary materials",
    "Supporting information",
)
OXFORDACADEMIC_MARKDOWN_NOISE_LINES = frozenset(
    {
        "Download slide",
        "Download all slides",
    }
)
OXFORDACADEMIC_SUPPLEMENTARY_LINK_SELECTORS = (".dataSuppLink",)
OXFORDACADEMIC_PARAGRAPH_BLOCK_CLASS = "block-child-p"
OXFORD_CITATION_FIELD_PATTERN = re.compile(
    r"(?P<key>citation_[A-Za-z0-9_]+)\s*=\s*(?P<value>[^;]*)"
)


@dataclass(frozen=True)
class OxfordAcademicExtraction:
    markdown_text: str
    metadata: dict[str, Any]
    html_text: str
    abstract_sections: list[Any]
    section_hints: list[Any]
    extracted_assets: list[dict[str, Any]]


def is_oxfordacademic_url(value: str | None) -> bool:
    hostname = urlparse(normalize_text(value)).hostname
    return host_matches_domain(hostname, "academic.oup.com")


def _nodes_with_class(
    root: BeautifulSoup | Tag,
    class_name: str,
    *,
    tag_name: str | None = None,
) -> list[Tag]:
    nodes = (
        root.find_all(tag_name, class_=class_name)
        if tag_name
        else root.find_all(class_=class_name)
    )
    return [node for node in nodes if isinstance(node, Tag)]


def _first_with_class(
    root: BeautifulSoup | Tag,
    class_name: str,
    *,
    tag_name: str | None = None,
) -> Tag | None:
    node = (
        root.find(tag_name, class_=class_name)
        if tag_name
        else root.find(class_=class_name)
    )
    return node if isinstance(node, Tag) else None


def _selector_class_name(selector: str) -> str | None:
    if not selector.startswith("."):
        return None
    class_name = selector[1:]
    if not class_name or any(char.isspace() for char in class_name):
        return None
    return class_name


def citation_reference_metadata(
    metadata: Mapping[str, Any],
) -> list[dict[str, str | None]]:
    raw_meta = (
        metadata.get("raw_meta")
        if isinstance(metadata.get("raw_meta"), Mapping)
        else {}
    )
    raw_values = (
        raw_meta.get("citation_reference") if isinstance(raw_meta, Mapping) else []
    )
    if isinstance(raw_values, str):
        raw_values = [raw_values]
    references: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for value in raw_values or []:
        raw = normalize_text(str(value))
        if not raw or raw in seen:
            continue
        seen.add(raw)
        cleaned = _clean_citation_reference_metadata(raw)
        if not cleaned:
            continue
        references.append(cleaned)
    return references


def _first_citation_field(fields: Mapping[str, list[str]], key: str) -> str:
    values = fields.get(key) or []
    return normalize_text(values[0]) if values else ""


def _append_reference_part(parts: list[str], value: str) -> None:
    normalized = normalize_text(value).rstrip(" ,;.")
    if normalized:
        parts.append(normalized)


def _clean_reference_sentence(value: str) -> str:
    normalized = normalize_text(value)
    normalized = re.sub(r"\s+([,.;:])", r"\1", normalized)
    normalized = re.sub(r"([(\[])\s+", r"\1", normalized)
    normalized = re.sub(r"\s+([)\]])", r"\1", normalized)
    normalized = re.sub(r"\s+([–-])\s+", r"\1", normalized)
    normalized = re.sub(r"\s*;\s*", "; ", normalized)
    normalized = re.sub(r"\bcitation_[A-Za-z0-9_]+\s*=\s*", "", normalized)
    return normalize_text(normalized)


def _clean_citation_reference_metadata(raw: str) -> dict[str, str | None]:
    fields: dict[str, list[str]] = {}
    for match in OXFORD_CITATION_FIELD_PATTERN.finditer(raw):
        key = normalize_text(match.group("key")).lower()
        value = normalize_text(match.group("value"))
        if key and value:
            fields.setdefault(key, []).append(value)
    if not fields:
        cleaned_raw = _clean_reference_sentence(raw)
        return (
            {"raw": cleaned_raw, "doi": None, "title": None, "year": None}
            if cleaned_raw
            else {}
        )

    authors = fields.get("citation_author") or []
    author_text = ", ".join(
        normalize_text(author).rstrip(" ,;")
        for author in authors
        if normalize_text(author)
    )
    year = _first_citation_field(fields, "citation_year")
    title = _first_citation_field(fields, "citation_title")
    journal = _first_citation_field(fields, "citation_journal_title")
    publisher = _first_citation_field(fields, "citation_publisher")
    volume = _first_citation_field(fields, "citation_volume")
    pages = _first_citation_field(fields, "citation_pages")
    doi = _first_citation_field(fields, "citation_doi") or None

    parts: list[str] = []
    lead = author_text
    if year:
        lead = f"{lead} ({year})" if lead else f"({year})"
    if title:
        lead = f"{lead}. {title}" if lead else title
    _append_reference_part(parts, lead)

    publication_parts = [item for item in (journal, volume, pages) if item]
    _append_reference_part(parts, ", ".join(publication_parts))
    _append_reference_part(parts, publisher)
    cleaned_raw = _clean_reference_sentence(". ".join(parts) or raw)
    return {
        "raw": cleaned_raw,
        "doi": doi,
        "title": title or None,
        "year": year or None,
    }


def merge_metadata_with_html(
    metadata: Mapping[str, Any],
    html_text: str,
    source_url: str,
    *,
    doi: str | None = None,
) -> dict[str, Any]:
    merged = merge_html_metadata(
        dict(metadata or {}),
        parse_html_metadata(html_text, source_url),
    )
    normalized_doi = normalize_doi(str(merged.get("doi") or doi or ""))
    if normalized_doi and not merged.get("doi"):
        merged["doi"] = normalized_doi
    references = extract_numbered_references_from_html(
        html_text
    ) or citation_reference_metadata(merged)
    if references:
        merged_payload: dict[str, Any] = dict(merged)
        merged_payload["references"] = references
        return merged_payload
    return dict(merged)


def _supplementary_lines(soup: BeautifulSoup) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for selector in OXFORDACADEMIC_SUPPLEMENTARY_LINK_SELECTORS:
        class_name = _selector_class_name(selector)
        nodes = (
            _nodes_with_class(soup, class_name) if class_name else soup.select(selector)
        )
        for node in nodes:
            text = render_clean_text_from_html(
                node,
                collapse_prose_line_breaks=True,
            )
            if not text:
                continue
            normalized = normalize_text(text)
            lowered = normalized.lower()
            if (
                "supplementary" not in lowered
                and "/oup/backfile/" not in str(node).lower()
            ):
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            lines.append(f"- {text}")
    return lines


def _article_body(soup: BeautifulSoup) -> Any:
    return (
        _first_with_class(soup, "article-body")
        or _first_with_class(soup, "widget-ArticleFulltext")
        or soup.find("article")
        or soup.body
        or soup
    )


def _normalize_oxford_body_for_rendering(body: Any) -> None:
    if not isinstance(body, Tag):
        return
    for node in _nodes_with_class(
        body,
        OXFORDACADEMIC_PARAGRAPH_BLOCK_CLASS,
        tag_name="div",
    ):
        node.name = "p"
    for comment in body.find_all(string=lambda value: isinstance(value, Comment)):
        if "citationlinks" in str(comment).lower():
            comment.extract()


def extract_markdown(
    html_text: str,
    source_url: str,
    *,
    metadata: Mapping[str, Any],
    asset_profile: AssetProfile = "all",
) -> OxfordAcademicExtraction:
    merged_metadata = merge_metadata_with_html(
        metadata,
        html_text,
        source_url,
        doi=str(metadata.get("doi") or ""),
    )
    title = str(merged_metadata.get("title") or merged_metadata.get("doi") or "")
    soup = BeautifulSoup(html_text, choose_parser())
    supplementary_lines = _supplementary_lines(soup)
    body = _article_body(soup)
    _normalize_oxford_body_for_rendering(body)
    for selector in OXFORDACADEMIC_EXTRACTION_CLEANUP_SELECTORS:
        class_name = _selector_class_name(selector)
        nodes = (
            _nodes_with_class(body, class_name) if class_name else body.select(selector)
        )
        for node in list(nodes):
            node.decompose()

    table_replacements: dict[str, str] = {}
    for index, wrapper in enumerate(
        list(_nodes_with_class(body, "table-wrap")), start=1
    ):
        overflow = _first_with_class(wrapper, "table-overflow")
        table = overflow.find("table") if overflow is not None else None
        table = table or wrapper.find("table")
        if table is None:
            continue
        label = render_clean_text_from_html(_first_with_class(wrapper, "label"))
        caption = render_clean_text_from_html(
            _first_with_class(wrapper, "caption"),
            collapse_prose_line_breaks=True,
        )
        rendered_table = render_table_markdown(table, label=label, caption=caption)
        if not normalize_text(rendered_table):
            continue
        marker = f"PAPER_FETCH_OXFORDACADEMIC_TABLE_{index:04d}"
        table_replacements[marker] = rendered_table
        marker_node = soup.new_tag("p")
        marker_node.string = marker
        wrapper.replace_with(marker_node)

    section_hints = collect_html_section_hints(body, title=title)
    abstract_sections = collect_html_abstract_blocks(body)
    lines: list[str] = []
    render_container_markdown(body, lines, level=2)
    markdown = clean_rendered_markdown("\n".join(lines))
    for marker, rendered_table in table_replacements.items():
        markdown = markdown.replace(marker, rendered_table)
    markdown = clean_rendered_markdown(markdown)
    markdown = "\n".join(
        line
        for line in markdown.splitlines()
        if normalize_text(line) not in OXFORDACADEMIC_MARKDOWN_NOISE_LINES
    )
    if supplementary_lines:
        markdown = clean_rendered_markdown(
            markdown + "\n\n## Supplementary Files\n\n" + "\n".join(supplementary_lines)
        )
    body_html = str(body)
    return OxfordAcademicExtraction(
        markdown_text=markdown,
        metadata=merged_metadata,
        html_text=body_html,
        abstract_sections=abstract_sections,
        section_hints=section_hints,
        extracted_assets=html_assets.extract_scoped_html_assets(
            body_html,
            source_url,
            asset_profile=asset_profile,
        ),
    )


def pdf_candidate_urls(
    metadata: Mapping[str, Any],
    *,
    html_text: str | None = None,
    source_url: str | None = None,
    doi: str | None = None,
) -> list[str]:
    candidates: list[str] = []
    metadata_pdf_url = extract_pdf_url_from_metadata_links(metadata)
    if metadata_pdf_url:
        extend_unique(candidates, [metadata_pdf_url])
    for value in (
        source_url,
        str(metadata.get("source_url") or ""),
        str(metadata.get("landing_page_url") or ""),
    ):
        normalized = normalize_text(value)
        if normalized and (
            "/article-pdf/" in normalized.lower() or normalized.lower().endswith(".pdf")
        ):
            extend_unique(candidates, [normalized])
    if html_text and source_url:
        extend_unique(
            candidates, extract_pdf_candidate_urls_from_html(html_text, source_url)
        )
    normalized_doi = normalize_doi(str(doi or metadata.get("doi") or ""))
    if normalized_doi:
        extend_unique(
            candidates,
            [
                f"https://academic.oup.com/doi/pdf/{normalized_doi}",
                f"https://academic.oup.com/doi/epdf/{normalized_doi}",
            ],
        )
    return candidates


__all__ = [
    "OXFORDACADEMIC_EXTRACTION_CLEANUP_SELECTORS",
    "OXFORDACADEMIC_FRONT_MATTER_CONTAINS_TOKENS",
    "OXFORDACADEMIC_FRONT_MATTER_EXACT_TEXTS",
    "OXFORDACADEMIC_FRONT_MATTER_PUBLICATION_KEYWORDS",
    "OXFORDACADEMIC_MARKDOWN_PROMO_TOKENS",
    "OXFORDACADEMIC_NOISE_PROFILE",
    "OXFORDACADEMIC_SITE_RULE_OVERRIDES",
    "OXFORDACADEMIC_SUPPLEMENTARY_TEXT_TOKENS",
    "OxfordAcademicExtraction",
    "citation_reference_metadata",
    "extract_markdown",
    "is_oxfordacademic_url",
    "merge_metadata_with_html",
    "pdf_candidate_urls",
]
