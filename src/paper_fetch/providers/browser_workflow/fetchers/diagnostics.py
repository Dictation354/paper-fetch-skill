"""Failure diagnostics for browser workflow fetchers."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from ....extraction.html.signals import (
    CLOUDFLARE_CHALLENGE_TITLE_TOKENS as _CLOUDFLARE_CHALLENGE_TITLE_TOKENS,
)
from ....utils import normalize_text

BROWSER_CONTEXT_ERROR = "browser_context_error"


def _looks_like_cloudflare_challenge_title(title: str | None) -> bool:
    normalized = normalize_text(title).lower()
    return bool(
        normalized
        and any(token in normalized for token in _CLOUDFLARE_CHALLENGE_TITLE_TOKENS)
    )


def _compact_failure_diagnostic(values: Mapping[str, Any]) -> dict[str, Any]:
    diagnostic: dict[str, Any] = {}
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, str):
            normalized = normalize_text(value)
            if normalized:
                diagnostic[key] = normalized
            continue
        if isinstance(value, (bool, int, float)):
            diagnostic[key] = value
            continue
        if isinstance(value, list) and value:
            diagnostic[key] = value
            continue
        if isinstance(value, Mapping) and value:
            diagnostic[key] = dict(value)
    return diagnostic


def _copy_failure_diagnostic(values: Mapping[str, Any]) -> dict[str, Any]:
    copied = dict(values)
    recovery_attempts = values.get("recovery_attempts")
    if isinstance(recovery_attempts, list):
        copied["recovery_attempts"] = [
            dict(item) if isinstance(item, Mapping) else item
            for item in recovery_attempts
        ]
    return copied


def _context_failure_diagnostic(exc: Exception) -> dict[str, Any]:
    message = normalize_text(str(exc))
    return _compact_failure_diagnostic(
        {
            "reason": BROWSER_CONTEXT_ERROR,
            "error_type": exc.__class__.__name__,
            "error_message": message[:240] if message else exc.__class__.__name__,
        },
    )


def _is_timeout_error(value: str | None) -> bool:
    normalized = normalize_text(value).lower()
    return bool(normalized and ("timeout" in normalized or "aborterror" in normalized))


def _image_fetch_failure_reason(
    *, error: str | None = None, timed_out: bool = False
) -> str:
    if timed_out or _is_timeout_error(error):
        return "image_fetch_timeout"
    return "image_fetch_error"
