"""Resolution stage for DOI, URL, and title inputs."""

from __future__ import annotations

from time import perf_counter

from ..config import build_runtime_env
from ..errors import ProviderFailure
from ..http import RequestFailure
from ..providers.base import map_request_failure
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
            query,
            transport=context.transport,
            env=context.env or build_runtime_env(),
            context=context,
        )
    except (ProviderFailure, RequestFailure) as error:
        exc = (
            map_request_failure(error, provider="resolver", stage="identity")
            if isinstance(error, RequestFailure)
            else error
        )
        if exc.diagnostics.error_category and not exc.diagnostics.stage:
            exc = exc.with_updates(
                provider=exc.diagnostics.provider or "resolver", stage="identity"
            )
        event = resolve_event(
            "resolver", "fail", duration_ms=round((perf_counter() - started) * 1000, 3)
        )
        raise exc.with_updates(trace=[*exc.trace, event]) from error
    resolved.duration_ms = round((perf_counter() - started) * 1000, 3)
    return resolved
