"""Compile non-authorizing provider-catalog request settings.

Catalog hosts and credential metadata describe provider integrations; they are
not an implicit network allowlist. Callers that need host restrictions must opt
in through :class:`HttpRequestPolicy`.
"""

from __future__ import annotations

from dataclasses import replace

from .transport import HttpRequestPolicy


def _normalized_host(value: str | None) -> str:
    return str(value or "").strip().lower().rstrip(".")


def provider_allowed_hosts(
    provider: str,
    route_name: str,
) -> tuple[str, ...]:
    """Return the declared publisher/API hosts for one provider route."""

    from ..provider_catalog import compile_route_execution_policy

    try:
        compiled = compile_route_execution_policy(provider, route_name)
    except ValueError:
        return ()
    return tuple(host for value in compiled.hosts if (host := _normalized_host(value)))


def provider_request_policy(
    provider: str,
    route_name: str,
    *,
    base: HttpRequestPolicy | None = None,
) -> HttpRequestPolicy:
    """Build a request policy without turning catalog data into authorization."""

    from ..provider_catalog import compile_route_execution_policy

    compiled = compile_route_execution_policy(provider, route_name)
    active = base or HttpRequestPolicy()
    return replace(
        active,
        timeout_seconds=compiled.timeout_seconds,
        retry_on_rate_limit=compiled.retry_on_rate_limit,
        rate_limit_retries=compiled.rate_limit_retries,
        max_rate_limit_wait_seconds=compiled.rate_limit_wait_budget_seconds,
        retry_on_transient=compiled.retry_on_transient,
        transient_retries=compiled.transient_retries,
        minimum_interval_seconds=compiled.minimum_interval_seconds,
        cooldown_scope=(
            active.cooldown_scope or f"provider:{compiled.provider}:{compiled.route}"
        ),
    )


__all__ = ["provider_allowed_hosts", "provider_request_policy"]
