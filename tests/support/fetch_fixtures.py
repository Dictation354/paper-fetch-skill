from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

from paper_fetch.models import (
    AcquisitionProvenance,
    ArticleModel,
    FetchEnvelope,
    Metadata,
    Quality,
    Section,
    TokenEstimateBreakdown,
)
from paper_fetch.resolve.query import ResolvedQuery
from paper_fetch.service import HasFulltextProbeResult
from paper_fetch.tracing import TraceContext, trace_event


def sample_article() -> ArticleModel:
    return ArticleModel(
        doi="10.1000/example",
        source="elsevier_xml",
        metadata=Metadata(
            title="Example Article",
            authors=["Alice Example"],
            abstract="Example abstract",
            journal="Example Journal",
            publication_dates=[
                {"kind": "unspecified", "value": "2026-01-01", "source": "test"}
            ],
        ),
        sections=[
            Section(heading="Introduction", level=2, kind="body", text="Example body.")
        ],
        references=[],
        assets=[],
        quality=Quality(
            has_fulltext=True,
            token_estimate=128,
            warnings=["example warning"],
            token_estimate_breakdown=TokenEstimateBreakdown(
                abstract=32, body=96, refs=24
            ),
        ),
        acquisition=AcquisitionProvenance(
            provider="elsevier",
            route="xml_api",
            representation="xml",
            transport="api",
            fallback_used=False,
        ),
    )


def sample_envelope(*, modes: set[str], doi: str = "10.1000/example") -> FetchEnvelope:
    article = sample_article()
    article.doi = doi
    article.metadata.title = (
        "Example Article" if doi == "10.1000/example" else f"Article for {doi}"
    )
    return FetchEnvelope(
        doi=doi,
        source="elsevier_xml",
        trace=[
            trace_event("resolve", "doi_selected", "ok"),
            trace_event(
                "metadata",
                "elsevier",
                "ok",
                context=TraceContext(provider="elsevier", route="metadata_api"),
            ),
            trace_event(
                "fulltext",
                "elsevier_xml",
                "ok",
                context=TraceContext(provider="elsevier", route="xml_api"),
            ),
        ],
        quality=article.quality,
        article=article if "article" in modes else None,
        markdown=(
            "# Example Article\n\nExample body.\n" if "markdown" in modes else None
        ),
        metadata=article.metadata if "metadata" in modes else None,
        acquisition=article.acquisition,
    )


def sample_resolved_query(query: str) -> ResolvedQuery:
    return ResolvedQuery(
        query=query,
        query_kind="doi",
        doi=query if query.startswith("10.") else "10.1000/example",
        landing_url="https://example.test/article",
        provider_hint="crossref",
        confidence=1.0,
        candidates=[],
        title="Example Article",
    )


def sample_probe_result(
    query: str,
    *,
    doi: str | None = None,
    title: str | None = None,
    state: str = "likely_yes",
    evidence: list[str] | None = None,
    warnings: list[str] | None = None,
) -> HasFulltextProbeResult:
    return HasFulltextProbeResult(
        query=query,
        doi=doi or (query if query.startswith("10.") else "10.1000/example"),
        title=title or f"Article for {query}",
        state=state,
        evidence=list(evidence or ["crossref_fulltext_link"]),
        warnings=list(warnings or []),
    )


def write_binary(path: Path, size: int = 8) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n" + (b"x" * max(0, size - 6)))


async def wait_for_threading_event(event: threading.Event, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if event.is_set():
            return True
        await asyncio.sleep(0.01)
    return event.is_set()


__all__ = [name for name in globals() if not name.startswith("__")]
