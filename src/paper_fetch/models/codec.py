"""Core structural codecs, independent of MCP requests and cache storage."""

from __future__ import annotations

from ..publication_dates import normalize_publication_dates

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from typing import Any, cast
from . import (
    ArticleModel,
    Asset,
    FetchEnvelope,
    Metadata,
    Quality,
    Reference,
    Section,
    coerce_asset_provenance,
    coerce_asset_timing,
    coerce_acquisition_provenance,
)
from ..tracing import TraceEvent
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
        publication_dates=normalize_publication_dates(value.get("publication_dates")),
        relations=list(value.get("relations") or []),
        update_to=list(value.get("update_to") or []),
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


def trace_from_payload(value: Any) -> list[TraceEvent]:
    if not isinstance(value, list) or any(
        not isinstance(entry, Mapping) for entry in value
    ):
        raise ValueError("trace must be a list of structured TraceEvent objects")
    return [TraceEvent(**dict(entry)) for entry in value]


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
    if not isinstance(value, Mapping):
        raise ValueError("quality is required")
    return Quality(**dict(value))


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
    from .schema import SourceKind

    return ArticleModel(
        doi=normalize_text(value.get("doi")) or None,
        source=cast(SourceKind, normalize_text(value.get("source")) or "crossref_meta"),
        metadata=metadata,
        acquisition=coerce_acquisition_provenance(value.get("acquisition")),
        diagnostics=dict(value.get("diagnostics") or {}),
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
                preview_accepted=bool(entry["preview_accepted"]),
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
        trace=trace_from_payload(value["trace"]),
    )


def envelope_from_payload(payload: Mapping[str, Any]) -> FetchEnvelope:
    from .schema import SupplementaryResult

    forbidden = {
        "has_fulltext",
        "content_kind",
        "has_abstract",
        "warnings",
        "source_trail",
        "token_estimate",
        "token_estimate_breakdown",
    }
    if forbidden.intersection(payload) or not isinstance(
        payload.get("quality"), Mapping
    ):
        raise ValueError("Unsupported fetch-envelope structure.")
    quality = quality_from_payload(payload["quality"])
    acquisition = coerce_acquisition_provenance(payload["acquisition"])
    trace = trace_from_payload(payload["trace"])
    article_payload = payload.get("article")
    if isinstance(article_payload, Mapping):
        if {"quality", "acquisition", "trace", "diagnostics"}.intersection(
            article_payload
        ):
            raise ValueError("Envelope article must contain content fields only.")
        article = article_from_payload(
            {
                **article_payload,
                "quality": payload["quality"],
                "acquisition": payload["acquisition"],
                "trace": payload["trace"],
                "diagnostics": payload.get("diagnostics") or {},
            }
        )
    else:
        article = None
    supplementary = payload.get("supplementary")
    return FetchEnvelope(
        doi=payload["doi"],
        source=payload["source"],
        target=payload["target"],
        supplementary=SupplementaryResult(**supplementary)
        if isinstance(supplementary, Mapping)
        else None,
        quality=quality,
        acquisition=acquisition,
        diagnostics=dict(payload.get("diagnostics") or {}),
        trace=trace,
        article=article,
        markdown=payload["markdown"],
        metadata=metadata_from_payload(payload.get("metadata")),
        diagnostic_artifacts=[dict(item) for item in payload["diagnostic_artifacts"]],
    )


def model_to_payload(
    model: Metadata | Quality | ArticleModel | FetchEnvelope,
) -> dict[str, Any]:
    """Encode exactly the public dataclass wire shape."""
    payload = asdict(model)
    if isinstance(model, FetchEnvelope) and payload["article"] is not None:
        for key in ("quality", "acquisition", "trace", "diagnostics"):
            payload["article"].pop(key)
    return payload
