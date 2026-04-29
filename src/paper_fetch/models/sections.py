"""Section parsing and section hint helpers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from difflib import SequenceMatcher
from typing import Any, Mapping

from ..extraction.section_hints import (
    SECTION_HINT_KINDS,
    coerce_section_hint_dicts,
    match_next_section_hint,
    normalize_section_hint_heading,
)
from ..markdown.citations import normalize_inline_citation_markdown
from ..utils import normalize_text
from .markdown import (
    INLINE_MARKDOWN_ABSTRACT_PREFIX_PATTERN,
    _canonical_match_text,
    normalize_abstract_text,
    normalize_authors,
    normalize_markdown_text,
    strip_markdown_images,
)
from .schema import ExtractedAbstractBlock, Section, SectionHint

BODY_SECTION_EXCLUDED_KINDS = frozenset(
    {"abstract", "references", "supplementary", "diagnostics", "data_availability", "code_availability"}
)


RETAINED_NON_BODY_SECTION_KINDS = frozenset({"data_availability", "code_availability"})


ABSTRACT_SECTION_HEADINGS = frozenset(
    {
        "abstract",
        "structured abstract",
        "summary",
        "resumo",
        "resumen",
        "resume",
        "résumé",
        "zusammenfassung",
    }
)


DATA_AVAILABILITY_SECTION_HEADINGS = frozenset(
    {
        "data availability",
        "data availability statement",
        "data, materials, and software availability",
        "data, code, and materials availability",
        "availability of data and materials",
    }
)


CODE_AVAILABILITY_SECTION_HEADINGS = frozenset(
    {
        "code availability",
        "code availability statement",
        "software availability",
        "software availability statement",
    }
)


PRESERVE_EMPTY_PARENT_SECTION_HEADINGS = frozenset(
    {
        "methods",
        "materials and methods",
        "methodology",
    }
)


SECTION_PRIORITY = {
    "significance": -1,
    "significance statement": -1,
    "abstract": 0,
    "introduction": 1,
    "background": 1,
    "methods": 2,
    "materials and methods": 2,
    "methodology": 2,
    "results": 3,
    "findings": 3,
    "discussion": 4,
    "conclusion": 5,
    "conclusions": 5,
    "abbreviations": 6,
    "data availability": 6,
    "data availability statement": 6,
    "data, materials, and software availability": 6,
    "data, code, and materials availability": 6,
    "availability of data and materials": 6,
    "code availability": 6,
    "code availability statement": 6,
    "software availability": 6,
    "software availability statement": 6,
    "references": 6,
}


LEADING_ABSTRACT_CONTEXT_HEADINGS = frozenset({"significance", "significance statement"})


ABSTRACT_NEAR_DUPLICATE_SIMILARITY_THRESHOLD = 0.995


ABSTRACT_NEAR_DUPLICATE_MAX_LENGTH_DELTA = 64


BODY_ABSTRACT_PARAGRAPH_NEAR_DUPLICATE_SIMILARITY_THRESHOLD = 0.989


BODY_ABSTRACT_PARAGRAPH_NEAR_DUPLICATE_MAX_LENGTH_DELTA = 64


def section_kind_for_heading(heading: str) -> str:
    normalized = normalize_text(heading).lower()
    if not normalized:
        return "body"
    if normalized in {"references", "bibliography"}:
        return "references"
    if normalized in {"supplementary materials", "supplementary information"}:
        return "supplementary"
    if normalized in {"conversion notes"}:
        return "diagnostics"
    from ..extraction.html.semantics import heading_category as html_heading_category

    category = html_heading_category("h2", heading)
    if category in {"data_availability", "code_availability"}:
        return category
    if category == "references_or_back_matter":
        return "references"
    if category == "abstract":
        return "abstract"
    if category == "ancillary":
        return "diagnostics"
    return "body"


def _should_preserve_empty_parent_section(heading: str, current_level: int, next_level: int) -> bool:
    if next_level <= current_level:
        return False
    normalized = normalize_text(heading)
    if not normalized:
        return False
    return section_kind_for_heading(normalized) == "body"


def section_priority(section: "Section") -> int:
    normalized = normalize_text(section.heading).lower()
    if normalized in SECTION_PRIORITY:
        return SECTION_PRIORITY[normalized]
    for key, priority in SECTION_PRIORITY.items():
        if key in normalized:
            return priority
    return 4


def _normalized_text_field(value: Any) -> str:
    return normalize_text(value) if isinstance(value, str) else ""


def filtered_body_sections(sections: Sequence["Section"]) -> list["Section"]:
    return [
        section
        for section in sections
        if strip_markdown_images(_normalized_text_field(getattr(section, "text", None)))
        and _normalized_text_field(getattr(section, "kind", None)).lower() not in BODY_SECTION_EXCLUDED_KINDS
    ]


def renderable_body_sections(sections: Sequence["Section"]) -> list["Section"]:
    renderable: list[Section] = []
    section_list = list(sections)
    for index, section in enumerate(section_list):
        kind = _normalized_text_field(getattr(section, "kind", None)).lower()
        if kind in BODY_SECTION_EXCLUDED_KINDS:
            continue
        if strip_markdown_images(_normalized_text_field(getattr(section, "text", None))):
            renderable.append(section)
            continue
        if kind != "body" or not _normalized_text_field(getattr(section, "heading", None)):
            continue
        for follower in section_list[index + 1 :]:
            follower_kind = _normalized_text_field(getattr(follower, "kind", None)).lower()
            if follower_kind in BODY_SECTION_EXCLUDED_KINDS:
                continue
            if not strip_markdown_images(_normalized_text_field(getattr(follower, "text", None))):
                continue
            if int(getattr(follower, "level", 0) or 0) > int(getattr(section, "level", 0) or 0):
                renderable.append(section)
            break
    return renderable


def abstract_sections(sections: Sequence["Section"]) -> list["Section"]:
    return [
        section
        for section in sections
        if strip_markdown_images(_normalized_text_field(getattr(section, "text", None)))
        and _normalized_text_field(getattr(section, "kind", None)).lower() == "abstract"
    ]


def first_abstract_text(*, abstract_text: str | None, sections: Sequence["Section"]) -> str:
    section_abstract = next(
        (
            strip_markdown_images(section.text)
            for section in abstract_sections(sections)
            if strip_markdown_images(section.text)
        ),
        "",
    )
    if section_abstract:
        return section_abstract
    return normalize_text(abstract_text)


def combine_abstract_text(*, abstract_text: str | None, sections: Sequence["Section"]) -> str:
    texts: list[str] = []
    seen: set[str] = set()
    for candidate in [normalize_text(abstract_text), *[strip_markdown_images(section.text) for section in abstract_sections(sections)]]:
        normalized_candidate = normalize_text(candidate)
        if not normalized_candidate:
            continue
        canonical_candidate = _canonical_match_text(normalized_candidate)
        if canonical_candidate in seen:
            continue
        texts.append(normalized_candidate)
        seen.add(canonical_candidate)
    return "\n\n".join(texts)


def split_leading_abstract_context_sections(
    sections: Sequence["Section"],
) -> tuple[tuple["Section", ...], tuple["Section", ...]]:
    lead_sections: list[Section] = []
    remaining_index = 0
    for index, section in enumerate(sections):
        normalized_heading = normalize_text(section.heading).lower()
        if normalized_heading in LEADING_ABSTRACT_CONTEXT_HEADINGS:
            lead_sections.append(section)
            remaining_index = index + 1
            continue
        break
    return tuple(lead_sections), tuple(sections[remaining_index:])


def _coerce_section_hints(
    section_hints: Sequence[SectionHint | Mapping[str, Any]] | None,
) -> list[SectionHint]:
    return [
        SectionHint(
            heading=hint["heading"],
            level=int(hint["level"]),
            kind=hint["kind"],
            order=int(hint["order"]),
            language=normalize_text(hint.get("language")) or None,
            source_selector=normalize_text(hint.get("source_selector")) or None,
        )
        for hint in coerce_section_hint_dicts(section_hints, allowed_kinds=SECTION_HINT_KINDS)
    ]


def _match_next_section_hint(
    section_hints: Sequence[SectionHint],
    hint_index: int,
    heading: str,
) -> tuple[SectionHint | None, int]:
    matched, next_index = match_next_section_hint(
        [
            {
                "heading": hint.heading,
                "heading_key": normalize_section_hint_heading(hint.heading),
            }
            for hint in section_hints
        ],
        hint_index,
        heading,
    )
    return (section_hints[next_index - 1], next_index) if matched is not None else (None, next_index)


def lines_to_sections(
    lines: list[str],
    *,
    fallback_heading: str = "Full Text",
    preserve_images: bool = False,
    section_hints: Sequence[SectionHint | Mapping[str, Any]] | None = None,
) -> list[Section]:
    sections: list[Section] = []
    current_heading = fallback_heading
    current_level = 2
    buffer: list[str] = []
    coerced_section_hints = _coerce_section_hints(section_hints)
    section_hint_index = 0

    def append_empty_section(heading: str, level: int) -> None:
        nonlocal section_hint_index
        matched_hint, section_hint_index = _match_next_section_hint(
            coerced_section_hints,
            section_hint_index,
            heading,
        )
        sections.append(
            Section(
                heading=heading,
                level=level,
                kind=matched_hint.kind if matched_hint is not None else section_kind_for_heading(heading),
                text="",
            )
        )

    def flush() -> None:
        nonlocal section_hint_index
        if not buffer:
            return
        raw_text = "\n".join(buffer)
        text = normalize_markdown_text(raw_text) if preserve_images else strip_markdown_images(raw_text)
        if not text:
            return
        matched_hint, section_hint_index = _match_next_section_hint(
            coerced_section_hints,
            section_hint_index,
            current_heading,
        )
        sections.append(
            Section(
                heading=current_heading,
                level=current_level,
                kind=matched_hint.kind if matched_hint is not None else section_kind_for_heading(current_heading),
                text=text,
            )
        )

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            next_level = len(stripped) - len(stripped.lstrip("#"))
            if not buffer and _should_preserve_empty_parent_section(current_heading, current_level, next_level):
                append_empty_section(current_heading, current_level)
            flush()
            buffer = []
            current_level = next_level
            current_heading = stripped[current_level:].strip() or fallback_heading
            continue
        if stripped or buffer:
            buffer.append(line.rstrip())
    flush()
    return sections


def _coerce_explicit_abstract_blocks(
    abstract_blocks: Sequence[ExtractedAbstractBlock | Mapping[str, Any] | Section] | None,
) -> list[ExtractedAbstractBlock]:
    coerced: list[ExtractedAbstractBlock] = []
    for index, block in enumerate(abstract_blocks or []):
        if isinstance(block, ExtractedAbstractBlock):
            candidate = block
        elif isinstance(block, Section):
            candidate = ExtractedAbstractBlock(
                heading=normalize_text(block.heading) or "Abstract",
                text=normalize_markdown_text(block.text),
                kind="abstract",
                order=index,
            )
        elif isinstance(block, Mapping):
            candidate = ExtractedAbstractBlock(
                heading=normalize_text(block.get("heading")) or "Abstract",
                text=normalize_markdown_text(str(block.get("text") or "")),
                language=normalize_text(block.get("language")) or None,
                kind=normalize_text(block.get("kind")) or "abstract",
                order=int(block.get("order") or index),
            )
        else:
            continue
        if not normalize_text(candidate.text):
            continue
        coerced.append(candidate)
    coerced.sort(key=lambda item: item.order)
    deduped: list[ExtractedAbstractBlock] = []
    for block in coerced:
        candidate_heading = _canonical_match_text(block.heading)
        candidate_text = _canonical_match_text(block.text)
        if any(
            candidate_heading == _canonical_match_text(existing.heading)
            and _is_near_duplicate_abstract_text(
                candidate_text,
                _canonical_match_text(existing.text),
            )
            for existing in deduped
        ):
            continue
        deduped.append(block)
    return deduped


def _abstract_sections_from_blocks(
    abstract_blocks: Sequence[ExtractedAbstractBlock | Mapping[str, Any] | Section] | None,
) -> list[Section]:
    sections: list[Section] = []
    for block in _coerce_explicit_abstract_blocks(abstract_blocks):
        sections.append(
            Section(
                heading=normalize_text(block.heading) or "Abstract",
                level=2,
                kind="abstract",
                text=normalize_markdown_text(block.text),
            )
        )
    return sections


def _abstract_sections_from_lines(abstract_lines: Sequence[str]) -> list[Section]:
    normalized_lines = [line.rstrip() for line in abstract_lines]
    sections = lines_to_sections(list(normalized_lines), fallback_heading="Abstract")
    if sections:
        return [
            Section(
                heading=normalize_text(section.heading) or "Abstract",
                level=section.level,
                kind="abstract",
                text=section.text,
            )
            for section in sections
            if normalize_text(section.text)
        ]
    fallback_text = strip_markdown_images("\n".join(normalized_lines))
    if not fallback_text:
        return []
    return [Section(heading="Abstract", level=2, kind="abstract", text=fallback_text)]


def _is_near_duplicate_abstract_text(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    if abs(len(left) - len(right)) > ABSTRACT_NEAR_DUPLICATE_MAX_LENGTH_DELTA:
        return False
    return (
        SequenceMatcher(None, left, right).ratio()
        >= ABSTRACT_NEAR_DUPLICATE_SIMILARITY_THRESHOLD
    )


def _abstract_sections_match(left: Section, right: Section) -> bool:
    left_heading = _canonical_match_text(left.heading)
    right_heading = _canonical_match_text(right.heading)
    if not left_heading or left_heading != right_heading:
        return False
    left_text = _canonical_match_text(strip_markdown_images(left.text))
    right_text = _canonical_match_text(strip_markdown_images(right.text))
    if not left_text or not right_text:
        return False
    return _is_near_duplicate_abstract_text(left_text, right_text)


def _is_near_duplicate_body_abstract_paragraph(left: str, right: str) -> bool:
    left_text = normalize_text(strip_markdown_images(left))
    right_text = normalize_text(strip_markdown_images(right))
    if not left_text or not right_text:
        return False
    if _canonical_match_text(left_text) == _canonical_match_text(right_text):
        return True
    if abs(len(left_text) - len(right_text)) > BODY_ABSTRACT_PARAGRAPH_NEAR_DUPLICATE_MAX_LENGTH_DELTA:
        return False
    return (
        SequenceMatcher(None, left_text, right_text).ratio()
        >= BODY_ABSTRACT_PARAGRAPH_NEAR_DUPLICATE_SIMILARITY_THRESHOLD
    )


def _section_matches_explicit_abstract(
    section: Section,
    explicit_abstract_sections: Sequence[Section],
) -> bool:
    if not explicit_abstract_sections:
        return False
    section_text = _canonical_match_text(strip_markdown_images(section.text))
    if not section_text:
        return False
    is_abstract_section = normalize_text(section.kind).lower() == "abstract"
    for candidate in explicit_abstract_sections:
        candidate_text = _canonical_match_text(strip_markdown_images(candidate.text))
        if section_text == candidate_text:
            return True
        if is_abstract_section and _abstract_sections_match(section, candidate):
            return True
    return False


def _strip_leading_explicit_abstract_paragraphs(
    section: Section,
    explicit_abstract_sections: Sequence[Section],
) -> Section | None:
    if not explicit_abstract_sections or normalize_text(section.kind).lower() != "body":
        return section

    abstract_paragraphs = [
        normalize_text(strip_markdown_images(paragraph))
        for candidate in explicit_abstract_sections
        for paragraph in re.split(r"\n\s*\n", candidate.text)
        if normalize_text(strip_markdown_images(paragraph))
    ]
    if not abstract_paragraphs:
        return section

    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", section.text)
        if normalize_text(strip_markdown_images(paragraph))
    ]
    leading_index = 0
    while leading_index < len(paragraphs):
        if not any(
            _is_near_duplicate_body_abstract_paragraph(paragraphs[leading_index], candidate)
            for candidate in abstract_paragraphs
        ):
            break
        leading_index += 1
    if leading_index == 0:
        return section
    remaining_text = normalize_markdown_text("\n\n".join(paragraphs[leading_index:]))
    if not remaining_text:
        return None
    return Section(
        heading=section.heading,
        level=section.level,
        kind=section.kind,
        text=remaining_text,
    )


def _promote_stripped_methods_summary_section(
    original_section: Section,
    stripped_section: Section | None,
    *,
    normalize_methods_summary: bool,
) -> Section | None:
    if normalize_text(original_section.kind).lower() != "body":
        return stripped_section
    if normalize_text(original_section.heading).lower() != "methods summary":
        return stripped_section
    if not normalize_methods_summary:
        return stripped_section
    if stripped_section is None:
        return Section(
            heading="Methods",
            level=original_section.level,
            kind=original_section.kind,
            text="",
        )
    if stripped_section.text == original_section.text:
        return stripped_section
    return Section(
        heading="Methods",
        level=stripped_section.level,
        kind=stripped_section.kind,
        text=stripped_section.text,
    )


def _coerced_section_hint_headings_and_sources(
    section_hints: Sequence[SectionHint | Mapping[str, Any]] | None,
) -> tuple[set[str], str]:
    headings: set[str] = set()
    sources: list[str] = []
    for hint in _coerce_section_hints(section_hints):
        normalized_heading = normalize_section_hint_heading(hint.heading)
        if normalized_heading:
            headings.add(normalized_heading)
        source_selector = normalize_text(hint.source_selector).lower()
        if source_selector:
            sources.append(source_selector)
    return headings, " ".join(sources)


def _has_old_nature_methods_summary_structure(
    parsed_sections: Sequence[Section],
    section_hints: Sequence[SectionHint | Mapping[str, Any]] | None,
) -> bool:
    parsed_headings = {normalize_text(section.heading).lower() for section in parsed_sections if normalize_text(section.heading)}
    if "methods summary" not in parsed_headings:
        return False
    if "online methods" in parsed_headings:
        return True

    hint_headings, hint_source_blob = _coerced_section_hint_headings_and_sources(section_hints)
    if "methods summary" in hint_headings and "online methods" in hint_headings:
        return True
    if "methods summary" in hint_headings and any(
        token in hint_source_blob
        for token in (
            "online-methods",
            "online_methods",
            "methods-summary",
            "methods_summary",
        )
    ):
        return True
    return False


def _normalize_inline_citations_in_section(section: Section) -> Section:
    normalized_text = normalize_inline_citation_markdown(section.text)
    if normalized_text == section.text:
        return section
    return Section(
        heading=section.heading,
        level=section.level,
        kind=section.kind,
        text=normalized_text,
    )


def split_leading_inline_abstract(sections: Sequence[Section]) -> tuple[str | None, list[Section]]:
    if not sections:
        return None, []

    first = sections[0]
    if normalize_text(first.kind).lower() != "body":
        return None, list(sections)

    paragraphs = [paragraph for paragraph in re.split(r"\n\s*\n", first.text) if normalize_text(paragraph)]
    if not paragraphs:
        return None, list(sections)

    first_paragraph = paragraphs[0].strip()
    if not INLINE_MARKDOWN_ABSTRACT_PREFIX_PATTERN.match(first_paragraph):
        return None, list(sections)

    if len(sections) == 1:
        return normalize_abstract_text(strip_markdown_images(first.text)) or None, []

    abstract_text = normalize_abstract_text(strip_markdown_images(first_paragraph)) or None
    remaining_text = normalize_markdown_text("\n\n".join(paragraphs[1:]))
    remaining_sections = list(sections)
    if remaining_text:
        replacement_heading = (
            "Main Text"
            if first.level <= 1 or normalize_text(first.heading).lower() in {"", "full text"}
            else first.heading
        )
        remaining_sections[0] = Section(
            heading=replacement_heading,
            level=first.level,
            kind=first.kind,
            text=remaining_text,
        )
    else:
        remaining_sections = remaining_sections[1:]
    return abstract_text, remaining_sections


__all__ = [
    "BODY_SECTION_EXCLUDED_KINDS",
    "RETAINED_NON_BODY_SECTION_KINDS",
    "ABSTRACT_SECTION_HEADINGS",
    "DATA_AVAILABILITY_SECTION_HEADINGS",
    "CODE_AVAILABILITY_SECTION_HEADINGS",
    "PRESERVE_EMPTY_PARENT_SECTION_HEADINGS",
    "SECTION_PRIORITY",
    "LEADING_ABSTRACT_CONTEXT_HEADINGS",
    "ABSTRACT_NEAR_DUPLICATE_SIMILARITY_THRESHOLD",
    "ABSTRACT_NEAR_DUPLICATE_MAX_LENGTH_DELTA",
    "BODY_ABSTRACT_PARAGRAPH_NEAR_DUPLICATE_SIMILARITY_THRESHOLD",
    "BODY_ABSTRACT_PARAGRAPH_NEAR_DUPLICATE_MAX_LENGTH_DELTA",
    "section_kind_for_heading",
    "section_priority",
    "filtered_body_sections",
    "renderable_body_sections",
    "abstract_sections",
    "first_abstract_text",
    "combine_abstract_text",
    "split_leading_abstract_context_sections",
    "lines_to_sections",
    "split_leading_inline_abstract",
    "normalize_authors",
    "normalize_abstract_text",
]
