from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from paper_fetch.mcp.cache_index import (
    cache_scope_id,
    scoped_cache_index_resource_uri,
    scoped_cached_resource_uri,
    scoped_cached_resource_uri_prefix,
)
from tests.paths import REPO_ROOT, SRC_DIR


SERVER_SCRIPT = textwrap.dedent(
    """
    import logging
    from pathlib import Path

    from paper_fetch.models import ArticleModel, Asset, FetchEnvelope, Metadata, Quality, Section, TokenEstimateBreakdown
    from paper_fetch.mcp.server import main
    from paper_fetch.providers.base import ProviderStatusResult, build_provider_status_check
    from paper_fetch.resolve.query import ResolvedQuery
    from paper_fetch.service import HasFulltextProbeResult
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

        logging.getLogger("paper_fetch.service").debug(
            "fetch_stage message=legacy-fallback",
            extra={"structured_data": {"event": "fetch_stage", "query": query, "step": "fake stage with spaces"}},
        )
        logging.getLogger("paper_fetch.http").debug("legacy_fetch_stage query=%s status=%s", query, "ok")

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
                token_estimate_breakdown=TokenEstimateBreakdown(abstract=16, body=48, refs=20),
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
            token_estimate_breakdown=TokenEstimateBreakdown(abstract=16, body=48, refs=20),
            article=article if "article" in requested_modes else None,
            markdown="# Example Article\\n\\nExample body.\\n" if "markdown" in requested_modes else None,
            metadata=article.metadata if "metadata" in requested_modes else None,
        )

    def fake_probe(query, *, transport=None, env=None):
        return HasFulltextProbeResult(
            query=query,
            doi=query if query.startswith("10.") else "10.1000/example",
            title=f"Example Article for {query}",
            state="likely_yes",
            evidence=["crossref_fulltext_link"],
            warnings=[],
        )

    class FakeProviderClient:
        def __init__(self, result):
            self.result = result
            self.official_provider = result.official_provider

        def probe_status(self):
            return self.result

    def fake_build_clients(*, transport=None, env=None):
        return {
            "crossref": FakeProviderClient(
                ProviderStatusResult(
                    provider="crossref",
                    status="ready",
                    available=True,
                    official_provider=False,
                    notes=["CROSSREF_MAILTO is not configured; adding one is recommended for better API etiquette."],
                    checks=[build_provider_status_check("metadata_api", "ok", "Crossref metadata lookup is available.")],
                )
            ),
            "elsevier": FakeProviderClient(
                ProviderStatusResult(
                    provider="elsevier",
                    status="not_configured",
                    available=False,
                    official_provider=True,
                    missing_env=["ELSEVIER_API_KEY"],
                    checks=[
                        build_provider_status_check(
                            "fulltext_api",
                            "not_configured",
                            "ELSEVIER_API_KEY is required for Elsevier full-text retrieval.",
                            missing_env=["ELSEVIER_API_KEY"],
                        )
                    ],
                )
            ),
            "springer": FakeProviderClient(
                ProviderStatusResult(
                    provider="springer",
                    status="partial",
                    available=True,
                    official_provider=True,
                    missing_env=["SPRINGER_OPENACCESS_API_KEY", "SPRINGER_FULLTEXT_API_KEY", "SPRINGER_FULLTEXT_URL_TEMPLATE"],
                    checks=[
                        build_provider_status_check("metadata_api", "ok", "Springer Meta API credentials are configured."),
                        build_provider_status_check(
                            "openaccess_api",
                            "not_configured",
                            "SPRINGER_OPENACCESS_API_KEY is required for Springer Open Access full-text retrieval.",
                            missing_env=["SPRINGER_OPENACCESS_API_KEY"],
                        ),
                        build_provider_status_check(
                            "fulltext_api",
                            "not_configured",
                            "SPRINGER_FULLTEXT_API_KEY and SPRINGER_FULLTEXT_URL_TEMPLATE are required for Springer Full Text API retrieval.",
                            missing_env=["SPRINGER_FULLTEXT_API_KEY", "SPRINGER_FULLTEXT_URL_TEMPLATE"],
                        ),
                    ],
                )
            ),
            "wiley": FakeProviderClient(
                ProviderStatusResult(
                    provider="wiley",
                    status="not_configured",
                    available=False,
                    official_provider=True,
                    missing_env=["WILEY_TDM_URL_TEMPLATE", "WILEY_TDM_TOKEN"],
                    checks=[
                        build_provider_status_check(
                            "fulltext_api",
                            "not_configured",
                            "WILEY_TDM_URL_TEMPLATE and WILEY_TDM_TOKEN are required for Wiley full-text retrieval.",
                            missing_env=["WILEY_TDM_URL_TEMPLATE", "WILEY_TDM_TOKEN"],
                        )
                    ],
                )
            ),
            "science": FakeProviderClient(
                ProviderStatusResult(
                    provider="science",
                    status="not_configured",
                    available=False,
                    official_provider=True,
                    missing_env=["FLARESOLVERR_ENV_FILE"],
                    checks=[
                        build_provider_status_check(
                            "runtime_env",
                            "not_configured",
                            "FLARESOLVERR_ENV_FILE is required.",
                            missing_env=["FLARESOLVERR_ENV_FILE"],
                        ),
                        build_provider_status_check("repo_local_workflow", "not_configured", "Skipped because runtime_env is not configured."),
                        build_provider_status_check("flaresolverr_health", "not_configured", "Skipped because runtime_env is not configured."),
                        build_provider_status_check("rate_limit_window", "not_configured", "Skipped because runtime_env is not configured."),
                    ],
                )
            ),
            "pnas": FakeProviderClient(
                ProviderStatusResult(
                    provider="pnas",
                    status="ready",
                    available=True,
                    official_provider=True,
                    checks=[
                        build_provider_status_check("runtime_env", "ok", "pnas runtime environment is configured."),
                        build_provider_status_check("repo_local_workflow", "ok", "Repo-local FlareSolverr workflow files are available."),
                        build_provider_status_check("flaresolverr_health", "ok", "Local FlareSolverr health check passed."),
                        build_provider_status_check("rate_limit_window", "ok", "Local Science/PNAS rate-limit window allows a new request."),
                    ],
                )
            ),
        }

    tools.service_resolve_paper = fake_resolve
    tools.service_fetch_paper = fake_fetch
    tools.service_probe_has_fulltext = fake_probe
    tools.build_clients = fake_build_clients
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
                            [
                                "batch_check",
                                "batch_resolve",
                                "fetch_paper",
                                "get_cached",
                                "has_fulltext",
                                "list_cached",
                                "provider_status",
                                "resolve_paper",
                            ],
                        )
                        self.assertTrue(all(tool.outputSchema is not None for tool in listed.tools))
                        self.assertTrue(all(tool.annotations is not None for tool in listed.tools))

                        prompts = await session.list_prompts()
                        self.assertEqual(
                            sorted(prompt.name for prompt in prompts.prompts),
                            ["summarize_paper", "verify_citation_list"],
                        )
                        summarize_prompt = await session.get_prompt(
                            "summarize_paper",
                            {"query": "10.1000/example", "focus": "methods"},
                        )
                        self.assertIn("token_estimate_breakdown", summarize_prompt.messages[0].content.text)
                        verify_prompt = await session.get_prompt(
                            "verify_citation_list",
                            {"citations": "Citation A\\nCitation B", "mode": "metadata"},
                        )
                        self.assertIn("batch_check", verify_prompt.messages[0].content.text)

                        resolved = await session.call_tool("resolve_paper", {"query": "10.1000/example"})
                        self.assertFalse(resolved.isError)
                        self.assertEqual(resolved.structuredContent["doi"], "10.1000/example")
                        structured_resolved = await session.call_tool(
                            "resolve_paper",
                            {"title": "Example title", "authors": ["Alice Example"], "year": 2024},
                        )
                        self.assertFalse(structured_resolved.isError)
                        self.assertEqual(structured_resolved.structuredContent["query"], "Example title Alice Example 2024")

                        probe = await session.call_tool("has_fulltext", {"query": "10.1000/example"})
                        self.assertFalse(probe.isError)
                        self.assertEqual(probe.structuredContent["state"], "likely_yes")
                        self.assertEqual(probe.structuredContent["evidence"], ["crossref_fulltext_link"])

                        provider_status = await session.call_tool("provider_status", {})
                        self.assertFalse(provider_status.isError)
                        self.assertEqual(
                            [item["provider"] for item in provider_status.structuredContent["providers"]],
                            ["crossref", "elsevier", "springer", "wiley", "science", "pnas"],
                        )
                        self.assertEqual(provider_status.structuredContent["providers"][0]["status"], "ready")
                        self.assertEqual(provider_status.structuredContent["providers"][1]["missing_env"], ["ELSEVIER_API_KEY"])

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
                        self.assertEqual(
                            custom_fetch.structuredContent["token_estimate_breakdown"],
                            {"abstract": 16, "body": 48, "refs": 20},
                        )
                        self.assertEqual([content.type for content in custom_fetch.content], ["text", "text", "image"])
                        self.assertEqual(progress_updates[-1], (4, 4, "fetch_paper complete"))
                        self.assertTrue(
                            any(
                                isinstance(message, dict)
                                and message.get("event") == "fetch_stage"
                                and message.get("step") == "fake stage with spaces"
                                for message in log_messages
                            )
                        )
                        self.assertTrue(
                            any(
                                isinstance(message, dict)
                                and message.get("event") == "legacy_fetch_stage"
                                and message.get("query") == "10.1000/custom"
                                for message in log_messages
                            )
                        )
                        custom_cached = await session.call_tool(
                            "get_cached",
                            {"doi": "10.1000/custom", "download_dir": str(isolated_dir)},
                        )
                        self.assertFalse(custom_cached.isError)
                        self.assertEqual(custom_cached.structuredContent["status"], "hit")
                        self.assertEqual(len(custom_cached.structuredContent["entries"]), 4)

                        listed_custom = await session.call_tool("list_cached", {"download_dir": str(isolated_dir)})
                        self.assertFalse(listed_custom.isError)
                        self.assertEqual(len(listed_custom.structuredContent["entries"]), 4)

                        batch = await session.call_tool(
                            "batch_check",
                            {"queries": ["10.1000/custom", "10.1000/other"], "mode": "metadata", "concurrency": 2},
                        )
                        self.assertFalse(batch.isError)
                        self.assertEqual(batch.structuredContent["mode"], "metadata")
                        self.assertEqual(len(batch.structuredContent["results"]), 2)
                        self.assertEqual(batch.structuredContent["results"][0]["probe_state"], "likely_yes")
                        self.assertEqual(batch.structuredContent["results"][0]["source"], None)
                        self.assertEqual(batch.structuredContent["results"][0]["token_estimate_breakdown"], None)

                        batch_resolved = await session.call_tool(
                            "batch_resolve",
                            {"queries": ["10.1000/custom", "10.1000/other"], "concurrency": 2},
                        )
                        self.assertFalse(batch_resolved.isError)
                        self.assertEqual(
                            [item["doi"] for item in batch_resolved.structuredContent["results"]],
                            ["10.1000/custom", "10.1000/other"],
                        )

                        default_fetch = await session.call_tool("fetch_paper", {"query": "10.1000/default"})
                        self.assertFalse(default_fetch.isError)

                        resources = await session.list_resources()
                        resource_uris = sorted(str(resource.uri) for resource in resources.resources)
                        self.assertIn("resource://paper-fetch/cache-index", resource_uris)
                        self.assertTrue(any(uri.startswith("resource://paper-fetch/cached/") for uri in resource_uris))
                        custom_scope_id = cache_scope_id(isolated_dir)
                        custom_index_uri = scoped_cache_index_resource_uri(custom_scope_id)
                        self.assertIn(custom_index_uri, resource_uris)
                        self.assertTrue(
                            any(uri.startswith(scoped_cached_resource_uri_prefix(custom_scope_id)) for uri in resource_uris)
                        )

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

                        custom_cache_index = await session.read_resource(custom_index_uri)
                        custom_cache_payload = json.loads(custom_cache_index.contents[0].text)
                        self.assertEqual(str(isolated_dir), custom_cache_payload["download_dir"])
                        custom_markdown_entry = next(
                            entry
                            for entry in custom_cache_payload["entries"]
                            if entry["doi"] == "10.1000/custom" and entry["kind"] == "markdown"
                        )
                        custom_markdown_resource = await session.read_resource(
                            scoped_cached_resource_uri(custom_scope_id, custom_markdown_entry["id"])
                        )
                        self.assertIn("# Example Article", custom_markdown_resource.contents[0].text)

                        invalid = await session.call_tool("fetch_paper", {"query": "10.1000/example", "modes": ["pdf"]})
                        self.assertTrue(invalid.isError)
                        self.assertEqual(invalid.structuredContent["status"], "error")
                        self.assertIn("unsupported output modes", invalid.structuredContent["reason"])


if __name__ == "__main__":
    unittest.main()
