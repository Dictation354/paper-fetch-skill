"""Browser-neutral runtime API."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from .. import _cloakbrowser
from ..base import ProviderStatusResult
from .backends.cloakbrowser import DEFAULT_CLOAKBROWSER_BACKEND
from .types import BrowserFetchedHtml, BrowserRuntimeBackend, BrowserRuntimeConfig

DEFAULT_BROWSER_RUNTIME_BACKEND: BrowserRuntimeBackend = DEFAULT_CLOAKBROWSER_BACKEND

DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS = (
    _cloakbrowser.DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS
)
DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS = (
    _cloakbrowser.DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS
)
DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS = (
    _cloakbrowser.DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS
)


def load_runtime_config(
    env: Mapping[str, str],
    *,
    provider: str,
    doi: str,
    require_storage_state: bool = False,
) -> BrowserRuntimeConfig:
    return DEFAULT_BROWSER_RUNTIME_BACKEND.load_runtime_config(
        env,
        provider=provider,
        doi=doi,
        require_storage_state=require_storage_state,
    )


def ensure_runtime_ready(config: BrowserRuntimeConfig) -> None:
    DEFAULT_BROWSER_RUNTIME_BACKEND.ensure_runtime_ready(config)


def probe_runtime_status(
    env: Mapping[str, str],
    *,
    provider: str,
    doi: str = "probe://browser/status",
    deep: bool = False,
) -> ProviderStatusResult:
    return DEFAULT_BROWSER_RUNTIME_BACKEND.probe_runtime_status(
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
    return DEFAULT_BROWSER_RUNTIME_BACKEND.fetch_html(
        candidate_urls,
        publisher=publisher,
        config=config,
        **kwargs,
    )


fetch_html_with_browser.paper_fetch_html_fetcher_name = "cloakbrowser"  # type: ignore[attr-defined]


def warm_browser_context(
    candidate_urls: list[str],
    *,
    publisher: str,
    config: BrowserRuntimeConfig,
    browser_context_seed: Mapping[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    return DEFAULT_BROWSER_RUNTIME_BACKEND.warm_context(
        candidate_urls,
        publisher=publisher,
        config=config,
        browser_context_seed=browser_context_seed,
        runtime_context=runtime_context,
    )


def storage_state_path(config: BrowserRuntimeConfig):
    return DEFAULT_BROWSER_RUNTIME_BACKEND.storage_state_path(config)


def save_storage_state(
    context: Any,
    config: BrowserRuntimeConfig,
    *,
    filter_url: str | None = None,
):
    return DEFAULT_BROWSER_RUNTIME_BACKEND.save_storage_state(
        context,
        config,
        filter_url=filter_url,
    )
