"""Small runner for provider-owned full-text fallback sequences."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Callable, Mapping

from ..tracing import source_trail_from_trace, trace_from_markers
from .base import ProviderFailure, RawFulltextPayload, combine_provider_failures
from ..reason_codes import (
    ERROR,
    NO_ACCESS,
    NO_RESULT,
    NOT_CONFIGURED,
    NOT_SUPPORTED,
    RATE_LIMITED,
)

DEFAULT_WATERFALL_CONTINUE_CODES = (
    NO_RESULT,
    NO_ACCESS,
    RATE_LIMITED,
    ERROR,
    NOT_CONFIGURED,
    NOT_SUPPORTED,
)


@dataclass
class ProviderWaterfallState:
    warnings: list[str] = field(default_factory=list)
    failures: list[tuple[str, ProviderFailure]] = field(default_factory=list)
    initial_source_trail: list[str] = field(default_factory=list)
    failure_source_trail: list[str] = field(default_factory=list)

    @property
    def source_trail(self) -> list[str]:
        return [*self.initial_source_trail, *self.failure_source_trail]

    def failure(self, label: str) -> ProviderFailure | None:
        for failure_label, failure in reversed(self.failures):
            if failure_label == label:
                return failure
        return None

    def last_failure(self) -> ProviderFailure | None:
        return self.failures[-1][1] if self.failures else None

    def source_markers(self) -> list[str]:
        return self.source_trail


WarningFactory = Callable[[ProviderFailure, ProviderWaterfallState], str | None]
StepRunner = Callable[..., RawFulltextPayload]
FinalFailureFactory = Callable[[ProviderWaterfallState], ProviderFailure]
StepCondition = Callable[[ProviderWaterfallState], bool]


@dataclass(frozen=True)
class WaterfallStep:
    label: str
    run: StepRunner
    failure_marker: str | None = None
    success_markers: tuple[str, ...] = ()
    continue_codes: tuple[str, ...] = (NO_RESULT,)
    failure_warning: str | WarningFactory | None = None
    success_warning: str | None = None
    include_failure_trail_on_success: bool = True
    condition: StepCondition | None = None


ProviderWaterfallStep = WaterfallStep


def _run_step(
    step: WaterfallStep,
    state: ProviderWaterfallState,
    doi: str | None,
    metadata: Mapping[str, Any] | None,
    *,
    context: Any = None,
    client: Any = None,
) -> RawFulltextPayload:
    if doi is None:
        return step.run(state)
    if client is not None:
        return step.run(client, doi, metadata or {}, context=context)
    return step.run(doi, metadata or {}, context=context)


def _append_unique_text(target: list[str], values: list[str] | tuple[str, ...]) -> None:
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in target:
            target.append(normalized)


def _failure_with_marker(
    failure: ProviderFailure, marker: str | None
) -> ProviderFailure:
    if not marker:
        return failure
    source_trail = list(failure.source_trail)
    if marker not in source_trail:
        source_trail.append(marker)
    return ProviderFailure(
        failure.code,
        failure.message,
        retry_after_seconds=failure.retry_after_seconds,
        missing_env=failure.missing_env,
        warnings=failure.warnings,
        source_trail=source_trail,
    )


def _failure_with_warning(
    failure: ProviderFailure, warning: str | None
) -> ProviderFailure:
    normalized = str(warning or "").strip()
    if not normalized:
        return failure
    warnings = list(failure.warnings)
    warnings.append(normalized)
    return ProviderFailure(
        failure.code,
        failure.message,
        retry_after_seconds=failure.retry_after_seconds,
        missing_env=failure.missing_env,
        warnings=warnings,
        source_trail=failure.source_trail,
    )


def _resolve_failure_warning(
    warning: str | WarningFactory | None,
    failure: ProviderFailure,
    state: ProviderWaterfallState,
) -> str | None:
    if warning is None:
        return None
    if callable(warning):
        return warning(failure, state)
    return warning


def _default_final_failure(state: ProviderWaterfallState) -> ProviderFailure:
    combined = combine_provider_failures(state.failures)
    warnings = list(state.warnings)
    for warning in combined.warnings:
        if warning not in warnings:
            warnings.append(warning)
    return ProviderFailure(
        combined.code,
        combined.message,
        retry_after_seconds=combined.retry_after_seconds,
        missing_env=combined.missing_env,
        warnings=warnings,
        source_trail=combined.source_trail,
    )


def run_provider_waterfall(
    steps: list[WaterfallStep] | tuple[WaterfallStep, ...],
    doi: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    *,
    context: Any = None,
    client: Any = None,
    initial_warnings: list[str] | tuple[str, ...] | None = None,
    initial_source_trail: list[str] | tuple[str, ...] | None = None,
    final_failure_factory: FinalFailureFactory | None = None,
) -> RawFulltextPayload:
    state = ProviderWaterfallState()
    _append_unique_text(state.warnings, list(initial_warnings or []))
    _append_unique_text(state.initial_source_trail, list(initial_source_trail or []))

    for step in steps:
        if step.condition is not None and not step.condition(state):
            continue
        try:
            payload = _run_step(
                step, state, doi, metadata, context=context, client=client
            )
        except ProviderFailure as exc:
            failure = _failure_with_marker(exc, step.failure_marker)
            if failure.code not in step.continue_codes:
                raise failure from exc
            warning = _resolve_failure_warning(step.failure_warning, failure, state)
            failure = _failure_with_warning(failure, warning)
            state.failures.append((step.label, failure))
            _append_unique_text(state.warnings, failure.warnings)
            _append_unique_text(state.failure_source_trail, failure.source_trail)
            continue

        payload_warnings = [*state.warnings, *payload.warnings]
        if step.success_warning:
            payload_warnings.append(step.success_warning)
        payload.warnings = [
            warning for warning in payload_warnings if str(warning).strip()
        ]

        if step.success_markers:
            source_trail = list(state.initial_source_trail)
            if step.include_failure_trail_on_success:
                _append_unique_text(source_trail, state.failure_source_trail)
            _append_unique_text(source_trail, list(step.success_markers))
            payload.trace = trace_from_markers(source_trail)
        elif state.source_trail:
            source_trail = list(state.source_trail)
            _append_unique_text(source_trail, source_trail_from_trace(payload.trace))
            payload.trace = trace_from_markers(source_trail)
        return payload

    if not state.failures:
        raise ProviderFailure(
            NO_RESULT, "Provider waterfall did not run any retrieval steps."
        )
    raise (final_failure_factory or _default_final_failure)(state)
