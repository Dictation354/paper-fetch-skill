"""Official TDM response through Wiley's current fallback and acceptance.

Only browser bootstrap failure and the offline token are injected; PDF bytes,
transport envelope, parsing, route selection and article assembly are real.
"""

from unittest import mock
import pymupdf
from paper_fetch.providers.wiley import WileyClient
from paper_fetch.providers.browser_workflow.profile import (
    BrowserWorkflowBootstrapResult,
)
from paper_fetch.runtime import RuntimeContext
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.support._browser_workflow_deps import install_browser_workflow_deps
from tests.support._paper_fetch_support import RecordingTransport, build_envelope
from tests.support.acquired_publisher_inputs import _record, _response


DOI = "10.1111/gcb.16414"


def test_captured_tdm_pdf_current_wiley_fallback_and_final_acceptance():
    record, body = _record(DOI, "original.pdf")
    assert record["status_code"] == 200
    assert record["response_headers"]["content-type"] == "application/pdf"
    with pymupdf.open(stream=body, filetype="pdf") as document:
        assert len(document) == 12
        assert DOI in document[0].get_text()
    transport = RecordingTransport(
        {("GET", record["requested_url"]): _response(record, body)}
    )
    client = WileyClient(transport, {"WILEY_TDM_CLIENT_TOKEN": "offline-fixture-token"})
    assert client._tdm_api_url(DOI) == record["requested_url"]
    bootstrap = BrowserWorkflowBootstrapResult(
        normalized_doi=DOI,
        runtime=None,
        landing_page_url=f"https://onlinelibrary.wiley.com/doi/{DOI}",
        html_candidates=[],
        pdf_candidates=[],
        html_failure_reason="cloudflare_challenge",
        html_failure_message="Injected browser challenge for offline TDM replay.",
    )
    install_browser_workflow_deps(
        client, bootstrap_browser_workflow=mock.Mock(return_value=bootstrap)
    )
    metadata = {"doi": DOI}
    with RuntimeContext(env={}, transport=transport) as context:
        payload = client.fetch_raw_fulltext(DOI, metadata, context=context)
        article = client.to_article_model(metadata, payload, context=context)
    assert payload.content.body == body
    assert len(transport.calls) == 1
    assert article.source == "wiley_browser"
    assert article.quality.has_fulltext
    assert "fulltext:wiley_pdf_api_ok" in article.quality.source_trail
    assert "fulltext:wiley_pdf_fallback_ok" in article.quality.source_trail
    rendered = article.to_ai_markdown(include_refs="all", max_tokens="full_text")
    assert DOI in rendered
    assert payload.content.markdown_text in rendered
    acceptance = evaluate_fetch_acceptance(
        build_envelope(article), asset_profile="none", doi=DOI, expected_doi=DOI
    )
    assert acceptance.overall == "degraded"
