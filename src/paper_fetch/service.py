"""Thin public facade over the workflow package."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .http import HttpTransport
from .models import FetchEnvelope, OutputMode, RenderOptions
from .providers.base import ProviderFailure
from .providers.registry import build_clients
from .resolve.query import ResolvedQuery
from .runtime import RUNTIME_UNSET, RuntimeContext, resolve_runtime_context
from .workflow.fulltext import fetch_article
from .workflow.metadata import fetch_metadata_for_resolved_query, merge_primary_secondary_metadata
from .workflow.rendering import build_fetch_envelope
from .workflow.resolution import resolve_paper
from .workflow.routing import (
    probe_has_fulltext as workflow_probe_has_fulltext,
)
from .workflow.types import FetchStrategy, HasFulltextProbeResult, PaperFetchFailure

DEFAULT_OUTPUT_MODES: set[OutputMode] = {"article", "markdown"}
__all__ = [
    "DEFAULT_OUTPUT_MODES",
    "FetchStrategy",
    "HasFulltextProbeResult",
    "PaperFetchFailure",
    "ProviderFailure",
    "ResolvedQuery",
    "RuntimeContext",
    "build_clients",
    "fetch_paper",
    "fetch_metadata_for_resolved_query",
    "merge_primary_secondary_metadata",
    "probe_has_fulltext",
    "resolve_paper",
]


def probe_has_fulltext(
    query: str,
    *,
    transport: HttpTransport | None | object = RUNTIME_UNSET,
    env: Mapping[str, str] | None | object = RUNTIME_UNSET,
    clients: Mapping[str, Any] | None | object = RUNTIME_UNSET,
    context: RuntimeContext | None = None,
) -> HasFulltextProbeResult:
    runtime = resolve_runtime_context(context, env=env, transport=transport, clients=clients)
    return workflow_probe_has_fulltext(
        query,
        transport=runtime.transport,
        env=runtime.env,
        clients=runtime.clients,
        context=runtime,
        resolve_paper_fn=resolve_paper,
    )


def fetch_paper(
    query: str,
    *,
    modes: set[OutputMode] | None = None,
    strategy: FetchStrategy | None = None,
    render: RenderOptions | None = None,
    download_dir: Path | None | object = RUNTIME_UNSET,
    clients: Mapping[str, Any] | None | object = RUNTIME_UNSET,
    transport: HttpTransport | None | object = RUNTIME_UNSET,
    env: Mapping[str, str] | None | object = RUNTIME_UNSET,
    context: RuntimeContext | None = None,
) -> FetchEnvelope:
    runtime = resolve_runtime_context(
        context,
        env=env,
        transport=transport,
        clients=clients,
        download_dir=download_dir,
    )
    requested_modes = set(modes or DEFAULT_OUTPUT_MODES)
    active_strategy = strategy or FetchStrategy()
    active_render = render or RenderOptions()
    resolved_render = RenderOptions(
        include_refs=active_render.include_refs,
        asset_profile=(
            active_render.asset_profile
            if active_render.asset_profile is not None
            else active_strategy.asset_profile
        ),
        max_tokens=active_render.max_tokens,
    )
    article = fetch_article(
        query,
        strategy=active_strategy,
        context=runtime,
        resolve_paper_fn=resolve_paper,
    )
    return build_fetch_envelope(article, modes=requested_modes, render=resolved_render)
