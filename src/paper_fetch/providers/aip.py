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
    ProviderRouteSpec,
    ProviderSpec,
    host_matches_domain,
)
from ..publisher_identity import normalize_doi
from ..utils import extend_unique, normalize_text
from . import _aip_html, browser_workflow
from ._registry import ProviderBundle


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

_PROVIDER_SPEC = ProviderSpec(
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
    status_order=17,
    base_domains=("pubs.aip.org",),
    html_path_templates=("/doi/full/{doi}", "/doi/{doi}"),
    pdf_path_templates=ATYPON_DEFAULT_PDF_PATH_TEMPLATES,
    crossref_pdf_position=0,
    body_text_thresholds=BodyTextThresholds(min_chars=1200),
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

AIP_BROWSER_PROFILE = browser_workflow.make_atypon_browser_profile(
    "aip",
    catalog=_PROVIDER_SPEC,
    fallback_author_extractor=_aip_html.extract_authors,
    policy=browser_workflow.BrowserWorkflowPolicy(
        fast_html_attempt=False,
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
            extend_unique(candidates, [landing])
        extend_unique(candidates, super().html_candidates(normalized_doi, metadata))
        return candidates


def _is_aip_url(value: str | None) -> bool:
    hostname = urlparse(normalize_text(value)).hostname
    return any(
        host_matches_domain(hostname, domain) for domain in _PROVIDER_SPEC.domains
    )


__all__ = ["AipClient"]


PROVIDER_BUNDLE = ProviderBundle(
    client_factory=AipClient,
    catalog=_PROVIDER_SPEC,
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
