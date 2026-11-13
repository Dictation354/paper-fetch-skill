"""Actual stdio and file contracts with a synthetic provider boundary."""

from __future__ import annotations


import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import textwrap

from mcp import Client
from mcp.client.stdio import StdioServerParameters
import pytest

from paper_fetch.mcp.fetch_tool import fetch_paper_payload
from tests.paths import REPO_ROOT
from tests.support._mcp_support import mcp_test_deps, sample_envelope


SERVER = textwrap.dedent("""
    from dataclasses import replace
    from paper_fetch.mcp import server
    from paper_fetch.mcp._deps import default_mcp_deps
    from paper_fetch.http import HttpTransport
    from paper_fetch.runtime import RuntimeContext
    from tests.support._mcp_support import sample_envelope, sample_resolved_query

    counts = {}
    def fake_fetch(query, *, modes, **kwargs):
        counts[query] = counts.get(query, 0) + 1
        if counts[query] > 1:
            raise AssertionError("provider was fetched twice")
        envelope = sample_envelope(modes=modes, doi=query)
        if envelope.markdown is not None:
            envelope.markdown = "## 中文😀\\n\\n" + "片段𐐷😀 $x$\\n" * 1000
        return envelope

    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected network or runtime preparation")
    HttpTransport.request = forbidden
    RuntimeContext.prepare_fetch_browser = forbidden
    deps = replace(default_mcp_deps(), service_fetch_paper=fake_fetch, service_resolve_paper=sample_resolved_query)
    server.default_mcp_deps = lambda: deps
    server.main()
""")


def parameters(tmp_path):
    return StdioServerParameters(
        command=sys.executable,
        args=["-c", SERVER],
        cwd=str(REPO_ROOT),
        env={
            **os.environ,
            "PYTHONPATH": str(REPO_ROOT / "src") + os.pathsep + str(REPO_ROOT),
            "PAPER_FETCH_DOWNLOAD_DIR": str(tmp_path / "downloads"),
        },
    )


def test_stdio_handles_page_unicode_batch_aliases_and_do_not_refetch_or_write(tmp_path):
    async def exercise():
        async with Client(parameters(tmp_path)) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            tool = tools["read_content"]
            assert tool.annotations.read_only_hint
            assert tool.annotations.open_world_hint is False
            assert tool.output_schema is None
            arguments = dict(
                modes=["markdown"],
                no_download=True,
                prefer_cache=False,
                artifact_mode="none",
                strategy={"asset_profile": "none"},
            )
            fetched = await client.call_tool(
                "fetch_paper", {"query": "10.1000/example", **arguments}
            )
            assert not fetched.is_error
            p = fetched.structured_content
            assert fetched.content == []
            assert "article" not in p and "markdown" not in p
            ref = p["content_ref"]
            assert set(ref["views"]) == {"markdown", "diagnostics"}
            assert p["metadata"]["title"] == "Example Article"

            async def collect(ref, view):
                offset = 0
                chunks = []
                while True:
                    r = await client.call_tool(
                        "read_content",
                        dict(
                            content_id=ref["content_id"],
                            view=view,
                            offset=offset,
                            max_chars=1999,
                        ),
                    )
                    assert not r.is_error
                    part = r.structured_content
                    chunks.append(part["text"])
                    offset = part["next_offset"]
                    if part["eof"]:
                        assert offset == part["total_chars"]
                        return "".join(chunks)

            expected = "## 中文😀\n\n" + "片段𐐷😀 $x$\n" * 1000
            assert await collect(ref, "markdown") == expected
            # A follow-up reuses the same retained representation.
            assert await collect(ref, "markdown") == expected
            assert (
                json.loads(await collect(ref, "diagnostics"))["acceptance"]["identity"][
                    "status"
                ]
                == "resolved"
            )
            batch = await client.call_tool(
                "batch_fetch",
                {
                    "queries": ["10.1000/batch", "https://doi.org/10.1000/batch"],
                    **arguments,
                },
            )
            assert not batch.is_error
            items = batch.structured_content["results"]
            assert [item["index"] for item in items] == [1, 2]
            assert items[0]["content_ref"] == items[1]["content_ref"]
            assert await collect(items[0]["content_ref"], "markdown") == expected
        # A new service instance cannot resolve another instance's handle.
        async with Client(parameters(tmp_path)) as other:
            result = await other.call_tool(
                "read_content", {"content_id": ref["content_id"]}
            )
            assert result.is_error
            assert result.structured_content["code"] == "content_handle_expired"

    asyncio.run(exercise())
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.parametrize("filename", [None, "chosen"])
def test_single_saving_returns_real_default_or_normalized_path_in_sync_payload(
    tmp_path, filename
):
    calls = []

    def fetch(request, **kwargs):
        calls.append(request)
        return sample_envelope(modes=request.requested_modes())

    p = fetch_paper_payload(
        query="10.1000/example",
        save_markdown=True,
        markdown_output_dir=str(tmp_path),
        markdown_filename=filename,
        no_download=True,
        artifact_mode="none",
        strategy={"asset_profile": "none"},
        deps=mcp_test_deps(fetch_paper_envelope=fetch),
    )
    assert "article" not in p and "markdown" not in p
    artifact = p["output_artifacts"][0]
    path = Path(artifact["path"])
    assert path.is_absolute() and path.is_file()
    if filename:
        assert path.name == "chosen.md"
    assert artifact["size"] == path.stat().st_size
    assert artifact["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert artifact["verification_status"] == "verified"
    assert artifact["completed_at"]


def test_stdio_cache_hit_saving_has_snapshots_and_handles_stay_out_of_persistent_outputs(
    tmp_path,
):
    async def exercise():
        async with Client(parameters(tmp_path)) as client:
            arguments = dict(
                query="10.1000/cache",
                preset="cacheable_read",
                modes=["article", "markdown"],
                artifact_mode="none",
                strategy={"asset_profile": "none"},
                download_dir=str(tmp_path / "cache"),
            )
            fetched = await client.call_tool("fetch_paper", arguments)
            assert not fetched.is_error
            saved = await client.call_tool(
                "fetch_paper",
                {
                    **arguments,
                    "prefer_cache": True,
                    "save_markdown": True,
                    "markdown_output_dir": str(tmp_path / "papers"),
                },
            )
            assert not saved.is_error
            artifact = saved.structured_content["output_artifacts"][0]
            path = Path(artifact["path"])
            assert path.is_file() and path.is_absolute()
            assert artifact["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
            read = await client.call_tool(
                "read_content",
                {"content_id": saved.structured_content["content_ref"]["content_id"]},
            )
            assert not read.is_error and read.structured_content["text"]
            results_path = tmp_path / "batch.jsonl"
            batch = await client.call_tool(
                "batch_fetch",
                {
                    "queries": ["10.1000/other"],
                    "modes": ["markdown"],
                    "no_download": True,
                    "artifact_mode": "none",
                    "strategy": {"asset_profile": "none"},
                    "batch_results": str(results_path),
                },
            )
            assert not batch.is_error
            assert batch.structured_content["results"][0]["content_ref"]
        for path in tmp_path.rglob("*"):
            if path.is_file():
                data = path.read_text(encoding="utf-8")
                assert '"content_ref"' not in data and '"content_id"' not in data

    asyncio.run(exercise())


def test_single_artifact_snapshot_includes_existing_diagnostic_files(tmp_path):
    from paper_fetch.mcp.fetch_tool import build_fetch_tool_result
    from paper_fetch.mcp.schemas import FetchPaperRequest

    envelope = sample_envelope(modes={"markdown"})
    diagnostic = tmp_path / "diagnostic.json"
    diagnostic.write_text('{"reason":"example"}', encoding="utf-8")
    envelope.diagnostic_artifacts = [
        {"path": str(diagnostic), "route": "xml_api", "failure_code": "example"}
    ]
    result = build_fetch_tool_result(envelope, FetchPaperRequest(query=envelope.doi))
    artifact = result.structured_content["output_artifacts"][0]
    assert artifact["path"] == str(diagnostic.resolve())
    assert artifact["kind"] == "diagnostic"
    assert artifact["verification_status"] == "verified"
    assert artifact["sha256"] == hashlib.sha256(diagnostic.read_bytes()).hexdigest()


def test_stdio_rejects_removed_fetch_parameters(tmp_path):
    async def exercise():
        async with Client(parameters(tmp_path)) as client:
            for tool, arguments in (
                (
                    "fetch_paper",
                    {"query": "10.1000/removed", "content_delivery": "inline"},
                ),
                ("batch_fetch", {"queries": ["10.1000/removed"], "detail": "full"}),
                (
                    "batch_fetch",
                    {"queries": ["10.1000/removed"], "content_max_chars": 100},
                ),
            ):
                result = await client.call_tool(tool, arguments)
                assert result.is_error

    asyncio.run(exercise())
    assert not list(tmp_path.rglob("*"))


@pytest.mark.parametrize("max_bytes,idle_ttl", [(1, 3600), (256 * 1024 * 1024, 0.05)])
def test_stdio_reports_capacity_and_idle_expiry(tmp_path, max_bytes, idle_ttl):
    async def exercise():
        args = parameters(tmp_path)
        setup = (
            "from paper_fetch.mcp.content_store import ContentStore\n"
            f"server.ContentStore = lambda: ContentStore(max_bytes={max_bytes}, idle_ttl={idle_ttl})\n"
        )
        args.args = ["-c", SERVER.replace("server.main()", setup + "server.main()")]
        async with Client(args) as client:
            result = await client.call_tool("fetch_paper", {"query": "10.1000/bounded"})
            assert not result.is_error
            assert result.content == []
            payload = result.structured_content
            if max_bytes == 1:
                assert payload["content_ref"] is None
                assert "content_store_capacity_exceeded" in payload["warnings"]
                assert payload["acceptance"]["has_fulltext"]
            else:
                ref = payload["content_ref"]
                assert ref is not None
                await asyncio.sleep(0.1)
                expired = await client.call_tool(
                    "read_content", {"content_id": ref["content_id"]}
                )
                assert expired.is_error
                assert expired.content == []
                assert expired.structured_content["code"] == "content_handle_expired"

    asyncio.run(exercise())
    assert not list(tmp_path.rglob("*"))


def test_stdio_requires_explicit_scope_and_archive_uses_markdown_directory(tmp_path):
    async def exercise():
        args = parameters(tmp_path)
        args.env["PAPER_FETCH_DOWNLOAD_DIR"] = ""
        async with Client(args) as client:
            missing = await client.call_tool(
                "fetch_paper",
                {"query": "10.1000/missing-scope", "preset": "cacheable_read"},
            )
            assert missing.is_error
            assert missing.structured_content["code"] == "validation_error"
            batch_missing = await client.call_tool(
                "batch_fetch",
                {"queries": ["10.1000/missing-scope"], "preset": "archive"},
            )
            assert batch_missing.is_error
            directory = tmp_path / "archive"
            result = await client.call_tool(
                "fetch_paper",
                {
                    "query": "10.1000/archive-scope",
                    "preset": "archive",
                    "markdown_output_dir": str(directory),
                },
            )
            assert not result.is_error
            payload = result.structured_content
            assert payload["effective_options"]["download_dir"] == str(
                directory.resolve()
            )
            assert Path(payload["output_artifacts"][0]["path"]).parent == directory

    asyncio.run(exercise())
