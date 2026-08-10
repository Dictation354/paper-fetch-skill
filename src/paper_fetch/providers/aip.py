"""AIP Publishing provider client."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping
from urllib.parse import urlparse

from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.provider_rules import (
    ATYPON_FRONT_MATTER_CONTAINS_TOKENS,
    ATYPON_FRONT_MATTER_EXACT_TEXTS,
    DomHooks,
    MarkdownHooks,
    ProviderAssetRules,
    ProviderCleanupRules,
    ProviderFrontMatterRules,
    ProviderHtmlRules,
)
from ..provider_catalog import (
    ATYPON_DEFAULT_PDF_PATH_TEMPLATES,
    BodyTextThresholds,
    ProviderSpec,
)
from ..publisher_identity import normalize_doi
from ..reason_codes import PDF_FALLBACK
from ..utils import normalize_text
from . import _aip_html, browser_workflow
from ._registry import ProviderBundle, register_provider_bundle
from .base import RawFulltextPayload


# SITE_UI_COPY_REGRESSION_MARKER: AIP article navigation/action labels owned by provider cleanup policy.
# STRUCTURAL_UI_COPY_HOOK: provider cleanup removes these only from AIP article chrome.
AIP_MARKDOWN_PROMO_TOKENS = (
    "close modal",
    "download citation",
    "article navigation",
    "article contents",
    "article metrics",
    "open figure viewer",
    "sign in or purchase",
    "view large",
)
AIP_FRONT_MATTER_EXACT_TEXTS = (
    *ATYPON_FRONT_MATTER_EXACT_TEXTS,
    "aip publishing",
    "aip advances",
    "journal of applied physics",
    "applied physics letters",
    "topics",
)
AIP_FRONT_MATTER_PUBLICATION_KEYWORDS = (
    "aip",
    "aip publishing",
    "aip advances",
    "journal of applied physics",
    "applied physics letters",
)
# SITE_UI_COPY_REGRESSION_MARKER: AIP post-article chrome labels owned by provider cleanup policy.
# STRUCTURAL_UI_COPY_HOOK: provider cleanup uses these as post-body boundaries, not global denylist text.
AIP_POST_CONTENT_BREAK_TOKENS = (
    "article metrics",
    "views",
    "cited by",
    "related articles",
    "recommended",
)
AIP_SITE_RULE_OVERRIDES = {
    "candidate_selectors": [
        "#itemFullTextId",
        "#html_fulltext",
        ".hlFld-Fulltext",
        ".article-fulltext",
        ".article-content",
        "article",
    ],
    "remove_selectors": [
        ".article-metrics",
        ".article-tools",
        ".article-navigation",
        ".citationTools",
        ".rightsLink",
        ".relatedContent",
    ],
    "drop_keywords": {"article-metrics", "citation-tools", "rightslink"},
    "drop_text": {
        "Close modal",
        "Download Citation",
        "Article Navigation",
        "Open figure viewer",
        "View large",
    },
}
AIP_SUPPLEMENTARY_TEXT_TOKENS = (
    "supplementary material",
    "supplemental material",
    "supporting information",
)


register_provider_bundle(
    ProviderBundle(
        catalog=ProviderSpec(
            name="aip",
            display_name="AIP Publishing",
            official=True,
            domains=("pubs.aip.org",),
            doi_prefixes=("10.1063/",),
            publisher_aliases=(
                "aip publishing",
                "aip publishing llc",
                "american institute of physics",
                "aip",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            client_factory_path="paper_fetch.providers.aip:AipClient",
            status_order=17,
            base_domains=("pubs.aip.org",),
            html_path_templates=("/doi/full/{doi}", "/doi/{doi}"),
            pdf_path_templates=ATYPON_DEFAULT_PDF_PATH_TEMPLATES,
            crossref_pdf_position=0,
            requires_browser_runtime=True,
            body_text_thresholds=BodyTextThresholds(min_chars=1200),
        ),
        html_rules=ProviderHtmlRules(
            name="aip",
            cleanup=ProviderCleanupRules(
                markdown_promo_tokens=AIP_MARKDOWN_PROMO_TOKENS,
                extraction_cleanup_selectors=tuple(
                    AIP_SITE_RULE_OVERRIDES["remove_selectors"]
                ),
                post_content_break_tokens=AIP_POST_CONTENT_BREAK_TOKENS,
            ),
            front_matter=ProviderFrontMatterRules(
                exact_texts=AIP_FRONT_MATTER_EXACT_TEXTS,
                contains_tokens=ATYPON_FRONT_MATTER_CONTAINS_TOKENS,
                publication_keywords=AIP_FRONT_MATTER_PUBLICATION_KEYWORDS,
            ),
            assets=ProviderAssetRules(
                supplementary_text_tokens=AIP_SUPPLEMENTARY_TEXT_TOKENS,
            ),
            availability=AvailabilityPolicy(
                name="aip",
                site_rule_overrides=AIP_SITE_RULE_OVERRIDES,
                no_signals=True,
            ),
            dom_hooks=DomHooks(
                before_block_normalization=_aip_html.aip_before_block_normalization,
                body_container=_aip_html.aip_body_container,
            ),
            markdown_hooks=MarkdownHooks(
                normalize_markdown=_aip_html.aip_normalize_markdown,
                classify_heading=_aip_html.aip_classify_heading,
            ),
        ),
        sources=("aip_html", "aip_pdf"),
    )
)


AIP_BROWSER_PROFILE = browser_workflow.make_atypon_browser_profile(
    "aip",
    article_source_name="aip_html",
    fallback_author_extractor=_aip_html.extract_authors,
    policy=browser_workflow.BrowserWorkflowPolicy(
        preflight_html_reuse=False,
        persistent_storage_state=False,
    ),
)


class AipClient(browser_workflow.BrowserWorkflowClient):
    name = AIP_BROWSER_PROFILE.name
    profile = AIP_BROWSER_PROFILE

    def html_candidates(self, doi: str, metadata: Mapping[str, Any]) -> list[str]:
        normalized_doi = normalize_doi(doi)
        candidates: list[str] = []
        landing = normalize_text(str(metadata.get("landing_page_url") or ""))
        if _is_aip_url(landing):
            _append_unique(candidates, landing)
        for candidate in super().html_candidates(normalized_doi, metadata):
            _append_unique(candidates, candidate)
        return candidates

    def article_source_for_payload(self, raw_payload: RawFulltextPayload) -> str:
        content = raw_payload.content
        route = normalize_text(
            content.route_kind if content is not None else ""
        ).lower()
        if route == PDF_FALLBACK:
            return "aip_pdf"
        return "aip_html"


def _is_aip_url(value: str | None) -> bool:
    parsed = urlparse(normalize_text(value))
    host = normalize_text(parsed.hostname or "").lower()
    return host == "pubs.aip.org" or host.endswith(".pubs.aip.org")


def _append_unique(values: list[str], candidate: str | None) -> None:
    normalized = normalize_text(candidate)
    if normalized and normalized not in values:
        values.append(normalized)


__all__ = ["AipClient"]
