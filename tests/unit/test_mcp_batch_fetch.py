from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
import threading
import time
from typing import Any

import pytest

from paper_fetch.http import RequestCancelledError, RequestFailure
from paper_fetch.manifest import ManifestRecordStatus
from paper_fetch.manifest_writer import (
    RunManifestState,
    audit_manifest_path,
    latest_manifest_records,
    read_manifest_events,
    read_run_manifest,
    resolve_run_events_path,
)
from paper_fetch.mcp import batch_fetch as batch_fetch_module
from paper_fetch.mcp._deps import default_mcp_deps
from paper_fetch.mcp.batch_fetch import batch_fetch_tool_async
from paper_fetch.mcp.server import build_server
from paper_fetch.models import QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION
from tests.paths import REPO_ROOT, SKILL_DIR

from ._mcp_support import sample_envelope


class RecordingContext:
    def __init__(self) -> None:
        self.progress: list[tuple[float, float | None, str | None]] = []

    async def report_progress(
        self, *, progress: float, total: float | None, message: str | None
    ) -> None:
        self.progress.append((progress, total, message))


def _deps(fetch_envelope):
    return replace(default_mcp_deps(), fetch_paper_envelope=fetch_envelope)


def _successful_fetch(request, **_kwargs):
    return sample_envelope(
        modes=set(request.requested_modes()),
        doi=request.query,
    )


def _temporary_kwargs(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "queries": ["10.1000/one", "10.1000/two"],
        "concurrency": 2,
        "strategy": {"asset_profile": "none"},
        "no_download": True,
        "artifact_mode": "none",
        "deps": _deps(_successful_fetch),
    }
    values.update(overrides)
    return values


def test_batch_fetch_preserves_input_order_and_completion_metadata_with_bounded_text() -> (
    None
):
    delays = {"10.1000/one": 0.05, "10.1000/two": 0.0}

    def fetch(request, **_kwargs):
        time.sleep(delays[request.query])
        return _successful_fetch(request)

    ctx = RecordingContext()
    result = asyncio.run(
        batch_fetch_tool_async(
            **_temporary_kwargs(
                deps=_deps(fetch),
                detail="bounded",
                content_max_chars=11,
                ctx=ctx,
            )
        )
    )

    assert result.isError is False
    payload = result.structuredContent
    assert payload is not None
    assert [item["index"] for item in payload["results"]] == [1, 2]
    assert [item["query"] for item in payload["results"]] == [
        "10.1000/one",
        "10.1000/two",
    ]
    assert [item["index"] for item in payload["completion_order"]] == [2, 1]
    assert sum(item["content_returned_chars"] for item in payload["results"]) == 11
    assert payload["content_returned_chars"] == 11
    assert all(item["content_truncated"] for item in payload["results"])
    assert ctx.progress[0] == (0, 2, "Starting batch_fetch")
    assert ctx.progress[-1] == (2, 2, "batch_fetch complete")
    assert {update[0] for update in ctx.progress[1:-1]} == {1, 2}
    output_model = (
        build_server()._tool_manager._tools["batch_fetch"].fn_metadata.output_model
    )
    assert output_model is not None
    output_model.model_validate(payload)


def test_batch_fetch_compact_default_never_returns_full_markdown() -> None:
    result = asyncio.run(batch_fetch_tool_async(**_temporary_kwargs()))

    assert result.isError is False
    payload = result.structuredContent
    assert payload is not None
    assert payload["detail"] == "compact"
    assert payload["content_returned_chars"] == 0
    assert all("content" not in item for item in payload["results"])
    assert all("article" not in item for item in payload["results"])
    assert all("markdown" not in item for item in payload["results"])


def test_batch_fetch_continues_after_item_failure_and_terminalizes_every_index() -> (
    None
):
    def fetch(request, **_kwargs):
        if request.query == "10.1000/two":
            raise RuntimeError("synthetic item failure")
        return _successful_fetch(request)

    result = asyncio.run(
        batch_fetch_tool_async(
            **_temporary_kwargs(
                queries=["10.1000/one", "10.1000/two", "10.1000/three"],
                concurrency=1,
                deps=_deps(fetch),
            )
        )
    )

    assert result.isError is False
    payload = result.structuredContent
    assert payload is not None
    assert [item["index"] for item in payload["results"]] == [1, 2, 3]
    assert [item["record_status"] for item in payload["results"]] == [
        "completed",
        "failed",
        "completed",
    ]
    assert payload["results"][1]["error"]["reason"] == "synthetic item failure"
    assert payload["summary"]["record_statuses"] == {"completed": 2, "failed": 1}
    assert payload["state"] == "completed"


def test_batch_fetch_continue_on_error_false_stops_new_submissions() -> None:
    calls: list[str] = []

    def fetch(request, **_kwargs):
        calls.append(request.query)
        raise RuntimeError("stop this batch")

    result = asyncio.run(
        batch_fetch_tool_async(
            **_temporary_kwargs(
                queries=["first", "second", "third"],
                concurrency=1,
                continue_on_error=False,
                deps=_deps(fetch),
            )
        )
    )

    assert result.isError is False
    payload = result.structuredContent
    assert payload is not None
    assert calls == ["first"]
    assert [item["record_status"] for item in payload["results"]] == [
        "failed",
        "aborted",
        "aborted",
    ]
    assert payload["aborted"] is True


def test_batch_fetch_rate_limit_aborts_only_limited_lane_and_continues_other_lane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queries = ["rate-now", "other-lane", "rate-later"]
    lanes = {
        "rate-now": "provider-a",
        "rate-later": "provider-a",
        "other-lane": "provider-b",
    }
    monkeypatch.setattr(batch_fetch_module, "_lane_for_query", lanes.__getitem__)

    def fetch(request, **_kwargs):
        if request.query == "rate-now":
            raise RequestFailure(429, "synthetic rate limit", retry_after_seconds=7)
        time.sleep(0.03)
        return _successful_fetch(request)

    result = asyncio.run(
        batch_fetch_tool_async(
            **_temporary_kwargs(
                queries=queries,
                concurrency=2,
                deps=_deps(fetch),
            )
        )
    )

    assert result.isError is False
    payload = result.structuredContent
    assert payload is not None
    assert [item["record_status"] for item in payload["results"]] == [
        "failed",
        "completed",
        "aborted",
    ]
    assert payload["results"][2]["error"]["code"] == "http_429"
    assert payload["lane_cooldowns"] == [
        {
            "lane": "provider-a",
            "reason_code": "http_429",
            "source_index": 1,
            "retry_after_seconds": 7.0,
            "cooldown_seconds": 7.0,
        }
    ]
    assert payload["aborted"] is True


def test_batch_fetch_reports_cache_hit_without_returning_cached_body() -> None:
    def fetch(request, **_kwargs):
        envelope = _successful_fetch(request)
        envelope.quality.flags.append(QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION)
        return envelope

    result = asyncio.run(batch_fetch_tool_async(**_temporary_kwargs(deps=_deps(fetch))))

    assert result.isError is False
    payload = result.structuredContent
    assert payload is not None
    assert payload["summary"]["cache_hits"] == 2
    assert [item["cache_hit"] for item in payload["results"]] == [True, True]
    assert all("content" not in item for item in payload["results"])


def test_batch_fetch_no_download_temporary_read_does_not_write_selected_scope(
    tmp_path: Path,
) -> None:
    result = asyncio.run(
        batch_fetch_tool_async(
            **_temporary_kwargs(download_dir=tmp_path, deps=_deps(_successful_fetch))
        )
    )

    assert result.isError is False
    assert list(tmp_path.iterdir()) == []
    assert result.structuredContent["persisted"] is False


def test_batch_fetch_archive_returns_hash_path_and_scoped_resource_uri(
    tmp_path: Path,
) -> None:
    result = asyncio.run(
        batch_fetch_tool_async(
            **_temporary_kwargs(
                download_dir=tmp_path,
                save_markdown=True,
                markdown_output_dir=str(tmp_path),
                deps=_deps(_successful_fetch),
            )
        )
    )

    assert result.isError is False
    payload = result.structuredContent
    assert payload is not None
    assert payload["summary"]["saved_markdown"] == 2
    for item in payload["results"]:
        saved_path = Path(item["saved_markdown_path"])
        artifact = item["output_artifacts"][0]
        assert saved_path.is_file()
        assert artifact["path"] == str(saved_path)
        assert len(artifact["sha256"]) == 64
        assert artifact["verification_status"] == "verified"
        assert item["resource_uri"].startswith("resource://paper-fetch/cached-dir/")
        assert artifact["resource_uri"] == item["resource_uri"]
    names = {path.name for path in tmp_path.iterdir()}
    assert not any(name.endswith(".fetch-envelope.json") for name in names)
    assert not any(name.endswith("_assets") for name in names)


def test_batch_fetch_persistent_partial_run_resumes_only_retry_indices(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "run.json"

    def first_fetch(request, **_kwargs):
        if request.query == "10.1000/two":
            raise RuntimeError("retry me")
        return _successful_fetch(request)

    first = asyncio.run(
        batch_fetch_tool_async(
            **_temporary_kwargs(
                deps=_deps(first_fetch),
                run_manifest=str(manifest_path),
            )
        )
    )
    assert first.isError is False
    assert first.structuredContent["persisted"] is True

    resumed_calls: list[str] = []

    def resumed_fetch(request, **_kwargs):
        resumed_calls.append(request.query)
        return _successful_fetch(request)

    resumed = asyncio.run(
        batch_fetch_tool_async(
            **_temporary_kwargs(
                deps=_deps(resumed_fetch),
                resume=str(manifest_path),
            )
        )
    )

    assert resumed.isError is False
    payload = resumed.structuredContent
    assert payload is not None
    assert resumed_calls == ["10.1000/two"]
    assert payload["attempted_count"] == 1
    assert payload["reused_count"] == 1
    assert [item["attempt"] for item in payload["results"]] == [1, 2]
    assert [item["reused"] for item in payload["results"]] == [True, False]
    manifest = read_run_manifest(manifest_path)
    events_path = resolve_run_events_path(manifest_path, manifest.events_path)
    records = read_manifest_events(events_path)
    latest = latest_manifest_records(records)
    assert set(latest) == {1, 2}
    assert latest[1].attempt == 1
    assert latest[2].attempt == 2
    assert manifest.state is RunManifestState.COMPLETED
    assert audit_manifest_path(manifest_path).reusable_indices == (1, 2)


def test_batch_fetch_refuses_existing_persistence_without_overwrite(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "run.json"
    first = asyncio.run(
        batch_fetch_tool_async(**_temporary_kwargs(run_manifest=str(manifest_path)))
    )
    second = asyncio.run(
        batch_fetch_tool_async(**_temporary_kwargs(run_manifest=str(manifest_path)))
    )

    assert first.isError is False
    assert second.isError is True
    assert "already exists" in second.content[0].text


def test_batch_fetch_task_cancellation_persists_cancelled_complete_index_set(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "run.json"
    started = threading.Event()

    def fetch(_request, *, cancel_check=None, **_kwargs):
        started.set()
        while cancel_check is None or not cancel_check():
            time.sleep(0.005)
        raise RequestCancelledError("cancelled")

    async def scenario() -> None:
        task = asyncio.create_task(
            batch_fetch_tool_async(
                **_temporary_kwargs(
                    concurrency=1,
                    deps=_deps(fetch),
                    run_manifest=str(manifest_path),
                )
            )
        )
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())

    manifest = read_run_manifest(manifest_path)
    events = read_manifest_events(
        resolve_run_events_path(manifest_path, manifest.events_path)
    )
    latest = latest_manifest_records(events)
    assert manifest.state is RunManifestState.CANCELLED
    assert set(latest) == {1, 2}
    assert all(
        record.record_status is ManifestRecordStatus.ABORTED
        for record in latest.values()
    )
    assert all(
        record.error is not None
        and (record.error.model_extra or {}).get("code") == "request_cancelled"
        for record in latest.values()
    )


def test_batch_fetch_internal_interruption_persists_interrupted_terminal_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = tmp_path / "run.json"

    async def fail_runner(*_args, **_kwargs):
        raise RuntimeError("synthetic adapter interruption")

    monkeypatch.setattr(batch_fetch_module, "run_batch_async", fail_runner)
    result = asyncio.run(
        batch_fetch_tool_async(**_temporary_kwargs(run_manifest=str(manifest_path)))
    )

    assert result.isError is True
    manifest = read_run_manifest(manifest_path)
    events = read_manifest_events(
        resolve_run_events_path(manifest_path, manifest.events_path)
    )
    latest = latest_manifest_records(events)
    assert manifest.state is RunManifestState.INTERRUPTED
    assert set(latest) == {1, 2}
    assert all(
        record.record_status is ManifestRecordStatus.ABORTED
        for record in latest.values()
    )


def test_batch_fetch_validation_rejects_ambiguous_persistence_and_filename() -> None:
    persistence = asyncio.run(
        batch_fetch_tool_async(
            **_temporary_kwargs(
                resume="run.json",
                run_manifest="other.json",
            )
        )
    )
    filename = asyncio.run(
        batch_fetch_tool_async(**_temporary_kwargs(markdown_filename="same.md"))
    )

    assert persistence.isError is True
    assert "resume cannot be combined" in persistence.content[0].text
    assert filename.isError is True
    assert "only valid when batch_fetch has one query" in filename.content[0].text


def test_batch_fetch_contract_documents_selection_limit_and_compact_response() -> None:
    contract = (SKILL_DIR / "references" / "tool-contract.md").read_text(
        encoding="utf-8"
    )
    presets = (SKILL_DIR / "references" / "presets.md").read_text(encoding="utf-8")
    architecture = (REPO_ROOT / "docs" / "architecture" / "overview.md").read_text(
        encoding="utf-8"
    )

    assert "## Batch Fetch Contract" in contract
    assert "`queries` 限 `1..50`" in contract
    assert '`detail="compact"`' in contract
    assert "`completion_order`" in contract
    assert "仍优先 CLI" in contract
    assert '"run_manifest": "./papers/run-manifest.json"' in presets
    assert 'resume="./papers/run-manifest.json"' in presets
    assert "workflow.batch_runner" in architecture
    assert "manifest.build_manifest_record" in architecture
    assert "manifest_writer.RunManifestStore" in architecture
