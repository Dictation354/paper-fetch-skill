"""Fixed HTTP responses exercise Nature resolution and per-paper CLI delivery."""

import json
from pathlib import Path

from paper_fetch import cli, runtime
from paper_fetch.providers import _springer_dom
from tests.support._paper_fetch_support import FixtureHtmlTransport, http_response

DOI = "10.1038/s41586-026-12345-x"
URL = "https://www.nature.com/articles/s41586-026-12345-x"
CROSSREF_URL = "https://api.crossref.org/works/10.1038%2Fs41586-026-12345-x"
TITLE = "Café measurements across independent samples"
INTRO = "The café experiment compared independent samples under controlled conditions."


def test_nature_url_and_doi_share_one_fetch_and_deliver_timed_sections(
    tmp_path, capsys, monkeypatch
):
    html = f"""
    <html><head>
    <meta name="citation_doi" content="{DOI}">
    <meta name="citation_title" content="{TITLE}">
    </head><body><article><h1>{TITLE}</h1>
    <div class="c-article-body main-content">
    <section data-title="Main"><h2>Main</h2><p>{(INTRO + " ") * 30}</p></section>
    <section data-title="Results"><h2>Results</h2>
    <p>{"The measurements showed consistent differences among samples. " * 30}</p>
    </section></div></article></body></html>
    """
    message = {"DOI": DOI, "URL": URL, "title": [TITLE], "publisher": "Springer Nature"}
    transport = FixtureHtmlTransport(
        {
            URL: http_response(
                URL, html.encode("cp1252"), "text/html; charset=windows-1252"
            ),
            CROSSREF_URL: http_response(
                CROSSREF_URL,
                json.dumps({"message": message}).encode(),
                "application/json",
            ),
        }
    )
    monkeypatch.setattr(cli, "build_runtime_env", lambda: {})
    monkeypatch.setattr(
        runtime, "build_http_transport_for_context", lambda *a, **k: transport
    )
    parsed = []
    parse_metadata = _springer_dom.parse_html_metadata

    def record_parse(text, url):
        parsed.append(url)
        return parse_metadata(text, url)

    monkeypatch.setattr(_springer_dom, "parse_html_metadata", record_parse)

    assert cli.main(["resolve", "--query", URL]) == 0
    assert json.loads(capsys.readouterr().out)["doi"] == DOI
    assert transport.calls == []

    queries = tmp_path / "queries.txt"
    queries.write_text(f"{URL}\n{DOI}\n", encoding="utf-8")
    assert (
        cli.main(
            [
                "fetch",
                "--progress",
                "text",
                "--query-file",
                str(queries),
                "--batch-concurrency",
                "2",
                "--output-dir",
                str(tmp_path / "papers"),
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "fetching" in captured.err and "scope=fulltext" in captured.err
    receipts = [json.loads(line) for line in captured.out.splitlines()]
    assert [receipt["query"] for receipt in receipts] == [URL, DOI]
    assert [call["url"] for call in transport.calls] == [CROSSREF_URL, URL]
    assert parsed == [URL]

    for receipt in receipts:
        assert receipt["doi"] == DOI and receipt["source"] == "springer_html"
        diagnostics = json.loads(
            Path(receipt["diagnostic_paths"][-1]).read_text(encoding="utf-8")
        )
        identity = diagnostics["diagnostics"]["identity"]
        assert (identity["status"], identity["method"], identity["observed_doi"]) == (
            "match",
            "doi",
            DOI,
        )
        section_path = Path(receipt["section_index_path"])
        sections = json.loads(section_path.read_text(encoding="utf-8"))["sections"]
        lines = Path(receipt["body_path"]).read_text(encoding="utf-8").splitlines()
        main = next(section for section in sections if section["title"] == "Main")
        selected = lines[main["start_line"] - 1 : main["end_line"]]
        assert selected[0] == "## Main"
        assert INTRO in "\n".join(selected)
        assert "## Results" not in selected
        manifest = json.loads(
            Path(receipt["manifest_path"]).read_text(encoding="utf-8")
        )
        assert manifest["schema_version"] == 3
        section_artifact = next(
            a for a in manifest["output_artifacts"] if a["kind"] == "section_index"
        )
        assert section_artifact["path"] == str(section_path)
        assert section_artifact["verification_status"] == "verified"
        timed = {
            event["component"]: event["duration_ms"]
            for event in manifest["trace"]
            if event["duration_ms"] is not None
        }
        assert {
            "url",
            "crossref",
            "springer_html_http",
            "springer_html_parse",
            "springer_html_extract",
        } <= timed.keys()
        assert all(duration >= 0 for duration in timed.values())
