"""Core structural codecs, independent of MCP requests and cache storage."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from typing import Any, cast
from .schema import EXTRACTION_REVISION
from . import (
    ArticleModel,
    Asset,
    FetchEnvelope,
    Metadata,
    Quality,
    Reference,
    Section,
    TokenEstimateBreakdown,
    build_token_estimate_breakdown,
    coerce_asset_failure_diagnostics,
    coerce_asset_provenance,
    coerce_asset_timing,
    coerce_asset_quality_summary,
    coerce_acquisition_provenance,
    coerce_body_quality_metrics,
    coerce_semantic_losses,
    coerce_token_estimate_breakdown,
)
from ..reason_codes import METADATA_ONLY
from ..tracing import TraceContext, TraceEvent, trace_event
from ..utils import normalize_text


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
    from .schema import ContentKind, QualityConfidence

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
            payload.get("extraction_revision") or EXTRACTION_REVISION
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
            text=str(entry.get("text") or ""),
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
    from .schema import SourceKind

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
                asset_timing=coerce_asset_timing(entry.get("asset_timing")),
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
    trace = trace_from_payload(payload.get("trace"))
    quality = (
        article.quality
        if article is not None
        else quality_from_payload(quality_payload)
    )
    if breakdown == TokenEstimateBreakdown():
        if article is not None:
            breakdown = article.quality.token_estimate_breakdown
        elif metadata is not None:
            breakdown = derived_breakdown(metadata=metadata, sections=[], references=[])
    if quality.token_estimate_breakdown == TokenEstimateBreakdown():
        quality.token_estimate_breakdown = breakdown
    if quality.token_estimate == 0:
        quality.token_estimate = int(payload.get("token_estimate") or 0)
    from .schema import ContentKind, SourceKind

    from .schema import SupplementaryResult

    supplementary = payload.get("supplementary")
    return FetchEnvelope(
        target=payload.get("target", "paper"),
        supplementary=SupplementaryResult(**supplementary)
        if isinstance(supplementary, Mapping)
        else None,
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


def model_to_payload(
    model: Metadata | Quality | ArticleModel | FetchEnvelope,
) -> dict[str, Any]:
    """Encode exactly the public dataclass wire shape."""
    return asdict(model)
