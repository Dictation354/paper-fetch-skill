from __future__ import annotations

from pathlib import Path

import pytest

from paper_fetch.mcp.fetch_tool import build_fetch_tool_result
from paper_fetch.mcp.schemas import FetchPaperRequest
from paper_fetch.mcp.server import build_server
from paper_fetch.models import (
    ArticleModel,
    FetchEnvelope,
    Metadata,
    Quality,
    Section,
    SemanticLosses,
)
from paper_fetch.tracing import source_trail_from_trace, trace_event


def _successful_trace():
    return [
        trace_event("resolve", "doi_selected", "ok"),
        trace_event(
            "fulltext",
            "elsevier",
            "ok",
            provider="elsevier",
            route="xml",
        ),
    ]


def _fulltext_envelope(
    *,
    losses: SemanticLosses | None = None,
) -> FetchEnvelope:
    events = _successful_trace()
    source_trail = source_trail_from_trace(events)
    metadata = Metadata(
        title="Acceptance Article",
        abstract="Accepted abstract.",
    )
    quality = Quality(
        has_fulltext=True,
        content_kind="fulltext",
        has_abstract=True,
        token_estimate=128,
        source_trail=source_trail,
        confidence="high",
        semantic_losses=losses or SemanticLosses(),
    )
    article = ArticleModel(
        doi="10.1000/acceptance",
        source="elsevier_xml",
        metadata=metadata,
        sections=[
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
        ],
        quality=quality,
    )
    return FetchEnvelope(
        doi=article.doi,
        source=article.source,
        has_fulltext=True,
        content_kind="fulltext",
        has_abstract=True,
        source_trail=source_trail,
        trace=events,
        token_estimate=128,
        quality=quality,
        article=article,
        markdown="# Acceptance Article\n\nAccepted body text.\n",
    )


def _limited_envelope(content_kind: str) -> FetchEnvelope:
    events = _successful_trace()
    source_trail = source_trail_from_trace(events)
    has_abstract = content_kind == "abstract_only"
    metadata = Metadata(
        title="Limited Article",
        abstract="Accepted abstract." if has_abstract else None,
    )
    quality = Quality(
        has_fulltext=False,
        content_kind=content_kind,
        has_abstract=has_abstract,
        token_estimate=32,
        source_trail=source_trail,
        confidence="medium",
    )
    return FetchEnvelope(
        doi="10.1000/limited",
        source="crossref_meta",
        has_fulltext=False,
        content_kind=content_kind,
        has_abstract=has_abstract,
        source_trail=source_trail,
        trace=events,
        token_estimate=32,
        quality=quality,
        metadata=metadata,
    )


def _fetch_request(
    query: str,
    *,
    modes: list[str],
    save_markdown: bool = False,
) -> FetchPaperRequest:
    return FetchPaperRequest.model_validate(
        {
            "query": query,
            "modes": modes,
            "strategy": {"asset_profile": "none"},
            "save_markdown": save_markdown,
        }
    )


def test_successful_fetch_returns_ok_status_and_compact_acceptance() -> None:
    result = build_fetch_tool_result(
        _fulltext_envelope(),
        _fetch_request(
            "https://doi.org/10.1000/acceptance",
            modes=["article", "markdown"],
        ),
    )

    assert result.is_error is False
    payload = result.structured_content
    assert payload is not None
    assert payload["status"] == "ok"
    assert payload["acceptance"] == {
        "overall": "complete",
        "identity": "resolved",
        "fetch": "ok",
        "content": "fulltext",
        "asset": "not_requested",
        "output": "complete",
        "provenance": "complete",
        "has_fulltext": True,
        "has_abstract": True,
        "token_estimate": 128,
    }

    output_model = (
        build_server()._tool_manager._tools["fetch_paper"].fn_metadata.output_model
    )
    assert output_model is not None
    output_model.model_validate(payload)


def test_fetch_acceptance_preserves_quality_degradation() -> None:
    result = build_fetch_tool_result(
        _fulltext_envelope(losses=SemanticLosses(table_fallback_count=1)),
        _fetch_request("10.1000/acceptance", modes=["article", "markdown"]),
    )

    payload = result.structured_content
    assert payload is not None
    assert payload["status"] == "ok"
    assert payload["acceptance"]["overall"] == "degraded"
    assert payload["acceptance"]["content"] == "fulltext"
    assert payload["quality"]["semantic_losses"]["table_fallback_count"] == 1


@pytest.mark.parametrize("content_kind", ["abstract_only", "metadata_only"])
def test_fetch_acceptance_reports_limited_content(content_kind: str) -> None:
    result = build_fetch_tool_result(
        _limited_envelope(content_kind),
        _fetch_request("10.1000/limited", modes=["metadata"]),
    )

    payload = result.structured_content
    assert payload is not None
    assert payload["status"] == "ok"
    assert payload["acceptance"]["overall"] == "limited"
    assert payload["acceptance"]["content"] == content_kind
    assert payload["acceptance"]["output"] == "complete"


def test_saved_markdown_compaction_keeps_pre_compaction_acceptance() -> None:
    result = build_fetch_tool_result(
        _fulltext_envelope(),
        _fetch_request(
            "10.1000/acceptance",
            modes=["article", "markdown"],
            save_markdown=True,
        ),
        saved_markdown_path=Path("/tmp/acceptance.md"),
    )

    payload = result.structured_content
    assert payload is not None
    assert payload["article"] is None
    assert payload["markdown"] is None
    assert payload["saved_markdown_path"] == "/tmp/acceptance.md"
    assert payload["acceptance"]["overall"] == "complete"
    assert payload["acceptance"]["output"] == "complete"
