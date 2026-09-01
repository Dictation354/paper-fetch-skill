"""Current manifest record serialization and atomic writes."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid5

from .artifacts import ArtifactStore
from .manifest import ManifestRecord


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
    """Atomically replace a single-record manifest."""

    return ArtifactStore.from_download_dir(path.parent).write_text_file(
        path,
        f"{serialize_manifest_record(record, indent=2)}\n",
        encoding="utf-8",
        overwrite=overwrite,
    )


def deterministic_manifest_record_id(run_id: UUID, *, index: int, attempt: int) -> UUID:
    """Derive the stable record ID for one run/index/attempt tuple."""

    if index < 1 or attempt < 1:
        raise ValueError("manifest index and attempt must be positive")
    return uuid5(run_id, f"paper-fetch-record:{index}:{attempt}")


__all__ = [
    "deterministic_manifest_record_id",
    "serialize_manifest_record",
    "write_manifest_record",
]
