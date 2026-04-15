"""Helpers for dual-purpose human-readable and structured logs."""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping


def _render_log_value(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if any(char.isspace() for char in text) or any(char in text for char in {'"', "'", "="}):
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


def emit_structured_log(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    logger.log(
        level,
        format_structured_log_message(event, fields),
        extra={"structured_data": structured_log_payload(event, **fields)},
    )
