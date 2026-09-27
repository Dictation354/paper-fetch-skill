"""Real Camoufox contracts for Wiley's serial image navigation."""

import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from paper_fetch.extraction.html.assets import (
    AssetDownloadOptions,
    FIGURE_KIND,
    download_assets,
)
from paper_fetch.http import RequestCancelledError
from paper_fetch.providers._wiley_page_assets import WileyPageAssetFetcher
from paper_fetch.runtime import RuntimeContext
from tests._environment import PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR
from tests.support.wiley_page_assets import figure, formula, png_bytes

ROOT = "https://example.test"
ARTICLE = ROOT + "/article"


@pytest.fixture
def browser(monkeypatch):
    executable = os.environ.get(PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR)
    if not executable or not Path(executable).is_file():
        pytest.skip("requires existing local Camoufox executable")
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
    with camoufox.Camoufox(
        headless=True, executable_path=executable, exclude_addons=list(DefaultAddons)
    ) as instance:
        yield instance


def setup_fetcher(browser, monkeypatch, assets, *, mode="success", runtime=None):
    context = browser.new_context()
    pages, navigations = [], []
    seen = {}
    bodies = {
        "/math.png": png_bytes(7, 3),
        "/full-1.png": png_bytes(640, 480),
        "/full-2.png": png_bytes(700, 500),
        "/preview-1.png": png_bytes(),
        "/preview-2.png": png_bytes(),
    }

    def route(route):
        path = route.request.url.removeprefix(ROOT)
        if route.request.is_navigation_request():
            navigations.append(route.request.url)
        seen[path] = seen.get(path, 0) + 1
        if path == "/full-1.png" and (
            mode in {"persistent", "forbidden", "cancel"}
            or (mode == "recover" and seen[path] == 1)
        ):
            challenge = mode != "forbidden"
            html = "<title>Just a moment...</title>" if challenge else "Forbidden"
            if mode == "recover":
                # The publisher's own verification flow re-navigates naturally.
                html += "<script>setTimeout(() => {document.cookie='seed=updated;path=/';location.href='/full-1.png'}, 150)</script>"
            route.fulfill(
                status=403,
                content_type="text/html",
                body=html,
                headers={"cf-mitigated": "challenge"} if challenge else {},
            )
        else:
            route.fulfill(content_type="image/png", body=bodies.get(path, b""))

    context.route(ROOT + "/**", route)
    factory = Mock(return_value=(None, None, context))
    monkeypatch.setattr(
        "paper_fetch.providers.browser_workflow.fetchers.context._new_browser_context",
        factory,
    )
    context.on("page", lambda page: pages.append(page))
    fetcher = WileyPageAssetFetcher(
        assets=assets,
        browser_context_seed_getter=lambda: {
            "browser_cookies": [
                {
                    "name": "seed",
                    "value": "original",
                    "domain": "example.test",
                    "path": "/",
                }
            ]
        },
        seed_urls_getter=lambda: [ARTICLE],
        runtime_context=runtime,
    )
    return fetcher, context, pages, navigations, bodies, factory


def download(fetcher, assets, tmp_path):
    transport = Mock()
    result = download_assets(
        FIGURE_KIND,
        transport,
        article_id="10.1111/test",
        assets=assets,
        output_dir=tmp_path,
        user_agent="test",
        asset_profile="body",
        options=AssetDownloadOptions(
            image_document_fetcher=fetcher, fetch_policy="browser_only"
        ),
    )
    transport.request.assert_not_called()
    return result


@pytest.mark.browser
def test_challenge_recovers_serial_assets_in_one_owned_session(
    browser, monkeypatch, tmp_path
):
    assets = [formula(ROOT + "/math.png"), figure(ROOT, 1), figure(ROOT, 2)]
    fetcher, context, pages, navigations, bodies, factory = setup_fetcher(
        browser, monkeypatch, assets, mode="recover"
    )
    try:
        result = download(fetcher, assets, tmp_path)
        assert not result["asset_failures"], result
        assert len(result["assets"]) == 3
        for asset in result["assets"]:
            assert (
                Path(asset["path"]).read_bytes()
                == bodies[asset["download_url"].removeprefix(ROOT)]
            )
        recovered = result["assets"][1]
        assert [item["reason"] for item in recovered["recovery_attempts"]] == [
            "cloudflare_challenge",
            "recovered",
        ]
        assert fetcher.failure_for(assets[1]["url"]) is None
        factory.assert_called_once()
        assert len(pages) == 1
        assert fetcher.navigation_count == 3
        assert navigations == [
            assets[0]["url"],
            assets[1]["url"],
            assets[1]["url"],
            assets[2]["url"],
        ]
        assert (
            next(c for c in context.cookies() if c["name"] == "seed")["value"]
            == "updated"
        )
        assert not fetcher._responses and not fetcher._requests
    finally:
        page = pages[0]
        remove = Mock(wraps=page.remove_listener)
        monkeypatch.setattr(page, "remove_listener", remove)
        fetcher.close()
        assert {call.args[0] for call in remove.call_args_list} == {
            "request",
            "requestfinished",
        }
    assert page.is_closed() and not context.pages and browser.is_connected()


@pytest.mark.browser
def test_plain_403_navigates_preview_with_remaining_budget(
    browser, monkeypatch, tmp_path
):
    asset = figure(ROOT, 1)
    fetcher, _, pages, navigations, bodies, _ = setup_fetcher(
        browser, monkeypatch, [asset], mode="forbidden"
    )
    try:
        result = download(fetcher, [asset], tmp_path)
        assert not result["asset_failures"], result
        saved = result["assets"][0]
        assert saved["download_tier"] == "preview"
        assert Path(saved["path"]).read_bytes() == bodies["/preview-1.png"]
        assert navigations == [asset["url"], asset["preview_url"]]
        assert len(pages) == 1 and fetcher.navigation_count == 2
        assert fetcher.failure_for(asset["url"])["status"] == 403
    finally:
        fetcher.close()


@pytest.mark.browser
def test_persistent_challenge_times_out_without_reload_or_new_context(
    browser, monkeypatch
):
    asset, other = figure(ROOT, 1), formula(ROOT + "/math.png")
    fetcher, _, pages, navigations, _, factory = setup_fetcher(
        browser, monkeypatch, [asset, other], mode="persistent"
    )
    assert fetcher._open(asset["url"])
    fetcher._timeout = 3
    try:
        assert fetcher(asset["url"], asset) is None
        assert fetcher(asset["preview_url"], asset) is None
        assert fetcher.failure_for(asset["url"])["reason"] == "cloudflare_challenge"
        assert fetcher(asset["url"], asset) is None
        fetcher._timeout = 30
        assert fetcher(other["url"], other)
        assert len(pages) == 1 and fetcher.navigation_count == 2
        assert navigations == [asset["url"], other["url"]]
        factory.assert_called_once()
    finally:
        fetcher.close()


@pytest.mark.browser
def test_successful_image_survives_navigation_wait_exception(browser, monkeypatch):
    asset = formula(ROOT + "/math.png")
    fetcher, context, _, navigations, bodies, _ = setup_fetcher(
        browser, monkeypatch, [asset]
    )
    try:
        assert fetcher._open(asset["url"])
        page = fetcher._page
        goto = page.goto

        def navigation(*args, **kwargs):
            goto(*args, **kwargs)
            page.wait_for_function(
                "document.images.length && document.images[0].complete && document.images[0].naturalWidth > 0"
            )
            raise TimeoutError("navigation wait failed after image completed")

        monkeypatch.setattr(page, "goto", navigation)
        response = fetcher(asset["url"], asset)
        assert response["body"] == bodies["/math.png"]
        assert fetcher.failure_for(asset["url"]) is None
        assert navigations == [asset["url"]]
    finally:
        fetcher.close()
    assert not context.pages


@pytest.mark.browser
def test_cancellation_during_challenge_closes_owned_page_and_releases_budget(
    browser, monkeypatch
):
    import time

    start = [None]
    runtime = RuntimeContext(
        env={},
        cancel_check=lambda: start[0] is not None and time.monotonic() - start[0] > 0.4,
    )
    asset = figure(ROOT, 1)
    fetcher, context, pages, navigations, _, _ = setup_fetcher(
        browser, monkeypatch, [asset], mode="cancel", runtime=runtime
    )
    try:
        assert fetcher._open(asset["url"])
        start[0] = time.monotonic()
        with pytest.raises(RequestCancelledError):
            fetcher(asset["url"], asset)
        assert fetcher._closed and pages[0].is_closed()
        assert not context.pages and not fetcher._responses and not fetcher._requests
        assert runtime.asset_budget.snapshot()["reserved_bytes"] == 0
        assert navigations == [asset["url"]] and browser.is_connected()
    finally:
        fetcher.close()
        runtime.close()


@pytest.mark.browser
def test_local_server_challenge_redirect_preserves_original_bytes(browser, monkeypatch):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading

    requests = []
    body = png_bytes(640, 480)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            if self.path == "/image.png" and requests.count(self.path) == 1:
                payload = b"<title>Just a moment...</title><script>setTimeout(()=>location.href='/image.png',150)</script>"
                self.send_response(403)
                self.send_header("cf-mitigated", "challenge")
                self.send_header("Content-Type", "text/html")
            elif self.path == "/image.png":
                payload = b""
                self.send_response(302)
                self.send_header("Location", "/actual.png")
            else:
                payload = body
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    context = browser.new_context()
    monkeypatch.setattr(
        "paper_fetch.providers.browser_workflow.fetchers.context._new_browser_context",
        lambda **kw: (None, None, context),
    )
    url = f"http://127.0.0.1:{server.server_port}/image.png"
    asset = formula(url)
    fetcher = WileyPageAssetFetcher(
        assets=[asset],
        browser_context_seed_getter=lambda: {},
        seed_urls_getter=lambda: [],
    )
    try:
        response = fetcher(url, asset)
        assert response and response["body"] == body
        assert response["url"].endswith("/actual.png")
        assert fetcher.failure_for(url) is None
        assert response["_paper_fetch_recovery_attempts"][-1]["reason"] == "recovered"
        assert requests.count("/image.png") == 2
        assert requests.count("/actual.png") == 1
        assert fetcher.navigation_count == 1
    finally:
        fetcher.close()
        server.shutdown()
        server.server_close()
        thread.join()
    assert not context.pages and browser.is_connected()
