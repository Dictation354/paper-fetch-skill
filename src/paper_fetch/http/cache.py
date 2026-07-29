"""HTTP cache key, memory cache, and disk cache helpers."""

from __future__ import annotations

import base64
import functools
import hashlib
import json
import os
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from collections.abc import Mapping

if TYPE_CHECKING:
    from cachetools import TTLCache

from ..provider_catalog import provider_sensitive_header_names
import contextlib

DEFAULT_CACHE_TTL_SECONDS = 30
DEFAULT_METADATA_CACHE_TTL_SECONDS = 86400
DEFAULT_CACHE_CAPACITY = 128
DEFAULT_MAX_CACHEABLE_BODY_BYTES = 1024 * 1024
DEFAULT_MAX_TOTAL_CACHE_BYTES = 16 * 1024 * 1024
DEFAULT_DISK_CACHE_MAX_ENTRIES = 4096
DEFAULT_DISK_CACHE_MAX_BYTES = 512 * 1024 * 1024
DEFAULT_DISK_CACHE_MAX_AGE_DAYS = 30
DEFAULT_DISK_CACHE_MAX_AGE_SECONDS = DEFAULT_DISK_CACHE_MAX_AGE_DAYS * 24 * 60 * 60
DISK_CACHE_VERSION = 2
DISK_CACHE_ROOT_NAME = "http-text-get"
DISK_CACHE_RECONCILE_WRITE_INTERVAL = 256
DISK_CACHE_RECONCILE_SECONDS = 300
CACHE_STAT_KEYS = (
    "memory_hit",
    "disk_fresh_hit",
    "disk_stale_revalidate",
    "disk_304_refresh",
    "miss",
    "store",
    "bypass",
)
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
    return frozenset(SENSITIVE_CACHE_HEADER_NAMES) | provider_sensitive_header_names()


@functools.cache
def _cache_key_header_names() -> frozenset[str]:
    return frozenset(CACHE_KEY_HEADER_NAMES) | _sensitive_cache_header_names()


@dataclass(frozen=True)
class _DiskCacheEntry:
    path: Path
    size: int
    stored_at: float


def _is_sensitive_query_param_name(name: str) -> bool:
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
        _is_sensitive_query_param_name(key)
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
                REDACTED_CACHE_VALUE if _is_sensitive_query_param_name(key) else value,
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
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


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


_DIAGNOSTIC_URL_IN_TEXT_RE = re.compile(
    r"(?P<base>(?:https?://|/)[^\s\"'<>?]+)\?[^\s\"'<>]*",
    re.IGNORECASE,
)
_DIAGNOSTIC_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?P<name>\b(?:x-amz-signature|signature|token|api[_-]?key|access[_-]?key)"
    r"\s*[=:]\s*)[^\s&;\"'<>]+",
    re.IGNORECASE,
)


def redact_text_for_diagnostics(value: str) -> str:
    """Remove URL queries and credential assignments from diagnostic text."""

    text = str(value or "")
    text = _DIAGNOSTIC_URL_IN_TEXT_RE.sub(
        lambda match: f"{match.group('base')}?[redacted]",
        text,
    )
    return _DIAGNOSTIC_SECRET_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group('name')}[redacted]",
        text,
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
                if _is_sensitive_query_param_name(key)
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
    metadata_cache_ttl: int
    cache_capacity: int
    max_cacheable_body_bytes: int
    max_total_cache_bytes: int
    disk_cache_dir: Path | None
    disk_cache_max_entries: int
    disk_cache_max_bytes: int
    disk_cache_max_age_seconds: int
    _cache: TTLCache[_CacheKey, dict[str, Any]]
    _cache_body_bytes: int
    _cache_lock: threading.RLock
    _cache_stats_lock: threading.Lock
    _cache_stats: dict[str, int]
    _disk_cache_lock: threading.RLock
    _disk_cache_entries: dict[Path, _DiskCacheEntry]
    _disk_cache_total_bytes: int
    _disk_cache_index_initialized: bool
    _disk_cache_writes_since_reconcile: int
    _disk_cache_last_reconcile: float
    _disk_cache_last_prune: float

    def _increment_cache_stat(self, name: str, amount: int = 1) -> None:
        if name not in self._cache_stats:
            return
        with self._cache_stats_lock:
            self._cache_stats[name] += max(0, int(amount))

    def cache_stats_snapshot(self) -> dict[str, int]:
        with self._cache_stats_lock:
            return dict(self._cache_stats)

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

    def _disk_cache_path(self, cache_key: _CacheKey) -> Path | None:
        if self.disk_cache_dir is None:
            return None
        encoded_key = json.dumps(
            cache_key, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        digest = hashlib.sha256(encoded_key).hexdigest()
        return self._disk_cache_root() / digest[:2] / f"{digest}.json"

    def _disk_cache_root(self) -> Path:
        assert self.disk_cache_dir is not None
        return self.disk_cache_dir / DISK_CACHE_ROOT_NAME

    def _unlink_disk_cache_path(self, path: Path) -> None:
        removed = self._disk_cache_entries.pop(path, None)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            return
        if removed is not None:
            self._disk_cache_total_bytes = max(
                0, self._disk_cache_total_bytes - removed.size
            )
        with contextlib.suppress(OSError):
            path.parent.rmdir()

    def _disk_cache_entry_from_path(self, path: Path) -> _DiskCacheEntry | None:
        try:
            stat_result = path.stat()
        except OSError:
            return None
        return _DiskCacheEntry(
            path=path,
            size=max(0, int(stat_result.st_size)),
            stored_at=float(stat_result.st_mtime),
        )

    def _iter_disk_cache_entries(self) -> list[_DiskCacheEntry]:
        if self.disk_cache_dir is None:
            return []
        root = self._disk_cache_root()
        if not root.exists():
            return []
        entries: list[_DiskCacheEntry] = []
        try:
            paths = sorted(root.rglob("*.json"))
        except OSError:
            return []
        for path in paths:
            entry = self._disk_cache_entry_from_path(path)
            if entry is not None:
                entries.append(entry)
        return entries

    def _reconcile_disk_cache_index(self) -> None:
        entries = self._iter_disk_cache_entries()
        self._disk_cache_entries = {entry.path: entry for entry in entries}
        self._disk_cache_total_bytes = sum(entry.size for entry in entries)
        self._disk_cache_index_initialized = True
        self._disk_cache_writes_since_reconcile = 0
        self._disk_cache_last_reconcile = time.monotonic()

    def _prune_disk_cache(self) -> None:
        if self.disk_cache_dir is None:
            return
        if (
            self.disk_cache_max_entries <= 0
            and self.disk_cache_max_bytes <= 0
            and self.disk_cache_max_age_seconds <= 0
        ):
            return
        with self._disk_cache_lock:
            monotonic_now = time.monotonic()
            reconcile_due = (
                not self._disk_cache_index_initialized
                or self._disk_cache_writes_since_reconcile
                >= DISK_CACHE_RECONCILE_WRITE_INTERVAL
                or monotonic_now - self._disk_cache_last_reconcile
                >= DISK_CACHE_RECONCILE_SECONDS
            )
            if reconcile_due:
                self._reconcile_disk_cache_index()
            over_entries = (
                self.disk_cache_max_entries > 0
                and len(self._disk_cache_entries) > self.disk_cache_max_entries
            )
            over_bytes = (
                self.disk_cache_max_bytes > 0
                and self._disk_cache_total_bytes > self.disk_cache_max_bytes
            )
            age_prune_due = (
                self.disk_cache_max_age_seconds > 0
                and monotonic_now - self._disk_cache_last_prune
                >= DISK_CACHE_RECONCILE_SECONDS
            )
            if not (over_entries or over_bytes or age_prune_due):
                return
            now = time.time()
            entries = list(self._disk_cache_entries.values())
            survivors: list[_DiskCacheEntry] = []
            for entry in entries:
                if (
                    self.disk_cache_max_age_seconds > 0
                    and now - entry.stored_at > self.disk_cache_max_age_seconds
                ):
                    self._unlink_disk_cache_path(entry.path)
                else:
                    survivors.append(entry)

            survivors.sort(key=lambda item: (item.stored_at, str(item.path)))
            if (
                self.disk_cache_max_entries > 0
                and len(survivors) > self.disk_cache_max_entries
            ):
                remove_count = len(survivors) - self.disk_cache_max_entries
                for entry in survivors[:remove_count]:
                    self._unlink_disk_cache_path(entry.path)
                survivors = survivors[remove_count:]

            if self.disk_cache_max_bytes > 0:
                total_bytes = self._disk_cache_total_bytes
                while survivors and total_bytes > self.disk_cache_max_bytes:
                    entry = survivors.pop(0)
                    total_bytes -= entry.size
                    self._unlink_disk_cache_path(entry.path)
            self._disk_cache_last_prune = monotonic_now

    def _load_disk_cached_entry(
        self, cache_key: _CacheKey | None
    ) -> dict[str, Any] | None:
        if cache_key is None:
            return None
        cache_path = self._disk_cache_path(cache_key)
        if cache_path is None:
            return None
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            if payload.get("version") != DISK_CACHE_VERSION:
                return None
            body = base64.b64decode(str(payload.get("body_b64") or ""), validate=True)
            response = {
                "status_code": int(payload.get("status_code") or 200),
                "headers": {
                    str(key).lower(): str(value)
                    for key, value in dict(payload.get("headers") or {}).items()
                },
                "body": body,
                "url": str(payload.get("url") or ""),
            }
            if not self._is_cacheable_response(response):
                return None
            stored_at = float(payload.get("stored_at") or 0.0)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None
        if (
            self.disk_cache_max_age_seconds > 0
            and time.time() - stored_at > self.disk_cache_max_age_seconds
        ):
            with self._disk_cache_lock:
                self._unlink_disk_cache_path(cache_path)
            return None
        return {
            "response": response,
            "stored_at": stored_at,
            "fresh": self.metadata_cache_ttl > 0
            and time.time() - stored_at <= self.metadata_cache_ttl,
        }

    def _store_disk_cached_response(
        self,
        cache_key: _CacheKey | None,
        response: Mapping[str, Any],
    ) -> bool:
        if (
            cache_key is None
            or self.disk_cache_dir is None
            or self._cache_key_has_credentials(cache_key)
            or not self._is_cacheable_response(response)
        ):
            return False
        cache_path = self._disk_cache_path(cache_key)
        if cache_path is None:
            return False
        body = response.get("body", b"")
        if not isinstance(body, (bytes, bytearray)):
            return False
        payload = {
            "version": DISK_CACHE_VERSION,
            "stored_at": time.time(),
            "status_code": int(response.get("status_code") or 200),
            "headers": self._safe_cached_response_headers(
                response.get("headers") or {}
            ),
            "url": str(response.get("url") or ""),
            "body_b64": base64.b64encode(bytes(body)).decode("ascii"),
        }
        with self._disk_cache_lock:
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = cache_path.with_suffix(
                    cache_path.suffix + f".{os.getpid()}.{threading.get_ident()}.tmp"
                )
                tmp_path.write_text(
                    json.dumps(payload, ensure_ascii=True, sort_keys=True),
                    encoding="utf-8",
                )
                tmp_path.replace(cache_path)
            except OSError:
                return False
            entry = self._disk_cache_entry_from_path(cache_path)
            if entry is not None:
                previous = self._disk_cache_entries.get(cache_path)
                if previous is not None:
                    self._disk_cache_total_bytes = max(
                        0, self._disk_cache_total_bytes - previous.size
                    )
                self._disk_cache_entries[cache_path] = entry
                self._disk_cache_total_bytes += entry.size
                self._disk_cache_writes_since_reconcile += 1
            self._prune_disk_cache()
            return cache_path.exists()

    def _conditional_headers_from_cached_response(
        self, response: Mapping[str, Any]
    ) -> dict[str, str]:
        headers = {
            str(key).lower(): str(value)
            for key, value in dict(response.get("headers") or {}).items()
        }
        conditional_headers: dict[str, str] = {}
        etag = headers.get("etag")
        last_modified = headers.get("last-modified")
        if etag:
            conditional_headers["If-None-Match"] = etag
        if last_modified:
            conditional_headers["If-Modified-Since"] = last_modified
        return conditional_headers

    def _response_from_not_modified(
        self,
        cached_response: Mapping[str, Any],
        *,
        response_url: str,
        headers_map: Mapping[str, str],
    ) -> dict[str, Any]:
        refreshed = self._clone_response(cached_response)
        merged_headers = dict(refreshed.get("headers") or {})
        merged_headers.update(dict(headers_map))
        refreshed["headers"] = merged_headers
        refreshed["url"] = redact_url_for_cache(
            response_url or str(refreshed.get("url") or "")
        )
        return refreshed

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
