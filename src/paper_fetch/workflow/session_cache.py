"""Typed session-cache keys for workflow-level memoization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar
from collections.abc import Callable

from ..runtime import RuntimeContext

T = TypeVar("T")
_CACHE_MISSING = object()


@dataclass(frozen=True)
class SessionCacheKey:
    namespace: str

    def materialize(self, *args: str) -> tuple[str, ...]:
        return (self.namespace, *args)


RESOLVED_QUERY_KEY = SessionCacheKey("resolved_query")
CROSSREF_METADATA_KEY = SessionCacheKey("crossref_metadata")
PROVIDER_PROBE_KEY = SessionCacheKey("provider_metadata_probe")
LANDING_PDF_PROBE_KEY = SessionCacheKey("landing_citation_pdf_probe")


def cached_call(
    key: SessionCacheKey,
    args: tuple[str, ...],
    context: RuntimeContext,
    fn: Callable[[], T],
) -> T:
    cache_key = key.materialize(*args)
    cached = context.get_session_cache(cache_key, default=_CACHE_MISSING)
    if cached is not _CACHE_MISSING:
        return cached
    return context.set_session_cache(cache_key, fn())


def get_cached(
    key: SessionCacheKey, args: tuple[str, ...], context: RuntimeContext
) -> Any | None:
    cached = context.get_session_cache(key.materialize(*args), default=_CACHE_MISSING)
    if cached is _CACHE_MISSING:
        return None
    return cached
