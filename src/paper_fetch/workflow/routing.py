"""Routing and probe logic for provider selection."""

from __future__ import annotations

from typing import Any, Mapping, cast

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
) -> tuple[bool, str | None]:
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
    has_citation_pdf_url = any(normalize_text(item) for item in (citation_pdf_values or []))
    return has_citation_pdf_url, normalize_text(html_metadata.get("title"))


def probe_official_provider(
    provider_name: str,
    *,
    doi: str,
    clients: Mapping[str, object],
) -> RouteProbeResult:
    if provider_name != "elsevier":
        return RouteProbeResult(provider=provider_name, state="unknown")
    client = clients.get(provider_name)
    if not isinstance(client, MetadataProvider):
        return RouteProbeResult(provider=provider_name, state="unknown")
    try:
        metadata = client.fetch_metadata({"doi": doi})
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
    resolved = resolver(query, transport=active_transport, env=active_env)
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

    if doi and isinstance(crossref_client, MetadataProvider):
        try:
            crossref_metadata = cast(ProviderMetadata, dict(crossref_client.fetch_metadata({"doi": doi})))
            title = normalize_text(crossref_metadata.get("title")) or title
            if crossref_metadata.get("license_urls"):
                extend_unique(evidence, ["crossref_license"])
            if crossref_metadata.get("fulltext_links"):
                extend_unique(evidence, ["crossref_fulltext_link"])
        except ProviderFailure as exc:
            if _is_unknown_has_fulltext_probe_failure(exc):
                extend_unique(warnings, [_probe_warning("Crossref metadata probe unavailable", exc.message)])

    if doi:
        strategy = FetchStrategy()
        for provider_name, _signal in build_official_provider_candidates(
            resolved,
            routing_metadata=crossref_metadata,
            strategy=strategy,
        ):
            if provider_name != "elsevier":
                continue
            client = client_registry.get(provider_name)
            if not isinstance(client, MetadataProvider):
                continue
            try:
                metadata = client.fetch_metadata({"doi": doi})
                if metadata:
                    extend_unique(evidence, [f"provider_probe:{provider_name}"])
                    title = normalize_text((metadata or {}).get("title")) or title
                    break
            except ProviderFailure as exc:
                if _is_unknown_has_fulltext_probe_failure(exc):
                    extend_unique(warnings, [_probe_warning(f"{provider_name} metadata probe unavailable", exc.message)])

    landing_url = choose_public_landing_page_url(
        resolved.landing_url,
        (crossref_metadata or {}).get("landing_page_url"),
    )
    if landing_url:
        try:
            has_citation_pdf_url, landing_title = _landing_page_citation_pdf_probe(
                landing_url,
                transport=active_transport,
                env=active_env,
            )
            if has_citation_pdf_url:
                extend_unique(evidence, ["landing_page_citation_pdf_url"])
            title = landing_title or title
        except RequestFailure as exc:
            extend_unique(warnings, [_probe_warning("Landing-page metadata probe unavailable", str(exc))])

    state = "likely_yes" if evidence else "unknown"
    return HasFulltextProbeResult(
        query=resolved.query,
        doi=doi,
        title=title,
        state=state,
        evidence=evidence,
        warnings=warnings,
    )
