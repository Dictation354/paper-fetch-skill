"""Pure, versioned acceptance evaluation for fetch results."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..models import (
    QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION,
    Asset,
    AssetProfile,
    FetchEnvelope,
    Quality,
    SemanticLosses,
)
from ..publisher_identity import normalize_doi
from ..reason_codes import (
    ABSTRACT_ONLY,
    ERROR,
    METADATA_ONLY,
    NOT_CONFIGURED,
    NO_ACCESS,
    PDF_FALLBACK,
    RATE_LIMITED,
)
from ..tracing import TraceEvent, merge_trace
from ..utils import normalize_text

FETCH_ACCEPTANCE_SCHEMA_VERSION = 1
FETCH_ACCEPTANCE_MIN_READER_VERSION = 1


class OverallAcceptanceStatus(StrEnum):
    """Stable top-level acceptance outcomes."""

    COMPLETE = "complete"
    DEGRADED = "degraded"
    LIMITED = "limited"
    FAILED = "failed"
    ACTION_REQUIRED = "action_required"


class IdentityAcceptanceStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    MISMATCH = "mismatch"
    UNAVAILABLE = "unavailable"


class FetchAcceptanceStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"
    ACTION_REQUIRED = "action_required"


class ContentAcceptanceStatus(StrEnum):
    FULLTEXT = "fulltext"
    ABSTRACT_ONLY = "abstract_only"
    METADATA_ONLY = "metadata_only"
    UNAVAILABLE = "unavailable"


class AssetAcceptanceStatus(StrEnum):
    COMPLETE = "complete"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"
    NOT_REQUESTED = "not_requested"


class OutputAcceptanceStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"
    NOT_REQUESTED = "not_requested"


class ProvenanceAcceptanceStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class AcceptanceOutputKind(StrEnum):
    ARTICLE = "article"
    MARKDOWN = "markdown"
    METADATA = "metadata"


AcceptanceAssetProfile = Literal["none", "body", "all", "unknown"]


class _AcceptanceModel(BaseModel):
    # Schema-version-compatible readers ignore additive fields they do not know.
    model_config = ConfigDict(extra="ignore", frozen=True, from_attributes=True)


class IdentityAcceptanceFacet(_AcceptanceModel):
    status: IdentityAcceptanceStatus
    doi: str | None = None
    expected_doi: str | None = None
    title: str | None = None
    candidate_count: int = Field(default=0, ge=0)
    codes: tuple[str, ...] = ()


class FetchAcceptanceFacet(_AcceptanceModel):
    status: FetchAcceptanceStatus
    completed: bool
    code: str | None = None


class TableAcceptanceFacet(_AcceptanceModel):
    fallback_count: int = Field(default=0, ge=0)
    layout_degraded_count: int = Field(default=0, ge=0)
    semantic_loss_count: int = Field(default=0, ge=0)
    legacy_lossy_count: int = Field(default=0, ge=0)


class FormulaAcceptanceFacet(_AcceptanceModel):
    fallback_count: int = Field(default=0, ge=0)
    missing_count: int = Field(default=0, ge=0)


class ContentAcceptanceFacet(_AcceptanceModel):
    status: ContentAcceptanceStatus
    has_fulltext: bool
    has_abstract: bool
    token_estimate: int = Field(default=0, ge=0)
    confidence: str | None = None
    flags: tuple[str, ...] = ()
    tables: TableAcceptanceFacet = Field(default_factory=TableAcceptanceFacet)
    formulas: FormulaAcceptanceFacet = Field(default_factory=FormulaAcceptanceFacet)

    @model_validator(mode="after")
    def validate_content_status(self) -> ContentAcceptanceFacet:
        if self.has_fulltext != (self.status == ContentAcceptanceStatus.FULLTEXT):
            raise ValueError("has_fulltext must match content status")
        if (
            self.status == ContentAcceptanceStatus.ABSTRACT_ONLY
            and not self.has_abstract
        ):
            raise ValueError("abstract_only content must have an abstract")
        if self.status == ContentAcceptanceStatus.UNAVAILABLE and (
            self.has_fulltext or self.has_abstract
        ):
            raise ValueError("unavailable content cannot contain accepted text")
        return self


class AssetAcceptanceSummary(_AcceptanceModel):
    """Structured asset facts accepted by the evaluator and future asset audits."""

    requested: bool
    profile: AcceptanceAssetProfile = "unknown"
    total: int = Field(default=0, ge=0)
    local: int = Field(default=0, ge=0)
    full_size: int = Field(default=0, ge=0)
    preview: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    placeholder_suspected: int = Field(default=0, ge=0)
    not_archived: int = Field(default=0, ge=0)
    remote_link_count: int = Field(default=0, ge=0)
    remote_only_count: int = Field(default=0, ge=0)
    failure_codes: tuple[str, ...] = ()


class AssetAcceptanceFacet(AssetAcceptanceSummary):
    status: AssetAcceptanceStatus
    remote_links_preserved: bool

    @model_validator(mode="after")
    def validate_request_status(self) -> AssetAcceptanceFacet:
        if not self.requested and self.status != AssetAcceptanceStatus.NOT_REQUESTED:
            raise ValueError("unrequested assets must use not_requested status")
        if self.requested and self.status == AssetAcceptanceStatus.NOT_REQUESTED:
            raise ValueError("requested assets cannot use not_requested status")
        if self.profile == "none" and self.requested:
            raise ValueError("asset profile none cannot be requested")
        return self


class OutputAcceptanceFacet(_AcceptanceModel):
    status: OutputAcceptanceStatus
    requested: tuple[AcceptanceOutputKind, ...] = ()
    available: tuple[AcceptanceOutputKind, ...] = ()
    missing: tuple[AcceptanceOutputKind, ...] = ()


class ProvenanceAcceptanceFacet(_AcceptanceModel):
    status: ProvenanceAcceptanceStatus
    source: str | None = None
    trace_event_count: int = Field(default=0, ge=0)
    fallback_codes: tuple[str, ...] = ()
    warning_codes: tuple[str, ...] = ()
    failure_codes: tuple[str, ...] = ()
    unstructured_warning_count: int = Field(default=0, ge=0)


class FetchAcceptanceReport(_AcceptanceModel):
    """Canonical acceptance report shared by all external adapters."""

    schema_version: Literal[1]
    minimum_reader_schema_version: Literal[1]
    overall: OverallAcceptanceStatus
    identity: IdentityAcceptanceFacet
    fetch: FetchAcceptanceFacet
    content: ContentAcceptanceFacet
    asset: AssetAcceptanceFacet
    output: OutputAcceptanceFacet
    provenance: ProvenanceAcceptanceFacet

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)


_ACTION_REQUIRED_CODES = frozenset(
    {"ambiguous", NO_ACCESS, NOT_CONFIGURED, RATE_LIMITED}
)
_TRACE_FAILURE_OUTCOMES = frozenset({"fail", "unavailable", "not_usable"})
_TRACE_WARNING_OUTCOMES = frozenset(
    {"partial", "unavailable", "not_usable", "abstract_only"}
)
_TRACE_FALLBACK_CODES = frozenset({ABSTRACT_ONLY, METADATA_ONLY, PDF_FALLBACK})
_NON_DEGRADING_QUALITY_FLAGS = frozenset({QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION})
_REMOTE_PREFIXES = ("http://", "https://", "//")
_REMOTE_ASSET_FIELDS = (
    "url",
    "download_url",
    "original_url",
    "source_url",
    "source_href",
)


def _normalized_codes(values: Sequence[str | None]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {normalized for value in values if (normalized := normalize_text(value))}
        )
    )


def _trace_fact_code(event: TraceEvent) -> str:
    code = normalize_text(event.code).lower()
    if code:
        return code
    return ":".join(
        (
            normalize_text(event.stage).lower() or "trace",
            normalize_text(event.component).lower() or "unknown",
            normalize_text(event.outcome).lower() or "info",
        )
    )


def _quality_for(envelope: FetchEnvelope | None) -> Quality:
    if envelope is None:
        return Quality()
    return envelope.quality


def _trace_for(envelope: FetchEnvelope | None, quality: Quality) -> list[TraceEvent]:
    if envelope is None:
        return []
    article_trace = (
        envelope.article.quality.trace if envelope.article is not None else []
    )
    return merge_trace(envelope.trace, quality.trace, article_trace)


def _title_for(
    envelope: FetchEnvelope | None, explicit_title: str | None
) -> str | None:
    title = normalize_text(explicit_title)
    if title:
        return title
    if envelope is None:
        return None
    metadata = (
        envelope.article.metadata if envelope.article is not None else envelope.metadata
    )
    return normalize_text(metadata.title if metadata is not None else None) or None


def _identity_facet(
    envelope: FetchEnvelope | None,
    *,
    identity_status: IdentityAcceptanceStatus | None,
    failure_code: str | None,
    candidate_count: int,
    doi: str | None,
    expected_doi: str | None,
    title: str | None,
) -> IdentityAcceptanceFacet:
    raw_doi = normalize_text(doi or (envelope.doi if envelope is not None else None))
    resolved_doi = normalize_doi(raw_doi) or raw_doi
    normalized_expected_doi = normalize_doi(expected_doi) or normalize_text(
        expected_doi
    )
    resolved_title = _title_for(envelope, title)
    if identity_status is None:
        if failure_code == "ambiguous":
            status = IdentityAcceptanceStatus.AMBIGUOUS
        elif normalized_expected_doi and resolved_doi != normalized_expected_doi:
            status = IdentityAcceptanceStatus.MISMATCH
        elif resolved_doi or (envelope is not None and resolved_title):
            status = IdentityAcceptanceStatus.RESOLVED
        else:
            status = IdentityAcceptanceStatus.UNAVAILABLE
    else:
        status = identity_status
    identity_code: str | None = None
    if status == IdentityAcceptanceStatus.MISMATCH:
        identity_code = "identity_mismatch"
    elif status != IdentityAcceptanceStatus.RESOLVED:
        identity_code = failure_code
    codes = _normalized_codes([identity_code])
    return IdentityAcceptanceFacet(
        status=status,
        doi=resolved_doi or None,
        expected_doi=normalized_expected_doi or None,
        title=resolved_title,
        candidate_count=candidate_count,
        codes=codes,
    )


def _fetch_facet(
    envelope: FetchEnvelope | None, failure_code: str | None
) -> FetchAcceptanceFacet:
    if envelope is not None:
        return FetchAcceptanceFacet(
            status=FetchAcceptanceStatus.OK,
            completed=True,
            code=None,
        )
    code = normalize_text(failure_code).lower() or ERROR
    status = (
        FetchAcceptanceStatus.ACTION_REQUIRED
        if code in _ACTION_REQUIRED_CODES
        else FetchAcceptanceStatus.FAILED
    )
    return FetchAcceptanceFacet(status=status, completed=False, code=code)


def _content_facet(
    envelope: FetchEnvelope | None, quality: Quality
) -> ContentAcceptanceFacet:
    if envelope is None:
        status = ContentAcceptanceStatus.UNAVAILABLE
        has_abstract = False
    else:
        status = ContentAcceptanceStatus(envelope.content_kind)
        has_abstract = bool(envelope.has_abstract)
    losses: SemanticLosses = quality.semantic_losses
    return ContentAcceptanceFacet(
        status=status,
        has_fulltext=status == ContentAcceptanceStatus.FULLTEXT,
        has_abstract=has_abstract,
        token_estimate=max(int(quality.token_estimate or 0), 0),
        confidence=(
            normalize_text(quality.confidence) or None if envelope is not None else None
        ),
        flags=_normalized_codes(quality.flags),
        tables=TableAcceptanceFacet(
            fallback_count=max(int(losses.table_fallback_count or 0), 0),
            layout_degraded_count=max(int(losses.table_layout_degraded_count or 0), 0),
            semantic_loss_count=max(int(losses.table_semantic_loss_count or 0), 0),
            legacy_lossy_count=max(int(losses.table_lossy_count or 0), 0),
        ),
        formulas=FormulaAcceptanceFacet(
            fallback_count=max(int(losses.formula_fallback_count or 0), 0),
            missing_count=max(int(losses.formula_missing_count or 0), 0),
        ),
    )


def _is_remote(value: str | None) -> bool:
    return normalize_text(value).lower().startswith(_REMOTE_PREFIXES)


def _asset_remote_counts(asset: Asset) -> tuple[int, int]:
    has_remote = any(
        _is_remote(getattr(asset, field, None)) for field in _REMOTE_ASSET_FIELDS
    )
    if not has_remote:
        return 0, 0
    return 1, int(not normalize_text(asset.path))


def _asset_failure_code(failure: Mapping[str, Any]) -> str | None:
    for key in ("code", "error_category", "reason"):
        code = normalize_text(failure.get(key)).lower()
        if code:
            return code
    return None


def _audited_asset_summary(
    quality: Quality, *, profile: AcceptanceAssetProfile
) -> AssetAcceptanceSummary | None:
    summary = getattr(quality, "asset_summary", None)
    if summary is None:
        return None
    audited = (
        bool(summary.get("audited"))
        if isinstance(summary, Mapping)
        else bool(getattr(summary, "audited", False))
    )
    summary_profile = normalize_text(
        summary.get("profile")
        if isinstance(summary, Mapping)
        else getattr(summary, "profile", "")
    ).lower()
    if not audited or summary_profile != profile:
        return None

    def value(field: str, default: Any = 0) -> Any:
        if isinstance(summary, Mapping):
            return summary.get(field, default)
        return getattr(summary, field, default)

    return AssetAcceptanceSummary(
        requested=bool(value("requested", profile != "none")),
        profile=profile,
        total=max(int(value("total") or 0), 0),
        local=max(int(value("local") or 0), 0),
        full_size=max(int(value("full_size") or 0), 0),
        preview=max(int(value("preview") or 0), 0),
        failed=max(int(value("failed") or 0), 0),
        placeholder_suspected=max(int(value("placeholder_suspected") or 0), 0),
        not_archived=max(int(value("not_archived") or 0), 0),
        remote_link_count=max(int(value("remote_link_count") or 0), 0),
        remote_only_count=max(int(value("remote_only_count") or 0), 0),
        failure_codes=_normalized_codes(value("failure_codes", ())),
    )


def _asset_summary_from_envelope(
    envelope: FetchEnvelope | None,
    *,
    profile: AcceptanceAssetProfile,
    quality: Quality,
) -> AssetAcceptanceSummary:
    if audited_summary := _audited_asset_summary(quality, profile=profile):
        return audited_summary
    assets = list(envelope.article.assets) if envelope and envelope.article else []
    requested = profile != "none"
    remote_counts = [_asset_remote_counts(asset) for asset in assets]
    remote_link_count = sum(item[0] for item in remote_counts)
    remote_only_count = sum(item[1] for item in remote_counts)
    local = sum(bool(normalize_text(asset.path)) for asset in assets)
    preview = (
        sum(
            normalize_text(asset.download_tier).lower() == "preview" for asset in assets
        )
        if requested
        else 0
    )
    failures = list(quality.asset_failures) if requested else []
    not_archived = remote_only_count if requested else 0
    return AssetAcceptanceSummary(
        requested=requested,
        profile=profile,
        total=len(assets),
        local=local,
        full_size=max(local - preview, 0),
        preview=preview,
        failed=len(failures),
        not_archived=not_archived,
        remote_link_count=remote_link_count,
        remote_only_count=remote_only_count,
        failure_codes=_normalized_codes(
            [_asset_failure_code(failure) for failure in failures]
        ),
    )


def _asset_facet(
    summary: AssetAcceptanceSummary, *, fetch_completed: bool
) -> AssetAcceptanceFacet:
    if not summary.requested:
        status = AssetAcceptanceStatus.NOT_REQUESTED
    elif not fetch_completed:
        status = AssetAcceptanceStatus.UNAVAILABLE
    elif summary.failed and summary.local == 0:
        status = AssetAcceptanceStatus.FAILED
    elif any(
        (
            summary.failed,
            summary.preview,
            summary.placeholder_suspected,
            summary.not_archived,
        )
    ):
        status = AssetAcceptanceStatus.DEGRADED
    else:
        status = AssetAcceptanceStatus.COMPLETE
    return AssetAcceptanceFacet(
        **summary.model_dump(),
        status=status,
        remote_links_preserved=summary.remote_only_count > 0,
    )


def _requested_output_kinds(
    envelope: FetchEnvelope | None,
    requested_outputs: Collection[AcceptanceOutputKind | str] | None,
) -> tuple[AcceptanceOutputKind, ...]:
    if requested_outputs is not None:
        return tuple(
            sorted(
                {AcceptanceOutputKind(value) for value in requested_outputs},
                key=lambda value: value.value,
            )
        )
    if envelope is None:
        return ()
    inferred: list[AcceptanceOutputKind] = []
    if envelope.article is not None:
        inferred.append(AcceptanceOutputKind.ARTICLE)
    if normalize_text(envelope.markdown):
        inferred.append(AcceptanceOutputKind.MARKDOWN)
    if envelope.metadata is not None:
        inferred.append(AcceptanceOutputKind.METADATA)
    return tuple(inferred)


def _output_facet(
    envelope: FetchEnvelope | None,
    requested_outputs: Collection[AcceptanceOutputKind | str] | None,
) -> OutputAcceptanceFacet:
    requested = _requested_output_kinds(envelope, requested_outputs)
    available_set: set[AcceptanceOutputKind] = set()
    if envelope is not None:
        if envelope.article is not None:
            available_set.add(AcceptanceOutputKind.ARTICLE)
        if normalize_text(envelope.markdown):
            available_set.add(AcceptanceOutputKind.MARKDOWN)
        if envelope.metadata is not None:
            available_set.add(AcceptanceOutputKind.METADATA)
    available = tuple(item for item in requested if item in available_set)
    missing = tuple(item for item in requested if item not in available_set)
    if not requested:
        status = OutputAcceptanceStatus.NOT_REQUESTED
    elif not missing:
        status = OutputAcceptanceStatus.COMPLETE
    elif available:
        status = OutputAcceptanceStatus.PARTIAL
    else:
        status = OutputAcceptanceStatus.MISSING
    return OutputAcceptanceFacet(
        status=status,
        requested=requested,
        available=available,
        missing=missing,
    )


def _structured_warning_codes(
    quality: Quality, asset: AssetAcceptanceFacet
) -> list[str | None]:
    losses = quality.semantic_losses
    codes: list[str | None] = [
        flag
        for flag in quality.flags
        if normalize_text(flag).lower() not in _NON_DEGRADING_QUALITY_FLAGS
    ]
    if losses.table_fallback_count:
        codes.append("table_fallback")
    if losses.table_layout_degraded_count:
        codes.append("table_layout_degraded")
    if losses.table_semantic_loss_count or losses.table_lossy_count:
        codes.append("table_semantic_loss")
    if losses.formula_fallback_count:
        codes.append("formula_fallback")
    if losses.formula_missing_count:
        codes.append("formula_missing")
    if asset.requested:
        codes.extend(asset.failure_codes)
        if asset.preview:
            codes.append("asset_preview")
        if asset.placeholder_suspected:
            codes.append("asset_placeholder_suspected")
        if asset.not_archived:
            codes.append("asset_not_archived")
    return codes


def _provenance_facet(
    *,
    source: str | None,
    trace: Sequence[TraceEvent],
    quality: Quality,
    asset: AssetAcceptanceFacet,
    content: ContentAcceptanceFacet,
    failure_code: str | None,
) -> ProvenanceAcceptanceFacet:
    normalized_source = normalize_text(source) or None
    if normalized_source and trace:
        status = ProvenanceAcceptanceStatus.COMPLETE
    elif normalized_source or trace:
        status = ProvenanceAcceptanceStatus.PARTIAL
    else:
        status = ProvenanceAcceptanceStatus.MISSING

    trace_failures = [
        event
        for event in trace
        if normalize_text(event.outcome).lower() in _TRACE_FAILURE_OUTCOMES
    ]
    fallback_events = [
        event
        for event in trace
        if normalize_text(event.stage).lower() == "fallback"
        or normalize_text(event.code).lower() in _TRACE_FALLBACK_CODES
        or (
            content.status != ContentAcceptanceStatus.UNAVAILABLE
            and normalize_text(event.stage).lower() == "fulltext"
            and normalize_text(event.outcome).lower() in _TRACE_FAILURE_OUTCOMES
        )
    ]
    trace_warnings = [
        event
        for event in trace
        if normalize_text(event.outcome).lower() in _TRACE_WARNING_OUTCOMES
    ]
    return ProvenanceAcceptanceFacet(
        status=status,
        source=normalized_source,
        trace_event_count=len(trace),
        fallback_codes=_normalized_codes(
            [_trace_fact_code(event) for event in fallback_events]
        ),
        warning_codes=_normalized_codes(
            [
                *_structured_warning_codes(quality, asset),
                *[_trace_fact_code(event) for event in trace_warnings],
            ]
        ),
        failure_codes=_normalized_codes(
            [
                failure_code,
                *(asset.failure_codes if asset.requested else ()),
                *[_trace_fact_code(event) for event in trace_failures],
            ]
        ),
        # Kept only for visibility; warning message text is never classified.
        unstructured_warning_count=len(quality.warnings),
    )


def _overall_status(
    *,
    identity: IdentityAcceptanceFacet,
    fetch: FetchAcceptanceFacet,
    content: ContentAcceptanceFacet,
    asset: AssetAcceptanceFacet,
    output: OutputAcceptanceFacet,
    provenance: ProvenanceAcceptanceFacet,
) -> OverallAcceptanceStatus:
    if fetch.status == FetchAcceptanceStatus.ACTION_REQUIRED:
        return OverallAcceptanceStatus.ACTION_REQUIRED
    if fetch.status == FetchAcceptanceStatus.FAILED:
        return OverallAcceptanceStatus.FAILED
    if identity.status in {
        IdentityAcceptanceStatus.AMBIGUOUS,
        IdentityAcceptanceStatus.MISMATCH,
        IdentityAcceptanceStatus.UNAVAILABLE,
    }:
        return OverallAcceptanceStatus.ACTION_REQUIRED
    if content.status == ContentAcceptanceStatus.UNAVAILABLE or output.status in {
        OutputAcceptanceStatus.PARTIAL,
        OutputAcceptanceStatus.MISSING,
    }:
        return OverallAcceptanceStatus.FAILED
    if content.status in {
        ContentAcceptanceStatus.ABSTRACT_ONLY,
        ContentAcceptanceStatus.METADATA_ONLY,
    }:
        return OverallAcceptanceStatus.LIMITED
    if (
        asset.status in {AssetAcceptanceStatus.DEGRADED, AssetAcceptanceStatus.FAILED}
        or provenance.status != ProvenanceAcceptanceStatus.COMPLETE
        or provenance.fallback_codes
        or provenance.warning_codes
        or provenance.failure_codes
    ):
        return OverallAcceptanceStatus.DEGRADED
    return OverallAcceptanceStatus.COMPLETE


def evaluate_fetch_acceptance(
    envelope: FetchEnvelope | None,
    *,
    asset_profile: AssetProfile,
    requested_outputs: Collection[AcceptanceOutputKind | str] | None = None,
    asset_summary: AssetAcceptanceSummary | None = None,
    failure_code: str | None = None,
    identity_status: IdentityAcceptanceStatus | None = None,
    candidate_count: int = 0,
    doi: str | None = None,
    expected_doi: str | None = None,
    title: str | None = None,
    source: str | None = None,
) -> FetchAcceptanceReport:
    """Evaluate immutable fetch facts without network, filesystem, or provider work."""

    if candidate_count < 0:
        raise ValueError("candidate_count must not be negative")
    normalized_failure = normalize_text(failure_code).lower() or None
    if envelope is not None and normalized_failure is not None:
        raise ValueError("failure_code cannot be combined with a completed envelope")
    effective_failure = normalized_failure or (ERROR if envelope is None else None)
    quality = _quality_for(envelope)
    trace = _trace_for(envelope, quality)
    resolved_source = (
        normalize_text(source or (envelope.source if envelope is not None else None))
        or None
    )
    resolved_profile: AcceptanceAssetProfile = asset_profile

    if asset_summary is None:
        summary = _asset_summary_from_envelope(
            envelope,
            profile=resolved_profile,
            quality=quality,
        )
    else:
        requested = asset_summary.requested
        if resolved_profile == "none":
            requested = False
        updates: dict[str, Any] = {
            "profile": resolved_profile,
            "requested": requested,
        }
        if not requested:
            updates.update(
                preview=0,
                failed=0,
                placeholder_suspected=0,
                not_archived=0,
                failure_codes=(),
            )
        summary = asset_summary.model_copy(update=updates)

    identity = _identity_facet(
        envelope,
        identity_status=identity_status,
        failure_code=effective_failure,
        candidate_count=candidate_count,
        doi=doi,
        expected_doi=expected_doi,
        title=title,
    )
    fetch = _fetch_facet(envelope, effective_failure)
    content = _content_facet(envelope, quality)
    asset = _asset_facet(summary, fetch_completed=fetch.completed)
    output = _output_facet(envelope, requested_outputs)
    provenance = _provenance_facet(
        source=resolved_source,
        trace=trace,
        quality=quality,
        asset=asset,
        content=content,
        failure_code=effective_failure,
    )
    overall = _overall_status(
        identity=identity,
        fetch=fetch,
        content=content,
        asset=asset,
        output=output,
        provenance=provenance,
    )
    return FetchAcceptanceReport(
        schema_version=FETCH_ACCEPTANCE_SCHEMA_VERSION,
        minimum_reader_schema_version=FETCH_ACCEPTANCE_MIN_READER_VERSION,
        overall=overall,
        identity=identity,
        fetch=fetch,
        content=content,
        asset=asset,
        output=output,
        provenance=provenance,
    )


def parse_fetch_acceptance_report(
    payload: Mapping[str, Any],
) -> FetchAcceptanceReport:
    """Load schema v1; additive unknown fields are ignored by compatibility rule."""

    return FetchAcceptanceReport.model_validate(payload)


def fetch_acceptance_json_schema() -> dict[str, Any]:
    """Return the canonical Draft 2020-12-compatible Pydantic JSON Schema."""

    return FetchAcceptanceReport.model_json_schema()


__all__ = [
    "FETCH_ACCEPTANCE_MIN_READER_VERSION",
    "FETCH_ACCEPTANCE_SCHEMA_VERSION",
    "AcceptanceOutputKind",
    "AssetAcceptanceFacet",
    "AssetAcceptanceStatus",
    "AssetAcceptanceSummary",
    "ContentAcceptanceFacet",
    "ContentAcceptanceStatus",
    "FetchAcceptanceFacet",
    "FetchAcceptanceReport",
    "FetchAcceptanceStatus",
    "FormulaAcceptanceFacet",
    "IdentityAcceptanceFacet",
    "IdentityAcceptanceStatus",
    "OutputAcceptanceFacet",
    "OutputAcceptanceStatus",
    "OverallAcceptanceStatus",
    "ProvenanceAcceptanceFacet",
    "ProvenanceAcceptanceStatus",
    "TableAcceptanceFacet",
    "evaluate_fetch_acceptance",
    "fetch_acceptance_json_schema",
    "parse_fetch_acceptance_report",
]
