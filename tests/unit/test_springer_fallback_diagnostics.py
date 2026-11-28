"""Springer PDF recovery must retain the HTML failure's concrete diagnostics."""

from types import SimpleNamespace

import pytest

from paper_fetch.delivery.receipts import receipt_from_record
from paper_fetch.failure import FailureDiagnostics
from paper_fetch.manifest import build_manifest_record
from paper_fetch.models import FetchEnvelope
from paper_fetch.providers.base import (
    ProviderContent,
    ProviderFailure,
    RawFulltextPayload,
)
from paper_fetch.providers.springer import (
    PdfFallbackStrategy,
    PdfFetchFailure,
    SpringerClient,
)
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


@pytest.mark.parametrize(
    ("route", "heading"),
    [("abstract_only", ""), ("pdf", ""), ("html", "Along the transect"), ("html", "")],
)
def test_springerlink_bilingual_preview_receipt(route, heading, monkeypatch, tmp_path):
    doi = "10.1007/example"
    url = f"https://link.springer.com/article/{doi}"
    pdf_url = f"https://link.springer.com/content/pdf/{doi}.pdf"
    abstract_en = "The abstract summarizes the measurements from all stations. " * 12
    abstract_zh = "本研究摘要概述了各个站点的测量结果。" * 40
    body = "Measurements across the entire transect showed a seasonal shift. " * 30
    article_body = f"<h2>{heading}</h2>" if heading else ""
    if route == "html":
        article_body += f"<p>{body}</p>"
    html = f"""
    <meta name="citation_doi" content="{doi}">
    <meta name="citation_pdf_url" content="{pdf_url}">
    <article><h1>Transect observations</h1><div class="c-article-body">
      <section aria-labelledby="Abs1" data-title="Abstract" lang="en">
        <h2 id="Abs1">Abstract</h2><p>{abstract_en}</p></section>
      <section aria-labelledby="Abs2" data-title="摘要" lang="zh">
        <h2 id="Abs2">摘要</h2><p>{abstract_zh}</p></section>
      {article_body}
      <div class="c-pdf-preview"><h2>PDF preview</h2>
        <p>{"Preview of the first page of the article. " * 12}</p></div>
      <section data-title="Acknowledgements"><h2>Acknowledgements</h2>
        <p>We thank our colleagues.</p></section>
      <section data-title="Additional information"><h2>Additional information</h2>
        <div><h3>Article Highlights</h3><ul><li>{"A summary of seasonal observations. " * 15}</li></ul></div></section>
      <section><h2>References</h2><ol><li>Survey of stations.</li></ol></section>
    </div></article>
    """
    transport = FixtureHtmlTransport(
        {url: http_response(url, html.encode(), "text/html; charset=utf-8")}
    )
    client = SpringerClient(transport, {})

    pdf_attempts = []

    def fetch_pdf(strategy, urls):
        pdf_attempts.append(urls)
        assert pdf_url in urls
        if route == "abstract_only":
            raise PdfFetchFailure("pdf_download_failed", "PDF unavailable")
        return SimpleNamespace(
            final_url=pdf_url,
            pdf_bytes=b"%PDF",
            suggested_filename="paper.pdf",
            markdown_text=body,
        )

    monkeypatch.setattr(PdfFallbackStrategy, "fetch", fetch_pdf)
    with RuntimeContext(env={}, transport=transport) as context:
        result = client.fetch_result(
            doi,
            {"doi": doi, "landing_page_url": url, "title": "Transect observations"},
            None,
            context=context,
        )
    assert len(pdf_attempts) == (0 if route == "html" else 1)
    article = result.article
    receipt = receipt_from_record(
        build_manifest_record(
            tool_version="test",
            index=1,
            attempt=1,
            query=doi,
            request_parameters={"target": "paper"},
            asset_profile="none",
            envelope=FetchEnvelope(
                doi=doi, source=article.source, article=article, trace=result.trace
            ),
        ),
        tmp_path / "manifest.json",
    )
    assert receipt["target_satisfied"] is (route != "abstract_only")
    assert article.source == ("springer_pdf" if route == "pdf" else "springer_html")
    if route != "html":
        assert any(
            event.component == "springer_html" and event.code == "abstract_only"
            for event in result.trace
        )
    if route != "pdf":
        assert [
            (s.heading, s.text.strip())
            for s in article.sections
            if s.kind == "abstract"
        ] == [("Abstract", abstract_en.strip()), ("摘要", abstract_zh)]
        diagnostics = result.content.diagnostics
        assert not any(
            h["kind"] == "body"
            and h["heading"] in {"摘要", "PDF preview", "Article Highlights"}
            for h in diagnostics["extraction"]["section_hints"]
        )
        metrics = diagnostics["availability_diagnostics"]["body_metrics"]
        if route == "abstract_only":
            assert receipt["content_kind"] == "abstract_only"
            assert metrics["char_count"] == metrics["body_paragraph_count"] == 0
        else:
            assert body.strip() in metrics["text"]
            body_sections = [s for s in article.sections if s.kind == "body"]
            assert body.strip() in [s.text for s in body_sections]
            assert all(
                s.heading not in {"摘要", "PDF preview", "Article Highlights"}
                for s in body_sections
            )
