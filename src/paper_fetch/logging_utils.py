"""Helpers for dual-purpose human-readable and structured logs."""

from __future__ import annotations

import json
import logging
from functools import cache
from typing import Any
from collections.abc import Mapping

_REDACTED_LOG_VALUE = "***"
_HEADER_CONTAINER_KEYS = frozenset(
    {"headers", "request-headers", "response-headers", "http-headers"}
)
_QUERY_CONTAINER_KEYS = frozenset(
    {"query", "params", "query-params", "query-parameters"}
)
_BASE_SENSITIVE_LOG_KEYS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "set-cookie2",
        "api-key",
        "apikey",
        "access-key",
        "secret",
        "token",
        "signature",
        "password",
    }
)


def _normalized_log_key(value: str | None) -> str:
    return str(value or "").strip().lower().replace("_", "-")


@cache
def _sensitive_log_keys() -> frozenset[str]:
    from .provider_catalog import provider_sensitive_header_names

    return frozenset(
        _normalized_log_key(value)
        for value in (*_BASE_SENSITIVE_LOG_KEYS, *provider_sensitive_header_names())
    )


def _url_log_key(key: str | None) -> bool:
    normalized = _normalized_log_key(key)
    return normalized in {"url", "location", "uri"} or normalized.endswith("-url")


def redact_log_value(
    value: Any,
    *,
    key: str | None = None,
    parent_key: str | None = None,
    query_context: bool = False,
) -> Any:
    """Recursively remove URL queries and credential-bearing fields."""

    normalized_key = _normalized_log_key(key)
    normalized_parent = _normalized_log_key(parent_key)
    active_query_context = query_context or normalized_key in _QUERY_CONTAINER_KEYS
    sensitive_keys = _sensitive_log_keys()
    if normalized_key in sensitive_keys or (
        normalized_parent in _HEADER_CONTAINER_KEYS and normalized_key in sensitive_keys
    ):
        return _REDACTED_LOG_VALUE
    if active_query_context and normalized_key:
        from .http.cache import is_sensitive_query_param_name

        if is_sensitive_query_param_name(normalized_key):
            return _REDACTED_LOG_VALUE
    if isinstance(value, Mapping):
        return {
            str(child_key): redact_log_value(
                child_value,
                key=str(child_key),
                parent_key=key,
                query_context=active_query_context,
            )
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [
            redact_log_value(
                item,
                key=key,
                parent_key=parent_key,
                query_context=active_query_context,
            )
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            redact_log_value(
                item,
                key=key,
                parent_key=parent_key,
                query_context=active_query_context,
            )
            for item in value
        )
    if isinstance(value, str):
        from .http.cache import redact_text_for_diagnostics, redact_url_for_diagnostics

        sanitized = redact_text_for_diagnostics(value)
        return redact_url_for_diagnostics(sanitized) if _url_log_key(key) else sanitized
    return value


def redact_structured_log_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): redact_log_value(value, key=str(key))
        for key, value in payload.items()
    }


def _render_log_value(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if any(char.isspace() for char in text) or any(
        char in text for char in {'"', "'", "="}
    ):
        return json.dumps(text, ensure_ascii=False)
    return text


def format_structured_log_message(event: str, fields: Mapping[str, Any]) -> str:
    tokens = [event]
    tokens.extend(f"{key}={_render_log_value(value)}" for key, value in fields.items())
    return " ".join(tokens)


def structured_log_payload(event: str, **fields: Any) -> dict[str, Any]:
    payload = {"event": event}
    payload.update(fields)
    return payload


def emit_structured_log(
    logger: logging.Logger, level: int, event: str, **fields: Any
) -> None:
    safe_fields = {
        key: redact_log_value(value, key=key) for key, value in fields.items()
    }
    safe_payload = redact_structured_log_payload(
        structured_log_payload(event, **safe_fields)
    )
    logger.log(
        level,
        format_structured_log_message(event, safe_fields),
        extra={"structured_data": safe_payload},
    )


__all__ = [
    "emit_structured_log",
    "format_structured_log_message",
    "redact_log_value",
    "redact_structured_log_payload",
    "structured_log_payload",
]
