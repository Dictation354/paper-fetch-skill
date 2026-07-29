"""Shared JSON decoding and root-schema guards for remote APIs."""

from __future__ import annotations

import json
from typing import Any
from collections.abc import Mapping

from .body import build_text_preview
from .cache import (
    redact_text_for_diagnostics,
    redact_url_for_diagnostics,
)
from .errors import RequestErrorCategory, RequestFailure


def decode_json_object_response(
    response: Mapping[str, Any],
    *,
    label: str,
    required_keys: tuple[str, ...] = (),
) -> dict[str, Any]:
    body = response.get("body", b"")
    url = redact_url_for_diagnostics(str(response.get("url") or ""))
    headers = {
        str(key).lower(): str(value)
        for key, value in dict(response.get("headers") or {}).items()
    }
    try:
        payload = json.loads(bytes(body).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        preview = build_text_preview(
            bytes(body) if isinstance(body, (bytes, bytearray)) else b"",
            headers.get("content-type"),
        )
        preview = redact_text_for_diagnostics(preview or "")
        raise RequestFailure(
            int(response.get("status_code") or 200),
            f"{label} returned invalid JSON: {preview}",
            body=(bytes(body) if isinstance(body, (bytes, bytearray)) else b"")[:1024],
            headers=headers,
            url=url,
            error_category=RequestErrorCategory.INVALID_JSON,
        ) from exc
    if not isinstance(payload, Mapping):
        raise RequestFailure(
            int(response.get("status_code") or 200),
            f"{label} JSON root must be an object.",
            body=(bytes(body) if isinstance(body, (bytes, bytearray)) else b"")[:1024],
            headers=headers,
            url=url,
            error_category=RequestErrorCategory.RESPONSE_SCHEMA_MISMATCH,
        )
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise RequestFailure(
            int(response.get("status_code") or 200),
            f"{label} JSON object is missing required keys: {', '.join(missing)}.",
            body=(bytes(body) if isinstance(body, (bytes, bytearray)) else b"")[:1024],
            headers=headers,
            url=url,
            error_category=RequestErrorCategory.RESPONSE_SCHEMA_MISMATCH,
        )
    return dict(payload)


__all__ = ["decode_json_object_response"]
