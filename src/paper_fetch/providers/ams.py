"""American Meteorological Society provider client."""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Mapping
from typing import Any, cast

from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.signals import HtmlExtractionFailure
from ..http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, PDF_MIME_TYPE
from ..extraction.html.provider_rules import (
    AMS_DOM_POSTPROCESS_CLEANUP_SELECTORS,
    AMS_FRONT_MATTER_EXACT_TEXTS,
    AMS_FRONT_MATTER_PUBLICATION_KEYWORDS,
    AMS_MARKDOWN_PROMO_TOKENS,
    AMS_POST_CONTENT_BREAK_TOKENS,
    AMS_SITE_RULE_OVERRIDES,
    ATYPON_FRONT_MATTER_CONTAINS_TOKENS,
    DomHooks,
    MarkdownHooks,
    ProviderCleanupRules,
    ProviderFormulaRules,
    ProviderFrontMatterRules,
    ProviderHtmlRules,
)
from ..metadata.types import ProviderMetadata
from ..publisher_identity import normalize_doi
from ..provider_catalog import ProviderSpec
from ..quality.html_signals import AMS_TEXT_MARKER_SIGNAL_SET
from ..tracing import fulltext_marker
from ..utils import normalize_text
from . import _ams_html, browser_workflow
from ._payloads import build_provider_payload
from ._pdf_candidates import extract_pdf_candidate_urls_from_html
from ._pdf_common import (
    default_pdf_headers,
    pdf_asset_output_dir,
    pdf_asset_profile_from_context,
    pdf_fetch_result_assets,
    pdf_fetch_result_warnings,
)
from ._pdf_fallback import PdfFallbackStrategy, PdfFetchFailure, fetch_pdf_over_http
from .base import ProviderClient, ProviderFailure, RawFulltextPayload
from .browser_workflow.direct_http import (
    DIRECT_HTTP_HTML_FETCHER_NAME,
    fetch_direct_http_html,
)
from ._registry import ProviderBundle, register_provider_bundle
from ..reason_codes import NO_RESULT, NOT_SUPPORTED, PDF_FALLBACK


register_provider_bundle(
    ProviderBundle(
        catalog=ProviderSpec(
            name="ams",
            display_name="AMS",
            official=True,
            domains=("journals.ametsoc.org", "ametsoc.org"),
            doi_prefixes=("10.1175/",),
            publisher_aliases=(
                "american meteorological society",
                "ams",
                "american meteorological society (ams)",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=True,
            client_factory_path="paper_fetch.providers.ams:AmsClient",
            status_order=9,
            base_domains=("journals.ametsoc.org",),
            crossref_pdf_position=0,
        ),
        html_rules=ProviderHtmlRules(
            name="ams",
            cleanup=ProviderCleanupRules(
                markdown_promo_tokens=AMS_MARKDOWN_PROMO_TOKENS,
                dom_postprocess_cleanup_selectors=AMS_DOM_POSTPROCESS_CLEANUP_SELECTORS,
                post_content_break_tokens=AMS_POST_CONTENT_BREAK_TOKENS,
            ),
            availability=AvailabilityPolicy(
                name="ams",
                site_rule_overrides=AMS_SITE_RULE_OVERRIDES,
                text_marker_signal_set=AMS_TEXT_MARKER_SIGNAL_SET,
            ),
            front_matter=ProviderFrontMatterRules(
                exact_texts=AMS_FRONT_MATTER_EXACT_TEXTS,
                contains_tokens=ATYPON_FRONT_MATTER_CONTAINS_TOKENS,
                publication_keywords=AMS_FRONT_MATTER_PUBLICATION_KEYWORDS,
            ),
            formula=ProviderFormulaRules(
                container_tokens=("formula",),
                display_selectors=("div.formula",),
            ),
            dom_hooks=DomHooks(
                before_block_normalization=_ams_html.ams_before_block_normalization,
                after_block_normalization=_ams_html.ams_after_block_normalization,
                body_container=_ams_html.ams_body_container,
                asset_body_container=_ams_html.ams_asset_body_container,
                asset_figure_extraction=_ams_html.ams_asset_figure_extraction,
            ),
            markdown_hooks=MarkdownHooks(
                normalize_markdown=_ams_html.ams_normalize_markdown,
                classify_heading=_ams_html.ams_classify_heading,
                keep_unknown_abstract_block=_ams_html.ams_keep_unknown_abstract_block,
            ),
        ),
        sources=("ams_html", "ams_pdf"),
    )
)


AMS_BROWSER_PROFILE = browser_workflow.make_atypon_browser_profile(
    "ams",
    fallback_author_extractor=_ams_html.extract_authors,
)
AMS_SICI_DOI_PATTERN = re.compile(
    r"^10\.1175/[0-9]{4}-[0-9]{4}\(\d{4}\)\d{3}<[^>]+>2\.0\.co;2$",
    flags=re.IGNORECASE,
)


def _append_unique(candidates: list[str], candidate: str | None) -> None:
    normalized = normalize_text(candidate)
    if normalized and normalized not in candidates:
        candidates.append(normalized)


def _ams_old_style_doi_url(doi: str) -> str | None:
    normalized = normalize_text(doi)
    if not AMS_SICI_DOI_PATTERN.match(normalized):
        return None
    return f"https://doi.org/{urllib.parse.quote(normalized, safe='/')}"


def _ams_pdf_candidate_urls_from_landing_url(
    landing_page_url: str | None, *, derive_from_article_url: bool
) -> list[str]:
    url = normalize_text(landing_page_url)
    if not url:
        return []
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return []

    candidates: list[str] = []

    def append_path(path: str, query: str = "") -> None:
        candidate = urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, path, "", query, "")
        )
        _append_unique(candidates, candidate)

    path = parsed.path
    lowered_path = path.lower()
    if "/downloadpdf/" in lowered_path or lowered_path.endswith(".pdf"):
        append_path(path, parsed.query)
        return candidates

    if not derive_from_article_url or not path.startswith("/view/"):
        return candidates

    suffix = path.removeprefix("/view")
    for prefix in ("/downloadpdf", "/downloadpdf/view"):
        append_path(f"{prefix}{suffix}")
        if suffix.lower().endswith(".xml"):
            append_path(f"{prefix}{suffix[:-4]}.pdf")
    return candidates


class AmsClient(browser_workflow.BrowserWorkflowClient):
    name = AMS_BROWSER_PROFILE.name
    profile = AMS_BROWSER_PROFILE

    def probe_status(self):
        return ProviderClient.probe_status(self)

    def allow_pdf_fallback_after_html_failure(
        self,
        *,
        html_failure_reason: str | None,
        html_failure_message: str | None,
    ) -> bool:
        del html_failure_reason, html_failure_message
        return True

    def html_candidates(self, doi: str, metadata: Mapping[str, Any]) -> list[str]:
        candidates: list[str] = []
        for candidate in super().html_candidates(doi, metadata):
            _append_unique(candidates, candidate)
        _append_unique(candidates, _ams_old_style_doi_url(doi))
        return candidates

    def pdf_candidates(self, doi: str, metadata: Mapping[str, Any]) -> list[str]:
        candidates: list[str] = []
        normalized_doi = normalize_doi(doi) or normalize_text(doi)
        old_style_doi = bool(AMS_SICI_DOI_PATTERN.match(normalized_doi))
        _append_unique(
            candidates,
            browser_workflow.extract_pdf_url_from_crossref(metadata),
        )
        for key in ("landing_page_url", "source_url"):
            for candidate in _ams_pdf_candidate_urls_from_landing_url(
                str(metadata.get(key) or "") or None,
                derive_from_article_url=not old_style_doi,
            ):
                _append_unique(candidates, candidate)
        return candidates

    def article_source_for_payload(self, raw_payload: RawFulltextPayload) -> str:
        if (
            raw_payload.content is not None
            and normalize_text(raw_payload.content.route_kind).lower() == PDF_FALLBACK
        ):
            return "ams_pdf"
        return "ams_html"

    def _pdf_headers(self, *, referer: str | None) -> dict[str, str]:
        user_agent = normalize_text(self.browser_user_agent) or self.user_agent
        return default_pdf_headers(user_agent, referer=referer)

    def _fetch_direct_http_pdf_payload(
        self,
        normalized_doi: str,
        metadata: ProviderMetadata,
        *,
        pdf_candidates: list[str],
        landing_page_url: str | None,
        html_failure_message: str,
        context=None,
        warnings: list[str] | None = None,
    ) -> RawFulltextPayload:
        if not pdf_candidates:
            raise ProviderFailure(
                NO_RESULT,
                (
                    "AMS direct HTTP HTML route did not return usable full text, "
                    "and no direct HTTP PDF candidates were available."
                ),
                warnings=list(warnings or []),
                source_trail=[
                    fulltext_marker(self.name, "fail", route="html"),
                    fulltext_marker(self.name, "fail", route=PDF_FALLBACK),
                ],
            )

        effective_asset_profile = pdf_asset_profile_from_context(context)
        try:
            pdf_result = PdfFallbackStrategy(
                transport=self.transport,
                headers=self._pdf_headers(referer=landing_page_url),
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                asset_profile=effective_asset_profile,
                asset_output_dir=pdf_asset_output_dir(
                    context,
                    asset_profile=effective_asset_profile,
                    doi=normalized_doi,
                ),
                fetcher=fetch_pdf_over_http,
            ).fetch(pdf_candidates)
        except PdfFetchFailure as exc:
            raise ProviderFailure(
                NO_RESULT,
                (
                    "AMS full text could not be retrieved via direct HTTP HTML "
                    f"or direct HTTP PDF fallback. HTML failure: {html_failure_message} "
                    f"PDF failure: {exc.message}"
                ),
                warnings=list(warnings or []),
                source_trail=[
                    fulltext_marker(self.name, "fail", route="html"),
                    fulltext_marker(self.name, "fail", route=PDF_FALLBACK),
                ],
            ) from exc

        final_url = urllib.parse.urljoin(
            pdf_result.source_url or pdf_candidates[0], pdf_result.final_url
        )
        return build_provider_payload(
            provider=self.name,
            route_kind=PDF_FALLBACK,
            source_url=final_url,
            content_type=PDF_MIME_TYPE,
            body=pdf_result.pdf_bytes,
            markdown_text=pdf_result.markdown_text,
            merged_metadata=metadata,
            diagnostics={
                PDF_FALLBACK: {
                    "candidates": list(pdf_candidates),
                    "html_failure_message": html_failure_message,
                    "fetcher": "direct_http",
                }
            },
            reason="Downloaded full text from AMS direct HTTP PDF fallback after AMS direct HTML was not usable.",
            suggested_filename=pdf_result.suggested_filename,
            html_failure_message=html_failure_message,
            extracted_assets=pdf_fetch_result_assets(pdf_result),
            warnings=[
                *(warnings or []),
                *pdf_fetch_result_warnings(pdf_result),
                "Full text was extracted from AMS direct HTTP PDF fallback after AMS direct HTML was not usable.",
            ],
            trace_markers=[
                fulltext_marker(self.name, "fail", route="html"),
                fulltext_marker(self.name, "ok", route=PDF_FALLBACK),
            ],
            content_needs_local_copy=True,
            needs_local_copy=True,
        )

    def _recover_pdf_payload_from_abstract_only_html(
        self,
        doi: str,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
        *,
        context=None,
    ) -> RawFulltextPayload:
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            raise ProviderFailure(
                NOT_SUPPORTED, "AMS PDF fallback recovery requires a DOI."
            )
        landing_page_url = (
            str(metadata.get("landing_page_url") or raw_payload.source_url or "")
            or None
        )
        html_failure_message = "AMS HTML route only exposed abstract-level content after markdown extraction."
        return self._fetch_direct_http_pdf_payload(
            normalized_doi,
            metadata,
            pdf_candidates=self.pdf_candidates(normalized_doi, metadata),
            landing_page_url=landing_page_url,
            html_failure_message=html_failure_message,
            context=context,
            warnings=[
                *raw_payload.warnings,
                (
                    "AMS HTML route only exposed abstract-level content after "
                    "markdown extraction; attempting direct HTTP PDF fallback."
                ),
            ],
        )

    def fetch_raw_fulltext(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        context=None,
    ) -> RawFulltextPayload:
        context = self._runtime_context(context)
        provider_metadata = cast(ProviderMetadata, metadata)
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            raise ProviderFailure(
                NOT_SUPPORTED, "AMS full-text retrieval requires a DOI."
            )
        landing_page_url = str(metadata.get("landing_page_url") or "") or None
        html_candidates = self.html_candidates(normalized_doi, provider_metadata)
        html_result = None
        try:
            html_result = fetch_direct_http_html(
                self,
                html_candidates,
                landing_page_url=landing_page_url,
            )
            markdown_text, extraction = self.deps._cached_browser_workflow_markdown(
                self,
                html_result.html,
                html_result.final_url,
                metadata=provider_metadata,
                context=context,
            )
        except HtmlExtractionFailure as exc:
            pdf_candidates = self.pdf_candidates(normalized_doi, provider_metadata)
            if html_result is not None:
                for pdf_candidate in reversed(
                    extract_pdf_candidate_urls_from_html(
                        html_result.html,
                        html_result.final_url,
                    )
                ):
                    if pdf_candidate and pdf_candidate not in pdf_candidates:
                        pdf_candidates.insert(0, pdf_candidate)
            return self._fetch_direct_http_pdf_payload(
                normalized_doi,
                provider_metadata,
                pdf_candidates=pdf_candidates,
                landing_page_url=landing_page_url,
                html_failure_message=exc.message,
                context=context,
                warnings=[
                    (
                        "AMS direct HTTP HTML route did not return usable full text; "
                        "attempting direct HTTP PDF fallback."
                    )
                ],
            )
        except Exception as exc:
            message = normalize_text(str(exc)) or exc.__class__.__name__
            raise ProviderFailure(
                NO_RESULT,
                f"AMS direct HTTP HTML route failed ({message}).",
                source_trail=[fulltext_marker(self.name, "fail", route="html")],
            ) from exc

        return browser_workflow._browser_workflow_html_payload(
            self,
            html_result,
            markdown_text=markdown_text,
            extraction=extraction,
            fetcher=DIRECT_HTTP_HTML_FETCHER_NAME,
            warnings=[],
        )

    def to_article_model(self, *args, **kwargs):
        article = super().to_article_model(*args, **kwargs)
        return _ams_html.normalize_article_model(article)
