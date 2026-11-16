"""Real subprocess contracts for selected images, with synthetic HTTP responses."""

from __future__ import annotations

from contextlib import suppress
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from tests.paths import REPO_ROOT
from tests.support.asset_delivery_scenarios import GIF, SOURCE

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


def environment():
    return {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT / "src") + os.pathsep + str(REPO_ROOT),
    }


@pytest.mark.parametrize("archive", [False, True])
def test_cli_fetch_assets_json_and_files_survive_process_exit(tmp_path, archive):
    script = SETUP + textwrap.dedent("""
        import sys
        from paper_fetch import cli
        cli.RuntimeContext = runtime
        raise SystemExit(cli.main(sys.argv[1:]))
    """)
    arguments = ["fetch-assets", "--query", "10.1000/example", "--kind", "formula"]
    if archive:
        arguments += ["--output-dir", str(tmp_path / "images")]
    process = subprocess.run(
        [sys.executable, "-c", script, *arguments],
        cwd=REPO_ROOT,
        env=environment(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert process.returncode == 0, process.stderr
    payload = json.loads(process.stdout)
    assert payload["doi"] == "10.1000/example"
    assert payload["source_url"] == SOURCE
    assert payload["temporary"] is not archive
    paths = [Path(item["path"]) for item in payload["results"]]
    assert len(paths) == 2
    for path in paths:
        assert path.read_bytes() == GIF
        if archive:
            assert path.parent == tmp_path / "images"
    if not archive:
        # CLI temporary files are deliberately caller-owned after exit.

        for path in paths:
            path.unlink()
        for directory in {path.parent for path in paths}:
            with suppress(OSError):
                directory.rmdir()


def test_cli_manifest_images_do_not_fetch_source_again(tmp_path):
    # First process produces the durable identity/index; the next only downloads selected images.
    seed = SETUP + textwrap.dedent("""
        import sys
        from paper_fetch import cli
        from tests.support.fetch_fixtures import sample_envelope
        def fetch(*args, **kwargs):
            envelope = sample_envelope(modes={"article", "markdown"})
            envelope._asset_context = asset_state()
            return envelope
        cli.fetch_paper = fetch
        cli.build_runtime_env = lambda: {}
        raise SystemExit(cli.main(sys.argv[1:]))
    """)
    first = subprocess.run(
        [
            sys.executable,
            "-c",
            seed,
            "fetch",
            "--query",
            "10.1000/example",
            "--output-dir",
            str(tmp_path / "paper"),
        ],
        cwd=REPO_ROOT,
        env=environment(),
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert first.returncode == 0, first.stderr
    receipt = json.loads(first.stdout)
    fetch = SETUP + textwrap.dedent("""
        import sys
        from paper_fetch import cli
        def reject_source(*args, **kwargs):
            raise AssertionError("Manifest download fetched the article again")
        targeted_assets._load_source = reject_source
        service.resolve_paper = reject_source
        cli.RuntimeContext = runtime
        raise SystemExit(cli.main(sys.argv[1:]))
    """)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            fetch,
            "fetch-assets",
            "--manifest",
            receipt["manifest_path"],
            "--kind",
            "formula",
            "--output-dir",
            str(tmp_path / "images"),
        ],
        cwd=REPO_ROOT,
        env=environment(),
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    paths = [Path(item["path"]) for item in json.loads(result.stdout)["results"]]
    assert len(paths) == 2 and all(path.read_bytes() == GIF for path in paths)
