"""Frontiers public JATS XML provider client."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Any
from collections.abc import Mapping, Sequence
import re
import urllib.parse

from ..config import build_user_agent, resolve_asset_download_concurrency
from ..extraction.html.assets import (
    FIGURE_KIND,
    download_assets,
    html_asset_identity_key,
    split_body_and_supplementary_assets,
)
from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.landing import fetch_landing_html
from ..extraction.html.provider_rules import ProviderFrontMatterRules, ProviderHtmlRules
from ..http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, HttpTransport, PDF_MIME_TYPE, RequestFailure
from ..http.headers import header_value
from ..models import AssetProfile, SourceKind, article_from_markdown, metadata_only_article
from ..provider_catalog import BodyTextThresholds, ProviderSpec
from ..publisher_identity import normalize_doi
from ..reason_codes import NO_RESULT, OK, PDF_FALLBACK
from ..runtime import RuntimeContext
from ..tracing import download_marker, fulltext_marker, trace_from_markers
from ..utils import empty_asset_results, normalize_text
from ._article_markdown_jats import parse_jats_xml
from ._payloads import build_provider_payload
from ._pdf_common import (
    default_pdf_headers,
    pdf_asset_output_dir,
    pdf_asset_profile_from_context,
    pdf_fetch_result_assets,
)
from ._pdf_fallback import PdfFallbackStrategy, PdfFetchFailure, fetch_pdf_over_http
from ._registry import ProviderBundle, register_provider_bundle
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
            name="frontiers",
            display_name="Frontiers",
            official=True,
            domains=("www.frontiersin.org", "frontiersin.org"),
            doi_prefixes=("10.3389/",),
            publisher_aliases=(
                "frontiers",
                "frontiers media",
                "frontiers media s.a.",
                "frontiers media sa",
            ),
            asset_default="body",
            probe_capability="routing_signal",
            provider_managed_abstract_only=False,
            client_factory_path="paper_fetch.providers.frontiers:FrontiersClient",
            status_order=18,
            base_domains=("www.frontiersin.org",),
            landing_path_templates=("/articles/{doi}/full",),
            xml_path_templates=("/journals/{journal_slug}/articles/{doi}/xml",),
            pdf_path_templates=(
                "/journals/{journal_slug}/articles/{doi}/pdf",
                "/articles/{doi}/pdf",
            ),
            emits_html_managed_marker=False,
            html_capable=False,
            xml_root_tags=("article",),
            xml_file_tokens=("10.3389", "frontiers"),
            body_text_thresholds=BodyTextThresholds(min_chars=1200),
        ),
        html_rules=ProviderHtmlRules(
            name="frontiers",
            front_matter=ProviderFrontMatterRules(
                exact_texts=(),
                contains_tokens=(),
                publication_keywords=("frontiers", "frontiers media"),
            ),
            availability=AvailabilityPolicy(name="frontiers", no_signals=True),
        ),
        sources=("frontiers_xml", "frontiers_pdf"),
    )
)


FRONTIERS_HOST = "https://www.frontiersin.org"
FRONTIERS_CANONICAL_ARTICLE_PATTERN = re.compile(
    r"^/journals/(?P<journal_slug>[^/]+)/articles/(?P<doi>10\.3389/[^/?#]+)"
    r"(?:/(?P<kind>full|xml|pdf|epub))?/?$",
    flags=re.IGNORECASE,
)
FRONTIERS_LEGACY_ARTICLE_PATTERN = re.compile(
    r"^/articles/(?P<doi>10\.3389/[^/?#]+)(?:/(?P<kind>full|xml|pdf|epub))?/?$",
    flags=re.IGNORECASE,
)
FRONTIERS_ARTICLE_ID_PATTERN = re.compile(r"^10\.3389/[^.]+\.\d{4}\.(?P<article_id>[^/?#]+)$")
FRONTIERS_GRAPHIC_FILENAME_PATTERN = re.compile(
    r"(?P<article_id>\d+)-g\d+",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class FrontiersArticleRoutes:
    landing_url: str
    xml_url: str | None
    pdf_url: str


def _response_body(response: Mapping[str, Any]) -> bytes:
    body = response.get("body", b"")
    if isinstance(body, bytes):
        return body
    if isinstance(body, bytearray):
        return bytes(body)
    if isinstance(body, str):
        return body.encode("utf-8")
    return b""


def _looks_like_html(body: bytes, content_type: str) -> bool:
    lowered_type = normalize_text(content_type).lower()
    if "html" in lowered_type:
        return True
    prefix = body[:1024].lstrip().lower()
    return prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html") or b"<html" in prefix


def _is_frontiers_url(value: str | None) -> bool:
    parsed = urllib.parse.urlparse(normalize_text(value))
    host = normalize_text(parsed.hostname or "").lower()
    return host == "frontiersin.org" or host == "www.frontiersin.org"


def _append_unique(values: list[str], candidate: str | None) -> None:
    normalized = normalize_text(candidate)
    if normalized and normalized not in values:
        values.append(normalized)


def _frontiers_legacy_landing_url(doi: str) -> str:
    normalized = normalize_doi(doi)
    return f"{FRONTIERS_HOST}/articles/{normalized}/full"


def _frontiers_legacy_pdf_url(doi: str) -> str:
    normalized = normalize_doi(doi)
    return f"{FRONTIERS_HOST}/articles/{normalized}/pdf"


def _canonical_routes_from_url(value: str | None) -> FrontiersArticleRoutes | None:
    if not _is_frontiers_url(value):
        return None
    parsed = urllib.parse.urlparse(normalize_text(value))
    match = FRONTIERS_CANONICAL_ARTICLE_PATTERN.match(parsed.path)
    if not match:
        return None
    journal_slug = match.group("journal_slug")
    doi = normalize_doi(match.group("doi"))
    if not journal_slug or not doi:
        return None
    base = f"{FRONTIERS_HOST}/journals/{journal_slug}/articles/{doi}"
    return FrontiersArticleRoutes(
        landing_url=f"{base}/full",
        xml_url=f"{base}/xml",
        pdf_url=f"{base}/pdf",
    )


def _legacy_routes_from_doi(doi: str) -> FrontiersArticleRoutes:
    normalized = normalize_doi(doi)
    landing_url = _frontiers_legacy_landing_url(normalized)
    return FrontiersArticleRoutes(
        landing_url=landing_url,
        xml_url=None,
        pdf_url=_frontiers_legacy_pdf_url(normalized),
    )


def _raw_meta_values(raw_meta: Mapping[str, Any], name: str) -> list[str]:
    value = raw_meta.get(name)
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [str(item) for item in value if normalize_text(str(item))]
    return []


def _routes_from_landing_metadata(
    *,
    final_url: str,
    raw_meta: Mapping[str, Any],
) -> FrontiersArticleRoutes | None:
    routes = _canonical_routes_from_url(final_url)
    if routes is not None:
        return routes
    for key in ("citation_pdf_url", "citation_fulltext_html_url", "og:url"):
        for value in _raw_meta_values(raw_meta, key):
            routes = _canonical_routes_from_url(urllib.parse.urljoin(final_url, value))
            if routes is not None:
                return routes
    return None


def _metadata_frontiers_urls(metadata: Mapping[str, Any]) -> list[str]:
    urls: list[str] = []
    for key in ("landing_page_url", "source_url", "url"):
        value = normalize_text(str(metadata.get(key) or ""))
        if _is_frontiers_url(value):
            _append_unique(urls, value)
    for item in metadata.get("fulltext_links") or ():
        if not isinstance(item, Mapping):
            continue
        value = normalize_text(str(item.get("url") or ""))
        if _is_frontiers_url(value):
            _append_unique(urls, value)
    return urls


def _article_id_from_doi(doi: str | None) -> str:
    match = FRONTIERS_ARTICLE_ID_PATTERN.match(normalize_doi(doi))
    return normalize_text(match.group("article_id")) if match else ""


def _frontiers_graphic_url(*, doi: str | None, href: str | None) -> str:
    normalized_href = normalize_text(href)
    if not normalized_href:
        return ""
    parsed = urllib.parse.urlparse(normalized_href)
    filename = PurePosixPath(parsed.path).name if parsed.path else normalized_href
    if not filename:
        return ""
    stem = filename.rsplit(".", 1)[0]
    article_id = _article_id_from_doi(doi)
    if not article_id:
        match = FRONTIERS_GRAPHIC_FILENAME_PATTERN.search(stem)
        article_id = normalize_text(match.group("article_id")) if match else ""
    if not article_id:
        return ""
    return f"{FRONTIERS_HOST}/files/Articles/{article_id}/xml-images/{stem}.webp"


def _frontiers_supplementary_anchor(landing_url: str) -> str:
    return f"{landing_url}#supplementary-material" if landing_url else ""


def _replace_markdown_urls(markdown_text: str, replacements: Mapping[str, str]) -> str:
    updated = str(markdown_text or "")
    for source, target in replacements.items():
        if source and target and source != target:
            updated = updated.replace(source, target)
    return updated


def _normalize_frontiers_extracted_assets(
    assets: Sequence[Mapping[str, Any]],
    *,
    doi: str,
    landing_url: str,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    normalized_assets: list[dict[str, Any]] = []
    replacements: dict[str, str] = {}
    supplementary_anchor = _frontiers_supplementary_anchor(landing_url)
    for item in assets:
        asset = dict(item)
        kind = normalize_text(str(asset.get("kind") or asset.get("asset_type") or "")).lower()
        if kind in {"figure", "formula"}:
            for key in ("download_url", "full_size_url", "url", "original_url", "link", "preview_url"):
                value = normalize_text(str(asset.get(key) or ""))
                candidate = _frontiers_graphic_url(doi=doi, href=value)
                if candidate:
                    replacements[value] = candidate
                    asset["link"] = candidate
                    asset["original_url"] = candidate
                    asset["download_url"] = candidate
                    asset["full_size_url"] = candidate
                    break
        elif kind == "supplementary" and supplementary_anchor:
            for key in ("download_url", "full_size_url", "url", "original_url", "link", "preview_url"):
                value = normalize_text(str(asset.get(key) or ""))
                if value:
                    replacements[value] = supplementary_anchor
            asset.setdefault("source_url", normalize_text(str(asset.get("link") or asset.get("original_url") or "")))
            asset["link"] = supplementary_anchor
            asset["original_url"] = supplementary_anchor
        normalized_assets.append(asset)
    return normalized_assets, replacements


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


def _frontiers_figure_candidates(_transport, *, asset, user_agent, figure_page_fetcher=None) -> list[str]:
    del _transport, user_agent, figure_page_fetcher
    candidates: list[str] = []
    doi = normalize_text(str(asset.get("doi") or ""))
    for key in ("download_url", "full_size_url", "url", "original_url", "link", "preview_url"):
        value = normalize_text(str(asset.get(key) or ""))
        derived = _frontiers_graphic_url(doi=doi, href=value)
        if derived:
            _append_unique(candidates, derived)
        if value.startswith(("http://", "https://")):
            _append_unique(candidates, value)
    return candidates


class FrontiersClient(ProviderClient):
    name = "frontiers"
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
                    "xml_route",
                    OK,
                    "Frontiers article landing pages expose public JATS XML routes without provider credentials.",
                    details={"mode": "direct_http_xml"},
                ),
                build_provider_status_check(
                    PDF_FALLBACK,
                    OK,
                    "Frontiers PDF fallback is available from the same canonical article route when XML is not usable.",
                    details={"mode": "direct_http_pdf"},
                ),
            ],
        )

    def _landing_headers(self) -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": self.user_agent,
        }

    def _xml_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/xml,text/xml,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "User-Agent": self.user_agent,
        }

    def _asset_headers(self) -> dict[str, str]:
        return {"User-Agent": self.user_agent}

    def landing_candidates(self, doi: str, metadata: Mapping[str, Any]) -> list[str]:
        candidates: list[str] = []
        for value in _metadata_frontiers_urls(metadata):
            routes = _canonical_routes_from_url(value)
            _append_unique(candidates, routes.landing_url if routes is not None else value)
        normalized_doi = normalize_doi(doi)
        if normalized_doi:
            _append_unique(candidates, _frontiers_legacy_landing_url(normalized_doi))
        return candidates

    def route_candidates(self, doi: str, metadata: Mapping[str, Any]) -> list[FrontiersArticleRoutes]:
        routes: list[FrontiersArticleRoutes] = []
        seen: set[tuple[str | None, str]] = set()

        def append_route(route: FrontiersArticleRoutes | None) -> None:
            if route is None:
                return
            key = (route.xml_url, route.pdf_url)
            if key not in seen:
                seen.add(key)
                routes.append(route)

        for value in _metadata_frontiers_urls(metadata):
            append_route(_canonical_routes_from_url(value))

        last_failure: ProviderFailure | None = None
        for landing_url in self.landing_candidates(doi, metadata):
            try:
                landing = fetch_landing_html(
                    landing_url,
                    transport=self.transport,
                    headers=self._landing_headers(),
                    timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                    retry_on_transient=True,
                    max_redirects=self.landing_max_redirects,
                )
            except RequestFailure as exc:
                last_failure = map_request_failure(exc)
                continue
            status_code = int(landing.status_code or 200)
            if status_code >= 400:
                last_failure = ProviderFailure(NO_RESULT, f"Frontiers landing page returned HTTP {status_code}.")
                continue
            content_type = header_value(landing.headers, "content-type", "text/html")
            if "html" not in normalize_text(content_type).lower():
                last_failure = ProviderFailure(
                    NO_RESULT,
                    f"Frontiers landing page returned non-HTML content: {content_type or 'unknown'}.",
                )
                continue
            raw_meta = landing.metadata.get("raw_meta") if isinstance(landing.metadata, Mapping) else {}
            append_route(
                _routes_from_landing_metadata(
                    final_url=landing.final_url,
                    raw_meta=raw_meta if isinstance(raw_meta, Mapping) else {},
                )
            )

        append_route(_legacy_routes_from_doi(doi))
        if routes:
            return routes
        if last_failure is not None:
            raise last_failure
        raise ProviderFailure(NO_RESULT, "No Frontiers route candidates were available.")

    def _fetch_xml_payload(
        self,
        route: FrontiersArticleRoutes,
        doi: str,
        metadata: Mapping[str, Any],
    ) -> RawFulltextPayload:
        if not route.xml_url:
            raise ProviderFailure(NO_RESULT, "Frontiers canonical XML URL was not available.")
        try:
            response = self.transport.request(
                "GET",
                route.xml_url,
                headers=self._xml_headers(),
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                retry_on_transient=True,
            )
        except RequestFailure as exc:
            raise map_request_failure(exc) from exc

        status_code = int(response.get("status_code") or 200)
        if status_code >= 400:
            raise ProviderFailure(NO_RESULT, f"Frontiers XML endpoint returned HTTP {status_code}.")
        headers = response.get("headers") if isinstance(response.get("headers"), Mapping) else {}
        content_type = header_value(headers, "content-type", "application/xml")
        body = _response_body(response)
        if not body:
            raise ProviderFailure(NO_RESULT, "Frontiers XML endpoint returned an empty body.")
        if _looks_like_html(body, content_type):
            raise ProviderFailure(NO_RESULT, "Frontiers XML endpoint returned HTML instead of JATS XML.")

        final_url = normalize_text(str(response.get("url") or route.xml_url)) or route.xml_url
        extraction = parse_jats_xml(body, source_url=final_url, base_metadata=metadata)
        if extraction is None:
            raise ProviderFailure(NO_RESULT, "Frontiers XML response did not parse as a JATS article.")
        if not normalize_text(extraction.markdown_text) and not extraction.references and not extraction.abstract_sections:
            raise ProviderFailure(NO_RESULT, "Frontiers XML response did not contain article body, references, or abstract text.")

        merged_metadata = dict(extraction.metadata)
        merged_metadata["landing_page_url"] = route.landing_url
        normalized_assets, replacements = _normalize_frontiers_extracted_assets(
            extraction.assets,
            doi=normalize_doi(str(merged_metadata.get("doi") or doi or "")),
            landing_url=route.landing_url,
        )
        markdown_text = _replace_markdown_urls(extraction.markdown_text, replacements)
        return build_provider_payload(
            provider=self.name,
            route_kind="xml",
            source_url=final_url,
            content_type=content_type,
            body=body,
            markdown_text=markdown_text,
            merged_metadata=merged_metadata,
            diagnostics={
                "extraction": {
                    "abstract_sections": extraction.abstract_sections,
                    "references": extraction.references,
                    "references_count": len(extraction.references),
                    "assets_count": len(normalized_assets),
                    "conversion_notes": list(extraction.conversion_notes),
                    "semantic_losses": asdict(extraction.semantic_losses),
                }
            },
            reason="Downloaded full text from the Frontiers public JATS XML route.",
            extracted_assets=normalized_assets,
            trace_markers=[fulltext_marker(self.name, "ok", route="xml")],
        )

    def _fetch_pdf_payload(
        self,
        route: FrontiersArticleRoutes,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        xml_failure_message: str,
        context: RuntimeContext | None = None,
    ) -> RawFulltextPayload:
        effective_asset_profile = pdf_asset_profile_from_context(context)
        try:
            pdf_result = PdfFallbackStrategy(
                transport=self.transport,
                headers=default_pdf_headers(self.user_agent, referer=route.landing_url),
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                asset_profile=effective_asset_profile,
                asset_output_dir=pdf_asset_output_dir(context, asset_profile=effective_asset_profile, doi=doi),
                fetcher=fetch_pdf_over_http,
            ).fetch([route.pdf_url])
        except PdfFetchFailure as exc:
            raise ProviderFailure(NO_RESULT, exc.message) from exc

        article_metadata = dict(metadata)
        article_metadata.setdefault("doi", normalize_doi(doi) or doi)
        article_metadata.setdefault("landing_page_url", route.landing_url)
        return build_provider_payload(
            provider=self.name,
            route_kind=PDF_FALLBACK,
            source_url=pdf_result.final_url or pdf_result.source_url or route.pdf_url,
            content_type=PDF_MIME_TYPE,
            body=pdf_result.pdf_bytes,
            markdown_text=pdf_result.markdown_text,
            merged_metadata=article_metadata,
            diagnostics={PDF_FALLBACK: {"candidates": [route.pdf_url]}},
            reason="Downloaded full text from the Frontiers PDF fallback after XML was not usable.",
            suggested_filename=pdf_result.suggested_filename,
            extracted_assets=pdf_fetch_result_assets(pdf_result),
            html_failure_message=xml_failure_message,
            warnings=[
                f"Frontiers XML route was not usable ({xml_failure_message}); used PDF fallback.",
            ],
            trace_markers=[
                fulltext_marker(self.name, "fail", route="xml"),
                fulltext_marker(self.name, "ok", route=PDF_FALLBACK),
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
        routes = self.route_candidates(doi, metadata)
        failures: list[tuple[str, ProviderFailure]] = []
        for route in routes:
            try:
                return self._fetch_xml_payload(route, doi, metadata)
            except ProviderFailure as exc:
                failures.append(("xml", exc))

        xml_failure_message = combine_provider_failures(failures).message if failures else "No XML candidates were available."
        for route in routes:
            try:
                return self._fetch_pdf_payload(
                    route,
                    doi,
                    metadata,
                    xml_failure_message=xml_failure_message,
                    context=context,
                )
            except ProviderFailure as exc:
                failures.append(("pdf", exc))

        combined = combine_provider_failures(failures)
        raise ProviderFailure(
            combined.code,
            "Frontiers full-text routes were not usable. " + combined.message,
            warnings=combined.warnings,
            source_trail=[
                fulltext_marker(self.name, "fail", route="xml"),
                fulltext_marker(self.name, "fail", route="pdf"),
                *combined.source_trail,
            ],
        )

    def should_download_related_assets_for_result(
        self,
        raw_payload: RawFulltextPayload,
        *,
        provisional_article=None,
    ) -> bool:
        del provisional_article
        content = raw_payload.content
        return normalize_text(content.route_kind if content is not None else "").lower() != PDF_FALLBACK

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
        route = normalize_text(content.route_kind if content is not None else "").lower()
        if route == PDF_FALLBACK:
            return empty_asset_results()
        extracted_assets = _filter_assets_for_profile(
            list(content.extracted_assets if content is not None else []),
            asset_profile=asset_profile,
        )
        if not extracted_assets:
            return empty_asset_results()

        body_assets, _supplementary_assets = split_body_and_supplementary_assets(extracted_assets)
        body_image_assets = [
            dict(item)
            for item in body_assets
            if normalize_text(str(item.get("kind") or item.get("asset_type") or "")).lower() in {"figure", "formula"}
        ]
        article_id = (
            normalize_doi(str((content.merged_metadata or {}).get("doi") or doi or ""))
            or normalize_doi(doi)
            or normalize_text(str(metadata.get("title") or ""))
            or raw_payload.source_url
        )
        if not body_image_assets:
            return empty_asset_results()
        return download_assets(
            FIGURE_KIND,
            self.transport,
            article_id=article_id,
            assets=body_image_assets,
            output_dir=output_dir,
            user_agent=self.user_agent,
            asset_profile=asset_profile,
            headers=self._asset_headers(),
            candidate_builder=_frontiers_figure_candidates,
            asset_download_concurrency=resolve_asset_download_concurrency(context.env),
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
        merged_metadata = content.merged_metadata if content is not None else raw_payload.merged_metadata
        article_metadata = dict(merged_metadata if isinstance(merged_metadata, Mapping) else metadata)
        doi = normalize_doi(str(article_metadata.get("doi") or metadata.get("doi") or ""))
        route = normalize_text(content.route_kind if content is not None else "").lower()
        trace = list(raw_payload.trace or trace_from_markers([fulltext_marker(self.name, "ok", route="xml")]))
        warnings = list(raw_payload.warnings)
        if asset_failures:
            warnings.append(f"Frontiers related assets were only partially downloaded ({len(asset_failures)} failed).")

        source: SourceKind = "frontiers_pdf" if route == PDF_FALLBACK else "frontiers_xml"
        markdown_text = str((content.markdown_text if content is not None else "") or "").strip()
        if not markdown_text:
            warnings.append("Frontiers retrieval did not produce usable Markdown.")
            return metadata_only_article(
                source=source,
                metadata=article_metadata,
                doi=doi or None,
                warnings=warnings,
                trace=trace,
            )

        diagnostics = dict(content.diagnostics.get("extraction") or {}) if content is not None else {}
        references = diagnostics.get("references")
        if isinstance(references, list) and references:
            article_metadata["references"] = [
                dict(item) if isinstance(item, Mapping) else item for item in references
            ]
        abstract_sections = diagnostics.get("abstract_sections")
        semantic_losses = diagnostics.get("semantic_losses")
        assets = _merge_assets(
            list(content.extracted_assets if content is not None else []),
            list(downloaded_assets or []),
        )
        article = article_from_markdown(
            source=source,
            metadata=article_metadata,
            doi=normalize_doi(str(article_metadata.get("doi") or doi)) or None,
            markdown_text=markdown_text,
            abstract_sections=abstract_sections if isinstance(abstract_sections, list) else None,
            assets=assets,
            warnings=warnings,
            trace=trace,
            semantic_losses=semantic_losses if isinstance(semantic_losses, Mapping) else None,
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
        if normalize_text(content.route_kind if content is not None else "").lower() != PDF_FALLBACK:
            return artifacts
        pdf_assets = list(content.extracted_assets if content is not None else [])
        return ProviderArtifacts(
            assets=[*list(artifacts.assets), *pdf_assets],
            asset_failures=list(artifacts.asset_failures),
            allow_related_assets=False,
            text_only=not pdf_assets,
            skip_trace=trace_from_markers([download_marker("frontiers_assets_skipped_text_only")])
            if not pdf_assets
            else [],
        )


__all__ = ["FrontiersClient"]
