"""Compatibility facade for MCP tool helpers.

The implementation lives in smaller internal modules. This module intentionally
keeps the historical import path and common monkeypatch points stable for tests
and local smoke scripts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from mcp.server.fastmcp import Context
from mcp.types import CallToolResult

from ..config import build_runtime_env as _build_runtime_env
from ..config import resolve_mcp_download_dir as _resolve_mcp_download_dir
from ..http import HttpTransport, RequestCancelledError
from ..providers.registry import build_clients as _build_clients
from ..service import fetch_paper as _service_fetch_paper
from ..service import probe_has_fulltext as _service_probe_has_fulltext
from ..service import resolve_paper as _service_resolve_paper
from . import batch as _batch
from . import cache_payloads as _cache_payloads
from . import fetch_tool as _fetch_tool
from .batch import (
    _BATCH_CHECK_MODES,
    _batch_check_success_payload,
    _run_batch_async,
    _run_batch_check_item,
    _run_batch_sync,
)
from .batch import run_blocking_call as _run_blocking_call
from .cache_index import (
    find_cached_entry as _find_cached_entry,
    list_cache_entries as _list_cache_entries,
    preferred_cached_entries as _preferred_cached_entries,
    refresh_cache_index_for_doi as _refresh_cache_index_for_doi,
)
from .cache_payloads import _MCP_DEFAULT_DOWNLOAD_DIR, _resolve_download_dir
from .fetch_cache import (
    FETCH_ENVELOPE_CACHE_VERSION as _FETCH_ENVELOPE_CACHE_VERSION,
    FETCH_ENVELOPE_EXTRACTION_REVISION as _FETCH_ENVELOPE_EXTRACTION_REVISION,
    FetchCache,
    article_from_payload as _article_from_payload,
    cached_payload_satisfies_request as _cached_payload_satisfies_request,
    cached_request_matches as _cached_request_matches,
    envelope_from_payload as _envelope_from_payload,
    fetch_envelope_cache_path,
    mark_envelope_cached_with_current_revision as _mark_envelope_cached_with_current_revision,
    metadata_from_payload as _metadata_from_payload,
    payload_from_envelope as _payload_from_envelope,
    quality_from_payload as _quality_from_payload,
    request_cache_payload as _request_cache_payload,
    trace_from_payload as _trace_from_payload,
)
from .fetch_tool import (
    _FETCH_PROGRESS_TOTAL,
    _PROVIDER_STATUS_ORDER,
    _call_service_fetch_paper,
    _call_service_probe_has_fulltext,
    _call_service_resolve_paper,
    _fetch_envelope_cache_path,
    _inline_image_contents,
    _inline_image_note,
    _is_body_figure_asset,
    _load_cached_fetch_envelope,
    _provider_status_error_payload,
    _service_modes_for_fetch_request,
)
from .fetch_tool import _fetch_paper_envelope as _default_fetch_paper_envelope
from .fetch_tool import _write_cached_fetch_envelope as _default_write_cached_fetch_envelope
from .fetch_tool import build_fetch_tool_result
from .log_bridge import (
    PaperFetchLogBridge,
    StructuredLogNotificationHandler,
    parse_structured_log_message,
    structured_log_payload_from_record,
)
from .results import _dump_payload, _tool_result, _validation_reason, error_payload_from_exception
from .schemas import (
    BatchCheckRequest,
    BatchResolveRequest,
    FetchPaperRequest,
    FetchStrategyInput,
    HasFulltextRequest,
    InlineImageBudget,
    ResolvePaperRequest,
)

__all__ = (
    "BatchCheckRequest",
    "BatchResolveRequest",
    "FetchCache",
    "FetchPaperRequest",
    "FetchStrategyInput",
    "HasFulltextRequest",
    "HttpTransport",
    "InlineImageBudget",
    "PaperFetchLogBridge",
    "RequestCancelledError",
    "ResolvePaperRequest",
    "StructuredLogNotificationHandler",
    "_BATCH_CHECK_MODES",
    "_CACHE_COMPAT_SYMBOLS",
    "_FETCH_ENVELOPE_CACHE_VERSION",
    "_FETCH_ENVELOPE_EXTRACTION_REVISION",
    "_FETCH_PROGRESS_TOTAL",
    "_MCP_DEFAULT_DOWNLOAD_DIR",
    "_PROVIDER_STATUS_ORDER",
    "_article_from_payload",
    "_batch_check_success_payload",
    "_cached_payload_satisfies_request",
    "_cached_request_matches",
    "_call_service_fetch_paper",
    "_call_service_probe_has_fulltext",
    "_call_service_resolve_paper",
    "_dump_payload",
    "_envelope_from_payload",
    "_fetch_envelope_cache_path",
    "_fetch_paper_envelope",
    "_inline_image_contents",
    "_inline_image_note",
    "_is_body_figure_asset",
    "_load_cached_fetch_envelope",
    "_mark_envelope_cached_with_current_revision",
    "_metadata_from_payload",
    "_payload_from_envelope",
    "_provider_status_error_payload",
    "_quality_from_payload",
    "_request_cache_payload",
    "_resolve_download_dir",
    "_run_batch_async",
    "_run_batch_check_item",
    "_run_batch_sync",
    "_run_blocking_call",
    "_service_modes_for_fetch_request",
    "_tool_result",
    "_trace_from_payload",
    "_validation_reason",
    "_write_cached_fetch_envelope",
    "batch_check_payload",
    "batch_check_tool",
    "batch_check_tool_async",
    "batch_resolve_payload",
    "batch_resolve_tool",
    "batch_resolve_tool_async",
    "build_clients",
    "build_fetch_tool_result",
    "build_runtime_env",
    "cached_entry_payload",
    "error_payload_from_exception",
    "fetch_envelope_cache_path",
    "fetch_paper_payload",
    "fetch_paper_tool",
    "fetch_paper_tool_async",
    "find_cached_entry",
    "get_cached_payload",
    "get_cached_tool",
    "has_fulltext_payload",
    "has_fulltext_tool",
    "list_cache_entries",
    "list_cached_payload",
    "list_cached_tool",
    "parse_structured_log_message",
    "preferred_cached_entries",
    "provider_status_payload",
    "provider_status_tool",
    "refresh_cache_index_for_doi",
    "resolve_mcp_download_dir",
    "resolve_paper_payload",
    "resolve_paper_tool",
    "service_fetch_paper",
    "service_probe_has_fulltext",
    "service_resolve_paper",
    "structured_log_payload_from_record",
)

build_runtime_env = _build_runtime_env
resolve_mcp_download_dir = _resolve_mcp_download_dir
service_fetch_paper = _service_fetch_paper
service_probe_has_fulltext = _service_probe_has_fulltext
service_resolve_paper = _service_resolve_paper
build_clients = _build_clients
find_cached_entry = _find_cached_entry
list_cache_entries = _list_cache_entries
preferred_cached_entries = _preferred_cached_entries
refresh_cache_index_for_doi = _refresh_cache_index_for_doi

_fetch_paper_envelope = _default_fetch_paper_envelope
_write_cached_fetch_envelope = _default_write_cached_fetch_envelope

_CACHE_COMPAT_SYMBOLS = (
    _FETCH_ENVELOPE_CACHE_VERSION,
    _FETCH_ENVELOPE_EXTRACTION_REVISION,
    _article_from_payload,
    _cached_payload_satisfies_request,
    _cached_request_matches,
    _envelope_from_payload,
    _mark_envelope_cached_with_current_revision,
    _metadata_from_payload,
    _payload_from_envelope,
    _quality_from_payload,
    _request_cache_payload,
    _trace_from_payload,
)


def _sync_dependency_overrides() -> None:
    _fetch_tool.build_runtime_env = build_runtime_env
    _fetch_tool.service_fetch_paper = service_fetch_paper
    _fetch_tool.service_probe_has_fulltext = service_probe_has_fulltext
    _fetch_tool.service_resolve_paper = service_resolve_paper
    _fetch_tool.build_clients = build_clients
    _fetch_tool.refresh_cache_index_for_doi = refresh_cache_index_for_doi
    _fetch_tool._fetch_paper_envelope = _fetch_paper_envelope
    _fetch_tool._write_cached_fetch_envelope = _write_cached_fetch_envelope

    _cache_payloads.build_runtime_env = build_runtime_env
    _cache_payloads.resolve_mcp_download_dir = resolve_mcp_download_dir
    _cache_payloads.find_cached_entry = find_cached_entry
    _cache_payloads.list_cache_entries = list_cache_entries
    _cache_payloads.preferred_cached_entries = preferred_cached_entries
    _cache_payloads.refresh_cache_index_for_doi = refresh_cache_index_for_doi

    _batch.build_runtime_env = build_runtime_env


def resolve_paper_payload(
    *,
    query: str | None = None,
    title: str | None = None,
    authors: list[str] | str | None = None,
    year: int | None = None,
    env: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
    context: Any | None = None,
) -> dict[str, Any]:
    _sync_dependency_overrides()
    return _fetch_tool.resolve_paper_payload(
        query=query,
        title=title,
        authors=authors,
        year=year,
        env=env,
        transport=transport,
        context=context,
    )


def has_fulltext_payload(
    *,
    query: str,
    env: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
    context: Any | None = None,
) -> dict[str, Any]:
    _sync_dependency_overrides()
    return _fetch_tool.has_fulltext_payload(
        query=query,
        env=env,
        transport=transport,
        context=context,
    )


def fetch_paper_payload(
    *,
    query: str,
    modes: list[str] | None = None,
    strategy: FetchStrategyInput | Mapping[str, Any] | None = None,
    include_refs: str | None = None,
    max_tokens: int | str = "full_text",
    prefer_cache: bool = False,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
    transport: HttpTransport | None = None,
    context: Any | None = None,
) -> dict[str, Any]:
    _sync_dependency_overrides()
    return _fetch_tool.fetch_paper_payload(
        query=query,
        modes=modes,
        strategy=strategy,
        include_refs=include_refs,
        max_tokens=max_tokens,
        prefer_cache=prefer_cache,
        env=env,
        download_dir=download_dir,
        transport=transport,
        context=context,
    )


def list_cached_payload(
    *,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
) -> dict[str, Any]:
    _sync_dependency_overrides()
    return _cache_payloads.list_cached_payload(env=env, download_dir=download_dir)


def get_cached_payload(
    *,
    doi: str,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
) -> dict[str, Any]:
    _sync_dependency_overrides()
    return _cache_payloads.get_cached_payload(doi=doi, env=env, download_dir=download_dir)


def cached_entry_payload(
    *,
    entry_id: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    _sync_dependency_overrides()
    return _cache_payloads.cached_entry_payload(entry_id=entry_id, env=env)


def provider_status_payload(
    *,
    env: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
) -> dict[str, Any]:
    _sync_dependency_overrides()
    return _fetch_tool.provider_status_payload(env=env, transport=transport)


def batch_resolve_payload(
    *,
    queries: list[str],
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    _sync_dependency_overrides()
    return _batch.batch_resolve_payload(queries=queries, concurrency=concurrency, env=env)


def batch_check_payload(
    *,
    queries: list[str],
    mode: str = "metadata",
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    _sync_dependency_overrides()
    return _batch.batch_check_payload(queries=queries, mode=mode, concurrency=concurrency, env=env)


def resolve_paper_tool(
    *,
    query: str | None = None,
    title: str | None = None,
    authors: list[str] | str | None = None,
    year: int | None = None,
    env: Mapping[str, str] | None = None,
) -> CallToolResult:
    _sync_dependency_overrides()
    return _fetch_tool.resolve_paper_tool(query=query, title=title, authors=authors, year=year, env=env)


def has_fulltext_tool(
    *,
    query: str,
    env: Mapping[str, str] | None = None,
) -> CallToolResult:
    _sync_dependency_overrides()
    return _fetch_tool.has_fulltext_tool(query=query, env=env)


def fetch_paper_tool(
    *,
    query: str,
    modes: list[str] | None = None,
    strategy: FetchStrategyInput | Mapping[str, Any] | None = None,
    include_refs: str | None = None,
    max_tokens: int | str = "full_text",
    prefer_cache: bool = False,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
) -> CallToolResult:
    _sync_dependency_overrides()
    return _fetch_tool.fetch_paper_tool(
        query=query,
        modes=modes,
        strategy=strategy,
        include_refs=include_refs,
        max_tokens=max_tokens,
        prefer_cache=prefer_cache,
        env=env,
        download_dir=download_dir,
    )


def list_cached_tool(
    *,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
) -> CallToolResult:
    _sync_dependency_overrides()
    return _cache_payloads.list_cached_tool(env=env, download_dir=download_dir)


def get_cached_tool(
    *,
    doi: str,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
) -> CallToolResult:
    _sync_dependency_overrides()
    return _cache_payloads.get_cached_tool(doi=doi, env=env, download_dir=download_dir)


def provider_status_tool(
    *,
    env: Mapping[str, str] | None = None,
) -> CallToolResult:
    _sync_dependency_overrides()
    return _fetch_tool.provider_status_tool(env=env)


def batch_resolve_tool(
    *,
    queries: list[str],
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
) -> CallToolResult:
    _sync_dependency_overrides()
    return _batch.batch_resolve_tool(queries=queries, concurrency=concurrency, env=env)


def batch_check_tool(
    *,
    queries: list[str],
    mode: str = "metadata",
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
) -> CallToolResult:
    _sync_dependency_overrides()
    return _batch.batch_check_tool(queries=queries, mode=mode, concurrency=concurrency, env=env)


async def fetch_paper_tool_async(
    *,
    query: str,
    modes: list[str] | None = None,
    strategy: FetchStrategyInput | Mapping[str, Any] | None = None,
    include_refs: str | None = None,
    max_tokens: int | str = "full_text",
    prefer_cache: bool = False,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
    ctx: Context | None = None,
) -> CallToolResult:
    _sync_dependency_overrides()
    return await _fetch_tool.fetch_paper_tool_async(
        query=query,
        modes=modes,
        strategy=strategy,
        include_refs=include_refs,
        max_tokens=max_tokens,
        prefer_cache=prefer_cache,
        env=env,
        download_dir=download_dir,
        ctx=ctx,
    )


async def batch_resolve_tool_async(
    *,
    queries: list[str],
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
    ctx: Context | None = None,
) -> CallToolResult:
    _sync_dependency_overrides()
    return await _batch.batch_resolve_tool_async(queries=queries, concurrency=concurrency, env=env, ctx=ctx)


async def batch_check_tool_async(
    *,
    queries: list[str],
    mode: str = "metadata",
    concurrency: int = 1,
    env: Mapping[str, str] | None = None,
    ctx: Context | None = None,
) -> CallToolResult:
    _sync_dependency_overrides()
    return await _batch.batch_check_tool_async(queries=queries, mode=mode, concurrency=concurrency, env=env, ctx=ctx)
