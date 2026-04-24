"""Full-text stage orchestrating providers and metadata fallback."""

from __future__ import annotations

import logging
from pathlib import Path
import time
from typing import Any, Mapping

from ..config import build_runtime_env
from ..http import HttpTransport
from ..logging_utils import emit_structured_log
from ..models import ArticleModel, AssetProfile, metadata_only_article
from ..providers.base import ProviderArtifacts, ProviderFailure, ProviderFetchResult
from ..providers.registry import build_clients
from ..tracing import trace_from_markers
from ..utils import (
    build_output_path,
    extension_from_content_type,
    extend_unique,
    normalize_text,
    safe_text,
    sanitize_filename,
    save_payload,
)
from .metadata import fetch_metadata_for_resolved_query
from .rendering import finalize_article
from .resolution import resolve_paper
from .routing import provider_allowed
from .shared import source_trail_for_failure
from .types import FetchStrategy, PaperFetchFailure

logger = logging.getLogger("paper_fetch.service")
PROVIDER_MANAGED_ABSTRACT_ONLY_PROVIDERS = {"springer", "wiley", "science", "pnas"}
ACCEPTABLE_PREVIEW_MIN_WIDTH = 300
ACCEPTABLE_PREVIEW_MIN_HEIGHT = 200


def _preview_asset_accepted(asset: Mapping[str, Any]) -> bool:
    if bool(asset.get("preview_accepted")):
        return True
    try:
        width = int(asset.get("width") or 0)
        height = int(asset.get("height") or 0)
    except (TypeError, ValueError):
        return False
    return width >= ACCEPTABLE_PREVIEW_MIN_WIDTH and height >= ACCEPTABLE_PREVIEW_MIN_HEIGHT


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
    if content is None or not content.needs_local_copy:
        return [], []
    provider_slug = safe_text(provider_name or "provider").lower().replace(" ", "_") or "provider"
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
            content.content_type,
            content.source_url,
        ),
        content.body,
    )
    if saved_path:
        return [f"{provider_label} official full text was downloaded as PDF/binary to {saved_path}."], [
            f"download:{provider_slug}_saved"
        ]
    return [f"{provider_label} official full text was available only as PDF/binary and could not be written to disk."], [
        f"download:{provider_slug}_save_failed"
    ]


def _provider_html_output_path(
    provider_name: str,
    *,
    content,
    download_dir: Path | None,
    doi: str | None,
    metadata: Mapping[str, Any],
) -> Path | None:
    if content is None or download_dir is None:
        return None
    if normalize_text(provider_name).lower() != "springer":
        return None
    if normalize_text(content.route_kind).lower() != "html":
        return None

    extension = extension_from_content_type(content.content_type, content.source_url).lower()
    if extension not in {".html", ".htm"}:
        return None

    article_slug = sanitize_filename(doi or safe_text(metadata.get("title")) or "article")
    if download_dir.name == article_slug:
        return download_dir / f"original{extension}"
    return download_dir / f"{article_slug}_original{extension}"


def maybe_save_provider_html_payload(
    provider_name: str,
    *,
    content,
    download_dir: Path | None,
    doi: str | None,
    metadata: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    output_path = _provider_html_output_path(
        provider_name,
        content=content,
        download_dir=download_dir,
        doi=doi,
        metadata=metadata,
    )
    if output_path is None or content is None:
        return [], []
    save_payload(output_path, content.body)
    return [], [f"download:{normalize_text(provider_name).lower()}_html_saved"]


def _provider_fetch_result(
    provider_client: Any,
    *,
    doi: str,
    metadata: Mapping[str, Any],
    download_dir: Path | None,
    asset_profile: AssetProfile,
) -> ProviderFetchResult:
    if hasattr(provider_client, "fetch_result"):
        return provider_client.fetch_result(doi, metadata, download_dir, asset_profile=asset_profile)

    raw_payload = provider_client.fetch_raw_fulltext(doi, metadata)
    downloaded_assets: list[Mapping[str, Any]] = []
    asset_failures: list[Mapping[str, Any]] = []
    if download_dir is not None and asset_profile != "none":
        asset_results = provider_client.download_related_assets(
            doi,
            metadata,
            raw_payload,
            download_dir,
            asset_profile=asset_profile,
        )
        downloaded_assets = list(asset_results.get("assets") or [])
        asset_failures = list(asset_results.get("asset_failures") or [])
    article = provider_client.to_article_model(
        metadata,
        raw_payload,
        downloaded_assets=downloaded_assets,
        asset_failures=asset_failures,
    )
    return ProviderFetchResult(
        provider=safe_text(getattr(provider_client, "name", "")) or "provider",
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
    if download_dir is None:
        return
    if asset_profile == "none":
        extend_unique(source_trail, [f"download:{provider_name}_assets_skipped_profile_none"])
        return
    if artifacts.skip_warning:
        extend_unique(warnings, [artifacts.skip_warning])
        extend_unique(source_trail, [event.marker() for event in artifacts.skip_trace if event.marker()])
        return
    if artifacts.assets:
        extend_unique(source_trail, [f"download:{provider_name}_assets_saved_profile_{asset_profile}"])
        preview_assets = [
            asset
            for asset in artifacts.assets
            if normalize_text(asset.get("download_tier")).lower() == "preview"
        ]
        preview_accepted_count = sum(1 for asset in preview_assets if _preview_asset_accepted(asset))
        preview_fallback_count = len(preview_assets) - preview_accepted_count
        if preview_accepted_count:
            extend_unique(
                warnings,
                [
                    (
                        f"{provider_name.replace('_', ' ').title()} figure downloads used preview images for "
                        f"{preview_accepted_count} asset(s), but their saved dimensions met the acceptance threshold."
                    )
                ],
            )
            extend_unique(source_trail, [f"download:{provider_name}_assets_preview_accepted"])
        if preview_fallback_count:
            extend_unique(
                warnings,
                [
                    (
                        f"{provider_name.replace('_', ' ').title()} figure downloads fell back to preview images for "
                        f"{preview_fallback_count} asset(s) because full-size/original downloads were unavailable."
                    )
                ],
            )
            extend_unique(source_trail, [f"download:{provider_name}_assets_preview_fallback"])
    if artifacts.asset_failures:
        extend_unique(
            warnings,
            [f"{provider_name.replace('_', ' ').title()} related assets were only partially downloaded ({len(artifacts.asset_failures)} failed)."],
        )
        extend_unique(source_trail, [f"download:{provider_name}_asset_failures"])


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
            download_dir=download_dir,
            asset_profile=resolved_asset_profile,
        )
        extend_unique(warnings, provider_result.warnings)
        download_warnings, download_trail = maybe_save_provider_payload(
            provider_result.provider or provider_name,
            content=provider_result.content,
            download_dir=download_dir,
            doi=doi,
            metadata=metadata,
        )
        extend_unique(warnings, download_warnings)
        extend_unique(source_trail, download_trail)
        html_download_warnings, html_download_trail = maybe_save_provider_html_payload(
            provider_result.provider or provider_name,
            content=provider_result.content,
            download_dir=download_dir,
            doi=doi,
            metadata=metadata,
        )
        extend_unique(warnings, html_download_warnings)
        extend_unique(source_trail, html_download_trail)
        _apply_provider_artifacts(
            provider_name=provider_name,
            artifacts=provider_result.artifacts,
            download_dir=download_dir,
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
    download_dir: Path | None,
    clients: Mapping[str, Any] | None = None,
    transport: HttpTransport | None = None,
    env: Mapping[str, str] | None = None,
    resolve_paper_fn=None,
) -> ArticleModel:
    active_env = env or build_runtime_env()
    active_transport = transport or HttpTransport()
    client_registry = dict(clients or build_clients(active_transport, active_env))
    resolver = resolve_paper_fn or resolve_paper
    resolved = resolver(query, transport=active_transport, env=active_env)
    source_trail: list[str] = [f"resolve:{resolved.query_kind}"]
    if resolved.doi:
        source_trail.append("resolve:doi_selected")
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
    )
    extend_unique(source_trail, metadata_trail)
    from ..publisher_identity import normalize_doi

    doi = normalize_doi(safe_text(metadata.get("doi") or resolved.doi)) or None
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

    if provider_name in {"elsevier", "springer", "wiley", "science", "pnas"}:
        extend_unique(source_trail, [f"fallback:{provider_name}_html_managed_by_provider"])

    return _fallback_to_metadata_only(
        metadata=metadata,
        resolved=resolved,
        strategy=strategy,
        warnings=warnings,
        source_trail=source_trail,
    )
