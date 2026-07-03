"""Profile data structures for provider browser workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Callable, Mapping

from ...provider_catalog import (
    provider_base_domains,
    provider_crossref_pdf_position,
    provider_domains,
    provider_html_path_templates,
    provider_pdf_path_templates,
)
from ...utils import provider_display_name
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
    shared_browser_image_fetcher: bool


def make_atypon_browser_profile(
    name: str,
    *,
    fallback_author_extractor: Callable[[str], list[str]],
    article_source_name: str | None = None,
) -> ProviderBrowserProfile:
    return ProviderBrowserProfile(
        name=name,
        article_source_name=article_source_name,
        label=provider_display_name(name),
        hosts=provider_domains(name),
        base_hosts=provider_base_domains(name),
        html_path_templates=provider_html_path_templates(name),
        pdf_path_templates=provider_pdf_path_templates(name),
        crossref_pdf_position=provider_crossref_pdf_position(name),
        markdown_publisher=name,
        fallback_author_extractor=fallback_author_extractor,
        shared_browser_image_fetcher=True,
    )
