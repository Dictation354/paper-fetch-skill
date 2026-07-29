"""Versioned manifest records shared by CLI and MCP adapters."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from .models import AssetProfile, FetchEnvelope
from .tracing import TraceEvent, merge_trace, trace_from_markers
from .utils import normalize_text
from .workflow.acceptance import (
    AcceptanceOutputKind,
    AssetAcceptanceFacet,
    AssetAcceptanceSummary,
    FetchAcceptanceReport,
    IdentityAcceptanceFacet,
    evaluate_fetch_acceptance,
)

MANIFEST_RECORD_SCHEMA_VERSION = 2
MANIFEST_RECORD_MIN_READER_VERSION = 2
MANIFEST_RECORD_SCHEMA_RESOURCE = "manifest-record-v2.schema.json"
MANIFEST_RECORD_SCHEMA_ID = (
    "https://paper-fetch.local/schema/manifest-record-v2.schema.json"
)


class ManifestRecordStatus(StrEnum):
    """Lifecycle of one immutable attempt record."""

    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class ArtifactVerificationStatus(StrEnum):
    """File state observed while the immutable record was built."""

    VERIFIED = "verified"
    MISSING = "missing"
    UNREADABLE = "unreadable"


class LegacyArtifactField(StrEnum):
    """Legacy CLI field supplied by one output artifact."""

    OUTPUT_PATH = "output_path"
    SAVED_MARKDOWN_PATH = "saved_markdown_path"


class ArtifactStat(Protocol):
    """The stat attributes needed by the artifact snapshot builder."""

    @property
    def st_size(self) -> int: ...

    @property
    def st_mtime(self) -> float: ...


Clock = Callable[[], datetime]
UuidFactory = Callable[[], UUID]
ArtifactStatReader = Callable[[Path], ArtifactStat]
ArtifactHasher = Callable[[Path], str]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _uuid4() -> UUID:
    return uuid4()


def _stat_artifact(path: Path) -> ArtifactStat:
    return path.stat()


def _sha256_artifact(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


@dataclass(frozen=True)
class ManifestBuilderDependencies:
    """Injectable nondeterminism and filesystem reads for record construction."""

    clock: Clock = _utc_now
    uuid_factory: UuidFactory = _uuid4
    stat: ArtifactStatReader = _stat_artifact
    sha256: ArtifactHasher = _sha256_artifact


DEFAULT_MANIFEST_BUILDER_DEPENDENCIES = ManifestBuilderDependencies()


class _ManifestModel(BaseModel):
    # Within v2, readers ignore additive fields they do not understand.
    model_config = ConfigDict(extra="ignore", frozen=True, from_attributes=True)


class ManifestRequest(_ManifestModel):
    """Original query plus JSON request semantics covered by the fingerprint."""

    query: str
    parameters: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        if not normalize_text(value):
            raise ValueError("query must not be blank")
        # Preserve the exact caller text; only the blank check is normalized.
        return value


class ManifestTraceEvent(_ManifestModel):
    """Pydantic wire representation of the canonical TraceEvent."""

    stage: str = Field(min_length=1)
    component: str = Field(min_length=1)
    outcome: str = Field(default="info", min_length=1)
    code: str | None = None
    message: str | None = None
    provider: str | None = None
    route: str | None = None
    span_id: str | None = None
    attempt_id: str | None = None
    parent_span_id: str | None = None
    attempt: int | None = Field(default=None, ge=1)
    http_status: int | None = None
    error_category: str | None = None
    retryable: bool | None = None
    retry_after_seconds: int | None = None
    target: str | None = None
    target_sha256: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    duration_ms: float | None = None


class ManifestError(_ManifestModel):
    """Structured failure with transport-specific additive facts preserved."""

    model_config = ConfigDict(extra="allow", frozen=True, from_attributes=True)

    status: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ManifestSemanticLosses(_ManifestModel):
    """Stable compatibility summary derived from acceptance content facets."""

    table_fallback_count: int = Field(default=0, ge=0)
    table_layout_degraded_count: int = Field(default=0, ge=0)
    table_semantic_loss_count: int = Field(default=0, ge=0)
    table_legacy_lossy_count: int = Field(default=0, ge=0)
    formula_fallback_count: int = Field(default=0, ge=0)
    formula_missing_count: int = Field(default=0, ge=0)


class ManifestOutputArtifactSpec(_ManifestModel):
    """Adapter input for an output file that should be snapshotted."""

    path: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    legacy_field: LegacyArtifactField | None = None
    completed_at: AwareDatetime | None = None

    @field_validator("path", mode="before")
    @classmethod
    def coerce_path(cls, value: Any) -> str:
        return str(value)


class ManifestOutputArtifact(_ManifestModel):
    """Immutable file facts observed at record completion."""

    path: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    legacy_field: LegacyArtifactField | None = None
    size: int | None = Field(default=None, ge=0)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    mtime: AwareDatetime | None = None
    completed_at: AwareDatetime
    verification_status: ArtifactVerificationStatus

    @model_validator(mode="after")
    def validate_verification_facts(self) -> ManifestOutputArtifact:
        if self.verification_status == ArtifactVerificationStatus.VERIFIED and (
            self.size is None or self.sha256 is None or self.mtime is None
        ):
            raise ValueError("verified artifacts require size, sha256, and mtime")
        if self.verification_status == ArtifactVerificationStatus.MISSING and any(
            value is not None for value in (self.size, self.sha256, self.mtime)
        ):
            raise ValueError("missing artifacts cannot contain observed file facts")
        return self


class LegacyManifestProjection(_ManifestModel):
    """The exact nine top-level fields exposed by the pre-v2 CLI JSONL."""

    index: int = Field(ge=1)
    query: str
    status: str
    doi: str | None
    source: str | None
    output_path: str | None
    saved_markdown_path: str | None
    warnings: tuple[str, ...]
    error: ManifestError | None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ManifestRecord(_ManifestModel):
    """One versioned, append-only fetch attempt record."""

    schema_version: Literal[2]
    minimum_reader_schema_version: Literal[2]
    tool_version: str = Field(min_length=1)
    run_id: UUID
    record_id: UUID
    index: int = Field(ge=1)
    attempt: int = Field(ge=1)
    query: str
    request: ManifestRequest
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    record_status: ManifestRecordStatus
    status: str = Field(min_length=1)
    identity: IdentityAcceptanceFacet
    doi: str | None
    started_at: AwareDatetime
    completed_at: AwareDatetime
    source: str | None
    acceptance: FetchAcceptanceReport
    trace: tuple[ManifestTraceEvent, ...]
    fallback_codes: tuple[str, ...]
    warning_codes: tuple[str, ...]
    failure_codes: tuple[str, ...]
    warnings: tuple[str, ...]
    semantic_losses: ManifestSemanticLosses
    asset_summary: AssetAcceptanceFacet
    error: ManifestError | None
    output_artifacts: tuple[ManifestOutputArtifact, ...]
    output_path: str | None
    saved_markdown_path: str | None

    @model_validator(mode="after")
    def validate_derived_fields(self) -> ManifestRecord:
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must not precede started_at")
        if self.query != self.request.query:
            raise ValueError("query must match request.query")
        if self.request_fingerprint != build_manifest_request_fingerprint(self.request):
            raise ValueError("request_fingerprint does not match request")
        if self.identity != self.acceptance.identity:
            raise ValueError("identity must be the acceptance identity facet")
        if self.doi != self.identity.doi:
            raise ValueError("doi must be the normalized acceptance DOI")
        if self.source != self.acceptance.provenance.source:
            raise ValueError("source must be the acceptance provenance source")
        if self.asset_summary != self.acceptance.asset:
            raise ValueError("asset_summary must be the acceptance asset facet")
        if self.fallback_codes != self.acceptance.provenance.fallback_codes:
            raise ValueError("fallback_codes must come from acceptance provenance")
        if self.warning_codes != self.acceptance.provenance.warning_codes:
            raise ValueError("warning_codes must come from acceptance provenance")
        if self.failure_codes != self.acceptance.provenance.failure_codes:
            raise ValueError("failure_codes must come from acceptance provenance")
        if self.semantic_losses != _semantic_losses_from_acceptance(self.acceptance):
            raise ValueError("semantic_losses must come from acceptance content")

        if self.record_status == ManifestRecordStatus.COMPLETED:
            if self.status != "ok" or self.error is not None:
                raise ValueError("completed records require status=ok and no error")
            if not self.acceptance.fetch.completed:
                raise ValueError("completed records require completed fetch acceptance")
        else:
            if self.error is None or self.status != self.error.status:
                raise ValueError(
                    "failed/aborted records require their structured error"
                )
            if self.acceptance.fetch.completed:
                raise ValueError("failed/aborted records cannot have completed fetch")

        legacy_paths: dict[LegacyArtifactField, str] = {}
        for artifact in self.output_artifacts:
            if artifact.legacy_field is None:
                continue
            if artifact.legacy_field in legacy_paths:
                raise ValueError(
                    f"duplicate legacy artifact field: {artifact.legacy_field.value}"
                )
            legacy_paths[artifact.legacy_field] = artifact.path
        if self.output_path != legacy_paths.get(LegacyArtifactField.OUTPUT_PATH):
            raise ValueError("output_path must be derived from output_artifacts")
        if self.saved_markdown_path != legacy_paths.get(
            LegacyArtifactField.SAVED_MARKDOWN_PATH
        ):
            raise ValueError(
                "saved_markdown_path must be derived from output_artifacts"
            )
        return self

    def legacy_projection(self) -> LegacyManifestProjection:
        """Return the old nine-field JSONL shape without adapter-owned assembly."""

        return LegacyManifestProjection(
            index=self.index,
            query=self.query,
            status=self.status,
            doi=self.doi,
            source=self.source,
            output_path=self.output_path,
            saved_markdown_path=self.saved_markdown_path,
            warnings=self.warnings,
            error=self.error,
        )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)


def build_manifest_request_fingerprint(
    request: ManifestRequest | Mapping[str, Any],
) -> str:
    """Hash canonical JSON request semantics for cache/resume comparisons."""

    model = (
        request
        if isinstance(request, ManifestRequest)
        else ManifestRequest.model_validate(request)
    )
    encoded = json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _semantic_losses_from_acceptance(
    acceptance: FetchAcceptanceReport,
) -> ManifestSemanticLosses:
    tables = acceptance.content.tables
    formulas = acceptance.content.formulas
    return ManifestSemanticLosses(
        table_fallback_count=tables.fallback_count,
        table_layout_degraded_count=tables.layout_degraded_count,
        table_semantic_loss_count=tables.semantic_loss_count,
        table_legacy_lossy_count=tables.legacy_lossy_count,
        formula_fallback_count=formulas.fallback_count,
        formula_missing_count=formulas.missing_count,
    )


def _trace_from_envelope(envelope: FetchEnvelope | None) -> list[TraceEvent]:
    if envelope is None:
        return []
    article_trace = (
        envelope.article.quality.trace if envelope.article is not None else []
    )
    return merge_trace(envelope.trace, envelope.quality.trace, article_trace)


def _error_extra_sequence(error: ManifestError, field: str) -> Sequence[Any]:
    value = (error.model_extra or {}).get(field)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _trace_for_record(
    envelope: FetchEnvelope | None,
    error: ManifestError | None,
    explicit_trace: Sequence[TraceEvent | ManifestTraceEvent] | None,
) -> tuple[ManifestTraceEvent, ...]:
    if explicit_trace is not None:
        raw_trace: Sequence[TraceEvent | ManifestTraceEvent] = explicit_trace
    elif envelope is not None:
        raw_trace = _trace_from_envelope(envelope)
    elif error is not None:
        trace_payload = _error_extra_sequence(error, "trace")
        if trace_payload:
            raw_trace = [
                ManifestTraceEvent.model_validate(item) for item in trace_payload
            ]
        else:
            raw_trace = trace_from_markers(
                [str(item) for item in _error_extra_sequence(error, "source_trail")]
            )
    else:
        raw_trace = ()

    return tuple(ManifestTraceEvent.model_validate(value) for value in raw_trace)


def _warnings_for_record(
    envelope: FetchEnvelope | None,
    error: ManifestError | None,
    explicit_warnings: Sequence[str] | None,
) -> tuple[str, ...]:
    if explicit_warnings is not None:
        values: Sequence[Any] = explicit_warnings
    elif envelope is not None:
        values = envelope.warnings
    elif error is not None:
        values = _error_extra_sequence(error, "warnings")
    else:
        values = ()
    return tuple(dict.fromkeys(str(item) for item in values))


def _failure_code(error: ManifestError) -> str:
    extra = error.model_extra or {}
    for field in ("code", "error_category"):
        value = normalize_text(extra.get(field)).lower()
        if value:
            return value
    return normalize_text(error.status).lower()


def _snapshot_artifact(
    spec: ManifestOutputArtifactSpec,
    *,
    completed_at: datetime,
    deps: ManifestBuilderDependencies,
) -> ManifestOutputArtifact:
    path = Path(spec.path)
    artifact_completed_at = spec.completed_at or completed_at
    try:
        stat = deps.stat(path)
    except FileNotFoundError:
        return ManifestOutputArtifact(
            path=spec.path,
            kind=spec.kind,
            legacy_field=spec.legacy_field,
            completed_at=artifact_completed_at,
            verification_status=ArtifactVerificationStatus.MISSING,
        )
    except OSError:
        return ManifestOutputArtifact(
            path=spec.path,
            kind=spec.kind,
            legacy_field=spec.legacy_field,
            completed_at=artifact_completed_at,
            verification_status=ArtifactVerificationStatus.UNREADABLE,
        )

    size = int(stat.st_size)
    mtime = datetime.fromtimestamp(float(stat.st_mtime), tz=UTC)
    try:
        sha256 = normalize_text(deps.sha256(path)).lower()
    except OSError:
        return ManifestOutputArtifact(
            path=spec.path,
            kind=spec.kind,
            legacy_field=spec.legacy_field,
            size=size,
            mtime=mtime,
            completed_at=artifact_completed_at,
            verification_status=ArtifactVerificationStatus.UNREADABLE,
        )
    return ManifestOutputArtifact(
        path=spec.path,
        kind=spec.kind,
        legacy_field=spec.legacy_field,
        size=size,
        sha256=sha256,
        mtime=mtime,
        completed_at=artifact_completed_at,
        verification_status=ArtifactVerificationStatus.VERIFIED,
    )


def build_manifest_record(
    *,
    tool_version: str,
    index: int,
    attempt: int,
    query: str,
    request_parameters: Mapping[str, JsonValue] | None,
    asset_profile: AssetProfile,
    envelope: FetchEnvelope | None = None,
    error: ManifestError | Mapping[str, Any] | None = None,
    aborted: bool = False,
    requested_outputs: Collection[AcceptanceOutputKind | str] | None = None,
    asset_summary: AssetAcceptanceSummary | None = None,
    candidate_count: int = 0,
    expected_doi: str | None = None,
    title: str | None = None,
    source: str | None = None,
    output_artifacts: Sequence[ManifestOutputArtifactSpec] = (),
    trace: Sequence[TraceEvent | ManifestTraceEvent] | None = None,
    warnings: Sequence[str] | None = None,
    run_id: UUID | str | None = None,
    record_id: UUID | str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    deps: ManifestBuilderDependencies = DEFAULT_MANIFEST_BUILDER_DEPENDENCIES,
) -> ManifestRecord:
    """Build one immutable record without writing any file or manifest."""

    if envelope is not None and error is not None:
        raise ValueError("envelope and error are mutually exclusive")
    if envelope is None and error is None:
        raise ValueError("a completed envelope or structured error is required")
    if aborted and envelope is not None:
        raise ValueError("aborted records cannot contain a completed envelope")

    request = ManifestRequest(
        query=query,
        parameters=dict(request_parameters or {}),
    )
    manifest_error = (
        error
        if isinstance(error, ManifestError)
        else ManifestError.model_validate(error)
        if error is not None
        else None
    )
    failure_code = _failure_code(manifest_error) if manifest_error is not None else None
    acceptance = evaluate_fetch_acceptance(
        envelope,
        asset_profile=asset_profile,
        requested_outputs=requested_outputs,
        asset_summary=asset_summary,
        failure_code=failure_code,
        candidate_count=candidate_count,
        expected_doi=expected_doi,
        title=title,
        source=source,
    )
    effective_started_at = started_at or deps.clock()
    effective_completed_at = completed_at or deps.clock()
    artifacts = tuple(
        _snapshot_artifact(
            ManifestOutputArtifactSpec.model_validate(spec),
            completed_at=effective_completed_at,
            deps=deps,
        )
        for spec in output_artifacts
    )
    legacy_paths = {
        artifact.legacy_field: artifact.path
        for artifact in artifacts
        if artifact.legacy_field is not None
    }
    if len(legacy_paths) != sum(
        artifact.legacy_field is not None for artifact in artifacts
    ):
        raise ValueError("each legacy artifact field may be assigned only once")

    if envelope is not None:
        record_status = ManifestRecordStatus.COMPLETED
        legacy_status = "ok"
    elif aborted:
        record_status = ManifestRecordStatus.ABORTED
        assert manifest_error is not None
        legacy_status = manifest_error.status
    else:
        record_status = ManifestRecordStatus.FAILED
        assert manifest_error is not None
        legacy_status = manifest_error.status

    return ManifestRecord(
        schema_version=MANIFEST_RECORD_SCHEMA_VERSION,
        minimum_reader_schema_version=MANIFEST_RECORD_MIN_READER_VERSION,
        tool_version=tool_version,
        run_id=run_id or deps.uuid_factory(),
        record_id=record_id or deps.uuid_factory(),
        index=index,
        attempt=attempt,
        query=query,
        request=request,
        request_fingerprint=build_manifest_request_fingerprint(request),
        record_status=record_status,
        status=legacy_status,
        identity=acceptance.identity,
        doi=acceptance.identity.doi,
        started_at=effective_started_at,
        completed_at=effective_completed_at,
        source=acceptance.provenance.source,
        acceptance=acceptance,
        trace=_trace_for_record(envelope, manifest_error, trace),
        fallback_codes=acceptance.provenance.fallback_codes,
        warning_codes=acceptance.provenance.warning_codes,
        failure_codes=acceptance.provenance.failure_codes,
        warnings=_warnings_for_record(envelope, manifest_error, warnings),
        semantic_losses=_semantic_losses_from_acceptance(acceptance),
        asset_summary=acceptance.asset,
        error=manifest_error,
        output_artifacts=artifacts,
        output_path=legacy_paths.get(LegacyArtifactField.OUTPUT_PATH),
        saved_markdown_path=legacy_paths.get(LegacyArtifactField.SAVED_MARKDOWN_PATH),
    )


def parse_manifest_record(payload: Mapping[str, Any]) -> ManifestRecord:
    """Load manifest schema v2; additive unknown fields are ignored."""

    return ManifestRecord.model_validate(payload)


def generated_manifest_record_json_schema() -> dict[str, Any]:
    """Generate the model schema used to verify the packaged stable resource."""

    schema = ManifestRecord.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = MANIFEST_RECORD_SCHEMA_ID
    return schema


def manifest_record_json_schema() -> dict[str, Any]:
    """Load the packaged, release-stable Draft 2020-12 JSON Schema."""

    resource = files("paper_fetch.resources.manifest").joinpath(
        MANIFEST_RECORD_SCHEMA_RESOURCE
    )
    return json.loads(resource.read_text(encoding="utf-8"))


__all__ = [
    "DEFAULT_MANIFEST_BUILDER_DEPENDENCIES",
    "MANIFEST_RECORD_MIN_READER_VERSION",
    "MANIFEST_RECORD_SCHEMA_ID",
    "MANIFEST_RECORD_SCHEMA_RESOURCE",
    "MANIFEST_RECORD_SCHEMA_VERSION",
    "ArtifactStat",
    "ArtifactVerificationStatus",
    "LegacyArtifactField",
    "LegacyManifestProjection",
    "ManifestBuilderDependencies",
    "ManifestError",
    "ManifestOutputArtifact",
    "ManifestOutputArtifactSpec",
    "ManifestRecord",
    "ManifestRecordStatus",
    "ManifestRequest",
    "ManifestSemanticLosses",
    "ManifestTraceEvent",
    "build_manifest_record",
    "build_manifest_request_fingerprint",
    "generated_manifest_record_json_schema",
    "manifest_record_json_schema",
    "parse_manifest_record",
]
