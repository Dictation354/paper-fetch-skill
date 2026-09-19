"""Camoufox-acquired IEEE PDF and unmodified, overlapping reference pages."""

import html
import json
from dataclasses import asdict
from pathlib import Path
from unittest import mock
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pymupdf
import pytest
from paper_fetch.providers import ieee
from paper_fetch.providers import _ieee_html
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.extraction.html.assets import (
    AssetDownloadOptions,
    FIGURE_KIND,
    download_assets,
)
from paper_fetch.providers._ieee_metadata import (
    IeeeLandingAttempt,
    fetch_ieee_reference_metadata,
)
from paper_fetch.runtime import RuntimeContext
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.support._paper_fetch_support import RecordingTransport, build_envelope
from tests.support.acquired_publisher_inputs import _record, _response
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi


DOI = "10.1109/ACCESS.2024.3352924"
TITLE = (
    "NDPmulator: Enabling Full-System Simulation for Near-Data Accelerators "
    "From Caches to DRAM"
)


def test_captured_figure_through_original_extraction_download_and_article(tmp_path):
    record, body = _record(DOI, "acquisition/figure-1.gif")
    sample = golden_criteria_sample_for_doi(DOI)
    raw = golden_criteria_asset(DOI, "original.html").read_text()
    metadata = {"doi": DOI, "title": TITLE}
    extraction = _ieee_html._extract_ieee_html(
        raw, sample["source_url"], metadata=metadata
    )
    selected = [
        asset
        for asset in extraction.extracted_assets
        if asset.get("url") == record["requested_url"]
    ]
    assert len(selected) == 1
    assert selected[0]["kind"] == "figure"
    transport = RecordingTransport(
        {("GET", record["requested_url"]): _response(record, body)}
    )
    result = download_assets(
        FIGURE_KIND,
        transport,
        article_id=DOI,
        assets=selected,
        output_dir=tmp_path,
        user_agent="offline replay",
        asset_profile="body",
        options=AssetDownloadOptions(
            asset_download_concurrency=1, provider_name="ieee"
        ),
    )
    assert not result["asset_failures"]
    assert len(result["assets"]) == 1
    downloaded = result["assets"][0]
    assert Path(downloaded["path"]).read_bytes() == body
    payload = RawFulltextPayload(
        provider="ieee",
        content=ProviderContent(
            route_kind="html",
            source_url=sample["source_url"],
            content_type="text/html",
            body=raw.encode(),
            markdown_text=extraction.markdown_text,
            merged_metadata=metadata,
            extracted_assets=extraction.extracted_assets,
            diagnostics={"extraction": asdict(extraction)},
        ),
    )
    article = ieee.IeeeClient(transport, {}).to_article_model(
        metadata, payload, downloaded_assets=result["assets"]
    )
    rendered = article.to_ai_markdown(max_tokens="full_text", asset_profile="body")
    assert article.quality.has_fulltext
    assert rendered.count(downloaded["path"]) == 1
    assert f"]({record['requested_url']})" not in rendered
    final = [asset for asset in article.assets if asset.path == downloaded["path"]]
    assert len(final) == 1
    assert final[0].caption == selected[0]["caption"]
    caption = "Physical representation of the proposed NDPmulator"
    assert caption in selected[0]["caption"]
    assert caption in rendered
    assert rendered.index(downloaded["path"]) < rendered.index(caption)


@pytest.mark.parametrize("expected_count", [0, 60])
def test_original_reference_pages_overlap_and_preserve_every_entry(expected_count):
    responses = {}
    originals = []
    urls = []
    for index in range(3):
        record, body = _record(DOI, f"acquisition/browser-references-{index}.json")
        payload = json.loads(body)
        assert str(payload["articleNumber"]) == "10388355"
        assert "NDPmulator" in payload["title"]
        originals.append(payload["references"])
        url = record["requested_url"]
        urls.append(url)
        responses[("GET", url)] = _response(record, body)
    assert [len(page) for page in originals] == [30, 30, 1]
    assert originals[0][-1] == originals[1][0]
    assert originals[2][0]["order"] == "60"
    transport = RecordingTransport(responses)
    actual = fetch_ieee_reference_metadata(
        transport,
        "10388355",
        headers={},
        decode_body=lambda body: body.decode(),
        expected_count=expected_count,
    )
    assert [call["url"] for call in transport.calls] == urls
    expected = {row["order"]: row for page in originals for row in page}
    assert [row["label"] for row in actual] == [str(i) for i in range(1, 61)]
    for row in actual:
        original = expected[row["label"]]
        text = BeautifulSoup(original["text"], "html.parser").get_text(" ")
        assert row["raw"] == " ".join(html.unescape(text).split())
        title = BeautifulSoup(original["title"], "html.parser").get_text(" ")
        assert row["title"] == " ".join(html.unescape(title).split())
        link = original.get("links", {}).get("crossRefLink")
        if link and "doi.org/" in link:
            assert row["doi"] == link.split("doi.org/", 1)[1].lower()
    assert "Gem5-SALAM" in actual[-1]["raw"]


def test_captured_stamp_pdf_current_provider_and_final_article():
    stamp, stamp_body = _record(DOI, "acquisition/browser-stamp.html")
    record, body = _record(DOI, "original.pdf")
    frame = BeautifulSoup(stamp_body, "html.parser").find("iframe", src=True)
    assert frame is not None
    assert urljoin(stamp["final_url"], frame["src"]) == record["requested_url"]
    with pymupdf.open(stream=body, filetype="pdf") as document:
        assert len(document) == 17
        assert DOI in document[0].get_text()
        assert "NDPmulator" in document[0].get_text()
    url = record["requested_url"]
    transport = RecordingTransport({("GET", url): _response(record, body)})
    client = ieee.IeeeClient(transport, {})
    metadata = {
        "doi": DOI,
        "article_number": "10388355",
        "title": TITLE,
        "pdfUrl": url,
    }
    landing = IeeeLandingAttempt(
        normalized_doi=DOI,
        landing_url="https://ieeexplore.ieee.org/document/10388355/",
        response_url=stamp["final_url"],
        html_text=stamp_body.decode(),
        merged_metadata=metadata,
        article_number="10388355",
        landing_metadata=metadata,
    )
    # HTML failure is injected; the PDF candidate is bound to the real stamp.
    with (
        RuntimeContext(env={}, transport=transport) as context,
        mock.patch(
            "paper_fetch.providers._pdf_fallback._build_cookie_seeded_opener",
            return_value=None,
        ),
    ):
        payload = client._fetch_pdf_payload(
            landing,
            html_failure_message="Injected HTML failure for PDF replay.",
            warnings=[],
            context=context,
        )
        article = client.to_article_model(metadata, payload, context=context)
    assert article.source == "ieee_pdf"
    assert article.quality.has_fulltext
    rendered = article.to_ai_markdown(include_refs="all", max_tokens="full_text")
    assert "NDPmulator" in rendered
    assert payload.content.markdown_text in rendered
    assert "fulltext:ieee_pdf_fallback_ok" in article.quality.source_trail
    acceptance = evaluate_fetch_acceptance(
        build_envelope(article), asset_profile="none", doi=DOI, expected_doi=DOI
    )
    assert acceptance.overall == "degraded"
