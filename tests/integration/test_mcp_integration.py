from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from tests.paths import REPO_ROOT, SRC_DIR


SERVER_SCRIPT = textwrap.dedent(
    """
    import logging
    from pathlib import Path

    from paper_fetch.models import ArticleModel, Asset, FetchEnvelope, Metadata, Quality, Section
    from paper_fetch.mcp.server import main
    from paper_fetch.resolve.query import ResolvedQuery
    from paper_fetch.utils import sanitize_filename
    import paper_fetch.mcp.tools as tools

    def fake_resolve(query, *, transport=None, env=None):
        return ResolvedQuery(
            query=query,
            query_kind="doi",
            doi=query if query.startswith("10.") else "10.1000/example",
            landing_url="https://example.test/article",
            provider_hint="crossref",
            confidence=1.0,
            candidates=[],
            title="Example Article",
        )

    def fake_fetch(query, *, modes=None, strategy=None, render=None, download_dir=None, clients=None, html_client=None, transport=None, env=None):
        figure_path = None
        if download_dir is not None:
            output_dir = Path(download_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            base = sanitize_filename(query)
            (output_dir / f"{base}.xml").write_text("<article />", encoding="utf-8")
            (output_dir / f"{base}.md").write_text("# Example Article\\n\\nExample body.\\n", encoding="utf-8")
            asset_dir = output_dir / f"{base}_assets"
            asset_dir.mkdir(parents=True, exist_ok=True)
            figure_path = asset_dir / "figure-1.png"
            figure_path.write_bytes(b"PNG")

        logging.getLogger("paper_fetch.service").debug("fetch_stage query=%s step=%s", query, "fake")

        article = ArticleModel(
            doi=query,
            source="crossref_meta",
            metadata=Metadata(
                title=f"Example Article for {query}",
                authors=["Alice Example"],
                abstract="Example abstract",
                journal="Example Journal",
                published="2026-01-01",
            ),
            sections=[Section(heading="Introduction", level=2, kind="body", text="Example body.")],
            references=[],
            assets=[
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Example inline figure.",
                    path=str(figure_path) if figure_path is not None else None,
                    section="body",
                )
            ],
            quality=Quality(
                has_fulltext=True,
                token_estimate=64,
                warnings=[],
                source_trail=["source:ok"],
            ),
        )
        requested_modes = set(modes or set())
        return FetchEnvelope(
            doi=query,
            source="elsevier_xml",
            has_fulltext=True,
            warnings=[],
            source_trail=["source:ok"],
            token_estimate=64,
            article=article if "article" in requested_modes else None,
            markdown="# Example Article\\n\\nExample body.\\n" if "markdown" in requested_modes else None,
            metadata=article.metadata if "metadata" in requested_modes else None,
        )

    tools.service_resolve_paper = fake_resolve
    tools.service_fetch_paper = fake_fetch
    main()
    """
)


class McpStdioIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_server_lists_tools_and_serves_cached_resources(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "default"
            isolated_dir = Path(tmpdir) / "isolated"
            progress_updates: list[tuple[float, float | None, str | None]] = []
            log_messages: list[object] = []
            server = StdioServerParameters(
                command=sys.executable,
                args=["-c", SERVER_SCRIPT],
                cwd=str(REPO_ROOT),
                env={
                    "PYTHONPATH": str(SRC_DIR),
                    "PAPER_FETCH_DOWNLOAD_DIR": str(default_dir),
                },
            )

            with tempfile.TemporaryFile(mode="w+") as errlog:
                async with stdio_client(server, errlog=errlog) as (read_stream, write_stream):
                    async def logging_callback(params) -> None:
                        log_messages.append(params.data)

                    async def progress_callback(progress, total, message) -> None:
                        progress_updates.append((progress, total, message))

                    async with ClientSession(read_stream, write_stream, logging_callback=logging_callback) as session:
                        await session.initialize()

                        listed = await session.list_tools()
                        tool_names = sorted(tool.name for tool in listed.tools)
                        self.assertEqual(
                            tool_names,
                            ["batch_check", "batch_resolve", "fetch_paper", "get_cached", "list_cached", "resolve_paper"],
                        )

                        resolved = await session.call_tool("resolve_paper", {"query": "10.1000/example"})
                        self.assertFalse(resolved.isError)
                        self.assertEqual(resolved.structuredContent["doi"], "10.1000/example")
                        structured_resolved = await session.call_tool(
                            "resolve_paper",
                            {"title": "Example title", "authors": ["Alice Example"], "year": 2024},
                        )
                        self.assertFalse(structured_resolved.isError)
                        self.assertEqual(structured_resolved.structuredContent["query"], "Example title Alice Example 2024")

                        custom_fetch = await session.call_tool(
                            "fetch_paper",
                            {
                                "query": "10.1000/custom",
                                "download_dir": str(isolated_dir),
                                "modes": ["markdown"],
                                "strategy": {"asset_profile": "body"},
                            },
                            progress_callback=progress_callback,
                        )
                        self.assertFalse(custom_fetch.isError)
                        self.assertEqual(custom_fetch.structuredContent["article"], None)
                        self.assertEqual([content.type for content in custom_fetch.content], ["text", "text", "image"])
                        self.assertEqual(progress_updates[-1], (4, 4, "fetch_paper complete"))
                        self.assertTrue(any(isinstance(message, dict) and message.get("event") == "fetch_stage" for message in log_messages))
                        custom_cached = await session.call_tool(
                            "get_cached",
                            {"doi": "10.1000/custom", "download_dir": str(isolated_dir)},
                        )
                        self.assertFalse(custom_cached.isError)
                        self.assertEqual(custom_cached.structuredContent["status"], "hit")
                        self.assertEqual(len(custom_cached.structuredContent["entries"]), 3)

                        listed_custom = await session.call_tool("list_cached", {"download_dir": str(isolated_dir)})
                        self.assertFalse(listed_custom.isError)
                        self.assertEqual(len(listed_custom.structuredContent["entries"]), 3)

                        batch = await session.call_tool(
                            "batch_check",
                            {"queries": ["10.1000/custom", "10.1000/other"], "mode": "metadata"},
                        )
                        self.assertFalse(batch.isError)
                        self.assertEqual(batch.structuredContent["mode"], "metadata")
                        self.assertEqual(len(batch.structuredContent["results"]), 2)

                        default_fetch = await session.call_tool("fetch_paper", {"query": "10.1000/default"})
                        self.assertFalse(default_fetch.isError)

                        resources = await session.list_resources()
                        resource_uris = sorted(str(resource.uri) for resource in resources.resources)
                        self.assertIn("resource://paper-fetch/cache-index", resource_uris)
                        self.assertTrue(any(uri.startswith("resource://paper-fetch/cached/") for uri in resource_uris))

                        templates = await session.list_resource_templates()
                        template_uris = [str(template.uriTemplate) for template in templates.resourceTemplates]
                        self.assertIn("resource://paper-fetch/cached/{entry_id}", template_uris)

                        cache_index = await session.read_resource("resource://paper-fetch/cache-index")
                        cache_text = cache_index.contents[0].text
                        cache_payload = json.loads(cache_text)
                        self.assertEqual(str(default_dir), cache_payload["download_dir"])
                        markdown_entry = next(
                            entry
                            for entry in cache_payload["entries"]
                            if entry["doi"] == "10.1000/default" and entry["kind"] == "markdown"
                        )

                        markdown_resource = await session.read_resource(
                            f"resource://paper-fetch/cached/{markdown_entry['id']}"
                        )
                        self.assertIn("# Example Article", markdown_resource.contents[0].text)

                        invalid = await session.call_tool("fetch_paper", {"query": "10.1000/example", "modes": ["pdf"]})
                        self.assertTrue(invalid.isError)
                        self.assertEqual(invalid.structuredContent["status"], "error")
                        self.assertIn("unsupported output modes", invalid.structuredContent["reason"])


if __name__ == "__main__":
    unittest.main()
