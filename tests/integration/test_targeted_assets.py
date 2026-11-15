"""Real subprocess contracts for selected images, with synthetic HTTP responses."""

from __future__ import annotations

import asyncio
import base64
from contextlib import suppress
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

from mcp import Client
from mcp.client.stdio import StdioServerParameters
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

SERVER = SETUP + textwrap.dedent("""
    from dataclasses import replace
    from paper_fetch.mcp import server
    from paper_fetch.mcp._deps import default_mcp_deps
    from tests.support._mcp_support import sample_envelope, sample_resolved_query
    counts = {}
    def fetch(query, *, modes, **kwargs):
        counts[query] = counts.get(query, 0) + 1
        assert counts[query] == 1
        result = sample_envelope(modes=modes, doi=query)
        result.__dict__["_asset_context"] = asset_state()
        result.markdown = "## Results\\n😀 ![Formula](https://example.test/math-1.gif)\\n"
        return result
    deps = replace(default_mcp_deps(), service_fetch_paper=fetch, service_resolve_paper=sample_resolved_query)
    server.default_mcp_deps = lambda: deps
    server.main()
""")


def environment():
    return {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT / "src") + os.pathsep + str(REPO_ROOT),
    }


def test_stdio_directed_images_batch_aliases_offsets_and_shutdown_cleanup():
    paths = []

    async def exercise():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-c", SERVER],
            cwd=str(REPO_ROOT),
            env=environment(),
        )
        async with Client(parameters) as client:
            schemas = {
                tool.name: tool.input_schema
                for tool in (await client.list_tools()).tools
            }
            assert "fetch_assets" in schemas
            assert '"$ref"' not in json.dumps(schemas["fetch_assets"])
            invalid = await client.call_tool(
                "fetch_assets",
                {"content_id": "unknown", "urls": [SOURCE], "kind": "formula"},
            )
            assert invalid.is_error
            batch = await client.call_tool(
                "batch_fetch",
                {"queries": ["10.1000/example", "https://doi.org/10.1000/example"]},
            )
            items = batch.structured_content["results"]
            assert items[0]["content_ref"] == items[1]["content_ref"]
            assert items[0]["image_delivery"]["formula_images"] == 1
            ref = items[0]["content_ref"]["content_id"]
            before = await client.call_tool(
                "read_content", {"content_id": ref, "offset": 12, "max_chars": 9}
            )
            fetched = await client.call_tool(
                "fetch_assets",
                {"content_id": ref, "urls": ["https://example.test/math-1.gif"]},
            )
            assert not fetched.is_error
            assert len(fetched.content) == 1 and fetched.content[0].type == "image"
            assert base64.b64decode(fetched.content[0].data) == GIF
            path = Path(fetched.structured_content["results"][0]["path"])
            paths.append(path)
            assert path.read_bytes() == GIF
            after = await client.call_tool(
                "read_content", {"content_id": ref, "offset": 12, "max_chars": 9}
            )
            assert before.structured_content == after.structured_content
            formulas = await client.call_tool(
                "fetch_assets",
                {
                    "content_id": ref,
                    "kind": "formula",
                    "inline_image_budget": {"max_images": 1},
                },
            )
            assert len(formulas.content) == 1
            results = formulas.structured_content["results"]
            assert [item["kind"] for item in results] == ["formula", "formula"]
            assert results[0]["path"] == str(path)
            assert results[1]["inline_reason"] == "image_count_limit"
            assert all(Path(item["path"]).is_file() for item in results)
            paths.extend(Path(item["path"]) for item in results)
            expired = await client.call_tool(
                "fetch_assets", {"content_id": "expired", "kind": "formula"}
            )
            assert (
                expired.is_error
                and expired.structured_content["code"] == "content_handle_expired"
            )
        assert all(not path.exists() for path in paths)

    asyncio.run(exercise())


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
