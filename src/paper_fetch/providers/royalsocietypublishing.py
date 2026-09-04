"""Royal Society Publishing browser-workflow provider client."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping
from urllib.parse import quote, urlparse

from ..extraction.html.assets import filter_assets_for_profile
from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.provider_rules import (
    ProviderAssetRules,
    ProviderCleanupRules,
    ProviderFrontMatterRules,
    ProviderHtmlRules,
)
from ..extraction.html.signals import HtmlExtractionFailure
from ..models import AssetProfile
from ..provider_catalog import (
    BodyTextThresholds,
    ProviderRouteSpec,
    ProviderSpec,
    host_matches_domain,
)
from ..publisher_identity import normalize_doi
from ..quality.html_availability import (
    HtmlQualityAssessor,
    availability_failure_message,
)
from ..runtime import RuntimeContext
from ..utils import empty_asset_results, extend_unique, normalize_text
from . import _royalsocietypublishing_html as royal_html
from . import browser_workflow
from ._pdf_candidates import build_direct_pdf_candidates
from ._registry import ProviderBundle
from .base import RawFulltextPayload

_PROVIDER_SPEC = ProviderSpec(
    name="royalsocietypublishing",
    display_name="Royal Society Publishing",
    official=True,
    domains=("royalsocietypublishing.org",),
    doi_prefixes=("10.1098/",),
    publisher_aliases=("the royal society", "royal society publishing"),
    asset_default="body",
    probe_capability="routing_signal",
    provider_managed_abstract_only=False,
    status_order=11,
    base_domains=("royalsocietypublishing.org",),
    html_path_templates=("/doi/{doi}",),
    pdf_path_templates=("/doi/pdf/{doi}",),
    body_text_thresholds=BodyTextThresholds(min_chars=800),
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

ROYAL_SOCIETY_BROWSER_PROFILE = browser_workflow.make_browser_profile(
    "royalsocietypublishing",
    catalog=_PROVIDER_SPEC,
    fallback_author_extractor=royal_html.extract_authors,
    policy=browser_workflow.BrowserWorkflowPolicy(
        blocked_resource_types=("image", "font", "media"),
        direct_figure_page_fallback=True,
    ),
)


def _is_royal_society_url(value: str | None) -> bool:
    hostname = urlparse(normalize_text(value)).hostname
    return any(
        host_matches_domain(hostname, domain) for domain in _PROVIDER_SPEC.domains
    )


class RoyalsocietypublishingClient(browser_workflow.BrowserWorkflowClient):
    name = ROYAL_SOCIETY_BROWSER_PROFILE.name
    profile = ROYAL_SOCIETY_BROWSER_PROFILE
    route_order = (
        "article_html",
        "pdf_fallback",
        "metadata_only",
    )

    def html_candidates(self, doi: str, metadata: Mapping[str, Any]) -> list[str]:
        normalized_doi = normalize_doi(doi)
        candidates: list[str] = []
        landing = normalize_text(str(metadata.get("landing_page_url") or ""))
        if _is_royal_society_url(landing):
            extend_unique(candidates, [landing])
        if normalized_doi:
            quoted = quote(normalized_doi, safe="/")
            extend_unique(
                candidates,
                [
                    royal_html.direct_article_url(normalized_doi),
                    f"https://doi.org/{quoted}",
                ],
            )
        return candidates

    def pdf_candidates(self, doi: str, metadata: Mapping[str, Any]) -> list[str]:
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            return []
        landing = normalize_text(str(metadata.get("landing_page_url") or ""))
        source_url = (
            landing
            if _is_royal_society_url(landing)
            else royal_html.direct_article_url(normalized_doi)
        )
        return build_direct_pdf_candidates(
            metadata,
            source_url=source_url,
            direct_pdf_url=royal_html.direct_pdf_url(normalized_doi),
        )

    def extract_markdown(
        self,
        html_text: str,
        final_url: str,
        *,
        metadata: Mapping[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        extraction = royal_html.extract_markdown(
            html_text,
            final_url,
            metadata=metadata,
            asset_profile="all",
        )
        title = normalize_text(str(extraction.metadata.get("title") or ""))
        diagnostics = HtmlQualityAssessor(self.name).assess(
            extraction.markdown_text,
            extraction.metadata,
            html_text=extraction.html_text or html_text,
            title=title,
            final_url=final_url,
            section_hints=extraction.section_hints,
        )
        if not diagnostics.accepted:
            raise HtmlExtractionFailure(
                diagnostics.reason,
                availability_failure_message(diagnostics),
            )

        abstract_text = (
            normalize_text(str(extraction.abstract_sections[0].get("text") or ""))
            if extraction.abstract_sections
            else None
        )
        references = extraction.metadata.get("references")
        extraction_payload: dict[str, Any] = {
            "title": title or None,
            "metadata": dict(extraction.metadata),
            "abstract_text": abstract_text,
            "abstract_sections": extraction.abstract_sections,
            "section_hints": extraction.section_hints,
            "availability_diagnostics": diagnostics.to_dict(),
            "extracted_authors": royal_html.extract_authors(html_text),
            "references": references if isinstance(references, list) else [],
            "extracted_assets": extraction.extracted_assets,
        }
        return extraction.markdown_text, extraction_payload

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
        extracted_metadata = (
            extraction.get("metadata") if isinstance(extraction, Mapping) else None
        )
        if isinstance(extracted_metadata, Mapping):
            effective_metadata = dict(extracted_metadata)
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

        extraction = (
            content.diagnostics.get("extraction")
            if content is not None and isinstance(content.diagnostics, Mapping)
            else None
        )
        extracted_assets = (
            extraction.get("extracted_assets")
            if isinstance(extraction, Mapping)
            else None
        )
        if not isinstance(extracted_assets, list):
            return empty_asset_results()
        assets = filter_assets_for_profile(
            [item for item in extracted_assets if isinstance(item, Mapping)],
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


__all__ = ["RoyalsocietypublishingClient"]


PROVIDER_BUNDLE = ProviderBundle(
    client_factory=RoyalsocietypublishingClient,
    catalog=_PROVIDER_SPEC,
    html_rules=ProviderHtmlRules(
        name="royalsocietypublishing",
        cleanup=ProviderCleanupRules(
            markdown_promo_tokens=royal_html.ROYAL_SOCIETY_MARKDOWN_PROMO_TOKENS,
            extraction_cleanup_selectors=royal_html.ROYAL_SOCIETY_EXTRACTION_CLEANUP_SELECTORS,
        ),
        front_matter=ProviderFrontMatterRules(
            exact_texts=royal_html.ROYAL_SOCIETY_FRONT_MATTER_EXACT_TEXTS,
            publication_keywords=("royal society", "royal society publishing"),
        ),
        assets=ProviderAssetRules(
            supplementary_text_tokens=royal_html.ROYAL_SOCIETY_SUPPLEMENTARY_TEXT_TOKENS,
        ),
        availability=AvailabilityPolicy(
            name="royalsocietypublishing",
        ),
    ),
    sources=("royalsocietypublishing_html", "royalsocietypublishing_pdf"),
)
