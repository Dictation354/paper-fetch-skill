"""Batch MCP payloads and bounded worker runners."""

from __future__ import annotations

import asyncio
from contextlib import ExitStack
from functools import partial
import threading
from typing import Any
from collections.abc import Callable, Mapping

from mcp.server.fastmcp import Context
from mcp.types import CallToolResult

from ..reason_codes import ERROR
from ..runtime import RuntimeContext
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

_BATCH_CHECK_MODES = {
    "article": ["article"],
    "metadata": ["metadata"],
}


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
    **kwargs: Any,
) -> Any:
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(None, partial(func, *args, **kwargs))
    try:
        return await future
    except asyncio.CancelledError:
        if cancel_event is not None:
            cancel_event.set()
        future.cancel()
        raise


def _batch_check_success_payload(
    query: str, payload: Mapping[str, Any], *, mode: str
) -> dict[str, Any]:
    title = None
    if mode == "metadata":
        title = payload.get("title")
        return with_schema_version(
            {
                "query": query,
                "doi": payload.get("doi"),
                "title": title,
                "has_fulltext": True if payload.get("state") == "likely_yes" else None,
                "content_kind": None,
                "has_abstract": None,
                "probe_state": payload.get("state"),
                "evidence": list(payload.get("evidence") or []),
                "warnings": list(payload.get("warnings") or []),
                "source": None,
                "source_trail": [],
                "trace": [],
                "token_estimate": None,
                "token_estimate_breakdown": None,
            }
        )
    article = payload.get("article") or {}
    if isinstance(article, Mapping):
        metadata = article.get("metadata") or {}
        if isinstance(metadata, Mapping):
            title = metadata.get("title")

    return with_schema_version(
        {
            "query": query,
            "doi": payload.get("doi"),
            "title": title,
            "source": payload.get("source"),
            "has_fulltext": payload.get("has_fulltext"),
            "content_kind": payload.get("content_kind"),
            "has_abstract": payload.get("has_abstract"),
            "warnings": list(payload.get("warnings") or []),
            "source_trail": list(payload.get("source_trail") or []),
            "trace": list(payload.get("trace") or []),
            "token_estimate": payload.get("token_estimate"),
            "token_estimate_breakdown": payload.get("token_estimate_breakdown"),
        }
    )


def _run_batch_check_item(
    query: str,
    *,
    mode: str,
    context: RuntimeContext,
    requested_modes: list[str],
    deps: MCPDeps = default_mcp_deps(),
) -> dict[str, Any]:
    from . import fetch_tool

    try:
        if mode == "metadata":
            payload = fetch_tool._call_service_probe_has_fulltext(
                query, context=context, deps=deps
            ).to_dict()
        else:
            payload = fetch_tool.fetch_paper_payload(
                query=query,
                modes=requested_modes,
                download_dir=None,
                context=context,
                deps=deps,
            )
        return _batch_check_success_payload(query, payload, mode=mode)
    finally:
        context.close_camoufox_for_current_thread()


def _run_batch_sync(
    *,
    queries: list[str],
    concurrency: int,
    process_item: Callable[[str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    run_result = run_batch(
        queries,
        process_item,
        max_workers=_batch_worker_count(queries, concurrency),
        failure_classifier=_mcp_batch_failure,
    )
    return _mcp_batch_payloads(run_result)


def _batch_worker_count(queries: list[str], concurrency: int) -> int:
    return max(1, min(concurrency, len(queries)))


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
    result: BatchItemResult[str, dict[str, Any]],
) -> dict[str, Any]:
    if result.failure is None:
        if result.value is None:
            return error_payload_from_exception(
                RuntimeError("Batch worker returned no payload.")
            )
        return result.value

    if isinstance(result.failure.details, Mapping):
        payload = dict(result.failure.details)
    elif result.error is not None:
        payload = error_payload_from_exception(result.error)
    else:
        payload = error_payload_from_exception(RuntimeError(result.failure.message))
    payload["query"] = result.item
    return payload


def _mcp_batch_payloads(
    run_result: BatchRunResult[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    payloads_by_index: dict[int, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    for result in run_result.results:
        if not result.was_submitted:
            continue
        payload = _mcp_payload_from_batch_result(result)
        payloads_by_index[result.index] = payload
        results.append(payload)

    abort_reason = None
    for event in run_result.completion_events:
        result = event.result
        if result.was_submitted and result.status is BatchItemStatus.RATE_LIMITED:
            abort_reason = dict(payloads_by_index[result.index])
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
    async def progress_callback(
        progress: BatchProgress[str, dict[str, Any]],
    ) -> None:
        if not progress.event.result.was_submitted:
            return
        await report_progress(
            ctx,
            progress.completed,
            len(queries),
            (f"{progress_prefix} {progress.completed} of {len(queries)} queries"),
        )

    run_result = await run_batch_async(
        queries,
        process_item,
        max_workers=_batch_worker_count(queries, concurrency),
        progress_callback=progress_callback,
        cancel_event=cancel_event,
        failure_classifier=_mcp_batch_failure,
    )
    return _mcp_batch_payloads(run_result)


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
    results, abort_reason = _run_batch_sync(
        queries=request.queries,
        concurrency=request.concurrency,
        process_item=lambda query: fetch_tool.resolve_paper_payload(
            query=query, context=runtime_context, deps=deps
        ),
    )

    return with_schema_version(
        {
            "results": results,
            "aborted": abort_reason is not None,
            "abort_reason": abort_reason,
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
    request = BatchCheckRequest(queries=queries, mode=mode, concurrency=concurrency)
    runtime_env = deps.build_runtime_env(env)
    runtime_context = RuntimeContext(env=runtime_env, download_dir=None)
    runtime_context.get_clients()
    requested_modes = _BATCH_CHECK_MODES[request.mode]
    results, abort_reason = _run_batch_sync(
        queries=request.queries,
        concurrency=request.concurrency,
        process_item=lambda query: _run_batch_check_item(
            query,
            mode=request.mode,
            context=runtime_context,
            requested_modes=requested_modes,
            deps=deps,
        ),
    )

    return with_schema_version(
        {
            "mode": request.mode,
            "results": results,
            "aborted": abort_reason is not None,
            "abort_reason": abort_reason,
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

    with ExitStack() as stack:
        if bridge is not None:
            stack.enter_context(bridge)
        try:
            results, abort_reason = await _run_batch_async(
                queries=request.queries,
                concurrency=request.concurrency,
                process_item=lambda query: fetch_tool.resolve_paper_payload(
                    query=query, context=runtime_context, deps=deps
                ),
                ctx=ctx,
                progress_prefix="Resolved",
                cancel_event=cancelled,
            )
        except asyncio.CancelledError:
            cancelled.set()
            raise

    payload = with_schema_version(
        {
            "results": results,
            "aborted": abort_reason is not None,
            "abort_reason": abort_reason,
        }
    )
    await report_progress(
        ctx,
        total_queries,
        total_queries,
        "batch_resolve complete"
        if abort_reason is None
        else "batch_resolve stopped after rate limit",
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
        request = BatchCheckRequest(queries=queries, mode=mode, concurrency=concurrency)
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)

    total_queries = len(request.queries)
    await report_progress(ctx, 0, total_queries, "Starting batch_check")

    runtime_env = deps.build_runtime_env(env)
    cancelled = threading.Event()
    runtime_context = RuntimeContext(
        env=runtime_env, download_dir=None, cancel_check=cancelled.is_set
    )
    runtime_context.get_clients()
    requested_modes = _BATCH_CHECK_MODES[request.mode]
    loop = asyncio.get_running_loop()
    bridge = PaperFetchLogBridge(ctx=ctx, loop=loop) if ctx is not None else None

    with ExitStack() as stack:
        if bridge is not None:
            stack.enter_context(bridge)
        try:
            results, abort_reason = await _run_batch_async(
                queries=request.queries,
                concurrency=request.concurrency,
                process_item=lambda query: _run_batch_check_item(
                    query,
                    mode=request.mode,
                    context=runtime_context,
                    requested_modes=requested_modes,
                    deps=deps,
                ),
                ctx=ctx,
                progress_prefix="Checked",
                cancel_event=cancelled,
            )
        except asyncio.CancelledError:
            cancelled.set()
            raise

    payload = with_schema_version(
        {
            "mode": request.mode,
            "results": results,
            "aborted": abort_reason is not None,
            "abort_reason": abort_reason,
        }
    )
    await report_progress(
        ctx,
        total_queries,
        total_queries,
        "batch_check complete"
        if abort_reason is None
        else "batch_check stopped after rate limit",
    )
    return _tool_result(payload, is_error=False)
