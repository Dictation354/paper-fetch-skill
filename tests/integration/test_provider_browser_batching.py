"""Browser contracts for document-local IEEE indexing and T&F table batches."""

from unittest.mock import Mock

import pytest

from paper_fetch.providers import _tandf_html
from paper_fetch.providers._ieee_asset_recovery import _IeeePreviewWarmImageFetcher
from tests.support.offline_camoufox import prepared_browser


@pytest.mark.browser
def test_ieee_index_follows_navigation_and_exact_original_urls(monkeypatch):
    with prepared_browser(monkeypatch) as browser:
        page = browser.new_page()
        html = '<div id="article"><a href="/first.gif"><img></a><a href="/second.gif" data-fig-id="f2"><img></a><a href="/not-original.gif">Related</a></div>'
        page.route(
            "**/*", lambda route: route.fulfill(body=html, content_type="text/html")
        )
        page.goto("https://ieeexplore.ieee.org/document/example")
        fetcher = _IeeePreviewWarmImageFetcher(Mock())
        first = "https://ieeexplore.ieee.org/first.gif"
        assert fetcher._article_original_entry(page, 0, first)["figure"] is False
        assert fetcher._article_original_entry(page, 0, first + "?other") is None
        assert (
            fetcher._article_original_entry(
                page, 0, "https://ieeexplore.ieee.org/not-original.gif"
            )
            is None
        )
        assert (
            fetcher._article_original_entry(
                page, 0, "https://ieeexplore.ieee.org/second.gif"
            )["figure"]
            is True
        )
        html = (
            '<div id="article"><a href="/first.gif" data-fig-id="new"><img></a></div>'
        )
        page.reload()
        assert fetcher._article_original_entry(page, 0, first)["figure"] is True
        fetcher.close()


@pytest.mark.browser
def test_tandf_batches_controls_and_injection_with_partial_csv_failure(monkeypatch):
    with prepared_browser(monkeypatch) as browser:
        page = browser.new_page()
        html = (
            "<article>"
            + "".join(
                f'<div id="t{i}" class="tableView"><div class="tableDownloadOption" id="t{i}-table-wrapper"><a href="/action/downloadTable?id=t{i}&downloadType=CSV">CSV</a></div></div>'
                for i in range(3)
            )
            + "</article>"
        )

        def route(request):
            url = request.request.url
            if "/action/downloadTable" in url:
                failed = "id=t1&" in url
                request.fulfill(
                    status=403 if failed else 200,
                    body="A,B\n1,2",
                    content_type="text/csv",
                )
            else:
                request.fulfill(body=html, content_type="text/html")

        page.route("**/*", route)
        page.goto("https://www.tandfonline.com/doi/full/example")
        result = _tandf_html.prepare_browser_page(page, timeout_ms=5000)
        assert result["table_controls"] == 3
        assert result["csv_tables_hydrated"] == 2
        assert result["table_failures"] == 1
        assert page.locator("#t0 table").count() == 1
        assert page.locator("#t1 table").count() == 0
        assert page.locator("#t2 table").count() == 1
