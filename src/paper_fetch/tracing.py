"""Structured tracing helpers for fetch workflows."""

from __future__ import annotations

from dataclasses import dataclass

from .utils import normalize_text

_OUTCOMELESS_MARKER_OUTCOMES = {"", "info", "selected", "done"}
_KNOWN_OUTCOMES = {
    "ok",
    "fail",
    "attempt",
    "positive",
    "negative",
    "unknown",
    "saved",
    "skipped",
    "partial",
    "disabled",
    "unavailable",
    "not_configured",
    "rate_limited",
    "abstract_only",
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

    def marker(self) -> str:
        stage = normalize_text(self.stage).lower()
        component = normalize_text(self.component).lower()
        outcome = normalize_text(self.outcome).lower()
        if not stage or not component:
            return ""
        if outcome in _OUTCOMELESS_MARKER_OUTCOMES:
            return f"{stage}:{component}"
        return f"{stage}:{component}_{outcome}"


def trace_event(
    stage: str,
    component: str,
    outcome: str = "info",
    *,
    code: str | None = None,
    message: str | None = None,
) -> TraceEvent:
    return TraceEvent(
        stage=normalize_text(stage).lower(),
        component=normalize_text(component).lower(),
        outcome=normalize_text(outcome).lower() or "info",
        code=normalize_text(code) or None,
        message=normalize_text(message) or None,
    )


def trace_event_from_marker(marker: str, *, code: str | None = None, message: str | None = None) -> TraceEvent:
    normalized_marker = normalize_text(marker).lower()
    if ":" not in normalized_marker:
        return trace_event("trace", normalized_marker or "unknown", code=code, message=message)
    stage, component_part = normalized_marker.split(":", 1)
    component = component_part
    outcome = "info"
    if "_" in component_part:
        candidate_component, candidate_outcome = component_part.rsplit("_", 1)
        if candidate_outcome in _KNOWN_OUTCOMES:
            component = candidate_component
            outcome = candidate_outcome
    return trace_event(stage, component, outcome, code=code, message=message)


def merge_trace(*collections: list[TraceEvent] | tuple[TraceEvent, ...] | None) -> list[TraceEvent]:
    merged: list[TraceEvent] = []
    seen: set[tuple[str, str, str, str | None, str | None]] = set()
    for collection in collections:
        for event in collection or []:
            key = (event.stage, event.component, event.outcome, event.code, event.message)
            if key in seen:
                continue
            seen.add(key)
            merged.append(event)
    return merged


def source_trail_from_trace(trace: list[TraceEvent] | tuple[TraceEvent, ...] | None) -> list[str]:
    markers: list[str] = []
    for event in trace or []:
        marker = event.marker()
        if marker and marker not in markers:
            markers.append(marker)
    return markers


def trace_from_markers(markers: list[str] | tuple[str, ...] | None) -> list[TraceEvent]:
    return [trace_event_from_marker(marker) for marker in markers or [] if normalize_text(marker)]
