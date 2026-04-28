"""Metadata fetching and merge stage."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Mapping, cast

from ..metadata_types import ProviderMetadata
from ..providers.base import ProviderFailure
from ..providers.protocols import MetadataProvider
from ..runtime import RuntimeContext
from ..utils import choose_public_landing_page_url, dedupe_authors, extend_unique, normalize_text, safe_text
from .routing import (
    build_official_provider_candidates,
    crossref_allowed_as_source,
    fetch_crossref_metadata_with_session_cache,
    get_cached_landing_page_citation_pdf_probe,
    provider_allowed,
    probe_official_provider,
    route_signal_markers,
    select_route_probe,
)
from .shared import source_trail_for_failure
from .types import FetchStrategy


def merge_primary_secondary_metadata(
    primary: Mapping[str, Any] | None,
    secondary: Mapping[str, Any] | None,
) -> ProviderMetadata:
    merged = dict(secondary or {})
    merged.update(primary or {})
    scalar_keys = ("doi", "title", "journal_title", "published", "abstract", "publisher")

    def scalarize(value: Any, *, preserve_blank: bool = False) -> str | None:
        if isinstance(value, str):
            normalized = normalize_text(value)
            if normalized:
                return normalized
            return "" if preserve_blank else None
        if isinstance(value, list):
            for item in value:
                scalar = scalarize(item, preserve_blank=preserve_blank)
                if scalar is not None:
                    return scalar
            return "" if preserve_blank and value else None
        if isinstance(value, Mapping):
            for key in ("value", "url", "URL"):
                scalar = scalarize(value.get(key), preserve_blank=preserve_blank)
                if scalar is not None:
                    return scalar
            return "" if preserve_blank and value else None
        if value is None:
            return None
        normalized = safe_text(value)
        if normalized:
            return normalized
        return "" if preserve_blank else None

    for key in scalar_keys:
        primary_has_value = primary is not None and key in primary and primary.get(key) is not None
        if primary_has_value:
            merged[key] = scalarize(primary.get(key), preserve_blank=True)
        else:
            merged[key] = scalarize((secondary or {}).get(key))
    merged["landing_page_url"] = choose_public_landing_page_url(
        (primary or {}).get("landing_page_url"),
        (secondary or {}).get("landing_page_url"),
    )

    def merged_list(key: str, *, semantic: bool = False) -> list[Any]:
        result: list[Any] = []
        for item in list((primary or {}).get(key) or []) + list((secondary or {}).get(key) or []):
            normalized_item = normalize_text(item) if isinstance(item, str) else item
            if normalized_item and normalized_item not in result:
                result.append(normalized_item)
        if semantic:
            return dedupe_authors([str(item) for item in result])
        return result

    merged["authors"] = merged_list("authors", semantic=True)
    merged["keywords"] = merged_list("keywords")
    merged["license_urls"] = merged_list("license_urls")
    merged["fulltext_links"] = merged_list("fulltext_links")
    merged["references"] = merged_list("references")
    for key in scalar_keys:
        if merged.get(key) == "":
            merged[key] = None
    return cast(ProviderMetadata, merged)


def metadata_from_resolution(resolved) -> ProviderMetadata:
    return {
        "doi": resolved.doi,
        "title": resolved.title,
        "journal_title": None,
        "published": None,
        "landing_page_url": resolved.landing_url,
        "authors": [],
        "keywords": [],
        "license_urls": [],
        "references": [],
        "fulltext_links": [],
    }


def _citation_pdf_link(url: str) -> dict[str, Any]:
    return {
        "url": url,
        "content_type": "application/pdf",
        "content_version": None,
        "intended_application": "full_text",
    }


def _merge_cached_landing_probe_links(
    metadata: ProviderMetadata,
    resolved,
    *,
    context: RuntimeContext | None,
) -> ProviderMetadata:
    if context is None:
        return metadata
    landing_urls = [
        choose_public_landing_page_url(resolved.landing_url),
        choose_public_landing_page_url(safe_text(metadata.get("landing_page_url"))),
    ]
    citation_pdf_urls: list[str] = []
    for landing_url in landing_urls:
        probe = get_cached_landing_page_citation_pdf_probe(landing_url, context=context)
        if probe is None:
            continue
        extend_unique(citation_pdf_urls, probe.citation_pdf_urls)
    if not citation_pdf_urls:
        return metadata

    merged = dict(metadata)
    fulltext_links = list(merged.get("fulltext_links") or [])
    seen_urls = {
        normalize_text(item.get("url"))
        for item in fulltext_links
        if isinstance(item, Mapping) and normalize_text(item.get("url"))
    }
    for url in citation_pdf_urls:
        normalized_url = normalize_text(url)
        if normalized_url and normalized_url not in seen_urls:
            seen_urls.add(normalized_url)
            fulltext_links.append(_citation_pdf_link(normalized_url))
    merged["fulltext_links"] = fulltext_links
    return cast(ProviderMetadata, merged)


def fetch_metadata_for_resolved_query(
    resolved,
    *,
    clients: Mapping[str, object],
    strategy: FetchStrategy,
    context: RuntimeContext | None = None,
) -> tuple[ProviderMetadata, str | None, list[str]]:
    official_metadata: ProviderMetadata | None = None
    crossref_metadata: ProviderMetadata | None = None
    source_trail: list[str] = []
    provider_name: str | None = None
    routing_metadata: ProviderMetadata | None = None
    crossref_is_public_source = crossref_allowed_as_source(strategy)
    crossref_client = clients.get("crossref")

    initial_probe_candidates = (
        build_official_provider_candidates(resolved, routing_metadata=None, strategy=strategy)
        if resolved.doi
        else []
    )
    crossref_result: ProviderMetadata | None = None
    crossref_failure: ProviderFailure | None = None
    initial_probe_results: dict[str, Any] = {}

    def fetch_crossref_metadata() -> ProviderMetadata | None:
        return fetch_crossref_metadata_with_session_cache(
            resolved.doi,
            crossref_client,
            context=context,
        )

    def run_probe(candidate_provider: str):
        assert resolved.doi is not None
        return probe_official_provider(candidate_provider, doi=resolved.doi, clients=clients, context=context)

    if resolved.doi and (isinstance(crossref_client, MetadataProvider) or initial_probe_candidates):
        max_workers = 1 + len(initial_probe_candidates)
        with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
            crossref_future = (
                executor.submit(fetch_crossref_metadata)
                if isinstance(crossref_client, MetadataProvider)
                else None
            )
            probe_futures = {
                candidate_provider: executor.submit(run_probe, candidate_provider)
                for candidate_provider, _signal in initial_probe_candidates
            }
            if crossref_future is not None:
                try:
                    crossref_result = crossref_future.result()
                except ProviderFailure as exc:
                    crossref_failure = exc
            for candidate_provider, future in probe_futures.items():
                initial_probe_results[candidate_provider] = future.result()

    if crossref_result:
        routing_metadata = crossref_result
        crossref_metadata = routing_metadata
        if crossref_is_public_source:
            source_trail.append("metadata:crossref_ok")
        else:
            source_trail.append("route:crossref_signal_ok")
    elif crossref_failure is not None and crossref_is_public_source:
        source_trail.append(source_trail_for_failure("metadata", "crossref", crossref_failure))

    extend_unique(
        source_trail,
        route_signal_markers(
            landing_urls=[
                resolved.landing_url,
                safe_text((routing_metadata or {}).get("landing_page_url")),
            ],
            publishers=[safe_text((routing_metadata or {}).get("publisher"))],
            doi=resolved.doi,
        ),
    )

    probes = []
    if resolved.doi:
        for candidate_provider, _signal in build_official_provider_candidates(
            resolved,
            routing_metadata=routing_metadata,
            strategy=strategy,
        ):
            probe = initial_probe_results.get(candidate_provider)
            if probe is None:
                probe = probe_official_provider(candidate_provider, doi=resolved.doi, clients=clients, context=context)
            probes.append(probe)
            source_trail.append(f"route:probe_{candidate_provider}_{probe.state}")
            if probe.state == "positive":
                break

    selected_probe = select_route_probe(probes)
    if selected_probe is not None:
        provider_name = selected_probe.provider
        official_metadata = selected_probe.metadata
        source_trail.append(f"route:provider_selected_{provider_name}")
    elif crossref_metadata:
        provider_name = "crossref"
    elif resolved.provider_hint and provider_allowed(resolved.provider_hint, strategy):
        provider_name = resolved.provider_hint
        source_trail.append(f"route:provider_selected_{provider_name}")

    if official_metadata or crossref_metadata:
        if official_metadata:
            source_trail.append(f"metadata:{provider_name}_ok")
        metadata = merge_primary_secondary_metadata(official_metadata, crossref_metadata)
        metadata["provider"] = (official_metadata or crossref_metadata or {}).get("provider")
        metadata["official_provider"] = (official_metadata or crossref_metadata or {}).get("official_provider")
        if not metadata.get("landing_page_url"):
            metadata["landing_page_url"] = resolved.landing_url
        metadata = _merge_cached_landing_probe_links(metadata, resolved, context=context)
        return metadata, provider_name, source_trail

    source_trail.append("metadata:resolution_only")
    metadata = _merge_cached_landing_probe_links(metadata_from_resolution(resolved), resolved, context=context)
    return metadata, provider_name, source_trail
