"""American Meteorological Society provider client."""

from __future__ import annotations

from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.provider_rules import (
    AMS_DOM_POSTPROCESS_CLEANUP_SELECTORS,
    AMS_FRONT_MATTER_EXACT_TEXTS,
    AMS_FRONT_MATTER_PUBLICATION_KEYWORDS,
    AMS_MARKDOWN_PROMO_TOKENS,
    AMS_POST_CONTENT_BREAK_TOKENS,
    AMS_SITE_RULE_OVERRIDES,
    ATYPON_FRONT_MATTER_CONTAINS_TOKENS,
    DomHooks,
    MarkdownHooks,
    ProviderCleanupRules,
    ProviderFormulaRules,
    ProviderFrontMatterRules,
    ProviderHtmlRules,
)
from ..provider_catalog import ProviderSpec
from ..quality.html_signals import AMS_TEXT_MARKER_SIGNAL_SET
from ..utils import normalize_text
from . import _ams_html, browser_workflow
from .base import RawFulltextPayload
from ._registry import ProviderBundle, register_provider_bundle
from ..reason_codes import PDF_FALLBACK


register_provider_bundle(
    ProviderBundle(
        catalog=ProviderSpec(
            name="ams",
            display_name="AMS",
            official=True,
            domains=("journals.ametsoc.org", "ametsoc.org"),
            doi_prefixes=("10.1175/",),
            publisher_aliases=(
                "american meteorological society",
                "ams",
                "american meteorological society (ams)",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            client_factory_path="paper_fetch.providers.ams:AmsClient",
            status_order=9,
            base_domains=("journals.ametsoc.org",),
            crossref_pdf_position=0,
            requires_browser_runtime=True,
        ),
        html_rules=ProviderHtmlRules(
            name="ams",
            cleanup=ProviderCleanupRules(
                markdown_promo_tokens=AMS_MARKDOWN_PROMO_TOKENS,
                dom_postprocess_cleanup_selectors=AMS_DOM_POSTPROCESS_CLEANUP_SELECTORS,
                post_content_break_tokens=AMS_POST_CONTENT_BREAK_TOKENS,
            ),
            availability=AvailabilityPolicy(
                name="ams",
                site_rule_overrides=AMS_SITE_RULE_OVERRIDES,
                text_marker_signal_set=AMS_TEXT_MARKER_SIGNAL_SET,
            ),
            front_matter=ProviderFrontMatterRules(
                exact_texts=AMS_FRONT_MATTER_EXACT_TEXTS,
                contains_tokens=ATYPON_FRONT_MATTER_CONTAINS_TOKENS,
                publication_keywords=AMS_FRONT_MATTER_PUBLICATION_KEYWORDS,
            ),
            formula=ProviderFormulaRules(
                container_tokens=("formula",),
                display_selectors=("div.formula",),
            ),
            dom_hooks=DomHooks(
                before_block_normalization=_ams_html.ams_before_block_normalization,
                after_block_normalization=_ams_html.ams_after_block_normalization,
                body_container=_ams_html.ams_body_container,
                asset_body_container=_ams_html.ams_asset_body_container,
                asset_figure_extraction=_ams_html.ams_asset_figure_extraction,
            ),
            markdown_hooks=MarkdownHooks(
                normalize_markdown=_ams_html.ams_normalize_markdown,
                classify_heading=_ams_html.ams_classify_heading,
                keep_unknown_abstract_block=_ams_html.ams_keep_unknown_abstract_block,
            ),
        ),
        sources=("ams_html", "ams_pdf"),
    )
)


AMS_BROWSER_PROFILE = browser_workflow.make_atypon_browser_profile(
    "ams",
    fallback_author_extractor=_ams_html.extract_authors,
    direct_http_html_preflight=True,
)


class AmsClient(browser_workflow.BrowserWorkflowClient):
    name = AMS_BROWSER_PROFILE.name
    profile = AMS_BROWSER_PROFILE

    def article_source_for_payload(self, raw_payload: RawFulltextPayload) -> str:
        content = raw_payload.content
        route = normalize_text(content.route_kind if content is not None else "").lower()
        if route == PDF_FALLBACK:
            return "ams_pdf"
        return "ams_html"

    def to_article_model(self, *args, **kwargs):
        article = super().to_article_model(*args, **kwargs)
        return _ams_html.normalize_article_model(article)
