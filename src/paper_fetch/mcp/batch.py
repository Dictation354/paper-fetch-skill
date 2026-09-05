"""Batch MCP payloads and bounded worker runners."""

from __future__ import annotations

import asyncio
from contextlib import ExitStack, suppress
from contextvars import copy_context
from dataclasses import dataclass, replace
from functools import partial
import threading
from typing import Any
from collections.abc import Callable, Mapping, Sequence

from mcp.server.mcpserver import Context
from mcp.types import CallToolResult

from ..reason_codes import ERROR
from ..provider_catalog import provider_for_source
from ..runtime import RuntimeContext
from ..publisher_identity import extract_doi, extract_doi_from_url, normalize_doi
from ..workflow.batch_routing import (
    GENERIC_BATCH_LANE,
    initial_provider_lane,
    provider_lane_from_resolved,
    provider_lane_limit,
    resolve_provider_lane,
)
from ..workflow.session_cache import RESOLVED_QUERY_KEY
from ..workflow.singleflight import RequestSingleFlight
from ..utils import normalize_text
from ..workflow.batch_runner import (
    BatchFailure,
    BatchItemResult,
    BatchItemStatus,
    BatchProgress,
    BatchRunResult,
    run_batch,
    run_batch_async,
)
from ._deps import MCPDeps, default_mcp_deps
from .log_bridge import PaperFetchLogBridge
from .results import (
    _tool_result,
    error_payload_from_exception,
    is_rate_limited_payload,
    with_schema_version,
)
from .schemas import BatchCheckRequest, BatchResolveRequest

DEFAULT_ASYNC_CANCEL_GRACE_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class _BatchCheckItem:
    """One check input with an isolated context and resolved scheduling lane."""

    index: int
    query: str
    lane_key: str
    context: RuntimeContext
    canonical_doi: str | None = None


def _canonical_doi_for_query(query: str) -> str | None:
    return (
        normalize_doi(extract_doi_from_url(query) or extract_doi(query) or "") or None
    )


async def _settle_blocking_future(
    future: asyncio.Future[Any],
    *,
    grace_seconds: float,
) -> None:
    done, _pending = await asyncio.wait((future,), timeout=grace_seconds)
    if done:
        with suppress(BaseException):
            future.result()


async def report_progress(
    ctx: Context | None,
    progress: float,
    total: float | None,
    message: str,
) -> None:
    if ctx is None:
        return
    try:
        await ctx.report_progress(progress=progress, total=total, message=message)
    except Exception:
        return


async def run_blocking_call(
    func: Callable[..., Any],
    /,
    *args: Any,
    cancel_event: threading.Event | None = None,
    cancel_fence: Callable[[], None] | None = None,
    cancel_grace_seconds: float = DEFAULT_ASYNC_CANCEL_GRACE_SECONDS,
    **kwargs: Any,
) -> Any:
    loop = asyncio.get_running_loop()
    call = partial(func, *args, **kwargs)
    future = loop.run_in_executor(None, copy_context().run, call)
    try:
        # Shield the executor future so task cancellation does not discard the
        # only handle through which we can wait for cooperative convergence.
        return await asyncio.shield(future)
    except asyncio.CancelledError as cancellation:
        if cancel_event is not None:
            cancel_event.set()
        if cancel_fence is not None:
            cancel_fence()
        if cancel_grace_seconds > 0:
            # Wait from an independent task so the caller's cancellation state (or
            # a repeated cancel request) cannot instantly cancel the grace wait.
            settle_task = asyncio.create_task(
                _settle_blocking_future(
                    future,
                    grace_seconds=cancel_grace_seconds,
                )
            )
            while not settle_task.done():
                try:
                    await asyncio.shield(settle_task)
                except asyncio.CancelledError:
                    continue
            with suppress(BaseException):
                settle_task.result()
        if not future.done():
            future.cancel()
        raise cancellation


def _batch_check_success_payload(
    query: str, payload: Mapping[str, Any]
) -> dict[str, Any]:
    return with_schema_version(
        {
            "query": query,
            "doi": payload.get("doi"),
            "title": payload.get("title"),
            "has_fulltext": None,
            "likely_has_fulltext": (
                True if payload.get("state") == "likely_yes" else None
            ),
            "content_kind": None,
            "has_abstract": None,
            "probe_state": payload.get("state"),
            "evidence": list(payload.get("evidence") or []),
            "warnings": list(payload.get("warnings") or []),
            "source": None,
            "acquisition": None,
            "source_trail": [],
            "trace": [],
            "token_estimate": None,
            "token_estimate_breakdown": None,
        }
    )


def _run_batch_check_item(
    query: str,
    *,
    context: RuntimeContext,
    deps: MCPDeps = default_mcp_deps(),
) -> dict[str, Any]:
    from . import fetch_tool

    try:
        payload = fetch_tool._call_service_probe_has_fulltext(
            query, context=context, deps=deps
        ).to_dict()
        return _batch_check_success_payload(query, payload)
    finally:
        context.close_camoufox_for_current_thread()


def _resolved_doi_from_context(item: _BatchCheckItem) -> str | None:
    cached = item.context.get_session_cache(
        RESOLVED_QUERY_KEY.materialize(normalize_text(item.query) or item.query)
    )
    doi = normalize_doi(
        str(
            (
                cached.get("doi")
                if isinstance(cached, Mapping)
                else getattr(cached, "doi", None)
            )
            or ""
        )
    )
    return doi or item.canonical_doi


def _prepare_batch_check_item(
    item: _BatchCheckItem,
    *,
    deps: MCPDeps,
) -> _BatchCheckItem:
    """Resolve only generic lanes and prime the item's resolution cache."""

    from . import fetch_tool

    if item.canonical_doi:
        # A DOI already has the best no-I/O catalog lane available. Unknown DOI
        # prefixes remain generic until the real check resolves them; preparation
        # must not add a resolver network round trip for a known identity.
        return item
    try:
        lane_key = resolve_provider_lane(
            item.query,
            initial_lane=item.lane_key,
            context=item.context,
            resolver=lambda query, *, context: fetch_tool._call_service_resolve_paper(
                query,
                context=context,
                deps=deps,
            ),
        )
    except Exception:
        # Check/probe remains the owner of resolution errors and their stable
        # diagnostics; preparation only improves scheduling identity.
        return item
    return replace(
        item,
        lane_key=lane_key,
        canonical_doi=_resolved_doi_from_context(item),
    )


def _prepare_batch_check_items_sync(
    items: list[_BatchCheckItem],
    *,
    concurrency: int,
    deps: MCPDeps,
) -> list[_BatchCheckItem]:
    prepared = run_batch(
        items,
        lambda item: _prepare_batch_check_item(item, deps=deps),
        max_workers=_batch_worker_count(items, concurrency),
        lane_key=lambda item: f"resolve:{item.index}",
    )
    return [
        result.value if result.value is not None else result.item
        for result in prepared.results
    ]


async def _prepare_batch_check_items_async(
    items: list[_BatchCheckItem],
    *,
    concurrency: int,
    deps: MCPDeps,
    cancel_event: threading.Event | None,
) -> list[_BatchCheckItem]:
    prepared = await run_batch_async(
        items,
        lambda item: _prepare_batch_check_item(item, deps=deps),
        max_workers=_batch_worker_count(items, concurrency),
        lane_key=lambda item: f"resolve:{item.index}",
        cancel_event=cancel_event,
    )
    return [
        result.value if result.value is not None else result.item
        for result in prepared.results
    ]


def _run_batch_sync(
    *,
    queries: list[str],
    concurrency: int,
    process_item: Callable[[str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    memo: RequestSingleFlight[dict[str, Any]] = RequestSingleFlight()

    def memoized(query: str) -> dict[str, Any]:
        doi = _canonical_doi_for_query(query)
        if not doi:
            return process_item(query)
        return memo.run(
            doi,
            lambda: process_item(query),
            retain_completed=True,
        )

    run_result = run_batch(
        queries,
        memoized,
        max_workers=_batch_worker_count(queries, concurrency),
        lane_key=initial_provider_lane,
        failure_classifier=_mcp_batch_failure,
    )
    return _mcp_batch_payloads(run_result)


def _batch_worker_count(items: Sequence[object], concurrency: int) -> int:
    return max(1, min(concurrency, len(items)))


def _mcp_batch_failure(error: Exception) -> BatchFailure:
    payload = error_payload_from_exception(error)
    retry_after_value = payload.get("retry_after_seconds")
    retry_after_seconds = (
        float(retry_after_value)
        if isinstance(retry_after_value, (int, float))
        and not isinstance(retry_after_value, bool)
        else None
    )
    return BatchFailure(
        reason_code=str(payload.get("code") or ERROR),
        message=str(payload.get("reason") or error),
        retry_after_seconds=retry_after_seconds,
        rate_limited=is_rate_limited_payload(payload),
        cancelled=payload.get("error_category") == "cancelled",
        details=payload,
    )


def _mcp_payload_from_batch_result(
    result: BatchItemResult[Any, dict[str, Any]],
) -> dict[str, Any]:
    if result.failure is None:
        if result.value is None:
            payload = error_payload_from_exception(
                RuntimeError("Batch worker returned no payload.")
            )
            error_payload: dict[str, Any] | None = dict(payload)
        else:
            payload = dict(result.value)
            error_payload = None
    else:
        if isinstance(result.failure.details, Mapping):
            payload = dict(result.failure.details)
        elif result.error is not None:
            payload = error_payload_from_exception(result.error)
        else:
            payload = error_payload_from_exception(RuntimeError(result.failure.message))
        error_payload = dict(payload)
    logical_query = (
        result.item.query
        if isinstance(result.item, _BatchCheckItem)
        else str(result.item)
    )
    provider_lane = str(result.lane_key)
    if provider_lane == GENERIC_BATCH_LANE:
        resolved_lane = provider_lane_from_resolved(result.value or {})
        if resolved_lane:
            provider_lane = resolved_lane
        elif result.value is not None:
            source_provider = provider_for_source(str(result.value.get("source") or ""))
            if source_provider:
                provider_lane = source_provider
        elif result.failure is not None and isinstance(result.failure.details, Mapping):
            failure_provider = str(result.failure.details.get("provider") or "").strip()
            if failure_provider:
                provider_lane = failure_provider
    payload.update(
        {
            "index": result.index + 1,
            "query": logical_query,
            "status": result.status.value,
            "error": error_payload,
            "provider_lane": provider_lane,
        }
    )
    return with_schema_version(payload)


def _mcp_batch_payloads(
    run_result: BatchRunResult[Any, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    payloads_by_index: dict[int, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    for result in run_result.results:
        payload = _mcp_payload_from_batch_result(result)
        payloads_by_index[result.index] = payload
        results.append(payload)

    abort_reason = None
    for event in run_result.completion_events:
        result = event.result
        if result.was_submitted and result.status is BatchItemStatus.RATE_LIMITED:
            decorated = payloads_by_index[result.index]
            error_payload = decorated.get("error")
            abort_reason = (
                dict(error_payload)
                if isinstance(error_payload, Mapping)
                else dict(decorated)
            )
            break
    return results, abort_reason


async def _run_batch_async(
    *,
    queries: list[str],
    concurrency: int,
    process_item: Callable[[str], dict[str, Any]],
    ctx: Context | None,
    progress_prefix: str,
    cancel_event: threading.Event | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    memo: RequestSingleFlight[dict[str, Any]] = RequestSingleFlight()

    def memoized(query: str) -> dict[str, Any]:
        doi = _canonical_doi_for_query(query)
        if not doi:
            return process_item(query)
        return memo.run(
            doi,
            lambda: process_item(query),
            cancel_check=(cancel_event.is_set if cancel_event is not None else None),
            retain_completed=True,
        )

    async def progress_callback(
        progress: BatchProgress[str, dict[str, Any]],
    ) -> None:
        await report_progress(
            ctx,
            progress.terminal,
            len(queries),
            (
                f"{progress_prefix} terminal {progress.terminal} of "
                f"{len(queries)} queries (completed={progress.completed}, "
                f"not_scheduled={progress.not_scheduled})"
            ),
        )

    run_result = await run_batch_async(
        queries,
        memoized,
        max_workers=_batch_worker_count(queries, concurrency),
        lane_key=initial_provider_lane,
        progress_callback=progress_callback,
        cancel_event=cancel_event,
        failure_classifier=_mcp_batch_failure,
    )
    return _mcp_batch_payloads(run_result)


def _run_batch_check_sync(
    *,
    items: list[_BatchCheckItem],
    concurrency: int,
    deps: MCPDeps,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    prepared_items = _prepare_batch_check_items_sync(
        items,
        concurrency=concurrency,
        deps=deps,
    )
    memo: RequestSingleFlight[dict[str, Any]] = RequestSingleFlight()

    def process(item: _BatchCheckItem) -> dict[str, Any]:
        def check() -> dict[str, Any]:
            return _run_batch_check_item(
                item.query,
                context=item.context,
                deps=deps,
            )

        if item.canonical_doi:
            return memo.run(item.canonical_doi, check, retain_completed=True)
        return check()

    run_result = run_batch(
        prepared_items,
        process,
        max_workers=_batch_worker_count(prepared_items, concurrency),
        lane_key=lambda item: item.lane_key,
        lane_limits=lambda lane: provider_lane_limit(
            lane,
            global_limit=concurrency,
        ),
        failure_classifier=_mcp_batch_failure,
    )
    return _mcp_batch_payloads(run_result)


async def _run_batch_check_async(
    *,
    items: list[_BatchCheckItem],
    concurrency: int,
    deps: MCPDeps,
    ctx: Context | None,
    cancel_event: threading.Event,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    prepared_items = await _prepare_batch_check_items_async(
        items,
        concurrency=concurrency,
        deps=deps,
        cancel_event=cancel_event,
    )
    memo: RequestSingleFlight[dict[str, Any]] = RequestSingleFlight()

    def process(item: _BatchCheckItem) -> dict[str, Any]:
        def check() -> dict[str, Any]:
            return _run_batch_check_item(
                item.query,
                context=item.context,
                deps=deps,
            )

        if item.canonical_doi:
            return memo.run(
                item.canonical_doi,
                check,
                cancel_check=cancel_event.is_set,
                retain_completed=True,
            )
        return check()

    async def progress_callback(
        progress: BatchProgress[_BatchCheckItem, dict[str, Any]],
    ) -> None:
        await report_progress(
            ctx,
            progress.terminal,
            len(prepared_items),
            (
                f"Checked terminal {progress.terminal} of "
                f"{len(prepared_items)} queries "
                f"(completed={progress.completed}, "
                f"not_scheduled={progress.not_scheduled})"
            ),
        )

    run_result = await run_batch_async(
        prepared_items,
        process,
        max_workers=_batch_worker_count(prepared_items, concurrency),
        lane_key=lambda item: item.lane_key,
        lane_limits=lambda lane: provider_lane_limit(
            lane,
            global_limit=concurrency,
        ),
        progress_callback=progress_callback,
        cancel_event=cancel_event,
        failure_classifier=_mcp_batch_failure,
    )
    return _mcp_batch_payloads(run_result)


def _batch_progress_payload(results: list[dict[str, Any]]) -> dict[str, int]:
    not_scheduled = sum(
        1 for item in results if item.get("status") == BatchItemStatus.NOT_SCHEDULED
    )
    return {
        "total": len(results),
        "terminal": len(results),
        "completed": len(results) - not_scheduled,
        "not_scheduled": not_scheduled,
    }


def _run_with_child_context(
    parent: RuntimeContext,
    operation: Callable[[RuntimeContext], dict[str, Any]],
) -> dict[str, Any]:
    child = parent.new_request_context()
    try:
        return operation(child)
    finally:
        child.close()


def batch_resolve_payload(
    *,
    queries: list[str],
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
    deps: MCPDeps = default_mcp_deps(),
) -> dict[str, Any]:
    from . import fetch_tool

    request = BatchResolveRequest(queries=queries, concurrency=concurrency)
    runtime_env = deps.build_runtime_env(env)
    runtime_context = RuntimeContext(env=runtime_env)
    try:
        results, abort_reason = _run_batch_sync(
            queries=request.queries,
            concurrency=request.concurrency,
            process_item=lambda query: _run_with_child_context(
                runtime_context,
                lambda child: fetch_tool.resolve_paper_payload(
                    query=query, context=child, deps=deps
                ),
            ),
        )
    finally:
        runtime_context.close()

    return with_schema_version(
        {
            "results": results,
            "aborted": abort_reason is not None,
            "abort_reason": abort_reason,
            "progress": _batch_progress_payload(results),
        }
    )


def batch_check_payload(
    *,
    queries: list[str],
    mode: str = "metadata",
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
    deps: MCPDeps = default_mcp_deps(),
) -> dict[str, Any]:
    request = BatchCheckRequest(
        queries=queries,
        mode=mode,
        concurrency=concurrency,
    )
    runtime_env = deps.build_runtime_env(env)
    runtime_context = RuntimeContext(env=runtime_env, download_dir=None)
    item_contexts: list[RuntimeContext] = []
    try:
        items: list[_BatchCheckItem] = []
        for index, query in enumerate(request.queries):
            child = runtime_context.new_request_context()
            item_contexts.append(child)
            items.append(
                _BatchCheckItem(
                    index=index,
                    query=query,
                    lane_key=initial_provider_lane(query),
                    context=child,
                    canonical_doi=_canonical_doi_for_query(query),
                )
            )
        results, abort_reason = _run_batch_check_sync(
            items=items,
            concurrency=request.concurrency,
            deps=deps,
        )
    finally:
        for item_context in item_contexts:
            item_context.close()
        runtime_context.close()

    return with_schema_version(
        {
            "mode": request.mode,
            "results": results,
            "aborted": abort_reason is not None,
            "abort_reason": abort_reason,
            "progress": _batch_progress_payload(results),
        }
    )


async def batch_resolve_tool_async(
    *,
    queries: list[str],
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
    ctx: Context | None = None,
    deps: MCPDeps = default_mcp_deps(),
) -> CallToolResult:
    from . import fetch_tool

    try:
        request = BatchResolveRequest(queries=queries, concurrency=concurrency)
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)

    total_queries = len(request.queries)
    await report_progress(ctx, 0, total_queries, "Starting batch_resolve")

    runtime_env = deps.build_runtime_env(env)
    cancelled = threading.Event()
    runtime_context = RuntimeContext(env=runtime_env, cancel_check=cancelled.is_set)
    loop = asyncio.get_running_loop()
    bridge = PaperFetchLogBridge(ctx=ctx, loop=loop) if ctx is not None else None

    try:
        with ExitStack() as stack:
            if bridge is not None:
                stack.enter_context(bridge)
            try:
                results, abort_reason = await _run_batch_async(
                    queries=request.queries,
                    concurrency=request.concurrency,
                    process_item=lambda query: _run_with_child_context(
                        runtime_context,
                        lambda child: fetch_tool.resolve_paper_payload(
                            query=query, context=child, deps=deps
                        ),
                    ),
                    ctx=ctx,
                    progress_prefix="Resolved",
                    cancel_event=cancelled,
                )
            except asyncio.CancelledError:
                cancelled.set()
                raise
    finally:
        runtime_context.close()

    payload = with_schema_version(
        {
            "results": results,
            "aborted": abort_reason is not None,
            "abort_reason": abort_reason,
            "progress": _batch_progress_payload(results),
        }
    )
    await report_progress(
        ctx,
        len(results),
        total_queries,
        (
            "batch_resolve terminalized "
            f"(terminal={len(results)}, "
            f"not_scheduled={_batch_progress_payload(results)['not_scheduled']})"
        ),
    )
    return _tool_result(payload, is_error=False)


async def batch_check_tool_async(
    *,
    queries: list[str],
    mode: str = "metadata",
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
    ctx: Context | None = None,
    deps: MCPDeps = default_mcp_deps(),
) -> CallToolResult:
    try:
        request = BatchCheckRequest(
            queries=queries,
            mode=mode,
            concurrency=concurrency,
        )
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)

    total_queries = len(request.queries)
    await report_progress(ctx, 0, total_queries, "Starting batch_check")

    try:
        runtime_env = deps.build_runtime_env(env)
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)
    cancelled = threading.Event()
    runtime_context = RuntimeContext(
        env=runtime_env, download_dir=None, cancel_check=cancelled.is_set
    )
    item_contexts: list[RuntimeContext] = []
    loop = asyncio.get_running_loop()
    bridge = PaperFetchLogBridge(ctx=ctx, loop=loop) if ctx is not None else None

    try:
        with ExitStack() as stack:
            if bridge is not None:
                stack.enter_context(bridge)
            try:
                items: list[_BatchCheckItem] = []
                for index, query in enumerate(request.queries):
                    child = runtime_context.new_request_context()
                    item_contexts.append(child)
                    items.append(
                        _BatchCheckItem(
                            index=index,
                            query=query,
                            lane_key=initial_provider_lane(query),
                            context=child,
                            canonical_doi=_canonical_doi_for_query(query),
                        )
                    )
                results, abort_reason = await _run_batch_check_async(
                    items=items,
                    concurrency=request.concurrency,
                    deps=deps,
                    ctx=ctx,
                    cancel_event=cancelled,
                )
            except asyncio.CancelledError:
                cancelled.set()
                raise
    finally:
        for item_context in item_contexts:
            item_context.close()
        runtime_context.close()

    payload = with_schema_version(
        {
            "mode": request.mode,
            "results": results,
            "aborted": abort_reason is not None,
            "abort_reason": abort_reason,
            "progress": _batch_progress_payload(results),
        }
    )
    await report_progress(
        ctx,
        len(results),
        total_queries,
        (
            "batch_check terminalized "
            f"(terminal={len(results)}, "
            f"not_scheduled={_batch_progress_payload(results)['not_scheduled']})"
        ),
    )
    return _tool_result(payload, is_error=False)
