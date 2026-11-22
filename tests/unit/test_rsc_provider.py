from __future__ import annotations

from unittest.mock import Mock

import pytest

from paper_fetch.auth import browser_auth_provider_names
from paper_fetch.errors import ProviderFailure
from paper_fetch.http import HttpTransport, RequestFailure
from paper_fetch.provider_catalog import provider_for_source, provider_routes
from paper_fetch.providers import rsc
from paper_fetch.providers._pdf_common import PdfFetchFailure
from paper_fetch.providers.browser_runtime import (
    BrowserFetchedHtml,
    BrowserRuntimeConfig,
)
from paper_fetch.providers.crossref import CrossrefClient
from paper_fetch.publisher_identity import infer_provider_from_publisher
from paper_fetch.quality.access_boundary import CONFIRMED_PAYWALL, raise_for_paywall
from paper_fetch.resolve import query as resolver
from paper_fetch.runtime import RuntimeContext
from paper_fetch.service import fetch_paper
from paper_fetch.workflow.types import FetchStrategy
from tests.support._browser_workflow_deps import install_browser_workflow_deps

DOI = "10.1039/d5gc03562g"
TITLE = "A study of heterogeneous photocatalytic reactions"
LEGACY = "https://pubs.rsc.org/en/content/articlelanding/2025/gc/D5GC03562G"
ARTICLE = "https://pubs.rsc.org/gc/article/28/1/309/894100/article-title"
CITATION_PDF = "https://pubs.rsc.org/gc/article-pdf/28/1/309/10402405/d5gc03562g.pdf"
CROSSREF_PDF = "http://pubs.rsc.org/en/content/articlepdf/2026/GC/D5GC03562G"
DERIVED_PDF = "https://pubs.rsc.org/en/content/articlepdf/2025/gc/D5GC03562G"
SUPPLEMENT = "https://pubs.rsc.org/gc/article-supplement/894100/pdf/d5gc03562g1_suppl/"
ABSTRACT = "The authors describe the goals of the study."
PAGE = f"""
<meta name="citation_doi" content="{DOI}">
<meta name="citation_title" content="{TITLE}">
<meta name="citation_pdf_url" content="{SUPPLEMENT}">
<meta name="citation_pdf_url" content="{CITATION_PDF}">
<div class="article-body"><div class="widget-ArticleFulltext">
<div class="article-section-wrapper"><section class="abstract"><p>{ABSTRACT}</p></section></div>
</div></div><a href="{SUPPLEMENT}">Supplementary information (PDF)</a>
"""
PAYWALL = (
    PAGE
    + '<div class="widget-ArticlePaywall">You do not have access to this article.</div>'
)


def _browser_page(html: str, url: str = ARTICLE) -> BrowserFetchedHtml:
    return BrowserFetchedHtml(
        source_url=url,
        final_url=url,
        html=html,
        response_status=200,
        response_headers={},
        title=TITLE,
        summary="",
        browser_context_seed={"browser_final_url": url},
    )


@pytest.mark.parametrize("query, kind", [(DOI.upper(), "doi"), (LEGACY, "url")])
def test_doi_and_legacy_url_route_without_a_request(query, kind) -> None:
    transport = Mock(spec=HttpTransport)
    resolved = resolver.resolve_query(query, transport=transport, env={})
    assert (resolved.doi, resolved.provider_hint, resolved.query_kind) == (
        DOI,
        "rsc",
        kind,
    )
    assert not transport.mock_calls
    assert infer_provider_from_publisher("Royal Society of Chemistry (RSC)") == "rsc"
    assert [route.name for route in provider_routes("rsc")] == [
        "metadata",
        "browser_html",
        "browser_pdf",
        "assets",
    ]
    assert provider_for_source("rsc_html") == provider_for_source("rsc_pdf") == "rsc"
    assert "rsc" in browser_auth_provider_names()


@pytest.mark.parametrize("http_has_doi", [True, False])
def test_silverchair_url_uses_browser_only_when_http_lacks_doi(
    monkeypatch, http_has_doi
) -> None:
    html = PAGE if http_has_doi else "<title>Single Sign-On</title>"
    transport = Mock(spec=HttpTransport)
    transport.request.return_value = {
        "url": ARTICLE,
        "status_code": 200,
        "headers": {"content-type": "text/html"},
        "body": html.encode(),
    }
    browser = Mock(return_value=_browser_page(PAGE))
    monkeypatch.setattr(rsc, "ensure_runtime_ready", Mock())
    monkeypatch.setattr(rsc, "fetch_html_with_browser", browser)
    resolved = resolver.resolve_query(ARTICLE, transport=transport, env={})
    assert (resolved.doi, resolved.landing_url, resolved.provider_hint) == (
        DOI,
        ARTICLE,
        "rsc",
    )
    assert browser.call_count == (0 if http_has_doi else 1)
    if not http_has_doi:
        assert browser.call_args.args == ([ARTICLE],)


def test_silverchair_resolver_rejects_offsite_citation_doi(monkeypatch) -> None:
    transport = Mock(spec=HttpTransport)
    transport.request.side_effect = RequestFailure(403, "Forbidden", url=ARTICLE)
    browser = Mock(
        return_value=_browser_page(PAGE, "https://sso.example.org/gc/article/894100")
    )
    monkeypatch.setattr(rsc, "ensure_runtime_ready", Mock())
    monkeypatch.setattr(rsc, "fetch_html_with_browser", browser)
    with pytest.raises(ProviderFailure, match="Failed to fetch landing page"):
        resolver.resolve_query(ARTICLE, transport=transport, env={})
    browser.assert_called_once()


def test_rsc_pdf_candidates_and_metadata_fallback(tmp_path) -> None:
    transport = Mock(spec=HttpTransport)
    client = rsc.RscClient(transport, {})
    html = Mock(return_value=_browser_page(PAGE))
    pdf = Mock(side_effect=PdfFetchFailure("downloaded_file_not_pdf", "PDF failed"))
    warm = Mock()
    install_browser_workflow_deps(
        client,
        load_runtime_config=Mock(
            return_value=BrowserRuntimeConfig(
                "rsc",
                DOI,
                tmp_path,
                True,
                None,
            )
        ),
        fetch_html_with_browser=html,
        ensure_runtime_ready=Mock(),
        fetch_pdf_with_browser=pdf,
        warm_browser_context=warm,
    )
    crossref = CrossrefClient(transport, {})
    crossref.fetch_metadata = Mock(
        return_value={
            "doi": DOI,
            "title": TITLE,
            "publisher": "Royal Society of Chemistry (RSC)",
            "landing_page_url": ARTICLE,
            "fulltext_links": [{"url": SUPPLEMENT}, {"url": CROSSREF_PDF}],
        }
    )
    with RuntimeContext(
        env={},
        transport=transport,
        clients={"rsc": client, "crossref": crossref},
        artifact_mode="none",
        download_dir=tmp_path,
    ) as context:
        result = fetch_paper(LEGACY, modes={"article"}, context=context)
    assert result.article.source == "crossref_meta"
    assert result.article.quality.content_kind == "metadata_only"
    assert html.call_args.args[0] == [
        LEGACY.replace("articlelanding", "articlehtml"),
        ARTICLE,
        f"https://doi.org/{DOI}",
    ]
    assert pdf.call_args.args[0] == [CITATION_PDF, CROSSREF_PDF, DERIVED_PDF]
    assert pdf.call_args.kwargs["request"].browser_only
    assert pdf.call_args.kwargs["seed_urls"] is None
    assert pdf.call_args.kwargs["request"].expected_identity == {
        "doi": DOI,
        "title": TITLE,
    }
    warm.assert_not_called()
    assert (
        client.pdf_candidates_from_html(
            PAGE.replace(DOI, "10.1039/d5gc00000a"),
            ARTICLE,
            doi=DOI,
        )
        == []
    )


def test_confirmed_rsc_paywall_short_circuits_pdf_and_keeps_article_metadata(
    tmp_path,
) -> None:
    client = rsc.RscClient(Mock(spec=HttpTransport), {})
    html = Mock(return_value=_browser_page(PAYWALL))
    pdf = Mock()
    install_browser_workflow_deps(
        client,
        load_runtime_config=Mock(
            return_value=BrowserRuntimeConfig(
                "rsc",
                DOI,
                tmp_path,
                True,
                None,
            )
        ),
        fetch_html_with_browser=html,
        ensure_runtime_ready=Mock(),
        fetch_pdf_with_browser=pdf,
    )
    result = client.fetch_result(DOI, {"doi": DOI, "landing_page_url": ARTICLE}, None)
    assert result.article.source == "rsc_html"
    assert result.article.quality.content_kind == "abstract_only"
    assert result.article.metadata.abstract == ABSTRACT
    assert result.article.metadata.title == TITLE
    assert any(event.code == CONFIRMED_PAYWALL for event in result.article.trace)
    html.assert_called_once()
    pdf.assert_not_called()


def test_new_url_paywall_stops_retrieval_during_resolution(
    tmp_path, monkeypatch
) -> None:
    transport = Mock(spec=HttpTransport)
    transport.request.return_value = {
        "url": ARTICLE,
        "status_code": 200,
        "headers": {"content-type": "text/html"},
        "body": b"<title>Single Sign-On</title>",
    }
    client = rsc.RscClient(transport, {})
    fulltext_html = Mock()
    crossref = Mock()
    install_browser_workflow_deps(client, fetch_html_with_browser=fulltext_html)
    with pytest.raises(ProviderFailure) as failure:
        raise_for_paywall(PAYWALL, source_url=ARTICLE, provider="rsc")
    browser = Mock(side_effect=failure.value)
    monkeypatch.setattr(rsc, "ensure_runtime_ready", Mock())
    monkeypatch.setattr(rsc, "fetch_html_with_browser", browser)
    with RuntimeContext(
        env={},
        transport=transport,
        clients={"rsc": client, "crossref": crossref},
        artifact_mode="none",
        download_dir=tmp_path,
    ) as context:
        result = fetch_paper(
            ARTICLE, modes={"article"}, strategy=FetchStrategy(), context=context
        )
    assert result.article.doi == DOI
    assert result.article.quality.content_kind == "abstract_only"
    assert result.article.metadata.abstract == ABSTRACT
    assert any(event.code == CONFIRMED_PAYWALL for event in result.article.trace)
    browser.assert_called_once()
    crossref.fetch_metadata.assert_not_called()
    fulltext_html.assert_not_called()
