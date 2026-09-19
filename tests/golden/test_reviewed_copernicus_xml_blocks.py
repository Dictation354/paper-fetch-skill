"""Unmodified publisher XML rejects, then same-paper PDF recovers or fails.

Historical HTTP headers/status are unknown: every HTTP envelope and the PDF
transport failure below is injected. XML, landing and successful PDF bytes are
the original canonical corpus files, and extraction/routing are current code.
"""

import hashlib
import pytest
from paper_fetch.http import RequestFailure
from paper_fetch.providers.copernicus import CopernicusClient
from paper_fetch.xml_security import parse_xml
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.block_fixtures import iter_block_samples
from tests.golden_corpus import golden_corpus_fixture_for_doi
from tests.golden_criteria import golden_criteria_asset
from tests.support._paper_fetch_support import RecordingTransport, http_response
from tests.support.reviewed_block_provider_paths import _fetch_through_service


FIXTURES = tuple(f for f in iter_block_samples() if f.provider == "copernicus")


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.doi)
@pytest.mark.parametrize(
    "pdf_succeeds", [True, False], ids=["pdf_recovery", "pdf_failure"]
)
def test_original_empty_xml_current_provider_waterfall(fixture, pdf_succeeds):
    golden = golden_corpus_fixture_for_doi(fixture.doi)
    xml = fixture.raw_path.read_bytes()
    assert xml == golden_criteria_asset(fixture.doi, "original.xml").read_bytes()
    assert hashlib.sha256(xml).hexdigest() == fixture.sample["provenance"]["sha256"]
    root = parse_xml(xml, allow_external_doctype=True)
    assert root.findtext(".//article-id[@pub-id-type='doi']") == fixture.doi
    assert not list(root.find("body"))
    assert "".join(root.find(".//abstract").itertext()).strip()
    pdf_url = next(
        node.attrib["{http://www.w3.org/1999/xlink}href"]
        for node in root.findall(".//self-uri")
        if node.attrib["{http://www.w3.org/1999/xlink}href"].endswith(".pdf")
    )
    assert pdf_url == golden.source_url
    landing_url = golden.sample["landing_url"]
    transport = RecordingTransport(
        {
            ("GET", landing_url): http_response(
                landing_url,
                golden_criteria_asset(fixture.doi, "landing.html").read_bytes(),
                "text/html",
            ),
            ("GET", fixture.source_url): http_response(
                fixture.source_url, xml, "application/xml"
            ),
            ("GET", pdf_url): (
                http_response(
                    pdf_url,
                    golden_criteria_asset(fixture.doi, "original.pdf").read_bytes(),
                    "application/pdf",
                )
                if pdf_succeeds
                else RequestFailure(
                    503, "Injected same-article PDF transport failure.", url=pdf_url
                )
            ),
        }
    )
    client = CopernicusClient(transport, {})
    envelope = _fetch_through_service(
        client,
        fixture,
        {
            "doi": fixture.doi,
            "title": golden.title,
            "landing_page_url": landing_url,
            "provider": "copernicus",
            "official_provider": True,
        },
    )
    article = envelope.article
    assert article is not None
    calls = [call["url"] for call in transport.calls]
    assert fixture.source_url in calls and pdf_url in calls
    assert calls.index(fixture.source_url) < calls.index(pdf_url)
    assert "fulltext:copernicus_xml_fail" in article.quality.source_trail
    assert any(
        fixture.expected_reason in warning for warning in article.quality.warnings
    )
    acceptance = evaluate_fetch_acceptance(
        envelope, asset_profile="none", doi=fixture.doi, expected_doi=fixture.doi
    )
    assert acceptance.overall != "complete"
    if pdf_succeeds:
        assert article.source == "copernicus_pdf"
        assert article.quality.has_fulltext
        assert "fulltext:copernicus_pdf_fallback_ok" in article.quality.source_trail
        converted = article.sections[0].text
        assert converted in article.to_ai_markdown(
            include_refs="all", max_tokens="full_text"
        )
        assert article.references == []
        assert acceptance.overall == "degraded"
    else:
        assert not article.quality.has_fulltext
        assert article.quality.content_kind in {"abstract_only", "metadata_only"}
        assert "fulltext:copernicus_pdf_fallback_ok" not in article.quality.source_trail
        assert any(
            "Injected same-article PDF transport failure." in warning
            for warning in article.quality.warnings
        )
