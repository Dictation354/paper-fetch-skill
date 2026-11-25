"""HTTP transport request scheduler, rate gating, and connection pooling."""

from __future__ import annotations

import contextlib
import logging
import socket
import threading
import time
import urllib.error
import urllib.parse
from collections.abc import Callable, Iterator, Mapping
from contextlib import nullcontext
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import partial
from http.client import BadStatusLine, IncompleteRead, InvalidURL, RemoteDisconnected
from http.client import HTTPResponse as StandardHTTPResponse
from pathlib import Path
from typing import Any, Literal, TypeVar

import urllib3
from urllib3.connection import HTTPConnection, HTTPSConnection

from ..logging_utils import emit_structured_log
from ..timeouts import (
    DEFAULT_FULLTEXT_TIMEOUT_SECONDS as DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
)
from .body import (
    DEFAULT_MAX_RESPONSE_BYTES,
    STREAM_CHUNK_BYTES,
    STREAM_PREVIEW_BYTES,
    read_bounded_response_body,
    read_raw_response_bytes,
    stream_bounded_response_to_file,
)
from .cache import (
    DEFAULT_CACHE_CAPACITY,
    DEFAULT_CACHE_TTL_SECONDS,
    DEFAULT_MAX_CACHEABLE_BODY_BYTES,
    DEFAULT_MAX_TOTAL_CACHE_BYTES,
    ResponseMemoryCache,
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
from .rate_limit import RequestRateGate
from .retry import (
    DEFAULT_TRANSIENT_BACKOFF_BASE_SECONDS,
    DEFAULT_TRANSIENT_RETRIES,
    RETRYABLE_METHODS,
    RetryDecision,
    RetryState,
    build_rate_limit_retry_policy,
    build_transient_retry_policy,
)
from .url_policy import DEFAULT_SAFE_REMOTE_URL_POLICY, SafeRemoteUrlPolicy

request_cancel_check: ContextVar[Callable[[], bool] | None] = ContextVar(
    "paper_fetch_request_cancel_check", default=None
)
request_timeout_limit: ContextVar[Callable[[], float] | None] = ContextVar(
    "paper_fetch_request_timeout_limit", default=None
)

DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_POOL_NUM_POOLS = 16
DEFAULT_POOL_MAXSIZE = 4
DEFAULT_PER_HOST_CONCURRENCY = 4
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_RATE_LIMIT_RETRIES = 1
DEFAULT_MAX_RATE_LIMIT_WAIT_SECONDS = 5
REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})
_SENSITIVE_REDIRECT_HEADERS = frozenset(
    {"authorization", "cookie", "proxy-authorization", "referer"}
)
logger = logging.getLogger("paper_fetch.http")

_T = TypeVar("_T")
_NETWORK_RETRY_EXCEPTIONS = (
    urllib3.exceptions.HTTPError,
    IncompleteRead,
    RemoteDisconnected,
    urllib.error.URLError,
    TimeoutError,
    OSError,
)


class _SocketReadGuard:
    """Update the deadline for each receive inside a buffered read."""

    def __init__(self, sock: socket.socket, before_read: Callable[[], None]) -> None:
        self.sock = sock
        self.before_read = before_read

    def recv_into(self, buffer: Any) -> int:
        self.before_read()
        return self.sock.recv_into(buffer)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.sock, name)


@contextlib.contextmanager
def _guard_socket_reads(
    socket_io: Any, sock: socket.socket, before_read: Callable[[], None]
) -> Iterator[None]:
    socket_io._sock = _SocketReadGuard(sock, before_read)
    try:
        yield
    finally:
        socket_io._sock = sock


class _DeadlineHTTPResponse(StandardHTTPResponse):
    def begin(self) -> None:
        raw = getattr(self.fp, "raw", None)
        sock = getattr(raw, "_sock", None)
        if (
            request_timeout_limit.get() is None
            or not isinstance(raw, socket.SocketIO)
            or sock is None
        ):
            super().begin()
            return
        idle_timeout = sock.gettimeout()

        def before_read() -> None:
            remaining = HttpTransport._remaining_request_time()
            sock.settimeout(
                remaining if idle_timeout is None else min(idle_timeout, remaining)
            )

        # http.client can read multiple packets before completing one header line.
        with _guard_socket_reads(raw, sock, before_read):
            super().begin()


class _DeadlineHTTPConnection(HTTPConnection):
    response_class = _DeadlineHTTPResponse


class _DeadlineHTTPSConnection(HTTPSConnection):
    response_class = _DeadlineHTTPResponse


class _DeadlineHTTPPool(urllib3.HTTPConnectionPool):
    ConnectionCls = _DeadlineHTTPConnection


class _DeadlineHTTPSPool(urllib3.HTTPSConnectionPool):
    ConnectionCls = _DeadlineHTTPSConnection


def _header_values(headers: Any, name: str) -> tuple[str, ...]:
    getter = getattr(headers, "getlist", None)
    if callable(getter):
        with contextlib.suppress(Exception):
            return tuple(str(value) for value in getter(name) if str(value))
    values = [
        str(value)
        for key, value in getattr(headers, "items", lambda: ())()
        if str(key).lower() == name.lower() and str(value)
    ]
    return tuple(values)


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
class _PoolCallResult:
    """Pooled HTTP response paired with redirect-resolved URL and timings."""

    response: Any
    final_url: str
    timing_seconds: dict[str, float] = field(default_factory=dict)


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
    body_access_provider: str | None = None
    sensitive_headers: tuple[str, ...] = ()
    timeout_seconds: int | None = None
    retry_on_rate_limit: bool | None = None
    rate_limit_retries: int | None = None
    max_rate_limit_wait_seconds: float | None = None
    retry_on_transient: bool | None = None
    transient_retries: int | None = None
    minimum_interval_seconds: float = 0.0


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
class _EffectiveRequestConfig:
    """Normalized immutable execution settings shared by buffered and stream paths."""

    method: str
    url: str
    headers: dict[str, str]
    prepared: _PreparedRequest
    policy: HttpRequestPolicy
    timeout: float
    response_limit: int
    compressed_response_limit: int | None
    host_semaphore: threading.BoundedSemaphore | None
    cooldown_key: str
    retry_on_rate_limit: bool
    rate_limit_retries: int
    max_rate_limit_wait_seconds: int
    retry_on_transient: bool
    transient_retries: int

    @property
    def stream_compressed_limit(self) -> int:
        return (
            self.response_limit
            if self.compressed_response_limit is None
            else self.compressed_response_limit
        )

    def build_retry_state(self) -> RetryState:
        return RetryState(
            rate_limit_policy=build_rate_limit_retry_policy(
                enabled=self.retry_on_rate_limit,
                retries=self.rate_limit_retries,
            ),
            transient_policy=build_transient_retry_policy(
                enabled=self.retry_on_transient,
                retries=self.transient_retries,
                backoff_base_seconds=max(
                    0.0, float(self.policy.transient_backoff_base_seconds)
                ),
            ),
            max_rate_limit_wait_seconds=self.max_rate_limit_wait_seconds,
            body_access_provider=self.policy.body_access_provider,
        )


@dataclass(frozen=True)
class _AttemptSuccessContext:
    pool_result: _PoolCallResult
    response_url: str
    headers_map: dict[str, str]
    status_code: int
    attempt: int
    started_at: float


class HttpTransport:
    """Minimal HTTP transport with short-lived in-memory caching and rate gating."""

    def __init__(
        self,
        *,
        cache_ttl: int = DEFAULT_CACHE_TTL_SECONDS,
        cache_capacity: int = DEFAULT_CACHE_CAPACITY,
        max_cacheable_body_bytes: int = DEFAULT_MAX_CACHEABLE_BODY_BYTES,
        max_total_cache_bytes: int = DEFAULT_MAX_TOTAL_CACHE_BYTES,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        pool_num_pools: int | None = None,
        pool_maxsize: int | None = None,
        per_host_concurrency: int | None = None,
        options: HttpTransportOptions | None = None,
    ) -> None:
        transport_options = options or HttpTransportOptions()
        self._response_cache = ResponseMemoryCache(
            ttl=cache_ttl,
            capacity=cache_capacity,
            max_cacheable_body_bytes=max_cacheable_body_bytes,
            max_total_cache_bytes=max_total_cache_bytes,
        )
        self.cache_ttl = self._response_cache.ttl
        self.cache_capacity = self._response_cache.capacity
        self.max_cacheable_body_bytes = self._response_cache.max_cacheable_body_bytes
        self.max_total_cache_bytes = self._response_cache.max_total_cache_bytes
        self.max_response_bytes = max(0, int(max_response_bytes))
        self.pool_num_pools = max(1, int(pool_num_pools or DEFAULT_POOL_NUM_POOLS))
        self.pool_maxsize = max(1, int(pool_maxsize or DEFAULT_POOL_MAXSIZE))
        self.per_host_concurrency = max(
            1, int(per_host_concurrency or DEFAULT_PER_HOST_CONCURRENCY)
        )
        self._cancel_check = transport_options.cancel_check
        self.remote_url_policy = (
            transport_options.remote_url_policy or DEFAULT_SAFE_REMOTE_URL_POLICY
        )
        self._cache = self._response_cache.entries
        self._rate_gate = RequestRateGate(
            per_host_concurrency=self.per_host_concurrency,
            clock=lambda: time.monotonic(),
            sleep=lambda seconds: self._cancellable_sleep(seconds),
            has_cancel_hooks=lambda: (
                self._cancel_check is not None or request_cancel_check.get() is not None
            ),
            check_cancelled=self._check_cancelled,
        )
        self._pool = urllib3.PoolManager(
            num_pools=self.pool_num_pools,
            maxsize=self.pool_maxsize,
            block=True,
        )
        self._pool.pool_classes_by_scheme = {
            "http": _DeadlineHTTPPool,
            "https": _DeadlineHTTPSPool,
        }

    @property
    def _cache_body_bytes(self) -> int:
        return self._response_cache.body_bytes

    def close(self) -> None:
        """Release pooled connections owned by this transport."""

        self._pool.clear()

    @property
    def cancelled(self) -> bool:
        local_check = request_cancel_check.get()
        return bool(
            (self._cancel_check and self._cancel_check())
            or (local_check and local_check())
        )

    def _check_cancelled(self) -> None:
        if self.cancelled:
            raise RequestCancelledError("Request cancelled.")

    @staticmethod
    def _remaining_request_time() -> float:
        timeout_limit = request_timeout_limit.get()
        remaining = timeout_limit() if timeout_limit is not None else float("inf")
        if remaining <= 0:
            raise RequestFailure(
                None,
                "Request deadline exceeded.",
                error_category=RequestErrorCategory.TIMEOUT,
                retryable=False,
            )
        return remaining

    def sleep_with_cancel(self, seconds: float) -> None:
        """Sleep for ``seconds`` while polling cooperative cancellation checks."""

        if (
            self._cancel_check is None
            and request_cancel_check.get() is None
            and request_timeout_limit.get() is None
        ):
            time.sleep(max(0.0, seconds))
            return
        deadline = time.monotonic() + max(0.0, seconds)
        while True:
            self._check_cancelled()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(remaining, self._remaining_request_time(), 0.1))

    def _cancellable_sleep(self, seconds: float) -> None:
        self.sleep_with_cancel(seconds)

    def _set_cooldown(self, key: str, delay_seconds: float) -> None:
        self._rate_gate.set_cooldown(key, delay_seconds)

    def _wait_for_rate_slot(
        self,
        key: str,
        minimum_interval_seconds: float,
        semaphore: threading.BoundedSemaphore | None,
    ) -> None:
        self._rate_gate.wait_for_rate_slot(key, minimum_interval_seconds, semaphore)

    def _rate_start_gate_for(self, key: str) -> threading.Lock:
        return self._rate_gate.rate_start_gate_for(key)

    @staticmethod
    def _enforce_response_limit(
        response: Mapping[str, Any],
        *,
        max_response_bytes: int,
        url: str,
    ) -> None:
        body = response.get("body")
        if isinstance(body, bytes | bytearray) and len(body) > max_response_bytes:
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

    def _normalize_request_config(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str] | None,
        query: Mapping[str, str] | None = None,
        timeout: float | None = None,
        retry_on_rate_limit: bool | None = None,
        rate_limit_retries: int | None = None,
        max_rate_limit_wait_seconds: int | float | None = None,
        retry_on_transient: bool | None = None,
        transient_retries: int | None = None,
        request_policy: HttpRequestPolicy | None = None,
        response_headers_observer: Callable[[str, Any], None] | None = None,
        request_headers_provider: (
            Callable[[str, Mapping[str, str]], Mapping[str, str]] | None
        ) = None,
    ) -> _EffectiveRequestConfig:
        policy = request_policy or HttpRequestPolicy()
        resolved_url = url
        if query:
            encoded_query = urllib.parse.urlencode(query, doseq=True)
            separator = "&" if "?" in resolved_url else "?"
            resolved_url = f"{resolved_url}{separator}{encoded_query}"

        request_headers = {
            key: value for key, value in (headers or {}).items() if value is not None
        }
        if not any(str(key).lower() == "accept-encoding" for key in request_headers):
            request_headers["Accept-Encoding"] = "gzip"

        response_limit = (
            self.max_response_bytes
            if policy.max_response_bytes is None
            else max(0, int(policy.max_response_bytes))
        )
        compressed_limit = (
            None
            if policy.max_compressed_response_bytes is None
            else max(0, int(policy.max_compressed_response_bytes))
        )
        prepared = _PreparedRequest(
            method=method.upper(),
            full_url=resolved_url,
            headers=dict(request_headers),
            follow_redirects=policy.follow_redirects,
            max_redirects=max(0, int(policy.max_redirects)),
            allowed_hosts=policy.allowed_hosts,
            sensitive_headers=policy.sensitive_headers,
            response_headers_observer=response_headers_observer,
            request_headers_provider=request_headers_provider,
        )
        return _EffectiveRequestConfig(
            method=method,
            url=resolved_url,
            headers=request_headers,
            prepared=prepared,
            policy=policy,
            timeout=(
                timeout
                if timeout is not None
                else policy.timeout_seconds or DEFAULT_TIMEOUT_SECONDS
            ),
            response_limit=response_limit,
            compressed_response_limit=compressed_limit,
            host_semaphore=self._rate_gate.host_semaphore_for_url(resolved_url),
            cooldown_key=self._rate_gate.cooldown_key_for_url(
                resolved_url, policy.cooldown_scope
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
                else DEFAULT_RATE_LIMIT_RETRIES
            ),
            max_rate_limit_wait_seconds=int(
                max_rate_limit_wait_seconds
                if max_rate_limit_wait_seconds is not None
                else policy.max_rate_limit_wait_seconds
                if policy.max_rate_limit_wait_seconds is not None
                else DEFAULT_MAX_RATE_LIMIT_WAIT_SECONDS
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
        )

    def _execute_pool_request(
        self, request: _PreparedRequest, *, timeout: float
    ) -> _PoolCallResult:
        current_url = request.full_url
        current_method = request.method
        current_headers = dict(request.headers)
        visited: set[str] = set()
        redirects_followed = 0
        timing_seconds = {"dns_policy_validation": 0.0, "connect_to_headers": 0.0}
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
            timeout_limit = request_timeout_limit.get()
            hop_timeout = min(timeout, self._remaining_request_time())
            socket_timeout = urllib3.Timeout(
                connect=hop_timeout,
                read=hop_timeout,
                total=hop_timeout if timeout_limit else None,
            )
            connect_started_at = time.monotonic()
            try:
                response = self._pool.request(
                    current_method,
                    current_url,
                    headers=current_headers,
                    timeout=socket_timeout,
                    preload_content=False,
                    retries=False,
                    redirect=False,
                )
                if timeout_limit is not None:
                    try:
                        self._remaining_request_time()
                    except BaseException:
                        self._close_response(response)
                        raise
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
                return _PoolCallResult(
                    response=response,
                    final_url=current_url,
                    timing_seconds=dict(timing_seconds),
                )
            if redirects_followed >= request.max_redirects:
                self._close_response(response)
                raise RequestFailure(
                    status,
                    f"Redirect limit exceeded for {redact_url_for_cache(request.full_url)}",
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
            if self._url_origin(current_url) != self._url_origin(target_url):
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

    def _perform_request(self, request: _PreparedRequest, *, timeout: float) -> Any:
        return self._execute_pool_request(request, timeout=timeout).response

    def _dispatch_pool_request(
        self, request: _PreparedRequest, *, timeout: float
    ) -> _PoolCallResult:
        if (
            "_perform_request" not in self.__dict__
            and type(self)._perform_request is HttpTransport._perform_request
        ):
            return self._execute_pool_request(request, timeout=timeout)
        raw_result = self._perform_request(request, timeout=timeout)
        if isinstance(raw_result, _PoolCallResult):
            return raw_result
        geturl = getattr(raw_result, "geturl", None)
        resolved_url = (
            str(geturl() or "") if callable(geturl) else ""
        ) or request.full_url
        return _PoolCallResult(response=raw_result, final_url=resolved_url)

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

    def _read_response_chunk(
        self, response: Any, limit: int, *, timeout: float
    ) -> bytes:
        self._check_cancelled()
        timeout_limit = request_timeout_limit.get()
        if timeout_limit is not None:
            self._remaining_request_time()
        if isinstance(response, urllib3.HTTPResponse):
            # read1 returns after one buffered read, even if only one byte arrived.
            with self._bound_socket_reads(response, timeout=timeout):
                chunk = response.read1(limit, decode_content=False) or b""
        else:
            chunk = read_raw_response_bytes(response, limit)
        self._check_cancelled()
        if timeout_limit is not None:
            self._remaining_request_time()
        return chunk

    @contextlib.contextmanager
    def _bound_socket_reads(
        self, response: urllib3.HTTPResponse, *, timeout: float
    ) -> Iterator[None]:
        if request_timeout_limit.get() is None:
            yield
            return
        # http.client can detach a connection-close socket after headers.
        raw = getattr(getattr(response._fp, "fp", None), "raw", None)
        sock = getattr(raw, "_sock", None) or getattr(response.connection, "sock", None)
        if sock is None:
            yield
            return

        def before_read() -> None:
            self._check_cancelled()
            sock.settimeout(min(timeout, self._remaining_request_time()))

        before_read()
        if not (response.chunked and isinstance(raw, socket.SocketIO)):
            yield
            return
        # A chunk size or trailer line can need multiple receives before read1 returns.
        with _guard_socket_reads(raw, sock, before_read):
            yield

    def _read_response_body(
        self, response: Any, limit: int, *, timeout: float
    ) -> bytes:
        if not isinstance(response, urllib3.HTTPResponse):
            return self._read_response_chunk(response, limit, timeout=timeout)
        body = bytearray()
        while len(body) < limit:
            chunk = self._read_response_chunk(
                response, min(STREAM_CHUNK_BYTES, limit - len(body)), timeout=timeout
            )
            if not chunk:
                break
            body.extend(chunk)
        return bytes(body)

    def _apply_retry_decision(
        self,
        decision: RetryDecision,
        *,
        cooldown_key: str,
        host_semaphore: threading.BoundedSemaphore | None,
    ) -> None:
        if decision.kind == "rate_limit":
            self._rate_gate.set_cooldown(cooldown_key, decision.wait_seconds)
            self._rate_gate.wait_for_cooldown(cooldown_key, host_semaphore)
            return
        self._rate_gate.sleep_without_host_slot(host_semaphore, decision.wait_seconds)

    def _handle_network_exception(
        self,
        exc: Exception,
        *,
        config: _EffectiveRequestConfig,
        retry_state: RetryState,
        started_at: float,
        attempt: int,
    ) -> None:
        is_timeout = isinstance(exc, TimeoutError) and not isinstance(
            exc, urllib3.exceptions.HTTPError | urllib.error.URLError
        )
        decision = retry_state.decide_network_error(
            method=config.method,
            request_url=config.url,
            exc=exc,
            started_at=started_at,
            attempt=attempt,
            is_timeout=is_timeout,
        )
        self._apply_retry_decision(
            decision,
            cooldown_key=config.cooldown_key,
            host_semaphore=config.host_semaphore,
        )

    def _execute_scheduled_request(
        self,
        config: _EffectiveRequestConfig,
        *,
        error_body_mode: Literal["bounded", "preview"],
        retry_body_errors: bool,
        on_success: Callable[[_AttemptSuccessContext], _T],
    ) -> _T:
        retry_state = config.build_retry_state()
        attempt = 0
        redacted_url = redact_url_for_cache(config.url)

        with (
            config.host_semaphore
            if config.host_semaphore is not None
            else nullcontext()
        ):
            while True:
                rate_wait_started = time.monotonic()
                self._wait_for_rate_slot(
                    config.cooldown_key,
                    config.policy.minimum_interval_seconds,
                    config.host_semaphore,
                )
                self._check_cancelled()
                attempt += 1
                request_started_at = time.monotonic()
                emit_structured_log(
                    logger,
                    logging.DEBUG,
                    "http_request_start",
                    method=config.method.upper(),
                    url=redacted_url,
                    status="attempt",
                    elapsed_ms=0.0,
                    rate_limit_wait_ms=round(
                        (request_started_at - rate_wait_started) * 1000, 3
                    ),
                    attempt=attempt,
                )

                response: Any = None
                response_reusable = False
                try:
                    try:
                        pool_result = self._dispatch_pool_request(
                            config.prepared, timeout=config.timeout
                        )
                    except _NETWORK_RETRY_EXCEPTIONS as exc:
                        self._handle_network_exception(
                            exc,
                            config=config,
                            retry_state=retry_state,
                            started_at=request_started_at,
                            attempt=attempt,
                        )
                        continue
                    except (BadStatusLine, InvalidURL) as exc:
                        raise RequestFailure(
                            None,
                            f"Network error for {redacted_url}: {exc}",
                            url=redacted_url,
                            error_category=RequestErrorCategory.UNKNOWN,
                            retryable=False,
                        ) from exc

                    response = pool_result.response
                    response_url = pool_result.final_url or config.url
                    headers_map = {
                        str(key).lower(): str(value)
                        for key, value in response.headers.items()
                    }
                    status_code = int(response.status)

                    if status_code >= 400:
                        try:
                            if error_body_mode == "bounded":
                                error_body = read_bounded_response_body(
                                    response,
                                    status_code=status_code,
                                    url=response_url,
                                    content_encoding=headers_map.get(
                                        "content-encoding"
                                    ),
                                    max_response_bytes=config.response_limit,
                                    max_compressed_response_bytes=config.compressed_response_limit,
                                    read_body=partial(
                                        self._read_response_body,
                                        response,
                                        timeout=config.timeout,
                                    ),
                                )
                                self._release_response(response)
                            else:
                                error_body = self._read_response_body(
                                    response,
                                    STREAM_PREVIEW_BYTES,
                                    timeout=config.timeout,
                                )
                                self._close_response(response)
                        except _NETWORK_RETRY_EXCEPTIONS:
                            error_body = b""
                            self._close_response(response)
                        response = None
                        decision = retry_state.decide_http_failure(
                            method=config.method,
                            request_url=config.url,
                            error_url=response_url,
                            status_code=status_code,
                            body=error_body,
                            headers_map=headers_map,
                            started_at=request_started_at,
                            attempt=attempt,
                        )
                        self._apply_retry_decision(
                            decision,
                            cooldown_key=config.cooldown_key,
                            host_semaphore=config.host_semaphore,
                        )
                        continue

                    try:
                        result = on_success(
                            _AttemptSuccessContext(
                                pool_result=pool_result,
                                response_url=response_url,
                                headers_map=headers_map,
                                status_code=status_code,
                                attempt=attempt,
                                started_at=request_started_at,
                            )
                        )
                        response_reusable = True
                        return result
                    except _NETWORK_RETRY_EXCEPTIONS as exc:
                        if not retry_body_errors:
                            if isinstance(exc, OSError) and not isinstance(
                                exc,
                                ConnectionError | TimeoutError | urllib.error.URLError,
                            ):
                                # Streaming can also fail while writing the staging file.
                                raise
                            raise RequestFailure(
                                None,
                                f"Network error for {redacted_url}: {build_network_error_detail(exc)}",
                                url=redacted_url,
                                error_category=classify_network_error(exc),
                                retryable=config.method.upper() in RETRYABLE_METHODS
                                and is_retryable_network_error(exc),
                            ) from exc
                        self._close_response(response)
                        response = None
                        self._handle_network_exception(
                            exc,
                            config=config,
                            retry_state=retry_state,
                            started_at=request_started_at,
                            attempt=attempt,
                        )
                        continue
                finally:
                    if response is not None:
                        if response_reusable:
                            self._release_response(response)
                        else:
                            self._close_response(response)

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, str] | None = None,
        timeout: float | None = None,
        retry_on_rate_limit: bool | None = None,
        rate_limit_retries: int | None = None,
        max_rate_limit_wait_seconds: int | None = None,
        retry_on_transient: bool | None = None,
        transient_retries: int | None = None,
        request_policy: HttpRequestPolicy | None = None,
    ) -> dict[str, Any]:
        config = self._normalize_request_config(
            method=method,
            url=url,
            headers=headers,
            query=query,
            timeout=timeout,
            retry_on_rate_limit=retry_on_rate_limit,
            rate_limit_retries=rate_limit_retries,
            max_rate_limit_wait_seconds=max_rate_limit_wait_seconds,
            retry_on_transient=retry_on_transient,
            transient_retries=transient_retries,
            request_policy=request_policy,
        )
        cache_key = self._response_cache.build_key(
            config.method, config.url, config.headers
        )
        cached_response = self._response_cache.load(cache_key)
        if cached_response is not None:
            self._enforce_response_limit(
                cached_response,
                max_response_bytes=config.response_limit,
                url=str(cached_response.get("url") or config.url),
            )
            return cached_response
        self._check_cancelled()

        def consume_buffered(ctx: _AttemptSuccessContext) -> dict[str, Any]:
            response = ctx.pool_result.response
            payload = read_bounded_response_body(
                response,
                status_code=ctx.status_code,
                url=ctx.response_url,
                content_encoding=ctx.headers_map.get("content-encoding"),
                max_response_bytes=config.response_limit,
                max_compressed_response_bytes=config.compressed_response_limit,
                read_body=lambda limit: self._read_response_body(
                    response, limit, timeout=config.timeout
                ),
            )
            set_cookie_values = list(_header_values(response.headers, "set-cookie"))
            response_payload: dict[str, Any] = {
                "status_code": ctx.status_code,
                "headers": ctx.headers_map,
                "body": payload,
                "url": redact_url_for_cache(ctx.response_url),
            }
            emit_structured_log(
                logger,
                logging.DEBUG,
                "http_request_success",
                method=config.method.upper(),
                url=response_payload["url"],
                status=ctx.status_code,
                elapsed_ms=round((time.monotonic() - ctx.started_at) * 1000, 3),
                attempt=ctx.attempt,
            )
            self._response_cache.store(cache_key, response_payload)
            if set_cookie_values:
                response_payload["_paper_fetch_header_values"] = {
                    "set-cookie": set_cookie_values
                }
            return response_payload

        return self._execute_scheduled_request(
            config,
            error_body_mode="bounded",
            retry_body_errors=True,
            on_success=consume_buffered,
        )

    def stream_to_file(
        self,
        method: str,
        url: str,
        destination: Path,
        *,
        headers: Mapping[str, str] | None = None,
        options: HttpStreamOptions,
    ) -> dict[str, Any]:
        """Stream one policy-validated response into an already unique path."""

        config = self._normalize_request_config(
            method=method,
            url=url,
            headers=headers,
            timeout=options.timeout,
            retry_on_rate_limit=options.retry_on_rate_limit,
            rate_limit_retries=options.rate_limit_retries,
            max_rate_limit_wait_seconds=options.max_rate_limit_wait_seconds,
            retry_on_transient=options.retry_on_transient,
            transient_retries=options.transient_retries,
            request_policy=options.request_policy,
            response_headers_observer=options.on_response_headers,
            request_headers_provider=options.request_headers_provider,
        )

        def consume_stream(ctx: _AttemptSuccessContext) -> dict[str, Any]:
            response = ctx.pool_result.response
            stats = stream_bounded_response_to_file(
                destination,
                request_url=config.url,
                response_url=ctx.response_url,
                status_code=ctx.status_code,
                headers_map=ctx.headers_map,
                response_limit=config.response_limit,
                compressed_limit=config.stream_compressed_limit,
                read_chunk=lambda limit: self._read_response_chunk(
                    response, limit, timeout=config.timeout
                ),
                on_content_length=options.on_content_length,
                on_chunk=options.on_chunk,
            )
            return {
                "status_code": ctx.status_code,
                "headers": ctx.headers_map,
                "url": redact_url_for_cache(ctx.response_url),
                "staging_path": str(destination),
                "downloaded_bytes": stats.downloaded_bytes,
                "body_preview": stats.body_preview,
                "compressed_bytes": stats.compressed_bytes,
                "_paper_fetch_timing_seconds": {
                    **ctx.pool_result.timing_seconds,
                    "body_stream": stats.elapsed_seconds,
                },
                "_paper_fetch_header_values": {
                    "set-cookie": list(_header_values(response.headers, "set-cookie"))
                },
            }

        return self._execute_scheduled_request(
            config,
            error_body_mode="preview",
            retry_body_errors=False,
            on_success=consume_stream,
        )


__all__ = [
    "DEFAULT_FULLTEXT_TIMEOUT_SECONDS",
    "DEFAULT_MAX_REDIRECTS",
    "DEFAULT_PER_HOST_CONCURRENCY",
    "DEFAULT_POOL_MAXSIZE",
    "DEFAULT_POOL_NUM_POOLS",
    "DEFAULT_TIMEOUT_SECONDS",
    "HttpRequestPolicy",
    "HttpStreamOptions",
    "HttpTransport",
    "HttpTransportOptions",
    "_PoolCallResult",
    "_PreparedRequest",
    "logger",
    "request_cancel_check",
    "request_timeout_limit",
]
