"""HTTP transport and content helpers."""

from __future__ import annotations

import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Mapping

DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_FULLTEXT_TIMEOUT_SECONDS = 90
DEFAULT_CACHE_TTL_SECONDS = 30
DEFAULT_CACHE_CAPACITY = 128
DEFAULT_MAX_CACHEABLE_BODY_BYTES = 1024 * 1024
DEFAULT_MAX_RESPONSE_BYTES = 32 * 1024 * 1024
DEFAULT_TRANSIENT_RETRIES = 2
DEFAULT_TRANSIENT_BACKOFF_BASE_SECONDS = 0.5

TEXTUAL_CONTENT_TYPES = (
    "text/",
    "application/xml",
    "text/xml",
    "application/json",
    "application/jats+xml",
)
SENSITIVE_CACHE_HEADER_NAMES = {
    "authorization",
    "wiley-tdm-client-token",
    "x-els-apikey",
    "x-els-insttoken",
    "cr-clickthrough-client-token",
    "proxy-authorization",
}
UNSTABLE_CACHE_HEADER_NAMES = {
    "x-els-reqid",
}
SENSITIVE_QUERY_PARAM_NAMES = {
    "api_key",
    "apikey",
    "token",
    "auth",
    "authorization",
    "mailto",
}
REDACTED_CACHE_VALUE = "***"


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


class HttpTransport:
    """Minimal HTTP transport with short-lived in-memory caching."""

    def __init__(
        self,
        *,
        cache_ttl: int = DEFAULT_CACHE_TTL_SECONDS,
        cache_capacity: int = DEFAULT_CACHE_CAPACITY,
        max_cacheable_body_bytes: int = DEFAULT_MAX_CACHEABLE_BODY_BYTES,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    ) -> None:
        self.cache_ttl = max(0, int(cache_ttl))
        self.cache_capacity = max(0, int(cache_capacity))
        self.max_cacheable_body_bytes = max(0, int(max_cacheable_body_bytes))
        self.max_response_bytes = max(0, int(max_response_bytes))
        self._cache: OrderedDict[tuple[str, str, tuple[tuple[str, str], ...]], tuple[float, dict[str, Any]]] = OrderedDict()
        self._cache_lock = threading.RLock()

    def _build_cache_key(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
    ) -> tuple[str, str, tuple[tuple[str, str], ...]] | None:
        if method.upper() != "GET" or self.cache_ttl <= 0 or self.cache_capacity <= 0:
            return None
        normalized_headers = tuple(
            sorted(
                (str(key).lower(), self._normalize_header_value_for_cache(str(key), str(value)))
                for key, value in headers.items()
            )
        )
        return (method.upper(), redact_url_for_cache(url), normalized_headers)

    def _normalize_header_value_for_cache(self, key: str, value: str) -> str:
        normalized_key = key.lower()
        if normalized_key in SENSITIVE_CACHE_HEADER_NAMES:
            return REDACTED_CACHE_VALUE
        if normalized_key in UNSTABLE_CACHE_HEADER_NAMES:
            return "<volatile>"
        return value

    def _clone_response(self, response: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "status_code": response.get("status_code"),
            "headers": dict(response.get("headers") or {}),
            "body": response.get("body", b""),
            "url": response.get("url"),
        }

    def _load_cached_response(
        self,
        cache_key: tuple[str, str, tuple[tuple[str, str], ...]] | None,
    ) -> dict[str, Any] | None:
        if cache_key is None:
            return None
        with self._cache_lock:
            cached_entry = self._cache.get(cache_key)
            if cached_entry is None:
                return None
            expires_at, response = cached_entry
            if expires_at <= time.monotonic():
                self._cache.pop(cache_key, None)
                return None
            self._cache.move_to_end(cache_key)
            return self._clone_response(response)

    def _store_cached_response(
        self,
        cache_key: tuple[str, str, tuple[tuple[str, str], ...]] | None,
        response: Mapping[str, Any],
    ) -> None:
        if cache_key is None or not self._is_cacheable_response(response):
            return
        with self._cache_lock:
            self._cache[cache_key] = (time.monotonic() + self.cache_ttl, self._clone_response(response))
            self._cache.move_to_end(cache_key)
            while len(self._cache) > self.cache_capacity:
                self._cache.popitem(last=False)

    def _is_cacheable_response(self, response: Mapping[str, Any]) -> bool:
        if self.max_cacheable_body_bytes <= 0:
            return False
        body = response.get("body", b"")
        if not isinstance(body, (bytes, bytearray)) or len(body) > self.max_cacheable_body_bytes:
            return False
        content_type = str((response.get("headers") or {}).get("content-type") or "")
        return is_textual_content_type(content_type)

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, str] | None = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        retry_on_rate_limit: bool = False,
        rate_limit_retries: int = 1,
        max_rate_limit_wait_seconds: int = 5,
        retry_on_transient: bool = False,
        transient_retries: int = DEFAULT_TRANSIENT_RETRIES,
        transient_backoff_base_seconds: float = DEFAULT_TRANSIENT_BACKOFF_BASE_SECONDS,
    ) -> dict[str, Any]:
        if query:
            encoded_query = urllib.parse.urlencode(query, doseq=True)
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{encoded_query}"

        request_headers = {key: value for key, value in (headers or {}).items() if value is not None}
        cache_key = self._build_cache_key(method, url, request_headers)
        cached_response = self._load_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        attempts_remaining = max(0, int(rate_limit_retries))
        transient_attempts_remaining = max(0, int(transient_retries))
        transient_attempts_made = 0
        transient_backoff_base_seconds = max(0.0, float(transient_backoff_base_seconds))
        while True:
            request = urllib.request.Request(url=url, headers=request_headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    response_url = response.geturl() or url
                    payload = self._read_response_body(
                        response,
                        status_code=response.status,
                        url=response_url,
                    )
                    response_payload = {
                        "status_code": response.status,
                        "headers": {key.lower(): value for key, value in response.headers.items()},
                        "body": payload,
                        "url": redact_url_for_cache(response_url),
                    }
                    self._store_cached_response(cache_key, response_payload)
                    return response_payload
            except urllib.error.HTTPError as exc:
                try:
                    error_url = exc.geturl() or url
                    body = self._read_response_body(
                        exc,
                        status_code=exc.code,
                        url=error_url,
                    )
                    headers_map = {key.lower(): value for key, value in exc.headers.items()}
                    retry_after_seconds = parse_retry_after_seconds(headers_map.get("retry-after"))
                    if (
                        exc.code == 429
                        and retry_on_rate_limit
                        and attempts_remaining > 0
                        and retry_after_seconds is not None
                        and retry_after_seconds <= max_rate_limit_wait_seconds
                    ):
                        attempts_remaining -= 1
                        time.sleep(max(0, retry_after_seconds))
                        continue
                    if retry_on_transient and transient_attempts_remaining > 0 and is_transient_http_status(exc.code):
                        transient_attempts_remaining -= 1
                        time.sleep(transient_backoff_base_seconds * (2**transient_attempts_made))
                        transient_attempts_made += 1
                        continue
                    raise RequestFailure(
                        exc.code,
                        build_http_error_message(exc.code, url, retry_after_seconds=retry_after_seconds),
                        body=body,
                        headers=headers_map,
                        url=redact_url_for_cache(error_url),
                        retry_after_seconds=retry_after_seconds,
                    ) from exc
                finally:
                    exc.close()
            except urllib.error.URLError as exc:
                if retry_on_transient and transient_attempts_remaining > 0 and is_transient_url_error(exc):
                    transient_attempts_remaining -= 1
                    time.sleep(transient_backoff_base_seconds * (2**transient_attempts_made))
                    transient_attempts_made += 1
                    continue
                raise RequestFailure(
                    None,
                    f"Network error for {redact_url_for_cache(url)}: {exc.reason}",
                    url=redact_url_for_cache(url),
                ) from exc
            except (socket.timeout, TimeoutError) as exc:
                if retry_on_transient and transient_attempts_remaining > 0:
                    transient_attempts_remaining -= 1
                    time.sleep(transient_backoff_base_seconds * (2**transient_attempts_made))
                    transient_attempts_made += 1
                    continue
                raise RequestFailure(
                    None,
                    f"Network error for {redact_url_for_cache(url)}: {exc}",
                    url=redact_url_for_cache(url),
                ) from exc

    def _read_response_body(
        self,
        response: Any,
        *,
        status_code: int | None,
        url: str,
    ) -> bytes:
        payload = response.read(self.max_response_bytes + 1)
        if not isinstance(payload, (bytes, bytearray)):
            payload = bytes(payload or b"")
        body = bytes(payload)
        if len(body) > self.max_response_bytes:
            raise RequestFailure(
                status_code,
                f"Response body exceeded {self.max_response_bytes} bytes for {redact_url_for_cache(url)}",
                body=body[: self.max_response_bytes],
                url=redact_url_for_cache(url),
            )
        return body


def redact_url_for_cache(url: str) -> str:
    if not url:
        return url
    parsed = urllib.parse.urlsplit(url)
    if not parsed.query:
        return url
    query_items = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted_query = urllib.parse.urlencode(
        [
            (
                key,
                REDACTED_CACHE_VALUE if key.lower() in SENSITIVE_QUERY_PARAM_NAMES else value,
            )
            for key, value in query_items
        ],
        doseq=True,
    )
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, redacted_query, parsed.fragment))


def parse_retry_after_seconds(value: str | None) -> int | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.isdigit():
        return max(0, int(normalized))
    try:
        parsed = parsedate_to_datetime(normalized)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    delta = (parsed - datetime.now(timezone.utc)).total_seconds()
    return max(0, int(delta))


def build_http_error_message(status_code: int | None, url: str, *, retry_after_seconds: int | None = None) -> str:
    message = f"HTTP {status_code} for {redact_url_for_cache(url)}"
    if retry_after_seconds is not None:
        message += f" (Retry-After: {retry_after_seconds}s)"
    return message


def is_transient_http_status(status_code: int | None) -> bool:
    return status_code is not None and 500 <= status_code < 600


def is_transient_url_error(exc: urllib.error.URLError) -> bool:
    reason = getattr(exc, "reason", None)
    return isinstance(reason, (socket.timeout, TimeoutError))


def is_xml_content_type(content_type: str | None) -> bool:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    return normalized in {"application/xml", "text/xml", "application/jats+xml"} or normalized.endswith("+xml")


def is_textual_content_type(content_type: str | None) -> bool:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    if not normalized:
        return False
    return any(normalized.startswith(prefix) or normalized == prefix for prefix in TEXTUAL_CONTENT_TYPES) or normalized.endswith("+xml")


def build_text_preview(body: bytes, content_type: str | None) -> str | None:
    normalized = (content_type or "").split(";", 1)[0].lower()
    if normalized and not is_textual_content_type(normalized):
        return None
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    return text[:500] or None
