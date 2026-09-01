"""HTTP memory-cache keys and bounds."""

from __future__ import annotations

import functools
import hashlib
import threading
import urllib.parse
from typing import TYPE_CHECKING, Any
from collections.abc import Mapping

if TYPE_CHECKING:
    from cachetools import TTLCache

from ..redaction import redact_text_for_diagnostics as _redact_text_for_diagnostics

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


class CacheMixin:
    """Private cache methods mixed into ``HttpTransport``."""

    # Attributes provided by the host class (HttpTransport.__init__)
    cache_ttl: int
    cache_capacity: int
    max_cacheable_body_bytes: int
    max_total_cache_bytes: int
    _cache: TTLCache[_CacheKey, dict[str, Any]]
    _cache_body_bytes: int
    _cache_lock: threading.RLock

    def _build_cache_key(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
    ) -> _CacheKey | None:
        if method.upper() != "GET" or self.cache_ttl <= 0 or self.cache_capacity <= 0:
            return None
        # Key all caller-visible request headers.  This is deliberately stricter
        # than trying to predict a response's Vary value before the response is
        # available: every standards-compliant Vary representation is therefore
        # isolated, while secret values remain one-way digests.
        normalized_headers = tuple(
            sorted(
                (
                    str(key).lower(),
                    self._normalize_header_value_for_cache(str(key), str(value)),
                )
                for key, value in headers.items()
                if str(key).lower() not in UNSTABLE_CACHE_HEADER_NAMES
            )
        )
        return (method.upper(), _cache_identity_url(url), normalized_headers)

    def _cache_key_has_credentials(self, cache_key: _CacheKey | None) -> bool:
        if cache_key is None:
            return False
        _method, identity_url, headers = cache_key
        if REDACTED_CACHE_HEADER_DIGEST_PREFIX in identity_url:
            return True
        sensitive_names = _sensitive_cache_header_names()
        return any(name in sensitive_names for name, _value in headers)

    def _normalize_header_value_for_cache(self, key: str, value: str) -> str:
        normalized_key = key.lower()
        if normalized_key in _sensitive_cache_header_names():
            digest = _secret_cache_digest(normalized_key, value)[:16]
            return f"{REDACTED_CACHE_HEADER_DIGEST_PREFIX}{digest}"
        if normalized_key in UNSTABLE_CACHE_HEADER_NAMES:
            return "<volatile>"
        return value

    def _clone_response(self, response: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "status_code": response.get("status_code"),
            "headers": self._safe_cached_response_headers(
                response.get("headers") or {}
            ),
            "body": response.get("body", b""),
            "url": response.get("url"),
        }

    def _safe_cached_response_headers(
        self, headers: Mapping[str, Any]
    ) -> dict[str, str]:
        return {
            str(key).lower(): str(value)
            for key, value in headers.items()
            if str(key).lower() not in SENSITIVE_RESPONSE_HEADER_NAMES
        }

    def _load_cached_response(
        self,
        cache_key: _CacheKey | None,
    ) -> dict[str, Any] | None:
        if cache_key is None:
            return None
        with self._cache_lock:
            self._cache.expire()
            try:
                response = self._cache[cache_key]
            except KeyError:
                self._sync_cache_body_bytes()
                return None
            self._sync_cache_body_bytes()
            return self._clone_response(response)

    def _store_cached_response(
        self,
        cache_key: _CacheKey | None,
        response: Mapping[str, Any],
    ) -> bool:
        if cache_key is None or not self._is_cacheable_response(response):
            return False
        cloned_response = self._clone_response(response)
        body_size = self._cache_body_size(cloned_response)
        if self.max_total_cache_bytes > 0 and body_size > self.max_total_cache_bytes:
            return False
        with self._cache_lock:
            self._cache.expire()
            self._cache.pop(cache_key, None)
            try:
                self._cache[cache_key] = cloned_response
            except ValueError:
                self._sync_cache_body_bytes()
                return False
            self._enforce_cache_capacity()
            self._sync_cache_body_bytes()
        return True

    def _is_cacheable_response(self, response: Mapping[str, Any]) -> bool:
        from .body import is_textual_content_type

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
            not isinstance(body, (bytes, bytearray))
            or len(body) > self.max_cacheable_body_bytes
        ):
            return False
        content_type = headers.get("content-type", "")
        return is_textual_content_type(content_type)

    def _cache_body_size(self, response: Mapping[str, Any]) -> int:
        body = response.get("body", b"")
        return len(body) if isinstance(body, (bytes, bytearray)) else 0

    def _enforce_cache_capacity(self) -> None:
        while len(self._cache) > self.cache_capacity:
            self._cache.popitem()

    def _sync_cache_body_bytes(self) -> None:
        self._cache_body_bytes = int(self._cache.currsize)
