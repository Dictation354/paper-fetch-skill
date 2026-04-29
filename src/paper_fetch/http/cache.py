"""HTTP cache key, memory cache, and disk cache helpers."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

DEFAULT_CACHE_TTL_SECONDS = 30
DEFAULT_METADATA_CACHE_TTL_SECONDS = 86400
DEFAULT_CACHE_CAPACITY = 128
DEFAULT_MAX_CACHEABLE_BODY_BYTES = 1024 * 1024
DEFAULT_MAX_TOTAL_CACHE_BYTES = 16 * 1024 * 1024
DEFAULT_DISK_CACHE_MAX_ENTRIES = 4096
DEFAULT_DISK_CACHE_MAX_BYTES = 512 * 1024 * 1024
DEFAULT_DISK_CACHE_MAX_AGE_DAYS = 30
DEFAULT_DISK_CACHE_MAX_AGE_SECONDS = DEFAULT_DISK_CACHE_MAX_AGE_DAYS * 24 * 60 * 60
DISK_CACHE_VERSION = 1
DISK_CACHE_ROOT_NAME = "http-text-get"
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
REDACTED_CACHE_HEADER_DIGEST_PREFIX = "sha256:"
_CacheKey = tuple[str, str, tuple[tuple[str, str], ...]]


@dataclass(frozen=True)
class _DiskCacheEntry:
    path: Path
    size: int
    stored_at: float


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


class CacheMixin:
    """Private cache methods mixed into ``HttpTransport``."""

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
            digest = hashlib.sha256(f"{normalized_key}\0{value}".encode("utf-8")).hexdigest()[:16]
            return f"{REDACTED_CACHE_HEADER_DIGEST_PREFIX}{digest}"
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
        encoded_key = json.dumps(cache_key, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(encoded_key).hexdigest()
        return self._disk_cache_root() / digest[:2] / f"{digest}.json"

    def _disk_cache_root(self) -> Path:
        assert self.disk_cache_dir is not None
        return self.disk_cache_dir / DISK_CACHE_ROOT_NAME

    def _unlink_disk_cache_path(self, path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            return
        except OSError:
            return
        try:
            path.parent.rmdir()
        except OSError:
            pass

    def _disk_cache_entry_from_path(self, path: Path) -> _DiskCacheEntry | None:
        try:
            stat_result = path.stat()
        except OSError:
            return None
        stored_at = float(stat_result.st_mtime)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            stored_at = float(payload.get("stored_at") or stored_at)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        return _DiskCacheEntry(path=path, size=max(0, int(stat_result.st_size)), stored_at=stored_at)

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
            now = time.time()
            entries = self._iter_disk_cache_entries()
            survivors: list[_DiskCacheEntry] = []
            for entry in entries:
                if self.disk_cache_max_age_seconds > 0 and now - entry.stored_at > self.disk_cache_max_age_seconds:
                    self._unlink_disk_cache_path(entry.path)
                else:
                    survivors.append(entry)

            survivors.sort(key=lambda item: (item.stored_at, str(item.path)))
            if self.disk_cache_max_entries > 0 and len(survivors) > self.disk_cache_max_entries:
                remove_count = len(survivors) - self.disk_cache_max_entries
                for entry in survivors[:remove_count]:
                    self._unlink_disk_cache_path(entry.path)
                survivors = survivors[remove_count:]

            if self.disk_cache_max_bytes > 0:
                total_bytes = sum(entry.size for entry in survivors)
                while survivors and total_bytes > self.disk_cache_max_bytes:
                    entry = survivors.pop(0)
                    total_bytes -= entry.size
                    self._unlink_disk_cache_path(entry.path)

    def _load_disk_cached_entry(self, cache_key: _CacheKey | None) -> dict[str, Any] | None:
        if cache_key is None:
            return None
        cache_path = self._disk_cache_path(cache_key)
        if cache_path is None:
            return None
        with self._disk_cache_lock:
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
                if payload.get("version") != DISK_CACHE_VERSION:
                    return None
                body = base64.b64decode(str(payload.get("body_b64") or ""), validate=True)
                response = {
                    "status_code": int(payload.get("status_code") or 200),
                    "headers": {str(key).lower(): str(value) for key, value in dict(payload.get("headers") or {}).items()},
                    "body": body,
                    "url": str(payload.get("url") or ""),
                }
                if not self._is_cacheable_response(response):
                    return None
                stored_at = float(payload.get("stored_at") or 0.0)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                return None
            if self.disk_cache_max_age_seconds > 0 and time.time() - stored_at > self.disk_cache_max_age_seconds:
                self._unlink_disk_cache_path(cache_path)
                return None
        return {
            "response": response,
            "stored_at": stored_at,
            "fresh": self.metadata_cache_ttl > 0 and time.time() - stored_at <= self.metadata_cache_ttl,
        }

    def _store_disk_cached_response(
        self,
        cache_key: _CacheKey | None,
        response: Mapping[str, Any],
    ) -> bool:
        if cache_key is None or self.disk_cache_dir is None or not self._is_cacheable_response(response):
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
            "headers": dict(response.get("headers") or {}),
            "url": str(response.get("url") or ""),
            "body_b64": base64.b64encode(bytes(body)).decode("ascii"),
        }
        with self._disk_cache_lock:
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = cache_path.with_suffix(cache_path.suffix + f".{os.getpid()}.{threading.get_ident()}.tmp")
                tmp_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")
                tmp_path.replace(cache_path)
            except OSError:
                return False
            self._prune_disk_cache()
            return cache_path.exists()

    def _conditional_headers_from_cached_response(self, response: Mapping[str, Any]) -> dict[str, str]:
        headers = {str(key).lower(): str(value) for key, value in dict(response.get("headers") or {}).items()}
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
        refreshed["url"] = redact_url_for_cache(response_url or str(refreshed.get("url") or ""))
        return refreshed

    def _is_cacheable_response(self, response: Mapping[str, Any]) -> bool:
        from .body import is_textual_content_type

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

    def _enforce_cache_capacity(self) -> None:
        while len(self._cache) > self.cache_capacity:
            self._cache.popitem()

    def _sync_cache_body_bytes(self) -> None:
        self._cache_body_bytes = int(self._cache.currsize)

    def _discard_cache_entry(self, cache_key: _CacheKey) -> None:
        self._cache.pop(cache_key, None)
        self._sync_cache_body_bytes()
