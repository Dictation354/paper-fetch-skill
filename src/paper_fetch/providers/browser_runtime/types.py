"""Browser-neutral runtime data types."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict

DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS = 120000
DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS = 8
DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS = 1


@dataclass(frozen=True)
class BrowserRuntimeConfig:
    provider: str
    doi: str
    artifact_dir: Path
    headless: bool
    user_agent: str | None
    timeout_ms: int = DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS
    binary_path: str | None = None
    profile_dir: Path | None = None
    user_data_dir: Path | None = None
    backend: str = "scrapling"
    browser_cache_dir: Path | None = None


@dataclass(frozen=True)
class BrowserRuntimeSession:
    """A persistent browser context and its local owner, or None when borrowed."""

    backend: str
    context: Any
    manager: Any | None = None


@dataclass(frozen=True)
class BrowserHtmlReadiness:
    """Select the readiness strategy used after browser HTML navigation."""

    wait_for_article_body: bool = True
    selector: str | None = None
    selector_text: str | None = None
    require_selector: bool = False


@dataclass(frozen=True)
class BrowserHtmlFetchOptions:
    """Select specialized HTML-fetch result modes without widening the facade."""

    supplementary_index: bool = False
    lightweight_seed_only: bool = False
    blocked_resource_types: frozenset[str] | tuple[str, ...] | None = None
    empty_script_response_urls: frozenset[str] | tuple[str, ...] = frozenset()
    readiness_budget_seconds: float | None = None
    reuse_runtime_page: bool = False


@dataclass(frozen=True)
class BrowserWarmResult:
    """Typed result for a bounded browser-context refresh attempt."""

    seed: Mapping[str, Any]
    changed: bool
    accepted: bool
    status: int | None
    reason: str
    final_url: str | None = None
    cookie_delta: Mapping[str, int] = field(default_factory=dict)
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrowserFetchedHtml:
    source_url: str
    final_url: str
    html: str
    response_status: int | None
    response_headers: Mapping[str, str]
    title: str | None
    summary: str
    browser_context_seed: Mapping[str, Any]
    image_payload: Mapping[str, Any] | None = None
    diagnostics: Mapping[str, Any] | None = None


class BrowserRuntimeFailure(Exception):
    def __init__(
        self,
        kind: str,
        message: str,
        *,
        browser_context_seed: Mapping[str, Any] | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.browser_context_seed = dict(browser_context_seed or {})
        self.details = dict(details or {})


class BrowserContextSeed(TypedDict, total=False):
    browser_cookies: list[dict[str, Any]]
    browser_user_agent: str | None
    browser_final_url: str | None
    paper_fetch_html_fetcher: str
    diagnostics: dict[str, Any]
    metadata: dict[str, Any]
