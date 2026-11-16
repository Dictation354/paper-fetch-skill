"""CLI receipts and retained reading artifacts, using boundary fetch doubles."""

from pathlib import Path
import json
import pytest

from paper_fetch import cli
from paper_fetch.models import FetchEnvelope, Metadata, Quality
from paper_fetch.resolve.query import ResolvedQuery
from paper_fetch.service import HasFulltextProbeResult, PaperFetchFailure
from tests.support.workflow_acceptance import _envelope


@pytest.fixture
def isolated(monkeypatch):
    monkeypatch.setattr(cli, "build_runtime_env", lambda: {})
    monkeypatch.setattr(cli, "fetch_paper", lambda *a, **kw: _envelope())


def test_default_receipt_delivers_retained_full_body(isolated, capsys):
    assert cli.main(["fetch", "--query", "10.1000/acceptance"]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert (
        receipt["contract"] == "paper-fetch/receipt" and receipt["schema_version"] == 1
    )
    assert receipt["content_kind"] == "fulltext"
    for key in ("body_path", "manifest_path", "image_index_path"):
        path = Path(receipt[key])
        assert path.is_absolute() and path.is_file()
    manifest = json.loads(Path(receipt["manifest_path"]).read_text())
    assert manifest["identity"]["doi"] == "10.1000/acceptance"
    assert "markdown" not in receipt and "trace" not in receipt
    assert not list(
        Path(receipt["manifest_path"]).parents[3].glob(".paper-fetch-cache.json")
    )


@pytest.mark.parametrize("output_format", ["markdown", "json", "both"])
def test_body_stdout_export_and_file_receipts(
    isolated, capsys, tmp_path, output_format
):
    args = [
        "fetch",
        "--query",
        "10.1000/acceptance",
        "--format",
        output_format,
        "--output-dir",
        str(tmp_path),
    ]
    assert cli.main(args + ["--output", "-"]) == 0
    exported = capsys.readouterr().out
    if output_format == "markdown":
        assert exported.startswith("---") or "Acceptance" in exported
    else:
        assert (
            json.loads(exported)
            if output_format == "json"
            else json.loads(exported)["article"]
        )["doi"] == "10.1000/acceptance"
    assert (
        cli.main(args + ["--output", str(tmp_path / "explicit.out"), "--overwrite"])
        == 0
    )
    receipt = json.loads(capsys.readouterr().out)
    assert Path(receipt["body_path"]).is_file()
    assert str(tmp_path / "explicit.out") in receipt["output_paths"]


@pytest.mark.parametrize("kind", ["abstract_only", "metadata_only", "failed"])
def test_partial_and_failure_keep_manifest_and_return_one(
    isolated, capsys, monkeypatch, kind
):
    def fetch(*a, **kw):
        if kind == "failed":
            raise PaperFetchFailure("no_access", "No access")
        return FetchEnvelope(
            doi="10.1000/acceptance",
            source="crossref",
            metadata=Metadata(
                title="Partial",
                abstract="Abstract" if kind == "abstract_only" else None,
            ),
            markdown="Abstract" if kind == "abstract_only" else "Metadata",
            quality=Quality(content_kind=kind),
        )

    monkeypatch.setattr(cli, "fetch_paper", fetch)
    assert cli.main(["fetch", "--query", "10.1000/acceptance"]) == 1
    receipt = json.loads(capsys.readouterr().out)
    assert Path(receipt["manifest_path"]).is_file()
    assert not receipt["acceptance"]["has_fulltext"]


def test_resolve_and_check_map_inputs_without_body_fetch(
    isolated, monkeypatch, tmp_path, capsys
):
    source = tmp_path / "queries.txt"
    source.write_text("10.1000/first\n10.1000/second\n")
    monkeypatch.setattr(
        cli,
        "resolve_paper",
        lambda q, **kw: ResolvedQuery(query=q, query_kind="doi", doi=q),
    )
    from paper_fetch import service

    monkeypatch.setattr(
        service,
        "probe_has_fulltext",
        lambda q, **kw: HasFulltextProbeResult(q, q, None, "unknown", [], []),
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("lookup must not fetch a body")

    monkeypatch.setattr(cli, "fetch_paper", forbidden)
    for name in ("resolve", "check"):
        assert cli.main([name, "--query-file", str(source)]) == 0
        payloads = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
        assert [p["index"] for p in payloads] == [1, 2]
        assert [p["doi"] for p in payloads] == source.read_text().splitlines()


def test_manifest_assets_never_resolve_or_fetch_body(
    isolated, tmp_path, capsys, monkeypatch
):
    assert (
        cli.main(
            ["fetch", "--query", "10.1000/acceptance", "--output-dir", str(tmp_path)]
        )
        == 0
    )
    receipt = json.loads(capsys.readouterr().out)
    from paper_fetch import targeted_assets

    seen = []

    def selected(state, **kwargs):
        seen.append(state.doi)
        return {"status": "ok", "assets": [{"path": str(tmp_path / "figure.png")}]}

    monkeypatch.setattr(targeted_assets, "fetch_selected_assets", selected)
    monkeypatch.setattr(
        targeted_assets,
        "context_from_query",
        lambda *a: pytest.fail("query fetch forbidden"),
    )
    assert (
        cli.main(
            [
                "fetch-assets",
                "--manifest",
                receipt["manifest_path"],
                "--kind",
                "formula",
            ]
        )
        == 0
    )
    assert seen == ["10.1000/acceptance"]
    assert json.loads(capsys.readouterr().out)["assets"][0]["path"].endswith(
        "figure.png"
    )


def test_truncation_reports_actual_render_warning(isolated, monkeypatch, capsys):
    from paper_fetch.models import TRUNCATION_WARNING

    envelope = _envelope()
    envelope.quality.warnings.append(TRUNCATION_WARNING)
    monkeypatch.setattr(cli, "fetch_paper", lambda *a, **kw: envelope)
    assert (
        cli.main(["fetch", "--query", "10.1000/acceptance", "--max-tokens", "7"]) == 0
    )
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["truncated"] is True and receipt["truncation_reason"] == "max_tokens"


@pytest.mark.parametrize("command", ["resolve", "check"])
@pytest.mark.parametrize("exists", [False, True])
def test_lookup_invalid_query_file_is_argument_error(tmp_path, command, exists, capsys):
    query_file = tmp_path / "queries.txt"
    if exists:
        query_file.write_text("# no queries\n")
    with pytest.raises(SystemExit) as error:
        cli.main([command, "--query-file", str(query_file)])
    assert error.value.code == 2
    assert "query file" in capsys.readouterr().err
