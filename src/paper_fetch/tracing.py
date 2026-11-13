"""Structured tracing helpers for fetch workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
import urllib.parse
from collections.abc import Iterable, Mapping

from .reason_codes import NOT_CONFIGURED, RATE_LIMITED
from .utils import normalize_text


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


def trace_event(
    stage: str,
    component: str,
    outcome: str = "info",
    *,
    code: str | None = None,
    message: str | None = None,
    context: TraceContext | None = None,
) -> TraceEvent:
    trace_context = context or TraceContext()
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


def provider_stage_event(
    stage: str, provider_name: str, outcome: str = "info", *, route: str | None = None
) -> TraceEvent:
    component = normalize_text(provider_name).lower()
    if route:
        component = f"{component}_{route}"
    return trace_event(
        stage,
        component,
        outcome,
        context=TraceContext(provider=provider_name, route=route),
    )


def fulltext_event(
    provider_name: str, outcome: str = "info", *, route: str | None = None
) -> TraceEvent:
    return provider_stage_event("fulltext", provider_name, outcome, route=route)


def download_event(component: str, outcome: str = "info") -> TraceEvent:
    return trace_event("download", component, outcome)


def metadata_event(component: str, outcome: str = "info") -> TraceEvent:
    return trace_event("metadata", component, outcome)


def route_event(component: str, outcome: str = "info") -> TraceEvent:
    return trace_event("route", component, outcome)


def resolve_event(component: str, outcome: str = "info") -> TraceEvent:
    return trace_event("resolve", component, outcome)


def fallback_event(component: str, outcome: str = "info") -> TraceEvent:
    return trace_event("fallback", component, outcome)


def merge_trace(
    *collections: list[TraceEvent] | tuple[TraceEvent, ...] | None,
) -> list[TraceEvent]:
    result: list[TraceEvent] = []
    for collection in collections:
        extend_trace(result, collection)
    return result


def extend_trace(target: list[TraceEvent], events: Iterable[TraceEvent] | None) -> None:
    for event in events or ():
        if event not in target:
            target.append(event)


def acquisition_fallback_used(trace: Iterable[TraceEvent]) -> bool:
    failure_outcomes = {
        "fail",
        "error",
        "negative",
        "not_usable",
        "unavailable",
        NOT_CONFIGURED,
        RATE_LIMITED,
    }
    return any(
        event.stage == "fallback"
        or (event.stage == "fulltext" and event.outcome in failure_outcomes)
        for event in trace
    )


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
