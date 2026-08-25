"""MCP fetch-envelope cache abstraction."""

from __future__ import annotations

import json
import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..artifacts import ArtifactStore
from ..manifest import build_manifest_request_fingerprint
from ..models import (
    ArticleModel,
    Asset,
    EXTRACTION_REVISION,
    FetchEnvelope,
    Metadata,
    Quality,
    QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION,
    Reference,
    Section,
    TokenEstimateBreakdown,
    build_token_estimate_breakdown,
    coerce_asset_failure_diagnostics,
    coerce_asset_provenance,
    coerce_asset_quality_summary,
    coerce_acquisition_provenance,
    coerce_body_quality_metrics,
    coerce_semantic_losses,
    coerce_token_estimate_breakdown,
)
from ..publisher_identity import normalize_doi
from ..reason_codes import METADATA_ONLY
from ..runtime import RuntimeContext
from ..tracing import TraceContext, TraceEvent, trace_event
from ..utils import normalize_text, sanitize_filename
from ..workflow.types import PaperFetchFailure
from ..workflow.acceptance import (
    FetchAcceptanceReport,
    FetchAcceptanceStatus,
    IdentityAcceptanceStatus,
    OutputAcceptanceStatus,
    ProvenanceAcceptanceStatus,
    evaluate_fetch_acceptance,
)
from ..workflow.types import effective_asset_profile
from .cache_index import (
    CACHE_INDEX_MODE_INDEX,
    CACHE_INDEX_MODE_RESCAN,
    CACHE_INDEX_MODE_REFRESH,
    CacheIndexResult,
    _scoped_file,
    cache_file_lock,
    fetch_envelope_lock_path,
    list_cache_entries,
    preferred_cached_entries,
    read_cache_index,
    read_scoped_file,
    register_markdown_entry,
    refresh_cache_index_for_doi,
    refresh_cache_index_for_doi_result,
    rescan_cache_index,
)
from .schemas import FetchPaperRequest

FETCH_ENVELOPE_CACHE_VERSION = 5
FETCH_ENVELOPE_EXTRACTION_REVISION = EXTRACTION_REVISION
PUBLIC_CREDENTIAL_SCOPE = "public"
_CREDENTIAL_ENV_TOKENS = ("API_KEY", "APIKEY", "TOKEN", "ACCESS_KEY", "SECRET")


class _CacheRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    modes: list[str]
    strategy: dict[str, Any]
    include_refs: str | None
    max_tokens: int | str


class _CacheAcquisitionSchema(BaseModel):
    """Strict JSON shape used at the cache trust boundary."""

    model_config = ConfigDict(extra="forbid", strict=True)

    provider: str = Field(min_length=1)
    route: str = Field(min_length=1)
    representation: Literal["metadata", "html", "xml", "pdf"]
    transport: Literal["api", "browser", "http"]
    fallback_used: bool


class _CacheEnvelopePayloadSchema(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    doi: str
    source: str = Field(min_length=1)
    acquisition: _CacheAcquisitionSchema
    has_fulltext: bool
    content_kind: Literal["fulltext", "abstract_only", "metadata_only"]
    has_abstract: bool
    article: dict[str, Any] | None
    markdown: str | None
    metadata: dict[str, Any] | None

    @model_validator(mode="after")
    def validate_content_flags(self) -> _CacheEnvelopePayloadSchema:
        if self.has_fulltext != (self.content_kind == "fulltext"):
            raise ValueError("has_fulltext must match content_kind")
        if self.content_kind == "abstract_only" and not self.has_abstract:
            raise ValueError("abstract_only cache payload must have an abstract")
        return self


class _FetchEnvelopeSidecarSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: int
    extraction_revision: int
    request_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    credential_scope: str = PUBLIC_CREDENTIAL_SCOPE
    request: _CacheRequestSchema
    payload: _CacheEnvelopePayloadSchema

    @model_validator(mode="after")
    def validate_versions(self) -> _FetchEnvelopeSidecarSchema:
        if self.version != FETCH_ENVELOPE_CACHE_VERSION:
            raise ValueError("unsupported fetch-envelope cache version")
        if self.extraction_revision != FETCH_ENVELOPE_EXTRACTION_REVISION:
            raise ValueError("stale fetch-envelope extraction revision")
        return self


@dataclass(frozen=True)
class CacheSidecarInspection:
    summary: dict[str, Any]
    envelope: FetchEnvelope | None = None


def fetch_envelope_cache_path(download_dir: Path, doi: str) -> Path:
    normalized_doi = normalize_doi(doi) or normalize_text(doi)
    return download_dir / f"{sanitize_filename(normalized_doi)}.fetch-envelope.json"


def fetch_envelope_variant_path(
    download_dir: Path,
    doi: str,
    request_fingerprint: str,
) -> Path:
    normalized_doi = normalize_doi(doi) or normalize_text(doi)
    fingerprint = normalize_text(request_fingerprint).lower()
    if len(fingerprint) != 64 or any(
        char not in "0123456789abcdef" for char in fingerprint
    ):
        raise ValueError("request_fingerprint must be a lowercase SHA-256 digest")
    return download_dir / (
        f"{sanitize_filename(normalized_doi)}.{fingerprint}.fetch-envelope.json"
    )


def credential_scope_from_env(env: Mapping[str, str] | None) -> str:
    """Build a one-way capability scope for credential-backed cache payloads."""

    scoped_values: list[tuple[str, str]] = []
    for raw_name, raw_value in sorted((env or {}).items()):
        name = str(raw_name).upper()
        value = normalize_text(raw_value)
        if not value or name == "CROSSREF_MAILTO":
            continue
        if any(token in name for token in _CREDENTIAL_ENV_TOKENS):
            scoped_values.append((name, value))
            continue
        if "STORAGE_STATE" not in name:
            continue
        path = Path(value).expanduser()
        try:
            if path.is_file():
                scoped_values.append(
                    (name, hashlib.sha256(path.read_bytes()).hexdigest())
                )
        except OSError:
            scoped_values.append((name, value))
    if not scoped_values:
        return PUBLIC_CREDENTIAL_SCOPE
    digest = hashlib.sha256(
        json.dumps(
            scoped_values,
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return f"credential:{digest}"


def request_cache_payload(request: FetchPaperRequest) -> dict[str, Any]:
    return {
        "modes": sorted(request.requested_modes()),
        "strategy": request.strategy.cache_request_payload(),
        "include_refs": request.include_refs,
        "max_tokens": request.max_tokens,
    }


def cache_request_fingerprint(
    doi: str,
    request_payload: Mapping[str, Any],
    *,
    credential_scope: str = PUBLIC_CREDENTIAL_SCOPE,
) -> str:
    """Return the shared manifest fingerprint for cache request semantics."""

    return build_manifest_request_fingerprint(
        {
            "query": doi or "<invalid-doi>",
            "parameters": {
                **dict(request_payload),
                "credential_scope": normalize_text(credential_scope)
                or PUBLIC_CREDENTIAL_SCOPE,
            },
        }
    )


def _acceptance_summary(report: FetchAcceptanceReport) -> dict[str, Any]:
    payload = report.to_dict()
    return {
        "status": "evaluated",
        "overall": payload["overall"],
        "identity": payload["identity"]["status"],
        "fetch": payload["fetch"]["status"],
        "content": payload["content"]["status"],
        "asset": payload["asset"]["status"],
        "output": payload["output"]["status"],
        "provenance": payload["provenance"]["status"],
        "acquisition": payload["provenance"].get("acquisition"),
    }


def _warning_summary(
    envelope: FetchEnvelope | None,
    report: FetchAcceptanceReport | None,
) -> dict[str, Any]:
    if report is None:
        return {
            "messages": [],
            "fallback_codes": [],
            "warning_codes": [],
            "failure_codes": [],
            "unstructured_warning_count": 0,
        }
    provenance = report.provenance
    return {
        "messages": list(envelope.warnings if envelope is not None else ()),
        "fallback_codes": list(provenance.fallback_codes),
        "warning_codes": list(provenance.warning_codes),
        "failure_codes": list(provenance.failure_codes),
        "unstructured_warning_count": provenance.unstructured_warning_count,
    }


def _entry_summary(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    for entry in entries:
        kind = normalize_text(entry.get("kind")) or "unknown"
        by_kind[kind] = by_kind.get(kind, 0) + 1
    return {
        "total": len(entries),
        "by_kind": dict(sorted(by_kind.items())),
    }


def _reported_cache_version(value: Any) -> int | str | None:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int | str):
        return value
    return None


def payload_from_envelope(
    envelope: FetchEnvelope, request: FetchPaperRequest
) -> dict[str, Any]:
    payload = envelope.to_dict()
    payload["schema_version"] = 2
    if "article" not in request.requested_modes():
        payload["article"] = None
    return payload


def cached_request_matches(
    cached_request: Mapping[str, Any],
    request: FetchPaperRequest,
) -> bool:
    cached_modes = {str(item) for item in cached_request.get("modes") or []}
    if not request.requested_modes().issubset(cached_modes):
        return False
    if cached_request.get("strategy") != request.strategy.cache_request_payload():
        return False
    if cached_request.get("include_refs") != request.include_refs:
        return False
    return cached_request.get("max_tokens") == request.max_tokens


def cached_payload_satisfies_request(
    payload: Mapping[str, Any], request: FetchPaperRequest
) -> bool:
    requested_modes = request.requested_modes()
    if "article" in requested_modes and payload.get("article") is None:
        return False
    if "markdown" in requested_modes and payload.get("markdown") is None:
        return False
    if "metadata" in requested_modes and payload.get("metadata") is None:
        return False
    return True


def _cache_sidecar_schema_is_valid(payload: Mapping[str, Any]) -> bool:
    try:
        _FetchEnvelopeSidecarSchema.model_validate(payload)
    except Exception:
        return False
    return True


def _metadata_has_useful_content(metadata: Metadata | None) -> bool:
    if metadata is None:
        return False
    return bool(
        normalize_text(metadata.title)
        or normalize_text(metadata.abstract)
        or metadata.authors
        or normalize_text(metadata.journal)
        or normalize_text(metadata.published)
    )


def cached_envelope_satisfies_request(
    envelope: FetchEnvelope,
    payload: Mapping[str, Any],
    request: FetchPaperRequest,
    *,
    expected_doi: str,
) -> bool:
    """Apply structural, identity, semantic, and acceptance gates before reuse."""

    if not cached_payload_satisfies_request(payload, request):
        return False
    normalized_expected_doi = normalize_doi(expected_doi)
    if not normalized_expected_doi:
        return False
    if normalize_doi(envelope.doi or "") != normalized_expected_doi:
        return False
    if not normalize_text(envelope.source):
        return False
    if envelope.acquisition is None:
        return False
    if envelope.has_fulltext != (envelope.content_kind == "fulltext"):
        return False

    requested_modes = request.requested_modes()
    if "markdown" in requested_modes and not normalize_text(envelope.markdown):
        return False
    if "metadata" in requested_modes:
        raw_metadata = payload.get("metadata")
        if not isinstance(raw_metadata, Mapping) or not raw_metadata:
            return False
        if not _metadata_has_useful_content(envelope.metadata):
            return False
    if "article" in requested_modes:
        raw_article = payload.get("article")
        article = envelope.article
        if not isinstance(raw_article, Mapping) or not raw_article or article is None:
            return False
        if article.doi and normalize_doi(article.doi) != normalized_expected_doi:
            return False
        if not (
            _metadata_has_useful_content(article.metadata)
            or article.sections
            or article.references
        ):
            return False

    try:
        acceptance = evaluate_fetch_acceptance(
            envelope,
            asset_profile=effective_asset_profile(
                request.strategy.asset_profile,
                source_name=envelope.source,
            ),
            requested_outputs=requested_modes,
            expected_doi=normalized_expected_doi,
        )
    except Exception:
        return False
    return (
        acceptance.identity.status == IdentityAcceptanceStatus.RESOLVED
        and acceptance.fetch.status == FetchAcceptanceStatus.OK
        and acceptance.output.status == OutputAcceptanceStatus.COMPLETE
        and acceptance.provenance.status == ProvenanceAcceptanceStatus.COMPLETE
    )


def metadata_from_payload(value: Mapping[str, Any] | None) -> Metadata | None:
    if value is None:
        return None
    return Metadata(
        title=normalize_text(value.get("title")) or None,
        authors=[
            normalize_text(item)
            for item in value.get("authors") or []
            if normalize_text(item)
        ],
        abstract=normalize_text(value.get("abstract")) or None,
        journal=normalize_text(value.get("journal")) or None,
        article_type=normalize_text(value.get("article_type")) or None,
        published=normalize_text(value.get("published")) or None,
        keywords=[
            normalize_text(item)
            for item in value.get("keywords") or []
            if normalize_text(item)
        ],
        license_urls=[
            normalize_text(item)
            for item in value.get("license_urls") or []
            if normalize_text(item)
        ],
        landing_page_url=normalize_text(value.get("landing_page_url")) or None,
    )


def derived_breakdown(
    *,
    metadata: Metadata | None,
    sections: Sequence[Section],
    references: Sequence[Reference],
) -> TokenEstimateBreakdown:
    return build_token_estimate_breakdown(
        abstract_text=metadata.abstract if metadata is not None else None,
        sections=sections,
        references=references,
    )


def trace_from_payload(value: Any) -> list[TraceEvent]:
    if not isinstance(value, list):
        return []
    trace: list[TraceEvent] = []
    for entry in value:
        if not isinstance(entry, Mapping):
            continue
        trace.append(
            trace_event(
                normalize_text(entry.get("stage")) or "trace",
                normalize_text(entry.get("component")) or "unknown",
                normalize_text(entry.get("outcome")) or "info",
                code=normalize_text(entry.get("code")) or None,
                message=normalize_text(entry.get("message")) or None,
                context=TraceContext(
                    provider=normalize_text(entry.get("provider")) or None,
                    route=normalize_text(entry.get("route")) or None,
                    span_id=normalize_text(entry.get("span_id")) or None,
                    attempt_id=normalize_text(entry.get("attempt_id")) or None,
                    parent_span_id=normalize_text(entry.get("parent_span_id")) or None,
                    attempt=_coerce_cached_int(entry.get("attempt")),
                    http_status=_coerce_cached_int(entry.get("http_status")),
                    error_category=normalize_text(entry.get("error_category")) or None,
                    retryable=(
                        entry.get("retryable")
                        if isinstance(entry.get("retryable"), bool)
                        else None
                    ),
                    retry_after_seconds=_coerce_cached_int(
                        entry.get("retry_after_seconds")
                    ),
                    target=normalize_text(entry.get("target")) or None,
                    target_sha256=normalize_text(entry.get("target_sha256")) or None,
                    started_at=(
                        float(entry["started_at"])
                        if isinstance(entry.get("started_at"), int | float)
                        else None
                    ),
                    finished_at=(
                        float(entry["finished_at"])
                        if isinstance(entry.get("finished_at"), int | float)
                        else None
                    ),
                    duration_ms=(
                        float(entry["duration_ms"])
                        if isinstance(entry.get("duration_ms"), int | float)
                        else None
                    ),
                ),
            )
        )
    return trace


def dedupe_quality_flags(values: Sequence[str] | None) -> list[str]:
    return list(
        dict.fromkeys(
            normalize_text(item) for item in (values or []) if normalize_text(item)
        )
    )


def _coerce_cached_int(value: Any) -> int | None:
    text = str(value or "")
    return int(text) if text.isdigit() else None


def _cached_preview_accepted(entry: Mapping[str, Any]) -> bool:
    value = entry.get("preview_accepted")
    if isinstance(value, bool):
        return value
    if normalize_text(entry.get("download_tier")).lower() != "preview":
        return False
    from ..extraction.html.assets.dom import preview_dimensions_are_acceptable

    return preview_dimensions_are_acceptable(
        _coerce_cached_int(entry.get("width")) or 0,
        _coerce_cached_int(entry.get("height")) or 0,
    )


def quality_from_payload(value: Mapping[str, Any] | None) -> Quality:
    payload = value or {}
    from ..models.schema import ContentKind, QualityConfidence

    return Quality(
        has_fulltext=bool(payload.get("has_fulltext")),
        content_kind=cast(
            ContentKind, normalize_text(payload.get("content_kind")) or METADATA_ONLY
        ),
        has_abstract=bool(payload.get("has_abstract")),
        token_estimate=int(payload.get("token_estimate") or 0),
        warnings=[
            normalize_text(item)
            for item in payload.get("warnings") or []
            if normalize_text(item)
        ],
        source_trail=[
            normalize_text(item)
            for item in payload.get("source_trail") or []
            if normalize_text(item)
        ],
        token_estimate_breakdown=coerce_token_estimate_breakdown(
            payload.get("token_estimate_breakdown")
        ),
        confidence=cast(
            QualityConfidence, normalize_text(payload.get("confidence")) or "low"
        ),
        flags=dedupe_quality_flags(payload.get("flags") or []),
        body_metrics=coerce_body_quality_metrics(
            payload.get("body_metrics")
            if isinstance(payload.get("body_metrics"), Mapping)
            else None
        ),
        semantic_losses=coerce_semantic_losses(
            payload.get("semantic_losses")
            if isinstance(payload.get("semantic_losses"), Mapping)
            else None
        ),
        asset_failures=coerce_asset_failure_diagnostics(payload.get("asset_failures")),
        asset_summary=coerce_asset_quality_summary(payload.get("asset_summary")),
        extraction_revision=int(
            payload.get("extraction_revision") or FETCH_ENVELOPE_EXTRACTION_REVISION
        ),
    )


def article_from_payload(value: Mapping[str, Any] | None) -> ArticleModel | None:
    if value is None:
        return None
    metadata = metadata_from_payload(value.get("metadata"))
    if metadata is None:
        return None
    sections = [
        Section(
            heading=normalize_text(entry.get("heading")) or "",
            level=int(entry.get("level") or 0),
            kind=normalize_text(entry.get("kind")) or "body",
            text=normalize_text(entry.get("text")) or "",
        )
        for entry in value.get("sections") or []
        if isinstance(entry, Mapping)
    ]
    references = [
        Reference(
            raw=normalize_text(entry.get("raw")) or "",
            doi=normalize_text(entry.get("doi")) or None,
            title=normalize_text(entry.get("title")) or None,
            year=normalize_text(entry.get("year")) or None,
        )
        for entry in value.get("references") or []
        if isinstance(entry, Mapping) and normalize_text(entry.get("raw"))
    ]
    quality = quality_from_payload(
        value.get("quality") if isinstance(value.get("quality"), Mapping) else None
    )
    if quality.token_estimate_breakdown == TokenEstimateBreakdown():
        quality.token_estimate_breakdown = derived_breakdown(
            metadata=metadata,
            sections=sections,
            references=references,
        )
    from ..models.schema import SourceKind

    return ArticleModel(
        doi=normalize_text(value.get("doi")) or None,
        source=cast(SourceKind, normalize_text(value.get("source")) or "crossref_meta"),
        metadata=metadata,
        acquisition=coerce_acquisition_provenance(value.get("acquisition")),
        sections=sections,
        references=references,
        assets=[
            Asset(
                kind=normalize_text(entry.get("kind")) or "",
                heading=normalize_text(entry.get("heading")) or "",
                caption=normalize_text(entry.get("caption")) or None,
                url=normalize_text(entry.get("url")) or None,
                path=normalize_text(entry.get("path")) or None,
                section=normalize_text(entry.get("section")) or None,
                render_state=normalize_text(entry.get("render_state")) or None,
                anchor_key=normalize_text(entry.get("anchor_key")) or None,
                download_tier=normalize_text(entry.get("download_tier")) or None,
                download_url=normalize_text(entry.get("download_url")) or None,
                original_url=normalize_text(entry.get("original_url")) or None,
                source_url=normalize_text(entry.get("source_url")) or None,
                source_path=normalize_text(entry.get("source_path")) or None,
                source_href=normalize_text(entry.get("source_href")) or None,
                content_type=normalize_text(entry.get("content_type")) or None,
                downloaded_bytes=_coerce_cached_int(entry.get("downloaded_bytes")),
                width=_coerce_cached_int(entry.get("width")),
                height=_coerce_cached_int(entry.get("height")),
                preview_accepted=_cached_preview_accepted(entry),
                browser_backend=normalize_text(entry.get("browser_backend")) or None,
                final_fetcher=normalize_text(entry.get("final_fetcher")) or None,
                recovery_attempts=[
                    dict(attempt)
                    for attempt in entry.get("recovery_attempts") or []
                    if isinstance(attempt, Mapping)
                ],
                provenance=coerce_asset_provenance(entry.get("provenance")),
            )
            for entry in value.get("assets") or []
            if isinstance(entry, Mapping)
        ],
        quality=quality,
    )


def envelope_from_payload(payload: Mapping[str, Any]) -> FetchEnvelope:
    article = article_from_payload(
        payload.get("article") if isinstance(payload.get("article"), Mapping) else None
    )
    metadata = metadata_from_payload(
        payload.get("metadata")
        if isinstance(payload.get("metadata"), Mapping)
        else None
    )
    breakdown = coerce_token_estimate_breakdown(payload.get("token_estimate_breakdown"))
    raw_quality_payload = payload.get("quality")
    quality_payload: Mapping[str, Any] | None = (
        raw_quality_payload if isinstance(raw_quality_payload, Mapping) else None
    )
    raw_article_payload = payload.get("article")
    article_payload: Mapping[str, Any] = (
        raw_article_payload if isinstance(raw_article_payload, Mapping) else {}
    )
    raw_article_quality_payload = article_payload.get("quality")
    article_quality_payload: Mapping[str, Any] = (
        raw_article_quality_payload
        if isinstance(raw_article_quality_payload, Mapping)
        else {}
    )
    trace = trace_from_payload(payload.get("trace"))
    if not trace:
        trace = trace_from_payload(
            quality_payload.get("trace") if quality_payload is not None else None
        )
    if not trace:
        trace = trace_from_payload(article_quality_payload.get("trace"))
    quality = quality_from_payload(quality_payload)
    if breakdown == TokenEstimateBreakdown():
        if article is not None:
            breakdown = article.quality.token_estimate_breakdown
        elif metadata is not None:
            breakdown = derived_breakdown(metadata=metadata, sections=[], references=[])
    if quality.token_estimate_breakdown == TokenEstimateBreakdown():
        quality.token_estimate_breakdown = breakdown
    if quality.token_estimate == 0:
        quality.token_estimate = int(payload.get("token_estimate") or 0)
    if article is not None and not quality.flags and quality_payload is None:
        quality = article.quality
    from ..models.schema import ContentKind, SourceKind

    return FetchEnvelope(
        doi=normalize_text(payload.get("doi")) or None,
        source=cast(SourceKind, normalize_text(payload.get("source")) or METADATA_ONLY),
        has_fulltext=bool(payload.get("has_fulltext")),
        acquisition=coerce_acquisition_provenance(payload.get("acquisition")),
        content_kind=cast(
            ContentKind, normalize_text(payload.get("content_kind")) or METADATA_ONLY
        ),
        has_abstract=bool(payload.get("has_abstract")),
        warnings=[
            normalize_text(item)
            for item in payload.get("warnings") or []
            if normalize_text(item)
        ],
        source_trail=[
            normalize_text(item)
            for item in payload.get("source_trail") or []
            if normalize_text(item)
        ],
        trace=trace,
        token_estimate=int(payload.get("token_estimate") or 0),
        token_estimate_breakdown=breakdown,
        quality=quality,
        article=article,
        markdown=payload.get("markdown"),
        metadata=metadata,
        diagnostic_artifacts=[
            dict(item)
            for item in payload.get("diagnostic_artifacts") or []
            if isinstance(item, Mapping)
        ],
    )


def _asset_integrity(
    article: ArticleModel, asset: Asset
) -> tuple[int | None, str | None]:
    expected_size = asset.downloaded_bytes
    expected_hash: str | None = None
    asset_path = normalize_text(asset.path)
    for diagnostic in article.quality.asset_summary.diagnostics:
        if normalize_text(diagnostic.path) != asset_path:
            continue
        if diagnostic.byte_count is not None:
            expected_size = diagnostic.byte_count
        expected_hash = normalize_text(diagnostic.sha256) or None
        break
    return expected_size, expected_hash


def cached_envelope_assets_are_scoped(
    envelope: FetchEnvelope, download_dir: Path
) -> bool:
    article = envelope.article
    if article is None:
        return True
    for asset in article.assets:
        path_text = normalize_text(asset.path)
        if path_text:
            expected_size, expected_hash = _asset_integrity(article, asset)
            opened = read_scoped_file(
                download_dir,
                path_text,
                expected_size=expected_size,
                expected_sha256=expected_hash,
            )
            if opened is None:
                return False
            asset.path = str(opened[0])
        source_path = normalize_text(asset.source_path)
        if source_path and _scoped_file(download_dir, source_path) is None:
            return False
    return True


def mark_envelope_cached_with_current_revision(envelope: FetchEnvelope) -> None:
    envelope.quality.flags = dedupe_quality_flags(
        [*envelope.quality.flags, QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION]
    )
    envelope.quality.extraction_revision = FETCH_ENVELOPE_EXTRACTION_REVISION
    envelope.warnings = list(envelope.quality.warnings)
    envelope.source_trail = list(envelope.quality.source_trail)
    envelope.token_estimate = envelope.quality.token_estimate
    envelope.token_estimate_breakdown = envelope.quality.token_estimate_breakdown
    if envelope.article is not None:
        envelope.article.quality.flags = dedupe_quality_flags(
            [*envelope.article.quality.flags, QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION]
        )
        envelope.article.quality.extraction_revision = (
            FETCH_ENVELOPE_EXTRACTION_REVISION
        )
        envelope.quality = envelope.article.quality
        envelope.warnings = list(envelope.article.quality.warnings)
        envelope.source_trail = list(envelope.article.quality.source_trail)
        envelope.token_estimate = envelope.article.quality.token_estimate
        envelope.token_estimate_breakdown = (
            envelope.article.quality.token_estimate_breakdown
        )


class FetchCache:
    """Cache facade for MCP fetch-envelope sidecars and cache index refresh."""

    def __init__(
        self,
        download_dir: Path | None,
        *,
        artifact_store: ArtifactStore | None = None,
        refresh_cache_index_for_doi_fn: Callable[
            [Path, str], list[dict[str, Any]]
        ] = refresh_cache_index_for_doi,
        refresh_cache_index_for_doi_result_fn: Callable[
            [Path, str], CacheIndexResult
        ] = refresh_cache_index_for_doi_result,
        read_cache_index_fn: Callable[..., CacheIndexResult] = read_cache_index,
        rescan_cache_index_fn: Callable[[Path], CacheIndexResult] = rescan_cache_index,
        list_cache_entries_fn: Callable[
            [Path], list[dict[str, Any]]
        ] = list_cache_entries,
        preferred_cached_entries_fn: Callable[
            [list[dict[str, Any]]], dict[str, Any]
        ] = preferred_cached_entries,
        register_markdown_entry_fn: Callable[..., dict[str, Any] | None] = (
            register_markdown_entry
        ),
        credential_scope: str = PUBLIC_CREDENTIAL_SCOPE,
    ) -> None:
        self._artifact_store = artifact_store or ArtifactStore.from_download_dir(
            download_dir
        )
        self.download_dir = self._artifact_store.download_dir
        self._refresh_cache_index_for_doi = refresh_cache_index_for_doi_fn
        self._refresh_cache_index_for_doi_result = refresh_cache_index_for_doi_result_fn
        self._read_cache_index = read_cache_index_fn
        self._rescan_cache_index = rescan_cache_index_fn
        self._list_cache_entries = list_cache_entries_fn
        self._preferred_cached_entries = preferred_cached_entries_fn
        self._register_markdown_entry = register_markdown_entry_fn
        self.credential_scope = (
            normalize_text(credential_scope) or PUBLIC_CREDENTIAL_SCOPE
        )

    def _candidate_sidecar_paths(
        self,
        doi: str,
        request: FetchPaperRequest,
    ) -> list[Path]:
        if self.download_dir is None:
            return []
        requested_fingerprint = cache_request_fingerprint(
            doi,
            request_cache_payload(request),
            credential_scope=self.credential_scope,
        )
        exact = fetch_envelope_variant_path(
            self.download_dir, doi, requested_fingerprint
        )
        base = sanitize_filename(doi)

        def modified_at(path: Path) -> float:
            try:
                return path.stat().st_mtime
            except OSError:
                return 0.0

        variants = sorted(
            self.download_dir.glob(f"{base}.*.fetch-envelope.json"),
            key=modified_at,
            reverse=True,
        )
        canonical = fetch_envelope_cache_path(self.download_dir, doi)
        return list(dict.fromkeys([exact, *variants, canonical]))

    def _load_sidecar_path(
        self,
        path: Path,
        *,
        doi: str,
        request: FetchPaperRequest,
    ) -> FetchEnvelope | None:
        if self.download_dir is None:
            return None
        scoped_path = _scoped_file(self.download_dir, str(path))
        if scoped_path is None:
            return None
        try:
            cache_payload = json.loads(scoped_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(cache_payload, Mapping):
            return None
        if cache_payload.get("version") != FETCH_ENVELOPE_CACHE_VERSION:
            return None
        if (
            cache_payload.get("extraction_revision")
            != FETCH_ENVELOPE_EXTRACTION_REVISION
        ):
            return None
        if not _cache_sidecar_schema_is_valid(cache_payload):
            return None
        cached_scope = (
            normalize_text(cache_payload.get("credential_scope"))
            or PUBLIC_CREDENTIAL_SCOPE
        )
        if cached_scope != self.credential_scope:
            return None
        cached_request = cache_payload.get("request")
        payload = cache_payload.get("payload")
        if not isinstance(cached_request, Mapping) or not isinstance(payload, Mapping):
            return None
        if normalize_doi(str(payload.get("doi") or "")) != doi:
            return None
        if not cached_request_matches(cached_request, request):
            return None
        try:
            envelope = envelope_from_payload(payload)
        except Exception:
            return None
        if not cached_envelope_assets_are_scoped(envelope, self.download_dir):
            return None
        if not cached_envelope_satisfies_request(
            envelope,
            payload,
            request,
            expected_doi=doi,
        ):
            return None
        return envelope

    def load_fetch_envelope(
        self,
        request: FetchPaperRequest,
        *,
        resolve_paper_fn: Callable[..., Any],
        context: RuntimeContext,
    ) -> FetchEnvelope | None:
        if not request.prefer_cache or self.download_dir is None:
            return None
        resolved = resolve_paper_fn(request.query, context=context)
        if resolved.candidates and not resolved.doi:
            raise PaperFetchFailure(
                "ambiguous",
                "Query resolution is ambiguous; choose one of the DOI candidates.",
                candidates=resolved.candidates,
            )
        doi = normalize_doi(normalize_text(resolved.doi))
        if not doi:
            return None
        self._refresh_cache_index_for_doi(self.download_dir, doi)
        envelope = None
        with cache_file_lock(fetch_envelope_lock_path(self.download_dir, doi)):
            for cache_path in self._candidate_sidecar_paths(doi, request):
                envelope = self._load_sidecar_path(
                    cache_path,
                    doi=doi,
                    request=request,
                )
                if envelope is not None:
                    break
        if envelope is None:
            return None
        mark_envelope_cached_with_current_revision(envelope)
        return envelope

    def write_fetch_envelope(
        self,
        envelope: FetchEnvelope,
        request: FetchPaperRequest,
        *,
        commit_guard: Callable[[], None] | None = None,
    ) -> None:
        if self.download_dir is None:
            return
        doi = normalize_doi(normalize_text(envelope.doi))
        if not doi:
            return
        request_payload = request_cache_payload(request)
        request_fingerprint = cache_request_fingerprint(
            doi,
            request_payload,
            credential_scope=self.credential_scope,
        )
        cache_path = fetch_envelope_cache_path(self.download_dir, doi)
        variant_path = fetch_envelope_variant_path(
            self.download_dir,
            doi,
            request_fingerprint,
        )
        payload = {
            "version": FETCH_ENVELOPE_CACHE_VERSION,
            "extraction_revision": FETCH_ENVELOPE_EXTRACTION_REVISION,
            "request_fingerprint": request_fingerprint,
            "credential_scope": self.credential_scope,
            "request": request_payload,
            "payload": payload_from_envelope(envelope, request),
        }
        with cache_file_lock(fetch_envelope_lock_path(self.download_dir, doi)):
            self._artifact_store.write_json_file(
                variant_path,
                payload,
                commit_guard=commit_guard,
            )
            self._artifact_store.write_json_file(
                cache_path,
                payload,
                commit_guard=commit_guard,
            )
        if commit_guard is not None:
            commit_guard()
        self._refresh_cache_index_for_doi(self.download_dir, doi)

    def register_markdown(
        self,
        path: Path,
        envelope: FetchEnvelope,
        *,
        commit_guard: Callable[[], None] | None = None,
    ) -> dict[str, Any] | None:
        """Register a saved Markdown file with identity known from its envelope."""

        if self.download_dir is None:
            return None
        doi = normalize_doi(normalize_text(envelope.doi))
        if not doi:
            return None
        return self._register_markdown_entry(
            self.download_dir,
            doi,
            path,
            source=str(envelope.source),
            acquisition=envelope.acquisition,
            has_fulltext=envelope.has_fulltext,
            content_kind=str(envelope.content_kind),
            commit_guard=commit_guard,
        )

    def refresh_for_doi(self, doi: str) -> list[dict[str, Any]]:
        if self.download_dir is None:
            return []
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            return []
        return self._refresh_cache_index_for_doi(self.download_dir, normalized_doi)

    def list_payload(
        self, *, cache_mode: str = CACHE_INDEX_MODE_INDEX
    ) -> dict[str, Any]:
        if self.download_dir is None:
            return {
                "download_dir": None,
                "entries": [],
                "cache_mode": cache_mode,
                "index_status": "unavailable",
                "index_version": None,
                "expected_index_version": None,
                "index_reason": "download directory is disabled",
            }
        if cache_mode == CACHE_INDEX_MODE_RESCAN:
            result = self._rescan_cache_index(self.download_dir)
        elif cache_mode == CACHE_INDEX_MODE_REFRESH:
            result = self._read_cache_index(
                self.download_dir, refresh=True, cache_mode=CACHE_INDEX_MODE_REFRESH
            )
        else:
            result = self._read_cache_index(
                self.download_dir, refresh=False, cache_mode=CACHE_INDEX_MODE_INDEX
            )
        return {
            "download_dir": str(self.download_dir),
            "entries": result.entries,
            **result.metadata(),
        }

    def _inspect_fetch_envelope_sidecar(
        self,
        doi: str,
        request: FetchPaperRequest,
    ) -> CacheSidecarInspection:
        requested_request = request_cache_payload(request)
        requested_fingerprint = cache_request_fingerprint(
            doi,
            requested_request,
            credential_scope=self.credential_scope,
        )
        candidate_paths = self._candidate_sidecar_paths(doi, request)
        path = next(
            (candidate for candidate in candidate_paths if candidate.exists()), None
        )
        if path is None and self.download_dir is not None:
            path = fetch_envelope_variant_path(
                self.download_dir,
                doi,
                requested_fingerprint,
            )
        base: dict[str, Any] = {
            "status": "missing",
            "reason_code": "cache_sidecar_missing",
            "reason": "No fetch-envelope sidecar exists in the selected cache scope.",
            "path": str(path) if path is not None else None,
            "version": None,
            "expected_version": FETCH_ENVELOPE_CACHE_VERSION,
            "extraction_revision": None,
            "expected_extraction_revision": FETCH_ENVELOPE_EXTRACTION_REVISION,
            "cached_request": None,
            "cached_request_fingerprint": None,
            "requested_request": requested_request,
            "requested_request_fingerprint": requested_fingerprint,
            "request_matches": False,
            "payload_satisfies_request": False,
            "request_satisfied": False,
            "request_status": "unavailable",
        }

        def finish(
            status: str,
            reason_code: str,
            reason: str,
            *,
            updates: Mapping[str, Any] | None = None,
            envelope: FetchEnvelope | None = None,
        ) -> CacheSidecarInspection:
            summary = {
                **base,
                "status": status,
                "reason_code": reason_code,
                "reason": reason,
                **dict(updates or {}),
            }
            return CacheSidecarInspection(summary=summary, envelope=envelope)

        if self.download_dir is None or path is None:
            return finish(
                "disabled",
                "cache_scope_disabled",
                "The selected cache scope is disabled.",
            )
        if not path.exists():
            return finish(
                "missing",
                "cache_sidecar_missing",
                "No fetch-envelope sidecar exists in the selected cache scope.",
            )
        try:
            resolved_root = self.download_dir.expanduser().resolve()
            resolved_path = path.expanduser().resolve()
            resolved_path.relative_to(resolved_root)
        except (OSError, ValueError):
            return finish(
                "invalid_scope",
                "cache_sidecar_outside_scope",
                "The fetch-envelope sidecar resolves outside the selected cache scope.",
            )
        if not resolved_path.is_file():
            return finish(
                "invalid",
                "cache_sidecar_not_file",
                "The expected fetch-envelope sidecar is not a regular file.",
            )
        try:
            with cache_file_lock(fetch_envelope_lock_path(self.download_dir, doi)):
                cache_payload = json.loads(resolved_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return finish(
                "corrupt",
                "cache_sidecar_invalid_json",
                "The fetch-envelope sidecar is not valid JSON.",
            )
        except OSError:
            return finish(
                "unreadable",
                "cache_sidecar_unreadable",
                "The fetch-envelope sidecar could not be read.",
            )
        if not isinstance(cache_payload, Mapping):
            return finish(
                "invalid",
                "cache_sidecar_invalid_shape",
                "The fetch-envelope sidecar root must be an object.",
            )

        cached_scope = (
            normalize_text(cache_payload.get("credential_scope"))
            or PUBLIC_CREDENTIAL_SCOPE
        )
        if cached_scope != self.credential_scope:
            return finish(
                "credential_scope_mismatch",
                "cache_sidecar_credential_scope_mismatch",
                "The fetch-envelope sidecar belongs to a different credential scope.",
            )

        version = cache_payload.get("version")
        extraction_revision = cache_payload.get("extraction_revision")
        version_updates = {
            "version": _reported_cache_version(version),
            "extraction_revision": _reported_cache_version(extraction_revision),
        }
        if version != FETCH_ENVELOPE_CACHE_VERSION:
            return finish(
                "version_mismatch",
                "cache_sidecar_version_mismatch",
                "The fetch-envelope sidecar version is not supported.",
                updates=version_updates,
            )
        if extraction_revision != FETCH_ENVELOPE_EXTRACTION_REVISION:
            return finish(
                "extraction_revision_mismatch",
                "cache_sidecar_extraction_revision_mismatch",
                "The fetch-envelope extraction revision is stale.",
                updates=version_updates,
            )
        if not _cache_sidecar_schema_is_valid(cache_payload):
            return finish(
                "invalid",
                "cache_sidecar_schema_invalid",
                "The fetch-envelope sidecar does not satisfy the current schema.",
                updates=version_updates,
            )

        cached_request = cache_payload.get("request")
        payload = cache_payload.get("payload")
        if not isinstance(cached_request, Mapping) or not isinstance(payload, Mapping):
            return finish(
                "invalid",
                "cache_sidecar_missing_request_or_payload",
                "The fetch-envelope sidecar lacks a structured request or payload.",
                updates=version_updates,
            )
        cached_request_payload = dict(cached_request)
        try:
            cached_fingerprint = cache_request_fingerprint(
                doi,
                cached_request_payload,
                credential_scope=cached_scope,
            )
        except (TypeError, ValueError):
            return finish(
                "invalid",
                "cache_sidecar_request_not_canonical_json",
                "The cached request cannot be represented as canonical JSON.",
                updates=version_updates,
            )
        request_updates = {
            **version_updates,
            "cached_request": cached_request_payload,
            "cached_request_fingerprint": cached_fingerprint,
        }
        if normalize_doi(str(payload.get("doi") or "")) != doi:
            return finish(
                "doi_mismatch",
                "cache_sidecar_doi_mismatch",
                "The fetch-envelope payload DOI does not match the requested DOI.",
                updates=request_updates,
            )
        try:
            envelope = envelope_from_payload(payload)
        except Exception:  # noqa: BLE001 - local cache corruption is reported.
            return finish(
                "invalid",
                "cache_sidecar_payload_invalid",
                "The fetch-envelope payload could not be reconstructed.",
                updates=request_updates,
            )
        if not cached_envelope_assets_are_scoped(envelope, self.download_dir):
            return finish(
                "invalid",
                "cache_sidecar_asset_scope_or_integrity_mismatch",
                (
                    "A cached asset resolves outside the cache scope or no longer "
                    "matches its recorded size/hash."
                ),
                updates=request_updates,
            )

        request_matches = cached_request_matches(cached_request, request)
        payload_matches = cached_envelope_satisfies_request(
            envelope,
            payload,
            request,
            expected_doi=doi,
        )
        satisfied = request_matches and payload_matches
        match_updates = {
            **request_updates,
            "request_matches": request_matches,
            "payload_satisfies_request": payload_matches,
            "request_satisfied": satisfied,
            "request_status": "satisfied" if satisfied else "mismatch",
        }
        if not request_matches:
            return finish(
                "ready",
                "cached_request_mismatch",
                "A valid sidecar exists, but its cached request does not match the current request.",
                updates=match_updates,
                envelope=envelope,
            )
        if not payload_matches:
            return finish(
                "ready",
                "cached_payload_missing_requested_modes",
                "The cached payload does not contain every currently requested output mode.",
                updates=match_updates,
                envelope=envelope,
            )
        return finish(
            "ready",
            "cached_request_satisfied",
            "The valid fetch-envelope sidecar satisfies the current request.",
            updates=match_updates,
            envelope=envelope,
        )

    def get_payload(
        self,
        doi: str,
        *,
        request: FetchPaperRequest | None = None,
        detail: str = "full",
        preferred_only: bool = False,
    ) -> dict[str, Any]:
        normalized_doi = normalize_doi(doi)
        if self.download_dir is None:
            entries: list[dict[str, Any]] = []
            index_metadata: dict[str, Any] = {
                "cache_mode": CACHE_INDEX_MODE_REFRESH,
                "index_status": "unavailable",
                "index_version": None,
                "expected_index_version": None,
                "index_reason": "download directory is disabled",
            }
        else:
            result = self._refresh_cache_index_for_doi_result(
                self.download_dir, normalized_doi
            )
            entries = result.entries
            index_metadata = result.metadata()
        preferred = self._preferred_cached_entries(entries)
        base_payload = {
            "status": "hit" if entries else "miss",
            "doi": normalized_doi,
            "download_dir": str(self.download_dir)
            if self.download_dir is not None
            else None,
            "entries": entries,
            "preferred": preferred,
            **index_metadata,
        }
        if request is None:
            return base_payload

        sidecar = self._inspect_fetch_envelope_sidecar(normalized_doi, request)
        envelope = sidecar.envelope
        acceptance: FetchAcceptanceReport | None = None
        acceptance_reason: str | None = sidecar.summary["reason_code"]
        if envelope is not None:
            try:
                acceptance = evaluate_fetch_acceptance(
                    envelope,
                    asset_profile=effective_asset_profile(
                        request.strategy.asset_profile,
                        source_name=envelope.source,
                    ),
                    requested_outputs=request.requested_modes(),
                    expected_doi=normalized_doi,
                )
                acceptance_reason = None
            except Exception:  # noqa: BLE001 - report malformed local cache facts.
                acceptance_reason = "cached_acceptance_invalid"

        entry_summary = _entry_summary(entries)
        preferred_markdown = preferred.get("markdown")
        content_kind = (
            str(envelope.content_kind)
            if envelope is not None
            else (
                str(preferred_markdown.get("content_kind"))
                if isinstance(preferred_markdown, Mapping)
                and preferred_markdown.get("content_kind") is not None
                else None
            )
        )
        has_fulltext = (
            envelope.has_fulltext
            if envelope is not None
            else (
                preferred_markdown.get("has_fulltext")
                if isinstance(preferred_markdown, Mapping)
                and isinstance(preferred_markdown.get("has_fulltext"), bool)
                else None
            )
        )
        confidence = str(envelope.quality.confidence) if envelope is not None else None
        acquisition = (
            asdict(envelope.acquisition)
            if envelope is not None and envelope.acquisition is not None
            else (
                preferred_markdown.get("acquisition")
                if isinstance(preferred_markdown, Mapping)
                else None
            )
        )
        acceptance_summary = (
            _acceptance_summary(acceptance)
            if acceptance is not None
            else {
                "status": "not_evaluated",
                "overall": None,
                "reason_code": acceptance_reason,
            }
        )
        asset_summary = (
            acceptance.asset.model_dump(mode="json")
            if acceptance is not None
            else {
                "status": "indexed_only",
                "total": entry_summary["by_kind"].get("asset", 0),
            }
        )
        scope_status = (
            "disabled"
            if self.download_dir is None
            else "available"
            if self.download_dir.exists()
            else "missing"
        )
        summary_fields = {
            "detail": detail,
            "preferred_only": preferred_only,
            "scope_status": scope_status,
            "identity_status": "proven" if entries else "no_proven_entries",
            "has_entries": bool(entries),
            "entry_summary": entry_summary,
            "content_kind": content_kind,
            "has_fulltext": has_fulltext,
            "confidence": confidence,
            "acquisition": acquisition,
            "acceptance": acceptance_summary,
            "asset_summary": asset_summary,
            "warning_summary": _warning_summary(envelope, acceptance),
            "sidecar": sidecar.summary,
            "cached_request": sidecar.summary["cached_request"],
            "cached_request_fingerprint": sidecar.summary["cached_request_fingerprint"],
            "requested_request": sidecar.summary["requested_request"],
            "requested_request_fingerprint": sidecar.summary[
                "requested_request_fingerprint"
            ],
            "request_status": sidecar.summary["request_status"],
            "request_satisfied": sidecar.summary["request_satisfied"],
        }

        compact_preferred = {
            "markdown": preferred.get("markdown"),
            "primary_payload": preferred.get("primary_payload"),
        }
        if detail == "compact":
            return {
                key: value
                for key, value in {
                    "status": base_payload["status"],
                    "doi": normalized_doi,
                    "download_dir": base_payload["download_dir"],
                    "preferred": compact_preferred,
                    **index_metadata,
                    **summary_fields,
                }.items()
                if key != "entries"
            }

        if preferred_only:
            selected_entries: list[dict[str, Any]] = []
            selected_ids: set[str] = set()
            for key in ("markdown", "primary_payload"):
                entry = preferred.get(key)
                if not isinstance(entry, dict):
                    continue
                entry_id = str(entry.get("id") or entry.get("path") or "")
                if entry_id in selected_ids:
                    continue
                selected_ids.add(entry_id)
                selected_entries.append(entry)
            return {
                **base_payload,
                "entries": selected_entries,
                "preferred": {**compact_preferred, "assets": []},
                **summary_fields,
            }
        return {**base_payload, **summary_fields}
