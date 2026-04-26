"""Typed MCP tool output schemas used for FastMCP structured output."""

from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class ResolvedCandidateOutput(TypedDict, total=False):
    doi: str | None
    title: str | None
    journal_title: str | None
    published: str | None
    landing_page_url: str | None
    provider_hint: str | None
    score: float


class ErrorPayloadOutput(TypedDict, total=False):
    status: str
    reason: str
    candidates: list[ResolvedCandidateOutput] | None
    missing_env: list[str] | None


class ResolvePaperOutput(ErrorPayloadOutput, total=False):
    query: str
    query_kind: str
    doi: str | None
    landing_url: str | None
    provider_hint: str | None
    confidence: float
    candidates: list[ResolvedCandidateOutput]
    title: str | None


class HasFulltextOutput(ErrorPayloadOutput, total=False):
    query: str
    doi: str | None
    state: str
    evidence: list[str]
    warnings: list[str]


class MetadataOutput(TypedDict, total=False):
    title: str | None
    authors: list[str]
    abstract: str | None
    journal: str | None
    published: str | None
    keywords: list[str]
    license_urls: list[str]
    landing_page_url: str | None


class SectionOutput(TypedDict, total=False):
    heading: str
    level: int
    kind: str
    text: str


class ReferenceOutput(TypedDict, total=False):
    raw: str
    doi: str | None
    title: str | None
    year: str | None


class AssetOutput(TypedDict, total=False):
    kind: str
    heading: str
    caption: str | None
    url: str | None
    path: str | None
    section: str | None
    render_state: str | None
    anchor_key: str | None
    download_tier: str | None
    download_url: str | None
    original_url: str | None
    content_type: str | None
    downloaded_bytes: int | None
    width: int | None
    height: int | None


class TokenEstimateBreakdownOutput(TypedDict, total=False):
    abstract: int
    body: int
    refs: int


class BodyMetricsOutput(TypedDict, total=False):
    char_count: int
    word_count: int
    body_block_count: int
    body_heading_count: int
    body_to_abstract_ratio: float
    explicit_body_container: bool
    post_abstract_body_run: bool
    figure_count: int


class SemanticLossesOutput(TypedDict, total=False):
    table_fallback_count: int
    table_lossy_count: int
    table_layout_degraded_count: int
    table_semantic_loss_count: int
    formula_fallback_count: int
    formula_missing_count: int


class TraceEventOutput(TypedDict, total=False):
    stage: str
    component: str
    outcome: str
    code: str | None
    message: str | None


class AssetFailureOutput(TypedDict, total=False):
    kind: str
    heading: str
    caption: str | None
    source_url: str
    section: str | None
    status: int | None
    content_type: str | None
    final_url: str | None
    title_snippet: str | None
    body_snippet: str | None
    reason: str
    recovery_attempts: list[dict[str, Any]]


class QualityOutput(TypedDict, total=False):
    has_fulltext: bool
    content_kind: str
    has_abstract: bool
    token_estimate: int
    token_estimate_breakdown: TokenEstimateBreakdownOutput
    warnings: list[str]
    source_trail: list[str]
    trace: list[TraceEventOutput]
    confidence: str
    flags: list[str]
    body_metrics: BodyMetricsOutput
    semantic_losses: SemanticLossesOutput
    asset_failures: list[AssetFailureOutput]
    extraction_revision: int


class ArticleOutput(TypedDict, total=False):
    doi: str | None
    source: str
    metadata: MetadataOutput
    sections: list[SectionOutput]
    references: list[ReferenceOutput]
    assets: list[AssetOutput]
    quality: QualityOutput


class FetchPaperOutput(ErrorPayloadOutput, total=False):
    doi: str | None
    source: str
    has_fulltext: bool
    content_kind: str
    has_abstract: bool
    warnings: list[str]
    source_trail: list[str]
    trace: list[TraceEventOutput]
    token_estimate: int
    token_estimate_breakdown: TokenEstimateBreakdownOutput
    quality: QualityOutput
    article: ArticleOutput | None
    markdown: str | None
    metadata: MetadataOutput | None


class CacheEntryOutput(TypedDict, total=False):
    id: str
    doi: str
    kind: str
    path: str
    mime: str
    size: int
    mtime: float


class PreferredCacheEntriesOutput(TypedDict, total=False):
    markdown: CacheEntryOutput | None
    primary_payload: CacheEntryOutput | None
    assets: list[CacheEntryOutput]


class ListCachedOutput(ErrorPayloadOutput, total=False):
    download_dir: str | None
    entries: list[CacheEntryOutput]


class GetCachedOutput(ErrorPayloadOutput, total=False):
    status: str
    doi: str
    download_dir: str | None
    entries: list[CacheEntryOutput]
    preferred: PreferredCacheEntriesOutput


class BatchResolveOutput(ErrorPayloadOutput, total=False):
    results: list[ResolvePaperOutput]
    aborted: bool
    abort_reason: ErrorPayloadOutput | None


class BatchCheckItemOutput(ErrorPayloadOutput, total=False):
    query: str
    doi: str | None
    title: str | None
    source: str | None
    has_fulltext: bool | None
    content_kind: str | None
    has_abstract: bool | None
    warnings: list[str]
    source_trail: list[str]
    trace: list[TraceEventOutput]
    token_estimate: int | None
    token_estimate_breakdown: TokenEstimateBreakdownOutput | None
    probe_state: str | None
    evidence: list[str]


class BatchCheckOutput(ErrorPayloadOutput, total=False):
    mode: str
    results: list[BatchCheckItemOutput]
    aborted: bool
    abort_reason: ErrorPayloadOutput | None


class ProviderStatusCheckOutput(TypedDict, total=False):
    name: str
    status: str
    message: str
    missing_env: list[str]
    details: dict[str, object]


class ProviderStatusItemOutput(TypedDict, total=False):
    provider: str
    status: str
    available: bool
    official_provider: bool
    missing_env: list[str]
    notes: list[str]
    checks: list[ProviderStatusCheckOutput]


class ProviderStatusOutput(ErrorPayloadOutput, total=False):
    providers: list[ProviderStatusItemOutput]
