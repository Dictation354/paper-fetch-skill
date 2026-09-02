"""Schema dataclasses and public model type aliases."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from ..acquisition import (
    AcquisitionProvenance,
    AcquisitionRepresentation,
    AcquisitionTransport,
    coerce_acquisition_provenance,
)
from ..tracing import TraceEvent, source_trail_from_trace, trace_from_markers
from ..utils import normalize_text

SourceKind = Literal[
    "elsevier_xml",
    "elsevier_pdf",
    "springer_html",
    "springer_pdf",
    "wiley_browser",
    "science",
    "pnas",
    "mdpi_html",
    "mdpi_pdf",
    "royalsocietypublishing_html",
    "royalsocietypublishing_pdf",
    "annualreviews_html",
    "annualreviews_pdf",
    "oxfordacademic_html",
    "oxfordacademic_pdf",
    "plos_xml",
    "plos_pdf",
    "frontiers_xml",
    "frontiers_pdf",
    "ieee_html",
    "ieee_pdf",
    "arxiv_html",
    "arxiv_pdf",
    "copernicus_xml",
    "copernicus_pdf",
    "ams_html",
    "ams_pdf",
    "acs",
    "iop_html",
    "iop_pdf",
    "aip_html",
    "aip_pdf",
    "tandf_html",
    "tandf_pdf",
    "crossref_meta",
]


OutputMode = Literal["article", "markdown", "metadata"]


AssetProfile = Literal["none", "body", "all"]


AssetLogicalKind = Literal[
    "figure",
    "formula",
    "table",
    "supplement",
    "decoration",
]


AssetDiagnosticStatus = Literal[
    "available",
    "not_requested",
    "not_archived",
    "failed",
    "placeholder_suspected",
]


MaxTokensMode = int | Literal["full_text"]


# Public wire/schema contract: keep these Literal values explicit for static
# typing and generated schemas; do not derive them from runtime reason-code
# constants even though the string values intentionally match.
ContentKind = Literal["fulltext", "abstract_only", "metadata_only"]


QualityConfidence = Literal["high", "medium", "low"]


TRUNCATION_WARNING = "Output truncated to satisfy token budget."
EXTRACTION_REVISION = 4


@dataclass
class Metadata:
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    abstract: str | None = None
    journal: str | None = None
    article_type: str | None = None
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
    source_url: str | None = None
    source_path: str | None = None
    source_href: str | None = None
    content_type: str | None = None
    downloaded_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    preview_accepted: bool = False
    browser_backend: str | None = None
    final_fetcher: str | None = None
    recovery_attempts: list[dict[str, Any]] = field(default_factory=list)
    provenance: list[str] = field(default_factory=list)
    asset_timing: dict[str, Any] = field(default_factory=dict)


@dataclass
class AssetDiagnostic:
    """Serializable, conservative facts for one logical asset."""

    request_profile: AssetProfile = "none"
    kind: AssetLogicalKind = "decoration"
    status: AssetDiagnosticStatus = "not_requested"
    download_tier: str | None = None
    path: str | None = None
    real_mime: str | None = None
    byte_count: int | None = None
    width: int | None = None
    height: int | None = None
    preview_accepted: bool = False
    sha256: str | None = None
    failure_code: str | None = None
    provenance: list[str] = field(default_factory=list)
    suspected_reasons: list[str] = field(default_factory=list)


@dataclass
class AssetKindSummary:
    """Machine-readable counts for one canonical logical asset kind."""

    total: int = 0
    requested: int = 0
    full_size: int = 0
    preview: int = 0
    accepted_preview: int = 0
    fallback_preview: int = 0
    failed: int = 0
    placeholder_suspected: int = 0
    not_requested: int = 0
    not_archived: int = 0


def _empty_asset_kind_summaries() -> dict[AssetLogicalKind, AssetKindSummary]:
    return {
        "figure": AssetKindSummary(),
        "formula": AssetKindSummary(),
        "table": AssetKindSummary(),
        "supplement": AssetKindSummary(),
        "decoration": AssetKindSummary(),
    }


@dataclass
class AssetQualitySummary:
    """Structured asset-quality facet kept separate from text quality."""

    audited: bool = False
    requested: bool = False
    profile: AssetProfile = "none"
    expected: int | None = None
    discovered: int = 0
    attempted: int = 0
    total: int = 0
    local: int = 0
    full_size: int = 0
    preview: int = 0
    accepted_preview: int = 0
    fallback_preview: int = 0
    failed: int = 0
    placeholder_suspected: int = 0
    not_requested: int = 0
    not_archived: int = 0
    remote_link_count: int = 0
    remote_only_count: int = 0
    failure_codes: list[str] = field(default_factory=list)
    issue_codes: list[str] = field(default_factory=list)
    by_kind: dict[AssetLogicalKind, AssetKindSummary] = field(
        default_factory=_empty_asset_kind_summaries
    )
    diagnostics: list[AssetDiagnostic] = field(default_factory=list)


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
    token_estimate_breakdown: TokenEstimateBreakdown = field(
        default_factory=TokenEstimateBreakdown
    )
    confidence: QualityConfidence = "low"
    flags: list[str] = field(default_factory=list)
    body_metrics: BodyQualityMetrics = field(default_factory=BodyQualityMetrics)
    semantic_losses: SemanticLosses = field(default_factory=SemanticLosses)
    asset_failures: list[dict[str, Any]] = field(default_factory=list)
    asset_summary: AssetQualitySummary = field(default_factory=AssetQualitySummary)
    extraction_revision: int = EXTRACTION_REVISION

    def __post_init__(self) -> None:
        from .quality import (
            _dedupe_strings,
            coerce_asset_failure_diagnostics,
            coerce_asset_quality_summary,
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
        self.asset_summary = coerce_asset_quality_summary(self.asset_summary)
        self.token_estimate_breakdown = coerce_token_estimate_breakdown(
            self.token_estimate_breakdown
        )
        self.extraction_revision = int(self.extraction_revision or EXTRACTION_REVISION)
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
    abstract_sections: tuple[Section, ...]
    level_shift: int
    include_figures: str
    reference_count: int
    lead_sections: tuple[Section, ...]
    body_sections: tuple[Section, ...]
    retained_sections: tuple[Section, ...]
    figure_assets: tuple[Asset, ...]
    table_assets: tuple[Asset, ...]
    supplementary_assets: tuple[Asset, ...]


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


_FETCH_ENVELOPE_QUALITY_FIELDS = frozenset(
    {
        "has_fulltext",
        "content_kind",
        "has_abstract",
        "warnings",
        "source_trail",
        "token_estimate",
        "token_estimate_breakdown",
    }
)


@dataclass(kw_only=True)
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
    token_estimate_breakdown: TokenEstimateBreakdown = field(
        default_factory=TokenEstimateBreakdown
    )
    quality: Quality = field(default_factory=Quality)
    article: ArticleModel | None = None
    markdown: str | None = None
    metadata: Metadata | None = None
    diagnostic_artifacts: list[dict[str, Any]] = field(default_factory=list)
    acquisition: AcquisitionProvenance | None = None

    def __getattribute__(self, name: str) -> Any:
        if name in _FETCH_ENVELOPE_QUALITY_FIELDS:
            state = object.__getattribute__(self, "__dict__")
            quality = state.get("quality")
            if quality is not None:
                return getattr(quality, name)
        return object.__getattribute__(self, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in _FETCH_ENVELOPE_QUALITY_FIELDS:
            state = object.__getattribute__(self, "__dict__")
            quality = state.get("quality")
            if quality is not None and name not in state:
                setattr(quality, name, value)
                return
        object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def __post_init__(self) -> None:
        from .quality import _dedupe_strings
        from .tokens import coerce_token_estimate_breakdown

        state = object.__getattribute__(self, "__dict__")
        has_fulltext = bool(state["has_fulltext"])
        content_kind = state["content_kind"]
        has_abstract = bool(state["has_abstract"])
        warnings = state["warnings"]
        source_trail = state["source_trail"]
        token_estimate = int(state["token_estimate"])
        token_estimate_breakdown = state["token_estimate_breakdown"]
        self.acquisition = coerce_acquisition_provenance(self.acquisition)
        if self.article is not None:
            self.quality = self.article.quality
            if self.acquisition is None:
                self.acquisition = self.article.acquisition
            elif self.article.acquisition is None:
                self.article.acquisition = self.acquisition
            elif self.article.acquisition != self.acquisition:
                raise ValueError(
                    "FetchEnvelope and ArticleModel acquisition provenance must match."
                )
        if self.trace and not source_trail:
            source_trail = source_trail_from_trace(self.trace)
        elif source_trail and not self.trace:
            self.trace = trace_from_markers(source_trail)
        if content_kind == "fulltext":
            has_fulltext = True
        elif content_kind == "abstract_only":
            has_fulltext = False
            has_abstract = True
        elif has_fulltext:
            content_kind = "fulltext"
        elif has_abstract:
            content_kind = "abstract_only"
        self.quality.has_fulltext = self.quality.has_fulltext or has_fulltext
        if content_kind != "metadata_only":
            self.quality.content_kind = content_kind
        self.quality.has_abstract = self.quality.has_abstract or has_abstract
        self.quality.warnings = _dedupe_strings([*self.quality.warnings, *warnings])
        self.quality.source_trail = _dedupe_strings(
            [*self.quality.source_trail, *source_trail]
        )
        if token_estimate and not self.quality.token_estimate:
            self.quality.token_estimate = token_estimate
        if (
            token_estimate_breakdown != TokenEstimateBreakdown()
            and self.quality.token_estimate_breakdown == TokenEstimateBreakdown()
        ):
            self.quality.token_estimate_breakdown = coerce_token_estimate_breakdown(
                token_estimate_breakdown
            )
        for name in _FETCH_ENVELOPE_QUALITY_FIELDS:
            state.pop(name, None)


@dataclass(kw_only=True)
class ArticleModel:
    doi: str | None
    source: SourceKind
    metadata: Metadata
    sections: list[Section] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)
    quality: Quality = field(
        default_factory=lambda: Quality(has_fulltext=False, token_estimate=0)
    )
    acquisition: AcquisitionProvenance | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def __post_init__(self) -> None:
        from .quality import apply_quality_assessment, classify_content
        from .sections import first_abstract_text

        self.acquisition = coerce_acquisition_provenance(self.acquisition)
        abstract_text = first_abstract_text(
            abstract_text=self.metadata.abstract, sections=self.sections
        )
        if not abstract_text:
            abstract_text = ""
        if abstract_text and not normalize_text(self.metadata.abstract):
            self.metadata.abstract = abstract_text
        content_kind = classify_content(
            sections=self.sections, abstract_text=abstract_text
        )
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
            remaining_budget=render_plan.token_budget
            - front_matter_block.token_estimate,
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
            item_groups=render_figure_asset_groups(
                list(render_plan.figure_assets),
                include_figures=render_plan.include_figures,
            ),
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
            item_groups=render_supplementary_asset_groups(
                list(render_plan.supplementary_assets)
            ),
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
    "EXTRACTION_REVISION",
    "TRUNCATION_WARNING",
    "AcquisitionProvenance",
    "AcquisitionRepresentation",
    "AcquisitionTransport",
    "ArticleModel",
    "Asset",
    "AssetDiagnostic",
    "AssetDiagnosticStatus",
    "AssetKindSummary",
    "AssetLogicalKind",
    "AssetProfile",
    "AssetQualitySummary",
    "BodyQualityMetrics",
    "ContentKind",
    "ExtractedAbstractBlock",
    "FetchEnvelope",
    "MaxTokensMode",
    "Metadata",
    "OutputMode",
    "Quality",
    "QualityConfidence",
    "Reference",
    "RenderContext",
    "RenderOptions",
    "RenderedBlock",
    "Section",
    "SectionHint",
    "SemanticLosses",
    "SourceKind",
    "TokenEstimateBreakdown",
    "coerce_acquisition_provenance",
]
