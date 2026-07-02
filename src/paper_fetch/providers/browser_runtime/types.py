"""Browser-neutral runtime data types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict
from collections.abc import Mapping


@dataclass(frozen=True)
class BrowserRuntimeConfig:
    provider: str
    doi: str
    artifact_dir: Path
    headless: bool
    user_agent: str | None
    timeout_ms: int = 120000
    binary_path: str | None = None
    cdp_endpoint: str | None = None
    profile_dir: Path | None = None
    user_data_dir: Path | None = None
    storage_state_path: Path | None = None


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
