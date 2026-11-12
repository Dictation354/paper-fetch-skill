"""PNAS provider client."""

from __future__ import annotations

from ._definitions import PROVIDER_DEFINITIONS

from urllib.parse import urlsplit

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
from ..publisher_identity import normalize_doi
from ..quality.html_signals import PNAS_SIGNAL_SET
from . import _pnas_html, browser_workflow
from ._registry import BrowserAssetPolicy, BrowserPagePolicy, ProviderBundle
from .browser_runtime import BrowserHtmlReadiness


_PROVIDER_DEFINITION = PROVIDER_DEFINITIONS["pnas"]

_PROVIDER_SPEC = _PROVIDER_DEFINITION.catalog


def _is_sidebar_metrics_url(url: str) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.hostname == "www.pnas.org"
        and parsed.path == "/pb/widgets/fullSideBarMetric/getResponse"
    )


PNAS_BROWSER_PROFILE = browser_workflow.make_atypon_browser_profile(
    "pnas",
    catalog=_PROVIDER_SPEC,
    fallback_author_extractor=_pnas_html.extract_authors,
    html_readiness=BrowserHtmlReadiness(wait_for_article_body=True),
    policy=browser_workflow.BrowserWorkflowPolicy(
        fast_html_attempt=False,
        preview_fallback=False,
        html_readiness_budget_seconds=8.0,
        blocked_resource_types=("image", "font", "media"),
    ),
)


class PnasClient(browser_workflow.BrowserWorkflowClient):
    name = PNAS_BROWSER_PROFILE.name
    profile = PNAS_BROWSER_PROFILE

    def _browser_asset_file_fetcher(self, context, **request):
        config = request.get("browser_config")
        if config is None or config.state_mode != "json":
            return super()._browser_asset_file_fetcher(context, **request)
        if not request["attempt_supplementary_assets"]:
            return None
        from .browser_workflow.fetchers.context import BrowserDocumentFetcherOptions

        # Keep discovered PNAS attachments in the same Byparr cookie context.
        return self.deps._build_shared_browser_file_fetcher(
            browser_context_seed_getter=request["browser_context_seed_getter"],
            seed_urls_getter=request["seed_urls_getter"],
            browser_user_agent=request["browser_user_agent"],
            headless=request["headless"],
            runtime_context=context,
            use_runtime_shared_browser=True,
            thread_local=True,
            browser_options=BrowserDocumentFetcherOptions(
                runtime_config=config, file_fetch_mode="context_request"
            ),
        )

    def html_candidates(self, doi: str, metadata) -> list[str]:
        del metadata
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            return []
        return [
            f"https://www.pnas.org/doi/full/{normalized_doi}",
            f"https://www.pnas.org/doi/{normalized_doi}",
            f"https://doi.org/{normalized_doi}",
        ]


PROVIDER_BUNDLE = ProviderBundle(
    browser_asset_policy=BrowserAssetPolicy(
        click_supplements=True, target_match_kinds=("*",), context_request_first=True
    ),
    browser_page_policy=BrowserPagePolicy(
        empty_request=_is_sidebar_metrics_url,
        readiness_per_candidate=True,
        document_hosts=("pnas.org", "www.pnas.org"),
    ),
    client_factory=PnasClient,
    catalog=_PROVIDER_SPEC,
    html_rules=ProviderHtmlRules(
        name=_PROVIDER_DEFINITION.rules_name,
        noise_profile=_PROVIDER_DEFINITION.noise_profile,
        cleanup=ProviderCleanupRules(
            markdown_promo_tokens=PNAS_MARKDOWN_PROMO_TOKENS,
            extraction_drop_keywords=("signup-alert-ad", "tab-nav"),
        ),
        availability=AvailabilityPolicy(
            paywall_gate_selectors="#bodymatter > .core-container > .denial-block",
            paywall_gate_pattern=r"view all access options to continue reading this article",
            paywall_paragraph_selector="p, [role='paragraph']",
            paywall_entitlement_signals=("pnas_paywall_no_access",),
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
    sources=_PROVIDER_DEFINITION.sources,
)
