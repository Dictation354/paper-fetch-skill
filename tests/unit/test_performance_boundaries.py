from unittest import mock

from bs4 import BeautifulSoup
import pytest

from paper_fetch.http import RequestCancelledError, RequestFailure
from paper_fetch.providers import _arxiv_atom, _playwright_browser
from paper_fetch.providers.arxiv import ArxivClient
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers._payloads import build_provider_payload
from paper_fetch.providers.browser_runtime import BrowserHtmlReadiness
from paper_fetch.providers.browser_workflow.fetchers import readiness
from paper_fetch.quality import access_boundary, html_availability
from paper_fetch.runtime import RuntimeContext
from tests.support._paper_fetch_support import RecordingTransport, http_response


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"html": "", "title": "", "url": "https://example.test"},
        {"html": "<html></html>", "title": 1, "url": "https://example.test"},
        {"html": "<html></html>", "title": "", "url": "https://other.test"},
    ],
)
def test_main_context_snapshot_invalid_result_uses_native_fallback(payload):
    page = mock.Mock(url="https://example.test")
    page.evaluate.return_value = payload
    assert _playwright_browser._main_context_html_snapshot(page) is None


@pytest.mark.parametrize(
    "error", [RuntimeError("navigation"), RequestCancelledError("cancelled")]
)
def test_main_context_snapshot_capture_error_preserves_cancellation(error):
    page = mock.Mock(url="https://example.test")
    page.evaluate.side_effect = error
    if isinstance(error, RequestCancelledError):
        with pytest.raises(RequestCancelledError):
            _playwright_browser._main_context_html_snapshot(page)
    else:
        assert _playwright_browser._main_context_html_snapshot(page) is None


def test_aip_terminal_readiness_records_block_instead_of_timeout():
    page = mock.Mock()
    page.evaluate.return_value = {
        "ready": False,
        "blockingReason": "cloudflare_challenge",
    }
    trace = {}
    result = _playwright_browser._wait_for_browser_html_readiness(
        page,
        publisher="aip",
        readiness=BrowserHtmlReadiness(wait_for_article_body=True),
        wait_seconds=5,
        timeout_ms=120000,
        request_started=readiness.time.monotonic(),
        return_image_payload=False,
        runtime_context=None,
        candidate_trace=trace,
        readiness_timeout_seconds=90,
    )
    assert result.blocking_reason == "cloudflare_challenge"
    assert trace["dom_readiness_result"] == "blocked"
    page.wait_for_timeout.assert_not_called()


def test_transient_challenge_can_become_ready():
    page = mock.Mock()
    page.evaluate.side_effect = [
        {"ready": False},
        {"ready": True, "fingerprint": "body"},
        {"ready": True, "fingerprint": "body"},
    ]
    result = readiness.wait_for_atypon_body_dom_ready(page, "aip", timeout_seconds=90)
    assert result.ready and result.blocking_reason is None
    assert page.wait_for_timeout.call_count == 2


def test_readiness_propagates_cancellation():
    page = mock.Mock()
    with pytest.raises(RequestCancelledError):
        readiness.wait_for_atypon_body_dom_ready(
            page,
            "aip",
            timeout_seconds=90,
            cancel_check=mock.Mock(side_effect=RequestCancelledError("cancelled")),
        )
    page.evaluate.assert_not_called()


@pytest.mark.parametrize(
    "failure",
    [
        RequestFailure(None, "Timed out", error_category="timeout"),
        RequestFailure(429, "Rate limited"),
        RequestFailure(None, "connection closed", error_category="connection_closed"),
    ],
)
def test_optional_atom_has_one_short_attempt_and_falls_back(failure):
    transport = RecordingTransport({("GET", _arxiv_atom.ARXIV_API_URL): failure})
    client = ArxivClient(transport, {})
    metadata, warnings = client._fetch_api_metadata_optional("2605.06663v1")
    assert metadata is None and "using official HTML front matter" in warnings[0]
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["timeout"] == 10
    assert call["retry_on_transient"] is call["retry_on_rate_limit"] is False
    assert call["transient_retries"] == call["rate_limit_retries"] == 0
    assert call["request_policy"].minimum_interval_seconds == 1


@pytest.mark.parametrize(
    "failure",
    [
        RequestCancelledError("cancelled"),
        RequestFailure(403, "Forbidden"),
        RequestFailure(402, "Payment Required"),
    ],
)
def test_optional_atom_propagates_cancellation_and_access_restriction(failure):
    transport = RecordingTransport({("GET", _arxiv_atom.ARXIV_API_URL): failure})
    client = ArxivClient(transport, {})
    with pytest.raises(
        RequestCancelledError
        if isinstance(failure, RequestCancelledError)
        else ProviderFailure
    ):
        client._fetch_api_metadata_optional("2605.06663v1")


def test_optional_atom_success_and_independent_metadata_policy():
    body = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
    <id>http://arxiv.org/abs/2605.06663v1</id><title>API title</title>
    <summary>API abstract</summary></entry></feed>"""
    transport = RecordingTransport(
        {
            ("GET", _arxiv_atom.ARXIV_API_URL): http_response(
                _arxiv_atom.ARXIV_API_URL,
                body=body,
                content_type="application/atom+xml",
            )
        }
    )
    client = ArxivClient(transport, {})
    metadata, warnings = client._fetch_api_metadata_optional("2605.06663v1")
    assert metadata["arxiv_id"] == "2605.06663v1" and metadata["title"] == "API title"
    assert warnings == []
    client.fetch_metadata({"arxiv_id": "2605.06663v1"})
    assert transport.calls[-1]["timeout"] == 60
    assert transport.calls[-1]["retry_on_transient"]
    assert transport.calls[-1]["transient_retries"] == 2
    with pytest.raises(ProviderFailure, match="identifier does not match"):
        client.fetch_metadata({"arxiv_id": "2605.06663v2"})


@pytest.mark.parametrize("successful", [True, False])
def test_fulltext_optional_metadata_preserves_content_and_records_fallback(
    monkeypatch, successful
):
    arxiv_id = "2605.06663v1"
    body = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
    <id>http://arxiv.org/abs/2605.06663v1</id><title>API title</title>
    <summary>API abstract</summary></entry></feed>"""
    response = (
        http_response(
            _arxiv_atom.ARXIV_API_URL, body=body, content_type="application/atom+xml"
        )
        if successful
        else RequestFailure(None, "Timed out", error_category="timeout")
    )
    client = ArxivClient(
        RecordingTransport({("GET", _arxiv_atom.ARXIV_API_URL): response}), {}
    )
    payload = build_provider_payload(
        provider="arxiv",
        route_kind="html",
        route_name="official_html",
        source_url=f"https://arxiv.org/html/{arxiv_id}",
        content_type="text/html",
        body=b"<article>Original HTML</article>",
        markdown_text="Original body and references",
        merged_metadata={
            "title": "HTML title",
            "arxiv_id": arxiv_id,
            "references": [{"text": "Reference"}],
        },
        extracted_assets=[{"url": "https://arxiv.org/html/figure.png"}],
    )
    monkeypatch.setattr(client, "_fetch_html_payload", lambda _metadata: payload)
    with RuntimeContext(env={}) as context:
        result = client.fetch_raw_fulltext(
            f"10.48550/arxiv.{arxiv_id}", {}, context=context
        )
    assert result.content.body == b"<article>Original HTML</article>"
    assert result.content.markdown_text == "Original body and references"
    assert result.content.extracted_assets == [
        {"url": "https://arxiv.org/html/figure.png"}
    ]
    assert result.content.merged_metadata["title"] == (
        "API title" if successful else "HTML title"
    )
    assert result.content.merged_metadata["references"] == [{"text": "Reference"}]
    assert result.content.merged_metadata["arxiv_id"] == arxiv_id
    diagnostic = result.content.diagnostics["arxiv_optional_metadata"]
    assert diagnostic["result"] == ("merged" if successful else "fallback")
    assert diagnostic["elapsed_seconds"] >= 0
    assert bool(diagnostic["fallback_reason"]) is (not successful)


def test_paywall_analysis_cache_is_fetch_local_and_identity_sensitive(monkeypatch):
    html = '<meta name="citation_doi" content="10.1000/test"><div class="paywall"><p>Purchase access to this article</p></div>'
    detector = mock.Mock(wraps=access_boundary._html_paywall_diagnostics)
    monkeypatch.setattr(access_boundary, "_html_paywall_diagnostics", detector)
    kwargs = dict(
        metadata={"doi": "10.1000/test"},
        source_url="https://example.test/10.1000/test",
        provider="aip",
    )
    with RuntimeContext(env={}) as context:
        first = access_boundary.html_paywall_diagnostics(
            html, context=context, **kwargs
        )
        with access_boundary.use_html_analysis_context(context):
            second = access_boundary.html_paywall_diagnostics(html.encode(), **kwargs)
        assert first == second and detector.call_count == 1
        first["received_metadata"]["title"] = "mutated"
        assert (
            "title"
            not in access_boundary.html_paywall_diagnostics(
                html, context=context, **kwargs
            )["received_metadata"]
        )
        for changed in [
            {**kwargs, "provider": "iop"},
            {**kwargs, "source_url": kwargs["source_url"] + "?different=1"},
            {**kwargs, "metadata": {"doi": "10.1000/other"}},
            {**kwargs, "metadata": {"doi": "10.1000/test", "abstract": "abstract"}},
        ]:
            access_boundary.html_paywall_diagnostics(html, context=context, **changed)
        access_boundary.html_paywall_diagnostics(html + " ", context=context, **kwargs)
        assert detector.call_count == 6
    with RuntimeContext(env={}) as context:
        access_boundary.html_paywall_diagnostics(html, context=context, **kwargs)
    assert detector.call_count == 7


@pytest.mark.parametrize(
    "html",
    [
        '<article><section property="articleBody"><h2>Results</h2><p>'
        + "Research results. " * 100
        + "</p><p>"
        + "Further evidence. " * 100
        + "</p></section></article>",
        "<article><h2>Abstract</h2><p>A short abstract.</p></article>",
        "<article><section hidden><h2>Results</h2><p>"
        + "Hidden text. " * 200
        + "</p></section></article>",
        '<article><div class="paywall"><p>Purchase access to this article</p></div></article>',
        "<article><h1>Empty shell</h1></article>",
    ],
)
def test_structure_dom_entry_matches_string_entry_and_preserves_input(html):
    soup = BeautifulSoup(html, html_availability.choose_parser())
    kwargs = dict(
        provider="aip",
        title="Paper",
        metadata={"doi": "10.1000/test"},
        final_url="https://example.test/10.1000/test",
    )
    original = str(soup)
    with mock.patch.object(
        html_availability, "BeautifulSoup", wraps=BeautifulSoup
    ) as parser:
        dom = html_availability.assess_html_fulltext_availability(
            "", kwargs.pop("metadata"), html_text=html, structure_dom=soup, **kwargs
        )
        assert parser.call_count == 1
    string = html_availability.assess_html_fulltext_availability(
        "", {"doi": "10.1000/test"}, html_text=html, structure_html_text=html, **kwargs
    )
    assert dom.to_dict() == string.to_dict()
    assert str(soup) == original


@pytest.mark.parametrize("provider", ["annualreviews", "wiley", "acs", "pnas", "tandf"])
def test_cleanup_scans_each_selector_once_and_keeps_independent_dom(
    monkeypatch, provider
):
    import copy
    from bs4 import Tag

    soup = BeautifulSoup(
        '<article><script>remove()</script><nav><a>Menu</a></nav><section><h2>Results</h2><p>Keep evidence.</p></section><div class="citation-links"><span>Crossref</span></div></article>',
        "html.parser",
    )
    original = str(soup)
    independent = copy.deepcopy(soup.article)
    queries = []
    select = Tag.select
    select_one = Tag.select_one

    def observed_select(node, selector, *args, **kwargs):
        queries.append(selector)
        return select(node, selector, *args, **kwargs)

    def no_descendant_scan(*args, **kwargs):
        raise AssertionError("local classification must not rescan descendants")

    monkeypatch.setattr(Tag, "select", observed_select)
    monkeypatch.setattr(Tag, "select_one", no_descendant_scan)
    result = html_availability.clean_container(independent, provider)
    assert queries == list(
        html_availability.availability_rules_for_provider(
            provider
        ).container_rules.remove_selectors
    )
    assert "Keep evidence." in result.get_text()
    assert "remove()" not in result.get_text()
    monkeypatch.setattr(Tag, "select_one", select_one)
    assert str(soup) == original


def test_runtime_environment_does_not_appear_in_default_repr(tmp_path):
    sentinel = "runtime-environment-sentinel-49275"
    with RuntimeContext(
        env={"CROSSREF_API_KEY": sentinel}, download_dir=tmp_path
    ) as context:
        assert context.env["CROSSREF_API_KEY"] == sentinel
        assert sentinel not in repr(context)
        assert "CROSSREF_API_KEY" not in repr(context)


def test_ieee_original_index_is_reused_invalidated_and_exact():
    from paper_fetch.providers._ieee_asset_recovery import _IeeePreviewWarmImageFetcher

    page = mock.Mock()
    first = "https://ieeexplore.ieee.org/first.gif"
    second = "https://ieeexplore.ieee.org/second.gif"
    entries = [{"url": url, "href": url, "figure": True} for url in (first, second)]
    page.locator.return_value.evaluate_all.return_value = entries
    fetcher = _IeeePreviewWarmImageFetcher(mock.Mock())
    assert fetcher._article_original_entry(page, 1, first)["url"] == first
    assert fetcher._article_original_entry(page, 1, second)["url"] == second
    assert page.locator.return_value.evaluate_all.call_count == 1
    assert fetcher._article_original_entry(page, 1, first + "?other") is None
    assert page.locator.return_value.evaluate_all.call_count == 2
    fetcher._article_original_entry(page, 2, first)
    assert page.locator.return_value.evaluate_all.call_count == 3
    page.on.call_args.args[1](page.main_frame)
    fetcher._article_original_entry(page, 2, first)
    assert page.locator.return_value.evaluate_all.call_count == 4
    fetcher.close()
    page.remove_listener.assert_called_once()


def test_tandf_batch_application_preserves_per_item_failures():
    from paper_fetch.providers import _tandf_html

    page = mock.Mock()
    page.evaluate.return_value = [True, False, True]
    result = {"tables_hydrated": 0, "csv_tables_hydrated": 0, "table_failures": 0}
    payloads = [{"tableId": f"t{i}", "rows": [["Column"], [str(i)]]} for i in range(3)]
    hydrated = _tandf_html._apply_tandf_table_batch(
        page, payloads, result, "csv_tables_hydrated"
    )
    assert hydrated == {"t0", "t2"}
    assert result == {
        "tables_hydrated": 2,
        "csv_tables_hydrated": 2,
        "table_failures": 1,
    }
    page.evaluate.assert_called_once_with(
        _tandf_html._TANDF_INJECT_TABLE_BATCH_SCRIPT, payloads
    )


def test_science_uses_one_normal_attempt_without_fast_timeout(monkeypatch):
    from paper_fetch.providers.science import ScienceClient
    from paper_fetch.providers.browser_workflow import html_extraction

    operation = mock.Mock(return_value=("html", "payload"))
    monkeypatch.setattr(html_extraction, "_fetch_browser_html_payload", operation)
    client = ScienceClient(None, {})
    with RuntimeContext(env={}) as context:
        result = html_extraction._fetch_browser_html_payload_with_fast_path(
            client,
            ["https://www.science.org/doi/full/example"],
            runtime=mock.Mock(),
            metadata={},
            context=context,
        )
    assert result == ("html", "payload")
    operation.assert_called_once()
    policy = operation.call_args.kwargs["policy"]
    assert policy.attempt == 1 and policy.max_timeout_ms is None


def test_annualreviews_assets_reuse_the_cleaned_body(monkeypatch):
    from paper_fetch.providers import _annualreviews_html as annual

    html = (
        '<html><head><meta name="citation_title" content="Example"></head><body><article id="itemFullTextId"><h2>Results</h2><p>'
        + "Observed result. " * 90
        + '</p><figure><img src="https://www.annualreviews.org/figure.png"><figcaption>Figure 1. Evidence</figcaption></figure></article></body></html>'
    )
    cleanup = mock.Mock(wraps=annual._cleaned_article_html_from_soup)
    monkeypatch.setattr(annual, "_cleaned_article_html_from_soup", cleanup)
    monkeypatch.setattr(
        annual.HtmlQualityAssessor,
        "assess",
        mock.Mock(return_value=mock.Mock(accepted=True, to_dict=lambda: {})),
    )
    _, extraction = annual.extract_markdown(
        html, "https://www.annualreviews.org/doi/example"
    )
    assert cleanup.call_count == 1
    assert extraction["extracted_assets"]
