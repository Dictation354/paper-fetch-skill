"""IOP Publishing provider client."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.provider_rules import (
    DomHooks,
    ProviderAssetRules,
    ProviderCleanupRules,
    ProviderFormulaRules,
    ProviderFrontMatterRules,
    ProviderHtmlRules,
)
from ..models import AssetProfile
from ..provider_catalog import BodyTextThresholds, ProviderSpec
from ..publisher_identity import normalize_doi
from ..reason_codes import PDF_FALLBACK
from ..runtime import RuntimeContext
from ..utils import empty_asset_results, normalize_text
from . import _iop_html, browser_workflow
from ._registry import ProviderBundle, register_provider_bundle
from .base import RawFulltextPayload
from .browser_workflow.profile import ProviderBrowserProfile


register_provider_bundle(
    ProviderBundle(
        catalog=ProviderSpec(
            name="iop",
            display_name="IOP Publishing",
            official=True,
            domains=("iopscience.iop.org",),
            doi_prefixes=("10.1088/",),
            publisher_aliases=(
                "iop publishing",
                "institute of physics publishing",
                "iopscience",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            client_factory_path="paper_fetch.providers.iop:IopClient",
            status_order=16,
            base_domains=("iopscience.iop.org",),
            html_path_templates=("/article/{doi}",),
            pdf_path_templates=("/article/{doi}/pdf",),
            crossref_pdf_position=0,
            requires_playwright=True,
            requires_browser_runtime=True,
            body_text_thresholds=BodyTextThresholds(min_chars=1200),
        ),
        html_rules=ProviderHtmlRules(
            name="iop",
            noise_profile=_iop_html.IOP_NOISE_PROFILE,
            cleanup=ProviderCleanupRules(
                markdown_promo_tokens=_iop_html.IOP_MARKDOWN_PROMO_TOKENS,
                extraction_cleanup_selectors=_iop_html.IOP_EXTRACTION_CLEANUP_SELECTORS,
                post_content_break_tokens=_iop_html.IOP_POST_CONTENT_BREAK_TOKENS,
                access_block_text_tokens=_iop_html.IOP_ACCESS_BLOCK_TEXT_TOKENS,
            ),
            front_matter=ProviderFrontMatterRules(
                exact_texts=_iop_html.IOP_FRONT_MATTER_EXACT_TEXTS,
                contains_tokens=_iop_html.IOP_FRONT_MATTER_CONTAINS_TOKENS,
                publication_keywords=_iop_html.IOP_FRONT_MATTER_PUBLICATION_KEYWORDS,
            ),
            formula=ProviderFormulaRules(
                container_tokens=_iop_html.IOP_FORMULA_CONTAINER_TOKENS,
                display_selectors=_iop_html.IOP_DISPLAY_FORMULA_SELECTORS,
            ),
            assets=ProviderAssetRules(
                supplementary_text_tokens=_iop_html.IOP_SUPPLEMENTARY_TEXT_TOKENS,
            ),
            availability=AvailabilityPolicy(
                name="iop",
                site_rule_overrides=_iop_html.IOP_SITE_RULE_OVERRIDES,
                text_marker_signal_set=_iop_html.IOP_TEXT_MARKER_SIGNAL_SET,
                access_block_text_tokens=_iop_html.IOP_ACCESS_BLOCK_TEXT_TOKENS,
            ),
            dom_hooks=DomHooks(
                body_container=_iop_html.iop_body_container,
                asset_body_container=_iop_html.iop_asset_body_container,
                asset_figure_extraction=_iop_html.iop_asset_figure_extraction,
            ),
        ),
        sources=("iop_html", "iop_pdf"),
    )
)


IOP_BROWSER_PROFILE = ProviderBrowserProfile(
    name="iop",
    article_source_name="iop_html",
    label="IOP Publishing",
    hosts=("iopscience.iop.org",),
    base_hosts=("iopscience.iop.org",),
    html_path_templates=("/article/{doi}",),
    pdf_path_templates=("/article/{doi}/pdf",),
    crossref_pdf_position=0,
    markdown_publisher="iop",
    fallback_author_extractor=_iop_html.extract_authors,
    shared_browser_image_fetcher=True,
)


def _append_unique(values: list[str], candidate: str | None) -> None:
    normalized = normalize_text(candidate)
    if normalized and normalized not in values:
        values.append(normalized)


class IopClient(browser_workflow.BrowserWorkflowClient):
    name = IOP_BROWSER_PROFILE.name
    profile = IOP_BROWSER_PROFILE
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
        if _iop_html.is_iop_url(landing):
            _append_unique(candidates, landing)
        if normalized_doi:
            _append_unique(candidates, _iop_html.direct_article_url(normalized_doi))
            _append_unique(candidates, f"https://doi.org/{normalized_doi}")
        return candidates

    def pdf_candidates(self, doi: str, metadata: Mapping[str, Any]) -> list[str]:
        normalized_doi = normalize_doi(doi)
        source_url = normalize_text(str(metadata.get("landing_page_url") or ""))
        if not source_url and normalized_doi:
            source_url = _iop_html.direct_article_url(normalized_doi)
        return _iop_html.pdf_candidate_urls(
            metadata,
            source_url=source_url,
            doi=normalized_doi,
        )

    def extract_markdown(
        self,
        html_text: str,
        final_url: str,
        *,
        metadata: Mapping[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        return _iop_html.extract_markdown(
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
            return "iop_pdf"
        return "iop_html"

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
        assets = _iop_html.extract_scoped_html_assets(
            html_text,
            raw_payload.source_url,
            asset_profile=asset_profile,
        )
        if content.markdown_text:
            assets = _iop_html.suppress_iop_asset_captions_already_in_markdown(
                assets,
                content.markdown_text,
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


__all__ = ["IopClient"]
