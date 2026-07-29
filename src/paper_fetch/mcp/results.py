"""MCP result and error payload helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
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

from ..http import RequestCancelledError, RequestFailure
from ..providers.base import ProviderFailure
from ..reason_codes import ERROR, NO_ACCESS, NOT_CONFIGURED, RATE_LIMITED
from ..service import PaperFetchFailure
from ..tracing import TraceEvent

MCP_OUTPUT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class _ErrorPayloadContext:
    code: str | None = None
    error_category: str | None = None
    http_status: int | None = None
    retry_after_seconds: int | None = None
    provider: str | None = None
    route: str | None = None
    stage: str | None = None
    retryable: bool | None = None
    details: Mapping[str, Any] | None = None
    trace: Sequence[TraceEvent] | None = None
    warnings: Sequence[str] | None = None
    source_trail: Sequence[str] | None = None
    candidates: Sequence[Mapping[str, Any]] | None = None
    missing_env: Sequence[str] | None = None


def _dump_payload(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, indent=2)


def with_schema_version(payload: Mapping[str, Any]) -> dict[str, Any]:
    versioned = dict(payload)
    versioned.setdefault("schema_version", MCP_OUTPUT_SCHEMA_VERSION)
    return versioned


def _tool_result(
    payload: Mapping[str, Any],
    *,
    is_error: bool,
    extra_content: Sequence[TextContent | ImageContent] | None = None,
) -> CallToolResult:
    versioned_payload = with_schema_version(payload)
    content: list[
        TextContent | ImageContent | AudioContent | ResourceLink | EmbeddedResource
    ] = [TextContent(type="text", text=_dump_payload(versioned_payload))]
    if extra_content:
        content.extend(extra_content)
    return CallToolResult(
        content=content,
        structured_content=versioned_payload,
        is_error=is_error,
    )


def _validation_reason(error: ValidationError) -> str:
    messages: list[str] = []
    for entry in error.errors(include_url=False):
        location = ".".join(str(part) for part in entry.get("loc", ())) or "request"
        messages.append(f"{location}: {entry.get('msg', 'invalid value')}")
    return "Invalid tool arguments. " + "; ".join(messages)


def _error_payload(
    *,
    status: str,
    reason: str,
    context: _ErrorPayloadContext | None = None,
) -> dict[str, Any]:
    error = context or _ErrorPayloadContext()
    return with_schema_version(
        {
            "status": status,
            "reason": reason,
            "code": error.code or status,
            "http_status": error.http_status,
            "error_category": error.error_category or error.code or status,
            "retry_after_seconds": error.retry_after_seconds,
            "provider": error.provider,
            "route": error.route,
            "stage": error.stage,
            "retryable": error.retryable,
            "details": dict(error.details or {}),
            "trace": [asdict(item) for item in (error.trace or [])],
            "warnings": [str(item) for item in (error.warnings or [])],
            "source_trail": [str(item) for item in (error.source_trail or [])],
            "candidates": list(error.candidates) if error.candidates else None,
            "missing_env": list(error.missing_env) if error.missing_env else None,
        }
    )


def _status_from_http_status(status_code: int | None) -> str:
    if status_code == 429:
        return RATE_LIMITED
    if status_code in {401, 403}:
        return NO_ACCESS
    return ERROR


def is_rate_limited_payload(payload: Mapping[str, Any]) -> bool:
    for key in ("status", "code", "error_category"):
        if payload.get(key) == RATE_LIMITED:
            return True
    return (
        payload.get("http_status") == 429
        or payload.get("retry_after_seconds") is not None
    )


def error_payload_from_exception(error: Exception) -> dict[str, Any]:
    if isinstance(error, ValidationError):
        return _error_payload(
            status=ERROR,
            reason=_validation_reason(error),
            context=_ErrorPayloadContext(
                code="validation_error",
                error_category="validation_error",
            ),
        )
    if isinstance(error, RequestCancelledError):
        return _error_payload(
            status=ERROR,
            reason="Request cancelled.",
            context=_ErrorPayloadContext(
                code="request_cancelled",
                error_category="cancelled",
            ),
        )
    if isinstance(error, RequestFailure):
        status = _status_from_http_status(error.status_code)
        category = RATE_LIMITED if error.status_code == 429 else error.error_category
        category_text = str(category) if category is not None else status
        code = (
            f"http_{error.status_code}"
            if error.status_code is not None
            else category_text
        )
        return _error_payload(
            status=status,
            reason=str(error),
            context=_ErrorPayloadContext(
                code=code,
                error_category=category_text,
                http_status=error.status_code,
                retry_after_seconds=error.retry_after_seconds,
            ),
        )
    if isinstance(error, PaperFetchFailure):
        return _error_payload(
            status=error.status,
            reason=error.reason,
            context=_ErrorPayloadContext(
                code=error.status,
                error_category=error.status,
                candidates=error.candidates,
                http_status=error.http_status,
                retry_after_seconds=error.retry_after_seconds,
                provider=error.provider,
                route=error.route,
                stage=error.stage,
                retryable=error.retryable,
                details=error.details,
                trace=error.trace,
                warnings=error.warnings,
                source_trail=error.source_trail,
                missing_env=error.missing_env,
            ),
        )
    if isinstance(error, ProviderFailure):
        status = error.code if error.code in {NO_ACCESS, RATE_LIMITED} else ERROR
        if error.code == NOT_CONFIGURED and error.missing_env:
            status = NO_ACCESS
        return _error_payload(
            status=status,
            reason=error.message,
            context=_ErrorPayloadContext(
                code=error.code,
                error_category=error.error_category or error.code,
                http_status=error.http_status,
                retry_after_seconds=error.retry_after_seconds,
                provider=error.provider,
                route=error.route,
                stage=error.stage,
                retryable=error.retryable,
                details=error.details,
                trace=error.trace,
                warnings=error.warnings,
                source_trail=error.source_trail,
                missing_env=error.missing_env,
            ),
        )
    return _error_payload(
        status=ERROR,
        reason=str(error),
        context=_ErrorPayloadContext(code=ERROR, error_category=ERROR),
    )
