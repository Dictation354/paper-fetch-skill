"""Resolution stage for DOI, URL, and title inputs."""

from __future__ import annotations

from typing import Mapping

from ..config import build_runtime_env
from ..http import HttpTransport
from ..resolve.query import ResolvedQuery, resolve_query
from ..runtime import RUNTIME_UNSET, RuntimeContext, resolve_runtime_context


def resolve_paper(
    query: str,
    *,
    transport: HttpTransport | None | object = RUNTIME_UNSET,
    env: Mapping[str, str] | None | object = RUNTIME_UNSET,
    context: RuntimeContext | None = None,
) -> ResolvedQuery:
    runtime = resolve_runtime_context(context, env=env, transport=transport)
    return resolve_query(query, transport=runtime.transport, env=runtime.env or build_runtime_env())
