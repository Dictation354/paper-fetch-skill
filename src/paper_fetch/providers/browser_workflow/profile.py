"""Profile data structures for provider browser workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from ..base import ProviderFailure, RawFulltextPayload


@dataclass
class BrowserWorkflowBootstrapResult:
    normalized_doi: str
    runtime: Any | None
    landing_page_url: str | None
    html_candidates: list[str]
    pdf_candidates: list[str]
    browser_context_seed: Mapping[str, Any] | None = None
    html_failure_reason: str | None = None
    html_failure_message: str | None = None
    html_payload: RawFulltextPayload | None = None
    runtime_failure: ProviderFailure | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderBrowserProfile:
    name: str
    article_source_name: str | None
    label: str
    hosts: tuple[str, ...]
    base_hosts: tuple[str, ...]
    html_path_templates: tuple[str, ...]
    pdf_path_templates: tuple[str, ...]
    crossref_pdf_position: int
    markdown_publisher: str
    fallback_author_extractor: Callable[[str], list[str]] | None
    shared_playwright_image_fetcher: bool
    direct_playwright_html_preflight: bool = False
