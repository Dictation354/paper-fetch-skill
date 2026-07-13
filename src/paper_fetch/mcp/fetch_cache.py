"""MCP fetch-envelope cache abstraction."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

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
    coerce_body_quality_metrics,
    coerce_semantic_losses,
    coerce_token_estimate_breakdown,
)
from ..publisher_identity import normalize_doi
from ..reason_codes import METADATA_ONLY
from ..runtime import RuntimeContext
from ..tracing import TraceEvent, trace_event
from ..utils import normalize_text, sanitize_filename
from ..workflow.types import PaperFetchFailure
from ..workflow.acceptance import FetchAcceptanceReport, evaluate_fetch_acceptance
from ..workflow.types import effective_asset_profile
from .cache_index import (
    CACHE_INDEX_MODE_INDEX,
    CACHE_INDEX_MODE_RESCAN,
    CACHE_INDEX_MODE_REFRESH,
    CacheIndexResult,
    cache_file_lock,
    fetch_envelope_lock_path,
    list_cache_entries,
    preferred_cached_entries,
    read_cache_index,
    register_markdown_entry,
    refresh_cache_index_for_doi,
    refresh_cache_index_for_doi_result,
    rescan_cache_index,
)
from .schemas import FetchPaperRequest

FETCH_ENVELOPE_CACHE_VERSION = 2
FETCH_ENVELOPE_EXTRACTION_REVISION = EXTRACTION_REVISION


@dataclass(frozen=True)
class CacheSidecarInspection:
    summary: dict[str, Any]
    envelope: FetchEnvelope | None = None


def fetch_envelope_cache_path(download_dir: Path, doi: str) -> Path:
    normalized_doi = normalize_doi(doi) or normalize_text(doi)
    return download_dir / f"{sanitize_filename(normalized_doi)}.fetch-envelope.json"


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
) -> str:
    """Return the shared manifest fingerprint for cache request semantics."""

    return build_manifest_request_fingerprint(
        {
            "query": doi or "<invalid-doi>",
            "parameters": dict(request_payload),
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
        trace=trace_from_payload(payload.get("trace")),
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
    quality_payload = (
        payload.get("quality") if isinstance(payload.get("quality"), Mapping) else None
    )
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
        trace=trace_from_payload(payload.get("trace")),
        token_estimate=int(payload.get("token_estimate") or 0),
        token_estimate_breakdown=breakdown,
        quality=quality,
        article=article,
        markdown=payload.get("markdown"),
        metadata=metadata,
    )


def mark_envelope_cached_with_current_revision(envelope: FetchEnvelope) -> None:
    envelope.quality.flags = dedupe_quality_flags(
        [*envelope.quality.flags, QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION]
    )
    envelope.quality.extraction_revision = FETCH_ENVELOPE_EXTRACTION_REVISION
    envelope.warnings = list(envelope.quality.warnings)
    envelope.source_trail = list(envelope.quality.source_trail)
    envelope.trace = list(envelope.quality.trace)
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
        envelope.trace = list(envelope.article.quality.trace)
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
        entries = self._refresh_cache_index_for_doi(self.download_dir, doi)
        cached_entry = next(
            (
                entry
                for entry in sorted(
                    entries,
                    key=lambda item: float(item.get("mtime") or 0.0),
                    reverse=True,
                )
                if entry.get("kind") == "fetch_envelope"
            ),
            None,
        )
        if cached_entry is None:
            return None
        try:
            cache_path = Path(str(cached_entry["path"]))
            with cache_file_lock(fetch_envelope_lock_path(self.download_dir, doi)):
                cache_payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, KeyError):
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
        cached_request = cache_payload.get("request")
        payload = cache_payload.get("payload")
        if not isinstance(cached_request, Mapping) or not isinstance(payload, Mapping):
            return None
        if normalize_doi(str(payload.get("doi") or "")) != doi:
            return None
        if not cached_request_matches(cached_request, request):
            return None
        if not cached_payload_satisfies_request(payload, request):
            return None
        envelope = envelope_from_payload(payload)
        mark_envelope_cached_with_current_revision(envelope)
        return envelope

    def write_fetch_envelope(
        self, envelope: FetchEnvelope, request: FetchPaperRequest
    ) -> None:
        if self.download_dir is None:
            return
        doi = normalize_doi(normalize_text(envelope.doi))
        if not doi:
            return
        cache_path = fetch_envelope_cache_path(self.download_dir, doi)
        payload = {
            "version": FETCH_ENVELOPE_CACHE_VERSION,
            "extraction_revision": FETCH_ENVELOPE_EXTRACTION_REVISION,
            "request": request_cache_payload(request),
            "payload": payload_from_envelope(envelope, request),
        }
        with cache_file_lock(fetch_envelope_lock_path(self.download_dir, doi)):
            self._artifact_store.write_json_file(cache_path, payload)
        self._refresh_cache_index_for_doi(self.download_dir, doi)

    def register_markdown(
        self, path: Path, envelope: FetchEnvelope
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
            has_fulltext=envelope.has_fulltext,
            content_kind=str(envelope.content_kind),
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
        requested_fingerprint = cache_request_fingerprint(doi, requested_request)
        path = (
            fetch_envelope_cache_path(self.download_dir, doi)
            if self.download_dir is not None
            else None
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
            cached_fingerprint = cache_request_fingerprint(doi, cached_request_payload)
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

        request_matches = cached_request_matches(cached_request, request)
        payload_matches = cached_payload_satisfies_request(payload, request)
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
