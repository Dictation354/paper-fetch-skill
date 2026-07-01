"""Royal Society Publishing direct-HTTP provider client."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections.abc import Mapping, Sequence
from urllib.parse import urljoin

from ..config import build_user_agent, resolve_asset_download_concurrency
from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.assets import (
    FIGURE_KIND,
    SUPPLEMENTARY_KIND,
    download_assets,
    html_asset_identity_key,
    split_body_and_supplementary_assets,
)
from ..extraction.html.landing import REDIRECT_STATUS_CODES, fetch_landing_html
from ..extraction.html.provider_rules import (
    ProviderAssetRules,
    ProviderCleanupRules,
    ProviderFrontMatterRules,
    ProviderHtmlRules,
)
from ..http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, HttpTransport, PDF_MIME_TYPE, RequestFailure
from ..http.headers import header_value
from ..models import AssetProfile, article_from_markdown, metadata_only_article
from ..provider_catalog import BodyTextThresholds, ProviderSpec
from ..publisher_identity import normalize_doi
from ..reason_codes import NO_RESULT, OK, PDF_FALLBACK
from ..runtime import RuntimeContext
from ..tracing import download_marker, fulltext_marker
from ..utils import empty_asset_results, normalize_text
from ..quality.html_availability import HtmlQualityAssessor, availability_failure_message
from . import _royalsocietypublishing_html as royal_html
from ._payloads import build_provider_payload
from ._pdf_common import (
    PdfFetchFailure,
    default_pdf_headers,
    filename_from_headers,
    pdf_asset_output_dir,
    pdf_asset_profile_from_context,
    pdf_fetch_result_assets,
    pdf_fetch_result_from_bytes,
)
from ._registry import ProviderBundle, register_provider_bundle
from ._waterfall import DEFAULT_WATERFALL_CONTINUE_CODES, ProviderWaterfallStep, ProviderWaterfallState, run_provider_waterfall
from .base import (
    ProviderArtifacts,
    ProviderClient,
    ProviderFailure,
    ProviderStatusResult,
    RawFulltextPayload,
    build_provider_status_check,
    combine_provider_failures,
    map_request_failure,
    summarize_capability_status,
)


register_provider_bundle(
    ProviderBundle(
        catalog=ProviderSpec(
            name="royalsocietypublishing",
            display_name="Royal Society Publishing",
            official=True,
            domains=("royalsocietypublishing.org",),
            doi_prefixes=("10.1098/",),
            publisher_aliases=("the royal society", "royal society publishing"),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=False,
            client_factory_path="paper_fetch.providers.royalsocietypublishing:RoyalsocietypublishingClient",
            status_order=11,
            base_domains=("royalsocietypublishing.org",),
            html_path_templates=("/doi/{doi}",),
            pdf_path_templates=("/doi/pdf/{doi}",),
            requires_playwright=False,
            requires_browser_runtime=False,
            body_text_thresholds=BodyTextThresholds(min_chars=800),
        ),
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
                no_signals=True,
            ),
        ),
        sources=("royalsocietypublishing_html", "royalsocietypublishing_pdf"),
    )
)


@dataclass(frozen=True)
class RoyalSocietyArticleAttempt:
    doi: str
    requested_url: str
    final_url: str
    html_text: str
    response_status: int | None
    response_headers: Mapping[str, str]
    metadata: dict[str, Any]


def _merge_assets(
    extracted_assets: Sequence[Mapping[str, Any]] | None,
    downloaded_assets: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    by_identity: dict[str, dict[str, Any]] = {}
    for item in extracted_assets or []:
        asset = dict(item)
        merged.append(asset)
        identity = html_asset_identity_key(asset)
        if identity:
            by_identity[identity] = asset
    for item in downloaded_assets or []:
        asset = dict(item)
        identity = html_asset_identity_key(asset)
        existing = by_identity.get(identity) if identity else None
        if existing is not None:
            existing.update(asset)
            continue
        merged.append(asset)
        if identity:
            by_identity[identity] = asset
    return merged


def _filter_assets_for_profile(
    assets: Sequence[Mapping[str, Any]] | None,
    *,
    asset_profile: AssetProfile,
) -> list[dict[str, Any]]:
    if asset_profile == "none":
        return []
    filtered: list[dict[str, Any]] = []
    for item in assets or []:
        asset = dict(item)
        kind = normalize_text(str(asset.get("kind") or asset.get("asset_type") or "")).lower()
        section = normalize_text(str(asset.get("section") or "")).lower()
        if asset_profile != "all" and (kind == "supplementary" or section == "supplementary"):
            continue
        filtered.append(asset)
    return filtered


def _pdf_failure_diagnostics(exc: PdfFetchFailure | None) -> dict[str, Any] | None:
    if exc is None:
        return None
    return {
        "kind": exc.kind,
        "message": exc.message,
        "details": dict(exc.details),
    }


class RoyalsocietypublishingClient(ProviderClient):
    name = "royalsocietypublishing"
    landing_max_redirects = 8

    def __init__(self, transport: HttpTransport, env: Mapping[str, str]) -> None:
        self.transport = transport
        self.env = dict(env)
        self.user_agent = build_user_agent(env)

    def probe_status(self) -> ProviderStatusResult:
        return summarize_capability_status(
            self.name,
            official_provider=self.official_provider,
            checks=[
                build_provider_status_check(
                    "article_html",
                    OK,
                    "Royal Society Publishing direct DOI HTML route is available without provider credentials.",
                    details={"mode": "direct_http_html"},
                ),
                build_provider_status_check(
                    PDF_FALLBACK,
                    OK,
                    "Royal Society Publishing direct PDF fallback is available; body/all asset requests can save exported PDF images when artifacts are enabled.",
                    details={"mode": "direct_http_pdf"},
                ),
            ],
        )

    def _html_headers(self) -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": self.user_agent,
        }

    def _fetch_article_attempt(
        self,
        doi: str,
        metadata: Mapping[str, Any],
    ) -> RoyalSocietyArticleAttempt:
        normalized_doi = normalize_doi(doi)
        requested_url = royal_html.direct_article_url(normalized_doi)
        try:
            landing = fetch_landing_html(
                requested_url,
                transport=self.transport,
                headers=self._html_headers(),
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                retry_on_transient=True,
                max_redirects=self.landing_max_redirects,
            )
        except RequestFailure as exc:
            raise map_request_failure(exc) from exc

        merged_metadata = royal_html.merge_metadata_with_html(
            metadata,
            landing.html_text,
            landing.final_url,
            doi=normalized_doi,
        )
        return RoyalSocietyArticleAttempt(
            doi=normalized_doi,
            requested_url=requested_url,
            final_url=landing.final_url,
            html_text=landing.html_text,
            response_status=landing.status_code or None,
            response_headers=landing.headers,
            metadata=merged_metadata,
        )

    def _fetch_article_html_payload(
        self,
        attempt: RoyalSocietyArticleAttempt,
        *,
        asset_profile: AssetProfile,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        del context
        extraction = royal_html.extract_markdown(
            attempt.html_text,
            attempt.final_url,
            metadata=attempt.metadata,
            asset_profile=asset_profile,
        )
        diagnostics = HtmlQualityAssessor(self.name).assess(
            extraction.markdown_text,
            extraction.metadata,
            html_text=extraction.html_text or attempt.html_text,
            title=str(extraction.metadata.get("title") or ""),
            requested_url=attempt.requested_url,
            final_url=attempt.final_url,
            response_status=attempt.response_status,
            section_hints=extraction.section_hints,
        )
        if not diagnostics.accepted:
            raise ProviderFailure(NO_RESULT, availability_failure_message(diagnostics))

        content_type = header_value(attempt.response_headers, "content-type", "text/html")
        return build_provider_payload(
            provider=self.name,
            route_kind="html",
            source_url=attempt.final_url,
            content_type=content_type,
            body=extraction.html_text.encode("utf-8"),
            markdown_text=extraction.markdown_text,
            merged_metadata=extraction.metadata,
            diagnostics={
                "availability_diagnostics": diagnostics.to_dict(),
                "extraction": {
                    "abstract_sections": extraction.abstract_sections,
                    "section_hints": extraction.section_hints,
                },
            },
            reason="Downloaded full text from the Royal Society Publishing direct DOI HTML route.",
            extracted_assets=extraction.extracted_assets,
        )

    def _request_pdf_candidate(self, url: str, *, referer: str | None = None) -> Mapping[str, Any]:
        headers = default_pdf_headers(self.user_agent, referer=referer)
        current_url = url
        for redirect_count in range(self.landing_max_redirects + 1):
            response = self.transport.request(
                "GET",
                current_url,
                headers=headers,
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                retry_on_transient=True,
            )
            response = dict(response)
            response["url"] = urljoin(current_url, str(response.get("url") or "").strip() or current_url)
            status_code = int(response.get("status_code") or 200)
            location = header_value(response.get("headers"), "location")
            if status_code in REDIRECT_STATUS_CODES and location:
                if redirect_count >= self.landing_max_redirects:
                    break
                current_url = urljoin(str(response["url"]), location)
                continue
            return response
        return response

    def _fetch_pdf_payload(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        source_url: str,
        html_failure_message: str,
        html_trace_markers: Sequence[str],
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        candidates = royal_html.pdf_candidate_urls(metadata, source_url=source_url, doi=doi)
        last_failure: PdfFetchFailure | None = None
        effective_asset_profile = pdf_asset_profile_from_context(context)
        for candidate in candidates:
            try:
                response = self._request_pdf_candidate(candidate, referer=source_url)
            except RequestFailure as exc:
                last_failure = PdfFetchFailure(
                    "pdf_download_failed",
                    f"Failed to download Royal Society Publishing PDF candidate: {exc}",
                    details={"candidate_url": candidate, "status": exc.status_code},
                )
                continue

            response_headers = response.get("headers") if isinstance(response.get("headers"), Mapping) else {}
            body = response.get("body", b"")
            pdf_bytes = bytes(body) if isinstance(body, (bytes, bytearray)) else b""
            content_type = header_value(response_headers, "content-type")
            final_url = str(response.get("url") or candidate)
            if not pdf_bytes.lstrip().startswith(b"%PDF-"):
                last_failure = PdfFetchFailure(
                    "downloaded_file_not_pdf",
                    "Royal Society Publishing PDF fallback candidate returned an HTML wrapper or other non-PDF content.",
                    details={
                        "candidate_url": candidate,
                        "final_url": final_url,
                        "status": int(response.get("status_code") or 0) or None,
                        "content_type": content_type or None,
                    },
                )
                continue

            try:
                pdf_result = pdf_fetch_result_from_bytes(
                    artifact_dir=None,
                    asset_profile=effective_asset_profile,
                    asset_output_dir=pdf_asset_output_dir(context, asset_profile=effective_asset_profile, doi=doi),
                    source_url=candidate,
                    final_url=final_url,
                    pdf_bytes=pdf_bytes,
                    suggested_filename=filename_from_headers(response_headers),
                )
            except PdfFetchFailure as exc:
                last_failure = exc
                continue

            merged_metadata = dict(metadata or {})
            return build_provider_payload(
                provider=self.name,
                route_kind=PDF_FALLBACK,
                source_url=pdf_result.final_url,
                content_type=PDF_MIME_TYPE,
                body=pdf_result.pdf_bytes,
                markdown_text=pdf_result.markdown_text,
                merged_metadata=merged_metadata,
                diagnostics={
                    PDF_FALLBACK: {
                        "candidates": candidates,
                        "source_url": candidate,
                        "final_url": pdf_result.final_url,
                        "html_failure_message": html_failure_message,
                    },
                },
                reason="Downloaded full text from the Royal Society Publishing direct PDF fallback route.",
                suggested_filename=pdf_result.suggested_filename,
                extracted_assets=pdf_fetch_result_assets(pdf_result),
                html_failure_message=html_failure_message,
                content_needs_local_copy=True,
                warnings=[
                    "Full text was extracted from Royal Society Publishing PDF fallback after the HTML route was not usable.",
                ],
                trace_markers=[
                    *list(html_trace_markers),
                    fulltext_marker(self.name, "ok", route=PDF_FALLBACK),
                ],
                needs_local_copy=True,
            )

        raise ProviderFailure(
            NO_RESULT,
            (
                last_failure.message
                if last_failure is not None
                else "No Royal Society Publishing PDF fallback candidates were attempted."
            ),
            warnings=[
                "Royal Society Publishing PDF fallback was not usable."
            ],
        )

    def fetch_raw_fulltext(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        runtime_context = self._runtime_context(context)
        normalized_doi = normalize_doi(doi)
        article_attempt: RoyalSocietyArticleAttempt | None = None
        article_fetch_failure: ProviderFailure | None = None
        try:
            article_attempt = self._fetch_article_attempt(normalized_doi, metadata)
        except ProviderFailure as exc:
            article_fetch_failure = exc

        def run_article_html(_state: ProviderWaterfallState) -> RawFulltextPayload:
            if article_fetch_failure is not None:
                raise article_fetch_failure
            assert article_attempt is not None
            return self._fetch_article_html_payload(
                article_attempt,
                asset_profile="all",
                context=runtime_context,
            )

        def run_pdf_fallback(state: ProviderWaterfallState) -> RawFulltextPayload:
            html_failure = state.failure("article_html")
            source_metadata = dict(metadata)
            source_url = royal_html.direct_article_url(normalized_doi)
            if article_attempt is not None:
                source_metadata = dict(article_attempt.metadata)
                source_url = article_attempt.final_url
            if not source_metadata.get("doi"):
                source_metadata["doi"] = normalized_doi
            html_failure_message = (
                html_failure.message if html_failure is not None else "Royal Society Publishing HTML route failed."
            )
            try:
                return self._fetch_pdf_payload(
                    normalized_doi,
                    source_metadata,
                    source_url=source_url,
                    html_failure_message=html_failure_message,
                    html_trace_markers=state.source_markers(),
                    context=runtime_context,
                )
            except ProviderFailure:
                raise

        def final_failure(state: ProviderWaterfallState) -> ProviderFailure:
            failures = [
                (
                    "article_html",
                    state.failure("article_html")
                    or ProviderFailure(NO_RESULT, "Royal Society Publishing HTML route failed."),
                ),
                (
                    "pdf_fallback",
                    state.failure("pdf_fallback")
                    or ProviderFailure(NO_RESULT, "Royal Society Publishing PDF fallback failed."),
                ),
            ]
            combined = combine_provider_failures(failures)
            return ProviderFailure(
                combined.code,
                "Royal Society Publishing full text could not be retrieved. " + combined.message,
                warnings=state.warnings,
                source_trail=state.source_markers(),
            )

        return run_provider_waterfall(
            [
                ProviderWaterfallStep(
                    label="article_html",
                    run=run_article_html,
                    failure_marker=fulltext_marker(self.name, "fail", route="html"),
                    success_markers=(fulltext_marker(self.name, "ok", route="html"),),
                    continue_codes=DEFAULT_WATERFALL_CONTINUE_CODES,
                    failure_warning=lambda failure, _state: (
                        f"Royal Society Publishing HTML route was not usable ({failure.message}); attempting PDF fallback."
                    ),
                ),
                ProviderWaterfallStep(
                    label="pdf_fallback",
                    run=run_pdf_fallback,
                    failure_marker=fulltext_marker(self.name, "fail", route=PDF_FALLBACK),
                    success_markers=(fulltext_marker(self.name, "ok", route=PDF_FALLBACK),),
                    continue_codes=DEFAULT_WATERFALL_CONTINUE_CODES,
                ),
            ],
            final_failure_factory=final_failure,
        )

    def html_to_markdown(
        self,
        html_text: str,
        source_url: str,
        *,
        metadata: Mapping[str, Any],
        context: RuntimeContext,
    ) -> tuple[str, Mapping[str, Any]]:
        del context
        extraction = royal_html.extract_markdown(
            html_text,
            source_url,
            metadata=metadata,
            asset_profile="all",
        )
        return extraction.markdown_text, {
            "abstract_sections": extraction.abstract_sections,
            "section_hints": extraction.section_hints,
            "extracted_assets": extraction.extracted_assets,
        }

    def to_article_model(
        self,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
        context: RuntimeContext | None = None,
    ):
        del asset_failures, context
        content = raw_payload.content
        route = normalize_text(content.route_kind if content is not None else "").lower()
        source = "royalsocietypublishing_pdf" if route == PDF_FALLBACK else "royalsocietypublishing_html"
        merged_metadata = dict(
            (content.merged_metadata if content is not None else None)
            or raw_payload.merged_metadata
            or metadata
            or {}
        )
        markdown_text = normalize_text(content.markdown_text if content is not None else "")
        if not markdown_text:
            return metadata_only_article(
                source=source,
                metadata=merged_metadata,
                doi=normalize_doi(str(merged_metadata.get("doi") or "")) or None,
                warnings=list(raw_payload.warnings),
                trace=raw_payload.trace,
            )
        diagnostics = dict(content.diagnostics if content is not None else {})
        extraction = diagnostics.get("extraction") if isinstance(diagnostics.get("extraction"), Mapping) else {}
        availability = diagnostics.get("availability_diagnostics")
        extracted_assets = content.extracted_assets if content is not None else []
        assets = (
            list(extracted_assets)
            if route == PDF_FALLBACK
            else _merge_assets(extracted_assets, downloaded_assets)
        )
        return article_from_markdown(
            source=source,
            metadata=merged_metadata,
            doi=normalize_doi(str(merged_metadata.get("doi") or "")) or None,
            markdown_text=markdown_text,
            abstract_sections=list(extraction.get("abstract_sections") or []),
            section_hints=list(extraction.get("section_hints") or []),
            assets=assets,
            warnings=list(raw_payload.warnings),
            trace=raw_payload.trace,
            availability_diagnostics=availability if isinstance(availability, Mapping) else None,
            allow_downgrade_from_diagnostics=True,
        )

    def download_related_assets(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        raw_payload: RawFulltextPayload,
        output_dir: Path | None,
        *,
        asset_profile: AssetProfile = "all",
        context: RuntimeContext | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        del metadata
        context = self._runtime_context(context, output_dir=output_dir)
        if output_dir is None or asset_profile == "none":
            return empty_asset_results()
        content = raw_payload.content
        if normalize_text(content.route_kind if content is not None else "").lower() != "html":
            return empty_asset_results()

        extracted_assets = _filter_assets_for_profile(
            content.extracted_assets if content is not None else [],
            asset_profile=asset_profile,
        )
        if not extracted_assets:
            return empty_asset_results()
        body_assets, supplementary_assets = split_body_and_supplementary_assets(extracted_assets)
        headers = {"Referer": raw_payload.source_url}
        article_id = normalize_doi(doi) or "royalsocietypublishing"
        body_results = download_assets(
            FIGURE_KIND,
            self.transport,
            article_id=article_id,
            assets=body_assets,
            output_dir=output_dir,
            user_agent=self.user_agent,
            asset_profile=asset_profile,
            headers=headers,
            seed_urls=[],
            asset_download_concurrency=resolve_asset_download_concurrency(context.env),
        )
        supplementary_results = (
            download_assets(
                SUPPLEMENTARY_KIND,
                self.transport,
                article_id=article_id,
                assets=supplementary_assets,
                output_dir=output_dir,
                user_agent=self.user_agent,
                asset_profile=asset_profile,
                headers=headers,
                seed_urls=[raw_payload.source_url],
                asset_download_concurrency=resolve_asset_download_concurrency(context.env),
            )
            if asset_profile == "all"
            else empty_asset_results()
        )
        return {
            "assets": [
                *list(body_results.get("assets") or []),
                *list(supplementary_results.get("assets") or []),
            ],
            "asset_failures": [
                *list(body_results.get("asset_failures") or []),
                *list(supplementary_results.get("asset_failures") or []),
            ],
        }

    def describe_artifacts(
        self,
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ) -> ProviderArtifacts:
        artifacts = super().describe_artifacts(
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
        )
        content = raw_payload.content
        if normalize_text(content.route_kind if content is not None else "").lower() != PDF_FALLBACK:
            return artifacts
        pdf_assets = list(content.extracted_assets if content is not None else [])
        return ProviderArtifacts(
            assets=[*list(artifacts.assets), *pdf_assets],
            asset_failures=list(artifacts.asset_failures),
            allow_related_assets=False,
            text_only=not pdf_assets,
            skip_trace=[download_marker("royalsocietypublishing_assets_skipped_text_only")]
            if not pdf_assets
            else [],
        )


__all__ = ["RoyalsocietypublishingClient"]
