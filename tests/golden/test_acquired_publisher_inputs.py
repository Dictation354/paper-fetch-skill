"""Replay 2026-09-14 response bytes, preserving endpoint and evidence limits."""

from tests.support.acquired_publisher_inputs import _record, _response
import json
from unittest import mock
import pymupdf
import pytest
from paper_fetch.extraction.html.assets import (
    AssetDownloadOptions,
    FIGURE_KIND,
    download_assets,
)
from paper_fetch.extraction.html.signals import HtmlExtractionFailure
from paper_fetch.http import RequestFailure
from paper_fetch.providers import elsevier, frontiers, springer
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers._iop_html import extract_supplementary_data_assets
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from paper_fetch.service import build_fetch_envelope
from paper_fetch.models import RenderOptions
from tests.golden_corpus import golden_corpus_fixture_for_doi
from tests.golden_criteria import golden_criteria_asset
from tests.support._paper_fetch_support import RecordingTransport, FixtureHtmlTransport
from tests.support.reviewed_block_provider_paths import _fetch_through_service


def test_elsevier_open_access_pdf_api_complete_response_and_article():
    doi = "10.1016/j.envres.2018.12.059"
    record, body = _record(doi, "original.pdf")
    assert record["status_code"] == 200
    assert record["response_headers"]["x-els-status"] == "OK"
    with pymupdf.open(stream=body, filetype="pdf") as document:
        assert len(document) == 11
        assert doi in document[0].get_text()
    transport = RecordingTransport(
        {("GET", record["requested_url"]): _response(record, body)}
    )
    client = elsevier.ElsevierClient(
        transport, {"ELSEVIER_API_KEY": "offline-fixture-key"}
    )
    # Explicit PDF API invocation; this does not simulate a live XML failure.
    payload = client._fetch_official_pdf_payload(doi)
    assert payload.content.body == body
    assert len(transport.calls) == 1
    article = client.to_article_model(
        {
            "doi": doi,
            "title": "New approach to identifying proper thresholds for a heat warning system using health risk increments",
        },
        payload,
    )
    assert article.quality.has_fulltext
    assert "fulltext:elsevier_pdf_api_ok" in article.quality.source_trail
    envelope = build_fetch_envelope(
        article,
        modes={"article", "markdown"},
        render=RenderOptions(include_refs="all", asset_profile="none"),
    )
    assert article.sections[0].text == payload.content.markdown_text
    assert payload.content.markdown_text in envelope.markdown
    acceptance = evaluate_fetch_acceptance(
        envelope, asset_profile="none", doi=doi, expected_doi=doi
    )
    assert acceptance.content.has_fulltext
    assert acceptance.overall == "degraded"


@pytest.mark.parametrize(
    "doi,provider,pages",
    [
        ("10.1038/s43247-024-01295-w", "springer", 10),
        ("10.3389/fmars.2023.1101972", "frontiers", 12),
    ],
)
def test_acquired_same_paper_pdf_current_provider_and_acceptance(doi, provider, pages):
    record, body = _record(doi, "original.pdf")
    fixture = golden_corpus_fixture_for_doi(doi)
    transport = FixtureHtmlTransport({record["requested_url"]: _response(record, body)})
    client = (
        springer.SpringerClient if provider == "springer" else frontiers.FrontiersClient
    )(transport, {})
    metadata = {
        "doi": doi,
        "title": fixture.title,
        "provider": provider,
        "official_provider": True,
        "landing_page_url": record["requested_url"]
        .removesuffix(".pdf")
        .removesuffix("/pdf"),
        "fulltext_links": [
            {"url": record["requested_url"], "content_type": "application/pdf"}
        ],
    }
    # HTML/XML transport failure and cookie seed setup are injected. The actual
    # PDF request uses its captured HTTP envelope through the provider waterfall.
    with mock.patch(
        "paper_fetch.providers._pdf_fallback._build_cookie_seeded_opener",
        return_value=None,
    ):
        envelope = _fetch_through_service(client, fixture, metadata)
    article = envelope.article
    assert article is not None and article.quality.has_fulltext
    assert article.source == f"{provider}_pdf"
    assert f"fulltext:{provider}_pdf_fallback_ok" in article.quality.source_trail
    text = article.to_ai_markdown(include_refs="all", max_tokens="full_text")
    assert article.sections[0].text in text
    with pymupdf.open(stream=body, filetype="pdf") as document:
        assert len(document) == pages
        assert doi in document[0].get_text()
    acceptance = evaluate_fetch_acceptance(
        envelope, asset_profile="none", doi=doi, expected_doi=doi
    )
    assert acceptance.overall == "degraded"


@pytest.mark.parametrize("header_case", ["original", "upper"])
def test_elsevier_actual_first_page_entitlement_response_is_rejected(header_case):
    doi = "10.1016/j.agrformet.2024.109975"
    record, body = _record(doi, "acquisition/pdf-first-page.pdf")
    response = _response(record, body)
    if header_case == "upper":
        # Header casing is a mechanism variation; body stays the real response.
        response["headers"] = {
            key.upper(): value for key, value in response["headers"].items()
        }
    with pymupdf.open(stream=body, filetype="pdf") as document:
        assert len(document) == 1 and doi in document[0].get_text()
    transport = RecordingTransport({("GET", record["requested_url"]): response})
    client = elsevier.ElsevierClient(
        transport, {"ELSEVIER_API_KEY": "injected-test-key"}
    )
    with pytest.raises(ProviderFailure, match="further retrieval stopped") as failure:
        client._fetch_official_pdf_payload(doi)
    assert failure.value.code == "no_access"
    assert failure.value.details["confirmed_article_paywall"]["confirmed"]


@pytest.mark.parametrize(
    "status", [None, "WARNING - Bibliographic metadata may be incomplete"]
)
def test_elsevier_synthetic_pdf_unrelated_warning_control(status):
    from tests.support._paper_fetch_support import fulltext_pdf_bytes, http_response

    # Mechanism control: synthetic full PDF and optional unrelated warning.
    doi = "10.1016/j.example.2024.100001"
    client = elsevier.ElsevierClient(None, {"ELSEVIER_API_KEY": "injected-test-key"})
    url = client._official_article_url(doi)
    headers = {"x-els-status": status} if status else {}
    client.transport = RecordingTransport(
        {
            ("GET", url): http_response(
                url,
                fulltext_pdf_bytes(doi=doi),
                "application/pdf",
                headers=headers,
            )
        }
    )
    payload = client._fetch_official_pdf_payload(doi)
    assert payload.content.route_kind == "pdf_fallback"
    assert payload.content.markdown_text


def test_iop_actual_data_challenge_rejects_as_attachment_index():
    doi = "10.1088/2058-9565/ac3460"
    record, body = _record(doi, "acquisition/data-challenge.html")
    assert record["status_code"] == 200
    with pytest.raises(HtmlExtractionFailure) as failure:
        extract_supplementary_data_assets(
            body.decode(), record["requested_url"], expected_doi=doi
        )
    assert failure.value.reason == "iop_supplementary_index_blocked"


def test_tandf_actual_figure_challenge_reports_failed_asset(tmp_path):
    from tests.support.tandf_lst_render import source_html, DOI

    record, body = _record(DOI, "acquisition/figure-1-challenge.html")
    url = record["requested_url"]
    from paper_fetch.providers.tandf import TandfClient
    from tests.support.tandf_lst_render import URL

    markdown, _ = TandfClient(None, {}).extract_markdown(
        source_html(), URL, metadata={"doi": DOI}
    )
    assert url in markdown
    transport = RecordingTransport(
        {
            ("GET", url): RequestFailure(
                record["status_code"],
                record["error"],
                body=body,
                headers=record["response_headers"],
                url=record["final_url"],
            )
        }
    )
    result = download_assets(
        FIGURE_KIND,
        transport,
        article_id=DOI,
        assets=[
            {"kind": "figure", "heading": "Figure 1", "url": url, "section": "body"}
        ],
        output_dir=tmp_path,
        user_agent="offline replay",
        asset_profile="body",
        options=AssetDownloadOptions(
            candidate_builder=lambda *_a, **_k: [url],
            asset_download_concurrency=1,
            fetch_policy="direct_then_browser",
            provider_name="tandf",
        ),
    )
    assert result["assets"] == []
    assert len(result["asset_failures"]) == 1
    failure = result["asset_failures"][0]
    assert failure["source_url"] == url
    assert failure["status"] == 403
    assert failure["reason"] == record["error"]
    assert record["response_headers"]["cf-mitigated"] == "challenge"
    assert b"Just a moment..." in body
    assert not list(tmp_path.rglob("*.jpg"))


def test_frontiers_actual_api_resolves_same_article_supplementary_link():
    doi = "10.3389/fmars.2023.1101972"
    api, api_body = _record(doi, "acquisition/supplemental-data.json")
    transport = RecordingTransport(
        {("GET", api["requested_url"]): _response(api, api_body)}
    )
    fixture = golden_corpus_fixture_for_doi(doi)
    client = frontiers.FrontiersClient(transport, {})
    from paper_fetch.providers._article_markdown_jats import parse_jats_xml
    from paper_fetch.models import article_from_markdown

    extraction = parse_jats_xml(
        fixture.raw_path.read_bytes(), source_url=fixture.source_url
    )
    assets, _ = frontiers._normalize_frontiers_extracted_assets(
        extraction.assets, doi=doi, landing_url=fixture.landing_url
    )
    pending = [
        a for a in assets if a.get("source_href", "").casefold() == "table_1.docx"
    ]
    assert len(pending) == 1
    resolved = client._resolve_supplementary_urls(pending, doi)
    official_url = json.loads(api_body)[0]["downloadUrl"]
    assert resolved[0]["download_url"] == official_url
    article = article_from_markdown(
        source="frontiers_xml",
        doi=doi,
        metadata=extraction.metadata,
        markdown_text=extraction.markdown_text,
        assets=resolved,
    )
    rendered = article.to_ai_markdown(
        include_refs="none", max_tokens="full_text", asset_profile="all"
    )
    assert any(
        official_url in (a.original_url, a.download_url, a.source_url)
        for a in article.assets
    )
    assert "Supplementary material" in rendered
    assert len(transport.calls) == 1


@pytest.mark.parametrize("page_kind", ["excerpt", "captured"])
def test_arxiv_same_version_ancillary_discovery_and_article_link_metadata(page_kind):
    from paper_fetch.providers._arxiv_assets import discover_arxiv_ancillary_assets
    from paper_fetch.runtime import RuntimeContext
    from paper_fetch.models import article_from_markdown
    from tests.support._paper_fetch_support import http_response

    doi = "10.48550/arxiv.0811.2625v2"
    abs_url = "https://arxiv.org/abs/0811.2625v2"
    details_url = "https://arxiv.org/src/0811.2625v2/anc"
    responses = {
        ("GET", abs_url): http_response(
            abs_url,
            golden_criteria_asset(doi, "abstract-excerpt.html").read_bytes(),
            "text/html",
        ),
        ("GET", details_url): http_response(
            details_url,
            golden_criteria_asset(doi, "ancillary-excerpt.html").read_bytes(),
            "text/html",
        ),
    }
    if page_kind == "captured":
        for filename in ("abstract-page.html", "ancillary-page.html"):
            record, body = _record(doi, "acquisition/" + filename)
            assert record["status_code"] == 200
            responses[("GET", record["requested_url"])] = _response(record, body)
    transport = RecordingTransport(responses)
    with RuntimeContext(env={}) as context:
        version, discovered = discover_arxiv_ancillary_assets(
            transport, "0811.2625v2", user_agent="offline replay", context=context
        )
    assert version == "0811.2625v2" and not discovered["asset_failures"]
    assert {a["source_path"] for a in discovered["assets"]} == {
        "solve-sparse-opt-check-small.nb",
        "solve-sparse-opt-check-small.pdf",
    }
    article = article_from_markdown(
        source="arxiv_html",
        doi=doi,
        metadata={"title": "Maximizing the number of q-colorings"},
        markdown_text="## Ancillary files",
        assets=discovered["assets"],
    )
    rendered = article.to_ai_markdown(
        include_refs="none", max_tokens="full_text", asset_profile="all"
    )
    links = {
        url
        for a in article.assets
        for url in (a.original_url, a.download_url, a.source_url)
    }
    for asset in discovered["assets"]:
        assert asset["url"] in links
        assert asset["source_path"] in rendered
    assert len(transport.calls) == 2
