"""Real owned Chrome/CDP/solver with a local HTTP server and preprepared runtime."""

from dataclasses import replace
import base64
import os
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from paper_fetch import offline_flaresolverr
from paper_fetch.providers.browser_runtime import flaresolverr_manager as managed
from paper_fetch.providers.browser_runtime import flaresolverr_preparation as prep
from paper_fetch.providers.browser_runtime.api import fetch_html_with_browser
from paper_fetch.providers.browser_runtime.chrome import (
    discover_chrome,
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

pytestmark = pytest.mark.browser


@pytest.fixture
def prepared(monkeypatch):
    cache = os.environ.get("PAPER_FETCH_TEST_FLARESOLVERR_CACHE")
    if not cache or not supported_platform():
        pytest.skip(
            "requires preprepared FlareSolverr source/driver cache and system Chrome"
        )
    cache = Path(cache)
    root, _, identity = prep.runtime_location(cache)
    if not prep.valid_cache(root, identity):
        pytest.skip("locked FlareSolverr cache is unavailable for this Python")
    chrome = discover_chrome()
    driver = cache / "drivers" / os.sys.platform / chrome.version
    if not prep.valid_cache(driver, chrome.version):
        pytest.skip("matching ChromeDriver cache is unavailable")
    monkeypatch.setattr(managed, "prepare_source", lambda cache, budget: root)
    monkeypatch.setattr(
        managed,
        "prepare_driver",
        lambda cache, version, budget: (
            driver / ("chromedriver.exe" if os.name == "nt" else "chromedriver"),
            (driver / "version").read_text(),
        ),
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

    class Owner(managed.FlareSolverrManager):
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
            processes.append(self.process)
            directories.append(self.work_dir)
            assert not context.cookies()
            assert all(
                page.url in {"about:blank", "chrome://newtab/"}
                for page in context.pages
            )
            if cancel:
                raise KeyboardInterrupt()
            return context

    monkeypatch.setattr(offline_flaresolverr, "FlareSolverrManager", Owner)
    chrome = discover_chrome()
    runtime = managed.prepare_source(tmp_path, prep.PreparationBudget(10))
    driver, version = managed.prepare_driver(
        tmp_path, chrome.version, prep.PreparationBudget(10)
    )
    if cancel:
        with pytest.raises(KeyboardInterrupt):
            offline_flaresolverr.local_check({}, chrome, runtime, driver, version)
    else:
        offline_flaresolverr.local_check({}, chrome, runtime, driver, version)
    assert all(process.poll() is not None for process in processes)
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
            if self.path in assets:
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
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
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
        timeout_ms=60000,
        user_data_dir=tmp_path / f"{provider}-flaresolverr",
        backend="flaresolverr",
        persist_storage_state=False,
    )


@pytest.mark.parametrize("provider", ["pnas", "elsevier"])
def test_owned_cdp_session_collects_original_asset_bytes_and_cleans_processes(
    prepared, site, monkeypatch, tmp_path, provider
):
    base, assets, calls = site
    monkeypatch.setattr(managed, "PNAS_HOME_URL", base + "/")
    monkeypatch.setitem(managed.PROVIDER_HOME_URLS, "elsevier", base + "/")
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
        manager = context._paper_fetch_solver
        process = manager.process
        work = manager.work_dir
        assert manager.new_context() is context
        assert manager.diagnostics["context_reused"]
        assert (
            result.browser_context_seed["diagnostics"]["browser_backend"]
            == "flaresolverr"
        )
        assert "Scientific results" in result.html
        assert calls.index("/") < calls.index("/doi/full/10.1073/pnas.test")
        assert calls.count("/") == 1
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
    assert process.poll() is not None and not work.exists()


def test_api_ok_does_not_accept_verification_page(
    prepared, site, monkeypatch, tmp_path
):
    base, _, _ = site
    monkeypatch.setattr(managed, "PNAS_HOME_URL", base + "/")
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
        assert context._paper_fetch_solver.diagnostics["homepage_visited"]
        assert not (tmp_path / "pnas-flaresolverr/storage-state.json").exists()


def test_accepted_json_state_restores_in_fresh_owned_chrome(
    prepared, site, monkeypatch, tmp_path
):
    base, _, _ = site
    config = replace(_config(tmp_path), persist_storage_state=True)
    monkeypatch.setattr(managed, "PNAS_HOME_URL", "https://www.pnas.org/")

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
        managed.navigate_page(page, "https://www.pnas.org/article", timeout_ms=30000)
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
        managed.navigate_page(page, "https://www.pnas.org/article", timeout_ms=30000)
        assert page.evaluate("localStorage.getItem('entitlement')") == "local-test"
        assert any(
            c["name"] == "auth" and c["value"] == "local-test"
            for c in context.cookies()
        )
        assert context._paper_fetch_solver.diagnostics["state_restored"]


def test_cancellation_stops_owned_browser_tree(prepared, site, monkeypatch, tmp_path):
    from paper_fetch.http import RequestCancelledError

    base, _, _ = site
    monkeypatch.setattr(managed, "PNAS_HOME_URL", base + "/")
    runtime = RuntimeContext(env={})
    config = _config(tmp_path)
    context = runtime.new_browser_context_for_runtime_config(config)
    manager = context._paper_fetch_solver
    process = manager.process
    work = manager.work_dir
    monkeypatch.setattr(
        runtime,
        "raise_if_cancelled",
        lambda: (_ for _ in ()).throw(RequestCancelledError("cancelled")),
    )
    try:
        with pytest.raises(RequestCancelledError):
            managed.navigate_page(
                context.new_page(), base + "/article", timeout_ms=30000
            )
    finally:
        runtime.close()
    assert process.poll() is not None and not work.exists()


def test_wsl_readonly_socket_mount_is_private_and_unchanged(tmp_path):
    import subprocess
    import sys

    sockets = Path("/tmp/.X11-unix")
    if sys.platform != "linux" or not sockets.exists() or os.access(sockets, os.W_OK):
        pytest.skip("requires read-only WSL X11 socket mount")
    stamp = (sockets.stat().st_dev, sockets.stat().st_ino)
    prefix = managed.linux_launch_prefix(True, tmp_path, prep.PreparationBudget(10))
    name = f"paper-fetch-test-{os.getpid()}-{tmp_path.name}"
    subprocess.run(
        [
            *prefix,
            sys.executable,
            "-I",
            "-c",
            "import socket; s=socket.socket(socket.AF_UNIX); s.bind('/tmp/.X11-unix/"
            + name
            + "')",
        ],
        check=True,
        timeout=10,
    )
    assert (tmp_path / "x11" / name).exists()
    assert not (sockets / name).exists()
    assert (sockets.stat().st_dev, sockets.stat().st_ino) == stamp


def test_native_pdf_click_uses_download_bytes_in_same_chrome(
    prepared, site, monkeypatch, tmp_path
):
    from paper_fetch.providers.browser_workflow.fetchers.context import (
        BrowserDocumentFetcherOptions,
    )
    from paper_fetch.providers.browser_workflow.fetchers.file import (
        _SharedBrowserFileDocumentFetcher,
    )

    base, assets, _ = site
    monkeypatch.setattr(managed, "PNAS_HOME_URL", base + "/")
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
            assert result is not None, fetcher.failure_for(base + "/paper.pdf")
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
        manager = context._paper_fetch_solver

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
        assert calls[0] == home
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
            assert fetched["body"] == pdf_bytes
            assert runtime.new_browser_context_for_runtime_config(config) is context
            assert context._paper_fetch_solver is manager
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
        assert context._paper_fetch_solver.home_url == home
