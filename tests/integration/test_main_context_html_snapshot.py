"""Offline browser contracts for atomic HTML capture after body readiness."""

import json
import threading
from unittest import mock

import pytest

from paper_fetch.http import RequestCancelledError
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers import _playwright_browser as fetcher
from paper_fetch.providers.browser_runtime import (
    BrowserHtmlReadiness,
    BrowserRuntimeConfig,
)
from paper_fetch.runtime import RuntimeContext
from tests.support.offline_camoufox import prepared_browser


@pytest.fixture
def browser_page(monkeypatch):
    with prepared_browser(monkeypatch) as browser:
        context = browser.new_context()
        page = context.new_page()
        register_route = page.route

        def offline_route(pattern, handler):
            # PNAS installs a page-level metrics filter. Continue through the
            # offline context routes instead of sending its requests online.
            class OfflineRoute:
                def __init__(self, route):
                    self.route = route

                def __getattr__(self, name):
                    return getattr(self.route, name)

                def continue_(self):
                    self.route.fallback()

            register_route(pattern, lambda route: handler(OfflineRoute(route)))

        monkeypatch.setattr(page, "route", offline_route)
        yield context, page
        context.close()


def _article(provider):
    body = (
        "<h2>Results</h2><p>" + "Research evidence. " * 600 + "</p><p>Discussion.</p>"
    )
    body += "<math><mi>x</mi><mo>=</mo><mn>2</mn></math>"
    body += '<p>Study <a role="doc-biblioref" href="#R2">2</a>.</p>'
    if provider == "wiley":
        body = (
            '<section class="article-section__content en main">' + body + "</section>"
        )
    else:
        body = (
            '<section id="bodymatter" data-extent="bodymatter" property="articleBody">'
            + body
            + "</section>"
        )
    return body


@pytest.mark.browser
@pytest.mark.parametrize(
    "provider,host",
    [
        ("pnas", "www.pnas.org"),
        ("science", "www.science.org"),
        ("wiley", "onlinelibrary.wiley.com"),
    ],
)
def test_ready_html_snapshot_keeps_delayed_body_math_and_prepared_references(
    browser_page,
    monkeypatch,
    tmp_path,
    provider,
    host,
):
    context, page = browser_page
    url = f"https://{host}/doi/full/10.1000/test"
    html = "<!DOCTYPE html><title>Loaded article</title><article></article><script>"
    html += (
        'setTimeout(() => document.querySelector("article").innerHTML = '
        + json.dumps(_article(provider))
        + ", 100);"
    )
    html += '</script><section id="bibliography"><div class="biblioentry"><div class="citations" id="R1"><div class="citation-content">First study.</div></div></div>'
    html += "<button onclick=\"this.remove(); setTimeout(() => document.querySelector('#bibliography').insertAdjacentHTML('beforeend', '<div class=biblioentry><div class=citations id=R2><div class=citation-content>Prepared second study.</div></div></div>'), 100)\">View all references</button></section>"
    context.route(
        "**/*", lambda route: route.fulfill(body=html, content_type="text/html")
    )
    monkeypatch.setattr(
        fetcher, "open_browser_context", lambda *_a, **_k: (None, context)
    )
    # Use the actual routed page, while allowing the fetcher to own its lifecycle.
    monkeypatch.setattr(context, "new_page", lambda: page)
    owner_thread = threading.get_ident()
    snapshots = []
    capture = fetcher._main_context_html_snapshot

    def record_snapshot(*args, **kwargs):
        assert threading.get_ident() == owner_thread
        result = capture(*args, **kwargs)
        snapshots.append(result)
        return result

    monkeypatch.setattr(fetcher, "_main_context_html_snapshot", record_snapshot)
    with mock.patch.object(
        page, "content", side_effect=AssertionError("utility capture used")
    ):
        result = fetcher.fetch_html_with_playwright(
            [url],
            publisher=provider,
            config=BrowserRuntimeConfig(
                provider=provider,
                doi="10.1000/test",
                artifact_dir=tmp_path,
                headless=True,
                user_agent=None,
                persist_storage_state=False,
            ),
            readiness=BrowserHtmlReadiness(wait_for_article_body=True),
        )
    assert len(snapshots) == 2 and all(snapshots)
    assert result.html.startswith("<!DOCTYPE html>")
    assert "<math>" in result.html and "Research evidence." in result.html
    assert result.final_url == url and result.title == "Loaded article"
    trace = result.diagnostics["browser_runtime_trace"]["candidates"][0]
    assert trace["dom_readiness_ready"] and trace["dom_readiness_seconds"] >= 0.75
    if provider == "science":
        assert 'id="R2"' not in snapshots[0][0]
        assert 'id="R2"' in result.html and "Prepared second study." in result.html
        assert not trace["provider_page_preparation"]["missing_reference_targets"]


@pytest.mark.browser
def test_snapshot_navigation_race_falls_back_to_current_native_document(
    browser_page,
    monkeypatch,
    tmp_path,
):
    context, page = browser_page
    context.route(
        "**/*",
        lambda route: route.fulfill(
            body="<!DOCTYPE html><title>"
            + route.request.url.rsplit("/", 1)[-1]
            + "</title><article>"
            + _article("pnas")
            + "</article>",
            content_type="text/html",
        ),
    )
    monkeypatch.setattr(
        fetcher, "open_browser_context", lambda *_a, **_k: (None, context)
    )
    monkeypatch.setattr(context, "new_page", lambda: page)
    evaluate = page.evaluate
    captures = []

    def navigating_evaluate(script, *args):
        result = evaluate(script, *args)
        if script == fetcher._MAIN_CONTEXT_HTML_SNAPSHOT_SCRIPT:
            captures.append(result)
            if len(captures) == 2:
                page.goto("https://www.pnas.org/second")
        return result

    monkeypatch.setattr(page, "evaluate", navigating_evaluate)
    with mock.patch.object(page, "content", wraps=page.content) as native:
        result = fetcher.fetch_html_with_playwright(
            ["https://www.pnas.org/first"],
            publisher="pnas",
            config=BrowserRuntimeConfig(
                provider="pnas",
                doi="10.1000/test",
                artifact_dir=tmp_path,
                headless=True,
                user_agent=None,
                persist_storage_state=False,
            ),
            readiness=BrowserHtmlReadiness(wait_for_article_body=True),
        )
    assert len(captures) == 2
    assert native.call_count == 1
    assert result.final_url.endswith("/second") and result.title == "second"
    assert "<title>second</title>" in result.html


@pytest.mark.browser
@pytest.mark.parametrize("boundary", ["paywall", "challenge"])
def test_ready_snapshot_preserves_access_boundaries(
    browser_page,
    monkeypatch,
    tmp_path,
    boundary,
):
    context, page = browser_page
    doi = "10.1073/pnas.2406303121"
    url = f"https://www.pnas.org/doi/full/{doi}"
    html = '<!DOCTYPE html><meta name="citation_doi" content="' + doi + '">'
    html += (
        "<title>Just a moment...</title>"
        if boundary == "challenge"
        else "<title>Article</title>"
    )
    html += _article("pnas")
    html += (
        '<div class="paywall" aria-modal="true"><p>Purchase access to this article</p></div>'
        if boundary == "paywall"
        else "<p>Checking your browser before accessing the site.</p>"
    )
    context.route(
        "**/*", lambda route: route.fulfill(body=html, content_type="text/html")
    )
    monkeypatch.setattr(
        fetcher, "open_browser_context", lambda *_a, **_k: (None, context)
    )
    monkeypatch.setattr(context, "new_page", lambda: page)
    with (
        mock.patch.object(
            fetcher,
            "_prepare_provider_browser_page",
            wraps=fetcher._prepare_provider_browser_page,
        ) as prepare,
        mock.patch.object(
            fetcher,
            "_main_context_html_snapshot",
            wraps=fetcher._main_context_html_snapshot,
        ) as capture,
        pytest.raises((ProviderFailure, fetcher.PlaywrightBrowserFailure)) as caught,
    ):
        fetcher.fetch_html_with_playwright(
            [url],
            publisher="pnas",
            config=BrowserRuntimeConfig(
                provider="pnas",
                doi=doi,
                artifact_dir=tmp_path,
                headless=True,
                user_agent=None,
                persist_storage_state=False,
            ),
            readiness=BrowserHtmlReadiness(wait_for_article_body=True),
        )
    if boundary == "paywall":
        assert caught.value.code == "no_access"
        prepare.assert_not_called()
        assert capture.call_count == 1
    else:
        assert caught.value.kind == "cloudflare_challenge"
        assert capture.call_count == 2


@pytest.mark.browser
def test_snapshot_cancellation_after_evaluate_propagates(browser_page):
    _, page = browser_page
    page.set_content("<article>Body</article>")
    with RuntimeContext(env={}) as runtime:

        class CancellingPage:
            url = page.url

            def evaluate(self, script):
                result = page.evaluate(script)
                runtime.fence_commits()
                return result

        with pytest.raises(RequestCancelledError):
            fetcher._main_context_html_snapshot(
                CancellingPage(), runtime_context=runtime
            )
