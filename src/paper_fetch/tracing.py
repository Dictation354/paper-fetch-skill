"""Structured tracing helpers for fetch workflows."""

from __future__ import annotations

from dataclasses import dataclass

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
    merged: list[TraceEvent] = []
    seen: set[tuple[str, str, str, str | None, str | None]] = set()
    for collection in collections:
        for event in collection or []:
            key = (
                event.stage,
                event.component,
                event.outcome,
                event.code,
                event.message,
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(event)
    return merged


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
