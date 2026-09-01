"""Typed dependency container for MCP payload and tool helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Callable

from ..config import build_runtime_env, resolve_mcp_download_dir
from ..browser_preflight import run_browser_provider_preflight
from ..providers.registry import build_clients
from ..service import fetch_paper as service_fetch_paper
from ..service import probe_has_fulltext as service_probe_has_fulltext
from ..service import resolve_paper as service_resolve_paper
from .cache_index import (
    find_cached_entry,
    list_cache_entries,
    preferred_cached_entries,
    register_markdown_entry,
)


@dataclass(frozen=True)
class MCPDeps:
    build_runtime_env: Callable[..., Any]
    service_fetch_paper: Callable[..., Any]
    service_probe_has_fulltext: Callable[..., Any]
    service_resolve_paper: Callable[..., Any]
    build_clients: Callable[..., Any]
    fetch_paper_envelope: Callable[..., Any]
    write_cached_fetch_envelope: Callable[..., Any]
    resolve_mcp_download_dir: Callable[..., Any]
    find_cached_entry: Callable[..., Any]
    list_cache_entries: Callable[..., Any]
    preferred_cached_entries: Callable[..., Any]
    register_markdown_entry: Callable[..., Any]
    run_browser_provider_preflight: Callable[..., Any]


def _fetch_paper_envelope(*args: Any, **kwargs: Any) -> Any:
    from .fetch_tool import _fetch_paper_envelope as fetch_paper_envelope

    return fetch_paper_envelope(*args, **kwargs)


def _write_cached_fetch_envelope(*args: Any, **kwargs: Any) -> Any:
    from .fetch_tool import _write_cached_fetch_envelope as write_cached_fetch_envelope

    return write_cached_fetch_envelope(*args, **kwargs)


def default_mcp_deps() -> MCPDeps:
    return MCPDeps(
        build_runtime_env=build_runtime_env,
        service_fetch_paper=service_fetch_paper,
        service_probe_has_fulltext=service_probe_has_fulltext,
        service_resolve_paper=service_resolve_paper,
        build_clients=build_clients,
        fetch_paper_envelope=_fetch_paper_envelope,
        write_cached_fetch_envelope=_write_cached_fetch_envelope,
        resolve_mcp_download_dir=resolve_mcp_download_dir,
        find_cached_entry=find_cached_entry,
        list_cache_entries=list_cache_entries,
        preferred_cached_entries=preferred_cached_entries,
        register_markdown_entry=register_markdown_entry,
        run_browser_provider_preflight=run_browser_provider_preflight,
    )
