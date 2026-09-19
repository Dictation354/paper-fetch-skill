"""IEEE subscription landing through current readiness and provider waterfall.

Successful REST bytes are live captures. The failure case explicitly injects
REST/PDF transport failures; the browser's real captured DOM lacks article body.
"""

from tests.support.acquired_ieee_paywall_flow import DOI, URL, _captured_landing
from contextlib import nullcontext
from types import SimpleNamespace
from unittest import mock
from bs4 import BeautifulSoup
from paper_fetch.http import RequestFailure
from paper_fetch.providers import (
    _ieee_browser_html,
    _playwright_browser,
    browser_runtime,
)
from paper_fetch.providers._pdf_common import PdfFetchFailure
from paper_fetch.providers.ieee import IeeeClient
from paper_fetch.providers import ieee
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.support._paper_fetch_support import RecordingTransport
from tests.support.acquired_publisher_inputs import _record, _response
from tests.support.camoufox_backend import _Context
from tests.support.ieee_provider_routes import (
    _FakeIeeeBrowserContext,
    _FakeIeeeBrowserPage,
)
from tests.support.reviewed_block_provider_paths import _fetch_through_service


REST = "https://ieeexplore.ieee.org/rest/document/10612240/?logAccess=true"
PREFIX = "acquisition/ieee-flow-2026-09-15/"


def _setup_landing_browser(monkeypatch, tmp_path, raw, metadata):
    config = browser_runtime.BrowserRuntimeConfig(
        provider="ieee",
        doi=DOI,
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    browser = _Context()
    browser.page.content = lambda: raw
    browser.page.title = lambda: metadata["title"]

    def wait_for_captured_node(_script, *, arg, timeout):
        assert timeout > 0
        node = BeautifulSoup(raw, "html.parser").select_one(arg["selector"])
        if node is None or arg["expectedText"] not in str(node):
            raise TimeoutError("Captured subscription DOM never exposes this node.")

    browser.page.wait_for_function.side_effect = wait_for_captured_node
    monkeypatch.setattr(browser_runtime, "load_runtime_config", lambda *a, **k: config)
    monkeypatch.setattr(
        browser_runtime,
        "fetch_html_with_browser",
        _playwright_browser.fetch_html_with_playwright,
    )
    monkeypatch.setattr(
        _playwright_browser, "open_browser_context", lambda *a, **k: (None, browser)
    )
    return browser


def _transport_responses():
    responses = {}
    for filename in (
        "landing-http-response.html",
        "references-1.json",
        "references-2.json",
        "rest-body.html",
    ):
        record, body = _record(DOI, PREFIX + filename)
        responses[("GET", record["requested_url"])] = _response(record, body)
    return responses


def test_confirmed_paywall_landing_stops_even_when_rest_fixture_has_fulltext(
    monkeypatch, tmp_path
):
    raw, metadata = _captured_landing()
    assert BeautifulSoup(raw, "html.parser").select_one("#article") is None
    browser = _setup_landing_browser(monkeypatch, tmp_path, raw, metadata)
    transport = RecordingTransport(_transport_responses())
    client = IeeeClient(transport, {})
    fixture = SimpleNamespace(doi=DOI, provider="ieee", source_url=URL)
    with (
        mock.patch.object(client, "_fetch_browser_html_payload") as browser_html,
        mock.patch.object(client, "_fetch_pdf_payload") as pdf,
    ):
        envelope = _fetch_through_service(client, fixture, metadata)
    assert browser.page.wait_for_function.called
    browser_html.assert_not_called()
    pdf.assert_not_called()
    assert [call["url"] for call in transport.calls] == [URL]
    article = envelope.article
    assert article.quality.content_kind == "abstract_only"
    assert article.metadata.abstract
    assert "trace:confirmed_article_paywall" in article.quality.source_trail
    acceptance = evaluate_fetch_acceptance(
        envelope, doi=DOI, expected_doi=DOI, asset_profile="none"
    )
    assert acceptance.overall == "limited"


def test_confirmed_paywall_landing_prevents_rest_browser_and_pdf_requests(
    monkeypatch, tmp_path
):
    raw, metadata = _captured_landing()
    _setup_landing_browser(monkeypatch, tmp_path, raw, metadata)
    responses = _transport_responses()
    responses[("GET", REST)] = RequestFailure(
        403,
        "Injected REST HTTP 403 for fallback verification.",
        url=REST,
        headers={"content-type": "text/html"},
    )
    transport = RecordingTransport(responses)
    client = IeeeClient(transport, {})
    events = []

    class PaywallPage(_FakeIeeeBrowserPage):
        def goto(self, url, **kwargs):
            events.append("browser_html")
            return super().goto(url, **kwargs)

        def title(self):
            return metadata["title"]

    page = PaywallPage(URL, html_text=raw)
    fake_context = _FakeIeeeBrowserContext(page)
    monkeypatch.setattr(
        _ieee_browser_html,
        "browser_context",
        lambda *a, **k: nullcontext(SimpleNamespace(context=fake_context)),
    )
    # Advance the observation budget in the offline browser only.
    monkeypatch.setattr(_ieee_browser_html, "IEEE_BROWSER_HTML_REST_WAIT_TIMEOUT_MS", 1)

    def failed_pdf(route):
        def fetch(*args, **kwargs):
            events.append(route)
            candidates = args[1] if route == "direct_pdf" else args[0]
            assert candidates and all("10612240" in url for url in candidates)
            raise PdfFetchFailure(
                "pdf_download_failed",
                f"Injected {route} transport failure.",
                details={"status": 403, "content_type": "text/html"},
            )

        return fetch

    monkeypatch.setattr(ieee, "fetch_pdf_over_http", failed_pdf("direct_pdf"))
    monkeypatch.setattr(ieee, "fetch_pdf_with_browser", failed_pdf("browser_pdf"))
    fixture = SimpleNamespace(doi=DOI, provider="ieee", source_url=URL)
    envelope = _fetch_through_service(client, fixture, metadata)
    assert events == []
    assert [call["url"] for call in transport.calls] == [URL]
    article = envelope.article
    assert article.quality.content_kind == "abstract_only"
    assert article.quality.has_abstract
    assert "trace:confirmed_article_paywall" in article.quality.source_trail
