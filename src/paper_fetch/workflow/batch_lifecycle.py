"""Shared durable batch-run preparation and manifest lifecycle.

CLI and MCP own their transport-specific requests and result payloads.  This
module owns the invariant run rules: create/resume validation, audited reuse,
attempt numbering, overwrite protection, checkpointing, and terminalization.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Generic, Protocol, TypeVar
from uuid import UUID

from ..manifest import ManifestRecord
from ..manifest_writer import (
    ManifestAuditStatus,
    ManifestJsonlWriter,
    RunManifest,
    RunManifestState,
    RunManifestStore,
    audit_manifest_path,
    build_run_request_fingerprint,
    checkpoint_run_manifest,
    create_run_manifest,
    latest_manifest_records,
    terminal_run_manifest,
)


class BatchLifecycleResumeError(ValueError):
    """The selected durable run cannot be safely resumed."""


class BatchLifecycleOverwriteError(FileExistsError):
    """A batch lifecycle operation would replace an existing artifact."""


class BatchLifecycleItem(Protocol):
    """Minimum item surface needed by lifecycle terminalization."""

    @property
    def index(self) -> int: ...

    @property
    def attempt(self) -> int: ...


ItemT = TypeVar("ItemT", bound=BatchLifecycleItem)


@dataclass(frozen=True, slots=True)
class BatchRunPreparation(Generic[ItemT]):
    """Validated starting state shared by CLI and MCP adapters."""

    manifest: RunManifest
    records: list[ManifestRecord]
    items: list[ItemT]
    run_id: UUID
    append_events: bool
    reused_count: int


def recorded_output_path(raw_path: str, *, manifest_path: Path) -> Path:
    """Resolve a recorded relative artifact beside its durable run manifest."""

    path = Path(raw_path).expanduser()
    if path.is_absolute() or path.exists():
        return path
    return manifest_path.parent / path


def _resume_items(
    *,
    queries: Sequence[str],
    records: Sequence[ManifestRecord],
    reusable_indices: set[int],
    item_factory: Callable[[int, str, int], ItemT],
) -> list[ItemT]:
    latest = latest_manifest_records(records)
    return [
        item_factory(
            index,
            query,
            latest[index].attempt + 1 if index in latest else 1,
        )
        for index, query in enumerate(queries, start=1)
        if index not in reusable_indices
    ]


def _existing_retry_outputs(
    *,
    items: Sequence[ItemT],
    records: Sequence[ManifestRecord],
    manifest_path: Path,
) -> list[str]:
    latest = latest_manifest_records(records)
    return sorted(
        {
            str(path)
            for item in items
            if (previous := latest.get(item.index)) is not None
            for artifact in previous.output_artifacts
            if (
                path := recorded_output_path(
                    artifact.path,
                    manifest_path=manifest_path,
                )
            ).exists()
        }
    )


def prepare_batch_run(
    *,
    store: RunManifestStore | None,
    queries: Sequence[str],
    request_parameters: Mapping[str, Any],
    tool_version: str,
    requested_run_id: UUID | None,
    resume: bool,
    overwrite: bool,
    clock: Callable[[], datetime],
    uuid_factory: Callable[[], UUID],
    item_factory: Callable[[int, str, int], ItemT],
) -> BatchRunPreparation[ItemT]:
    """Create or validate one run and return the exact items still requiring work."""

    if resume:
        if store is None:
            raise BatchLifecycleResumeError(
                "resume did not resolve a run manifest store"
            )
        manifest = store.read()
        if requested_run_id is not None and requested_run_id != manifest.run_id:
            raise BatchLifecycleResumeError(
                "requested run_id differs from the recorded run"
            )
        if [item.query for item in manifest.inputs] != list(queries):
            raise BatchLifecycleResumeError(
                "queries differ from the recorded run; create a new run instead"
            )
        if (
            build_run_request_fingerprint(queries, request_parameters)
            != manifest.request_fingerprint
        ):
            raise BatchLifecycleResumeError(
                "critical fetch/output configuration differs from the recorded run; "
                "create a new run instead"
            )
        if manifest.tool_version != tool_version:
            raise BatchLifecycleResumeError(
                "tool version differs from the recorded run; create a new run instead"
            )
        report = audit_manifest_path(store.manifest_path, mode="audit")
        if report.status is ManifestAuditStatus.INVALID:
            raise BatchLifecycleResumeError(
                "run manifest is structurally invalid and cannot be resumed"
            )
        records = store.read_records() if store.events_path.is_file() else []
        items = _resume_items(
            queries=queries,
            records=records,
            reusable_indices=set(report.reusable_indices),
            item_factory=item_factory,
        )
        if not overwrite:
            existing_outputs = _existing_retry_outputs(
                items=items,
                records=records,
                manifest_path=store.manifest_path,
            )
            if existing_outputs:
                raise BatchLifecycleOverwriteError(
                    "resume would replace existing stale or below-request output; "
                    "review it and enable overwrite: " + ", ".join(existing_outputs)
                )
        manifest = store.write(checkpoint_run_manifest(manifest, records))
        return BatchRunPreparation(
            manifest=manifest,
            records=records,
            items=items,
            run_id=manifest.run_id,
            append_events=True,
            reused_count=len(queries) - len(items),
        )

    if store is not None:
        if store.manifest_path.exists() and not overwrite:
            raise BatchLifecycleOverwriteError(
                f"run manifest already exists at {store.manifest_path}; "
                "enable overwrite or choose another path"
            )
        if store.events_path.exists() and not overwrite:
            raise BatchLifecycleOverwriteError(
                f"batch event file already exists at {store.events_path}; "
                "enable overwrite or choose another path"
            )
    run_id = requested_run_id or uuid_factory()
    manifest = create_run_manifest(
        run_id=run_id,
        tool_version=tool_version,
        queries=queries,
        request_parameters=request_parameters,
        started_at=clock(),
        events_path=store.events_reference() if store is not None else "<memory>",
    )
    if store is not None:
        manifest = store.create(manifest, overwrite=overwrite)
    items = [
        item_factory(index, query, 1) for index, query in enumerate(queries, start=1)
    ]
    return BatchRunPreparation(
        manifest=manifest,
        records=[],
        items=items,
        run_id=run_id,
        append_events=False,
        reused_count=0,
    )


@dataclass(slots=True)
class BatchManifestJournal:
    """Append attempts and atomically checkpoint/terminalize their run summary."""

    manifest: RunManifest
    records: list[ManifestRecord]
    store: RunManifestStore | None = None
    record_sequences: dict[tuple[int, int], int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.record_sequences:
            self.record_sequences.update(
                {
                    (record.index, record.attempt): sequence
                    for sequence, record in enumerate(self.records, start=1)
                }
            )

    def persist(
        self,
        record: ManifestRecord,
        *,
        writer: ManifestJsonlWriter | None = None,
    ) -> None:
        """Persist one event, update sequence metadata, and checkpoint the run."""

        if writer is not None:
            writer.write(record)
        elif self.store is not None:
            self.store.append_record(record)
        self.records.append(record)
        self.record_sequences[(record.index, record.attempt)] = len(self.records)
        if self.store is not None:
            self.manifest = self.store.write(
                checkpoint_run_manifest(self.manifest, self.records)
            )

    def terminalize_missing(
        self,
        items: Sequence[ItemT],
        record_factory: Callable[[ItemT], ManifestRecord],
    ) -> None:
        """Create one aborted attempt for every prepared item still lacking a record."""

        latest = latest_manifest_records(self.records)
        for item in items:
            previous = latest.get(item.index)
            if previous is not None and previous.attempt >= item.attempt:
                continue
            self.persist(record_factory(item))

    def require_complete(self, query_count: int) -> dict[int, ManifestRecord]:
        """Return latest records only when every ordered input is terminal."""

        latest = latest_manifest_records(self.records)
        if set(latest) != set(range(1, query_count + 1)):
            raise RuntimeError(
                "batch run does not have one latest terminal attempt per input"
            )
        return latest

    def finish(
        self,
        *,
        state: RunManifestState,
        completed_at: datetime,
    ) -> RunManifest:
        """Write and return the terminal run manifest."""

        self.manifest = terminal_run_manifest(
            self.manifest,
            self.records,
            state=state,
            completed_at=completed_at,
        )
        if self.store is not None:
            self.manifest = self.store.write(self.manifest)
        return self.manifest


__all__ = [
    "BatchLifecycleOverwriteError",
    "BatchLifecycleResumeError",
    "BatchManifestJournal",
    "BatchRunPreparation",
    "prepare_batch_run",
    "recorded_output_path",
]
