"""Browser-neutral runtime API."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from .. import _playwright_browser
from ..base import ProviderStatusResult
from .selection import selected_backend
from .backend import BrowserBackend
from .types import (
    BrowserFetchedHtml,
    BrowserRuntimeConfig,
    BrowserWarmResult,
)


def _backend(name: str) -> BrowserBackend:
    if name in {"byparr", "camoufox"}:
        from .backends.byparr import DEFAULT_BYPARR_BACKEND

        return DEFAULT_BYPARR_BACKEND
    raise ValueError(f"Unknown browser backend: {name}")


DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS = (
    _playwright_browser.DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS
)
DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS = (
    _playwright_browser.DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS
)
DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS = (
    _playwright_browser.DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS
)


def load_runtime_config(
    env: Mapping[str, str],
    *,
    provider: str,
    doi: str,
    require_storage_state: bool = False,
) -> BrowserRuntimeConfig:
    return _backend(selected_backend(env, provider=provider)).load_runtime_config(
        env,
        provider=provider,
        doi=doi,
        require_storage_state=require_storage_state,
    )


def ensure_runtime_ready(config: BrowserRuntimeConfig) -> None:
    _backend(config.backend).ensure_runtime_ready(config)


def prepare_runtime(
    config: BrowserRuntimeConfig, *, runtime_context: Any = None
) -> Any:
    """Explicit preparation uses the same component records as automatic launches."""
    return _backend(config.backend).prepare(config, runtime_context=runtime_context)


def probe_runtime_status(
    env: Mapping[str, str],
    *,
    provider: str,
    doi: str = "probe://browser/status",
    deep: bool = False,
) -> ProviderStatusResult:
    return _backend(selected_backend(env, provider=provider)).probe_runtime_status(
        env,
        provider=provider,
        doi=doi,
        deep=deep,
    )


def fetch_html_with_browser(
    candidate_urls: list[str],
    *,
    publisher: str,
    config: BrowserRuntimeConfig,
    **kwargs: Any,
) -> BrowserFetchedHtml:
    return _backend(config.backend).fetch_html(
        candidate_urls,
        publisher=publisher,
        config=config,
        **kwargs,
    )


fetch_html_with_browser.paper_fetch_html_fetcher_name = "byparr"  # type: ignore[attr-defined]


def warm_browser_context(
    candidate_urls: list[str],
    *,
    publisher: str,
    config: BrowserRuntimeConfig,
    browser_context_seed: Mapping[str, Any] | None = None,
    runtime_context: Any | None = None,
    lightweight: bool = False,
) -> BrowserWarmResult:
    return _backend(config.backend).warm_context(
        candidate_urls,
        publisher=publisher,
        config=config,
        browser_context_seed=browser_context_seed,
        runtime_context=runtime_context,
        lightweight=lightweight,
    )


def storage_state_path(config: BrowserRuntimeConfig):
    return _backend(config.backend).storage_state_path(config)
