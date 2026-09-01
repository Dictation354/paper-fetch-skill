"""Full-text stage orchestrating providers and metadata fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
import time
from typing import Any
from collections.abc import Mapping, Sequence

from ..artifacts import ArtifactStore
from ..failure import FailureDiagnostics
from ..http import HttpTransport
from ..logging_utils import emit_structured_log
from ..models import ArticleModel, AssetProfile, metadata_only_article
from ..provider_catalog import (
    acquisition_for_provider_route,
    is_official_provider,
    provider_emits_html_managed_marker,
    provider_managed_abstract_only_names,
)
from ..publisher_identity import validate_extracted_identity
from ..providers.base import ProviderArtifacts, ProviderFailure, ProviderFetchResult
from ..providers.protocols import AssetProvider, FulltextProvider, RawFulltextProvider
from ..reason_codes import (
    ABSTRACT_ONLY,
    ERROR,
    METADATA_ONLY,
    IDENTITY_MISMATCH,
    NO_ACCESS,
    NOT_CONFIGURED,
    NOT_SUPPORTED,
    PDF_FALLBACK,
    RATE_LIMITED,
)
from ..quality.reason_codes import FULLTEXT
from ..runtime import RUNTIME_UNSET, RuntimeContext, resolve_runtime_context
from ..tracing import (
    TraceEvent,
    acquisition_fallback_used,
    fallback_marker,
    fulltext_marker,
    merge_trace,
    project_source_trail_trace,
    resolve_marker,
    route_marker,
    trace_from_markers,
)
from ..utils import (
    extend_unique,
    safe_text,
)
from .metadata import fetch_metadata_for_resolved_query
from .rendering import finalize_article
from .resolution import resolve_paper
from .routing import (
    build_official_provider_candidate_evidence,
    provider_allowed,
    resolve_query_with_session_cache,
)
from .shared import source_trail_for_failure
from .types import FetchStrategy, PaperFetchFailure

logger = logging.getLogger("paper_fetch.service")


def build_metadata_only_result(
    metadata: Mapping[str, Any],
    *,
    resolved,
    warnings: list[str] | None = None,
    source_trail: list[str] | None = None,
    trace: list[TraceEvent] | None = None,
) -> ArticleModel:
    from ..publisher_identity import normalize_doi

    article = metadata_only_article(
        source="crossref_meta",
        metadata=metadata,
        doi=normalize_doi(safe_text(metadata.get("doi") or resolved.doi)) or None,
        warnings=list(warnings or []),
        trace=merge_trace(trace_from_markers(list(source_trail or [])), trace),
    )
    effective_trace = merge_trace(trace_from_markers(list(source_trail or [])), trace)
    article.acquisition = acquisition_for_provider_route(
        "crossref",
        "metadata",
        fallback_used=acquisition_fallback_used(
            effective_trace,
            source_trail=source_trail or (),
        ),
    )
    return article


def _apply_article_acquisition(
    article: ArticleModel,
    *,
    provider_name: str,
    content: object | None,
    trace: Sequence[TraceEvent],
    source_trail: Sequence[str],
) -> None:
    route_name = safe_text(getattr(content, "route_name", "")) or None
    article.acquisition = acquisition_for_provider_route(
        provider_name,
        route_name,
        fallback_used=acquisition_fallback_used(
            trace,
            source_trail=source_trail,
        ),
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
    download_dir = artifact_store.asset_download_dir
    previous_asset_profile = context.asset_profile
    context.asset_profile = asset_profile
    try:
        if isinstance(provider_client, FulltextProvider):
            return provider_client.fetch_result(
                doi,
                metadata,
                download_dir,
                asset_profile=asset_profile,
                artifact_store=artifact_store,
                context=context,
            )

        if not isinstance(provider_client, RawFulltextProvider):
            raise ProviderFailure(
                NOT_SUPPORTED, "Provider does not implement raw full-text retrieval."
            )

        raw_payload = provider_client.fetch_raw_fulltext(doi, metadata, context=context)
        downloaded_assets: list[Mapping[str, Any]] = []
        asset_failures: list[Mapping[str, Any]] = []
        if (
            download_dir is not None
            and asset_profile != "none"
            and isinstance(provider_client, AssetProvider)
        ):
            asset_results = provider_client.download_related_assets(
                doi,
                metadata,
                raw_payload,
                download_dir,
                asset_profile=asset_profile,
                context=context,
            )
            downloaded_assets = list(asset_results.get("assets") or [])
            asset_failures = list(asset_results.get("asset_failures") or [])
        article = provider_client.to_article_model(
            metadata,
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
            context=context,
        )
        content = getattr(raw_payload, "content", None)
        route = safe_text(getattr(content, "route_kind", "")).lower()
        extracted_assets = (
            list(getattr(content, "extracted_assets", []) or [])
            if route == PDF_FALLBACK
            else []
        )
        return ProviderFetchResult(
            provider=safe_text(getattr(provider_client, "name", ""))
            or safe_text(raw_payload.provider)
            or "provider",
            article=article,
            content=content,
            warnings=list(getattr(raw_payload, "warnings", []) or []),
            trace=list(getattr(raw_payload, "trace", []) or []),
            artifacts=ProviderArtifacts(
                assets=[dict(item) for item in [*extracted_assets, *downloaded_assets]],
                asset_failures=[dict(item) for item in asset_failures],
            ),
        )
    finally:
        context.asset_profile = previous_asset_profile


@dataclass
class _ProviderAttemptOutputs:
    warnings: list[str] = field(default_factory=list)
    source_trail: list[str] = field(default_factory=list)
    trace: list[TraceEvent] = field(default_factory=list)
    failures: list[ProviderFailure] = field(default_factory=list)


def _try_official_provider(
    *,
    doi: str | None,
    metadata: Mapping[str, Any],
    provider_name: str | None,
    strategy: FetchStrategy,
    artifact_store: ArtifactStore,
    context: RuntimeContext,
    clients: Mapping[str, object],
    outputs: _ProviderAttemptOutputs,
) -> ArticleModel | None:
    warnings = outputs.warnings
    source_trail = outputs.source_trail
    workflow_trace = outputs.trace
    if not doi or not provider_name or not is_official_provider(provider_name):
        return None
    if not provider_allowed(provider_name, strategy):
        extend_unique(source_trail, [fulltext_marker(provider_name, "skipped")])
        return None

    provider_client = clients.get(provider_name)
    if not isinstance(provider_client, (FulltextProvider, RawFulltextProvider)):
        return None
    resolved_asset_profile = strategy.effective_asset_profile_for_provider(
        provider_name
    )

    extend_unique(source_trail, [fulltext_marker(provider_name, "attempt")])
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
        observed_article = provider_result.article
        identity = validate_extracted_identity(
            {"doi": doi, "title": metadata.get("title")},
            None,
            {
                "doi": observed_article.doi,
                "title": observed_article.metadata.title,
            },
        )
        if identity.mismatch:
            raise ProviderFailure(
                IDENTITY_MISMATCH,
                identity.reason or "Provider article identity mismatch.",
                diagnostics=FailureDiagnostics(
                    provider=provider_name,
                    route=safe_text(getattr(provider_result.content, "route_kind", ""))
                    or None,
                    details={"identity": identity.to_dict()},
                ),
            )
        workflow_trace[:] = merge_trace(workflow_trace, provider_result.trace)
        extend_unique(warnings, provider_result.warnings)
        download_warnings, download_trail = artifact_store.save_provider_payload(
            provider_result.provider or provider_name,
            content=provider_result.content,
            doi=doi,
            metadata=metadata,
        )
        extend_unique(warnings, download_warnings)
        extend_unique(source_trail, download_trail)
        html_download_warnings, html_download_trail = (
            artifact_store.save_provider_html_payload(
                provider_result.provider or provider_name,
                content=provider_result.content,
                doi=doi,
                metadata=metadata,
            )
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
        _apply_article_acquisition(
            article,
            provider_name=provider_result.provider or provider_name,
            content=provider_result.content,
            trace=workflow_trace,
            source_trail=source_trail,
        )
        artifact_store.audit_article_assets(
            article,
            asset_profile=resolved_asset_profile,
            asset_failures=provider_result.artifacts.asset_failures,
            archive_enabled=(
                artifact_store.asset_download_dir is not None
                and provider_result.artifacts.allow_related_assets
                and not provider_result.artifacts.text_only
            ),
        )
        extend_unique(source_trail, article.quality.source_trail)
        if article.quality.content_kind == FULLTEXT:
            emit_structured_log(
                logger,
                logging.DEBUG,
                "official_provider_result",
                provider=provider_name,
                url=provider_result.content.source_url
                if provider_result.content is not None
                else None,
                status="success",
                elapsed_ms=round((time.monotonic() - attempt_started_at) * 1000, 3),
                attempt=1,
            )
            extend_unique(source_trail, [fulltext_marker(provider_name, "article_ok")])
            return finalize_article(
                article,
                warnings=warnings,
                source_trail=source_trail,
                trace=workflow_trace,
            )
        if article.quality.content_kind == ABSTRACT_ONLY:
            emit_structured_log(
                logger,
                logging.DEBUG,
                "official_provider_result",
                provider=provider_name,
                url=provider_result.content.source_url
                if provider_result.content is not None
                else None,
                status=ABSTRACT_ONLY,
                elapsed_ms=round((time.monotonic() - attempt_started_at) * 1000, 3),
                attempt=1,
            )
            extend_unique(source_trail, [fulltext_marker(provider_name, ABSTRACT_ONLY)])
            if provider_name in provider_managed_abstract_only_names():
                warnings.append(
                    "Official full text only contained abstract-level content; returning abstract-only provider result."
                )
                return finalize_article(
                    article,
                    warnings=warnings,
                    source_trail=source_trail,
                    trace=workflow_trace,
                )
            warnings.append(
                "Official full text only contained abstract-level content; continuing to metadata-only fallback."
            )
        else:
            content = provider_result.content
            route = safe_text(getattr(content, "route_kind", "")).lower()
            body = getattr(content, "body", b"") if content is not None else b""
            if (
                route == PDF_FALLBACK
                and isinstance(body, (bytes, bytearray))
                and bytes(body).startswith(b"%PDF-")
            ):
                warnings.append(
                    "Official provider downloaded a PDF, but Markdown full text was not available; returning PDF-only provider result."
                )
                emit_structured_log(
                    logger,
                    logging.DEBUG,
                    "official_provider_result",
                    provider=provider_name,
                    url=provider_result.content.source_url
                    if provider_result.content is not None
                    else None,
                    status="pdf_only",
                    elapsed_ms=round((time.monotonic() - attempt_started_at) * 1000, 3),
                    attempt=1,
                )
                extend_unique(
                    source_trail,
                    [fulltext_marker(provider_name, "ok", route=PDF_FALLBACK)],
                )
                return finalize_article(
                    article,
                    warnings=warnings,
                    source_trail=source_trail,
                    trace=workflow_trace,
                )
            emit_structured_log(
                logger,
                logging.DEBUG,
                "official_provider_result",
                provider=provider_name,
                url=provider_result.content.source_url
                if provider_result.content is not None
                else None,
                status="not_usable",
                elapsed_ms=round((time.monotonic() - attempt_started_at) * 1000, 3),
                attempt=1,
            )
            extend_unique(source_trail, [fulltext_marker(provider_name, "not_usable")])
        extend_unique(warnings, article.quality.warnings)
    except ProviderFailure as exc:
        outputs.failures.append(exc)
        workflow_trace[:] = merge_trace(workflow_trace, exc.trace)
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
        extend_unique(
            source_trail, [source_trail_for_failure("fulltext", provider_name, exc)]
        )
    return None


def _ranked_fulltext_provider_candidates(
    *,
    resolved: object,
    metadata: Mapping[str, Any],
    selected_provider: str | None,
    strategy: FetchStrategy,
) -> list[tuple[str, str, str]]:
    """Return deduplicated, evidence-ranked official full-text candidates."""

    evidence = build_official_provider_candidate_evidence(
        resolved,
        routing_metadata=metadata,
        strategy=strategy,
    )
    evidence_by_provider = {item.provider: item for item in evidence}
    ranked: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    if (
        selected_provider
        and is_official_provider(selected_provider)
        and provider_allowed(selected_provider, strategy)
    ):
        selected_evidence = evidence_by_provider.get(selected_provider)
        ranked.append(
            (
                selected_provider,
                "metadata_selected",
                selected_evidence.strength if selected_evidence is not None else "weak",
            )
        )
        seen.add(selected_provider)
    for candidate in evidence:
        provider_name = candidate.provider
        if provider_name in seen:
            continue
        seen.add(provider_name)
        ranked.append((provider_name, candidate.signal, candidate.strength))
    return ranked


def _primary_provider_failure(
    failures: Sequence[ProviderFailure],
) -> ProviderFailure | None:
    if not failures:
        return None
    priority = {
        NO_ACCESS: 50,
        RATE_LIMITED: 40,
        IDENTITY_MISMATCH: 30,
        NOT_CONFIGURED: 20,
        ERROR: 10,
    }
    return max(
        enumerate(failures),
        key=lambda item: (priority.get(item[1].code, 0), item[0]),
    )[1]


def _fallback_to_metadata_only(
    *,
    metadata: Mapping[str, Any],
    resolved,
    strategy: FetchStrategy,
    warnings: list[str],
    source_trail: list[str],
    trace: list[TraceEvent] | None = None,
    provider_failure: ProviderFailure | None = None,
) -> ArticleModel:
    if not metadata:
        raise PaperFetchFailure(
            ERROR, "Unable to resolve metadata or full text for the requested paper."
        )
    if not strategy.allow_metadata_only_fallback:
        if provider_failure is not None:
            raise PaperFetchFailure.from_provider_failure(provider_failure)
        raise PaperFetchFailure(
            ERROR, "Full text was not available and metadata-only fallback is disabled."
        )
    warnings.append(
        "Full text was not available; returning metadata and abstract only."
    )
    extend_unique(source_trail, [fallback_marker(METADATA_ONLY)])
    return build_metadata_only_result(
        metadata,
        resolved=resolved,
        warnings=warnings,
        source_trail=source_trail,
        trace=trace,
    )


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
        runtime.fetch_trace = []
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
        source_trail: list[str] = [resolve_marker(resolved.query_kind)]
        if resolved.doi:
            source_trail.append(resolve_marker("doi_selected"))
        if resolved.candidates and not resolved.doi:
            raise PaperFetchFailure(
                "ambiguous",
                "Query resolution is ambiguous; choose one of the DOI candidates.",
                candidates=resolved.candidates,
            )

        metadata, provider_name, metadata_trail = fetch_metadata_for_resolved_query(
            resolved,
            clients=client_registry,
            strategy=strategy,
            context=runtime,
        )
        extend_unique(source_trail, metadata_trail)
        from ..publisher_identity import normalize_doi

        doi = normalize_doi(safe_text(metadata.get("doi") or resolved.doi)) or None
        warnings: list[str] = []
        trace: list[TraceEvent] = []

        article = None
        provider_failures: list[ProviderFailure] = []
        provider_candidates = _ranked_fulltext_provider_candidates(
            resolved=resolved,
            metadata=metadata,
            selected_provider=provider_name,
            strategy=strategy,
        )
        for rank, (candidate_provider, signal, identity_strength) in enumerate(
            provider_candidates,
            start=1,
        ):
            provider_name = candidate_provider
            source_trail.append(
                route_marker(
                    f"provider_candidate_{candidate_provider}_{signal}_rank_{rank}"
                )
            )
            source_trail.append(
                route_marker(
                    f"provider_candidate_{candidate_provider}_identity_{identity_strength}"
                )
            )
            attempt_outputs = _ProviderAttemptOutputs(
                warnings=warnings,
                source_trail=source_trail,
                trace=trace,
            )
            article = _try_official_provider(
                doi=doi,
                metadata=metadata,
                provider_name=candidate_provider,
                strategy=strategy,
                artifact_store=runtime.artifact_store,
                context=runtime,
                clients=client_registry,
                outputs=attempt_outputs,
            )
            provider_failures.extend(attempt_outputs.failures)
            if article is not None:
                source_trail.append(
                    route_marker(f"provider_candidate_{candidate_provider}_accepted")
                )
                article = finalize_article(
                    article,
                    warnings=warnings,
                    source_trail=source_trail,
                    trace=trace,
                )
                runtime.fetch_trace = project_source_trail_trace(source_trail, trace)
                break
            source_trail.append(
                route_marker(f"provider_candidate_{candidate_provider}_rejected")
            )
            if identity_strength == "strong" and any(
                failure.code == NO_ACCESS for failure in attempt_outputs.failures
            ):
                source_trail.append(
                    route_marker(
                        f"provider_candidate_{candidate_provider}_access_boundary_stop"
                    )
                )
                break
            if any(failure.code == NO_ACCESS for failure in attempt_outputs.failures):
                source_trail.append(
                    route_marker(
                        f"provider_candidate_{candidate_provider}_access_boundary_weak_continue"
                    )
                )
        if article is not None:
            return article

        if provider_emits_html_managed_marker(provider_name):
            extend_unique(
                source_trail,
                [fallback_marker(f"{provider_name}_html_managed_by_provider")],
            )

        fallback_article = _fallback_to_metadata_only(
            metadata=metadata,
            resolved=resolved,
            strategy=strategy,
            warnings=warnings,
            source_trail=source_trail,
            trace=trace,
            provider_failure=_primary_provider_failure(provider_failures),
        )
        runtime.fetch_trace = project_source_trail_trace(source_trail, trace)
        return fallback_article
    finally:
        if owns_runtime:
            runtime.close()
