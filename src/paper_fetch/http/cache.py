"""HTTP memory-cache keys, URL redaction, and bounded response cache."""

from __future__ import annotations

import functools
import hashlib
import threading
import time
import urllib.parse
from collections.abc import Mapping
from typing import Any

from cachetools import TTLCache

from ..redaction import redact_text_for_diagnostics as _redact_text_for_diagnostics
from .content_types import is_textual_content_type

DEFAULT_CACHE_TTL_SECONDS = 30
DEFAULT_CACHE_CAPACITY = 128
DEFAULT_MAX_CACHEABLE_BODY_BYTES = 1024 * 1024
DEFAULT_MAX_TOTAL_CACHE_BYTES = 16 * 1024 * 1024
SENSITIVE_CACHE_HEADER_NAMES = {
    "authorization",
    "cookie",
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
    "awsaccesskeyid",
    "token",
    "auth",
    "authorization",
    "mailto",
    "signature",
}
REDACTED_CACHE_VALUE = "***"
REDACTED_CACHE_HEADER_DIGEST_PREFIX = "sha256:"
SENSITIVE_RESPONSE_HEADER_NAMES = {
    "set-cookie",
    "set-cookie2",
    "www-authenticate",
    "proxy-authenticate",
}
_CacheKey = tuple[str, str, tuple[tuple[str, str], ...]]


@functools.cache
def _sensitive_cache_header_names() -> frozenset[str]:
    from ..provider_catalog import provider_sensitive_header_names

    return frozenset(SENSITIVE_CACHE_HEADER_NAMES) | provider_sensitive_header_names()


def is_sensitive_query_param_name(name: str) -> bool:
    normalized = name.lower()
    return (
        normalized in SENSITIVE_QUERY_PARAM_NAMES
        or normalized.startswith("x-amz-")
        or normalized.startswith("x-goog-")
    )


def _url_has_sensitive_query_params(url: str) -> bool:
    if not url:
        return False
    parsed = urllib.parse.urlsplit(url)
    return any(
        is_sensitive_query_param_name(key)
        for key, _value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    )


def _secret_cache_digest(name: str, value: str) -> str:
    raw = f"{name.lower()}\0{value}".encode()
    return hashlib.sha256(raw).hexdigest()


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
                REDACTED_CACHE_VALUE if is_sensitive_query_param_name(key) else value,
            )
            for key, value in query_items
        ],
        doseq=True,
    )
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, redacted_query, parsed.fragment)
    )


def redact_url_for_diagnostics(url: str) -> str:
    """Remove all query/fragment data from a URL before durable diagnostics."""

    if not url:
        return url
    parsed = urllib.parse.urlsplit(url)
    hostname = str(parsed.hostname or "")
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    try:
        port = parsed.port
    except ValueError:
        port = None
    netloc = f"{hostname}:{port}" if hostname and port is not None else hostname
    return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def diagnostic_url_payload(url: str) -> dict[str, str]:
    """Return a secret-free URL summary with a correlation digest."""

    if not url:
        return {}
    parsed = urllib.parse.urlsplit(url)
    redacted = redact_url_for_diagnostics(url)
    return {
        "url": redacted,
        "host": str(parsed.hostname or "").lower(),
        "path": parsed.path,
        "url_sha256": hashlib.sha256(url.encode("utf-8")).hexdigest(),
    }


def redact_text_for_diagnostics(value: str) -> str:
    """Remove URL queries and credential assignments from diagnostic text."""

    return _redact_text_for_diagnostics(
        value,
        additional_secret_names=_sensitive_cache_header_names(),
    )


def _cache_identity_url(url: str) -> str:
    """Return a secret-safe URL that still distinguishes credential scopes."""

    if not url:
        return url
    parsed = urllib.parse.urlsplit(url)
    if not parsed.query:
        return urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, "", "")
        )
    identity_query = urllib.parse.urlencode(
        [
            (
                key,
                (
                    f"{REDACTED_CACHE_HEADER_DIGEST_PREFIX}"
                    f"{_secret_cache_digest(key, value)}"
                )
                if is_sensitive_query_param_name(key)
                else value,
            )
            for key, value in urllib.parse.parse_qsl(
                parsed.query, keep_blank_values=True
            )
        ],
        doseq=True,
    )
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, identity_query, "")
    )


def _normalize_header_value_for_cache(key: str, value: str) -> str:
    normalized_key = key.lower()
    if normalized_key in _sensitive_cache_header_names():
        digest = _secret_cache_digest(normalized_key, value)[:16]
        return f"{REDACTED_CACHE_HEADER_DIGEST_PREFIX}{digest}"
    if normalized_key in UNSTABLE_CACHE_HEADER_NAMES:
        return "<volatile>"
    return value


def _safe_cached_response_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(key).lower(): str(value)
        for key, value in headers.items()
        if str(key).lower() not in SENSITIVE_RESPONSE_HEADER_NAMES
    }


def _cache_body_size(response: Mapping[str, Any]) -> int:
    body = response.get("body", b"")
    return len(body) if isinstance(body, bytes | bytearray) else 0


class ResponseMemoryCache:
    """Thread-safe short-lived GET cache owned by ``HttpTransport``."""

    def __init__(
        self,
        *,
        ttl: int = DEFAULT_CACHE_TTL_SECONDS,
        capacity: int = DEFAULT_CACHE_CAPACITY,
        max_cacheable_body_bytes: int = DEFAULT_MAX_CACHEABLE_BODY_BYTES,
        max_total_cache_bytes: int = DEFAULT_MAX_TOTAL_CACHE_BYTES,
    ) -> None:
        self.ttl = max(0, int(ttl))
        self.capacity = max(0, int(capacity))
        self.max_cacheable_body_bytes = max(0, int(max_cacheable_body_bytes))
        self.max_total_cache_bytes = max(0, int(max_total_cache_bytes))
        maxsize = (
            self.max_total_cache_bytes
            if self.max_total_cache_bytes > 0
            else float("inf")
        )
        self.entries: TTLCache[_CacheKey, dict[str, Any]] = TTLCache(
            maxsize=maxsize,
            ttl=max(1, self.ttl),
            timer=time.monotonic,
            getsizeof=_cache_body_size,
        )
        self.body_bytes = 0
        self._lock = threading.RLock()

    def build_key(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
    ) -> _CacheKey | None:
        if method.upper() != "GET" or self.ttl <= 0 or self.capacity <= 0:
            return None
        normalized_headers = tuple(
            sorted(
                (
                    str(key).lower(),
                    _normalize_header_value_for_cache(str(key), str(value)),
                )
                for key, value in headers.items()
                if str(key).lower() not in UNSTABLE_CACHE_HEADER_NAMES
            )
        )
        return (method.upper(), _cache_identity_url(url), normalized_headers)

    def load(self, cache_key: _CacheKey | None) -> dict[str, Any] | None:
        if cache_key is None:
            return None
        with self._lock:
            self.entries.expire()
            try:
                response = self.entries[cache_key]
            except KeyError:
                self._sync_body_bytes()
                return None
            self._sync_body_bytes()
            return self._clone_response(response)

    def store(
        self,
        cache_key: _CacheKey | None,
        response: Mapping[str, Any],
    ) -> bool:
        if cache_key is None or not self._is_cacheable_response(response):
            return False
        cloned_response = self._clone_response(response)
        body_size = _cache_body_size(cloned_response)
        if self.max_total_cache_bytes > 0 and body_size > self.max_total_cache_bytes:
            return False
        with self._lock:
            self.entries.expire()
            self.entries.pop(cache_key, None)
            try:
                self.entries[cache_key] = cloned_response
            except ValueError:
                self._sync_body_bytes()
                return False
            while len(self.entries) > self.capacity:
                self.entries.popitem()
            self._sync_body_bytes()
        return True

    def _clone_response(self, response: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "status_code": response.get("status_code"),
            "headers": _safe_cached_response_headers(response.get("headers") or {}),
            "body": response.get("body", b""),
            "url": response.get("url"),
        }

    def _is_cacheable_response(self, response: Mapping[str, Any]) -> bool:
        if self.max_cacheable_body_bytes <= 0:
            return False
        headers = {
            str(key).lower(): str(value)
            for key, value in dict(response.get("headers") or {}).items()
        }
        cache_control = {
            directive.strip().lower()
            for directive in headers.get("cache-control", "").split(",")
            if directive.strip()
        }
        if (
            "no-store" in cache_control
            or "private" in cache_control
            or "set-cookie" in headers
            or "set-cookie2" in headers
            or headers.get("vary", "").strip() == "*"
        ):
            return False
        if _url_has_sensitive_query_params(headers.get("location", "")):
            return False
        body = response.get("body", b"")
        if (
            not isinstance(body, bytes | bytearray)
            or len(body) > self.max_cacheable_body_bytes
        ):
            return False
        content_type = headers.get("content-type", "")
        return is_textual_content_type(content_type)

    def _sync_body_bytes(self) -> None:
        self.body_bytes = int(self.entries.currsize)


__all__ = [
    "CACHE_KEY_HEADER_NAMES",
    "DEFAULT_CACHE_CAPACITY",
    "DEFAULT_CACHE_TTL_SECONDS",
    "DEFAULT_MAX_CACHEABLE_BODY_BYTES",
    "DEFAULT_MAX_TOTAL_CACHE_BYTES",
    "REDACTED_CACHE_HEADER_DIGEST_PREFIX",
    "REDACTED_CACHE_VALUE",
    "SENSITIVE_CACHE_HEADER_NAMES",
    "SENSITIVE_QUERY_PARAM_NAMES",
    "SENSITIVE_RESPONSE_HEADER_NAMES",
    "UNSTABLE_CACHE_HEADER_NAMES",
    "ResponseMemoryCache",
    "_CacheKey",
    "diagnostic_url_payload",
    "is_sensitive_query_param_name",
    "redact_text_for_diagnostics",
    "redact_url_for_cache",
    "redact_url_for_diagnostics",
]
