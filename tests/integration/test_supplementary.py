"""CLI/MCP supplementary outputs with real HTTP, downloads and index files."""

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

import pytest

from paper_fetch import cli, service
from paper_fetch.mcp.fetch_tool import fetch_paper_payload
from paper_fetch.mcp.batch_fetch import batch_fetch_tool_async
from paper_fetch.providers.springer import SpringerClient
from paper_fetch.resolve.query import ResolvedQuery
from paper_fetch.runtime import RuntimeContext
from paper_fetch.workflow import supplementary
from tests.support.supplementary import DOI, html_page


@pytest.fixture
def supplementary_server(monkeypatch):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            if self.path == "/support.csv":
                body, content_type = b"a,b\n1,2\n", "text/csv"
            elif self.path == "/empty":
                body, content_type = html_page(links="").encode(), "text/html"
            else:
                body, content_type = html_page().encode(), "text/html"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    from paper_fetch.http.url_policy import SafeRemoteUrlPolicy, ValidatedRemoteUrl

    original_validate = SafeRemoteUrlPolicy.validate

    def validate_local(self, url, **kwargs):
        if url.startswith(base + "/"):
            return ValidatedRemoteUrl(
                url=url,
                scheme="http",
                host="127.0.0.1",
                port=server.server_port,
                addresses=("127.0.0.1",),
            )
        return original_validate(self, url, **kwargs)

    monkeypatch.setattr(SafeRemoteUrlPolicy, "validate", validate_local)
    metadata = {
        "doi": DOI,
        "title": "Attachment contract",
        "landing_page_url": base + "/article",
    }
    monkeypatch.setattr(
        service,
        "resolve_paper",
        lambda query, **kwargs: ResolvedQuery(
            query=query, query_kind="doi", doi=DOI, provider_hint="springer"
        ),
    )
    monkeypatch.setattr(
        supplementary,
        "fetch_metadata_for_resolved_query",
        lambda *a, **k: (dict(metadata), "springer", []),
    )
    monkeypatch.setattr(
        supplementary,
        "_ranked_fulltext_provider_candidates",
        lambda **kwargs: [("springer", "doi", "strong")],
    )
    monkeypatch.setattr(
        RuntimeContext,
        "get_clients",
        lambda self: {"springer": SpringerClient(self.transport, self.env)},
    )
    monkeypatch.setattr(
        SpringerClient,
        "fetch_raw_fulltext",
        lambda *a, **k: pytest.fail("body request"),
    )
    try:
        yield metadata, calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_cli_single_downloads_only_material_and_writes_index(
    supplementary_server, tmp_path, capsys
):
    _, calls = supplementary_server
    assert (
        cli.main(
            [
                "fetch",
                "--query",
                DOI,
                "--target",
                "supplementary",
                "--output-dir",
                str(tmp_path),
                "--format",
                "json",
            ]
        )
        == 0
    )
    outputs = list(tmp_path.glob("*_supplementary.json"))
    assert len(outputs) == 1
    payload = json.loads(outputs[0].read_text())
    assert payload["target"] == "supplementary"
    assert payload["article"] is None and not payload["has_fulltext"]
    materials = payload["supplementary"]["assets"]
    assert len(materials) == 1
    assert Path(materials[0]["path"]).read_bytes() == b"a,b\n1,2\n"
    assert sorted(calls) == ["/article", "/support.csv"]
    indexes = list(tmp_path.glob("*_supplementary.md"))
    assert len(indexes) == 1 and "Purchase" not in indexes[0].read_text()


def test_cli_empty_single_and_batch_return_nonzero_with_empty_lists(
    supplementary_server, tmp_path, capsys
):
    metadata, calls = supplementary_server
    metadata["landing_page_url"] = metadata["landing_page_url"].replace(
        "/article", "/empty"
    )
    single = tmp_path / "single"
    assert (
        cli.main(
            [
                "fetch",
                "--query",
                DOI,
                "--target",
                "supplementary",
                "--output-dir",
                str(single),
                "--format",
                "json",
            ]
        )
        != 0
    )
    payload = json.loads(next(single.glob("*_supplementary.json")).read_text())
    assert payload["supplementary"]["assets"] == []
    assert payload["supplementary"]["discovery_complete"]
    queries = tmp_path / "queries.txt"
    queries.write_text(DOI + "\n")
    batch = tmp_path / "batch"
    assert (
        cli.main(
            [
                "fetch",
                "--query-file",
                str(queries),
                "--target",
                "supplementary",
                "--output-dir",
                str(batch),
                "--format",
                "json",
            ]
        )
        != 0
    )
    record = json.loads((batch / "batch-results.jsonl").read_text().splitlines()[0])
    assert record["acceptance"]["fetch"]["code"] == "no_result"


def test_mcp_single_and_batch_keep_structured_materials(supplementary_server, tmp_path):
    _, calls = supplementary_server
    payload = fetch_paper_payload(
        query=DOI,
        target="supplementary",
        download_dir=tmp_path / "single",
        save_markdown=True,
        env={},
    )
    assert payload["status"] == "ok"
    assert payload["acceptance"]["overall"] == "complete"
    assert payload["acceptance"]["content_requested"] is False
    assert len(payload["supplementary"]["assets"]) == 1
    assert len(list((tmp_path / "single").glob("*_supplementary.md"))) == 1
    result = asyncio.run(
        batch_fetch_tool_async(
            queries=[DOI],
            target="supplementary",
            download_dir=tmp_path / "batch",
            env={},
        )
    )
    payload = result.structured_content
    assert not result.is_error
    assert payload["results"][0]["target"] == "supplementary"
    assert payload["results"][0]["acceptance"]["overall"] == "complete"
    assert len(payload["results"][0]["supplementary"]["assets"]) == 1


@pytest.mark.parametrize("options", [{"no_download": True}, {"artifact_mode": "none"}])
def test_mcp_discovery_without_archival(supplementary_server, tmp_path, options):
    _, calls = supplementary_server
    result = fetch_paper_payload(
        query=DOI, target="supplementary", download_dir=tmp_path, env={}, **options
    )
    assert result["status"] == "ok"
    assert result["acceptance"]["overall"] == "degraded"
    assert result["supplementary"]["assets"][0]["archive_state"] == "not_archived"
    assert calls == ["/article"]
    assert not list(tmp_path.rglob("*.csv"))


@pytest.mark.browser
def test_browser_index_accepts_paywalled_abstract_without_body(monkeypatch, tmp_path):
    from paper_fetch.providers import _playwright_browser as browser_fetcher
    from paper_fetch.providers.browser_runtime import (
        BrowserHtmlFetchOptions,
        BrowserHtmlReadiness,
        BrowserRuntimeConfig,
    )
    from tests.support.offline_camoufox import prepared_browser

    with prepared_browser(monkeypatch) as browser:
        context = browser.new_context()
        page = context.new_page()
        register_route = page.route

        class OfflineRoute:
            def __init__(self, route):
                self.route = route

            def __getattr__(self, name):
                return getattr(self.route, name)

            def continue_(self):
                self.route.fallback()

        monkeypatch.setattr(
            page,
            "route",
            lambda pattern, handler: register_route(
                pattern, lambda route: handler(OfflineRoute(route))
            ),
        )
        monkeypatch.setattr(context, "new_page", lambda: page)
        url = "https://www.science.org/doi/abs/" + DOI
        abstract_url = url

        def reply(route):
            route.fulfill(body=html_page(), content_type="text/html")

        context.route("**/*", reply)
        monkeypatch.setattr(
            browser_fetcher, "open_browser_context", lambda *_a, **_k: (None, context)
        )
        result = browser_fetcher.fetch_html_with_playwright(
            [url],
            publisher="science",
            config=BrowserRuntimeConfig(
                provider="science",
                doi=DOI,
                artifact_dir=tmp_path,
                headless=True,
                user_agent=None,
                persist_storage_state=False,
            ),
            readiness=BrowserHtmlReadiness(wait_for_article_body=False),
            options=BrowserHtmlFetchOptions(supplementary_index=True),
        )
        assert result.final_url == abstract_url
        assert "support.csv" in result.html
        assert result.staged_storage_state is None
