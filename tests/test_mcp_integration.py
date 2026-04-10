from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"


SERVER_SCRIPT = textwrap.dedent(
    """
    from paper_fetch.models import ArticleModel, FetchEnvelope, Metadata, Quality, Section
    from paper_fetch.mcp.server import main
    from paper_fetch.resolve.query import ResolvedQuery
    import paper_fetch.mcp.tools as tools

    def fake_resolve(query, *, transport=None, env=None):
        return ResolvedQuery(
            query=query,
            query_kind="doi",
            doi="10.1000/example",
            landing_url="https://example.test/article",
            provider_hint="crossref",
            confidence=1.0,
            candidates=[],
            title="Example Article",
        )

    def fake_fetch(query, *, modes=None, strategy=None, render=None, download_dir=None, clients=None, html_client=None, transport=None, env=None):
        article = ArticleModel(
            doi="10.1000/example",
            source="crossref_meta",
            metadata=Metadata(
                title="Example Article",
                authors=["Alice Example"],
                abstract="Example abstract",
                journal="Example Journal",
                published="2026-01-01",
            ),
            sections=[],
            references=[],
            assets=[],
            quality=Quality(
                has_fulltext=False,
                token_estimate=64,
                warnings=["metadata only"],
                source_trail=["fallback:metadata_only"],
            ),
        )
        return FetchEnvelope(
            doi="10.1000/example",
            source="metadata_only",
            has_fulltext=False,
            warnings=["metadata only"],
            source_trail=["fallback:metadata_only"],
            token_estimate=64,
            article=article if "article" in (modes or set()) else None,
            markdown="# Example Article\\n\\nMetadata only.\\n" if "markdown" in (modes or set()) else None,
            metadata=article.metadata if "metadata" in (modes or set()) else None,
        )

    tools.service_resolve_paper = fake_resolve
    tools.service_fetch_paper = fake_fetch
    main()
    """
)


class McpStdioIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_server_lists_tools_and_returns_structured_results(self) -> None:
        server = StdioServerParameters(
            command=sys.executable,
            args=["-c", SERVER_SCRIPT],
            cwd=str(REPO_ROOT),
            env={"PYTHONPATH": str(SRC_DIR)},
        )

        with tempfile.TemporaryFile(mode="w+") as errlog:
            async with stdio_client(server, errlog=errlog) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()

                    listed = await session.list_tools()
                    tool_names = sorted(tool.name for tool in listed.tools)
                    self.assertEqual(tool_names, ["fetch_paper", "resolve_paper"])

                    resolved = await session.call_tool("resolve_paper", {"query": "10.1000/example"})
                    self.assertFalse(resolved.isError)
                    self.assertEqual(resolved.structuredContent["doi"], "10.1000/example")

                    fetched = await session.call_tool("fetch_paper", {"query": "10.1000/example", "modes": ["metadata"]})
                    self.assertFalse(fetched.isError)
                    self.assertEqual(fetched.structuredContent["source"], "metadata_only")
                    self.assertEqual(fetched.structuredContent["article"], None)
                    self.assertEqual(fetched.structuredContent["metadata"]["title"], "Example Article")

                    invalid = await session.call_tool("fetch_paper", {"query": "10.1000/example", "modes": ["pdf"]})
                    self.assertTrue(invalid.isError)
                    self.assertEqual(invalid.structuredContent["status"], "error")
                    self.assertIn("unsupported output modes", invalid.structuredContent["reason"])


if __name__ == "__main__":
    unittest.main()
