"""Resolution CLI JSONL contracts through injected HTTP and availability boundaries."""

import json
import os
import subprocess
import sys
import textwrap

import pytest

from tests.paths import REPO_ROOT


def run_cli(*args, script):
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script), *args],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "PYTHONPATH": str(REPO_ROOT / "src") + os.pathsep + str(REPO_ROOT),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.mark.parametrize("progress", ["text", "jsonl"])
def test_resolve_pubmed_keeps_stdout_jsonl(progress):
    process = run_cli(
        "resolve",
        "--query",
        "https://pubmed.ncbi.nlm.nih.gov/123/",
        "--progress",
        progress,
        script="""
            import json
            import sys
            from paper_fetch import cli
            from paper_fetch.runtime import RuntimeContext
            from tests.support._paper_fetch_support import RecordingTransport

            converter = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
            crossref = "https://api.crossref.org/works/10.1016%2Fexample"
            transport = RecordingTransport({
                ("GET", converter): {
                    "url": converter, "body": b'{"records": [{"pmid": "123", "doi": "10.1016/EXAMPLE"}]}',
                },
                ("GET", crossref): {"url": crossref, "body": json.dumps({"message": {
                    "title": ["Example article"],
                    "URL": "https://www.sciencedirect.com/science/article/pii/example",
                }}).encode()},
            })
            cli.RuntimeContext = lambda **kw: RuntimeContext(env={}, transport=transport, **kw)
            raise SystemExit(cli.main(sys.argv[1:]))
        """,
    )
    assert process.returncode == 0, process.stderr
    (line,) = process.stdout.splitlines()
    result = json.loads(line)
    assert result["contract"] == "paper-fetch/resolve" and result["index"] == 1
    assert result["status"] == "ok" and result["doi"] == "10.1016/example"
    assert (
        result["provider_hint"] == "elsevier" and result["title"] == "Example article"
    )
    assert result["landing_url"].startswith("https://www.sciencedirect.com/")


def test_resolve_exhausted_incomplete_read_keeps_identity_diagnostics():
    process = run_cli(
        "resolve",
        "--query",
        "https://example.test/landing",
        script="""
            import sys
            from http.client import IncompleteRead
            from paper_fetch import cli
            from paper_fetch.http import HttpTransport
            from paper_fetch.runtime import RuntimeContext
            from tests.support.http_cache import FakeHTTPResponse

            transport = HttpTransport()
            def incomplete(request, **kwargs):
                response = FakeHTTPResponse(b"", request.full_url)
                def read(*args, **kwargs):
                    raise IncompleteRead(b"broken", 20)
                response.read = read
                return response
            transport._perform_request = incomplete
            cli.RuntimeContext = lambda **kw: RuntimeContext(env={}, transport=transport, **kw)
            raise SystemExit(cli.main(sys.argv[1:]))
        """,
    )
    assert process.returncode == 1, process.stderr
    result = json.loads(process.stdout)
    assert result["status"] == "failed"
    assert {
        key: result["error"][key]
        for key in ("provider", "stage", "error_category", "retryable")
    } == {
        "provider": "resolver",
        "stage": "identity",
        "error_category": "connection_closed",
        "retryable": True,
    }


def test_check_progress_keeps_stdout_jsonl():
    process = run_cli(
        "check",
        "--query",
        "10.1000/example",
        "--progress",
        "jsonl",
        script="""
            import sys
            from paper_fetch import cli, service
            from paper_fetch.workflow.types import HasFulltextProbeResult
            service.probe_has_fulltext = lambda query, **kw: HasFulltextProbeResult(
                query=query, doi=query, title="Example", state="available",
                evidence=[], warnings=[],
            )
            raise SystemExit(cli.main(sys.argv[1:]))
        """,
    )
    assert process.returncode == 0, process.stderr
    (line,) = process.stdout.splitlines()
    result = json.loads(line)
    assert result["contract"] == "paper-fetch/check" and result["status"] == "ok"
    assert result["doi"] == "10.1000/example"


def test_resolve_challenge_url_is_unresolved():
    process = run_cli(
        "resolve",
        "--query",
        "https://example.test/challenge",
        script="""
            import sys
            from paper_fetch import cli
            from paper_fetch.runtime import RuntimeContext
            from tests.support._paper_fetch_support import RecordingTransport

            url = "https://example.test/challenge"
            transport = RecordingTransport({
                ("GET", url): {"url": url, "status_code": 200, "body": b"<title>Just a moment...</title>"},
            })
            cli.RuntimeContext = lambda **kw: RuntimeContext(env={}, transport=transport, **kw)
            raise SystemExit(cli.main(sys.argv[1:]))
        """,
    )
    assert process.returncode == 1, process.stderr
    result = json.loads(process.stdout)
    assert result["status"] == "unresolved"
    assert (
        result["doi"] is None
        and result["title"] is None
        and result["landing_url"] is None
    )


def test_check_provider_transport_failure_retains_probe_diagnostics():
    process = run_cli(
        "check",
        "--query",
        "10.1016/example",
        script="""
            import sys
            from paper_fetch import cli, service
            from paper_fetch.http import RequestFailure
            from paper_fetch.runtime import RuntimeContext
            from paper_fetch.resolve.query import ResolvedQuery
            from paper_fetch.workflow.routing import probe_has_fulltext

            class Provider:
                def fetch_metadata(self, query):
                    raise RequestFailure(503, "HTTP 503", retryable=True)

            def resolve(query, **kwargs):
                return ResolvedQuery(query, "doi", doi=query, provider_hint="elsevier")

            cli.RuntimeContext = lambda **kw: RuntimeContext(env={}, clients={"elsevier": Provider()}, **kw)
            service.probe_has_fulltext = lambda query, context: probe_has_fulltext(query, context=context, resolve_paper_fn=resolve)
            raise SystemExit(cli.main(sys.argv[1:]))
        """,
    )
    assert process.returncode == 0, process.stderr
    result = json.loads(process.stdout)
    assert result["state"] == "unknown"
    assert result["probe_failures"] == [
        {
            "provider": "elsevier",
            "stage": "metadata",
            "http_status": 503,
            "error_category": None,
            "retryable": True,
        }
    ]
