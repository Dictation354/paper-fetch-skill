"""Science provider client."""

from __future__ import annotations

from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.provider_rules import (
    ATYPON_FRONT_MATTER_CONTAINS_TOKENS,
    DomHooks,
    MarkdownHooks,
    ProviderCleanupRules,
    ProviderFrontMatterRules,
    ProviderHtmlRules,
    SCIENCE_FRONT_MATTER_EXACT_TEXTS,
    SCIENCE_FRONT_MATTER_PUBLICATION_KEYWORDS,
    SCIENCE_POST_CONTENT_BREAK_TOKENS,
    SCIENCE_SITE_RULE_OVERRIDES,
)
from ..provider_catalog import (
    ATYPON_DEFAULT_PDF_PATH_TEMPLATES,
    ProviderRouteSpec,
    ProviderSpec,
)
from ..quality.html_signals import (
    SCIENCE_AVAILABILITY_OVERRIDES,
    SCIENCE_SIGNAL_SET,
)
from . import _science_html, browser_workflow
from ._registry import ProviderBundle, register_provider_bundle


register_provider_bundle(
    ProviderBundle(
        catalog=ProviderSpec(
            name="science",
            display_name="Science",
            official=True,
            domains=("www.science.org", "science.org"),
            doi_prefixes=("10.1126/",),
            publisher_aliases=(
                "american association for the advancement of science",
                "aaas",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            client_factory_path="paper_fetch.providers.science:ScienceClient",
            status_order=4,
            base_domains=("www.science.org", "science.org"),
            html_path_templates=("/doi/full/{doi}", "/doi/{doi}"),
            pdf_path_templates=(
                *ATYPON_DEFAULT_PDF_PATH_TEMPLATES,
                "/doi/pdf/{doi}?download=true",
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
        ),
        html_rules=ProviderHtmlRules(
            name="science",
            aliases=("aaas",),
            cleanup=ProviderCleanupRules(
                post_content_break_tokens=SCIENCE_POST_CONTENT_BREAK_TOKENS,
            ),
            availability=AvailabilityPolicy(
                name="science",
                site_rule_overrides=SCIENCE_SITE_RULE_OVERRIDES,
                datalayer_signal_set=SCIENCE_SIGNAL_SET,
                overrides=SCIENCE_AVAILABILITY_OVERRIDES,
            ),
            front_matter=ProviderFrontMatterRules(
                exact_texts=SCIENCE_FRONT_MATTER_EXACT_TEXTS,
                contains_tokens=ATYPON_FRONT_MATTER_CONTAINS_TOKENS,
                publication_keywords=SCIENCE_FRONT_MATTER_PUBLICATION_KEYWORDS,
            ),
            dom_hooks=DomHooks(
                before_block_normalization=_science_html.science_before_block_normalization,
                asset_body_container=_science_html.science_asset_body_container,
                asset_figure_extraction=_science_html.science_asset_figure_extraction,
            ),
            markdown_hooks=MarkdownHooks(
                normalize_markdown=_science_html.science_normalize_markdown,
                keep_unknown_abstract_block=_science_html.science_keep_unknown_abstract_block,
            ),
        ),
        sources=("science",),
    )
)


SCIENCE_BROWSER_PROFILE = browser_workflow.make_atypon_browser_profile(
    "science",
    fallback_author_extractor=_science_html.extract_authors,
    policy=browser_workflow.BrowserWorkflowPolicy(
        blocked_resource_types=("image", "font", "media"),
        preflight_html_reuse=True,
    ),
)


class ScienceClient(browser_workflow.BrowserWorkflowClient):
    name = SCIENCE_BROWSER_PROFILE.name
    profile = SCIENCE_BROWSER_PROFILE
