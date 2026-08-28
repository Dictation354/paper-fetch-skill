"""Copernicus Publications XML-first provider client."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from collections.abc import Mapping
import re
import urllib.parse
import xml.etree.ElementTree as ET

from ..config import build_publisher_user_agent, resolve_asset_download_concurrency
from ..extraction.html._metadata import merge_html_metadata
from ..extraction.html.assets import (
    FIGURE_KIND,
    SUPPLEMENTARY_KIND,
    download_assets,
    filter_assets_for_profile,
    merge_extracted_and_downloaded_assets,
    split_body_and_supplementary_assets,
)
from ..extraction.html.landing import (
    LandingHtmlFetchResult,
    LandingRedirectLimitExceeded,
    fetch_landing_html,
)
from ..http import (
    DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
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
from ..provider_catalog import (
    BodyTextThresholds,
    ProviderRouteSpec,
    ProviderSpec,
    provider_domains,
    provider_landing_path_templates,
    provider_pdf_path_templates,
    provider_xml_path_templates,
)
from ..publisher_identity import normalize_doi
from ..runtime import RuntimeContext
from ..tracing import download_marker, fulltext_marker, trace_from_markers
from ..utils import (
    choose_public_landing_page_url,
    empty_asset_results,
    extend_unique,
    normalize_text,
)
from ..xml_security import XmlParseFailure, parse_xml
from ._article_markdown_common import (
    first_child,
    first_descendant,
    iter_descendants,
    xml_local_name,
)
from ._article_markdown_copernicus import CopernicusExtraction, parse_copernicus_xml
from ._payloads import build_provider_payload
from ._pdf_common import (
    default_pdf_headers,
    pdf_asset_output_dir,
    pdf_asset_profile_from_context,
    pdf_fetch_result_assets,
    pdf_fetch_result_warnings,
)
from ._pdf_fallback import PdfFallbackStrategy, PdfFetchFailure, fetch_pdf_over_http
from ._registry import ProviderBundle, register_provider_bundle
from ._waterfall import (
    DEFAULT_WATERFALL_CONTINUE_CODES,
    ProviderWaterfallState,
    ProviderWaterfallStep,
    run_provider_waterfall,
)
from ..reason_codes import ERROR, NO_RESULT, NOT_SUPPORTED, OK, PDF_FALLBACK
from .base import (
    ProviderArtifacts,
    ProviderClient,
    ProviderContent,
    ProviderFailure,
    ProviderStatusResult,
    RawFulltextPayload,
    build_provider_status_check,
    combine_provider_failures,
    map_request_failure,
    summarize_capability_status,
)

from bs4 import BeautifulSoup, Tag


register_provider_bundle(
    ProviderBundle(
        catalog=ProviderSpec(
            name="copernicus",
            display_name="Copernicus",
            official=True,
            domains=(),
            doi_prefixes=("10.5194/",),
            publisher_aliases=(
                "copernicus",
                "copernicus publications",
                "copernicus gmbh",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=False,
            client_factory_path="paper_fetch.providers.copernicus:CopernicusClient",
            status_order=8,
            domain_suffixes=("copernicus.org",),
            xml_path_templates=("/articles/{volume}/{page}/{year}/{suffix}.xml",),
            landing_path_templates=("/articles/{volume}/{page}/{year}/",),
            pdf_path_templates=("/articles/{volume}/{page}/{year}/{suffix}.pdf",),
            emits_html_managed_marker=False,
            html_capable=False,
            xml_root_tags=("article",),
            xml_file_tokens=("copernicus", "10.5194"),
            body_text_thresholds=BodyTextThresholds(min_chars=500),
            routes=(
                ProviderRouteSpec(name="metadata", kind="metadata"),
                ProviderRouteSpec(name="xml", kind="xml"),
                ProviderRouteSpec(
                    name="direct_pdf",
                    kind="pdf",
                    requires_pdf_conversion=True,
                ),
                ProviderRouteSpec(
                    name="assets",
                    kind="assets",
                    timeout_seconds=20,
                    concurrency=2,
                    transient_retries=2,
                ),
            ),
        ),
        sources=("copernicus_xml", "copernicus_pdf"),
    )
)

MIN_BODY_CHARS = 500
COPERNICUS_XML_DOI_PATTERN = re.compile(
    r"^10\.5194/(?P<journal>[a-z0-9]+)-(?P<volume>\d+)-(?P<page>.+)-(?P<year>\d{4})$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class CopernicusLandingAttempt:
    normalized_doi: str
    landing_url: str
    response_url: str
    html_text: str
    response: Mapping[str, Any]
    merged_metadata: dict[str, Any]
    xml_candidates: list[str]
    pdf_candidates: list[str]
    warnings: list[str] | None = None
    source_trail: list[str] | None = None


def _candidate_urls(doi: str, *, templates: tuple[str, ...]) -> list[str]:
    match = COPERNICUS_XML_DOI_PATTERN.match(normalize_doi(doi))
    if not match:
        return []
    normalized_doi = normalize_doi(doi)
    journal = match.group("journal").lower()
    fields = {
        "doi": normalized_doi,
        "journal": journal,
        "volume": match.group("volume"),
        "page": match.group("page"),
        "year": match.group("year"),
        "suffix": normalized_doi.split("/", 1)[1],
    }
    urls: list[str] = []
    for host in provider_domains("copernicus"):
        candidate_host = (
            f"{journal}.{host}" if host == "copernicus.org" else host.format(**fields)
        )
        for template in templates:
            url = f"https://{candidate_host}{template.format(**fields)}"
            if url not in urls:
                urls.append(url)
    return urls


def _first_candidate_url(doi: str, *, templates: tuple[str, ...]) -> str:
    candidates = _candidate_urls(doi, templates=templates)
    return candidates[0] if candidates else ""


def _raw_meta_urls(metadata: Mapping[str, Any], key: str, base_url: str) -> list[str]:
    raw_meta = metadata.get("raw_meta")
    if not isinstance(raw_meta, Mapping):
        return []
    values = raw_meta.get(key) or raw_meta.get(key.lower()) or []
    if isinstance(values, str):
        values = [values]
    return [
        urllib.parse.urljoin(base_url, normalized)
        for normalized in [normalize_text(str(item or "")) for item in values]
        if normalized
    ]


def _discover_link_urls(html_text: str, base_url: str, *, suffix: str) -> list[str]:
    soup = BeautifulSoup(html_text, "html.parser")
    urls: list[str] = []
    for node in soup.select("a[href], link[href], meta[content]"):
        if not isinstance(node, Tag):
            continue
        value = normalize_text(str(node.get("href") or node.get("content") or ""))
        if not value:
            continue
        path = urllib.parse.urlparse(value).path.lower()
        if path.endswith(suffix):
            urls.append(urllib.parse.urljoin(base_url, value))
    deduped: list[str] = []
    extend_unique(deduped, urls)
    return deduped


class CopernicusClient(ProviderClient):
    name = "copernicus"
    landing_max_redirects = 4

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
                    "xml_route",
                    OK,
                    "Copernicus direct NLM/JATS XML route is available without provider credentials.",
                    details={"mode": "direct_xml"},
                ),
                build_provider_status_check(
                    PDF_FALLBACK,
                    OK,
                    "Copernicus PDF fallback is available when XML is not usable; body/all asset requests can save exported PDF images when artifacts are enabled.",
                    details={"mode": "direct_http_pdf"},
                ),
            ],
        )

    def _html_headers(self) -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": self.user_agent,
        }

    def _xml_headers(self, *, referer: str | None = None) -> dict[str, str]:
        headers = {
            "Accept": "application/xml,text/xml,*/*;q=0.5",
            "User-Agent": self.user_agent,
        }
        if referer:
            headers["Referer"] = referer
        return headers

    def _pdf_headers(self, *, referer: str | None = None) -> dict[str, str]:
        return default_pdf_headers(self.user_agent, referer=referer)

    def _resolve_landing_url(self, doi: str, metadata: Mapping[str, Any]) -> str:
        normalized_doi = normalize_doi(doi)
        doi_url = f"https://doi.org/{urllib.parse.quote(normalized_doi, safe='/')}"
        return (
            choose_public_landing_page_url(
                metadata.get("landing_page_url"),
                _first_candidate_url(
                    normalized_doi,
                    templates=provider_landing_path_templates("copernicus"),
                ),
                doi_url,
            )
            or doi_url
        )

    def _fetch_landing(self, landing_url: str) -> LandingHtmlFetchResult:
        try:
            return fetch_landing_html(
                landing_url,
                transport=self.transport,
                headers=self._html_headers(),
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                max_redirects=self.landing_max_redirects,
                raise_on_redirect_limit=True,
                retry_on_transient=True,
            )
        except LandingRedirectLimitExceeded as exc:
            raise ProviderFailure(
                ERROR,
                f"Copernicus landing retrieval exceeded {self.landing_max_redirects} redirects.",
            ) from exc
        except RequestFailure as exc:
            raise map_request_failure(exc) from exc

    def _doi_derived_landing_attempt(
        self,
        normalized_doi: str,
        metadata: Mapping[str, Any],
        *,
        landing_url: str,
        landing_failure: ProviderFailure,
    ) -> CopernicusLandingAttempt:
        response_url = (
            _first_candidate_url(
                normalized_doi,
                templates=provider_landing_path_templates("copernicus"),
            )
            or landing_url
        )
        merged_metadata = dict(metadata)
        if not merged_metadata.get("doi"):
            merged_metadata["doi"] = normalized_doi
        if not merged_metadata.get("landing_page_url"):
            merged_metadata["landing_page_url"] = response_url
        warning = (
            f"Copernicus landing page was not usable ({landing_failure.message}); "
            "continuing with DOI-derived XML/PDF candidates."
        )
        return CopernicusLandingAttempt(
            normalized_doi=normalized_doi,
            landing_url=landing_url,
            response_url=response_url,
            html_text="",
            response={},
            merged_metadata=merged_metadata,
            xml_candidates=_candidate_urls(
                normalized_doi,
                templates=provider_xml_path_templates("copernicus"),
            ),
            pdf_candidates=_candidate_urls(
                normalized_doi,
                templates=provider_pdf_path_templates("copernicus"),
            ),
            warnings=[warning, *landing_failure.warnings],
            source_trail=[
                fulltext_marker(self.name, "fail", route="landing"),
                *landing_failure.source_trail,
            ],
        )

    def _prepare_landing_attempt(
        self, doi: str, metadata: Mapping[str, Any]
    ) -> CopernicusLandingAttempt:
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            raise ProviderFailure(
                NOT_SUPPORTED, "Copernicus full-text retrieval requires a DOI."
            )
        landing_url = self._resolve_landing_url(normalized_doi, metadata)
        try:
            landing = self._fetch_landing(landing_url)
        except ProviderFailure as exc:
            return self._doi_derived_landing_attempt(
                normalized_doi,
                metadata,
                landing_url=landing_url,
                landing_failure=exc,
            )
        merged_metadata = merge_html_metadata(dict(metadata), landing.metadata)
        if not merged_metadata.get("doi"):
            merged_metadata["doi"] = normalized_doi
        if not merged_metadata.get("landing_page_url"):
            merged_metadata["landing_page_url"] = landing.final_url
        xml_candidates: list[str] = []
        extend_unique(
            xml_candidates,
            _raw_meta_urls(merged_metadata, "citation_xml_url", landing.final_url),
        )
        extend_unique(
            xml_candidates,
            _discover_link_urls(landing.html_text, landing.final_url, suffix=".xml"),
        )
        extend_unique(
            xml_candidates,
            _candidate_urls(
                normalized_doi,
                templates=provider_xml_path_templates("copernicus"),
            ),
        )
        pdf_candidates: list[str] = []
        extend_unique(
            pdf_candidates,
            _raw_meta_urls(merged_metadata, "citation_pdf_url", landing.final_url),
        )
        extend_unique(
            pdf_candidates,
            _discover_link_urls(landing.html_text, landing.final_url, suffix=".pdf"),
        )
        extend_unique(
            pdf_candidates,
            _candidate_urls(
                normalized_doi,
                templates=provider_pdf_path_templates("copernicus"),
            ),
        )
        return CopernicusLandingAttempt(
            normalized_doi=normalized_doi,
            landing_url=landing_url,
            response_url=landing.final_url,
            html_text=landing.html_text,
            response=landing.response,
            merged_metadata=dict(merged_metadata),
            xml_candidates=xml_candidates,
            pdf_candidates=pdf_candidates,
            warnings=[],
            source_trail=[],
        )

    def _fetch_xml_response(self, url: str, *, referer: str) -> tuple[bytes, str, str]:
        try:
            response = self.transport.request(
                "GET",
                url,
                headers=self._xml_headers(referer=referer),
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                retry_on_transient=True,
            )
        except RequestFailure as exc:
            raise map_request_failure(exc) from exc
        body = bytes(response.get("body") or b"")
        response_url = urllib.parse.urljoin(
            url, normalize_text(str(response.get("url") or "")) or url
        )
        content_type = header_value(
            response.get("headers"), "content-type", "application/xml"
        )
        return body, response_url, content_type

    def _validate_xml_extraction(
        self,
        extraction: CopernicusExtraction | None,
        xml_root: ET.Element,
    ) -> CopernicusExtraction:
        root = xml_root
        if xml_local_name(root.tag) != "article":
            raise ProviderFailure(
                NO_RESULT, "Copernicus XML payload root is not a JATS article."
            )
        if extraction is None:
            raise ProviderFailure(
                NO_RESULT,
                "Copernicus XML payload is not parseable NLM/JATS article XML.",
            )
        article_meta = first_descendant(first_child(root, "front"), "article-meta")
        body = first_child(root, "body")
        body_sections = list(iter_descendants(body, "sec"))
        body_section_paragraph_chars = 0
        body_sections_with_paragraphs = 0
        for section in body_sections:
            section_chars = sum(
                len(normalize_text(" ".join(paragraph.itertext())))
                for paragraph in iter_descendants(section, "p")
            )
            if section_chars > 0:
                body_sections_with_paragraphs += 1
                body_section_paragraph_chars += section_chars
        abstract_text = normalize_text(str(extraction.metadata.get("abstract") or ""))
        if article_meta is None or body is None or not body_sections:
            raise ProviderFailure(
                NO_RESULT,
                "Copernicus XML payload is missing article metadata or body sections.",
            )
        if not abstract_text:
            raise ProviderFailure(
                NO_RESULT, "Copernicus XML payload did not expose a non-empty abstract."
            )
        if body_sections_with_paragraphs == 0:
            raise ProviderFailure(
                NO_RESULT, "Copernicus XML payload did not expose body paragraphs."
            )
        if body_section_paragraph_chars < MIN_BODY_CHARS:
            raise ProviderFailure(
                NO_RESULT, "Copernicus XML payload did not expose enough body text."
            )
        return extraction

    def _fetch_xml_payload(
        self, attempt: CopernicusLandingAttempt
    ) -> RawFulltextPayload:
        if not attempt.xml_candidates:
            raise ProviderFailure(
                NO_RESULT,
                "Copernicus landing page did not expose an XML candidate.",
                warnings=list(attempt.warnings or []),
                source_trail=list(attempt.source_trail or []),
            )
        failures: list[tuple[str, ProviderFailure]] = []
        for candidate in attempt.xml_candidates:
            try:
                body, response_url, content_type = self._fetch_xml_response(
                    candidate, referer=attempt.response_url
                )
                try:
                    xml_root = parse_xml(
                        body,
                        source="Copernicus XML payload",
                        allow_external_doctype=True,
                    )
                except XmlParseFailure as exc:
                    raise ProviderFailure(
                        exc.code, "Copernicus XML payload could not be parsed."
                    ) from exc
                extraction = self._validate_xml_extraction(
                    parse_copernicus_xml(
                        body,
                        source_url=response_url,
                        base_metadata=attempt.merged_metadata,
                        xml_root=xml_root,
                    ),
                    xml_root,
                )
                markdown_text = extraction.markdown_text
                return build_provider_payload(
                    provider=self.name,
                    route_kind="xml",
                    route_name="xml",
                    source_url=response_url,
                    content_type=content_type,
                    body=body,
                    markdown_text=markdown_text,
                    merged_metadata=extraction.metadata,
                    diagnostics={
                        "extraction": {
                            "abstract_sections": extraction.abstract_sections,
                            "references": extraction.references,
                            "references_count": len(extraction.references),
                            "assets_count": len(extraction.assets),
                            "semantic_losses": asdict(extraction.semantic_losses),
                        }
                    },
                    reason="Downloaded full text from Copernicus NLM/JATS XML.",
                    extracted_assets=extraction.assets,
                    warnings=list(attempt.warnings or []),
                )
            except ProviderFailure as exc:
                failures.append((candidate, exc))
                continue
        if failures:
            combined = combine_provider_failures(
                [(label, failure) for label, failure in failures]
            )
            raise ProviderFailure(
                combined.code,
                "Copernicus XML route was not usable. " + combined.message,
                warnings=[*list(attempt.warnings or []), *combined.warnings],
                source_trail=[
                    *list(attempt.source_trail or []),
                    *combined.source_trail,
                ],
            )
        raise ProviderFailure(NO_RESULT, "Copernicus XML route did not run.")

    def _fetch_pdf_payload(
        self,
        attempt: CopernicusLandingAttempt,
        *,
        xml_failure_message: str,
        warnings: list[str],
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        if not attempt.pdf_candidates:
            raise ProviderFailure(
                NO_RESULT, "Copernicus landing page did not expose a PDF candidate."
            )
        effective_asset_profile = pdf_asset_profile_from_context(context)
        try:
            pdf_result = PdfFallbackStrategy(
                transport=self.transport,
                provider_name="copernicus",
                headers=self._pdf_headers(referer=attempt.response_url),
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                asset_profile=effective_asset_profile,
                asset_output_dir=pdf_asset_output_dir(
                    context,
                    asset_profile=effective_asset_profile,
                    doi=attempt.normalized_doi,
                ),
                expected_identity={
                    "doi": attempt.normalized_doi,
                    "title": attempt.merged_metadata.get("title"),
                },
                context=context,
                fetcher=fetch_pdf_over_http,
            ).fetch(attempt.pdf_candidates)
        except PdfFetchFailure as exc:
            raise ProviderFailure(NO_RESULT, exc.message) from exc
        final_url = urllib.parse.urljoin(
            pdf_result.source_url or attempt.response_url, pdf_result.final_url
        )
        return build_provider_payload(
            provider=self.name,
            route_kind=PDF_FALLBACK,
            route_name="direct_pdf",
            source_url=final_url,
            content_type=PDF_MIME_TYPE,
            body=pdf_result.pdf_bytes,
            markdown_text=pdf_result.markdown_text,
            merged_metadata=attempt.merged_metadata,
            diagnostics={PDF_FALLBACK: {"candidates": list(attempt.pdf_candidates)}},
            reason="Downloaded full text from Copernicus PDF fallback after XML was not usable.",
            suggested_filename=pdf_result.suggested_filename,
            extracted_assets=pdf_fetch_result_assets(pdf_result),
            html_failure_message=xml_failure_message,
            warnings=[
                *warnings,
                *pdf_fetch_result_warnings(pdf_result),
                "Full text was extracted from Copernicus PDF fallback after the XML route was not usable.",
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
        landing_context: dict[str, Any] = {"attempt": None}

        def landing_attempt() -> CopernicusLandingAttempt:
            attempt = landing_context.get("attempt")
            if isinstance(attempt, CopernicusLandingAttempt):
                return attempt
            attempt = self._prepare_landing_attempt(doi, metadata)
            landing_context["attempt"] = attempt
            return attempt

        def run_xml(_state: ProviderWaterfallState) -> RawFulltextPayload:
            attempt = landing_attempt()
            for marker in attempt.source_trail or []:
                if marker not in _state.initial_source_trail:
                    _state.initial_source_trail.append(marker)
            return self._fetch_xml_payload(attempt)

        def run_pdf(state: ProviderWaterfallState) -> RawFulltextPayload:
            attempt = landing_attempt()
            for marker in attempt.source_trail or []:
                if marker not in state.initial_source_trail:
                    state.initial_source_trail.append(marker)
            xml_failure = state.failure("xml")
            xml_failure_message = (
                xml_failure.message
                if xml_failure is not None
                else "Copernicus XML route failed."
            )
            return self._fetch_pdf_payload(
                attempt,
                xml_failure_message=xml_failure_message,
                warnings=[],
                context=context,
            )

        return run_provider_waterfall(
            [
                ProviderWaterfallStep(
                    label="xml",
                    route_name="xml",
                    run=run_xml,
                    failure_marker=fulltext_marker(self.name, "fail", route="xml"),
                    success_markers=(fulltext_marker(self.name, "ok", route="xml"),),
                    continue_codes=DEFAULT_WATERFALL_CONTINUE_CODES,
                    failure_warning=lambda failure, _state: (
                        f"Copernicus XML route was not usable ({failure.message}); attempting PDF fallback."
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
                        f"Copernicus PDF fallback was not usable ({failure.message})."
                    ),
                ),
            ],
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
        context = self._runtime_context(context, output_dir=output_dir)
        if output_dir is None or asset_profile == "none":
            return empty_asset_results()
        content = raw_payload.content
        route = normalize_text(
            content.route_kind if content is not None else ""
        ).lower()
        if route == PDF_FALLBACK:
            return empty_asset_results()
        extracted_assets = filter_assets_for_profile(
            list(content.extracted_assets if content is not None else []),
            asset_profile=asset_profile,
        )
        if not extracted_assets:
            return empty_asset_results()
        body_assets, supplementary_assets = split_body_and_supplementary_assets(
            extracted_assets
        )
        downloadable_body_assets = [
            dict(item)
            for item in body_assets
            if normalize_text(
                str(
                    item.get("url")
                    or item.get("full_size_url")
                    or item.get("download_url")
                    or item.get("original_url")
                    or item.get("link")
                    or ""
                )
            )
        ]
        merged_metadata = (
            content.merged_metadata
            if content is not None
            else raw_payload.merged_metadata
        )
        article_id = (
            normalize_doi(str((merged_metadata or {}).get("doi") or doi or ""))
            or normalize_doi(doi)
            or normalize_text(str(metadata.get("title") or ""))
            or raw_payload.source_url
        )
        seed_urls: list[str] = []
        body_result = (
            download_assets(
                FIGURE_KIND,
                self.transport,
                article_id=article_id,
                assets=downloadable_body_assets,
                output_dir=output_dir,
                user_agent=self.user_agent,
                asset_profile=asset_profile,
                headers=self._html_headers(),
                seed_urls=seed_urls,
                asset_download_concurrency=resolve_asset_download_concurrency(
                    context.env
                ),
                provider_name="copernicus",
                runtime_context=context,
            )
            if downloadable_body_assets
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
                headers=self._html_headers(),
                seed_urls=seed_urls,
                asset_download_concurrency=resolve_asset_download_concurrency(
                    context.env
                ),
                provider_name="copernicus",
                runtime_context=context,
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
        doi = normalize_doi(
            str(article_metadata.get("doi") or metadata.get("doi") or "")
        )
        route = normalize_text(
            content.route_kind if content is not None else ""
        ).lower()
        trace = list(
            raw_payload.trace
            or trace_from_markers([fulltext_marker(self.name, "ok", route="xml")])
        )
        warnings = list(raw_payload.warnings)
        if asset_failures:
            warnings.append(
                f"Copernicus related assets were only partially downloaded ({len(asset_failures)} failed)."
            )

        source: SourceKind = "copernicus_xml"
        if route == PDF_FALLBACK:
            source = "copernicus_pdf"

        if route == "xml":
            markdown_text = str(
                (content.markdown_text if content is not None else "") or ""
            ).strip()
            if not markdown_text:
                warnings.append(
                    "Copernicus XML retrieval did not produce usable Markdown."
                )
                return metadata_only_article(
                    source="copernicus_xml",
                    metadata=article_metadata,
                    doi=doi or None,
                    warnings=warnings,
                    trace=trace,
                )
            extraction_diagnostics = (
                dict(content.diagnostics.get("extraction") or {})
                if content is not None
                and isinstance(content.diagnostics.get("extraction"), Mapping)
                else {}
            )
            references = extraction_diagnostics.get("references")
            if isinstance(references, list) and references:
                article_metadata["references"] = [
                    dict(item) if isinstance(item, Mapping) else item
                    for item in references
                ]
            abstract_sections = extraction_diagnostics.get("abstract_sections")
            semantic_losses = extraction_diagnostics.get("semantic_losses")
            assets = merge_extracted_and_downloaded_assets(
                list(content.extracted_assets if content is not None else []),
                list(downloaded_assets or []),
            )
            article = article_from_markdown(
                source="copernicus_xml",
                metadata=article_metadata,
                doi=normalize_doi(str(article_metadata.get("doi") or doi)) or None,
                markdown_text=markdown_text,
                abstract_sections=abstract_sections
                if isinstance(abstract_sections, list)
                else None,
                assets=assets,
                warnings=warnings,
                trace=trace,
                semantic_losses=semantic_losses
                if isinstance(semantic_losses, Mapping)
                else None,
            )
            if asset_failures:
                article.quality.asset_failures = [dict(item) for item in asset_failures]
            return article

        markdown_text = str(
            (content.markdown_text if content is not None else "") or ""
        ).strip()
        if not markdown_text:
            warnings.append("Copernicus retrieval did not produce usable Markdown.")
            return metadata_only_article(
                source=source,
                metadata=article_metadata,
                doi=doi or None,
                warnings=warnings,
                trace=trace,
            )
        extracted_assets = list(content.extracted_assets if content is not None else [])
        assets = merge_extracted_and_downloaded_assets(
            extracted_assets, list(downloaded_assets or [])
        )
        availability_diagnostics = (
            dict(content.diagnostics.get("availability_diagnostics") or {})
            if content is not None
            and isinstance(content.diagnostics.get("availability_diagnostics"), Mapping)
            else None
        )
        article = article_from_markdown(
            source=source,
            metadata=article_metadata,
            doi=doi or None,
            markdown_text=markdown_text,
            assets=assets,
            warnings=warnings,
            trace=trace,
            availability_diagnostics=availability_diagnostics,
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
                [download_marker("copernicus_assets_skipped_text_only")]
            )
            if not pdf_assets
            else [],
        )


__all__ = ["CopernicusClient", "ProviderContent", "RawFulltextPayload"]
