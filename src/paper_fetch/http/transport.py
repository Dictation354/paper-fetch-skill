"""HTTP transport request loop and connection pooling."""

from __future__ import annotations

import logging
import os
import socket
import threading
import time
import urllib.error
import urllib.parse
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from cachetools import TTLCache
import urllib3

from ..logging_utils import emit_structured_log
from .body import BodyMixin, DEFAULT_MAX_RESPONSE_BYTES
from .cache import (
    CACHE_STAT_KEYS,
    DEFAULT_CACHE_CAPACITY,
    DEFAULT_CACHE_TTL_SECONDS,
    DEFAULT_DISK_CACHE_MAX_AGE_SECONDS,
    DEFAULT_DISK_CACHE_MAX_BYTES,
    DEFAULT_DISK_CACHE_MAX_ENTRIES,
    DEFAULT_MAX_CACHEABLE_BODY_BYTES,
    DEFAULT_MAX_TOTAL_CACHE_BYTES,
    CacheMixin,
    _CacheKey,
    redact_url_for_cache,
)
from .errors import (
    RequestCancelledError,
    RequestFailure,
    build_network_error_detail,
    is_timeout_network_error,
)
from .retry import (
    DEFAULT_TRANSIENT_BACKOFF_BASE_SECONDS,
    DEFAULT_TRANSIENT_RETRIES,
    RetryMixin,
)

DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_FULLTEXT_TIMEOUT_SECONDS = 90
DEFAULT_POOL_NUM_POOLS = 16
DEFAULT_POOL_MAXSIZE = 4
DEFAULT_PER_HOST_CONCURRENCY = 4
logger = logging.getLogger("paper_fetch.http")


@dataclass(frozen=True)
class _PreparedRequest:
    method: str
    full_url: str
    headers: Mapping[str, str]


class HttpTransport(CacheMixin, RetryMixin, BodyMixin):
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
        disk_cache_max_entries: int | None = None,
        disk_cache_max_bytes: int | None = None,
        disk_cache_max_age_seconds: int | None = None,
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
        self.disk_cache_max_entries = max(
            0,
            int(disk_cache_max_entries if disk_cache_max_entries is not None else DEFAULT_DISK_CACHE_MAX_ENTRIES),
        )
        self.disk_cache_max_bytes = max(
            0,
            int(disk_cache_max_bytes if disk_cache_max_bytes is not None else DEFAULT_DISK_CACHE_MAX_BYTES),
        )
        self.disk_cache_max_age_seconds = max(
            0,
            int(
                disk_cache_max_age_seconds
                if disk_cache_max_age_seconds is not None
                else DEFAULT_DISK_CACHE_MAX_AGE_SECONDS
            ),
        )
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
        self._disk_cache_lock = threading.RLock()
        self._host_semaphores: dict[str, threading.BoundedSemaphore] = {}
        self._host_semaphores_lock = threading.Lock()
        self._pool = urllib3.PoolManager(
            num_pools=self.pool_num_pools,
            maxsize=self.pool_maxsize,
            block=True,
        )

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
