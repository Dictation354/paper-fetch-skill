"""Thin public facade over the workflow package."""

from __future__ import annotations

from .formula.convert import formula_runtime_env
from .formula.validation import formula_validation_session, capture_formula_diagnostics
from .models import FetchEnvelope, OutputMode, RenderOptions
from .models.quality import (
    QUALITY_FLAG_FORMULA_FALLBACK_PRESENT,
    _semantic_loss_warning_messages,
)
from .providers.base import ProviderFailure
from .providers.registry import build_clients
from .resolve.query import ResolvedQuery, StructuredResolveRequest
from .runtime import RuntimeContext
from .workflow.fulltext import fetch_article
from .workflow.metadata import (
    fetch_metadata_for_resolved_query,
    merge_primary_secondary_metadata,
)
from .workflow.rendering import build_fetch_envelope
from .workflow.resolution import resolve_paper as workflow_resolve_paper
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
    "fetch_metadata_for_resolved_query",
    "fetch_paper",
    "merge_primary_secondary_metadata",
    "probe_has_fulltext",
    "resolve_paper",
]


def resolve_paper(
    query: str | StructuredResolveRequest,
    *,
    context: RuntimeContext | None = None,
) -> ResolvedQuery:
    owns_runtime = context is None
    runtime = context or RuntimeContext()
    try:
        return workflow_resolve_paper(query, context=runtime)
    finally:
        if owns_runtime:
            runtime.close()


def probe_has_fulltext(
    query: str,
    *,
    context: RuntimeContext | None = None,
) -> HasFulltextProbeResult:
    owns_runtime = context is None
    runtime = context or RuntimeContext()
    try:
        return workflow_probe_has_fulltext(
            query,
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
    context: RuntimeContext | None = None,
) -> FetchEnvelope:
    owns_runtime = context is None
    runtime = context or RuntimeContext()
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

        with formula_runtime_env(runtime.env or {}), formula_validation_session():
            article = fetch_article(
                query,
                strategy=active_strategy,
                context=runtime,
                resolve_paper_fn=resolve_paper,
            )
            runtime.raise_if_cancelled()
            if not article.source.endswith("_pdf") and not (
                article.acquisition and article.acquisition.representation == "pdf"
            ):
                losses = article.quality.semantic_losses
                count_before = losses.formula_fallback_count
                capture_formula_diagnostics(losses, count_fallbacks=True)
                if losses.formula_fallback_count > count_before:
                    if (
                        QUALITY_FLAG_FORMULA_FALLBACK_PRESENT
                        not in article.quality.flags
                    ):
                        article.quality.flags.append(
                            QUALITY_FLAG_FORMULA_FALLBACK_PRESENT
                        )
                    for warning in _semantic_loss_warning_messages(losses):
                        if warning not in article.quality.warnings:
                            article.quality.warnings.append(warning)
                    if article.quality.confidence == "high":
                        article.quality.confidence = "medium"
            runtime.report_progress("stage", stage="validating")
            envelope = build_fetch_envelope(
                article,
                modes=requested_modes,
                render=resolved_render,
                trace=list(runtime.fetch_trace),
                diagnostic_artifacts=list(runtime.diagnostic_artifacts),
            )
        return envelope
    finally:
        if owns_runtime:
            runtime.close()
