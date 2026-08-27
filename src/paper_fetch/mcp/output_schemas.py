"""Typed MCP tool output schemas used for MCPServer structured output."""

from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


def compact_tool_output_schema(
    schema: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Remove presentation-only metadata from a tool output JSON Schema.

    Pydantic emits a title and a ``default: null`` annotation for nearly every
    optional TypedDict field. Neither affects JSON Schema validation: field
    optionality is controlled by ``required``, and titles are display metadata.
    MCP hosts receive every tool schema in ``tools/list``, so retaining those
    repeated annotations consumes substantial context without strengthening the
    structured-output contract.
    """

    named_schema_maps = frozenset(
        {
            "$defs",
            "definitions",
            "dependentSchemas",
            "mapping",
            "patternProperties",
            "properties",
        }
    )

    def compact(value: Any, *, named_children: bool = False) -> Any:
        if isinstance(value, dict):
            return {
                key: compact(child, named_children=key in named_schema_maps)
                for key, child in value.items()
                if named_children
                or (key != "title" and not (key == "default" and child is None))
            }
        if isinstance(value, list):
            return [compact(child) for child in value]
        return value

    return compact(schema)


class ResolvedCandidateOutput(TypedDict, total=False):
    doi: str | None
    title: str | None
    authors: list[str]
    journal_title: str | None
    published: str | None
    landing_page_url: str | None
    provider_hint: str | None
    score: float
    title_score: float
    author_score: float
    year_score: float


class ErrorPayloadOutput(TypedDict, total=False):
    schema_version: int
    status: str
    reason: str
    code: str | None
    http_status: int | None
    error_category: str | None
    retry_after_seconds: int | None
    provider: str | None
    route: str | None
    stage: str | None
    retryable: bool | None
    details: dict[str, Any]
    trace: list[TraceEventOutput]
    warnings: list[str]
    source_trail: list[str]
    candidates: list[ResolvedCandidateOutput] | None
    missing_env: list[str] | None


class ResolvePaperOutput(ErrorPayloadOutput, total=False):
    index: int
    query: str
    error: dict[str, Any] | None
    provider_lane: str
    query_kind: str
    doi: str | None
    landing_url: str | None
    provider_hint: str | None
    confidence: float
    title: str | None


class HasFulltextOutput(ErrorPayloadOutput, total=False):
    query: str
    doi: str | None
    state: str
    evidence: list[str]


class MetadataOutput(TypedDict, total=False):
    title: str | None
    authors: list[str]
    abstract: str | None
    journal: str | None
    article_type: str | None
    published: str | None
    keywords: list[str]
    license_urls: list[str]
    landing_page_url: str | None


class AcquisitionProvenanceOutput(TypedDict, total=False):
    provider: str
    route: str
    representation: str
    transport: str
    fallback_used: bool


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
    source_url: str | None
    source_path: str | None
    source_href: str | None
    content_type: str | None
    downloaded_bytes: int | None
    width: int | None
    height: int | None
    preview_accepted: bool
    provenance: list[str]
    asset_timing: dict[str, Any]


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
    provider: str | None
    route: str | None
    span_id: str | None
    attempt_id: str | None
    parent_span_id: str | None
    attempt: int | None
    http_status: int | None
    error_category: str | None
    retryable: bool | None
    retry_after_seconds: int | None
    target: str | None
    target_sha256: str | None
    started_at: float | None
    finished_at: float | None
    duration_ms: float | None


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
    asset_timing: dict[str, Any]


class AssetDiagnosticOutput(TypedDict, total=False):
    request_profile: str
    kind: str
    status: str
    download_tier: str | None
    path: str | None
    real_mime: str | None
    byte_count: int | None
    width: int | None
    height: int | None
    preview_accepted: bool
    sha256: str | None
    failure_code: str | None
    provenance: list[str]
    suspected_reasons: list[str]


class AssetKindSummaryOutput(TypedDict, total=False):
    total: int
    requested: int
    full_size: int
    preview: int
    accepted_preview: int
    fallback_preview: int
    failed: int
    placeholder_suspected: int
    not_requested: int
    not_archived: int


class AssetByKindOutput(TypedDict, total=False):
    figure: AssetKindSummaryOutput
    formula: AssetKindSummaryOutput
    table: AssetKindSummaryOutput
    supplement: AssetKindSummaryOutput
    decoration: AssetKindSummaryOutput


class AssetQualitySummaryOutput(TypedDict, total=False):
    audited: bool
    requested: bool
    profile: str
    total: int
    local: int
    full_size: int
    preview: int
    accepted_preview: int
    fallback_preview: int
    failed: int
    placeholder_suspected: int
    not_requested: int
    not_archived: int
    remote_link_count: int
    remote_only_count: int
    failure_codes: list[str]
    issue_codes: list[str]
    by_kind: AssetByKindOutput
    diagnostics: list[AssetDiagnosticOutput]


class QualityOutput(TypedDict, total=False):
    has_fulltext: bool
    content_kind: str
    has_abstract: bool
    token_estimate: int
    token_estimate_breakdown: TokenEstimateBreakdownOutput
    warnings: list[str]
    source_trail: list[str]
    confidence: str
    flags: list[str]
    body_metrics: BodyMetricsOutput
    semantic_losses: SemanticLossesOutput
    asset_failures: list[AssetFailureOutput]
    asset_summary: AssetQualitySummaryOutput
    extraction_revision: int


class ArticleOutput(TypedDict, total=False):
    doi: str | None
    source: str
    acquisition: AcquisitionProvenanceOutput | None
    metadata: MetadataOutput
    sections: list[SectionOutput]
    references: list[ReferenceOutput]
    assets: list[AssetOutput]
    quality: QualityOutput


class FetchAcceptanceSummaryOutput(TypedDict, total=False):
    overall: str
    identity: str
    fetch: str
    content: str
    asset: str
    output: str
    provenance: str
    acquisition: AcquisitionProvenanceOutput | None
    has_fulltext: bool
    has_abstract: bool
    token_estimate: int
    asset_summary: dict[str, Any]


class FetchPaperOutput(ErrorPayloadOutput, total=False):
    doi: str | None
    source: str
    acquisition: AcquisitionProvenanceOutput | None
    has_fulltext: bool
    content_kind: str
    has_abstract: bool
    token_estimate: int
    token_estimate_breakdown: TokenEstimateBreakdownOutput
    quality: QualityOutput
    article: ArticleOutput | None
    markdown: str | None
    metadata: MetadataOutput | None
    saved_markdown_path: str | None
    acceptance: FetchAcceptanceSummaryOutput
    diagnostic_artifacts: list[dict[str, Any]]


class CacheEntryOutput(TypedDict, total=False):
    id: str
    doi: str
    kind: str
    path: str
    mime: str
    size: int
    mtime: float
    identity_proof: str
    source: str | None
    acquisition: AcquisitionProvenanceOutput | None
    has_fulltext: bool | None
    likely_has_fulltext: bool | None
    content_kind: str | None
    completed_at: str | None
    content_sha256: str | None


class PreferredCacheEntriesOutput(TypedDict, total=False):
    markdown: CacheEntryOutput | None
    primary_payload: CacheEntryOutput | None
    assets: list[CacheEntryOutput]


class CacheEntrySummaryOutput(TypedDict, total=False):
    total: int
    by_kind: dict[str, int]


class CacheAcceptanceSummaryOutput(TypedDict, total=False):
    status: str
    overall: str | None
    identity: str
    fetch: str
    content: str
    asset: str
    output: str
    provenance: str
    acquisition: AcquisitionProvenanceOutput | None
    reason_code: str | None


class CacheAssetSummaryOutput(TypedDict, total=False):
    status: str
    requested: bool
    profile: str
    audited: bool
    expected: int | None
    discovered: int
    attempted: int
    total: int
    local: int
    full_size: int
    preview: int
    accepted_preview: int
    fallback_preview: int
    failed: int
    placeholder_suspected: int
    not_archived: int
    remote_link_count: int
    remote_only_count: int
    body_discovered: int
    body_attempted: int
    body_local: int
    body_full_size: int
    body_preview: int
    body_failed: int
    body_not_archived: int
    body_remote_only_count: int
    require_local_body_assets: bool
    require_full_size_body_assets: bool
    has_local_body_assets: bool
    all_body_assets_local: bool
    all_body_assets_full_size: bool
    local_body_assets_satisfied: bool
    full_size_body_assets_satisfied: bool
    failure_codes: list[str]
    issue_codes: list[str]
    remote_links_preserved: bool


class CacheWarningSummaryOutput(TypedDict, total=False):
    messages: list[str]
    fallback_codes: list[str]
    warning_codes: list[str]
    failure_codes: list[str]
    unstructured_warning_count: int


class CacheSidecarOutput(TypedDict, total=False):
    status: str
    reason_code: str
    reason: str
    path: str | None
    version: int | str | None
    expected_version: int
    extraction_revision: int | str | None
    expected_extraction_revision: int
    cached_request: dict[str, Any] | None
    cached_request_fingerprint: str | None
    requested_request: dict[str, Any]
    requested_request_fingerprint: str
    request_matches: bool
    payload_satisfies_request: bool
    request_satisfied: bool
    request_status: str


class ListCachedOutput(ErrorPayloadOutput, total=False):
    download_dir: str | None
    entries: list[CacheEntryOutput]
    cache_mode: str
    index_status: str
    index_version: int | str | None
    expected_index_version: int | None
    index_reason: str | None


class GetCachedOutput(ErrorPayloadOutput, total=False):
    doi: str
    download_dir: str | None
    entries: list[CacheEntryOutput]
    preferred: PreferredCacheEntriesOutput
    cache_mode: str
    index_status: str
    index_version: int | str | None
    expected_index_version: int | None
    index_reason: str | None
    detail: str
    preferred_only: bool
    scope_status: str
    identity_status: str
    has_entries: bool
    entry_summary: CacheEntrySummaryOutput
    content_kind: str | None
    has_fulltext: bool | None
    confidence: str | None
    acquisition: AcquisitionProvenanceOutput | None
    acceptance: CacheAcceptanceSummaryOutput
    asset_summary: CacheAssetSummaryOutput
    warning_summary: CacheWarningSummaryOutput
    sidecar: CacheSidecarOutput
    cached_request: dict[str, Any] | None
    cached_request_fingerprint: str | None
    requested_request: dict[str, Any]
    requested_request_fingerprint: str
    request_status: str
    request_satisfied: bool


class BatchTerminalProgressOutput(TypedDict):
    total: int
    terminal: int
    completed: int
    not_scheduled: int


class BatchResolveOutput(ErrorPayloadOutput, total=False):
    results: list[ResolvePaperOutput]
    aborted: bool
    abort_reason: ErrorPayloadOutput | None
    progress: BatchTerminalProgressOutput


class BatchCheckItemOutput(ErrorPayloadOutput, total=False):
    index: int
    query: str
    error: dict[str, Any] | None
    provider_lane: str
    doi: str | None
    title: str | None
    source: str | None
    acquisition: AcquisitionProvenanceOutput | None
    has_fulltext: bool | None
    content_kind: str | None
    has_abstract: bool | None
    token_estimate: int | None
    token_estimate_breakdown: TokenEstimateBreakdownOutput | None
    probe_state: str | None
    evidence: list[str]


class BatchCheckOutput(ErrorPayloadOutput, total=False):
    mode: str
    results: list[BatchCheckItemOutput]
    aborted: bool
    abort_reason: ErrorPayloadOutput | None
    progress: BatchTerminalProgressOutput


class BatchFetchArtifactOutput(TypedDict, total=False):
    path: str
    kind: str
    route: str | None
    failure_code: str | None
    size: int | None
    sha256: str | None
    completed_at: str
    verification_status: str
    resource_uri: str | None


class BatchFetchItemOutput(TypedDict, total=False):
    index: int
    query: str
    attempt: int
    completion_sequence: int | None
    started_at: str
    completed_at: str
    record_status: str
    status: str
    run_id: str
    record_id: str
    request_fingerprint: str
    doi: str | None
    source: str | None
    acquisition: AcquisitionProvenanceOutput | None
    reused: bool
    cache_hit: bool
    acceptance: FetchAcceptanceSummaryOutput
    fallback_codes: list[str]
    warning_codes: list[str]
    failure_codes: list[str]
    warnings: list[str]
    error: ErrorPayloadOutput | None
    output_artifacts: list[BatchFetchArtifactOutput]
    saved_markdown_path: str | None
    resource_uri: str | None
    content: str | None
    content_available_chars: int | None
    content_returned_chars: int
    content_truncated: bool


class BatchFetchCompletionOutput(TypedDict, total=False):
    sequence: int
    index: int
    attempt: int
    status: str
    completed_at: str


class BatchFetchLaneCooldownOutput(TypedDict, total=False):
    lane: str
    reason_code: str
    source_index: int
    retry_after_seconds: float | None
    cooldown_seconds: float


class BatchFetchSummaryOutput(TypedDict, total=False):
    record_statuses: dict[str, int]
    acceptance: dict[str, int]
    cache_hits: int
    saved_markdown: int


class BatchFetchOutput(ErrorPayloadOutput, total=False):
    run_id: str
    request_fingerprint: str
    semantic_fingerprint: str
    execution_policy: dict[str, Any]
    state: str
    persisted: bool
    run_manifest_path: str | None
    events_path: str | None
    query_count: int
    attempted_count: int
    execution_count: int
    deduplicated_count: int
    not_scheduled_count: int
    reused_count: int
    detail: str
    content_max_chars: int
    content_returned_chars: int
    results: list[BatchFetchItemOutput]
    completion_order: list[BatchFetchCompletionOutput]
    summary: BatchFetchSummaryOutput
    lane_cooldowns: list[BatchFetchLaneCooldownOutput]
    aborted: bool
    cancelled: bool


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
    reason_code: str
    reason: str
    suggested_action: str
    diagnostic_scope: str
    live_checked: bool


class ConfigurationSourceValueOutput(TypedDict, total=False):
    name: str
    source: str
    present: bool
    uses_default: bool
    sensitive: bool


class ConfigurationSourceLayerOutput(TypedDict, total=False):
    source: str
    present: bool


class ConfigurationSourcesOutput(TypedDict, total=False):
    precedence: list[str]
    layers: list[ConfigurationSourceLayerOutput]
    values: list[ConfigurationSourceValueOutput]


class ProviderStatusOutput(ErrorPayloadOutput, total=False):
    diagnostic_scope: str
    live_network_checked: bool
    remote_publisher_health: str
    detail: str
    provider_filter: str | None
    group_filter: str | None
    providers: list[ProviderStatusItemOutput]
    configuration: ConfigurationSourcesOutput
    local_capabilities: dict[str, Any]


class BrowserPreflightStorageStateOutput(TypedDict, total=False):
    path: str | None
    save_requested: bool
    attempted: bool
    saved: bool
    reason: str | None


class BrowserPreflightItemOutput(TypedDict, total=False):
    provider: str
    provider_label: str
    status: str
    ready: bool
    reason_code: str
    stage: str | None
    message: str | None
    next_action: str
    target_url: str | None
    final_url: str | None
    title: str | None
    storage_state: BrowserPreflightStorageStateOutput
    diagnostics: dict[str, Any]


class BrowserPreflightSummaryOutput(TypedDict, total=False):
    requested: int
    completed: int
    ready: int
    challenge: int
    auth_required: int
    network_timeout: int
    extraction_error: int
    runtime_error: int
    cancelled: int


class BrowserPreflightOutput(ErrorPayloadOutput, total=False):
    diagnostic_scope: str
    provider_filter: str | None
    detail: str
    network_access: str
    storage_state_write_enabled: bool
    pdf_fallback_attempted: bool
    auth_attempted: bool
    results: list[BrowserPreflightItemOutput]
    summary: BrowserPreflightSummaryOutput
