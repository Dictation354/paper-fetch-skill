"""Versioned manifest records shared by CLI file delivery."""

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
from .tracing import TraceEvent
from .utils import normalize_text
from .workflow.acceptance import (
    AcceptanceOutputKind,
    AssetAcceptanceSummary,
    FetchAcceptanceReport,
    FetchAcceptanceStatus,
    evaluate_fetch_acceptance,
)

MANIFEST_RECORD_SCHEMA_VERSION = 3
MANIFEST_RECORD_SCHEMA_RESOURCE = "manifest-record-v3.schema.json"
MANIFEST_RECORD_SCHEMA_ID = (
    "https://paper-fetch.local/schema/manifest-record-v3.schema.json"
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
    # Within v3, readers ignore additive fields they do not understand.
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


class ManifestOutputArtifactSpec(_ManifestModel):
    """Adapter input for an output file that should be snapshotted."""

    path: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    route: str | None = None
    failure_code: str | None = None
    completed_at: AwareDatetime | None = None

    @field_validator("path", mode="before")
    @classmethod
    def coerce_path(cls, value: Any) -> str:
        return str(value)


class ManifestOutputArtifact(_ManifestModel):
    """Immutable file facts observed at record completion."""

    path: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    route: str | None = None
    failure_code: str | None = None
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


class ManifestRecord(_ManifestModel):
    """One versioned fetch result record."""

    schema_version: Literal[3]
    tool_version: str = Field(min_length=1)
    run_id: UUID
    record_id: UUID
    index: int = Field(ge=1)
    attempt: int = Field(ge=1)
    request: ManifestRequest
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    record_status: ManifestRecordStatus
    started_at: AwareDatetime
    completed_at: AwareDatetime
    acceptance: FetchAcceptanceReport
    trace: tuple[ManifestTraceEvent, ...]
    warnings: tuple[str, ...]
    error: ManifestError | None
    output_artifacts: tuple[ManifestOutputArtifact, ...]

    @model_validator(mode="after")
    def validate_derived_fields(self) -> ManifestRecord:
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must not precede started_at")
        if self.request_fingerprint != build_manifest_request_fingerprint(self.request):
            raise ValueError("request_fingerprint does not match request")

        fetch_completed = self.acceptance.fetch.status == FetchAcceptanceStatus.OK
        if self.record_status == ManifestRecordStatus.COMPLETED:
            if self.error is not None:
                raise ValueError("completed records cannot contain an error")
            if not fetch_completed:
                raise ValueError("completed records require completed fetch acceptance")
        else:
            if self.error is None:
                raise ValueError(
                    "failed/aborted records require their structured error"
                )
            if fetch_completed:
                raise ValueError("failed/aborted records cannot have completed fetch")

        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)


def build_manifest_request_fingerprint(
    request: ManifestRequest | Mapping[str, Any],
) -> str:
    """Hash canonical JSON request semantics for cache comparisons."""

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


def _trace_from_envelope(envelope: FetchEnvelope | None) -> list[TraceEvent]:
    if envelope is None:
        return []
    return list(envelope.trace)


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
        raw_trace = [ManifestTraceEvent.model_validate(item) for item in trace_payload]
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
        values = envelope.quality.warnings
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


def snapshot_output_artifact(
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
            route=spec.route,
            failure_code=spec.failure_code,
            completed_at=artifact_completed_at,
            verification_status=ArtifactVerificationStatus.MISSING,
        )
    except OSError:
        return ManifestOutputArtifact(
            path=spec.path,
            kind=spec.kind,
            route=spec.route,
            failure_code=spec.failure_code,
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
            route=spec.route,
            failure_code=spec.failure_code,
            size=size,
            mtime=mtime,
            completed_at=artifact_completed_at,
            verification_status=ArtifactVerificationStatus.UNREADABLE,
        )
    return ManifestOutputArtifact(
        path=spec.path,
        kind=spec.kind,
        route=spec.route,
        failure_code=spec.failure_code,
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
    requested_outputs: Collection[AcceptanceOutputKind | str] | None = None,
    asset_summary: AssetAcceptanceSummary | None = None,
    require_local_body_assets: bool | None = None,
    require_full_size_body_assets: bool | None = None,
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
    strategy_parameters = request.parameters.get("strategy")
    strategy_parameters = (
        strategy_parameters if isinstance(strategy_parameters, Mapping) else {}
    )
    effective_require_local = bool(
        strategy_parameters.get("require_local_body_assets", False)
        if require_local_body_assets is None
        else require_local_body_assets
    )
    effective_require_full_size = bool(
        strategy_parameters.get("require_full_size_body_assets", False)
        if require_full_size_body_assets is None
        else require_full_size_body_assets
    )
    supplementary_error = (
        manifest_error if request.parameters.get("target") == "supplementary" else None
    )
    acceptance = evaluate_fetch_acceptance(
        envelope,
        asset_profile=asset_profile,
        target="supplementary"
        if request.parameters.get("target") == "supplementary"
        else "paper",
        requested_outputs=requested_outputs,
        asset_summary=asset_summary,
        require_local_body_assets=effective_require_local,
        require_full_size_body_assets=effective_require_full_size,
        failure_code=failure_code,
        candidate_count=candidate_count,
        doi=getattr(supplementary_error, "doi", None),
        expected_doi=expected_doi,
        title=title,
        source=source or getattr(supplementary_error, "provider", None),
    )
    effective_started_at = started_at or deps.clock()
    effective_completed_at = completed_at or deps.clock()
    artifacts = tuple(
        snapshot_output_artifact(
            ManifestOutputArtifactSpec.model_validate(spec),
            completed_at=effective_completed_at,
            deps=deps,
        )
        for spec in output_artifacts
    )
    if (
        envelope is not None
        and envelope.target == "supplementary"
        and acceptance.fetch.status != FetchAcceptanceStatus.OK
    ):
        record_status = ManifestRecordStatus.FAILED
        manifest_error = ManifestError(
            status=acceptance.fetch.code or "error",
            reason=(
                "No supplementary materials were found after complete discovery."
                if acceptance.fetch.code == "no_result"
                else "Supplementary acquisition failed; see individual material failures."
            ),
        )
    elif envelope is not None:
        record_status = ManifestRecordStatus.COMPLETED
    elif aborted:
        record_status = ManifestRecordStatus.ABORTED
        assert manifest_error is not None
    else:
        record_status = ManifestRecordStatus.FAILED
        assert manifest_error is not None

    return ManifestRecord(
        schema_version=MANIFEST_RECORD_SCHEMA_VERSION,
        tool_version=tool_version,
        run_id=(
            run_id
            if isinstance(run_id, UUID)
            else UUID(run_id)
            if run_id is not None
            else deps.uuid_factory()
        ),
        record_id=(
            record_id
            if isinstance(record_id, UUID)
            else UUID(record_id)
            if record_id is not None
            else deps.uuid_factory()
        ),
        index=index,
        attempt=attempt,
        request=request,
        request_fingerprint=build_manifest_request_fingerprint(request),
        record_status=record_status,
        started_at=effective_started_at,
        completed_at=effective_completed_at,
        acceptance=acceptance,
        trace=_trace_for_record(envelope, manifest_error, trace),
        warnings=_warnings_for_record(envelope, manifest_error, warnings),
        error=manifest_error,
        output_artifacts=artifacts,
    )


def parse_manifest_record(payload: Mapping[str, Any]) -> ManifestRecord:
    """Load manifest schema v3; additive unknown fields are ignored."""

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
    "MANIFEST_RECORD_SCHEMA_ID",
    "MANIFEST_RECORD_SCHEMA_RESOURCE",
    "MANIFEST_RECORD_SCHEMA_VERSION",
    "ArtifactStat",
    "ArtifactVerificationStatus",
    "ManifestBuilderDependencies",
    "ManifestError",
    "ManifestOutputArtifact",
    "ManifestOutputArtifactSpec",
    "ManifestRecord",
    "ManifestRecordStatus",
    "ManifestRequest",
    "ManifestTraceEvent",
    "build_manifest_record",
    "build_manifest_request_fingerprint",
    "generated_manifest_record_json_schema",
    "manifest_record_json_schema",
    "parse_manifest_record",
    "snapshot_output_artifact",
]
