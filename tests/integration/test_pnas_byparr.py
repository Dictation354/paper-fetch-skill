"""Real shared Camoufox/Byparr lifecycle and local HTTP/browser contracts."""

from dataclasses import replace
import base64
import contextlib
import os
from pathlib import Path
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from paper_fetch import offline_byparr
from paper_fetch.providers.browser_runtime import byparr_manager as managed
from paper_fetch.providers.browser_runtime import byparr_preparation as prep
from paper_fetch.providers.browser_runtime.api import fetch_html_with_browser
from paper_fetch.providers.browser_runtime.navigation import navigate_page
from paper_fetch.providers.browser_runtime.platforms import (
    supported_platform,
)
from paper_fetch.providers.browser_runtime.paths import (
    stage_storage_state,
    commit_staged_storage_state,
)
from paper_fetch.providers.browser_runtime.types import (
    BrowserHtmlFetchOptions,
    BrowserHtmlReadiness,
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
)
from paper_fetch.runtime import RuntimeContext

from paper_fetch.providers.browser_runtime.byparr_engine import engine_name

pytestmark = pytest.mark.browser


def _owned_processes(owner):
    session = getattr(owner, "_invisible_session", None)
    if session is not None:
        from invisible_core.process import find_processes

        return find_processes(session._session_token)
    return [owner.process] if owner.process is not None else []


def _exited(process):
    if hasattr(process, "poll"):
        return process.poll() is not None
    return not process.is_running() or process.status() == "zombie"


@pytest.fixture(
    params=["auto", "camoufox"] if engine_name() == "invisible" else ["auto"]
)
def prepared(monkeypatch, request):
    if request.param == "camoufox":
        monkeypatch.setattr(
            "paper_fetch.providers.browser_runtime.byparr_engine.engine_name",
            lambda: "camoufox",
        )
    cache = os.environ.get("PAPER_FETCH_TEST_BYPARR_CACHE")
    if not cache or not supported_platform():
        pytest.skip("requires preprepared Byparr component and Camoufox")
    cache = Path(cache)
    root, _, identity = prep.runtime_location(cache)
    if (cache / "ready.json").is_file():
        root = cache
    if not prep.valid_cache(root, identity):
        pytest.skip("locked Byparr cache is unavailable for this Python")
    monkeypatch.setattr(prep, "prepare_source", lambda cache, budget: root)
    from paper_fetch.providers.browser_runtime.byparr_engine import engine_name

    if engine_name() == "invisible":
        monkeypatch.setenv("BROWSER_TIMEZONE", "UTC")
        monkeypatch.setenv("BROWSER_LOCALE", "en-US")
        from invisible_core.download import cache_dir_for_seal

        if not cache_dir_for_seal().exists():
            pytest.skip("requires preprepared sealed Invisible engine")
        monkeypatch.delenv("PAPER_FETCH_BROWSER_BINARY_PATH", raising=False)
    else:
        from tests._environment import (
            PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR,
            PRESERVED_CAMOUFOX_CACHE_HOME_ENV_VAR,
        )

        executable = os.environ.get(PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR)
        cache_home = os.environ.get(PRESERVED_CAMOUFOX_CACHE_HOME_ENV_VAR)
        if not executable or not cache_home:
            pytest.skip("requires prepared Camoufox executable and dependency cache")
        monkeypatch.setenv("XDG_CACHE_HOME", cache_home)
        monkeypatch.setenv("PAPER_FETCH_BROWSER_BINARY_PATH", executable)
        monkeypatch.setattr(
            "paper_fetch.providers.browser_runtime.camoufox_manager._launch_executable_path",
            lambda _: None if os.sys.platform == "darwin" else executable,
        )
    yield
    assert prep.valid_cache(root, identity), (
        "Byparr must not mutate its shared component"
    )


@pytest.mark.parametrize("cancel", [False, True])
def test_installer_local_check_never_restores_or_navigates_and_cleans_processes(
    prepared,
    monkeypatch,
    tmp_path,
    cancel,
):
    owners = []
    processes = []
    directories = []

    class Owner(managed.ByparrManager):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            owners.append(self)

        def _restore_state(self):
            pytest.fail("Installer must not restore publisher state")

        def refresh(self):
            pytest.fail("Installer must not inspect publisher state")

        def navigate(self, *args, **kwargs):
            pytest.fail("Installer must not visit publisher homepage")

        def new_context(self, **kwargs):
            context = super().new_context(**kwargs)
            processes.extend(_owned_processes(self))
            directories.append(self.work_dir)
            assert not context.cookies()
            assert all(
                page.url in {"about:blank", "chrome://newtab/"}
                for page in context.pages
            )
            if cancel:
                raise KeyboardInterrupt()
            return context

    monkeypatch.setattr(offline_byparr, "ByparrManager", Owner)
    runtime = prep.prepare_source(tmp_path, prep.PreparationBudget(10))
    if cancel:
        with pytest.raises(KeyboardInterrupt):
            offline_byparr.local_check({}, runtime)
    else:
        offline_byparr.local_check({}, runtime)
    assert processes and all(_exited(process) for process in processes)
    assert all(not directory.exists() for directory in directories)
    assert all(owner.browser is None and owner.process is None for owner in owners)


@pytest.fixture
def site():
    image = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
    )
    assets = {
        "/image.png": ("image/png", image),
        "/paper.pdf": ("application/pdf", b"%PDF-1.7\noriginal local PDF bytes\n%%EOF"),
        "/supplement.bin": ("application/octet-stream", bytes(range(256))),
    }
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            calls.append(self.path)
            status = 200
            challenge = False
            if self.path in {
                "/auto",
                "/recover",
            } and "clearance=local" not in self.headers.get("Cookie", ""):
                status = 403
                challenge = True
                mime = "text/html"
                body = b'<html><title>Just a moment...</title><script>setTimeout(() => {document.cookie="clearance=local; path=/"; location.replace("/recover");}, 150)</script><body>Automatic verification</body></html>'
            elif self.path == "/recover":
                mime, body = "application/octet-stream", bytes(range(256))
            elif self.path == "/delayed-challenge":
                status, challenge, mime = 403, True, "text/html"
                body = b"""<html><title>Loading verification</title><body>
<script>setTimeout(() => {
  const indicator = document.createElement('script');
  indicator.type = 'application/json';
  indicator.src = '/cdn-cgi/challenge-platform/local.js';
  document.head.appendChild(indicator);
  const widget = document.createElement('div');
  widget.style = 'width:300px;height:70px;background:#eee';
  widget.innerHTML = '<input type="hidden" name="cf-turnstile-response"><span>Verify</span>';
  widget.onclick = () => location.replace('/article');
  document.body.appendChild(widget);
}, 1100);</script></body></html>"""
            elif self.path == "/slow":
                time.sleep(2)
                mime, body = "text/html", b"<html><title>Slow article</title></html>"
            elif self.path in assets:
                mime, body = assets[self.path]
            else:
                mime = "text/html"
                if self.path == "/challenge":
                    body = b"<html><title>Verify you are human</title><body>Please verify you are human before proceeding</body></html>"
                else:
                    body = (
                        '<html><title>Local article</title><meta name="citation_doi" content="10.1073/pnas.test"><body><main id="bodymatter"><h2>Results</h2><p>'
                        + (
                            "Scientific results demonstrate the proposed mechanism. "
                            * 100
                        )
                        + '</p></main><a href="/paper.pdf" target="_blank">Supplement</a></body></html>'
                    ).encode()
            self.send_response(status)
            if challenge:
                self.send_header("cf-mitigated", "challenge")
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", assets, calls
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def _config(tmp_path, provider="pnas"):
    return BrowserRuntimeConfig(
        provider,
        "10.1073/pnas.test" if provider == "pnas" else "10.1016/example",
        tmp_path / "artifacts",
        True,
        None,
        user_data_dir=tmp_path / f"{provider}-byparr",
        backend="byparr",
        state_mode="json",
        persist_storage_state=False,
    )


@pytest.mark.parametrize("provider", ["pnas", "elsevier"])
def test_owned_shared_session_collects_original_asset_bytes_and_cleans_processes(
    prepared, site, monkeypatch, tmp_path, provider
):
    base, assets, calls = site
    _set_home(monkeypatch, "pnas", base + "/")
    _set_home(monkeypatch, "elsevier", base + "/")
    config = _config(tmp_path, provider)
    with RuntimeContext(env={}) as runtime:
        result = fetch_html_with_browser(
            [base + "/doi/full/10.1073/pnas.test"],
            publisher=provider,
            config=config,
            runtime_context=runtime,
            wait_seconds=0,
            options=BrowserHtmlFetchOptions(readiness_budget_seconds=2),
        )
        context = runtime.new_browser_context_for_runtime_config(config)
        manager = context._paper_fetch_navigator
        process = manager.process
        owned_processes = _owned_processes(manager)
        work = manager.work_dir
        assert manager.new_context() is context
        assert manager.diagnostics["context_reused"]
        assert result.browser_context_seed["diagnostics"]["browser_backend"] == "byparr"
        assert "Scientific results" in result.html
        assert calls[0] == "/doi/full/10.1073/pnas.test"
        assert "/" not in calls
        from paper_fetch.providers.browser_workflow.fetchers.context import (
            BrowserDocumentFetcherOptions,
        )
        from paper_fetch.providers.browser_workflow.fetchers.file import (
            _SharedBrowserFileDocumentFetcher,
        )

        fetcher = _SharedBrowserFileDocumentFetcher(
            browser_context_seed_getter=lambda: result.browser_context_seed,
            seed_urls_getter=lambda: [],
            runtime_context=runtime,
            browser_options=BrowserDocumentFetcherOptions(runtime_config=config),
        )
        try:
            for path, (_mime, expected) in assets.items():
                fetched = fetcher(base + path, {})
                assert fetched["body"] == expected
        finally:
            fetcher.close()
        assert manager.process is process
    assert process is None or process.poll() is not None
    assert owned_processes and all(_exited(p) for p in owned_processes)
    assert manager.context is None and manager.browser is None and not work.exists()


def test_api_ok_does_not_accept_verification_page(
    prepared, site, monkeypatch, tmp_path
):
    base, _, _ = site
    _set_home(monkeypatch, "pnas", base + "/")
    with RuntimeContext(env={}) as runtime:
        with pytest.raises(BrowserRuntimeFailure):
            fetch_html_with_browser(
                [base + "/challenge"],
                publisher="pnas",
                config=_config(tmp_path),
                runtime_context=runtime,
                wait_seconds=0,
                readiness=BrowserHtmlReadiness(wait_for_article_body=False),
            )
        context = runtime.new_browser_context_for_runtime_config(_config(tmp_path))
        assert context._paper_fetch_navigator.diagnostics["byparr_navigations"]
        assert not (tmp_path / "pnas-byparr/storage-state.json").exists()


def test_accepted_json_state_restores_in_fresh_owned_camoufox(
    prepared, site, monkeypatch, tmp_path
):
    base, _, _ = site
    config = replace(_config(tmp_path), persist_storage_state=True)
    _set_home(monkeypatch, "pnas", "https://www.pnas.org/")

    def attach(context):
        page = context.new_page()
        context.route(
            "https://www.pnas.org/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body="<html><title>Article</title><body>Article</body></html>",
            ),
        )
        return page

    with RuntimeContext(env={}) as runtime:
        context = runtime.new_browser_context_for_runtime_config(config)
        page = attach(context)
        navigate_page(page, "https://www.pnas.org/article", timeout_ms=30000)
        context.add_cookies(
            [
                {
                    "name": "auth",
                    "value": "local-test",
                    "domain": "www.pnas.org",
                    "path": "/",
                    "secure": True,
                }
            ]
        )
        page.evaluate("localStorage.setItem('entitlement','local-test')")
        staged, _ = stage_storage_state(
            context, config, filter_url="https://www.pnas.org/article"
        )
        assert commit_staged_storage_state(staged, config)["saved"]
    with RuntimeContext(env={}) as runtime:
        context = runtime.new_browser_context_for_runtime_config(config)
        page = attach(context)
        navigate_page(page, "https://www.pnas.org/article", timeout_ms=30000)
        assert page.evaluate("localStorage.getItem('entitlement')") == "local-test"
        assert any(
            c["name"] == "auth" and c["value"] == "local-test"
            for c in context.cookies()
        )
        assert context._paper_fetch_navigator.diagnostics["state_restored"]


def test_cancellation_stops_owned_browser_tree(prepared, site, monkeypatch, tmp_path):
    from paper_fetch.http import RequestCancelledError

    base, _, _ = site
    _set_home(monkeypatch, "pnas", base + "/")
    runtime = RuntimeContext(env={})
    config = _config(tmp_path)
    context = runtime.new_browser_context_for_runtime_config(config)
    manager = context._paper_fetch_navigator
    process = manager.process
    owned_processes = _owned_processes(manager)
    work = manager.work_dir
    monkeypatch.setattr(
        runtime,
        "raise_if_cancelled",
        lambda: (_ for _ in ()).throw(RequestCancelledError("cancelled")),
    )
    try:
        with pytest.raises(RequestCancelledError):
            navigate_page(context.new_page(), base + "/article", timeout_ms=30000)
    finally:
        runtime.close()
    assert process is None or process.poll() is not None
    assert owned_processes and all(_exited(p) for p in owned_processes)
    assert manager.context is None and manager.browser is None and not work.exists()


def test_native_pdf_click_uses_download_bytes_in_same_camoufox(
    prepared, site, monkeypatch, tmp_path
):
    from paper_fetch.providers.browser_workflow.fetchers.context import (
        BrowserDocumentFetcherOptions,
    )
    from paper_fetch.providers.browser_workflow.fetchers.file import (
        _SharedBrowserFileDocumentFetcher,
    )

    base, assets, _ = site
    _set_home(monkeypatch, "pnas", base + "/")
    config = _config(tmp_path)
    with RuntimeContext(env={}) as runtime:
        context = runtime.new_browser_context_for_runtime_config(config)
        fetcher = _SharedBrowserFileDocumentFetcher(
            browser_context_seed_getter=lambda: {
                "browser_final_url": base + "/article"
            },
            seed_urls_getter=lambda: [base + "/article"],
            runtime_context=runtime,
            browser_options=BrowserDocumentFetcherOptions(
                runtime_config=config, file_fetch_mode="page_click"
            ),
        )
        try:
            result = fetcher(
                base + "/paper.pdf",
                {"kind": "supplementary", "source_url": base + "/paper.pdf"},
            )
            assert result is not None, str(fetcher.failure_for(base + "/paper.pdf"))
            assert result["body"] == assets["/paper.pdf"][1]
            assert runtime.new_browser_context_for_runtime_config(config) is context
        finally:
            fetcher.close()


def test_elsevier_final_document_mathjax_and_current_pdf_share_context(
    prepared, monkeypatch, tmp_path
):
    from paper_fetch.providers._elsevier_html import (
        extract_pdf_candidate_urls_from_html,
    )
    from paper_fetch.providers.browser_workflow.fetchers.context import (
        BrowserDocumentFetcherOptions,
    )
    from paper_fetch.providers.browser_workflow.fetchers.file import (
        _SharedBrowserFileDocumentFetcher,
    )

    pii = "S016819232400090X"
    home = "https://www.sciencedirect.com/"
    url = home + "science/article/pii/" + pii
    pdf_url = url + "/pdfft?download=true"
    calls = []
    pdf_bytes = b"%PDF-1.7\nowned article bytes\n%%EOF"
    article = (
        '<html><meta name="citation_doi" content="10.1016/example"><title>Example</title>'
        '<body><div id="body"><h2>Results</h2><p>'
        + "Observed scientific mechanism. "
        * 100
        + "</p>"
        '<mjx-container id="math-source">rendered glyphs</mjx-container></div>'
        '<a href="' + pdf_url + '">Download PDF</a>'
        '<div id="references"><a href="' + url + '/pdf">Reference PDF</a></div>'
        "<script>window.MathJax={startup:{document:{getMathItemsWithin:()=>["
        '{typesetRoot:document.getElementById("math-source"),math:"<math><msup><mi>x</mi><mn>2</mn></msup></math>"}'
        "]}}};</script></body></html>"
    )
    config = _config(tmp_path, "elsevier")
    with RuntimeContext(env={}) as runtime:
        context = runtime.new_browser_context_for_runtime_config(config)
        manager = context._paper_fetch_navigator

        def respond(route):
            requested = route.request.url
            calls.append(requested)
            if requested == pdf_url:
                route.fulfill(
                    status=200, content_type="application/pdf", body=pdf_bytes
                )
            elif requested == url and calls.count(url) == 1:
                route.fulfill(
                    status=403,
                    content_type="text/html",
                    body="<html><title>Access</title><script>setTimeout(()=>location.reload(), 100)</script></html>",
                )
            else:
                route.fulfill(
                    status=200,
                    content_type="text/html",
                    body=article
                    if requested == url
                    else "<html><title>Home</title></html>",
                )

        context.route(home + "**", respond)
        result = fetch_html_with_browser(
            [url],
            publisher="elsevier",
            config=config,
            runtime_context=runtime,
            wait_seconds=0,
            readiness=BrowserHtmlReadiness(wait_for_article_body=True),
            options=BrowserHtmlFetchOptions(readiness_budget_seconds=5),
        )
        assert result.response_status == 200
        assert 'data-paper-fetch-mathml="' in result.html
        assert "&lt;msup&gt;" in result.html
        assert calls[0] == url
        assert calls.count(url) == 2
        candidate = result.diagnostics["browser_runtime_trace"]["candidates"][-1]
        assert candidate["main_document_response"]["status"] == 200
        assert extract_pdf_candidate_urls_from_html(result.html, url) == [pdf_url]
        fetcher = _SharedBrowserFileDocumentFetcher(
            browser_context_seed_getter=lambda: result.browser_context_seed,
            seed_urls_getter=lambda: [],
            runtime_context=runtime,
            browser_options=BrowserDocumentFetcherOptions(
                runtime_config=config, file_fetch_mode="page_click"
            ),
        )
        try:
            fetched = fetcher(pdf_url, {"kind": "supplementary", "source_url": pdf_url})
            assert fetched is not None, str(fetcher.failure_for(pdf_url))
            assert fetched["body"] == pdf_bytes
            assert runtime.new_browser_context_for_runtime_config(config) is context
            assert context._paper_fetch_navigator is manager
        finally:
            fetcher.close()


def test_elsevier_pdf_route_downloads_in_owned_context_without_http_lane(
    prepared, monkeypatch, tmp_path
):
    from paper_fetch.providers import _pdf_fallback as pdf
    from paper_fetch.providers.browser_workflow.pdf_fallback import (
        fetch_seeded_browser_pdf_payload,
    )
    from paper_fetch.providers.browser_workflow.shared import (
        default_browser_workflow_deps,
    )
    from paper_fetch.providers._pdf_common import PdfFetchResult

    home = "https://www.sciencedirect.com/"
    url = home + "science/article/pii/S016819232400090X/pdfft?download=true"
    original = b"%PDF-1.7\nowned current article\n%%EOF"
    config = _config(tmp_path, "elsevier")

    def converted(**kwargs):
        assert kwargs["pdf_bytes"] == original
        return PdfFetchResult(
            kwargs["source_url"], kwargs["final_url"], original, "Converter boundary"
        )

    monkeypatch.setattr(pdf, "pdf_fetch_result_from_bytes", converted)
    monkeypatch.setattr(
        pdf,
        "fetch_pdf_over_http",
        lambda *a, **k: pytest.fail(
            "Elsevier browser PDF must stay in its browser context"
        ),
    )
    with RuntimeContext(env={}) as runtime:
        context = runtime.new_browser_context_for_runtime_config(config)
        context.route(
            home + "**",
            lambda route: route.fulfill(
                status=200,
                content_type="application/pdf"
                if route.request.url == url
                else "text/html",
                headers={"Content-Disposition": 'attachment; filename="article.pdf"'}
                if route.request.url == url
                else {},
                body=original
                if route.request.url == url
                else "<html><title>Home</title></html>",
            ),
        )

        def unnecessary_warm(*args, **kwargs):
            pytest.fail(
                "Elsevier PDF must reuse HTML context without warming a PDF URL"
            )

        result = fetch_seeded_browser_pdf_payload(
            provider="elsevier",
            doi="10.1016/example",
            runtime=config,
            pdf_candidates=[url],
            html_candidates=[url.split("/pdfft")[0]],
            landing_page_url=None,
            user_agent="test",
            context=runtime,
            browser_context_seed={
                "browser_final_url": url.split("/pdfft")[0],
                "browser_cookies": [
                    {
                        "name": "session",
                        "value": "local",
                        "domain": "www.sciencedirect.com",
                        "path": "/",
                    }
                ],
            },
            html_failure_reason="insufficient_body",
            html_failure_message="Article body unavailable",
            deps=replace(
                default_browser_workflow_deps(), warm_browser_context=unnecessary_warm
            ),
        )
        assert result.body == original
        assert runtime.new_browser_context_for_runtime_config(config) is context
        assert context._paper_fetch_navigator.home_url == home


def _set_home(monkeypatch, provider, url):
    from dataclasses import replace
    from paper_fetch import provider_catalog

    catalog = dict(provider_catalog.PROVIDER_CATALOG)
    catalog[provider] = replace(catalog[provider], browser_home_url=url)
    monkeypatch.setattr(provider_catalog, "PROVIDER_CATALOG", catalog)


@pytest.mark.parametrize("state_mode", ["native", "json"])
def test_shared_context_modes_preserve_state_and_real_responses(
    prepared, site, tmp_path, state_mode
):
    from paper_fetch.providers.browser_runtime.context import open_browser_context
    from paper_fetch.providers.browser_runtime.navigation import context_get

    base, assets, calls = site
    config = replace(_config(tmp_path), provider="wiley", state_mode=state_mode)
    owner, context = open_browser_context(config)
    try:
        page = context.new_page()
        response = navigate_page(
            page, base + "/article", wait_until="domcontentloaded", timeout_ms=10000
        )
        assert response.status == 200 and response.url == base + "/article"
        page.evaluate("localStorage.setItem('replay', 'native-value')")
        context.add_cookies(
            [
                {
                    "name": "replay",
                    "value": "native-value",
                    "url": base,
                    "expires": time.time() + 3600,
                }
            ]
        )
        for path, (mime, body) in assets.items():
            fetched = context_get(context, base + path, timeout=10000)
            assert fetched.body() == body and fetched.headers["content-type"] == mime
        if state_mode == "native":
            assert owner.manager.context is context
            assert context._paper_fetch_navigator.native_profile == owner.path
    finally:
        owner.close()
    if state_mode == "native":
        owner, context = open_browser_context(config)
        try:
            page = context.new_page()
            navigate_page(
                page, base + "/article", wait_until="domcontentloaded", timeout_ms=10000
            )
            assert page.evaluate("localStorage.getItem('replay')") == "native-value"
            assert any(item["name"] == "replay" for item in context.cookies())
        finally:
            owner.close()


def test_challenged_get_recovers_once_in_same_context(prepared, site, tmp_path):
    from paper_fetch.providers.browser_runtime.context import open_browser_context
    from paper_fetch.providers.browser_runtime.navigation import context_get

    base, _, calls = site
    owner, context = open_browser_context(_config(tmp_path))
    try:
        response = context_get(context, base + "/recover", timeout=15000)
        assert response.status == 200
        assert response.body() == bytes(range(256))
        assert (
            calls.count("/recover") == 4
        )  # original GET, page GET, automatic redirect, one retry GET
        events = [
            event
            for item in owner.diagnostics["byparr_navigations"]
            for event in item["events"]
        ]
        assert any(event["kind"] == "challenge_detected" for event in events)
        assert not any(
            event["kind"] in {"solver_called", "solver_click"} for event in events
        )
        assert len(owner.browser.contexts) == 1
    finally:
        owner.close()


def test_invisible_delayed_challenge_calls_upstream_and_receives_article(
    prepared, site, tmp_path
):
    from paper_fetch.providers.browser_runtime.context import open_browser_context
    from paper_fetch.providers.browser_runtime.byparr_engine import engine_name

    if engine_name() != "invisible":
        pytest.skip("Invisible sync polling contract")
    base, _, calls = site
    owner, context = open_browser_context(_config(tmp_path))
    try:
        page = context.new_page()
        response = navigate_page(
            page,
            base + "/delayed-challenge",
            timeout_ms=15000,
            wait_until="domcontentloaded",
        )
        assert response.status == 200
        assert response.url == base + "/article"
        assert b"Scientific results demonstrate" in response.body()
        assert "Scientific results demonstrate" in page.content()
        assert calls.count("/delayed-challenge") == calls.count("/article") == 1
        operation = owner.diagnostics["byparr_navigations"][-1]
        assert [doc["status"] for doc in operation["documents"]] == [403, 200]
        events = operation["events"]
        assert sum(event["kind"] == "solver_called" for event in events) == 1
        assert sum(event["kind"] == "solver_click" for event in events) == 1
        assert any(
            event["kind"] == "challenge_result"
            and event["outcome"] == "awaiting_response"
            for event in events
        )
        assert events[-1]["outcome"] == "cleared"
    finally:
        owner.close()


def test_click_popup_and_iframe_automatic_validation_keep_relationships(
    prepared, site, tmp_path
):
    from paper_fetch.providers.browser_runtime.context import open_browser_context
    from paper_fetch.providers.browser_runtime.navigation import managed_action

    base, _, calls = site
    owner, context = open_browser_context(_config(tmp_path))
    try:
        page = context.new_page()
        navigate_page(
            page, base + "/article", timeout_ms=10000, wait_until="domcontentloaded"
        )
        context.route(
            base + "/click",
            lambda route: route.fulfill(
                content_type="text/html",
                body=f'<a href="{base}/auto" target="_blank">Open</a>',
            ),
        )
        navigate_page(
            page, base + "/click", timeout_ms=10000, wait_until="domcontentloaded"
        )
        popup_downloads = []
        page.on(
            "popup",
            lambda popup: popup.on(
                "download", lambda download: popup_downloads.append(download)
            ),
        )
        with page.expect_popup() as popup_info:
            with managed_action(page, timeout_ms=15000):
                page.locator("a").click(no_wait_after=True)
        popup = popup_info.value
        assert popup.opener() is page
        deadline = time.monotonic() + 10
        while not popup_downloads and time.monotonic() < deadline:
            page.wait_for_timeout(20)
        assert popup_downloads and popup_downloads[0].url == base + "/recover"
        # The auto challenge ends in a download; the original click is issued once.
        assert calls.count("/auto") == 1
        context.clear_cookies()
        context.route(
            base + "/wrapper",
            lambda route: route.fulfill(
                content_type="text/html",
                body=f'<html><iframe src="{base}/auto"></iframe></html>',
            ),
        )
        with page.expect_download(timeout=10000) as iframe_download:
            navigate_page(
                page, base + "/wrapper", timeout_ms=15000, wait_until="domcontentloaded"
            )
        assert iframe_download.value.url == base + "/recover"
        from paper_fetch.providers.browser_runtime.navigation import (
            settle_page_navigation,
        )

        settle_page_navigation(page, timeout_ms=10000)
        events = [
            event
            for item in owner.diagnostics["byparr_navigations"]
            for event in item["events"]
        ]
        assert sum(event["kind"] == "navigation_managed" for event in events) >= 3
        assert any(
            event["kind"] == "challenge_detected"
            and event.get("response_sequence") is not None
            for event in events
        ), owner.diagnostics
        assert not any(event["kind"] == "solver_click" for event in events)
    finally:
        owner.close()


def test_cancellation_interrupts_inflight_managed_navigation(prepared, site, tmp_path):
    from paper_fetch.http import RequestCancelledError

    base, _, _ = site
    runtime = RuntimeContext(env={})
    context = runtime.new_browser_context_for_runtime_config(_config(tmp_path))
    owner = context._paper_fetch_navigator
    process = owner.process
    owned_processes = _owned_processes(owner)
    page = context.new_page()
    timer = threading.Timer(0.15, runtime.fence_commits)
    started = time.monotonic()
    timer.start()
    try:
        with pytest.raises(RequestCancelledError):
            navigate_page(page, base + "/slow", timeout_ms=10000)
        assert time.monotonic() - started < 1.5
    finally:
        timer.join()
        runtime.close()
    assert process is None or process.poll() is not None
    assert owned_processes and all(_exited(p) for p in owned_processes)
    assert owner.context is None and owner.browser is None


def test_ieee_iframe_pdf_keeps_real_response_or_download_under_byparr(
    prepared, tmp_path
):
    from paper_fetch.providers._ieee_pdf import navigate_stamp_pdf
    from paper_fetch.providers.browser_runtime.context import open_browser_context

    config = replace(
        _config(tmp_path), provider="ieee", doi="10.1109/test", state_mode="native"
    )
    owner, context = open_browser_context(config)
    body = b"%PDF-1.7\nlocal IEEE original bytes\n%%EOF"
    stamp = "https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=12345"
    pdf = "https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?arnumber=12345"
    context.route(
        stamp,
        lambda route: route.fulfill(
            content_type="text/html", body=f'<html><iframe src="{pdf}"></iframe></html>'
        ),
    )
    context.route(
        pdf, lambda route: route.fulfill(content_type="application/pdf", body=body)
    )
    try:
        initial, response, download = navigate_stamp_pdf(
            context.new_page(),
            stamp,
            goto_kwargs={"wait_until": "domcontentloaded", "timeout": 10000},
            timeout_ms=10000,
            expected_identity={"doi": "10.1109/test"},
        )
        assert initial.status == 200
        if download is not None:
            destination = tmp_path / "ieee.pdf"
            download.save_as(destination)
            assert destination.read_bytes() == body
        else:
            assert response.status == 200 and response.body() == body
        assert context._paper_fetch_navigator.diagnostics["backend"] == "byparr"
    finally:
        owner.close()


def test_wiley_page_image_captures_original_bytes_under_byparr(prepared, tmp_path):
    from paper_fetch.providers._wiley_page_assets import WileyPageAssetFetcher
    from paper_fetch.providers.browser_workflow.fetchers.context import (
        BrowserDocumentFetcherOptions,
    )
    from tests.support.wiley_page_assets import figure, png_bytes

    root = "https://onlinelibrary.wiley.com"
    asset = figure(root, 1)
    body = png_bytes(640, 480)
    config = replace(
        _config(tmp_path), provider="wiley", doi="10.1111/test", state_mode="native"
    )
    with RuntimeContext(env={}) as runtime:
        context = runtime.new_browser_context_for_runtime_config(config)
        context.route(
            asset["url"],
            lambda route: route.fulfill(content_type="image/png", body=body),
        )
        fetcher = WileyPageAssetFetcher(
            assets=[asset],
            browser_context_seed_getter=lambda: {},
            seed_urls_getter=lambda: [],
            runtime_context=runtime,
            browser_options=BrowserDocumentFetcherOptions(runtime_config=config),
        )
        try:
            result = fetcher(asset["url"], asset)
            assert result is not None, fetcher.failure_for(asset["url"])
            assert result["body"] == body
            assert fetcher.navigation_count == 1
            assert fetcher.browser_backend == "byparr"
        finally:
            fetcher.close()
