"""Browser-neutral runtime contract for provider workflows."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from .seed import (
    CLOUDFLARE_COOKIE_NAMES,
    _CLOUDFLARE_COOKIE_PREFIXES,
    browser_context_seed_from_mapping,
    browser_context_seed_to_mapping,
    merge_browser_context_seeds,
    normalize_browser_cookie_for_playwright,
    normalize_browser_cookies_for_playwright,
    parse_optional_int,
)
from .types import (
    BrowserContextSeed,
    BrowserFetchedHtml,
    BrowserImagePayload,
    BrowserRuntimeBackend,
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
)

_API_EXPORTS = {
    "DEFAULT_BROWSER_RUNTIME_BACKEND",
    "DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS",
    "DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS",
    "DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS",
    "ensure_runtime_ready",
    "fetch_html_with_browser",
    "load_runtime_config",
    "probe_runtime_status",
    "save_storage_state",
    "storage_state_path",
    "warm_browser_context",
}

__all__ = [
    "CLOUDFLARE_COOKIE_NAMES",
    "DEFAULT_BROWSER_RUNTIME_BACKEND",
    "DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS",
    "DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS",
    "DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS",
    "_CLOUDFLARE_COOKIE_PREFIXES",
    "BrowserContextSeed",
    "BrowserFetchedHtml",
    "BrowserImagePayload",
    "BrowserRuntimeBackend",
    "BrowserRuntimeConfig",
    "BrowserRuntimeFailure",
    "browser_context_seed_from_mapping",
    "browser_context_seed_to_mapping",
    "ensure_runtime_ready",
    "fetch_html_with_browser",
    "load_runtime_config",
    "merge_browser_context_seeds",
    "normalize_browser_cookie_for_playwright",
    "normalize_browser_cookies_for_playwright",
    "parse_optional_int",
    "probe_runtime_status",
    "save_storage_state",
    "storage_state_path",
    "warm_browser_context",
]


def __getattr__(name: str) -> Any:
    if name not in _API_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    api = import_module(f"{__name__}.api")
    value = getattr(api, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
