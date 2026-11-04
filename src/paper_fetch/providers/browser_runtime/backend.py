"""Neutral contract implemented by each browser engine adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from ..base import ProviderStatusResult
from .types import BrowserRuntimeConfig


class BrowserSessionManager(Protocol):
    def new_context(self, **kwargs: Any) -> Any: ...
    def navigate(self, page: Any, url: str, timeout_ms: int) -> Any: ...
    def close(self) -> None: ...


class BrowserBackend(Protocol):
    name: str

    def load_runtime_config(
        self,
        env: Mapping[str, str],
        *,
        provider: str,
        doi: str,
        require_storage_state: bool = False,
    ) -> BrowserRuntimeConfig: ...
    def ensure_runtime_ready(self, config: BrowserRuntimeConfig) -> None: ...
    def probe_runtime_status(
        self,
        env: Mapping[str, str],
        *,
        provider: str,
        doi: str = "probe://browser/status",
        deep: bool = False,
    ) -> ProviderStatusResult: ...
    def prepare(
        self, config: BrowserRuntimeConfig, *, runtime_context: Any = None
    ) -> Any: ...
    def create_manager(
        self, config: BrowserRuntimeConfig, *, runtime_context: Any = None
    ) -> Any: ...
    def fetch_html(
        self,
        candidate_urls: list[str],
        *,
        publisher: str,
        config: BrowserRuntimeConfig,
        **kwargs: Any,
    ) -> Any: ...
    def warm_context(
        self,
        candidate_urls: list[str],
        *,
        publisher: str,
        config: BrowserRuntimeConfig,
        browser_context_seed: Mapping[str, Any] | None = None,
        runtime_context: Any = None,
        lightweight: bool = False,
    ) -> Any: ...
    def storage_state_path(self, config: BrowserRuntimeConfig) -> Any: ...
