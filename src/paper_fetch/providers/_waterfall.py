"""Small runner for provider-owned full-text fallback sequences."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..tracing import source_trail_from_trace, trace_from_markers
from .base import ProviderFailure, RawFulltextPayload, combine_provider_failures


@dataclass
class ProviderWaterfallState:
    warnings: list[str] = field(default_factory=list)
    failures: list[tuple[str, ProviderFailure]] = field(default_factory=list)
    initial_source_trail: list[str] = field(default_factory=list)
    failure_source_trail: list[str] = field(default_factory=list)

    @property
    def source_trail(self) -> list[str]:
        return [*self.initial_source_trail, *self.failure_source_trail]


WarningFactory = Callable[[ProviderFailure, ProviderWaterfallState], str | None]
StepRunner = Callable[[ProviderWaterfallState], RawFulltextPayload]
FinalFailureFactory = Callable[[ProviderWaterfallState], ProviderFailure]


@dataclass(frozen=True)
class ProviderWaterfallStep:
    label: str
    run: StepRunner
    failure_marker: str | None = None
    success_markers: tuple[str, ...] = ()
    continue_codes: tuple[str, ...] = ("no_result",)
    failure_warning: str | WarningFactory | None = None
    success_warning: str | None = None
    include_failure_trail_on_success: bool = True


def _extend_unique(target: list[str], values: list[str] | tuple[str, ...]) -> None:
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in target:
            target.append(normalized)


def _failure_with_marker(failure: ProviderFailure, marker: str | None) -> ProviderFailure:
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


def _failure_with_warning(failure: ProviderFailure, warning: str | None) -> ProviderFailure:
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
    steps: list[ProviderWaterfallStep] | tuple[ProviderWaterfallStep, ...],
    *,
    initial_warnings: list[str] | tuple[str, ...] | None = None,
    initial_source_trail: list[str] | tuple[str, ...] | None = None,
    final_failure_factory: FinalFailureFactory | None = None,
) -> RawFulltextPayload:
    state = ProviderWaterfallState()
    _extend_unique(state.warnings, list(initial_warnings or []))
    _extend_unique(state.initial_source_trail, list(initial_source_trail or []))

    for step in steps:
        try:
            payload = step.run(state)
        except ProviderFailure as exc:
            failure = _failure_with_marker(exc, step.failure_marker)
            if failure.code not in step.continue_codes:
                raise failure
            warning = _resolve_failure_warning(step.failure_warning, failure, state)
            failure = _failure_with_warning(failure, warning)
            state.failures.append((step.label, failure))
            _extend_unique(state.warnings, failure.warnings)
            _extend_unique(state.failure_source_trail, failure.source_trail)
            continue

        payload_warnings = [*state.warnings, *payload.warnings]
        if step.success_warning:
            payload_warnings.append(step.success_warning)
        payload.warnings = [warning for warning in payload_warnings if str(warning).strip()]

        if step.success_markers:
            source_trail = list(state.initial_source_trail)
            if step.include_failure_trail_on_success:
                _extend_unique(source_trail, state.failure_source_trail)
            _extend_unique(source_trail, list(step.success_markers))
            payload.trace = trace_from_markers(source_trail)
        elif state.source_trail:
            source_trail = list(state.source_trail)
            _extend_unique(source_trail, source_trail_from_trace(payload.trace))
            payload.trace = trace_from_markers(source_trail)
        return payload

    if not state.failures:
        raise ProviderFailure("no_result", "Provider waterfall did not run any retrieval steps.")
    raise (final_failure_factory or _default_final_failure)(state)
