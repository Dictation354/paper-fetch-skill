"""Runtime dependency container for service and adapter entrypoints."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import threading
import time
from collections.abc import Callable, Hashable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from .asset_budget import AssetBudget
from .artifacts import DEFAULT_ARTIFACT_MODE, ArtifactMode, ArtifactStore
from .config import (
    HTTP_PER_HOST_CONCURRENCY_ENV_VAR,
    HTTP_POOL_MAXSIZE_ENV_VAR,
    HTTP_POOL_NUM_POOLS_ENV_VAR,
    build_runtime_env,
    parse_positive_int_env,
)
from .http import (
    DEFAULT_PER_HOST_CONCURRENCY,
    DEFAULT_POOL_MAXSIZE,
    DEFAULT_POOL_NUM_POOLS,
    HttpTransport,
    RequestCancelledError,
)

RUNTIME_UNSET = object()
_PARSE_CACHE_MISSING = object()
_SESSION_CACHE_MISSING = object()


def build_http_transport_for_context(
    env: Mapping[str, str],
    *,
    download_dir: Path | None,
    cancel_check: Callable[[], bool] | None,
    artifact_mode: ArtifactMode = DEFAULT_ARTIFACT_MODE,
) -> HttpTransport:
    from .http import HttpTransportOptions

    return HttpTransport(
        pool_num_pools=parse_positive_int_env(
            env, HTTP_POOL_NUM_POOLS_ENV_VAR, default=DEFAULT_POOL_NUM_POOLS
        ),
        pool_maxsize=parse_positive_int_env(
            env, HTTP_POOL_MAXSIZE_ENV_VAR, default=DEFAULT_POOL_MAXSIZE
        ),
        per_host_concurrency=parse_positive_int_env(
            env,
            HTTP_PER_HOST_CONCURRENCY_ENV_VAR,
            default=DEFAULT_PER_HOST_CONCURRENCY,
        ),
        options=HttpTransportOptions(cancel_check=cancel_check),
    )


@dataclass(slots=True)
class RuntimeCommitGuard:
    """Linearizable cancellation fence for final filesystem commits."""

    cancel_check: Callable[[], bool] | None = None
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    _fenced: bool = field(default=False, init=False, repr=False)

    def _raise_if_cancelled_unlocked(self) -> None:
        if self._fenced or bool(self.cancel_check is not None and self.cancel_check()):
            raise RequestCancelledError("Request cancelled.")

    def __call__(self) -> None:
        with self._lock:
            self._raise_if_cancelled_unlocked()

    @contextlib.contextmanager
    def critical_section(self) -> Iterator[None]:
        """Check and hold the fence lock across the final atomic replace."""

        with self._lock:
            self._raise_if_cancelled_unlocked()
            yield

    def fence(self) -> None:
        """Wait for an active commit to linearize, then reject every later one."""

        with self._lock:
            self._fenced = True

    @property
    def cancelled(self) -> bool:
        with self._lock:
            return self._fenced or bool(
                self.cancel_check is not None and self.cancel_check()
            )


@dataclass
class RuntimeContext:
    """Holds runtime dependencies shared across service, workflow, and adapters."""

    env: Mapping[str, str] | None = None
    transport: HttpTransport | None = None
    clients: Mapping[str, object] | None = None
    download_dir: Path | None = None
    artifact_mode: ArtifactMode = DEFAULT_ARTIFACT_MODE
    asset_profile: str | None = None
    asset_budget: AssetBudget | None = None
    cancel_check: Callable[[], bool] | None = None
    artifact_store: ArtifactStore | None = None
    fetch_cache: Any | None = None
    parse_cache: dict[tuple[Hashable, ...], Any] = field(default_factory=dict)
    session_cache: dict[tuple[Hashable, ...], Any] = field(default_factory=dict)
    fetch_trace: list[Any] = field(default_factory=list)
    diagnostic_artifacts: list[dict[str, Any]] = field(default_factory=list)
    capability_uses: list[dict[str, Any]] = field(default_factory=list)
    request_started_at: float = field(default_factory=time.monotonic)
    deadline_monotonic: float | None = None
    _parse_cache_lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False
    )
    _parse_cache_inflight: dict[tuple[Hashable, ...], threading.Event] = field(
        default_factory=dict, init=False, repr=False
    )
    _session_cache_lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False
    )
    _capability_uses_lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False
    )
    _clients_lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False
    )
    _browser_context_manager_lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False
    )
    _camoufox_browser_managers: dict[tuple[int, bool, str], Any] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _owns_transport: bool = field(default=False, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)
    _commit_guard: RuntimeCommitGuard = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._owns_transport = self.transport is None
        self.env = build_runtime_env() if self.env is None else dict(self.env)
        self._commit_guard = RuntimeCommitGuard(self.cancel_check)
        if self.asset_budget is None:
            self.asset_budget = AssetBudget(cancel_check=self.cancel_check)
        if self.artifact_store is None:
            self.artifact_store = ArtifactStore.from_download_dir(
                self.download_dir,
                artifact_mode=self.artifact_mode,
                commit_guard=self._commit_guard,
            )
        else:
            self.artifact_mode = self.artifact_store.artifact_mode
            if self.download_dir is None:
                self.download_dir = self.artifact_store.download_dir
            self.artifact_store.default_commit_guard = self._commit_guard
        if self.transport is None:
            self.transport = build_http_transport_for_context(
                self.env,
                download_dir=self.download_dir,
                cancel_check=self.cancel_check,
                artifact_mode=self.artifact_mode,
            )

    def get_clients(self) -> Mapping[str, object]:
        with self._clients_lock:
            if self.clients is None:
                from .providers.registry import build_clients

                assert self.transport is not None
                assert self.env is not None
                self.clients = build_clients(self.transport, self.env)
            return self.clients

    def new_request_context(
        self,
        *,
        download_dir: Path | None | object = RUNTIME_UNSET,
        artifact_mode: ArtifactMode | object = RUNTIME_UNSET,
        asset_profile: str | None = None,
        cancel_check: Callable[[], bool] | None | object = RUNTIME_UNSET,
    ) -> RuntimeContext:
        """Create an item-local context while reusing the shared HTTP transport.

        Request-mutated fields, parser/session caches, artifact policy, and
        browser leases stay local to the child. The transport (and therefore its
        connection pools, per-host semaphores, and HTTP caches) is intentionally
        shared across batch items.
        """

        resolved_download_dir = (
            self.download_dir
            if download_dir is RUNTIME_UNSET
            else cast(Path | None, download_dir)
        )
        resolved_artifact_mode = (
            self.artifact_mode
            if artifact_mode is RUNTIME_UNSET
            else cast(ArtifactMode, artifact_mode)
        )
        resolved_cancel_check = (
            self.cancel_check
            if cancel_check is RUNTIME_UNSET
            else cast(Callable[[], bool] | None, cancel_check)
        )
        return RuntimeContext(
            env=self.env,
            transport=self.transport,
            download_dir=resolved_download_dir,
            artifact_mode=resolved_artifact_mode,
            asset_profile=asset_profile,
            cancel_check=resolved_cancel_check,
        )

    @property
    def cancelled(self) -> bool:
        return self._commit_guard.cancelled

    @property
    def commit_guard(self) -> RuntimeCommitGuard:
        return self._commit_guard

    def fence_commits(self) -> None:
        """Permanently reject commits from this request after cancellation."""

        self._commit_guard.fence()

    def raise_if_cancelled(self) -> None:
        """Fence a commit or expensive stage against cooperative cancellation."""

        self._commit_guard()

    def record_browser_state_capability_use(
        self,
        *,
        provider: str,
        backend: str,
        storage_state_path: Path | str,
        content_sha256: str | None = None,
    ) -> None:
        """Record state only after it was successfully injected into a context."""

        from .capability_scope import BrowserStateCapabilityUse

        use = BrowserStateCapabilityUse.from_path(
            provider=provider,
            backend=backend,
            storage_state_path=storage_state_path,
        )
        record = {
            "provider": use.provider,
            "backend": use.backend,
            "storage_state_path": use.storage_state_path,
            "content_sha256": (str(content_sha256 or "").strip() or use.content_sha256),
            "used": True,
        }
        with self._capability_uses_lock:
            if record not in self.capability_uses:
                self.capability_uses.append(record)

    def browser_state_capability_uses(self) -> tuple[dict[str, Any], ...]:
        with self._capability_uses_lock:
            return tuple(copy.deepcopy(self.capability_uses))

    def initialize_deadline(self, timeout_seconds: float) -> float:
        """Initialize the request deadline once from the request start time."""

        if self.deadline_monotonic is None:
            timeout_value = max(0.0, float(timeout_seconds))
            self.deadline_monotonic = self.request_started_at + timeout_value
        return self.deadline_monotonic

    def reset_request_deadline(self) -> None:
        """Start a fresh request budget while preserving item-local cached state.

        Batch schedulers may create a context early so resolution can prime its
        session cache.  Resolution and lane-queue time are not part of the later
        fetch attempt, so the worker resets only the request clock immediately
        before fetching.
        """

        self.request_started_at = time.monotonic()
        self.deadline_monotonic = None

    def remaining_seconds(self, maximum: float | None = None) -> float:
        """Return remaining request budget, optionally capped for one operation."""

        self.raise_if_cancelled()
        if self.deadline_monotonic is None:
            if maximum is None:
                return float("inf")
            return max(0.0, float(maximum))
        remaining = max(0.0, self.deadline_monotonic - time.monotonic())
        if maximum is not None:
            remaining = min(remaining, max(0.0, float(maximum)))
        return remaining

    def remaining_timeout_ms(
        self,
        maximum_ms: int,
        *,
        minimum_ms: int = 1,
    ) -> int:
        remaining = self.remaining_seconds(maximum_ms / 1000.0)
        if remaining <= 0:
            raise TimeoutError("Request deadline exceeded.")
        return max(minimum_ms, min(maximum_ms, int(remaining * 1000)))

    def new_browser_context_for_runtime_config(
        self,
        config: Any,
        **context_kwargs: Any,
    ) -> Any:
        """Create a fresh context using the backend carried by runtime config."""

        key = (
            threading.get_ident(),
            bool(config.headless),
            str(config.binary_path or "").strip(),
        )
        with self._browser_context_manager_lock:
            manager = self._camoufox_browser_managers.get(key)
            if manager is None:
                from .providers.browser_runtime.camoufox_manager import (
                    CamoufoxBrowserManager,
                )

                manager = CamoufoxBrowserManager(
                    binary_path=config.binary_path,
                    headless=config.headless,
                )
                self._camoufox_browser_managers[key] = manager
        return manager.new_context(**context_kwargs)

    def close_browser(self) -> None:
        """Close Camoufox managers owned by this runtime context."""

        with self._browser_context_manager_lock:
            camoufox_managers = list(self._camoufox_browser_managers.values())
            self._camoufox_browser_managers.clear()
        seen: set[int] = set()
        for camoufox_manager in camoufox_managers:
            if id(camoufox_manager) in seen:
                continue
            seen.add(id(camoufox_manager))
            camoufox_manager.close()

    def close_camoufox_for_current_thread(self) -> None:
        """Close Camoufox managers while still on their owning worker thread."""

        owner_thread_id = threading.get_ident()
        with self._browser_context_manager_lock:
            owned_items = [
                (key, manager)
                for key, manager in self._camoufox_browser_managers.items()
                if key[0] == owner_thread_id
            ]
            for key, _manager in owned_items:
                self._camoufox_browser_managers.pop(key, None)
        seen: set[int] = set()
        for _key, manager in owned_items:
            if id(manager) in seen:
                continue
            seen.add(id(manager))
            manager.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        session_values = list(self.session_cache.values())
        self.session_cache.clear()
        seen: set[int] = set()
        for value in session_values:
            close = getattr(value, "close", None)
            if not callable(close) or id(value) in seen:
                continue
            seen.add(id(value))
            with contextlib.suppress(Exception):
                close()
        self.close_browser()
        if self._owns_transport and self.transport is not None:
            close_transport = getattr(self.transport, "close", None)
            if callable(close_transport):
                with contextlib.suppress(Exception):
                    close_transport()

    def __enter__(self) -> RuntimeContext:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        del exc_type, exc, traceback
        self.close()

    def __del__(
        self,
    ) -> None:  # pragma: no cover - defensive cleanup at GC/interpreter shutdown
        with contextlib.suppress(Exception):
            self.close_browser()

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

    def get_or_set_parse_cache(
        self,
        key: tuple[Hashable, ...],
        factory: Callable[[], Any],
        *,
        copy_value: bool = True,
    ) -> Any:
        """Atomically memoize parser output for a single cache key."""

        while True:
            with self._parse_cache_lock:
                cached = self.parse_cache.get(key, _PARSE_CACHE_MISSING)
                if cached is not _PARSE_CACHE_MISSING:
                    return copy.deepcopy(cached) if copy_value else cached
                inflight = self._parse_cache_inflight.get(key)
                if inflight is None:
                    inflight = threading.Event()
                    self._parse_cache_inflight[key] = inflight
                    break
            inflight.wait()

        try:
            value = factory()
            stored = copy.deepcopy(value) if copy_value else value
            with self._parse_cache_lock:
                self.parse_cache[key] = stored
            return copy.deepcopy(stored) if copy_value else stored
        finally:
            with self._parse_cache_lock:
                completed = self._parse_cache_inflight.pop(key, None)
                if completed is not None:
                    completed.set()

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
        """Atomically create fetch-session state without leaking it across papers."""

        with self._session_cache_lock:
            value = self.session_cache.get(key, _SESSION_CACHE_MISSING)
            if value is _SESSION_CACHE_MISSING:
                created = factory()
                value = copy.deepcopy(created) if copy_value else created
                self.session_cache[key] = value
            return copy.deepcopy(value) if copy_value else value


def resolve_runtime_context(
    context: RuntimeContext | None = None,
    *,
    env: Mapping[str, str] | None | object = RUNTIME_UNSET,
    transport: HttpTransport | None | object = RUNTIME_UNSET,
    clients: Mapping[str, object] | None | object = RUNTIME_UNSET,
    download_dir: Path | None | object = RUNTIME_UNSET,
    cancel_check: Callable[[], bool] | None | object = RUNTIME_UNSET,
    artifact_store: ArtifactStore | None | object = RUNTIME_UNSET,
    artifact_mode: ArtifactMode | object = RUNTIME_UNSET,
    fetch_cache: Any | object = RUNTIME_UNSET,
    parse_cache: dict[tuple[Hashable, ...], Any] | object = RUNTIME_UNSET,
    session_cache: dict[tuple[Hashable, ...], Any] | object = RUNTIME_UNSET,
) -> RuntimeContext:
    """Return an explicit context or build one from internal runtime parts."""

    runtime_parts = {
        "env": env,
        "transport": transport,
        "clients": clients,
        "download_dir": download_dir,
        "cancel_check": cancel_check,
        "artifact_store": artifact_store,
        "artifact_mode": artifact_mode,
        "fetch_cache": fetch_cache,
        "parse_cache": parse_cache,
        "session_cache": session_cache,
    }
    if context is not None:
        explicit = [
            name for name, value in runtime_parts.items() if value is not RUNTIME_UNSET
        ]
        if explicit:
            joined = ", ".join(explicit)
            raise TypeError(
                f"RuntimeContext cannot be combined with runtime keyword arguments: {joined}"
            )
        return context

    resolved_env = None if env is RUNTIME_UNSET else cast(Mapping[str, str] | None, env)
    resolved_transport = (
        None if transport is RUNTIME_UNSET else cast(HttpTransport | None, transport)
    )
    resolved_clients = (
        None if clients is RUNTIME_UNSET else cast(Mapping[str, object] | None, clients)
    )
    resolved_download_dir = (
        None if download_dir is RUNTIME_UNSET else cast(Path | None, download_dir)
    )
    resolved_cancel_check = (
        None
        if cancel_check is RUNTIME_UNSET
        else cast(Callable[[], bool] | None, cancel_check)
    )
    resolved_artifact_store = (
        None
        if artifact_store is RUNTIME_UNSET
        else cast(ArtifactStore | None, artifact_store)
    )
    resolved_artifact_mode = (
        DEFAULT_ARTIFACT_MODE
        if artifact_mode is RUNTIME_UNSET
        else cast(ArtifactMode, artifact_mode)
    )
    resolved_parse_cache = (
        {}
        if parse_cache is RUNTIME_UNSET
        else cast(dict[tuple[Hashable, ...], Any], parse_cache)
    )
    resolved_session_cache = (
        {}
        if session_cache is RUNTIME_UNSET
        else cast(dict[tuple[Hashable, ...], Any], session_cache)
    )
    return RuntimeContext(
        env=resolved_env,
        transport=resolved_transport,
        clients=resolved_clients,
        download_dir=resolved_download_dir,
        cancel_check=resolved_cancel_check,
        artifact_store=resolved_artifact_store,
        artifact_mode=resolved_artifact_mode,
        fetch_cache=None if fetch_cache is RUNTIME_UNSET else fetch_cache,
        parse_cache=resolved_parse_cache,
        session_cache=resolved_session_cache,
    )
