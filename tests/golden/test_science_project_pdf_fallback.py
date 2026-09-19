"""Actual project PDF fallback receipt; no assertions about PDF conversion."""

import hashlib
import json

import pymupdf

from tests.golden_criteria import golden_criteria_asset
from tests.support.acquired_publisher_inputs import _record

DOI = "10.1126/sciadv.abf8021"
PREFIX = "acquisition/project-pdf-fallback-2026-09-16/"
TITLE = "Increasing precipitation variability on daily-to-multiyear time scales in a warmer world"


def test_science_project_fallback_captured_official_complete_same_paper_pdf():
    record, body = _record(DOI, PREFIX + "001-http_response_entity.pdf")
    collection = json.loads(
        golden_criteria_asset(DOI, PREFIX + "collection.json").read_text()
    )
    assert (
        collection["helper"]
        == "paper_fetch.providers._pdf_fallback.fetch_pdf_with_browser"
    )
    assert collection["outcome"] == "pdf_obtained"
    assert record["status_code"] == 200
    assert record["capture_kind"] == "http_response_entity"
    assert (
        record["requested_url"]
        == record["final_url"]
        == "https://www.science.org/doi/pdf/" + DOI
    )
    assert "application/pdf" in record["response_headers"]["content-type"]
    assert len(body) == record["size"] == collection["size"]
    assert hashlib.sha256(body).hexdigest() == record["sha256"] == collection["sha256"]
    assert body.startswith(b"%PDF-") and body.rstrip().endswith(b"%%EOF")
    with pymupdf.open(stream=body, filetype="pdf") as pdf:
        assert len(pdf) == 12
        assert not pdf.is_repaired and not pdf.needs_pass
        assert pdf.metadata["title"] == TITLE
        # The source DOI is printed on the last two pages, outside the bounded
        # first-pages metadata reader; verify it without changing that reader.
        assert DOI in pdf[10].get_text()
        assert DOI in pdf[11].get_text()
        assert all(pdf.load_page(i).rect.width > 0 for i in range(len(pdf)))
    initial, failed_body = _record(DOI, PREFIX + "000-http_response_entity.bin")
    assert initial["status_code"] == 403
    assert initial["response_headers"]["cf-mitigated"] == "challenge"
    assert not failed_body.startswith(b"%PDF-")
