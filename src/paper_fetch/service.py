"""Thin public facade over the workflow package."""

from __future__ import annotations

from pathlib import Path
import time
from typing import Mapping

from .formula.convert import formula_timing_collector
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
    clients: Mapping[str, object] | None | object = RUNTIME_UNSET,
    context: RuntimeContext | None = None,
) -> HasFulltextProbeResult:
    owns_runtime = context is None
    runtime = resolve_runtime_context(context, env=env, transport=transport, clients=clients)
    try:
        return workflow_probe_has_fulltext(
            query,
            transport=runtime.transport,
            env=runtime.env,
            clients=runtime.clients,
            context=runtime,
            resolve_paper_fn=resolve_paper,
        )
    finally:
        if owns_runtime:
            runtime.close()


def fetch_paper(
    query: str,
    *,
    modes: set[OutputMode] | None = None,
    strategy: FetchStrategy | None = None,
    render: RenderOptions | None = None,
    download_dir: Path | None | object = RUNTIME_UNSET,
    clients: Mapping[str, object] | None | object = RUNTIME_UNSET,
    transport: HttpTransport | None | object = RUNTIME_UNSET,
    env: Mapping[str, str] | None | object = RUNTIME_UNSET,
    context: RuntimeContext | None = None,
) -> FetchEnvelope:
    owns_runtime = context is None
    runtime = resolve_runtime_context(
        context,
        env=env,
        transport=transport,
        clients=clients,
        download_dir=download_dir,
    )
    try:
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
        with formula_timing_collector(
            lambda seconds: runtime.accumulate_stage_timing("formula_seconds", elapsed=seconds)
        ):
            article = fetch_article(
                query,
                strategy=active_strategy,
                context=runtime,
                resolve_paper_fn=resolve_paper,
            )
            render_started_at = time.monotonic()
            envelope = build_fetch_envelope(article, modes=requested_modes, render=resolved_render)
            runtime.record_stage_timing("render_seconds", render_started_at)
        return envelope
    finally:
        if owns_runtime:
            runtime.close()
