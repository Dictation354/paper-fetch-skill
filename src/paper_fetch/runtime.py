"""Runtime dependency container for service and adapter entrypoints."""

from __future__ import annotations

import copy
import hashlib
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Hashable, Mapping

from .artifacts import ArtifactStore
from .config import (
    HTTP_DISK_CACHE_DIR_ENV_VAR,
    HTTP_DISK_CACHE_ENV_VAR,
    HTTP_METADATA_CACHE_TTL_ENV_VAR,
    HTTP_PER_HOST_CONCURRENCY_ENV_VAR,
    HTTP_POOL_MAXSIZE_ENV_VAR,
    HTTP_POOL_NUM_POOLS_ENV_VAR,
    build_runtime_env,
    env_flag_enabled,
    parse_nonnegative_int_env,
    parse_positive_int_env,
    resolve_user_data_dir,
)
from .http import (
    DEFAULT_METADATA_CACHE_TTL_SECONDS,
    DEFAULT_PER_HOST_CONCURRENCY,
    DEFAULT_POOL_MAXSIZE,
    DEFAULT_POOL_NUM_POOLS,
    HttpTransport,
)

RUNTIME_UNSET = object()
_PARSE_CACHE_MISSING = object()
_SESSION_CACHE_MISSING = object()


def _transport_disk_cache_dir(env: Mapping[str, str], download_dir: Path | None) -> Path | None:
    configured = str(env.get(HTTP_DISK_CACHE_DIR_ENV_VAR, "")).strip()
    if configured:
        return Path(configured).expanduser()
    if download_dir is not None:
        return download_dir / ".paper-fetch-http-cache"
    if env_flag_enabled(env, HTTP_DISK_CACHE_ENV_VAR):
        return resolve_user_data_dir(env) / "http-cache"
    return None


def build_http_transport_for_context(
    env: Mapping[str, str],
    *,
    download_dir: Path | None,
    cancel_check: Callable[[], bool] | None,
) -> HttpTransport:
    metadata_cache_ttl = parse_nonnegative_int_env(
        env,
        HTTP_METADATA_CACHE_TTL_ENV_VAR,
        default=DEFAULT_METADATA_CACHE_TTL_SECONDS,
    )
    return HttpTransport(
        pool_num_pools=parse_positive_int_env(env, HTTP_POOL_NUM_POOLS_ENV_VAR, default=DEFAULT_POOL_NUM_POOLS),
        pool_maxsize=parse_positive_int_env(env, HTTP_POOL_MAXSIZE_ENV_VAR, default=DEFAULT_POOL_MAXSIZE),
        per_host_concurrency=parse_positive_int_env(
            env,
            HTTP_PER_HOST_CONCURRENCY_ENV_VAR,
            default=DEFAULT_PER_HOST_CONCURRENCY,
        ),
        metadata_cache_ttl=metadata_cache_ttl,
        disk_cache_dir=_transport_disk_cache_dir(env, download_dir),
        cancel_check=cancel_check,
    )


@dataclass
class RuntimeContext:
    """Holds runtime dependencies shared across service, workflow, and adapters."""

    env: Mapping[str, str] | None = None
    transport: HttpTransport | None = None
    clients: Mapping[str, object] | None = None
    download_dir: Path | None = None
    cancel_check: Callable[[], bool] | None = None
    artifact_store: ArtifactStore | None = None
    fetch_cache: Any | None = None
    parse_cache: dict[tuple[Hashable, ...], Any] = field(default_factory=dict)
    session_cache: dict[tuple[Hashable, ...], Any] = field(default_factory=dict)
    stage_timings: dict[str, float] = field(default_factory=dict)
    _session_cache_lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    _stage_timing_lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    _playwright_lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    _playwright_manager: Any | None = field(default=None, init=False, repr=False)
    _playwright_browser: Any | None = field(default=None, init=False, repr=False)
    _playwright_headless: bool | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.env = build_runtime_env() if self.env is None else dict(self.env)
        if self.transport is None:
            self.transport = build_http_transport_for_context(
                self.env,
                download_dir=self.download_dir,
                cancel_check=self.cancel_check,
            )
        if self.artifact_store is None:
            self.artifact_store = ArtifactStore.from_download_dir(self.download_dir)
        elif self.download_dir is None:
            self.download_dir = self.artifact_store.download_dir
        self.stage_timings.setdefault("asset_seconds", 0.0)
        self.stage_timings.setdefault("formula_seconds", 0.0)

    def get_clients(self) -> Mapping[str, object]:
        if self.clients is None:
            from .providers.registry import build_clients

            assert self.transport is not None
            assert self.env is not None
            self.clients = build_clients(self.transport, self.env)
        return self.clients

    def playwright_browser(self, *, headless: bool = True) -> Any:
        """Return a lazily started shared Playwright Chromium browser."""

        active_headless = bool(headless)
        with self._playwright_lock:
            if self._playwright_browser is not None and self._playwright_headless == active_headless:
                return self._playwright_browser
            if self._playwright_browser is not None or self._playwright_manager is not None:
                self.close_playwright()

            from playwright.sync_api import sync_playwright

            manager = sync_playwright().start()
            try:
                browser = manager.chromium.launch(headless=active_headless)
            except Exception:
                try:
                    manager.stop()
                finally:
                    pass
                raise
            self._playwright_manager = manager
            self._playwright_browser = browser
            self._playwright_headless = active_headless
            return browser

    def new_playwright_context(self, *, headless: bool = True, **context_kwargs: Any) -> Any:
        """Create an isolated browser context from the shared Playwright browser."""

        with self._playwright_lock:
            browser = self.playwright_browser(headless=headless)
            return browser.new_context(**context_kwargs)

    def close_playwright(self) -> None:
        """Close any Playwright browser/manager owned by this runtime context."""

        with self._playwright_lock:
            browser = self._playwright_browser
            manager = self._playwright_manager
            self._playwright_browser = None
            self._playwright_manager = None
            self._playwright_headless = None
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
            if manager is not None:
                try:
                    manager.stop()
                except Exception:
                    pass

    def close(self) -> None:
        self.close_playwright()

    def __del__(self) -> None:  # pragma: no cover - defensive cleanup at GC/interpreter shutdown
        try:
            self.close_playwright()
        except Exception:
            pass

    def build_parse_cache_key(
        self,
        *,
        provider: str,
        role: str,
        source: str | None,
        body: bytes | bytearray | str | None,
        parser: str,
        config: Mapping[str, Any] | None = None,
    ) -> tuple[Hashable, ...]:
        """Build a stable key for per-fetch parser/extraction memoization."""

        if isinstance(body, str):
            body_bytes = body.encode("utf-8", errors="replace")
        elif isinstance(body, (bytes, bytearray)):
            body_bytes = bytes(body)
        else:
            body_bytes = b""
        body_digest = hashlib.sha256(body_bytes).hexdigest()
        normalized_config = tuple(
            sorted((str(key), repr(value)) for key, value in (config or {}).items())
        )
        return (
            "parse",
            str(provider or ""),
            str(role or ""),
            str(source or ""),
            body_digest,
            str(parser or ""),
            normalized_config,
        )

    def get_parse_cache(
        self,
        key: tuple[Hashable, ...],
        *,
        copy_value: bool = True,
        default: Any = _PARSE_CACHE_MISSING,
    ) -> Any:
        value = self.parse_cache.get(key, _PARSE_CACHE_MISSING)
        if value is _PARSE_CACHE_MISSING:
            if default is _PARSE_CACHE_MISSING:
                return None
            return default
        return copy.deepcopy(value) if copy_value else value

    def set_parse_cache(
        self,
        key: tuple[Hashable, ...],
        value: Any,
        *,
        copy_value: bool = True,
    ) -> Any:
        self.parse_cache[key] = copy.deepcopy(value) if copy_value else value
        return copy.deepcopy(value) if copy_value else value

    def get_or_set_parse_cache(
        self,
        key: tuple[Hashable, ...],
        factory: Callable[[], Any],
        *,
        copy_value: bool = True,
    ) -> Any:
        cached = self.parse_cache.get(key, _PARSE_CACHE_MISSING)
        if cached is not _PARSE_CACHE_MISSING:
            return copy.deepcopy(cached) if copy_value else cached
        value = factory()
        return self.set_parse_cache(key, value, copy_value=copy_value)

    def get_session_cache(
        self,
        key: tuple[Hashable, ...],
        *,
        copy_value: bool = True,
        default: Any = _SESSION_CACHE_MISSING,
    ) -> Any:
        with self._session_cache_lock:
            value = self.session_cache.get(key, _SESSION_CACHE_MISSING)
            if value is _SESSION_CACHE_MISSING:
                if default is _SESSION_CACHE_MISSING:
                    return None
                return default
            return copy.deepcopy(value) if copy_value else value

    def set_session_cache(
        self,
        key: tuple[Hashable, ...],
        value: Any,
        *,
        copy_value: bool = True,
    ) -> Any:
        stored = copy.deepcopy(value) if copy_value else value
        with self._session_cache_lock:
            self.session_cache[key] = stored
        return copy.deepcopy(stored) if copy_value else stored

    def get_or_set_session_cache(
        self,
        key: tuple[Hashable, ...],
        factory: Callable[[], Any],
        *,
        copy_value: bool = True,
    ) -> Any:
        with self._session_cache_lock:
            cached = self.session_cache.get(key, _SESSION_CACHE_MISSING)
            if cached is not _SESSION_CACHE_MISSING:
                return copy.deepcopy(cached) if copy_value else cached
        value = factory()
        return self.set_session_cache(key, value, copy_value=copy_value)

    def record_stage_timing(self, name: str, started_at: float) -> float:
        """Record a non-cumulative stage duration in seconds."""

        elapsed = max(0.0, time.monotonic() - started_at)
        rounded = round(elapsed, 3)
        with self._stage_timing_lock:
            self.stage_timings[str(name)] = rounded
        return rounded

    def accumulate_stage_timing(
        self,
        name: str,
        *,
        started_at: float | None = None,
        elapsed: float | None = None,
    ) -> float:
        """Add elapsed seconds to a cumulative stage timing key."""

        if elapsed is None:
            if started_at is None:
                raise ValueError("started_at or elapsed is required")
            elapsed = time.monotonic() - started_at
        elapsed = max(0.0, float(elapsed))
        with self._stage_timing_lock:
            current = self.stage_timings.get(str(name), 0.0)
            try:
                current_value = float(current)
            except (TypeError, ValueError):
                current_value = 0.0
            updated = round(max(0.0, current_value + elapsed), 6)
            self.stage_timings[str(name)] = updated
            return updated


def resolve_runtime_context(
    context: RuntimeContext | None = None,
    *,
    env: Mapping[str, str] | None | object = RUNTIME_UNSET,
    transport: HttpTransport | None | object = RUNTIME_UNSET,
    clients: Mapping[str, object] | None | object = RUNTIME_UNSET,
    download_dir: Path | None | object = RUNTIME_UNSET,
    cancel_check: Callable[[], bool] | None | object = RUNTIME_UNSET,
    artifact_store: ArtifactStore | None | object = RUNTIME_UNSET,
    fetch_cache: Any | object = RUNTIME_UNSET,
    parse_cache: dict[tuple[Hashable, ...], Any] | object = RUNTIME_UNSET,
    session_cache: dict[tuple[Hashable, ...], Any] | object = RUNTIME_UNSET,
    stage_timings: dict[str, float] | object = RUNTIME_UNSET,
) -> RuntimeContext:
    """Merge explicit legacy keyword arguments over an optional context."""

    if (
        context is not None
        and env is RUNTIME_UNSET
        and transport is RUNTIME_UNSET
        and clients is RUNTIME_UNSET
        and download_dir is RUNTIME_UNSET
        and cancel_check is RUNTIME_UNSET
        and artifact_store is RUNTIME_UNSET
        and fetch_cache is RUNTIME_UNSET
        and parse_cache is RUNTIME_UNSET
        and session_cache is RUNTIME_UNSET
        and stage_timings is RUNTIME_UNSET
    ):
        return context

    active_env = context.env if context is not None and env is RUNTIME_UNSET else env
    active_transport = context.transport if context is not None and transport is RUNTIME_UNSET else transport
    active_clients = context.clients if context is not None and clients is RUNTIME_UNSET else clients
    active_cancel_check = context.cancel_check if context is not None and cancel_check is RUNTIME_UNSET else cancel_check
    active_download_dir = context.download_dir if context is not None and download_dir is RUNTIME_UNSET else download_dir
    if context is not None and artifact_store is RUNTIME_UNSET and download_dir is RUNTIME_UNSET:
        active_artifact_store = context.artifact_store
    else:
        active_artifact_store = artifact_store
    active_fetch_cache = context.fetch_cache if context is not None and fetch_cache is RUNTIME_UNSET else fetch_cache
    active_parse_cache = context.parse_cache if context is not None and parse_cache is RUNTIME_UNSET else parse_cache
    active_session_cache = context.session_cache if context is not None and session_cache is RUNTIME_UNSET else session_cache
    active_stage_timings = context.stage_timings if context is not None and stage_timings is RUNTIME_UNSET else stage_timings

    runtime = RuntimeContext(
        env=None if active_env is RUNTIME_UNSET else active_env,
        transport=None if active_transport is RUNTIME_UNSET else active_transport,
        clients=None if active_clients is RUNTIME_UNSET else active_clients,
        download_dir=None if active_download_dir is RUNTIME_UNSET else active_download_dir,
        cancel_check=None if active_cancel_check is RUNTIME_UNSET else active_cancel_check,
        artifact_store=None if active_artifact_store is RUNTIME_UNSET else active_artifact_store,
        fetch_cache=None if active_fetch_cache is RUNTIME_UNSET else active_fetch_cache,
        parse_cache={} if active_parse_cache is RUNTIME_UNSET else active_parse_cache,
        session_cache={} if active_session_cache is RUNTIME_UNSET else active_session_cache,
        stage_timings={} if active_stage_timings is RUNTIME_UNSET else active_stage_timings,
    )
    if context is not None and runtime.session_cache is context.session_cache:
        runtime._session_cache_lock = context._session_cache_lock
    if context is not None and runtime.stage_timings is context.stage_timings:
        runtime._stage_timing_lock = context._stage_timing_lock
    return runtime
