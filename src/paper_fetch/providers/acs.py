"""American Chemical Society provider client."""

from __future__ import annotations

from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.provider_rules import (
    ATYPON_FRONT_MATTER_CONTAINS_TOKENS,
    ATYPON_FRONT_MATTER_EXACT_TEXTS,
    DomHooks,
    ProviderCleanupRules,
    ProviderFrontMatterRules,
    ProviderHtmlRules,
)
from ..provider_catalog import (
    ATYPON_DEFAULT_PDF_PATH_TEMPLATES,
    ProviderRouteSpec,
    ProviderSpec,
)
from . import _acs_html, browser_workflow
from ._registry import ProviderBundle, register_provider_bundle


# SITE_UI_COPY_REGRESSION_MARKER: ACS Publications site UI copy owned by the
# provider cleanup policy; rerun extraction-rules validation when this list changes.
ACS_MARKDOWN_PROMO_TOKENS = (
    "download citation",
    "download hi-res image",
    "download to ms-powerpoint",
    "article recommendations",
    "article views",
)
ACS_FRONT_MATTER_EXACT_TEXTS = (
    *ATYPON_FRONT_MATTER_EXACT_TEXTS,
    "acs publications",
    "american chemical society",
)
ACS_FRONT_MATTER_PUBLICATION_KEYWORDS = ("acs", "acs omega")
# SITE_UI_COPY_REGRESSION_MARKER: ACS Publications post-article chrome owned by
# the provider cleanup policy; rerun extraction-rules validation when this list changes.
ACS_POST_CONTENT_BREAK_TOKENS = (
    "article recommendations",
    "cited by",
    "article views",
    "altmetric",
)
ACS_SITE_RULE_OVERRIDES = {
    "candidate_selectors": [
        ".article_content",
        ".hlFld-Fulltext",
        ".article-body",
        "#articleBody",
    ],
    "remove_selectors": [
        ".articleMetrics",
        ".article-tools",
        ".citationTools",
        ".rightsLink",
        ".article_content-leftRail",
        ".article_content-rightRail",
    ],
    "drop_keywords": {"article-metrics", "rightslink"},
    "drop_text": {"Download Citation", "Get e-Alerts"},
}


register_provider_bundle(
    ProviderBundle(
        catalog=ProviderSpec(
            name="acs",
            display_name="ACS",
            official=True,
            domains=("www.acs.org", "pubs.acs.org", "acs.org"),
            doi_prefixes=("10.1021/",),
            publisher_aliases=(
                "american chemical society",
                "american chemical society (acs)",
                "acs publications",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            client_factory_path="paper_fetch.providers.acs:AcsClient",
            status_order=15,
            base_domains=("pubs.acs.org",),
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
            name="acs",
            cleanup=ProviderCleanupRules(
                markdown_promo_tokens=ACS_MARKDOWN_PROMO_TOKENS,
                post_content_break_tokens=ACS_POST_CONTENT_BREAK_TOKENS,
            ),
            availability=AvailabilityPolicy(
                name="acs",
                site_rule_overrides=ACS_SITE_RULE_OVERRIDES,
                no_signals=True,
            ),
            front_matter=ProviderFrontMatterRules(
                exact_texts=ACS_FRONT_MATTER_EXACT_TEXTS,
                contains_tokens=ATYPON_FRONT_MATTER_CONTAINS_TOKENS,
                publication_keywords=ACS_FRONT_MATTER_PUBLICATION_KEYWORDS,
            ),
            dom_hooks=DomHooks(
                before_block_normalization=_acs_html.acs_before_block_normalization,
                body_container=_acs_html.acs_body_container,
            ),
        ),
        sources=("acs",),
    )
)


ACS_BROWSER_PROFILE = browser_workflow.make_atypon_browser_profile(
    "acs",
    fallback_author_extractor=_acs_html.extract_authors,
    policy=browser_workflow.BrowserWorkflowPolicy(
        blocked_resource_types=("image", "font", "media"),
        preflight_html_reuse=True,
        direct_figure_page_fallback=True,
    ),
)


class AcsClient(browser_workflow.BrowserWorkflowClient):
    name = ACS_BROWSER_PROFILE.name
    profile = ACS_BROWSER_PROFILE
