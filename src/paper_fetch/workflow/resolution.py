"""Resolution stage for DOI, URL, and title inputs."""

from __future__ import annotations

from typing import Mapping

from ..config import build_runtime_env
from ..http import HttpTransport
from ..resolve.query import ResolvedQuery, resolve_query


def resolve_paper(
    query: str,
    *,
    transport: HttpTransport | None = None,
    env: Mapping[str, str] | None = None,
) -> ResolvedQuery:
    return resolve_query(query, transport=transport, env=env or build_runtime_env())

