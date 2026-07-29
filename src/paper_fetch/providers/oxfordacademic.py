"""Oxford Academic provider client."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections.abc import Mapping, Sequence
from urllib.parse import quote, urljoin

from ..config import (
    build_publisher_user_agent,
    resolve_asset_download_concurrency,
)
from ..extraction.html.assets import (
    FIGURE_KIND,
    SUPPLEMENTARY_KIND,
    download_assets,
    html_asset_identity_key,
    split_body_and_supplementary_assets,
)
from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.landing import REDIRECT_STATUS_CODES, fetch_landing_html
from ..extraction.html.provider_rules import (
    ProviderAssetRules,
    ProviderCleanupRules,
    ProviderFrontMatterRules,
    ProviderHtmlRules,
)
from ..http import (
    DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
    HttpRequestPolicy,
    HttpTransport,
    PDF_MIME_TYPE,
    RequestFailure,
)
from ..http.headers import header_value
from ..models import (
    AssetProfile,
    SourceKind,
    article_from_markdown,
    metadata_only_article,
)
from ..provider_catalog import BodyTextThresholds, ProviderSpec
from ..pdf_limits import pdf_max_bytes
from ..publisher_identity import normalize_doi
from ..reason_codes import NO_RESULT, OK, PDF_FALLBACK
from ..runtime import RuntimeContext
from ..tracing import download_marker, fulltext_marker, trace_from_markers
from ..utils import empty_asset_results, normalize_text
from ..quality.html_availability import (
    HtmlQualityAssessor,
    availability_failure_message,
)
from . import _oxfordacademic_html as oxford_html
from ._payloads import build_provider_payload
from ._pdf_common import (
    PdfFetchFailure,
    default_pdf_headers,
    pdf_asset_output_dir,
    pdf_asset_profile_from_context,
    pdf_fetch_result_assets,
    pdf_fetch_result_warnings,
    pdf_fetch_result_from_response,
)
from ._registry import ProviderBundle, register_provider_bundle
from ._waterfall import (
    DEFAULT_WATERFALL_CONTINUE_CODES,
    ProviderWaterfallState,
    ProviderWaterfallStep,
    run_provider_waterfall,
)
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
            name="oxfordacademic",
            display_name="Oxford Academic",
            official=True,
            domains=("academic.oup.com",),
            doi_prefixes=("10.1093/",),
            publisher_aliases=(
                "oxford academic",
                "oxford university press",
                "oxford university press (oup)",
                "oup",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=False,
            client_factory_path="paper_fetch.providers.oxfordacademic:OxfordAcademicClient",
            status_order=14,
            base_domains=("academic.oup.com",),
            pdf_path_templates=(
                "/doi/pdf/{doi}",
                "/doi/epdf/{doi}",
            ),
            requires_playwright=False,
            requires_browser_runtime=False,
            body_text_thresholds=BodyTextThresholds(min_chars=1200),
        ),
        html_rules=ProviderHtmlRules(
            name="oxfordacademic",
            noise_profile=oxford_html.OXFORDACADEMIC_NOISE_PROFILE,
            cleanup=ProviderCleanupRules(
                markdown_promo_tokens=oxford_html.OXFORDACADEMIC_MARKDOWN_PROMO_TOKENS,
                extraction_cleanup_selectors=oxford_html.OXFORDACADEMIC_EXTRACTION_CLEANUP_SELECTORS,
            ),
            front_matter=ProviderFrontMatterRules(
                exact_texts=oxford_html.OXFORDACADEMIC_FRONT_MATTER_EXACT_TEXTS,
                contains_tokens=oxford_html.OXFORDACADEMIC_FRONT_MATTER_CONTAINS_TOKENS,
                publication_keywords=oxford_html.OXFORDACADEMIC_FRONT_MATTER_PUBLICATION_KEYWORDS,
            ),
            assets=ProviderAssetRules(
                supplementary_text_tokens=oxford_html.OXFORDACADEMIC_SUPPLEMENTARY_TEXT_TOKENS,
            ),
            availability=AvailabilityPolicy(
                name="oxfordacademic",
                site_rule_overrides=oxford_html.OXFORDACADEMIC_SITE_RULE_OVERRIDES,
                no_signals=True,
            ),
        ),
        sources=("oxfordacademic_html", "oxfordacademic_pdf"),
    )
)


@dataclass(frozen=True)
class OxfordAcademicArticleAttempt:
    doi: str
    requested_url: str
    final_url: str
    html_text: str
    response_status: int | None
    response_headers: Mapping[str, str]
    metadata: dict[str, Any]


def _append_unique(values: list[str], candidate: str | None) -> None:
    normalized = normalize_text(candidate)
    if normalized and normalized not in values:
        values.append(normalized)


def _filter_oxford_assets(
    assets: Sequence[Mapping[str, Any]],
    *,
    asset_profile: AssetProfile,
) -> list[dict[str, Any]]:
    if asset_profile == "none":
        return []
    filtered: list[dict[str, Any]] = []
    for item in assets:
        asset = dict(item)
        kind = normalize_text(
            str(asset.get("kind") or asset.get("asset_type") or "")
        ).lower()
        section = normalize_text(str(asset.get("section") or "")).lower()
        if asset_profile != "all" and (
            kind == "supplementary" or section == "supplementary"
        ):
            continue
        filtered.append(asset)
    return filtered


def _merge_oxford_assets(
    extracted_assets: Sequence[Mapping[str, Any]],
    downloaded_assets: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    by_identity: dict[str, dict[str, Any]] = {}
    for item in [*extracted_assets, *downloaded_assets]:
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


class OxfordAcademicClient(ProviderClient):
    name = "oxfordacademic"
    landing_max_redirects = 8

    def __init__(self, transport: HttpTransport, env: Mapping[str, str]) -> None:
        self.transport = transport
        self.env = dict(env)
        self.user_agent = build_publisher_user_agent(env)

    def probe_status(self) -> ProviderStatusResult:
        return summarize_capability_status(
            self.name,
            official_provider=self.official_provider,
            checks=[
                build_provider_status_check(
                    "article_html",
                    OK,
                    "Oxford Academic public article HTML is available through DOI or academic.oup.com landing routes.",
                    details={"mode": "direct_http_html"},
                ),
                build_provider_status_check(
                    PDF_FALLBACK,
                    OK,
                    "Oxford Academic PDF fallback accepts only validated PDF responses; body/all asset requests can save exported PDF images when artifacts are enabled.",
                    details={"mode": "direct_http_pdf"},
                ),
            ],
        )

    def _html_headers(self) -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": self.user_agent,
        }

    def _asset_headers(self) -> dict[str, str]:
        return {
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": "https://academic.oup.com/",
            "User-Agent": self.user_agent,
        }

    def html_candidates(self, doi: str, metadata: Mapping[str, Any]) -> list[str]:
        normalized_doi = normalize_doi(doi)
        candidates: list[str] = []
        for key in ("landing_page_url", "source_url", "url"):
            value = normalize_text(str(metadata.get(key) or ""))
            if (
                oxford_html.is_oxfordacademic_url(value)
                and "/article-pdf/" not in value.lower()
            ):
                _append_unique(candidates, value)
        if normalized_doi:
            _append_unique(
                candidates, f"https://doi.org/{quote(normalized_doi, safe='/')}"
            )
        return candidates

    def pdf_candidates(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        html_text: str | None = None,
        source_url: str | None = None,
    ) -> list[str]:
        return oxford_html.pdf_candidate_urls(
            metadata,
            html_text=html_text,
            source_url=source_url,
            doi=doi,
        )

    def _fetch_article_attempt(
        self,
        doi: str,
        metadata: Mapping[str, Any],
    ) -> OxfordAcademicArticleAttempt:
        candidates = self.html_candidates(doi, metadata)
        last_failure: ProviderFailure | None = None
        for requested_url in candidates:
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
                last_failure = map_request_failure(exc)
                continue
            content_type = header_value(landing.headers, "content-type", "text/html")
            if "html" not in normalize_text(content_type).lower():
                last_failure = ProviderFailure(
                    NO_RESULT,
                    f"Oxford Academic HTML candidate returned non-HTML content: {content_type or 'unknown'}.",
                )
                continue
            merged_metadata = oxford_html.merge_metadata_with_html(
                metadata,
                landing.html_text,
                landing.final_url,
                doi=doi,
            )
            return OxfordAcademicArticleAttempt(
                doi=normalize_doi(doi),
                requested_url=requested_url,
                final_url=landing.final_url,
                html_text=landing.html_text,
                response_status=landing.status_code or None,
                response_headers=landing.headers,
                metadata=merged_metadata,
            )

        raise last_failure or ProviderFailure(
            NO_RESULT,
            "No Oxford Academic HTML candidates were available.",
        )

    def _fetch_article_html_payload(
        self,
        attempt: OxfordAcademicArticleAttempt,
        *,
        asset_profile: AssetProfile,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        del context
        extraction = oxford_html.extract_markdown(
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

        content_type = header_value(
            attempt.response_headers, "content-type", "text/html"
        )
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
            reason="Downloaded full text from the Oxford Academic public article HTML route.",
            extracted_assets=extraction.extracted_assets,
        )

    def _request_pdf_candidate(
        self, url: str, *, referer: str | None = None
    ) -> Mapping[str, Any]:
        headers = default_pdf_headers(self.user_agent, referer=referer)
        maximum_pdf_bytes = pdf_max_bytes()
        current_url = url
        response: Mapping[str, Any] = {}
        for redirect_count in range(self.landing_max_redirects + 1):
            response = self.transport.request(
                "GET",
                current_url,
                headers=headers,
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                retry_on_transient=True,
                request_policy=HttpRequestPolicy(
                    max_response_bytes=maximum_pdf_bytes,
                    max_compressed_response_bytes=maximum_pdf_bytes,
                ),
            )
            response = dict(response)
            response["url"] = urljoin(
                current_url, str(response.get("url") or "").strip() or current_url
            )
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
        html_text: str | None,
        html_failure_message: str,
        html_trace_markers: Sequence[str],
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        candidates = self.pdf_candidates(
            doi,
            metadata,
            html_text=html_text,
            source_url=source_url,
        )
        last_failure: PdfFetchFailure | None = None
        effective_asset_profile = pdf_asset_profile_from_context(context)
        for candidate in candidates:
            try:
                response = self._request_pdf_candidate(candidate, referer=source_url)
                pdf_result = pdf_fetch_result_from_response(
                    response,
                    artifact_dir=None,
                    asset_profile=effective_asset_profile,
                    asset_output_dir=pdf_asset_output_dir(
                        context, asset_profile=effective_asset_profile, doi=doi
                    ),
                    source_url=candidate,
                    final_url=str(response.get("url") or candidate),
                    not_pdf_message=(
                        "Oxford Academic PDF fallback candidate returned an HTML wrapper or other non-PDF content."
                    ),
                    allow_pdf_only=True,
                    expected_identity={
                        "doi": doi,
                        "title": metadata.get("title"),
                    },
                )
            except RequestFailure as exc:
                last_failure = PdfFetchFailure(
                    "pdf_download_failed",
                    f"Failed to download Oxford Academic PDF candidate: {exc}",
                    details={"candidate_url": candidate, "status": exc.status_code},
                )
                continue
            except PdfFetchFailure as exc:
                last_failure = exc
                continue

            merged_metadata = dict(metadata or {})
            if not merged_metadata.get("doi"):
                merged_metadata["doi"] = normalize_doi(doi)
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
                reason="Downloaded full text from the Oxford Academic public PDF fallback route.",
                suggested_filename=pdf_result.suggested_filename,
                extracted_assets=pdf_fetch_result_assets(pdf_result),
                html_failure_message=html_failure_message,
                content_needs_local_copy=True,
                warnings=[
                    *pdf_fetch_result_warnings(pdf_result),
                    "Full text was extracted from Oxford Academic PDF fallback after the HTML route was not usable.",
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
                else "No Oxford Academic PDF fallback candidates were attempted."
            ),
            warnings=["Oxford Academic PDF fallback was not usable."],
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
        article_attempt: OxfordAcademicArticleAttempt | None = None
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
            source_url = ""
            html_text = None
            if article_attempt is not None:
                source_metadata = dict(article_attempt.metadata)
                source_url = article_attempt.final_url
                html_text = article_attempt.html_text
            else:
                for key in ("landing_page_url", "source_url", "url"):
                    candidate = normalize_text(str(source_metadata.get(key) or ""))
                    if candidate:
                        source_url = candidate
                        break
            if not source_metadata.get("doi"):
                source_metadata["doi"] = normalized_doi
            html_failure_message = (
                html_failure.message
                if html_failure is not None
                else "Oxford Academic HTML route failed."
            )
            return self._fetch_pdf_payload(
                normalized_doi,
                source_metadata,
                source_url=source_url,
                html_text=html_text,
                html_failure_message=html_failure_message,
                html_trace_markers=state.source_markers(),
                context=runtime_context,
            )

        def final_failure(state: ProviderWaterfallState) -> ProviderFailure:
            failures = [
                (
                    "article_html",
                    state.failure("article_html")
                    or ProviderFailure(NO_RESULT, "Oxford Academic HTML route failed."),
                ),
                (
                    "pdf_fallback",
                    state.failure("pdf_fallback")
                    or ProviderFailure(
                        NO_RESULT, "Oxford Academic PDF fallback failed."
                    ),
                ),
            ]
            combined = combine_provider_failures(failures)
            return ProviderFailure(
                combined.code,
                "Oxford Academic full text could not be retrieved. " + combined.message,
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
                        f"Oxford Academic HTML route was not usable ({failure.message}); attempting PDF fallback."
                    ),
                ),
                ProviderWaterfallStep(
                    label="pdf_fallback",
                    run=run_pdf_fallback,
                    failure_marker=fulltext_marker(
                        self.name, "fail", route=PDF_FALLBACK
                    ),
                    success_markers=(
                        fulltext_marker(self.name, "ok", route=PDF_FALLBACK),
                    ),
                    continue_codes=DEFAULT_WATERFALL_CONTINUE_CODES,
                ),
            ],
            doi=doi,
            metadata=metadata,
            context=context,
            client=self,
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
        extraction = oxford_html.extract_markdown(
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
        del context
        content = raw_payload.content
        route = normalize_text(
            content.route_kind if content is not None else ""
        ).lower()
        source: SourceKind = (
            "oxfordacademic_pdf" if route == PDF_FALLBACK else "oxfordacademic_html"
        )
        merged_metadata = dict(
            (content.merged_metadata if content is not None else None)
            or raw_payload.merged_metadata
            or metadata
            or {}
        )
        markdown_text = normalize_text(
            content.markdown_text if content is not None else ""
        )
        if not markdown_text:
            return metadata_only_article(
                source=source,
                metadata=merged_metadata,
                doi=normalize_doi(str(merged_metadata.get("doi") or "")) or None,
                warnings=list(raw_payload.warnings),
                trace=raw_payload.trace,
            )
        diagnostics = dict(content.diagnostics if content is not None else {})
        extraction_candidate = diagnostics.get("extraction")
        extraction: Mapping[str, Any] = (
            extraction_candidate if isinstance(extraction_candidate, Mapping) else {}
        )
        availability = diagnostics.get("availability_diagnostics")
        assets = _merge_oxford_assets(
            list(content.extracted_assets if content is not None else []),
            list(downloaded_assets or []),
        )
        article = article_from_markdown(
            source=source,
            metadata=merged_metadata,
            doi=normalize_doi(str(merged_metadata.get("doi") or "")) or None,
            markdown_text=markdown_text,
            abstract_sections=list(extraction.get("abstract_sections") or []),
            section_hints=list(extraction.get("section_hints") or []),
            assets=assets,
            warnings=list(raw_payload.warnings),
            trace=raw_payload.trace,
            availability_diagnostics=availability
            if isinstance(availability, Mapping)
            else None,
            allow_downgrade_from_diagnostics=True,
        )
        if asset_failures:
            article.quality.asset_failures = [dict(item) for item in asset_failures]
        return article

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
        context = self._runtime_context(context, output_dir=output_dir)
        if output_dir is None or asset_profile == "none":
            return empty_asset_results()
        content = raw_payload.content
        route = normalize_text(
            content.route_kind if content is not None else ""
        ).lower()
        if route == PDF_FALLBACK:
            return empty_asset_results()
        extracted_assets = _filter_oxford_assets(
            list(content.extracted_assets if content is not None else []),
            asset_profile=asset_profile,
        )
        if not extracted_assets:
            return empty_asset_results()
        body_assets, supplementary_assets = split_body_and_supplementary_assets(
            extracted_assets
        )
        body_images = [
            dict(item)
            for item in body_assets
            if normalize_text(
                str(item.get("kind") or item.get("asset_type") or "")
            ).lower()
            in {"figure", "formula"}
        ]
        merged_metadata = content.merged_metadata if content is not None else None
        article_id = (
            normalize_doi(str((merged_metadata or {}).get("doi") or doi or ""))
            or normalize_text(str(metadata.get("title") or ""))
            or raw_payload.source_url
        )
        concurrency = resolve_asset_download_concurrency(context.env)
        body_result = (
            download_assets(
                FIGURE_KIND,
                self.transport,
                article_id=article_id,
                assets=body_images,
                output_dir=output_dir,
                user_agent=self.user_agent,
                asset_profile=asset_profile,
                headers=self._asset_headers(),
                asset_download_concurrency=concurrency,
                fetch_policy="direct_then_browser",
            )
            if body_images
            else empty_asset_results()
        )
        supplementary_result = (
            download_assets(
                SUPPLEMENTARY_KIND,
                self.transport,
                article_id=article_id,
                assets=supplementary_assets,
                output_dir=output_dir,
                user_agent=self.user_agent,
                asset_profile=asset_profile,
                headers=self._asset_headers(),
                asset_download_concurrency=concurrency,
                fetch_policy="direct_then_browser",
            )
            if supplementary_assets and asset_profile == "all"
            else empty_asset_results()
        )
        return {
            "assets": [
                *list(body_result.get("assets") or []),
                *list(supplementary_result.get("assets") or []),
            ],
            "asset_failures": [
                *list(body_result.get("asset_failures") or []),
                *list(supplementary_result.get("asset_failures") or []),
            ],
        }

    def describe_artifacts(
        self,
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ) -> ProviderArtifacts:
        content = raw_payload.content
        text_only = (
            normalize_text(content.route_kind if content is not None else "").lower()
            == PDF_FALLBACK
        )
        pdf_assets = list(
            content.extracted_assets if content is not None and text_only else []
        )
        return ProviderArtifacts(
            assets=[
                dict(item) for item in [*pdf_assets, *list(downloaded_assets or [])]
            ],
            asset_failures=[dict(item) for item in (asset_failures or [])],
            allow_related_assets=not text_only,
            text_only=text_only and not pdf_assets,
            skip_trace=trace_from_markers(
                [download_marker("oxfordacademic_assets_skipped_text_only")]
            )
            if text_only and not pdf_assets
            else [],
        )


__all__ = ["OxfordAcademicClient"]
