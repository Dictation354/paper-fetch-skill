"""CLI/MCP supplementary outputs with real HTTP, downloads and index files."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from paper_fetch import cli, service
from paper_fetch.providers.oxfordacademic import OxfordAcademicClient
from paper_fetch.providers.springer import SpringerClient
from paper_fetch.resolve.query import ResolvedQuery
from paper_fetch.runtime import RuntimeContext
from paper_fetch.workflow import supplementary
from tests.support.supplementary import DOI, html_page


@pytest.fixture
def supplementary_server(monkeypatch, request):
    calls = []
    provider = getattr(request, "param", "springer")
    client_class = (
        OxfordAcademicClient if provider == "oxfordacademic" else SpringerClient
    )
    doi = "10.1093/bioinformatics/btaa161" if provider == "oxfordacademic" else DOI
    links = (
        '<div class="dataSuppLink"><a href="/support.csv">Supplementary data</a></div>'
        if provider == "oxfordacademic"
        else '<section id="supplementary"><a href="/support.csv">Supplementary data</a></section>'
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            if self.path == "/support.csv":
                body, content_type = b"a,b\n1,2\n", "text/csv"
            elif self.path == "/empty":
                body, content_type = html_page(doi, links="").encode(), "text/html"
            else:
                body, content_type = html_page(doi, links=links).encode(), "text/html"
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
        "doi": doi,
        "title": "Attachment contract",
        "landing_page_url": base + "/article",
    }
    monkeypatch.setattr(
        service,
        "resolve_paper",
        lambda query, **kwargs: ResolvedQuery(
            query=query, query_kind="doi", doi=doi, provider_hint=provider
        ),
    )
    monkeypatch.setattr(cli, "resolve_paper", service.resolve_paper)
    monkeypatch.setattr(
        supplementary,
        "fetch_metadata_for_resolved_query",
        lambda *a, **k: (dict(metadata), provider, []),
    )
    monkeypatch.setattr(
        supplementary,
        "_ranked_fulltext_provider_candidates",
        lambda **kwargs: [(provider, "doi", "strong")],
    )
    monkeypatch.setattr(
        RuntimeContext,
        "get_clients",
        lambda self: {provider: client_class(self.transport, self.env)},
    )
    monkeypatch.setattr(
        client_class,
        "fetch_raw_fulltext",
        lambda *a, **k: pytest.fail("body request"),
    )
    try:
        yield metadata, calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize(
    "supplementary_server", ["springer", "oxfordacademic"], indirect=True
)
@pytest.mark.parametrize("preset", ["temporary_read", "cacheable_read", "archive"])
def test_cli_single_downloads_only_material_and_writes_index(
    supplementary_server, tmp_path, capsys, preset
):
    metadata, calls = supplementary_server
    assert (
        cli.main(
            [
                "fetch",
                "--query",
                metadata["doi"],
                "--target",
                "supplementary",
                "--preset",
                preset,
                "--output-dir",
                str(tmp_path),
                "--format",
                "json",
            ]
        )
        == 0
    )
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["target_satisfied"] and receipt["error"] is None
    assert receipt["acceptance"]["asset"] == "complete"
    outputs = list(tmp_path.glob("*_supplementary.json"))
    assert len(outputs) == 1
    payload = json.loads(outputs[0].read_text())
    assert payload["target"] == "supplementary"
    assert payload["source"] == payload["acquisition"]["provider"]
    assert payload["acquisition"]["route"] == "supplementary"
    assert payload["acquisition"]["transport"] == "http"
    assert payload["article"] is None and not payload["quality"]["has_fulltext"]
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
                "--preset",
                "archive",
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
                "--preset",
                "archive",
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


@pytest.mark.browser
def test_browser_index_accepts_paywalled_abstract_without_body(monkeypatch, tmp_path):
    from paper_fetch.providers.browser_runtime import (
        BrowserHtmlFetchOptions,
        BrowserHtmlReadiness,
        BrowserRuntimeConfig,
    )
    from paper_fetch.providers.browser_runtime import html_fetcher as browser_fetcher
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
        result = browser_fetcher.fetch_browser_html(
            [url],
            publisher="science",
            config=BrowserRuntimeConfig(
                provider="science",
                doi=DOI,
                artifact_dir=tmp_path,
                headless=True,
                user_agent=None,
            ),
            readiness=BrowserHtmlReadiness(wait_for_article_body=False),
            options=BrowserHtmlFetchOptions(supplementary_index=True),
        )
        assert result.final_url == abstract_url
        assert "support.csv" in result.html
        assert not hasattr(result, "staged_storage_state")


@pytest.mark.parametrize(
    "restriction", ["--artifact-mode=none", "--asset-profile=none"]
)
def test_cli_explicit_download_restrictions_preserve_links(
    supplementary_server, tmp_path, capsys, restriction
):
    metadata, calls = supplementary_server
    code = cli.main(
        [
            "fetch",
            "--query",
            metadata["doi"],
            "--target",
            "supplementary",
            "--output-dir",
            str(tmp_path),
            restriction,
        ]
    )
    receipt = json.loads(capsys.readouterr().out)
    assert code == int(not receipt["target_satisfied"])
    assert receipt["error"] is None
    assert receipt["acceptance"]["asset_summary"]["not_archived"] == 1
    assert "asset_not_archived" in receipt["warning_codes"]
    assert calls == ["/article"]
