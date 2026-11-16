"""Reading paths survive CLI processes and completed batch items survive cancellation."""

from pathlib import Path
import json
import os
import signal
import subprocess
import sys
import textwrap

from tests.paths import REPO_ROOT


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
        first = json.loads(process.stdout.readline())
        assert first["index"] == 1
        assert process.poll() is None
        manifest = Path(first["manifest_path"])
        assert json.loads(manifest.read_text())["query"] == "10.1000/first"
        assert Path(first["body_path"]).read_text()
        # The second logical input shares acquisition, while retaining its own identity/manifest.
        duplicate = json.loads(process.stdout.readline())
        assert (
            duplicate["index"] == 2
            and duplicate["manifest_path"] != first["manifest_path"]
        )
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 1, stderr
        last = json.loads(stdout.strip())
        assert last["index"] == 3 and "request_cancelled" in last["failure_codes"]
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
