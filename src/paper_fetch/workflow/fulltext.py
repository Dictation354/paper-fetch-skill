"""Full-text stage orchestrating providers and metadata fallback."""

from __future__ import annotations

import inspect
import logging
from pathlib import Path
import time
from functools import lru_cache
from typing import Any, Mapping

from ..artifacts import ArtifactStore
from ..http import HttpTransport
from ..logging_utils import emit_structured_log
from ..models import ArticleModel, AssetProfile, metadata_only_article
from ..provider_catalog import is_official_provider, provider_managed_abstract_only_names
from ..providers.base import ProviderArtifacts, ProviderFailure, ProviderFetchResult
from ..providers.protocols import AssetProvider, FulltextProvider, RawFulltextProvider
from ..runtime import RUNTIME_UNSET, RuntimeContext, resolve_runtime_context
from ..tracing import trace_from_markers
from ..utils import (
    extend_unique,
    safe_text,
)
from .metadata import fetch_metadata_for_resolved_query
from .rendering import finalize_article
from .resolution import resolve_paper
from .routing import provider_allowed, resolve_query_with_session_cache
from .shared import source_trail_for_failure
from .types import FetchStrategy, PaperFetchFailure

logger = logging.getLogger("paper_fetch.service")
PROVIDER_MANAGED_ABSTRACT_ONLY_PROVIDERS = provider_managed_abstract_only_names()


def _record_stage_timing(context: RuntimeContext, name: str, started_at: float) -> None:
    context.record_stage_timing(name, started_at)


@lru_cache(maxsize=128)
def _fetch_result_accepts_artifact_store(fetch_result_type: type, fetch_result_name: str) -> bool:
    del fetch_result_name
    fetch_result = getattr(fetch_result_type, "fetch_result", None)
    if fetch_result is None:
        return False
    try:
        parameters = inspect.signature(fetch_result).parameters
    except (TypeError, ValueError):
        return False
    return "artifact_store" in parameters


def build_metadata_only_result(
    metadata: Mapping[str, Any],
    *,
    resolved,
    warnings: list[str] | None = None,
    source_trail: list[str] | None = None,
) -> ArticleModel:
    from ..publisher_identity import normalize_doi

    return metadata_only_article(
        source="crossref_meta",
        metadata=metadata,
        doi=normalize_doi(safe_text(metadata.get("doi") or resolved.doi)) or None,
        warnings=list(warnings or []),
        trace=trace_from_markers(list(source_trail or [])),
    )


def maybe_save_provider_payload(
    provider_name: str,
    *,
    content,
    download_dir: Path | None,
    doi: str | None,
    metadata: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    return ArtifactStore.from_download_dir(download_dir).save_provider_payload(
        provider_name,
        content=content,
        doi=doi,
        metadata=metadata,
    )


def _provider_html_output_path(
    provider_name: str,
    *,
    content,
    download_dir: Path | None,
    doi: str | None,
    metadata: Mapping[str, Any],
) -> Path | None:
    return ArtifactStore.from_download_dir(download_dir).provider_html_output_path(
        provider_name,
        content=content,
        doi=doi,
        metadata=metadata,
    )


def maybe_save_provider_html_payload(
    provider_name: str,
    *,
    content,
    download_dir: Path | None,
    doi: str | None,
    metadata: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    return ArtifactStore.from_download_dir(download_dir).save_provider_html_payload(
        provider_name,
        content=content,
        doi=doi,
        metadata=metadata,
    )


def _provider_fetch_result(
    provider_client: FulltextProvider | RawFulltextProvider,
    *,
    doi: str,
    metadata: Mapping[str, Any],
    artifact_store: ArtifactStore,
    asset_profile: AssetProfile,
    context: RuntimeContext,
) -> ProviderFetchResult:
    download_dir = artifact_store.download_dir
    if isinstance(provider_client, FulltextProvider):
        fetch_result = provider_client.fetch_result
        if _fetch_result_accepts_artifact_store(type(provider_client), getattr(fetch_result, "__name__", "fetch_result")):
            return fetch_result(
                doi,
                metadata,
                download_dir,
                asset_profile=asset_profile,
                artifact_store=artifact_store,
                context=context,
            )
        return fetch_result(doi, metadata, download_dir, asset_profile=asset_profile, context=context)

    if not isinstance(provider_client, RawFulltextProvider):
        raise ProviderFailure("not_supported", "Provider does not implement raw full-text retrieval.")

    raw_payload = provider_client.fetch_raw_fulltext(doi, metadata, context=context)
    downloaded_assets: list[Mapping[str, Any]] = []
    asset_failures: list[Mapping[str, Any]] = []
    if download_dir is not None and asset_profile != "none" and isinstance(provider_client, AssetProvider):
        asset_started_at = time.monotonic()
        try:
            asset_results = provider_client.download_related_assets(
                doi,
                metadata,
                raw_payload,
                download_dir,
                asset_profile=asset_profile,
                context=context,
            )
        finally:
            context.accumulate_stage_timing("asset_seconds", started_at=asset_started_at)
        downloaded_assets = list(asset_results.get("assets") or [])
        asset_failures = list(asset_results.get("asset_failures") or [])
    article = provider_client.to_article_model(
        metadata,
        raw_payload,
        downloaded_assets=downloaded_assets,
        asset_failures=asset_failures,
        context=context,
    )
    return ProviderFetchResult(
        provider=safe_text(getattr(provider_client, "name", "")) or safe_text(raw_payload.provider) or "provider",
        article=article,
        content=getattr(raw_payload, "content", None),
        warnings=list(getattr(raw_payload, "warnings", []) or []),
        trace=list(getattr(raw_payload, "trace", []) or []),
        artifacts=ProviderArtifacts(
            assets=[dict(item) for item in downloaded_assets],
            asset_failures=[dict(item) for item in asset_failures],
        ),
    )


def _apply_provider_artifacts(
    *,
    provider_name: str,
    artifacts: ProviderArtifacts,
    download_dir: Path | None,
    asset_profile: AssetProfile,
    warnings: list[str],
    source_trail: list[str],
) -> None:
    ArtifactStore.from_download_dir(download_dir).apply_provider_artifacts(
        provider_name=provider_name,
        artifacts=artifacts,
        asset_profile=asset_profile,
        warnings=warnings,
        source_trail=source_trail,
    )


def _try_official_provider(
    *,
    doi: str | None,
    metadata: Mapping[str, Any],
    provider_name: str | None,
    strategy: FetchStrategy,
    artifact_store: ArtifactStore,
    context: RuntimeContext,
    clients: Mapping[str, object],
    warnings: list[str],
    source_trail: list[str],
) -> ArticleModel | None:
    if not doi or not provider_name or provider_name == "crossref":
        return None
    if not provider_allowed(provider_name, strategy):
        extend_unique(source_trail, [f"fulltext:{provider_name}_skipped"])
        return None

    provider_client = clients.get(provider_name)
    if not isinstance(provider_client, (FulltextProvider, RawFulltextProvider)):
        return None
    resolved_asset_profile = strategy.effective_asset_profile_for_provider(provider_name)

    extend_unique(source_trail, [f"fulltext:{provider_name}_attempt"])
    attempt_started_at = time.monotonic()
    emit_structured_log(
        logger,
        logging.DEBUG,
        "official_provider_attempt",
        provider=provider_name,
        url=safe_text(metadata.get("landing_page_url")) or None,
        status="attempt",
        elapsed_ms=0.0,
        attempt=1,
    )
    try:
        provider_result = _provider_fetch_result(
            provider_client,
            doi=doi,
            metadata=metadata,
            artifact_store=artifact_store,
            asset_profile=resolved_asset_profile,
            context=context,
        )
        extend_unique(warnings, provider_result.warnings)
        download_warnings, download_trail = artifact_store.save_provider_payload(
            provider_result.provider or provider_name,
            content=provider_result.content,
            doi=doi,
            metadata=metadata,
        )
        extend_unique(warnings, download_warnings)
        extend_unique(source_trail, download_trail)
        html_download_warnings, html_download_trail = artifact_store.save_provider_html_payload(
            provider_result.provider or provider_name,
            content=provider_result.content,
            doi=doi,
            metadata=metadata,
        )
        extend_unique(warnings, html_download_warnings)
        extend_unique(source_trail, html_download_trail)
        artifact_store.apply_provider_artifacts(
            provider_name=provider_name,
            artifacts=provider_result.artifacts,
            asset_profile=resolved_asset_profile,
            warnings=warnings,
            source_trail=source_trail,
        )
        article = provider_result.article
        extend_unique(source_trail, article.quality.source_trail)
        if article.quality.content_kind == "fulltext":
            emit_structured_log(
                logger,
                logging.DEBUG,
                "official_provider_result",
                provider=provider_name,
                url=provider_result.content.source_url if provider_result.content is not None else None,
                status="success",
                elapsed_ms=round((time.monotonic() - attempt_started_at) * 1000, 3),
                attempt=1,
            )
            extend_unique(source_trail, [f"fulltext:{provider_name}_article_ok"])
            return finalize_article(article, warnings=warnings, source_trail=source_trail)
        if article.quality.content_kind == "abstract_only":
            emit_structured_log(
                logger,
                logging.DEBUG,
                "official_provider_result",
                provider=provider_name,
                url=provider_result.content.source_url if provider_result.content is not None else None,
                status="abstract_only",
                elapsed_ms=round((time.monotonic() - attempt_started_at) * 1000, 3),
                attempt=1,
            )
            extend_unique(source_trail, [f"fulltext:{provider_name}_abstract_only"])
            if provider_name in PROVIDER_MANAGED_ABSTRACT_ONLY_PROVIDERS:
                warnings.append("Official full text only contained abstract-level content; returning abstract-only provider result.")
                return finalize_article(article, warnings=warnings, source_trail=source_trail)
            warnings.append("Official full text only contained abstract-level content; continuing to metadata-only fallback.")
        else:
            emit_structured_log(
                logger,
                logging.DEBUG,
                "official_provider_result",
                provider=provider_name,
                url=provider_result.content.source_url if provider_result.content is not None else None,
                status="not_usable",
                elapsed_ms=round((time.monotonic() - attempt_started_at) * 1000, 3),
                attempt=1,
            )
            extend_unique(source_trail, [f"fulltext:{provider_name}_not_usable"])
        extend_unique(warnings, article.quality.warnings)
    except ProviderFailure as exc:
        extend_unique(warnings, exc.warnings)
        extend_unique(source_trail, exc.source_trail)
        emit_structured_log(
            logger,
            logging.DEBUG,
            "official_provider_result",
            provider=provider_name,
            url=safe_text(metadata.get("landing_page_url")) or None,
            status=exc.code,
            elapsed_ms=round((time.monotonic() - attempt_started_at) * 1000, 3),
            attempt=1,
        )
        warnings.append(exc.message)
        extend_unique(source_trail, [source_trail_for_failure("fulltext", provider_name, exc)])
    return None


def _fallback_to_metadata_only(
    *,
    metadata: Mapping[str, Any],
    resolved,
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


def fetch_article(
    query: str,
    *,
    strategy: FetchStrategy,
    download_dir: Path | None | object = RUNTIME_UNSET,
    clients: Mapping[str, object] | None | object = RUNTIME_UNSET,
    transport: HttpTransport | None | object = RUNTIME_UNSET,
    env: Mapping[str, str] | None | object = RUNTIME_UNSET,
    context: RuntimeContext | None = None,
    resolve_paper_fn=None,
) -> ArticleModel:
    owns_runtime = context is None
    runtime = resolve_runtime_context(
        context,
        env=env,
        transport=transport,
        clients=clients,
        download_dir=download_dir,
    )
    assert runtime.env is not None
    assert runtime.transport is not None
    assert runtime.artifact_store is not None
    try:
        active_env = runtime.env
        active_transport = runtime.transport
        client_registry = dict(runtime.get_clients())
        resolver = resolve_paper_fn or resolve_paper
        resolve_started_at = time.monotonic()
        resolved = resolve_query_with_session_cache(
            query,
            resolver=resolver,
            transport=active_transport,
            env=active_env,
            context=runtime,
        )
        _record_stage_timing(runtime, "resolve_seconds", resolve_started_at)
        source_trail: list[str] = [f"resolve:{resolved.query_kind}"]
        if resolved.doi:
            source_trail.append("resolve:doi_selected")
        if resolved.candidates and not resolved.doi:
            raise PaperFetchFailure(
                "ambiguous",
                "Query resolution is ambiguous; choose one of the DOI candidates.",
                candidates=resolved.candidates,
            )

        metadata_started_at = time.monotonic()
        metadata, provider_name, metadata_trail = fetch_metadata_for_resolved_query(
            resolved,
            clients=client_registry,
            strategy=strategy,
            context=runtime,
        )
        _record_stage_timing(runtime, "metadata_seconds", metadata_started_at)
        extend_unique(source_trail, metadata_trail)
        from ..publisher_identity import normalize_doi

        doi = normalize_doi(safe_text(metadata.get("doi") or resolved.doi)) or None
        warnings: list[str] = []

        fulltext_started_at = time.monotonic()
        article = _try_official_provider(
            doi=doi,
            metadata=metadata,
            provider_name=provider_name,
            strategy=strategy,
            artifact_store=runtime.artifact_store,
            context=runtime,
            clients=client_registry,
            warnings=warnings,
            source_trail=source_trail,
        )
        _record_stage_timing(runtime, "fulltext_seconds", fulltext_started_at)
        if article is not None:
            return article

        if is_official_provider(provider_name):
            extend_unique(source_trail, [f"fallback:{provider_name}_html_managed_by_provider"])

        return _fallback_to_metadata_only(
            metadata=metadata,
            resolved=resolved,
            strategy=strategy,
            warnings=warnings,
            source_trail=source_trail,
        )
    finally:
        if owns_runtime:
            runtime.close()
