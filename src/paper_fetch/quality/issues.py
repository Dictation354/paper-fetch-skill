"""Shared article issue-flag diagnostics."""

from __future__ import annotations

import re
from typing import Any, Sequence

from ..models import (
    LEADING_ABSTRACT_CONTEXT_HEADINGS,
    FetchEnvelope,
    estimate_tokens,
    filtered_body_sections,
    strip_markdown_images,
)
from ..utils import normalize_text

EXPECTED_FULLTEXT_SOURCES_BY_PROVIDER = {
    "elsevier": frozenset({"elsevier_xml", "elsevier_pdf"}),
    "springer": frozenset({"springer_html"}),
    "wiley": frozenset({"wiley_browser"}),
    "science": frozenset({"science"}),
    "pnas": frozenset({"pnas"}),
}
ASCII_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/[!-~]+$")
RESEARCH_BRIEFING_HEADING_SIGNATURE = (
    "the question",
    "the discovery",
    "the implications",
    "expert opinion",
    "behind the paper",
    "from the editor",
)
ABSTRACT_INFLATED_TOKEN_THRESHOLD = 900
ABSTRACT_INFLATED_CHAR_THRESHOLD = 3500
ABSTRACT_INFLATED_WITH_OVERLAP_TOKEN_THRESHOLD = 600
ABSTRACT_INFLATED_WITH_OVERLAP_CHAR_THRESHOLD = 2600
OVERLAP_SINGLE_CHUNK_MIN_CHARS = 240
OVERLAP_MULTI_CHUNK_MIN_CHARS = 160
OVERLAP_MULTI_CHUNK_MATCHES = 2
PRIMARY_ABSTRACT_HEADINGS = frozenset({"abstract", "structured abstract", "summary"})


def normalize_issue_heading(value: Any) -> str:
    return normalize_text(value).lower().strip(" :")


def normalize_issue_section_text(value: Any) -> str:
    return strip_markdown_images(str(value or ""))


def issue_abstract_sections(article: Any) -> list[Any]:
    return [
        section
        for section in (getattr(article, "sections", []) or [])
        if normalize_text(getattr(section, "kind", "")).lower() == "abstract"
        and normalize_issue_section_text(getattr(section, "text", ""))
    ]


def is_issue_primary_abstract_heading(heading: str) -> bool:
    return normalize_issue_heading(heading) in PRIMARY_ABSTRACT_HEADINGS


def is_leading_abstract_context_heading(heading: str) -> bool:
    return normalize_issue_heading(heading) in LEADING_ABSTRACT_CONTEXT_HEADINGS


def metadata_matches_leading_abstract_context(metadata_abstract: str, abstract_sections: Sequence[Any]) -> bool:
    normalized_metadata = normalize_issue_section_text(metadata_abstract)
    if not normalized_metadata:
        return False
    return any(
        is_leading_abstract_context_heading(getattr(section, "heading", ""))
        and normalize_issue_section_text(getattr(section, "text", "")) == normalized_metadata
        for section in abstract_sections
    )


def resolve_issue_primary_abstract(article: Any) -> str:
    if article is None:
        return ""
    abstract_candidates = issue_abstract_sections(article)
    for section in abstract_candidates:
        if is_issue_primary_abstract_heading(getattr(section, "heading", "")):
            return normalize_issue_section_text(getattr(section, "text", ""))

    metadata = getattr(article, "metadata", None)
    metadata_abstract = normalize_issue_section_text(getattr(metadata, "abstract", None))
    if metadata_abstract and not metadata_matches_leading_abstract_context(metadata_abstract, abstract_candidates):
        return metadata_abstract

    for section in abstract_candidates:
        if not is_leading_abstract_context_heading(getattr(section, "heading", "")):
            return normalize_issue_section_text(getattr(section, "text", ""))
    return metadata_abstract


def collect_issue_flags(provider: str, envelope: FetchEnvelope, *, status: str) -> list[str]:
    issue_flags: list[str] = []
    article = envelope.article
    metadata = getattr(article, "metadata", None)
    abstract_text = resolve_issue_primary_abstract(article)
    body_sections = filtered_body_sections(getattr(article, "sections", []) or []) if article is not None else []
    body_text = "\n\n".join(normalize_text(section.text) for section in body_sections if normalize_text(section.text))

    if abstract_text and status == "fulltext":
        abstract_tokens = estimate_tokens(abstract_text)
        overlap_detected = bool(body_text) and has_abstract_body_overlap(abstract_text, body_text)
        if has_inflated_abstract(
            abstract_text,
            abstract_tokens=abstract_tokens,
            body_text=body_text,
            overlap_detected=overlap_detected,
        ):
            issue_flags.append("abstract_inflated")
        if overlap_detected:
            issue_flags.append("abstract_body_overlap")

    if article is not None and any(reference_doi_requires_normalization(item.doi) for item in article.references):
        issue_flags.append("refs_doi_not_normalized")
    if status == "fulltext" and envelope.source not in EXPECTED_FULLTEXT_SOURCES_BY_PROVIDER.get(provider, frozenset()):
        issue_flags.append("unexpected_source_path")
    if article is not None and not getattr(metadata, "authors", []) and not is_authorless_briefing_like(article):
        issue_flags.append("empty_authors")
    if len(envelope.warnings) >= 3:
        issue_flags.append("high_warning_count")
    return sorted(set(issue_flags))


def has_abstract_body_overlap(abstract_text: str, body_text: str) -> bool:
    normalized_body = normalize_overlap_text(body_text)
    if not normalized_body:
        return False
    matched_chunks = 0
    for chunk in overlap_chunks(abstract_text):
        if chunk in normalized_body:
            if len(chunk) >= OVERLAP_SINGLE_CHUNK_MIN_CHARS:
                return True
            matched_chunks += 1
            if matched_chunks >= OVERLAP_MULTI_CHUNK_MATCHES:
                return True
    return False


def has_inflated_abstract(
    abstract_text: str,
    *,
    abstract_tokens: int,
    body_text: str,
    overlap_detected: bool | None = None,
) -> bool:
    if abstract_tokens >= ABSTRACT_INFLATED_TOKEN_THRESHOLD or len(abstract_text) >= ABSTRACT_INFLATED_CHAR_THRESHOLD:
        return True
    if overlap_detected is None:
        overlap_detected = bool(body_text) and has_abstract_body_overlap(abstract_text, body_text)
    if overlap_detected and (
        abstract_tokens >= ABSTRACT_INFLATED_WITH_OVERLAP_TOKEN_THRESHOLD
        or len(abstract_text) >= ABSTRACT_INFLATED_WITH_OVERLAP_CHAR_THRESHOLD
    ):
        return True
    return False


def is_authorless_briefing_like(article: Any) -> bool:
    headings = [
        normalize_text(getattr(section, "heading", "")).lower()
        for section in filtered_body_sections(getattr(article, "sections", []) or [])
        if normalize_text(getattr(section, "heading", ""))
    ]
    if not headings:
        return False
    heading_set = set(headings)
    return all(item in heading_set for item in RESEARCH_BRIEFING_HEADING_SIGNATURE)


def overlap_chunks(text: str) -> list[str]:
    chunks = [
        normalize_overlap_text(item)
        for item in re.split(r"\n\s*\n", text)
        if len(normalize_overlap_text(item)) >= OVERLAP_MULTI_CHUNK_MIN_CHARS
    ]
    if not chunks:
        return []
    if len(chunks) == 1:
        return chunks
    return chunks


def normalize_overlap_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", normalize_text(text)).strip().lower()


def reference_doi_requires_normalization(doi: str | None) -> bool:
    normalized = normalize_text(doi)
    if not normalized:
        return False
    ascii_normalized = normalized.encode("ascii", errors="ignore").decode("ascii")
    lowered = normalized.lower()
    if ascii_normalized != normalized:
        return True
    if normalized.startswith(("http://", "https://", "doi:")):
        return True
    if any(character.isspace() for character in normalized):
        return True
    return not ASCII_DOI_PATTERN.match(lowered)


__all__ = [
    "collect_issue_flags",
    "has_abstract_body_overlap",
    "has_inflated_abstract",
    "is_authorless_briefing_like",
    "reference_doi_requires_normalization",
]
