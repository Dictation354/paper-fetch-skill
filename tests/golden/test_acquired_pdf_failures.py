"""Captured PDF failures and explicitly labeled browser DOM observations.

PDF endpoints replay the RequestFailure envelope through the direct PDF helper.
Browser observations lack HTTP envelopes and do not exercise provider readiness.
"""

from unittest import mock
from bs4 import BeautifulSoup
import pytest
from paper_fetch.http import RequestFailure
from paper_fetch.providers._pdf_common import PdfFetchFailure
from paper_fetch.providers._pdf_fallback import fetch_pdf_over_http
from paper_fetch.providers._playwright_browser import detect_html_block
from tests.support._paper_fetch_support import RecordingTransport
from tests.support.acquired_publisher_inputs import _record


@pytest.mark.parametrize(
    "doi,filename,status,reason",
    [
        ("10.1111/gcb.16414", "pdf-challenge.html", 403, "cloudflare_challenge"),
        ("10.1126/sciadv.abf8021", "pdf-challenge.html", 403, "cloudflare_challenge"),
        ("10.1073/pnas.2406303121", "pdf-challenge.html", 403, "cloudflare_challenge"),
        ("10.1109/ACCESS.2024.3352924", "pdf-response.html", 418, "non_pdf_html"),
    ],
)
def test_captured_pdf_endpoint_failure_preserves_diagnostics(
    doi, filename, status, reason, tmp_path
):
    record, body = _record(doi, "acquisition/" + filename)
    assert record["status_code"] == status
    url = record["requested_url"]
    transport = RecordingTransport(
        {
            ("GET", url): RequestFailure(
                status,
                record["error"],
                url=record["final_url"],
                headers=record["response_headers"],
                body=body,
            )
        }
    )
    with (
        mock.patch(
            "paper_fetch.providers._pdf_fallback.pdf_fetch_result_from_bytes"
        ) as parser,
        pytest.raises(PdfFetchFailure) as caught,
    ):
        fetch_pdf_over_http(transport, [url], artifact_dir=tmp_path)
    assert caught.value.kind == "pdf_download_failed"
    assert caught.value.details["status"] == status
    assert caught.value.details["reason"] == reason
    assert caught.value.details["content_type"].startswith("text/html")
    assert caught.value.details["candidate_url_sha256"]
    assert caught.value.details["final_url_sha256"]
    assert len(transport.calls) == 1
    parser.assert_not_called()
    assert not list(tmp_path.rglob("*.pdf"))


@pytest.mark.parametrize(
    "doi",
    [
        "10.1111/gcb.16414",
        "10.1126/sciadv.abf8021",
        "10.1073/pnas.2406303121",
        "10.1063/5.0129134",
        "10.1088/2058-9565/ac3460",
        "10.1175/JAMC-D-24-0048.1",
        "10.1080/17538947.2022.2137254",
        "10.1093/bioinformatics/btaa823",
    ],
)
def test_observed_browser_dom_is_a_challenge_without_inventing_http_status(doi):
    record, body = _record(doi, "acquisition/browser-observed.dom.html")
    assert record["capture_kind"] == "browser_rendered_dom"
    assert record["status_code"] is None
    soup = BeautifulSoup(body, "html.parser")
    assert soup.title.get_text() == record["title"]
    block = detect_html_block(record["title"], soup.get_text(" ", strip=True), None)
    assert block is not None
    assert block.reason == record["observed_reason"] == "cloudflare_challenge"
