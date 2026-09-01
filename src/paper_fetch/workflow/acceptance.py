"""Pure, versioned acceptance evaluation for fetch results."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..models import (
    AcquisitionProvenance,
    QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION,
    Asset,
    AssetProfile,
    FetchEnvelope,
    Quality,
    SemanticLosses,
)
from ..publisher_identity import normalize_doi
from ..provider_catalog import (
    acquisition_matches_provider_route,
    compile_route_execution_policy,
    provider_for_source,
)
from ..reason_codes import (
    ABSTRACT_ONLY,
    ERROR,
    METADATA_ONLY,
    NOT_CONFIGURED,
    NO_ACCESS,
    PDF_FALLBACK,
    RATE_LIMITED,
)
from ..tracing import TraceEvent, acquisition_fallback_used
from ..utils import normalize_text

FETCH_ACCEPTANCE_SCHEMA_VERSION = 2
FETCH_ACCEPTANCE_MIN_READER_VERSION = 2


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
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
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
    canonical_landing_url: str | None = None
    canonical_landing_verified: bool = False
    canonical_landing_unique: bool = False
    codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_resolved_identity(self) -> IdentityAcceptanceFacet:
        if self.status != IdentityAcceptanceStatus.RESOLVED:
            return self
        if self.doi:
            return self
        if not (
            self.canonical_landing_url
            and self.canonical_landing_verified
            and self.canonical_landing_unique
        ):
            raise ValueError(
                "DOI-less resolved identity requires one verified unique canonical landing"
            )
        return self


class FetchAcceptanceFacet(_AcceptanceModel):
    status: FetchAcceptanceStatus
    completed: bool
    code: str | None = None


class TableAcceptanceFacet(_AcceptanceModel):
    fallback_count: int = Field(default=0, ge=0)
    layout_degraded_count: int = Field(default=0, ge=0)
    semantic_loss_count: int = Field(default=0, ge=0)


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
    audited: bool = False
    expected: int | None = Field(default=None, ge=0)
    discovered: int = Field(default=0, ge=0)
    attempted: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)
    local: int = Field(default=0, ge=0)
    full_size: int = Field(default=0, ge=0)
    preview: int = Field(default=0, ge=0)
    accepted_preview: int = Field(default=0, ge=0)
    fallback_preview: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    placeholder_suspected: int = Field(default=0, ge=0)
    not_archived: int = Field(default=0, ge=0)
    remote_link_count: int = Field(default=0, ge=0)
    remote_only_count: int = Field(default=0, ge=0)
    body_discovered: int = Field(default=0, ge=0)
    body_attempted: int = Field(default=0, ge=0)
    body_local: int = Field(default=0, ge=0)
    body_full_size: int = Field(default=0, ge=0)
    body_preview: int = Field(default=0, ge=0)
    body_failed: int = Field(default=0, ge=0)
    body_not_archived: int = Field(default=0, ge=0)
    body_remote_only_count: int = Field(default=0, ge=0)
    require_local_body_assets: bool = False
    require_full_size_body_assets: bool = False
    has_local_body_assets: bool = False
    all_body_assets_local: bool = True
    all_body_assets_full_size: bool = True
    local_body_assets_satisfied: bool = True
    full_size_body_assets_satisfied: bool = True
    failure_codes: tuple[str, ...] = ()
    issue_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_preview_counts(self) -> AssetAcceptanceSummary:
        if self.preview != self.accepted_preview + self.fallback_preview:
            raise ValueError("preview must equal accepted_preview + fallback_preview")
        return self


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
        if self.discovered != self.total:
            raise ValueError("discovered must match total")
        if self.attempted > self.discovered:
            raise ValueError("attempted cannot exceed discovered")
        return self


class OutputAcceptanceFacet(_AcceptanceModel):
    status: OutputAcceptanceStatus
    requested: tuple[AcceptanceOutputKind, ...] = ()
    available: tuple[AcceptanceOutputKind, ...] = ()
    missing: tuple[AcceptanceOutputKind, ...] = ()


class ProvenanceAcceptanceFacet(_AcceptanceModel):
    status: ProvenanceAcceptanceStatus
    source: str | None = None
    acquisition: AcquisitionProvenance | None = None
    trace_event_count: int = Field(default=0, ge=0)
    fallback_codes: tuple[str, ...] = ()
    warning_codes: tuple[str, ...] = ()
    failure_codes: tuple[str, ...] = ()
    unstructured_warning_count: int = Field(default=0, ge=0)
    acceptance_policy: str | None = None
    acceptance_policy_satisfied: bool = False


class FetchAcceptanceReport(_AcceptanceModel):
    """Canonical acceptance report shared by all external adapters."""

    schema_version: Literal[2]
    minimum_reader_schema_version: Literal[2]
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
_TRACE_FAILURE_OUTCOMES = frozenset(
    {"fail", "unavailable", "not_usable", RATE_LIMITED, NOT_CONFIGURED}
)
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
_BODY_ASSET_KINDS = frozenset({"figure", "formula", "table"})


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


def _trace_is_failure(event: TraceEvent) -> bool:
    outcome = normalize_text(event.outcome).lower()
    code = normalize_text(event.code).lower()
    return (
        outcome in _TRACE_FAILURE_OUTCOMES
        or code in {RATE_LIMITED, NOT_CONFIGURED}
        or event.http_status == 429
    )


def _quality_for(envelope: FetchEnvelope | None) -> Quality:
    if envelope is None:
        return Quality()
    return envelope.quality


def _trace_for(envelope: FetchEnvelope | None, quality: Quality) -> list[TraceEvent]:
    del quality
    if envelope is None:
        return []
    return list(envelope.trace)


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
    canonical_landing_url: str | None,
    canonical_landing_verified: bool,
    canonical_landing_unique: bool,
) -> IdentityAcceptanceFacet:
    raw_doi = normalize_text(doi or (envelope.doi if envelope is not None else None))
    resolved_doi = normalize_doi(raw_doi) or raw_doi
    normalized_expected_doi = normalize_doi(expected_doi) or normalize_text(
        expected_doi
    )
    resolved_title = _title_for(envelope, title)
    resolved_landing_url = normalize_text(canonical_landing_url) or None
    has_verified_landing_identity = bool(
        resolved_landing_url and canonical_landing_verified and canonical_landing_unique
    )
    if identity_status is None:
        if failure_code == "ambiguous":
            status = IdentityAcceptanceStatus.AMBIGUOUS
        elif normalized_expected_doi and resolved_doi != normalized_expected_doi:
            status = IdentityAcceptanceStatus.MISMATCH
        elif resolved_doi or has_verified_landing_identity:
            status = IdentityAcceptanceStatus.RESOLVED
        else:
            status = IdentityAcceptanceStatus.UNAVAILABLE
    else:
        status = identity_status
    identity_code: str | None = None
    if status == IdentityAcceptanceStatus.MISMATCH:
        identity_code = "identity_mismatch"
    elif status != IdentityAcceptanceStatus.RESOLVED:
        identity_code = failure_code or (
            "canonical_landing_identity_unverified"
            if resolved_title and not resolved_doi
            else None
        )
    codes = _normalized_codes([identity_code])
    return IdentityAcceptanceFacet(
        status=status,
        doi=resolved_doi or None,
        expected_doi=normalized_expected_doi or None,
        title=resolved_title,
        candidate_count=candidate_count,
        canonical_landing_url=resolved_landing_url,
        canonical_landing_verified=bool(canonical_landing_verified),
        canonical_landing_unique=bool(canonical_landing_unique),
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


def _diagnostic_value(diagnostic: Any, field: str, default: Any = None) -> Any:
    if isinstance(diagnostic, Mapping):
        return diagnostic.get(field, default)
    return getattr(diagnostic, field, default)


def _audited_body_counts(diagnostics: Any) -> dict[str, int] | None:
    """Count only body records that represent an independently archivable file."""

    if not isinstance(diagnostics, Sequence) or isinstance(
        diagnostics, (str, bytes, bytearray)
    ):
        return None
    if not diagnostics:
        return None
    counts = {
        "discovered": 0,
        "attempted": 0,
        "local": 0,
        "full_size": 0,
        "preview": 0,
        "failed": 0,
        "not_archived": 0,
        "remote_only": 0,
    }
    for diagnostic in diagnostics:
        kind = normalize_text(_diagnostic_value(diagnostic, "kind")).lower()
        status = normalize_text(_diagnostic_value(diagnostic, "status")).lower()
        path = normalize_text(_diagnostic_value(diagnostic, "path"))
        tier = normalize_text(_diagnostic_value(diagnostic, "download_tier")).lower()
        failure_code = normalize_text(
            _diagnostic_value(diagnostic, "failure_code")
        ).lower()
        if kind not in _BODY_ASSET_KINDS or status == "not_requested":
            continue
        # Inline semantic tables/formulas/figures can be complete without a
        # separate binary payload. They are not strict-local file obligations.
        if not path and not tier and status == "available":
            continue
        counts["discovered"] += 1
        counts["attempted"] += 1
        local = bool(path) and status not in {"failed", "not_archived"}
        if local:
            counts["local"] += 1
            counts["preview" if tier == "preview" else "full_size"] += 1
        if status == "failed":
            counts["failed"] += 1
        if status == "not_archived":
            counts["not_archived"] += 1
        if status == "not_archived" or failure_code == "missing_path":
            counts["remote_only"] += 1
    return counts


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

    preview = max(int(value("preview") or 0), 0)
    accepted_preview = max(int(value("accepted_preview") or 0), 0)
    fallback_preview = max(int(value("fallback_preview") or 0), 0)
    by_kind = value("by_kind", {})

    def kind_value(kind: str, field: str) -> int:
        if not isinstance(by_kind, Mapping):
            return 0
        kind_summary = by_kind.get(kind)
        if isinstance(kind_summary, Mapping):
            raw = kind_summary.get(field, 0)
        else:
            raw = getattr(kind_summary, field, 0)
        return max(int(raw or 0), 0)

    body_counts = _audited_body_counts(value("diagnostics", ()))
    if body_counts is None:
        body_full_size = sum(
            kind_value(kind, "full_size") for kind in _BODY_ASSET_KINDS
        )
        body_preview = sum(kind_value(kind, "preview") for kind in _BODY_ASSET_KINDS)
        body_local = body_full_size + body_preview
        body_failed = sum(kind_value(kind, "failed") for kind in _BODY_ASSET_KINDS)
        body_not_archived = sum(
            kind_value(kind, "not_archived") for kind in _BODY_ASSET_KINDS
        )
        body_discovered = sum(
            kind_value(kind, "requested") for kind in _BODY_ASSET_KINDS
        )
        body_attempted = min(
            body_discovered,
            body_local + body_failed + body_not_archived,
        )
        body_remote_only = body_not_archived
    else:
        body_discovered = body_counts["discovered"]
        body_attempted = body_counts["attempted"]
        body_local = body_counts["local"]
        body_full_size = body_counts["full_size"]
        body_preview = body_counts["preview"]
        body_failed = body_counts["failed"]
        body_not_archived = body_counts["not_archived"]
        body_remote_only = body_counts["remote_only"]
    return AssetAcceptanceSummary(
        requested=bool(value("requested", profile != "none")),
        profile=profile,
        audited=audited,
        expected=(
            max(int(value("expected")), 0)
            if value("expected", None) is not None
            else None
        ),
        discovered=max(int(value("discovered", value("total")) or 0), 0),
        attempted=max(
            int(
                value(
                    "attempted",
                    (
                        int(value("local") or 0)
                        + int(value("failed") or 0)
                        + int(value("not_archived") or 0)
                    ),
                )
                or 0
            ),
            0,
        ),
        total=max(int(value("total") or 0), 0),
        local=max(int(value("local") or 0), 0),
        full_size=max(int(value("full_size") or 0), 0),
        preview=preview,
        accepted_preview=accepted_preview,
        fallback_preview=fallback_preview,
        failed=max(int(value("failed") or 0), 0),
        placeholder_suspected=max(int(value("placeholder_suspected") or 0), 0),
        not_archived=max(int(value("not_archived") or 0), 0),
        remote_link_count=max(int(value("remote_link_count") or 0), 0),
        remote_only_count=max(int(value("remote_only_count") or 0), 0),
        body_discovered=body_discovered,
        body_attempted=body_attempted,
        body_local=body_local,
        body_full_size=body_full_size,
        body_preview=body_preview,
        body_failed=body_failed,
        body_not_archived=body_not_archived,
        body_remote_only_count=body_remote_only,
        failure_codes=_normalized_codes(value("failure_codes", ())),
        issue_codes=_normalized_codes(value("issue_codes", ())),
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
    from ..quality.assets import logical_asset_kind, preview_asset_is_accepted

    body_assets = [
        asset for asset in assets if logical_asset_kind(asset) in _BODY_ASSET_KINDS
    ]

    preview_assets = (
        [
            asset
            for asset in assets
            if normalize_text(asset.download_tier).lower() == "preview"
        ]
        if requested
        else []
    )
    accepted_preview = sum(preview_asset_is_accepted(asset) for asset in preview_assets)
    fallback_preview = len(preview_assets) - accepted_preview
    preview = accepted_preview + fallback_preview
    failures = list(quality.asset_failures) if requested else []
    body_failures = [
        failure
        for failure in failures
        if logical_asset_kind(failure) in _BODY_ASSET_KINDS
    ]
    body_local_assets = [asset for asset in body_assets if normalize_text(asset.path)]
    body_preview = sum(
        normalize_text(asset.download_tier).lower() == "preview"
        for asset in body_local_assets
    )
    body_remote_only_count = sum(
        _asset_remote_counts(asset)[1] for asset in body_assets
    )
    body_discovered = len(body_assets) + len(body_failures)
    body_local = len(body_local_assets)
    discovered = len(assets) + len(failures)
    attempted = (
        sum(
            bool(normalize_text(asset.path)) or _asset_remote_counts(asset)[0] > 0
            for asset in assets
        )
        + len(failures)
        if requested
        else 0
    )
    not_archived = remote_only_count if requested else 0
    failure_codes = _normalized_codes(
        [_asset_failure_code(failure) for failure in failures]
    )
    issue_codes: list[str] = []
    if failures:
        issue_codes.append("asset_download_failure")
    if fallback_preview:
        issue_codes.append("asset_fidelity_degraded")
    if requested and remote_only_count:
        issue_codes.append("asset_remote_only")
    return AssetAcceptanceSummary(
        requested=requested,
        profile=profile,
        audited=False,
        expected=None,
        discovered=discovered,
        attempted=attempted,
        total=discovered,
        local=local,
        full_size=max(local - preview, 0),
        preview=preview,
        accepted_preview=accepted_preview,
        fallback_preview=fallback_preview,
        failed=len(failures),
        not_archived=not_archived,
        remote_link_count=remote_link_count,
        remote_only_count=remote_only_count,
        body_discovered=body_discovered,
        body_attempted=min(
            body_discovered,
            body_local + len(body_failures) + body_remote_only_count,
        ),
        body_local=body_local,
        body_full_size=max(body_local - body_preview, 0),
        body_preview=body_preview,
        body_failed=len(body_failures),
        body_not_archived=body_remote_only_count if requested else 0,
        body_remote_only_count=body_remote_only_count if requested else 0,
        failure_codes=failure_codes,
        issue_codes=tuple(issue_codes),
    )


def _with_asset_requirements(
    summary: AssetAcceptanceSummary,
    *,
    require_local_body_assets: bool,
    require_full_size_body_assets: bool,
) -> AssetAcceptanceSummary:
    require_full_size = bool(require_full_size_body_assets)
    require_local = bool(require_local_body_assets or require_full_size)
    applicable = summary.profile in {"body", "all"} and summary.requested
    body_discovered = summary.body_discovered
    body_attempted = summary.body_attempted
    body_local = summary.body_local
    body_full_size = summary.body_full_size
    body_preview = summary.body_preview
    body_failed = summary.body_failed
    body_not_archived = summary.body_not_archived
    body_remote_only = summary.body_remote_only_count
    all_local = bool(
        body_discovered == 0
        or (
            body_local >= body_discovered
            and body_failed == 0
            and body_not_archived == 0
            and body_remote_only == 0
        )
    )
    all_full_size = bool(
        all_local
        and (body_discovered == 0 or body_full_size >= body_discovered)
        and body_preview == 0
    )
    local_satisfied = not applicable or not require_local or all_local
    full_size_satisfied = not applicable or not require_full_size or all_full_size
    issue_codes = list(summary.issue_codes)
    if not local_satisfied:
        issue_codes.append("local_body_assets_required")
    if not full_size_satisfied:
        issue_codes.append("full_size_body_assets_required")
    return summary.model_copy(
        update={
            "body_discovered": body_discovered,
            "body_attempted": body_attempted,
            "body_local": body_local,
            "body_full_size": body_full_size,
            "body_preview": body_preview,
            "body_failed": body_failed,
            "body_not_archived": body_not_archived,
            "body_remote_only_count": body_remote_only,
            "require_local_body_assets": require_local,
            "require_full_size_body_assets": require_full_size,
            "has_local_body_assets": body_local > 0,
            "all_body_assets_local": all_local,
            "all_body_assets_full_size": all_full_size,
            "local_body_assets_satisfied": local_satisfied,
            "full_size_body_assets_satisfied": full_size_satisfied,
            "issue_codes": tuple(dict.fromkeys(issue_codes)),
        }
    )


def _asset_facet(
    summary: AssetAcceptanceSummary, *, fetch_completed: bool
) -> AssetAcceptanceFacet:
    discovered = summary.discovered or summary.total
    attempted = summary.attempted or min(
        discovered,
        summary.local + summary.failed + summary.not_archived,
    )
    issue_codes = list(summary.issue_codes)
    if not issue_codes:
        if summary.failed:
            issue_codes.append("asset_download_failure")
        if summary.fallback_preview:
            issue_codes.append("asset_fidelity_degraded")
        if summary.placeholder_suspected:
            issue_codes.append("asset_placeholder_suspected")
        if summary.remote_only_count and not summary.audited:
            issue_codes.append("asset_remote_only")
    normalized_summary = summary.model_copy(
        update={
            "discovered": discovered,
            "attempted": attempted,
            "total": discovered,
            "issue_codes": tuple(dict.fromkeys(issue_codes)),
        }
    )
    if not normalized_summary.requested:
        status = AssetAcceptanceStatus.NOT_REQUESTED
    elif not fetch_completed:
        status = AssetAcceptanceStatus.UNAVAILABLE
    elif normalized_summary.audited and normalized_summary.expected == 0:
        status = AssetAcceptanceStatus.NOT_APPLICABLE
    elif normalized_summary.discovered == 0:
        status = AssetAcceptanceStatus.UNKNOWN
    elif (
        normalized_summary.require_local_body_assets
        and not normalized_summary.local_body_assets_satisfied
    ) or (
        normalized_summary.require_full_size_body_assets
        and not normalized_summary.full_size_body_assets_satisfied
    ):
        status = AssetAcceptanceStatus.DEGRADED
    elif normalized_summary.failed and normalized_summary.local == 0:
        status = AssetAcceptanceStatus.FAILED
    elif normalized_summary.issue_codes:
        status = AssetAcceptanceStatus.DEGRADED
    else:
        status = AssetAcceptanceStatus.COMPLETE
    return AssetAcceptanceFacet(
        **normalized_summary.model_dump(),
        status=status,
        remote_links_preserved=normalized_summary.remote_only_count > 0,
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
    if losses.table_semantic_loss_count:
        codes.append("table_semantic_loss")
    if losses.formula_fallback_count:
        codes.append("formula_fallback")
    if losses.formula_missing_count:
        codes.append("formula_missing")
    if asset.requested:
        codes.extend(asset.issue_codes)
    return codes


def _route_acceptance_satisfied(
    policy: str | None,
    *,
    acquisition: AcquisitionProvenance,
    identity: IdentityAcceptanceFacet,
    content: ContentAcceptanceFacet,
    asset: AssetAcceptanceFacet,
) -> bool:
    """Evaluate the compiled route contract against the matching facet only."""

    if policy == "metadata_identity":
        return identity.status == IdentityAcceptanceStatus.RESOLVED
    representation = normalize_text(acquisition.representation).lower()
    if policy == "provider_html_body":
        return (
            representation == "html"
            and content.status == ContentAcceptanceStatus.FULLTEXT
        )
    if policy == "structured_xml_body":
        return (
            representation == "xml"
            and content.status == ContentAcceptanceStatus.FULLTEXT
        )
    if policy == "validated_pdf":
        return (
            representation == "pdf"
            and content.status == ContentAcceptanceStatus.FULLTEXT
        )
    if policy == "validated_asset":
        return bool(
            asset.requested
            and (
                (asset.status == AssetAcceptanceStatus.COMPLETE and asset.local > 0)
                or (
                    asset.status == AssetAcceptanceStatus.NOT_APPLICABLE
                    and asset.audited
                    and asset.expected == 0
                )
            )
        )
    # Catalog extensions are fail-closed until this versioned evaluator knows
    # which public facet constitutes sufficient evidence.
    return False


def _provenance_facet(
    *,
    source: str | None,
    acquisition: AcquisitionProvenance | None,
    trace: Sequence[TraceEvent],
    quality: Quality,
    identity: IdentityAcceptanceFacet,
    asset: AssetAcceptanceFacet,
    content: ContentAcceptanceFacet,
    failure_code: str | None,
) -> ProvenanceAcceptanceFacet:
    normalized_source = normalize_text(source) or None
    source_provider = provider_for_source(normalized_source)
    acquisition_consistent = False
    route_acceptance_policy: str | None = None
    route_acceptance_satisfied = False
    if acquisition_matches_provider_route(acquisition) and acquisition is not None:
        compiled_route = compile_route_execution_policy(
            acquisition.provider, acquisition.route
        )
        route_acceptance_policy = compiled_route.acceptance_policy
        route_acceptance_satisfied = _route_acceptance_satisfied(
            route_acceptance_policy,
            acquisition=acquisition,
            identity=identity,
            content=content,
            asset=asset,
        )
        if source_provider is not None:
            acquisition_consistent = source_provider == acquisition.provider
        elif normalized_source == METADATA_ONLY:
            acquisition_consistent = acquisition.provider == "crossref"
        acquisition_consistent = acquisition_consistent and (
            acquisition.fallback_used
            == acquisition_fallback_used(trace, source_trail=quality.source_trail)
        )
    has_resolve = any(
        normalize_text(event.stage).lower() == "resolve" for event in trace
    )
    has_provider_selection = any(
        normalize_text(event.stage).lower() in {"metadata", "fulltext"}
        and (normalize_text(event.provider) or normalize_text(event.component))
        for event in trace
    )
    has_terminal_route = any(
        normalize_text(event.stage).lower() in {"fulltext", "fallback"}
        and normalize_text(event.outcome).lower() not in {"attempt", "selected"}
        for event in trace
    )
    if (
        normalized_source
        and acquisition_consistent
        and route_acceptance_satisfied
        and has_resolve
        and has_provider_selection
        and has_terminal_route
    ):
        status = ProvenanceAcceptanceStatus.COMPLETE
    elif normalized_source or trace:
        status = ProvenanceAcceptanceStatus.PARTIAL
    else:
        status = ProvenanceAcceptanceStatus.MISSING

    trace_failures = [
        event
        for event in trace
        if _trace_is_failure(event)
        and not (
            content.status == ContentAcceptanceStatus.FULLTEXT
            and normalize_text(event.stage).lower() in {"resolve", "metadata"}
        )
    ]
    fallback_events = [
        event
        for event in trace
        if normalize_text(event.stage).lower() == "fallback"
        or normalize_text(event.code).lower() in _TRACE_FALLBACK_CODES
        or (
            content.status != ContentAcceptanceStatus.UNAVAILABLE
            and normalize_text(event.stage).lower() == "fulltext"
            and _trace_is_failure(event)
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
        acquisition=acquisition,
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
        acceptance_policy=route_acceptance_policy,
        acceptance_policy_satisfied=route_acceptance_satisfied,
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
        asset.status
        in {
            AssetAcceptanceStatus.DEGRADED,
            AssetAcceptanceStatus.FAILED,
            AssetAcceptanceStatus.UNKNOWN,
            AssetAcceptanceStatus.UNAVAILABLE,
        }
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
    require_local_body_assets: bool = False,
    require_full_size_body_assets: bool = False,
    title: str | None = None,
    source: str | None = None,
    canonical_landing_url: str | None = None,
    canonical_landing_verified: bool = False,
    canonical_landing_unique: bool = False,
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
                accepted_preview=0,
                fallback_preview=0,
                failed=0,
                placeholder_suspected=0,
                not_archived=0,
                failure_codes=(),
                issue_codes=(),
            )
        summary = asset_summary.model_copy(update=updates)

    summary = _with_asset_requirements(
        summary,
        require_local_body_assets=require_local_body_assets,
        require_full_size_body_assets=require_full_size_body_assets,
    )

    identity = _identity_facet(
        envelope,
        identity_status=identity_status,
        failure_code=effective_failure,
        candidate_count=candidate_count,
        doi=doi,
        expected_doi=expected_doi,
        title=title,
        canonical_landing_url=canonical_landing_url,
        canonical_landing_verified=canonical_landing_verified,
        canonical_landing_unique=canonical_landing_unique,
    )
    fetch = _fetch_facet(envelope, effective_failure)
    content = _content_facet(envelope, quality)
    asset = _asset_facet(summary, fetch_completed=fetch.completed)
    output = _output_facet(envelope, requested_outputs)
    provenance = _provenance_facet(
        source=resolved_source,
        acquisition=envelope.acquisition if envelope is not None else None,
        trace=trace,
        quality=quality,
        identity=identity,
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
    """Load the public v2 acceptance contract."""

    return FetchAcceptanceReport.model_validate(dict(payload))


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
