"""Browser-neutral runtime data types."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict


@dataclass(frozen=True)
class BrowserRuntimeConfig:
    provider: str
    doi: str
    artifact_dir: Path
    headless: bool
    user_agent: str | None
    timeout_ms: int = 120000
    binary_path: str | None = None
    profile_dir: Path | None = None
    user_data_dir: Path | None = None
    storage_state_path: Path | None = None
    persist_storage_state: bool = True
    capability_storage_state_path: Path | None = None


@dataclass(frozen=True)
class BrowserRuntimeSession:
    """A fresh selected-backend browser context and its owning manager, if any."""

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

    return_image_payload: bool = False
    return_screenshot: bool = False
    lightweight_seed_only: bool = False
    blocked_resource_types: frozenset[str] | tuple[str, ...] | None = None
    readiness_budget_seconds: float | None = None
    reuse_runtime_page: bool = False


@dataclass(frozen=True)
class BrowserStagedStorageState:
    """Provider-scoped browser state captured before an accepted commit."""

    path: Path
    provider: str
    filter_url: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class BrowserWarmResult(Mapping[str, Any]):
    """Typed result for a bounded browser-context refresh attempt.

    Mapping methods proxy the effective seed for compatibility with existing
    provider adapters while callers migrate to the explicit outcome fields.
    """

    seed: Mapping[str, Any]
    changed: bool
    accepted: bool
    status: int | None
    reason: str
    final_url: str | None = None
    cookie_delta: Mapping[str, int] = field(default_factory=dict)
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        return self.seed[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.seed)

    def __len__(self) -> int:
        return len(self.seed)


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
    screenshot_b64: str | None = None
    image_payload: Mapping[str, Any] | None = None
    diagnostics: Mapping[str, Any] | None = None
    staged_storage_state: BrowserStagedStorageState | None = None


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


class BrowserImagePayload(TypedDict, total=False):
    bodyB64: str
    contentType: str
    url: str
    status: int
    width: int
    height: int


class BrowserContextSeed(TypedDict, total=False):
    browser_cookies: list[dict[str, Any]]
    browser_user_agent: str | None
    browser_final_url: str | None
    paper_fetch_html_fetcher: str
    diagnostics: dict[str, Any]
    metadata: dict[str, Any]
