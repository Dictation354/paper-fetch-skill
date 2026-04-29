"""Payload glue for MCP cache listing and lookup tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from mcp.types import CallToolResult

from ..config import build_runtime_env as _build_runtime_env
from ..config import resolve_mcp_download_dir as _resolve_mcp_download_dir
from .cache_index import (
    find_cached_entry as _find_cached_entry,
    list_cache_entries as _list_cache_entries,
    preferred_cached_entries as _preferred_cached_entries,
    refresh_cache_index_for_doi as _refresh_cache_index_for_doi,
)
from .fetch_cache import FetchCache
from .results import _tool_result, error_payload_from_exception
from .schemas import ResolvePaperRequest

build_runtime_env = _build_runtime_env
resolve_mcp_download_dir = _resolve_mcp_download_dir
find_cached_entry = _find_cached_entry
list_cache_entries = _list_cache_entries
preferred_cached_entries = _preferred_cached_entries
refresh_cache_index_for_doi = _refresh_cache_index_for_doi

_MCP_DEFAULT_DOWNLOAD_DIR = object()


def _resolve_download_dir(
    runtime_env: Mapping[str, str],
    download_dir: Path | None | object,
) -> Path | None:
    if download_dir is _MCP_DEFAULT_DOWNLOAD_DIR:
        return resolve_mcp_download_dir(runtime_env)
    return download_dir


def list_cached_payload(
    *,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
) -> dict[str, Any]:
    runtime_env = build_runtime_env(env)
    effective_download_dir = _resolve_download_dir(runtime_env, download_dir)
    return FetchCache(
        effective_download_dir,
        list_cache_entries_fn=list_cache_entries,
    ).list_payload()


def get_cached_payload(
    *,
    doi: str,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
) -> dict[str, Any]:
    request = ResolvePaperRequest(query=doi)
    runtime_env = build_runtime_env(env)
    effective_download_dir = _resolve_download_dir(runtime_env, download_dir)
    return FetchCache(
        effective_download_dir,
        refresh_cache_index_for_doi_fn=refresh_cache_index_for_doi,
        preferred_cached_entries_fn=preferred_cached_entries,
    ).get_payload(request.composed_query())


def cached_entry_payload(
    *,
    entry_id: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    runtime_env = build_runtime_env(env)
    default_download_dir = resolve_mcp_download_dir(runtime_env)
    return find_cached_entry(default_download_dir, entry_id)


def list_cached_tool(
    *,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
) -> CallToolResult:
    try:
        return _tool_result(
            list_cached_payload(
                env=env,
                download_dir=download_dir,
            ),
            is_error=False,
        )
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)


def get_cached_tool(
    *,
    doi: str,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
) -> CallToolResult:
    try:
        return _tool_result(
            get_cached_payload(
                doi=doi,
                env=env,
                download_dir=download_dir,
            ),
            is_error=False,
        )
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)
