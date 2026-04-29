"""Bridge structured paper-fetch logs into MCP notifications."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

from mcp.server.fastmcp import Context

from ..utils import normalize_text

_FETCH_LOGGER_NAMES = ("paper_fetch.service", "paper_fetch.http")
_LOG_LEVEL_BY_RECORD_LEVEL = {
    logging.DEBUG: "debug",
    logging.INFO: "info",
    logging.WARNING: "warning",
    logging.ERROR: "error",
    logging.CRITICAL: "critical",
}


def _parse_log_value(raw_value: str) -> Any:
    if raw_value == "None":
        return None
    lowered = raw_value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        if any(marker in raw_value for marker in (".", "e", "E")):
            return float(raw_value)
        return int(raw_value)
    except ValueError:
        return raw_value


def parse_structured_log_message(message: str, *, logger_name: str | None = None) -> dict[str, Any]:
    normalized = normalize_text(message)
    payload: dict[str, Any] = {"event": "log"}
    if logger_name:
        payload["logger"] = logger_name
    if not normalized:
        return payload

    parts = normalized.split()
    payload["event"] = parts[0]
    unparsed_tokens: list[str] = []

    for token in parts[1:]:
        if "=" not in token:
            unparsed_tokens.append(token)
            continue
        key, raw_value = token.split("=", 1)
        if not key:
            unparsed_tokens.append(token)
            continue
        payload[key] = _parse_log_value(raw_value)

    if unparsed_tokens:
        payload["raw_message"] = normalized
    return payload


def structured_log_payload_from_record(record: logging.LogRecord) -> dict[str, Any]:
    raw_payload = getattr(record, "structured_data", None)
    if isinstance(raw_payload, Mapping):
        payload = dict(raw_payload)
        payload["event"] = normalize_text(payload.get("event")) or "log"
        payload.setdefault("logger", record.name)
        return payload
    return parse_structured_log_message(record.getMessage(), logger_name=record.name)


def _mcp_log_level(record: logging.LogRecord) -> str:
    for level, name in sorted(_LOG_LEVEL_BY_RECORD_LEVEL.items()):
        if record.levelno <= level:
            return name
    return "debug"


class StructuredLogNotificationHandler(logging.Handler):
    def __init__(self, *, ctx: Context, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(level=logging.DEBUG)
        self._ctx = ctx
        self._loop = loop

    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload = structured_log_payload_from_record(record)
            asyncio.run_coroutine_threadsafe(
                self._ctx.session.send_log_message(
                    level=_mcp_log_level(record),
                    data=payload,
                    logger=record.name,
                    related_request_id=self._ctx.request_id,
                ),
                self._loop,
            )
        except Exception:
            return


class PaperFetchLogBridge:
    def __init__(self, *, ctx: Context, loop: asyncio.AbstractEventLoop) -> None:
        self._ctx = ctx
        self._loop = loop
        self._handler = StructuredLogNotificationHandler(ctx=ctx, loop=loop)
        self._logger_states: list[tuple[logging.Logger, int]] = []

    def __enter__(self) -> "PaperFetchLogBridge":
        for logger_name in _FETCH_LOGGER_NAMES:
            logger = logging.getLogger(logger_name)
            self._logger_states.append((logger, logger.level))
            logger.addHandler(self._handler)
            logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        for logger, level in self._logger_states:
            logger.removeHandler(self._handler)
            logger.setLevel(level)
        self._handler.close()
