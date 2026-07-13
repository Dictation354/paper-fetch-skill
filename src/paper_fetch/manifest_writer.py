"""Durable run manifests, append-only attempts, and read-only audits."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from types import TracebackType
from typing import Literal, TextIO
from uuid import UUID, uuid5

from filelock import FileLock
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from .artifacts import ArtifactStore, artifact_file_lock_path
from .manifest import (
    ArtifactVerificationStatus,
    ManifestRecord,
    ManifestRecordStatus,
    ManifestRequest,
    build_manifest_request_fingerprint,
    parse_manifest_record,
)
from .mcp.markdown_frontmatter import read_markdown_front_matter
from .publisher_identity import normalize_doi
from .workflow.acceptance import (
    AssetAcceptanceStatus,
    ContentAcceptanceStatus,
    FetchAcceptanceStatus,
    IdentityAcceptanceStatus,
    OutputAcceptanceStatus,
    OverallAcceptanceStatus,
)

RUN_MANIFEST_SCHEMA_VERSION = 1
RUN_MANIFEST_MIN_READER_VERSION = 1


class ManifestPersistenceError(ValueError):
    """Raised when durable manifest state cannot be safely read or written."""


class RunManifestState(StrEnum):
    """Lifecycle state of one durable batch run."""

    RUNNING = "running"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ManifestAuditStatus(StrEnum):
    """Stable top-level outcome of a read-only manifest inspection."""

    OK = "ok"
    MANIFEST_STALE = "manifest_stale"
    INVALID = "invalid"


AuditSeverity = Literal["stale", "invalid"]


class _PersistenceModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class RunManifestInput(_PersistenceModel):
    index: int = Field(ge=1)
    query: str = Field(min_length=1)


class RunStatusCounts(_PersistenceModel):
    record_statuses: dict[str, int] = Field(default_factory=dict)
    acceptance: dict[str, int] = Field(default_factory=dict)

    @field_validator("record_statuses", "acceptance")
    @classmethod
    def validate_counts(cls, value: dict[str, int]) -> dict[str, int]:
        if any(count < 0 for count in value.values()):
            raise ValueError("run status counts cannot be negative")
        return dict(sorted(value.items()))


class RunManifest(_PersistenceModel):
    """Atomic run summary pointing at append-only attempt events."""

    schema_version: Literal[1]
    minimum_reader_schema_version: Literal[1]
    run_id: UUID
    tool_version: str = Field(min_length=1)
    inputs: tuple[RunManifestInput, ...]
    query_count: int = Field(ge=1)
    request_parameters: dict[str, JsonValue]
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    started_at: AwareDatetime
    completed_at: AwareDatetime | None = None
    state: RunManifestState
    events_path: str = Field(min_length=1)
    attempt_count: int = Field(default=0, ge=0)
    status_counts: RunStatusCounts = Field(default_factory=RunStatusCounts)

    @model_validator(mode="after")
    def validate_run_contract(self) -> RunManifest:
        if self.query_count != len(self.inputs):
            raise ValueError("query_count must equal the number of ordered inputs")
        if [item.index for item in self.inputs] != list(range(1, self.query_count + 1)):
            raise ValueError("run input indices must be the complete ordered 1..N set")
        if self.request_fingerprint != build_run_request_fingerprint(
            self.inputs, self.request_parameters
        ):
            raise ValueError("run request_fingerprint does not match inputs/config")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at must not precede started_at")
        if self.state == RunManifestState.RUNNING and self.completed_at is not None:
            raise ValueError("running run manifests cannot have completed_at")
        if self.state != RunManifestState.RUNNING and self.completed_at is None:
            raise ValueError("terminal run manifests require completed_at")
        return self

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)


class ManifestAuditFinding(_PersistenceModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: AuditSeverity = "stale"
    index: int | None = Field(default=None, ge=1)
    attempt: int | None = Field(default=None, ge=1)
    path: str | None = None


class ManifestArtifactAudit(_PersistenceModel):
    path: str
    kind: str
    current_path: str
    status: Literal["ok", "stale"]
    findings: tuple[ManifestAuditFinding, ...] = ()


class ManifestRecordAudit(_PersistenceModel):
    index: int = Field(ge=1)
    attempt: int = Field(ge=1)
    record_id: UUID
    reusable: bool
    findings: tuple[ManifestAuditFinding, ...] = ()
    artifacts: tuple[ManifestArtifactAudit, ...] = ()


class ManifestAuditReport(_PersistenceModel):
    schema_version: Literal[1] = 1
    mode: Literal["audit", "reconcile"]
    manifest_path: str
    manifest_kind: Literal["run", "single", "unknown"]
    status: ManifestAuditStatus
    run_id: UUID | None = None
    run_state: RunManifestState | None = None
    query_count: int = Field(default=0, ge=0)
    record_count: int = Field(default=0, ge=0)
    unique_index_count: int = Field(default=0, ge=0)
    latest_record_count: int = Field(default=0, ge=0)
    missing_indices: tuple[int, ...] = ()
    reusable_indices: tuple[int, ...] = ()
    retry_indices: tuple[int, ...] = ()
    findings: tuple[ManifestAuditFinding, ...] = ()
    records: tuple[ManifestRecordAudit, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)


def serialize_manifest_record(
    record: ManifestRecord, *, indent: int | None = None
) -> str:
    """Serialize one schema-v2 record without duplicating its field projection."""

    return record.model_dump_json(indent=indent)


def write_manifest_record(
    path: Path,
    record: ManifestRecord,
    *,
    overwrite: bool = True,
) -> Path:
    """Atomically replace a single-record manifest behind a path lock."""

    return ArtifactStore.from_download_dir(path.parent).write_text_file(
        path,
        f"{serialize_manifest_record(record, indent=2)}\n",
        encoding="utf-8",
        overwrite=overwrite,
        use_lock=True,
    )


def build_run_request_fingerprint(
    inputs: Sequence[RunManifestInput | str],
    request_parameters: Mapping[str, JsonValue],
) -> str:
    """Hash the complete ordered input set and shared request configuration."""

    normalized_inputs = [
        item.model_dump(mode="json")
        if isinstance(item, RunManifestInput)
        else {"index": index, "query": str(item)}
        for index, item in enumerate(inputs, start=1)
    ]
    encoded = json.dumps(
        {
            "inputs": normalized_inputs,
            "request_parameters": dict(request_parameters),
        },
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def deterministic_manifest_record_id(run_id: UUID, *, index: int, attempt: int) -> UUID:
    """Derive the unique stable record ID for one run/index/attempt tuple."""

    if index < 1 or attempt < 1:
        raise ValueError("manifest index and attempt must be positive")
    return uuid5(run_id, f"paper-fetch-record:{index}:{attempt}")


def create_run_manifest(
    *,
    run_id: UUID,
    tool_version: str,
    queries: Sequence[str],
    request_parameters: Mapping[str, JsonValue],
    started_at: datetime,
    events_path: str,
) -> RunManifest:
    inputs = tuple(
        RunManifestInput(index=index, query=query)
        for index, query in enumerate(queries, start=1)
    )
    return RunManifest(
        schema_version=RUN_MANIFEST_SCHEMA_VERSION,
        minimum_reader_schema_version=RUN_MANIFEST_MIN_READER_VERSION,
        run_id=run_id,
        tool_version=tool_version,
        inputs=inputs,
        query_count=len(inputs),
        request_parameters=dict(request_parameters),
        request_fingerprint=build_run_request_fingerprint(inputs, request_parameters),
        started_at=started_at,
        state=RunManifestState.RUNNING,
        events_path=events_path,
    )


def latest_manifest_records(
    records: Sequence[ManifestRecord],
) -> dict[int, ManifestRecord]:
    """Return the highest attempt for each input index."""

    latest: dict[int, ManifestRecord] = {}
    for record in records:
        previous = latest.get(record.index)
        if previous is None or record.attempt > previous.attempt:
            latest[record.index] = record
    return latest


def summarize_run_records(records: Sequence[ManifestRecord]) -> RunStatusCounts:
    latest = latest_manifest_records(records)
    return RunStatusCounts(
        record_statuses=dict(
            Counter(record.record_status.value for record in latest.values())
        ),
        acceptance=dict(
            Counter(record.acceptance.overall.value for record in latest.values())
        ),
    )


def checkpoint_run_manifest(
    manifest: RunManifest, records: Sequence[ManifestRecord]
) -> RunManifest:
    return manifest.model_copy(
        update={
            "state": RunManifestState.RUNNING,
            "completed_at": None,
            "attempt_count": len(records),
            "status_counts": summarize_run_records(records),
        }
    )


def terminal_run_manifest(
    manifest: RunManifest,
    records: Sequence[ManifestRecord],
    *,
    state: RunManifestState,
    completed_at: datetime,
) -> RunManifest:
    if state == RunManifestState.RUNNING:
        raise ValueError("terminal run manifest requires a terminal state")
    return manifest.model_copy(
        update={
            "state": state,
            "completed_at": completed_at,
            "attempt_count": len(records),
            "status_counts": summarize_run_records(records),
        }
    )


def _stored_events_path(manifest_path: Path, events_path: Path) -> str:
    manifest_parent = manifest_path.parent.resolve(strict=False)
    resolved_events = events_path.resolve(strict=False)
    try:
        return str(resolved_events.relative_to(manifest_parent))
    except ValueError:
        return str(resolved_events)


def resolve_run_events_path(manifest_path: Path, events_path: str) -> Path:
    path = Path(events_path).expanduser()
    return path if path.is_absolute() else manifest_path.parent / path


@dataclass(frozen=True)
class RunManifestStore:
    """Filesystem adapter for one atomic summary plus its append-only events."""

    manifest_path: Path
    events_path: Path

    @classmethod
    def for_new_run(cls, *, manifest_path: Path, events_path: Path) -> RunManifestStore:
        return cls(
            manifest_path=manifest_path.expanduser(),
            events_path=events_path.expanduser(),
        )

    @classmethod
    def from_manifest(cls, manifest_path: Path) -> RunManifestStore:
        manifest_path = manifest_path.expanduser()
        manifest = read_run_manifest(manifest_path)
        return cls(
            manifest_path=manifest_path,
            events_path=resolve_run_events_path(manifest_path, manifest.events_path),
        )

    @property
    def run_lock_path(self) -> Path:
        return artifact_file_lock_path(self.manifest_path, scope="run")

    def run_lock(self) -> FileLock:
        self.run_lock_path.parent.mkdir(parents=True, exist_ok=True)
        return FileLock(str(self.run_lock_path))

    def events_reference(self) -> str:
        return _stored_events_path(self.manifest_path, self.events_path)

    def read(self) -> RunManifest:
        return read_run_manifest(self.manifest_path)

    def read_records(self) -> list[ManifestRecord]:
        return read_manifest_events(self.events_path)

    def create(self, manifest: RunManifest, *, overwrite: bool = False) -> RunManifest:
        referenced = resolve_run_events_path(
            self.manifest_path, manifest.events_path
        ).resolve(strict=False)
        if referenced != self.events_path.resolve(strict=False):
            raise ManifestPersistenceError(
                "run manifest events_path does not match the selected event file"
            )
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        ArtifactStore.from_download_dir(self.manifest_path.parent).write_text_file(
            self.manifest_path,
            f"{manifest.to_json()}\n",
            encoding="utf-8",
            overwrite=overwrite,
            use_lock=True,
        )
        return manifest

    def write(self, manifest: RunManifest) -> RunManifest:
        ArtifactStore.from_download_dir(self.manifest_path.parent).write_text_file(
            self.manifest_path,
            f"{manifest.to_json()}\n",
            encoding="utf-8",
            overwrite=True,
            use_lock=True,
        )
        return manifest

    def append_record(self, record: ManifestRecord) -> None:
        with ManifestJsonlWriter(self.events_path, append=True) as writer:
            writer.write(record)


class ManifestJsonlWriter:
    """Write and fsync completion-ordered records under a path-scoped lock."""

    def __init__(
        self,
        path: Path,
        *,
        append: bool = False,
        overwrite: bool = True,
    ) -> None:
        self.path = path
        self.append = append
        self.overwrite = overwrite
        self._stream: TextIO | None = None
        self._lock: FileLock | None = None

    def __enter__(self) -> ManifestJsonlWriter:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = artifact_file_lock_path(self.path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = FileLock(str(lock_path))
        self._lock.acquire()
        try:
            if self.append:
                self._stream = self.path.open("a", encoding="utf-8")
            elif self.overwrite:
                self._stream = self.path.open("w", encoding="utf-8")
            else:
                self._stream = self.path.open("x", encoding="utf-8")
        except Exception:
            self._lock.release()
            self._lock = None
            raise
        return self

    def write(self, record: ManifestRecord) -> None:
        if self._stream is None:
            raise RuntimeError("ManifestJsonlWriter must be opened before writing.")
        self._stream.write(f"{serialize_manifest_record(record)}\n")
        self._stream.flush()
        os.fsync(self._stream.fileno())

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        try:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
        finally:
            if self._lock is not None:
                self._lock.release()
                self._lock = None


def read_run_manifest(path: Path) -> RunManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestPersistenceError(
            f"could not read run manifest {path}: {exc}"
        ) from exc
    try:
        return RunManifest.model_validate(payload)
    except ValueError as exc:
        raise ManifestPersistenceError(f"invalid run manifest {path}: {exc}") from exc


def read_manifest_events(path: Path) -> list[ManifestRecord]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ManifestPersistenceError(
            f"could not read manifest events {path}: {exc}"
        ) from exc
    records: list[ManifestRecord] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            records.append(parse_manifest_record(json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ManifestPersistenceError(
                f"invalid manifest event at {path}:{line_number}: {exc}"
            ) from exc
    return records


def _finding(
    code: str,
    message: str,
    *,
    severity: AuditSeverity = "stale",
    record: ManifestRecord | None = None,
    path: str | None = None,
) -> ManifestAuditFinding:
    return ManifestAuditFinding(
        code=code,
        message=message,
        severity=severity,
        index=record.index if record is not None else None,
        attempt=record.attempt if record is not None else None,
        path=path,
    )


def _current_artifact_path(raw_path: str, *, manifest_path: Path) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute() or path.exists():
        return path
    return manifest_path.parent / path


def _artifact_sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _audit_artifact(
    record: ManifestRecord,
    artifact,
    *,
    manifest_path: Path,
) -> ManifestArtifactAudit:
    current_path = _current_artifact_path(artifact.path, manifest_path=manifest_path)
    findings: list[ManifestAuditFinding] = []
    if artifact.verification_status != ArtifactVerificationStatus.VERIFIED:
        findings.append(
            _finding(
                "recorded_artifact_not_verified",
                "the attempt did not record a verified artifact",
                record=record,
                path=artifact.path,
            )
        )
    try:
        stat = current_path.stat()
    except FileNotFoundError:
        findings.append(
            _finding(
                "artifact_missing",
                "the recorded output file no longer exists",
                record=record,
                path=artifact.path,
            )
        )
    except OSError as exc:
        findings.append(
            _finding(
                "artifact_unreadable",
                f"the recorded output cannot be inspected: {exc}",
                record=record,
                path=artifact.path,
            )
        )
    else:
        if artifact.size is None or stat.st_size != artifact.size:
            findings.append(
                _finding(
                    "artifact_size_mismatch",
                    "the current output size differs from the recorded size",
                    record=record,
                    path=artifact.path,
                )
            )
        try:
            current_hash = _artifact_sha256(current_path)
        except OSError as exc:
            findings.append(
                _finding(
                    "artifact_unreadable",
                    f"the current output hash cannot be computed: {exc}",
                    record=record,
                    path=artifact.path,
                )
            )
        else:
            if artifact.sha256 is None or current_hash != artifact.sha256:
                findings.append(
                    _finding(
                        "artifact_hash_mismatch",
                        "the current output SHA256 differs from the recorded SHA256",
                        record=record,
                        path=artifact.path,
                    )
                )

        is_markdown = artifact.kind.endswith("markdown") or (
            current_path.suffix.lower() in {".md", ".markdown"}
            and artifact.kind != "primary_both"
        )
        if is_markdown:
            front_matter = read_markdown_front_matter(current_path)
            if front_matter is None:
                findings.append(
                    _finding(
                        "markdown_front_matter_invalid",
                        "Markdown output lacks structured identity front matter",
                        record=record,
                        path=artifact.path,
                    )
                )
            else:
                expected_doi = normalize_doi(record.doi or "")
                if not expected_doi or front_matter.doi != expected_doi:
                    findings.append(
                        _finding(
                            "markdown_doi_mismatch",
                            "Markdown front matter DOI does not match the attempt identity",
                            record=record,
                            path=artifact.path,
                        )
                    )
                if not record.source or front_matter.source != record.source:
                    findings.append(
                        _finding(
                            "markdown_source_mismatch",
                            "Markdown front matter source does not match attempt provenance",
                            record=record,
                            path=artifact.path,
                        )
                    )
                if front_matter.content_kind != record.acceptance.content.status.value:
                    findings.append(
                        _finding(
                            "markdown_content_kind_mismatch",
                            "Markdown front matter content_kind differs from acceptance",
                            record=record,
                            path=artifact.path,
                        )
                    )
                if front_matter.has_fulltext != record.acceptance.content.has_fulltext:
                    findings.append(
                        _finding(
                            "markdown_fulltext_mismatch",
                            "Markdown front matter has_fulltext differs from acceptance",
                            record=record,
                            path=artifact.path,
                        )
                    )
    return ManifestArtifactAudit(
        path=artifact.path,
        kind=artifact.kind,
        current_path=str(current_path),
        status="stale" if findings else "ok",
        findings=tuple(findings),
    )


def _requested_modes(record: ManifestRecord) -> set[str]:
    value = record.request.parameters.get("modes")
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return {str(item) for item in value}
    return set()


def _strategy_asset_profile(record: ManifestRecord) -> str:
    strategy = record.request.parameters.get("strategy")
    if isinstance(strategy, Mapping):
        value = strategy.get("asset_profile")
        if isinstance(value, str):
            return value
    render = record.request.parameters.get("render")
    if isinstance(render, Mapping):
        value = render.get("asset_profile")
        if isinstance(value, str):
            return value
    return "none"


def _acceptance_findings(record: ManifestRecord) -> list[ManifestAuditFinding]:
    report = record.acceptance
    findings: list[ManifestAuditFinding] = []
    if record.record_status != ManifestRecordStatus.COMPLETED or record.status != "ok":
        return [
            _finding(
                "attempt_not_completed",
                "the latest attempt did not complete successfully",
                record=record,
            )
        ]
    if report.identity.status != IdentityAcceptanceStatus.RESOLVED:
        findings.append(
            _finding(
                "identity_below_request",
                "the accepted identity is not uniquely resolved",
                record=record,
            )
        )
    if report.fetch.status != FetchAcceptanceStatus.OK or not report.fetch.completed:
        findings.append(
            _finding(
                "fetch_below_request",
                "the fetch facet is not complete and ok",
                record=record,
            )
        )
    if _requested_modes(record) & {"article", "markdown"} and (
        report.content.status != ContentAcceptanceStatus.FULLTEXT
    ):
        findings.append(
            _finding(
                "content_below_request",
                "the latest attempt does not provide requested full text",
                record=record,
            )
        )
    if report.output.status in {
        OutputAcceptanceStatus.PARTIAL,
        OutputAcceptanceStatus.MISSING,
    }:
        findings.append(
            _finding(
                "output_below_request",
                "one or more requested in-memory outputs are missing",
                record=record,
            )
        )
    if bool(record.request.parameters.get("primary_output_to_output_dir")) and not (
        record.output_artifacts
    ):
        findings.append(
            _finding(
                "output_artifact_missing",
                "the requested primary archived output was not recorded",
                record=record,
            )
        )
    if _strategy_asset_profile(record) in {"body", "all"}:
        asset = report.asset
        below_request = asset.status in {
            AssetAcceptanceStatus.FAILED,
            AssetAcceptanceStatus.UNAVAILABLE,
            AssetAcceptanceStatus.NOT_REQUESTED,
        } or any(
            value > 0
            for value in (asset.failed, asset.not_archived, asset.placeholder_suspected)
        )
        if below_request:
            findings.append(
                _finding(
                    "asset_below_request",
                    "the requested local asset profile is incomplete",
                    record=record,
                )
            )
    if report.overall in {
        OverallAcceptanceStatus.LIMITED,
        OverallAcceptanceStatus.FAILED,
        OverallAcceptanceStatus.ACTION_REQUIRED,
    }:
        findings.append(
            _finding(
                "acceptance_below_request",
                f"overall acceptance is {report.overall.value}",
                record=record,
            )
        )
    return findings


def audit_manifest_record(
    record: ManifestRecord,
    *,
    manifest_path: Path,
    expected_request_fingerprint: str | None = None,
) -> ManifestRecordAudit:
    findings = _acceptance_findings(record)
    if (
        expected_request_fingerprint is not None
        and record.request_fingerprint != expected_request_fingerprint
    ):
        findings.append(
            _finding(
                "request_fingerprint_mismatch",
                "the attempt request differs from the run configuration",
                severity="invalid",
                record=record,
            )
        )
    artifacts = tuple(
        _audit_artifact(record, artifact, manifest_path=manifest_path)
        for artifact in record.output_artifacts
    )
    for artifact in artifacts:
        findings.extend(artifact.findings)
    return ManifestRecordAudit(
        index=record.index,
        attempt=record.attempt,
        record_id=record.record_id,
        reusable=not findings,
        findings=tuple(findings),
        artifacts=artifacts,
    )


def _expected_record_fingerprint(
    manifest: RunManifest, input_item: RunManifestInput
) -> str:
    return build_manifest_request_fingerprint(
        ManifestRequest(
            query=input_item.query,
            parameters=manifest.request_parameters,
        )
    )


def _invalid_report(
    path: Path,
    *,
    mode: Literal["audit", "reconcile"],
    message: str,
) -> ManifestAuditReport:
    return ManifestAuditReport(
        mode=mode,
        manifest_path=str(path),
        manifest_kind="unknown",
        status=ManifestAuditStatus.INVALID,
        findings=(
            ManifestAuditFinding(
                code="invalid_manifest",
                message=message,
                severity="invalid",
            ),
        ),
    )


def audit_run_manifest(
    manifest_path: Path,
    manifest: RunManifest,
    *,
    mode: Literal["audit", "reconcile"] = "audit",
) -> ManifestAuditReport:
    findings: list[ManifestAuditFinding] = []
    events_path = resolve_run_events_path(manifest_path, manifest.events_path)
    try:
        records = read_manifest_events(events_path)
    except ManifestPersistenceError as exc:
        records = []
        events_exist = events_path.exists()
        findings.append(
            _finding(
                "events_unreadable" if events_exist else "events_missing",
                str(exc),
                severity="invalid" if events_exist else "stale",
                path=str(events_path),
            )
        )

    inputs = {item.index: item for item in manifest.inputs}
    seen_attempts: set[tuple[int, int]] = set()
    seen_record_ids: set[UUID] = set()
    attempts_by_index: dict[int, set[int]] = defaultdict(set)
    structurally_valid: list[ManifestRecord] = []
    for record in records:
        if record.run_id != manifest.run_id:
            findings.append(
                _finding(
                    "record_run_id_mismatch",
                    "attempt run_id differs from the run manifest",
                    severity="invalid",
                    record=record,
                )
            )
        input_item = inputs.get(record.index)
        if input_item is None:
            findings.append(
                _finding(
                    "record_index_out_of_range",
                    "attempt index is outside the complete run input set",
                    severity="invalid",
                    record=record,
                )
            )
        elif record.query != input_item.query:
            findings.append(
                _finding(
                    "record_query_mismatch",
                    "attempt query differs from the ordered run input",
                    severity="invalid",
                    record=record,
                )
            )
        key = (record.index, record.attempt)
        if key in seen_attempts:
            findings.append(
                _finding(
                    "duplicate_index_attempt",
                    "run contains more than one record for the same index/attempt",
                    severity="invalid",
                    record=record,
                )
            )
        else:
            seen_attempts.add(key)
        if record.record_id in seen_record_ids:
            findings.append(
                _finding(
                    "duplicate_record_id",
                    "run contains a duplicate record_id",
                    severity="invalid",
                    record=record,
                )
            )
        else:
            seen_record_ids.add(record.record_id)
        if record.record_id != deterministic_manifest_record_id(
            manifest.run_id,
            index=record.index,
            attempt=record.attempt,
        ):
            findings.append(
                _finding(
                    "record_id_mismatch",
                    "record_id is not the stable run/index/attempt identity",
                    severity="invalid",
                    record=record,
                )
            )
        if record.tool_version != manifest.tool_version:
            findings.append(
                _finding(
                    "record_tool_version_mismatch",
                    "attempt tool version differs from the run manifest",
                    severity="invalid",
                    record=record,
                )
            )
        if input_item is not None and record.request_fingerprint != (
            _expected_record_fingerprint(manifest, input_item)
        ):
            findings.append(
                _finding(
                    "request_fingerprint_mismatch",
                    "attempt request differs from the run configuration",
                    severity="invalid",
                    record=record,
                )
            )
        attempts_by_index[record.index].add(record.attempt)
        structurally_valid.append(record)

    for index, attempts in sorted(attempts_by_index.items()):
        expected = set(range(1, max(attempts) + 1))
        if attempts != expected:
            findings.append(
                ManifestAuditFinding(
                    code="attempt_sequence_incomplete",
                    message="attempt numbers must be the contiguous 1..latest set",
                    severity="invalid",
                    index=index,
                )
            )

    latest = latest_manifest_records(structurally_valid)
    missing_indices = tuple(sorted(set(inputs) - set(latest)))
    for index in missing_indices:
        findings.append(
            ManifestAuditFinding(
                code="record_missing",
                message="run has no terminal attempt for this input index",
                index=index,
            )
        )

    record_audits: list[ManifestRecordAudit] = []
    for index in sorted(latest):
        record = latest[index]
        input_item = inputs.get(index)
        expected_fingerprint = (
            _expected_record_fingerprint(manifest, input_item)
            if input_item is not None
            else None
        )
        audit = audit_manifest_record(
            record,
            manifest_path=manifest_path,
            expected_request_fingerprint=expected_fingerprint,
        )
        record_audits.append(audit)
        findings.extend(audit.findings)

    if manifest.attempt_count != len(records):
        findings.append(
            _finding(
                "attempt_count_mismatch",
                "run summary attempt_count differs from the event record count",
            )
        )
    expected_counts = summarize_run_records(records)
    if manifest.status_counts != expected_counts:
        findings.append(
            _finding(
                "status_counts_mismatch",
                "run summary status counts differ from the latest attempts",
            )
        )
    if manifest.state != RunManifestState.COMPLETED:
        findings.append(
            _finding(
                "run_not_completed",
                f"run state is {manifest.state.value}",
            )
        )

    reusable_indices = tuple(audit.index for audit in record_audits if audit.reusable)
    retry_indices = tuple(sorted(set(inputs) - set(reusable_indices)))
    has_invalid = any(finding.severity == "invalid" for finding in findings)
    status = (
        ManifestAuditStatus.INVALID
        if has_invalid
        else ManifestAuditStatus.MANIFEST_STALE
        if findings
        else ManifestAuditStatus.OK
    )
    return ManifestAuditReport(
        mode=mode,
        manifest_path=str(manifest_path),
        manifest_kind="run",
        status=status,
        run_id=manifest.run_id,
        run_state=manifest.state,
        query_count=manifest.query_count,
        record_count=len(records),
        unique_index_count=len({record.index for record in records}),
        latest_record_count=len(latest),
        missing_indices=missing_indices,
        reusable_indices=reusable_indices,
        retry_indices=retry_indices,
        findings=tuple(findings),
        records=tuple(record_audits),
    )


def audit_single_manifest(
    manifest_path: Path,
    record: ManifestRecord,
    *,
    mode: Literal["audit", "reconcile"] = "audit",
) -> ManifestAuditReport:
    audit = audit_manifest_record(record, manifest_path=manifest_path)
    status = (
        ManifestAuditStatus.OK
        if audit.reusable
        else ManifestAuditStatus.INVALID
        if any(finding.severity == "invalid" for finding in audit.findings)
        else ManifestAuditStatus.MANIFEST_STALE
    )
    return ManifestAuditReport(
        mode=mode,
        manifest_path=str(manifest_path),
        manifest_kind="single",
        status=status,
        run_id=record.run_id,
        query_count=1,
        record_count=1,
        unique_index_count=1,
        latest_record_count=1,
        reusable_indices=(1,) if audit.reusable else (),
        retry_indices=() if audit.reusable else (1,),
        findings=audit.findings,
        records=(audit,),
    )


def audit_manifest_path(
    path: Path,
    *,
    mode: Literal["audit", "reconcile"] = "audit",
) -> ManifestAuditReport:
    """Inspect a run or single manifest without writing files or using network."""

    if mode not in {"audit", "reconcile"}:
        raise ValueError("manifest audit mode must be audit or reconcile")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return _invalid_report(path, mode=mode, message=str(exc))
    if not isinstance(payload, Mapping):
        return _invalid_report(
            path, mode=mode, message="manifest root must be a JSON object"
        )
    if "inputs" in payload and "events_path" in payload:
        try:
            manifest = RunManifest.model_validate(payload)
        except ValueError as exc:
            return _invalid_report(path, mode=mode, message=str(exc))
        return audit_run_manifest(path, manifest, mode=mode)
    try:
        record = parse_manifest_record(payload)
    except ValueError as exc:
        return _invalid_report(path, mode=mode, message=str(exc))
    return audit_single_manifest(path, record, mode=mode)


def manifest_audit_exit_code(report: ManifestAuditReport) -> int:
    return {
        ManifestAuditStatus.OK: 0,
        ManifestAuditStatus.MANIFEST_STALE: 1,
        ManifestAuditStatus.INVALID: 2,
    }[report.status]


__all__ = [
    "ManifestArtifactAudit",
    "ManifestAuditFinding",
    "ManifestAuditReport",
    "ManifestAuditStatus",
    "ManifestJsonlWriter",
    "ManifestPersistenceError",
    "ManifestRecordAudit",
    "RunManifest",
    "RunManifestInput",
    "RunManifestState",
    "RunManifestStore",
    "RunStatusCounts",
    "audit_manifest_path",
    "audit_manifest_record",
    "audit_run_manifest",
    "audit_single_manifest",
    "build_run_request_fingerprint",
    "checkpoint_run_manifest",
    "create_run_manifest",
    "deterministic_manifest_record_id",
    "latest_manifest_records",
    "manifest_audit_exit_code",
    "read_manifest_events",
    "read_run_manifest",
    "resolve_run_events_path",
    "serialize_manifest_record",
    "summarize_run_records",
    "terminal_run_manifest",
    "write_manifest_record",
]
