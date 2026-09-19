"""September 15 inputs: current PDF assembly and complete arXiv discovery pages.

Network retrieval is replayed or injected; conversion and article rendering run
the current implementation. This does not claim an unattended live fallback.
"""

import pymupdf
import pytest
from paper_fetch.models import RenderOptions
from paper_fetch.providers._pdf_common import pdf_fetch_result_from_bytes
from paper_fetch.providers._registry import provider_bundle
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers._arxiv_assets import discover_arxiv_ancillary_assets
from paper_fetch.runtime import RuntimeContext
from paper_fetch.service import build_fetch_envelope
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.support._paper_fetch_support import RecordingTransport
from tests.support.acquired_publisher_inputs import _record, _response


@pytest.mark.parametrize(
    "provider,doi,title,pages",
    [
        (
            "aip",
            "10.1063/5.0129134",
            "On-chip on-demand delivery of K+ for in vitro bioelectronics",
            9,
        ),
        (
            "science",
            "10.1126/sciadv.abf8021",
            "Increasing precipitation variability on daily-to-multiyear time scales in a warmer world",
            12,
        ),
        (
            "tandf",
            "10.1080/17538947.2022.2137254",
            "A new approach to LST modeling and normalization under clear-sky conditions based on a local optimization strategy",
            23,
        ),
        (
            "arxiv",
            "10.48550/arxiv.0811.2625v2",
            "Maximizing the number of q-colorings",
            43,
        ),
    ],
    ids=["aip", "science", "tandf", "arxiv"],
)
def test_complete_pdf_current_parser_provider_and_acceptance(
    provider, doi, title, pages
):
    record, body = _record(doi, "original.pdf")
    with pymupdf.open(stream=body, filetype="pdf") as document:
        assert len(document) == pages
        identity = "0811.2625v2" if provider == "arxiv" else doi
        assert any(identity in page.get_text() for page in document)
    source = record.get("requested_url") or f"https://doi.org/{doi}"
    result = pdf_fetch_result_from_bytes(
        artifact_dir=None,
        source_url=source,
        final_url=record.get("final_url") or source,
        pdf_bytes=body,
        expected_identity={"doi": doi, "title": title},
    )
    metadata = {"doi": doi, "title": title}
    if provider == "arxiv":
        metadata["arxiv_id"] = "0811.2625v2"
    payload = RawFulltextPayload(
        provider=provider,
        content=ProviderContent(
            route_kind="pdf_fallback",
            source_url=source,
            content_type="application/pdf",
            body=body,
            markdown_text=result.markdown_text,
            merged_metadata=metadata,
        ),
    )
    article = (
        provider_bundle(provider)
        .client_factory(None, {})
        .to_article_model(metadata, payload)
    )
    envelope = build_fetch_envelope(
        article,
        modes={"article", "markdown"},
        render=RenderOptions(
            include_refs="all", max_tokens="full_text", asset_profile="none"
        ),
    )
    acceptance = evaluate_fetch_acceptance(
        envelope, asset_profile="none", doi=doi, expected_doi=doi
    )
    assert acceptance.overall == "degraded"
    assert acceptance.content.has_fulltext
    assert envelope.markdown
    assert article.sections[0].text == result.markdown_text
    assert result.markdown_text in envelope.markdown
    assert article.references == []


@pytest.mark.parametrize("version,count", [("2606.00587v2", 1), ("0905.2326v2", 103)])
def test_complete_arxiv_pages_discover_exact_version_and_all_files(version, count):
    doi = "10.48550/arxiv." + version
    responses = {}
    for name in ["abstract-page.html", "ancillary-page.html"]:
        record, body = _record(doi, "acquisition/" + name)
        assert record["status_code"] == 200
        assert b"<html" in body.lower()
        responses[("GET", record["requested_url"])] = _response(record, body)
    transport = RecordingTransport(responses)
    with RuntimeContext(env={}) as context:
        observed, result = discover_arxiv_ancillary_assets(
            transport, version, user_agent="offline replay", context=context
        )
    assert observed == version
    assert not result["asset_failures"]
    assert len(result["assets"]) == count
    assert len(transport.calls) == 2
    assert all(f"/src/{version}/anc/" in asset["url"] for asset in result["assets"])
