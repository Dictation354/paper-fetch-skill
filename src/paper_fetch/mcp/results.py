"""MCP result and error payload helpers."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from mcp.types import CallToolResult, ImageContent, TextContent
from pydantic import ValidationError

from ..http import RequestCancelledError
from ..providers.base import ProviderFailure
from ..service import PaperFetchFailure


def _dump_payload(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, indent=2)


def _tool_result(
    payload: Mapping[str, Any],
    *,
    is_error: bool,
    extra_content: Sequence[TextContent | ImageContent] | None = None,
) -> CallToolResult:
    content: list[TextContent | ImageContent] = [TextContent(type="text", text=_dump_payload(payload))]
    if extra_content:
        content.extend(extra_content)
    return CallToolResult(
        content=content,
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
        return {"status": "error", "reason": _validation_reason(error), "candidates": None, "missing_env": None}
    if isinstance(error, RequestCancelledError):
        return {"status": "error", "reason": "Request cancelled.", "candidates": None, "missing_env": None}
    if isinstance(error, PaperFetchFailure):
        return {
            "status": error.status,
            "reason": error.reason,
            "candidates": error.candidates or None,
            "missing_env": None,
        }
    if isinstance(error, ProviderFailure):
        status = error.code if error.code in {"no_access", "rate_limited"} else "error"
        if error.code == "not_configured" and error.missing_env:
            status = "no_access"
        return {
            "status": status,
            "reason": error.message,
            "candidates": None,
            "missing_env": error.missing_env or None,
        }
    return {"status": "error", "reason": str(error), "candidates": None, "missing_env": None}
