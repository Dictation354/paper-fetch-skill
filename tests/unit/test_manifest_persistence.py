from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from paper_fetch.manifest import (
    LegacyArtifactField,
    ManifestOutputArtifactSpec,
    build_manifest_record,
)
from paper_fetch.manifest_writer import (
    ManifestAuditStatus,
    RunManifest,
    RunManifestState,
    RunManifestStore,
    audit_manifest_path,
    build_run_request_fingerprint,
    checkpoint_run_manifest,
    create_run_manifest,
    deterministic_manifest_record_id,
    manifest_audit_exit_code,
    read_manifest_events,
    terminal_run_manifest,
    write_manifest_record,
)

from .test_workflow_acceptance import _envelope


RUN_ID = UUID("10000000-0000-4000-8000-000000000001")
STARTED_AT = datetime(2026, 7, 13, 8, 0, tzinfo=UTC)
PARAMETERS = {
    "modes": ["article", "markdown"],
    "format": "markdown",
    "strategy": {"asset_profile": "none"},
    "render": {"asset_profile": "none", "include_refs": "all"},
    "artifact_mode": "none",
    "no_download": True,
    "save_markdown": False,
    "output": "-",
    "output_dir": "papers",
    "primary_output_to_output_dir": True,
}


def _markdown(
    *,
    doi: str,
    source: str = "elsevier_xml",
    content_kind: str = "fulltext",
    has_fulltext: bool = True,
) -> str:
    return f"""---
doi: {doi}
source: {source}
acquisition:
  provider: elsevier
  route: xml_api
  representation: xml
  transport: api
  fallback_used: false
has_fulltext: {str(has_fulltext).lower()}
content_kind: {content_kind}
completed_at: 2026-07-13T08:01:00+00:00
---
# Acceptance Article

Accepted body text.
"""


def _record(
    tmp_path: Path,
    *,
    index: int,
    attempt: int = 1,
    query: str | None = None,
    output_exists: bool = True,
    content_kind: str = "fulltext",
    record_id: UUID | None = None,
):
    query = query or f"10.1000/acceptance-{index}"
    output_path = tmp_path / f"paper-{index}.md"
    envelope = _envelope(content_kind)
    envelope.doi = query
    if envelope.article is not None:
        envelope.article.doi = query
    if output_exists:
        output_path.write_text(
            _markdown(
                doi=query,
                content_kind=content_kind,
                has_fulltext=content_kind == "fulltext",
            ),
            encoding="utf-8",
        )
    return build_manifest_record(
        tool_version="3.1.0",
        run_id=RUN_ID,
        record_id=record_id
        or deterministic_manifest_record_id(RUN_ID, index=index, attempt=attempt),
        index=index,
        attempt=attempt,
        query=query,
        request_parameters=PARAMETERS,
        asset_profile="none",
        envelope=envelope,
        requested_outputs={"article", "markdown"},
        output_artifacts=(
            ManifestOutputArtifactSpec(
                path=str(output_path),
                kind="primary_markdown",
                legacy_field=LegacyArtifactField.OUTPUT_PATH,
            ),
        ),
        started_at=STARTED_AT + timedelta(minutes=index + attempt),
        completed_at=STARTED_AT + timedelta(minutes=index + attempt + 1),
    )


def _store(tmp_path: Path) -> RunManifestStore:
    return RunManifestStore.for_new_run(
        manifest_path=tmp_path / "run-manifest.json",
        events_path=tmp_path / "events.jsonl",
    )


def _manifest(store: RunManifestStore, queries: list[str]) -> RunManifest:
    return create_run_manifest(
        run_id=RUN_ID,
        tool_version="3.1.0",
        queries=queries,
        request_parameters=PARAMETERS,
        started_at=STARTED_AT,
        events_path=store.events_reference(),
    )


def _complete_run(
    store: RunManifestStore,
    manifest: RunManifest,
    records,
) -> RunManifest:
    store.create(manifest, overwrite=False)
    for record in records:
        store.append_record(record)
    return store.write(
        terminal_run_manifest(
            manifest,
            records,
            state=RunManifestState.COMPLETED,
            completed_at=STARTED_AT + timedelta(hours=1),
        )
    )


def test_atomic_run_manifest_and_append_only_events_round_trip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    queries = ["10.1000/acceptance-1", "10.1000/acceptance-2"]
    manifest = _manifest(store, queries)
    records = [_record(tmp_path, index=2), _record(tmp_path, index=1)]

    completed = _complete_run(store, manifest, records)

    assert not store.manifest_path.with_suffix(".json.part").exists()
    assert store.read() == completed
    assert [record.index for record in store.read_records()] == [2, 1]
    assert completed.query_count == 2
    assert completed.attempt_count == 2
    assert completed.status_counts.record_statuses == {"completed": 2}
    assert completed.status_counts.acceptance == {"complete": 2}
    with store.run_lock():
        pass
    assert not list(tmp_path.rglob("*.lock"))
    assert not store.run_lock_path.is_relative_to(tmp_path)


def test_append_records_is_locked_across_concurrent_writers(tmp_path: Path) -> None:
    store = _store(tmp_path)
    records = [_record(tmp_path, index=1), _record(tmp_path, index=2)]

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(store.append_record, records))

    persisted = read_manifest_events(store.events_path)
    assert {record.index for record in persisted} == {1, 2}
    assert len({record.record_id for record in persisted}) == 2


def test_read_only_reconcile_accepts_legal_out_of_order_records(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    queries = ["10.1000/acceptance-1", "10.1000/acceptance-2"]
    records = [_record(tmp_path, index=2), _record(tmp_path, index=1)]
    _complete_run(store, _manifest(store, queries), records)
    before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (store.manifest_path, store.events_path)
    }

    report = audit_manifest_path(store.manifest_path, mode="reconcile")

    assert report.status == ManifestAuditStatus.OK
    assert manifest_audit_exit_code(report) == 0
    assert report.reusable_indices == (1, 2)
    assert report.retry_indices == ()
    assert [audit.index for audit in report.records] == [1, 2]
    assert before == {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (store.manifest_path, store.events_path)
    }


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("missing", "artifact_missing"),
        ("hash", "artifact_hash_mismatch"),
        ("doi", "markdown_doi_mismatch"),
        ("source", "markdown_source_mismatch"),
        ("content", "markdown_content_kind_mismatch"),
    ],
)
def test_reconcile_detects_current_file_drift(
    tmp_path: Path, mutation: str, expected_code: str
) -> None:
    store = _store(tmp_path)
    record = _record(tmp_path, index=1)
    _complete_run(store, _manifest(store, [record.query]), [record])
    output = Path(record.output_path or "")
    if mutation == "missing":
        output.unlink()
    elif mutation == "hash":
        output.write_text(_markdown(doi=record.query) + "changed\n", encoding="utf-8")
    elif mutation == "doi":
        output.write_text(_markdown(doi="10.1000/wrong"), encoding="utf-8")
    elif mutation == "source":
        output.write_text(_markdown(doi=record.query, source="wrong"), encoding="utf-8")
    else:
        output.write_text(
            _markdown(
                doi=record.query,
                content_kind="metadata_only",
                has_fulltext=False,
            ),
            encoding="utf-8",
        )

    report = audit_manifest_path(store.manifest_path)

    codes = {finding.code for finding in report.findings}
    assert report.status == ManifestAuditStatus.MANIFEST_STALE
    assert manifest_audit_exit_code(report) == 1
    assert report.retry_indices == (1,)
    assert expected_code in codes


def test_duplicate_index_attempt_and_record_id_are_invalid(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record = _record(tmp_path, index=1)
    _complete_run(store, _manifest(store, [record.query]), [record, record])

    report = audit_manifest_path(store.manifest_path)

    codes = {finding.code for finding in report.findings}
    assert report.status == ManifestAuditStatus.INVALID
    assert manifest_audit_exit_code(report) == 2
    assert "duplicate_index_attempt" in codes
    assert "duplicate_record_id" in codes


def test_attempt_sequence_gap_is_invalid(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record = _record(tmp_path, index=1, attempt=2)
    _complete_run(store, _manifest(store, [record.query]), [record])

    report = audit_manifest_path(store.manifest_path)

    assert report.status == ManifestAuditStatus.INVALID
    assert "attempt_sequence_incomplete" in {
        finding.code for finding in report.findings
    }


def test_non_deterministic_run_record_id_is_invalid(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record = _record(tmp_path, index=1, record_id=uuid4())
    _complete_run(store, _manifest(store, [record.query]), [record])

    report = audit_manifest_path(store.manifest_path)

    assert report.status == ManifestAuditStatus.INVALID
    assert "record_id_mismatch" in {finding.code for finding in report.findings}


@pytest.mark.parametrize("content_kind", ["metadata_only", "abstract_only"])
def test_below_request_acceptance_is_retried(tmp_path: Path, content_kind: str) -> None:
    store = _store(tmp_path)
    record = _record(tmp_path, index=1, content_kind=content_kind)
    _complete_run(store, _manifest(store, [record.query]), [record])

    report = audit_manifest_path(store.manifest_path)

    assert report.status == ManifestAuditStatus.MANIFEST_STALE
    assert report.reusable_indices == ()
    assert report.retry_indices == (1,)
    assert "content_below_request" in {finding.code for finding in report.findings}


def test_missing_index_and_summary_count_mismatch_are_stale(tmp_path: Path) -> None:
    store = _store(tmp_path)
    manifest = _manifest(store, ["10.1000/acceptance-1", "10.1000/acceptance-2"])
    record = _record(tmp_path, index=1)
    store.create(manifest, overwrite=False)
    store.append_record(record)

    report = audit_manifest_path(store.manifest_path)

    codes = {finding.code for finding in report.findings}
    assert report.status == ManifestAuditStatus.MANIFEST_STALE
    assert report.missing_indices == (2,)
    assert report.retry_indices == (2,)
    assert "attempt_count_mismatch" in codes
    assert "status_counts_mismatch" in codes


def test_missing_events_are_stale_but_malformed_events_are_invalid(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    manifest = _manifest(store, ["10.1000/acceptance-1"])
    record = _record(tmp_path, index=1)
    _complete_run(store, manifest, [record])
    store.events_path.unlink()

    missing = audit_manifest_path(store.manifest_path)

    assert missing.status == ManifestAuditStatus.MANIFEST_STALE
    assert "events_missing" in {finding.code for finding in missing.findings}

    store.events_path.write_text("not json\n", encoding="utf-8")
    malformed = audit_manifest_path(store.manifest_path)
    assert malformed.status == ManifestAuditStatus.INVALID
    assert "events_unreadable" in {finding.code for finding in malformed.findings}


def test_single_manifest_uses_the_same_record_audit(tmp_path: Path) -> None:
    record = _record(tmp_path, index=1)
    manifest_path = tmp_path / "single.manifest.json"
    write_manifest_record(manifest_path, record)

    report = audit_manifest_path(manifest_path, mode="audit")

    assert report.manifest_kind == "single"
    assert report.status == ManifestAuditStatus.OK
    assert report.reusable_indices == (1,)
    Path(record.output_path or "").unlink()
    stale = audit_manifest_path(manifest_path, mode="reconcile")
    assert stale.status == ManifestAuditStatus.MANIFEST_STALE
    assert stale.retry_indices == (1,)


def test_run_fingerprint_covers_input_order_and_configuration() -> None:
    baseline = build_run_request_fingerprint(["a", "b"], PARAMETERS)

    assert baseline == build_run_request_fingerprint(["a", "b"], PARAMETERS)
    assert baseline != build_run_request_fingerprint(["b", "a"], PARAMETERS)
    assert baseline != build_run_request_fingerprint(
        ["a", "b"], {**PARAMETERS, "format": "json"}
    )


def test_run_manifest_rejects_invalid_indices_and_fingerprint() -> None:
    manifest = create_run_manifest(
        run_id=RUN_ID,
        tool_version="3.1.0",
        queries=["a", "b"],
        request_parameters=PARAMETERS,
        started_at=STARTED_AT,
        events_path="events.jsonl",
    )
    payload = manifest.to_dict()
    payload["inputs"] = [
        {"index": 2, "query": "a"},
        {"index": 1, "query": "b"},
    ]
    with pytest.raises(ValidationError, match="complete ordered 1..N"):
        RunManifest.model_validate(payload)

    payload = manifest.to_dict()
    payload["request_fingerprint"] = "0" * 64
    with pytest.raises(ValidationError, match="does not match"):
        RunManifest.model_validate(payload)


def test_store_create_refuses_existing_summary_without_overwrite(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    manifest = _manifest(store, ["a"])
    store.create(manifest)

    with pytest.raises(FileExistsError):
        store.create(manifest)


def test_atomic_manifest_replace_failure_preserves_previous_summary(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    manifest = _manifest(store, ["10.1000/acceptance-1"])
    store.create(manifest)
    before = store.manifest_path.read_bytes()
    record = _record(tmp_path, index=1)

    with mock.patch.object(Path, "replace", side_effect=OSError("disk failed")):
        with pytest.raises(OSError, match="disk failed"):
            store.write(checkpoint_run_manifest(manifest, [record]))

    assert store.manifest_path.read_bytes() == before
    assert not store.manifest_path.with_suffix(".json.part").exists()
    assert store.read() == manifest


def test_interrupted_run_is_auditable_and_reuses_verified_attempts(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    manifest = _manifest(store, ["10.1000/acceptance-1"])
    record = _record(tmp_path, index=1)
    store.create(manifest)
    store.append_record(record)
    store.write(
        terminal_run_manifest(
            manifest,
            [record],
            state=RunManifestState.INTERRUPTED,
            completed_at=STARTED_AT + timedelta(hours=1),
        )
    )

    report = audit_manifest_path(store.manifest_path)

    assert report.status == ManifestAuditStatus.MANIFEST_STALE
    assert report.run_state == RunManifestState.INTERRUPTED
    assert report.reusable_indices == (1,)
    assert report.retry_indices == ()
    assert "run_not_completed" in {finding.code for finding in report.findings}


def test_events_path_is_stored_relative_to_run_manifest(tmp_path: Path) -> None:
    store = RunManifestStore.for_new_run(
        manifest_path=tmp_path / "run" / "run-manifest.json",
        events_path=tmp_path / "run" / "events.jsonl",
    )
    manifest = _manifest(store, ["a"])

    assert manifest.events_path == "events.jsonl"
