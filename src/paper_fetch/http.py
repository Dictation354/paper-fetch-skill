"""HTTP transport and content helpers."""

from __future__ import annotations

import gzip
import base64
import hashlib
import io
import json
import logging
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from cachetools import TTLCache
import urllib3
from urllib3.util import Retry

from .logging_utils import emit_structured_log

DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_FULLTEXT_TIMEOUT_SECONDS = 90
DEFAULT_CACHE_TTL_SECONDS = 30
DEFAULT_METADATA_CACHE_TTL_SECONDS = 86400
DEFAULT_CACHE_CAPACITY = 128
DEFAULT_MAX_CACHEABLE_BODY_BYTES = 1024 * 1024
DEFAULT_MAX_TOTAL_CACHE_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_RESPONSE_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_COMPRESSED_BODY_MULTIPLIER = 8
DEFAULT_TRANSIENT_RETRIES = 2
DEFAULT_TRANSIENT_BACKOFF_BASE_SECONDS = 0.5
DEFAULT_POOL_NUM_POOLS = 16
DEFAULT_POOL_MAXSIZE = 4
DEFAULT_PER_HOST_CONCURRENCY = 4
DISK_CACHE_VERSION = 1
TRANSIENT_HTTP_STATUS_CODES = frozenset(range(500, 600))
CACHE_STAT_KEYS = (
    "memory_hit",
    "disk_fresh_hit",
    "disk_stale_revalidate",
    "disk_304_refresh",
    "miss",
    "store",
    "bypass",
)

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
REDACTED_CACHE_HEADER_DIGEST_PREFIX = "sha256:"
logger = logging.getLogger("paper_fetch.http")
_CacheKey = tuple[str, str, tuple[tuple[str, str], ...]]


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
        metadata_cache_ttl: int | None = None,
        cache_capacity: int = DEFAULT_CACHE_CAPACITY,
        max_cacheable_body_bytes: int = DEFAULT_MAX_CACHEABLE_BODY_BYTES,
        max_total_cache_bytes: int = DEFAULT_MAX_TOTAL_CACHE_BYTES,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        pool_num_pools: int | None = None,
        pool_maxsize: int | None = None,
        per_host_concurrency: int | None = None,
        disk_cache_dir: str | os.PathLike[str] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        self.cache_ttl = max(0, int(cache_ttl))
        self.metadata_cache_ttl = max(0, int(metadata_cache_ttl if metadata_cache_ttl is not None else cache_ttl))
        self.cache_capacity = max(0, int(cache_capacity))
        self.max_cacheable_body_bytes = max(0, int(max_cacheable_body_bytes))
        self.max_total_cache_bytes = max(0, int(max_total_cache_bytes))
        self.max_response_bytes = max(0, int(max_response_bytes))
        self.pool_num_pools = max(1, int(pool_num_pools or DEFAULT_POOL_NUM_POOLS))
        self.pool_maxsize = max(1, int(pool_maxsize or DEFAULT_POOL_MAXSIZE))
        self.per_host_concurrency = max(1, int(per_host_concurrency or DEFAULT_PER_HOST_CONCURRENCY))
        self.disk_cache_dir = Path(disk_cache_dir).expanduser() if disk_cache_dir else None
        self._cancel_check = cancel_check
        cache_maxsize = self.max_total_cache_bytes if self.max_total_cache_bytes > 0 else float("inf")
        self._cache: TTLCache[_CacheKey, dict[str, Any]] = TTLCache(
            maxsize=cache_maxsize,
            ttl=max(1, self.cache_ttl),
            timer=time.monotonic,
            getsizeof=self._cache_body_size,
        )
        self._cache_body_bytes = 0
        self._cache_lock = threading.RLock()
        self._cache_stats_lock = threading.Lock()
        self._cache_stats = {key: 0 for key in CACHE_STAT_KEYS}
        self._host_semaphores: dict[str, threading.BoundedSemaphore] = {}
        self._host_semaphores_lock = threading.Lock()
        self._pool = urllib3.PoolManager(
            num_pools=self.pool_num_pools,
            maxsize=self.pool_maxsize,
            block=True,
        )

    def _increment_cache_stat(self, name: str, amount: int = 1) -> None:
        if name not in self._cache_stats:
            return
        with self._cache_stats_lock:
            self._cache_stats[name] += max(0, int(amount))

    def cache_stats_snapshot(self) -> dict[str, int]:
        with self._cache_stats_lock:
            return dict(self._cache_stats)

    def _host_semaphore_for_url(self, url: str) -> threading.BoundedSemaphore | None:
        hostname = urllib.parse.urlparse(url).hostname
        if not hostname:
            return None
        normalized = hostname.lower()
        with self._host_semaphores_lock:
            semaphore = self._host_semaphores.get(normalized)
            if semaphore is None:
                semaphore = threading.BoundedSemaphore(self.per_host_concurrency)
                self._host_semaphores[normalized] = semaphore
        return semaphore

    @property
    def cancelled(self) -> bool:
        return bool(self._cancel_check and self._cancel_check())

    def _check_cancelled(self) -> None:
        if self.cancelled:
            raise RequestCancelledError("Request cancelled.")

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
        return self.disk_cache_dir / "http-text-get" / digest[:2] / f"{digest}.json"

    def _load_disk_cached_entry(self, cache_key: _CacheKey | None) -> dict[str, Any] | None:
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
                "headers": {str(key).lower(): str(value) for key, value in dict(payload.get("headers") or {}).items()},
                "body": body,
                "url": str(payload.get("url") or ""),
            }
            if not self._is_cacheable_response(response):
                return None
            stored_at = float(payload.get("stored_at") or 0.0)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
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
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = cache_path.with_suffix(cache_path.suffix + f".{os.getpid()}.{threading.get_ident()}.tmp")
            tmp_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")
            tmp_path.replace(cache_path)
        except OSError:
            return False
        return True

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

    def _build_rate_limit_retry_policy(
        self,
        *,
        enabled: bool,
        retries: int,
    ) -> Retry:
        total = max(0, int(retries)) if enabled else 0
        return Retry(
            total=total,
            status=total,
            allowed_methods=None,
            status_forcelist={429},
            respect_retry_after_header=True,
            raise_on_status=False,
        )

    def _build_transient_retry_policy(
        self,
        *,
        enabled: bool,
        retries: int,
        backoff_base_seconds: float,
    ) -> Retry:
        total = max(0, int(retries)) if enabled else 0
        return Retry(
            total=total,
            connect=total,
            read=total,
            status=total,
            other=total,
            allowed_methods=None,
            status_forcelist=TRANSIENT_HTTP_STATUS_CODES,
            backoff_factor=max(0.0, float(backoff_base_seconds)),
            respect_retry_after_header=False,
            raise_on_status=False,
        )

    def _retry_remaining(self, policy: Retry) -> int:
        return max(0, int(policy.total or 0))

    def _consume_retry(self, policy: Retry) -> Retry:
        return policy.new(total=max(0, self._retry_remaining(policy) - 1))

    def _transient_backoff_seconds(self, policy: Retry, attempts_made: int) -> float:
        return max(0.0, float(policy.backoff_factor)) * (2**attempts_made)

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
        rate_limit_policy: Retry,
        max_rate_limit_wait_seconds: int,
        transient_policy: Retry,
        transient_attempts_made: int,
    ) -> tuple[bool, Retry, Retry, int]:
        retry_after_seconds = parse_retry_after_seconds(headers_map.get("retry-after"))
        rate_limit_wait_seconds = retry_after_seconds
        if rate_limit_wait_seconds is None:
            fallback_wait_seconds = max(0.0, float(transient_policy.backoff_factor))
            if fallback_wait_seconds <= max_rate_limit_wait_seconds:
                rate_limit_wait_seconds = fallback_wait_seconds
        if (
            status_code == 429
            and self._retry_remaining(rate_limit_policy) > 0
            and rate_limit_policy.is_retry(method.upper(), status_code, retry_after_seconds is not None)
            and rate_limit_wait_seconds is not None
            and rate_limit_wait_seconds <= max_rate_limit_wait_seconds
        ):
            emit_structured_log(
                logger,
                logging.DEBUG,
                "http_request_retry",
                method=method.upper(),
                url=redact_url_for_cache(error_url),
                status=status_code,
                elapsed_ms=round((time.monotonic() - request_started_at) * 1000, 3),
                retry_after_seconds=retry_after_seconds,
                attempt=attempt,
                reason="rate_limit",
            )
            rate_limit_policy = self._consume_retry(rate_limit_policy)
            time.sleep(max(0.0, rate_limit_wait_seconds))
            return True, rate_limit_policy, transient_policy, transient_attempts_made
        if (
            self._retry_remaining(transient_policy) > 0
            and transient_policy.is_retry(method.upper(), status_code, retry_after_seconds is not None)
        ):
            emit_structured_log(
                logger,
                logging.DEBUG,
                "http_request_retry",
                method=method.upper(),
                url=redact_url_for_cache(error_url),
                status=status_code,
                elapsed_ms=round((time.monotonic() - request_started_at) * 1000, 3),
                retry_after_seconds=retry_after_seconds,
                attempt=attempt,
                reason="transient_http",
            )
            transient_policy = self._consume_retry(transient_policy)
            time.sleep(self._transient_backoff_seconds(transient_policy, transient_attempts_made))
            transient_attempts_made += 1
            return True, rate_limit_policy, transient_policy, transient_attempts_made
        emit_structured_log(
            logger,
            logging.DEBUG,
            "http_request_failure",
            method=method.upper(),
            url=redact_url_for_cache(error_url),
            status=status_code,
            elapsed_ms=round((time.monotonic() - request_started_at) * 1000, 3),
            retry_after_seconds=retry_after_seconds,
            attempt=attempt,
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
        if cache_key is None:
            self._increment_cache_stat("bypass")
        cached_response = self._load_cached_response(cache_key)
        if cached_response is not None:
            self._increment_cache_stat("memory_hit")
            return cached_response
        disk_cache_entry = self._load_disk_cached_entry(cache_key)
        stale_disk_response: dict[str, Any] | None = None
        if disk_cache_entry is not None:
            disk_response = self._clone_response(disk_cache_entry["response"])
            if disk_cache_entry["fresh"]:
                self._increment_cache_stat("disk_fresh_hit")
                if self._store_cached_response(cache_key, disk_response):
                    self._increment_cache_stat("store")
                return disk_response
            stale_disk_response = disk_response
            self._increment_cache_stat("disk_stale_revalidate")
            for header_name, header_value in self._conditional_headers_from_cached_response(disk_response).items():
                request_headers.setdefault(header_name, header_value)
        elif cache_key is not None:
            self._increment_cache_stat("miss")
        self._check_cancelled()
        transient_backoff_base_seconds = max(0.0, float(transient_backoff_base_seconds))
        rate_limit_policy = self._build_rate_limit_retry_policy(
            enabled=retry_on_rate_limit,
            retries=rate_limit_retries,
        )
        transient_policy = self._build_transient_retry_policy(
            enabled=retry_on_transient,
            retries=transient_retries,
            backoff_base_seconds=transient_backoff_base_seconds,
        )
        transient_attempts_made = 0
        attempt = 0
        host_semaphore = self._host_semaphore_for_url(url)
        with host_semaphore if host_semaphore is not None else nullcontext():
            while True:
                self._check_cancelled()
                attempt += 1
                request_started_at = time.monotonic()
                redacted_url = redact_url_for_cache(url)
                emit_structured_log(
                    logger,
                    logging.DEBUG,
                    "http_request_start",
                    method=method.upper(),
                    url=redacted_url,
                    status="attempt",
                    elapsed_ms=0.0,
                    attempt=attempt,
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
                    if int(response.status) == 304 and stale_disk_response is not None:
                        response_payload = self._response_from_not_modified(
                            stale_disk_response,
                            response_url=response_url,
                            headers_map=headers_map,
                        )
                        emit_structured_log(
                            logger,
                            logging.DEBUG,
                            "http_request_success",
                            method=method.upper(),
                            url=response_payload["url"],
                            status=int(response.status),
                            elapsed_ms=round((time.monotonic() - request_started_at) * 1000, 3),
                            attempt=attempt,
                        )
                        self._increment_cache_stat("disk_304_refresh")
                        stored = self._store_cached_response(cache_key, response_payload)
                        stored = self._store_disk_cached_response(cache_key, response_payload) or stored
                        if stored:
                            self._increment_cache_stat("store")
                        return response_payload
                    if int(response.status) >= 400:
                        (
                            should_retry,
                            rate_limit_policy,
                            transient_policy,
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
                            rate_limit_policy=rate_limit_policy,
                            max_rate_limit_wait_seconds=max_rate_limit_wait_seconds,
                            transient_policy=transient_policy,
                            transient_attempts_made=transient_attempts_made,
                        )
                        if should_retry:
                            continue
                    response_payload = {
                        "status_code": int(response.status),
                        "headers": headers_map,
                        "body": payload,
                        "url": redact_url_for_cache(response_url),
                    }
                    emit_structured_log(
                        logger,
                        logging.DEBUG,
                        "http_request_success",
                        method=method.upper(),
                        url=response_payload["url"],
                        status=int(response.status),
                        elapsed_ms=round((time.monotonic() - request_started_at) * 1000, 3),
                        attempt=attempt,
                    )
                    stored = self._store_cached_response(cache_key, response_payload)
                    stored = self._store_disk_cached_response(cache_key, response_payload) or stored
                    if stored:
                        self._increment_cache_stat("store")
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
                            rate_limit_policy,
                            transient_policy,
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
                            rate_limit_policy=rate_limit_policy,
                            max_rate_limit_wait_seconds=max_rate_limit_wait_seconds,
                            transient_policy=transient_policy,
                            transient_attempts_made=transient_attempts_made,
                        )
                        if should_retry:
                            continue
                    finally:
                        exc.close()
                except (urllib3.exceptions.HTTPError, urllib.error.URLError) as exc:
                    if self._retry_remaining(transient_policy) > 0 and is_timeout_network_error(exc):
                        emit_structured_log(
                            logger,
                            logging.DEBUG,
                            "http_request_retry",
                            method=method.upper(),
                            url=redacted_url,
                            status=None,
                            elapsed_ms=round((time.monotonic() - request_started_at) * 1000, 3),
                            retry_after_seconds=None,
                            attempt=attempt,
                            reason="pool_timeout",
                        )
                        transient_policy = self._consume_retry(transient_policy)
                        time.sleep(self._transient_backoff_seconds(transient_policy, transient_attempts_made))
                        transient_attempts_made += 1
                        continue
                    emit_structured_log(
                        logger,
                        logging.DEBUG,
                        "http_request_failure",
                        method=method.upper(),
                        url=redacted_url,
                        status=None,
                        elapsed_ms=round((time.monotonic() - request_started_at) * 1000, 3),
                        retry_after_seconds=None,
                        attempt=attempt,
                    )
                    raise RequestFailure(
                        None,
                        f"Network error for {redact_url_for_cache(url)}: {build_network_error_detail(exc)}",
                        url=redact_url_for_cache(url),
                    ) from exc
                except (socket.timeout, TimeoutError) as exc:
                    if self._retry_remaining(transient_policy) > 0:
                        emit_structured_log(
                            logger,
                            logging.DEBUG,
                            "http_request_retry",
                            method=method.upper(),
                            url=redacted_url,
                            status=None,
                            elapsed_ms=round((time.monotonic() - request_started_at) * 1000, 3),
                            retry_after_seconds=None,
                            attempt=attempt,
                            reason="timeout",
                        )
                        transient_policy = self._consume_retry(transient_policy)
                        time.sleep(self._transient_backoff_seconds(transient_policy, transient_attempts_made))
                        transient_attempts_made += 1
                        continue
                    emit_structured_log(
                        logger,
                        logging.DEBUG,
                        "http_request_failure",
                        method=method.upper(),
                        url=redacted_url,
                        status=None,
                        elapsed_ms=round((time.monotonic() - request_started_at) * 1000, 3),
                        retry_after_seconds=None,
                        attempt=attempt,
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


def is_xml_content_type(content_type: str | None) -> bool:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    return normalized in {"application/xml", "text/xml", "application/jats+xml"} or normalized.endswith("+xml")


def is_textual_content_type(content_type: str | None) -> bool:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    if not normalized:
        return False
    return (
        any(normalized.startswith(prefix) or normalized == prefix for prefix in TEXTUAL_CONTENT_TYPES)
        or normalized.endswith("+xml")
        or normalized.endswith("+json")
    )


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
