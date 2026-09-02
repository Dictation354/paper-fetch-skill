"""PNAS provider client."""

from __future__ import annotations

from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.provider_rules import (
    ATYPON_FRONT_MATTER_CONTAINS_TOKENS,
    DomHooks,
    MarkdownHooks,
    PNAS_FRONT_MATTER_EXACT_TEXTS,
    PNAS_FRONT_MATTER_PUBLICATION_KEYWORDS,
    PNAS_MARKDOWN_PROMO_TOKENS,
    PNAS_SITE_RULE_OVERRIDES,
    ProviderCleanupRules,
    ProviderFrontMatterRules,
    ProviderHtmlRules,
)
from ..provider_catalog import ProviderRouteSpec, ProviderSpec
from ..publisher_identity import normalize_doi
from ..quality.html_signals import PNAS_SIGNAL_SET
from . import _pnas_html, browser_workflow
from ._registry import ProviderBundle
from .browser_runtime import BrowserHtmlReadiness

_PROVIDER_SPEC = ProviderSpec(
    name="pnas",
    display_name="PNAS",
    official=True,
    domains=("www.pnas.org", "pnas.org"),
    doi_prefixes=("10.1073/",),
    publisher_aliases=(
        "proceedings of the national academy of sciences",
        "proceedings of the national academy of sciences of the united states of america",
    ),
    asset_default="body",
    probe_capability="routing_signal",
    provider_managed_abstract_only=True,
    status_order=5,
    base_domains=("www.pnas.org", "pnas.org"),
    html_path_templates=("/doi/{doi}", "/doi/full/{doi}"),
    pdf_path_templates=(
        "/doi/epdf/{doi}",
        "/doi/pdf/{doi}?download=true",
        "/doi/pdf/{doi}",
    ),
    routes=(
        ProviderRouteSpec(name="metadata", kind="metadata"),
        ProviderRouteSpec(
            name="browser_html",
            kind="html",
            browser_required=True,
            browser_preflight=True,
            auth_supported=True,
            requires_playwright=True,
            concurrency=1,
        ),
        ProviderRouteSpec(
            name="browser_pdf",
            kind="pdf",
            browser_required=True,
            browser_preflight=True,
            auth_supported=True,
            requires_playwright=True,
            requires_pdf_conversion=True,
            concurrency=1,
        ),
        ProviderRouteSpec(
            name="assets",
            kind="assets",
            browser_optional=True,
            requires_playwright=True,
            timeout_seconds=20,
            concurrency=2,
            transient_retries=0,
        ),
    ),
)

PNAS_BROWSER_PROFILE = browser_workflow.make_atypon_browser_profile(
    "pnas",
    catalog=_PROVIDER_SPEC,
    fallback_author_extractor=_pnas_html.extract_authors,
    html_readiness=BrowserHtmlReadiness(wait_for_article_body=True),
    policy=browser_workflow.BrowserWorkflowPolicy(
        fast_html_attempt=False,
        html_readiness_budget_seconds=8.0,
        blocked_resource_types=("image", "font", "media"),
    ),
)


class PnasClient(browser_workflow.BrowserWorkflowClient):
    name = PNAS_BROWSER_PROFILE.name
    profile = PNAS_BROWSER_PROFILE

    def html_candidates(self, doi: str, metadata) -> list[str]:
        del metadata
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            return []
        return [
            f"https://www.pnas.org/doi/{normalized_doi}",
            f"https://www.pnas.org/doi/full/{normalized_doi}",
            f"https://doi.org/{normalized_doi}",
        ]


PROVIDER_BUNDLE = ProviderBundle(
    client_factory=PnasClient,
    catalog=_PROVIDER_SPEC,
    html_rules=ProviderHtmlRules(
        name="pnas",
        noise_profile="pnas",
        cleanup=ProviderCleanupRules(
            markdown_promo_tokens=PNAS_MARKDOWN_PROMO_TOKENS,
            extraction_drop_keywords=("signup-alert-ad", "tab-nav"),
        ),
        availability=AvailabilityPolicy(
            name="pnas",
            site_rule_overrides=PNAS_SITE_RULE_OVERRIDES,
            datalayer_signal_set=PNAS_SIGNAL_SET,
        ),
        front_matter=ProviderFrontMatterRules(
            exact_texts=PNAS_FRONT_MATTER_EXACT_TEXTS,
            contains_tokens=ATYPON_FRONT_MATTER_CONTAINS_TOKENS,
            publication_keywords=PNAS_FRONT_MATTER_PUBLICATION_KEYWORDS,
        ),
        dom_hooks=DomHooks(
            before_block_normalization=_pnas_html.pnas_before_block_normalization,
        ),
        markdown_hooks=MarkdownHooks(
            suppress_missing_abstract=_pnas_html.pnas_suppress_missing_abstract,
        ),
    ),
    sources=("pnas",),
)
