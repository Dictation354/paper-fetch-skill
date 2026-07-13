from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from paper_fetch.manifest import (
    MANIFEST_RECORD_SCHEMA_VERSION,
    ArtifactVerificationStatus,
    LegacyArtifactField,
    ManifestBuilderDependencies,
    ManifestOutputArtifactSpec,
    ManifestRecordStatus,
    build_manifest_record,
    build_manifest_request_fingerprint,
    generated_manifest_record_json_schema,
    manifest_record_json_schema,
    parse_manifest_record,
)
from paper_fetch.reason_codes import METADATA_ONLY, PDF_FALLBACK
from paper_fetch.tracing import trace_event
from paper_fetch.workflow.acceptance import OverallAcceptanceStatus

from .test_workflow_acceptance import _envelope

RUN_ID = UUID("10000000-0000-4000-8000-000000000001")
RECORD_ID = UUID("20000000-0000-4000-8000-000000000002")
STARTED_AT = datetime(2026, 7, 10, 8, 0, tzinfo=UTC)
COMPLETED_AT = datetime(2026, 7, 10, 8, 1, tzinfo=UTC)
ARTIFACT_MTIME = datetime(2026, 7, 10, 7, 59, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


@dataclass(frozen=True)
class _Stat:
    st_size: int
    st_mtime: float


def _deps(
    *,
    sizes: dict[str, int] | None = None,
    hashes: dict[str, str] | None = None,
) -> ManifestBuilderDependencies:
    sizes = sizes or {}
    hashes = hashes or {}

    def stat(path: Path) -> _Stat:
        if path.name == "missing.bin":
            raise FileNotFoundError(path)
        if path.name == "unreadable.bin":
            return _Stat(st_size=17, st_mtime=ARTIFACT_MTIME.timestamp())
        return _Stat(
            st_size=sizes.get(str(path), 23),
            st_mtime=ARTIFACT_MTIME.timestamp(),
        )

    def sha256(path: Path) -> str:
        if path.name == "unreadable.bin":
            raise PermissionError(path)
        return hashes.get(str(path), HASH_A)

    return ManifestBuilderDependencies(
        clock=lambda: COMPLETED_AT,
        uuid_factory=lambda: RECORD_ID,
        stat=stat,
        sha256=sha256,
    )


def _build_success(**overrides):
    values = {
        "tool_version": "3.1.0",
        "run_id": RUN_ID,
        "record_id": RECORD_ID,
        "index": 1,
        "attempt": 1,
        "query": "10.1000/acceptance",
        "request_parameters": {
            "modes": ["article", "markdown"],
            "strategy": {"asset_profile": "none"},
        },
        "asset_profile": "none",
        "envelope": _envelope(),
        "requested_outputs": {"article", "markdown"},
        "started_at": STARTED_AT,
        "completed_at": COMPLETED_AT,
        "deps": _deps(),
    }
    values.update(overrides)
    return build_manifest_record(**values)


def test_complete_record_derives_identity_acceptance_trace_and_legacy_projection() -> (
    None
):
    primary = "/archive/论文-正文.md"
    saved = "/archive/论文-保存副本.md"
    record = _build_success(
        query="  DOI:10.1000/ACCEPTANCE — 气候响应  ",
        request_parameters={
            "modes": ["markdown", "article"],
            "include_refs": "all",
            "locale": "简体中文",
        },
        output_artifacts=(
            ManifestOutputArtifactSpec(
                path=primary,
                kind="primary_markdown",
                legacy_field=LegacyArtifactField.OUTPUT_PATH,
            ),
            ManifestOutputArtifactSpec(
                path=saved,
                kind="saved_markdown",
                legacy_field=LegacyArtifactField.SAVED_MARKDOWN_PATH,
            ),
        ),
        deps=_deps(
            sizes={primary: 101, saved: 102},
            hashes={primary: HASH_A, saved: HASH_B},
        ),
    )

    assert record.schema_version == MANIFEST_RECORD_SCHEMA_VERSION == 2
    assert record.record_status == ManifestRecordStatus.COMPLETED
    assert record.status == "ok"
    assert record.query == "  DOI:10.1000/ACCEPTANCE — 气候响应  "
    assert record.identity == record.acceptance.identity
    assert record.doi == "10.1000/acceptance"
    assert record.source == "elsevier_xml"
    assert record.acceptance.overall == OverallAcceptanceStatus.COMPLETE
    assert record.trace[0].stage == "fulltext"
    assert record.fallback_codes == ()
    assert record.warning_codes == ()
    assert record.asset_summary == record.acceptance.asset
    assert [artifact.verification_status for artifact in record.output_artifacts] == [
        ArtifactVerificationStatus.VERIFIED,
        ArtifactVerificationStatus.VERIFIED,
    ]
    assert [artifact.size for artifact in record.output_artifacts] == [101, 102]
    assert [artifact.sha256 for artifact in record.output_artifacts] == [
        HASH_A,
        HASH_B,
    ]
    assert all(artifact.mtime == ARTIFACT_MTIME for artifact in record.output_artifacts)
    assert all(
        artifact.completed_at == COMPLETED_AT for artifact in record.output_artifacts
    )

    legacy = record.legacy_projection().to_dict()
    assert list(legacy) == [
        "index",
        "query",
        "status",
        "doi",
        "source",
        "output_path",
        "saved_markdown_path",
        "warnings",
        "error",
    ]
    assert legacy == {
        "index": 1,
        "query": "  DOI:10.1000/ACCEPTANCE — 气候响应  ",
        "status": "ok",
        "doi": "10.1000/acceptance",
        "source": "elsevier_xml",
        "output_path": primary,
        "saved_markdown_path": saved,
        "warnings": [],
        "error": None,
    }


def test_degraded_record_reuses_structured_trace_and_never_classifies_warning_text() -> (
    None
):
    envelope = _envelope(
        warnings=["metadata fallback formula missing no_access is arbitrary prose"],
        trace=[
            trace_event(
                "fulltext",
                "elsevier_html",
                "fail",
                code="html_unavailable",
                message="human detail is not a classifier",
            ),
            trace_event(
                "fallback",
                "elsevier_pdf",
                "ok",
                code=PDF_FALLBACK,
            ),
        ],
    )
    record = _build_success(envelope=envelope)

    assert record.acceptance.overall == OverallAcceptanceStatus.DEGRADED
    assert set(record.fallback_codes) == {"html_unavailable", PDF_FALLBACK}
    assert record.warning_codes == ()
    assert record.failure_codes == ("html_unavailable",)
    assert record.warnings == (
        "metadata fallback formula missing no_access is arbitrary prose",
    )
    assert METADATA_ONLY not in record.fallback_codes


def test_limited_metadata_record_keeps_legacy_status_ok() -> None:
    record = _build_success(
        envelope=_envelope("metadata_only", include_markdown=False),
        requested_outputs={"article"},
        request_parameters={"modes": ["article"]},
    )

    assert record.status == "ok"
    assert record.record_status == ManifestRecordStatus.COMPLETED
    assert record.acceptance.overall == OverallAcceptanceStatus.LIMITED
    assert record.acceptance.content.status == "metadata_only"
    assert record.acceptance.content.has_fulltext is False


def test_failed_record_preserves_structured_error_and_legacy_shape() -> None:
    error = {
        "status": "error",
        "reason": "provider failed",
        "code": "provider_error",
        "http_status": 503,
        "warnings": ["重试稍后进行"],
        "source_trail": ["fulltext:provider_fail"],
    }
    record = build_manifest_record(
        tool_version="3.1.0",
        run_id=RUN_ID,
        record_id=RECORD_ID,
        index=2,
        attempt=3,
        query="失败论文",
        request_parameters={"modes": ["article"]},
        asset_profile="body",
        error=error,
        source="publisher_api",
        started_at=STARTED_AT,
        completed_at=COMPLETED_AT,
        deps=_deps(),
    )

    assert record.record_status == ManifestRecordStatus.FAILED
    assert record.status == "error"
    assert record.acceptance.overall == OverallAcceptanceStatus.FAILED
    assert record.failure_codes == ("provider_error",)
    assert record.warnings == ("重试稍后进行",)
    assert record.trace[0].stage == "fulltext"
    assert record.error is not None
    assert record.error.model_dump(mode="json") == error
    assert record.legacy_projection().to_dict()["error"] == error


def test_aborted_record_is_distinct_from_failure() -> None:
    record = build_manifest_record(
        tool_version="3.1.0",
        run_id=RUN_ID,
        record_id=RECORD_ID,
        index=3,
        attempt=1,
        query="cancel me",
        request_parameters={},
        asset_profile="none",
        error={
            "status": "aborted",
            "reason": "cooperative cancellation",
            "code": "request_cancelled",
        },
        aborted=True,
        started_at=STARTED_AT,
        completed_at=COMPLETED_AT,
        deps=_deps(),
    )

    assert record.record_status == ManifestRecordStatus.ABORTED
    assert record.status == "aborted"
    assert record.acceptance.fetch.completed is False
    assert record.failure_codes == ("request_cancelled",)


def test_completed_in_memory_result_can_have_no_output_artifacts() -> None:
    record = _build_success(output_artifacts=())

    assert record.output_artifacts == ()
    assert record.output_path is None
    assert record.saved_markdown_path is None
    assert record.acceptance.output.status == "complete"


def test_multiple_artifacts_capture_verified_missing_and_unreadable_states() -> None:
    record = _build_success(
        output_artifacts=(
            ManifestOutputArtifactSpec(path="article.md", kind="markdown"),
            ManifestOutputArtifactSpec(path="missing.bin", kind="asset"),
            ManifestOutputArtifactSpec(path="unreadable.bin", kind="asset"),
        )
    )

    verified, missing, unreadable = record.output_artifacts
    assert verified.verification_status == ArtifactVerificationStatus.VERIFIED
    assert (verified.size, verified.sha256, verified.mtime) == (
        23,
        HASH_A,
        ARTIFACT_MTIME,
    )
    assert missing.verification_status == ArtifactVerificationStatus.MISSING
    assert (missing.size, missing.sha256, missing.mtime) == (None, None, None)
    assert unreadable.verification_status == ArtifactVerificationStatus.UNREADABLE
    assert (unreadable.size, unreadable.sha256, unreadable.mtime) == (
        17,
        None,
        ARTIFACT_MTIME,
    )


def test_unicode_round_trip_additive_compatibility_and_stable_fingerprint() -> None:
    record = _build_success(
        query="标题：森林—气候反馈 🌲",
        request_parameters={
            "authors": ["张三", "Zoë"],
            "options": {"语言": "中文", "threshold": 0.25},
        },
    )
    payload = json.loads(record.to_json())

    assert payload["query"] == "标题：森林—气候反馈 🌲"
    assert parse_manifest_record(payload) == record
    payload["future_additive_field"] = {"v3_reader": True}
    assert parse_manifest_record(payload) == record

    reordered = {
        "query": record.request.query,
        "parameters": {
            "options": {"threshold": 0.25, "语言": "中文"},
            "authors": ["张三", "Zoë"],
        },
    }
    assert build_manifest_request_fingerprint(reordered) == record.request_fingerprint


def test_fixed_clock_uuid_stat_and_hash_make_records_byte_stable() -> None:
    def build_once():
        times = iter((STARTED_AT, COMPLETED_AT))
        uuids = iter((RUN_ID, RECORD_ID))
        deps = ManifestBuilderDependencies(
            clock=lambda: next(times),
            uuid_factory=lambda: next(uuids),
            stat=lambda _path: _Stat(
                st_size=123,
                st_mtime=ARTIFACT_MTIME.timestamp(),
            ),
            sha256=lambda _path: HASH_C,
        )
        return build_manifest_record(
            tool_version="3.1.0",
            index=1,
            attempt=1,
            query="稳定输入",
            request_parameters={"b": 2, "a": 1},
            asset_profile="none",
            envelope=_envelope(),
            requested_outputs={"article", "markdown"},
            output_artifacts=(
                ManifestOutputArtifactSpec(path="stable.md", kind="markdown"),
            ),
            deps=deps,
        )

    first = build_once()
    second = build_once()

    assert first == second
    assert first.to_json() == second.to_json()
    assert first.run_id == RUN_ID
    assert first.record_id == RECORD_ID
    assert first.started_at == STARTED_AT
    assert first.completed_at == COMPLETED_AT


def test_packaged_json_schema_is_current_and_validates_round_trip_payload() -> None:
    record = _build_success()
    schema = manifest_record_json_schema()

    assert schema == generated_manifest_record_json_schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(record.to_dict())
    assert schema["properties"]["index"]["minimum"] == 1
    assert schema["properties"]["attempt"]["minimum"] == 1
    assert schema["properties"]["schema_version"]["const"] == 2


@pytest.mark.parametrize("field", ["schema_version", "request_fingerprint"])
def test_missing_required_version_or_fingerprint_is_rejected(field: str) -> None:
    payload = _build_success().to_dict()
    payload.pop(field)

    with pytest.raises(ValidationError):
        parse_manifest_record(payload)


def test_index_and_attempt_are_one_based() -> None:
    for field in ("index", "attempt"):
        overrides = {field: 0}
        with pytest.raises(ValidationError):
            _build_success(**overrides)
