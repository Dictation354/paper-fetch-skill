"""Shared HTML full-text availability diagnostics and structure analysis."""

from __future__ import annotations

import importlib.util
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from ..models import classify_article_content, filtered_body_sections
from ..utils import normalize_text
from . import html_noise as _html_noise
from ._html_access_signals import (
    contains_access_gate_text,
    detect_html_access_signals,
    html_failure_message,
    matched_access_gate_patterns,
)
from ._html_semantics import (
    BACK_MATTER_TOKENS,
    HTML_SECTION_HINT_KINDS,
    classify_html_paragraph,
    container_has_explicit_body_container,
    heading_category,
    iter_html_blocks,
    looks_like_explicit_body_container,
    node_identity_text,
    normalize_heading,
)
from ._science_pnas_profiles import (
    looks_like_abstract_redirect,
    provider_blocking_fallback_signals,
    provider_positive_signals,
    site_rule_for_publisher,
)

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None
    Tag = None

body_metrics = _html_noise.body_metrics
has_sufficient_article_body = _html_noise.has_sufficient_article_body
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
ARTICLE_TYPE_FRONT_MATTER_PREFIXES = (
    "regular paper",
    "research article",
    "original article",
    "review article",
    "short communication",
    "brief communication",
    "case report",
    "letter to the editor",
)


@dataclass
class StructuredBodyAnalysis:
    explicit_body_container: bool = False
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


@dataclass
class FulltextAvailabilityDiagnostics:
    accepted: bool
    reason: str
    content_kind: str
    blocking_fallback_signals: list[str] = field(default_factory=list)
    hard_negative_signals: list[str] = field(default_factory=list)
    strong_positive_signals: list[str] = field(default_factory=list)
    soft_positive_signals: list[str] = field(default_factory=list)
    body_metrics: dict[str, Any] = field(default_factory=dict)
    figure_count: int = 0
    title: str | None = None
    container_tag: str | None = None
    container_text_length: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def choose_parser() -> str:
    return "lxml" if importlib.util.find_spec("lxml") is not None else "html.parser"


def extract_page_title(soup: BeautifulSoup) -> str | None:
    for selector in ["h1", "meta[property='og:title']", "title"]:
        node = soup.select_one(selector)
        if node is None:
            continue
        if node.name == "meta":
            title = normalize_text((getattr(node, "attrs", None) or {}).get("content", ""))
        else:
            title = normalize_text(node.get_text(" ", strip=True))
        if title:
            return title
    return None


def _sentence_count(text: str) -> int:
    return len([item for item in re.split(r"(?<=[.!?])\s+", normalize_text(text)) if normalize_text(item)])


def _is_substantial_prose(text: str) -> bool:
    normalized = normalize_text(text)
    return len(normalized) >= 80 or _sentence_count(normalized) >= 2


def _looks_like_explicit_body_container(node: Tag | None) -> bool:
    return looks_like_explicit_body_container(node)


def _normalized_page_text(html_text: str) -> str:
    if BeautifulSoup is None:
        return normalize_text(re.sub(r"<[^>]+>", " ", html_text))
    soup = BeautifulSoup(html_text, choose_parser())
    return normalize_text(" ".join(soup.stripped_strings))


def _extract_article_type(
    metadata: Mapping[str, Any] | None,
    *,
    provider: str | None = None,
    html_text: str | None = None,
) -> str | None:
    metadata_map = dict(metadata or {})
    for key in ("article_type", "type", "subtype"):
        value = normalize_text(metadata_map.get(key))
        if value:
            return value
    if not html_text or BeautifulSoup is None:
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
            value = normalize_text((getattr(node, "attrs", None) or {}).get("content", ""))
        else:
            attrs = getattr(node, "attrs", None) or {}
            value = normalize_text(str(attrs.get("data-article-type") or node.get_text(" ", strip=True)))
        if value:
            return value
    if provider == "science" and soup.select_one(".perspective, .article-type-perspective"):
        return "Perspective"
    return None


def _is_narrative_article_type(article_type: str | None) -> bool:
    normalized = normalize_heading(article_type or "")
    return normalized in NARRATIVE_ARTICLE_TYPES


def _final_url_looks_like_access_page(final_url: str | None) -> bool:
    normalized = normalize_text(final_url or "").lower()
    if not normalized:
        return False
    return any(
        token in normalized
        for token in ("/abstract", "/summary", "/doi/abs/", "/article/access", "/access", "/article-abstract")
    )


def _detect_html_hard_negative_signals_impl(
    title: str,
    text: str,
    response_status: int | None,
    *,
    requested_url: str | None = None,
    final_url: str | None = None,
    include_paywall_text: bool = True,
    provider_metadata: Mapping[str, Any] | None = None,
) -> list[str]:
    redirected_to_abstract = bool(requested_url and looks_like_abstract_redirect(requested_url, final_url))
    return detect_html_access_signals(
        title,
        text,
        response_status,
        redirected_to_abstract=redirected_to_abstract,
        include_paywall_text=include_paywall_text,
        explicit_no_access=bool(provider_metadata and provider_metadata.get("explicit_no_access")),
    )


def detect_html_hard_negative_signals(
    title: str,
    text: str,
    response_status: int | None,
    *,
    requested_url: str | None = None,
    final_url: str | None = None,
) -> list[str]:
    return _detect_html_hard_negative_signals_impl(
        title,
        text,
        response_status,
        requested_url=requested_url,
        final_url=final_url,
        include_paywall_text=True,
    )


def score_container(node: Tag) -> float:
    text_length = len(normalize_text(node.get_text(" ", strip=True)))
    heading_count = len(node.find_all(re.compile(r"^h[1-6]$")))
    paragraph_count = len([child for child in node.find_all(["p", "div", "section", "article"]) if normalize_text(child.get_text(" ", strip=True))])
    figure_count = len(node.find_all(["figure", "table"]))
    identity = node_identity_text(node)
    identity_bonus = 0.0
    if looks_like_explicit_body_container(node):
        identity_bonus += 400.0
    if any(token in identity for token in BACK_MATTER_TOKENS):
        identity_bonus -= 120.0
    return float(text_length + heading_count * 200 + paragraph_count * 40 + figure_count * 20 + identity_bonus)


def select_best_container(soup: BeautifulSoup, publisher: str):
    selectors = site_rule_for_publisher(publisher)["candidate_selectors"]
    candidates: list[Tag] = []
    seen: set[int] = set()
    for selector in selectors:
        try:
            matches = soup.select(selector)
        except Exception:
            continue
        for match in matches:
            if not isinstance(match, Tag) or id(match) in seen:
                continue
            seen.add(id(match))
            candidates.append(match)
    if not candidates:
        body = soup.body
        return body if isinstance(body, Tag) else None
    return max(candidates, key=score_container)


def should_drop_node(node: Tag, publisher: str) -> bool:
    rule = site_rule_for_publisher(publisher)
    identity = node_identity_text(node)
    text = normalize_text(node.get_text(" ", strip=True))
    if any(token in identity for token in rule["drop_keywords"]):
        return True
    if text in rule["drop_text"]:
        return True
    if node.name in {"script", "style", "noscript", "iframe", "svg"}:
        return True
    try:
        return any(node.select_one(selector) is node for selector in rule["remove_selectors"])
    except Exception:
        return False


def clean_container(container: Tag, publisher: str) -> Tag:
    for selector in site_rule_for_publisher(publisher)["remove_selectors"]:
        try:
            for node in list(container.select(selector)):
                if isinstance(node, Tag):
                    node.decompose()
        except Exception:
            continue
    for node in list(container.find_all(True)):
        if should_drop_node(node, publisher):
            node.decompose()
    return container


def _looks_like_front_matter_paragraph(text: str, *, title: str | None = None) -> bool:
    normalized = normalize_text(text)
    lowered = normalized.lower()
    if not lowered:
        return False
    if title and lowered == normalize_text(title).lower():
        return True
    if title:
        compact_text = re.sub(r"\s+", "", lowered)
        compact_title = re.sub(r"\s+", "", normalize_text(title).lower())
        if compact_title and compact_text.endswith(compact_title):
            for prefix in ARTICLE_TYPE_FRONT_MATTER_PREFIXES:
                if compact_text.startswith(re.sub(r"\s+", "", prefix)):
                    return True
    if lowered.startswith("all content on this site") or lowered.startswith("copyright"):
        return True
    return any(
        token in lowered
        for token in (
            "published",
            "accepted",
            "received",
            "author information",
            "authors info",
            "citation",
            "view options",
            "metrics & citations",
        )
    )


def _looks_like_access_gate_text(text: str) -> bool:
    return contains_access_gate_text(text)


def _run_candidate_barrier(kind: str) -> bool:
    return kind in {"front_matter", "abstract", "references_or_back_matter", "ancillary", "data_availability"}


def _normalize_section_hint_heading(text: str) -> str:
    return normalize_text(text).lower().strip(" :")


def _coerce_section_hints(section_hints: Any) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for index, hint in enumerate(section_hints or []):
        if isinstance(hint, Mapping):
            heading = normalize_text(hint.get("heading"))
            kind = normalize_text(hint.get("kind")).lower()
            order = hint.get("order")
        else:
            heading = normalize_text(getattr(hint, "heading", None))
            kind = normalize_text(getattr(hint, "kind", None)).lower()
            order = getattr(hint, "order", None)
        if not heading or kind not in HTML_SECTION_HINT_KINDS:
            continue
        hints.append(
            {
                "heading_key": _normalize_section_hint_heading(heading),
                "kind": kind,
                "order": int(order) if isinstance(order, int) or str(order).isdigit() else index,
            }
        )
    hints.sort(key=lambda item: item["order"])
    return hints


def _match_next_section_hint(section_hints: list[dict[str, Any]], hint_index: int, heading: str) -> tuple[dict[str, Any] | None, int]:
    heading_key = _normalize_section_hint_heading(heading)
    if not heading_key:
        return None, hint_index
    for index in range(hint_index, len(section_hints)):
        if section_hints[index]["heading_key"] == heading_key:
            return section_hints[index], index + 1
    return None, hint_index


def _category_for_section_hint_kind(kind: str) -> str:
    if kind == "data_availability":
        return "data_availability"
    if kind == "references":
        return "references_or_back_matter"
    return "body_heading"


def _analyze_html_structure(
    html_text: str,
    *,
    provider: str | None,
    title: str | None,
    metadata: Mapping[str, Any] | None,
    final_url: str | None,
) -> tuple[StructuredBodyAnalysis, str | None, int | None]:
    analysis = StructuredBodyAnalysis(
        narrative_article_type=_is_narrative_article_type(_extract_article_type(metadata, provider=provider, html_text=html_text))
    )
    if BeautifulSoup is None:
        return analysis, None, None

    soup = BeautifulSoup(html_text, choose_parser())
    container = select_best_container(soup, provider or "wiley")
    if container is None:
        return analysis, None, None

    clean_container(container, provider or "wiley")
    analysis.explicit_body_container = container_has_explicit_body_container(container)
    container_text = normalize_text(container.get_text(" ", strip=True))
    page_text = _normalized_page_text(html_text)
    analysis.page_has_paywall_text = contains_access_gate_text(page_text)
    analysis.container_has_paywall_text = contains_access_gate_text(container_text)

    blocks = iter_html_blocks(container)
    body_chunks: list[str] = []
    normalized_title_heading = normalize_heading(title or "")
    in_abstract = False
    in_back_matter = False
    in_front_matter = False
    in_data_availability = False
    abstract_seen = False
    body_heading_after_abstract = False
    current_run_paragraphs = 0
    current_run_chars = 0

    for block in blocks:
        if block["kind"] == "marker":
            analysis.explicit_body_container = True
            continue

        node = block["node"]
        text = block["text"]
        access_gate_markers = matched_access_gate_patterns(text)
        if block["kind"] == "heading":
            if normalized_title_heading and normalize_heading(text) == normalized_title_heading:
                in_abstract = False
                in_back_matter = False
                in_front_matter = False
                in_data_availability = False
                if current_run_paragraphs:
                    current_run_paragraphs = 0
                    current_run_chars = 0
                continue
            category = heading_category(normalize_text(node.name or "").lower(), text, title=title)
        elif block["kind"] == "figure_or_table":
            category = "figure_or_table"
        else:
            category = classify_html_paragraph(
                node,
                text,
                title=title,
                in_back_matter=in_back_matter,
                in_front_matter=in_front_matter,
                in_abstract=in_abstract,
                in_data_availability=in_data_availability,
                looks_like_front_matter_paragraph=lambda value: _looks_like_front_matter_paragraph(value, title=title),
                is_substantial_prose=_is_substantial_prose,
                looks_like_access_gate_text=_looks_like_access_gate_text,
            )
        if access_gate_markers:
            analysis.access_gate_markers.extend(access_gate_markers)

        if category == "abstract":
            abstract_seen = True
            in_abstract = True
            in_back_matter = False
            in_front_matter = False
            in_data_availability = False
            if current_run_paragraphs:
                current_run_paragraphs = 0
                current_run_chars = 0
            continue
        if category == "references_or_back_matter":
            in_back_matter = True
            in_abstract = False
            in_front_matter = False
            in_data_availability = False
            if current_run_paragraphs:
                current_run_paragraphs = 0
                current_run_chars = 0
            continue
        if category == "data_availability":
            in_data_availability = True
            in_abstract = False
            in_back_matter = False
            in_front_matter = False
            if current_run_paragraphs:
                current_run_paragraphs = 0
                current_run_chars = 0
            continue
        if category == "front_matter":
            in_front_matter = block["kind"] == "heading"
            in_abstract = False
            in_back_matter = False
            in_data_availability = False
            if current_run_paragraphs:
                current_run_paragraphs = 0
                current_run_chars = 0
            continue
        if category == "ancillary":
            in_front_matter = False
            in_data_availability = False
            if current_run_paragraphs:
                current_run_paragraphs = 0
                current_run_chars = 0
            continue
        if category == "body_heading":
            in_abstract = False
            in_back_matter = False
            in_front_matter = False
            in_data_availability = False
            if abstract_seen:
                body_heading_after_abstract = True
            continue
        if category == "figure_or_table":
            continue
        if category != "body_paragraph":
            if _run_candidate_barrier(category):
                current_run_paragraphs = 0
                current_run_chars = 0
            continue

        in_abstract = False
        in_back_matter = False
        in_front_matter = False
        in_data_availability = False
        analysis.body_paragraph_count += 1
        body_chunks.append(text)
        current_run_paragraphs += 1
        current_run_chars += len(normalize_text(text))
        analysis.body_run_paragraph_count = max(analysis.body_run_paragraph_count, current_run_paragraphs)
        analysis.body_run_char_count = max(analysis.body_run_char_count, current_run_chars)
        if abstract_seen and body_heading_after_abstract:
            analysis.post_abstract_body_run = True

    analysis.body_candidate_text = "\n\n".join(body_chunks)
    analysis.paywall_text_outside_body_ignored = (
        analysis.page_has_paywall_text and not analysis.container_has_paywall_text and analysis.body_paragraph_count > 0
    )
    analysis.paywall_gate_detected = (
        analysis.body_paragraph_count == 0
        and (analysis.container_has_paywall_text or _final_url_looks_like_access_page(final_url))
    )
    analysis.access_gate_markers = _dedupe_signals(analysis.access_gate_markers)
    return analysis, container.name, len(" ".join(container.stripped_strings))


def _analyze_markdown_structure(
    markdown_text: str,
    *,
    metadata: Mapping[str, Any] | None,
    title: str | None,
    section_hints: Any = None,
) -> StructuredBodyAnalysis:
    analysis = StructuredBodyAnalysis(
        narrative_article_type=_is_narrative_article_type(_extract_article_type(metadata))
    )
    blocks = [normalize_text(block) for block in re.split(r"\n\s*\n", markdown_text) if normalize_text(block)]
    normalized_title_heading = normalize_heading(title or "")
    coerced_section_hints = _coerce_section_hints(section_hints)
    in_abstract = False
    in_back_matter = False
    in_front_matter = False
    in_data_availability = False
    abstract_seen = False
    body_heading_after_abstract = False
    current_run_paragraphs = 0
    current_run_chars = 0
    body_chunks: list[str] = []
    section_hint_index = 0

    for block in blocks:
        stripped = block.strip()
        is_heading = stripped.startswith("#")
        access_gate_markers = matched_access_gate_patterns(block)
        if is_heading:
            match = re.match(r"^(#+)\s*(.*)$", stripped)
            heading = normalize_text(match.group(2) if match else stripped)
            level = len(match.group(1)) if match else 2
            if normalized_title_heading and normalize_heading(heading) == normalized_title_heading:
                in_abstract = False
                in_back_matter = False
                in_front_matter = False
                in_data_availability = False
                current_run_paragraphs = 0
                current_run_chars = 0
                continue
            matched_hint, next_hint_index = _match_next_section_hint(coerced_section_hints, section_hint_index, heading)
            if matched_hint is not None:
                section_hint_index = next_hint_index
                category = _category_for_section_hint_kind(matched_hint["kind"])
            else:
                category = heading_category(f"h{min(level, 6)}", heading, title=title)
        else:
            category = "body_paragraph" if _is_substantial_prose(block) and not _looks_like_front_matter_paragraph(block, title=title) else "front_matter"
            if in_back_matter:
                category = "references_or_back_matter"
            elif in_front_matter:
                category = "front_matter"
            elif in_data_availability:
                category = "data_availability"
            elif in_abstract:
                category = "abstract"
            elif _looks_like_access_gate_text(block):
                category = "ancillary"
        if access_gate_markers:
            analysis.access_gate_markers.extend(access_gate_markers)

        if category == "abstract":
            abstract_seen = True
            in_abstract = True
            in_back_matter = False
            in_front_matter = False
            in_data_availability = False
            current_run_paragraphs = 0
            current_run_chars = 0
            continue
        if category == "references_or_back_matter":
            in_back_matter = True
            in_abstract = False
            in_front_matter = False
            in_data_availability = False
            current_run_paragraphs = 0
            current_run_chars = 0
            continue
        if category == "data_availability":
            in_data_availability = True
            in_abstract = False
            in_back_matter = False
            in_front_matter = False
            current_run_paragraphs = 0
            current_run_chars = 0
            continue
        if category == "front_matter":
            in_front_matter = is_heading
            in_abstract = False
            in_back_matter = False
            in_data_availability = False
            if current_run_paragraphs:
                current_run_paragraphs = 0
                current_run_chars = 0
            continue
        if category == "ancillary":
            in_front_matter = False
            in_data_availability = False
            if current_run_paragraphs:
                current_run_paragraphs = 0
                current_run_chars = 0
            continue
        if category == "body_heading":
            in_abstract = False
            in_back_matter = False
            in_front_matter = False
            in_data_availability = False
            if abstract_seen:
                body_heading_after_abstract = True
            continue
        if category != "body_paragraph":
            continue

        in_abstract = False
        in_back_matter = False
        in_front_matter = False
        in_data_availability = False
        analysis.body_paragraph_count += 1
        body_chunks.append(block)
        current_run_paragraphs += 1
        current_run_chars += len(normalize_text(block))
        analysis.body_run_paragraph_count = max(analysis.body_run_paragraph_count, current_run_paragraphs)
        analysis.body_run_char_count = max(analysis.body_run_char_count, current_run_chars)
        if abstract_seen and body_heading_after_abstract:
            analysis.post_abstract_body_run = True

    analysis.body_candidate_text = "\n\n".join(body_chunks)
    analysis.access_gate_markers = _dedupe_signals(analysis.access_gate_markers)
    return analysis


def _structure_accepts_fulltext(analysis: StructuredBodyAnalysis) -> bool:
    if analysis.explicit_body_container and analysis.body_paragraph_count >= 1:
        return True
    if analysis.post_abstract_body_run:
        return True
    if analysis.body_run_paragraph_count >= 3:
        return True
    if analysis.narrative_article_type and (
        analysis.body_run_paragraph_count >= 2
        or (analysis.explicit_body_container and analysis.body_run_char_count >= NARRATIVE_BODY_RUN_MIN_CHARS)
    ):
        return True
    return False


def availability_failure_message(diagnostics: FulltextAvailabilityDiagnostics) -> str:
    if diagnostics.reason in {"structured_article_not_fulltext", "structured_missing_body_sections"}:
        return html_failure_message(diagnostics.reason)
    return html_failure_message(diagnostics.reason)


def _dedupe_signals(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _diagnostics_content_kind(
    *,
    body_ok: bool,
    has_abstract: bool,
    blocking_fallback_signals: list[str] | None = None,
) -> str:
    if blocking_fallback_signals:
        return "abstract_only" if has_abstract else "metadata_only"
    if body_ok:
        return "fulltext"
    if has_abstract:
        return "abstract_only"
    return "metadata_only"


def _normalized_text_field(value: Any) -> str:
    return normalize_text(value) if isinstance(value, str) else ""


def _dom_access_hints(
    html_text: str,
    *,
    provider: str | None,
    structure: StructuredBodyAnalysis,
    final_url: str | None,
    metadata: Mapping[str, Any] | None,
) -> tuple[list[str], list[str], list[str]]:
    hard_negative_signals: list[str] = []
    abstract_only_hints: list[str] = []
    blocking_fallback_signals: list[str] = []
    if BeautifulSoup is None:
        if _final_url_looks_like_access_page(final_url):
            abstract_only_hints.append("access_page_url")
            blocking_fallback_signals.append("access_page_url")
        return (
            _dedupe_signals(hard_negative_signals),
            _dedupe_signals(abstract_only_hints),
            _dedupe_signals(blocking_fallback_signals),
        )

    soup = BeautifulSoup(html_text, choose_parser())
    if soup.select_one(".accessDenialWidget"):
        hard_negative_signals.append("publisher_paywall")
        blocking_fallback_signals.append("publisher_paywall")
    if _final_url_looks_like_access_page(final_url):
        abstract_only_hints.append("access_page_url")
        blocking_fallback_signals.append("access_page_url")
    for node in soup.select("[data-article-access], [data-article-access-type]"):
        attrs = getattr(node, "attrs", None) or {}
        access_value = normalize_text(str(attrs.get("data-article-access") or "")).lower()
        access_type = normalize_text(str(attrs.get("data-article-access-type") or "")).lower()
        values = [access_value, access_type]
        joined = " ".join(value.lower() for value in values if value)
        if access_value == "no":
            blocking_fallback_signals.append("data_article_access_no")
        if any(token in joined for token in {"abstract", "summary", "preview", "teaser", "limited"}):
            abstract_only_hints.append("data_article_access_abstract")
            blocking_fallback_signals.append("data_article_access_abstract")
        if any(token in joined for token in {"denied", "subscription", "restricted", "paywall"}):
            hard_negative_signals.append("publisher_paywall")
            blocking_fallback_signals.append("publisher_paywall")
    wt_node = soup.select_one("meta[name='WT.z_cg_type']")
    if wt_node is not None:
        wt_value = normalize_text(str((getattr(wt_node, "attrs", None) or {}).get("content") or "")).lower()
        if "abstract" in wt_value or "summary" in wt_value:
            abstract_only_hints.append("wt_abstract_page_type")
            blocking_fallback_signals.append("wt_abstract_page_type")
    citation_abstract_url = normalize_text(str((metadata or {}).get("citation_abstract_html_url") or ""))
    citation_fulltext_url = normalize_text(str((metadata or {}).get("citation_fulltext_html_url") or ""))
    normalized_final_url = normalize_text(final_url or "")
    if citation_abstract_url:
        abstract_only_hints.append("citation_abstract_html_url")
        if normalized_final_url and normalized_final_url == citation_abstract_url:
            abstract_only_hints.append("final_url_matches_citation_abstract_html_url")
            blocking_fallback_signals.append("final_url_matches_citation_abstract_html_url")
    if citation_fulltext_url and normalized_final_url and normalized_final_url == citation_fulltext_url:
        hard_negative_signals = [signal for signal in hard_negative_signals if signal != "publisher_paywall"]
        blocking_fallback_signals = [signal for signal in blocking_fallback_signals if signal != "publisher_paywall"]
    if provider == "elsevier":
        canonical_node = soup.select_one("link[rel='canonical']")
        canonical_url = normalize_text(str((getattr(canonical_node, "attrs", None) or {}).get("href") or ""))
        if "/science/article/abs/" in canonical_url:
            abstract_only_hints.append("canonical_abstract_url")
            blocking_fallback_signals.append("canonical_abstract_url")
    if provider == "springer" and not structure.post_abstract_body_run:
        if soup.select_one(".app-article-access__heading, .c-preview-message__link, [data-test='access-via-institution']"):
            blocking_fallback_signals.append("springer_access_preview_wall")
    return (
        _dedupe_signals(hard_negative_signals),
        _dedupe_signals(abstract_only_hints),
        _dedupe_signals(blocking_fallback_signals),
    )


def _count_figures_from_html(html_text: str) -> int:
    lowered = html_text.lower()
    if BeautifulSoup is None:
        return lowered.count("<figure")
    soup = BeautifulSoup(html_text, choose_parser())
    figure_count = len(soup.find_all("figure"))
    if figure_count:
        return figure_count
    return len(soup.select(".figure, .figure-wrap, [data-open='viewer']"))


def assess_html_fulltext_availability(
    markdown_text: str,
    metadata: Mapping[str, Any] | None,
    *,
    provider: str | None = None,
    html_text: str | None = None,
    title: str | None = None,
    response_status: int | None = None,
    requested_url: str | None = None,
    final_url: str | None = None,
    container_tag: str | None = None,
    container_text_length: int | None = None,
    section_hints: Any = None,
) -> FulltextAvailabilityDiagnostics:
    metadata_map = dict(metadata or {})
    normalized_title = normalize_text(title or metadata_map.get("title") or "") or None
    page_text = _normalized_page_text(html_text or "") if html_text else normalize_text(markdown_text)
    hard_negative_signals = _detect_html_hard_negative_signals_impl(
        normalized_title or "",
        page_text,
        response_status,
        requested_url=requested_url,
        final_url=final_url,
        include_paywall_text=False,
        provider_metadata=metadata_map,
    )
    structure = StructuredBodyAnalysis()
    resolved_container_tag = container_tag
    resolved_container_text_length = container_text_length
    if html_text:
        structure, inferred_container_tag, inferred_container_text_length = _analyze_html_structure(
            html_text,
            provider=provider,
            title=normalized_title,
            metadata=metadata_map,
            final_url=final_url,
        )
        if not resolved_container_tag:
            resolved_container_tag = inferred_container_tag
        if not resolved_container_text_length:
            resolved_container_text_length = inferred_container_text_length
    structure_ok = _structure_accepts_fulltext(structure)
    body_ok_fallback = has_sufficient_article_body(markdown_text, metadata_map, section_hints=section_hints)
    body_ok = structure_ok or body_ok_fallback
    metrics = body_metrics(markdown_text, metadata_map, section_hints=section_hints)
    metrics["body_run_paragraph_count"] = structure.body_run_paragraph_count
    metrics["body_run_char_count"] = structure.body_run_char_count
    metrics["body_paragraph_count"] = structure.body_paragraph_count
    metrics["explicit_body_container"] = structure.explicit_body_container
    metrics["post_abstract_body_run"] = structure.post_abstract_body_run
    metrics["narrative_article_type"] = structure.narrative_article_type
    strong_positive_signals: list[str] = []
    soft_positive_signals: list[str] = []
    abstract_only_hints: list[str] = []
    blocking_fallback_signals: list[str] = list(hard_negative_signals)
    figure_count = _count_figures_from_html(html_text or "") if html_text else 0
    if body_ok:
        strong_positive_signals.append("body_sufficient")
    if structure.explicit_body_container:
        strong_positive_signals.append("explicit_body_container")
    if structure.post_abstract_body_run:
        strong_positive_signals.append("post_abstract_body_run")
    if structure.body_run_paragraph_count:
        strong_positive_signals.append("body_run_paragraph_count")
    if resolved_container_text_length and resolved_container_text_length >= 800:
        strong_positive_signals.append("selected_container_has_body_text")
    if resolved_container_tag:
        soft_positive_signals.append("selected_article_container")
    if figure_count:
        soft_positive_signals.append("has_figures")
    if structure.narrative_article_type:
        soft_positive_signals.append("narrative_article_type")
    if structure.paywall_text_outside_body_ignored:
        soft_positive_signals.append("paywall_text_outside_body_ignored")
    if html_text:
        provider_strong, provider_soft, provider_abstract = provider_positive_signals(provider, html_text)
        provider_blocking = provider_blocking_fallback_signals(provider, html_text)
        strong_positive_signals.extend(provider_strong)
        soft_positive_signals.extend(provider_soft)
        blocking_fallback_signals.extend(provider_blocking)
        dom_hard_negative_signals, dom_abstract_only_hints, dom_blocking_fallback_signals = _dom_access_hints(
            html_text,
            provider=provider,
            structure=structure,
            final_url=final_url,
            metadata=metadata_map,
        )
        hard_negative_signals.extend(dom_hard_negative_signals)
        abstract_only_hints.extend(dom_abstract_only_hints)
        abstract_only_hints.extend(provider_abstract)
        blocking_fallback_signals.extend(dom_blocking_fallback_signals)
    blocking_fallback_signals.extend(structure.access_gate_markers)
    if not blocking_fallback_signals and not body_ok and structure.paywall_gate_detected:
        hard_negative_signals.append("publisher_paywall")
        blocking_fallback_signals.append("publisher_paywall")
    if not body_ok and not metrics["char_count"] and abstract_only_hints:
        metrics["abstract_only_hints"] = _dedupe_signals(abstract_only_hints)
    has_abstract = bool(metrics.get("has_abstract"))
    blocking_fallback_signals = _dedupe_signals(blocking_fallback_signals)
    content_kind = _diagnostics_content_kind(
        body_ok=body_ok,
        has_abstract=has_abstract,
        blocking_fallback_signals=blocking_fallback_signals,
    )
    if not blocking_fallback_signals and content_kind != "fulltext" and abstract_only_hints and has_abstract:
        content_kind = "abstract_only"
    reason = hard_negative_signals[0] if hard_negative_signals else (
        "abstract_only"
        if blocking_fallback_signals and has_abstract
        else (
            "publisher_paywall"
            if blocking_fallback_signals
            else ("body_sufficient" if body_ok else ("abstract_only" if content_kind == "abstract_only" else "insufficient_body"))
        )
    )
    return FulltextAvailabilityDiagnostics(
        accepted=body_ok and not blocking_fallback_signals,
        reason=reason,
        content_kind=content_kind,
        blocking_fallback_signals=blocking_fallback_signals,
        hard_negative_signals=_dedupe_signals(hard_negative_signals),
        strong_positive_signals=_dedupe_signals(strong_positive_signals),
        soft_positive_signals=_dedupe_signals(soft_positive_signals + abstract_only_hints),
        body_metrics=metrics,
        figure_count=figure_count,
        title=normalized_title,
        container_tag=resolved_container_tag,
        container_text_length=resolved_container_text_length,
    )


def assess_plain_text_fulltext_availability(
    markdown_text: str,
    metadata: Mapping[str, Any] | None,
    *,
    title: str | None = None,
    section_hints: Any = None,
) -> FulltextAvailabilityDiagnostics:
    metadata_map = dict(metadata or {})
    normalized_title = normalize_text(title or metadata_map.get("title") or "") or None
    structure = _analyze_markdown_structure(
        markdown_text,
        metadata=metadata_map,
        title=normalized_title,
        section_hints=section_hints,
    )
    body_ok = _structure_accepts_fulltext(structure)
    if not body_ok:
        body_ok = has_sufficient_article_body(markdown_text, metadata_map, section_hints=section_hints)
    metrics = body_metrics(markdown_text, metadata_map, section_hints=section_hints)
    metrics["body_run_paragraph_count"] = structure.body_run_paragraph_count
    metrics["body_run_char_count"] = structure.body_run_char_count
    metrics["body_paragraph_count"] = structure.body_paragraph_count
    metrics["narrative_article_type"] = structure.narrative_article_type
    blocking_fallback_signals = _dedupe_signals(list(structure.access_gate_markers))
    content_kind = _diagnostics_content_kind(
        body_ok=body_ok,
        has_abstract=bool(metrics.get("has_abstract")),
        blocking_fallback_signals=blocking_fallback_signals,
    )
    return FulltextAvailabilityDiagnostics(
        accepted=body_ok and not blocking_fallback_signals,
        reason=(
            "abstract_only"
            if blocking_fallback_signals and content_kind == "abstract_only"
            else (
                "publisher_paywall"
                if blocking_fallback_signals
                else ("body_sufficient" if body_ok else ("abstract_only" if content_kind == "abstract_only" else "insufficient_body"))
            )
        ),
        content_kind=content_kind,
        blocking_fallback_signals=blocking_fallback_signals,
        strong_positive_signals=[
            signal
            for signal, enabled in (
                ("body_sufficient", body_ok),
                ("post_abstract_body_run", structure.post_abstract_body_run),
                ("body_run_paragraph_count", structure.body_run_paragraph_count > 0),
            )
            if enabled
        ],
        soft_positive_signals=["narrative_article_type"] if structure.narrative_article_type else [],
        body_metrics=metrics,
        title=normalized_title,
    )


def assess_structured_article_fulltext_availability(
    article: Any,
    *,
    title: str | None = None,
) -> FulltextAvailabilityDiagnostics:
    sections = list(getattr(article, "sections", []) or [])
    body_sections = [
        section
        for section in filtered_body_sections(sections)
        if _is_substantial_prose(str(getattr(section, "text", "") or ""))
    ]
    body_text = "\n\n".join(normalize_text(str(getattr(section, "text", "") or "")) for section in body_sections)
    metadata = getattr(article, "metadata", None)
    article_title = normalize_text(title or _normalized_text_field(getattr(metadata, "title", None)) or "") or None
    article_abstract = _normalized_text_field(getattr(metadata, "abstract", None)) or None
    metrics = body_metrics(body_text, {"title": article_title, "abstract": article_abstract} if article_title or article_abstract else {})
    metrics["section_count"] = len(sections)
    metrics["body_section_count"] = len(body_sections)
    strong_positive_signals: list[str] = []
    if body_sections:
        strong_positive_signals.append("structured_body_sections")
    figure_count = len(
        [
            asset
            for asset in list(getattr(article, "assets", []) or [])
            if normalize_text(str(getattr(asset, "kind", "") or "")).lower() == "figure"
        ]
    )
    soft_positive_signals = ["has_figures"] if figure_count else []
    content_kind = classify_article_content(article)
    accepted = content_kind == "fulltext" and bool(body_sections)
    reason = "structured_body_sections" if accepted else (
        "structured_missing_body_sections" if content_kind == "abstract_only" else "structured_article_not_fulltext"
    )
    return FulltextAvailabilityDiagnostics(
        accepted=accepted,
        reason=reason,
        content_kind=content_kind,
        blocking_fallback_signals=[],
        strong_positive_signals=strong_positive_signals,
        soft_positive_signals=soft_positive_signals,
        body_metrics=metrics,
        figure_count=figure_count,
        title=article_title,
    )
