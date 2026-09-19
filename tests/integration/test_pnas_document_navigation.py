"""PNAS document replacement and candidate readiness in a real offline browser."""

import json
import os
from pathlib import Path

import pytest

from paper_fetch.providers import _playwright_browser, pnas
from paper_fetch.providers.browser_runtime import (
    BrowserHtmlFetchOptions,
    BrowserHtmlReadiness,
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
)
from tests._environment import PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR


@pytest.mark.browser
@pytest.mark.parametrize("scenario", ["replacement", "next_candidate", "denied"])
def test_pnas_uses_completed_document_and_waits_for_each_candidate(
    monkeypatch, tmp_path, scenario
):
    executable = os.environ.get(PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR)
    if not executable or not Path(executable).is_file():
        pytest.skip("requires the existing local Camoufox executable")
    camoufox = pytest.importorskip("camoufox.sync_api")
    from camoufox import DefaultAddons, utils

    version_file = next(
        parent / "version.json"
        for parent in Path(executable).parents
        if (parent / "version.json").is_file()
    )
    monkeypatch.setattr(
        utils,
        "installed_verstr",
        lambda: json.loads(version_file.read_text())["version"],
    )
    monkeypatch.setattr(utils, "get_path", lambda file: str(version_file.parent / file))
    # Keep all network interception in this offline context. Sidebar blocking has
    # its own contract; a page route's continue_ would bypass context fixtures.
    monkeypatch.setattr(pnas, "_is_sidebar_metrics_url", None)
    doi = "10.1073/example"
    url = f"https://www.pnas.org/doi/full/{doi}"
    alternate = f"https://www.pnas.org/doi/{doi}"
    body = (
        '<main id="bodymatter"><h2>Results</h2>'
        + "<p>"
        + ("Observed scientific results and supporting evidence. " * 100)
        + "</p></main>"
    )
    calls = []

    def serve(route):
        target = route.request.url
        calls.append(target)
        status = 403
        html = "<html><title>Access denied</title><body>Access denied</body></html>"
        if scenario == "replacement" and calls.count(url) == 1:
            html = "<html><body>Loading<script>setTimeout(() => location.reload(), 100)</script></body></html>"
        elif scenario == "replacement" or (
            scenario == "next_candidate" and target == alternate
        ):
            status = 200
            html = (
                '<html><title>Article</title><body><script>setTimeout(() => document.body.insertAdjacentHTML("beforeend", '
                + json.dumps(body)
                + "), 100)</script></body></html>"
            )
        route.fulfill(status=status, content_type="text/html", body=html)

    with camoufox.Camoufox(
        headless=True, executable_path=executable, exclude_addons=list(DefaultAddons)
    ) as browser:
        context = browser.new_context()
        context.route("**/*", serve)
        monkeypatch.setattr(
            _playwright_browser,
            "open_browser_context",
            lambda *args, **kwargs: (None, context),
        )
        kwargs = dict(
            publisher="pnas",
            config=BrowserRuntimeConfig(
                provider="pnas",
                doi=doi,
                artifact_dir=tmp_path,
                headless=True,
                user_agent=None,
                persist_storage_state=False,
            ),
            max_timeout_ms=15000,
            wait_seconds=0,
            readiness=BrowserHtmlReadiness(wait_for_article_body=True),
            options=BrowserHtmlFetchOptions(readiness_budget_seconds=2.0),
        )
        if scenario == "denied":
            with pytest.raises(BrowserRuntimeFailure):
                _playwright_browser.fetch_html_with_playwright([url], **kwargs)
            return
        result = _playwright_browser.fetch_html_with_playwright(
            [url, alternate] if scenario == "next_candidate" else [url], **kwargs
        )
        assert result.response_status == 200
        assert body in result.html
        trace = result.diagnostics["browser_runtime_trace"]
        assert trace["candidates"][-1]["dom_readiness_ready"] is True
        documents = trace["page_events"]["document_requests"]
        assert [item["status"] for item in documents] == [403, 200]
        assert documents[-1]["request_finished_observed"] is True
        if scenario == "next_candidate":
            assert trace["candidates"][0]["dom_readiness_result"] == "timeout"
            assert trace["navigation_count"] == 2
