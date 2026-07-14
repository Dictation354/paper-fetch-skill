"""IOP Publishing provider client."""

from __future__ import annotations

import contextlib
from typing import Any
from collections.abc import Mapping

from ..extraction.html import decode_html
from ..extraction.html.signals import HtmlExtractionFailure
from ..http import redact_url_for_cache
from ..http.headers import header_value
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
from .browser_runtime import BrowserRuntimeFailure
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


def _supplementary_index_failure(
    source_url: str,
    reason: str,
    *,
    message: str = "",
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    failure: dict[str, Any] = {
        "kind": "supplementary",
        "heading": "Supplementary data",
        "caption": "",
        "source_url": source_url,
        "reason": reason,
        "section": "supplementary",
        "source_kind": "iop_supplementary_index",
    }
    if message:
        failure["error_message"] = message
    for key, value in (details or {}).items():
        if value in (None, "", [], {}):
            continue
        if key == "reason":
            failure["upstream_reason"] = value
        elif key not in failure:
            failure[key] = value
    return failure


def _redact_iop_supplementary_urls(
    items: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    redacted: list[dict[str, Any]] = []
    for raw_item in items:
        item = dict(raw_item)
        if normalize_text(str(item.get("kind") or "")).lower() == "supplementary":
            for key in (
                "url",
                "download_url",
                "source_url",
                "final_url",
                "original_url",
            ):
                value = item.get(key)
                if isinstance(value, str):
                    item[key] = redact_url_for_cache(value)
        redacted.append(item)
    return redacted


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

    def _resolve_supplementary_data_assets(
        self,
        normalized_doi: str,
        raw_payload: RawFulltextPayload,
        index_urls: list[str],
        *,
        context: RuntimeContext,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if not index_urls:
            return [], []
        try:
            runtime = self.deps.load_runtime_config(
                self.env,
                provider=self.name,
                doi=normalized_doi,
            )
            self.deps.ensure_runtime_ready(runtime)
        except BrowserRuntimeFailure as exc:
            failures = [
                _supplementary_index_failure(
                    index_url,
                    "iop_supplementary_index_runtime_failed",
                    message=exc.message,
                    details={"runtime_reason": exc.kind, **exc.details},
                )
                for index_url in index_urls
            ]
            return [], failures

        content = raw_payload.content
        browser_context_seed = (
            dict(content.browser_context_seed or {}) if content is not None else {}
        )
        seed_urls = [
            url
            for url in (
                raw_payload.source_url,
                normalize_text(
                    str(browser_context_seed.get("browser_final_url") or "")
                ),
            )
            if url
        ]
        index_fetcher = self.deps._build_shared_browser_file_fetcher(
            browser_context_seed_getter=lambda: browser_context_seed,
            seed_urls_getter=lambda: list(seed_urls),
            browser_user_agent=(
                normalize_text(str(getattr(runtime, "user_agent", None) or ""))
                or self.browser_user_agent
            ),
            headless=bool(getattr(runtime, "headless", True)),
            runtime_context=context,
            use_runtime_shared_browser=True,
            binary_path=getattr(runtime, "binary_path", None),
            cdp_endpoint=getattr(runtime, "cdp_endpoint", None),
            profile_dir=getattr(runtime, "profile_dir", None),
            user_data_dir=getattr(runtime, "user_data_dir", None),
        )
        resolved_assets: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        try:
            for index_url in index_urls:
                try:
                    response = index_fetcher(
                        index_url,
                        {
                            "kind": "supplementary",
                            "section": "supplementary",
                            "referer_url": raw_payload.source_url,
                        },
                    )
                except BrowserRuntimeFailure as exc:
                    failures.append(
                        _supplementary_index_failure(
                            index_url,
                            "iop_supplementary_index_fetch_failed",
                            message=exc.message,
                            details={"upstream_reason": exc.kind, **exc.details},
                        )
                    )
                    continue
                if not isinstance(response, Mapping):
                    failure_for = getattr(index_fetcher, "failure_for", None)
                    diagnostic = (
                        failure_for(index_url) if callable(failure_for) else None
                    )
                    failures.append(
                        _supplementary_index_failure(
                            index_url,
                            "iop_supplementary_index_fetch_failed",
                            details=diagnostic
                            if isinstance(diagnostic, Mapping)
                            else None,
                        )
                    )
                    continue

                body = response.get("body")
                if not isinstance(body, (bytes, bytearray)) or not body:
                    failures.append(
                        _supplementary_index_failure(
                            index_url,
                            "iop_supplementary_index_fetch_failed",
                            details={
                                "upstream_reason": "empty_response_body",
                                "status": response.get("status_code"),
                            },
                        )
                    )
                    continue
                final_url = normalize_text(str(response.get("url") or "")) or index_url
                content_type = header_value(
                    response.get("headers"),
                    "content-type",
                )
                html_text = decode_html(bytes(body), content_type=content_type)
                try:
                    resolved_assets.extend(
                        _iop_html.extract_supplementary_data_assets(
                            html_text,
                            final_url,
                            expected_doi=normalized_doi,
                        )
                    )
                except HtmlExtractionFailure as exc:
                    failures.append(
                        _supplementary_index_failure(
                            index_url,
                            exc.reason,
                            message=exc.message,
                            details={
                                "status": response.get("status_code"),
                                "content_type": content_type,
                                "final_url": final_url,
                            },
                        )
                    )
        finally:
            close = getattr(index_fetcher, "close", None)
            if callable(close):
                with contextlib.suppress(Exception):
                    close()

        deduplicated_assets: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for asset in resolved_assets:
            key = (
                normalize_text(str(asset.get("source_ref") or "")).lower(),
                normalize_text(str(asset.get("url") or "")),
            )
            if key in seen:
                continue
            seen.add(key)
            deduplicated_assets.append(asset)
        return deduplicated_assets, failures

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
        index_failures: list[dict[str, Any]] = []
        if asset_profile == "all":
            index_urls = _iop_html.extract_supplementary_index_urls(
                html_text,
                raw_payload.source_url,
                doi=normalized_doi,
            )
            supplementary_assets, index_failures = (
                self._resolve_supplementary_data_assets(
                    normalized_doi,
                    raw_payload,
                    index_urls,
                    context=context,
                )
            )
            assets.extend(supplementary_assets)
        if content.markdown_text:
            assets = _iop_html.suppress_iop_asset_captions_already_in_markdown(
                assets,
                content.markdown_text,
            )
        if not assets:
            return {
                "assets": [],
                "asset_failures": _redact_iop_supplementary_urls(index_failures),
            }
        result = self._download_browser_backed_related_assets(
            doi,
            metadata,
            raw_payload,
            output_dir,
            asset_profile=asset_profile,
            context=context,
            assets=assets,
        )
        return {
            "assets": _redact_iop_supplementary_urls(list(result.get("assets") or [])),
            "asset_failures": _redact_iop_supplementary_urls(
                [
                    *index_failures,
                    *list(result.get("asset_failures") or []),
                ]
            ),
        }


__all__ = ["IopClient"]
