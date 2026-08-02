"""Structured tracing helpers for fetch workflows."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import math
from typing import Any
import urllib.parse
from collections.abc import Iterable, Mapping

from .reason_codes import NOT_CONFIGURED, OK, PARTIAL, RATE_LIMITED
from .quality.reason_codes import ABSTRACT_ONLY
from .utils import normalize_text

_OUTCOMELESS_MARKER_OUTCOMES = {"", "info", "selected", "done"}
_KNOWN_OUTCOMES = {
    OK,
    "fail",
    "attempt",
    "positive",
    "negative",
    "unknown",
    "saved",
    "skipped",
    PARTIAL,
    "disabled",
    "unavailable",
    NOT_CONFIGURED,
    RATE_LIMITED,
    ABSTRACT_ONLY,
    "not_usable",
    "article_ok",
    "article_fail",
}


@dataclass(frozen=True)
class TraceEvent:
    stage: str
    component: str
    outcome: str = "info"
    code: str | None = None
    message: str | None = None
    provider: str | None = None
    route: str | None = None
    span_id: str | None = None
    attempt_id: str | None = None
    parent_span_id: str | None = None
    attempt: int | None = None
    http_status: int | None = None
    error_category: str | None = None
    retryable: bool | None = None
    retry_after_seconds: int | None = None
    target: str | None = None
    target_sha256: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    duration_ms: float | None = None

    def marker(self) -> str:
        stage = normalize_text(self.stage).lower()
        component = normalize_text(self.component).lower()
        outcome = normalize_text(self.outcome).lower()
        if not stage or not component:
            return ""
        if outcome in _OUTCOMELESS_MARKER_OUTCOMES:
            return f"{stage}:{component}"
        return f"{stage}:{component}_{outcome}"


@dataclass(frozen=True)
class TraceContext:
    """Typed timing, route, retry, and target fields for one trace event."""

    provider: str | None = None
    route: str | None = None
    span_id: str | None = None
    attempt_id: str | None = None
    parent_span_id: str | None = None
    attempt: int | None = None
    http_status: int | None = None
    error_category: str | None = None
    retryable: bool | None = None
    retry_after_seconds: int | None = None
    target: str | None = None
    target_sha256: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    duration_ms: float | None = None


@dataclass
class _TraceAttemptBucket:
    attempts: int = 0
    failures: int = 0
    durations_ms: list[float] = field(default_factory=list)


_TRACE_CONTEXT_FIELDS = frozenset(TraceContext.__dataclass_fields__)


def _coerce_trace_context(
    context: TraceContext | None,
    legacy_fields: Mapping[str, Any],
) -> TraceContext:
    unexpected = sorted(set(legacy_fields) - _TRACE_CONTEXT_FIELDS)
    if unexpected:
        names = ", ".join(unexpected)
        raise TypeError(f"unexpected trace context field(s): {names}")
    if not legacy_fields:
        return context or TraceContext()
    return replace(context or TraceContext(), **legacy_fields)


def trace_event(
    stage: str,
    component: str,
    outcome: str = "info",
    *,
    code: str | None = None,
    message: str | None = None,
    context: TraceContext | None = None,
    **legacy_fields: Any,
) -> TraceEvent:
    trace_context = _coerce_trace_context(context, legacy_fields)
    safe_target, inferred_target_digest = _safe_trace_target(trace_context.target)
    return TraceEvent(
        stage=normalize_text(stage).lower(),
        component=normalize_text(component).lower(),
        outcome=normalize_text(outcome).lower() or "info",
        code=normalize_text(code) or None,
        message=normalize_text(message) or None,
        provider=normalize_text(trace_context.provider).lower() or None,
        route=normalize_text(trace_context.route).lower() or None,
        span_id=normalize_text(trace_context.span_id) or None,
        attempt_id=normalize_text(trace_context.attempt_id) or None,
        parent_span_id=normalize_text(trace_context.parent_span_id) or None,
        attempt=(
            trace_context.attempt
            if isinstance(trace_context.attempt, int) and trace_context.attempt > 0
            else None
        ),
        http_status=trace_context.http_status,
        error_category=normalize_text(trace_context.error_category).lower() or None,
        retryable=trace_context.retryable,
        retry_after_seconds=trace_context.retry_after_seconds,
        target=safe_target,
        target_sha256=normalize_text(trace_context.target_sha256)
        or inferred_target_digest,
        started_at=trace_context.started_at,
        finished_at=trace_context.finished_at,
        duration_ms=trace_context.duration_ms,
    )


def _safe_trace_target(value: str | None) -> tuple[str | None, str | None]:
    """Return a query-free trace target plus a digest of the original value."""

    target = normalize_text(value)
    if not target:
        return None, None
    parsed = urllib.parse.urlsplit(target)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return target, None
    safe = urllib.parse.urlunsplit(
        (parsed.scheme.lower(), parsed.netloc, parsed.path, "", "")
    )
    return safe, hashlib.sha256(target.encode("utf-8")).hexdigest()


def trace_marker(stage: str, component: str, outcome: str = "info") -> str:
    return trace_event(stage, component, outcome).marker()


def provider_stage_marker(
    stage: str, provider_name: str, outcome: str = "info", *, route: str | None = None
) -> str:
    component = normalize_text(provider_name).lower()
    route_component = normalize_text(route).lower()
    if route_component:
        component = f"{component}_{route_component}" if component else route_component
    return trace_marker(stage, component, outcome)


def fulltext_marker(
    provider_name: str, outcome: str = "info", *, route: str | None = None
) -> str:
    return provider_stage_marker("fulltext", provider_name, outcome, route=route)


def download_marker(component: str, outcome: str = "info") -> str:
    return trace_marker("download", component, outcome)


def metadata_marker(component: str, outcome: str = "info") -> str:
    return trace_marker("metadata", component, outcome)


def route_marker(component: str, outcome: str = "info") -> str:
    return trace_marker("route", component, outcome)


def resolve_marker(component: str, outcome: str = "info") -> str:
    return trace_marker("resolve", component, outcome)


def fallback_marker(component: str, outcome: str = "info") -> str:
    return trace_marker("fallback", component, outcome)


def trace_event_from_marker(
    marker: str, *, code: str | None = None, message: str | None = None
) -> TraceEvent:
    normalized_marker = normalize_text(marker).lower()
    if ":" not in normalized_marker:
        return trace_event(
            "trace", normalized_marker or "unknown", code=code, message=message
        )
    stage, component_part = normalized_marker.split(":", 1)
    component = component_part
    outcome = "info"
    if "_" in component_part:
        candidate_component, candidate_outcome = component_part.rsplit("_", 1)
        if candidate_outcome in _KNOWN_OUTCOMES:
            component = candidate_component
            outcome = candidate_outcome
    return trace_event(stage, component, outcome, code=code, message=message)


def merge_trace(
    *collections: list[TraceEvent] | tuple[TraceEvent, ...] | None,
) -> list[TraceEvent]:
    return [event for collection in collections for event in (collection or [])]


def source_trail_from_trace(
    trace: list[TraceEvent] | tuple[TraceEvent, ...] | None,
) -> list[str]:
    markers: list[str] = []
    for event in trace or []:
        marker = event.marker()
        if marker and marker not in markers:
            markers.append(marker)
    return markers


def trace_from_markers(markers: list[str] | tuple[str, ...] | None) -> list[TraceEvent]:
    return [
        trace_event_from_marker(marker)
        for marker in markers or []
        if normalize_text(marker)
    ]


def project_source_trail_trace(
    markers: list[str] | tuple[str, ...] | None,
    structured_trace: list[TraceEvent] | tuple[TraceEvent, ...] | None,
) -> list[TraceEvent]:
    """Project markers once while preserving every structured retry event."""

    remaining = list(structured_trace or [])
    projected: list[TraceEvent] = []
    for marker_event in trace_from_markers(markers):
        matching = [
            event for event in remaining if event.marker() == marker_event.marker()
        ]
        if matching:
            projected.extend(matching)
            matching_ids = {id(event) for event in matching}
            remaining = [event for event in remaining if id(event) not in matching_ids]
        else:
            projected.append(marker_event)
    projected.extend(remaining)
    return projected


def nearest_rank_percentile(
    values: Iterable[float],
    percentile: float,
) -> float | None:
    """Return a rounded nearest-rank percentile for non-empty samples."""

    if not 0 < percentile <= 1:
        raise ValueError("percentile must be in the interval (0, 1]")
    samples = list(values)
    if not samples:
        return None
    ordered = sorted(samples)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index], 3)


def summarize_trace_attempts(
    trace: Iterable[TraceEvent | Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    """Aggregate ordered attempt spans without collapsing repeated retries."""

    buckets: dict[str, _TraceAttemptBucket] = {}
    for raw_event in trace:
        provider_value = (
            raw_event.provider
            if isinstance(raw_event, TraceEvent)
            else raw_event.get("provider")
        )
        provider = normalize_text(
            provider_value
            if isinstance(provider_value, str | None)
            else str(provider_value)
        ).lower()
        if not provider:
            continue
        outcome_value = (
            raw_event.outcome
            if isinstance(raw_event, TraceEvent)
            else raw_event.get("outcome")
        )
        outcome = normalize_text(
            outcome_value
            if isinstance(outcome_value, str | None)
            else str(outcome_value)
        ).lower()
        duration = (
            raw_event.duration_ms
            if isinstance(raw_event, TraceEvent)
            else raw_event.get("duration_ms")
        )
        bucket = buckets.setdefault(provider, _TraceAttemptBucket())
        bucket.attempts += 1
        if outcome in {"fail", "error", "negative", "not_usable"}:
            bucket.failures += 1
        if isinstance(duration, int | float) and duration >= 0:
            bucket.durations_ms.append(float(duration))

    summaries: dict[str, dict[str, object]] = {}
    for provider, bucket in buckets.items():
        summaries[provider] = {
            "attempts": bucket.attempts,
            "failures": bucket.failures,
            "failure_rate": (
                round(bucket.failures / bucket.attempts, 6) if bucket.attempts else 0.0
            ),
            "p50_duration_ms": nearest_rank_percentile(bucket.durations_ms, 0.50),
            "p95_duration_ms": nearest_rank_percentile(bucket.durations_ms, 0.95),
        }
    return summaries
