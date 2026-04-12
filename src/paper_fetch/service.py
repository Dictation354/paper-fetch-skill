"""Service-layer orchestration for paper fetch."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import time
from typing import Any, Mapping, cast

from .config import build_runtime_env
from .http import HttpTransport, RequestFailure
from .metadata_types import ProviderMetadata
from .utils import (
    build_output_path,
    choose_public_landing_page_url,
    dedupe_authors,
    empty_asset_results,
    extend_unique,
    normalize_text,
    safe_text,
    save_payload,
)
from .models import (
    ArticleModel,
    AssetProfile,
    FetchEnvelope,
    OutputMode,
    RenderOptions,
    metadata_only_article,
)
from .providers.base import ProviderFailure
from .providers.html_generic import HtmlGenericClient
from .providers.registry import build_clients
from .publisher_identity import (
    infer_provider_from_doi,
    infer_provider_from_publisher,
    infer_provider_from_url,
    normalize_doi,
    ordered_provider_candidates,
)
from .resolve.query import ResolvedQuery, resolve_query

DEFAULT_OUTPUT_MODES: set[OutputMode] = {"article", "markdown"}
OFFICIAL_PROVIDER_NAMES = ("elsevier", "springer", "wiley")
PUBLIC_SOURCE_BY_ARTICLE_SOURCE = {
    "elsevier_xml": "elsevier_xml",
    "springer_xml": "springer_xml",
    "wiley": "wiley_tdm",
    "html_generic": "html_fallback",
    "crossref_meta": "crossref_meta",
}
HTML_PROVIDER_ALIASES = {"html", "html_generic", "html_fallback"}
logger = logging.getLogger("paper_fetch.service")


class PaperFetchFailure(Exception):
    def __init__(self, status: str, reason: str, *, candidates: list[dict[str, Any]] | None = None) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason
        self.candidates = list(candidates or [])


@dataclass(frozen=True)
class RouteProbeResult:
    provider: str
    state: str
    metadata: ProviderMetadata | None = None


@dataclass(frozen=True)
class FetchStrategy:
    allow_html_fallback: bool = True
    allow_metadata_only_fallback: bool = True
    preferred_providers: list[str] | None = None
    asset_profile: AssetProfile = "none"

    def normalized_preferred_providers(self) -> set[str] | None:
        if self.preferred_providers is None:
            return None
        normalized = {normalize_text(item).lower() for item in self.preferred_providers if normalize_text(item)}
        return normalized or set()
def source_trail_for_failure(stage: str, provider_name: str, failure: ProviderFailure) -> str:
    if failure.code == "not_configured":
        suffix = "not_configured"
    elif failure.code == "rate_limited":
        suffix = "rate_limited"
    else:
        suffix = "fail"
    return f"{stage}:{provider_name}_{suffix}"


def finalize_article(article: ArticleModel, *, warnings: list[str] | None = None, source_trail: list[str] | None = None) -> ArticleModel:
    extend_unique(article.quality.warnings, list(warnings or []))
    extend_unique(article.quality.source_trail, list(source_trail or []))
    return article


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
            normalized_item = item
            if isinstance(item, str):
                normalized_item = normalize_text(item)
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


def metadata_from_resolution(resolved: ResolvedQuery) -> ProviderMetadata:
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


def provider_allowed(provider_name: str | None, strategy: FetchStrategy) -> bool:
    normalized = strategy.normalized_preferred_providers()
    if normalized is None:
        return True
    if provider_name is None:
        return False
    return normalize_text(provider_name).lower() in normalized


def html_fallback_allowed(strategy: FetchStrategy) -> bool:
    if not strategy.allow_html_fallback:
        return False
    normalized = strategy.normalized_preferred_providers()
    if normalized is None:
        return True
    return any(alias in normalized for alias in HTML_PROVIDER_ALIASES)


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
    resolved: ResolvedQuery,
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


def probe_official_provider(
    provider_name: str,
    *,
    doi: str,
    clients: Mapping[str, Any],
) -> RouteProbeResult:
    if provider_name == "wiley":
        return RouteProbeResult(provider=provider_name, state="unknown")

    client = clients.get(provider_name)
    if client is None:
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


def fetch_metadata_for_resolved_query(
    resolved: ResolvedQuery,
    *,
    clients: Mapping[str, Any],
    strategy: FetchStrategy,
) -> tuple[ProviderMetadata, str | None, list[str]]:
    official_metadata: ProviderMetadata | None = None
    crossref_metadata: ProviderMetadata | None = None
    source_trail: list[str] = []
    provider_name: str | None = None
    routing_metadata: ProviderMetadata | None = None
    crossref_is_public_source = crossref_allowed_as_source(strategy)
    crossref_client = clients.get("crossref")

    if resolved.doi and crossref_client is not None:
        try:
            routing_metadata = dict(crossref_client.fetch_metadata({"doi": resolved.doi}))
            if routing_metadata:
                crossref_metadata = routing_metadata
                if crossref_is_public_source:
                    source_trail.append("metadata:crossref_ok")
                else:
                    source_trail.append("route:crossref_signal_ok")
        except ProviderFailure as exc:
            routing_metadata = None
            if crossref_is_public_source:
                source_trail.append(source_trail_for_failure("metadata", "crossref", exc))

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

    probes: list[RouteProbeResult] = []
    if resolved.doi:
        for candidate_provider, _signal in build_official_provider_candidates(
            resolved,
            routing_metadata=routing_metadata,
            strategy=strategy,
        ):
            probe = probe_official_provider(candidate_provider, doi=resolved.doi, clients=clients)
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

    if official_metadata or crossref_metadata:
        if official_metadata:
            source_trail.append(f"metadata:{provider_name}_ok")
        metadata = merge_primary_secondary_metadata(official_metadata, crossref_metadata)
        metadata["provider"] = (official_metadata or crossref_metadata or {}).get("provider")
        metadata["official_provider"] = (official_metadata or crossref_metadata or {}).get("official_provider")
        if not metadata.get("landing_page_url"):
            metadata["landing_page_url"] = resolved.landing_url
        return metadata, provider_name, source_trail

    source_trail.append("metadata:resolution_only")
    return metadata_from_resolution(resolved), provider_name, source_trail


def build_metadata_only_result(
    metadata: Mapping[str, Any],
    *,
    resolved: ResolvedQuery,
    warnings: list[str] | None = None,
    source_trail: list[str] | None = None,
) -> ArticleModel:
    return metadata_only_article(
        source="crossref_meta",
        metadata=metadata,
        doi=normalize_doi(safe_text(metadata.get("doi") or resolved.doi)) or None,
        warnings=list(warnings or []),
        source_trail=list(source_trail or []),
    )


def maybe_save_provider_payload(
    raw_payload: Any,
    *,
    download_dir: Path | None,
    doi: str | None,
    metadata: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    if not raw_payload.needs_local_copy:
        return [], []
    provider_slug = safe_text(raw_payload.provider or "provider").lower().replace(" ", "_") or "provider"
    provider_label = provider_slug.replace("_", " ").title()
    if download_dir is None:
        return [f"{provider_label} official PDF/binary was not written to disk because --no-download was set."], [
            f"download:{provider_slug}_skipped"
        ]

    saved_path = save_payload(
        build_output_path(
            download_dir,
            doi,
            safe_text(metadata.get("title")),
            raw_payload.content_type,
            raw_payload.source_url,
        ),
        raw_payload.body,
    )
    if saved_path:
        return [f"{provider_label} official full text was downloaded as PDF/binary to {saved_path}."], [
            f"download:{provider_slug}_saved"
        ]
    return [f"{provider_label} official full text was available only as PDF/binary and could not be written to disk."], [
        f"download:{provider_slug}_save_failed"
    ]


def maybe_download_provider_assets(
    provider_client: Any,
    *,
    provider_name: str,
    raw_payload: Any,
    download_dir: Path | None,
    doi: str,
    metadata: Mapping[str, Any],
    asset_profile: AssetProfile,
) -> tuple[dict[str, list[dict[str, Any]]], list[str], list[str]]:
    if download_dir is None:
        return empty_asset_results(), [], []
    if asset_profile == "none":
        return empty_asset_results(), [], [f"download:{provider_name}_assets_skipped_profile_none"]

    provider_label = safe_text(provider_name).replace("_", " ").title() or "Provider"
    try:
        asset_results = provider_client.download_related_assets(
            doi,
            metadata,
            raw_payload,
            download_dir,
            asset_profile=asset_profile,
        )
    except ProviderFailure as exc:
        return empty_asset_results(), [f"{provider_label} related assets could not be downloaded: {exc.message}"], [
            f"download:{provider_name}_assets_failed"
        ]
    except (RequestFailure, OSError) as exc:
        return empty_asset_results(), [f"{provider_label} related assets could not be downloaded: {exc}"], [
            f"download:{provider_name}_assets_failed"
        ]

    assets = list(asset_results.get("assets") or [])
    failures = list(asset_results.get("asset_failures") or [])
    warnings: list[str] = []
    source_trail: list[str] = []
    if assets:
        source_trail.append(f"download:{provider_name}_assets_saved_profile_{asset_profile}")
    if failures:
        warnings.append(f"{provider_label} related assets were only partially downloaded ({len(failures)} failed).")
        source_trail.append(f"download:{provider_name}_asset_failures")
    return {
        "assets": assets,
        "asset_failures": failures,
    }, warnings, source_trail


def _try_official_provider(
    *,
    doi: str | None,
    metadata: Mapping[str, Any],
    provider_name: str | None,
    strategy: FetchStrategy,
    download_dir: Path | None,
    clients: Mapping[str, Any],
    warnings: list[str],
    source_trail: list[str],
) -> ArticleModel | None:
    if not doi or not provider_name or provider_name == "crossref":
        return None
    if not provider_allowed(provider_name, strategy):
        extend_unique(source_trail, [f"fulltext:{provider_name}_skipped"])
        return None

    provider_client = clients.get(provider_name)
    if provider_client is None:
        return None

    extend_unique(source_trail, [f"fulltext:{provider_name}_attempt"])
    attempt_started_at = time.monotonic()
    logger.debug(
        "official_provider_attempt provider=%s url=%s status=%s elapsed_ms=%s attempt=%s",
        provider_name,
        safe_text(metadata.get("landing_page_url")) or None,
        "attempt",
        0.0,
        1,
    )
    try:
        raw_payload = provider_client.fetch_raw_fulltext(doi, metadata)
        extend_unique(source_trail, [f"fulltext:{provider_name}_raw_ok"])
        download_warnings, download_trail = maybe_save_provider_payload(
            raw_payload,
            download_dir=download_dir,
            doi=doi,
            metadata=metadata,
        )
        extend_unique(warnings, download_warnings)
        extend_unique(source_trail, download_trail)
        asset_results, asset_warnings, asset_trail = maybe_download_provider_assets(
            provider_client,
            provider_name=provider_name,
            raw_payload=raw_payload,
            download_dir=download_dir,
            doi=doi,
            metadata=metadata,
            asset_profile=strategy.asset_profile,
        )
        downloaded_assets = list(asset_results.get("assets") or [])
        asset_failures = list(asset_results.get("asset_failures") or [])
        extend_unique(warnings, asset_warnings)
        extend_unique(source_trail, asset_trail)
        article = provider_client.to_article_model(
            metadata,
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
        )
        extend_unique(source_trail, article.quality.source_trail)
        if article.quality.has_fulltext and article.sections:
            logger.debug(
                "official_provider_result provider=%s url=%s status=%s elapsed_ms=%s attempt=%s",
                provider_name,
                raw_payload.source_url,
                "success",
                round((time.monotonic() - attempt_started_at) * 1000, 3),
                1,
            )
            extend_unique(source_trail, [f"fulltext:{provider_name}_article_ok"])
            return finalize_article(article, warnings=warnings, source_trail=source_trail)
        if article.quality.has_fulltext and not article.sections:
            logger.debug(
                "official_provider_result provider=%s url=%s status=%s elapsed_ms=%s attempt=%s",
                provider_name,
                raw_payload.source_url,
                "abstract_only",
                round((time.monotonic() - attempt_started_at) * 1000, 3),
                1,
            )
            warnings.append("Official full text only contained abstract-level content; continuing to HTML fallback.")
            extend_unique(source_trail, [f"fulltext:{provider_name}_abstract_only"])
        else:
            logger.debug(
                "official_provider_result provider=%s url=%s status=%s elapsed_ms=%s attempt=%s",
                provider_name,
                raw_payload.source_url,
                "not_usable",
                round((time.monotonic() - attempt_started_at) * 1000, 3),
                1,
            )
            extend_unique(source_trail, [f"fulltext:{provider_name}_not_usable"])
        extend_unique(warnings, article.quality.warnings)
    except ProviderFailure as exc:
        logger.debug(
            "official_provider_result provider=%s url=%s status=%s elapsed_ms=%s attempt=%s",
            provider_name,
            safe_text(metadata.get("landing_page_url")) or None,
            exc.code,
            round((time.monotonic() - attempt_started_at) * 1000, 3),
            1,
        )
        warnings.append(exc.message)
        extend_unique(source_trail, [source_trail_for_failure("fulltext", provider_name, exc)])
    return None


def _try_html_fallback(
    *,
    landing_url: str | None,
    doi: str | None,
    metadata: Mapping[str, Any],
    strategy: FetchStrategy,
    download_dir: Path | None,
    html_client: HtmlGenericClient,
    warnings: list[str],
    source_trail: list[str],
) -> ArticleModel | None:
    if not html_fallback_allowed(strategy):
        extend_unique(source_trail, ["fallback:html_disabled"])
        return None
    if not landing_url:
        extend_unique(source_trail, ["fallback:html_unavailable"])
        return None

    extend_unique(source_trail, ["fallback:html_attempt"])
    attempt_started_at = time.monotonic()
    logger.debug(
        "html_fallback_attempt provider=%s url=%s status=%s elapsed_ms=%s attempt=%s",
        "html_generic",
        landing_url,
        "attempt",
        0.0,
        1,
    )
    try:
        article = html_client.fetch_article_model(
            landing_url,
            metadata=metadata,
            expected_doi=doi,
            download_dir=download_dir,
            asset_profile=strategy.asset_profile,
        )
        if article.quality.has_fulltext:
            logger.debug(
                "html_fallback_result provider=%s url=%s status=%s elapsed_ms=%s attempt=%s",
                "html_generic",
                landing_url,
                "success",
                round((time.monotonic() - attempt_started_at) * 1000, 3),
                1,
            )
            extend_unique(source_trail, article.quality.source_trail)
            extend_unique(source_trail, ["fallback:html_ok"])
            return finalize_article(article, warnings=warnings, source_trail=source_trail)
        logger.debug(
            "html_fallback_result provider=%s url=%s status=%s elapsed_ms=%s attempt=%s",
            "html_generic",
            landing_url,
            "not_usable",
            round((time.monotonic() - attempt_started_at) * 1000, 3),
            1,
        )
        extend_unique(warnings, article.quality.warnings)
        extend_unique(source_trail, article.quality.source_trail)
        extend_unique(source_trail, ["fallback:html_not_usable"])
    except ProviderFailure as exc:
        logger.debug(
            "html_fallback_result provider=%s url=%s status=%s elapsed_ms=%s attempt=%s",
            "html_generic",
            landing_url,
            exc.code,
            round((time.monotonic() - attempt_started_at) * 1000, 3),
            1,
        )
        warnings.append(exc.message)
        extend_unique(source_trail, ["fallback:html_fail"])
    return None


def _fallback_to_metadata_only(
    *,
    metadata: Mapping[str, Any],
    resolved: ResolvedQuery,
    strategy: FetchStrategy,
    warnings: list[str],
    source_trail: list[str],
) -> ArticleModel:
    if not metadata:
        raise PaperFetchFailure("error", "Unable to resolve metadata or full text for the requested paper.")
    if not strategy.allow_metadata_only_fallback:
        raise PaperFetchFailure("error", "Full text was not available and metadata-only fallback is disabled.")
    warnings.append("Full text was not available; returning metadata and abstract only.")
    extend_unique(source_trail, ["fallback:metadata_only"])
    return build_metadata_only_result(metadata, resolved=resolved, warnings=warnings, source_trail=source_trail)


def _fetch_article(
    query: str,
    *,
    strategy: FetchStrategy,
    download_dir: Path | None,
    clients: Mapping[str, Any] | None = None,
    html_client: HtmlGenericClient | None = None,
    transport: HttpTransport | None = None,
    env: Mapping[str, str] | None = None,
) -> ArticleModel:
    active_env = env or build_runtime_env()
    active_transport = transport or HttpTransport()
    client_registry = dict(clients or build_clients(active_transport, active_env))
    resolved = resolve_paper(query, transport=active_transport, env=active_env)
    source_trail: list[str] = [f"resolve:{resolved.query_kind}"]
    if resolved.doi:
        source_trail.append("resolve:doi_selected")
    if resolved.candidates and not resolved.doi:
        raise PaperFetchFailure(
            "ambiguous",
            "Query resolution is ambiguous; choose one of the DOI candidates.",
            candidates=resolved.candidates,
        )

    metadata, provider_name, metadata_trail = fetch_metadata_for_resolved_query(resolved, clients=client_registry, strategy=strategy)
    extend_unique(source_trail, metadata_trail)
    landing_url = choose_public_landing_page_url(
        resolved.landing_url,
        metadata.get("landing_page_url"),
    )
    doi = normalize_doi(safe_text(metadata.get("doi") or resolved.doi)) or None
    html_fallback_client = html_client or HtmlGenericClient(active_transport, active_env)
    warnings: list[str] = []

    article = _try_official_provider(
        doi=doi,
        metadata=metadata,
        provider_name=provider_name,
        strategy=strategy,
        download_dir=download_dir,
        clients=client_registry,
        warnings=warnings,
        source_trail=source_trail,
    )
    if article is not None:
        return article

    article = _try_html_fallback(
        landing_url=landing_url,
        doi=doi,
        metadata=metadata,
        strategy=strategy,
        download_dir=download_dir,
        html_client=html_fallback_client,
        warnings=warnings,
        source_trail=source_trail,
    )
    if article is not None:
        return article

    return _fallback_to_metadata_only(
        metadata=metadata,
        resolved=resolved,
        strategy=strategy,
        warnings=warnings,
        source_trail=source_trail,
    )

def public_source_for_article(article: ArticleModel) -> str:
    if "fallback:metadata_only" in article.quality.source_trail:
        return "metadata_only"
    return PUBLIC_SOURCE_BY_ARTICLE_SOURCE.get(article.source, article.source)


def build_fetch_envelope(
    article: ArticleModel,
    *,
    modes: set[OutputMode],
    render: RenderOptions,
) -> FetchEnvelope:
    effective_asset_profile = render.asset_profile or "none"
    markdown = (
        article.to_ai_markdown(
            include_refs=render.include_refs,
            asset_profile=effective_asset_profile,
            max_tokens=render.max_tokens,
        )
        if "markdown" in modes
        else None
    )
    metadata = article.metadata if "metadata" in modes else None
    return FetchEnvelope(
        doi=article.doi,
        source=public_source_for_article(article),
        has_fulltext=article.quality.has_fulltext,
        warnings=list(article.quality.warnings),
        source_trail=list(article.quality.source_trail),
        token_estimate=article.quality.token_estimate,
        article=article if "article" in modes else None,
        markdown=markdown,
        metadata=metadata,
    )


def resolve_paper(
    query: str,
    *,
    transport: HttpTransport | None = None,
    env: Mapping[str, str] | None = None,
) -> ResolvedQuery:
    return resolve_query(query, transport=transport, env=env)


def fetch_paper(
    query: str,
    *,
    modes: set[OutputMode] | None = None,
    strategy: FetchStrategy | None = None,
    render: RenderOptions | None = None,
    download_dir: Path | None = None,
    clients: Mapping[str, Any] | None = None,
    html_client: HtmlGenericClient | None = None,
    transport: HttpTransport | None = None,
    env: Mapping[str, str] | None = None,
) -> FetchEnvelope:
    requested_modes = set(modes or DEFAULT_OUTPUT_MODES)
    active_strategy = strategy or FetchStrategy()
    active_render = render or RenderOptions()
    resolved_render = RenderOptions(
        include_refs=active_render.include_refs,
        asset_profile=active_render.asset_profile or active_strategy.asset_profile,
        max_tokens=active_render.max_tokens,
    )

    article = _fetch_article(
        query,
        strategy=active_strategy,
        download_dir=download_dir,
        clients=clients,
        html_client=html_client,
        transport=transport,
        env=env,
    )
    envelope = build_fetch_envelope(article, modes=requested_modes, render=resolved_render)
    return envelope
