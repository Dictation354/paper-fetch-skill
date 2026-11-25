"""Shared helpers reused across workflow stages."""

from __future__ import annotations

from dataclasses import replace

from ..providers.base import ProviderFailure
from ..reason_codes import NOT_CONFIGURED, RATE_LIMITED
from ..tracing import TraceEvent, provider_stage_event


def events_for_failure(
    stage: str, provider_name: str, failure: ProviderFailure
) -> TraceEvent:
    if failure.code == NOT_CONFIGURED:
        suffix = NOT_CONFIGURED
    elif failure.code == RATE_LIMITED:
        suffix = RATE_LIMITED
    else:
        suffix = "fail"
    event = provider_stage_event(stage, provider_name, suffix)
    if (
        failure.diagnostics.error_category
        or failure.diagnostics.http_status is not None
        or failure.diagnostics.retryable is not None
        or failure.retry_after_seconds is not None
    ):
        return replace(
            event,
            http_status=failure.diagnostics.http_status,
            error_category=failure.diagnostics.error_category,
            retryable=failure.diagnostics.retryable,
            retry_after_seconds=failure.retry_after_seconds,
        )
    return event
