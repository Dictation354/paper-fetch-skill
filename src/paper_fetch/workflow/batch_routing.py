"""Shared provider-lane resolution and production concurrency policy."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ..provider_catalog import provider_batch_concurrency, provider_names
from ..publisher_identity import (
    extract_doi,
    extract_doi_from_url,
    infer_provider_from_doi,
    infer_provider_from_url,
)
from ..runtime import RuntimeContext
from ..utils import normalize_text
from .session_cache import RESOLVED_QUERY_KEY

GENERIC_BATCH_LANE = "generic"


def initial_provider_lane(query: str) -> str:
    """Return a no-I/O lane hint for a DOI, URL, or unresolved title."""

    provider = infer_provider_from_url(query)
    if provider:
        return provider
    doi = extract_doi_from_url(query) or extract_doi(query)
    return infer_provider_from_doi(doi) or GENERIC_BATCH_LANE


def provider_lane_from_resolved(resolved: object) -> str | None:
    """Derive the actual provider lane from a resolved-query result."""

    if isinstance(resolved, Mapping):
        provider_hint = str(resolved.get("provider_hint") or "").strip().lower()
        landing_url = str(resolved.get("landing_url") or "")
        doi = str(resolved.get("doi") or "")
    else:
        provider_hint = (
            str(getattr(resolved, "provider_hint", "") or "").strip().lower()
        )
        landing_url = str(getattr(resolved, "landing_url", "") or "")
        doi = str(getattr(resolved, "doi", "") or "")
    return (
        provider_hint
        or infer_provider_from_url(landing_url)
        or infer_provider_from_doi(doi)
    )


def resolve_provider_lane(
    query: str,
    *,
    initial_lane: str,
    context: RuntimeContext,
    resolver: Callable[..., Any],
) -> str:
    """Resolve a generic lane and prime the item's resolution session cache."""

    if initial_lane != GENERIC_BATCH_LANE:
        return initial_lane
    resolved = resolver(query, context=context)
    cache_key = RESOLVED_QUERY_KEY.materialize(normalize_text(query) or str(query))
    context.set_session_cache(cache_key, resolved)
    return provider_lane_from_resolved(resolved) or initial_lane


def provider_lane_limit(lane: object, *, global_limit: int) -> int:
    """Bound a resolved provider lane by its catalog-declared policy."""

    provider = normalize_text(str(lane)).lower()
    if provider == GENERIC_BATCH_LANE:
        return global_limit
    if provider not in provider_names():
        return 1
    return min(global_limit, provider_batch_concurrency(provider))


__all__ = [
    "GENERIC_BATCH_LANE",
    "initial_provider_lane",
    "provider_lane_from_resolved",
    "provider_lane_limit",
    "resolve_provider_lane",
]
