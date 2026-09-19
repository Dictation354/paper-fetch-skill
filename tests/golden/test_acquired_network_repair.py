"""Real IOP/arXiv supplementary indexes and retained T&F body image bytes."""

import pymupdf
import pytest
from paper_fetch.extraction.html._metadata import parse_html_metadata
from paper_fetch.providers import _iop_html
from paper_fetch.providers.iop import IopClient
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers._arxiv_assets import discover_arxiv_ancillary_assets
from paper_fetch.runtime import RuntimeContext
from tests.golden_criteria import golden_criteria_asset
from tests.support._paper_fetch_support import RecordingTransport
from tests.support.acquired_publisher_inputs import _record, _response
from tests.support.iop_provider import (
    _FakeIopSupplementaryIndexFetcher,
    _iop_supplementary_test_deps,
)


PREFIX = "acquisition/network-repair/"


@pytest.mark.parametrize("index", range(1, 13))
def test_tandf_original_jpeg_matches_browser_recovered_figure(index):
    doi = "10.1080/17538947.2022.2137254"
    name = f"tjde_a_2137254_f{index:04d}_oc"
    record, jpeg = _record(doi, PREFIX + "raw-body-assets/" + name + ".jpg")
    recovered, png = _record(doi, PREFIX + "body-assets/" + name + ".png")
    assert record["status_code"] == 200
    assert record["capture_kind"] == "http_response_entity"
    assert recovered["capture_kind"] == "browser_recovered_image"
    assert record["requested_url"] == recovered["requested_url"]
    assert jpeg.startswith(b"\xff\xd8\xff") and png.startswith(b"\x89PNG\r\n\x1a\n")
    original = pymupdf.Pixmap(jpeg)
    browser = pymupdf.Pixmap(png)
    assert (original.width, original.height) == (browser.width, browser.height)
    assert (original.width, original.height) == (record["width"], record["height"])
    if browser.alpha:
        browser = pymupdf.Pixmap(browser, 0)
    original = pymupdf.Pixmap(pymupdf.csRGB, original)
    browser = pymupdf.Pixmap(pymupdf.csRGB, browser)
    # Compare the complete images with a 1% mean RGB tolerance for browser
    # serialization and decoder differences, rather than byte equality.
    left, right = original.samples, browser.samples
    assert len(left) == len(right)
    mean_error = sum(abs(a - b) for a, b in zip(left, right, strict=True)) / len(left)
    assert mean_error / 255 < 0.01


def test_iop_real_article_index_and_link_metadata():
    doi = "10.1088/1748-9326/ab7d02"
    source = f"https://iopscience.iop.org/article/{doi}"
    html = golden_criteria_asset(doi, "original.html").read_text()
    metadata = {**parse_html_metadata(html, source), "doi": doi}
    index_record, index_body = _record(doi, PREFIX + "supplementary-index.html")
    assert index_record["status_code"] == 200
    indexes = _iop_html.extract_supplementary_index_urls(html, source, doi=doi)
    assert indexes == [index_record["requested_url"]]
    fetcher = _FakeIopSupplementaryIndexFetcher(_response(index_record, index_body))
    transport = RecordingTransport({})
    client = IopClient(transport, {}, deps=_iop_supplementary_test_deps(fetcher))
    markdown, extraction = client.extract_markdown(html, source, metadata=metadata)
    payload = RawFulltextPayload(
        provider="iop",
        content=ProviderContent(
            route_kind="html",
            source_url=source,
            content_type="text/html",
            body=html.encode(),
            markdown_text=markdown,
            merged_metadata=metadata,
            diagnostics={"extraction": extraction},
        ),
    )
    with RuntimeContext(env={}, transport=transport) as context:
        assets, failures = client._resolve_supplementary_data_assets(
            doi, payload, indexes, context=context
        )
    assert not failures and len(assets) == 1
    assert fetcher.closed and len(fetcher.calls) == 1
    assert assets[0]["source_ref"] == "supp1"
    assert "ERL_15_5_054014_suppdata.pdf" in assets[0]["url"]
    assert not transport.calls
    article = client.to_article_model(metadata, payload, downloaded_assets=assets)
    rendered = article.to_ai_markdown(
        include_refs="all", max_tokens="full_text", asset_profile="all"
    )
    assert article.quality.has_fulltext and len(article.references) == 27
    assert any(
        assets[0]["url"] in (a.original_url, a.download_url, a.source_url)
        for a in article.assets
    )
    assert "Supplementary data" in rendered
    assert "internal variability" in rendered


@pytest.mark.parametrize("version,count", [("2606.00587v2", 1), ("0905.2326v2", 103)])
def test_arxiv_complete_index_and_article_link_metadata(version, count):
    doi = "10.48550/arxiv." + version
    responses = {}
    for name in ["abstract-page.html", "ancillary-page.html"]:
        record, body = _record(doi, "acquisition/" + name)
        responses[("GET", record["requested_url"])] = _response(record, body)
    with RuntimeContext(env={}) as context:
        observed, result = discover_arxiv_ancillary_assets(
            RecordingTransport(responses),
            version,
            user_agent="offline replay",
            context=context,
        )
    assert observed == version and not result["asset_failures"]
    from paper_fetch.models import article_from_markdown

    assets = result["assets"]
    assert len({a["source_path"] for a in assets}) == count
    article = article_from_markdown(
        source="arxiv_html",
        doi=doi,
        metadata={"title": version},
        markdown_text="## Ancillary files",
        assets=assets,
    )
    rendered = article.to_ai_markdown(
        include_refs="none", max_tokens="full_text", asset_profile="all"
    )
    links = {
        url
        for a in article.assets
        for url in (a.original_url, a.download_url, a.source_url)
    }
    for asset in assets:
        assert f"/src/{version}/anc/" in asset["url"]
        assert asset["url"] in links
        assert asset["source_path"] in rendered
