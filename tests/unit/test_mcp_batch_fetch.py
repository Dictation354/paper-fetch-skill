from __future__ import annotations

import asyncio
import json
import threading
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from paper_fetch import runtime as runtime_module
from paper_fetch.http import RequestFailure
from paper_fetch.mcp import batch_fetch as batch_fetch_module
from paper_fetch.mcp._deps import default_mcp_deps
from paper_fetch.mcp.batch_fetch import batch_fetch_tool_async
from paper_fetch.mcp.fetch_tool import build_fetch_tool_result
from paper_fetch.mcp.schemas import FetchPaperRequest
from paper_fetch.mcp.server import build_server
from paper_fetch.models import QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION
from paper_fetch.reason_codes import RATE_LIMITED
from paper_fetch.runtime import RuntimeContext
from paper_fetch.tracing import TraceContext, trace_event

from ._mcp_support import assert_mcp_tool_omits_output_schema, sample_envelope


class RecordingContext:
    def __init__(self) -> None:
        self.progress: list[tuple[float, float | None, str | None]] = []

    async def report_progress(
        self, *, progress: float, total: float | None, message: str | None
    ) -> None:
        self.progress.append((progress, total, message))


def _deps(fetch_envelope):
    return replace(
        default_mcp_deps(),
        fetch_paper_envelope=fetch_envelope,
        service_resolve_paper=lambda query, **_kwargs: SimpleNamespace(
            query=query,
            provider_hint=f"test-{query}",
            landing_url=None,
            doi=query,
        ),
    )


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

    assert result.is_error is False
    payload = result.structured_content
    assert payload is not None
    assert [item["index"] for item in payload["results"]] == [1, 2]
    assert [item["query"] for item in payload["results"]] == [
        "10.1000/one",
        "10.1000/two",
    ]
    assert [item["index"] for item in payload["completion_order"]] == [2, 1]
    assert sum(item["content_returned_chars"] for item in payload["results"]) == 11
    assert payload["content_returned_chars"] == 11
    assert payload["attempted_count"] == 2
    assert payload["execution_count"] == 2
    assert payload["deduplicated_count"] == 0
    assert payload["not_scheduled_count"] == 0
    assert all(item["content_truncated"] for item in payload["results"])
    assert set(payload["results"][0]["acceptance"]) == {
        "overall",
        "identity",
        "fetch",
        "content",
        "asset",
        "output",
        "provenance",
        "acquisition",
        "has_fulltext",
        "has_abstract",
        "token_estimate",
        "asset_summary",
    }
    assert ctx.progress[0] == (0, 2, "Starting batch_fetch")
    assert ctx.progress[-1] == (
        2,
        2,
        "batch_fetch terminalized (terminal=2, not_scheduled=0)",
    )
    assert {update[0] for update in ctx.progress[1:-1]} == {1, 2}
    assert_mcp_tool_omits_output_schema(build_server(), "batch_fetch", payload)


def test_single_and_batch_fetch_share_compact_acceptance_projection() -> None:
    request = FetchPaperRequest.model_validate(
        {
            "query": "10.1000/one",
            "strategy": {"asset_profile": "none"},
        }
    )
    envelope = _successful_fetch(request)
    single = build_fetch_tool_result(envelope, request)
    batch = asyncio.run(
        batch_fetch_tool_async(
            **_temporary_kwargs(
                queries=[request.query],
                concurrency=1,
            )
        )
    )

    assert single.structured_content is not None
    assert batch.structured_content is not None
    assert (
        single.structured_content["acceptance"]
        == batch.structured_content["results"][0]["acceptance"]
    )


def test_batch_fetch_propagates_strict_asset_strategy_to_every_item() -> None:
    observed: list[tuple[bool, bool]] = []

    def fetch(request, **_kwargs):
        observed.append(
            (
                request.strategy.require_local_body_assets,
                request.strategy.require_full_size_body_assets,
            )
        )
        return _successful_fetch(request)

    result = asyncio.run(
        batch_fetch_tool_async(
            **_temporary_kwargs(
                strategy={
                    "asset_profile": "body",
                    "require_full_size_body_assets": True,
                },
                deps=_deps(fetch),
            )
        )
    )

    assert result.is_error is False
    assert observed == [(True, True), (True, True)]


def test_batch_fetch_uses_item_local_contexts_with_one_shared_transport() -> None:
    context_ids: list[int] = []
    transport_ids: list[int] = []
    barrier = threading.Barrier(2)

    def fetch(request, *, context=None, **_kwargs):
        assert context is not None
        context_ids.append(id(context))
        transport_ids.append(id(context.transport))
        barrier.wait(timeout=2)
        return _successful_fetch(request)

    result = asyncio.run(
        batch_fetch_tool_async(**_temporary_kwargs(deps=_deps(fetch), concurrency=2))
    )

    assert result.is_error is False
    assert len(set(context_ids)) == 2
    assert len(set(transport_ids)) == 1


def test_batch_fetch_deduplicates_canonical_doi_and_fans_out_original_indices() -> None:
    calls: list[str] = []

    def fetch(request, **_kwargs):
        calls.append(request.query)
        return _successful_fetch(request)

    queries = [
        "10.1000/Example",
        "https://doi.org/10.1000/example",
        "10.1000/example",
    ]
    result = asyncio.run(
        batch_fetch_tool_async(
            **_temporary_kwargs(
                queries=queries,
                concurrency=1,
                deps=_deps(fetch),
            )
        )
    )

    assert result.is_error is False
    payload = result.structured_content
    assert payload is not None
    assert calls == [queries[0]]
    assert [item["index"] for item in payload["results"]] == [1, 2, 3]
    assert [item["query"] for item in payload["results"]] == queries
    assert payload["attempted_count"] == 3
    assert payload["execution_count"] == 1
    assert payload["deduplicated_count"] == 2
    assert payload["not_scheduled_count"] == 0
    assert len(payload["completion_order"]) == 3


def test_batch_fetch_resolves_generic_queries_before_assigning_lanes() -> None:
    queries = ["title-provider-a-now", "title-provider-b", "title-provider-a-later"]
    providers = {
        "title-provider-a-now": "provider-a",
        "title-provider-a-later": "provider-a",
        "title-provider-b": "provider-b",
    }
    calls: list[str] = []

    def resolve(query, **_kwargs):
        return SimpleNamespace(
            query=query,
            provider_hint=providers[query],
            landing_url=None,
            doi=None,
        )

    def fetch(request, **_kwargs):
        calls.append(request.query)
        if request.query == "title-provider-a-now":
            raise RequestFailure(429, "synthetic rate limit", retry_after_seconds=3)
        return _successful_fetch(request)

    deps = replace(_deps(fetch), service_resolve_paper=resolve)
    result = asyncio.run(
        batch_fetch_tool_async(
            **_temporary_kwargs(
                queries=queries,
                concurrency=2,
                deps=deps,
            )
        )
    )

    assert result.is_error is False
    assert set(calls) == {"title-provider-a-now", "title-provider-b"}
    assert result.structured_content["results"][2]["record_status"] == "aborted"
    assert result.structured_content["lane_cooldowns"][0]["lane"] == "provider-a"


def test_prefer_cache_batch_skips_lane_enrichment_for_known_doi(
    tmp_path: Path,
) -> None:
    resolved_queries: list[str] = []

    def resolve(query, **_kwargs):
        resolved_queries.append(query)
        return SimpleNamespace(
            query=query,
            provider_hint="provider-a",
            landing_url=None,
            doi="10.1000/resolved-title",
        )

    deps = replace(_deps(_successful_fetch), service_resolve_paper=resolve)
    result = asyncio.run(
        batch_fetch_tool_async(
            **_temporary_kwargs(
                queries=["10.1000/already-known", "A generic paper title"],
                prefer_cache=True,
                download_dir=tmp_path,
                deps=deps,
            )
        )
    )

    assert result.is_error is False
    assert resolved_queries == ["A generic paper title"]


def test_batch_fetch_resolution_and_queue_time_do_not_consume_fetch_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [300.0]
    observed: list[dict[str, object]] = []

    def resolve(query, *, context, **_kwargs):
        context.request_started_at = 100.0
        return SimpleNamespace(
            query=query,
            provider_hint="test-provider",
            landing_url=None,
            doi=f"10.1000/{query.split()[0].lower()}",
        )

    def fetch(request, *, context=None, **_kwargs):
        assert context is not None
        observed.append(
            {
                "query": request.query,
                "request_started_at": context.request_started_at,
                "deadline": context.initialize_deadline(120.0),
                "remaining": context.remaining_seconds(),
                "session_cache": dict(context.session_cache),
            }
        )
        clock[0] += 200.0
        return _successful_fetch(request)

    monkeypatch.setattr(runtime_module.time, "monotonic", lambda: clock[0])
    deps = replace(
        _deps(fetch),
        service_resolve_paper=resolve,
    )
    result = asyncio.run(
        batch_fetch_tool_async(
            **_temporary_kwargs(
                queries=[
                    "First generic paper title",
                    "Second generic paper title",
                ],
                concurrency=1,
                deps=deps,
            )
        )
    )

    assert result.is_error is False
    assert [item["request_started_at"] for item in observed] == [300.0, 500.0]
    assert [item["deadline"] for item in observed] == [420.0, 620.0]
    assert [item["remaining"] for item in observed] == [120.0, 120.0]
    assert all(item["session_cache"] for item in observed)


def test_batch_fetch_cools_lane_after_recovered_rate_limit() -> None:
    queries = ["title-first", "title-same-provider"]

    def resolve(query, **_kwargs):
        return SimpleNamespace(
            query=query,
            provider_hint="provider-a",
            landing_url=None,
            doi=None,
        )

    def fetch(request, **_kwargs):
        envelope = _successful_fetch(request)
        envelope.trace.append(
            trace_event(
                "fulltext",
                "provider-a_api",
                RATE_LIMITED,
                code=RATE_LIMITED,
                context=TraceContext(
                    provider="provider-a",
                    route="api",
                    http_status=429,
                    retry_after_seconds=11,
                ),
            )
        )
        return envelope

    deps = replace(_deps(fetch), service_resolve_paper=resolve)
    result = asyncio.run(
        batch_fetch_tool_async(
            **_temporary_kwargs(
                queries=queries,
                concurrency=2,
                deps=deps,
            )
        )
    )

    assert result.is_error is False
    payload = result.structured_content
    assert payload["results"][0]["record_status"] == "completed"
    assert payload["results"][1]["record_status"] == "aborted"
    assert payload["lane_cooldowns"] == [
        {
            "lane": "provider-a",
            "reason_code": RATE_LIMITED,
            "source_index": 1,
            "retry_after_seconds": 11.0,
            "cooldown_seconds": 11.0,
        }
    ]


def test_batch_fetch_compact_default_never_returns_full_markdown() -> None:
    result = asyncio.run(batch_fetch_tool_async(**_temporary_kwargs()))

    assert result.is_error is False
    payload = result.structured_content
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

    assert result.is_error is False
    payload = result.structured_content
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


def test_batch_fetch_continue_on_error_false_stops_new_submissions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    created_children: set[int] = set()
    closed_children: set[int] = set()
    original_new_request_context = RuntimeContext.new_request_context
    original_close = RuntimeContext.close

    def tracked_new_request_context(self, **kwargs):
        child = original_new_request_context(self, **kwargs)
        created_children.add(id(child))
        return child

    def tracked_close(self):
        if id(self) in created_children:
            closed_children.add(id(self))
        return original_close(self)

    monkeypatch.setattr(
        RuntimeContext, "new_request_context", tracked_new_request_context
    )
    monkeypatch.setattr(RuntimeContext, "close", tracked_close)

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

    assert result.is_error is False
    payload = result.structured_content
    assert payload is not None
    assert calls == ["first"]
    assert [item["record_status"] for item in payload["results"]] == [
        "failed",
        "aborted",
        "aborted",
    ]
    assert payload["aborted"] is True
    assert payload["attempted_count"] == 1
    assert payload["execution_count"] == 1
    assert payload["not_scheduled_count"] == 2
    assert created_children == closed_children


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

    assert result.is_error is False
    payload = result.structured_content
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

    assert result.is_error is False
    payload = result.structured_content
    assert payload is not None
    assert payload["summary"]["cache_hits"] == 2
    assert [item["cache_hit"] for item in payload["results"]] == [True, True]
    assert all("content" not in item for item in payload["results"])


@pytest.mark.parametrize("modes", [None, ["article"]])
def test_batch_fetch_no_download_temporary_read_does_not_write_selected_scope(
    tmp_path: Path,
    modes,
) -> None:
    result = asyncio.run(
        batch_fetch_tool_async(
            **_temporary_kwargs(
                modes=modes,
                detail="compact",
                save_markdown=False,
                prefer_cache=False,
                download_dir=tmp_path,
                deps=_deps(_successful_fetch),
            )
        )
    )

    assert result.is_error is False
    assert list(tmp_path.iterdir()) == []
    assert result.structured_content["persisted"] is False
    assert all(
        item["acceptance"]["content"] == "fulltext"
        for item in result.structured_content["results"]
    )
    assert all(
        "article" not in item and "markdown" not in item
        for item in result.structured_content["results"]
    )


def test_batch_fetch_archive_returns_verified_hash_and_path(
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

    assert result.is_error is False
    payload = result.structured_content
    assert payload is not None
    assert payload["summary"]["saved_markdown"] == 2
    for item in payload["results"]:
        artifact = item["output_artifacts"][0]
        saved_path = Path(artifact["path"])
        assert saved_path.is_file()
        assert artifact["path"] == str(saved_path)
        assert len(artifact["sha256"]) == 64
        assert artifact["verification_status"] == "verified"
        assert {"route", "failure_code"} <= set(artifact)
        assert "resource_uri" not in item
        assert "resource_uri" not in artifact
    names = {path.name for path in tmp_path.iterdir()}
    assert not any(name.endswith(".fetch-envelope.json") for name in names)
    assert not any(name.endswith("_assets") for name in names)


def test_batch_fetch_atomically_writes_input_order_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    results_path = tmp_path / "results.jsonl"
    first = asyncio.run(
        batch_fetch_tool_async(**_temporary_kwargs(batch_results=str(results_path)))
    )
    second = asyncio.run(
        batch_fetch_tool_async(**_temporary_kwargs(batch_results=str(results_path)))
    )

    assert first.is_error is False
    records = [json.loads(line) for line in results_path.read_text().splitlines()]
    assert [record["index"] for record in records] == [1, 2]
    assert second.is_error is True
    assert "refusing to overwrite" in second.content[0].text


def test_batch_manifest_records_normalized_item_request_parameters(
    tmp_path: Path,
) -> None:
    results_path = tmp_path / "results.jsonl"
    result = asyncio.run(
        batch_fetch_tool_async(
            **_temporary_kwargs(
                queries=[" 10.1000/one ", " 10.1000/two "],
                markdown_filename="   ",
                batch_results=f"  {results_path}  ",
            )
        )
    )

    assert result.is_error is False
    records = [json.loads(line) for line in results_path.read_text().splitlines()]
    assert [record["query"] for record in records] == [
        "10.1000/one",
        "10.1000/two",
    ]
    for record in records:
        assert record["request"]["parameters"]["markdown_filename"] is None


def test_batch_fetch_cancellation_fences_late_markdown_commit(
    tmp_path: Path,
) -> None:
    started = threading.Event()

    def fetch(request, *, context, **_kwargs):
        started.set()
        while not context.cancelled:
            time.sleep(0.005)
        return _successful_fetch(request)

    async def scenario() -> None:
        task = asyncio.create_task(
            batch_fetch_tool_async(
                **_temporary_kwargs(
                    queries=["10.1000/late-write"],
                    concurrency=1,
                    no_download=False,
                    artifact_mode="markdown-assets",
                    save_markdown=True,
                    markdown_output_dir=str(tmp_path),
                    download_dir=tmp_path,
                    deps=_deps(fetch),
                )
            )
        )
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())

    assert not list(tmp_path.glob("*.md"))
    assert not list(tmp_path.glob("*.fetch-envelope.json"))


def test_batch_fetch_validation_rejects_shared_filename() -> None:
    filename = asyncio.run(
        batch_fetch_tool_async(**_temporary_kwargs(markdown_filename="same.md"))
    )

    assert filename.is_error is True
    assert "only valid when batch_fetch has one query" in filename.content[0].text
