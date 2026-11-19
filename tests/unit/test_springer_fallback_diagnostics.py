"""Springer PDF recovery must retain the HTML failure's concrete diagnostics."""

from types import SimpleNamespace

import pytest

from paper_fetch.failure import FailureDiagnostics
from paper_fetch.providers.base import (
    ProviderContent,
    ProviderFailure,
    RawFulltextPayload,
)
from paper_fetch.providers.springer import PdfFallbackStrategy, SpringerClient
from paper_fetch.runtime import RuntimeContext
from paper_fetch.tracing import trace_event
from tests.support._paper_fetch_support import (
    FixtureHtmlTransport,
    RecordingTransport,
    http_response,
)


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
        trace=[trace_event("fulltext", "springer_pdf_fallback", "ok")],
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


def test_conflicting_springer_page_only_falls_back_from_requested_identity(monkeypatch):
    doi = "10.1038/s41586-026-12345-x"
    requested = "https://www.nature.com/articles/s41586-026-12345-x"
    wrong_doi = "10.1038/s41586-026-45678-y"
    wrong_url = "https://www.nature.com/articles/s41586-026-45678-y"
    wrong_body = f"""
    <meta name="citation_doi" content="{wrong_doi}">
    <meta name="citation_title" content="Unrelated article">
    <meta name="citation_pdf_url" content="{wrong_url}.pdf">
    <article><figure data-container-section="table">
    <a href="{wrong_url}/tables/1">Full size table</a>
    </figure><a href="{wrong_url}/supplement.pdf">Supplementary Information</a></article>
    """
    transport = FixtureHtmlTransport(
        {
            requested: http_response(wrong_url, wrong_body.encode(), "text/html"),
        }
    )
    client = SpringerClient(transport, {})
    original_pdf = f"{requested}.pdf"
    metadata = {
        "doi": doi,
        "title": "Requested study",
        "landing_page_url": requested,
        "fulltext_links": [{"url": original_pdf, "content_type": "application/pdf"}],
    }

    def recover_pdf(strategy, urls):
        assert original_pdf in urls and all(wrong_url not in url for url in urls)
        assert strategy.expected_identity == {"doi": doi, "title": "Requested study"}
        assert strategy.seed_urls == [requested]
        assert strategy.headers["Referer"] == requested
        return SimpleNamespace(
            final_url=original_pdf,
            pdf_bytes=b"%PDF",
            suggested_filename="paper.pdf",
            markdown_text="## Results\n\n" + "Verified PDF body. " * 150,
        )

    def unexpected(*args, **kwargs):
        pytest.fail("The rejected HTML triggered table or supplementary processing.")

    monkeypatch.setattr(PdfFallbackStrategy, "fetch", recover_pdf)
    monkeypatch.setattr(client, "_prepare_html_with_inline_tables", unexpected)
    monkeypatch.setattr(client, "download_related_assets", unexpected)
    with RuntimeContext(env={}, transport=transport) as context:
        result = client.fetch_result(
            doi, metadata, None, asset_profile="all", context=context
        )

    assert [call["url"] for call in transport.calls] == [requested]
    assert result.article.source == "springer_pdf"
    assert result.content.source_url == original_pdf
    assert (
        result.content.diagnostics["html_failure"]["identity"]["observed_doi"]
        == wrong_doi
    )
    assert any(event.code == "identity_mismatch" for event in result.trace)
    assert {
        event.component for event in result.trace if event.duration_ms is not None
    } >= {"springer_html_http", "springer_html_parse"}


@pytest.mark.parametrize(
    "page_title, status, method",
    [
        ("Independent identity from the title", "match", "title"),
        (None, "insufficient", "none"),
    ],
)
def test_springer_uses_only_page_identity_before_merging(page_title, status, method):
    doi = "10.1038/s41586-026-12345-x"
    url = "https://www.nature.com/articles/s41586-026-12345-x"
    title = "Independent identity from the title"
    title_meta = (
        f'<meta name="citation_title" content="{page_title}">' if page_title else ""
    )
    html = f"""
    <html><head>{title_meta}</head><body><article><h1>{title}</h1>
    <section><h2>Results</h2><p>{"Measurements were consistent across independent samples. " * 45}</p></section>
    </article></body></html>
    """
    transport = FixtureHtmlTransport(
        {url: http_response(url, html.encode(), "text/html")}
    )
    client = SpringerClient(transport, {})
    with RuntimeContext(env={}, transport=transport) as context:
        result = client.fetch_result(
            doi,
            {"doi": doi, "title": title, "landing_page_url": url},
            None,
            context=context,
        )

    assert result.article.source == "springer_html"
    assert result.article.doi == doi
    assert result.content.diagnostics["identity"]["status"] == status
    assert result.content.diagnostics["identity"]["method"] == method
    assert result.content.diagnostics["identity_evidence"] == {
        "doi": None,
        "title": page_title,
    }
