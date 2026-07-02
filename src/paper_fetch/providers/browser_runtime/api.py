"""Browser-neutral runtime API backed by CloakBrowser."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from .. import _cloakbrowser
from ..base import ProviderStatusResult
from .types import BrowserFetchedHtml, BrowserRuntimeConfig

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
    env: Mapping[str, str], *, provider: str, doi: str
) -> BrowserRuntimeConfig:
    return _cloakbrowser.load_runtime_config(env, provider=provider, doi=doi)


def ensure_runtime_ready(config: BrowserRuntimeConfig) -> None:
    _cloakbrowser.ensure_runtime_ready(config)


def probe_runtime_status(
    env: Mapping[str, str],
    *,
    provider: str,
    doi: str = "probe://browser/status",
) -> ProviderStatusResult:
    return _cloakbrowser.probe_runtime_status(env, provider=provider, doi=doi)


def fetch_html_with_browser(
    candidate_urls: list[str],
    *,
    publisher: str,
    config: BrowserRuntimeConfig,
    **kwargs: Any,
) -> BrowserFetchedHtml:
    return _cloakbrowser.fetch_html_with_cloakbrowser(
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
    return _cloakbrowser.warm_browser_context_with_cloakbrowser(
        candidate_urls,
        publisher=publisher,
        config=config,
        browser_context_seed=browser_context_seed,
        runtime_context=runtime_context,
    )
