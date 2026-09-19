"""Real subscription pages; transient challenges are not paywall evidence."""

import json
from bs4 import BeautifulSoup
import pytest
from paper_fetch.extraction.html._metadata import parse_html_metadata
from paper_fetch.extraction.html.signals import detect_html_block
from paper_fetch.providers import ieee
from paper_fetch.providers._ieee_metadata import (
    IeeeLandingAttempt,
    _merge_ieee_metadata,
    _parse_landing_metadata,
)
from tests.block_fixtures import block_asset, execute_block_fixture, iter_block_samples
from tests.golden_criteria import golden_criteria_asset


@pytest.mark.parametrize(
    "doi,abstract_selector,purchase_text",
    [
        (
            "10.1146/annurev-neuro-062111-150343",
            ".abstract",
            "Buy Online Access",
        ),
        (
            "10.1038/nature12915",
            '[data-title="Abstract"]',
            "This is a preview of subscription content",
        ),
    ],
)
def test_http200_paywall_keeps_identity_and_abstract_without_primary_body(
    doi, abstract_selector, purchase_text
):
    fixture = next(f for f in iter_block_samples() if f.doi == doi)
    records = json.loads(block_asset(doi, "acquisition/provenance.json").read_text())[
        "records"
    ]
    response = next(r for r in records if r["body_file"] == "raw.html")
    assert response["status_code"] == 200
    assert response["capture_kind"] == "http_response_entity"
    for name in ("raw.html", "acquisition/final.dom.html"):
        raw = block_asset(doi, name).read_text()
        soup = BeautifulSoup(raw, "html.parser")
        text = soup.get_text(" ", strip=True)
        assert parse_html_metadata(raw, fixture.source_url)["doi"] == doi
        assert purchase_text in text
        abstract = soup.select_one(abstract_selector)
        assert abstract is not None and len(abstract.get_text(" ", strip=True)) > 500
        assert (
            soup.select_one('.article-body, .hlFld-Fulltext, [data-title="Main"]')
            is None
        )
        signal = detect_html_block(fixture.title, text, None, html_text=raw)
        assert signal is not None and signal.reason == "publisher_paywall"
    result = execute_block_fixture(fixture)
    assert not result.accepted
    assert result.reason == result.content_kind == "abstract_only"


def test_ieee_purchase_landing_preserves_real_abstract_without_fulltext_claim():
    # This test exercises abstract assembly only. Success and injected failure
    # waterfalls are covered in test_acquired_ieee_paywall_flow.py; the landing
    # remains auxiliary because the actual REST route returned full text.
    doi = "10.1109/TBME.2024.3434477"
    raw = golden_criteria_asset(
        doi, "acquisition/paywall-2026-09-15/article-response.html"
    ).read_text()
    dom = golden_criteria_asset(
        doi, "acquisition/paywall-2026-09-15/final.dom.html"
    ).read_text()
    soup = BeautifulSoup(dom, "html.parser")
    assert "Sign In or Purchase" in soup.get_text(" ", strip=True)
    assert soup.select_one("#article") is None
    landing_metadata = _parse_landing_metadata(raw)
    assert landing_metadata["isOpenAccess"] is False
    assert landing_metadata["openAccessFlag"] == "F"
    assert str(landing_metadata["articleNumber"]) == "10612240"
    assert len(landing_metadata["abstract"]) > 2000
    url = "https://ieeexplore.ieee.org/document/10612240"
    metadata = _merge_ieee_metadata({"doi": doi}, landing_metadata, url)
    assert metadata["doi"].lower() == doi.lower()
    landing = IeeeLandingAttempt(
        normalized_doi=doi.lower(),
        landing_url=url,
        response_url=url,
        html_text=raw,
        merged_metadata=metadata,
        article_number="10612240",
        landing_metadata=landing_metadata,
        acquisition_source="camoufox_browser",
    )
    client = ieee.IeeeClient(None, {})
    payload = client._abstract_only_payload(landing, warnings=[], trace_markers=[])
    article = client.to_article_model(metadata, payload)
    assert not article.quality.has_fulltext
    assert article.quality.content_kind == "abstract_only"
    rendered = article.to_ai_markdown(include_refs="all", max_tokens="full_text")
    assert metadata["title"] in rendered
    assert "Paediatric" in rendered
    assert "## Abstract" in rendered
