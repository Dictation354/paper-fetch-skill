"""Run the managed Chromium controller against local publisher endpoints."""

import contextlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from paper_fetch.http import RequestCancelledError
from paper_fetch.providers._pdf_fallback import (
    PdfRequestContext,
    fetch_pdf_with_browser,
)
from paper_fetch.providers.browser_runtime.api import (
    fetch_html_with_browser,
    load_runtime_config,
)
from paper_fetch.providers.browser_runtime.context import open_browser_context
from paper_fetch.providers.browser_runtime.navigation import navigate_page
from paper_fetch.providers.browser_runtime.types import (
    BrowserHtmlReadiness,
    BrowserRuntimeFailure,
)
from paper_fetch.runtime import RuntimeContext

pytestmark = pytest.mark.browser

DOI = "10.1016/local-chromium"


@pytest.fixture
def config(tmp_path):
    from tests.support.offline_chromium import prepared_executable

    return load_runtime_config(
        {
            "PAPER_FETCH_BROWSER_BINARY_PATH": str(prepared_executable()),
            "PAPER_FETCH_BROWSER_PROFILE_DIR": str(tmp_path / "profile"),
            "PAPER_FETCH_BROWSER_TIMEOUT_MS": "10000",
            "XDG_DATA_HOME": str(tmp_path / "data"),
        },
        provider="elsevier",
        doi=DOI,
    )


@pytest.fixture
def article_server():
    fitz = pytest.importorskip("pymupdf")
    with fitz.open() as doc:
        doc.new_page().insert_text((50, 50), f"Local Chromium article, DOI {DOI}")
        pdf = doc.tobytes()
    slow = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path
            if path == "/slow":
                slow.wait(5)
                return
            if path == "/article":
                body = b"<title>Local article</title><article>Chromium article body</article>"
                headers = {
                    "Content-Type": "text/html",
                    "Set-Cookie": "paper=local; Path=/",
                }
            elif path == "/article.pdf" and self.headers.get("Cookie") == "paper=local":
                body = pdf
                headers = {
                    "Content-Type": "application/pdf",
                    "Content-Disposition": 'attachment; filename="article.pdf"',
                }
            else:
                self.send_error(404)
                return
            self.send_response(200)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}", pdf
        finally:
            slow.set()
            server.shutdown()
            thread.join(2)


def test_real_chromium_html_and_pdf_share_the_request_context(
    config, article_server, tmp_path
):
    base, pdf = article_server
    with RuntimeContext(env={}, download_dir=tmp_path / "results") as runtime:
        html = fetch_html_with_browser(
            [base + "/article"],
            publisher="elsevier",
            config=config,
            runtime_context=runtime,
            readiness=BrowserHtmlReadiness(wait_for_article_body=False),
            wait_seconds=0,
        )
        assert html.response_status == 200
        assert "Chromium article body" in html.html
        result = fetch_pdf_with_browser(
            [base + "/article.pdf"],
            artifact_dir=config.artifact_dir,
            browser_config=config,
            allow_pdf_only=True,
            request=PdfRequestContext(runtime=runtime, browser_only=True),
        )
        assert result.pdf_bytes == pdf
    assert len(runtime.diagnostic_artifacts) == 1
    diagnostic = next((tmp_path / "results").rglob("scrapling.json"))
    evidence = json.loads(diagnostic.read_text())
    assert evidence["browser_backend"] == "scrapling"
    assert evidence["chromium_version"]
    assert evidence["context_reused"] and evidence["session_closed"]
    assert [entry["mode"] for entry in evidence["navigations"]] == ["html", "file"]
    assert evidence["navigations"][0]["response_status"] == 200
    assert evidence["navigations"][1]["response_status"] == 200
    assert evidence["navigations"][1]["download_started"]
    assert (config.profile_dir / "Local State").is_file()


@pytest.mark.parametrize("cancel", [False, True], ids=["budget", "cancel"])
def test_real_chromium_stops_navigation_and_cleans_up(config, article_server, cancel):
    base, _ = article_server
    cancelled = threading.Event()
    with RuntimeContext(env={}, cancel_check=cancelled.is_set) as runtime:
        _, context = open_browser_context(config, runtime_context=runtime)
        manager = context._paper_fetch_navigator
        process = manager.process.process
        browser = context.browser
        page = context.new_page()
        started = time.monotonic()
        if cancel:
            timer = threading.Timer(0.2, cancelled.set)
            timer.start()
        else:
            runtime.browser_deadline_monotonic = started + 0.2
        try:
            with pytest.raises(
                RequestCancelledError if cancel else BrowserRuntimeFailure
            ) as failure:
                navigate_page(page, base + "/slow", timeout_ms=4000)
            if not cancel:
                assert failure.value.kind == "scrapling_timeout"
            assert time.monotonic() - started < 2
        finally:
            if cancel:
                timer.cancel()
                timer.join()
            with contextlib.suppress(Exception):
                page.close()
    assert process.poll() is not None
    assert not browser.is_connected()
    assert manager.diagnostics["session_closed"]
    assert manager.diagnostics["navigations"][0]["failure_stage"] == "navigation"
    assert (config.profile_dir / "Local State").is_file()
