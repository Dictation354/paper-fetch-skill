"""Springer PDF recovery must retain the HTML failure's concrete diagnostics."""

import pytest

from paper_fetch.failure import FailureDiagnostics
from paper_fetch.providers.springer import SpringerClient
from paper_fetch.providers.base import (
    ProviderContent,
    ProviderFailure,
    RawFulltextPayload,
)
from paper_fetch.runtime import RuntimeContext
from paper_fetch.tracing import trace_from_markers
from tests.support._paper_fetch_support import RecordingTransport


@pytest.mark.parametrize("code,status", [("abstract_only", 200), ("timeout", None)])
def test_successful_pdf_recovery_preserves_structured_html_failure(
    monkeypatch, code, status
):
    transport = RecordingTransport({})
    client = SpringerClient(transport, {})
    failure = ProviderFailure(
        "no_result",
        "HTML body unavailable",
        diagnostics=FailureDiagnostics(
            provider="springer",
            route="html",
            http_status=status,
            details={
                "failure_code": code,
                "diagnostic_path": "/tmp/html-1/diagnostic.json",
            },
        ),
    )

    def failed_html(*args, **kwargs):
        raise failure

    monkeypatch.setattr(client, "_prepare_html_attempt", failed_html)
    pdf = RawFulltextPayload(
        provider="springer",
        content=ProviderContent(
            route_kind="pdf_fallback",
            source_url="https://example.org/article.pdf",
            content_type="application/pdf",
            body=b"%PDF",
            markdown_text="opaque converter output",
        ),
        trace=trace_from_markers(["fulltext:springer_pdf_fallback_ok"]),
    )
    monkeypatch.setattr(
        client, "_fetch_pdf_payload_from_html_attempt", lambda *a, **k: pdf
    )
    with RuntimeContext(env={}, transport=transport) as context:
        prepared = client.prepare_fetch_result_payload(
            "10.1186/example", {}, context=context
        )
        recovered = client.maybe_recover_fetch_result_payload(
            "10.1186/example", {}, prepared, context=context
        )
    for payload in (prepared.raw_payload, recovered.raw_payload):
        events = [
            event
            for event in payload.trace
            if event.component == "springer_html" and event.outcome == "fail"
        ]
        assert len(events) == 1
        assert events[0].code == code
        assert events[0].message == failure.message
        assert events[0].http_status == status
        assert events[0].target == "/tmp/html-1/diagnostic.json"
    assert recovered.raw_payload.content.route_kind == "pdf_fallback"
    assert recovered.raw_payload.content.markdown_text == "opaque converter output"
    assert (
        recovered.raw_payload.content.diagnostics["html_failure"]["diagnostic_path"]
        == "/tmp/html-1/diagnostic.json"
    )
    assert any(
        event.component == "springer_pdf_fallback" and event.outcome == "ok"
        for event in recovered.raw_payload.trace
    )
