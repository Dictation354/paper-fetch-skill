"""MCP fetch-envelope cache abstraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..http import HttpTransport
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
    coerce_body_quality_metrics,
    coerce_semantic_losses,
    coerce_token_estimate_breakdown,
)
from ..tracing import TraceEvent, trace_event
from ..utils import normalize_text, sanitize_filename
from ..workflow.types import PaperFetchFailure
from .cache_index import (
    cache_file_lock,
    fetch_envelope_lock_path,
    list_cache_entries,
    preferred_cached_entries,
    refresh_cache_index_for_doi,
)
from .schemas import FetchPaperRequest

FETCH_ENVELOPE_CACHE_VERSION = 2
FETCH_ENVELOPE_EXTRACTION_REVISION = EXTRACTION_REVISION


def fetch_envelope_cache_path(download_dir: Path, doi: str) -> Path:
    return download_dir / f"{sanitize_filename(doi)}.fetch-envelope.json"


def request_cache_payload(request: FetchPaperRequest) -> dict[str, Any]:
    return {
        "modes": list(request.modes),
        "strategy": request.strategy.cache_request_payload(),
        "include_refs": request.include_refs,
        "max_tokens": request.max_tokens,
    }


def payload_from_envelope(envelope: FetchEnvelope, request: FetchPaperRequest) -> dict[str, Any]:
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


def cached_payload_satisfies_request(payload: Mapping[str, Any], request: FetchPaperRequest) -> bool:
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
        authors=[normalize_text(item) for item in value.get("authors") or [] if normalize_text(item)],
        abstract=normalize_text(value.get("abstract")) or None,
        journal=normalize_text(value.get("journal")) or None,
        published=normalize_text(value.get("published")) or None,
        keywords=[normalize_text(item) for item in value.get("keywords") or [] if normalize_text(item)],
        license_urls=[normalize_text(item) for item in value.get("license_urls") or [] if normalize_text(item)],
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
    return list(dict.fromkeys(normalize_text(item) for item in (values or []) if normalize_text(item)))


def quality_from_payload(value: Mapping[str, Any] | None) -> Quality:
    payload = value or {}
    return Quality(
        has_fulltext=bool(payload.get("has_fulltext")),
        content_kind=normalize_text(payload.get("content_kind")) or "metadata_only",
        has_abstract=bool(payload.get("has_abstract")),
        token_estimate=int(payload.get("token_estimate") or 0),
        warnings=[normalize_text(item) for item in payload.get("warnings") or [] if normalize_text(item)],
        source_trail=[normalize_text(item) for item in payload.get("source_trail") or [] if normalize_text(item)],
        trace=trace_from_payload(payload.get("trace")),
        token_estimate_breakdown=coerce_token_estimate_breakdown(payload.get("token_estimate_breakdown")),
        confidence=normalize_text(payload.get("confidence")) or "low",
        flags=dedupe_quality_flags(payload.get("flags") or []),
        body_metrics=coerce_body_quality_metrics(
            payload.get("body_metrics") if isinstance(payload.get("body_metrics"), Mapping) else None
        ),
        semantic_losses=coerce_semantic_losses(
            payload.get("semantic_losses") if isinstance(payload.get("semantic_losses"), Mapping) else None
        ),
        extraction_revision=int(payload.get("extraction_revision") or FETCH_ENVELOPE_EXTRACTION_REVISION),
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
    quality = quality_from_payload(value.get("quality") if isinstance(value.get("quality"), Mapping) else None)
    if quality.token_estimate_breakdown == TokenEstimateBreakdown():
        quality.token_estimate_breakdown = derived_breakdown(
            metadata=metadata,
            sections=sections,
            references=references,
        )
    return ArticleModel(
        doi=normalize_text(value.get("doi")) or None,
        source=normalize_text(value.get("source")) or "crossref_meta",
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
                content_type=normalize_text(entry.get("content_type")) or None,
                downloaded_bytes=int(entry.get("downloaded_bytes")) if str(entry.get("downloaded_bytes") or "").isdigit() else None,
                width=int(entry.get("width")) if str(entry.get("width") or "").isdigit() else None,
                height=int(entry.get("height")) if str(entry.get("height") or "").isdigit() else None,
            )
            for entry in value.get("assets") or []
            if isinstance(entry, Mapping)
        ],
        quality=quality,
    )


def envelope_from_payload(payload: Mapping[str, Any]) -> FetchEnvelope:
    article = article_from_payload(payload.get("article") if isinstance(payload.get("article"), Mapping) else None)
    metadata = metadata_from_payload(payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else None)
    breakdown = coerce_token_estimate_breakdown(payload.get("token_estimate_breakdown"))
    quality_payload = payload.get("quality") if isinstance(payload.get("quality"), Mapping) else None
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
    return FetchEnvelope(
        doi=normalize_text(payload.get("doi")) or None,
        source=normalize_text(payload.get("source")) or "metadata_only",
        has_fulltext=bool(payload.get("has_fulltext")),
        content_kind=normalize_text(payload.get("content_kind")) or "metadata_only",
        has_abstract=bool(payload.get("has_abstract")),
        warnings=[normalize_text(item) for item in payload.get("warnings") or [] if normalize_text(item)],
        source_trail=[normalize_text(item) for item in payload.get("source_trail") or [] if normalize_text(item)],
        trace=trace_from_payload(payload.get("trace")),
        token_estimate=int(payload.get("token_estimate") or 0),
        token_estimate_breakdown=breakdown,
        quality=quality,
        article=article,
        markdown=payload.get("markdown"),
        metadata=metadata,
    )


def mark_envelope_cached_with_current_revision(envelope: FetchEnvelope) -> FetchEnvelope:
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
        envelope.article.quality.extraction_revision = FETCH_ENVELOPE_EXTRACTION_REVISION
        envelope.quality = envelope.article.quality
        envelope.warnings = list(envelope.article.quality.warnings)
        envelope.source_trail = list(envelope.article.quality.source_trail)
        envelope.trace = list(envelope.article.quality.trace)
        envelope.token_estimate = envelope.article.quality.token_estimate
        envelope.token_estimate_breakdown = envelope.article.quality.token_estimate_breakdown
    return envelope


class FetchCache:
    """Cache facade for MCP fetch-envelope sidecars and cache index refresh."""

    def __init__(
        self,
        download_dir: Path | None,
        *,
        refresh_cache_index_for_doi_fn: Callable[[Path, str], list[dict[str, Any]]] = refresh_cache_index_for_doi,
        list_cache_entries_fn: Callable[[Path], list[dict[str, Any]]] = list_cache_entries,
        preferred_cached_entries_fn: Callable[[list[dict[str, Any]]], dict[str, Any]] = preferred_cached_entries,
    ) -> None:
        self.download_dir = download_dir
        self._refresh_cache_index_for_doi = refresh_cache_index_for_doi_fn
        self._list_cache_entries = list_cache_entries_fn
        self._preferred_cached_entries = preferred_cached_entries_fn

    def load_fetch_envelope(
        self,
        request: FetchPaperRequest,
        *,
        resolve_paper_fn: Callable[..., Any],
        transport: HttpTransport | None,
        env: Mapping[str, str],
    ) -> FetchEnvelope | None:
        if not request.prefer_cache or self.download_dir is None:
            return None
        resolved = resolve_paper_fn(request.query, transport=transport, env=env)
        if resolved.candidates and not resolved.doi:
            raise PaperFetchFailure(
                "ambiguous",
                "Query resolution is ambiguous; choose one of the DOI candidates.",
                candidates=resolved.candidates,
            )
        doi = normalize_text(resolved.doi)
        if not doi:
            return None
        entries = self._refresh_cache_index_for_doi(self.download_dir, doi)
        cached_entry = next(
            (
                entry
                for entry in sorted(entries, key=lambda item: float(item.get("mtime") or 0.0), reverse=True)
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
        if cache_payload.get("extraction_revision") != FETCH_ENVELOPE_EXTRACTION_REVISION:
            return None
        cached_request = cache_payload.get("request")
        payload = cache_payload.get("payload")
        if not isinstance(cached_request, Mapping) or not isinstance(payload, Mapping):
            return None
        if not cached_request_matches(cached_request, request):
            return None
        if not cached_payload_satisfies_request(payload, request):
            return None
        return mark_envelope_cached_with_current_revision(envelope_from_payload(payload))

    def write_fetch_envelope(self, envelope: FetchEnvelope, request: FetchPaperRequest) -> None:
        if self.download_dir is None:
            return
        doi = normalize_text(envelope.doi)
        if not doi:
            return
        self.download_dir.mkdir(parents=True, exist_ok=True)
        cache_path = fetch_envelope_cache_path(self.download_dir, doi)
        payload = {
            "version": FETCH_ENVELOPE_CACHE_VERSION,
            "extraction_revision": FETCH_ENVELOPE_EXTRACTION_REVISION,
            "request": request_cache_payload(request),
            "payload": payload_from_envelope(envelope, request),
        }
        with cache_file_lock(fetch_envelope_lock_path(self.download_dir, doi)):
            tmp_path = cache_path.with_suffix(cache_path.suffix + ".part")
            tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_path.replace(cache_path)
        self._refresh_cache_index_for_doi(self.download_dir, doi)

    def refresh_for_doi(self, doi: str) -> list[dict[str, Any]]:
        if self.download_dir is None:
            return []
        return self._refresh_cache_index_for_doi(self.download_dir, doi)

    def list_payload(self) -> dict[str, Any]:
        if self.download_dir is None:
            return {"download_dir": None, "entries": []}
        return {
            "download_dir": str(self.download_dir),
            "entries": self._list_cache_entries(self.download_dir),
        }

    def get_payload(self, doi: str) -> dict[str, Any]:
        if self.download_dir is None:
            entries: list[dict[str, Any]] = []
        else:
            entries = self._refresh_cache_index_for_doi(self.download_dir, doi)
        preferred = self._preferred_cached_entries(entries)
        return {
            "status": "hit" if entries else "miss",
            "doi": doi,
            "download_dir": str(self.download_dir) if self.download_dir is not None else None,
            "entries": entries,
            "preferred": preferred,
        }
