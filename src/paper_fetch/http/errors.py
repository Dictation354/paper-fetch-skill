"""HTTP exception and network error helpers."""

from __future__ import annotations

import socket
import ssl
from collections.abc import Iterator
from enum import StrEnum
from collections.abc import Mapping

import urllib3


class RequestErrorCategory(StrEnum):
    """Stable transport-level category for network failures."""

    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    TLS_ERROR = "tls_error"
    DNS_ERROR = "dns_error"
    CONNECTION_RESET = "connection_reset"
    CONNECTION_CLOSED = "connection_closed"
    RESPONSE_TOO_LARGE = "response_too_large"
    UNSUPPORTED_SCHEME = "unsupported_url_scheme"
    UNSAFE_REDIRECT = "unsafe_redirect"
    INVALID_JSON = "invalid_json"
    RESPONSE_SCHEMA_MISMATCH = "response_schema_mismatch"


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
        error_category: RequestErrorCategory | str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.headers = dict(headers or {})
        self.url = url
        self.retry_after_seconds = retry_after_seconds
        self.error_category = _normalize_request_error_category(error_category)


def _normalize_request_error_category(
    value: RequestErrorCategory | str | None,
) -> RequestErrorCategory | None:
    if isinstance(value, RequestErrorCategory):
        return value
    if value is None:
        return None
    try:
        return RequestErrorCategory(str(value))
    except ValueError:
        return None


class RequestCancelledError(Exception):
    """Raised when a cooperative cancellation check trips."""


def build_http_error_message(
    status_code: int | None, url: str, *, retry_after_seconds: int | None = None
) -> str:
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
        isinstance(
            item, (socket.timeout, TimeoutError, urllib3.exceptions.TimeoutError)
        )
        for item in iter_network_error_causes(exc)
    )


def classify_network_error(exc: Exception) -> RequestErrorCategory:
    """Classify third-party network exceptions into stable retry categories."""

    causes = list(iter_network_error_causes(exc))
    if any(
        isinstance(
            item, (socket.timeout, TimeoutError, urllib3.exceptions.TimeoutError)
        )
        for item in causes
    ):
        return RequestErrorCategory.TIMEOUT
    if any(
        isinstance(item, (ssl.SSLError, urllib3.exceptions.SSLError)) for item in causes
    ):
        return RequestErrorCategory.TLS_ERROR
    if any(isinstance(item, socket.gaierror) for item in causes):
        return RequestErrorCategory.DNS_ERROR

    text = " ".join(str(item).lower() for item in causes if str(item).strip())
    if "connection reset" in text:
        return RequestErrorCategory.CONNECTION_RESET
    if any(
        token in text
        for token in (
            "remote end closed",
            "connection aborted",
            "connection broken",
            "eof",
        )
    ):
        return RequestErrorCategory.CONNECTION_CLOSED
    if "temporary failure" in text and "name resolution" in text:
        return RequestErrorCategory.DNS_ERROR
    return RequestErrorCategory.NETWORK_ERROR


def is_retryable_network_error(exc: Exception) -> bool:
    """Allow only transient connection failures; TLS/security errors never retry."""

    category = classify_network_error(exc)
    if category in {
        RequestErrorCategory.TIMEOUT,
        RequestErrorCategory.CONNECTION_RESET,
        RequestErrorCategory.CONNECTION_CLOSED,
    }:
        return True
    if category != RequestErrorCategory.DNS_ERROR:
        return False
    for cause in iter_network_error_causes(exc):
        if isinstance(cause, socket.gaierror) and cause.errno == socket.EAI_AGAIN:
            return True
    text = " ".join(str(item).lower() for item in iter_network_error_causes(exc))
    return "temporary failure" in text or "try again" in text


def build_network_error_detail(exc: Exception) -> str:
    for nested in iter_network_error_causes(exc):
        if nested is exc:
            continue
        detail = str(nested).strip()
        if detail:
            return detail
    return str(exc)
