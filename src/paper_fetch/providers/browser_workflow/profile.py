"""Profile data structures for provider browser workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
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
from ..browser_runtime import BrowserHtmlReadiness

if TYPE_CHECKING:
    from ...provider_catalog import ProviderSpec


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
    html_failure_diagnostics: Mapping[str, Any] | None = None
    html_payload: RawFulltextPayload | None = None
    runtime_failure: ProviderFailure | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BrowserWorkflowPolicy:
    """Group provider-specific browser behavior outside the catalog contract."""

    fast_html_attempt: bool = True
    html_readiness_budget_seconds: float | None = None
    blocked_resource_types: frozenset[str] | tuple[str, ...] = frozenset()
    persistent_storage_state: bool = True
    retry_incomplete_html_candidates: bool = False
    direct_figure_page_fallback: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "blocked_resource_types",
            frozenset(
                str(item).strip().lower()
                for item in self.blocked_resource_types
                if str(item).strip()
            ),
        )


DEFAULT_BROWSER_WORKFLOW_POLICY = BrowserWorkflowPolicy()


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
    html_readiness: BrowserHtmlReadiness | None = None
    policy: BrowserWorkflowPolicy = DEFAULT_BROWSER_WORKFLOW_POLICY

    def __getattr__(self, name: str) -> Any:
        if name in BrowserWorkflowPolicy.__dataclass_fields__:
            return getattr(self.policy, name)
        raise AttributeError(name)


def make_browser_profile(
    name: str,
    *,
    catalog: ProviderSpec,
    fallback_author_extractor: Callable[[str], list[str]],
    article_source_name: str | None = None,
    html_readiness: BrowserHtmlReadiness | None = None,
    markdown_publisher: str | None = None,
    shared_browser_image_fetcher: bool = True,
    policy: BrowserWorkflowPolicy = DEFAULT_BROWSER_WORKFLOW_POLICY,
) -> ProviderBrowserProfile:
    """Build catalog-owned routing fields plus provider-specific extraction hooks."""

    return ProviderBrowserProfile(
        name=name,
        article_source_name=article_source_name,
        label=catalog.display_name,
        hosts=catalog.domains,
        base_hosts=catalog.base_domains,
        html_path_templates=catalog.html_path_templates,
        pdf_path_templates=catalog.pdf_path_templates,
        crossref_pdf_position=catalog.crossref_pdf_position,
        markdown_publisher=markdown_publisher or name,
        fallback_author_extractor=fallback_author_extractor,
        shared_browser_image_fetcher=shared_browser_image_fetcher,
        html_readiness=html_readiness,
        policy=policy,
    )


def make_atypon_browser_profile(
    name: str,
    *,
    catalog: ProviderSpec,
    fallback_author_extractor: Callable[[str], list[str]],
    article_source_name: str | None = None,
    html_readiness: BrowserHtmlReadiness | None = None,
    policy: BrowserWorkflowPolicy = DEFAULT_BROWSER_WORKFLOW_POLICY,
) -> ProviderBrowserProfile:
    return make_browser_profile(
        name,
        catalog=catalog,
        article_source_name=article_source_name,
        fallback_author_extractor=fallback_author_extractor,
        html_readiness=html_readiness,
        policy=policy,
    )


def browser_profile_catalog_mismatches(
    profile: ProviderBrowserProfile,
) -> tuple[str, ...]:
    expected = {
        "label": provider_display_name(profile.name),
        "hosts": provider_domains(profile.name),
        "base_hosts": provider_base_domains(profile.name),
        "html_path_templates": provider_html_path_templates(profile.name),
        "pdf_path_templates": provider_pdf_path_templates(profile.name),
        "crossref_pdf_position": provider_crossref_pdf_position(profile.name),
    }
    mismatches = [
        field_name
        for field_name, expected_value in expected.items()
        if getattr(profile, field_name) != expected_value
    ]
    return tuple(mismatches)


def validate_browser_profile_catalog_sync(
    profile: ProviderBrowserProfile,
) -> None:
    mismatches = browser_profile_catalog_mismatches(profile)
    if mismatches:
        raise ValueError(
            f"Browser profile {profile.name!r} is out of sync with the provider "
            f"catalog: {', '.join(mismatches)}"
        )
