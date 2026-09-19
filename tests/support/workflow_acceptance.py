"""Shared test support; contains no collected tests."""

from __future__ import annotations
from paper_fetch.models import (
    AcquisitionProvenance,
    ArticleModel,
    Asset,
    FetchEnvelope,
    Metadata,
    Quality,
    Section,
    SemanticLosses,
    apply_quality_assessment,
)
from paper_fetch.tracing import (
    TraceContext,
    acquisition_fallback_used,
    source_trail_from_trace,
    trace_event,
)


def _envelope(
    content_kind: str = "fulltext",
    *,
    assets: list[Asset] | None = None,
    asset_failures: list[dict[str, object]] | None = None,
    losses: SemanticLosses | None = None,
    flags: list[str] | None = None,
    warnings: list[str] | None = None,
    trace: list | None = None,
    include_article: bool = True,
    include_markdown: bool = True,
    include_metadata: bool = False,
) -> FetchEnvelope:
    abstract = None if content_kind == "metadata_only" else "Accepted abstract."
    sections = (
        [
            Section(
                heading="Introduction",
                level=2,
                kind="body",
                text="Accepted body text. " * 20,
            ),
            Section(
                heading="Results",
                level=2,
                kind="body",
                text="Accepted result text. " * 20,
            ),
        ]
        if content_kind == "fulltext"
        else []
    )
    article = ArticleModel(
        doi="10.1000/acceptance",
        source="elsevier_xml",
        metadata=Metadata(title="Acceptance Article", abstract=abstract),
        acquisition=AcquisitionProvenance(
            provider="elsevier",
            route="xml_api",
            representation="xml",
            transport="api",
        ),
        sections=sections,
        assets=list(assets or []),
        quality=Quality(),
    )
    events = list(
        [
            trace_event("resolve", "doi_selected", "ok"),
            trace_event(
                "fulltext",
                "elsevier",
                "ok",
                context=TraceContext(provider="elsevier", route="xml"),
            ),
        ]
        if trace is None
        else trace
    )
    article.acquisition = AcquisitionProvenance(
        provider="elsevier",
        route="xml_api",
        representation="xml",
        transport="api",
        fallback_used=acquisition_fallback_used(events),
    )
    article.quality.asset_failures = list(asset_failures or [])
    article.quality.source_trail = source_trail_from_trace(events)
    apply_quality_assessment(
        article,
        semantic_losses=losses or SemanticLosses(),
        extra_flags=flags,
        recompute_tokens=False,
    )
    article.quality.warnings.extend(warnings or [])
    markdown = (
        "# Acceptance Article\n\nAccepted body text.\n" if include_markdown else None
    )
    return FetchEnvelope(
        doi=article.doi,
        source=article.source,
        has_fulltext=article.quality.has_fulltext,
        content_kind=article.quality.content_kind,
        has_abstract=article.quality.has_abstract,
        warnings=article.quality.warnings,
        source_trail=article.quality.source_trail,
        trace=events,
        token_estimate=article.quality.token_estimate,
        quality=article.quality,
        article=article if include_article else None,
        markdown=markdown,
        metadata=article.metadata if include_metadata else None,
    )
