"""MDPI provider client."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.provider_rules import (
    ProviderAssetRules,
    ProviderCleanupRules,
    ProviderFrontMatterRules,
    ProviderHtmlRules,
)
from ..mdpi_url import is_mdpi_url, mdpi_landing_url_from_doi
from ..models import AssetProfile
from ..provider_catalog import ProviderRouteSpec, ProviderSpec
from ..publisher_identity import normalize_doi
from ..reason_codes import PDF_FALLBACK
from ..runtime import RuntimeContext
from ..utils import empty_asset_results, normalize_text
from . import _mdpi_html, browser_workflow
from ._registry import ProviderBundle, ProviderRenderPolicy, register_provider_bundle
from .base import RawFulltextPayload
from .browser_runtime import BrowserHtmlReadiness
from .browser_workflow.shared import extract_pdf_url_from_crossref


register_provider_bundle(
    ProviderBundle(
        catalog=ProviderSpec(
            name="mdpi",
            display_name="MDPI",
            official=True,
            domains=("www.mdpi.com", "mdpi.com"),
            doi_prefixes=("10.3390/",),
            publisher_aliases=("mdpi", "mdpi ag"),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=False,
            client_factory_path="paper_fetch.providers.mdpi:MdpiClient",
            status_order=10,
            base_domains=("www.mdpi.com",),
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
            name="mdpi",
            noise_profile=_mdpi_html.MDPI_NOISE_PROFILE,
            cleanup=ProviderCleanupRules(
                markdown_promo_tokens=_mdpi_html.MDPI_MARKDOWN_PROMO_TOKENS,
                extraction_cleanup_selectors=_mdpi_html.MDPI_EXTRACTION_CLEANUP_SELECTORS,
                post_content_break_tokens=_mdpi_html.MDPI_POST_CONTENT_BREAK_TOKENS,
            ),
            front_matter=ProviderFrontMatterRules(
                exact_texts=_mdpi_html.MDPI_FRONT_MATTER_EXACT_TEXTS,
                contains_tokens=_mdpi_html.MDPI_FRONT_MATTER_CONTAINS_TOKENS,
                publication_keywords=("mdpi",),
            ),
            assets=ProviderAssetRules(
                supplementary_text_tokens=_mdpi_html.MDPI_SUPPLEMENTARY_TEXT_TOKENS,
            ),
            availability=AvailabilityPolicy(
                name="mdpi",
                site_rule_overrides=_mdpi_html.MDPI_SITE_RULE_OVERRIDES,
                no_signals=True,
            ),
        ),
        sources=("mdpi_html", "mdpi_pdf"),
        render_policy=ProviderRenderPolicy(
            mark_inline_assets=_mdpi_html.mark_inline_assets,
        ),
    )
)


MDPI_BROWSER_PROFILE = browser_workflow.make_browser_profile(
    "mdpi",
    article_source_name="mdpi_html",
    fallback_author_extractor=_mdpi_html.extract_authors,
    html_readiness=BrowserHtmlReadiness(wait_for_article_body=True),
    policy=browser_workflow.BrowserWorkflowPolicy(
        blocked_resource_types=("image", "font", "media"),
        preflight_html_reuse=True,
        retry_incomplete_html_candidates=True,
    ),
)


def _mdpi_landing_url(
    metadata: Mapping[str, Any], doi: str | None = None
) -> str | None:
    landing = normalize_text(str(metadata.get("landing_page_url") or ""))
    if is_mdpi_url(landing):
        return landing
    derived = mdpi_landing_url_from_doi(doi or str(metadata.get("doi") or ""))
    if derived:
        return derived
    return None


def _metadata_pdf_urls(metadata: Mapping[str, Any]) -> list[str]:
    urls: list[str] = []
    for item in metadata.get("fulltext_links") or ():
        if not isinstance(item, Mapping):
            continue
        content_type = normalize_text(str(item.get("content_type") or "")).lower()
        url = normalize_text(str(item.get("url") or ""))
        if url and ("pdf" in content_type or url.rstrip("/").endswith("/pdf")):
            urls.append(url)
    crossref_pdf = extract_pdf_url_from_crossref(metadata)
    if crossref_pdf:
        urls.append(crossref_pdf)
    return list(dict.fromkeys(urls))


class MdpiClient(browser_workflow.BrowserWorkflowClient):
    name = MDPI_BROWSER_PROFILE.name
    profile = MDPI_BROWSER_PROFILE
    route_order = ("article_html", "pdf_fallback", "metadata_only")
    article_asset_failure_warning = False

    def html_candidates(self, doi: str, metadata: Mapping[str, Any]) -> list[str]:
        normalized_doi = normalize_doi(doi)
        candidates: list[str] = []
        landing = _mdpi_landing_url(metadata, normalized_doi)
        if landing:
            candidates.append(landing)
        if normalized_doi:
            candidates.append(f"https://doi.org/{normalized_doi}")
        return list(dict.fromkeys(candidate for candidate in candidates if candidate))

    def pdf_candidates(self, doi: str, metadata: Mapping[str, Any]) -> list[str]:
        normalized_doi = normalize_doi(doi)
        candidates: list[str] = []
        landing = _mdpi_landing_url(
            metadata,
            str(metadata.get("doi") or normalized_doi or ""),
        )
        pdf_from_landing = _mdpi_html.mdpi_pdf_url_from_landing_url(landing)
        if pdf_from_landing:
            candidates.append(pdf_from_landing)
        candidates.extend(_metadata_pdf_urls(metadata))
        return list(dict.fromkeys(candidate for candidate in candidates if candidate))

    def extract_markdown(
        self,
        html_text: str,
        final_url: str,
        *,
        metadata: Mapping[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        return _mdpi_html.extract_markdown(
            html_text,
            final_url,
            metadata=metadata,
        )

    def article_source_for_payload(self, raw_payload: RawFulltextPayload) -> str:
        content = raw_payload.content
        route = normalize_text(
            content.route_kind if content is not None else ""
        ).lower()
        if route == PDF_FALLBACK:
            return "mdpi_pdf"
        return "mdpi_html"

    def download_related_assets(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        output_dir,
        *,
        asset_profile: AssetProfile = "all",
        context: RuntimeContext | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        context = self._runtime_context(context, output_dir=output_dir)
        if output_dir is None or asset_profile == "none":
            return empty_asset_results()
        content = raw_payload.content
        if (
            normalize_text(content.route_kind if content is not None else "").lower()
            != "html"
        ):
            return empty_asset_results()

        normalized_doi = normalize_doi(str(metadata.get("doi") or doi or ""))
        if not normalized_doi:
            return empty_asset_results()
        html_text = raw_payload.body.decode("utf-8", errors="replace")
        assets = _mdpi_html.extract_scoped_html_assets(
            html_text,
            raw_payload.source_url,
            asset_profile=asset_profile,
        )
        if not assets:
            return empty_asset_results()
        return self._download_browser_backed_related_assets(
            doi,
            metadata,
            raw_payload,
            output_dir,
            asset_profile=asset_profile,
            context=context,
            assets=assets,
        )
