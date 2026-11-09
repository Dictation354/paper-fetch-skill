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
    from dataclasses import replace
    from paper_fetch import provider_catalog

    bundles = dict(provider_catalog.PROVIDER_BUNDLE_MAP)
    bundles["pnas"] = replace(
        pnas.PROVIDER_BUNDLE,
        browser_page_policy=replace(
            pnas.PROVIDER_BUNDLE.browser_page_policy, empty_request=None
        ),
    )
    monkeypatch.setattr(provider_catalog, "PROVIDER_BUNDLE_MAP", bundles)
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


@pytest.mark.browser
@pytest.mark.parametrize(
    "scenario",
    [
        "role_paragraph",
        "delayed",
        "growing",
        "unstable",
        "layout",
        "challenge",
        "denied",
    ],
)
def test_pnas_readiness_samples_body_text_without_layout_resets(monkeypatch, scenario):
    from paper_fetch.providers.browser_workflow.fetchers.readiness import (
        wait_for_atypon_body_dom_ready,
    )

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
    body = (
        '<main id="bodymatter"><div role="paragraph">'
        + "Scientific evidence. " * 80
        + '</div><div role="paragraph">Second paragraph.</div><span id="layout">Layout text</span></main>'
    )
    with camoufox.Camoufox(
        headless=True, executable_path=executable, exclude_addons=list(DefaultAddons)
    ) as browser:
        page = browser.new_page()
        if scenario == "delayed":
            page.set_content(
                '<body><script>setTimeout(() => document.body.insertAdjacentHTML("beforeend", '
                + json.dumps(body)
                + "), 200)</script></body>"
            )
        elif scenario in {"challenge", "denied"}:
            page.set_content(
                "<title>Just a moment...</title><body>Checking your browser</body>"
                if scenario == "challenge"
                else "<title>Access denied</title><body>View all access options</body>"
            )
        else:
            page.set_content(body)
        samples = []

        class SamplingPage:
            def evaluate(self, script, args):
                if scenario in {"growing", "unstable"} and (
                    len(samples) < 3 or scenario == "unstable"
                ):
                    page.evaluate(
                        "() => document.querySelector('[role=paragraph]').append(' More results.')"
                    )
                if scenario == "layout":
                    page.evaluate(
                        "hidden => document.querySelector('#layout').style.display = hidden ? 'none' : 'inline'",
                        len(samples) % 2 == 0,
                    )
                result = page.evaluate(script, args)
                samples.append(result)
                return result

            def wait_for_timeout(self, milliseconds):
                page.wait_for_timeout(milliseconds)

        result = wait_for_atypon_body_dom_ready(
            SamplingPage(), "pnas", timeout_seconds=4 if scenario == "growing" else 1.7
        )
        assert result.ready == (scenario not in {"unstable", "challenge", "denied"})
        if result.ready:
            assert result.paragraph_count == 2
            assert result.heading_count == 0
            assert samples[-1]["fingerprint"] == samples[-2]["fingerprint"]
        if scenario in {"role_paragraph", "layout"}:
            assert len(samples) == 2
        if scenario == "delayed":
            assert not samples[0]["ready"]
        if scenario == "growing":
            assert len(samples) >= 4
        if scenario == "unstable":
            assert samples[-1]["fingerprint"] != samples[-2]["fingerprint"]
