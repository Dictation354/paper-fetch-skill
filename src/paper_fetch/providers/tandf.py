"""Taylor & Francis Online provider client."""

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
)
from ..publisher_identity import normalize_doi
from ..reason_codes import PDF_FALLBACK
from ..utils import extend_unique, normalize_text
from . import _tandf_html, browser_workflow
from ._registry import ProviderBundle
from .base import RawFulltextPayload

_PROVIDER_SPEC = ProviderSpec(
    name="tandf",
    display_name="Taylor & Francis Online",
    official=True,
    domains=("tandfonline.com", "www.tandfonline.com"),
    domain_suffixes=("tandfonline.com",),
    doi_prefixes=("10.1080/",),
    publisher_aliases=(
        "taylor & francis",
        "taylor & francis group",
        "informa uk limited",
    ),
    asset_default="body",
    probe_capability="routing_signal",
    provider_managed_abstract_only=True,
    status_order=19,
    base_domains=("www.tandfonline.com",),
    html_path_templates=("/doi/full/{doi}", "/doi/abs/{doi}", "/doi/{doi}"),
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

TANDF_BROWSER_PROFILE = browser_workflow.make_atypon_browser_profile(
    "tandf",
    catalog=_PROVIDER_SPEC,
    article_source_name="tandf_html",
    fallback_author_extractor=_tandf_html.extract_authors,
    policy=browser_workflow.BrowserWorkflowPolicy(
        blocked_resource_types=("image", "font", "media"),
    ),
)


class TandfClient(browser_workflow.BrowserWorkflowClient):
    name = TANDF_BROWSER_PROFILE.name
    profile = TANDF_BROWSER_PROFILE
    route_order = (
        "article_html",
        "pdf_fallback",
        "abstract_only",
        "metadata_only",
    )

    def html_candidates(self, doi: str, metadata: Mapping[str, Any]) -> list[str]:
        normalized_doi = normalize_doi(doi)
        candidates: list[str] = []
        landing = normalize_text(str(metadata.get("landing_page_url") or ""))
        if _is_tandf_url(landing):
            extend_unique(candidates, [landing])
        extend_unique(candidates, super().html_candidates(normalized_doi, metadata))
        return candidates

    def extract_markdown(
        self,
        html_text: str,
        final_url: str,
        *,
        metadata: Mapping[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        return super().extract_markdown(
            _tandf_html.prepare_html_for_extraction(html_text),
            final_url,
            metadata=metadata,
        )

    def article_source_for_payload(self, raw_payload: RawFulltextPayload) -> str:
        content = raw_payload.content
        route = normalize_text(
            content.route_kind if content is not None else ""
        ).lower()
        if route == PDF_FALLBACK:
            return "tandf_pdf"
        return "tandf_html"


def _is_tandf_url(value: str | None) -> bool:
    parsed = urlparse(normalize_text(value))
    host = normalize_text(parsed.hostname or "").lower()
    return host == "tandfonline.com" or host.endswith(".tandfonline.com")


__all__ = ["TandfClient"]


PROVIDER_BUNDLE = ProviderBundle(
    client_factory=TandfClient,
    catalog=_PROVIDER_SPEC,
    html_rules=ProviderHtmlRules(
        name="tandf",
        cleanup=ProviderCleanupRules(
            markdown_promo_tokens=_tandf_html.TANDF_MARKDOWN_PROMO_TOKENS,
            extraction_cleanup_selectors=tuple(
                _tandf_html.TANDF_SITE_RULE_OVERRIDES["remove_selectors"]
            ),
            post_content_break_tokens=_tandf_html.TANDF_POST_CONTENT_BREAK_TOKENS,
        ),
        front_matter=ProviderFrontMatterRules(
            exact_texts=(
                *ATYPON_FRONT_MATTER_EXACT_TEXTS,
                *_tandf_html.TANDF_FRONT_MATTER_EXACT_TEXTS,
            ),
            contains_tokens=(
                *ATYPON_FRONT_MATTER_CONTAINS_TOKENS,
                *_tandf_html.TANDF_FRONT_MATTER_CONTAINS_TOKENS,
            ),
            publication_keywords=(_tandf_html.TANDF_FRONT_MATTER_PUBLICATION_KEYWORDS),
        ),
        assets=ProviderAssetRules(
            supplementary_text_tokens=(_tandf_html.TANDF_SUPPLEMENTARY_TEXT_TOKENS),
        ),
        availability=AvailabilityPolicy(
            name="tandf",
            site_rule_overrides=_tandf_html.TANDF_SITE_RULE_OVERRIDES,
        ),
        dom_hooks=DomHooks(
            before_block_normalization=(_tandf_html.tandf_before_block_normalization),
            body_container=_tandf_html.tandf_body_container,
            asset_body_container=_tandf_html.tandf_asset_body_container,
            asset_figure_extraction=(_tandf_html.tandf_asset_figure_extraction),
        ),
        markdown_hooks=MarkdownHooks(
            normalize_markdown=_tandf_html.tandf_normalize_markdown,
            classify_heading=_tandf_html.tandf_classify_heading,
        ),
    ),
    sources=("tandf_html", "tandf_pdf"),
)
