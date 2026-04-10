"""Thin MCP tool wrappers over the service layer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from mcp.types import CallToolResult, TextContent
from pydantic import ValidationError

from ..config import build_runtime_env, resolve_mcp_download_dir
from ..providers.base import ProviderFailure
from ..service import PaperFetchFailure, fetch_paper as service_fetch_paper
from ..service import resolve_paper as service_resolve_paper
from .schemas import FetchPaperRequest, FetchStrategyInput, ResolvePaperRequest

_MCP_DEFAULT_DOWNLOAD_DIR = object()


def _dump_payload(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, indent=2)


def _tool_result(payload: Mapping[str, Any], *, is_error: bool) -> CallToolResult:
    text = _dump_payload(payload)
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structuredContent=dict(payload),
        isError=is_error,
    )


def _validation_reason(error: ValidationError) -> str:
    messages: list[str] = []
    for entry in error.errors(include_url=False):
        location = ".".join(str(part) for part in entry.get("loc", ())) or "request"
        messages.append(f"{location}: {entry.get('msg', 'invalid value')}")
    return "Invalid tool arguments. " + "; ".join(messages)


def error_payload_from_exception(error: Exception) -> dict[str, Any]:
    if isinstance(error, ValidationError):
        return {"status": "error", "reason": _validation_reason(error), "candidates": None}
    if isinstance(error, PaperFetchFailure):
        return {
            "status": error.status,
            "reason": error.reason,
            "candidates": error.candidates or None,
        }
    if isinstance(error, ProviderFailure):
        return {"status": "error", "reason": error.message, "candidates": None}
    return {"status": "error", "reason": str(error), "candidates": None}


def resolve_paper_payload(
    *,
    query: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    request = ResolvePaperRequest(query=query)
    runtime_env = build_runtime_env(env)
    resolved = service_resolve_paper(request.query, env=runtime_env)
    return resolved.to_dict()


def fetch_paper_payload(
    *,
    query: str,
    modes: list[str] | None = None,
    strategy: FetchStrategyInput | Mapping[str, Any] | None = None,
    include_refs: str = "top10",
    max_tokens: int = 8000,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
) -> dict[str, Any]:
    request = FetchPaperRequest(
        query=query,
        modes=modes,
        strategy=strategy,
        include_refs=include_refs,
        max_tokens=max_tokens,
    )
    runtime_env = build_runtime_env(env)
    effective_download_dir = resolve_mcp_download_dir(runtime_env) if download_dir is _MCP_DEFAULT_DOWNLOAD_DIR else download_dir
    envelope = service_fetch_paper(
        request.query,
        modes=request.requested_modes(),
        strategy=request.strategy.to_service_strategy(),
        render=request.to_render_options(),
        download_dir=effective_download_dir,
        env=runtime_env,
    )
    return envelope.to_dict()


def resolve_paper_tool(*, query: str, env: Mapping[str, str] | None = None) -> CallToolResult:
    try:
        return _tool_result(resolve_paper_payload(query=query, env=env), is_error=False)
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)


def fetch_paper_tool(
    *,
    query: str,
    modes: list[str] | None = None,
    strategy: FetchStrategyInput | Mapping[str, Any] | None = None,
    include_refs: str = "top10",
    max_tokens: int = 8000,
    env: Mapping[str, str] | None = None,
    download_dir: Path | None | object = _MCP_DEFAULT_DOWNLOAD_DIR,
) -> CallToolResult:
    try:
        return _tool_result(
            fetch_paper_payload(
                query=query,
                modes=modes,
                strategy=strategy,
                include_refs=include_refs,
                max_tokens=max_tokens,
                env=env,
                download_dir=download_dir,
            ),
            is_error=False,
        )
    except Exception as error:
        return _tool_result(error_payload_from_exception(error), is_error=True)
