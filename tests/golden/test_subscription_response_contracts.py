"""Fixed DOI + response access expectations, through current provider boundaries."""

from types import SimpleNamespace
from unittest import mock

import pytest

from paper_fetch.providers import browser_runtime, royalsocietypublishing
from paper_fetch.quality.access_boundary import html_paywall_diagnostics
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.support.acquired_article_assets import CLIENTS
from tests.support.acquired_publisher_inputs import _record
from tests.support._browser_workflow_deps import install_browser_workflow_deps
from tests.support._paper_fetch_support import RecordingTransport
from tests.support.reviewed_block_provider_paths import _fetch_through_service
from tests.support.subscription_scenarios import SUBSCRIPTION_RESPONSES


@pytest.mark.parametrize("provider,doi,filename,expected_gate", SUBSCRIPTION_RESPONSES)
def test_captured_response_has_independent_access_expectation(
    provider, doi, filename, expected_gate, tmp_path
):
    path = (
        filename
        if filename.startswith("acquisition/")
        else "acquisition/subscription-2026-09-15/" + filename
    )
    record, raw = _record(doi, path)
    metadata = {
        "doi": doi,
        "provider": provider,
        "official_provider": True,
        "landing_page_url": record["final_url"],
    }
    diagnostics = html_paywall_diagnostics(
        raw, metadata=metadata, source_url=record["final_url"], provider=provider
    )
    assert bool(diagnostics) is expected_gate
    if not expected_gate:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(raw, "html.parser")
        if provider == "ams":
            assert "Introduction" in soup.select_one("#articleBody").get_text()
        elif provider == "wiley":
            assert soup.select_one(".article-section__abstract") is not None
            assert not any("Introduction" in h.text for h in soup.select("h2"))
        return
    assert diagnostics["confirmed_article_paywall"]["doi"] == doi.lower()
    cls = {
        **CLIENTS,
        "royalsocietypublishing": royalsocietypublishing.RoyalsocietypublishingClient,
    }[provider]
    transport = RecordingTransport({})
    client = cls(transport, {})
    runtime = browser_runtime.BrowserRuntimeConfig(
        provider=provider,
        doi=doi,
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
    )
    fetched = browser_runtime.BrowserFetchedHtml(
        source_url=record["requested_url"],
        final_url=record["final_url"],
        html=raw.decode(),
        response_status=record["status_code"],
        response_headers=record["response_headers"],
        title="",
        summary="",
        browser_context_seed={},
    )
    html = mock.Mock(return_value=fetched)
    forbidden = mock.Mock(side_effect=AssertionError("Request after confirmed gate"))
    install_browser_workflow_deps(
        client,
        load_runtime_config=mock.Mock(return_value=runtime),
        ensure_runtime_ready=mock.Mock(),
        fetch_html_with_browser=html,
        warm_browser_context=mock.Mock(return_value={}),
        fetch_pdf_with_browser=forbidden,
    )
    client.download_related_assets = forbidden
    fixture = SimpleNamespace(
        doi=doi, provider=provider, source_url=record["final_url"]
    )
    envelope = _fetch_through_service(
        client, fixture, metadata, output_dir=tmp_path, asset_profile="all"
    )
    html.assert_called_once()
    forbidden.assert_not_called()
    assert transport.calls == []  # Includes REST, TDM and reference pagination.
    article = envelope.article
    assert article.doi == doi.lower()
    assert not article.quality.has_fulltext
    received = diagnostics["received_metadata"]
    assert article.metadata.title == received["title"]
    if received.get("abstract"):
        assert article.metadata.abstract == received["abstract"].removeprefix(
            "Abstract "
        )
    acceptance = evaluate_fetch_acceptance(
        envelope, doi=doi, expected_doi=doi, asset_profile="all"
    )
    assert acceptance.overall == "limited"


@pytest.mark.parametrize("entry", ["http", "browser"])
def test_oup_received_subscription_entity_and_dom_stop_before_pdf(entry, tmp_path):
    import json
    from paper_fetch.providers import oxfordacademic
    from tests.block_fixtures import iter_block_samples
    from tests.support._paper_fetch_support import FixtureHtmlTransport

    fixture = next(
        f for f in iter_block_samples() if f.doi == "10.1093/reseval/rvag052"
    )
    records = json.loads(fixture.asset("acquisition/provenance.json").read_text())[
        "records"
    ]
    record = next(
        r
        for r in records
        if r["capture_kind"] == "http_response_entity" and r["status_code"] == 200
    )
    body = (
        fixture.asset(record["body_file"]).read_bytes()
        if entry == "http"
        else fixture.raw_path.read_bytes()
    )
    metadata = {
        "doi": fixture.doi,
        "title": fixture.title,
        "provider": fixture.provider,
        "official_provider": True,
        "landing_page_url": record["final_url"],
    }
    transport = FixtureHtmlTransport(
        {
            record["final_url"]: {
                "status_code": 200,
                "headers": record["response_headers"],
                "url": record["final_url"],
                "body": body,
            }
        }
        if entry == "http"
        else {}
    )
    client = oxfordacademic.OxfordAcademicClient(transport, {})
    if entry == "browser":
        # DOM replay enters the existing attempt boundary; no invented HTTP status.
        client._fetch_article_attempt = mock.Mock(
            return_value=oxfordacademic.OxfordAcademicArticleAttempt(
                doi=fixture.doi,
                requested_url=fixture.source_url,
                final_url=fixture.source_url,
                html_text=body.decode(),
                response_status=None,
                response_headers={},
                metadata=metadata,
            )
        )
    forbidden = mock.Mock(side_effect=AssertionError("Request after OUP gate"))
    client._request_pdf_candidate = forbidden
    client.download_related_assets = forbidden
    envelope = _fetch_through_service(
        client, fixture, metadata, output_dir=tmp_path, asset_profile="all"
    )
    forbidden.assert_not_called()
    assert len(transport.calls) == (1 if entry == "http" else 0)
    article = envelope.article
    assert article.doi == fixture.doi
    assert article.metadata.title == fixture.title
    assert "Drawing on 30 critical-incident interviews" in article.metadata.abstract
    assert not article.quality.has_fulltext
    assert (
        evaluate_fetch_acceptance(
            envelope, doi=fixture.doi, expected_doi=fixture.doi, asset_profile="all"
        ).overall
        == "limited"
    )


@pytest.mark.parametrize("doi", ["10.1126/sciadv.abf8021", "10.1073/pnas.2406303121"])
def test_historical_download_does_not_gain_an_invented_http_envelope(doi):
    record, body = _record(doi, "original.pdf")
    assert body.startswith(b"%PDF-")
    assert record["capture_kind"] == "downloaded_provider_artifact"
    assert record["status_code"] is None
    assert record["final_url"] is None
