"""Real native persistence and directory lease concurrency contracts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest
from filelock import FileLock

from paper_fetch.providers.browser_runtime import profile
from paper_fetch.providers.browser_runtime.api import load_runtime_config
from paper_fetch.providers.browser_runtime.context import (
    browser_context,
    open_browser_context,
)
from paper_fetch.providers.browser_runtime.types import BrowserRuntimeFailure
from paper_fetch.runtime import RuntimeContext
from tests.support.publisher_profiles import NativeProfileDouble


@pytest.fixture
def config(tmp_path):
    return load_runtime_config(
        {"XDG_DATA_HOME": str(tmp_path)}, provider="pnas", doi="10.1073/pnas.test"
    )


def test_same_directory_threads_queue_and_different_publishers_do_not(
    config, monkeypatch
):
    monkeypatch.setattr(profile, "ScraplingManager", NativeProfileDouble)
    first, _ = open_browser_context(config)
    entered = threading.Event()
    waiting = threading.Event()
    failures = []

    def worker():
        waiting.set()
        try:
            manager, _ = open_browser_context(config)
            entered.set()
            manager.close()
        except BaseException as exc:
            failures.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    try:
        assert waiting.wait(2)
        assert not entered.wait(0.15)
        other, _ = open_browser_context(
            replace(
                config,
                provider="aip",
                user_data_dir=config.user_data_dir.parent / "aip-camoufox",
            )
        )
        other.close()
    finally:
        first.close()
        thread.join(4)
    assert entered.is_set()
    assert not failures
    assert not thread.is_alive()


def test_process_lease_wait_obeys_cancel_deadline_and_releases_on_exception(
    config, monkeypatch
):
    monkeypatch.setattr(profile, "ScraplingManager", NativeProfileDouble)
    path = profile.profile_path(config)
    path.mkdir(parents=True)
    process = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-c",
            "from filelock import FileLock; import sys; lock=FileLock(sys.argv[1]); lock.acquire(); print('locked', flush=True); sys.stdin.readline(); lock.release()",
            str(path / profile.PROFILE_LOCK_FILENAME),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout.readline().strip() == "locked"
        with RuntimeContext(env={}) as runtime:
            timer = threading.Timer(0.08, runtime.fence_commits)
            timer.start()
            started = time.monotonic()
            with pytest.raises(Exception, match="[Cc]ancel"):
                open_browser_context(config, runtime_context=runtime)
            timer.join()
            assert time.monotonic() - started < 2
    finally:
        process.stdin.write("release\n")
        process.stdin.flush()
        process.communicate(timeout=5)
    manager, _ = open_browser_context(config)
    manager.close()

    class BrokenNative(NativeProfileDouble):
        def new_context(self):
            raise RuntimeError("native launch failed")

    monkeypatch.setattr(profile, "ScraplingManager", BrokenNative)
    with pytest.raises(BrowserRuntimeFailure, match="native launch failed") as error:
        open_browser_context(config)
    assert error.value.kind == "browser_profile_load_failed"
    with FileLock(str(path / profile.PROFILE_LOCK_FILENAME)).acquire(timeout=0):
        pass


@pytest.fixture
def native_config(config):
    from tests.support.offline_chromium import prepared_executable

    return replace(config, binary_path=str(prepared_executable()))


@pytest.fixture
def offline_assets():
    import struct
    import zlib
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    def chunk(kind, body):
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body))
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 100, 100, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress((b"\0" + b"\x40\x80\xc0" * 100) * 100))
        + chunk(b"IEND", b"")
    )
    assets = {
        "/body": (
            "text/html",
            b"<title>Publisher article</title><article>Offline article body</article>",
        ),
        "/figure.png": ("image/png", png),
        "/article.pdf": ("application/pdf", b"%PDF-1.7 offline native browser bytes"),
        "/supplement.zip": (
            "application/zip",
            b"PK\x03\x04offline supplementary bytes",
        ),
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            content_type, body = assets[self.path]
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", assets
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


@pytest.mark.browser
def test_native_cookie_localstorage_survive_restart_and_all_entrypoints_borrow(
    native_config,
    offline_assets,
):
    from paper_fetch.providers._pdf_fallback import _open_pdf_browser_context
    from paper_fetch.providers.browser_runtime.html_fetcher import fetch_browser_html
    from paper_fetch.providers.browser_runtime.types import BrowserHtmlReadiness
    from paper_fetch.providers.browser_workflow.fetchers.context import (
        BrowserDocumentFetcherOptions,
    )
    from paper_fetch.providers.browser_workflow.fetchers.file import (
        _SharedBrowserFileDocumentFetcher,
    )
    from paper_fetch.providers.browser_workflow.fetchers.image import (
        _SharedBrowserImageDocumentFetcher,
    )

    config = native_config
    asset_root, assets = offline_assets
    url = "https://www.pnas.org/offline-profile-test"
    with RuntimeContext(env={}) as runtime:
        _, context = open_browser_context(config, runtime_context=runtime)
        context.route(
            "https://www.pnas.org/**",
            lambda route: route.fulfill(
                body="<title>Publisher article</title><article>Offline article body</article>",
                content_type="text/html",
            ),
        )
        initial_pages = list(context.pages)
        page = context.new_page()
        page.goto(url)
        page.evaluate("localStorage.setItem('profile-test', 'persistent')")
        context.add_cookies(
            [
                {
                    "name": "profile-test",
                    "value": "persistent",
                    "domain": "www.pnas.org",
                    "path": "/",
                    "expires": time.time() + 3600,
                }
            ]
        )
        page.close()
        html_result = fetch_browser_html(
            [asset_root + "/body"],
            publisher="pnas",
            config=replace(
                config,
            ),
            runtime_context=runtime,
            wait_seconds=0,
            readiness=BrowserHtmlReadiness(wait_for_article_body=False),
        )
        assert "Offline article body" in html_result.html
        assert html_result.diagnostics["browser_runtime_trace"]["persistent_profile"][
            "context_reused"
        ]
        assert (
            "storage_state_load" not in html_result.diagnostics["browser_runtime_trace"]
        )
        with browser_context(config, runtime_context=runtime) as html:
            assert html.context is context
        _, pdf = _open_pdf_browser_context(config, runtime=runtime)
        assert pdf is context
        response = pdf.request.get(asset_root + "/article.pdf")
        assert response.body() == assets["/article.pdf"][1]
        for fetcher_class in (
            _SharedBrowserFileDocumentFetcher,
            _SharedBrowserImageDocumentFetcher,
        ):
            fetcher = fetcher_class(
                browser_context_seed_getter=lambda: {},
                seed_urls_getter=lambda: [],
                runtime_context=runtime,
                browser_options=BrowserDocumentFetcherOptions(runtime_config=config),
            )
            assert fetcher._ensure_context(url) is context
            name = (
                "/figure.png"
                if fetcher_class is _SharedBrowserImageDocumentFetcher
                else "/supplement.zip"
            )
            result = fetcher(
                asset_root + name,
                {"kind": "figure" if name.endswith("png") else "supplementary"},
            )
            assert result is not None
            assert result["body"] == assets[name][1]
            fetcher.close()
            assert context.pages == initial_pages
            probe = context.new_page()
            probe.goto(url)
            assert (
                probe.evaluate("localStorage.getItem('profile-test')") == "persistent"
            )
            probe.close()
    # Reopen the native directory to restore cookies and local storage.
    assert not (profile.profile_path(config) / "storage-state.json").exists()
    with RuntimeContext(env={}) as runtime:
        _, context = open_browser_context(
            replace(
                config,
            ),
            runtime_context=runtime,
        )
        context.route(
            "https://www.pnas.org/**",
            lambda route: route.fulfill(body="<title>Offline</title>"),
        )
        page = context.new_page()
        page.goto(url)
        assert page.evaluate("localStorage.getItem('profile-test')") == "persistent"
        assert any(
            cookie["name"] == "profile-test" and cookie["value"] == "persistent"
            for cookie in context.cookies()
        )
        page.close()
    assert profile.trusted_profile_digest(profile.profile_path(config), "pnas")


@pytest.mark.skipif(os.name == "nt", reason="POSIX Chromium singleton socket")
def test_external_native_socket_is_reported_without_removing_it(config, monkeypatch):
    import socket

    monkeypatch.setattr(profile, "ScraplingManager", NativeProfileDouble)
    path = profile.profile_path(config)
    path.mkdir(parents=True)
    native_lock = path / "SingletonSocket"
    import tempfile

    with (
        tempfile.TemporaryDirectory(prefix="pf-socket-") as short_directory,
        socket.socket(socket.AF_UNIX) as owner,
    ):
        actual_socket = Path(short_directory) / "socket"
        owner.bind(str(actual_socket))
        native_lock.symlink_to(actual_socket)
        owner.listen()
        with pytest.raises(BrowserRuntimeFailure) as error:
            open_browser_context(config)
        assert error.value.kind == "browser_profile_external_occupancy"
        assert native_lock.exists()
    manager, _ = open_browser_context(config)
    manager.close()
    assert native_lock.is_symlink()


@pytest.mark.browser
def test_auth_reopens_same_native_profile(native_config, monkeypatch):
    if (
        sys.platform == "linux"
        and not os.environ.get("DISPLAY")
        and not os.environ.get("WAYLAND_DISPLAY")
    ):
        pytest.skip("headed auth requires a local display")
    from paper_fetch import auth
    from paper_fetch.config import (
        BROWSER_BINARY_PATH_ENV_VAR,
        BROWSER_PROFILE_DIR_ENV_VAR,
    )

    original = profile.ScraplingManager.new_context
    launches = []

    def routed_context(self):
        context = original(self)
        launches.append((str(self.native_profile), self.config.headless))
        context.route(
            "https://www.pnas.org/**",
            lambda route: route.fulfill(
                body="<title>Publisher Article</title><article>Legitimate offline article</article>",
                content_type="text/html",
            ),
        )
        return context

    monkeypatch.setattr(profile.ScraplingManager, "new_context", routed_context)
    monkeypatch.setattr(auth, "ensure_runtime_ready", lambda runtime: None)
    result = auth.authenticate_provider_profile(
        provider="pnas",
        confirm=lambda prompt: None,
        env={
            BROWSER_BINARY_PATH_ENV_VAR: native_config.binary_path,
            BROWSER_PROFILE_DIR_ENV_VAR: str(
                profile.profile_path(native_config).parent
            ),
        },
    )
    assert result.verified
    assert not (result.profile_dir / "storage-state.json").exists()
    assert launches == [
        (str(profile.profile_path(native_config)), False),
        (str(profile.profile_path(native_config)), True),
    ]
    metadata = json.loads(
        (profile.profile_path(native_config) / profile.METADATA_FILENAME).read_text()
    )
    assert metadata["auth"]["native_profile_verified"] is True
