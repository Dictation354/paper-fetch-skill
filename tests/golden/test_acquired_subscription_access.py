"""Real access evidence, independent of PDF conversion/formatting quality."""

import json
from types import SimpleNamespace
from urllib.parse import unquote
from bs4 import BeautifulSoup
import pytest
from paper_fetch.http import HttpTransport, RequestFailure
from paper_fetch.providers import elsevier, iop
from paper_fetch.extraction.html.signals import HtmlExtractionFailure
from paper_fetch.xml_security import parse_xml
from tests.golden_criteria import golden_criteria_asset
from tests.block_fixtures import execute_block_fixture, iter_block_samples
from tests.support.acquired_publisher_inputs import _record
from tests.support.reviewed_block_provider_paths import _fetch_through_service


PREFIX = "acquisition/subscription-2026-09-15/"
ELSEVIER_DOIS = (
    "10.1016/0034-4257(94)90046-9",
    "10.1016/0034-4257(88)90106-x",
    "10.1016/0168-1923(91)90003-9",
    "10.1016/0168-1923(91)90002-8",
)


def test_oxford_subscription_page_has_explicit_access_denial_and_only_abstract():
    fixture = next(
        f for f in iter_block_samples() if f.doi == "10.1093/reseval/rvag052"
    )
    provenance = json.loads(fixture.asset("acquisition/provenance.json").read_text())
    response = next(
        r
        for r in provenance["records"]
        if r["capture_kind"] == "http_response_entity" and r["status_code"] == 200
    )
    # Verify both the actual HTTP entity and the final headed browser DOM.
    for path in (fixture.asset(response["body_file"]), fixture.raw_path):
        soup = BeautifulSoup(path.read_bytes(), "html.parser")
        assert soup.select_one('meta[name="citation_doi"]')["content"] == fixture.doi
        assert (
            soup.select_one('meta[name="citation_title"]')["content"] == fixture.title
        )
        assert soup.select_one("#no-access-message").get_text(strip=True) == (
            "You do not currently have access to this article."
        )
        assert soup.select_one('a[href="/rev/subscribe"]') is not None
        assert "Drawing on 30 critical-incident interviews" in soup.select_one(
            ".abstract"
        ).get_text(" ", strip=True)
        assert [
            h.get_text(" ", strip=True) for h in soup.select(".article-body h2")
        ] == ["Abstract"]
    replay = execute_block_fixture(fixture)
    assert not replay.accepted
    assert replay.reason == "abstract_only"
    assert replay.content_kind == "abstract_only"


def test_tandf_subscription_page_has_article_purchase_and_no_fulltext():
    fixture = next(
        f for f in iter_block_samples() if f.doi == "10.1080/01431161.2025.2516689"
    )
    provenance = json.loads(fixture.asset("acquisition/provenance.json").read_text())
    response = next(
        r
        for r in provenance["records"]
        if r["capture_kind"] == "http_response_entity" and r["status_code"] == 200
    )
    for path in (fixture.asset(response["body_file"]), fixture.raw_path):
        soup = BeautifulSoup(path.read_bytes(), "html.parser")
        assert soup.select_one('meta[name="publication_doi"]')["content"] == fixture.doi
        assert soup.select_one('meta[name="dc.Title"]')["content"] == fixture.title
        assert (
            "subPage:string:Access Denial"
            in soup.select_one('meta[name="pbContext"]')["content"]
        )
        denial = soup.select_one("#accessDenialWidget")
        assert "Log in via your institution" in denial.get_text(" ", strip=True)
        assert denial.select_one("#purchaseLink") is not None
        assert "48 hours access to article PDF & online version" in denial.get_text(
            " ", strip=True
        )
        assert fixture.doi in denial.select_one("a.add-article-to-cart")["href"]
        assert "Complete remote-sensing time series with consistent length" in (
            soup.select_one(".hlFld-Abstract").get_text(" ", strip=True)
        )
        assert soup.select_one(".hlFld-Fulltext") is None
    replay = execute_block_fixture(fixture)
    assert not replay.accepted
    assert replay.reason == "abstract_only"
    # Current acceptance retains the abstract already present in this response.
    assert replay.content_kind == "abstract_only"


def _article(doi):
    return json.loads(golden_criteria_asset(doi, PREFIX + "article.json").read_text())


@pytest.mark.parametrize("doi", ELSEVIER_DOIS)
def test_legacy_elsevier_real_full_view_failures_exhaust_current_api_waterfall(doi):
    capture = json.loads(
        golden_criteria_asset(doi, PREFIX + "capture.json").read_text()
    )
    responses = [
        r for r in capture["responses"] if r.get("request_query") == {"view": "FULL"}
    ]
    assert len(responses) == 3
    calls = []

    class CapturedTransport(HttpTransport):
        def request(self, method, url, **kwargs):
            record = responses[len(calls)]
            assert method == "GET"
            assert url == record["requested_url"]
            assert kwargs["query"] == record["request_query"]
            calls.append(kwargs["headers"]["Accept"])
            body = golden_criteria_asset(doi, record["body_file"]).read_bytes()
            assert record["status_code"] == 400
            assert parse_xml(body).findtext("status/statusCode") == "INVALID_INPUT"
            raise RequestFailure(
                record["status_code"],
                record["error"],
                url=record["final_url"],
                headers=record["response_headers"],
                body=body,
            )

    metadata = _article(doi)["metadata"]
    client = elsevier.ElsevierClient(
        CapturedTransport(), {"ELSEVIER_API_KEY": "offline-fixture-key"}
    )
    fixture = SimpleNamespace(
        doi=doi, provider="elsevier", source_url=metadata.get("landing_page_url")
    )
    envelope = _fetch_through_service(client, fixture, metadata)
    assert calls == ["text/xml", "text/xml", "application/pdf"]
    assert not envelope.article.quality.has_fulltext
    assert envelope.article.quality.content_kind == "abstract_only"
    # Preserve the current error classification; do not relabel HTTP400 as 403.
    assert "fulltext:elsevier_pdf_api_fail" in envelope.article.quality.source_trail


@pytest.mark.parametrize("doi", ELSEVIER_DOIS)
def test_elsevier_entitlement_is_explicit_separate_api_evidence(doi):
    records = json.loads(
        golden_criteria_asset(doi, "acquisition/provenance.json").read_text()
    )["records"]
    record = next(r for r in records if r.get("request_query") == {"view": "ENTITLED"})
    body = golden_criteria_asset(doi, record["body_file"]).read_bytes()
    root = parse_xml(body)
    assert record["status_code"] == 401
    assert root.findtext("status") == "NOT_ENTITLED"
    assert "not entitled" in root.findtext("message")
    assert doi in unquote(root.findtext("url")).lower()


@pytest.mark.parametrize("doi", (ELSEVIER_DOIS[0], ELSEVIER_DOIS[3]))
def test_elsevier_http200_first_page_is_not_a_complete_pdf_access_success(doi):
    records = json.loads(
        golden_criteria_asset(doi, "acquisition/provenance.json").read_text()
    )["records"]
    record = next(
        r
        for r in records
        if r.get("request_accept") == "application/pdf"
        and "view-probe" in r["body_file"]
    )
    body = golden_criteria_asset(doi, record["body_file"]).read_bytes()
    assert record["status_code"] == 200
    assert body.startswith(b"%PDF-")
    assert "limited to first page" in record["response_headers"]["x-els-status"]
    assert "not entitled" in record["response_headers"]["x-els-status"]
    # File/entitlement checks only: no conversion, OCR or formatting assertions.


@pytest.mark.parametrize(
    "doi",
    (
        "10.1088/1681-7575/ae1dfc",
        "10.1088/0034-4885/53/3/002",
        "10.1088/2058-9565/ac3460",
    ),
)
def test_iop_real_subscription_html_and_pdf_target_both_return_access_page(doi):
    capture = json.loads(
        golden_criteria_asset(doi, PREFIX + "capture.json").read_text()
    )
    pages = [
        r
        for r in capture["responses"]
        if r["capture_kind"] == "http_response_entity" and r["status_code"] == 200
    ]
    assert any(r["requested_url"].endswith("/pdf") for r in pages)
    client = iop.IopClient(None, {})
    for record in pages:
        raw = golden_criteria_asset(doi, record["body_file"]).read_text()
        text = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
        assert (
            "not registered by an institution with a subscription to this article"
            in text
        )
        assert "Purchase this article" in text
        with pytest.raises(HtmlExtractionFailure) as error:
            client.extract_markdown(
                raw, record["final_url"], metadata=_article(doi)["metadata"]
            )
        assert error.value.reason == "abstract_only"
    assert not _article(doi)["quality"]["has_fulltext"]


@pytest.mark.parametrize(
    "doi,filename,access_text",
    [
        ("10.1021/ja00160a040", "response-003.bin", "You do not currently have access"),
        ("10.1063/5.0260731", "response-003.bin", "You do not currently have access"),
        ("10.1175/jas-d-26-0015.1", "response-001.bin", "Purchase article"),
        (
            "10.1098/rspa.1984.0023",
            "response-001.bin",
            "You do not currently have access",
        ),
        (
            "10.1038/s41586-026-11124-z",
            "response-001.bin",
            "preview of subscription content",
        ),
        ("10.1126/science.aeg3511", "response-003.bin", "Log in to view the full text"),
    ],
)
def test_real_subscription_page_and_recorded_cli_pdf_acceptance(
    doi, filename, access_text
):
    record, raw = _record(doi, PREFIX + filename)
    assert record["status_code"] == 200
    assert access_text in BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    manifest = json.loads(
        golden_criteria_asset(doi, PREFIX + "fetch.manifest.json").read_text()
    )
    # Preserve observed CLI output, including known wrong-document, preview,
    # and supplement false positives. This does not verify full-paper identity.
    acceptance = manifest["acceptance"]
    assert acceptance["overall"] == "degraded"
    assert acceptance["content"]["has_fulltext"]
    assert acceptance["provenance"]["acquisition"]["representation"] == "pdf"
    if doi == "10.1038/s41586-026-11124-z":
        # The historical CLI false positive remains recorded; the supplementary
        # payload was removed at the user's request and is not a body fixture.
        provenance = json.loads(
            golden_criteria_asset(doi, "acquisition/provenance.json").read_text()
        )
        assert any(
            r["former_body_file"] == PREFIX + "downloaded.pdf"
            for r in provenance["removed_records"]
        )
    else:
        assert (
            golden_criteria_asset(doi, PREFIX + "downloaded.pdf")
            .read_bytes()
            .startswith(b"%PDF-")
        )
