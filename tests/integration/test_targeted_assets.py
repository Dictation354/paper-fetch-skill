"""Real subprocess contracts for selected images, with synthetic HTTP responses."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests.paths import REPO_ROOT
from tests.support.asset_delivery_scenarios import GIF, SOURCE, asset_state

SETUP = textwrap.dedent("""
    from paper_fetch import targeted_assets, service
    from paper_fetch.runtime import RuntimeContext
    from tests.support.asset_delivery_scenarios import ImageTransport, asset_state, SOURCE
    from paper_fetch.resolve.query import ResolvedQuery
    transport = ImageTransport()
    def runtime(**kwargs):
        return RuntimeContext(env={}, transport=transport, clients={}, artifact_mode="none")
    targeted_assets.RuntimeContext = runtime
    service.resolve_paper = lambda query, **kw: ResolvedQuery(query=query, query_kind="doi", doi="10.1000/example", landing_url=SOURCE)
    def forbidden(*args, **kwargs):
        raise AssertionError("Full paper fetch is forbidden for fetch-assets")
    service.fetch_paper = forbidden
""")


CLI_ENTRY = textwrap.dedent("""
    import sys
    from paper_fetch import cli
    cli.RuntimeContext = runtime
    raise SystemExit(cli.main(sys.argv[1:]))
""")


def run_cli(tmp_path, *arguments, script=SETUP + CLI_ENTRY):
    return subprocess.run(
        [sys.executable, "-c", script, *arguments],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "PYTHONPATH": str(REPO_ROOT / "src") + os.pathsep + str(REPO_ROOT),
            "TMPDIR": str(tmp_path),
        },
        capture_output=True,
        text=True,
        timeout=30,
    )


def compact_receipt(process, exit_code):
    assert process.returncode == exit_code, process.stderr
    (line,) = process.stdout.splitlines()
    receipt = json.loads(line)
    assert receipt["schema_version"] == 1
    assert receipt["contract"] == "paper-fetch/asset-receipt"
    return receipt


def read_details(receipt):
    path = Path(receipt["details_path"])
    assert path.is_absolute()
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("compact", [False, True])
@pytest.mark.parametrize("archive", [False, True])
def test_cli_fetch_assets_json_and_files_survive_process_exit(
    tmp_path, archive, compact
):
    arguments = ["fetch-assets", "--query", "10.1000/example", "--kind", "formula"]
    destination = tmp_path / "images#archive"
    if archive:
        arguments += ["--output-dir", str(destination)]
    if compact:
        arguments.append("--compact")
    process = run_cli(tmp_path, *arguments)
    assert process.returncode == 0, process.stderr
    payload = compact_receipt(process, 0) if compact else json.loads(process.stdout)
    assert payload["doi"] == "10.1000/example"
    assert payload["status"] == "ok"
    paths = [Path(item["path"]) for item in payload["results"]]
    assert len(paths) == 2
    for path in paths:
        assert path.is_absolute() and path.read_bytes() == GIF
        if archive:
            assert path.parent == destination
    if compact:
        details = read_details(payload)
        details_dir = Path(payload["details_path"]).parent
        if archive:
            assert details_dir == destination
        else:
            assert details_dir.parent == tmp_path
            assert all(path.is_relative_to(details_dir) for path in paths)
        assert [item["path"] for item in details["results"]] == [str(p) for p in paths]
        assert all(
            set(item) == {"asset_id", "path", "status"} for item in payload["results"]
        )
    else:
        details = payload
        assert "details_path" not in payload
    assert details["source_url"] == SOURCE
    assert details["temporary"] is not archive
    assert all("caption" in item for item in details["results"])


def test_compact_partial_receipt_keeps_per_image_failure_in_details(tmp_path):
    setup = SETUP + 'transport.fail.add("https://example.test/math-2.gif")\n'
    process = run_cli(
        tmp_path,
        "fetch-assets",
        "--query",
        "10.1000/example",
        "--kind",
        "formula",
        "--compact",
        script=setup + CLI_ENTRY,
    )
    receipt = compact_receipt(process, 1)
    assert receipt["status"] == "partial"
    success, failure = receipt["results"]
    assert success["status"] == "ok" and Path(success["path"]).read_bytes() == GIF
    assert failure == {
        "asset_id": next(
            a["asset_id"]
            for a in asset_state().assets
            if a["url"].endswith("math-2.gif")
        ),
        "status": "failed",
        "reason": "asset_download_failed",
    }
    assert read_details(receipt)["results"][1]["failures"]


def test_compact_unknown_url_reports_redacted_selector(tmp_path):
    process = run_cli(
        tmp_path,
        "fetch-assets",
        "--query",
        "10.1000/example",
        "--asset-url",
        "https://user:password-value@example.test/unknown.gif?token=signed-value",
        "--compact",
    )
    receipt = compact_receipt(process, 1)
    assert receipt["status"] == "error"
    assert receipt["results"] == [
        {
            "selector": "https://example.test/unknown.gif?[redacted]",
            "status": "failed",
            "reason": "asset_not_found",
        }
    ]
    assert read_details(receipt)["results"] == receipt["results"]


@pytest.mark.parametrize(
    "query,doi", [("10.1000/example", "10.1000/example"), ("https://[", None)]
)
def test_compact_command_failure_reports_short_redacted_reason(tmp_path, query, doi):
    setup = SETUP + textwrap.dedent(r"""
        from paper_fetch.failure import FailureDiagnostics
        from paper_fetch.providers.base import ProviderFailure
        def fail(*args, **kwargs):
            raise ProviderFailure(
                "auth_required",
                "Sign in at https://user:password-value@example.test/?token=signed-value\n"
                "Authorization: Basic header-value " + "Long diagnostics. " * 100,
                diagnostics=FailureDiagnostics(details={"Authorization": "nested-value", "stage_note": "sign in"}),
            )
        service.resolve_paper = fail
    """)
    process = run_cli(
        tmp_path,
        "fetch-assets",
        "--query",
        query,
        "--kind",
        "formula",
        "--compact",
        script=setup + CLI_ENTRY,
    )
    receipt = compact_receipt(process, 1)
    assert receipt["doi"] == doi
    assert receipt["status"] == "auth_required" and receipt["results"] == []
    assert receipt["reason"].startswith("Sign in at https://example.test/")
    assert receipt["reason"].endswith("...") and len(receipt["reason"]) <= 300
    details = read_details(receipt)
    assert details["reason"].endswith("Long diagnostics. " * 100)
    assert details["details"] == {"stage_note": "sign in"}
    for secret in ("password-value", "signed-value", "header-value", "nested-value"):
        assert secret not in process.stdout + process.stderr + json.dumps(details)


def test_compact_invalid_kind_is_a_usage_error(tmp_path):
    process = run_cli(
        tmp_path,
        "fetch-assets",
        "--query",
        "10.1000/example",
        "--kind",
        "figure",
        "--compact",
    )
    assert process.returncode == 2
    assert not process.stdout
    assert "invalid choice" in process.stderr


def test_cli_manifest_images_do_not_fetch_source_again(tmp_path):
    # First process produces the durable identity/index; the next only downloads selected images.
    seed = SETUP + textwrap.dedent("""
        import sys
        from paper_fetch import cli
        from tests.support.fetch_fixtures import sample_envelope
        def fetch(*args, **kwargs):
            envelope = sample_envelope(modes={"article", "markdown"})
            envelope._asset_context = asset_state()
            for asset in envelope._asset_context.assets:
                asset["caption"] = (asset["asset_id"] + " long caption. ") * 100
            return envelope
        cli.fetch_paper = fetch
        cli.build_runtime_env = lambda: {}
        raise SystemExit(cli.main(sys.argv[1:]))
    """)
    first = run_cli(
        tmp_path,
        "fetch",
        "--query",
        "10.1000/example",
        "--output-dir",
        str(tmp_path / "paper"),
        script=seed,
    )
    assert first.returncode == 0, first.stderr
    paper = json.loads(first.stdout)
    index = json.loads(Path(paper["image_index_path"]).read_text(encoding="utf-8"))
    selected = [item for item in index["assets"] if item["kind"] == "formula"]
    assert len(selected) == 2
    fetch = SETUP + textwrap.dedent("""
        def reject_source(*args, **kwargs):
            raise AssertionError("Manifest download fetched the article again")
        targeted_assets._load_source = reject_source
        service.resolve_paper = reject_source
    """)
    result = run_cli(
        tmp_path,
        "fetch-assets",
        "--manifest",
        paper["manifest_path"],
        "--compact",
        "--asset-id",
        selected[0]["asset_id"],
        "--asset-id",
        selected[1]["asset_id"],
        "--output-dir",
        str(tmp_path / "images"),
        script=fetch + CLI_ENTRY,
    )
    receipt = compact_receipt(result, 0)
    assert receipt["doi"] == paper["doi"] == "10.1000/example"
    assert [item["asset_id"] for item in receipt["results"]] == [
        item["asset_id"] for item in selected
    ]
    assert all(Path(item["path"]).read_bytes() == GIF for item in receipt["results"])
    assert "long caption" not in result.stdout
    assert [item["caption"] for item in read_details(receipt)["results"]] == [
        item["caption"] for item in selected
    ]
