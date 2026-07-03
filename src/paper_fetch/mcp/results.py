"""MCP result and error payload helpers."""

from __future__ import annotations

import json
from typing import Any
from collections.abc import Mapping, Sequence

from mcp.types import (
    AudioContent,
    CallToolResult,
    EmbeddedResource,
    ImageContent,
    ResourceLink,
    TextContent,
)
from pydantic import ValidationError

from ..http import RequestCancelledError
from ..providers.base import ProviderFailure
from ..reason_codes import ERROR, NO_ACCESS, NOT_CONFIGURED, RATE_LIMITED
from ..service import PaperFetchFailure


def _dump_payload(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, indent=2)


def _tool_result(
    payload: Mapping[str, Any],
    *,
    is_error: bool,
    extra_content: Sequence[TextContent | ImageContent] | None = None,
) -> CallToolResult:
    content: list[
        TextContent | ImageContent | AudioContent | ResourceLink | EmbeddedResource
    ] = [TextContent(type="text", text=_dump_payload(payload))]
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
        return {
            "status": ERROR,
            "reason": _validation_reason(error),
            "candidates": None,
            "missing_env": None,
        }
    if isinstance(error, RequestCancelledError):
        return {
            "status": ERROR,
            "reason": "Request cancelled.",
            "candidates": None,
            "missing_env": None,
        }
    if isinstance(error, PaperFetchFailure):
        return {
            "status": error.status,
            "reason": error.reason,
            "candidates": error.candidates or None,
            "missing_env": None,
        }
    if isinstance(error, ProviderFailure):
        status = error.code if error.code in {NO_ACCESS, RATE_LIMITED} else ERROR
        if error.code == NOT_CONFIGURED and error.missing_env:
            status = NO_ACCESS
        return {
            "status": status,
            "reason": error.message,
            "candidates": None,
            "missing_env": error.missing_env or None,
        }
    return {
        "status": ERROR,
        "reason": str(error),
        "candidates": None,
        "missing_env": None,
    }
