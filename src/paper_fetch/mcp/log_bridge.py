"""Bridge structured paper-fetch logs into MCP notifications."""

from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
import logging
import threading
from typing import Any
from collections.abc import Mapping

from mcp.server.mcpserver import Context

from ..utils import normalize_text
from ..logging_utils import redact_structured_log_payload

_FETCH_LOGGER_NAMES = (
    "paper_fetch.service",
    "paper_fetch.http",
    "paper_fetch.browser_runtime",
)
_LOG_LEVEL_BY_RECORD_LEVEL = {
    logging.DEBUG: "debug",
    logging.INFO: "info",
    logging.WARNING: "warning",
    logging.ERROR: "error",
    logging.CRITICAL: "critical",
}
_SORTED_LOG_LEVELS = sorted(_LOG_LEVEL_BY_RECORD_LEVEL.items())


@dataclass
class _LogTarget:
    ctx: Context
    loop: asyncio.AbstractEventLoop
    _active: bool = field(default=True, init=False, repr=False)
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    def deactivate(self) -> None:
        """Linearize request shutdown against copied-context log emitters."""

        with self._lock:
            self._active = False

    def submit(
        self,
        record: logging.LogRecord,
        payload: Mapping[str, Any],
    ) -> None:
        """Submit only while this request target and its event loop are live."""

        with self._lock:
            if not self._active or self.loop.is_closed() or not self.loop.is_running():
                return
            try:
                notification = self.ctx.session.send_log_message(
                    level=_mcp_log_level(record),
                    data=dict(payload),
                    logger=record.name,
                    related_request_id=self.ctx.request_id,
                )
            except Exception:
                return
            try:
                asyncio.run_coroutine_threadsafe(notification, self.loop)
            except Exception:
                # ``run_coroutine_threadsafe`` can lose a race with an
                # externally closed loop.  Close the never-submitted coroutine
                # so it cannot leak a RuntimeWarning or retain request data.
                notification.close()


_ACTIVE_LOG_TARGET: ContextVar[_LogTarget | None] = ContextVar(
    "paper_fetch_mcp_log_target", default=None
)
_ROUTER_LOCK = threading.RLock()
_ROUTER_REFCOUNT = 0
_ROUTER_LOGGER_STATES: list[tuple[logging.Logger, int]] = []


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


def parse_structured_log_message(
    message: str, *, logger_name: str | None = None
) -> dict[str, Any]:
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
    return redact_structured_log_payload(payload)


def structured_log_payload_from_record(record: logging.LogRecord) -> dict[str, Any]:
    raw_payload = getattr(record, "structured_data", None)
    if isinstance(raw_payload, Mapping):
        payload = dict(raw_payload)
        payload["event"] = normalize_text(payload.get("event")) or "log"
        payload.setdefault("logger", record.name)
        return redact_structured_log_payload(payload)
    return redact_structured_log_payload(
        parse_structured_log_message(record.getMessage(), logger_name=record.name)
    )


def _mcp_log_level(record: logging.LogRecord) -> str:
    for level, name in _SORTED_LOG_LEVELS:
        if record.levelno <= level:
            return name
    return "critical"


class StructuredLogNotificationHandler(logging.Handler):
    def __init__(
        self,
        *,
        ctx: Context | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        super().__init__(level=logging.DEBUG)
        self._target = _LogTarget(ctx=ctx, loop=loop) if ctx and loop else None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            target = self._target or _ACTIVE_LOG_TARGET.get()
            if target is None:
                return
            payload = structured_log_payload_from_record(record)
            target.submit(record, payload)
        except Exception:
            return

    def close(self) -> None:
        target = self._target
        if target is not None:
            target.deactivate()
        super().close()


_GLOBAL_LOG_ROUTER = StructuredLogNotificationHandler()


class PaperFetchLogBridge:
    def __init__(self, *, ctx: Context, loop: asyncio.AbstractEventLoop) -> None:
        self._ctx = ctx
        self._loop = loop
        self._token: Token[_LogTarget | None] | None = None
        self._target: _LogTarget | None = None
        self._entered = False

    def __enter__(self) -> PaperFetchLogBridge:
        global _ROUTER_REFCOUNT
        if self._entered:
            return self
        with _ROUTER_LOCK:
            if _ROUTER_REFCOUNT == 0:
                _ROUTER_LOGGER_STATES.clear()
                for logger_name in _FETCH_LOGGER_NAMES:
                    active_logger = logging.getLogger(logger_name)
                    _ROUTER_LOGGER_STATES.append((active_logger, active_logger.level))
                    if _GLOBAL_LOG_ROUTER not in active_logger.handlers:
                        active_logger.addHandler(_GLOBAL_LOG_ROUTER)
                    active_logger.setLevel(logging.DEBUG)
            _ROUTER_REFCOUNT += 1
        target = _LogTarget(ctx=self._ctx, loop=self._loop)
        self._target = target
        self._token = _ACTIVE_LOG_TARGET.set(target)
        self._entered = True
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        global _ROUTER_REFCOUNT
        if not self._entered:
            return
        target = self._target
        self._target = None
        if target is not None:
            # Copied contexts retain the target object after ContextVar reset.
            # Invalidate it before changing the process-global router lifetime.
            target.deactivate()
        token = self._token
        self._token = None
        self._entered = False
        if token is not None:
            _ACTIVE_LOG_TARGET.reset(token)
        with _ROUTER_LOCK:
            _ROUTER_REFCOUNT = max(0, _ROUTER_REFCOUNT - 1)
            if _ROUTER_REFCOUNT != 0:
                return
            for active_logger, level in _ROUTER_LOGGER_STATES:
                active_logger.removeHandler(_GLOBAL_LOG_ROUTER)
                active_logger.setLevel(level)
            _ROUTER_LOGGER_STATES.clear()
