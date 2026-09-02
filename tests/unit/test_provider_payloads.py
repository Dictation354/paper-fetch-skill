from __future__ import annotations

import tempfile
from dataclasses import asdict, fields, replace
from pathlib import Path

from paper_fetch.artifacts import ArtifactStore
from paper_fetch.providers._payloads import build_provider_payload
from paper_fetch.providers._waterfall import ProviderWaterfallState
from paper_fetch.providers.base import (
    ProviderArtifacts,
    ProviderFailure,
    RawFulltextPayload,
)
from paper_fetch.tracing import trace_from_markers


def test_build_provider_payload_populates_typed_content_and_trace() -> None:
    payload = build_provider_payload(
        provider="example",
        route_kind="pdf_fallback",
        source_url="https://example.test/article.pdf",
        content_type="application/pdf",
        body=b"%PDF-1.7",
        markdown_text="# Example",
        merged_metadata={"doi": "10.1234/example"},
        diagnostics={"pdf_fallback": {"fetcher": "direct_http"}},
        reason="Downloaded PDF fallback.",
        suggested_filename="article.pdf",
        warnings=["fallback warning"],
        trace_markers=["fulltext:example_pdf_ok"],
        needs_local_copy=True,
    )

    assert payload.provider == "example"
    assert payload.needs_local_copy
    assert payload.content is not None
    assert payload.content.route_kind == "pdf_fallback"
    assert payload.content.needs_local_copy
    assert payload.content.markdown_text == "# Example"
    assert payload.content.merged_metadata == {"doi": "10.1234/example"}
    assert payload.content.diagnostics == {"pdf_fallback": {"fetcher": "direct_http"}}
    assert payload.content.suggested_filename == "article.pdf"
    assert payload.warnings == ["fallback warning"]
    assert [event.marker() for event in payload.trace] == ["fulltext:example_pdf_ok"]


def test_raw_payload_serializes_and_replaces_only_canonical_content() -> None:
    content = build_provider_payload(
        provider="example",
        route_kind="html",
        source_url="https://example.test/article",
        content_type="text/html",
        body=b"<article>Example</article>",
        merged_metadata={"doi": "10.1234/example"},
    ).content
    payload = RawFulltextPayload(provider="example", content=content)

    assert [item.name for item in fields(payload)] == [
        "provider",
        "content",
        "warnings",
        "trace",
    ]
    assert set(asdict(payload)) == {"provider", "content", "warnings", "trace"}

    replaced = replace(
        payload,
        content=replace(content, source_url="https://example.test/replaced"),
    )
    assert replaced != payload
    assert replaced.source_url == "https://example.test/replaced"
    assert replaced.content.source_url == "https://example.test/replaced"


def test_raw_payload_legacy_fulltext_fields_are_projections() -> None:
    payload = RawFulltextPayload(
        provider="extension",
        source_url="https://example.test/legacy",
        content_type="text/html",
        body=b"legacy",
        merged_metadata={"doi": "10.1234/legacy"},
        needs_local_copy=True,
    )

    payload.source_url = "https://example.test/projected"
    payload.needs_local_copy = False

    assert payload.content.source_url == "https://example.test/projected"
    assert payload.content.merged_metadata == {"doi": "10.1234/legacy"}
    assert not payload.content.needs_local_copy


def test_provider_waterfall_state_failure_helpers_return_labelled_failures() -> None:
    html_failure = ProviderFailure(
        "no_result", "HTML route failed.", source_trail=["fulltext:html_fail"]
    )
    pdf_failure = ProviderFailure(
        "no_result", "PDF route failed.", source_trail=["fulltext:pdf_fail"]
    )
    state = ProviderWaterfallState(
        initial_source_trail=["fulltext:start"],
        failure_source_trail=["fulltext:html_fail", "fulltext:pdf_fail"],
    )
    state.failures.extend([("html", html_failure), ("pdf", pdf_failure)])

    assert state.failure("html") is html_failure
    assert state.failure("pdf") is pdf_failure
    assert state.failure("abstract") is None
    assert state.last_failure() is pdf_failure
    assert state.source_trail == [
        "fulltext:start",
        "fulltext:html_fail",
        "fulltext:pdf_fail",
    ]


def test_artifact_store_applies_skip_trace_without_skip_warning() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ArtifactStore.from_download_dir(
            Path(tmpdir), artifact_mode="markdown-assets"
        )
        warnings: list[str] = []
        source_trail: list[str] = []

        store.apply_provider_artifacts(
            provider_name="example",
            artifacts=ProviderArtifacts(
                text_only=True,
                skip_trace=trace_from_markers(
                    ["download:example_assets_skipped_text_only"]
                ),
            ),
            asset_profile="body",
            warnings=warnings,
            source_trail=source_trail,
        )

    assert warnings == []
    assert source_trail == ["download:example_assets_skipped_text_only"]
