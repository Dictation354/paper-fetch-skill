"""Browser-neutral runtime contract for provider workflows."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from .context import browser_context
from .seed import (
    _CLOUDFLARE_COOKIE_PREFIXES,
    CLOUDFLARE_COOKIE_NAMES,
    browser_context_seed_from_mapping,
    browser_context_seed_from_session,
    browser_context_seed_to_mapping,
    merge_browser_context_seeds,
    normalize_browser_cookie_for_playwright,
    normalize_browser_cookies_for_playwright,
    parse_optional_int,
)
from .types import (
    DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS,
    DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS,
    DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS,
    BrowserContextSeed,
    BrowserFetchedHtml,
    BrowserHtmlFetchOptions,
    BrowserHtmlReadiness,
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
    BrowserRuntimeSession,
    BrowserWarmResult,
)

_API_EXPORTS = {
    "ensure_runtime_ready",
    "fetch_html_with_browser",
    "load_runtime_config",
    "prepare_runtime",
    "probe_runtime_status",
    "warm_browser_context",
}
_TELEMETRY_EXPORTS = {
    "browser_page_user_agent",
}

__all__ = [
    "CLOUDFLARE_COOKIE_NAMES",
    "DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS",
    "DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS",
    "DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS",
    "_CLOUDFLARE_COOKIE_PREFIXES",
    "BrowserContextSeed",
    "BrowserFetchedHtml",
    "BrowserHtmlFetchOptions",
    "BrowserHtmlReadiness",
    "BrowserRuntimeConfig",
    "BrowserRuntimeFailure",
    "BrowserRuntimeSession",
    "BrowserWarmResult",
    "browser_context",
    "browser_context_seed_from_mapping",
    "browser_context_seed_from_session",
    "browser_context_seed_to_mapping",
    "browser_page_user_agent",
    "ensure_runtime_ready",
    "fetch_html_with_browser",
    "load_runtime_config",
    "merge_browser_context_seeds",
    "normalize_browser_cookie_for_playwright",
    "normalize_browser_cookies_for_playwright",
    "parse_optional_int",
    "prepare_runtime",
    "probe_runtime_status",
    "warm_browser_context",
]


def __getattr__(name: str) -> Any:
    if name in _API_EXPORTS:
        target = import_module(f"{__name__}.api")
    elif name in _TELEMETRY_EXPORTS:
        target = import_module(f"{__name__}.telemetry")
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(target, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
