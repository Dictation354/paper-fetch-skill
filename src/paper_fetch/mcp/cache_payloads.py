"""Payload glue for MCP cache listing and lookup tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from collections.abc import Mapping

from mcp.types import CallToolResult

from ._deps import MCPDeps, default_mcp_deps
from .cache_index import (
    CACHE_INDEX_MODE_INDEX,
    CACHE_INDEX_MODE_RESCAN,
    CACHE_INDEX_MODE_REFRESH,
)
from .fetch_cache import FetchCache
from .results import _tool_result, error_payload_from_exception, with_schema_version
from .schemas import FetchStrategyInput, GetCachedRequest

_MCP_DEFAULT_DOWNLOAD_DIR = object()
_CACHE_MODES = {
    CACHE_INDEX_MODE_INDEX,
    CACHE_INDEX_MODE_REFRESH,
    CACHE_INDEX_MODE_RESCAN,
}


def _resolve_download_dir(
    runtime_env: Mapping[str, str],
    download_dir: Path | None | object,
    *,
    deps: MCPDeps = default_mcp_deps(),
) -> Path | None:
    if download_dir is _MCP_DEFAULT_DOWNLOAD_DIR:
        return deps.resolve_mcp_download_dir(runtime_env)
    return download_dir  # type: ignore[return-value]


def list_cached_payload(
    *,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
    cache_mode: str = CACHE_INDEX_MODE_INDEX,
    deps: MCPDeps = default_mcp_deps(),
) -> dict[str, Any]:
    if cache_mode not in _CACHE_MODES:
        raise ValueError("cache_mode must be one of: index, refresh, rescan.")
    runtime_env = deps.build_runtime_env(env)
    effective_download_dir = _resolve_download_dir(runtime_env, download_dir, deps=deps)
    return with_schema_version(
        FetchCache(
            effective_download_dir,
            list_cache_entries_fn=deps.list_cache_entries,
        ).list_payload(cache_mode=cache_mode)
    )


def get_cached_payload(
    *,
    doi: str,
    detail: str = "full",
    preferred_only: bool = False,
    modes: list[str] | None = None,
    strategy: FetchStrategyInput | Mapping[str, Any] | None = None,
    include_refs: str | None = None,
    max_tokens: int | str = "full_text",
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
    deps: MCPDeps = default_mcp_deps(),
) -> dict[str, Any]:
    request = GetCachedRequest.model_validate(
        {
            "doi": doi,
            "detail": detail,
            "preferred_only": preferred_only,
            "modes": modes,
            "strategy": strategy,
            "include_refs": include_refs,
            "max_tokens": max_tokens,
        }
    )
    runtime_env = deps.build_runtime_env(env)
    effective_download_dir = _resolve_download_dir(runtime_env, download_dir, deps=deps)
    return with_schema_version(
        FetchCache(
            effective_download_dir,
            refresh_cache_index_for_doi_fn=deps.refresh_cache_index_for_doi,
            preferred_cached_entries_fn=deps.preferred_cached_entries,
        ).get_payload(
            request.doi,
            request=request.to_fetch_request(),
            detail=request.detail,
            preferred_only=request.preferred_only,
        )
    )


def cached_entry_payload(
    *,
    entry_id: str,
    env: Mapping[str, str] | None = None,
    deps: MCPDeps = default_mcp_deps(),
) -> dict[str, Any] | None:
    runtime_env = deps.build_runtime_env(env)
    default_download_dir = deps.resolve_mcp_download_dir(runtime_env)
    return deps.find_cached_entry(default_download_dir, entry_id)


def list_cached_tool(
    *,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
    cache_mode: str = CACHE_INDEX_MODE_INDEX,
    deps: MCPDeps = default_mcp_deps(),
) -> CallToolResult:
    try:
        return _tool_result(
            list_cached_payload(
                env=env,
                download_dir=download_dir,
                cache_mode=cache_mode,
                deps=deps,
            ),
            is_error=False,
        )
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)


def get_cached_tool(
    *,
    doi: str,
    detail: str = "full",
    preferred_only: bool = False,
    modes: list[str] | None = None,
    strategy: FetchStrategyInput | Mapping[str, Any] | None = None,
    include_refs: str | None = None,
    max_tokens: int | str = "full_text",
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
    deps: MCPDeps = default_mcp_deps(),
) -> CallToolResult:
    try:
        return _tool_result(
            get_cached_payload(
                doi=doi,
                detail=detail,
                preferred_only=preferred_only,
                modes=modes,
                strategy=strategy,
                include_refs=include_refs,
                max_tokens=max_tokens,
                env=env,
                download_dir=download_dir,
                deps=deps,
            ),
            is_error=False,
        )
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)
