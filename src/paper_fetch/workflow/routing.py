"""Routing and probe logic for provider selection."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Mapping, cast
import urllib.parse

from ..config import build_user_agent
from ..extraction.html.landing import fetch_landing_html
from ..http import HttpTransport, RequestFailure
from ..metadata_types import ProviderMetadata
from ..provider_catalog import official_provider_names
from ..providers.base import ProviderFailure
from ..providers.protocols import MetadataProvider
from ..runtime import RUNTIME_UNSET, RuntimeContext, resolve_runtime_context
from ..publisher_identity import (
    infer_provider_from_doi,
    infer_provider_from_publisher,
    infer_provider_from_url,
    normalize_doi,
    ordered_provider_candidates,
)
from ..utils import choose_public_landing_page_url, extend_unique, normalize_text, safe_text
from .resolution import resolve_paper
from .types import FetchStrategy, HasFulltextProbeResult, PaperFetchFailure, RouteProbeResult

OFFICIAL_PROVIDER_NAMES = official_provider_names()
_CACHE_MISSING = object()


@dataclass(frozen=True)
class LandingPageCitationPdfProbeResult:
    has_citation_pdf_url: bool
    title: str | None
    citation_pdf_urls: list[str]


def provider_allowed(provider_name: str | None, strategy: FetchStrategy) -> bool:
    normalized = strategy.normalized_preferred_providers()
    if normalized is None:
        return True
    if provider_name is None:
        return False
    return normalize_text(provider_name).lower() in normalized


def crossref_allowed_as_source(strategy: FetchStrategy) -> bool:
    return provider_allowed("crossref", strategy)


def route_signal_markers(
    *,
    landing_urls: list[str | None] | None = None,
    publishers: list[str | None] | None = None,
    doi: str | None = None,
) -> list[str]:
    markers: list[str] = []
    for url in landing_urls or []:
        provider = infer_provider_from_url(url)
        if provider:
            extend_unique(markers, [f"route:signal_domain_{provider}"])
    for publisher in publishers or []:
        provider = infer_provider_from_publisher(publisher)
        if provider:
            extend_unique(markers, [f"route:signal_publisher_{provider}"])
    provider = infer_provider_from_doi(doi)
    if provider:
        extend_unique(markers, [f"route:signal_doi_{provider}"])
    return markers


def build_official_provider_candidates(
    resolved,
    *,
    routing_metadata: Mapping[str, Any] | None,
    strategy: FetchStrategy,
) -> list[tuple[str, str]]:
    candidates = ordered_provider_candidates(
        landing_urls=[
            resolved.landing_url,
            safe_text((routing_metadata or {}).get("landing_page_url")),
        ],
        publishers=[safe_text((routing_metadata or {}).get("publisher"))],
        doi=resolved.doi,
    )
    return [
        (provider, signal)
        for provider, signal in candidates
        if provider in OFFICIAL_PROVIDER_NAMES and provider_allowed(provider, strategy)
    ]


def classify_probe_state(failure: ProviderFailure) -> str:
    if failure.code == "no_result":
        return "negative"
    return "unknown"


def _is_unknown_has_fulltext_probe_failure(error: ProviderFailure) -> bool:
    return error.code in {"no_access", "rate_limited", "not_configured", "not_supported", "error"}


def _probe_warning(prefix: str, message: str) -> str:
    normalized_message = normalize_text(message)
    if not normalized_message:
        return prefix
    return f"{prefix}: {normalized_message}"


def _landing_page_citation_pdf_probe(
    landing_url: str,
    *,
    transport: HttpTransport,
    env: Mapping[str, str],
) -> LandingPageCitationPdfProbeResult:
    landing_fetch = fetch_landing_html(
        landing_url,
        transport=transport,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": build_user_agent(env),
        },
        max_redirects=0,
        retry_on_transient=True,
    )
    html_metadata = landing_fetch.metadata
    raw_meta = html_metadata.get("raw_meta") or {}
    citation_pdf_values = raw_meta.get("citation_pdf_url") if isinstance(raw_meta, Mapping) else None
    citation_pdf_urls = [
        urllib.parse.urljoin(landing_fetch.final_url, normalized)
        for normalized in [normalize_text(item) for item in (citation_pdf_values or [])]
        if normalized
    ]
    return LandingPageCitationPdfProbeResult(
        has_citation_pdf_url=bool(citation_pdf_urls),
        title=normalize_text(html_metadata.get("title")),
        citation_pdf_urls=list(dict.fromkeys(citation_pdf_urls)),
    )


def _session_cache_key_resolved_query(query: str) -> tuple[str, str]:
    return ("resolved_query", normalize_text(query) or str(query))


def _session_cache_key_crossref_metadata(doi: str) -> tuple[str, str, str]:
    return ("metadata", "crossref", normalize_doi(doi) or doi)


def _session_cache_key_provider_metadata_probe(provider_name: str, doi: str) -> tuple[str, str, str]:
    return ("metadata_probe", normalize_text(provider_name).lower(), normalize_doi(doi) or doi)


def _session_cache_key_landing_citation_pdf_probe(landing_url: str) -> tuple[str, str]:
    return ("landing_page_citation_pdf_probe", normalize_text(landing_url) or landing_url)


def resolve_query_with_session_cache(
    query: str,
    *,
    resolver,
    transport: HttpTransport,
    env: Mapping[str, str],
    context: RuntimeContext,
):
    cache_key = _session_cache_key_resolved_query(query)
    return context.get_or_set_session_cache(
        cache_key,
        lambda: resolver(query, transport=transport, env=env),
        copy_value=True,
    )


def fetch_crossref_metadata_with_session_cache(
    doi: str | None,
    crossref_client: object,
    *,
    context: RuntimeContext | None = None,
) -> ProviderMetadata | None:
    if not doi or not isinstance(crossref_client, MetadataProvider):
        return None
    normalized_doi = normalize_doi(doi) or doi
    cache_key = _session_cache_key_crossref_metadata(normalized_doi)
    if context is not None:
        cached = context.get_session_cache(cache_key, default=_CACHE_MISSING)
        if cached is not _CACHE_MISSING:
            return cast(ProviderMetadata, cached)
    metadata = cast(ProviderMetadata, dict(crossref_client.fetch_metadata({"doi": normalized_doi})))
    if metadata and context is not None:
        context.set_session_cache(cache_key, metadata)
    return metadata


def fetch_provider_metadata_probe_with_session_cache(
    provider_name: str,
    doi: str | None,
    *,
    clients: Mapping[str, object],
    context: RuntimeContext | None = None,
) -> ProviderMetadata | None:
    if not doi:
        return None
    client = clients.get(provider_name)
    if not isinstance(client, MetadataProvider):
        return None
    normalized_doi = normalize_doi(doi) or doi
    cache_key = _session_cache_key_provider_metadata_probe(provider_name, normalized_doi)
    if context is not None:
        cached = context.get_session_cache(cache_key, default=_CACHE_MISSING)
        if cached is not _CACHE_MISSING:
            return cast(ProviderMetadata, cached)
    metadata = client.fetch_metadata({"doi": normalized_doi})
    result = cast(ProviderMetadata, dict(metadata)) if metadata else None
    if result and context is not None:
        context.set_session_cache(cache_key, result)
    return result


def landing_page_citation_pdf_probe_with_session_cache(
    landing_url: str,
    *,
    transport: HttpTransport,
    env: Mapping[str, str],
    context: RuntimeContext | None = None,
) -> LandingPageCitationPdfProbeResult:
    cache_key = _session_cache_key_landing_citation_pdf_probe(landing_url)
    if context is not None:
        cached = context.get_session_cache(cache_key, default=_CACHE_MISSING)
        if cached is not _CACHE_MISSING:
            return cast(LandingPageCitationPdfProbeResult, cached)
    result = _landing_page_citation_pdf_probe(
        landing_url,
        transport=transport,
        env=env,
    )
    if result and context is not None:
        context.set_session_cache(cache_key, result)
    return result


def get_cached_landing_page_citation_pdf_probe(
    landing_url: str | None,
    *,
    context: RuntimeContext | None,
) -> LandingPageCitationPdfProbeResult | None:
    if context is None or not landing_url:
        return None
    cached = context.get_session_cache(
        _session_cache_key_landing_citation_pdf_probe(landing_url),
        default=_CACHE_MISSING,
    )
    if cached is _CACHE_MISSING:
        return None
    return cast(LandingPageCitationPdfProbeResult, cached)


def probe_official_provider(
    provider_name: str,
    *,
    doi: str,
    clients: Mapping[str, object],
    context: RuntimeContext | None = None,
) -> RouteProbeResult:
    if provider_name != "elsevier":
        return RouteProbeResult(provider=provider_name, state="unknown")
    if not isinstance(clients.get(provider_name), MetadataProvider):
        return RouteProbeResult(provider=provider_name, state="unknown")
    try:
        metadata = fetch_provider_metadata_probe_with_session_cache(
            provider_name,
            doi,
            clients=clients,
            context=context,
        )
    except ProviderFailure as exc:
        return RouteProbeResult(provider=provider_name, state=classify_probe_state(exc))
    if metadata:
        return RouteProbeResult(provider=provider_name, state="positive", metadata=dict(metadata))
    return RouteProbeResult(provider=provider_name, state="negative")


def select_route_probe(probes: list[RouteProbeResult]) -> RouteProbeResult | None:
    for state in ("positive", "unknown", "negative"):
        for probe in probes:
            if probe.state == state:
                return probe
    return None


def probe_has_fulltext(
    query: str,
    *,
    transport: HttpTransport | None | object = RUNTIME_UNSET,
    env: Mapping[str, str] | None | object = RUNTIME_UNSET,
    clients: Mapping[str, object] | None | object = RUNTIME_UNSET,
    context: RuntimeContext | None = None,
    resolve_paper_fn=None,
) -> HasFulltextProbeResult:
    runtime = resolve_runtime_context(context, env=env, transport=transport, clients=clients)
    assert runtime.env is not None
    assert runtime.transport is not None
    active_env = runtime.env
    active_transport = runtime.transport
    client_registry = dict(runtime.get_clients())
    resolver = resolve_paper_fn or resolve_paper
    resolved = resolve_query_with_session_cache(
        query,
        resolver=resolver,
        transport=active_transport,
        env=active_env,
        context=runtime,
    )
    if resolved.candidates and not resolved.doi:
        raise PaperFetchFailure(
            "ambiguous",
            "Query resolution is ambiguous; choose one of the DOI candidates.",
            candidates=resolved.candidates,
        )

    warnings: list[str] = []
    evidence: list[str] = []
    title = normalize_text(resolved.title)
    doi = normalize_doi(safe_text(resolved.doi)) or None
    crossref_metadata: ProviderMetadata | None = None
    crossref_client = client_registry.get("crossref")

    strategy = FetchStrategy()
    initial_elsevier_probe = False
    if doi:
        initial_elsevier_probe = any(
            provider_name == "elsevier"
            for provider_name, _signal in build_official_provider_candidates(
                resolved,
                routing_metadata=None,
                strategy=strategy,
            )
        )

    def fetch_crossref_metadata() -> ProviderMetadata | None:
        return fetch_crossref_metadata_with_session_cache(doi, crossref_client, context=runtime)

    def fetch_elsevier_metadata() -> ProviderMetadata | None:
        return fetch_provider_metadata_probe_with_session_cache(
            "elsevier",
            doi,
            clients=client_registry,
            context=runtime,
        )

    def fetch_landing_probe(landing_url: str) -> LandingPageCitationPdfProbeResult:
        return landing_page_citation_pdf_probe_with_session_cache(
            landing_url,
            transport=active_transport,
            env=active_env,
            context=runtime,
        )

    landing_probe_by_url: dict[str, LandingPageCitationPdfProbeResult] = {}
    landing_probe_errors: dict[str, RequestFailure] = {}
    elsevier_metadata: ProviderMetadata | None = None
    elsevier_error: ProviderFailure | None = None
    crossref_error: ProviderFailure | None = None
    initial_landing_url = choose_public_landing_page_url(resolved.landing_url)

    with ThreadPoolExecutor(max_workers=3) as executor:
        crossref_future = executor.submit(fetch_crossref_metadata) if doi and isinstance(crossref_client, MetadataProvider) else None
        elsevier_future = executor.submit(fetch_elsevier_metadata) if initial_elsevier_probe else None
        landing_future = executor.submit(fetch_landing_probe, initial_landing_url) if initial_landing_url else None

        if crossref_future is not None:
            try:
                crossref_metadata = crossref_future.result()
            except ProviderFailure as exc:
                crossref_error = exc
        if elsevier_future is not None:
            try:
                elsevier_metadata = elsevier_future.result()
            except ProviderFailure as exc:
                elsevier_error = exc
        if landing_future is not None and initial_landing_url:
            try:
                landing_probe_by_url[initial_landing_url] = landing_future.result()
            except RequestFailure as exc:
                landing_probe_errors[initial_landing_url] = exc

    if crossref_metadata:
        title = normalize_text(crossref_metadata.get("title")) or title
        if crossref_metadata.get("license_urls"):
            extend_unique(evidence, ["crossref_license"])
        if crossref_metadata.get("fulltext_links"):
            extend_unique(evidence, ["crossref_fulltext_link"])
    elif crossref_error is not None and _is_unknown_has_fulltext_probe_failure(crossref_error):
        extend_unique(warnings, [_probe_warning("Crossref metadata probe unavailable", crossref_error.message)])

    needs_elsevier_probe = False
    if doi and elsevier_metadata is None and elsevier_error is None:
        needs_elsevier_probe = any(
            provider_name == "elsevier"
            for provider_name, _signal in build_official_provider_candidates(
                resolved,
                routing_metadata=crossref_metadata,
                strategy=strategy,
            )
        )
    if needs_elsevier_probe:
        try:
            elsevier_metadata = fetch_elsevier_metadata()
        except ProviderFailure as exc:
            elsevier_error = exc
    if elsevier_metadata:
        extend_unique(evidence, ["provider_probe:elsevier"])
        title = normalize_text((elsevier_metadata or {}).get("title")) or title
    elif elsevier_error is not None and _is_unknown_has_fulltext_probe_failure(elsevier_error):
        extend_unique(warnings, [_probe_warning("elsevier metadata probe unavailable", elsevier_error.message)])

    landing_url = choose_public_landing_page_url(
        resolved.landing_url,
        (crossref_metadata or {}).get("landing_page_url"),
    )
    if landing_url:
        if landing_url not in landing_probe_by_url and landing_url not in landing_probe_errors:
            try:
                landing_probe_by_url[landing_url] = fetch_landing_probe(landing_url)
            except RequestFailure as exc:
                landing_probe_errors[landing_url] = exc
        if landing_url in landing_probe_by_url:
            landing_probe = landing_probe_by_url[landing_url]
            if landing_probe.has_citation_pdf_url:
                extend_unique(evidence, ["landing_page_citation_pdf_url"])
            title = landing_probe.title or title
        elif landing_url in landing_probe_errors:
            extend_unique(warnings, [_probe_warning("Landing-page metadata probe unavailable", str(landing_probe_errors[landing_url]))])

    state = "likely_yes" if evidence else "unknown"
    return HasFulltextProbeResult(
        query=resolved.query,
        doi=doi,
        title=title,
        state=state,
        evidence=evidence,
        warnings=warnings,
    )
