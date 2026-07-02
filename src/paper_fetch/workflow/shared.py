"""Shared helpers reused across workflow stages."""

from __future__ import annotations

from ..providers.base import ProviderFailure
from ..reason_codes import NOT_CONFIGURED, RATE_LIMITED
from ..tracing import provider_stage_marker


def source_trail_for_failure(
    stage: str, provider_name: str, failure: ProviderFailure
) -> str:
    if failure.code == NOT_CONFIGURED:
        suffix = NOT_CONFIGURED
    elif failure.code == RATE_LIMITED:
        suffix = RATE_LIMITED
    else:
        suffix = "fail"
    return provider_stage_marker(stage, provider_name, suffix)
