"""Schema dataclasses and public model type aliases."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from ..tracing import TraceEvent, source_trail_from_trace, trace_from_markers
from ..utils import normalize_text

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


TRUNCATION_WARNING = "Output truncated to satisfy token budget."
EXTRACTION_REVISION = 2


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
    asset_failures: list[dict[str, Any]] = field(default_factory=list)
    extraction_revision: int = EXTRACTION_REVISION

    def __post_init__(self) -> None:
        from .quality import (
            _dedupe_strings,
            coerce_asset_failure_diagnostics,
            coerce_body_quality_metrics,
            coerce_semantic_losses,
        )
        from .tokens import coerce_token_estimate_breakdown

        self.warnings = _dedupe_strings(self.warnings)
        self.source_trail = _dedupe_strings(self.source_trail)
        self.flags = _dedupe_strings(self.flags)
        self.body_metrics = coerce_body_quality_metrics(self.body_metrics)
        self.semantic_losses = coerce_semantic_losses(self.semantic_losses)
        self.asset_failures = coerce_asset_failure_diagnostics(self.asset_failures)
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
        from .quality import _clone_quality, _dedupe_strings
        from .tokens import coerce_token_estimate_breakdown

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
        from .quality import apply_quality_assessment, classify_content
        from .sections import first_abstract_text

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
        from .render import (
            _append_abstract_with_budget,
            _append_sections_with_budget,
            _build_article_header_block,
            _build_markdown_render_plan,
            append_asset_block_with_budget,
            append_reference_block_with_budget,
            asset_block_heading,
            render_figure_asset_groups,
            render_supplementary_asset_groups,
            render_table_asset_groups,
        )

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


__all__ = [
    "SourceKind",
    "OutputMode",
    "AssetProfile",
    "MaxTokensMode",
    "ContentKind",
    "QualityConfidence",
    "TRUNCATION_WARNING",
    "EXTRACTION_REVISION",
    "Metadata",
    "Section",
    "SectionHint",
    "ExtractedAbstractBlock",
    "Reference",
    "Asset",
    "TokenEstimateBreakdown",
    "BodyQualityMetrics",
    "SemanticLosses",
    "Quality",
    "RenderOptions",
    "RenderedBlock",
    "RenderContext",
    "FetchEnvelope",
    "ArticleModel",
]
