"""Resolution stage for DOI, URL, and title inputs."""

from __future__ import annotations

from time import perf_counter

from ..config import build_runtime_env
from ..errors import ProviderFailure
from ..resolve.query import ResolvedQuery, StructuredResolveRequest, resolve_query
from ..runtime import RuntimeContext
from ..tracing import resolve_event


def resolve_paper(
    query: str | StructuredResolveRequest,
    *,
    context: RuntimeContext,
) -> ResolvedQuery:
    started = perf_counter()
    try:
        resolved = resolve_query(
            query, transport=context.transport, env=context.env or build_runtime_env()
        )
    except ProviderFailure as exc:
        event = resolve_event(
            "resolver", "fail", duration_ms=round((perf_counter() - started) * 1000, 3)
        )
        raise exc.with_updates(trace=[*exc.trace, event]) from exc
    resolved.duration_ms = round((perf_counter() - started) * 1000, 3)
    return resolved
