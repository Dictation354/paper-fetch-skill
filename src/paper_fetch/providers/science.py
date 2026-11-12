"""Science provider client."""

from __future__ import annotations

from ._definitions import PROVIDER_DEFINITIONS

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
from ..quality.html_signals import (
    SCIENCE_AVAILABILITY_OVERRIDES,
    SCIENCE_SIGNAL_SET,
)
from . import _science_html, browser_workflow
from ._registry import BrowserAssetPolicy, BrowserPagePolicy, ProviderBundle


_PROVIDER_DEFINITION = PROVIDER_DEFINITIONS["science"]

_PROVIDER_SPEC = _PROVIDER_DEFINITION.catalog

SCIENCE_BROWSER_PROFILE = browser_workflow.make_atypon_browser_profile(
    "science",
    catalog=_PROVIDER_SPEC,
    fallback_author_extractor=_science_html.extract_authors,
    policy=browser_workflow.BrowserWorkflowPolicy(
        fast_html_attempt=False,
        blocked_resource_types=("image", "font", "media"),
    ),
)


class ScienceClient(browser_workflow.BrowserWorkflowClient):
    name = SCIENCE_BROWSER_PROFILE.name
    profile = SCIENCE_BROWSER_PROFILE


PROVIDER_BUNDLE = ProviderBundle(
    browser_asset_policy=BrowserAssetPolicy(click_supplements=True),
    browser_page_policy=BrowserPagePolicy(
        document_hosts=("science.org", "www.science.org")
    ),
    client_factory=ScienceClient,
    catalog=_PROVIDER_SPEC,
    html_rules=ProviderHtmlRules(
        name=_PROVIDER_DEFINITION.rules_name,
        aliases=_PROVIDER_DEFINITION.rules_aliases,
        cleanup=ProviderCleanupRules(
            post_content_break_tokens=SCIENCE_POST_CONTENT_BREAK_TOKENS,
        ),
        availability=AvailabilityPolicy(
            paywall_gate_selectors="#bodymatter > .core-container > .denial-block",
            paywall_gate_pattern=r"view all access options to continue reading this article",
            paywall_paragraph_selector="p, [role='paragraph']",
            paywall_entitlement_signals=("aaas_page_type_denial",),
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
            render_table=_science_html.render_table_with_missing_trailing_cells,
            body_container=_science_html.science_body_container,
            asset_body_container=_science_html.science_asset_body_container,
            asset_figure_extraction=_science_html.science_asset_figure_extraction,
        ),
        markdown_hooks=MarkdownHooks(
            classify_heading=_science_html.science_classify_heading,
            normalize_markdown=_science_html.science_normalize_markdown,
            keep_unknown_abstract_block=_science_html.science_keep_unknown_abstract_block,
            keep_leading_auxiliary_block=_science_html.science_keep_leading_auxiliary_block,
        ),
    ),
    sources=_PROVIDER_DEFINITION.sources,
)
