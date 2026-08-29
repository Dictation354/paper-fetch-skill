"""Frontiers public JATS XML provider client."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import html
from pathlib import PurePosixPath
from typing import Any
from collections.abc import Mapping, Sequence
import re
import urllib.parse

from ..config import build_publisher_user_agent, resolve_asset_download_concurrency
from ..failure import FailureDiagnostics
from ..extraction.html.assets import (
    FIGURE_KIND,
    SUPPLEMENTARY_KIND,
    download_assets,
    filter_assets_for_profile,
    merge_extracted_and_downloaded_assets,
    split_body_and_supplementary_assets,
)
from ..extraction.html.availability_policy import AvailabilityPolicy
from ..extraction.html.landing import fetch_landing_html
from ..extraction.html.provider_rules import ProviderFrontMatterRules, ProviderHtmlRules
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
    provider_body_text_thresholds,
)
from ..publisher_identity import normalize_doi
from ..reason_codes import NO_RESULT, OK, PDF_FALLBACK
from ..runtime import RuntimeContext
from ..tracing import download_marker, fulltext_marker, trace_from_markers
from ..utils import empty_asset_results, normalize_text
from ._article_markdown_jats import assess_jats_body_availability, parse_jats_xml
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
FRONTIERS_ARTICLE_ID_PATTERN = re.compile(
    r"^10\.3389/[^.]+\.\d{4}\.(?P<article_id>[^/?#]+)$"
)
FRONTIERS_GRAPHIC_FILENAME_PATTERN = re.compile(
    r"(?P<article_id>\d+)-g\d+",
    flags=re.IGNORECASE,
)
FRONTIERS_ORIGINAL_GRAPHIC_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?frontiersin\.org/files/Articles/"
    r"\d+/xml-images/[^\"'<>?&#\s]+",
    flags=re.IGNORECASE,
)
FRONTIERS_ORIGINAL_GRAPHIC_PATH_PATTERN = re.compile(
    r"^/files/Articles/\d+/xml-images/[^/]+$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class FrontiersArticleRoutes:
    landing_url: str
    xml_url: str | None
    pdf_url: str
    discovery_reason: str = "metadata_canonical"


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
    return (
        prefix.startswith(b"<!doctype html")
        or prefix.startswith(b"<html")
        or b"<html" in prefix
    )


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


def _canonical_routes_from_url(
    value: str | None,
    *,
    discovery_reason: str = "metadata_canonical",
) -> FrontiersArticleRoutes | None:
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
        discovery_reason=discovery_reason,
    )


def _legacy_routes_from_doi(doi: str) -> FrontiersArticleRoutes:
    normalized = normalize_doi(doi)
    landing_url = _frontiers_legacy_landing_url(normalized)
    return FrontiersArticleRoutes(
        landing_url=landing_url,
        xml_url=None,
        pdf_url=_frontiers_legacy_pdf_url(normalized),
        discovery_reason="legacy_doi_fallback",
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
    routes = _canonical_routes_from_url(
        final_url,
        discovery_reason="landing_redirect",
    )
    if routes is not None:
        return routes
    for key in ("citation_pdf_url", "citation_fulltext_html_url", "og:url"):
        for value in _raw_meta_values(raw_meta, key):
            routes = _canonical_routes_from_url(
                urllib.parse.urljoin(final_url, value),
                discovery_reason="landing_metadata",
            )
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


def _frontiers_graphic_stem(value: str | None) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    parsed = urllib.parse.urlparse(normalized)
    filename = PurePosixPath(urllib.parse.unquote(parsed.path)).name
    return filename.rsplit(".", 1)[0] if filename else ""


def _is_frontiers_original_graphic_url(value: str | None) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    parsed = urllib.parse.urlparse(normalized)
    return (
        parsed.scheme.lower() in {"http", "https"}
        and _is_frontiers_url(normalized)
        and bool(FRONTIERS_ORIGINAL_GRAPHIC_PATH_PATTERN.fullmatch(parsed.path))
    )


def _frontiers_original_graphics_from_landing(html_text: str) -> dict[str, str]:
    original_graphics: dict[str, str] = {}
    for match in FRONTIERS_ORIGINAL_GRAPHIC_URL_PATTERN.finditer(
        html.unescape(str(html_text or ""))
    ):
        candidate = normalize_text(match.group(0))
        stem = _frontiers_graphic_stem(candidate)
        if stem and _is_frontiers_original_graphic_url(candidate):
            original_graphics.setdefault(stem, candidate)
    return original_graphics


def _frontiers_asset_graphic_stems(asset: Mapping[str, Any]) -> list[str]:
    stems: list[str] = []
    for key in (
        "download_url",
        "full_size_url",
        "url",
        "original_url",
        "link",
        "preview_url",
    ):
        _append_unique(stems, _frontiers_graphic_stem(str(asset.get(key) or "")))
    alternatives = asset.get("alternatives")
    if isinstance(alternatives, Sequence) and not isinstance(
        alternatives, (bytes, bytearray, str)
    ):
        for alternative in alternatives:
            if not isinstance(alternative, Mapping):
                continue
            for key in ("url", "original_url"):
                _append_unique(
                    stems,
                    _frontiers_graphic_stem(str(alternative.get(key) or "")),
                )
    return stems


def _promote_frontiers_original_graphics(
    assets: Sequence[Mapping[str, Any]],
    *,
    original_graphics: Mapping[str, str],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    promoted_assets: list[dict[str, Any]] = []
    replacements: dict[str, str] = {}
    for item in assets:
        asset = dict(item)
        kind = normalize_text(
            str(asset.get("kind") or asset.get("asset_type") or "")
        ).lower()
        matched_url = ""
        if kind in {"figure", "formula"}:
            matched_url = next(
                (
                    normalize_text(original_graphics.get(stem))
                    for stem in _frontiers_asset_graphic_stems(asset)
                    if normalize_text(original_graphics.get(stem))
                ),
                "",
            )
        if matched_url:
            for key in (
                "download_url",
                "full_size_url",
                "url",
                "original_url",
                "link",
                "preview_url",
            ):
                previous = normalize_text(str(asset.get(key) or ""))
                if previous and previous != matched_url:
                    replacements[previous] = matched_url
            asset["link"] = matched_url
            asset["original_url"] = matched_url
            asset["download_url"] = matched_url
            asset["full_size_url"] = matched_url
        promoted_assets.append(asset)
    return promoted_assets, replacements


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
        kind = normalize_text(
            str(asset.get("kind") or asset.get("asset_type") or "")
        ).lower()
        if kind in {"figure", "formula"}:
            for key in (
                "download_url",
                "full_size_url",
                "url",
                "original_url",
                "link",
                "preview_url",
            ):
                value = normalize_text(str(asset.get(key) or ""))
                candidate = _frontiers_graphic_url(doi=doi, href=value)
                if candidate:
                    replacements[value] = candidate
                    asset["link"] = candidate
                    asset["original_url"] = candidate
                    asset["download_url"] = candidate
                    asset["full_size_url"] = candidate
                    break
        elif kind == "supplementary":
            source_href = normalize_text(str(asset.get("source_href") or ""))
            original_value = next(
                (
                    normalize_text(str(asset.get(key) or ""))
                    for key in (
                        "download_url",
                        "full_size_url",
                        "url",
                        "original_url",
                        "link",
                    )
                    if normalize_text(str(asset.get(key) or ""))
                ),
                "",
            )
            source_value = source_href or original_value
            parsed = urllib.parse.urlparse(source_value)
            downloadable = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
            if downloadable:
                asset["download_url"] = original_value
                asset["original_url"] = original_value
                asset["link"] = original_value
                asset["archive_state"] = "downloadable"
            elif supplementary_anchor:
                asset["link"] = supplementary_anchor
                asset["archive_state"] = "not_archived"
                asset["not_archived_reason"] = (
                    "Frontiers supplementary entry did not expose a downloadable URL."
                )
            if source_value:
                asset["source_url"] = source_value
            elif supplementary_anchor:
                asset["source_url"] = supplementary_anchor
            if original_value and not downloadable and supplementary_anchor:
                replacements[original_value] = supplementary_anchor
        normalized_assets.append(asset)
    return normalized_assets, replacements


def _frontiers_figure_candidates(
    _transport, *, asset, user_agent, figure_page_fetcher=None
) -> list[str]:
    del _transport, user_agent, figure_page_fetcher
    candidates: list[str] = []
    doi = normalize_text(str(asset.get("doi") or ""))
    keys = (
        "download_url",
        "full_size_url",
        "url",
        "original_url",
        "link",
        "preview_url",
    )
    values = [normalize_text(str(asset.get(key) or "")) for key in keys]
    for value in values:
        if _is_frontiers_original_graphic_url(value):
            _append_unique(candidates, value)
    for value in values:
        derived = _frontiers_graphic_url(doi=doi, href=value)
        if derived:
            _append_unique(candidates, derived)
    for value in values:
        if value.startswith(("http://", "https://")):
            _append_unique(candidates, value)
    return candidates


class FrontiersClient(ProviderClient):
    name = "frontiers"
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

    def _landing_original_graphics(self, landing_url: str) -> dict[str, str]:
        if not _is_frontiers_url(landing_url):
            return {}
        try:
            landing = fetch_landing_html(
                landing_url,
                transport=self.transport,
                headers=self._landing_headers(),
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                retry_on_transient=True,
                max_redirects=self.landing_max_redirects,
            )
        except (OSError, RequestFailure):
            return {}
        if int(landing.status_code or 200) >= 400:
            return {}
        content_type = header_value(landing.headers, "content-type", "text/html")
        if "html" not in normalize_text(content_type).lower():
            return {}
        return _frontiers_original_graphics_from_landing(landing.html_text)

    def landing_candidates(self, doi: str, metadata: Mapping[str, Any]) -> list[str]:
        candidates: list[str] = []
        for value in _metadata_frontiers_urls(metadata):
            routes = _canonical_routes_from_url(value)
            _append_unique(
                candidates, routes.landing_url if routes is not None else value
            )
        normalized_doi = normalize_doi(doi)
        if normalized_doi:
            _append_unique(candidates, _frontiers_legacy_landing_url(normalized_doi))
        return candidates

    def route_candidates(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        *,
        discover_landing: bool = True,
    ) -> list[FrontiersArticleRoutes]:
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

        if not discover_landing:
            return routes

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
                last_failure = ProviderFailure(
                    NO_RESULT, f"Frontiers landing page returned HTTP {status_code}."
                )
                continue
            content_type = header_value(landing.headers, "content-type", "text/html")
            if "html" not in normalize_text(content_type).lower():
                last_failure = ProviderFailure(
                    NO_RESULT,
                    f"Frontiers landing page returned non-HTML content: {content_type or 'unknown'}.",
                )
                continue
            raw_meta = (
                landing.metadata.get("raw_meta")
                if isinstance(landing.metadata, Mapping)
                else {}
            )
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
        raise ProviderFailure(
            NO_RESULT, "No Frontiers route candidates were available."
        )

    def _fetch_xml_payload(
        self,
        route: FrontiersArticleRoutes,
        doi: str,
        metadata: Mapping[str, Any],
    ) -> RawFulltextPayload:
        if not route.xml_url:
            raise ProviderFailure(
                NO_RESULT, "Frontiers canonical XML URL was not available."
            )
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
            raise ProviderFailure(
                NO_RESULT, f"Frontiers XML endpoint returned HTTP {status_code}."
            )
        headers = (
            response.get("headers")
            if isinstance(response.get("headers"), Mapping)
            else {}
        )
        content_type = header_value(headers, "content-type", "application/xml")
        body = _response_body(response)
        if not body:
            raise ProviderFailure(
                NO_RESULT, "Frontiers XML endpoint returned an empty body."
            )
        if _looks_like_html(body, content_type):
            raise ProviderFailure(
                NO_RESULT, "Frontiers XML endpoint returned HTML instead of JATS XML."
            )

        final_url = (
            normalize_text(str(response.get("url") or route.xml_url)) or route.xml_url
        )
        extraction = parse_jats_xml(body, source_url=final_url, base_metadata=metadata)
        if extraction is None:
            raise ProviderFailure(
                NO_RESULT, "Frontiers XML response did not parse as a JATS article."
            )
        availability = assess_jats_body_availability(
            extraction,
            min_body_chars=provider_body_text_thresholds(self.name).min_chars,
        )
        if not availability.accepted:
            raise ProviderFailure(
                NO_RESULT,
                "Frontiers XML response did not contain sufficient JATS body prose.",
                diagnostics=FailureDiagnostics(
                    details={"availability_diagnostics": availability.to_dict()}
                ),
            )

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
            route_name="xml",
            source_url=final_url,
            content_type=content_type,
            body=body,
            markdown_text=markdown_text,
            merged_metadata=merged_metadata,
            diagnostics={
                "route_discovery": {
                    "reason": route.discovery_reason,
                    "landing_requested": route.discovery_reason.startswith("landing_"),
                },
                "extraction": {
                    "abstract_sections": extraction.abstract_sections,
                    "references": extraction.references,
                    "references_count": len(extraction.references),
                    "assets_count": len(normalized_assets),
                    "conversion_notes": list(extraction.conversion_notes),
                    "semantic_losses": asdict(extraction.semantic_losses),
                },
                "availability_diagnostics": availability.to_dict(),
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
                provider_name="frontiers",
                headers=default_pdf_headers(self.user_agent, referer=route.landing_url),
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                asset_profile=effective_asset_profile,
                asset_output_dir=pdf_asset_output_dir(
                    context, asset_profile=effective_asset_profile, doi=doi
                ),
                expected_identity={
                    "doi": doi,
                    "title": metadata.get("title"),
                },
                context=context,
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
            route_name="direct_pdf",
            source_url=pdf_result.final_url or pdf_result.source_url or route.pdf_url,
            content_type=PDF_MIME_TYPE,
            body=pdf_result.pdf_bytes,
            markdown_text=pdf_result.markdown_text,
            merged_metadata=article_metadata,
            diagnostics={
                "route_discovery": {
                    "reason": route.discovery_reason,
                    "landing_requested": route.discovery_reason.startswith("landing_"),
                },
                PDF_FALLBACK: {"candidates": [route.pdf_url]},
            },
            reason="Downloaded full text from the Frontiers PDF fallback after XML was not usable.",
            suggested_filename=pdf_result.suggested_filename,
            extracted_assets=pdf_fetch_result_assets(pdf_result),
            html_failure_message=xml_failure_message,
            warnings=[
                *pdf_fetch_result_warnings(pdf_result),
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
        failures: list[tuple[str, ProviderFailure]] = []

        direct_routes = self.route_candidates(
            doi,
            metadata,
            discover_landing=False,
        )
        for route in direct_routes:
            try:
                return self.validate_raw_payload_identity(
                    doi,
                    metadata,
                    self._fetch_xml_payload(route, doi, metadata),
                )
            except ProviderFailure as exc:
                failures.append(("xml", exc))

            xml_failure_message = combine_provider_failures(failures).message
            try:
                return self.validate_raw_payload_identity(
                    doi,
                    metadata,
                    self._fetch_pdf_payload(
                        route,
                        doi,
                        metadata,
                        xml_failure_message=xml_failure_message,
                        context=context,
                    ),
                )
            except ProviderFailure as exc:
                failures.append(("pdf", exc))

        discovered_routes = self.route_candidates(
            doi,
            metadata,
            discover_landing=True,
        )
        direct_keys = {(route.xml_url, route.pdf_url) for route in direct_routes}
        routes = [
            route
            for route in discovered_routes
            if (route.xml_url, route.pdf_url) not in direct_keys
        ]
        for route in routes:
            try:
                return self.validate_raw_payload_identity(
                    doi,
                    metadata,
                    self._fetch_xml_payload(route, doi, metadata),
                )
            except ProviderFailure as exc:
                failures.append(("xml", exc))

        xml_failure_message = (
            combine_provider_failures(failures).message
            if failures
            else "No XML candidates were available."
        )
        for route in routes:
            try:
                return self.validate_raw_payload_identity(
                    doi,
                    metadata,
                    self._fetch_pdf_payload(
                        route,
                        doi,
                        metadata,
                        xml_failure_message=xml_failure_message,
                        context=context,
                    ),
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
        return (
            normalize_text(content.route_kind if content is not None else "").lower()
            != PDF_FALLBACK
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
        body_image_assets = [
            dict(item)
            for item in body_assets
            if normalize_text(
                str(item.get("kind") or item.get("asset_type") or "")
            ).lower()
            in {"figure", "formula"}
        ]
        if body_image_assets and content is not None:
            landing_metadata = content.merged_metadata or {}
            landing_url = normalize_text(
                str(
                    landing_metadata.get("landing_page_url")
                    or metadata.get("landing_page_url")
                    or ""
                )
            )
            original_graphics = self._landing_original_graphics(landing_url)
            if original_graphics:
                promoted_assets, replacements = _promote_frontiers_original_graphics(
                    content.extracted_assets,
                    original_graphics=original_graphics,
                )
                content = replace(
                    content,
                    extracted_assets=promoted_assets,
                    markdown_text=_replace_markdown_urls(
                        content.markdown_text or "", replacements
                    ),
                )
                raw_payload.content = content
                extracted_assets = filter_assets_for_profile(
                    promoted_assets,
                    asset_profile=asset_profile,
                )
                body_assets, supplementary_assets = split_body_and_supplementary_assets(
                    extracted_assets
                )
                body_image_assets = [
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
            or normalize_doi(doi)
            or normalize_text(str(metadata.get("title") or ""))
            or raw_payload.source_url
        )
        concurrency = resolve_asset_download_concurrency(context.env)
        results: list[Mapping[str, Any]] = []
        if body_image_assets:
            results.append(
                download_assets(
                    FIGURE_KIND,
                    self.transport,
                    article_id=article_id,
                    assets=body_image_assets,
                    output_dir=output_dir,
                    user_agent=self.user_agent,
                    asset_profile=asset_profile,
                    headers=self._asset_headers(),
                    candidate_builder=_frontiers_figure_candidates,
                    asset_download_concurrency=concurrency,
                    fetch_policy="direct_then_browser",
                    provider_name="frontiers",
                    runtime_context=context,
                )
            )
        if asset_profile == "all" and supplementary_assets:
            downloadable = [
                dict(asset)
                for asset in supplementary_assets
                if normalize_text(str(asset.get("archive_state") or ""))
                != "not_archived"
            ]
            if downloadable:
                results.append(
                    download_assets(
                        SUPPLEMENTARY_KIND,
                        self.transport,
                        article_id=article_id,
                        assets=downloadable,
                        output_dir=output_dir,
                        user_agent=self.user_agent,
                        asset_profile=asset_profile,
                        headers=self._asset_headers(),
                        asset_download_concurrency=concurrency,
                        fetch_policy="direct_then_browser",
                        provider_name="frontiers",
                        runtime_context=context,
                    )
                )
            unresolved_failures = [
                {
                    "kind": "supplementary",
                    "heading": asset.get("heading") or "Supplementary material",
                    "source_url": asset.get("source_url") or asset.get("link") or "",
                    "section": "supplementary",
                    "reason": asset.get("not_archived_reason")
                    or "Frontiers supplementary entry was not archived.",
                    "archive_state": "not_archived",
                }
                for asset in supplementary_assets
                if normalize_text(str(asset.get("archive_state") or ""))
                == "not_archived"
            ]
            if unresolved_failures:
                results.append({"assets": [], "asset_failures": unresolved_failures})
        return {
            "assets": [
                dict(asset)
                for result in results
                for asset in list(result.get("assets") or [])
            ],
            "asset_failures": [
                dict(failure)
                for result in results
                for failure in list(result.get("asset_failures") or [])
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
                f"Frontiers related assets were only partially downloaded ({len(asset_failures)} failed)."
            )

        source: SourceKind = (
            "frontiers_pdf" if route == PDF_FALLBACK else "frontiers_xml"
        )
        markdown_text = str(
            (content.markdown_text if content is not None else "") or ""
        ).strip()
        if not markdown_text:
            warnings.append("Frontiers retrieval did not produce usable Markdown.")
            return metadata_only_article(
                source=source,
                metadata=article_metadata,
                doi=doi or None,
                warnings=warnings,
                trace=trace,
            )

        diagnostics = (
            dict(content.diagnostics.get("extraction") or {})
            if content is not None
            else {}
        )
        references = diagnostics.get("references")
        if isinstance(references, list) and references:
            article_metadata["references"] = [
                dict(item) if isinstance(item, Mapping) else item for item in references
            ]
        abstract_sections = diagnostics.get("abstract_sections")
        semantic_losses = diagnostics.get("semantic_losses")
        assets = merge_extracted_and_downloaded_assets(
            list(content.extracted_assets if content is not None else []),
            list(downloaded_assets or []),
        )
        article = article_from_markdown(
            source=source,
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
                [download_marker("frontiers_assets_skipped_text_only")]
            )
            if not pdf_assets
            else [],
        )


__all__ = ["FrontiersClient"]
