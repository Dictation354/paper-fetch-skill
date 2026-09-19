"""Captured abstract-only HTML retains its diagnosis after injected PDF recovery."""

import pytest

from paper_fetch.models import FetchEnvelope
from paper_fetch.providers.springer import SpringerClient
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.runtime import RuntimeContext
from paper_fetch.tracing import trace_from_markers
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.support.acquired_publisher_inputs import _record, _response
from tests.support._paper_fetch_support import FixtureHtmlTransport


@pytest.mark.parametrize(
    "doi,capture,expected_reason",
    [
        ("10.1186/s40359-026-04991-8", "template-gaps-2026-09-16", "insufficient_body"),
        (
            "10.1038/s41419-026-09210-1",
            "requested-templates-2026-09-16",
            "abstract_only",
        ),
    ],
)
def test_abstract_only_diagnostic_survives_successful_pdf_recovery(
    doi, capture, expected_reason, monkeypatch
):
    record, body = _record(doi, f"acquisition/{capture}/article-response.html")
    transport = FixtureHtmlTransport({record["requested_url"]: _response(record, body)})
    metadata = {"doi": doi, "landing_page_url": record["requested_url"]}
    client = SpringerClient(transport, {})
    # PDF retrieval/conversion is outside this test's evidence scope.
    pdf = RawFulltextPayload(
        provider="springer",
        content=ProviderContent(
            route_kind="pdf_fallback",
            source_url=record["requested_url"] + ".pdf",
            content_type="application/pdf",
            body=b"%PDF",
            markdown_text="opaque PDF output",
            merged_metadata=metadata,
        ),
        trace=trace_from_markers(["fulltext:springer_pdf_fallback_ok"]),
    )

    def recovered_pdf(attempt, **kwargs):
        assert attempt.diagnostics.reason == expected_reason
        return pdf

    monkeypatch.setattr(client, "_fetch_pdf_payload_from_html_attempt", recovered_pdf)
    with RuntimeContext(env={}, transport=transport) as context:
        result = client.fetch_result(doi, metadata, None, context=context)
    events = [
        e
        for e in result.trace
        if e.component == "springer_html" and e.outcome == "fail"
    ]
    assert len(events) == 1
    assert events[0].code == expected_reason
    assert events[0].message
    assert events[0].http_status == 200
    assert result.content.route_kind == "pdf_fallback"
    assert result.content.markdown_text == "opaque PDF output"
    assert result.content.diagnostics["html_failure"]["failure_code"] == expected_reason
    acceptance = evaluate_fetch_acceptance(
        FetchEnvelope(
            doi=doi,
            source="springer_pdf",
            has_fulltext=True,
            article=result.article,
            trace=result.trace,
        ),
        asset_profile="none",
    )
    assert any(expected_reason in code for code in acceptance.provenance.failure_codes)
    assert acceptance.overall != "complete"
