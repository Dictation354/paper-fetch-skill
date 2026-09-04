"""Annual Reviews provider client."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping
from urllib.parse import quote, urlparse

from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.provider_rules import (
    ProviderAssetRules,
    ProviderCleanupRules,
    ProviderFrontMatterRules,
    ProviderHtmlRules,
)
from ..models import AssetProfile
from ..provider_catalog import (
    BodyTextThresholds,
    ProviderRouteSpec,
    ProviderSpec,
    host_matches_domain,
)
from ..publisher_identity import normalize_doi
from ..runtime import RuntimeContext
from ..utils import empty_asset_results, extend_unique, normalize_text
from . import _annualreviews_html, browser_workflow
from ._pdf_candidates import build_direct_pdf_candidates
from ._registry import ProviderBundle
from .base import RawFulltextPayload

_PROVIDER_SPEC = ProviderSpec(
    name="annualreviews",
    display_name="Annual Reviews",
    official=True,
    domains=("annualreviews.org", "www.annualreviews.org"),
    doi_prefixes=("10.1146/",),
    publisher_aliases=(
        "annual reviews",
        "annual reviews inc",
        "annual reviews inc.",
    ),
    asset_default="body",
    probe_capability="routing_signal",
    provider_managed_abstract_only=True,
    status_order=12,
    base_domains=("www.annualreviews.org",),
    html_path_templates=(
        "/content/journals/{doi}",
        "/doi/{doi}",
    ),
    pdf_path_templates=("/doi/pdf/{doi}",),
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
            concurrency=2,
            asset_scope="body",
        ),
    ),
)

ANNUALREVIEWS_BROWSER_PROFILE = browser_workflow.make_browser_profile(
    "annualreviews",
    catalog=_PROVIDER_SPEC,
    fallback_author_extractor=_annualreviews_html.extract_authors,
    policy=browser_workflow.BrowserWorkflowPolicy(
        blocked_resource_types=("image", "font", "media"),
        direct_figure_page_fallback=True,
    ),
)


def _is_annualreviews_url(value: str | None) -> bool:
    hostname = urlparse(normalize_text(value)).hostname
    return any(
        host_matches_domain(hostname, domain) for domain in _PROVIDER_SPEC.domains
    )


class AnnualreviewsClient(browser_workflow.BrowserWorkflowClient):
    name = ANNUALREVIEWS_BROWSER_PROFILE.name
    profile = ANNUALREVIEWS_BROWSER_PROFILE
    route_order = (
        "landing_html",
        "article_html",
        "pdf_fallback",
        "abstract_only",
        "metadata_only",
    )

    def html_candidates(self, doi: str, metadata: Mapping[str, Any]) -> list[str]:
        normalized_doi = normalize_doi(doi)
        candidates: list[str] = []
        landing = normalize_text(str(metadata.get("landing_page_url") or ""))
        if _is_annualreviews_url(landing):
            extend_unique(candidates, [landing])
        if normalized_doi:
            quoted = quote(normalized_doi, safe="/")
            extend_unique(
                candidates,
                [
                    f"https://www.annualreviews.org/content/journals/{quoted}",
                    f"https://www.annualreviews.org/doi/{quoted}",
                    f"https://doi.org/{quoted}",
                ],
            )
        return candidates

    def pdf_candidates(self, doi: str, metadata: Mapping[str, Any]) -> list[str]:
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            return []
        source_url = normalize_text(
            str(metadata.get("landing_page_url") or "")
        ) or _annualreviews_html.direct_article_url(normalized_doi)
        return build_direct_pdf_candidates(
            metadata,
            source_url=source_url,
            direct_pdf_url=_annualreviews_html.direct_pdf_url(normalized_doi),
        )

    def extract_markdown(
        self,
        html_text: str,
        final_url: str,
        *,
        metadata: Mapping[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        return _annualreviews_html.extract_markdown(
            html_text,
            final_url,
            metadata=metadata,
        )

    def to_article_model(
        self,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
        context: RuntimeContext | None = None,
    ):
        effective_metadata = dict(metadata)
        content = raw_payload.content
        extraction = (
            content.diagnostics.get("extraction")
            if content is not None and isinstance(content.diagnostics, Mapping)
            else None
        )
        title = (
            normalize_text(str(extraction.get("title") or ""))
            if isinstance(extraction, Mapping)
            else ""
        )
        doi = normalize_doi(str(effective_metadata.get("doi") or ""))
        current_title = normalize_text(str(effective_metadata.get("title") or ""))
        if title and (
            not current_title or (doi and normalize_doi(current_title) == doi)
        ):
            effective_metadata["title"] = title
        return super().to_article_model(
            effective_metadata,
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
            context=context,
        )

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
        assets = _annualreviews_html.extract_scoped_html_assets(
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


__all__ = ["AnnualreviewsClient"]


PROVIDER_BUNDLE = ProviderBundle(
    client_factory=AnnualreviewsClient,
    catalog=_PROVIDER_SPEC,
    html_rules=ProviderHtmlRules(
        name="annualreviews",
        noise_profile=_annualreviews_html.ANNUALREVIEWS_NOISE_PROFILE,
        cleanup=ProviderCleanupRules(
            markdown_promo_tokens=_annualreviews_html.ANNUALREVIEWS_MARKDOWN_PROMO_TOKENS,
            extraction_cleanup_selectors=_annualreviews_html.ANNUALREVIEWS_EXTRACTION_CLEANUP_SELECTORS,
            post_content_break_tokens=_annualreviews_html.ANNUALREVIEWS_POST_CONTENT_BREAK_TOKENS,
        ),
        front_matter=ProviderFrontMatterRules(
            exact_texts=_annualreviews_html.ANNUALREVIEWS_FRONT_MATTER_EXACT_TEXTS,
            contains_tokens=_annualreviews_html.ANNUALREVIEWS_FRONT_MATTER_CONTAINS_TOKENS,
            publication_keywords=("annual reviews",),
        ),
        assets=ProviderAssetRules(
            supplementary_text_tokens=_annualreviews_html.ANNUALREVIEWS_SUPPLEMENTARY_TEXT_TOKENS,
        ),
        availability=AvailabilityPolicy(
            name="annualreviews",
            site_rule_overrides=_annualreviews_html.ANNUALREVIEWS_SITE_RULE_OVERRIDES,
        ),
    ),
    sources=("annualreviews_html", "annualreviews_pdf"),
)
