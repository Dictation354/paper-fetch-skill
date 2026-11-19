"""Unified HTML and Markdown section-structure scanning for availability checks."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..extraction.html.front_matter import ARTICLE_TYPE_FRONT_MATTER_PREFIXES
from ..extraction.html.parsing import choose_parser
from ..extraction.html.provider_rules import (
    availability_rules_for_provider,
    front_matter_footer_prefixes,
)
from ..extraction.html.section_scan import SectionScanState, SectionStateName
from ..extraction.html.semantics import (
    category_for_section_hint_kind,
    classify_html_paragraph,
    coerce_html_section_hints,
    container_has_explicit_body_container,
    heading_category,
    iter_html_blocks,
    looks_like_explicit_body_container,
    match_next_html_section_hint,
    normalize_heading,
)
from ..extraction.html.signals import (
    contains_access_gate_text,
    matched_access_gate_patterns,
)
from ..utils import normalize_text
from ._container_cleanup import (
    HtmlContainerEvidence,
    clean_availability_container,
    html_container_evidence,
    select_container,
)
from .html_signals import (
    AvailabilityOverrideState,
    apply_availability_overrides,
    dedupe_signals,
)

# Narrative labels relax structural availability thresholds for short
# commentary/news-style content. They are not front-matter cleanup tokens; the
# provider cleanup layer keeps its own article-type chrome vocabulary.
NARRATIVE_ARTICLE_TYPES = {
    "review",
    "perspective",
    "commentary",
    "analysis",
    "news",
    "research briefing",
    "editorial",
}
NARRATIVE_BODY_RUN_MIN_CHARS = 400

_BARRIER_SECTION_CATEGORIES = frozenset(
    {
        "front_matter",
        "abstract",
        "references_or_back_matter",
        "ancillary",
        "data_availability",
        "code_availability",
    }
)
_ENABLED_SCAN_STATES: frozenset[SectionStateName] = frozenset(
    {
        "body",
        "abstract",
        "back_matter",
        "front_matter",
        "data_availability",
        "auxiliary",
    }
)
_ACCESS_PAGE_URL_TOKENS = (
    "/abstract",
    "/summary",
    "/doi/abs/",
    "/article/access",
    "/access",
    "/article-abstract",
)
_FRONT_MATTER_PARAGRAPH_TOKENS = (
    "published",
    "accepted",
    "received",
    "author information",
    "authors info",
    "citation",
    "view options",
    "metrics & citations",
)
_MARKDOWN_HEADING_RE = re.compile(r"^(#+)\s*(.*)$")


@dataclass
class StructuredBodyAnalysis:
    body_marker_present: bool = False
    substantive_article_container: bool = False
    explicit_body_container: bool = False
    substantive_body_container: bool = False
    post_abstract_body_run: bool = False
    narrative_article_type: bool = False
    paywall_text_outside_body_ignored: bool = False
    body_run_paragraph_count: int = 0
    body_run_char_count: int = 0
    body_paragraph_count: int = 0
    body_candidate_text: str = ""
    paywall_gate_detected: bool = False
    page_has_paywall_text: bool = False
    container_has_paywall_text: bool = False
    access_gate_markers: list[str] = field(default_factory=list)
    provider_hard_negative_signals: list[str] = field(default_factory=list)
    provider_abstract_only_hints: list[str] = field(default_factory=list)
    provider_blocking_fallback_signals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DomStructureScanInput:
    soup: BeautifulSoup
    provider: str | None = None
    title: str | None = None
    metadata: Mapping[str, Any] | None = None
    final_url: str | None = None
    article_type: str | None = None
    page_text: str | None = None


@dataclass(frozen=True)
class DomStructureScanResult:
    analysis: StructuredBodyAnalysis
    container_evidence: HtmlContainerEvidence | None
    container_text_length: int | None


def _sentence_count(text: str) -> int:
    return sum(
        1
        for item in re.split(r"(?<=[.!?])\s+", normalize_text(text))
        if normalize_text(item)
    )


def is_substantial_prose(text: str) -> bool:
    normalized = normalize_text(text)
    return len(normalized) >= 80 or _sentence_count(normalized) >= 2


def extract_article_type(
    metadata: Mapping[str, Any] | None,
    *,
    html_text: str | None = None,
    soup: BeautifulSoup | None = None,
) -> str | None:
    metadata_map = dict(metadata or {})
    for key in ("article_type", "type", "subtype"):
        value = normalize_text(metadata_map.get(key))
        if value:
            return value
    if soup is None:
        if not html_text:
            return None
        soup = BeautifulSoup(html_text, choose_parser())
    for selector in (
        "meta[name='citation_article_type']",
        "meta[property='article:section']",
        "[data-article-type]",
    ):
        node = soup.select_one(selector)
        if node is None:
            continue
        if node.name == "meta":
            value = normalize_text(
                (getattr(node, "attrs", None) or {}).get("content", "")
            )
        else:
            attrs = getattr(node, "attrs", None) or {}
            value = normalize_text(
                str(attrs.get("data-article-type") or node.get_text(" ", strip=True))
            )
        if value:
            return value
    return None


def is_narrative_article_type(article_type: str | None) -> bool:
    return normalize_heading(article_type or "") in NARRATIVE_ARTICLE_TYPES


def final_url_looks_like_access_page(final_url: str | None) -> bool:
    normalized = normalize_text(final_url or "").lower()
    if not normalized:
        return False
    return any(token in normalized for token in _ACCESS_PAGE_URL_TOKENS)


def _looks_like_front_matter_paragraph(text: str, *, title: str | None = None) -> bool:
    normalized = normalize_text(text)
    lowered = normalized.lower()
    if not lowered:
        return False
    if title:
        normalized_title = normalize_text(title).lower()
        if lowered == normalized_title:
            return True
        compact_text = re.sub(r"\s+", "", lowered)
        compact_title = re.sub(r"\s+", "", normalized_title)
        if compact_title and compact_text.endswith(compact_title):
            for prefix in ARTICLE_TYPE_FRONT_MATTER_PREFIXES:
                if compact_text.startswith(re.sub(r"\s+", "", prefix)):
                    return True
    if any(lowered.startswith(prefix) for prefix in front_matter_footer_prefixes()):
        return True
    return any(token in lowered for token in _FRONT_MATTER_PARAGRAPH_TOKENS)


def _substantive_explicit_body_container(container: Tag) -> bool:
    candidates = [
        node
        for node in (container, *container.find_all(True))
        if isinstance(node, Tag) and looks_like_explicit_body_container(node)
    ]
    for candidate in candidates:
        paragraphs = [
            normalize_text(node.get_text(" ", strip=True))
            for node in candidate.find_all("p")
            if isinstance(node, Tag)
        ]
        if any(is_substantial_prose(text) for text in paragraphs):
            return True
        if not paragraphs and is_substantial_prose(
            normalize_text(candidate.get_text(" ", strip=True))
        ):
            return True
    return False


def _substantive_article_container(container: Tag) -> bool:
    candidates = (
        [container]
        if normalize_text(str(container.name or "")).lower() == "article"
        else []
    )
    candidates.extend(
        node for node in container.find_all("article") if isinstance(node, Tag)
    )
    return any(
        is_substantial_prose(normalize_text(node.get_text(" ", strip=True)))
        for node in candidates
    )


def _apply_availability_override_policy(
    *,
    provider: str | None,
    soup: BeautifulSoup,
    analysis: StructuredBodyAnalysis,
    final_url: str | None,
    metadata: Mapping[str, Any] | None,
) -> None:
    policy = availability_rules_for_provider(provider)
    if policy.overrides is None:
        return
    state = AvailabilityOverrideState(
        final_url=final_url,
        metadata=metadata,
        soup=soup,
        structure=analysis,
    )
    apply_availability_overrides(state, policy.overrides)
    analysis.provider_hard_negative_signals = dedupe_signals(
        state.hard_negative_signals or []
    )
    analysis.provider_abstract_only_hints = dedupe_signals(
        state.abstract_only_hints or []
    )
    analysis.provider_blocking_fallback_signals = dedupe_signals(
        state.blocking_fallback_signals or []
    )


class _SectionStructureScanner:
    """Shared state-machine driver for HTML and Markdown block streams."""

    def __init__(self, *, analysis: StructuredBodyAnalysis, title: str | None) -> None:
        self.analysis = analysis
        self.state = SectionScanState(enabled_states=_ENABLED_SCAN_STATES)
        self._normalized_title = normalize_heading(title or "")
        self._body_chunks: list[str] = []

    def record_gate_markers(self, text: str) -> None:
        markers = matched_access_gate_patterns(text)
        if markers:
            self.analysis.access_gate_markers.extend(markers)

    def matches_document_title(self, heading_text: str) -> bool:
        if (
            self._normalized_title
            and normalize_heading(heading_text) == self._normalized_title
        ):
            self.state.transition("front_matter", is_heading=False)
            self.state.reset_body_run()
            return True
        return False

    def advance(self, text: str, category: str, *, is_heading: bool) -> None:
        if category in _BARRIER_SECTION_CATEGORIES:
            self.state.transition(category, is_heading=is_heading)
            self.state.reset_body_run()
            return
        if category == "body_heading":
            self.state.transition(category, is_heading=is_heading)
            return
        if category != "body_paragraph":
            return

        self._body_chunks.append(text)
        self.state.record_body_paragraph(text_len=len(normalize_text(text)))
        self.analysis.body_paragraph_count = self.state.body_paragraph_count
        self.analysis.body_run_paragraph_count = self.state.body_run_paragraph_count
        self.analysis.body_run_char_count = self.state.body_run_char_count
        if self.state.abstract_seen and self.state.body_heading_after_abstract:
            self.analysis.post_abstract_body_run = True

    def finalize(self) -> StructuredBodyAnalysis:
        self.analysis.body_candidate_text = "\n\n".join(self._body_chunks)
        self.analysis.access_gate_markers = dedupe_signals(
            self.analysis.access_gate_markers
        )
        return self.analysis


def scan_dom_structure(
    scan_input: DomStructureScanInput,
    *,
    select_container_fn: Callable[[BeautifulSoup, str | None], Tag | None] = (
        select_container
    ),
    clean_container_fn: Callable[[Tag, str | None], Tag] = clean_availability_container,
) -> DomStructureScanResult:
    """Analyze an isolated DOM with availability container selection and cleanup."""
    soup = scan_input.soup
    provider = scan_input.provider
    title = scan_input.title
    resolved_article_type = scan_input.article_type or extract_article_type(
        scan_input.metadata, soup=soup
    )
    analysis = StructuredBodyAnalysis(
        narrative_article_type=is_narrative_article_type(resolved_article_type)
    )
    page_text = (
        scan_input.page_text
        if scan_input.page_text is not None
        else normalize_text(" ".join(soup.stripped_strings))
    )
    container = select_container_fn(soup, provider)
    if container is None:
        _apply_availability_override_policy(
            provider=provider,
            soup=soup,
            analysis=analysis,
            final_url=scan_input.final_url,
            metadata=scan_input.metadata,
        )
        return DomStructureScanResult(analysis, None, None)

    clean_container_fn(container, provider)
    container_evidence = html_container_evidence(container)
    analysis.body_marker_present = container_has_explicit_body_container(container)
    analysis.substantive_article_container = _substantive_article_container(container)
    analysis.substantive_body_container = _substantive_explicit_body_container(
        container
    )
    analysis.explicit_body_container = analysis.substantive_body_container
    container_text = normalize_text(container.get_text(" ", strip=True))
    analysis.page_has_paywall_text = contains_access_gate_text(page_text)
    analysis.container_has_paywall_text = contains_access_gate_text(container_text)

    scanner = _SectionStructureScanner(analysis=analysis, title=title)
    for block in iter_html_blocks(container):
        kind = block["kind"]
        if kind == "marker":
            analysis.body_marker_present = True
            continue

        node = block["node"]
        text = block["text"]
        scanner.record_gate_markers(text)
        if kind == "heading":
            if scanner.matches_document_title(text):
                continue
            category = heading_category(
                normalize_text(node.name or "").lower(), text, title=title
            )
            scanner.advance(text, category, is_heading=True)
        elif kind == "figure_or_table":
            continue
        else:
            category = classify_html_paragraph(
                node,
                text,
                title=title,
                in_back_matter=scanner.state.in_back_matter,
                in_front_matter=scanner.state.in_front_matter,
                in_abstract=scanner.state.in_abstract,
                in_data_availability=scanner.state.in_data_availability,
                in_auxiliary=scanner.state.in_auxiliary,
                looks_like_front_matter_paragraph=lambda value: (
                    _looks_like_front_matter_paragraph(value, title=title)
                ),
                is_substantial_prose=is_substantial_prose,
                looks_like_access_gate_text=contains_access_gate_text,
            )
            scanner.advance(text, category, is_heading=False)

    scanner.finalize()
    analysis.paywall_text_outside_body_ignored = (
        analysis.page_has_paywall_text
        and not analysis.container_has_paywall_text
        and analysis.body_paragraph_count > 0
    )
    analysis.paywall_gate_detected = analysis.body_paragraph_count == 0 and (
        analysis.container_has_paywall_text
        or final_url_looks_like_access_page(scan_input.final_url)
    )
    _apply_availability_override_policy(
        provider=provider,
        soup=soup,
        analysis=analysis,
        final_url=scan_input.final_url,
        metadata=scan_input.metadata,
    )
    return DomStructureScanResult(
        analysis=analysis,
        container_evidence=container_evidence,
        container_text_length=len(" ".join(container.stripped_strings)),
    )


def _classify_markdown_paragraph(
    block: str, state: SectionScanState, *, title: str | None
) -> str:
    if state.in_back_matter:
        return "references_or_back_matter"
    if state.in_front_matter:
        return "front_matter"
    if state.in_data_availability:
        return "data_availability"
    if state.in_abstract:
        return "abstract"
    if state.in_auxiliary or contains_access_gate_text(block):
        return "ancillary"
    if is_substantial_prose(block) and not _looks_like_front_matter_paragraph(
        block, title=title
    ):
        return "body_paragraph"
    return "front_matter"


def scan_markdown_structure(
    markdown_text: str,
    *,
    metadata: Mapping[str, Any] | None,
    title: str | None,
    section_hints: Any = None,
) -> StructuredBodyAnalysis:
    analysis = StructuredBodyAnalysis(
        narrative_article_type=is_narrative_article_type(extract_article_type(metadata))
    )
    blocks = [
        normalize_text(block)
        for block in re.split(r"\n\s*\n", markdown_text)
        if normalize_text(block)
    ]
    coerced_section_hints = coerce_html_section_hints(section_hints)
    section_hint_index = 0
    scanner = _SectionStructureScanner(analysis=analysis, title=title)

    for block in blocks:
        stripped = block.strip()
        is_heading = stripped.startswith("#")
        scanner.record_gate_markers(block)
        if is_heading:
            match = _MARKDOWN_HEADING_RE.match(stripped)
            heading = normalize_text(match.group(2) if match else stripped)
            level = len(match.group(1)) if match else 2
            if scanner.matches_document_title(heading):
                continue
            matched_hint, next_hint_index = match_next_html_section_hint(
                coerced_section_hints, section_hint_index, heading
            )
            if matched_hint is not None:
                section_hint_index = next_hint_index
                category = category_for_section_hint_kind(matched_hint["kind"])
            else:
                category = heading_category(f"h{min(level, 6)}", heading, title=title)
            scanner.advance(block, category, is_heading=True)
        else:
            category = _classify_markdown_paragraph(block, scanner.state, title=title)
            scanner.advance(block, category, is_heading=False)

    return scanner.finalize()


def structure_accepts_fulltext(analysis: StructuredBodyAnalysis) -> bool:
    if (
        analysis.explicit_body_container
        and analysis.body_run_paragraph_count >= 1
        and analysis.body_run_char_count >= 80
    ):
        return True
    if (
        analysis.substantive_article_container
        and analysis.post_abstract_body_run
        and analysis.body_run_paragraph_count >= 1
        and analysis.body_run_char_count >= 80
    ):
        return True
    if analysis.post_abstract_body_run and analysis.body_run_paragraph_count >= 2:
        return True
    if analysis.body_run_paragraph_count >= 3:
        return True
    return bool(
        analysis.narrative_article_type
        and (
            analysis.body_run_paragraph_count >= 2
            or (
                analysis.explicit_body_container
                and analysis.body_run_char_count >= NARRATIVE_BODY_RUN_MIN_CHARS
            )
        )
    )
