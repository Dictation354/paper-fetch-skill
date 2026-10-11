"""Real Camoufox page-click contracts against locally fulfilled responses."""

from __future__ import annotations

import hashlib
from html import escape
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from paper_fetch.asset_budget import AssetBudget
from paper_fetch.extraction.html.assets import (
    SUPPLEMENTARY_KIND,
    AssetDownloadOptions,
    download_assets,
)
from paper_fetch.http import RequestCancelledError
from paper_fetch.providers.browser_workflow.asset_download import (
    _CLICK_SUPPLEMENT_PROVIDERS,
)
from paper_fetch.providers.browser_workflow.fetchers import (
    BrowserDocumentFetcherOptions,
)
from paper_fetch.providers.browser_workflow.fetchers.file import (
    _SharedBrowserFileDocumentFetcher,
)
from paper_fetch.runtime import RuntimeContext
from tests._environment import PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR
from tests.support._paper_fetch_support import build_pdf_bytes

pytestmark = pytest.mark.browser


@pytest.fixture
def local_responses():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading

    servers = []

    def start(responder):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                status, headers, body = responder(self.path)
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        return f"http://127.0.0.1:{server.server_port}"

    yield start
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture(autouse=True)
def local_click_deadline(monkeypatch):
    from paper_fetch.providers.browser_workflow.fetchers import click

    # Parallel Camoufox workers can take several seconds to render a local
    # article. Keep the short deadline specific to the timeout scenario.
    monkeypatch.setattr(click, "_CLICK_TIMEOUT_SECONDS", 20)


@pytest.fixture(scope="module")
def click_browser():
    executable = os.environ.get(PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR)
    if not executable or not Path(executable).is_file():
        pytest.skip("requires the existing local Camoufox executable")
    camoufox = pytest.importorskip("camoufox.sync_api")
    from camoufox import DefaultAddons, pkgman, utils

    version_file = next(
        parent / "version.json"
        for parent in Path(executable).parents
        if (parent / "version.json").is_file()
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            utils,
            "installed_verstr",
            lambda: json.loads(version_file.read_text())["version"],
        )
        patch.setattr(pkgman, "camoufox_path", lambda: version_file.parent)
        with camoufox.Camoufox(
            headless=True,
            executable_path=executable,
            exclude_addons=list(DefaultAddons),
        ) as browser:
            yield browser


def click_fetcher(
    context, runtime, *, provider="science", article="https://example.test/article"
):
    fetcher = _SharedBrowserFileDocumentFetcher(
        browser_context_seed_getter=lambda: {"browser_final_url": article},
        seed_urls_getter=lambda: [article],
        runtime_context=runtime,
        browser_options=BrowserDocumentFetcherOptions(
            runtime_config=SimpleNamespace(provider=provider),
            file_fetch_mode="page_click",
        ),
    )
    fetcher._context = context
    fetcher._page = context.new_page()
    return fetcher


def article_html(links):
    return (
        '<section class="article-section__content"><h2>Results</h2><p>'
        + "Article body. " * 120
        + '</p><p>Second paragraph.</p></section><section class="article-section__supporting">'
        + links
        + "</section>"
    )


@pytest.mark.parametrize("provider", sorted(_CLICK_SUPPLEMENT_PROVIDERS))
def test_each_provider_downloads_existing_link_serially(
    click_browser, provider, tmp_path
):
    body = build_pdf_bytes(["Supplementary Material", "Local download contract"])
    requests = []
    with RuntimeContext(env={}) as runtime:
        context = click_browser.new_context()
        fetcher = click_fetcher(context, runtime, provider=provider)

        def route(route):
            requests.append(route.request.url)
            if route.request.url.endswith("/article"):
                route.fulfill(
                    body=article_html(
                        '<a href="/first.pdf">SI 1</a><a href="/second.pdf">SI 2</a>'
                    ),
                    content_type="text/html",
                )
            else:
                route.fulfill(
                    body=body,
                    content_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="si.pdf"'},
                )

        context.route("https://example.test/**", route)
        unrelated = context.new_page()
        unrelated.goto("https://example.test/article")
        assets = [
            {
                "kind": "supplementary",
                "url": "https://example.test/" + name,
                "source_href": "/" + name,
            }
            for name in ("first.pdf", "second.pdf")
        ]
        transport = mock.Mock()
        result = download_assets(
            SUPPLEMENTARY_KIND,
            transport,
            article_id="10.5555/click",
            user_agent="test-agent",
            output_dir=tmp_path,
            assets=assets,
            asset_profile="all",
            options=AssetDownloadOptions(
                file_document_fetcher=fetcher,
                runtime_context=runtime,
                fetch_policy="browser_only",
                asset_download_concurrency=1,
            ),
        )
        assert not result["asset_failures"], result
        assert len(result["assets"]) == 2
        for asset in result["assets"]:
            saved = Path(asset["path"]).read_bytes()
            assert len(saved) == len(body)
            assert hashlib.sha256(saved).digest() == hashlib.sha256(body).digest()
            assert asset["asset_route"]["capture_event"] == "download"
            assert asset["content_type"] == "application/pdf"
        assert len(context.pages) == 2
        assert unrelated.url.endswith("/article")
        assert fetcher._page.url.endswith("/article")
        assert requests.count("https://example.test/first.pdf") == 1
        assert requests.count("https://example.test/second.pdf") == 1
        transport.request.assert_not_called()
        context.close()


@pytest.mark.parametrize(
    "scenario",
    [
        "redirect",
        "inline",
        "popup",
        "popup_redirect",
        "popup_inline",
        "popup_challenge",
        "popup_noopener",
        "download_without_finished_event",
        "delayed_link",
        "pending_script",
        "redirecting_page",
        "challenge",
        "empty",
        "oversize",
        "timeout",
        "cancel",
        "unrelated",
    ],
)
def test_click_response_and_failure_boundaries(
    click_browser, scenario, tmp_path, monkeypatch, local_responses
):
    from paper_fetch.providers.browser_workflow.fetchers import click

    body = build_pdf_bytes(["Supplementary Material", "Inline response contract"])
    base = "https://example.test"
    if scenario in {"redirect", "popup_redirect"}:

        def server_response(path):
            if path == "/article":
                return (
                    200,
                    {"Content-Type": "text/html"},
                    article_html(
                        '<a href="/si.pdf"'
                        + (' target="_blank"' if scenario == "popup_redirect" else "")
                        + ">Supplement</a>"
                    ).encode(),
                )
            if path == "/si.pdf":
                return 302, {"Location": "/final.pdf"}, b""
            return (
                200,
                {
                    "Content-Type": "application/pdf",
                    "Content-Disposition": 'attachment; filename="si.pdf"',
                },
                body,
            )

        base = local_responses(server_response)
    target = base + "/si.pdf"
    with RuntimeContext(env={}) as runtime:
        if scenario == "oversize":
            runtime.asset_budget = AssetBudget(max_bytes_per_asset=64)
        context = click_browser.new_context()
        fetcher = click_fetcher(context, runtime, article=base + "/article")
        if scenario == "download_without_finished_event":
            # Firefox's download manager can complete a file without a terminal
            # event for the intercepted page navigation. Keep real file bytes
            # and download events, suppressing only those network listeners.
            original_on = context.on

            def on(event, callback):
                if event not in {"requestfinished", "requestfailed"}:
                    original_on(event, callback)

            monkeypatch.setattr(context, "on", on)
        if scenario == "timeout":
            monkeypatch.setattr(click, "_CLICK_TIMEOUT_SECONDS", 0.8)

        def route(route):
            url = route.request.url
            if url.endswith("/article"):
                link = (
                    '<a href="/si.pdf"'
                    + (' target="_blank"' if scenario.startswith("popup") else "")
                    + (' rel="noopener"' if scenario == "popup_noopener" else "")
                    + ">Supplement</a>"
                )
                if scenario in {"timeout", "cancel"}:
                    link = '<a href="/si.pdf" onclick="event.preventDefault()">Supplement</a>'
                if scenario == "delayed_link":
                    link = """<script>setTimeout(() => {
                        const link = document.createElement('a');
                        link.href = '/si.pdf'; link.textContent = 'Supplement';
                        document.body.appendChild(link);
                    }, 250);</script>"""
                if scenario == "pending_script":
                    link += '<script src="/pending.js"></script>'
                if scenario == "redirecting_page":
                    link = "<script>location.replace('/ready');</script>"
                if scenario == "unrelated":
                    link = '<a href="/si.pdf" onclick="event.preventDefault(); fetch(\'/other.pdf\')">Supplement</a>'
                    monkeypatch.setattr(click, "_CLICK_TIMEOUT_SECONDS", 0.8)
                route.fulfill(body=article_html(link), content_type="text/html")
            elif url.endswith("/ready"):
                route.fulfill(
                    body=article_html('<a href="/si.pdf">Supplement</a>'),
                    content_type="text/html",
                )
            elif url.endswith("/pending.js"):
                # Leave a parser-blocking script pending after the target link.
                # Its load must not prevent a click on the existing attachment.
                return
            elif scenario == "redirect" and url == target:
                route.fulfill(status=302, headers={"Location": "/final.pdf"})
            elif scenario in {"challenge", "popup_challenge"}:
                route.fulfill(
                    status=403,
                    body="<title>Just a moment...</title>",
                    content_type="text/html",
                )
            else:
                route.fulfill(
                    body=b"" if scenario == "empty" else body,
                    content_type="application/pdf",
                    headers={}
                    if scenario in {"inline", "popup_inline"}
                    else {"Content-Disposition": 'attachment; filename="si.pdf"'},
                )

        context.route("https://example.test/**", route)
        if scenario == "cancel":
            original = fetcher._page.wait_for_timeout

            def cancel(milliseconds):
                runtime.fence_commits()
                original(milliseconds)

            monkeypatch.setattr(fetcher._page, "wait_for_timeout", cancel)
        asset = {"kind": "supplementary", "url": target}
        if scenario == "cancel":
            with pytest.raises(RequestCancelledError):
                fetcher(target, asset)
        else:
            result = download_assets(
                SUPPLEMENTARY_KIND,
                mock.Mock(),
                article_id="10.5555/click",
                user_agent="test-agent",
                output_dir=tmp_path,
                assets=[asset],
                asset_profile="all",
                options=AssetDownloadOptions(
                    file_document_fetcher=fetcher,
                    runtime_context=runtime,
                    fetch_policy="browser_only",
                    asset_budget=runtime.asset_budget,
                    asset_download_concurrency=1,
                ),
            )
            if scenario in {
                "redirect",
                "inline",
                "popup",
                "popup_redirect",
                "popup_inline",
                "popup_noopener",
                "download_without_finished_event",
                "delayed_link",
                "pending_script",
                "redirecting_page",
            }:
                assert not result["asset_failures"], result
                saved = result["assets"][0]
                assert Path(saved["path"]).read_bytes() == body
                if scenario == "popup_inline":
                    assert saved["asset_route"]["capture_event"] in {
                        "inline_response",
                        "download",
                    }
                else:
                    assert saved["asset_route"]["capture_event"] == (
                        "inline_response" if scenario == "inline" else "download"
                    )
                if scenario in {"redirect", "popup_redirect"}:
                    assert saved["asset_route"]["final_url"].endswith("/final.pdf")
                if scenario == "redirecting_page":
                    assert saved["asset_route"]["click_page_url"].endswith("/ready")
            else:
                assert not result["assets"]
                assert result["asset_failures"]
                if scenario == "popup_challenge":
                    assert (
                        result["asset_failures"][0]["reason"] == "cloudflare_challenge"
                    )
                    assert result["asset_failures"][0]["status"] == 403
                assert not list(tmp_path.rglob("*.pdf"))
        assert len(context.pages) == 1
        # No listeners survive a call, including failure/cancellation paths.
        assert not context._impl_obj.listeners("response")
        assert not context._impl_obj.listeners("requestfinished")
        assert not context._impl_obj.listeners("requestfailed")
        context.close()


def test_iop_directory_click_and_mdpi_original_url_mapping(
    click_browser, local_responses
):
    body = b"PK\x03\x04directory-supplement"

    def response(path):
        if path == "/data":
            return (
                200,
                {"Content-Type": "text/html"},
                b'<a id="SM0001" href="/raw.zip">Supplement</a>',
            )
        if path == "/raw.zip":
            return 302, {"Location": "/cdn.zip"}, b""
        if path == "/cdn.zip":
            return (
                200,
                {
                    "Content-Type": "application/zip",
                    "Content-Disposition": 'attachment; filename="si.zip"',
                },
                body,
            )
        return 200, {"Content-Type": "text/html"}, article_html("").encode()

    base = local_responses(response)
    with RuntimeContext(env={}) as runtime:
        context = click_browser.new_context()
        fetcher = click_fetcher(
            context, runtime, provider="iop", article=base + "/article"
        )
        result = fetcher(
            base + "/cdn.zip",
            {
                "source_page_url": base + "/data",
                "source_href": "/raw.zip",
                "source_ref": "SM0001",
            },
        )
        assert result is not None, fetcher.failure_for(base + "/cdn.zip")
        assert result["body"] == body
        assert (
            result["_paper_fetch_asset_route_diagnostics"]["original_href"]
            == "/raw.zip"
        )
        assert fetcher._page.url == base + "/article"
        context.close()


@pytest.mark.parametrize("delayed", [False, True])
@pytest.mark.parametrize("tab_label", ["Multimedia", "Supplemental Items"])
@pytest.mark.parametrize("filename_label", [False, True])
def test_ieee_multimedia_tab_clicks_existing_filename_button(
    click_browser, delayed, tab_label, filename_label
):
    with RuntimeContext(env={}) as runtime:
        context = click_browser.new_context()
        fetcher = click_fetcher(context, runtime, provider="ieee")
        body = b"PK\x03\x04ieee-attachment"
        media = """<button role="tab" onclick="document.getElementById('multimedia').hidden=false">Multimedia</button>
            <div id="multimedia" hidden><button onclick="window.location='/si.zip'">si.zip</button></div>"""
        media = media.replace(">Multimedia<", ">" + tab_label + "<")
        if filename_label:
            media = (
                media.replace("id='multimedia'", "id='media'")
                .replace('id="multimedia"', 'id="media"')
                .replace("getElementById('multimedia')", "getElementById('media')")
            )
            media = media.replace(
                "<button onclick=\"window.location='/si.zip'\">si.zip</button>",
                "<span onclick=\"window.location='/si.zip'\">si.zip</span>",
            )
            media += "<xpl-document-media hidden><button>si.zip</button></xpl-document-media>"
        if delayed:
            media = (
                '<div id="media-holder"></div><script>setTimeout(() => {'
                "document.getElementById('media-holder').innerHTML = "
                + json.dumps(media)
                + ";}, 250);</script>"
            )
        html = article_html(media)

        def route(route):
            if route.request.url.endswith("/article"):
                route.fulfill(body=html, content_type="text/html")
            else:
                route.fulfill(
                    body=body,
                    content_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="si.zip"'},
                )

        context.route("https://example.test/**", route)
        result = fetcher("https://example.test/si.zip", {"filename_hint": "si.zip"})
        assert result is not None, fetcher.failure_for("https://example.test/si.zip")
        assert result["body"] == body
        assert (
            result["_paper_fetch_asset_route_diagnostics"]["attachment_label"]
            == "si.zip"
        )
        assert not context._impl_obj.listeners("response")
        context.close()


def test_ieee_doi_bound_file_icon_clicks_existing_tracking_link(click_browser):
    with RuntimeContext(env={}) as runtime:
        context = click_browser.new_context()
        fetcher = click_fetcher(context, runtime, provider="ieee")
        doi = "10.1109/EXAMPLE/mm1"
        body = b"%PDF-1.7\nieee-attachment"
        html = article_html(
            '<div id="media"><div class="media-item">'
            f'<a class="multimedia-doi">{doi}</a>'
            '<a class="stats-Multimedia_pdf_1" '
            'href="/si.pdf?tag=1" onclick="event.preventDefault(); '
            "fetch('/si.pdf?tag=2'); setTimeout(() => {"
            "window.location='/si.pdf?tag=1';}, 200)\">"
            "<span>PDF</span></a></div>"
            '<div class="media-item"><a class="multimedia-doi">'
            '10.1109/other/mm2</a><a class="stats-Multimedia_pdf_1" '
            'href="/other.pdf">Other PDF</a></div></div>'
        )

        def route(route):
            if route.request.url.endswith("/article"):
                route.fulfill(body=html, content_type="text/html")
            elif route.request.url.endswith("?tag=2"):
                route.fulfill(
                    body=b"%PDF-1.7\nunrelated", content_type="application/pdf"
                )
            else:
                assert route.request.url == "https://example.test/si.pdf?tag=1"
                route.fulfill(
                    body=body,
                    content_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="si.pdf"'},
                )

        context.route("https://example.test/**", route)
        result = fetcher(
            "https://example.test/si.pdf",
            {"filename_hint": "si.pdf", "doi": doi.lower()},
        )
        assert result is not None, fetcher.failure_for("https://example.test/si.pdf")
        assert result["body"] == body
        assert result["url"] == "https://example.test/si.pdf?tag=1"
        context.close()


@pytest.mark.parametrize("duplicate", [False, True])
def test_mdpi_existing_modal_link_maps_to_normalized_asset(
    click_browser, local_responses, duplicate
):
    body = b"PK\x03\x04mdpi-attachment"
    links = '<a href="/raw.zip">Supplementary ZIP</a>'
    if duplicate:
        links = '<div style="display:none">' + links + "</div>" + links
    canonical = (
        '<a href="/cdn.zip" target="_blank" rel="noopener">Normalized DOI link</a>'
        if duplicate
        else ""
    )
    html = article_html(
        """<button data-reveal-id="supplementaryModal" onclick="document.getElementById('supplementaryModal').hidden=false">Download Supplementary Material</button>
        """
        + canonical
        + """<div id="supplementaryModal" hidden>"""
        + links
        + "</div>"
    )

    def responder(path):
        if path == "/article":
            return 200, {"Content-Type": "text/html"}, html.encode()
        if path == "/raw.zip":
            return 302, {"Location": "/cdn.zip"}, b""
        return (
            200,
            {
                "Content-Type": "application/zip",
                "Content-Disposition": 'attachment; filename="si.zip"',
            },
            body,
        )

    base = local_responses(responder)
    with RuntimeContext(env={}) as runtime:
        context = click_browser.new_context()
        fetcher = click_fetcher(
            context, runtime, provider="mdpi", article=base + "/article"
        )
        result = fetcher(base + "/cdn.zip", {"source_href": "/raw.zip"})
        assert result is not None, fetcher.failure_for(base + "/cdn.zip")
        assert result["body"] == body
        assert result["_paper_fetch_asset_route_diagnostics"][
            "click_target_url"
        ] == base + ("/cdn.zip" if duplicate else "/raw.zip")
        assert fetcher._page.url == base + "/article"
        context.close()


@pytest.mark.parametrize("dropdown", [False, True, "redraw"])
def test_annualreviews_opens_existing_supplementary_tab(click_browser, dropdown):
    with RuntimeContext(env={}) as runtime:
        context = click_browser.new_context()
        fetcher = click_fetcher(context, runtime, provider="annualreviews")
        body = b"PK\x03\x04annualreviews-attachment"
        tab = """<a role="button" href="#supplementary_data" onclick="document.getElementById('supplementary_data').hidden=false">Supplemental Material</a>"""
        if dropdown:
            opening = "document.getElementById('menu').hidden=false"
            if dropdown == "redraw":
                opening = "document.getElementById('clone').innerHTML = " + json.dumps(
                    tab
                )
            tab = (
                '<li class="dropdown"><a href="#" data-toggle="dropdown" onclick="'
                + escape(opening, quote=True)
                + '">Info</a><ul id="menu" hidden><li>'
                + tab
                + '</li></ul></li><div id="clone"></div>'
            )
        html = article_html(
            tab
            + """<div id="supplementary_data" hidden><a href="/si.zip">Supplement</a></div>"""
        )

        def route(route):
            if route.request.url.endswith("/article"):
                route.fulfill(body=html, content_type="text/html")
            else:
                route.fulfill(
                    body=body,
                    content_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="si.zip"'},
                )

        context.route("https://example.test/**", route)
        result = fetcher("https://example.test/si.zip", {})
        assert result is not None, fetcher.failure_for("https://example.test/si.zip")
        assert result["body"] == body
        context.close()
