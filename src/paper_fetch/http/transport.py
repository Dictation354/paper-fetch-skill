"""HTTP transport request loop and connection pooling."""

from __future__ import annotations

import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import contextlib
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections.abc import Callable, Mapping

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
    RequestErrorCategory,
    RequestFailure,
    build_network_error_detail,
    classify_network_error,
    is_retryable_network_error,
)
from .retry import (
    DEFAULT_TRANSIENT_BACKOFF_BASE_SECONDS,
    DEFAULT_TRANSIENT_RETRIES,
    RetryAttemptContext,
    RetryMixin,
)
from .url_policy import DEFAULT_SAFE_REMOTE_URL_POLICY, SafeRemoteUrlPolicy

DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_FULLTEXT_TIMEOUT_SECONDS = 90
DEFAULT_POOL_NUM_POOLS = 16
DEFAULT_POOL_MAXSIZE = 4
DEFAULT_PER_HOST_CONCURRENCY = 4
DEFAULT_MAX_REDIRECTS = 5
REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})
_SENSITIVE_REDIRECT_HEADERS = frozenset(
    {"authorization", "cookie", "proxy-authorization", "referer"}
)
logger = logging.getLogger("paper_fetch.http")


@dataclass(frozen=True)
class _PreparedRequest:
    method: str
    full_url: str
    headers: Mapping[str, str]
    follow_redirects: bool = True
    max_redirects: int = DEFAULT_MAX_REDIRECTS
    allowed_hosts: tuple[str, ...] | None = None


@dataclass(frozen=True)
class HttpTransportOptions:
    cancel_check: Callable[[], bool] | None = None
    remote_url_policy: SafeRemoteUrlPolicy | None = None


@dataclass(frozen=True)
class HttpRequestPolicy:
    transient_backoff_base_seconds: float = DEFAULT_TRANSIENT_BACKOFF_BASE_SECONDS
    follow_redirects: bool = True
    max_redirects: int = DEFAULT_MAX_REDIRECTS
    allowed_hosts: tuple[str, ...] | None = None
    max_response_bytes: int | None = None
    max_compressed_response_bytes: int | None = None
    cooldown_scope: str | None = None


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
        options: HttpTransportOptions | None = None,
    ) -> None:
        transport_options = options or HttpTransportOptions()
        self.cache_ttl = max(0, int(cache_ttl))
        self.metadata_cache_ttl = max(
            0, int(metadata_cache_ttl if metadata_cache_ttl is not None else cache_ttl)
        )
        self.cache_capacity = max(0, int(cache_capacity))
        self.max_cacheable_body_bytes = max(0, int(max_cacheable_body_bytes))
        self.max_total_cache_bytes = max(0, int(max_total_cache_bytes))
        self.max_response_bytes = max(0, int(max_response_bytes))
        self.pool_num_pools = max(1, int(pool_num_pools or DEFAULT_POOL_NUM_POOLS))
        self.pool_maxsize = max(1, int(pool_maxsize or DEFAULT_POOL_MAXSIZE))
        self.per_host_concurrency = max(
            1, int(per_host_concurrency or DEFAULT_PER_HOST_CONCURRENCY)
        )
        self.disk_cache_dir = (
            Path(disk_cache_dir).expanduser() if disk_cache_dir else None
        )
        self.disk_cache_max_entries = max(
            0,
            int(
                disk_cache_max_entries
                if disk_cache_max_entries is not None
                else DEFAULT_DISK_CACHE_MAX_ENTRIES
            ),
        )
        self.disk_cache_max_bytes = max(
            0,
            int(
                disk_cache_max_bytes
                if disk_cache_max_bytes is not None
                else DEFAULT_DISK_CACHE_MAX_BYTES
            ),
        )
        self.disk_cache_max_age_seconds = max(
            0,
            int(
                disk_cache_max_age_seconds
                if disk_cache_max_age_seconds is not None
                else DEFAULT_DISK_CACHE_MAX_AGE_SECONDS
            ),
        )
        self._cancel_check = transport_options.cancel_check
        self.remote_url_policy = (
            transport_options.remote_url_policy or DEFAULT_SAFE_REMOTE_URL_POLICY
        )
        cache_maxsize = (
            self.max_total_cache_bytes
            if self.max_total_cache_bytes > 0
            else float("inf")
        )
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
        self._disk_cache_entries: dict[Path, Any] = {}
        self._disk_cache_total_bytes = 0
        self._disk_cache_index_initialized = False
        self._disk_cache_writes_since_reconcile = 0
        self._disk_cache_last_reconcile = 0.0
        self._disk_cache_last_prune = 0.0
        self._host_semaphores: dict[str, threading.BoundedSemaphore] = {}
        self._host_semaphores_lock = threading.Lock()
        self._cooldown_until: dict[str, float] = {}
        self._cooldown_lock = threading.RLock()
        self._pool = urllib3.PoolManager(
            num_pools=self.pool_num_pools,
            maxsize=self.pool_maxsize,
            block=True,
        )

    def close(self) -> None:
        """Release pooled connections owned by this transport."""

        self._pool.clear()

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

    @staticmethod
    def _cooldown_key_for_url(url: str, scope: str | None = None) -> str:
        if scope and str(scope).strip():
            return str(scope).strip().lower()
        return (urllib.parse.urlparse(url).hostname or "").lower()

    def _set_cooldown(self, key: str, delay_seconds: float) -> None:
        if not key or delay_seconds <= 0:
            return
        with self._cooldown_lock:
            self._cooldown_until[key] = max(
                self._cooldown_until.get(key, 0.0),
                time.monotonic() + delay_seconds,
            )

    def _cancellable_sleep(self, seconds: float) -> None:
        if self._cancel_check is None:
            time.sleep(max(0.0, seconds))
            return
        deadline = time.monotonic() + max(0.0, seconds)
        while True:
            self._check_cancelled()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(remaining, 0.1))

    def _sleep_without_host_slot(
        self,
        semaphore: threading.BoundedSemaphore | None,
        seconds: float,
    ) -> None:
        if seconds <= 0:
            return
        if semaphore is None:
            self._cancellable_sleep(seconds)
            return
        semaphore.release()
        try:
            self._cancellable_sleep(seconds)
        finally:
            semaphore.acquire()

    def _wait_for_cooldown(
        self,
        key: str,
        semaphore: threading.BoundedSemaphore | None,
    ) -> None:
        while key:
            with self._cooldown_lock:
                cooldown_deadline = self._cooldown_until.get(key, 0.0)
                remaining = cooldown_deadline - time.monotonic()
                if remaining <= 0:
                    self._cooldown_until.pop(key, None)
                    return
            self._sleep_without_host_slot(semaphore, remaining)
            with self._cooldown_lock:
                if self._cooldown_until.get(key, 0.0) <= cooldown_deadline:
                    self._cooldown_until.pop(key, None)
                    return

    @property
    def cancelled(self) -> bool:
        return bool(self._cancel_check and self._cancel_check())

    def _check_cancelled(self) -> None:
        if self.cancelled:
            raise RequestCancelledError("Request cancelled.")

    @staticmethod
    def _enforce_response_limit(
        response: Mapping[str, Any],
        *,
        max_response_bytes: int,
        url: str,
    ) -> None:
        body = response.get("body")
        if isinstance(body, (bytes, bytearray)) and len(body) > max_response_bytes:
            raise RequestFailure(
                int(response.get("status_code") or 0) or None,
                (
                    f"Response body exceeded {max_response_bytes} bytes for "
                    f"{redact_url_for_cache(url)}"
                ),
                body=bytes(body[:max_response_bytes]),
                headers=response.get("headers")
                if isinstance(response.get("headers"), Mapping)
                else None,
                url=redact_url_for_cache(url),
                error_category=RequestErrorCategory.RESPONSE_TOO_LARGE,
            )

    def _perform_request(self, request: _PreparedRequest, *, timeout: int) -> Any:
        current_url = request.full_url
        current_method = request.method
        current_headers = dict(request.headers)
        visited: set[str] = set()
        redirects_followed = 0
        while True:
            self._check_cancelled()
            self.remote_url_policy.validate(
                current_url,
                allowed_hosts=request.allowed_hosts,
                resolve_dns=True,
            )
            if current_url in visited:
                raise RequestFailure(
                    None,
                    f"Redirect loop for {redact_url_for_cache(current_url)}",
                    url=redact_url_for_cache(current_url),
                    error_category=RequestErrorCategory.UNSAFE_REDIRECT,
                )
            visited.add(current_url)
            response = self._pool.request(
                current_method,
                current_url,
                headers=current_headers,
                timeout=urllib3.Timeout(connect=timeout, read=timeout),
                preload_content=False,
                retries=False,
                redirect=False,
            )
            status = int(getattr(response, "status", 0) or 0)
            location = next(
                (
                    str(value)
                    for key, value in getattr(response, "headers", {}).items()
                    if str(key).lower() == "location"
                ),
                "",
            ).strip()
            if (
                not request.follow_redirects
                or status not in REDIRECT_STATUS_CODES
                or not location
            ):
                with contextlib.suppress(Exception):
                    response._paper_fetch_final_url = current_url
                return response
            if redirects_followed >= request.max_redirects:
                self._close_response(response)
                raise RequestFailure(
                    status,
                    (
                        f"Redirect limit exceeded for "
                        f"{redact_url_for_cache(request.full_url)}"
                    ),
                    headers={
                        str(key).lower(): str(value)
                        for key, value in getattr(response, "headers", {}).items()
                    },
                    url=redact_url_for_cache(current_url),
                    error_category=RequestErrorCategory.UNSAFE_REDIRECT,
                )
            target_url = urllib.parse.urljoin(current_url, location)
            self.remote_url_policy.validate(
                target_url,
                allowed_hosts=request.allowed_hosts,
                previous_url=current_url,
                resolve_dns=False,
            )
            old_origin = self._url_origin(current_url)
            new_origin = self._url_origin(target_url)
            if old_origin != new_origin:
                current_headers = {
                    key: value
                    for key, value in current_headers.items()
                    if str(key).lower() not in _SENSITIVE_REDIRECT_HEADERS
                }
            if status == 303 and current_method != "HEAD":
                current_method = "GET"
                current_headers = {
                    key: value
                    for key, value in current_headers.items()
                    if str(key).lower() not in {"content-length", "content-type"}
                }
            self._close_response(response)
            redirects_followed += 1
            current_url = target_url

    @staticmethod
    def _url_origin(url: str) -> tuple[str, str, int]:
        parsed = urllib.parse.urlsplit(url)
        scheme = parsed.scheme.lower()
        return (
            scheme,
            (parsed.hostname or "").lower(),
            parsed.port or (443 if scheme == "https" else 80),
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
        request_policy: HttpRequestPolicy | None = None,
    ) -> dict[str, Any]:
        policy = request_policy or HttpRequestPolicy()
        response_limit = (
            self.max_response_bytes
            if policy.max_response_bytes is None
            else max(0, int(policy.max_response_bytes))
        )
        compressed_response_limit = (
            None
            if policy.max_compressed_response_bytes is None
            else max(0, int(policy.max_compressed_response_bytes))
        )
        if query:
            encoded_query = urllib.parse.urlencode(query, doseq=True)
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{encoded_query}"

        request_headers = {
            key: value for key, value in (headers or {}).items() if value is not None
        }
        if not any(str(key).lower() == "accept-encoding" for key in request_headers):
            request_headers["Accept-Encoding"] = "gzip"
        cache_key = self._build_cache_key(method, url, request_headers)
        if cache_key is None:
            self._increment_cache_stat("bypass")
        cached_response = self._load_cached_response(cache_key)
        if cached_response is not None:
            self._enforce_response_limit(
                cached_response,
                max_response_bytes=response_limit,
                url=str(cached_response.get("url") or url),
            )
            self._increment_cache_stat("memory_hit")
            return cached_response
        disk_cache_entry = self._load_disk_cached_entry(cache_key)
        stale_disk_response: dict[str, Any] | None = None
        if disk_cache_entry is not None:
            disk_response = self._clone_response(disk_cache_entry["response"])
            if disk_cache_entry["fresh"]:
                self._enforce_response_limit(
                    disk_response,
                    max_response_bytes=response_limit,
                    url=str(disk_response.get("url") or url),
                )
                self._increment_cache_stat("disk_fresh_hit")
                if self._store_cached_response(cache_key, disk_response):
                    self._increment_cache_stat("store")
                return disk_response
            stale_disk_response = disk_response
            self._increment_cache_stat("disk_stale_revalidate")
            for (
                header_name,
                header_value,
            ) in self._conditional_headers_from_cached_response(disk_response).items():
                request_headers.setdefault(header_name, header_value)
        elif cache_key is not None:
            self._increment_cache_stat("miss")
        self._check_cancelled()
        transient_backoff_base_seconds = max(
            0.0,
            float(policy.transient_backoff_base_seconds),
        )
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
        cooldown_key = self._cooldown_key_for_url(url, policy.cooldown_scope)
        with host_semaphore if host_semaphore is not None else nullcontext():
            while True:
                self._wait_for_cooldown(cooldown_key, host_semaphore)
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
                request = _PreparedRequest(
                    method=method.upper(),
                    full_url=url,
                    headers=dict(request_headers),
                    follow_redirects=policy.follow_redirects,
                    max_redirects=max(0, int(policy.max_redirects)),
                    allowed_hosts=policy.allowed_hosts,
                )
                response = None
                response_reusable = False
                try:
                    response = self._perform_request(request, timeout=timeout)
                    response_url = (
                        getattr(response, "_paper_fetch_final_url", None)
                        or response.geturl()
                        or url
                    )
                    headers_map = {
                        str(key).lower(): str(value)
                        for key, value in response.headers.items()
                    }
                    payload = self._read_response_body(
                        response,
                        status_code=response.status,
                        url=response_url,
                        content_encoding=headers_map.get("content-encoding"),
                        max_response_bytes=response_limit,
                        max_compressed_response_bytes=compressed_response_limit,
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
                            elapsed_ms=round(
                                (time.monotonic() - request_started_at) * 1000, 3
                            ),
                            attempt=attempt,
                        )
                        self._increment_cache_stat("disk_304_refresh")
                        stored = self._store_cached_response(
                            cache_key, response_payload
                        )
                        stored = (
                            self._store_disk_cached_response(
                                cache_key, response_payload
                            )
                            or stored
                        )
                        if stored:
                            self._increment_cache_stat("store")
                        return response_payload
                    if int(response.status) >= 400:
                        status_code = int(response.status)
                        self._release_response(response)
                        response = None
                        (
                            rate_limit_policy,
                            transient_policy,
                            transient_attempts_made,
                        ) = self._handle_http_failure(
                            method=method,
                            request_url=url,
                            error_url=response_url,
                            status_code=status_code,
                            body=payload,
                            headers_map=headers_map,
                            rate_limit_policy=rate_limit_policy,
                            max_rate_limit_wait_seconds=max_rate_limit_wait_seconds,
                            transient_policy=transient_policy,
                            transient_attempts_made=transient_attempts_made,
                            attempt_context=RetryAttemptContext(
                                started_at=request_started_at,
                                attempt=attempt,
                                cooldown_key=cooldown_key,
                                host_semaphore=host_semaphore,
                            ),
                        )
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
                        elapsed_ms=round(
                            (time.monotonic() - request_started_at) * 1000, 3
                        ),
                        attempt=attempt,
                    )
                    stored = self._store_cached_response(cache_key, response_payload)
                    stored = (
                        self._store_disk_cached_response(cache_key, response_payload)
                        or stored
                    )
                    if stored:
                        self._increment_cache_stat("store")
                    return response_payload
                except urllib.error.HTTPError as exc:
                    try:
                        error_url = exc.geturl() or url
                        headers_map = {
                            key.lower(): value for key, value in exc.headers.items()
                        }
                        body = self._read_response_body(
                            exc,
                            status_code=exc.code,
                            url=error_url,
                            content_encoding=headers_map.get("content-encoding"),
                            max_response_bytes=response_limit,
                            max_compressed_response_bytes=compressed_response_limit,
                        )
                        (
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
                            rate_limit_policy=rate_limit_policy,
                            max_rate_limit_wait_seconds=max_rate_limit_wait_seconds,
                            transient_policy=transient_policy,
                            transient_attempts_made=transient_attempts_made,
                            attempt_context=RetryAttemptContext(
                                started_at=request_started_at,
                                attempt=attempt,
                                cooldown_key=cooldown_key,
                                host_semaphore=host_semaphore,
                            ),
                        )
                        continue
                    finally:
                        exc.close()
                except (urllib3.exceptions.HTTPError, urllib.error.URLError) as exc:
                    if (
                        method.upper() in {"GET", "HEAD"}
                        and self._retry_remaining(transient_policy) > 0
                        and is_retryable_network_error(exc)
                    ):
                        emit_structured_log(
                            logger,
                            logging.DEBUG,
                            "http_request_retry",
                            method=method.upper(),
                            url=redacted_url,
                            status=None,
                            elapsed_ms=round(
                                (time.monotonic() - request_started_at) * 1000, 3
                            ),
                            retry_after_seconds=None,
                            attempt=attempt,
                            reason="pool_timeout",
                        )
                        transient_policy = self._consume_retry(transient_policy)
                        self._sleep_without_host_slot(
                            host_semaphore,
                            self._transient_backoff_seconds(
                                transient_policy, transient_attempts_made
                            ),
                        )
                        transient_attempts_made += 1
                        continue
                    emit_structured_log(
                        logger,
                        logging.DEBUG,
                        "http_request_failure",
                        method=method.upper(),
                        url=redacted_url,
                        status=None,
                        elapsed_ms=round(
                            (time.monotonic() - request_started_at) * 1000, 3
                        ),
                        retry_after_seconds=None,
                        attempt=attempt,
                    )
                    raise RequestFailure(
                        None,
                        f"Network error for {redact_url_for_cache(url)}: {build_network_error_detail(exc)}",
                        url=redact_url_for_cache(url),
                        error_category=classify_network_error(exc),
                    ) from exc
                except TimeoutError as exc:
                    if (
                        method.upper() in {"GET", "HEAD"}
                        and self._retry_remaining(transient_policy) > 0
                    ):
                        emit_structured_log(
                            logger,
                            logging.DEBUG,
                            "http_request_retry",
                            method=method.upper(),
                            url=redacted_url,
                            status=None,
                            elapsed_ms=round(
                                (time.monotonic() - request_started_at) * 1000, 3
                            ),
                            retry_after_seconds=None,
                            attempt=attempt,
                            reason="timeout",
                        )
                        transient_policy = self._consume_retry(transient_policy)
                        self._sleep_without_host_slot(
                            host_semaphore,
                            self._transient_backoff_seconds(
                                transient_policy, transient_attempts_made
                            ),
                        )
                        transient_attempts_made += 1
                        continue
                    emit_structured_log(
                        logger,
                        logging.DEBUG,
                        "http_request_failure",
                        method=method.upper(),
                        url=redacted_url,
                        status=None,
                        elapsed_ms=round(
                            (time.monotonic() - request_started_at) * 1000, 3
                        ),
                        retry_after_seconds=None,
                        attempt=attempt,
                    )
                    raise RequestFailure(
                        None,
                        f"Network error for {redact_url_for_cache(url)}: {exc}",
                        url=redact_url_for_cache(url),
                        error_category=classify_network_error(exc),
                    ) from exc
                finally:
                    if response is not None:
                        if response_reusable:
                            self._release_response(response)
                        else:
                            self._close_response(response)
