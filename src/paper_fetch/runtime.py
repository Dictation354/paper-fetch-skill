"""Runtime dependency container for service and adapter entrypoints."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .artifacts import ArtifactStore
from .config import build_runtime_env
from .http import HttpTransport

RUNTIME_UNSET = object()


@dataclass
class RuntimeContext:
    """Holds runtime dependencies shared across service, workflow, and adapters."""

    env: Mapping[str, str] | None = None
    transport: HttpTransport | None = None
    clients: Mapping[str, Any] | None = None
    download_dir: Path | None = None
    cancel_check: Callable[[], bool] | None = None
    artifact_store: ArtifactStore | None = None
    fetch_cache: Any | None = None

    def __post_init__(self) -> None:
        self.env = build_runtime_env() if self.env is None else dict(self.env)
        if self.transport is None:
            self.transport = HttpTransport(cancel_check=self.cancel_check)
        if self.artifact_store is None:
            self.artifact_store = ArtifactStore.from_download_dir(self.download_dir)
        elif self.download_dir is None:
            self.download_dir = self.artifact_store.download_dir

    def get_clients(self) -> Mapping[str, Any]:
        if self.clients is None:
            from .providers.registry import build_clients

            assert self.transport is not None
            assert self.env is not None
            self.clients = build_clients(self.transport, self.env)
        return self.clients


def resolve_runtime_context(
    context: RuntimeContext | None = None,
    *,
    env: Mapping[str, str] | None | object = RUNTIME_UNSET,
    transport: HttpTransport | None | object = RUNTIME_UNSET,
    clients: Mapping[str, Any] | None | object = RUNTIME_UNSET,
    download_dir: Path | None | object = RUNTIME_UNSET,
    cancel_check: Callable[[], bool] | None | object = RUNTIME_UNSET,
    artifact_store: ArtifactStore | None | object = RUNTIME_UNSET,
    fetch_cache: Any | object = RUNTIME_UNSET,
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

    return RuntimeContext(
        env=None if active_env is RUNTIME_UNSET else active_env,
        transport=None if active_transport is RUNTIME_UNSET else active_transport,
        clients=None if active_clients is RUNTIME_UNSET else active_clients,
        download_dir=None if active_download_dir is RUNTIME_UNSET else active_download_dir,
        cancel_check=None if active_cancel_check is RUNTIME_UNSET else active_cancel_check,
        artifact_store=None if active_artifact_store is RUNTIME_UNSET else active_artifact_store,
        fetch_cache=None if active_fetch_cache is RUNTIME_UNSET else active_fetch_cache,
    )
