"""Small runner for provider-owned full-text fallback sequences."""

from __future__ import annotations

from ..tracing import extend_trace

from ..quality.access_boundary import propagate_paywall

from dataclasses import dataclass, field, replace
import time
from typing import Any
from collections.abc import Callable, Mapping

from ..tracing import (
    TraceContext,
    TraceEvent,
    merge_trace,
    trace_event,
)
from .base import ProviderFailure, RawFulltextPayload, combine_provider_failures
from ..reason_codes import (
    ERROR,
    IDENTITY_MISMATCH,
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
    IDENTITY_MISMATCH,
)


@dataclass
class ProviderWaterfallState:
    warnings: list[str] = field(default_factory=list)
    failures: list[tuple[str, ProviderFailure]] = field(default_factory=list)
    initial_events: list[TraceEvent] = field(default_factory=list)
    failure_events: list[TraceEvent] = field(default_factory=list)

    @property
    def events(self) -> list[TraceEvent]:
        return [*self.initial_events, *self.failure_events]

    def failure(self, label: str) -> ProviderFailure | None:
        for failure_label, failure in reversed(self.failures):
            if failure_label == label:
                return failure
        return None

    def last_failure(self) -> ProviderFailure | None:
        return self.failures[-1][1] if self.failures else None


WarningFactory = Callable[[ProviderFailure, ProviderWaterfallState], str | None]
StepRunner = Callable[..., RawFulltextPayload]
FinalFailureFactory = Callable[[ProviderWaterfallState], ProviderFailure]
StepCondition = Callable[[ProviderWaterfallState], bool]


@dataclass(frozen=True, kw_only=True)
class WaterfallStep:
    label: str
    run: StepRunner
    failure_event: TraceEvent | None = None
    success_events: tuple[TraceEvent, ...] = ()
    continue_codes: tuple[str, ...] = DEFAULT_WATERFALL_CONTINUE_CODES
    failure_warning: str | WarningFactory | None = None
    success_warning: str | None = None
    include_failure_trail_on_success: bool = True
    condition: StepCondition | None = None
    route_name: str | None = None


ProviderWaterfallStep = WaterfallStep


def _run_step(
    step: WaterfallStep,
    state: ProviderWaterfallState,
    doi: str | None,
    metadata: Mapping[str, Any] | None,
    *,
    context: Any = None,
    client: Any = None,
    invoke_with_request: bool = False,
) -> RawFulltextPayload:
    if not invoke_with_request or doi is None:
        return step.run(state)
    if client is not None:
        return step.run(client, doi, metadata or {}, context=context)
    return step.run(doi, metadata or {}, context=context)


def _append_unique_text(target: list[str], values: list[str] | tuple[str, ...]) -> None:
    for value in values:
        normalized = str(value or "").strip()
        if normalized and normalized not in target:
            target.append(normalized)


def _combined_trace(
    markers: list[TraceEvent],
    payload_trace: list[TraceEvent],
) -> list[TraceEvent]:
    return merge_trace(markers, payload_trace)


def _failure_with_event(
    failure: ProviderFailure, marker: TraceEvent | None
) -> ProviderFailure:
    if not marker:
        return failure
    events = list(failure.trace)
    if not any(
        (event.stage, event.component, event.outcome)
        == (marker.stage, marker.component, marker.outcome)
        for event in events
    ):
        events.append(marker)
    return failure.with_updates(
        trace=events,
    )


def _failure_with_warning(
    failure: ProviderFailure, warning: str | None
) -> ProviderFailure:
    normalized = str(warning or "").strip()
    if not normalized:
        return failure
    warnings = list(failure.warnings)
    _append_unique_text(warnings, [normalized])
    return failure.with_updates(
        warnings=warnings,
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


def _failure_with_state(
    failure: ProviderFailure,
    state: ProviderWaterfallState,
) -> ProviderFailure:
    warnings: list[str] = []
    events: list[TraceEvent] = []
    missing_env: list[str] = []
    retry_after_values: list[int] = []
    state_trace: list[TraceEvent] = []

    _append_unique_text(warnings, state.warnings)
    _append_unique_text(warnings, failure.warnings)
    extend_trace(events, state.initial_events)
    extend_trace(events, state.failure_events)
    extend_trace(events, failure.trace)
    for _label, state_failure in state.failures:
        _append_unique_text(missing_env, state_failure.missing_env)
        state_trace = merge_trace(state_trace, state_failure.trace)
        if state_failure.retry_after_seconds is not None:
            retry_after_values.append(state_failure.retry_after_seconds)
    _append_unique_text(missing_env, failure.missing_env)
    if failure.retry_after_seconds is not None:
        retry_after_values.append(failure.retry_after_seconds)
    trace = list(state_trace)
    if (
        failure.trace
        and failure.trace != state_trace
        and all(
            failure is not state_failure for _label, state_failure in state.failures
        )
    ):
        trace = merge_trace(trace, failure.trace)

    return failure.with_updates(
        retry_after_seconds=max(retry_after_values) if retry_after_values else None,
        missing_env=missing_env,
        warnings=warnings,
        trace=merge_trace(events, trace),
    )


def _default_final_failure(state: ProviderWaterfallState) -> ProviderFailure:
    combined = combine_provider_failures(state.failures)
    return _failure_with_state(combined, state)


def run_provider_waterfall(
    steps: list[WaterfallStep] | tuple[WaterfallStep, ...],
    doi: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    *,
    context: Any = None,
    client: Any = None,
    invoke_with_request: bool = False,
    initial_warnings: list[str] | tuple[str, ...] | None = None,
    initial_events: list[TraceEvent] | tuple[TraceEvent, ...] | None = None,
    final_failure_factory: FinalFailureFactory | None = None,
) -> RawFulltextPayload:
    state = ProviderWaterfallState()
    _append_unique_text(state.warnings, list(initial_warnings or []))
    extend_trace(state.initial_events, list(initial_events or []))

    for attempt_index, step in enumerate(steps, start=1):
        if step.condition is not None and not step.condition(state):
            continue
        attempt_started = time.monotonic()
        attempt_started_epoch = time.time()
        provider_name = str(getattr(client, "name", "") or "") or None
        attempt_id = f"{provider_name or 'provider'}:{step.label}:{attempt_index}"
        span_id = attempt_id
        route_name = step.route_name or step.label
        try:
            payload = _run_step(
                step,
                state,
                doi,
                metadata,
                context=context,
                client=client,
                invoke_with_request=invoke_with_request,
            )
            if client is not None and doi is not None:
                payload = client.validate_raw_payload_identity(
                    doi, metadata or {}, payload
                )
        except ProviderFailure as exc:
            propagate_paywall(exc)
            failure = exc.with_updates(
                provider=exc.diagnostics.provider or provider_name,
                route=exc.diagnostics.route or route_name,
                stage=exc.diagnostics.stage or "fulltext",
                trace=merge_trace(
                    exc.trace,
                    [
                        trace_event(
                            "fulltext",
                            f"{provider_name}_{step.label}"
                            if provider_name
                            else step.label,
                            "fail",
                            code=exc.code,
                            message=exc.message,
                            context=TraceContext(
                                provider=provider_name,
                                route=route_name,
                                span_id=span_id,
                                attempt_id=attempt_id,
                                attempt=attempt_index,
                                http_status=exc.diagnostics.http_status,
                                error_category=exc.diagnostics.error_category,
                                retryable=exc.diagnostics.retryable,
                                retry_after_seconds=exc.retry_after_seconds,
                                started_at=attempt_started_epoch,
                                finished_at=time.time(),
                                duration_ms=round(
                                    (time.monotonic() - attempt_started) * 1000, 3
                                ),
                            ),
                        )
                    ],
                ),
            )
            failure = _failure_with_event(failure, step.failure_event)
            if failure.code not in step.continue_codes:
                raise _failure_with_state(failure, state) from exc
            warning = _resolve_failure_warning(step.failure_warning, failure, state)
            failure = _failure_with_warning(failure, warning)
            state.failures.append((step.label, failure))
            _append_unique_text(state.warnings, failure.warnings)
            extend_trace(state.failure_events, failure.trace)
            continue

        payload_warnings: list[str] = []
        _append_unique_text(payload_warnings, state.warnings)
        _append_unique_text(payload_warnings, payload.warnings)
        if step.success_warning:
            _append_unique_text(payload_warnings, [step.success_warning])
        payload.warnings = payload_warnings
        if payload.content is not None and not payload.content.route_name:
            payload.content = replace(payload.content, route_name=route_name)
        successful_route_name = (
            payload.content.route_name
            if payload.content is not None and payload.content.route_name
            else route_name
        )

        events: list[TraceEvent] = []
        if step.success_events:
            events = list(state.initial_events)
            if step.include_failure_trail_on_success:
                extend_trace(events, state.failure_events)
            extend_trace(events, list(step.success_events))
        elif state.events:
            events = list(state.events)
            extend_trace(events, payload.trace)
        prior_failure_trace = [
            event for _label, failure in state.failures for event in failure.trace
        ]
        payload.trace = (
            _combined_trace(
                events,
                merge_trace(prior_failure_trace, payload.trace),
            )
            if events
            else merge_trace(prior_failure_trace, payload.trace)
        )
        payload.trace = merge_trace(
            payload.trace,
            [
                trace_event(
                    "fulltext",
                    f"{provider_name}_{step.label}" if provider_name else step.label,
                    "ok",
                    context=TraceContext(
                        provider=provider_name,
                        route=successful_route_name,
                        span_id=span_id,
                        attempt_id=attempt_id,
                        attempt=attempt_index,
                        started_at=attempt_started_epoch,
                        finished_at=time.time(),
                        duration_ms=round(
                            (time.monotonic() - attempt_started) * 1000, 3
                        ),
                    ),
                )
            ],
        )
        return payload

    if not state.failures:
        raise ProviderFailure(
            NO_RESULT, "Provider waterfall did not run any retrieval steps."
        )
    raise _failure_with_state(
        (final_failure_factory or _default_final_failure)(state), state
    )
