from __future__ import annotations

from paper_fetch.providers._payloads import build_provider_payload
from paper_fetch.providers._waterfall import ProviderWaterfallState
from paper_fetch.providers.base import ProviderFailure


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
    assert state.source_markers() == [
        "fulltext:start",
        "fulltext:html_fail",
        "fulltext:pdf_fail",
    ]
