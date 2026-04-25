"""Shared article model and AI-friendly serialization helpers."""

from __future__ import annotations

import html
import json
import math
import re
import urllib.parse
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from typing import Any, Literal, Mapping

from .providers._html_citations import normalize_inline_citation_markdown
from .publisher_identity import normalize_doi
from .tracing import TraceEvent, source_trail_from_trace, trace_from_markers
from .utils import normalize_text, safe_text

SourceKind = Literal[
    "elsevier_xml",
    "elsevier_pdf",
    "springer_html",
    "wiley_browser",
    "science",
    "pnas",
    "crossref_meta",
]
OutputMode = Literal["article", "markdown", "metadata"]
AssetProfile = Literal["none", "body", "all"]
MaxTokensMode = int | Literal["full_text"]
ContentKind = Literal["fulltext", "abstract_only", "metadata_only"]
QualityConfidence = Literal["high", "medium", "low"]
MARKDOWN_FENCE_PATTERN = re.compile(r"^\s*(```+|~~~+)")
MARKDOWN_TABLE_RULE_PATTERN = re.compile(r"^\s*[-+:| ]{3,}\s*$")
MARKDOWN_LIST_MARKER_PATTERN = re.compile(r"^(\s{0,3}(?:[-*+]|\d+[.)])\s+)(.*)$")
TRUNCATION_WARNING = "Output truncated to satisfy token budget."
BODY_SECTION_EXCLUDED_KINDS = frozenset({"abstract", "references", "supplementary", "diagnostics", "data_availability"})
SECTION_HINT_KINDS = frozenset({"body", "data_availability", "references"})
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
    "references": 6,
}
LEADING_ABSTRACT_CONTEXT_HEADINGS = frozenset({"significance", "significance statement"})
ABSTRACT_NEAR_DUPLICATE_SIMILARITY_THRESHOLD = 0.995
ABSTRACT_NEAR_DUPLICATE_MAX_LENGTH_DELTA = 64
BODY_ABSTRACT_PARAGRAPH_NEAR_DUPLICATE_SIMILARITY_THRESHOLD = 0.989
BODY_ABSTRACT_PARAGRAPH_NEAR_DUPLICATE_MAX_LENGTH_DELTA = 64
ABSTRACT_PREFIX_PATTERN = re.compile(r"^(?:[Aa]bstract|[Ss]ummary)\b[:.\-\s]+(?=[A-Z])")
INLINE_HTML_TAG_PATTERN = re.compile(r"</?(?:sub|sup|br)\b[^>]*>", flags=re.IGNORECASE)
INLINE_MARKDOWN_ABSTRACT_PREFIX_PATTERN = re.compile(r"^\*\*(?:Abstract|Summary)\.?\*\*\s*", re.IGNORECASE)
MARKDOWN_ABSTRACT_PREFIX_PATTERN = re.compile(r"^(?:\*\*|__)(?:[Aa]bstract|[Ss]ummary)\.?(?:\*\*|__)\s*")
MARKDOWN_IMAGE_URL_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
MARKDOWN_IMAGE_LINK_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
MARKDOWN_BLOCK_IMAGE_ALT_PATTERN = re.compile(
    r"^\s*(?:fig(?:ure)?\.?|(?:extended data|supplementary)?\s*table|supplementary\s+fig(?:ure)?\.?)\b",
    flags=re.IGNORECASE,
)
MARKDOWN_STANDALONE_IMAGE_ALT_PATTERN = re.compile(
    r"^\s*(?:fig(?:ure)?\.?|(?:extended data|supplementary)?\s*table|supplementary\s+fig(?:ure)?\.?|formula|equation)\b",
    flags=re.IGNORECASE,
)
TABLE_LIKE_FIGURE_ASSET_PATTERN = re.compile(
    r"^(?:(?:extended data|supplementary)\s+)?table\s+\d+[A-Za-z]?\b",
    flags=re.IGNORECASE,
)
NUMBERED_REFERENCE_PATTERN = re.compile(r"^\s*(?:\[\d+[A-Za-z]?\]|\d+[A-Za-z]?[.)])\s+")
EXTRACTION_REVISION = 2
QUALITY_FLAG_ACCESS_GATE_DETECTED = "access_gate_detected"
QUALITY_FLAG_INSUFFICIENT_BODY = "insufficient_body"
QUALITY_FLAG_WEAK_BODY_STRUCTURE = "weak_body_structure"
QUALITY_FLAG_TABLE_FALLBACK_PRESENT = "table_fallback_present"
QUALITY_FLAG_TABLE_LOSSY_PRESENT = "table_lossy_present"
QUALITY_FLAG_TABLE_LAYOUT_DEGRADED = "table_layout_degraded"
QUALITY_FLAG_TABLE_SEMANTIC_LOSS = "table_semantic_loss"
QUALITY_FLAG_FORMULA_FALLBACK_PRESENT = "formula_fallback_present"
QUALITY_FLAG_FORMULA_MISSING_PRESENT = "formula_missing_present"
QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION = "cached_with_current_revision"
_QUALITY_ACCESS_SIGNAL_TOKENS = frozenset(
    {
        "publisher_paywall",
        "access",
        "redirect",
        "no_access",
        "abstract_page",
        "citation_abstract",
        "wt_abstract",
        "preview",
        "limited",
        "teaser",
        "denied",
        "subscription",
    }
)
_QUALITY_DOWNGRADE_REASONS = frozenset(
    {
        "publisher_paywall",
        "insufficient_body",
        "abstract_only",
        "no_access",
        "redirected_to_abstract",
        "access_page_url",
        "final_url_matches_citation_abstract_html_url",
        "data_article_access_abstract",
        "wt_abstract_page_type",
        "citation_abstract_html_url",
    }
)


def normalize_markdown_text(value: str | None) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    normalized_lines: list[str] = []
    in_fence = False
    blank_run = 0
    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        if MARKDOWN_FENCE_PATTERN.match(line):
            normalized_lines.append(line.strip())
            in_fence = not in_fence
            blank_run = 0
            continue

        if in_fence or should_preserve_markdown_line(line):
            normalized_line = line
        else:
            normalized_line = normalize_markdown_prose_line(line)

        if normalized_line:
            normalized_lines.append(normalized_line)
            blank_run = 0
            continue

        if in_fence or blank_run < 2:
            normalized_lines.append("")
        blank_run += 1

    normalized = "\n".join(normalized_lines).strip()
    normalized = _collapse_display_math_padding(normalized)
    return _normalize_markdown_image_block_boundaries(normalized)


def _is_block_markdown_image_alt(alt_text: str) -> bool:
    return bool(MARKDOWN_BLOCK_IMAGE_ALT_PATTERN.match(normalize_text(alt_text)))


def _is_standalone_markdown_image_alt(alt_text: str) -> bool:
    return bool(MARKDOWN_STANDALONE_IMAGE_ALT_PATTERN.match(normalize_text(alt_text)))


def _is_standalone_markdown_image_line(line: str) -> bool:
    match = MARKDOWN_IMAGE_LINK_PATTERN.fullmatch(line.strip())
    return bool(match and _is_standalone_markdown_image_alt(match.group(1)))


def _split_markdown_image_adjacency_line(line: str) -> list[str]:
    matches = list(MARKDOWN_IMAGE_LINK_PATTERN.finditer(line))
    if not matches:
        return [line]

    stripped = line.strip()
    if MARKDOWN_IMAGE_LINK_PATTERN.fullmatch(stripped):
        return [line]

    split_required = False
    for match in matches:
        prefix = line[: match.start()]
        suffix = line[match.end() :]
        if _is_block_markdown_image_alt(match.group(1)):
            split_required = True
            break
        if (
            _is_standalone_markdown_image_alt(match.group(1))
            and re.search(r"\b(?:equation|formula)\b", normalize_text(prefix), flags=re.IGNORECASE)
            and not normalize_text(suffix)
        ):
            split_required = True
            break
        if normalize_text(prefix).endswith("$$") or normalize_text(suffix).startswith("$$"):
            split_required = True
            break
    if not split_required:
        return [line]

    pieces: list[str] = []
    cursor = 0
    for match in matches:
        prefix = line[cursor : match.start()]
        if normalize_text(prefix):
            pieces.append(prefix.rstrip())
        pieces.append(match.group(0))
        cursor = match.end()
    suffix = line[cursor:]
    if normalize_text(suffix):
        pieces.append(suffix.strip())
    return pieces or [line]


def _normalize_markdown_image_block_boundaries(text: str) -> str:
    if not text:
        return ""

    split_lines: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if MARKDOWN_FENCE_PATTERN.match(line):
            split_lines.append(line.strip())
            in_fence = not in_fence
            continue
        if in_fence:
            split_lines.append(line)
            continue
        split_lines.extend(_split_markdown_image_adjacency_line(line))

    bounded_lines: list[str] = []
    for index, line in enumerate(split_lines):
        if _is_standalone_markdown_image_line(line):
            if bounded_lines and bounded_lines[-1].strip():
                bounded_lines.append("")
            bounded_lines.append(line.strip())
            next_line = split_lines[index + 1] if index + 1 < len(split_lines) else ""
            if normalize_text(next_line):
                bounded_lines.append("")
            continue
        bounded_lines.append(line)

    return "\n".join(bounded_lines).strip()


def _collapse_display_math_padding(text: str) -> str:
    if not text:
        return ""

    collapsed_lines: list[str] = []
    math_lines: list[str] = []
    in_fence = False
    in_display_math = False

    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        if MARKDOWN_FENCE_PATTERN.match(line):
            if in_display_math:
                math_lines.append(line)
                continue
            collapsed_lines.append(line.strip())
            in_fence = not in_fence
            continue

        if not in_fence and line.strip() == "$$":
            if in_display_math:
                while math_lines and not math_lines[-1].strip():
                    math_lines.pop()
                collapsed_lines.extend(math_lines)
                collapsed_lines.append("$$")
                math_lines = []
                in_display_math = False
            else:
                collapsed_lines.append("$$")
                math_lines = []
                in_display_math = True
            continue

        if in_display_math:
            if not math_lines and not line.strip():
                continue
            math_lines.append(line)
            continue

        collapsed_lines.append(line)

    if in_display_math:
        collapsed_lines.extend(math_lines)

    return "\n".join(collapsed_lines).strip()


def should_preserve_markdown_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if line.startswith(("    ", "\t")):
        return True
    if stripped.startswith("|") or stripped.endswith("|"):
        return True
    return bool(MARKDOWN_TABLE_RULE_PATTERN.match(stripped))


def normalize_markdown_prose_line(line: str) -> str:
    expanded = line.replace("\xa0", " ")
    list_match = MARKDOWN_LIST_MARKER_PATTERN.match(expanded)
    if list_match:
        marker, body = list_match.groups()
        body = re.sub(r"[ \t\r\f\v]+", " ", body).strip()
        return f"{marker}{body}" if body else marker.rstrip()

    leading_match = re.match(r"^\s*", expanded)
    leading = leading_match.group(0) if leading_match else ""
    body = re.sub(r"[ \t\r\f\v]+", " ", expanded[len(leading):]).strip()
    if not body:
        return ""
    return f"{leading}{body}" if leading else body


def estimate_tokens(text: str) -> int:
    normalized = normalize_markdown_text(text)
    return estimate_normalized_tokens(normalized)


def estimate_normalized_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def strip_markdown_images(text: str) -> str:
    stripped = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    return normalize_markdown_text(stripped)


def asset_link(asset: "Asset") -> str:
    return normalize_text(asset.path or asset.url)


def is_table_like_figure_asset(asset: "Asset") -> bool:
    for candidate in (asset.heading, asset.caption):
        if TABLE_LIKE_FIGURE_ASSET_PATTERN.match(normalize_text(candidate)):
            return True
    return False


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


def truncate_text_to_tokens(text: str, token_budget: int) -> str:
    if token_budget <= 0:
        return ""
    normalized = normalize_markdown_text(text)
    if estimate_normalized_tokens(normalized) <= token_budget:
        return normalized
    max_chars = max(32, token_budget * 4)
    truncated = normalized[:max_chars].rstrip(" ,;:\n")
    if len(truncated) < len(normalized):
        truncated += "..."
    return truncated


def normalize_token_budget(max_tokens: MaxTokensMode) -> tuple[float, bool]:
    if max_tokens == "full_text":
        return math.inf, True
    return float(max_tokens), False


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
    from .providers._html_semantics import heading_category as html_heading_category

    category = html_heading_category("h2", heading)
    if category == "data_availability":
        return "data_availability"
    if category == "references_or_back_matter":
        return "references"
    if category == "abstract":
        return "abstract"
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


@dataclass
class Metadata:
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    abstract: str | None = None
    journal: str | None = None
    published: str | None = None
    keywords: list[str] = field(default_factory=list)
    license_urls: list[str] = field(default_factory=list)
    landing_page_url: str | None = None


@dataclass
class Section:
    heading: str
    level: int
    kind: str
    text: str


@dataclass(frozen=True)
class SectionHint:
    heading: str
    level: int
    kind: str
    order: int = 0
    language: str | None = None
    source_selector: str | None = None


@dataclass(frozen=True)
class ExtractedAbstractBlock:
    heading: str
    text: str
    language: str | None = None
    kind: str = "abstract"
    order: int = 0


@dataclass
class Reference:
    raw: str
    doi: str | None = None
    title: str | None = None
    year: str | None = None


@dataclass
class Asset:
    kind: str
    heading: str
    caption: str | None = None
    url: str | None = None
    path: str | None = None
    section: str | None = None
    render_state: str | None = None
    anchor_key: str | None = None
    download_tier: str | None = None
    download_url: str | None = None
    original_url: str | None = None
    content_type: str | None = None
    downloaded_bytes: int | None = None
    width: int | None = None
    height: int | None = None


@dataclass
class TokenEstimateBreakdown:
    abstract: int = 0
    body: int = 0
    refs: int = 0


def coerce_token_estimate_breakdown(
    value: TokenEstimateBreakdown | Mapping[str, Any] | None,
) -> TokenEstimateBreakdown:
    if isinstance(value, TokenEstimateBreakdown):
        return value
    if isinstance(value, Mapping):
        return TokenEstimateBreakdown(
            abstract=int(value.get("abstract") or 0),
            body=int(value.get("body") or 0),
            refs=int(value.get("refs") or 0),
        )
    return TokenEstimateBreakdown()


def build_token_estimate_breakdown(
    *,
    abstract_text: str | None,
    sections: Sequence["Section"],
    references: Sequence["Reference"],
) -> TokenEstimateBreakdown:
    abstract = estimate_tokens(combine_abstract_text(abstract_text=abstract_text, sections=sections) or "")
    body = estimate_tokens(
        "\n\n".join(
            strip_markdown_images(section.text)
            for section in sections
            if section.kind not in BODY_SECTION_EXCLUDED_KINDS and strip_markdown_images(section.text)
        )
    )
    refs = estimate_tokens("\n".join(normalize_text(reference.raw) for reference in references if normalize_text(reference.raw)))
    return TokenEstimateBreakdown(abstract=abstract, body=body, refs=refs)


@dataclass
class BodyQualityMetrics:
    char_count: int = 0
    word_count: int = 0
    body_block_count: int = 0
    body_heading_count: int = 0
    body_to_abstract_ratio: float = 0.0
    explicit_body_container: bool = False
    post_abstract_body_run: bool = False
    figure_count: int = 0


@dataclass
class SemanticLosses:
    table_fallback_count: int = 0
    table_lossy_count: int = 0
    table_layout_degraded_count: int = 0
    table_semantic_loss_count: int = 0
    formula_fallback_count: int = 0
    formula_missing_count: int = 0


def coerce_body_quality_metrics(
    value: BodyQualityMetrics | Mapping[str, Any] | None,
    *,
    figure_count: int | None = None,
) -> BodyQualityMetrics:
    if isinstance(value, BodyQualityMetrics):
        metrics = BodyQualityMetrics(
            char_count=int(value.char_count or 0),
            word_count=int(value.word_count or 0),
            body_block_count=int(value.body_block_count or 0),
            body_heading_count=int(value.body_heading_count or 0),
            body_to_abstract_ratio=float(value.body_to_abstract_ratio or 0.0),
            explicit_body_container=bool(value.explicit_body_container),
            post_abstract_body_run=bool(value.post_abstract_body_run),
            figure_count=int(value.figure_count or 0),
        )
    elif isinstance(value, Mapping):
        metrics = BodyQualityMetrics(
            char_count=int(value.get("char_count") or 0),
            word_count=int(value.get("word_count") or 0),
            body_block_count=int(value.get("body_block_count") or 0),
            body_heading_count=int(value.get("body_heading_count") or 0),
            body_to_abstract_ratio=float(value.get("body_to_abstract_ratio") or 0.0),
            explicit_body_container=bool(value.get("explicit_body_container")),
            post_abstract_body_run=bool(value.get("post_abstract_body_run")),
            figure_count=int(value.get("figure_count") or 0),
        )
    else:
        metrics = BodyQualityMetrics()
    if figure_count is not None:
        metrics.figure_count = int(figure_count or 0)
    return metrics


def coerce_semantic_losses(value: SemanticLosses | Mapping[str, Any] | None) -> SemanticLosses:
    if isinstance(value, SemanticLosses):
        return SemanticLosses(
            table_fallback_count=int(value.table_fallback_count or 0),
            table_lossy_count=int(value.table_lossy_count or 0),
            table_layout_degraded_count=int(value.table_layout_degraded_count or 0),
            table_semantic_loss_count=int(value.table_semantic_loss_count or 0),
            formula_fallback_count=int(value.formula_fallback_count or 0),
            formula_missing_count=int(value.formula_missing_count or 0),
        )
    if isinstance(value, Mapping):
        legacy_lossy_count = int(value.get("table_lossy_count") or 0)
        return SemanticLosses(
            table_fallback_count=int(value.get("table_fallback_count") or 0),
            table_lossy_count=legacy_lossy_count,
            table_layout_degraded_count=int(value.get("table_layout_degraded_count") or 0),
            table_semantic_loss_count=int(value.get("table_semantic_loss_count") or legacy_lossy_count or 0),
            formula_fallback_count=int(value.get("formula_fallback_count") or 0),
            formula_missing_count=int(value.get("formula_missing_count") or 0),
        )
    return SemanticLosses()


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


def classify_content(*, sections: Sequence["Section"], abstract_text: str | None) -> ContentKind:
    if filtered_body_sections(sections):
        return "fulltext"
    if normalize_text(abstract_text) or abstract_sections(sections):
        return "abstract_only"
    return "metadata_only"


def classify_article_content(article: "ArticleModel") -> ContentKind:
    metadata = getattr(article, "metadata", None)
    abstract_text = _normalized_text_field(getattr(metadata, "abstract", None))
    sections = list(getattr(article, "sections", []) or [])
    if not abstract_text:
        abstract_text = next(
            (
                _normalized_text_field(getattr(section, "text", None))
                for section in sections
                if _normalized_text_field(getattr(section, "kind", None)).lower() == "abstract"
                and _normalized_text_field(getattr(section, "text", None))
            ),
            "",
        )
    return classify_content(sections=sections, abstract_text=abstract_text)


def _dedupe_strings(values: Sequence[str] | None) -> list[str]:
    return list(dict.fromkeys(normalize_text(value) for value in (values or []) if normalize_text(value)))


def _word_count(text: str) -> int:
    normalized = normalize_text(text)
    if not normalized:
        return 0
    return len(re.findall(r"\w+", normalized, flags=re.UNICODE))


def _article_body_quality_metrics(article: "ArticleModel") -> BodyQualityMetrics:
    body_sections = filtered_body_sections(article.sections)
    body_chunks = [strip_markdown_images(section.text) for section in body_sections if strip_markdown_images(section.text)]
    body_text = normalize_text("\n\n".join(body_chunks))
    abstract_text = first_abstract_text(abstract_text=article.metadata.abstract, sections=article.sections)
    abstract_word_count = _word_count(abstract_text)
    word_count = _word_count(body_text)
    body_to_abstract_ratio = (
        word_count / max(abstract_word_count, 1)
        if abstract_word_count
        else (float(word_count) if word_count else 0.0)
    )
    figure_count = len(
        [
            asset
            for asset in article.assets
            if normalize_text(asset.kind).lower() == "figure" and normalize_text(asset.section).lower() != "supplementary"
        ]
    )
    return BodyQualityMetrics(
        char_count=len(body_text),
        word_count=word_count,
        body_block_count=len(body_sections),
        body_heading_count=len([section for section in body_sections if normalize_text(section.heading)]),
        body_to_abstract_ratio=body_to_abstract_ratio,
        explicit_body_container=False,
        post_abstract_body_run=False,
        figure_count=figure_count,
    )


def _quality_body_metrics(
    article: "ArticleModel",
    *,
    availability_diagnostics: Mapping[str, Any] | None,
) -> BodyQualityMetrics:
    article_metrics = _article_body_quality_metrics(article)
    if not isinstance(availability_diagnostics, Mapping):
        return article_metrics
    diagnostics_metrics = coerce_body_quality_metrics(
        availability_diagnostics.get("body_metrics") if isinstance(availability_diagnostics.get("body_metrics"), Mapping) else None,
        figure_count=int(availability_diagnostics.get("figure_count") or 0),
    )
    has_article_metrics = any(
        (
            article_metrics.char_count,
            article_metrics.word_count,
            article_metrics.body_block_count,
            article_metrics.body_heading_count,
            article_metrics.figure_count,
        )
    )
    if not has_article_metrics:
        return diagnostics_metrics
    return BodyQualityMetrics(
        char_count=article_metrics.char_count,
        word_count=article_metrics.word_count,
        body_block_count=article_metrics.body_block_count,
        body_heading_count=article_metrics.body_heading_count,
        body_to_abstract_ratio=article_metrics.body_to_abstract_ratio,
        explicit_body_container=article_metrics.explicit_body_container or diagnostics_metrics.explicit_body_container,
        post_abstract_body_run=article_metrics.post_abstract_body_run or diagnostics_metrics.post_abstract_body_run,
        figure_count=max(article_metrics.figure_count, diagnostics_metrics.figure_count),
    )


def _diagnostic_signals(value: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    signals = [
        normalize_text(value.get("reason")).lower(),
        *[normalize_text(item).lower() for item in value.get("blocking_fallback_signals") or []],
        *[normalize_text(item).lower() for item in value.get("hard_negative_signals") or []],
        *[normalize_text(item).lower() for item in value.get("soft_positive_signals") or []],
        *[normalize_text(item).lower() for item in value.get("strong_positive_signals") or []],
    ]
    return [signal for signal in signals if signal]


def _diagnostic_access_gate_signals(value: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    signals = [
        normalize_text(value.get("reason")).lower(),
        *[normalize_text(item).lower() for item in value.get("blocking_fallback_signals") or []],
        *[normalize_text(item).lower() for item in value.get("hard_negative_signals") or []],
    ]
    if value.get("accepted") is False:
        signals.extend(
            normalize_text(item).lower()
            for item in value.get("soft_positive_signals") or []
        )
    return [signal for signal in signals if signal]


def _diagnostics_access_gate_detected(value: Mapping[str, Any] | None) -> bool:
    if isinstance(value, Mapping) and [item for item in value.get("blocking_fallback_signals") or [] if normalize_text(item)]:
        return True
    for signal in _diagnostic_access_gate_signals(value):
        if any(token in signal for token in _QUALITY_ACCESS_SIGNAL_TOKENS):
            return True
    return False


def _has_weak_body_structure(metrics: BodyQualityMetrics) -> bool:
    if metrics.word_count <= 0 and metrics.char_count <= 0:
        return False
    if metrics.explicit_body_container or metrics.post_abstract_body_run:
        return False
    if metrics.body_block_count >= 2 and metrics.body_heading_count >= 1:
        return False
    return True


def _diagnostics_require_downgrade(
    diagnostics: Mapping[str, Any] | None,
    *,
    body_metrics: BodyQualityMetrics,
) -> bool:
    if not isinstance(diagnostics, Mapping):
        return False
    if [item for item in diagnostics.get("blocking_fallback_signals") or [] if normalize_text(item)]:
        return True
    if diagnostics.get("accepted") is not False:
        return False
    reason = normalize_text(diagnostics.get("reason")).lower()
    if reason in _QUALITY_DOWNGRADE_REASONS:
        return True
    if _diagnostics_access_gate_detected(diagnostics):
        return True
    if reason == QUALITY_FLAG_INSUFFICIENT_BODY and body_metrics.word_count <= 40:
        return True
    return False


def _clone_quality(quality: "Quality") -> "Quality":
    return Quality(
        has_fulltext=quality.has_fulltext,
        token_estimate=quality.token_estimate,
        content_kind=quality.content_kind,
        has_abstract=quality.has_abstract,
        warnings=list(quality.warnings),
        source_trail=list(quality.source_trail),
        trace=list(quality.trace),
        token_estimate_breakdown=coerce_token_estimate_breakdown(quality.token_estimate_breakdown),
        confidence=quality.confidence,
        flags=list(quality.flags),
        body_metrics=coerce_body_quality_metrics(quality.body_metrics),
        semantic_losses=coerce_semantic_losses(quality.semantic_losses),
        extraction_revision=quality.extraction_revision,
    )


def _refresh_article_quality(
    article: "ArticleModel",
    *,
    explicit_content_kind: ContentKind | None = None,
    recompute_tokens: bool = True,
) -> None:
    abstract_text = first_abstract_text(abstract_text=article.metadata.abstract, sections=article.sections)
    if abstract_text and not normalize_text(article.metadata.abstract):
        article.metadata.abstract = abstract_text
    if recompute_tokens or article.quality.token_estimate_breakdown == TokenEstimateBreakdown():
        token_estimate_breakdown = build_token_estimate_breakdown(
            abstract_text=article.metadata.abstract,
            sections=article.sections,
            references=article.references,
        )
        article.quality.token_estimate_breakdown = token_estimate_breakdown
    token_estimate_breakdown = article.quality.token_estimate_breakdown
    if recompute_tokens or article.quality.token_estimate <= 0:
        article.quality.token_estimate = token_estimate_breakdown.abstract + token_estimate_breakdown.body
    content_kind = explicit_content_kind or classify_content(sections=article.sections, abstract_text=article.metadata.abstract)
    article.quality.content_kind = content_kind
    article.quality.has_abstract = bool(first_abstract_text(abstract_text=article.metadata.abstract, sections=article.sections))
    article.quality.has_fulltext = content_kind == "fulltext"


def _downgrade_article(article: "ArticleModel", *, target_kind: ContentKind) -> None:
    if target_kind == "metadata_only":
        article.sections = []
        article.assets = []
        _refresh_article_quality(article, explicit_content_kind="metadata_only")
        return
    article.sections = [
        section
        for section in article.sections
        if normalize_text(section.kind).lower() == "abstract"
    ]
    article.assets = []
    if not first_abstract_text(abstract_text=article.metadata.abstract, sections=article.sections):
        article.sections = []
        _refresh_article_quality(article, explicit_content_kind="metadata_only")
        return
    _refresh_article_quality(article, explicit_content_kind="abstract_only")


def _semantic_loss_warning_messages(losses: SemanticLosses) -> list[str]:
    warnings: list[str] = []
    if losses.table_fallback_count:
        warnings.append("Some tables could only be retained as original-resource fallbacks; structured table data may be incomplete.")
    if losses.table_semantic_loss_count or losses.table_lossy_count:
        warnings.append("Some tables lost semantic content during Markdown conversion.")
    if losses.table_layout_degraded_count:
        warnings.append("Some tables were flattened lossily for Markdown output; merged-cell structure was not preserved exactly.")
    if losses.formula_fallback_count:
        warnings.append("Some formulas required degraded fallback rendering.")
    if losses.formula_missing_count:
        warnings.append("Some formulas could not be converted faithfully and were replaced with explicit placeholders.")
    return warnings


def _resolve_quality_confidence(
    *,
    content_kind: ContentKind,
    flags: Sequence[str],
    semantic_losses: SemanticLosses,
    diagnostics: Mapping[str, Any] | None,
) -> QualityConfidence:
    normalized_flags = set(_dedupe_strings(flags))
    hard_negative = bool(
        isinstance(diagnostics, Mapping)
        and [normalize_text(item) for item in diagnostics.get("hard_negative_signals") or [] if normalize_text(item)]
    )
    if (
        content_kind != "fulltext"
        or hard_negative
        or QUALITY_FLAG_ACCESS_GATE_DETECTED in normalized_flags
        or QUALITY_FLAG_INSUFFICIENT_BODY in normalized_flags
    ):
        return "low"
    if (
        QUALITY_FLAG_WEAK_BODY_STRUCTURE in normalized_flags
        or semantic_losses.table_fallback_count > 0
        or semantic_losses.table_semantic_loss_count > 0
        or semantic_losses.table_lossy_count > 0
        or semantic_losses.formula_fallback_count > 0
        or semantic_losses.formula_missing_count > 0
    ):
        return "medium"
    return "high"


def apply_quality_assessment(
    article: "ArticleModel",
    *,
    availability_diagnostics: Mapping[str, Any] | None = None,
    semantic_losses: SemanticLosses | Mapping[str, Any] | None = None,
    extra_flags: Sequence[str] | None = None,
    allow_downgrade_from_diagnostics: bool = False,
    cached_with_current_revision: bool = False,
    recompute_tokens: bool = True,
) -> "ArticleModel":
    losses = coerce_semantic_losses(semantic_losses)
    body_metrics = _quality_body_metrics(article, availability_diagnostics=availability_diagnostics)
    flags = _dedupe_strings(extra_flags)
    reason = normalize_text((availability_diagnostics or {}).get("reason") if isinstance(availability_diagnostics, Mapping) else "").lower()

    if _diagnostics_access_gate_detected(availability_diagnostics):
        flags.append(QUALITY_FLAG_ACCESS_GATE_DETECTED)
    if reason == "insufficient_body":
        flags.append(QUALITY_FLAG_INSUFFICIENT_BODY)
    if article.quality.content_kind == "fulltext" and _has_weak_body_structure(body_metrics):
        flags.append(QUALITY_FLAG_WEAK_BODY_STRUCTURE)
    if losses.table_fallback_count > 0:
        flags.append(QUALITY_FLAG_TABLE_FALLBACK_PRESENT)
    if losses.table_layout_degraded_count > 0:
        flags.append(QUALITY_FLAG_TABLE_LAYOUT_DEGRADED)
    if losses.table_semantic_loss_count > 0 or losses.table_lossy_count > 0:
        flags.append(QUALITY_FLAG_TABLE_SEMANTIC_LOSS)
    if losses.table_lossy_count > 0:
        flags.append(QUALITY_FLAG_TABLE_LOSSY_PRESENT)
    if losses.formula_fallback_count > 0:
        flags.append(QUALITY_FLAG_FORMULA_FALLBACK_PRESENT)
    if losses.formula_missing_count > 0:
        flags.append(QUALITY_FLAG_FORMULA_MISSING_PRESENT)
    if cached_with_current_revision:
        flags.append(QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION)

    if allow_downgrade_from_diagnostics and _diagnostics_require_downgrade(
        availability_diagnostics,
        body_metrics=body_metrics,
    ):
        target_kind = normalize_text((availability_diagnostics or {}).get("content_kind") if isinstance(availability_diagnostics, Mapping) else "").lower()
        if target_kind not in {"abstract_only", "metadata_only"}:
            target_kind = "abstract_only" if first_abstract_text(abstract_text=article.metadata.abstract, sections=article.sections) else "metadata_only"
        _downgrade_article(article, target_kind=target_kind)
    else:
        _refresh_article_quality(article, recompute_tokens=recompute_tokens)

    article.quality.flags = _dedupe_strings(flags)
    article.quality.body_metrics = body_metrics
    article.quality.semantic_losses = losses
    article.quality.extraction_revision = EXTRACTION_REVISION
    article.quality.confidence = _resolve_quality_confidence(
        content_kind=article.quality.content_kind,
        flags=article.quality.flags,
        semantic_losses=losses,
        diagnostics=availability_diagnostics,
    )
    article.quality.warnings = _dedupe_strings([*article.quality.warnings, *_semantic_loss_warning_messages(losses)])
    return article


@dataclass
class Quality:
    has_fulltext: bool = False
    token_estimate: int = 0
    content_kind: ContentKind = "metadata_only"
    has_abstract: bool = False
    warnings: list[str] = field(default_factory=list)
    source_trail: list[str] = field(default_factory=list)
    trace: list[TraceEvent] = field(default_factory=list)
    token_estimate_breakdown: TokenEstimateBreakdown = field(default_factory=TokenEstimateBreakdown)
    confidence: QualityConfidence = "low"
    flags: list[str] = field(default_factory=list)
    body_metrics: BodyQualityMetrics = field(default_factory=BodyQualityMetrics)
    semantic_losses: SemanticLosses = field(default_factory=SemanticLosses)
    extraction_revision: int = EXTRACTION_REVISION

    def __post_init__(self) -> None:
        self.warnings = _dedupe_strings(self.warnings)
        self.source_trail = _dedupe_strings(self.source_trail)
        self.flags = _dedupe_strings(self.flags)
        self.body_metrics = coerce_body_quality_metrics(self.body_metrics)
        self.semantic_losses = coerce_semantic_losses(self.semantic_losses)
        self.token_estimate_breakdown = coerce_token_estimate_breakdown(self.token_estimate_breakdown)
        self.extraction_revision = int(self.extraction_revision or EXTRACTION_REVISION)
        if self.trace and not self.source_trail:
            self.source_trail = source_trail_from_trace(self.trace)
        elif self.source_trail and not self.trace:
            self.trace = trace_from_markers(self.source_trail)
        if self.content_kind == "fulltext":
            self.has_fulltext = True
        elif self.content_kind == "abstract_only":
            self.has_fulltext = False
            self.has_abstract = True
        elif self.has_fulltext:
            self.content_kind = "fulltext"
        elif self.has_abstract:
            self.content_kind = "abstract_only"
        if self.content_kind != "fulltext" and self.confidence == "high":
            self.confidence = "low"


@dataclass(frozen=True)
class RenderOptions:
    include_refs: str | None = None
    asset_profile: AssetProfile | None = None
    max_tokens: MaxTokensMode = "full_text"


@dataclass(frozen=True)
class RenderedBlock:
    lines: tuple[str, ...]
    normalized_text: str
    token_estimate: int


@dataclass(frozen=True)
class _MarkdownRenderPlan:
    token_budget: float
    abstract_text: str
    abstract_sections: tuple["Section", ...]
    level_shift: int
    include_figures: str
    reference_count: int
    lead_sections: tuple["Section", ...]
    body_sections: tuple["Section", ...]
    retained_sections: tuple["Section", ...]
    figure_assets: tuple["Asset", ...]
    table_assets: tuple["Asset", ...]
    supplementary_assets: tuple["Asset", ...]


@dataclass
class RenderContext:
    remaining_budget: float
    warnings: list[str] = field(default_factory=list)
    truncated_any: bool = False

    def append_if_fits(self, lines: list[str], block: RenderedBlock) -> bool:
        if block.token_estimate > self.remaining_budget:
            return False
        lines.extend(block.lines)
        self.remaining_budget -= block.token_estimate
        return True

    def mark_truncated(self) -> None:
        self.truncated_any = True

    def finalize_warnings(self) -> None:
        if self.truncated_any and TRUNCATION_WARNING not in self.warnings:
            self.warnings.append(TRUNCATION_WARNING)


@dataclass
class FetchEnvelope:
    doi: str | None
    source: str
    has_fulltext: bool
    content_kind: ContentKind = "metadata_only"
    has_abstract: bool = False
    warnings: list[str] = field(default_factory=list)
    source_trail: list[str] = field(default_factory=list)
    trace: list[TraceEvent] = field(default_factory=list)
    token_estimate: int = 0
    token_estimate_breakdown: TokenEstimateBreakdown = field(default_factory=TokenEstimateBreakdown)
    quality: Quality = field(default_factory=Quality)
    article: "ArticleModel | None" = None
    markdown: str | None = None
    metadata: Metadata | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def __post_init__(self) -> None:
        if self.article is not None:
            self.quality = _clone_quality(self.article.quality)
        if self.trace and not self.source_trail:
            self.source_trail = source_trail_from_trace(self.trace)
        elif self.source_trail and not self.trace:
            self.trace = trace_from_markers(self.source_trail)
        if self.content_kind == "fulltext":
            self.has_fulltext = True
        elif self.content_kind == "abstract_only":
            self.has_fulltext = False
            self.has_abstract = True
        elif self.has_fulltext:
            self.content_kind = "fulltext"
        elif self.has_abstract:
            self.content_kind = "abstract_only"
        self.quality.has_fulltext = self.quality.has_fulltext or self.has_fulltext
        if self.content_kind != "metadata_only":
            self.quality.content_kind = self.content_kind
        self.quality.has_abstract = self.quality.has_abstract or self.has_abstract
        self.quality.warnings = _dedupe_strings([*self.quality.warnings, *self.warnings])
        self.quality.source_trail = _dedupe_strings([*self.quality.source_trail, *self.source_trail])
        self.quality.trace = list(self.quality.trace or self.trace)
        if self.trace and not self.quality.trace:
            self.quality.trace = list(self.trace)
        if self.token_estimate and not self.quality.token_estimate:
            self.quality.token_estimate = self.token_estimate
        if self.token_estimate_breakdown != TokenEstimateBreakdown() and self.quality.token_estimate_breakdown == TokenEstimateBreakdown():
            self.quality.token_estimate_breakdown = coerce_token_estimate_breakdown(self.token_estimate_breakdown)
        self.has_fulltext = self.quality.has_fulltext
        self.content_kind = self.quality.content_kind
        self.has_abstract = self.quality.has_abstract
        self.warnings = list(self.quality.warnings)
        self.source_trail = list(self.quality.source_trail)
        self.trace = list(self.quality.trace)
        self.token_estimate = self.quality.token_estimate
        self.token_estimate_breakdown = self.quality.token_estimate_breakdown


@dataclass
class ArticleModel:
    doi: str | None
    source: SourceKind
    metadata: Metadata
    sections: list[Section] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)
    quality: Quality = field(default_factory=lambda: Quality(has_fulltext=False, token_estimate=0))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def __post_init__(self) -> None:
        abstract_text = first_abstract_text(abstract_text=self.metadata.abstract, sections=self.sections)
        if not abstract_text:
            abstract_text = ""
        if abstract_text and not normalize_text(self.metadata.abstract):
            self.metadata.abstract = abstract_text
        content_kind = classify_content(sections=self.sections, abstract_text=abstract_text)
        self.quality.content_kind = content_kind
        self.quality.has_abstract = bool(abstract_text)
        self.quality.has_fulltext = content_kind == "fulltext"
        apply_quality_assessment(
            self,
            semantic_losses=self.quality.semantic_losses,
            extra_flags=self.quality.flags,
            recompute_tokens=False,
        )

    def to_ai_markdown(
        self,
        *,
        include_refs: str | None = None,
        include_figures: str | None = None,
        include_supplementary: bool | None = None,
        asset_profile: AssetProfile = "none",
        max_tokens: MaxTokensMode = "full_text",
    ) -> str:
        warnings = list(self.quality.warnings)
        render_plan = _build_markdown_render_plan(
            self,
            include_refs=include_refs,
            include_figures=include_figures,
            include_supplementary=include_supplementary,
            asset_profile=asset_profile,
            max_tokens=max_tokens,
        )
        front_matter_block = _build_article_header_block(self)
        lines = list(front_matter_block.lines)
        context = RenderContext(
            remaining_budget=render_plan.token_budget - front_matter_block.token_estimate,
            warnings=warnings,
        )
        if context.remaining_budget <= 0:
            context.mark_truncated()
            context.finalize_warnings()
            return "\n".join(lines).strip() + "\n"

        _append_sections_with_budget(
            lines,
            sections=render_plan.lead_sections,
            level_shift=render_plan.level_shift,
            context=context,
            preserve_source_order=True,
        )
        if render_plan.abstract_sections:
            _append_sections_with_budget(
                lines,
                sections=render_plan.abstract_sections,
                level_shift=render_plan.level_shift,
                context=context,
                preserve_source_order=True,
            )
        else:
            _append_abstract_with_budget(
                lines,
                abstract_text=render_plan.abstract_text,
                context=context,
                as_section=bool(render_plan.lead_sections),
            )
        _append_sections_with_budget(
            lines,
            sections=render_plan.body_sections + render_plan.retained_sections,
            level_shift=render_plan.level_shift,
            context=context,
        )

        append_asset_block_with_budget(
            lines,
            heading=asset_block_heading("Figures", render_plan.figure_assets),
            item_groups=render_figure_asset_groups(list(render_plan.figure_assets), include_figures=render_plan.include_figures),
            context=context,
        )
        append_asset_block_with_budget(
            lines,
            heading=asset_block_heading("Tables", render_plan.table_assets),
            item_groups=render_table_asset_groups(list(render_plan.table_assets)),
            context=context,
        )
        append_asset_block_with_budget(
            lines,
            heading="Supplementary Materials",
            item_groups=render_supplementary_asset_groups(list(render_plan.supplementary_assets)),
            context=context,
        )

        append_reference_block_with_budget(
            lines,
            references=self.references[: render_plan.reference_count],
            total_references=len(self.references),
            context=context,
        )

        context.finalize_warnings()
        return "\n".join(lines).strip() + "\n"


def resolve_reference_limit(include_refs: str, total: int) -> int:
    if include_refs == "none" or total <= 0:
        return 0
    if include_refs == "all":
        return total
    if include_refs.startswith("top"):
        suffix = include_refs[3:] or "10"
        try:
            return min(total, int(suffix))
        except ValueError:
            return min(total, 10)
    return min(total, 10)


def resolve_reference_mode(include_refs: str | None, *, full_text_requested: bool) -> str:
    if include_refs is not None:
        return include_refs
    if full_text_requested:
        return "all"
    return "top10"


def resolve_figure_mode(include_figures: str | None, *, asset_profile: AssetProfile) -> str:
    if include_figures is not None:
        return include_figures
    return "captions_only" if asset_profile == "none" else "inline"


def resolve_supplementary_mode(include_supplementary: bool | None, *, asset_profile: AssetProfile) -> bool:
    if include_supplementary is not None:
        return include_supplementary
    return asset_profile == "all"


def _build_article_header_block(article: "ArticleModel") -> RenderedBlock:
    lines = ["---"]
    front_matter_fields = (
        ("title", article.metadata.title),
        ("authors", ", ".join(article.metadata.authors) if article.metadata.authors else None),
        ("journal", article.metadata.journal),
        ("doi", article.doi),
        ("published", article.metadata.published),
    )
    for key, value in front_matter_fields:
        normalized_value = normalize_inline_html_text(value)
        if normalized_value:
            lines.append(f'{key}: "{normalized_value.replace(chr(34), chr(39))}"')
    display_title = normalize_inline_html_text(article.metadata.title) or "Untitled Article"
    lines.extend(
        [
            f'source: "{article.source}"',
            f"has_fulltext: {str(article.quality.has_fulltext).lower()}",
            f'content_kind: "{article.quality.content_kind}"',
            f"has_abstract: {str(article.quality.has_abstract).lower()}",
            f"token_estimate: {article.quality.token_estimate}",
            "---",
            "",
            f"# {display_title}",
            "",
        ]
    )
    return build_rendered_block(lines)


def _build_markdown_render_plan(
    article: "ArticleModel",
    *,
    include_refs: str | None,
    include_figures: str | None,
    include_supplementary: bool | None,
    asset_profile: AssetProfile,
    max_tokens: MaxTokensMode,
) -> _MarkdownRenderPlan:
    token_budget, full_text_requested = normalize_token_budget(max_tokens)
    effective_include_refs = resolve_reference_mode(include_refs, full_text_requested=full_text_requested)
    effective_include_figures = resolve_figure_mode(include_figures, asset_profile=asset_profile)
    effective_include_supplementary = resolve_supplementary_mode(
        include_supplementary,
        asset_profile=asset_profile,
    )
    body_sections = tuple(renderable_body_sections(article.sections))
    rendered_abstract_sections = tuple(abstract_sections(article.sections))
    lead_sections, remaining_body_sections = split_leading_abstract_context_sections(body_sections)
    retained_sections = tuple(
        section
        for section in article.sections
        if strip_markdown_images(section.text) and normalize_text(section.kind).lower() == "data_availability"
    )
    figure_assets = selected_figure_assets(article.assets, asset_profile=asset_profile)
    figure_assets = filter_inline_body_figure_assets(figure_assets, sections=body_sections)
    return _MarkdownRenderPlan(
        token_budget=token_budget,
        abstract_text=first_abstract_text(abstract_text=article.metadata.abstract, sections=article.sections),
        abstract_sections=rendered_abstract_sections,
        level_shift=compute_level_shift(body_sections or retained_sections),
        include_figures=effective_include_figures,
        reference_count=resolve_reference_limit(effective_include_refs, len(article.references)),
        lead_sections=lead_sections,
        body_sections=remaining_body_sections,
        retained_sections=retained_sections,
        figure_assets=tuple(figure_assets),
        table_assets=tuple(selected_table_assets(article.assets, asset_profile=asset_profile)),
        supplementary_assets=tuple(
            selected_supplementary_assets(
                article.assets,
                asset_profile=asset_profile,
                include_supplementary=effective_include_supplementary,
            )
        ),
    )


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


def render_abstract_section_block(abstract_text: str) -> RenderedBlock:
    return render_section_block(Section(heading="Abstract", level=2, kind="abstract", text=abstract_text))


def _append_abstract_with_budget(
    lines: list[str],
    *,
    abstract_text: str,
    context: RenderContext,
    as_section: bool = False,
) -> None:
    if not abstract_text:
        return
    abstract_block = render_abstract_section_block(abstract_text) if as_section else render_abstract_block(abstract_text)
    if context.append_if_fits(lines, abstract_block):
        return
    truncated_text = truncate_text_to_tokens(abstract_text, max(int(context.remaining_budget - 8), 0))
    if truncated_text:
        context.append_if_fits(
            lines,
            render_abstract_section_block(truncated_text) if as_section else render_abstract_block(truncated_text),
        )
    context.mark_truncated()


def _append_sections_with_budget(
    lines: list[str],
    *,
    sections: tuple["Section", ...],
    level_shift: int,
    context: RenderContext,
    preserve_source_order: bool = False,
) -> None:
    selected_sections: list[tuple[int, RenderedBlock]] = []
    indexed_sections = list(enumerate(sections))
    ordered_sections = indexed_sections if preserve_source_order else sorted(
        indexed_sections,
        key=lambda item: (section_priority(item[1]), item[0]),
    )
    for index, section in ordered_sections:
        section_block = render_section_block(section, level_shift=level_shift)
        if section_block.token_estimate <= context.remaining_budget:
            selected_sections.append((index, section_block))
            context.remaining_budget -= section_block.token_estimate
            continue
        if not math.isinf(context.remaining_budget) and context.remaining_budget > 64:
            truncated_text = truncate_text_to_tokens(
                section.text,
                max(int(context.remaining_budget - estimate_tokens(section.heading) - 4), 0),
            )
            if truncated_text:
                truncated_section = Section(
                    heading=section.heading,
                    level=section.level,
                    kind=section.kind,
                    text=truncated_text,
                )
                selected_sections.append(
                    (
                        index,
                        render_section_block(truncated_section, level_shift=level_shift),
                    )
                )
                context.remaining_budget = 0
        context.mark_truncated()
        break

    for _, section_block in sorted(selected_sections, key=lambda item: item[0]):
        lines.extend(section_block.lines)


def normalize_asset_section(asset: Asset) -> str:
    normalized = normalize_text(asset.section).lower()
    return normalized or "body"


def normalize_asset_render_state(asset: Asset) -> str:
    return normalize_text(asset.render_state).lower()


def asset_is_appendable(asset: Asset) -> bool:
    return normalize_asset_render_state(asset) not in {"inline", "suppressed"}


def asset_in_body(asset: Asset) -> bool:
    return normalize_asset_section(asset) not in {"appendix", "supplementary"}


def selected_figure_assets(assets: list[Asset], *, asset_profile: AssetProfile) -> list[Asset]:
    figure_assets = [asset for asset in assets if asset.kind == "figure" and asset_is_appendable(asset)]
    if asset_profile == "body":
        return [asset for asset in figure_assets if asset_in_body(asset)]
    return figure_assets


def _inline_markdown_image_urls(sections: Sequence["Section"]) -> set[str]:
    urls: set[str] = set()
    for section in sections:
        for match in MARKDOWN_IMAGE_URL_PATTERN.finditer(section.text or ""):
            candidate = normalize_text(match.group(1)).strip("<>")
            if candidate:
                urls.add(candidate)
    return urls


def _image_reference_candidates(value: str | None) -> set[str]:
    normalized = normalize_text(value).strip("<>")
    if not normalized:
        return set()

    parsed = urllib.parse.urlsplit(normalized)
    path = parsed.path or normalized
    candidates = {normalized, path, urllib.parse.unquote(normalized), urllib.parse.unquote(path)}
    cleaned: set[str] = set()
    for candidate in candidates:
        text = normalize_text(candidate).replace("\\", "/")
        text = re.sub(r"/+", "/", text).strip()
        text = text.removeprefix("./")
        if text:
            cleaned.add(text)
            cleaned.add(text.lstrip("/"))
    return cleaned


def _image_reference_basename(value: str) -> str:
    return value.rstrip("/").rsplit("/", 1)[-1]


def _image_references_match(left: set[str], right: set[str]) -> bool:
    if left & right:
        return True
    for left_item in left:
        for right_item in right:
            if left_item.endswith(f"/{right_item}") or right_item.endswith(f"/{left_item}"):
                return True
    left_basenames = {_image_reference_basename(item) for item in left if _image_reference_basename(item)}
    right_basenames = {_image_reference_basename(item) for item in right if _image_reference_basename(item)}
    return bool(left_basenames & right_basenames)


def _asset_link_field(asset: Asset | Mapping[str, Any], field: str) -> str | None:
    if isinstance(asset, Asset):
        return getattr(asset, field, None)
    return safe_text(asset.get(field)) or None


def _asset_markdown_reference_candidates(asset: Asset | Mapping[str, Any]) -> set[str]:
    candidates: set[str] = set()
    for field in (
        "path",
        "url",
        "original_url",
        "download_url",
        "source_url",
        "preview_url",
        "full_size_url",
        "link",
    ):
        candidates |= _image_reference_candidates(_asset_link_field(asset, field))
    return candidates


def rewrite_markdown_asset_links(markdown_text: str, assets: Sequence[Asset | Mapping[str, Any]] | None) -> str:
    if not markdown_text or not assets:
        return markdown_text

    indexed_assets: list[tuple[str, set[str]]] = []
    for asset in assets:
        replacement_path = safe_text(_asset_link_field(asset, "path"))
        if not replacement_path:
            continue
        candidates = _asset_markdown_reference_candidates(asset)
        if candidates:
            indexed_assets.append((replacement_path, candidates))

    if not indexed_assets:
        return markdown_text

    def replace(match: re.Match[str]) -> str:
        inline_url = normalize_text(match.group(2)).strip("<>")
        inline_candidates = _image_reference_candidates(inline_url)
        if not inline_candidates:
            return match.group(0)
        for replacement_path, asset_candidates in indexed_assets:
            if _image_references_match(asset_candidates, inline_candidates):
                return f"![{match.group(1)}]({replacement_path})"
        return match.group(0)

    return MARKDOWN_IMAGE_LINK_PATTERN.sub(replace, markdown_text)


def filter_inline_body_figure_assets(
    assets: Sequence[Asset],
    *,
    sections: Sequence["Section"],
) -> list[Asset]:
    inline_urls = _inline_markdown_image_urls(sections)
    if not inline_urls:
        return list(assets)
    inline_candidates = [_image_reference_candidates(url) for url in inline_urls]

    remaining: list[Asset] = []
    for asset in assets:
        if not asset_in_body(asset):
            remaining.append(asset)
            continue
        asset_candidates = _image_reference_candidates(asset.path) | _image_reference_candidates(asset.url)
        if asset_candidates and any(
            _image_references_match(asset_candidates, inline_candidate)
            for inline_candidate in inline_candidates
            if inline_candidate
        ):
            continue
        remaining.append(asset)
    return remaining


def selected_table_assets(assets: list[Asset], *, asset_profile: AssetProfile) -> list[Asset]:
    table_assets = [asset for asset in assets if asset.kind == "table" and asset_is_appendable(asset)]
    if asset_profile == "none":
        return []
    if asset_profile == "body":
        return [asset for asset in table_assets if asset_in_body(asset)]
    return table_assets


def selected_supplementary_assets(
    assets: list[Asset],
    *,
    asset_profile: AssetProfile,
    include_supplementary: bool,
) -> list[Asset]:
    if not include_supplementary:
        return []
    supplementary_assets = [asset for asset in assets if asset.kind == "supplementary"]
    if asset_profile == "body":
        return [asset for asset in supplementary_assets if asset_in_body(asset)]
    if asset_profile == "none":
        return []
    return supplementary_assets


def build_rendered_block(lines: list[str], *, normalized_text: str | None = None) -> RenderedBlock:
    normalized = normalized_text if normalized_text is not None else normalize_markdown_text("\n".join(lines))
    return RenderedBlock(
        lines=tuple(lines),
        normalized_text=normalized,
        token_estimate=estimate_normalized_tokens(normalized),
    )


def render_abstract_block(abstract_text: str) -> RenderedBlock:
    return build_rendered_block([f"**Abstract.** {abstract_text}", ""])


def append_asset_block(lines: list[str], *, heading: str, item_groups: list[RenderedBlock]) -> None:
    if not item_groups:
        return
    lines.extend([f"## {heading}", ""])
    for group in item_groups:
        lines.extend(group.lines)
    lines.append("")


def append_asset_block_with_budget(
    lines: list[str],
    *,
    heading: str,
    item_groups: list[RenderedBlock],
    context: RenderContext,
) -> None:
    if not item_groups:
        return

    header_block = build_rendered_block([f"## {heading}", ""])
    if header_block.token_estimate > context.remaining_budget:
        context.mark_truncated()
        return

    selected_groups: list[RenderedBlock] = []
    remaining_after_header = context.remaining_budget - header_block.token_estimate
    for group in item_groups:
        if group.token_estimate <= remaining_after_header:
            selected_groups.append(group)
            remaining_after_header -= group.token_estimate
            continue
        context.mark_truncated()
        break

    if not selected_groups:
        return

    lines.extend(header_block.lines)
    for group in selected_groups:
        lines.extend(group.lines)
    lines.append("")
    context.remaining_budget = remaining_after_header


def asset_block_heading(default_heading: str, assets: Sequence[Asset]) -> str:
    if assets and all(normalize_asset_render_state(asset) == "appendix" for asset in assets):
        return f"Additional {default_heading}"
    return default_heading


def _render_reference_line(reference_raw: str) -> str:
    normalized = normalize_text(reference_raw)
    if NUMBERED_REFERENCE_PATTERN.match(normalized):
        return normalized
    return f"- {normalized}"


def append_reference_block(
    lines: list[str],
    *,
    references: list[Reference],
    total_references: int,
    shown_references: int,
) -> None:
    if not references:
        return
    lines.extend([f"## References ({total_references} total, showing {shown_references})", ""])
    for reference in references:
        lines.append(_render_reference_line(reference.raw))
    lines.append("")


def append_reference_block_with_budget(
    lines: list[str],
    *,
    references: list[Reference],
    total_references: int,
    context: RenderContext,
) -> None:
    if not references:
        return

    header_block = build_rendered_block([f"## References ({total_references} total, showing {len(references)})", ""])
    if header_block.token_estimate > context.remaining_budget:
        context.mark_truncated()
        return

    selected_references: list[RenderedBlock] = []
    remaining_after_header = context.remaining_budget - header_block.token_estimate
    for reference in references:
        candidate_block = build_rendered_block([_render_reference_line(reference.raw)])
        if candidate_block.token_estimate <= remaining_after_header:
            selected_references.append(candidate_block)
            remaining_after_header -= candidate_block.token_estimate
            continue
        if not math.isinf(remaining_after_header) and remaining_after_header > 16:
            truncated_reference = truncate_text_to_tokens(reference.raw, max(8, int(remaining_after_header - 2)))
            truncated_block = build_rendered_block([_render_reference_line(truncated_reference)])
            if truncated_block.token_estimate <= remaining_after_header:
                selected_references.append(truncated_block)
                remaining_after_header -= truncated_block.token_estimate
        context.mark_truncated()
        break

    if not selected_references:
        return

    lines.extend(build_rendered_block([f"## References ({total_references} total, showing {len(selected_references)})", ""]).lines)
    for block in selected_references:
        lines.extend(block.lines)
    lines.append("")
    context.remaining_budget = remaining_after_header


def render_figure_asset_groups(assets: list[Asset], *, include_figures: str) -> list[RenderedBlock]:
    if include_figures not in {"captions_only", "inline"}:
        return []

    item_groups: list[RenderedBlock] = []
    for asset in assets:
        if is_table_like_figure_asset(asset):
            continue
        heading = normalize_text(asset.heading) or "Figure"
        caption = normalize_text(asset.caption)
        link = asset_link(asset)
        if include_figures == "inline" and link:
            group = [f"![{heading}]({link})", ""]
            if caption:
                group.extend([caption, ""])
            item_groups.append(build_rendered_block(group))
            continue
        if caption:
            item_groups.append(build_rendered_block([f"- {heading}: {caption}"]))
        elif heading:
            item_groups.append(build_rendered_block([f"- {heading}"]))
    return item_groups


def render_table_asset_groups(assets: list[Asset]) -> list[RenderedBlock]:
    item_groups: list[RenderedBlock] = []
    for asset in assets:
        heading = normalize_text(asset.heading) or "Table"
        caption = normalize_text(asset.caption)
        link = asset_link(asset)
        if link:
            group = [f"![{heading}]({link})", ""]
            if caption:
                group.extend([caption, ""])
            item_groups.append(build_rendered_block(group))
            continue
        if caption:
            item_groups.append(build_rendered_block([f"- {heading}: {caption}"]))
        elif heading:
            item_groups.append(build_rendered_block([f"- {heading}"]))
    return item_groups


def render_supplementary_asset_groups(assets: list[Asset]) -> list[RenderedBlock]:
    item_groups: list[RenderedBlock] = []
    for asset in assets:
        heading = normalize_text(asset.heading) or "Supplementary Material"
        caption = normalize_text(asset.caption)
        link = asset_link(asset)
        bullet = f"- [{heading}]({link})" if link else f"- {heading}"
        if caption:
            bullet += f": {caption}"
        item_groups.append(build_rendered_block([bullet]))
    return item_groups


def render_heading(section: Section, *, level_shift: int = 0) -> str:
    if not normalize_text(section.heading):
        return ""
    level = max(2, min(section.level - level_shift, 6))
    return f"{'#' * level} {section.heading}"


def render_section(section: Section, *, level_shift: int = 0) -> str:
    heading = render_heading(section, level_shift=level_shift)
    if not heading:
        return section.text.strip()
    return f"{heading}\n\n{section.text}".strip()


def render_section_block(section: Section, *, level_shift: int = 0) -> RenderedBlock:
    heading = render_heading(section, level_shift=level_shift)
    if not heading:
        normalized_text = normalize_markdown_text(section.text)
        return build_rendered_block(
            [*normalized_text.splitlines(), ""],
            normalized_text=normalized_text,
        )
    if not normalize_text(section.text):
        normalized_text = normalize_markdown_text(heading)
        return build_rendered_block(
            [*normalized_text.splitlines(), ""],
            normalized_text=normalized_text,
        )
    normalized_text = normalize_markdown_text(f"{heading}\n\n{section.text}".strip())
    return build_rendered_block(
        [*normalized_text.splitlines(), ""],
        normalized_text=normalized_text,
    )


def compute_level_shift(sections: Sequence[Section]) -> int:
    """Return how many heading levels to subtract so the shallowest body
    section renders at level 2 (right under the article title at level 1).

    Diagnostics / hardcoded level=2 sections are excluded so we don't anchor
    on them.
    """
    body_levels = [
        section.level
        for section in sections
        if normalize_text(section.kind).lower() not in BODY_SECTION_EXCLUDED_KINDS and section.level > 0
    ]
    if not body_levels:
        return 0
    return max(0, min(body_levels) - 2)


def _normalize_section_hint_heading(value: str) -> str:
    return normalize_text(value).lower().strip(" :")


def _coerce_section_hints(
    section_hints: Sequence[SectionHint | Mapping[str, Any]] | None,
) -> list[SectionHint]:
    coerced: list[SectionHint] = []
    for index, hint in enumerate(section_hints or []):
        if isinstance(hint, SectionHint):
            candidate = hint
        elif isinstance(hint, Mapping):
            heading = normalize_text(hint.get("heading"))
            kind = normalize_text(hint.get("kind")).lower()
            if not heading or kind not in SECTION_HINT_KINDS:
                continue
            raw_level = hint.get("level")
            raw_order = hint.get("order")
            candidate = SectionHint(
                heading=heading,
                level=int(raw_level) if isinstance(raw_level, int) or str(raw_level).isdigit() else 2,
                kind=kind,
                order=int(raw_order) if isinstance(raw_order, int) or str(raw_order).isdigit() else index,
                language=normalize_text(hint.get("language")) or None,
                source_selector=normalize_text(hint.get("source_selector")) or None,
            )
        else:
            continue
        if not normalize_text(candidate.heading) or normalize_text(candidate.kind).lower() not in SECTION_HINT_KINDS:
            continue
        coerced.append(candidate)
    coerced.sort(key=lambda item: item.order)
    return coerced


def _match_next_section_hint(
    section_hints: Sequence[SectionHint],
    hint_index: int,
    heading: str,
) -> tuple[SectionHint | None, int]:
    heading_key = _normalize_section_hint_heading(heading)
    if not heading_key:
        return None, hint_index
    for index in range(hint_index, len(section_hints)):
        if _normalize_section_hint_heading(section_hints[index].heading) == heading_key:
            return section_hints[index], index + 1
    return None, hint_index


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


def _canonical_match_text(value: str) -> str:
    return re.sub(r"[\W_]+", "", normalize_text(value).lower(), flags=re.UNICODE)


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
) -> Section | None:
    if normalize_text(original_section.kind).lower() != "body":
        return stripped_section
    if normalize_text(original_section.heading).lower() != "methods summary":
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


def normalize_authors(value: Any) -> list[str]:
    if isinstance(value, list):
        return [normalize_inline_html_text(item) for item in value if normalize_inline_html_text(item)]
    if isinstance(value, str):
        parts = [normalize_inline_html_text(part) for part in re.split(r"\s*;\s*|\s*,\s*", value)]
        return [part for part in parts if part]
    return []


def normalize_abstract_text(value: Any) -> str:
    text = normalize_inline_html_text(value)
    if not text:
        return ""
    text = MARKDOWN_ABSTRACT_PREFIX_PATTERN.sub("", text, count=1).lstrip()
    return ABSTRACT_PREFIX_PATTERN.sub("", text, count=1).lstrip()


def normalize_inline_html_text(value: Any) -> str:
    text = html.unescape(safe_text(value))
    if not text:
        return ""
    if not INLINE_HTML_TAG_PATTERN.search(text):
        return text
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\s*(<br\s*/?>)\s*", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*<(sub|sup)>\s*", r"<\1>", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+</(sub|sup)>", r"</\1>", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+(<(?:sub|sup)>)", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"(</(?:sub|sup)>)\s*\n\s*", r"\1 ", text, flags=re.IGNORECASE)
    text = re.sub(r"(</(?:sub|sup)>)(?=[A-Za-z0-9])", r"\1 ", text, flags=re.IGNORECASE)
    text = re.sub(r"(</(?:sub|sup)>)\s+([,.;:%\]\}\+\)])", r"\1\2", text, flags=re.IGNORECASE)
    return text.strip()


def strip_leading_markdown_title_heading(markdown_text: str, *, title: str | None) -> str:
    normalized_markdown = normalize_markdown_text(markdown_text)
    normalized_title = normalize_text(title)
    if not normalized_markdown or not normalized_title:
        return normalized_markdown

    lines = normalized_markdown.splitlines()
    line_index = 0
    while line_index < len(lines) and not normalize_text(lines[line_index]):
        line_index += 1
    if line_index >= len(lines):
        return normalized_markdown

    match = re.match(r"^(#+)\s*(.*?)\s*$", lines[line_index].strip())
    if match is None or len(match.group(1)) != 1:
        return normalized_markdown
    heading_text = normalize_text(match.group(2))
    if _canonical_match_text(heading_text) != _canonical_match_text(normalized_title):
        return normalized_markdown

    trimmed_lines = list(lines[:line_index]) + list(lines[line_index + 1 :])
    while line_index < len(trimmed_lines) and not normalize_text(trimmed_lines[line_index]):
        trimmed_lines.pop(line_index)
    return normalize_markdown_text("\n".join(trimmed_lines))


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
        from .providers._html_availability import assess_structured_article_fulltext_availability

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
        section = _promote_stripped_methods_summary_section(original_section, section)
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
        from .providers._html_availability import assess_plain_text_fulltext_availability

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
