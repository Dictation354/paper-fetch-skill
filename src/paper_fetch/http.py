"""HTTP transport and content helpers."""

from __future__ import annotations

import gzip
import io
import logging
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Mapping

import urllib3

DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_FULLTEXT_TIMEOUT_SECONDS = 90
DEFAULT_CACHE_TTL_SECONDS = 30
DEFAULT_CACHE_CAPACITY = 128
DEFAULT_MAX_CACHEABLE_BODY_BYTES = 1024 * 1024
DEFAULT_MAX_TOTAL_CACHE_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_RESPONSE_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_COMPRESSED_BODY_MULTIPLIER = 8
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
CACHE_KEY_HEADER_NAMES = {
    "accept",
    "accept-language",
    *SENSITIVE_CACHE_HEADER_NAMES,
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
logger = logging.getLogger("paper_fetch.http")


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


@dataclass(frozen=True)
class _PreparedRequest:
    method: str
    full_url: str
    headers: Mapping[str, str]


class HttpTransport:
    """Minimal HTTP transport with short-lived in-memory caching."""

    def __init__(
        self,
        *,
        cache_ttl: int = DEFAULT_CACHE_TTL_SECONDS,
        cache_capacity: int = DEFAULT_CACHE_CAPACITY,
        max_cacheable_body_bytes: int = DEFAULT_MAX_CACHEABLE_BODY_BYTES,
        max_total_cache_bytes: int = DEFAULT_MAX_TOTAL_CACHE_BYTES,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    ) -> None:
        self.cache_ttl = max(0, int(cache_ttl))
        self.cache_capacity = max(0, int(cache_capacity))
        self.max_cacheable_body_bytes = max(0, int(max_cacheable_body_bytes))
        self.max_total_cache_bytes = max(0, int(max_total_cache_bytes))
        self.max_response_bytes = max(0, int(max_response_bytes))
        self._cache: OrderedDict[tuple[str, str, tuple[tuple[str, str], ...]], tuple[float, dict[str, Any]]] = OrderedDict()
        self._cache_body_bytes = 0
        self._cache_lock = threading.RLock()
        self._pool = urllib3.PoolManager()

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
                if str(key).lower() in CACHE_KEY_HEADER_NAMES
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
                self._discard_cache_entry(cache_key)
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
        cloned_response = self._clone_response(response)
        body_size = self._cache_body_size(cloned_response)
        if self.max_total_cache_bytes > 0 and body_size > self.max_total_cache_bytes:
            return
        with self._cache_lock:
            self._discard_cache_entry(cache_key)
            self._cache[cache_key] = (time.monotonic() + self.cache_ttl, cloned_response)
            self._cache_body_bytes += body_size
            self._cache.move_to_end(cache_key)
            while len(self._cache) > self.cache_capacity or (
                self.max_total_cache_bytes > 0 and self._cache_body_bytes > self.max_total_cache_bytes
            ):
                self._discard_cache_entry(next(iter(self._cache)))

    def _is_cacheable_response(self, response: Mapping[str, Any]) -> bool:
        if self.max_cacheable_body_bytes <= 0:
            return False
        body = response.get("body", b"")
        if not isinstance(body, (bytes, bytearray)) or len(body) > self.max_cacheable_body_bytes:
            return False
        content_type = str((response.get("headers") or {}).get("content-type") or "")
        return is_textual_content_type(content_type)

    def _cache_body_size(self, response: Mapping[str, Any]) -> int:
        body = response.get("body", b"")
        return len(body) if isinstance(body, (bytes, bytearray)) else 0

    def _discard_cache_entry(
        self,
        cache_key: tuple[str, str, tuple[tuple[str, str], ...]],
    ) -> None:
        cached_entry = self._cache.pop(cache_key, None)
        if cached_entry is None:
            return
        _expires_at, response = cached_entry
        self._cache_body_bytes = max(0, self._cache_body_bytes - self._cache_body_size(response))

    def _perform_request(self, request: _PreparedRequest, *, timeout: int) -> Any:
        return self._pool.request(
            request.method,
            request.full_url,
            headers=dict(request.headers),
            timeout=urllib3.Timeout(connect=timeout, read=timeout),
            preload_content=False,
            retries=False,
            redirect=True,
        )

    def _handle_http_failure(
        self,
        *,
        method: str,
        request_url: str,
        error_url: str,
        status_code: int,
        body: bytes,
        headers_map: Mapping[str, str],
        request_started_at: float,
        attempt: int,
        retry_on_rate_limit: bool,
        attempts_remaining: int,
        max_rate_limit_wait_seconds: int,
        retry_on_transient: bool,
        transient_attempts_remaining: int,
        transient_attempts_made: int,
        transient_backoff_base_seconds: float,
    ) -> tuple[bool, int, int, int]:
        retry_after_seconds = parse_retry_after_seconds(headers_map.get("retry-after"))
        rate_limit_wait_seconds = retry_after_seconds
        if rate_limit_wait_seconds is None:
            fallback_wait_seconds = max(0.0, transient_backoff_base_seconds)
            if fallback_wait_seconds <= max_rate_limit_wait_seconds:
                rate_limit_wait_seconds = fallback_wait_seconds
        if (
            status_code == 429
            and retry_on_rate_limit
            and attempts_remaining > 0
            and rate_limit_wait_seconds is not None
            and rate_limit_wait_seconds <= max_rate_limit_wait_seconds
        ):
            logger.debug(
                (
                    "http_request_retry method=%s url=%s status=%s elapsed_ms=%s "
                    "retry_after_seconds=%s attempt=%s reason=rate_limit"
                ),
                method.upper(),
                redact_url_for_cache(error_url),
                status_code,
                round((time.monotonic() - request_started_at) * 1000, 3),
                retry_after_seconds,
                attempt,
            )
            attempts_remaining -= 1
            time.sleep(max(0.0, rate_limit_wait_seconds))
            return True, attempts_remaining, transient_attempts_remaining, transient_attempts_made
        if retry_on_transient and transient_attempts_remaining > 0 and is_transient_http_status(status_code):
            logger.debug(
                (
                    "http_request_retry method=%s url=%s status=%s elapsed_ms=%s "
                    "retry_after_seconds=%s attempt=%s reason=transient_http"
                ),
                method.upper(),
                redact_url_for_cache(error_url),
                status_code,
                round((time.monotonic() - request_started_at) * 1000, 3),
                retry_after_seconds,
                attempt,
            )
            transient_attempts_remaining -= 1
            time.sleep(transient_backoff_base_seconds * (2**transient_attempts_made))
            transient_attempts_made += 1
            return True, attempts_remaining, transient_attempts_remaining, transient_attempts_made
        logger.debug(
            "http_request_failure method=%s url=%s status=%s elapsed_ms=%s retry_after_seconds=%s attempt=%s",
            method.upper(),
            redact_url_for_cache(error_url),
            status_code,
            round((time.monotonic() - request_started_at) * 1000, 3),
            retry_after_seconds,
            attempt,
        )
        raise RequestFailure(
            status_code,
            build_http_error_message(status_code, request_url, retry_after_seconds=retry_after_seconds),
            body=body,
            headers=headers_map,
            url=redact_url_for_cache(error_url),
            retry_after_seconds=retry_after_seconds,
        )

    def _release_response(self, response: Any) -> None:
        release_conn = getattr(response, "release_conn", None)
        if callable(release_conn):
            release_conn()
            return
        close = getattr(response, "close", None)
        if callable(close):
            close()

    def _close_response(self, response: Any) -> None:
        close = getattr(response, "close", None)
        if callable(close):
            close()

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
        if not any(str(key).lower() == "accept-encoding" for key in request_headers):
            request_headers["Accept-Encoding"] = "gzip"
        cache_key = self._build_cache_key(method, url, request_headers)
        cached_response = self._load_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        attempts_remaining = max(0, int(rate_limit_retries))
        transient_attempts_remaining = max(0, int(transient_retries))
        transient_attempts_made = 0
        transient_backoff_base_seconds = max(0.0, float(transient_backoff_base_seconds))
        attempt = 0
        while True:
            attempt += 1
            request_started_at = time.monotonic()
            redacted_url = redact_url_for_cache(url)
            logger.debug(
                "http_request_start method=%s url=%s status=%s elapsed_ms=%s attempt=%s",
                method.upper(),
                redacted_url,
                "attempt",
                0.0,
                attempt,
            )
            request = _PreparedRequest(method=method.upper(), full_url=url, headers=dict(request_headers))
            response = None
            response_reusable = False
            try:
                response = self._perform_request(request, timeout=timeout)
                response_url = response.geturl() or url
                headers_map = {str(key).lower(): str(value) for key, value in response.headers.items()}
                payload = self._read_response_body(
                    response,
                    status_code=response.status,
                    url=response_url,
                    content_encoding=headers_map.get("content-encoding"),
                )
                response_reusable = True
                if int(response.status) >= 400:
                    (
                        should_retry,
                        attempts_remaining,
                        transient_attempts_remaining,
                        transient_attempts_made,
                    ) = self._handle_http_failure(
                        method=method,
                        request_url=url,
                        error_url=response_url,
                        status_code=int(response.status),
                        body=payload,
                        headers_map=headers_map,
                        request_started_at=request_started_at,
                        attempt=attempt,
                        retry_on_rate_limit=retry_on_rate_limit,
                        attempts_remaining=attempts_remaining,
                        max_rate_limit_wait_seconds=max_rate_limit_wait_seconds,
                        retry_on_transient=retry_on_transient,
                        transient_attempts_remaining=transient_attempts_remaining,
                        transient_attempts_made=transient_attempts_made,
                        transient_backoff_base_seconds=transient_backoff_base_seconds,
                    )
                    if should_retry:
                        continue
                response_payload = {
                    "status_code": int(response.status),
                    "headers": headers_map,
                    "body": payload,
                    "url": redact_url_for_cache(response_url),
                }
                logger.debug(
                    "http_request_success method=%s url=%s status=%s elapsed_ms=%s attempt=%s",
                    method.upper(),
                    response_payload["url"],
                    response.status,
                    round((time.monotonic() - request_started_at) * 1000, 3),
                    attempt,
                )
                self._store_cached_response(cache_key, response_payload)
                return response_payload
            except urllib.error.HTTPError as exc:
                try:
                    error_url = exc.geturl() or url
                    headers_map = {key.lower(): value for key, value in exc.headers.items()}
                    body = self._read_response_body(
                        exc,
                        status_code=exc.code,
                        url=error_url,
                        content_encoding=headers_map.get("content-encoding"),
                    )
                    (
                        should_retry,
                        attempts_remaining,
                        transient_attempts_remaining,
                        transient_attempts_made,
                    ) = self._handle_http_failure(
                        method=method,
                        request_url=url,
                        error_url=error_url,
                        status_code=int(exc.code),
                        body=body,
                        headers_map=headers_map,
                        request_started_at=request_started_at,
                        attempt=attempt,
                        retry_on_rate_limit=retry_on_rate_limit,
                        attempts_remaining=attempts_remaining,
                        max_rate_limit_wait_seconds=max_rate_limit_wait_seconds,
                        retry_on_transient=retry_on_transient,
                        transient_attempts_remaining=transient_attempts_remaining,
                        transient_attempts_made=transient_attempts_made,
                        transient_backoff_base_seconds=transient_backoff_base_seconds,
                    )
                    if should_retry:
                        continue
                finally:
                    exc.close()
            except (urllib3.exceptions.HTTPError, urllib.error.URLError) as exc:
                if retry_on_transient and transient_attempts_remaining > 0 and is_timeout_network_error(exc):
                    logger.debug(
                        "http_request_retry method=%s url=%s status=%s elapsed_ms=%s retry_after_seconds=%s attempt=%s reason=pool_timeout",
                        method.upper(),
                        redacted_url,
                        None,
                        round((time.monotonic() - request_started_at) * 1000, 3),
                        None,
                        attempt,
                    )
                    transient_attempts_remaining -= 1
                    time.sleep(transient_backoff_base_seconds * (2**transient_attempts_made))
                    transient_attempts_made += 1
                    continue
                logger.debug(
                    "http_request_failure method=%s url=%s status=%s elapsed_ms=%s retry_after_seconds=%s attempt=%s",
                    method.upper(),
                    redacted_url,
                    None,
                    round((time.monotonic() - request_started_at) * 1000, 3),
                    None,
                    attempt,
                )
                raise RequestFailure(
                    None,
                    f"Network error for {redact_url_for_cache(url)}: {build_network_error_detail(exc)}",
                    url=redact_url_for_cache(url),
                ) from exc
            except (socket.timeout, TimeoutError) as exc:
                if retry_on_transient and transient_attempts_remaining > 0:
                    logger.debug(
                        "http_request_retry method=%s url=%s status=%s elapsed_ms=%s retry_after_seconds=%s attempt=%s reason=timeout",
                        method.upper(),
                        redacted_url,
                        None,
                        round((time.monotonic() - request_started_at) * 1000, 3),
                        None,
                        attempt,
                    )
                    transient_attempts_remaining -= 1
                    time.sleep(transient_backoff_base_seconds * (2**transient_attempts_made))
                    transient_attempts_made += 1
                    continue
                logger.debug(
                    "http_request_failure method=%s url=%s status=%s elapsed_ms=%s retry_after_seconds=%s attempt=%s",
                    method.upper(),
                    redacted_url,
                    None,
                    round((time.monotonic() - request_started_at) * 1000, 3),
                    None,
                    attempt,
                )
                raise RequestFailure(
                    None,
                    f"Network error for {redact_url_for_cache(url)}: {exc}",
                    url=redact_url_for_cache(url),
                ) from exc
            finally:
                if response is not None:
                    if response_reusable:
                        self._release_response(response)
                    else:
                        self._close_response(response)

    def _read_response_body(
        self,
        response: Any,
        *,
        status_code: int | None,
        url: str,
        content_encoding: str | None = None,
    ) -> bytes:
        normalized_content_encoding = normalize_content_encoding(content_encoding)
        if normalized_content_encoding == "gzip":
            max_compressed_body_bytes = max(
                self.max_response_bytes,
                self.max_response_bytes * DEFAULT_MAX_COMPRESSED_BODY_MULTIPLIER,
            )
            payload = self._read_raw_bytes(response, max_compressed_body_bytes + 1)
        else:
            payload = self._read_raw_bytes(response, self.max_response_bytes + 1)
        if not isinstance(payload, (bytes, bytearray)):
            payload = bytes(payload or b"")
        body = bytes(payload)
        if normalized_content_encoding == "gzip":
            if len(body) > max_compressed_body_bytes:
                raise RequestFailure(
                    status_code,
                    (
                        f"Compressed response body exceeded {max_compressed_body_bytes} bytes "
                        f"for {redact_url_for_cache(url)}"
                    ),
                    body=body[:max_compressed_body_bytes],
                    url=redact_url_for_cache(url),
                )
            return decompress_gzip_body(
                body,
                status_code=status_code,
                url=url,
                max_response_bytes=self.max_response_bytes,
            )
        if len(body) > self.max_response_bytes:
            raise RequestFailure(
                status_code,
                f"Response body exceeded {self.max_response_bytes} bytes for {redact_url_for_cache(url)}",
                body=body[: self.max_response_bytes],
                url=redact_url_for_cache(url),
            )
        return body

    def _read_raw_bytes(self, response: Any, max_bytes: int) -> bytes:
        try:
            return response.read(max_bytes, decode_content=False, cache_content=False)
        except TypeError:
            return response.read(max_bytes)


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


def is_timeout_network_error(exc: Exception) -> bool:
    if isinstance(exc, urllib3.exceptions.TimeoutError):
        return True
    reason = getattr(exc, "reason", None)
    return isinstance(reason, (socket.timeout, TimeoutError, urllib3.exceptions.TimeoutError))


def build_network_error_detail(exc: Exception) -> str:
    reason = getattr(exc, "reason", None)
    if reason:
        return str(reason)
    return str(exc)


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


def normalize_content_encoding(value: str | None) -> str:
    if not value:
        return ""
    return ",".join(
        token.strip().lower()
        for token in str(value).split(",")
        if token.strip()
    )


def decompress_gzip_body(
    body: bytes,
    *,
    status_code: int | None,
    url: str,
    max_response_bytes: int,
) -> bytes:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as gzip_file:
            decompressed = gzip_file.read(max_response_bytes + 1)
    except OSError as exc:
        raise RequestFailure(
            status_code,
            f"Unable to decompress gzip response for {redact_url_for_cache(url)}: {exc}",
            body=body[:max_response_bytes],
            url=redact_url_for_cache(url),
        ) from exc
    if len(decompressed) > max_response_bytes:
        raise RequestFailure(
            status_code,
            f"Response body exceeded {max_response_bytes} bytes for {redact_url_for_cache(url)}",
            body=decompressed[:max_response_bytes],
            url=redact_url_for_cache(url),
        )
    return decompressed
