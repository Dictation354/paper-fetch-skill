"""Shared helpers reused across workflow stages."""

from __future__ import annotations

from ..providers.base import ProviderFailure


def source_trail_for_failure(stage: str, provider_name: str, failure: ProviderFailure) -> str:
    if failure.code == "not_configured":
        suffix = "not_configured"
    elif failure.code == "rate_limited":
        suffix = "rate_limited"
    else:
        suffix = "fail"
    return f"{stage}:{provider_name}_{suffix}"

