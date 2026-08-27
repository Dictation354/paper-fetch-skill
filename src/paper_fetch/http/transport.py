"""HTTP transport request loop and connection pooling."""

from __future__ import annotations

import contextlib
from contextlib import nullcontext
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
import logging
import os
from pathlib import Path
import threading
import time
from typing import Any
import urllib.error
import urllib.parse
import zlib
from collections.abc import Callable, Iterator, Mapping

from cachetools import TTLCache
import urllib3

from ..logging_utils import emit_structured_log
from ..reason_codes import (
    ASSET_BYTES_PER_ASSET_EXCEEDED,
    ASSET_CONTENT_ENCODING_UNSUPPORTED,
)
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
from .url_policy import (
    DEFAULT_SAFE_REMOTE_URL_POLICY,
    SafeRemoteUrlPolicy,
)

DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_FULLTEXT_TIMEOUT_SECONDS = 90
DEFAULT_POOL_NUM_POOLS = 16
DEFAULT_POOL_MAXSIZE = 4
DEFAULT_PER_HOST_CONCURRENCY = 4
DEFAULT_MAX_REDIRECTS = 5
STREAM_CHUNK_BYTES = 64 * 1024
STREAM_PREVIEW_BYTES = 8192
REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})
_SENSITIVE_REDIRECT_HEADERS = frozenset(
    {"authorization", "cookie", "proxy-authorization", "referer"}
)
logger = logging.getLogger("paper_fetch.http")
_HTTP_TIMING_COLLECTOR: ContextVar[Callable[[str, float], None] | None] = ContextVar(
    "paper_fetch_http_timing_collector", default=None
)


def _parsed_content_length(headers: Mapping[str, Any]) -> int | None:
    raw = next(
        (
            value
            for key, value in headers.items()
            if str(key).lower() == "content-length"
        ),
        None,
    )
    try:
        parsed = int(str(raw))
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _header_values(headers: Any, name: str) -> tuple[str, ...]:
    getter = getattr(headers, "getlist", None)
    if callable(getter):
        try:
            return tuple(str(value) for value in getter(name) if str(value))
        except Exception:
            pass
    values = [
        str(value)
        for key, value in getattr(headers, "items", lambda: ())()
        if str(key).lower() == name.lower() and str(value)
    ]
    return tuple(values)


@contextmanager
def http_timing_collector(
    collector: Callable[[str, float], None] | None,
) -> Iterator[None]:
    """Collect request and retry wall-clock durations for the active fetch."""

    token = _HTTP_TIMING_COLLECTOR.set(collector)
    try:
        yield
    finally:
        _HTTP_TIMING_COLLECTOR.reset(token)


def _record_http_timing(stage: str, elapsed: float) -> None:
    collector = _HTTP_TIMING_COLLECTOR.get()
    if collector is None:
        return
    with contextlib.suppress(Exception):
        collector(stage, max(0.0, elapsed))


@dataclass(frozen=True)
class _PreparedRequest:
    method: str
    full_url: str
    headers: Mapping[str, str]
    follow_redirects: bool = True
    max_redirects: int = DEFAULT_MAX_REDIRECTS
    allowed_hosts: tuple[str, ...] | None = None
    sensitive_headers: tuple[str, ...] = ()
    response_headers_observer: Callable[[str, Any], None] | None = None
    request_headers_provider: (
        Callable[[str, Mapping[str, str]], Mapping[str, str]] | None
    ) = None


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
    sensitive_headers: tuple[str, ...] = ()
    timeout_seconds: int | None = None
    retry_on_rate_limit: bool | None = None
    rate_limit_retries: int | None = None
    max_rate_limit_wait_seconds: float | None = None
    retry_on_transient: bool | None = None
    transient_retries: int | None = None
    minimum_interval_seconds: float = 0.0
    route_concurrency_cap: int | None = None
    acceptance_policy: str | None = None
    asset_scope: str | None = None


@dataclass(frozen=True)
class HttpStreamOptions:
    """Streaming-only controls and observers for ``stream_to_file``."""

    timeout: int | None = None
    retry_on_rate_limit: bool | None = None
    rate_limit_retries: int | None = None
    max_rate_limit_wait_seconds: int | None = None
    retry_on_transient: bool | None = None
    transient_retries: int | None = None
    request_policy: HttpRequestPolicy | None = None
    on_content_length: Callable[[int | None], None] | None = None
    on_chunk: Callable[[int], None] | None = None
    on_response_headers: Callable[[str, Any], None] | None = None
    request_headers_provider: (
        Callable[[str, Mapping[str, str]], Mapping[str, str]] | None
    ) = None


@dataclass(frozen=True)
class _PreparedStreamRequest:
    method: str
    url: str
    prepared: _PreparedRequest
    timeout: int
    response_limit: int
    compressed_limit: int
    max_rate_limit_wait_seconds: int
    policy: HttpRequestPolicy
    options: HttpStreamOptions
    host_semaphore: Any
    cooldown_key: str
    rate_limit_policy: Any
    transient_policy: Any


def _coerce_http_stream_options(
    options: HttpStreamOptions | None,
    legacy_options: Mapping[str, Any],
) -> HttpStreamOptions:
    """Preserve keyword compatibility while new callers use one request model."""

    if not legacy_options:
        return options or HttpStreamOptions()
    known = frozenset(HttpStreamOptions.__dataclass_fields__)
    unexpected = sorted(set(legacy_options) - known)
    if unexpected:
        joined = ", ".join(unexpected)
        raise TypeError(f"unexpected stream_to_file option(s): {joined}")
    return replace(options or HttpStreamOptions(), **dict(legacy_options))


@dataclass(frozen=True)
class _HttpRequestInput:
    method: str
    url: str
    headers: Mapping[str, str] | None
    query: Mapping[str, str] | None
    timeout: int
    retry_on_rate_limit: bool
    rate_limit_retries: int
    max_rate_limit_wait_seconds: int
    retry_on_transient: bool
    transient_retries: int
    request_policy: HttpRequestPolicy | None


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
        self._rate_next_at: dict[str, float] = {}
        self._rate_start_gates: dict[str, threading.Lock] = {}
        self._cooldown_lock = threading.RLock()
        self._pool = urllib3.PoolManager(
            num_pools=self.pool_num_pools,
            maxsize=self.pool_maxsize,
            block=True,
        )
        # Instance-scoped so lightweight injected transports that do not run
        # this initializer are not mistaken for production streaming support.
        self._streaming_ready = True

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

    def _wait_for_rate_slot(
        self,
        key: str,
        minimum_interval_seconds: float,
        semaphore: threading.BoundedSemaphore | None,
    ) -> None:
        """Serialize cross-worker request starts for ``key``.

        A worker holds the per-scope start gate until its actual network start
        has been admitted.  This is intentionally different from reserving all
        future timestamps up front: a late Retry-After can move the head waiter
        without collapsing every already-queued worker onto the same deadline.
        Host concurrency is released while waiting for either the gate or the
        clock, so a paced queue cannot deadlock the requests that will produce
        the response which advances it.
        """

        interval = max(0.0, float(minimum_interval_seconds))
        if not key or interval <= 0:
            self._wait_for_cooldown(key, semaphore)
            return
        gate = self._rate_start_gate_for(key)
        self._acquire_rate_start_gate(gate, semaphore)
        try:
            while True:
                with self._cooldown_lock:
                    now = time.monotonic()
                    scheduled_at = max(
                        self._rate_next_at.get(key, 0.0),
                        self._cooldown_until.get(key, 0.0),
                    )
                self._sleep_without_host_slot(
                    semaphore,
                    max(0.0, scheduled_at - now),
                )
                with self._cooldown_lock:
                    now = time.monotonic()
                    if now < max(
                        self._rate_next_at.get(key, 0.0),
                        self._cooldown_until.get(key, 0.0),
                    ):
                        continue
                    self._cooldown_until.pop(key, None)
                    self._rate_next_at[key] = now + interval
                    return
        finally:
            gate.release()

    def _rate_start_gate_for(self, key: str) -> threading.Lock:
        with self._cooldown_lock:
            gate = self._rate_start_gates.get(key)
            if gate is None:
                gate = threading.Lock()
                self._rate_start_gates[key] = gate
            return gate

    def _acquire_rate_start_gate(
        self,
        gate: threading.Lock,
        semaphore: threading.BoundedSemaphore | None,
    ) -> None:
        if semaphore is not None:
            semaphore.release()
        try:
            if self._cancel_check is None:
                gate.acquire()
                return
            while True:
                self._check_cancelled()
                if gate.acquire(timeout=0.05):
                    return
        finally:
            if semaphore is not None:
                semaphore.acquire()

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
        timing_seconds = {
            "dns_policy_validation": 0.0,
            "connect_to_headers": 0.0,
        }
        while True:
            self._check_cancelled()
            policy_started_at = time.monotonic()
            try:
                self.remote_url_policy.validate(
                    current_url,
                    allowed_hosts=request.allowed_hosts,
                    resolve_dns=True,
                )
            finally:
                timing_seconds["dns_policy_validation"] += max(
                    0.0, time.monotonic() - policy_started_at
                )
            if current_url in visited:
                raise RequestFailure(
                    None,
                    f"Redirect loop for {redact_url_for_cache(current_url)}",
                    url=redact_url_for_cache(current_url),
                    error_category=RequestErrorCategory.UNSAFE_REDIRECT,
                )
            visited.add(current_url)
            if request.request_headers_provider is not None:
                current_headers = dict(
                    request.request_headers_provider(current_url, current_headers)
                )
            connect_started_at = time.monotonic()
            try:
                response = self._pool.request(
                    current_method,
                    current_url,
                    headers=current_headers,
                    timeout=urllib3.Timeout(connect=timeout, read=timeout),
                    preload_content=False,
                    retries=False,
                    redirect=False,
                )
            finally:
                timing_seconds["connect_to_headers"] += max(
                    0.0, time.monotonic() - connect_started_at
                )
            if request.response_headers_observer is not None:
                request.response_headers_observer(current_url, response.headers)
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
                    response._paper_fetch_timing_seconds = dict(timing_seconds)
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
            redirect_policy_started_at = time.monotonic()
            try:
                self.remote_url_policy.validate(
                    target_url,
                    allowed_hosts=request.allowed_hosts,
                    previous_url=current_url,
                    resolve_dns=False,
                )
            finally:
                timing_seconds["dns_policy_validation"] += max(
                    0.0, time.monotonic() - redirect_policy_started_at
                )
            old_origin = self._url_origin(current_url)
            new_origin = self._url_origin(target_url)
            if old_origin != new_origin:
                sensitive_headers = _SENSITIVE_REDIRECT_HEADERS | frozenset(
                    str(header).strip().lower()
                    for header in request.sensitive_headers
                    if str(header).strip()
                )
                current_headers = {
                    key: value
                    for key, value in current_headers.items()
                    if str(key).lower() not in sensitive_headers
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
        try:
            if callable(close):
                close()
        finally:
            release_conn = getattr(response, "release_conn", None)
            if callable(release_conn):
                release_conn()

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, str] | None = None,
        timeout: int | None = None,
        retry_on_rate_limit: bool | None = None,
        rate_limit_retries: int | None = None,
        max_rate_limit_wait_seconds: int | None = None,
        retry_on_transient: bool | None = None,
        transient_retries: int | None = None,
        request_policy: HttpRequestPolicy | None = None,
    ) -> dict[str, Any]:
        policy = request_policy or HttpRequestPolicy()
        started_at = time.monotonic()
        try:
            return self._request_impl(
                _HttpRequestInput(
                    method=method,
                    url=url,
                    headers=headers,
                    query=query,
                    timeout=int(
                        timeout
                        if timeout is not None
                        else policy.timeout_seconds or DEFAULT_TIMEOUT_SECONDS
                    ),
                    retry_on_rate_limit=(
                        retry_on_rate_limit
                        if retry_on_rate_limit is not None
                        else bool(policy.retry_on_rate_limit)
                    ),
                    rate_limit_retries=int(
                        rate_limit_retries
                        if rate_limit_retries is not None
                        else policy.rate_limit_retries
                        if policy.rate_limit_retries is not None
                        else 1
                    ),
                    max_rate_limit_wait_seconds=int(
                        max_rate_limit_wait_seconds
                        if max_rate_limit_wait_seconds is not None
                        else policy.max_rate_limit_wait_seconds
                        if policy.max_rate_limit_wait_seconds is not None
                        else 5
                    ),
                    retry_on_transient=(
                        retry_on_transient
                        if retry_on_transient is not None
                        else bool(policy.retry_on_transient)
                    ),
                    transient_retries=int(
                        transient_retries
                        if transient_retries is not None
                        else policy.transient_retries
                        if policy.transient_retries is not None
                        else DEFAULT_TRANSIENT_RETRIES
                    ),
                    request_policy=policy,
                )
            )
        finally:
            _record_http_timing(
                "http_seconds",
                time.monotonic() - started_at,
            )

    def _prepare_stream_request(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str] | None,
        options: HttpStreamOptions,
    ) -> _PreparedStreamRequest:
        policy = options.request_policy or HttpRequestPolicy()
        effective_timeout = int(
            options.timeout
            if options.timeout is not None
            else policy.timeout_seconds or DEFAULT_TIMEOUT_SECONDS
        )
        effective_rate_limit_retries = int(
            options.rate_limit_retries
            if options.rate_limit_retries is not None
            else policy.rate_limit_retries
            if policy.rate_limit_retries is not None
            else 1
        )
        effective_transient_retries = int(
            options.transient_retries
            if options.transient_retries is not None
            else policy.transient_retries
            if policy.transient_retries is not None
            else DEFAULT_TRANSIENT_RETRIES
        )
        response_limit = (
            self.max_response_bytes
            if policy.max_response_bytes is None
            else max(0, int(policy.max_response_bytes))
        )
        compressed_limit = (
            response_limit
            if policy.max_compressed_response_bytes is None
            else max(0, int(policy.max_compressed_response_bytes))
        )
        request_headers = {
            key: value for key, value in (headers or {}).items() if value is not None
        }
        request_headers.setdefault("Accept-Encoding", "gzip")
        prepared = _PreparedRequest(
            method=method.upper(),
            full_url=url,
            headers=request_headers,
            follow_redirects=policy.follow_redirects,
            max_redirects=max(0, int(policy.max_redirects)),
            allowed_hosts=policy.allowed_hosts,
            sensitive_headers=policy.sensitive_headers,
            response_headers_observer=options.on_response_headers,
            request_headers_provider=options.request_headers_provider,
        )
        host_semaphore = self._host_semaphore_for_url(url)
        return _PreparedStreamRequest(
            method=method,
            url=url,
            prepared=prepared,
            timeout=effective_timeout,
            response_limit=response_limit,
            compressed_limit=compressed_limit,
            max_rate_limit_wait_seconds=int(
                options.max_rate_limit_wait_seconds
                if options.max_rate_limit_wait_seconds is not None
                else policy.max_rate_limit_wait_seconds
                if policy.max_rate_limit_wait_seconds is not None
                else 5
            ),
            policy=policy,
            options=options,
            host_semaphore=host_semaphore,
            cooldown_key=self._cooldown_key_for_url(url, policy.cooldown_scope),
            rate_limit_policy=self._build_rate_limit_retry_policy(
                enabled=(
                    options.retry_on_rate_limit
                    if options.retry_on_rate_limit is not None
                    else bool(policy.retry_on_rate_limit)
                ),
                retries=effective_rate_limit_retries,
            ),
            transient_policy=self._build_transient_retry_policy(
                enabled=(
                    options.retry_on_transient
                    if options.retry_on_transient is not None
                    else bool(policy.retry_on_transient)
                ),
                retries=effective_transient_retries,
                backoff_base_seconds=max(
                    0.0, float(policy.transient_backoff_base_seconds)
                ),
            ),
        )

    def _validate_stream_response_headers(
        self,
        request: _PreparedStreamRequest,
        headers: Mapping[str, str],
        *,
        status_code: int,
        response_url: str,
    ) -> tuple[str, int]:
        declared_length = _parsed_content_length(headers)
        content_encoding = str(headers.get("content-encoding") or "").strip().lower()
        if content_encoding in {"", "identity"}:
            declared_limit = request.response_limit
        elif content_encoding == "gzip":
            declared_limit = request.compressed_limit
        else:
            raise RequestFailure(
                status_code,
                f"asset_content_encoding_unsupported: {content_encoding}",
                headers=headers,
                url=redact_url_for_cache(response_url),
                error_category=RequestErrorCategory.RESPONSE_TOO_LARGE,
                reason_code=ASSET_CONTENT_ENCODING_UNSUPPORTED,
            )
        if request.options.on_content_length is not None:
            request.options.on_content_length(
                declared_length if content_encoding in {"", "identity"} else None
            )
        if declared_length is not None and declared_length > declared_limit:
            raise RequestFailure(
                status_code,
                (
                    f"Response Content-Length exceeded {declared_limit} bytes "
                    f"for {redact_url_for_cache(response_url)}"
                ),
                headers=headers,
                url=redact_url_for_cache(response_url),
                error_category=RequestErrorCategory.RESPONSE_TOO_LARGE,
                reason_code=ASSET_BYTES_PER_ASSET_EXCEEDED,
            )
        return content_encoding, declared_limit

    def stream_to_file(
        self,
        method: str,
        url: str,
        destination: Path,
        *,
        headers: Mapping[str, str] | None = None,
        options: HttpStreamOptions | None = None,
        **legacy_options: Any,
    ) -> dict[str, Any]:
        """Stream one policy-validated response into an already unique path.

        This intentionally bypasses the in-memory/disk response caches. Redirects
        still use ``_perform_request``, so every hop is policy/DNS validated before
        the shared hostname-keyed urllib3 pool opens or reuses a connection.
        """

        started_at = time.monotonic()
        stream_options = _coerce_http_stream_options(options, legacy_options)
        stream_request = self._prepare_stream_request(
            method, url, headers, stream_options
        )
        policy = stream_request.policy
        effective_timeout = stream_request.timeout
        effective_rate_limit_wait = stream_request.max_rate_limit_wait_seconds
        response_limit = stream_request.response_limit
        compressed_limit = stream_request.compressed_limit
        prepared = stream_request.prepared
        host_semaphore = stream_request.host_semaphore
        cooldown_key = stream_request.cooldown_key
        rate_limit_policy = stream_request.rate_limit_policy
        transient_policy = stream_request.transient_policy
        transient_attempts_made = 0
        attempt = 0
        response = None
        response_complete = False
        destination_created = False
        try:
            with host_semaphore if host_semaphore is not None else nullcontext():
                while True:
                    self._wait_for_rate_slot(
                        cooldown_key,
                        policy.minimum_interval_seconds,
                        host_semaphore,
                    )
                    self._check_cancelled()
                    attempt += 1
                    request_started_at = time.monotonic()
                    try:
                        response = self._perform_request(
                            prepared, timeout=effective_timeout
                        )
                    except (urllib3.exceptions.HTTPError, urllib.error.URLError) as exc:
                        if (
                            method.upper() in {"GET", "HEAD"}
                            and self._retry_remaining(transient_policy) > 0
                            and is_retryable_network_error(exc)
                        ):
                            transient_policy = self._consume_retry(transient_policy)
                            self._sleep_without_host_slot(
                                host_semaphore,
                                self._transient_backoff_seconds(
                                    transient_policy,
                                    transient_attempts_made,
                                ),
                            )
                            transient_attempts_made += 1
                            continue
                        raise RequestFailure(
                            None,
                            (
                                "Network error for "
                                f"{redact_url_for_cache(url)}: "
                                f"{build_network_error_detail(exc)}"
                            ),
                            url=redact_url_for_cache(url),
                            error_category=classify_network_error(exc),
                        ) from exc
                    except TimeoutError as exc:
                        if (
                            method.upper() in {"GET", "HEAD"}
                            and self._retry_remaining(transient_policy) > 0
                        ):
                            transient_policy = self._consume_retry(transient_policy)
                            self._sleep_without_host_slot(
                                host_semaphore,
                                self._transient_backoff_seconds(
                                    transient_policy,
                                    transient_attempts_made,
                                ),
                            )
                            transient_attempts_made += 1
                            continue
                        raise RequestFailure(
                            None,
                            f"Network error for {redact_url_for_cache(url)}: {exc}",
                            url=redact_url_for_cache(url),
                            error_category=classify_network_error(exc),
                        ) from exc
                    response_url = (
                        getattr(response, "_paper_fetch_final_url", None)
                        or response.geturl()
                        or url
                    )
                    headers_map = {
                        str(key).lower(): str(value)
                        for key, value in response.headers.items()
                    }
                    status_code = int(response.status)
                    if status_code < 400:
                        break
                    body = self._read_raw_bytes(response, STREAM_PREVIEW_BYTES)
                    self._close_response(response)
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
                        body=bytes(body or b"")[:STREAM_PREVIEW_BYTES],
                        headers_map=headers_map,
                        rate_limit_policy=rate_limit_policy,
                        max_rate_limit_wait_seconds=effective_rate_limit_wait,
                        transient_policy=transient_policy,
                        transient_attempts_made=transient_attempts_made,
                        attempt_context=RetryAttemptContext(
                            started_at=request_started_at,
                            attempt=attempt,
                            cooldown_key=cooldown_key,
                            host_semaphore=host_semaphore,
                        ),
                    )
                content_encoding, _declared_limit = (
                    self._validate_stream_response_headers(
                        stream_request,
                        headers_map,
                        status_code=status_code,
                        response_url=response_url,
                    )
                )

                destination.parent.mkdir(parents=True, exist_ok=True)
                preview = bytearray()
                written = 0
                compressed_read = 0
                decompressor = (
                    zlib.decompressobj(16 + zlib.MAX_WBITS)
                    if content_encoding == "gzip"
                    else None
                )

                def write_chunk(stream: Any, chunk: bytes) -> None:
                    nonlocal written
                    if not chunk:
                        return
                    # Let a shared AssetBudget classify per-file versus aggregate
                    # exhaustion before the transport's local safety ceiling.
                    if stream_options.on_chunk is not None:
                        stream_options.on_chunk(len(chunk))
                    if written + len(chunk) > response_limit:
                        raise RequestFailure(
                            status_code,
                            (
                                f"Response body exceeded {response_limit} bytes for "
                                f"{redact_url_for_cache(response_url)}"
                            ),
                            headers=headers_map,
                            url=redact_url_for_cache(response_url),
                            error_category=RequestErrorCategory.RESPONSE_TOO_LARGE,
                            reason_code=ASSET_BYTES_PER_ASSET_EXCEEDED,
                        )
                    stream.write(chunk)
                    written += len(chunk)
                    if len(preview) < STREAM_PREVIEW_BYTES:
                        preview.extend(chunk[: STREAM_PREVIEW_BYTES - len(preview)])

                body_stream_started_at = time.monotonic()
                with destination.open("xb") as stream:
                    destination_created = True
                    while True:
                        self._check_cancelled()
                        raw = self._read_raw_bytes(response, STREAM_CHUNK_BYTES)
                        if not raw:
                            break
                        raw_bytes = bytes(raw)
                        compressed_read += len(raw_bytes)
                        if compressed_read > compressed_limit:
                            raise RequestFailure(
                                status_code,
                                (
                                    "Compressed response body exceeded "
                                    f"{compressed_limit} bytes for "
                                    f"{redact_url_for_cache(response_url)}"
                                ),
                                headers=headers_map,
                                url=redact_url_for_cache(response_url),
                                error_category=RequestErrorCategory.RESPONSE_TOO_LARGE,
                                reason_code=ASSET_BYTES_PER_ASSET_EXCEEDED,
                            )
                        if decompressor is None:
                            write_chunk(stream, raw_bytes)
                            continue
                        pending = raw_bytes
                        while pending:
                            expanded = decompressor.decompress(
                                pending,
                                STREAM_CHUNK_BYTES,
                            )
                            write_chunk(stream, expanded)
                            pending = decompressor.unconsumed_tail
                    if decompressor is not None:
                        write_chunk(stream, decompressor.flush(STREAM_CHUNK_BYTES))
                        if not decompressor.eof:
                            raise RequestFailure(
                                status_code,
                                (
                                    "Truncated gzip response for "
                                    f"{redact_url_for_cache(response_url)}"
                                ),
                                headers=headers_map,
                                url=redact_url_for_cache(response_url),
                                error_category=RequestErrorCategory.NETWORK_ERROR,
                            )
                        if decompressor.unused_data:
                            raise RequestFailure(
                                status_code,
                                (
                                    "Trailing gzip response data for "
                                    f"{redact_url_for_cache(response_url)}"
                                ),
                                headers=headers_map,
                                url=redact_url_for_cache(response_url),
                                error_category=RequestErrorCategory.NETWORK_ERROR,
                            )
                    stream.flush()
                    os.fsync(stream.fileno())
                response_complete = True
                return {
                    "status_code": status_code,
                    "headers": headers_map,
                    "url": redact_url_for_cache(response_url),
                    "staging_path": str(destination),
                    "downloaded_bytes": written,
                    "body_preview": bytes(preview),
                    "compressed_bytes": compressed_read,
                    "_paper_fetch_timing_seconds": {
                        **dict(
                            getattr(response, "_paper_fetch_timing_seconds", {}) or {}
                        ),
                        "body_stream": max(
                            0.0, time.monotonic() - body_stream_started_at
                        ),
                    },
                    "_paper_fetch_header_values": {
                        "set-cookie": list(
                            _header_values(response.headers, "set-cookie")
                        )
                    },
                }
        except zlib.error as exc:
            raise RequestFailure(
                None,
                f"Invalid gzip response for {redact_url_for_cache(url)}: {exc}",
                url=redact_url_for_cache(url),
                error_category=RequestErrorCategory.NETWORK_ERROR,
            ) from exc
        except (
            urllib3.exceptions.HTTPError,
            urllib.error.URLError,
            TimeoutError,
        ) as exc:
            raise RequestFailure(
                None,
                (
                    f"Network error for {redact_url_for_cache(url)}: "
                    f"{build_network_error_detail(exc)}"
                ),
                url=redact_url_for_cache(url),
                error_category=classify_network_error(exc),
            ) from exc
        finally:
            if destination_created and not response_complete:
                with contextlib.suppress(OSError):
                    destination.unlink(missing_ok=True)
            if response is not None:
                if response_complete:
                    self._release_response(response)
                else:
                    self._close_response(response)
            _record_http_timing("http_seconds", time.monotonic() - started_at)

    def request_preview(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: int | None = None,
        preview_bytes: int = STREAM_PREVIEW_BYTES,
        request_policy: HttpRequestPolicy | None = None,
        on_response_headers: Callable[[str, Any], None] | None = None,
        request_headers_provider: (
            Callable[[str, Mapping[str, str]], Mapping[str, str]] | None
        ) = None,
    ) -> dict[str, Any]:
        """Read only a bounded prefix while retaining uncached raw headers."""

        policy = request_policy or HttpRequestPolicy()
        effective_timeout = int(
            timeout
            if timeout is not None
            else policy.timeout_seconds or DEFAULT_TIMEOUT_SECONDS
        )
        request_headers = {
            key: value for key, value in (headers or {}).items() if value is not None
        }
        request_headers.setdefault("Accept-Encoding", "identity")
        prepared = _PreparedRequest(
            method=method.upper(),
            full_url=url,
            headers=request_headers,
            follow_redirects=policy.follow_redirects,
            max_redirects=max(0, int(policy.max_redirects)),
            allowed_hosts=policy.allowed_hosts,
            sensitive_headers=policy.sensitive_headers,
            response_headers_observer=on_response_headers,
            request_headers_provider=request_headers_provider,
        )
        response = None
        host_semaphore = self._host_semaphore_for_url(url)
        cooldown_key = self._cooldown_key_for_url(url, policy.cooldown_scope)
        try:
            with host_semaphore if host_semaphore is not None else nullcontext():
                self._wait_for_rate_slot(
                    cooldown_key,
                    policy.minimum_interval_seconds,
                    host_semaphore,
                )
                response = self._perform_request(prepared, timeout=effective_timeout)
                response_url = (
                    getattr(response, "_paper_fetch_final_url", None)
                    or response.geturl()
                    or url
                )
                response_headers = response.headers
                headers_map = {
                    str(key).lower(): str(value)
                    for key, value in response_headers.items()
                }
                prefix = self._read_raw_bytes(response, max(0, int(preview_bytes)))
                return {
                    "status_code": int(response.status),
                    "headers": headers_map,
                    "body_preview": bytes(prefix or b""),
                    "url": redact_url_for_cache(response_url),
                    "_paper_fetch_header_values": {
                        "set-cookie": list(
                            _header_values(response_headers, "set-cookie")
                        )
                    },
                }
        except RequestFailure:
            raise
        except (
            urllib3.exceptions.HTTPError,
            urllib.error.URLError,
            TimeoutError,
        ) as exc:
            raise RequestFailure(
                None,
                (
                    f"Network error for {redact_url_for_cache(url)}: "
                    f"{build_network_error_detail(exc)}"
                ),
                url=redact_url_for_cache(url),
                error_category=classify_network_error(exc),
            ) from exc
        finally:
            if response is not None:
                # The remainder is intentionally not read, so this connection
                # cannot be returned as a reusable pooled response.
                self._close_response(response)

    def _request_impl(
        self,
        request_input: _HttpRequestInput,
    ) -> dict[str, Any]:
        method = request_input.method
        url = request_input.url
        headers = request_input.headers
        query = request_input.query
        timeout = request_input.timeout
        retry_on_rate_limit = request_input.retry_on_rate_limit
        rate_limit_retries = request_input.rate_limit_retries
        max_rate_limit_wait_seconds = request_input.max_rate_limit_wait_seconds
        retry_on_transient = request_input.retry_on_transient
        transient_retries = request_input.transient_retries
        request_policy = request_input.request_policy
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
                self._wait_for_rate_slot(
                    cooldown_key,
                    policy.minimum_interval_seconds,
                    host_semaphore,
                )
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
                    sensitive_headers=policy.sensitive_headers,
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
                        _record_http_timing(
                            "retry_seconds",
                            time.monotonic() - request_started_at,
                        )
                        continue
                    set_cookie_values = list(
                        _header_values(response.headers, "set-cookie")
                    )
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
                    if set_cookie_values:
                        # Multi-value Set-Cookie is request-local capability
                        # state. Attach it only after both cache stores have
                        # applied the existing Set-Cookie no-store rule.
                        response_payload["_paper_fetch_header_values"] = {
                            "set-cookie": set_cookie_values
                        }
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
                        _record_http_timing(
                            "retry_seconds",
                            time.monotonic() - request_started_at,
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
                        _record_http_timing(
                            "retry_seconds",
                            time.monotonic() - request_started_at,
                        )
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
                        _record_http_timing(
                            "retry_seconds",
                            time.monotonic() - request_started_at,
                        )
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
