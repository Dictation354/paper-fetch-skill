"""Shared provider-lane resolution and production concurrency policy."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any, Protocol, TypeVar, cast

from ..provider_catalog import provider_batch_concurrency, provider_names
from ..publisher_identity import (
    extract_doi,
    extract_doi_from_url,
    infer_provider_from_doi,
    infer_provider_from_url,
    normalize_doi,
)
from ..runtime import RuntimeContext
from ..utils import normalize_text
from .session_cache import RESOLVED_QUERY_KEY

GENERIC_BATCH_LANE = "generic"


class _BatchRoutingItem(Protocol):
    """Minimum item facts shared by CLI and MCP batch routing."""

    @property
    def index(self) -> int: ...

    @property
    def query(self) -> str: ...

    @property
    def lane_key(self) -> str: ...

    @property
    def canonical_doi(self) -> str | None: ...


_BatchRoutingItemT = TypeVar("_BatchRoutingItemT", bound=_BatchRoutingItem)


def expected_doi_from_query(query: str) -> str | None:
    """Return a normalized DOI only when the original query carries one."""

    return (
        normalize_doi(extract_doi_from_url(query) or extract_doi(query) or "") or None
    )


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


def resolve_batch_item_routing(
    item: _BatchRoutingItemT,
    *,
    context: RuntimeContext,
    resolver: Callable[..., Any],
) -> _BatchRoutingItemT:
    """Resolve one item's lane and backfill its cached canonical DOI."""

    try:
        lane_key = resolve_provider_lane(
            item.query,
            initial_lane=item.lane_key,
            context=context,
            resolver=resolver,
        )
    except Exception:
        # The fetch attempt remains the owner of resolution errors and diagnostics.
        return item
    resolved = context.get_session_cache(
        RESOLVED_QUERY_KEY.materialize(normalize_text(item.query) or item.query)
    )
    if isinstance(resolved, Mapping):
        resolved_doi = resolved.get("doi")
    else:
        resolved_doi = getattr(resolved, "doi", None)
    canonical_doi = normalize_doi(str(resolved_doi or "")) or item.canonical_doi
    return cast(
        _BatchRoutingItemT,
        replace(cast(Any, item), lane_key=lane_key, canonical_doi=canonical_doi),
    )


def deduplicate_batch_items(
    items: list[_BatchRoutingItemT],
) -> tuple[list[_BatchRoutingItemT], dict[int, tuple[_BatchRoutingItemT, ...]]]:
    """Keep the first item for each canonical DOI and group its fan-out items."""

    representatives: list[_BatchRoutingItemT] = []
    owner_by_doi: dict[str, _BatchRoutingItemT] = {}
    duplicates: dict[int, list[_BatchRoutingItemT]] = {}
    for item in items:
        doi = normalize_doi(item.canonical_doi or "")
        if not doi:
            representatives.append(item)
            continue
        owner = owner_by_doi.get(doi)
        if owner is None:
            owner_by_doi[doi] = item
            representatives.append(item)
            continue
        duplicates.setdefault(owner.index, []).append(item)
    return representatives, {
        index: tuple(values) for index, values in duplicates.items()
    }


def fanout_batch_items(
    item: _BatchRoutingItemT,
    duplicates_by_owner: Mapping[int, tuple[_BatchRoutingItemT, ...]],
) -> tuple[_BatchRoutingItemT, ...]:
    """Return an executed item followed by its original-order logical duplicates."""

    return (item, *duplicates_by_owner.get(item.index, ()))


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
    "deduplicate_batch_items",
    "expected_doi_from_query",
    "fanout_batch_items",
    "initial_provider_lane",
    "provider_lane_from_resolved",
    "provider_lane_limit",
    "resolve_batch_item_routing",
    "resolve_provider_lane",
]
