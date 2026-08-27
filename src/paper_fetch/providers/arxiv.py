"""arXiv provider client orchestration."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any
from collections.abc import Mapping, Sequence
import urllib.parse

from ..arxiv_id import (
    arxiv_id_from_doi,
    arxiv_id_from_query,
    canonical_arxiv_doi,
    canonical_arxiv_html_url,
    canonical_arxiv_pdf_url,
    normalize_arxiv_id,
)
from ..config import build_publisher_user_agent, build_user_agent
from ..failure import FailureDiagnostics
from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.provider_rules import ProviderHtmlRules
from ..http import (
    DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
    HttpTransport,
    PDF_MIME_TYPE,
    RequestFailure,
    classify_network_error,
)
from ..metadata.types import ProviderMetadata
from ..models import (
    AssetProfile,
    SourceKind,
    article_from_markdown,
    metadata_only_article,
)
from ..provider_catalog import ProviderRouteSpec, ProviderSpec
from ..runtime import RuntimeContext
from ..tracing import download_marker, fulltext_marker, trace_from_markers
from ..utils import empty_asset_results, normalize_text
from ._arxiv_assets import (
    ARXIV_ASSET_RETRY_POLICY,
    ARXIV_IMAGE_ACCEPT,
    inline_arxiv_source_assets_in_markdown,
)
from ._arxiv_asset_strategy import (
    ArxivHtmlAssetDownloadPlan,
    download_arxiv_html_figure_assets,
)
from ._arxiv_atom import (
    ARXIV_API_DELAY_SECONDS,
    ARXIV_API_NUM_RETRIES,
    ARXIV_API_TIMEOUT_SECONDS,
    ArxivSearch as _ArxivSearch,
    InternalArxivApiClient as _InternalArxivApiClient,
)
from ._arxiv_html import _extract_arxiv_html_markdown, _looks_like_html
from ._arxiv_metadata import (
    _arxiv_id_from_metadata_or_doi,
    _dedupe_strings,
    _first_header_value,
    _merge_arxiv_metadata_layers,
    _minimal_arxiv_metadata,
    metadata_from_arxiv_result as _metadata_from_arxiv_result,
)
from ._payloads import build_provider_payload
from ._pdf_fallback import PdfFallbackStrategy, PdfFetchFailure, fetch_pdf_over_http
from ._pdf_common import (
    default_pdf_headers,
    pdf_asset_output_dir,
    pdf_asset_profile_from_context,
    pdf_fetch_result_assets,
    pdf_fetch_result_warnings,
)
from ._registry import ProviderBundle, register_provider_bundle
from ._waterfall import (
    DEFAULT_WATERFALL_CONTINUE_CODES,
    ProviderWaterfallStep,
    ProviderWaterfallState,
    run_provider_waterfall,
)
from ..reason_codes import ERROR, NO_RESULT, NOT_SUPPORTED, OK, PDF_FALLBACK
from .base import (
    ProviderArtifacts,
    ProviderClient,
    ProviderFailure,
    ProviderStatusResult,
    RawFulltextPayload,
    build_provider_status_check,
    map_request_failure,
    summarize_capability_status,
)


register_provider_bundle(
    ProviderBundle(
        catalog=ProviderSpec(
            name="arxiv",
            display_name="arXiv",
            official=True,
            domains=("arxiv.org",),
            doi_prefixes=("10.48550/",),
            publisher_aliases=("arxiv",),
            asset_default="body",
            probe_capability="metadata_api",
            provider_managed_abstract_only=False,
            client_factory_path="paper_fetch.providers.arxiv:ArxivClient",
            status_order=7,
            metadata_probe_short_circuit=(
                "paper_fetch.providers._arxiv_metadata:"
                "arxiv_metadata_probe_short_circuit"
            ),
            persist_provider_html=True,
            routes=(
                ProviderRouteSpec(
                    name="atom_metadata",
                    kind="metadata",
                    transport="api",
                    timeout_seconds=60,
                    qps=1 / 3,
                    rate_policy="arxiv_three_second_pacing",
                ),
                ProviderRouteSpec(name="official_html", kind="html"),
                ProviderRouteSpec(
                    name="direct_pdf",
                    kind="pdf",
                    requires_pdf_conversion=True,
                ),
                ProviderRouteSpec(
                    name="source_assets",
                    kind="assets",
                    hosts=("arxiv.org",),
                    qps=1 / 3,
                    rate_policy="arxiv_three_second_pacing",
                    asset_scope="body",
                ),
            ),
        ),
        html_rules=ProviderHtmlRules(
            name="arxiv",
            availability=AvailabilityPolicy(name="arxiv", no_signals=True),
        ),
        asset_retry=ARXIV_ASSET_RETRY_POLICY,
        sources=("arxiv_html", "arxiv_pdf"),
    )
)


class ArxivClient(ProviderClient):
    name = "arxiv"

    def __init__(
        self,
        transport: HttpTransport,
        env: Mapping[str, str],
        api_client: Any | None = None,
    ) -> None:
        self.transport = transport
        self.env = dict(env)
        self.user_agent = build_publisher_user_agent(env)
        self.api_enrichment_enabled = True
        self.api_client = api_client or _InternalArxivApiClient(
            transport=self.transport,
            user_agent=build_user_agent(env),
        )

    def probe_status(self) -> ProviderStatusResult:
        return summarize_capability_status(
            self.name,
            official_provider=self.official_provider,
            checks=[
                build_provider_status_check(
                    "metadata_api",
                    OK,
                    (
                        "arXiv API metadata route uses the internal Atom client for "
                        "default metadata enrichment."
                    ),
                    details={
                        "mode": "arxiv_api",
                        "client": "internal_atom",
                        "client_timeout_seconds": ARXIV_API_TIMEOUT_SECONDS,
                        "client_delay_seconds": ARXIV_API_DELAY_SECONDS,
                        "client_num_retries": ARXIV_API_NUM_RETRIES,
                    },
                ),
                build_provider_status_check(
                    "html_route",
                    OK,
                    "arXiv official HTML route is the primary full-text path and is available without local converters.",
                    details={"mode": "direct_http_html"},
                ),
                build_provider_status_check(
                    PDF_FALLBACK,
                    OK,
                    (
                        "arXiv PDF fallback is available when official HTML "
                        "is not usable."
                    ),
                    details={"mode": "direct_http_pdf"},
                ),
            ],
        )

    def _html_headers(self) -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": self.user_agent,
        }

    def _image_headers(self) -> dict[str, str]:
        return {
            "Accept": ARXIV_IMAGE_ACCEPT,
            "User-Agent": self.user_agent,
        }

    def _pdf_headers(self, *, referer: str | None = None) -> dict[str, str]:
        return default_pdf_headers(self.user_agent, referer=referer)

    def fetch_metadata(self, query: Mapping[str, str | None]) -> ProviderMetadata:
        arxiv_id = (
            normalize_arxiv_id(query.get("arxiv_id"))
            or arxiv_id_from_doi(query.get("doi"))
            or arxiv_id_from_query(query.get("landing_page_url"))
            or arxiv_id_from_query(query.get("url"))
        )
        if not arxiv_id:
            raise ProviderFailure(
                NOT_SUPPORTED,
                "arXiv metadata retrieval requires an arXiv ID or arXiv DOI.",
            )
        try:
            search = _ArxivSearch(id_list=[arxiv_id], max_results=1)
            results = list(self.api_client.results(search))
        except ProviderFailure:
            raise
        except Exception as exc:
            error_category = classify_network_error(exc)
            raise ProviderFailure(
                ERROR,
                f"arXiv API metadata retrieval failed: {exc}",
                diagnostics=FailureDiagnostics(
                    provider=self.name,
                    route="metadata_api",
                    stage="fetch_or_decode",
                    error_category=error_category.value,
                    retryable=error_category.value
                    in {
                        "timeout",
                        "connection_reset",
                        "connection_closed",
                        "dns_error",
                    },
                    details={"exception_type": exc.__class__.__name__},
                ),
            ) from exc
        if not results:
            raise ProviderFailure(
                NO_RESULT, f"arXiv API returned no result for {arxiv_id}."
            )
        return _metadata_from_arxiv_result(results[0], requested_arxiv_id=arxiv_id)

    def _ensure_derived_metadata(
        self, doi: str, metadata: Mapping[str, Any]
    ) -> ProviderMetadata:
        arxiv_id = _arxiv_id_from_metadata_or_doi(doi, metadata)
        if not arxiv_id:
            raise ProviderFailure(
                NOT_SUPPORTED,
                "arXiv full-text retrieval requires an arXiv ID or arXiv DOI.",
            )
        return _minimal_arxiv_metadata(arxiv_id, doi=doi, metadata=metadata)

    def _fetch_api_metadata_optional(
        self, arxiv_id: str
    ) -> tuple[ProviderMetadata | None, list[str]]:
        try:
            return self.fetch_metadata({"arxiv_id": arxiv_id}), []
        except ProviderFailure as exc:
            warning = (
                "arXiv API metadata retrieval failed; using official HTML front matter and derived "
                f"arXiv URLs from identifier {arxiv_id} ({exc.message})."
            )
            return None, [warning]

    def _payload_with_api_metadata(
        self,
        payload: RawFulltextPayload,
        *,
        derived_metadata: Mapping[str, Any],
        api_metadata: Mapping[str, Any] | None,
        metadata_warnings: Sequence[str],
    ) -> RawFulltextPayload:
        warnings = [*list(payload.warnings), *list(metadata_warnings)]
        if not api_metadata:
            payload.warnings = warnings
            return payload
        content = payload.content
        content_metadata = (
            content.merged_metadata if content is not None else payload.merged_metadata
        )
        references = (
            list(content_metadata.get("references") or [])
            if isinstance(content_metadata, Mapping)
            else []
        )
        merged_metadata = _merge_arxiv_metadata_layers(
            derived_metadata,
            html_metadata=content_metadata
            if isinstance(content_metadata, Mapping)
            else None,
            api_metadata=api_metadata,
            references=references,
        )
        payload.merged_metadata = merged_metadata
        payload.warnings = warnings
        if content is not None:
            payload.content = replace(content, merged_metadata=merged_metadata)
        return payload

    def _fetch_html_payload(
        self, api_metadata: Mapping[str, Any]
    ) -> RawFulltextPayload:
        arxiv_id = normalize_arxiv_id(str(api_metadata.get("arxiv_id") or ""))
        html_url = normalize_text(
            str(api_metadata.get("html_url") or "")
        ) or canonical_arxiv_html_url(arxiv_id)
        if not html_url:
            raise ProviderFailure(
                NO_RESULT, "arXiv metadata did not expose an HTML candidate."
            )
        try:
            response = self.transport.request(
                "GET",
                html_url,
                headers=self._html_headers(),
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                retry_on_transient=True,
            )
        except RequestFailure as exc:
            raise map_request_failure(exc) from exc

        body = bytes(response.get("body") or b"")
        final_url = urllib.parse.urljoin(
            html_url, normalize_text(str(response.get("url") or "")) or html_url
        )
        content_type = _first_header_value(
            response.get("headers"), "content-type", "text/html"
        )
        if not _looks_like_html(content_type, body):
            raise ProviderFailure(
                NO_RESULT, "arXiv official HTML candidate did not return HTML."
            )
        html_text = body.decode("utf-8", errors="replace")
        extraction = _extract_arxiv_html_markdown(
            html_text, final_url, metadata=api_metadata
        )
        return build_provider_payload(
            provider=self.name,
            route_kind="html",
            route_name="official_html",
            source_url=final_url,
            content_type=content_type,
            body=body,
            markdown_text=extraction.markdown_text,
            merged_metadata=extraction.merged_metadata,
            diagnostics={
                "availability_diagnostics": extraction.diagnostics,
                "extraction": extraction.diagnostics.get("extraction"),
                "semantic_losses": extraction.diagnostics.get("semantic_losses"),
            },
            reason="Downloaded full text from arXiv official HTML.",
            extracted_assets=extraction.extracted_assets,
            warnings=extraction.warnings,
            trace_markers=[fulltext_marker(self.name, "ok", route="html")],
        )

    def _fetch_pdf_payload(
        self,
        api_metadata: Mapping[str, Any],
        *,
        previous_failure_message: str,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        arxiv_id = normalize_arxiv_id(str(api_metadata.get("arxiv_id") or ""))
        candidates = _dedupe_strings(
            [
                str(api_metadata.get("pdf_url") or ""),
                canonical_arxiv_pdf_url(arxiv_id),
            ]
        )
        if not candidates:
            raise ProviderFailure(
                NO_RESULT, "arXiv metadata did not expose a PDF candidate."
            )
        referer = normalize_text(
            str(
                api_metadata.get("html_url")
                or api_metadata.get("landing_page_url")
                or ""
            )
        )
        effective_asset_profile = pdf_asset_profile_from_context(context)
        try:
            pdf_result = PdfFallbackStrategy(
                transport=self.transport,
                provider_name="arxiv",
                headers=self._pdf_headers(referer=referer),
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                asset_profile=effective_asset_profile,
                asset_output_dir=pdf_asset_output_dir(
                    context,
                    asset_profile=effective_asset_profile,
                    doi=str(api_metadata.get("doi") or ""),
                ),
                expected_identity={
                    "doi": api_metadata.get("doi"),
                    "arxiv_id": api_metadata.get("arxiv_id"),
                    "title": api_metadata.get("title"),
                },
                context=context,
                fetcher=fetch_pdf_over_http,
            ).fetch(candidates)
        except PdfFetchFailure as exc:
            raise ProviderFailure(NO_RESULT, exc.message) from exc
        final_url = urllib.parse.urljoin(
            pdf_result.source_url or candidates[0], pdf_result.final_url
        )
        return build_provider_payload(
            provider=self.name,
            route_kind=PDF_FALLBACK,
            route_name="direct_pdf",
            source_url=final_url,
            content_type=PDF_MIME_TYPE,
            body=pdf_result.pdf_bytes,
            markdown_text=pdf_result.markdown_text,
            merged_metadata=api_metadata,
            diagnostics={
                PDF_FALLBACK: {
                    "candidates": candidates,
                    "previous_failure_message": previous_failure_message,
                }
            },
            reason="Downloaded full text from arXiv PDF fallback after arXiv official HTML was not usable.",
            suggested_filename=pdf_result.suggested_filename,
            extracted_assets=pdf_fetch_result_assets(pdf_result),
            html_failure_message=previous_failure_message,
            warnings=[
                *pdf_fetch_result_warnings(pdf_result),
                "Full text was extracted from arXiv PDF fallback after arXiv official HTML was not usable.",
            ],
            content_needs_local_copy=True,
            needs_local_copy=True,
        )

    def fetch_raw_fulltext(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        context = self._runtime_context(context)
        derived_metadata = self._ensure_derived_metadata(doi, metadata)
        arxiv_id = normalize_arxiv_id(str(derived_metadata.get("arxiv_id") or ""))

        def run_html(_state: ProviderWaterfallState) -> RawFulltextPayload:
            return self._fetch_html_payload(derived_metadata)

        def run_pdf(state: ProviderWaterfallState) -> RawFulltextPayload:
            failure_messages = [
                f"{label}: {failure.message}"
                for label in ("html",)
                if (failure := state.failure(label)) is not None
            ]
            previous_failure_message = (
                "; ".join(failure_messages) or "arXiv official HTML route failed."
            )
            return self._fetch_pdf_payload(
                derived_metadata,
                previous_failure_message=previous_failure_message,
                context=context,
            )

        payload = run_provider_waterfall(
            [
                ProviderWaterfallStep(
                    label="html",
                    route_name="official_html",
                    run=run_html,
                    failure_marker=fulltext_marker(self.name, "fail", route="html"),
                    success_markers=(fulltext_marker(self.name, "ok", route="html"),),
                    continue_codes=DEFAULT_WATERFALL_CONTINUE_CODES,
                    failure_warning=lambda failure, _state: (
                        "arXiv official HTML route was not usable "
                        f"({failure.message}); attempting PDF fallback."
                    ),
                ),
                ProviderWaterfallStep(
                    label="pdf",
                    route_name="direct_pdf",
                    run=run_pdf,
                    failure_marker=fulltext_marker(self.name, "fail", route="pdf"),
                    success_markers=(
                        fulltext_marker(self.name, "ok", route=PDF_FALLBACK),
                    ),
                    continue_codes=DEFAULT_WATERFALL_CONTINUE_CODES,
                    failure_warning=lambda failure, _state: (
                        f"arXiv PDF fallback was not usable ({failure.message})."
                    ),
                ),
            ],
            doi=doi,
            metadata=derived_metadata,
            context=context,
            client=self,
            initial_warnings=[],
        )
        if not self.api_enrichment_enabled:
            return payload
        api_metadata, metadata_warnings = self._fetch_api_metadata_optional(arxiv_id)
        return self._payload_with_api_metadata(
            payload,
            derived_metadata=derived_metadata,
            api_metadata=api_metadata,
            metadata_warnings=metadata_warnings,
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
        route_kind = normalize_text(
            content.route_kind if content is not None else ""
        ).lower()
        if route_kind != "html":
            return empty_asset_results()
        merged_metadata = (
            content.merged_metadata
            if content is not None
            else raw_payload.merged_metadata
        )
        arxiv_id = normalize_arxiv_id(
            str((merged_metadata or {}).get("arxiv_id") or "")
        ) or _arxiv_id_from_metadata_or_doi(doi, merged_metadata or {})
        article_id = arxiv_id or normalize_text(doi) or raw_payload.source_url
        article_html = bytes(
            content.body if content is not None else raw_payload.body or b""
        ).decode("utf-8", errors="replace")
        return download_arxiv_html_figure_assets(
            self.transport,
            ArxivHtmlAssetDownloadPlan(
                arxiv_id=arxiv_id,
                article_id=article_id,
                article_html=article_html,
                source_url=normalize_text(
                    content.source_url
                    if content is not None
                    else raw_payload.source_url
                ),
                extracted_assets=(
                    content.extracted_assets if content is not None else []
                ),
                output_dir=output_dir,
                user_agent=self.user_agent,
                asset_profile=asset_profile,
                runtime_context=context,
                image_headers=self._image_headers(),
            ),
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
        del context
        content = raw_payload.content
        merged_metadata = (
            content.merged_metadata
            if content is not None
            else raw_payload.merged_metadata
        )
        article_metadata = dict(
            merged_metadata if isinstance(merged_metadata, Mapping) else metadata
        )
        arxiv_id = normalize_arxiv_id(str(article_metadata.get("arxiv_id") or ""))
        doi = canonical_arxiv_doi(arxiv_id) or str(
            article_metadata.get("doi") or metadata.get("doi") or ""
        )
        route = normalize_text(
            content.route_kind if content is not None else ""
        ).lower()
        source: SourceKind = "arxiv_pdf" if route == PDF_FALLBACK else "arxiv_html"
        markdown_text = str(
            (content.markdown_text if content is not None else "") or ""
        ).strip()
        markdown_text = inline_arxiv_source_assets_in_markdown(
            markdown_text, downloaded_assets
        )
        default_route = PDF_FALLBACK if route == PDF_FALLBACK else "html"
        trace = list(
            raw_payload.trace
            or trace_from_markers(
                [fulltext_marker(self.name, "ok", route=default_route)]
            )
        )
        warnings = list(raw_payload.warnings)
        if asset_failures:
            warnings.append(
                f"arXiv related assets were only partially downloaded ({len(asset_failures)} failed)."
            )
        if not markdown_text:
            warnings.append("arXiv retrieval did not produce usable Markdown.")
            return metadata_only_article(
                source=source,
                metadata=article_metadata,
                doi=doi or None,
                warnings=warnings,
                trace=trace,
            )
        availability_diagnostics = (
            dict(content.diagnostics.get("availability_diagnostics") or {})
            if content is not None
            and isinstance(content.diagnostics.get("availability_diagnostics"), Mapping)
            else None
        )
        semantic_losses = (
            dict(content.diagnostics.get("semantic_losses") or {})
            if content is not None
            and isinstance(content.diagnostics.get("semantic_losses"), Mapping)
            else (
                dict(availability_diagnostics.get("semantic_losses") or {})
                if isinstance(availability_diagnostics, Mapping)
                and isinstance(availability_diagnostics.get("semantic_losses"), Mapping)
                else None
            )
        )
        extraction_payload = (
            content.diagnostics.get("extraction")
            if content is not None
            and isinstance(content.diagnostics.get("extraction"), Mapping)
            else {}
        )
        section_hints = (
            list(extraction_payload.get("section_hints") or [])
            if isinstance(extraction_payload, Mapping)
            else []
        )
        article = article_from_markdown(
            source=source,
            metadata=article_metadata,
            doi=doi or None,
            markdown_text=markdown_text,
            section_hints=section_hints,
            assets=[
                dict(item)
                for item in (
                    list(content.extracted_assets if content is not None else [])
                    if route == PDF_FALLBACK
                    else list(downloaded_assets or [])
                )
            ],
            warnings=warnings,
            trace=trace,
            availability_diagnostics=availability_diagnostics,
            semantic_losses=semantic_losses,
            allow_downgrade_from_diagnostics=True,
        )
        if asset_failures:
            article.quality.asset_failures = [dict(item) for item in asset_failures]
        return article

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
        if (
            normalize_text(content.route_kind if content is not None else "").lower()
            != PDF_FALLBACK
        ):
            return artifacts
        pdf_assets = list(content.extracted_assets if content is not None else [])
        return ProviderArtifacts(
            assets=[*list(artifacts.assets), *pdf_assets],
            asset_failures=list(artifacts.asset_failures),
            allow_related_assets=False,
            text_only=not pdf_assets,
            skip_trace=trace_from_markers(
                [download_marker("arxiv_assets_skipped_text_only")]
            )
            if not pdf_assets
            else [],
        )


__all__ = [
    "ArxivClient",
]
