"""Resolution stage for DOI, URL, and title inputs."""

from __future__ import annotations

from ..config import build_runtime_env
from ..resolve.query import ResolvedQuery, StructuredResolveRequest, resolve_query
from ..runtime import RuntimeContext


def resolve_paper(
    query: str | StructuredResolveRequest,
    *,
    context: RuntimeContext,
) -> ResolvedQuery:
    return resolve_query(
        query, transport=context.transport, env=context.env or build_runtime_env()
    )
