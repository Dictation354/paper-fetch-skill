"""Payload glue for MCP cache listing and lookup tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from collections.abc import Mapping

from mcp.types import CallToolResult

from ..capability_scope import capability_scopes_for_query
from ._deps import MCPDeps, default_mcp_deps
from .cache_index import cache_entry_visible_for_scopes
from .fetch_cache import (
    FetchCache,
    FetchCacheDependencies,
)
from .results import _tool_result, error_payload_from_exception, with_schema_version
from .schemas import FetchStrategyInput, GetCachedRequest

_MCP_DEFAULT_DOWNLOAD_DIR = object()


def _entry_visible_in_runtime_env(
    entry: Mapping[str, Any], runtime_env: Mapping[str, str]
) -> bool:
    doi = str(entry.get("doi") or "").strip()
    if not doi:
        return False
    return cache_entry_visible_for_scopes(
        entry,
        capability_scopes_for_query(runtime_env, doi),
    )


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
    deps: MCPDeps = default_mcp_deps(),
) -> dict[str, Any]:
    runtime_env = deps.build_runtime_env(env)
    effective_download_dir = _resolve_download_dir(runtime_env, download_dir, deps=deps)
    payload = FetchCache(
        effective_download_dir,
        dependencies=FetchCacheDependencies(list_entries=deps.list_cache_entries),
    ).list_payload(_filter_entries=False)
    payload["entries"] = [
        entry
        for entry in payload.get("entries", [])
        if isinstance(entry, Mapping)
        and _entry_visible_in_runtime_env(entry, runtime_env)
    ]
    return with_schema_version(payload)


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

    read_scopes = capability_scopes_for_query(runtime_env, request.doi)
    payload = FetchCache(
        effective_download_dir,
        dependencies=FetchCacheDependencies(
            preferred_entries=deps.preferred_cached_entries,
        ),
        credential_scope=read_scopes[0],
        read_credential_scopes=read_scopes,
    ).get_payload(
        request.doi,
        request=request.to_fetch_request(),
        detail=request.detail,
        preferred_only=request.preferred_only,
    )
    return with_schema_version(payload)


def cached_entry_payload(
    *,
    entry_id: str,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
    deps: MCPDeps = default_mcp_deps(),
) -> dict[str, Any] | None:
    runtime_env = deps.build_runtime_env(env)
    effective_download_dir = _resolve_download_dir(
        runtime_env,
        download_dir,
        deps=deps,
    )
    if effective_download_dir is None:
        return None
    entry = deps.find_cached_entry(effective_download_dir, entry_id)
    if entry is None or not _entry_visible_in_runtime_env(entry, runtime_env):
        return None
    return entry


def list_cached_tool(
    *,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
    deps: MCPDeps = default_mcp_deps(),
) -> CallToolResult:
    try:
        return _tool_result(
            list_cached_payload(
                env=env,
                download_dir=download_dir,
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
