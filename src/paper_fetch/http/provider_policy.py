"""Compile provider-catalog network declarations into HTTP request policy."""

from __future__ import annotations

from dataclasses import replace

from ..provider_catalog import compile_route_execution_policy
from .transport import HttpRequestPolicy


def _normalized_host(value: str | None) -> str:
    return str(value or "").strip().lower().rstrip(".")


def provider_allowed_hosts(
    provider: str,
    route_name: str | None = None,
) -> tuple[str, ...]:
    """Return the declared publisher/API hosts for one provider route."""

    try:
        compiled = compile_route_execution_policy(provider, route_name)
    except ValueError:
        return ()
    return tuple(host for value in compiled.hosts if (host := _normalized_host(value)))


def provider_request_policy(
    provider: str,
    route_name: str | None = None,
    *,
    base: HttpRequestPolicy | None = None,
) -> HttpRequestPolicy:
    """Build a request policy and automatically include catalog secrets."""

    compiled = compile_route_execution_policy(provider, route_name)
    normalized_provider = compiled.provider
    sensitive_headers = compiled.sensitive_headers
    allowed_hosts = compiled.hosts
    if sensitive_headers and not allowed_hosts:
        raise ValueError(
            f"Credentialed provider route has no declared hosts: {normalized_provider}:{route_name or '*'}"
        )
    active = base or HttpRequestPolicy()
    merged_allowed_hosts = tuple(
        dict.fromkeys((*tuple(active.allowed_hosts or ()), *allowed_hosts))
    )
    return replace(
        active,
        allowed_hosts=merged_allowed_hosts or None,
        sensitive_headers=tuple(
            dict.fromkeys((*active.sensitive_headers, *sensitive_headers))
        ),
        timeout_seconds=compiled.timeout_seconds,
        retry_on_rate_limit=compiled.retry_on_rate_limit,
        rate_limit_retries=compiled.rate_limit_retries,
        max_rate_limit_wait_seconds=compiled.rate_limit_wait_budget_seconds,
        retry_on_transient=compiled.retry_on_transient,
        transient_retries=compiled.transient_retries,
        minimum_interval_seconds=compiled.minimum_interval_seconds,
        cooldown_scope=(
            active.cooldown_scope
            or f"provider:{compiled.provider}:{compiled.route or 'all'}"
        ),
        route_concurrency_cap=compiled.asset_concurrency_cap,
        acceptance_policy=compiled.acceptance_policy,
        asset_scope=compiled.asset_scope,
    )


__all__ = ["provider_allowed_hosts", "provider_request_policy"]
