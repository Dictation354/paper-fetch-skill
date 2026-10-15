import json
from unittest import mock

import pytest

from paper_fetch.providers.browser_workflow.fetchers.readiness import (
    _BODY_READY_SCRIPT,
    wait_for_atypon_body_dom_ready,
)
from tests.support.offline_camoufox import prepared_browser
from paper_fetch.providers import _playwright_browser
from paper_fetch.providers.browser_runtime import (
    BrowserRuntimeConfig,
    BrowserHtmlReadiness,
)
from paper_fetch.runtime import RuntimeContext


def _validation_route(text, status):
    def fulfill(route):
        route.fulfill(
            body=f'<meta charset="utf-8"><title>{text}</title><body>{text}</body>',
            status=status,
            content_type="text/html",
        )

    return fulfill


@pytest.mark.browser
@pytest.mark.parametrize("headless", [True, False])
def test_aip_terminal_validation_requires_url_and_page_evidence(monkeypatch, headless):
    with prepared_browser(monkeypatch, headless=headless) as browser:
        context = browser.new_context()
        page = context.new_page()
        try:
            # URL alone, ordinary 403s, temporary challenge text, and other
            # providers/hosts must continue polling.
            for url, text, status, provider, blocked in [
                (
                    "https://pubs.aip.org/crawlprevention/governor",
                    "Validate User",
                    200,
                    "aip",
                    True,
                ),
                (
                    "https://pubs.aip.org/crawlprevention/governor?next=article",
                    "确认不是机器人",
                    403,
                    "aip",
                    True,
                ),
                (
                    "https://pubs.aip.org/crawlprevention/governor",
                    "Just a moment...",
                    403,
                    "aip",
                    False,
                ),
                (
                    "https://pubs.aip.org/crawlprevention/governor",
                    "Loading",
                    200,
                    "aip",
                    False,
                ),
                (
                    "https://pubs.aip.org/article/test",
                    "Validate User",
                    403,
                    "aip",
                    False,
                ),
                (
                    "https://other.test/crawlprevention/governor",
                    "Validate User",
                    403,
                    "aip",
                    False,
                ),
                (
                    "https://pubs.aip.org/crawlprevention/governor",
                    "Validate User",
                    403,
                    "iop",
                    False,
                ),
            ]:
                page.unroute("**/*")

                page.route("**/*", _validation_route(text, status))
                page.goto(url)
                assert page.url == url
                payload = page.evaluate(
                    _BODY_READY_SCRIPT,
                    {"provider": provider, "selectors": [], "minChars": 1200},
                )
                assert bool(payload.get("blockingReason")) is blocked, (
                    url,
                    text,
                    page.title(),
                    payload,
                )
                with mock.patch.object(
                    page, "wait_for_timeout", wraps=page.wait_for_timeout
                ) as waits:
                    result = wait_for_atypon_body_dom_ready(
                        page, provider, timeout_seconds=0.25
                    )
                assert bool(result.blocking_reason) is blocked
                if blocked:
                    waits.assert_not_called()
                else:
                    assert result.elapsed_ms >= 250
            page.unroute("**/*")
            page.route(
                "**/*",
                lambda route: route.fulfill(
                    body='<title>Just a moment...</title><script>setTimeout(() => {document.title="Article"; document.body.innerHTML="<div class=article-body><h2>Results</h2><p>" + "Evidence. ".repeat(250) + "</p><p>Conclusion.</p></div>"}, 50)</script>',
                    content_type="text/html",
                ),
            )
            page.goto("https://pubs.aip.org/article/test")
            assert wait_for_atypon_body_dom_ready(page, "aip", timeout_seconds=3).ready
        finally:
            context.close()


@pytest.mark.browser
def test_aip_terminal_challenge_saves_diagnostic_and_advances_candidate(
    monkeypatch, tmp_path
):
    with prepared_browser(monkeypatch) as browser:
        context = browser.new_context()

        def route_page(route):
            html = (
                "<title>Validate User</title><body>Confirm you are not a robot.</body>"
                if "/governor" in route.request.url
                else '<title>Article</title><div class="article-body"><h2>Results</h2><p>'
                + "Research evidence. " * 250
                + "</p><p>Conclusion.</p></div>"
            )
            route.fulfill(body=html, content_type="text/html")

        context.route("**/*", route_page)
        monkeypatch.setattr(
            _playwright_browser,
            "open_browser_context",
            lambda *_a, **_k: (None, context),
        )
        config = BrowserRuntimeConfig(
            provider="aip",
            doi="10.1063/test",
            artifact_dir=tmp_path,
            headless=True,
            user_agent=None,
            persist_storage_state=False,
        )
        with RuntimeContext(
            env={}, download_dir=tmp_path, artifact_mode="all"
        ) as runtime:
            result = _playwright_browser.fetch_html_with_playwright(
                [
                    "https://pubs.aip.org/crawlprevention/governor",
                    "https://pubs.aip.org/article/test",
                ],
                publisher="aip",
                config=config,
                runtime_context=runtime,
                readiness=BrowserHtmlReadiness(wait_for_article_body=True),
            )
        candidates = result.diagnostics["browser_runtime_trace"]["candidates"]
        assert len(candidates) == 2
        assert candidates[0]["dom_readiness_result"] == "blocked"
        assert candidates[0]["block_reason"] == "cloudflare_challenge"
        assert candidates[1]["dom_readiness_result"] == "ready"
        diagnostic_paths = list(tmp_path.rglob("diagnostic.json"))
        assert diagnostic_paths
        assert any(
            json.loads(path.read_text())["failure_code"] == "cloudflare_challenge"
            for path in diagnostic_paths
        )
