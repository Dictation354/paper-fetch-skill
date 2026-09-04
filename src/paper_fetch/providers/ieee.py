"""IEEE Xplore direct HTML provider client."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any
from collections.abc import Mapping

from ..config import build_browser_user_agent, build_publisher_user_agent
from ..extraction.html import decode_html
from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.provider_rules import (
    IEEE_ACCESS_BLOCK_TEXT_TOKENS,
    IEEE_AVAILABILITY_DROP_KEYWORDS,
    IEEE_EXTRACTION_CLEANUP_SELECTORS,
    IEEE_MARKDOWN_PROMO_TOKENS,
    IEEE_SITE_RULE_OVERRIDES,
    ProviderCleanupRules,
    ProviderHtmlRules,
)
from ..http import (
    DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
    HttpTransport,
    PDF_MIME_TYPE,
    RequestFailure,
    redact_url_for_diagnostics,
)
from ..http.headers import header_value
from ..metadata.types import ProviderMetadata
from ..models import AssetProfile
from ..provider_catalog import ProviderSpec
from ..publisher_identity import normalize_doi
from ..quality.html_availability import (
    HtmlQualityAssessor,
    availability_failure_message,
)
from ..quality.html_signals import (
    IEEE_AVAILABILITY_OVERRIDES,
    IEEE_TEXT_MARKER_SIGNAL_SET,
)
from ..reason_codes import (
    ABSTRACT_ONLY,
    NO_RESULT,
    NOT_SUPPORTED,
    OK,
    PDF_FALLBACK,
)
from ..runtime import RuntimeContext
from ..tracing import download_marker, fulltext_marker, trace_from_markers
from ..utils import normalize_text
from . import _ieee_browser_html as ieee_browser_html
from . import _ieee_html as ieee_html
from . import _ieee_landing as ieee_landing
from . import _ieee_metadata as ieee_metadata
from . import _ieee_recovery_policy as ieee_recovery_policy
from ._ieee_routes import IEEE_ROUTES, landing_route_name
from . import _ieee_supplementary as ieee_supplementary
from . import _ieee_url as ieee_url
from . import browser_runtime
from ._pdf_common import (
    pdf_asset_output_dir,
    pdf_asset_profile_from_context,
    pdf_fetch_result_assets,
    pdf_fetch_result_warnings,
)
from ._pdf_fallback import (
    PdfFallbackStrategy,
    PdfFetchFailure,
    PdfRequestContext,
    fetch_pdf_over_http,
    fetch_pdf_with_browser,
)
from ._payloads import (
    build_provider_payload,
    provider_failure_diagnostics as _provider_failure_diagnostics,
)
from ._registry import ProviderBundle
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
    RawFulltextPayload as _RawFulltextPayload,
    build_provider_status_check,
    combine_provider_failures,
    map_request_failure,
    summarize_capability_status,
)

__all__ = ["IeeeClient"]


def _pdf_failure_diagnostics(failure: PdfFetchFailure | None) -> dict[str, Any] | None:
    if failure is None:
        return None
    diagnostics: dict[str, Any] = {"kind": failure.kind, "message": failure.message}
    if failure.details:
        diagnostics["details"] = dict(failure.details)
    return diagnostics


_ieee_pdf_browser_recovery_allowed = ieee_recovery_policy.pdf_browser_recovery_allowed
_ieee_html_browser_recovery_allowed = ieee_recovery_policy.html_browser_recovery_allowed


class IeeeClient(ProviderClient):
    name = "ieee"

    def __init__(self, transport: HttpTransport, env: Mapping[str, str]) -> None:
        self.transport = transport
        self.env = dict(env)
        self.user_agent = build_publisher_user_agent(env)
        self.browser_user_agent = build_browser_user_agent(env)

    def probe_status(self) -> ProviderStatusResult:
        browser_status = browser_runtime.probe_runtime_status(
            self.env,
            provider=self.name,
        )
        return summarize_capability_status(
            self.name,
            official_provider=self.official_provider,
            checks=[
                build_provider_status_check(
                    "html_route",
                    OK,
                    "IEEE Xplore direct REST HTML and selected-browser HTML fallback routes are available when the article exposes ml_html/full HTML.",
                    details={"mode": "direct_rest_html_or_selected_browser_html"},
                ),
                build_provider_status_check(
                    "browser_fallback",
                    OK,
                    (
                        "IEEE direct routes remain available; selected-browser recovery "
                        f"is {browser_status.status}."
                    ),
                    details={
                        "backend": "camoufox",
                        "fallback_status": browser_status.status,
                        "fallback_available": browser_status.available,
                        "notes": list(browser_status.notes),
                        "checks": [check.to_dict() for check in browser_status.checks],
                    },
                ),
                build_provider_status_check(
                    PDF_FALLBACK,
                    OK,
                    "IEEE Xplore PDF fallback is available when direct HTTP or a seeded browser returns a real PDF payload; body/all asset requests can save exported PDF images when artifacts are enabled.",
                    details={"mode": "direct_http_pdf_or_seeded_browser_pdf"},
                ),
            ],
        )

    def _landing_headers(self) -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": self.user_agent,
        }

    def _rest_headers(self, document_url: str) -> dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Referer": document_url,
            "User-Agent": self.user_agent,
            "x-security-request": "required",
        }

    def _document_url(self, article_number: str) -> str:
        return ieee_url.IEEE_DOCUMENT_URL_TEMPLATE.format(article_number=article_number)

    def _rest_url(self, article_number: str) -> str:
        return ieee_url.IEEE_REST_URL_TEMPLATE.format(article_number=article_number)

    def _multimedia_url(self, article_number: str) -> str:
        return ieee_url.IEEE_MULTIMEDIA_URL_TEMPLATE.format(
            article_number=article_number
        )

    def _multimedia_headers(self, document_url: str) -> dict[str, str]:
        headers = self._rest_headers(document_url)
        headers.update(
            {
                "Origin": ieee_url.IEEE_BASE_URL,
                "X-Requested-With": "XMLHttpRequest",
                "cache-http-response": "true",
                "Pragma": "no-cache",
                "Cache-Control": "no-store",
            }
        )
        return headers

    def _fetch_reference_metadata(
        self, article_number: str, document_url: str, *, expected_count: int = 0
    ) -> list[dict[str, str | None]]:
        return ieee_metadata.fetch_ieee_reference_metadata(
            self.transport,
            article_number,
            headers=self._rest_headers(document_url),
            timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
            decode_body=decode_html,
            expected_count=expected_count,
        )

    def _fetch_multimedia_assets(
        self, landing_attempt: ieee_metadata.IeeeLandingAttempt
    ) -> list[dict[str, str]]:
        if not landing_attempt.article_number:
            return []
        document_url = self._document_url(landing_attempt.article_number)
        return ieee_supplementary.fetch_ieee_multimedia_assets(
            self.transport,
            landing_attempt,
            multimedia_url=self._multimedia_url(landing_attempt.article_number),
            headers=self._multimedia_headers(document_url),
            timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
        )

    def _html_extraction_assets_with_landing_payloads(
        self,
        extraction: ieee_html.IeeeHtmlExtraction,
        landing_attempt: ieee_metadata.IeeeLandingAttempt,
    ) -> list[dict[str, Any]]:
        return ieee_html._dedupe_ieee_assets_by_priority(
            [
                *list(extraction.extracted_assets),
                *self._fetch_multimedia_assets(landing_attempt),
            ],
            merge_fields=ieee_html.IEEE_ASSET_URL_FIELDS,
        )

    def fetch_metadata(self, query: Mapping[str, str | None]) -> ProviderMetadata:
        raise ProviderFailure(
            NOT_SUPPORTED,
            "IEEE publisher metadata is read from the Xplore landing page during full-text retrieval; routing relies on Crossref metadata.",
        )

    def _fetch_landing_attempt(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        context: RuntimeContext | None = None,
    ) -> ieee_metadata.IeeeLandingAttempt:
        return ieee_landing.fetch_ieee_landing_attempt(
            self,
            doi,
            metadata,
            context=context,
        )

    def _fetch_dynamic_html_payload(
        self,
        landing_attempt: ieee_metadata.IeeeLandingAttempt,
        *,
        context: RuntimeContext | None = None,
    ) -> _RawFulltextPayload:
        article_number = landing_attempt.article_number
        document_url = self._document_url(article_number)
        rest_url = self._rest_url(article_number)
        try:
            response = self.transport.request(
                "GET",
                rest_url,
                headers=self._rest_headers(document_url),
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                retry_on_transient=True,
            )
        except RequestFailure as exc:
            raise map_request_failure(exc) from exc
        response_url = ieee_url._absolute_ieee_url(
            str(response.get("url") or rest_url), rest_url
        )
        body = bytes(response.get("body") or b"")
        html_text = decode_html(
            body,
            content_type=header_value(response.get("headers"), "content-type"),
        )
        extraction = ieee_html._extract_ieee_html(
            html_text,
            response_url,
            metadata=landing_attempt.merged_metadata,
            context=context,
        )
        diagnostics = HtmlQualityAssessor("ieee").assess(
            extraction.markdown_text,
            landing_attempt.merged_metadata,
            html_text=extraction.html_text,
            title=str(landing_attempt.merged_metadata.get("title") or ""),
            requested_url=rest_url,
            final_url=response_url,
            response_status=int(response.get("status_code") or 0) or None,
            section_hints=extraction.section_hints,
        )
        if not diagnostics.accepted:
            raise ProviderFailure(NO_RESULT, availability_failure_message(diagnostics))
        content_type = header_value(
            response.get("headers"), "content-type", "text/html"
        )
        extracted_assets = self._html_extraction_assets_with_landing_payloads(
            extraction, landing_attempt
        )
        return build_provider_payload(
            provider=self.name,
            route_kind="html",
            route_name="rest_html",
            source_url=response_url,
            content_type=content_type,
            body=extraction.html_text.encode("utf-8"),
            markdown_text=extraction.markdown_text,
            merged_metadata=landing_attempt.merged_metadata,
            diagnostics={
                "availability_diagnostics": diagnostics.to_dict(),
                "extraction": {
                    "abstract_sections": extraction.abstract_sections,
                    "section_hints": extraction.section_hints,
                    "marker_counts": extraction.marker_counts,
                },
                "landing": dict(landing_attempt.diagnostics),
            },
            reason="Downloaded full text from the IEEE Xplore dynamic HTML route.",
            extracted_assets=extracted_assets,
            browser_context_seed=landing_attempt.browser_context_seed,
            trace_markers=[fulltext_marker("ieee", "ok", route="html")],
        )

    def _fetch_browser_html_payload(
        self,
        landing_attempt: ieee_metadata.IeeeLandingAttempt,
        *,
        direct_html_failure: ProviderFailure | None,
        context: RuntimeContext,
    ) -> _RawFulltextPayload:
        article_number = landing_attempt.article_number
        runtime_config = browser_runtime.load_runtime_config(
            context.env or self.env,
            provider=self.name,
            doi=landing_attempt.normalized_doi,
        )
        return ieee_browser_html.fetch_ieee_browser_html_payload(
            provider_name=self.name,
            browser_user_agent=self.browser_user_agent,
            landing_attempt=landing_attempt,
            document_url=self._document_url(article_number),
            rest_url=self._rest_url(article_number),
            direct_html_failure=direct_html_failure,
            context=context,
            runtime_config=runtime_config,
            extraction_assets=self._html_extraction_assets_with_landing_payloads,
        )

    def _fetch_pdf_payload(
        self,
        landing_attempt: ieee_metadata.IeeeLandingAttempt,
        *,
        html_failure_message: str,
        warnings: list[str],
        context: RuntimeContext,
        html_trace_markers: list[str] | None = None,
    ) -> _RawFulltextPayload:
        document_url = self._document_url(landing_attempt.article_number)
        candidates = ieee_url._pdf_candidates(landing_attempt)
        headers = {
            "User-Agent": self.user_agent,
            "Referer": document_url,
        }
        artifact_dir = (
            context.download_dir / "ieee_pdf_fallback"
            if context.download_dir is not None
            and context.artifact_store is not None
            and context.artifact_store.allows_auxiliary_artifacts
            else None
        )
        effective_asset_profile = pdf_asset_profile_from_context(context)
        asset_output_dir = pdf_asset_output_dir(
            context,
            asset_profile=effective_asset_profile,
            doi=landing_attempt.normalized_doi,
        )
        direct_failure: PdfFetchFailure | None = None
        try:
            pdf_result = PdfFallbackStrategy(
                transport=self.transport,
                provider_name="ieee",
                headers=headers,
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                artifact_dir=artifact_dir,
                asset_profile=effective_asset_profile,
                asset_output_dir=asset_output_dir,
                seed_urls=[document_url],
                expected_identity={"doi": landing_attempt.normalized_doi},
                context=context,
                fetcher=fetch_pdf_over_http,
            ).fetch(candidates)
            fetcher = "direct_http"
        except PdfFetchFailure as exc:
            direct_failure = exc
            if not _ieee_pdf_browser_recovery_allowed(exc):
                raise
            runtime_config = browser_runtime.load_runtime_config(
                context.env or self.env,
                provider=self.name,
                doi=landing_attempt.normalized_doi,
            )
            browser_seed = browser_runtime.merge_browser_context_seeds(
                landing_attempt.browser_context_seed
            )
            browser_seed_urls = ieee_url._dedupe_urls(
                [
                    str(browser_seed.get("browser_final_url") or ""),
                    landing_attempt.response_url,
                    document_url,
                ]
            )

            def run_browser_pdf(active_artifact_dir: Path):
                return fetch_pdf_with_browser(
                    candidates,
                    artifact_dir=active_artifact_dir,
                    asset_profile=effective_asset_profile,
                    asset_output_dir=asset_output_dir,
                    browser_user_agent=normalize_text(
                        str(browser_seed.get("browser_user_agent") or "")
                    )
                    or self.browser_user_agent,
                    browser_cookies=list(browser_seed.get("browser_cookies") or []),
                    referer=document_url,
                    seed_urls=browser_seed_urls,
                    allow_pdf_only=True,
                    request=PdfRequestContext(
                        expected_identity={"doi": landing_attempt.normalized_doi},
                        runtime=context,
                    ),
                    browser_config=runtime_config,
                )

            try:
                if artifact_dir is None:
                    with tempfile.TemporaryDirectory(
                        prefix="paper_fetch_ieee_pdf_"
                    ) as tempdir:
                        pdf_result = run_browser_pdf(Path(tempdir))
                else:
                    pdf_result = run_browser_pdf(artifact_dir)
                fetcher = "camoufox_browser"
            except PdfFetchFailure as browser_exc:
                raise PdfFetchFailure(
                    browser_exc.kind,
                    (
                        "IEEE PDF fallback failed. "
                        f"Direct HTTP failure: {direct_failure.message} "
                        f"Browser fallback failure: {browser_exc.message}"
                    ),
                    details={
                        "candidates": [
                            redact_url_for_diagnostics(item) for item in candidates
                        ],
                        "direct_failure": _pdf_failure_diagnostics(direct_failure),
                        "browser_failure": _pdf_failure_diagnostics(browser_exc),
                    },
                ) from browser_exc
        pdf_diagnostics = {
            "fetcher": fetcher,
            "candidates": [redact_url_for_diagnostics(item) for item in candidates],
            "direct_failure": _pdf_failure_diagnostics(direct_failure),
        }
        payload_warnings = list(warnings)
        if direct_failure is not None:
            payload_warnings.append(
                f"IEEE direct PDF fallback was not usable ({direct_failure.message}); browser PDF fallback succeeded."
            )
        payload_warnings.append(
            "Full text was extracted from IEEE PDF fallback after the IEEE HTML paths were not usable."
        )
        return build_provider_payload(
            provider=self.name,
            route_kind=PDF_FALLBACK,
            route_name=("browser_pdf" if direct_failure is not None else "direct_pdf"),
            source_url=pdf_result.final_url,
            content_type=PDF_MIME_TYPE,
            body=pdf_result.pdf_bytes,
            markdown_text=pdf_result.markdown_text,
            merged_metadata=landing_attempt.merged_metadata,
            diagnostics={PDF_FALLBACK: pdf_diagnostics},
            extracted_assets=pdf_fetch_result_assets(pdf_result),
            reason=(
                f"Downloaded full text from the IEEE Xplore {fetcher} PDF fallback route."
                if fetcher != "direct_http"
                else "Downloaded full text from the IEEE Xplore direct PDF fallback route."
            ),
            suggested_filename=pdf_result.suggested_filename,
            html_failure_message=html_failure_message,
            needs_local_copy=True,
            warnings=[*payload_warnings, *pdf_fetch_result_warnings(pdf_result)],
            trace_markers=[
                *list(
                    html_trace_markers
                    or [fulltext_marker("ieee", "fail", route="html")]
                ),
                fulltext_marker("ieee", "ok", route=PDF_FALLBACK),
            ],
        )

    def _abstract_only_payload(
        self,
        landing_attempt: ieee_metadata.IeeeLandingAttempt,
        *,
        warnings: list[str],
        trace_markers: list[str],
        diagnostics: Mapping[str, Any] | None = None,
    ) -> _RawFulltextPayload:
        markdown_text = ieee_metadata._abstract_markdown(
            landing_attempt.merged_metadata
        )
        if not markdown_text:
            raise ProviderFailure(
                NO_RESULT,
                "IEEE landing metadata did not include provider abstract content.",
            )
        return build_provider_payload(
            provider=self.name,
            route_kind=ABSTRACT_ONLY,
            route_name=landing_route_name(landing_attempt.acquisition_source),
            source_url=landing_attempt.response_url,
            content_type="text/markdown",
            body=markdown_text.encode("utf-8"),
            markdown_text=markdown_text,
            merged_metadata=landing_attempt.merged_metadata,
            diagnostics=diagnostics,
            reason="IEEE provider route only exposed abstract-level content.",
            warnings=warnings,
            trace_markers=[*trace_markers, fulltext_marker("ieee", ABSTRACT_ONLY)],
        )

    def fetch_raw_fulltext(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        context: RuntimeContext | None = None,
    ) -> _RawFulltextPayload:
        runtime_context = self._runtime_context(context)
        landing_attempt = self._fetch_landing_attempt(
            doi, metadata, context=runtime_context
        )
        pdf_failure_diagnostics: dict[str, Any] | None = None

        def run_browser_html(state: ProviderWaterfallState) -> _RawFulltextPayload:
            return self._fetch_browser_html_payload(
                landing_attempt,
                direct_html_failure=state.failure("html"),
                context=runtime_context,
            )

        def run_pdf(state: ProviderWaterfallState) -> _RawFulltextPayload:
            nonlocal pdf_failure_diagnostics
            html_failure = state.failure("html")
            browser_html_failure = state.failure("browser_html")
            html_failure_message = (
                html_failure.message
                if html_failure is not None
                else "IEEE dynamic HTML route failed."
            )
            if browser_html_failure is not None:
                html_failure_message = f"{html_failure_message} Browser HTML fallback: {browser_html_failure.message}"
            try:
                return self._fetch_pdf_payload(
                    landing_attempt,
                    html_failure_message=html_failure_message,
                    warnings=[],
                    context=runtime_context,
                    html_trace_markers=state.source_trail,
                )
            except PdfFetchFailure as exc:
                pdf_failure_diagnostics = _pdf_failure_diagnostics(exc)
                raise ProviderFailure(NO_RESULT, exc.message) from exc

        def run_abstract(state: ProviderWaterfallState) -> _RawFulltextPayload:
            return self._abstract_only_payload(
                landing_attempt,
                warnings=[],
                trace_markers=state.source_trail,
                diagnostics={
                    "html_failure": _provider_failure_diagnostics(
                        state.failure("html")
                    ),
                    "browser_html_failure": _provider_failure_diagnostics(
                        state.failure("browser_html")
                    ),
                    PDF_FALLBACK: pdf_failure_diagnostics
                    or _provider_failure_diagnostics(state.failure("pdf")),
                },
            )

        def final_failure(state: ProviderWaterfallState) -> ProviderFailure:
            failures = [
                (
                    "html",
                    state.failure("html")
                    or ProviderFailure(NO_RESULT, "IEEE dynamic HTML route failed."),
                ),
                (
                    "pdf",
                    state.failure("pdf")
                    or ProviderFailure(NO_RESULT, "IEEE PDF fallback failed."),
                ),
                (
                    "abstract",
                    state.failure("abstract")
                    or ProviderFailure(NO_RESULT, "IEEE abstract fallback failed."),
                ),
            ]
            browser_html_failure = state.failure("browser_html")
            if browser_html_failure is not None:
                failures.insert(1, ("browser_html", browser_html_failure))
            combined = combine_provider_failures(failures)
            return ProviderFailure(
                combined.code,
                "IEEE full text could not be retrieved. " + combined.message,
                warnings=state.warnings,
                source_trail=[
                    fulltext_marker("ieee", "fail", route="html"),
                    fulltext_marker("ieee", "fail", route="browser_html"),
                    fulltext_marker("ieee", "fail", route="pdf"),
                ],
            )

        return run_provider_waterfall(
            [
                ProviderWaterfallStep(
                    label="html",
                    route_name="rest_html",
                    run=lambda _state: self._fetch_dynamic_html_payload(
                        landing_attempt, context=runtime_context
                    ),
                    failure_marker=fulltext_marker("ieee", "fail", route="html"),
                    continue_codes=DEFAULT_WATERFALL_CONTINUE_CODES,
                    failure_warning=lambda failure, _state: (
                        f"IEEE dynamic HTML route was not usable ({failure.message}); "
                        + (
                            "attempting selected-browser HTML fallback."
                            if _ieee_html_browser_recovery_allowed(failure)
                            else "browser recovery is not eligible; continuing to PDF fallback."
                        )
                    ),
                ),
                ProviderWaterfallStep(
                    label="browser_html",
                    run=run_browser_html,
                    condition=lambda state: _ieee_html_browser_recovery_allowed(
                        state.failure("html")
                    ),
                    failure_marker=fulltext_marker(
                        "ieee", "fail", route="browser_html"
                    ),
                    continue_codes=DEFAULT_WATERFALL_CONTINUE_CODES,
                    failure_warning=lambda failure, _state: (
                        f"IEEE browser HTML fallback was not usable ({failure.message}); attempting PDF fallback."
                    ),
                ),
                ProviderWaterfallStep(
                    label="pdf",
                    route_name="direct_pdf",
                    run=run_pdf,
                    failure_marker=fulltext_marker("ieee", "fail", route="pdf"),
                    continue_codes=DEFAULT_WATERFALL_CONTINUE_CODES,
                    failure_warning=lambda failure, _state: (
                        f"IEEE PDF fallback was not usable ({failure.message})."
                    ),
                ),
                ProviderWaterfallStep(
                    label="abstract",
                    route_name="direct_landing",
                    run=run_abstract,
                    continue_codes=DEFAULT_WATERFALL_CONTINUE_CODES,
                ),
            ],
            doi=landing_attempt.normalized_doi,
            metadata=metadata,
            context=runtime_context,
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
        extraction = ieee_html._extract_ieee_html(
            html_text, source_url, metadata=metadata, context=context
        )
        return extraction.markdown_text, {
            "abstract_sections": extraction.abstract_sections,
            "section_hints": extraction.section_hints,
            "marker_counts": extraction.marker_counts,
        }

    def download_related_assets(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        raw_payload: _RawFulltextPayload,
        output_dir: Path | None,
        *,
        asset_profile: AssetProfile = "all",
        context: RuntimeContext | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        context = self._runtime_context(context, output_dir=output_dir)
        content = raw_payload.content
        browser_runtime_config = None
        if (
            output_dir is not None
            and asset_profile != "none"
            and normalize_text(
                content.route_kind if content is not None else ""
            ).lower()
            == "html"
        ):
            browser_runtime_config = browser_runtime.load_runtime_config(
                context.env or self.env,
                provider=self.name,
                doi=normalize_doi(doi) or doi,
            )
        return ieee_supplementary.download_ieee_related_assets(
            self.transport,
            doi,
            metadata,
            raw_payload,
            output_dir,
            user_agent=self.user_agent,
            env=context.env or self.env,
            asset_profile=asset_profile,
            browser_runtime_config=browser_runtime_config,
            runtime_context=context,
        )

    def asset_download_failure_warning(
        self, exc: ProviderFailure | RequestFailure | OSError
    ) -> str:
        message = exc.message if isinstance(exc, ProviderFailure) else str(exc)
        return f"IEEE related assets could not be downloaded: {message}"

    def to_article_model(
        self,
        metadata: Mapping[str, Any],
        raw_payload: _RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
        context: RuntimeContext | None = None,
    ):
        del context
        return ieee_metadata.build_ieee_article_model(
            metadata,
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
        )

    def describe_artifacts(
        self,
        raw_payload: _RawFulltextPayload,
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
        if (
            normalize_text(content.route_kind if content is not None else "").lower()
            != PDF_FALLBACK
        ):
            return artifacts
        pdf_assets = list(content.extracted_assets if content is not None else [])
        skip_trace = (
            []
            if pdf_assets
            else trace_from_markers([download_marker("ieee_assets_skipped_text_only")])
        )
        return ProviderArtifacts(
            assets=[*list(artifacts.assets), *pdf_assets],
            asset_failures=list(artifacts.asset_failures),
            allow_related_assets=False,
            text_only=not pdf_assets,
            skip_trace=skip_trace,
        )


PROVIDER_BUNDLE = ProviderBundle(
    client_factory=IeeeClient,
    catalog=ProviderSpec(
        name="ieee",
        display_name="IEEE",
        official=True,
        domains=("ieeexplore.ieee.org",),
        doi_prefixes=("10.1109/",),
        publisher_aliases=(
            "ieee",
            "institute of electrical and electronics engineers",
        ),
        asset_default="body",
        probe_capability="routing_signal",
        provider_managed_abstract_only=True,
        status_order=6,
        routes=IEEE_ROUTES,
    ),
    html_rules=ProviderHtmlRules(
        name="ieee",
        noise_profile="ieee",
        cleanup=ProviderCleanupRules(
            markdown_promo_tokens=IEEE_MARKDOWN_PROMO_TOKENS,
            extraction_cleanup_selectors=IEEE_EXTRACTION_CLEANUP_SELECTORS,
            extraction_drop_keywords=IEEE_AVAILABILITY_DROP_KEYWORDS,
            access_block_text_tokens=IEEE_ACCESS_BLOCK_TEXT_TOKENS,
        ),
        availability=AvailabilityPolicy(
            name="ieee",
            site_rule_overrides=IEEE_SITE_RULE_OVERRIDES,
            text_marker_signal_set=IEEE_TEXT_MARKER_SIGNAL_SET,
            overrides=IEEE_AVAILABILITY_OVERRIDES,
        ),
    ),
    sources=("ieee_html", "ieee_pdf"),
)
