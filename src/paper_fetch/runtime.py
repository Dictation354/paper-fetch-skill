"""Runtime dependency container for service and adapter entrypoints."""

from __future__ import annotations

import atexit
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
    HTTP_DISK_CACHE_DIR_ENV_VAR,
    HTTP_DISK_CACHE_ENV_VAR,
    HTTP_DISK_CACHE_MAX_AGE_DAYS_ENV_VAR,
    HTTP_DISK_CACHE_MAX_BYTES_ENV_VAR,
    HTTP_DISK_CACHE_MAX_ENTRIES_ENV_VAR,
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
    DEFAULT_DISK_CACHE_MAX_AGE_DAYS,
    DEFAULT_DISK_CACHE_MAX_BYTES,
    DEFAULT_DISK_CACHE_MAX_ENTRIES,
    HttpTransport,
    RequestCancelledError,
)
from .runtime_browser import BrowserContextManager

RUNTIME_UNSET = object()
_PARSE_CACHE_MISSING = object()
_SESSION_CACHE_MISSING = object()
_SHARED_BROWSER_MANAGER_LOCK = threading.RLock()
_SHARED_BROWSER_BATCH_SCOPE_COUNT = 0
_SHARED_BROWSER_MANAGERS: dict[
    tuple[str, str, str, str, str], _SharedBrowserManagerEntry
] = {}


@dataclass
class _SharedBrowserManagerEntry:
    manager: Any
    ref_count: int = 0


class _SharedBrowserManagerLease:
    def __init__(self, key: tuple[str, str, str, str, str], manager: Any) -> None:
        self._key = key
        self._manager = manager
        self._closed = False

    def browser(self, *, headless: bool = True) -> Any:
        return self._manager.browser(headless=headless)

    def new_context(self, *, headless: bool = True, **context_kwargs: Any) -> Any:
        return self._manager.new_context(headless=headless, **context_kwargs)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        manager_to_close = None
        with _SHARED_BROWSER_MANAGER_LOCK:
            entry = _SHARED_BROWSER_MANAGERS.get(self._key)
            if entry is None or entry.manager is not self._manager:
                return
            entry.ref_count -= 1
            if entry.ref_count <= 0:
                entry.ref_count = 0
                if _SHARED_BROWSER_BATCH_SCOPE_COUNT <= 0:
                    _SHARED_BROWSER_MANAGERS.pop(self._key, None)
                    manager_to_close = entry.manager
        if manager_to_close is not None:
            manager_to_close.close()


def _acquire_shared_browser_manager(
    *,
    key: tuple[str, str, str, str, str],
    binary_path: str | None,
    cdp_endpoint: str | None,
    external_new_context: bool,
    profile_dir: Path | None,
    user_data_dir: Path | None,
) -> _SharedBrowserManagerLease:
    with _SHARED_BROWSER_MANAGER_LOCK:
        entry = _SHARED_BROWSER_MANAGERS.get(key)
        if entry is None:
            entry = _SharedBrowserManagerEntry(
                manager=BrowserContextManager(
                    binary_path=binary_path,
                    cdp_endpoint=cdp_endpoint,
                    external_new_context=external_new_context,
                    profile_dir=profile_dir,
                    user_data_dir=user_data_dir,
                )
            )
            _SHARED_BROWSER_MANAGERS[key] = entry
        entry.ref_count += 1
        return _SharedBrowserManagerLease(key, entry.manager)


def dump_shared_browser_managers() -> list[dict[str, Any]]:
    with _SHARED_BROWSER_MANAGER_LOCK:
        return [
            {
                "key": key,
                "ref_count": entry.ref_count,
                "manager_type": entry.manager.__class__.__name__,
                "external_cdp": bool(key[1]),
                "external_new_context": key[2] == "1",
                "retained_by_batch_scope": (
                    entry.ref_count == 0 and _SHARED_BROWSER_BATCH_SCOPE_COUNT > 0
                ),
            }
            for key, entry in _SHARED_BROWSER_MANAGERS.items()
        ]


def close_shared_browser_managers() -> None:
    with _SHARED_BROWSER_MANAGER_LOCK:
        entries = list(_SHARED_BROWSER_MANAGERS.values())
        _SHARED_BROWSER_MANAGERS.clear()
    for entry in entries:
        with contextlib.suppress(Exception):
            entry.manager.close()


@contextlib.contextmanager
def retain_shared_browser_managers():
    """Keep idle shared browser managers alive for one overlapping batch scope."""

    global _SHARED_BROWSER_BATCH_SCOPE_COUNT
    with _SHARED_BROWSER_MANAGER_LOCK:
        _SHARED_BROWSER_BATCH_SCOPE_COUNT += 1
    try:
        yield
    finally:
        managers_to_close: list[Any] = []
        with _SHARED_BROWSER_MANAGER_LOCK:
            _SHARED_BROWSER_BATCH_SCOPE_COUNT = max(
                0, _SHARED_BROWSER_BATCH_SCOPE_COUNT - 1
            )
            if _SHARED_BROWSER_BATCH_SCOPE_COUNT == 0:
                idle_keys = [
                    key
                    for key, entry in _SHARED_BROWSER_MANAGERS.items()
                    if entry.ref_count <= 0
                ]
                for key in idle_keys:
                    managers_to_close.append(_SHARED_BROWSER_MANAGERS.pop(key).manager)
        for manager in managers_to_close:
            with contextlib.suppress(Exception):
                manager.close()


atexit.register(close_shared_browser_managers)


def _transport_disk_cache_dir(
    env: Mapping[str, str],
    download_dir: Path | None,
    *,
    artifact_mode: ArtifactMode = DEFAULT_ARTIFACT_MODE,
) -> Path | None:
    if artifact_mode != "all":
        return None
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
    artifact_mode: ArtifactMode = DEFAULT_ARTIFACT_MODE,
) -> HttpTransport:
    metadata_cache_ttl = parse_nonnegative_int_env(
        env,
        HTTP_METADATA_CACHE_TTL_ENV_VAR,
        default=DEFAULT_METADATA_CACHE_TTL_SECONDS,
    )
    disk_cache_max_age_days = parse_nonnegative_int_env(
        env,
        HTTP_DISK_CACHE_MAX_AGE_DAYS_ENV_VAR,
        default=DEFAULT_DISK_CACHE_MAX_AGE_DAYS,
    )
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
        metadata_cache_ttl=metadata_cache_ttl,
        disk_cache_dir=_transport_disk_cache_dir(
            env,
            download_dir,
            artifact_mode=artifact_mode,
        ),
        disk_cache_max_entries=parse_nonnegative_int_env(
            env,
            HTTP_DISK_CACHE_MAX_ENTRIES_ENV_VAR,
            default=DEFAULT_DISK_CACHE_MAX_ENTRIES,
        ),
        disk_cache_max_bytes=parse_nonnegative_int_env(
            env,
            HTTP_DISK_CACHE_MAX_BYTES_ENV_VAR,
            default=DEFAULT_DISK_CACHE_MAX_BYTES,
        ),
        disk_cache_max_age_seconds=disk_cache_max_age_days * 24 * 60 * 60,
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
    stage_timings: dict[str, float] = field(default_factory=dict)
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
    _stage_timing_lock: threading.RLock = field(
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
    _browser_context_manager: Any | None = field(default=None, init=False, repr=False)
    _browser_context_managers: dict[tuple[str, str, str, str, str], Any] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _camoufox_browser_managers: dict[tuple[int, bool, str, bool], Any] = field(
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
        self.stage_timings.setdefault("asset_seconds", 0.0)
        self.stage_timings.setdefault("browser_seconds", 0.0)
        self.stage_timings.setdefault("dom_readiness_seconds", 0.0)
        self.stage_timings.setdefault("http_seconds", 0.0)
        self.stage_timings.setdefault("retry_seconds", 0.0)
        self.stage_timings.setdefault("formula_seconds", 0.0)

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

        Request-mutated fields, parser/session caches, timings, artifact policy, and
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

    def playwright_browser(self, *, headless: bool = True) -> Any:
        """Return a lazily attached shared CDP browser."""

        return self._browser_lifecycle().browser(headless=headless)

    def new_browser_context(
        self, *, headless: bool = True, **context_kwargs: Any
    ) -> Any:
        """Create a browser context from the shared CDP browser."""

        return self._browser_lifecycle().new_context(
            headless=headless, **context_kwargs
        )

    def new_browser_context_for_config(
        self,
        *,
        headless: bool = True,
        binary_path: str | None = None,
        cdp_endpoint: str | None = None,
        external_new_context: bool = False,
        profile_dir: Path | str | None = None,
        user_data_dir: Path | str | None = None,
        **context_kwargs: Any,
    ) -> Any:
        """Create a context from a browser lifecycle keyed by runtime browser config."""

        return self._browser_lifecycle_for_config(
            binary_path=binary_path,
            cdp_endpoint=cdp_endpoint,
            external_new_context=external_new_context,
            profile_dir=profile_dir,
            user_data_dir=user_data_dir,
        ).new_context(headless=headless, **context_kwargs)

    def new_playwright_context(
        self, *, headless: bool = True, **context_kwargs: Any
    ) -> Any:
        """Create a browser context from the shared CDP browser."""

        return self.new_browser_context(headless=headless, **context_kwargs)

    def new_browser_context_for_runtime_config(
        self,
        config: Any,
        **context_kwargs: Any,
    ) -> Any:
        """Create a fresh context using the backend carried by runtime config."""

        backend = str(config.backend).strip().lower()
        if backend != "camoufox":
            raise RuntimeError(f"Unsupported browser backend {config.backend!r}.")
        key = (
            threading.get_ident(),
            bool(config.headless),
            str(config.binary_path or "").strip(),
            bool(config.auto_prepare),
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
                    auto_prepare=config.auto_prepare,
                    cancel_check=self.cancel_check,
                )
                self._camoufox_browser_managers[key] = manager
        return manager.new_context(**context_kwargs)

    def close_playwright(self) -> None:
        """Close any browser owned by this runtime context."""

        with self._browser_context_manager_lock:
            manager = self._browser_context_manager
            keyed_managers = list(self._browser_context_managers.values())
            camoufox_managers = list(self._camoufox_browser_managers.values())
            self._browser_context_managers.clear()
            self._camoufox_browser_managers.clear()
            self._browser_context_manager = None
        seen: set[int] = set()
        if manager is not None:
            seen.add(id(manager))
            manager.close()
        for keyed_manager in keyed_managers:
            if id(keyed_manager) in seen:
                continue
            seen.add(id(keyed_manager))
            keyed_manager.close()
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

    def _browser_lifecycle(self) -> Any:
        with self._browser_context_manager_lock:
            if self._browser_context_manager is None:
                cdp_endpoint = None
                binary_path = None
                profile_dir = None
                user_data_dir = None
                external_new_context = False
                key = self._browser_lifecycle_key(
                    binary_path=binary_path,
                    cdp_endpoint=cdp_endpoint,
                    external_new_context=external_new_context,
                    profile_dir=profile_dir,
                    user_data_dir=user_data_dir,
                )
                self._browser_context_manager = _acquire_shared_browser_manager(
                    key=key,
                    binary_path=binary_path,
                    cdp_endpoint=cdp_endpoint,
                    external_new_context=external_new_context,
                    profile_dir=profile_dir,
                    user_data_dir=user_data_dir,
                )
            return self._browser_context_manager

    def _browser_lifecycle_for_config(
        self,
        *,
        binary_path: str | None,
        cdp_endpoint: str | None,
        external_new_context: bool,
        profile_dir: Path | str | None = None,
        user_data_dir: Path | str | None = None,
    ) -> Any:
        key = self._browser_lifecycle_key(
            binary_path=binary_path,
            cdp_endpoint=cdp_endpoint,
            external_new_context=external_new_context,
            profile_dir=profile_dir,
            user_data_dir=user_data_dir,
        )
        with self._browser_context_manager_lock:
            manager = self._browser_context_managers.get(key)
            if manager is None:
                active_binary_path = str(binary_path or "").strip() or None
                active_cdp_endpoint = str(cdp_endpoint or "").strip() or None
                active_profile_dir = (
                    Path(profile_dir).expanduser() if profile_dir is not None else None
                )
                active_user_data_dir = (
                    Path(user_data_dir).expanduser()
                    if user_data_dir is not None
                    else None
                )
                manager = _acquire_shared_browser_manager(
                    key=key,
                    binary_path=active_binary_path,
                    cdp_endpoint=active_cdp_endpoint,
                    external_new_context=external_new_context,
                    profile_dir=active_profile_dir,
                    user_data_dir=active_user_data_dir,
                )
                self._browser_context_managers[key] = manager
            return manager

    @staticmethod
    def _browser_lifecycle_key(
        *,
        binary_path: str | None,
        cdp_endpoint: str | None,
        external_new_context: bool = False,
        profile_dir: Path | str | None,
        user_data_dir: Path | str | None,
    ) -> tuple[str, str, str, str, str]:
        return (
            str(binary_path or "").strip(),
            str(cdp_endpoint or "").strip(),
            "1" if external_new_context else "0",
            str(Path(profile_dir).expanduser()) if profile_dir is not None else "",
            str(Path(user_data_dir).expanduser()) if user_data_dir is not None else "",
        )

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
        self.close_playwright()
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
            self.close_playwright()

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
        with self._parse_cache_lock:
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
        stored = copy.deepcopy(value) if copy_value else value
        with self._parse_cache_lock:
            self.parse_cache[key] = stored
        return copy.deepcopy(stored) if copy_value else stored

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
    artifact_mode: ArtifactMode | object = RUNTIME_UNSET,
    fetch_cache: Any | object = RUNTIME_UNSET,
    parse_cache: dict[tuple[Hashable, ...], Any] | object = RUNTIME_UNSET,
    session_cache: dict[tuple[Hashable, ...], Any] | object = RUNTIME_UNSET,
    stage_timings: dict[str, float] | object = RUNTIME_UNSET,
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
        "stage_timings": stage_timings,
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
    resolved_stage_timings = (
        {} if stage_timings is RUNTIME_UNSET else cast(dict[str, float], stage_timings)
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
        stage_timings=resolved_stage_timings,
    )


@contextlib.contextmanager
def runtime_context_scope(
    context: RuntimeContext | None = None,
    **runtime_parts: Any,
):
    """Yield a runtime and close it only when this scope created it."""

    runtime = resolve_runtime_context(context, **runtime_parts)
    try:
        yield runtime
    finally:
        if context is None:
            runtime.close()
