"""Pure, versioned acceptance evaluation for fetch results."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..models import (
    QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION,
    AcquisitionProvenance,
    Asset,
    AssetProfile,
    AssetQualitySummary,
    FetchEnvelope,
    Quality,
    SemanticLosses,
)
from ..provider_catalog import (
    acquisition_matches_provider_route,
    compile_route_execution_policy,
    provider_for_source,
)
from ..publisher_identity import normalize_doi
from ..quality.assets import (
    asset_has_remote_link,
    build_asset_quality_summary,
    logical_asset_kind,
)
from ..reason_codes import (
    ABSTRACT_ONLY,
    AUTH_REQUIRED,
    ERROR,
    METADATA_ONLY,
    NO_ACCESS,
    NOT_CONFIGURED,
    PDF_FALLBACK,
    RATE_LIMITED,
)
from ..tracing import TraceEvent, acquisition_fallback_used
from ..utils import normalize_text

FETCH_ACCEPTANCE_SCHEMA_VERSION = 3


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


class FetchAcceptanceFacet(_AcceptanceModel):
    status: FetchAcceptanceStatus
    code: str | None = None


class ContentAcceptanceFacet(_AcceptanceModel):
    requested: bool = True
    status: ContentAcceptanceStatus
    has_fulltext: bool
    has_abstract: bool
    token_estimate: int = Field(default=0, ge=0)
    semantic_losses: SemanticLosses = Field(default_factory=SemanticLosses)

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


class BodyAssetCounts(_AcceptanceModel):
    """Body file counts retained for CLI receipts and strict-asset acceptance."""

    discovered: int = Field(default=0, ge=0)
    attempted: int = Field(default=0, ge=0)
    local: int = Field(default=0, ge=0)
    full_size: int = Field(default=0, ge=0)
    preview: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    not_archived: int = Field(default=0, ge=0)
    remote_only_count: int = Field(default=0, ge=0)

    @property
    def all_local(self) -> bool:
        return self.discovered == 0 or (
            self.local >= self.discovered
            and self.failed == 0
            and self.not_archived == 0
            and self.remote_only_count == 0
        )

    @property
    def all_full_size(self) -> bool:
        return (
            self.all_local and self.preview == 0 and self.full_size >= self.discovered
        )


class AssetAcceptanceSummary(_AcceptanceModel):
    """Structured asset facts accepted by the evaluator and asset audits."""

    requested: bool
    profile: AcceptanceAssetProfile = "unknown"
    audited: bool = False
    expected: int | None = Field(default=None, ge=0)
    discovered: int = Field(default=0, ge=0)
    attempted: int = Field(default=0, ge=0)
    local: int = Field(default=0, ge=0)
    full_size: int = Field(default=0, ge=0)
    accepted_preview: int = Field(default=0, ge=0)
    fallback_preview: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    placeholder_suspected: int = Field(default=0, ge=0)
    not_archived: int = Field(default=0, ge=0)
    remote_link_count: int = Field(default=0, ge=0)
    remote_only_count: int = Field(default=0, ge=0)
    body_assets: BodyAssetCounts = Field(default_factory=BodyAssetCounts)
    require_local_body_assets: bool = False
    require_full_size_body_assets: bool = False
    local_body_assets_satisfied: bool = True
    full_size_body_assets_satisfied: bool = True
    failure_codes: tuple[str, ...] = ()
    issue_codes: tuple[str, ...] = ()

    @property
    def preview(self) -> int:
        return self.accepted_preview + self.fallback_preview


class AssetAcceptanceFacet(AssetAcceptanceSummary):
    status: AssetAcceptanceStatus

    @model_validator(mode="after")
    def validate_request_status(self) -> AssetAcceptanceFacet:
        if not self.requested and self.status != AssetAcceptanceStatus.NOT_REQUESTED:
            raise ValueError("unrequested assets must use not_requested status")
        if self.requested and self.status == AssetAcceptanceStatus.NOT_REQUESTED:
            raise ValueError("requested assets cannot use not_requested status")
        if self.profile == "none" and self.requested:
            raise ValueError("asset profile none cannot be requested")
        if self.attempted > self.discovered:
            raise ValueError("attempted cannot exceed discovered")
        return self


class OutputAcceptanceFacet(_AcceptanceModel):
    status: OutputAcceptanceStatus


class ProvenanceAcceptanceFacet(_AcceptanceModel):
    status: ProvenanceAcceptanceStatus
    source: str | None = None
    acquisition: AcquisitionProvenance | None = None
    fallback_codes: tuple[str, ...] = ()
    warning_codes: tuple[str, ...] = ()
    failure_codes: tuple[str, ...] = ()


class FetchAcceptanceReport(_AcceptanceModel):
    """Canonical acceptance report shared by all external adapters."""

    schema_version: Literal[3]
    overall: OverallAcceptanceStatus
    target: Literal["paper", "supplementary"] = "paper"
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
    {"ambiguous", AUTH_REQUIRED, NO_ACCESS, NOT_CONFIGURED, RATE_LIMITED}
)
_TRACE_FAILURE_OUTCOMES = frozenset(
    {"fail", "unavailable", "not_usable", RATE_LIMITED, NOT_CONFIGURED}
)
_TRACE_WARNING_OUTCOMES = frozenset(
    {"partial", "unavailable", "not_usable", "abstract_only"}
)
_TRACE_FALLBACK_CODES = frozenset({ABSTRACT_ONLY, METADATA_ONLY, PDF_FALLBACK})
_NON_DEGRADING_QUALITY_FLAGS = frozenset({QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION})
_BODY_ASSET_KINDS: tuple[Literal["figure", "formula", "table"], ...] = (
    "figure",
    "formula",
    "table",
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


def _trace_is_failure(event: TraceEvent) -> bool:
    outcome = normalize_text(event.outcome).lower()
    code = normalize_text(event.code).lower()
    return (
        outcome in _TRACE_FAILURE_OUTCOMES
        or code in {RATE_LIMITED, NOT_CONFIGURED}
        or event.http_status == 429
    )


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
        elif failure_code == "identity_mismatch" or (
            normalized_expected_doi
            and resolved_doi
            and resolved_doi != normalized_expected_doi
        ):
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
    return IdentityAcceptanceFacet(
        status=status,
        doi=resolved_doi or None,
        expected_doi=normalized_expected_doi or None,
        title=resolved_title,
        candidate_count=candidate_count,
        canonical_landing_url=resolved_landing_url,
        canonical_landing_verified=canonical_landing_verified,
        canonical_landing_unique=canonical_landing_unique,
        codes=_normalized_codes([identity_code]),
    )


def _fetch_facet(
    envelope: FetchEnvelope | None, failure_code: str | None
) -> FetchAcceptanceFacet:
    if envelope is not None:
        return FetchAcceptanceFacet(status=FetchAcceptanceStatus.OK, code=None)
    code = normalize_text(failure_code).lower() or ERROR
    status = (
        FetchAcceptanceStatus.ACTION_REQUIRED
        if code in _ACTION_REQUIRED_CODES
        else FetchAcceptanceStatus.FAILED
    )
    return FetchAcceptanceFacet(status=status, code=code)


def _content_facet(
    envelope: FetchEnvelope | None, quality: Quality
) -> ContentAcceptanceFacet:
    if envelope is None:
        status = ContentAcceptanceStatus.UNAVAILABLE
        has_abstract = False
    else:
        status = ContentAcceptanceStatus(envelope.quality.content_kind)
        has_abstract = bool(envelope.quality.has_abstract)
    return ContentAcceptanceFacet(
        status=status,
        has_fulltext=status == ContentAcceptanceStatus.FULLTEXT,
        has_abstract=has_abstract,
        token_estimate=max(int(quality.token_estimate or 0), 0),
        semantic_losses=quality.semantic_losses,
    )


def _audited_body_counts(q_summary: AssetQualitySummary) -> BodyAssetCounts:
    if q_summary.diagnostics:
        body_diagnostics = [
            item
            for item in q_summary.diagnostics
            if item.kind in _BODY_ASSET_KINDS
            and item.status != "not_requested"
            # Inline semantic tables/formulas/figures without a separate binary
            # payload are not strict-local file obligations.
            and not (
                not item.path and not item.download_tier and item.status == "available"
            )
        ]
        local = [
            item
            for item in body_diagnostics
            if item.path and item.status not in {"failed", "not_archived"}
        ]
        preview = sum(
            normalize_text(item.download_tier).lower() == "preview" for item in local
        )
        return BodyAssetCounts(
            discovered=len(body_diagnostics),
            attempted=len(body_diagnostics),
            local=len(local),
            full_size=len(local) - preview,
            preview=preview,
            failed=sum(item.status == "failed" for item in body_diagnostics),
            not_archived=sum(
                item.status == "not_archived" for item in body_diagnostics
            ),
            remote_only_count=sum(
                item.status == "not_archived" or item.failure_code == "missing_path"
                for item in body_diagnostics
            ),
        )

    kinds = [q_summary.by_kind[kind] for kind in _BODY_ASSET_KINDS]
    discovered = sum(kind.requested for kind in kinds)
    full_size = sum(kind.full_size for kind in kinds)
    preview = sum(kind.preview for kind in kinds)
    failed = sum(kind.failed for kind in kinds)
    not_archived = sum(kind.not_archived for kind in kinds)
    return BodyAssetCounts(
        discovered=discovered,
        attempted=min(discovered, full_size + preview + failed + not_archived),
        local=full_size + preview,
        full_size=full_size,
        preview=preview,
        failed=failed,
        not_archived=not_archived,
        remote_only_count=not_archived,
    )


def _unaudited_body_counts(
    assets: Sequence[Asset], failures: Sequence[Mapping[str, Any]]
) -> BodyAssetCounts:
    body_assets = [
        asset for asset in assets if logical_asset_kind(asset) in _BODY_ASSET_KINDS
    ]
    local = [asset for asset in body_assets if normalize_text(asset.path)]
    preview = sum(
        normalize_text(asset.download_tier).lower() == "preview" for asset in local
    )
    failed = sum(logical_asset_kind(item) in _BODY_ASSET_KINDS for item in failures)
    remote_only = sum(
        not normalize_text(asset.path) and asset_has_remote_link(asset)
        for asset in body_assets
    )
    discovered = len(body_assets) + failed
    return BodyAssetCounts(
        discovered=discovered,
        attempted=min(discovered, len(local) + failed + remote_only),
        local=len(local),
        full_size=len(local) - preview,
        preview=preview,
        failed=failed,
        not_archived=remote_only,
        remote_only_count=remote_only,
    )


def _evaluate_asset_summary(
    envelope: FetchEnvelope | None,
    *,
    profile: AssetProfile,
    quality: Quality,
    explicit_summary: AssetAcceptanceSummary | None,
    require_local_body_assets: bool,
    require_full_size_body_assets: bool,
) -> AssetAcceptanceSummary:
    if explicit_summary is not None:
        requested = False if profile == "none" else explicit_summary.requested
        updates: dict[str, Any] = {"profile": profile, "requested": requested}
        if not requested:
            updates.update(
                accepted_preview=0,
                fallback_preview=0,
                failed=0,
                placeholder_suspected=0,
                not_archived=0,
                failure_codes=(),
                issue_codes=(),
            )
        summary = explicit_summary.model_copy(update=updates)
        all_local = summary.discovered == 0 or (
            summary.local >= summary.discovered
            and summary.failed == 0
            and summary.not_archived == 0
            and summary.remote_only_count == 0
        )
        all_full_size = (
            all_local
            and summary.preview == 0
            and (summary.discovered == 0 or summary.full_size >= summary.discovered)
        )
    elif envelope is None:
        summary = AssetAcceptanceSummary(
            requested=profile != "none",
            profile=profile,
        )
        all_local = True
        all_full_size = True
    else:
        q_summary = quality.asset_summary
        if q_summary.audited and q_summary.profile == profile:
            audited = True
            body_counts = _audited_body_counts(q_summary)
        else:
            audited = False
            assets = envelope.article.assets if envelope.article is not None else ()
            failures = quality.asset_failures if profile != "none" else ()
            q_summary = build_asset_quality_summary(
                assets,
                asset_failures=failures,
                asset_profile=profile,
                archive_enabled=bool(failures),
            )
            body_counts = _unaudited_body_counts(assets, failures)
        all_local = body_counts.all_local
        all_full_size = body_counts.all_full_size

        issue_codes = list(q_summary.issue_codes)
        if not audited and profile != "none" and q_summary.remote_only_count:
            issue_codes.append("asset_remote_only")
        summary = AssetAcceptanceSummary(
            requested=q_summary.requested,
            profile=profile,
            audited=audited,
            expected=q_summary.expected,
            discovered=q_summary.discovered,
            attempted=min(
                q_summary.discovered,
                q_summary.attempted
                or (q_summary.local + q_summary.failed + q_summary.not_archived),
            ),
            local=q_summary.local,
            full_size=q_summary.full_size,
            accepted_preview=q_summary.accepted_preview,
            fallback_preview=q_summary.fallback_preview,
            failed=q_summary.failed,
            placeholder_suspected=q_summary.placeholder_suspected,
            not_archived=q_summary.not_archived,
            remote_link_count=q_summary.remote_link_count,
            remote_only_count=q_summary.remote_only_count,
            body_assets=body_counts,
            failure_codes=_normalized_codes(q_summary.failure_codes),
            issue_codes=_normalized_codes(issue_codes),
        )

    require_full_size = bool(require_full_size_body_assets)
    require_local = bool(require_local_body_assets or require_full_size)
    applicable = summary.profile in {"body", "all"} and summary.requested
    local_satisfied = not applicable or not require_local or all_local
    full_size_satisfied = not applicable or not require_full_size or all_full_size
    final_issues = list(summary.issue_codes)
    if not local_satisfied:
        final_issues.append("local_body_assets_required")
    if not full_size_satisfied:
        final_issues.append("full_size_body_assets_required")
    return summary.model_copy(
        update={
            "require_local_body_assets": require_local,
            "require_full_size_body_assets": require_full_size,
            "local_body_assets_satisfied": local_satisfied,
            "full_size_body_assets_satisfied": full_size_satisfied,
            "issue_codes": tuple(dict.fromkeys(final_issues)),
        }
    )


def _asset_facet(
    summary: AssetAcceptanceSummary, *, fetch_ok: bool
) -> AssetAcceptanceFacet:
    attempted = summary.attempted or min(
        summary.discovered,
        summary.local + summary.failed + summary.not_archived,
    )
    issue_codes = list(summary.issue_codes)
    if summary.requested and not issue_codes:
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
            "attempted": attempted,
            "issue_codes": tuple(dict.fromkeys(issue_codes)),
        }
    )
    if not normalized_summary.requested:
        status = AssetAcceptanceStatus.NOT_REQUESTED
    elif not fetch_ok:
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
    return OutputAcceptanceFacet(status=status)


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
    route_acceptance_satisfied = False
    if acquisition_matches_provider_route(acquisition) and acquisition is not None:
        compiled_route = compile_route_execution_policy(
            acquisition.provider, acquisition.route
        )
        route_acceptance_satisfied = _route_acceptance_satisfied(
            compiled_route.acceptance_policy,
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
            acquisition.fallback_used == acquisition_fallback_used(trace)
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
    target: Literal["paper", "supplementary"] = "paper",
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
    """Evaluate immutable fetch facts without network or provider work."""

    if candidate_count < 0:
        raise ValueError("candidate_count must not be negative")
    normalized_failure = normalize_text(failure_code).lower() or None
    if envelope is not None and normalized_failure is not None:
        raise ValueError("failure_code cannot be combined with a completed envelope")
    effective_failure = normalized_failure or (ERROR if envelope is None else None)
    target = envelope.target if envelope is not None else target
    if target == "supplementary":
        if envelope is not None:
            return _evaluate_supplementary_acceptance(
                envelope, expected_doi=expected_doi, requested_outputs=requested_outputs
            )
        asset_profile = "all"
        require_local_body_assets = require_full_size_body_assets = False
        if requested_outputs is not None:
            requested_outputs = [
                item for item in requested_outputs if item != "article"
            ]
    quality = envelope.quality if envelope is not None else Quality()
    trace = list(envelope.trace) if envelope is not None else []
    resolved_source = (
        normalize_text(source or (envelope.source if envelope is not None else None))
        or None
    )

    summary = _evaluate_asset_summary(
        envelope,
        profile=asset_profile,
        quality=quality,
        explicit_summary=asset_summary,
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
    content = (
        ContentAcceptanceFacet(
            status=ContentAcceptanceStatus.UNAVAILABLE,
            requested=False,
            has_fulltext=False,
            has_abstract=False,
        )
        if target == "supplementary"
        else _content_facet(envelope, quality)
    )
    asset = _asset_facet(summary, fetch_ok=fetch.status == FetchAcceptanceStatus.OK)
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
        overall=overall,
        target=target,
        identity=identity,
        fetch=fetch,
        content=content,
        asset=asset,
        output=output,
        provenance=provenance,
    )


def _evaluate_supplementary_acceptance(
    envelope: FetchEnvelope,
    *,
    expected_doi: str | None,
    requested_outputs: Collection[AcceptanceOutputKind | str] | None,
) -> FetchAcceptanceReport:
    result = envelope.supplementary
    assert result is not None
    local = sum(bool(asset.get("path")) for asset in result.assets)
    failed = len(result.asset_failures)
    unarchived = sum(not asset.get("path") for asset in result.assets)
    codes = tuple(
        dict.fromkeys(
            str(item.get("reason") or "asset_download_failure")
            for item in result.asset_failures
        )
    )
    identity = _identity_facet(
        envelope,
        identity_status=(
            None if result.identity_verified else IdentityAcceptanceStatus.UNAVAILABLE
        ),
        failure_code=None,
        candidate_count=0,
        doi=envelope.doi,
        expected_doi=expected_doi,
        title=None,
        canonical_landing_url=result.source_urls[0] if result.source_urls else None,
        canonical_landing_verified=result.identity_verified,
        canonical_landing_unique=True,
    )
    status = result.status
    completed = status in {"complete", "degraded"}
    asset_status = (
        AssetAcceptanceStatus.NOT_APPLICABLE
        if status == "no_result"
        else AssetAcceptanceStatus.COMPLETE
        if status == "complete"
        else AssetAcceptanceStatus.DEGRADED
        if completed
        else AssetAcceptanceStatus.FAILED
    )
    assets = AssetAcceptanceFacet(
        requested=True,
        profile="all",
        audited=result.discovery_complete,
        expected=len(result.assets) if result.discovery_complete else None,
        discovered=len(result.assets),
        attempted=min(len(result.assets), local + failed),
        local=local,
        failed=failed,
        not_archived=unarchived,
        remote_only_count=unarchived,
        failure_codes=codes,
        issue_codes=_normalized_codes(
            [*codes, "asset_not_archived" if unarchived else None]
        ),
        status=asset_status,
    )
    requested = tuple(
        AcceptanceOutputKind(item)
        for item in sorted(set(requested_outputs or ()))
        if item != "article"
    )
    available = tuple(
        item
        for item in requested
        if (item == AcceptanceOutputKind.MARKDOWN and envelope.markdown is not None)
        or (item == AcceptanceOutputKind.METADATA and envelope.metadata is not None)
    )
    missing = tuple(item for item in requested if item not in available)
    provenance_complete = bool(
        result.source_urls
        and envelope.acquisition
        and envelope.trace
        and envelope.acquisition.provider == envelope.source
        and envelope.acquisition.route in {"supplementary", "source_assets"}
        and envelope.acquisition.representation in {"html", "xml"}
    )
    overall = (
        OverallAcceptanceStatus.ACTION_REQUIRED
        if identity.status != IdentityAcceptanceStatus.RESOLVED
        else OverallAcceptanceStatus.FAILED
        if not completed or missing
        else OverallAcceptanceStatus.COMPLETE
        if status == "complete" and provenance_complete
        else OverallAcceptanceStatus.DEGRADED
    )
    return FetchAcceptanceReport(
        schema_version=FETCH_ACCEPTANCE_SCHEMA_VERSION,
        target="supplementary",
        overall=overall,
        identity=identity,
        fetch=FetchAcceptanceFacet(
            status=(
                FetchAcceptanceStatus.OK if completed else FetchAcceptanceStatus.FAILED
            ),
            code=None if completed else status,
        ),
        content=ContentAcceptanceFacet(
            status=ContentAcceptanceStatus.UNAVAILABLE,
            requested=False,
            has_fulltext=False,
            has_abstract=False,
        ),
        asset=assets,
        output=OutputAcceptanceFacet(
            status=(
                OutputAcceptanceStatus.COMPLETE
                if not missing
                else OutputAcceptanceStatus.MISSING
            ),
        ),
        provenance=ProvenanceAcceptanceFacet(
            status=(
                ProvenanceAcceptanceStatus.COMPLETE
                if provenance_complete
                else ProvenanceAcceptanceStatus.PARTIAL
            ),
            source=envelope.source,
            acquisition=envelope.acquisition,
            warning_codes=assets.issue_codes,
            failure_codes=codes,
        ),
    )


def parse_fetch_acceptance_report(
    payload: Mapping[str, Any],
) -> FetchAcceptanceReport:
    """Load the public v3 acceptance contract."""

    return FetchAcceptanceReport.model_validate(dict(payload))


def fetch_acceptance_json_schema() -> dict[str, Any]:
    """Return the canonical Draft 2020-12-compatible Pydantic JSON Schema."""

    return FetchAcceptanceReport.model_json_schema()


__all__ = [
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
    "IdentityAcceptanceFacet",
    "IdentityAcceptanceStatus",
    "OutputAcceptanceFacet",
    "OutputAcceptanceStatus",
    "OverallAcceptanceStatus",
    "ProvenanceAcceptanceFacet",
    "ProvenanceAcceptanceStatus",
    "evaluate_fetch_acceptance",
    "fetch_acceptance_json_schema",
    "parse_fetch_acceptance_report",
]
