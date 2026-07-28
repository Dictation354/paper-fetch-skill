"""Browser-neutral runtime data types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypedDict
from collections.abc import Mapping


@dataclass(frozen=True)
class BrowserRuntimeConfig:
    provider: str
    doi: str
    artifact_dir: Path
    headless: bool
    user_agent: str | None
    backend: str
    timeout_ms: int = 120000
    binary_path: str | None = None
    cdp_endpoint: str | None = None
    external_new_context: bool = False
    profile_dir: Path | None = None
    user_data_dir: Path | None = None
    storage_state_path: Path | None = None
    persist_storage_state: bool = True


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


class BrowserImagePayload(TypedDict):
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


class BrowserRuntimeBackend(Protocol):
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
    ) -> Any: ...

    def fetch_html(
        self,
        candidate_urls: list[str],
        *,
        publisher: str,
        config: BrowserRuntimeConfig,
        **kwargs: Any,
    ) -> BrowserFetchedHtml: ...

    def warm_context(
        self,
        candidate_urls: list[str],
        *,
        publisher: str,
        config: BrowserRuntimeConfig,
        browser_context_seed: Mapping[str, Any] | None = None,
        runtime_context: Any | None = None,
        lightweight: bool = False,
    ) -> dict[str, Any]: ...

    def storage_state_path(self, config: BrowserRuntimeConfig) -> Path | None: ...

    def save_storage_state(
        self,
        context: Any,
        config: BrowserRuntimeConfig,
        *,
        filter_url: str | None = None,
    ) -> Mapping[str, Any]: ...
