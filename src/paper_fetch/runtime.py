"""Runtime dependency container for service and adapter entrypoints."""

from __future__ import annotations

import copy
import hashlib
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
    DEFAULT_CACHE_TTL_SECONDS,
    DEFAULT_PER_HOST_CONCURRENCY,
    DEFAULT_POOL_MAXSIZE,
    DEFAULT_POOL_NUM_POOLS,
    HttpTransport,
)

RUNTIME_UNSET = object()
_PARSE_CACHE_MISSING = object()


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
        default=DEFAULT_CACHE_TTL_SECONDS,
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

    def get_clients(self) -> Mapping[str, object]:
        if self.clients is None:
            from .providers.registry import build_clients

            assert self.transport is not None
            assert self.env is not None
            self.clients = build_clients(self.transport, self.env)
        return self.clients

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
) -> RuntimeContext:
    """Merge explicit legacy keyword arguments over an optional context."""

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

    return RuntimeContext(
        env=None if active_env is RUNTIME_UNSET else active_env,
        transport=None if active_transport is RUNTIME_UNSET else active_transport,
        clients=None if active_clients is RUNTIME_UNSET else active_clients,
        download_dir=None if active_download_dir is RUNTIME_UNSET else active_download_dir,
        cancel_check=None if active_cancel_check is RUNTIME_UNSET else active_cancel_check,
        artifact_store=None if active_artifact_store is RUNTIME_UNSET else active_artifact_store,
        fetch_cache=None if active_fetch_cache is RUNTIME_UNSET else active_fetch_cache,
        parse_cache={} if active_parse_cache is RUNTIME_UNSET else active_parse_cache,
    )
