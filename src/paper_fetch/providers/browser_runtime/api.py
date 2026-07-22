"""Browser-neutral runtime API."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping
from dataclasses import replace
import threading
import warnings

from .. import _cloakbrowser
from ..base import ProviderFailure, ProviderStatusResult
from ...config import (
    BROWSER_BACKEND_ENV_VAR,
    DEFAULT_BROWSER_BACKEND,
    SUPPORTED_BROWSER_BACKENDS,
    resolve_browser_backend_selection,
)
from ...reason_codes import NOT_CONFIGURED
from .backends.camoufox import DEFAULT_CAMOUFOX_BACKEND
from .backends.cloakbrowser import DEFAULT_CLOAKBROWSER_BACKEND
from .types import BrowserFetchedHtml, BrowserRuntimeBackend, BrowserRuntimeConfig

_BROWSER_RUNTIME_BACKENDS: dict[str, BrowserRuntimeBackend] = {
    DEFAULT_CAMOUFOX_BACKEND.name: DEFAULT_CAMOUFOX_BACKEND,
    DEFAULT_CLOAKBROWSER_BACKEND.name: DEFAULT_CLOAKBROWSER_BACKEND,
}
DEFAULT_BROWSER_RUNTIME_BACKEND: BrowserRuntimeBackend = _BROWSER_RUNTIME_BACKENDS[
    DEFAULT_BROWSER_BACKEND
]
_DEPRECATION_LOCK = threading.Lock()
_DEPRECATION_WARNED: set[str] = set()

DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS = (
    _cloakbrowser.DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS
)
DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS = (
    _cloakbrowser.DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS
)
DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS = (
    _cloakbrowser.DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS
)


def browser_runtime_backend(name: str) -> BrowserRuntimeBackend:
    normalized = str(name or "").strip().lower()
    try:
        return _BROWSER_RUNTIME_BACKENDS[normalized]
    except KeyError as exc:
        supported = ", ".join(sorted(SUPPORTED_BROWSER_BACKENDS))
        raise ProviderFailure(
            NOT_CONFIGURED,
            f"Invalid {BROWSER_BACKEND_ENV_VAR}={name!r}; expected one of: {supported}.",
        ) from exc


def selected_browser_runtime_backend(
    env: Mapping[str, str],
) -> BrowserRuntimeBackend:
    selection = resolve_browser_backend_selection(env)
    backend = browser_runtime_backend(selection.backend)
    if selection.deprecated:
        with _DEPRECATION_LOCK:
            if selection.backend not in _DEPRECATION_WARNED:
                warnings.warn(
                    (
                        "CloakBrowser is deprecated in paper-fetch 3.2.0 and may be "
                        "removed in 4.0.0; use the default Camoufox backend."
                    ),
                    FutureWarning,
                    stacklevel=2,
                )
                _DEPRECATION_WARNED.add(selection.backend)
    return backend


def _backend_for_config(config: BrowserRuntimeConfig) -> BrowserRuntimeBackend:
    backend_name = config.backend
    if not isinstance(backend_name, str) or not backend_name.strip():
        raise ProviderFailure(
            NOT_CONFIGURED,
            "BrowserRuntimeConfig.backend must explicitly name a supported backend.",
        )
    return browser_runtime_backend(backend_name)


def load_runtime_config(
    env: Mapping[str, str],
    *,
    provider: str,
    doi: str,
    require_storage_state: bool = False,
) -> BrowserRuntimeConfig:
    return selected_browser_runtime_backend(env).load_runtime_config(
        env,
        provider=provider,
        doi=doi,
        require_storage_state=require_storage_state,
    )


def ensure_runtime_ready(config: BrowserRuntimeConfig) -> None:
    _backend_for_config(config).ensure_runtime_ready(config)


def probe_runtime_status(
    env: Mapping[str, str],
    *,
    provider: str,
    doi: str = "probe://browser/status",
    deep: bool = False,
) -> ProviderStatusResult:
    selection = resolve_browser_backend_selection(env)
    result = selected_browser_runtime_backend(env).probe_runtime_status(
        env,
        provider=provider,
        doi=doi,
        deep=deep,
    )
    return replace(result, notes=[*result.notes, *selection.notes])


def fetch_html_with_browser(
    candidate_urls: list[str],
    *,
    publisher: str,
    config: BrowserRuntimeConfig,
    **kwargs: Any,
) -> BrowserFetchedHtml:
    return _backend_for_config(config).fetch_html(
        candidate_urls,
        publisher=publisher,
        config=config,
        **kwargs,
    )


fetch_html_with_browser.paper_fetch_html_fetcher_name = "selected_browser"  # type: ignore[attr-defined]


def warm_browser_context(
    candidate_urls: list[str],
    *,
    publisher: str,
    config: BrowserRuntimeConfig,
    browser_context_seed: Mapping[str, Any] | None = None,
    runtime_context: Any | None = None,
    lightweight: bool = False,
) -> dict[str, Any]:
    return _backend_for_config(config).warm_context(
        candidate_urls,
        publisher=publisher,
        config=config,
        browser_context_seed=browser_context_seed,
        runtime_context=runtime_context,
        lightweight=lightweight,
    )


def storage_state_path(config: BrowserRuntimeConfig):
    return _backend_for_config(config).storage_state_path(config)


def save_storage_state(
    context: Any,
    config: BrowserRuntimeConfig,
    *,
    filter_url: str | None = None,
):
    return _backend_for_config(config).save_storage_state(
        context,
        config,
        filter_url=filter_url,
    )
