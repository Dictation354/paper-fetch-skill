"""HTTP exception and network error helpers."""

from __future__ import annotations

import socket
from collections.abc import Iterator
from typing import Mapping

import urllib3


class RequestFailure(Exception):
    """HTTP or transport failure."""

    def __init__(
        self,
        status_code: int | None,
        message: str,
        *,
        body: bytes = b"",
        headers: Mapping[str, str] | None = None,
        url: str | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.headers = dict(headers or {})
        self.url = url
        self.retry_after_seconds = retry_after_seconds


class RequestCancelledError(Exception):
    """Raised when a cooperative cancellation check trips."""


def build_http_error_message(status_code: int | None, url: str, *, retry_after_seconds: int | None = None) -> str:
    from .cache import redact_url_for_cache

    message = f"HTTP {status_code} for {redact_url_for_cache(url)}"
    if retry_after_seconds is not None:
        message += f" (Retry-After: {retry_after_seconds}s)"
    return message


def iter_network_error_causes(exc: Exception) -> Iterator[BaseException]:
    pending: list[BaseException] = [exc]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        current_id = id(current)
        if current_id in seen:
            continue
        seen.add(current_id)
        yield current
        for attribute_name in ("reason", "__cause__", "__context__"):
            nested = getattr(current, attribute_name, None)
            if isinstance(nested, BaseException):
                pending.append(nested)
        for item in getattr(current, "args", ()):
            if isinstance(item, BaseException):
                pending.append(item)


def is_timeout_network_error(exc: Exception) -> bool:
    return any(
        isinstance(item, (socket.timeout, TimeoutError, urllib3.exceptions.TimeoutError))
        for item in iter_network_error_causes(exc)
    )


def build_network_error_detail(exc: Exception) -> str:
    for nested in iter_network_error_causes(exc):
        if nested is exc:
            continue
        detail = str(nested).strip()
        if detail:
            return detail
    return str(exc)
