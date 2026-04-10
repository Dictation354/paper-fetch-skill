"""Service-layer orchestration for paper fetch."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .config import build_runtime_env
from .http import HttpTransport
from .models import ArticleModel, FetchEnvelope, Metadata, OutputMode, RenderOptions, metadata_only_article, normalize_text
from .providers.base import ProviderFailure
from .providers.html_generic import HtmlGenericClient
from .providers.registry import build_clients
from .publisher_identity import infer_provider_from_doi, normalize_doi
from .resolve.query import ResolvedQuery, resolve_query
from .utils import build_output_path, dedupe_authors, save_payload

DEFAULT_OUTPUT_MODES: set[OutputMode] = {"article", "markdown"}
PUBLIC_SOURCE_BY_ARTICLE_SOURCE = {
    "elsevier_xml": "elsevier_xml",
    "springer_xml": "springer_xml",
    "wiley": "wiley_tdm",
    "html_generic": "html_fallback",
    "crossref_meta": "crossref_meta",
}
HTML_PROVIDER_ALIASES = {"html", "html_generic", "html_fallback"}


class PaperFetchFailure(Exception):
    def __init__(self, status: str, reason: str, *, candidates: list[dict[str, Any]] | None = None) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason
        self.candidates = list(candidates or [])


@dataclass(frozen=True)
class FetchStrategy:
    allow_html_fallback: bool = True
    allow_metadata_only_fallback: bool = True
    preferred_providers: list[str] | None = None

    def normalized_preferred_providers(self) -> set[str] | None:
        if self.preferred_providers is None:
            return None
        normalized = {normalize_text(item).lower() for item in self.preferred_providers if normalize_text(item)}
        return normalized or set()


def extend_unique(target: list[str], items: list[str] | None) -> None:
    for item in items or []:
        normalized = normalize_text(item)
        if normalized and normalized not in target:
            target.append(normalized)


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


def merge_metadata(primary: Mapping[str, Any] | None, secondary: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = dict(secondary or {})
    merged.update(primary or {})
    scalar_keys = ("doi", "title", "journal_title", "published", "landing_page_url", "abstract", "publisher")

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
        normalized = normalize_text(str(value))
        if normalized:
            return normalized
        return "" if preserve_blank else None

    for key in scalar_keys:
        primary_has_value = primary is not None and key in primary and primary.get(key) is not None
        if primary_has_value:
            merged[key] = scalarize(primary.get(key), preserve_blank=True)
        else:
            merged[key] = scalarize((secondary or {}).get(key))

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
    return merged


def metadata_from_resolution(resolved: ResolvedQuery) -> dict[str, Any]:
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


def fetch_metadata_for_resolved_query(
    resolved: ResolvedQuery,
    *,
    clients: Mapping[str, Any],
    strategy: FetchStrategy,
) -> tuple[dict[str, Any], str | None, list[str]]:
    provider_name = resolved.provider_hint
    if not provider_name and resolved.doi:
        provider_name = infer_provider_from_doi(resolved.doi)
    provider_name = provider_name or "crossref"

    official_metadata: dict[str, Any] | None = None
    crossref_metadata: dict[str, Any] | None = None
    source_trail: list[str] = []

    if resolved.doi and provider_name != "crossref":
        if provider_allowed(provider_name, strategy):
            client = clients.get(provider_name)
            if client is not None:
                try:
                    official_metadata = client.fetch_metadata({"doi": resolved.doi})
                    if official_metadata:
                        source_trail.append(f"metadata:{provider_name}_ok")
                except ProviderFailure as exc:
                    official_metadata = None
                    source_trail.append(source_trail_for_failure("metadata", provider_name, exc))
        else:
            source_trail.append(f"metadata:{provider_name}_skipped")

    if resolved.doi and provider_allowed("crossref", strategy):
        try:
            crossref_metadata = clients["crossref"].fetch_metadata({"doi": resolved.doi})
            if crossref_metadata:
                source_trail.append("metadata:crossref_ok")
        except ProviderFailure as exc:
            crossref_metadata = None
            source_trail.append(source_trail_for_failure("metadata", "crossref", exc))
    elif resolved.doi:
        source_trail.append("metadata:crossref_skipped")

    if official_metadata or crossref_metadata:
        metadata = merge_metadata(official_metadata, crossref_metadata)
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
        doi=normalize_doi(str(metadata.get("doi") or resolved.doi or "")) or None,
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
    provider_slug = normalize_text(str(raw_payload.provider or "provider")).lower().replace(" ", "_") or "provider"
    provider_label = provider_slug.replace("_", " ").title()
    if download_dir is None:
        return [f"{provider_label} official PDF/binary was not written to disk because --no-download was set."], [
            f"download:{provider_slug}_skipped"
        ]

    saved_path = save_payload(
        build_output_path(
            download_dir,
            doi,
            str(metadata.get("title") or ""),
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
    landing_url = normalize_text(str(metadata.get("landing_page_url") or resolved.landing_url or "")) or None
    doi = normalize_doi(str(metadata.get("doi") or resolved.doi or "")) or None
    html_fallback_client = html_client or HtmlGenericClient(active_transport, active_env)
    warnings: list[str] = []

    if doi and provider_name and provider_name != "crossref":
        if provider_allowed(provider_name, strategy):
            provider_client = client_registry.get(provider_name)
            if provider_client is not None:
                extend_unique(source_trail, [f"fulltext:{provider_name}_attempt"])
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
                    article = provider_client.to_article_model(metadata, raw_payload)
                    extend_unique(source_trail, article.quality.source_trail)
                    if article.quality.has_fulltext and article.sections:
                        extend_unique(source_trail, [f"fulltext:{provider_name}_article_ok"])
                        return finalize_article(article, warnings=warnings, source_trail=source_trail)
                    if article.quality.has_fulltext and not article.sections:
                        warnings.append("Official full text only contained abstract-level content; continuing to HTML fallback.")
                        extend_unique(source_trail, [f"fulltext:{provider_name}_abstract_only"])
                    else:
                        extend_unique(source_trail, [f"fulltext:{provider_name}_not_usable"])
                    extend_unique(warnings, article.quality.warnings)
                except ProviderFailure as exc:
                    warnings.append(exc.message)
                    extend_unique(source_trail, [source_trail_for_failure("fulltext", provider_name, exc)])
        else:
            extend_unique(source_trail, [f"fulltext:{provider_name}_skipped"])

    if not html_fallback_allowed(strategy):
        extend_unique(source_trail, ["fallback:html_disabled"])
    if html_fallback_allowed(strategy) and landing_url:
        extend_unique(source_trail, ["fallback:html_attempt"])
        try:
            article = html_fallback_client.fetch_article_model(
                landing_url,
                metadata=metadata,
                expected_doi=doi,
            )
            if article.quality.has_fulltext:
                extend_unique(source_trail, article.quality.source_trail)
                extend_unique(source_trail, ["fallback:html_ok"])
                return finalize_article(article, warnings=warnings, source_trail=source_trail)
            extend_unique(warnings, article.quality.warnings)
            extend_unique(source_trail, article.quality.source_trail)
            extend_unique(source_trail, ["fallback:html_not_usable"])
        except ProviderFailure as exc:
            warnings.append(exc.message)
            extend_unique(source_trail, ["fallback:html_fail"])
    elif html_fallback_allowed(strategy):
        extend_unique(source_trail, ["fallback:html_unavailable"])

    if metadata:
        if not strategy.allow_metadata_only_fallback:
            raise PaperFetchFailure("error", "Full text was not available and metadata-only fallback is disabled.")
        warnings.append("Full text was not available; returning metadata and abstract only.")
        extend_unique(source_trail, ["fallback:metadata_only"])
        return build_metadata_only_result(metadata, resolved=resolved, warnings=warnings, source_trail=source_trail)

    raise PaperFetchFailure("error", "Unable to resolve metadata or full text for the requested paper.")


def metadata_model_from_mapping(metadata: Mapping[str, Any]) -> Metadata:
    return Metadata(
        title=normalize_text(str(metadata.get("title") or "")) or None,
        authors=[normalize_text(str(item)) for item in list(metadata.get("authors") or []) if normalize_text(str(item))],
        abstract=normalize_text(str(metadata.get("abstract") or "")) or None,
        journal=normalize_text(str(metadata.get("journal_title") or metadata.get("journal") or "")) or None,
        published=normalize_text(str(metadata.get("published") or "")) or None,
        keywords=[normalize_text(str(item)) for item in list(metadata.get("keywords") or []) if normalize_text(str(item))],
        license_urls=[normalize_text(str(item)) for item in list(metadata.get("license_urls") or []) if normalize_text(str(item))],
        landing_page_url=normalize_text(str(metadata.get("landing_page_url") or "")) or None,
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
    markdown = article.to_ai_markdown(include_refs=render.include_refs, max_tokens=render.max_tokens) if "markdown" in modes else None
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

    article = _fetch_article(
        query,
        strategy=active_strategy,
        download_dir=download_dir,
        clients=clients,
        html_client=html_client,
        transport=transport,
        env=env,
    )
    envelope = build_fetch_envelope(article, modes=requested_modes, render=active_render)
    if "metadata" in requested_modes and envelope.metadata is None:
        envelope.metadata = metadata_model_from_mapping({})
    return envelope
