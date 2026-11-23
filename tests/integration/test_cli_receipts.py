"""Reading paths survive CLI processes and completed batch items survive cancellation."""

import json
import os
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests.paths import REPO_ROOT


def test_lookup_cli_recovers_verified_receipts_and_requires_section_index(
    tmp_path, monkeypatch, capsys
):
    from paper_fetch import cli
    from paper_fetch.models import TRUNCATION_WARNING
    from tests.support.fetch_fixtures import sample_envelope, sample_resolved_query

    doi = "10.1000/example"
    project = tmp_path / "papers"
    envelope = sample_envelope(modes={"article", "markdown"}, doi=doi)
    monkeypatch.setattr(cli, "fetch_paper", lambda *a, **k: envelope)
    monkeypatch.setattr(
        cli, "resolve_paper", lambda query, **k: sample_resolved_query(query)
    )
    monkeypatch.setattr(cli, "build_runtime_env", lambda: {})

    def fetch(directory=project):
        assert (
            cli.main(
                [
                    "fetch",
                    "--query",
                    doi,
                    "--output-dir",
                    str(directory),
                    "--overwrite",
                ]
            )
            == 0
        )
        return json.loads(capsys.readouterr().out)

    def lookup(*directories, query=doi, include_legacy=False):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "paper_fetch.cli",
                "lookup",
                "--doi",
                query,
                *(
                    arg
                    for directory in directories or (project,)
                    for arg in ("--output-dir", str(directory))
                ),
                *(["--include-legacy"] if include_legacy else []),
            ],
            cwd=tmp_path,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
            capture_output=True,
            text=True,
            timeout=10,
        )

    without_sections = fetch()
    no_sections_manifest_path = Path(without_sections["manifest_path"])
    no_sections_manifest = json.loads(no_sections_manifest_path.read_text())
    no_sections_manifest["output_artifacts"] = [
        artifact
        for artifact in no_sections_manifest["output_artifacts"]
        if artifact["kind"] != "section_index"
    ]
    no_sections_manifest_path.write_text(json.dumps(no_sections_manifest))

    previous = fetch()
    current = fetch()
    other_project = tmp_path / "another-project"
    other_project.mkdir()
    sidecar = other_project / "10.1000_example.fetch-envelope.json"
    historical_data = {
        "version": 2,
        "extraction_revision": 2,
        "request": {"max_tokens": "full_text"},
        "payload": {
            "doi": doi,
            "source": "wiley_browser",
            "markdown": "# Historical text",
            "content_kind": "fulltext",
            "has_fulltext": True,
            "warnings": [],
            "quality": {
                "content_kind": "fulltext",
                "has_fulltext": True,
                "warnings": [],
            },
        },
    }
    sidecar.write_text(json.dumps(historical_data))
    other = fetch(other_project)
    assert (
        json.loads(lookup(project, other_project, include_legacy=True).stdout) == other
    )

    other_manifest = Path(other["manifest_path"])
    other_record = json.loads(other_manifest.read_text())
    current_record = json.loads(Path(current["manifest_path"]).read_text())
    for field in ("started_at", "completed_at"):
        other_record[field] = current_record[field]
    other_manifest.write_text(json.dumps(other_record))
    assert json.loads(lookup(project, other_project).stdout) == current
    assert json.loads(lookup(other_project, project).stdout) == other
    assert (
        json.loads(lookup(other_project, project, include_legacy=True).stdout) == other
    )
    Path(other["section_index_path"]).write_text("damaged index")
    assert (
        json.loads(lookup(other_project, project, include_legacy=True).stdout)
        == current
    )

    missing = fetch()
    Path(missing["body_path"]).unlink()
    envelope.quality.warnings.append(TRUNCATION_WARNING)
    assert fetch()["truncated"] is True

    hit = lookup(query="10.1000/EXAMPLE")
    assert hit.returncode == 0, hit.stderr
    assert json.loads(hit.stdout) == current
    assert len(hit.stdout.splitlines()) == 1 and not hit.stderr

    current_body = Path(current["body_path"])
    original = current_body.read_bytes()
    current_body.write_bytes(b"!" + original[1:])
    fallback = lookup()
    assert fallback.returncode == 0, fallback.stderr
    assert json.loads(fallback.stdout) == previous

    elsewhere = lookup(other_project)
    assert elsewhere.returncode == 1
    assert json.loads(elsewhere.stdout) == {"status": "not_found", "doi": doi}
    Path(previous["body_path"]).unlink()
    miss = lookup()
    assert miss.returncode == 1
    assert miss.stdout == elsewhere.stdout and len(miss.stdout.splitlines()) == 1

    legacy = lookup(project, other_project, include_legacy=True)
    assert legacy.returncode == 0, legacy.stderr
    assert json.loads(legacy.stdout) == {
        "schema_version": 1,
        "contract": "paper-fetch/legacy-lookup",
        "status": "found",
        "doi": doi,
        "source": "wiley_browser",
        "sidecar_path": str(sidecar),
        "sidecar_version": 2,
        "body_json_pointer": "/payload/markdown",
        "acceptance": "historical_unverified",
    }
    preferred_sidecar = project / sidecar.name
    preferred_sidecar.write_text(sidecar.read_text())
    assert json.loads(lookup(project, other_project, include_legacy=True).stdout)[
        "sidecar_path"
    ] == str(preferred_sidecar)
    historical_data["payload"]["quality"]["warnings"] = [TRUNCATION_WARNING]
    preferred_sidecar.write_text(json.dumps(historical_data))
    assert json.loads(lookup(project, other_project, include_legacy=True).stdout)[
        "sidecar_path"
    ] == str(sidecar)

    invalid = lookup(query="not-a-doi")
    assert invalid.returncode == 2 and not invalid.stdout


def _auth_process(script, path):
    return subprocess.Popen(
        [sys.executable, "-u", "-c", textwrap.dedent(script), str(path)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "PYTHONPATH": str(REPO_ROOT / "src") + os.pathsep + str(REPO_ROOT),
        },
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_concurrent_cli_auth_rechecks_actual_profile_and_opens_once(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    alias = tmp_path / "alias"
    if os.name != "nt":
        alias.symlink_to(profile, target_is_directory=True)
    else:
        alias = profile / "."
    script = """
        import sys
        from types import SimpleNamespace
        from paper_fetch import cli, auth
        from paper_fetch.config import BROWSER_PROFILE_DIR_ENV_VAR
        from paper_fetch.runtime import RuntimeContext
        from tests.support.publisher_profiles import write_verified_ams_profile
        sys.stdin.isatty = lambda: True
        def authenticate(**kwargs):
            print('opened', flush=True)
            sys.stdin.readline()
            write_verified_ams_profile(auth.ams_profile_path(kwargs['env']))
        cli.authenticate_provider_profile = authenticate
        print('ready', flush=True)
        with RuntimeContext(env={BROWSER_PROFILE_DIR_ENV_VAR: sys.argv[1]}) as runtime:
            cli._ensure_cli_ams_auth(SimpleNamespace(control_stdin=False), runtime)
        print('done', flush=True)
    """
    first = _auth_process(script, profile)
    second = None
    try:
        assert first.stdout.readline().strip() == "ready"
        assert first.stdout.readline().strip() == "opened"
        second = _auth_process(script, alias)
        assert second.stdout.readline().strip() == "ready"
        assert second.poll() is None
        out, err = first.communicate("finished\n", timeout=10)
        assert first.returncode == 0, err
        assert out.strip() == "done"
        out, err = second.communicate(timeout=10)
        assert second.returncode == 0, err
        assert (
            out.strip() == "done"
        )  # Rechecked after lock admission; no second window.
    finally:
        for process in (first, second):
            if process is not None and process.poll() is None:
                process.kill()
                process.communicate(timeout=5)


@pytest.mark.parametrize("waiting_for_human", [False, True])
def test_cli_auth_wait_can_be_cancelled_without_fetching(tmp_path, waiting_for_human):
    from contextlib import nullcontext

    from paper_fetch.auth import ams_auth_coordination
    from paper_fetch.config import BROWSER_PROFILE_DIR_ENV_VAR

    profile = tmp_path / "profile"
    coordination = (
        nullcontext()
        if waiting_for_human
        else ams_auth_coordination(
            {BROWSER_PROFILE_DIR_ENV_VAR: str(profile)},
            cancel=lambda: None,
        )
    )
    script = """
        import sys, time
        from types import SimpleNamespace
        from paper_fetch import cli
        from paper_fetch.config import BROWSER_PROFILE_DIR_ENV_VAR
        from paper_fetch.http import RequestCancelledError
        from paper_fetch.runtime import RuntimeContext
        sys.stdin.isatty = lambda: True
        def authenticate(**kwargs):
            kwargs['confirm']('Complete authentication here.\\n')
            raise AssertionError('cancelled authentication must not continue')
        cli.authenticate_provider_profile = authenticate
        started = time.monotonic()
        with RuntimeContext(
            env={BROWSER_PROFILE_DIR_ENV_VAR: sys.argv[1]},
            cancel_check=lambda: time.monotonic() - started > 0.2,
        ) as runtime:
            try:
                cli._ensure_cli_ams_auth(SimpleNamespace(control_stdin=False), runtime)
            except RequestCancelledError:
                print('cancelled', flush=True)
            else:
                raise AssertionError('expected cancellation')
    """
    with coordination:
        process = _auth_process(script, profile)
        try:
            # Keep stdin open so cancellation, rather than EOF, ends the prompt.
            assert process.stdout.readline().strip() == "cancelled"
            out, err = process.communicate(timeout=5)
            assert process.returncode == 0, err
            assert not out
            assert ("Complete authentication here" in err) == waiting_for_human
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)


def test_batch_manifest_is_readable_before_completion_and_after_cancel(tmp_path):
    queries = tmp_path / "queries.txt"
    queries.write_text("10.1000/first\n10.1000/first\n10.1000/second\n")
    script = textwrap.dedent("""
        import sys, time
        from paper_fetch import cli
        from paper_fetch.resolve.query import ResolvedQuery
        from tests.support.fetch_fixtures import sample_envelope
        def resolve(query, **kwargs):
            return ResolvedQuery(query=query, query_kind="doi", doi=query, provider_hint="elsevier")
        def fetch(query, *, context, **kwargs):
            if query.endswith("second"):
                while True:
                    context.raise_if_cancelled()
                    time.sleep(0.01)
            return sample_envelope(modes={"article", "markdown"}, doi=query)
        cli.resolve_paper = resolve
        cli.fetch_paper = fetch
        cli.build_runtime_env = lambda: {}
        raise SystemExit(cli.main(sys.argv[1:]))
    """)
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT / "src") + os.pathsep + str(REPO_ROOT),
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-c",
            script,
            "fetch",
            "--query-file",
            str(queries),
            "--output-dir",
            str(tmp_path / "papers"),
            "--batch-concurrency",
            "1",
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        first_line = process.stdout.readline()
        first = json.loads(first_line)
        assert first["index"] == 1
        assert process.poll() is None
        manifest = Path(first["manifest_path"])
        assert manifest.with_name("receipt.json").read_text() == first_line
        assert json.loads(manifest.read_text())["request"]["query"] == "10.1000/first"
        assert Path(first["body_path"]).read_text()
        # The second logical input shares acquisition, while retaining its own identity/manifest.
        duplicate_line = process.stdout.readline()
        duplicate = json.loads(duplicate_line)
        assert (
            duplicate["index"] == 2
            and duplicate["manifest_path"] != first["manifest_path"]
        )
        assert (
            Path(duplicate["manifest_path"]).with_name("receipt.json").read_text()
            == duplicate_line
        )
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 1, stderr
        last = json.loads(stdout.strip())
        assert last["index"] == 3 and "request_cancelled" in last["failure_codes"]
        assert (
            Path(last["manifest_path"]).with_name("receipt.json").read_text() == stdout
        )
        assert manifest.with_name("receipt.json").read_text() == first_line
        assert manifest.is_file() and Path(first["body_path"]).is_file()
        summary = [
            json.loads(line)
            for line in (tmp_path / "papers/batch-results.jsonl")
            .read_text()
            .splitlines()
        ]
        assert [item["index"] for item in summary] == [1, 2, 3]
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
