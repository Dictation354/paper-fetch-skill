"""CLI receipts and retained reading artifacts, using boundary fetch doubles."""

import json
from pathlib import Path

import pytest

from paper_fetch import cli
from paper_fetch.models import (
    AssetDiagnostic,
    AssetQualitySummary,
    FetchEnvelope,
    Metadata,
    Quality,
)
from paper_fetch.resolve.query import ResolvedQuery
from paper_fetch.service import HasFulltextProbeResult, PaperFetchFailure
from tests.support.asset_delivery_scenarios import GIF, asset_state
from tests.support.workflow_acceptance import _envelope


@pytest.fixture
def isolated(monkeypatch):
    monkeypatch.setattr(cli, "build_runtime_env", lambda: {})
    monkeypatch.setattr(cli, "fetch_paper", lambda *a, **kw: _envelope())
    monkeypatch.setattr(
        cli,
        "resolve_paper",
        lambda q, **kw: ResolvedQuery(query=q, query_kind="doi", doi=q),
    )


def test_default_receipt_delivers_retained_full_body(isolated, capsys):
    assert cli.main(["fetch", "--query", "10.1000/acceptance"]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert (
        receipt["contract"] == "paper-fetch/receipt" and receipt["schema_version"] == 2
    )
    assert receipt["content_kind"] == "fulltext"
    assert receipt["target_satisfied"] is True and receipt["error"] is None
    for key in ("body_path", "manifest_path", "image_index_path", "section_index_path"):
        path = Path(receipt[key])
        assert path.is_absolute() and path.is_file()
    manifest = json.loads(Path(receipt["manifest_path"]).read_text())
    assert manifest["acceptance"]["identity"]["doi"] == "10.1000/acceptance"
    assert "markdown" not in receipt and "trace" not in receipt
    assert not list(
        Path(receipt["manifest_path"]).parents[3].glob(".paper-fetch-cache.json")
    )


def test_receipt_v2_projects_compact_fields_across_lookup(
    isolated, tmp_path, capsys, monkeypatch
):
    envelope = _envelope()
    envelope.quality.asset_summary = AssetQualitySummary(
        requested=True,
        audited=True,
        profile="body",
        discovered=2,
        attempted=2,
        local=1,
        accepted_preview=1,
        not_archived=1,
        remote_link_count=1,
        remote_only_count=1,
        diagnostics=[
            AssetDiagnostic(
                request_profile="body",
                kind="figure",
                status="available",
                path="preview.png",
                download_tier="preview",
            ),
            AssetDiagnostic(
                request_profile="body", kind="figure", status="not_archived"
            ),
        ],
    )
    monkeypatch.setattr(cli, "fetch_paper", lambda *a, **kw: envelope)
    doi = "10.1000/acceptance"
    output = ["--output-dir", str(tmp_path)]
    assert (
        cli.main(
            [
                "fetch",
                "--query",
                doi,
                *output,
                "--asset-profile",
                "body",
                "--require-full-size-body-assets",
            ]
        )
        == 0
    )
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["schema_version"] == 2
    assert receipt["identity"].keys() == {
        "status",
        "doi",
        "expected_doi",
        "title",
        "candidate_count",
        "codes",
    }
    assert receipt["acceptance"]["asset_summary"] == {
        "requested": True,
        "profile": "body",
        "discovered": 2,
        "local": 1,
        "full_size": 0,
        "failed": 0,
        "not_archived": 1,
        "issue_codes": ["local_body_assets_required", "full_size_body_assets_required"],
    }
    assert cli.main(["lookup", "--doi", doi, *output]) == 0
    assert json.loads(capsys.readouterr().out) == receipt


def test_section_index_uses_written_body_lines_and_leaves_stdout_export_intact(
    isolated, capsys, tmp_path, monkeypatch
):
    markdown = (
        "---\n# YAML comment\ntitle: Paper\n---\n"
        "# Paper\n\n## Main ###\nIntroduction.\n"
        "````md\n## Fenced\n```\n## Still fenced\n````\n"
        "~~~text\nHidden\n------\n~~~\n"
        "\nResults\n-------\nResult text.\n\n### Detail\nLast line.\n"
    )
    envelope = _envelope()
    envelope.markdown = markdown
    monkeypatch.setattr(cli, "fetch_paper", lambda *a, **k: envelope)
    args = ["fetch", "--query", "10.1000/acceptance", "--output-dir", str(tmp_path)]
    assert cli.main(args) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert Path(receipt["body_path"]).read_bytes() == markdown.encode()
    assert json.loads(Path(receipt["section_index_path"]).read_text()) == {
        "schema_version": 1,
        "sections": [
            {"title": "Paper", "level": 1, "start_line": 5, "end_line": 6},
            {"title": "Main", "level": 2, "start_line": 7, "end_line": 18},
            {"title": "Results", "level": 2, "start_line": 19, "end_line": 22},
            {"title": "Detail", "level": 3, "start_line": 23, "end_line": 24},
        ],
    }
    assert cli.main([*args, "--output", "-"]) == 0
    assert capsys.readouterr().out == markdown


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
    assert receipt["target_satisfied"] is False
    assert (receipt["error"] is not None) == (kind == "failed")


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


@pytest.mark.parametrize("manifest_version", [2, 3])
def test_manifest_assets_require_v3_and_never_fetch_body(
    isolated, tmp_path, capsys, monkeypatch, manifest_version
):
    assert (
        cli.main(
            ["fetch", "--query", "10.1000/acceptance", "--output-dir", str(tmp_path)]
        )
        == 0
    )
    receipt = json.loads(capsys.readouterr().out)
    manifest_path = Path(receipt["manifest_path"])
    if manifest_version == 2:
        payload = json.loads(manifest_path.read_text())
        identity = payload["acceptance"]["identity"]
        payload.update(
            schema_version=2,
            minimum_reader_schema_version=2,
            doi=identity["doi"],
            identity=identity,
        )
        payload["acceptance"].update(schema_version=2, minimum_reader_schema_version=2)
        payload["output_artifacts"] = [
            item
            for item in payload["output_artifacts"]
            if item["kind"] != "section_index"
        ]
        manifest_path.write_text(json.dumps(payload))
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
    monkeypatch.setattr(
        cli, "fetch_paper", lambda *a, **kw: pytest.fail("body fetch forbidden")
    )
    exit_code = cli.main(
        ["fetch-assets", "--manifest", str(manifest_path), "--kind", "formula"]
    )
    response = json.loads(capsys.readouterr().out)
    if manifest_version == 2:
        assert exit_code == 1
        assert response["status"] == "error" and "schema_version" in response["reason"]
        assert seen == []
        return
    assert exit_code == 0
    assert seen == ["10.1000/acceptance"]
    assert response["assets"][0]["path"].endswith("figure.png")


def test_compact_assets_return_actual_files_when_details_write_fails(
    tmp_path, capsys, monkeypatch
):
    from paper_fetch import targeted_assets

    state = asset_state()
    image = tmp_path / "formula#1.gif"
    image.write_bytes(GIF)
    asset = state.assets[0]
    asset["path"] = str(image)
    monkeypatch.setattr(targeted_assets, "context_from_manifest", lambda path: state)

    def fail_write(*args, **kwargs):
        raise OSError("Unwritable path with token=private-value")

    monkeypatch.setattr(cli.ArtifactStore, "write_json_file", fail_write)
    assert (
        cli.main(
            [
                "fetch-assets",
                "--manifest",
                "manifest.json",
                "--asset-id",
                asset["asset_id"],
                "--output-dir",
                str(tmp_path / "images"),
                "--compact",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    receipt = json.loads(captured.out)
    assert receipt["details_path"] is None and receipt["status"] == "ok"
    (result,) = receipt["results"]
    assert result["asset_id"] == asset["asset_id"]
    path = Path(result["path"])
    assert path.parent == tmp_path / "images" and path.read_bytes() == GIF
    assert captured.err == "Warning: could not save fetch-assets details.\n"


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


def test_receipt_error_projects_diagnostics_and_redacts_secrets(
    isolated, monkeypatch, capsys
):
    from paper_fetch.failure import FailureDiagnostics

    def fetch(*args, **kwargs):
        raise PaperFetchFailure(
            "no_access",
            "Denied https://example.test/article?token=secret-value",
            diagnostics=FailureDiagnostics(
                provider="ams",
                route="browser_html",
                stage="auth_profile_reopen",
                http_status=403,
                retryable=False,
                details={"unbounded": "not part of receipt"},
            ),
        )

    monkeypatch.setattr(cli, "fetch_paper", fetch)
    assert cli.main(["fetch", "--query", "10.1000/acceptance"]) == 1
    output = capsys.readouterr()
    receipt = json.loads(output.out)
    error = receipt["error"]
    assert set(error) == {
        "status",
        "reason",
        "provider",
        "route",
        "stage",
        "http_status",
        "retryable",
    }
    assert error["http_status"] == 403 and error["retryable"] is False
    assert error["stage"] == "auth_profile_reopen"
    assert "secret-value" not in output.out


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
