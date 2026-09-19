"""New observations supplement historical unknown envelopes without rewriting them."""

import hashlib
import json

import pymupdf
import pytest

from paper_fetch.extraction.html._metadata import parse_html_metadata
from paper_fetch.providers._pdf_common import _pdf_identity_evidence
from tests.golden_criteria import golden_criteria_asset
from tests.support.acquired_publisher_inputs import _record

PREFIX = "acquisition/known-gaps-2026-09-16/"


@pytest.mark.parametrize("doi", ["10.1063/5.0129134", "10.1093/bioinformatics/btaa823"])
def test_new_article_response_and_dom_do_not_claim_historical_challenge(doi):
    collection = json.loads(
        golden_criteria_asset(doi, PREFIX + "collection.json").read_text()
    )
    dom_record, dom = _record(doi, collection["dom_file"])
    response_record, response = _record(doi, PREFIX + "001-http_response_entity.bin")
    assert response_record["status_code"] == 200
    assert dom_record["status_code"] is None
    assert dom_record["capture_kind"] == "browser_rendered_dom"
    assert response_record["capture_kind"] == "http_response_entity"
    for content in (dom, response):
        assert (
            parse_html_metadata(content.decode(), collection["final_url"])[
                "doi"
            ].lower()
            == doi
        )
    assert not collection["challenge"]
    assert not collection["confirmed_paywall"]


@pytest.mark.parametrize(
    "doi,prefix,pages",
    [
        ("10.1073/pnas.2406303121", PREFIX, 10),
        ("10.1109/PGEC.1967.264619", "acquisition/known-gaps-pdf-2026-09-16/", 4),
        ("10.1109/TBME.2024.3434477", "acquisition/known-gaps-pdf-2026-09-16/", 9),
    ],
)
def test_new_official_pdf_envelope_completeness_and_identity(doi, prefix, pages):
    name = prefix + "002-http_response_entity.pdf"
    record, body = _record(doi, name)
    assert record["status_code"] == 200
    assert record["capture_kind"] == "http_response_entity"
    assert "application/pdf" in record["response_headers"]["content-type"]
    assert hashlib.sha256(body).hexdigest() == record["sha256"]
    assert body.startswith(b"%PDF-") and body.rstrip().endswith(b"%%EOF")
    path = golden_criteria_asset(doi, name)
    assert _pdf_identity_evidence(path)["doi"].lower() == doi.lower()
    with pymupdf.open(path) as document:
        assert not document.is_repaired
        assert not document.needs_pass
        assert len(document) == pages
        # Exercise every page object for file completeness only, no conversion assertions.
        assert all(document.load_page(i).rect.width > 0 for i in range(pages))


def test_science_stopped_at_real_challenge_without_claiming_new_pdf():
    doi = "10.1126/sciadv.abf8021"
    prefix = "acquisition/known-gaps-bytes-2026-09-16/"
    capture = json.loads(
        golden_criteria_asset(doi, prefix + "collection.json").read_text()
    )
    record, body = _record(doi, prefix + "001-http_response_entity.bin")
    assert record["status_code"] == 403
    assert record["response_headers"]["cf-mitigated"] == "challenge"
    assert b"%PDF-" not in body[:16]
    assert capture["stop_reason"] == "browser_challenge_requires_manual_verification"


@pytest.mark.parametrize(
    "doi", ["10.1109/PGEC.1967.264619", "10.1109/TBME.2024.3434477"]
)
def test_ieee_empty_rest_is_not_permission_denial(doi):
    prefix = "acquisition/known-gaps-rest-2026-09-16/"
    record, body = _record(doi, prefix + "001-http_response_entity.bin")
    assert record["status_code"] == 200
    assert body == b""
    capture = json.loads(
        golden_criteria_asset(doi, prefix + "collection.json").read_text()
    )
    assert not capture["confirmed_paywall"]


def test_current_wiley_formula_link_still_has_only_captured_preview():
    from paper_fetch.extraction.image_payloads import image_dimensions_from_bytes

    doi = "10.1029/2004gb002273"
    current = json.loads(
        golden_criteria_asset(doi, PREFIX + "collection.json").read_text()
    )
    assert current["formula_resource_links"] == [
        "/cms/asset/34efb858-9f37-465e-95e0-1a1a4ab00ca7/gbc1137-math-0001.gif"
    ]
    old = json.loads(
        golden_criteria_asset(
            doi, "acquisition/browser-retry-2026-09-16/collection.json"
        ).read_text()
    )
    formula = next(t for t in old["targets"] if t["file_role"] == "formula")
    record, body = _record(doi, formula["record"])
    assert record["final_url"].endswith(current["formula_resource_links"][0])
    assert image_dimensions_from_bytes(body) == (384, 17)
    assert formula["download_tier"] == "preview"
