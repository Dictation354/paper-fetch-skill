"""Batch MCP payloads and bounded worker runners."""

from __future__ import annotations

import asyncio
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from functools import partial
import threading
from typing import Any, Callable, Mapping

from mcp.server.fastmcp import Context
from mcp.types import CallToolResult

from ..config import build_runtime_env as _build_runtime_env
from ..runtime import RuntimeContext
from .log_bridge import PaperFetchLogBridge
from .results import _tool_result, error_payload_from_exception
from .schemas import BatchCheckRequest, BatchResolveRequest

build_runtime_env = _build_runtime_env

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
    max_workers: int = 1,
    cancel_event: threading.Event | None = None,
    **kwargs: Any,
) -> Any:
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=max(1, int(max_workers)))
    future = loop.run_in_executor(executor, partial(func, *args, **kwargs))
    shutdown_wait = True
    try:
        return await future
    except asyncio.CancelledError:
        if cancel_event is not None:
            cancel_event.set()
        future.cancel()
        shutdown_wait = False
        raise
    finally:
        executor.shutdown(wait=shutdown_wait, cancel_futures=not shutdown_wait)


def _batch_check_success_payload(query: str, payload: Mapping[str, Any], *, mode: str) -> dict[str, Any]:
    title = None
    if mode == "metadata":
        title = payload.get("title")
        return {
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
    article = payload.get("article") or {}
    if isinstance(article, Mapping):
        metadata = article.get("metadata") or {}
        if isinstance(metadata, Mapping):
            title = metadata.get("title")

    return {
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


def _run_batch_check_item(
    query: str,
    *,
    mode: str,
    context: RuntimeContext,
    requested_modes: list[str],
) -> dict[str, Any]:
    from . import fetch_tool

    if mode == "metadata":
        payload = fetch_tool._call_service_probe_has_fulltext(query, context=context).to_dict()
    else:
        payload = fetch_tool.fetch_paper_payload(
            query=query,
            modes=requested_modes,
            download_dir=None,
            context=context,
        )
    return _batch_check_success_payload(query, payload, mode=mode)


def _run_batch_sync(
    *,
    queries: list[str],
    concurrency: int,
    process_item: Callable[[str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    max_workers = max(1, min(concurrency, len(queries)))
    results: list[dict[str, Any] | None] = [None] * len(queries)
    abort_reason: dict[str, Any] | None = None

    if max_workers == 1:
        for index, query in enumerate(queries):
            try:
                results[index] = process_item(query)
            except Exception as error:
                payload = error_payload_from_exception(error)
                payload["query"] = query
                results[index] = payload
                if payload["status"] == "rate_limited":
                    abort_reason = dict(payload)
                    break
        return [result for result in results if result is not None], abort_reason

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        pending: dict[Any, tuple[int, str]] = {}
        next_index = 0

        def submit(index: int) -> None:
            future = executor.submit(process_item, queries[index])
            pending[future] = (index, queries[index])

        while next_index < len(queries) and len(pending) < max_workers:
            submit(next_index)
            next_index += 1

        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                index, query = pending.pop(future)
                try:
                    results[index] = future.result()
                except Exception as error:
                    payload = error_payload_from_exception(error)
                    payload["query"] = query
                    results[index] = payload
                    if payload["status"] == "rate_limited" and abort_reason is None:
                        abort_reason = dict(payload)
            while abort_reason is None and next_index < len(queries) and len(pending) < max_workers:
                submit(next_index)
                next_index += 1

    return [result for result in results if result is not None], abort_reason


async def _run_batch_async(
    *,
    queries: list[str],
    concurrency: int,
    process_item: Callable[[str], dict[str, Any]],
    ctx: Context | None,
    progress_prefix: str,
    cancel_event: threading.Event | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    results: list[dict[str, Any] | None] = [None] * len(queries)
    abort_reason: dict[str, Any] | None = None
    completed = 0
    max_workers = max(1, min(concurrency, len(queries)))
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=max_workers)
    pending: dict[asyncio.Future[dict[str, Any]], tuple[int, str]] = {}
    next_index = 0
    shutdown_wait = True

    def launch(index: int) -> None:
        future = loop.run_in_executor(executor, process_item, queries[index])
        pending[future] = (index, queries[index])

    try:
        while next_index < len(queries) and len(pending) < max_workers:
            launch(next_index)
            next_index += 1

        while pending:
            done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for future in done:
                index, query = pending.pop(future)
                try:
                    results[index] = future.result()
                except Exception as error:
                    payload = error_payload_from_exception(error)
                    payload["query"] = query
                    results[index] = payload
                    if payload["status"] == "rate_limited" and abort_reason is None:
                        abort_reason = dict(payload)
                completed += 1
                await report_progress(
                    ctx,
                    completed,
                    len(queries),
                    f"{progress_prefix} {completed} of {len(queries)} queries",
                )
            while abort_reason is None and next_index < len(queries) and len(pending) < max_workers:
                launch(next_index)
                next_index += 1
    except asyncio.CancelledError:
        if cancel_event is not None:
            cancel_event.set()
        for future in pending:
            future.cancel()
        shutdown_wait = False
        raise
    finally:
        executor.shutdown(wait=shutdown_wait, cancel_futures=not shutdown_wait)

    return [result for result in results if result is not None], abort_reason


def batch_resolve_payload(
    *,
    queries: list[str],
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    from . import fetch_tool

    request = BatchResolveRequest(queries=queries, concurrency=concurrency)
    runtime_env = build_runtime_env(env)
    runtime_context = RuntimeContext(env=runtime_env)
    results, abort_reason = _run_batch_sync(
        queries=request.queries,
        concurrency=request.concurrency,
        process_item=lambda query: fetch_tool.resolve_paper_payload(query=query, context=runtime_context),
    )

    return {
        "results": results,
        "aborted": abort_reason is not None,
        "abort_reason": abort_reason,
    }


def batch_check_payload(
    *,
    queries: list[str],
    mode: str = "metadata",
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    request = BatchCheckRequest(queries=queries, mode=mode, concurrency=concurrency)
    runtime_env = build_runtime_env(env)
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
        ),
    )

    return {
        "mode": request.mode,
        "results": results,
        "aborted": abort_reason is not None,
        "abort_reason": abort_reason,
    }


def batch_resolve_tool(
    *,
    queries: list[str],
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
) -> CallToolResult:
    try:
        return _tool_result(batch_resolve_payload(queries=queries, concurrency=concurrency, env=env), is_error=False)
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)


def batch_check_tool(
    *,
    queries: list[str],
    mode: str = "metadata",
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
) -> CallToolResult:
    try:
        return _tool_result(
            batch_check_payload(queries=queries, mode=mode, concurrency=concurrency, env=env),
            is_error=False,
        )
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)


async def batch_resolve_tool_async(
    *,
    queries: list[str],
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
    ctx: Context | None = None,
) -> CallToolResult:
    from . import fetch_tool

    try:
        request = BatchResolveRequest(queries=queries, concurrency=concurrency)
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)

    total_queries = len(request.queries)
    await report_progress(ctx, 0, total_queries, "Starting batch_resolve")

    runtime_env = build_runtime_env(env)
    cancelled = threading.Event()
    runtime_context = RuntimeContext(env=runtime_env, cancel_check=cancelled.is_set)
    loop = asyncio.get_running_loop()
    bridge = PaperFetchLogBridge(ctx=ctx, loop=loop) if ctx is not None else None

    try:
        if bridge is not None:
            bridge.__enter__()
        results, abort_reason = await _run_batch_async(
            queries=request.queries,
            concurrency=request.concurrency,
            process_item=lambda query: fetch_tool.resolve_paper_payload(query=query, context=runtime_context),
            ctx=ctx,
            progress_prefix="Resolved",
            cancel_event=cancelled,
        )
    except asyncio.CancelledError:
        cancelled.set()
        raise
    finally:
        if bridge is not None:
            bridge.__exit__(None, None, None)

    payload = {
        "results": results,
        "aborted": abort_reason is not None,
        "abort_reason": abort_reason,
    }
    await report_progress(
        ctx,
        total_queries,
        total_queries,
        "batch_resolve complete" if abort_reason is None else "batch_resolve stopped after rate limit",
    )
    return _tool_result(payload, is_error=False)


async def batch_check_tool_async(
    *,
    queries: list[str],
    mode: str = "metadata",
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
    ctx: Context | None = None,
) -> CallToolResult:
    try:
        request = BatchCheckRequest(queries=queries, mode=mode, concurrency=concurrency)
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)

    total_queries = len(request.queries)
    await report_progress(ctx, 0, total_queries, "Starting batch_check")

    runtime_env = build_runtime_env(env)
    cancelled = threading.Event()
    runtime_context = RuntimeContext(env=runtime_env, download_dir=None, cancel_check=cancelled.is_set)
    runtime_context.get_clients()
    requested_modes = _BATCH_CHECK_MODES[request.mode]
    loop = asyncio.get_running_loop()
    bridge = PaperFetchLogBridge(ctx=ctx, loop=loop) if ctx is not None else None

    try:
        if bridge is not None:
            bridge.__enter__()
        results, abort_reason = await _run_batch_async(
            queries=request.queries,
            concurrency=request.concurrency,
            process_item=lambda query: _run_batch_check_item(
                query,
                mode=request.mode,
                context=runtime_context,
                requested_modes=requested_modes,
            ),
            ctx=ctx,
            progress_prefix="Checked",
            cancel_event=cancelled,
        )
    except asyncio.CancelledError:
        cancelled.set()
        raise
    finally:
        if bridge is not None:
            bridge.__exit__(None, None, None)

    payload = {
        "mode": request.mode,
        "results": results,
        "aborted": abort_reason is not None,
        "abort_reason": abort_reason,
    }
    await report_progress(
        ctx,
        total_queries,
        total_queries,
        "batch_check complete" if abort_reason is None else "batch_check stopped after rate limit",
    )
    return _tool_result(payload, is_error=False)
