from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from mcp import types as mcp_types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from paper_fetch.mcp.cache_index import (
    cache_scope_id,
    scoped_cache_index_resource_uri,
    scoped_cached_resource_uri,
    scoped_cached_resource_uri_prefix,
)
from paper_fetch.mcp.provider_catalog import PROVIDER_CATALOG_RESOURCE_URI
from paper_fetch.provider_catalog import SOURCE_PROVIDER_MAP, provider_status_order
from tests.paths import REPO_ROOT, SRC_DIR


SERVER_SCRIPT = textwrap.dedent(
    """
    import logging
    from pathlib import Path

    from paper_fetch.models import ArticleModel, Asset, FetchEnvelope, Metadata, Quality, Section, TokenEstimateBreakdown
    from dataclasses import replace

    from paper_fetch.browser_preflight import BrowserPreflightResult
    from paper_fetch.mcp import server as mcp_server
    from paper_fetch.mcp._deps import default_mcp_deps
    from paper_fetch.mcp.server import main
    from paper_fetch.providers.base import ProviderStatusResult, build_provider_status_check
    from paper_fetch.resolve.query import ResolvedQuery
    from paper_fetch.service import HasFulltextProbeResult
    from paper_fetch.utils import sanitize_filename

    def fake_resolve(query, *, context=None):
        lookup_query = query.lookup_query if hasattr(query, "lookup_query") else query
        return ResolvedQuery(
            query=lookup_query,
            query_kind="doi",
            doi=lookup_query if lookup_query.startswith("10.") else "10.1000/example",
            landing_url="https://example.test/article",
            provider_hint="crossref",
            confidence=1.0,
            candidates=[],
            title="Example Article",
        )

    def fake_fetch(query, *, modes=None, strategy=None, render=None, context=None):
        figure_path = None
        download_dir = context.download_dir if context is not None else None
        if download_dir is not None:
            output_dir = Path(download_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            base = sanitize_filename(query)
            (output_dir / f"{base}.xml").write_text("<article />", encoding="utf-8")
            (output_dir / f"{base}.md").write_text(
                (
                    "---\\n"
                    f'doi: "{query}"\\n'
                    'source: "crossref_meta"\\n'
                    "has_fulltext: true\\n"
                    'content_kind: "fulltext"\\n'
                    "---\\n\\n# Example Article\\n\\nExample body.\\n"
                ),
                encoding="utf-8",
            )
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

    def fake_probe(query, *, context=None):
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

    def fake_build_clients(*, transport=None, env=None, provider_names=None):
        clients = {
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
                    status="ready",
                    available=True,
                    official_provider=True,
                    checks=[
                        build_provider_status_check(
                            "html_route",
                            "ok",
                            "Springer direct HTML route is available.",
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
                    checks=[
                        build_provider_status_check(
                            "runtime_env",
                            "not_configured",
                            "wiley browser runtime requires Playwright and Camoufox packages.",
                        ),
                        build_provider_status_check(
                            "playwright_dependency",
                            "not_configured",
                            "Playwright Python package is not installed.",
                        ),
                    ],
                )
            ),
            "science": FakeProviderClient(
                ProviderStatusResult(
                    provider="science",
                    status="not_configured",
                    available=False,
                    official_provider=True,
                    checks=[
                        build_provider_status_check(
                            "runtime_env",
                            "not_configured",
                            "science browser runtime requires Playwright and Camoufox packages.",
                        ),
                        build_provider_status_check(
                            "playwright_dependency",
                            "not_configured",
                            "Playwright Python package is not installed.",
                        ),
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
                        build_provider_status_check(
                            "playwright_dependency",
                            "ok",
                            "Playwright Python package is importable; CDP connection is not probed.",
                        ),
                    ],
                )
            ),
            "ieee": FakeProviderClient(
                ProviderStatusResult(
                    provider="ieee",
                    status="ready",
                    available=True,
                    official_provider=True,
                    checks=[
                        build_provider_status_check(
                            "html_route",
                            "ok",
                            "IEEE Xplore dynamic HTML route is available.",
                        ),
                        build_provider_status_check(
                            "pdf_fallback",
                            "ok",
                            "IEEE Xplore PDF fallback is available.",
                        ),
                    ],
                )
            ),
            "arxiv": FakeProviderClient(
                ProviderStatusResult(
                    provider="arxiv",
                    status="ready",
                    available=True,
                    official_provider=True,
                    checks=[
                        build_provider_status_check(
                            "metadata_api",
                            "ok",
                            (
                                "arXiv API metadata route uses the internal Atom client "
                                "for default metadata enrichment."
                            ),
                        ),
                        build_provider_status_check(
                            "html_route",
                            "ok",
                            "arXiv official HTML fallback is available.",
                        ),
                        build_provider_status_check(
                            "pdf_fallback",
                            "ok",
                            "arXiv PDF fallback is available.",
                        ),
                    ],
                )
            ),
            "copernicus": FakeProviderClient(
                ProviderStatusResult(
                    provider="copernicus",
                    status="ready",
                    available=True,
                    official_provider=True,
                    checks=[
                        build_provider_status_check(
                            "xml_route",
                            "ok",
                            "Copernicus direct NLM/JATS XML route is available.",
                        ),
                        build_provider_status_check(
                            "pdf_fallback",
                            "ok",
                            "Copernicus PDF fallback is available.",
                        ),
                    ],
                )
            ),
            "ams": FakeProviderClient(
                ProviderStatusResult(
                    provider="ams",
                    status="ready",
                    available=True,
                    official_provider=True,
                    checks=[
                        build_provider_status_check(
                            "local_requirements",
                            "ok",
                            "AMS direct HTTP HTML route is available.",
                        ),
                    ],
                )
            ),
            "mdpi": FakeProviderClient(
                ProviderStatusResult(
                    provider="mdpi",
                    status="ready",
                    available=True,
                    official_provider=True,
                    checks=[
                        build_provider_status_check("runtime_env", "ok", "mdpi runtime environment is configured."),
                    ],
                )
            ),
        }
        if provider_names is None:
            return clients
        return {
            name: clients[name]
            for name in provider_names
            if name in clients
        }

    def fake_browser_preflight(
        *,
        providers=None,
        target_url=None,
        storage_state_path=None,
        save_storage_state=True,
        on_result=None,
        **kwargs,
    ):
        del kwargs
        provider = list(providers or ["wiley"])[0]
        saved = False
        if storage_state_path is not None and save_storage_state:
            storage_state_path.parent.mkdir(parents=True, exist_ok=True)
            storage_state_path.write_text('{"cookies": []}\\n', encoding="utf-8")
            saved = True
        result = BrowserPreflightResult(
            provider=provider,
            provider_label="Wiley",
            status="ready",
            reason_code="browser_preflight_ready",
            stage="complete",
            target_url=target_url or "https://onlinelibrary.wiley.com/doi/full/10.1111/example",
            final_url=target_url or "https://onlinelibrary.wiley.com/doi/full/10.1111/example",
            title="Wiley preflight sample",
            storage_state_path=storage_state_path,
            diagnostics={
                "browser_runtime_trace": {
                    "storage_state_save": {
                        "attempted": storage_state_path is not None and save_storage_state,
                        "saved": saved,
                        "path": str(storage_state_path) if storage_state_path is not None else None,
                        "reason": None,
                    }
                }
            },
        )
        if on_result is not None:
            on_result(result, 1, 1)
        return [result]

    def fake_default_mcp_deps():
        return replace(
            default_mcp_deps(),
            service_resolve_paper=fake_resolve,
            service_fetch_paper=fake_fetch,
            service_probe_has_fulltext=fake_probe,
            build_clients=fake_build_clients,
            run_browser_provider_preflight=fake_browser_preflight,
        )

    mcp_server.default_mcp_deps = fake_default_mcp_deps
    main()
    """
)


class McpStdioIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_server_lists_tools_and_serves_cached_resources(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "default"
            isolated_dir = Path(tmpdir) / "isolated"
            progress_updates: list[tuple[float, float | None, str | None]] = []
            batch_fetch_progress: list[tuple[float, float | None, str | None]] = []
            preflight_progress: list[tuple[float, float | None, str | None]] = []
            log_messages: list[object] = []
            protocol_messages: list[object] = []
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
                async with stdio_client(server, errlog=errlog) as (
                    read_stream,
                    write_stream,
                ):

                    async def logging_callback(params) -> None:
                        log_messages.append(params.data)

                    async def progress_callback(progress, total, message) -> None:
                        progress_updates.append((progress, total, message))

                    async def preflight_progress_callback(
                        progress, total, message
                    ) -> None:
                        preflight_progress.append((progress, total, message))

                    async def batch_fetch_progress_callback(
                        progress, total, message
                    ) -> None:
                        batch_fetch_progress.append((progress, total, message))

                    async def message_handler(message) -> None:
                        protocol_messages.append(message)

                    async with ClientSession(
                        read_stream,
                        write_stream,
                        logging_callback=logging_callback,
                        message_handler=message_handler,
                    ) as session:
                        init_result = await session.initialize()
                        self.assertIsNotNone(init_result.capabilities.resources)
                        self.assertTrue(init_result.capabilities.resources.list_changed)

                        listed = await session.list_tools()
                        tool_names = sorted(tool.name for tool in listed.tools)
                        self.assertEqual(
                            tool_names,
                            [
                                "batch_check",
                                "batch_fetch",
                                "batch_resolve",
                                "browser_preflight",
                                "fetch_paper",
                                "get_cached",
                                "has_fulltext",
                                "list_cached",
                                "provider_status",
                                "resolve_paper",
                            ],
                        )
                        self.assertTrue(
                            all(tool.output_schema is not None for tool in listed.tools)
                        )
                        self.assertTrue(
                            all(tool.annotations is not None for tool in listed.tools)
                        )
                        batch_fetch_tool = next(
                            tool for tool in listed.tools if tool.name == "batch_fetch"
                        )
                        self.assertEqual(
                            batch_fetch_tool.input_schema["properties"]["queries"][
                                "maxItems"
                            ],
                            50,
                        )
                        self.assertEqual(
                            batch_fetch_tool.input_schema["properties"]["concurrency"][
                                "maximum"
                            ],
                            8,
                        )
                        self.assertEqual(
                            batch_fetch_tool.input_schema["properties"]["detail"][
                                "enum"
                            ],
                            ["compact", "bounded"],
                        )
                        browser_tool = next(
                            tool
                            for tool in listed.tools
                            if tool.name == "browser_preflight"
                        )
                        self.assertFalse(browser_tool.annotations.read_only_hint)
                        self.assertFalse(browser_tool.annotations.destructive_hint)
                        self.assertFalse(browser_tool.annotations.idempotent_hint)
                        self.assertTrue(browser_tool.annotations.open_world_hint)

                        prompts = await session.list_prompts()
                        self.assertEqual(
                            sorted(prompt.name for prompt in prompts.prompts),
                            ["summarize_paper", "verify_citation_list"],
                        )
                        summarize_prompt = await session.get_prompt(
                            "summarize_paper",
                            {"query": "10.1000/example", "focus": "methods"},
                        )
                        self.assertIn(
                            "token_estimate_breakdown",
                            summarize_prompt.messages[0].content.text,
                        )
                        verify_prompt = await session.get_prompt(
                            "verify_citation_list",
                            {
                                "citations": "Citation A\\nCitation B",
                                "mode": "metadata",
                            },
                        )
                        self.assertIn(
                            "batch_check", verify_prompt.messages[0].content.text
                        )

                        resolved = await session.call_tool(
                            "resolve_paper", {"query": "10.1000/example"}
                        )
                        self.assertFalse(resolved.is_error)
                        self.assertEqual(
                            resolved.structured_content["doi"], "10.1000/example"
                        )
                        structured_resolved = await session.call_tool(
                            "resolve_paper",
                            {
                                "title": "Example title",
                                "authors": ["Alice Example"],
                                "year": 2024,
                            },
                        )
                        self.assertFalse(structured_resolved.is_error)
                        self.assertEqual(
                            structured_resolved.structured_content["query"],
                            "Example title",
                        )

                        probe = await session.call_tool(
                            "has_fulltext", {"query": "10.1000/example"}
                        )
                        self.assertFalse(probe.is_error)
                        self.assertEqual(
                            probe.structured_content["state"], "likely_yes"
                        )
                        self.assertEqual(
                            probe.structured_content["evidence"],
                            ["crossref_fulltext_link"],
                        )

                        provider_status = await session.call_tool("provider_status", {})
                        self.assertFalse(
                            provider_status.is_error,
                            provider_status.structured_content,
                        )
                        providers_by_name = {
                            item["provider"]: item
                            for item in provider_status.structured_content["providers"]
                        }
                        self.assertEqual(
                            [
                                item["provider"]
                                for item in provider_status.structured_content[
                                    "providers"
                                ]
                            ],
                            list(provider_status_order()),
                        )
                        self.assertEqual(
                            providers_by_name["crossref"]["status"], "ready"
                        )
                        self.assertEqual(
                            providers_by_name["elsevier"]["missing_env"],
                            ["ELSEVIER_API_KEY"],
                        )
                        self.assertIn("mdpi", providers_by_name)
                        self.assertEqual(providers_by_name["ams"]["provider"], "ams")

                        compact_status = await session.call_tool(
                            "provider_status",
                            {"provider": "crossref", "detail": "compact"},
                        )
                        self.assertFalse(compact_status.is_error)
                        self.assertEqual(
                            compact_status.structured_content["provider_filter"],
                            "crossref",
                        )
                        self.assertEqual(
                            compact_status.structured_content["providers"],
                            [
                                {
                                    "provider": "crossref",
                                    "status": "ready",
                                    "reason_code": "static_requirements_ready",
                                    "reason": (
                                        "Static configuration and local dependencies "
                                        "are ready; remote access was not checked."
                                    ),
                                    "suggested_action": "run the requested fetch",
                                }
                            ],
                        )
                        self.assertNotIn(
                            "configuration", compact_status.structured_content
                        )

                        storage_state_path = isolated_dir / "browser" / "wiley.json"
                        live_preflight = await session.call_tool(
                            "browser_preflight",
                            {
                                "provider": "wiley",
                                "test_url": (
                                    "https://onlinelibrary.wiley.com/doi/full/"
                                    "10.1111/example"
                                ),
                                "storage_state_path": str(storage_state_path),
                                "detail": "full",
                            },
                            progress_callback=preflight_progress_callback,
                        )
                        self.assertFalse(live_preflight.is_error)
                        self.assertEqual(
                            live_preflight.structured_content["status"], "ready"
                        )
                        self.assertEqual(
                            live_preflight.structured_content["results"][0]["status"],
                            "ready",
                        )
                        self.assertEqual(
                            live_preflight.structured_content["results"][0][
                                "storage_state"
                            ]["saved"],
                            True,
                        )
                        self.assertFalse(
                            live_preflight.structured_content["pdf_fallback_attempted"]
                        )
                        self.assertFalse(
                            live_preflight.structured_content["auth_attempted"]
                        )
                        self.assertTrue(storage_state_path.is_file())
                        self.assertEqual(
                            preflight_progress,
                            [
                                (0, 1, "Starting live browser_preflight"),
                                (1, 1, "Preflight wiley: ready"),
                                (1, 1, "browser_preflight complete"),
                            ],
                        )

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
                        self.assertFalse(custom_fetch.is_error)
                        self.assertEqual(
                            custom_fetch.structured_content["status"], "ok"
                        )
                        self.assertEqual(
                            custom_fetch.structured_content["acceptance"]["fetch"],
                            "ok",
                        )
                        self.assertEqual(
                            custom_fetch.structured_content["acceptance"]["content"],
                            "fulltext",
                        )
                        self.assertEqual(
                            custom_fetch.structured_content["acceptance"]["output"],
                            "complete",
                        )
                        self.assertEqual(
                            custom_fetch.structured_content["article"], None
                        )
                        self.assertEqual(
                            custom_fetch.structured_content["token_estimate_breakdown"],
                            {"abstract": 16, "body": 48, "refs": 20},
                        )
                        self.assertEqual(
                            [content.type for content in custom_fetch.content],
                            ["text", "text", "image"],
                        )
                        self.assertEqual(
                            progress_updates[-1], (4, 4, "fetch_paper complete")
                        )
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
                            {
                                "doi": "10.1000/custom",
                                "download_dir": str(isolated_dir),
                            },
                        )
                        self.assertFalse(custom_cached.is_error)
                        self.assertEqual(
                            custom_cached.structured_content["status"], "hit"
                        )
                        self.assertEqual(
                            len(custom_cached.structured_content["entries"]), 4
                        )

                        compact_cached = await session.call_tool(
                            "get_cached",
                            {
                                "doi": "10.1000/custom",
                                "download_dir": str(isolated_dir),
                                "detail": "compact",
                                "preferred_only": True,
                                "modes": ["markdown"],
                                "strategy": {"asset_profile": "body"},
                            },
                        )
                        self.assertFalse(compact_cached.is_error)
                        self.assertEqual(
                            compact_cached.structured_content["status"], "hit"
                        )
                        self.assertNotIn("entries", compact_cached.structured_content)
                        self.assertEqual(
                            set(compact_cached.structured_content["preferred"]),
                            {"markdown", "primary_payload"},
                        )
                        self.assertTrue(
                            compact_cached.structured_content["request_satisfied"],
                            compact_cached.structured_content["sidecar"],
                        )
                        self.assertEqual(
                            len(
                                compact_cached.structured_content[
                                    "cached_request_fingerprint"
                                ]
                            ),
                            64,
                        )

                        listed_custom = await session.call_tool(
                            "list_cached", {"download_dir": str(isolated_dir)}
                        )
                        self.assertFalse(listed_custom.is_error)
                        self.assertEqual(
                            len(listed_custom.structured_content["entries"]), 4
                        )

                        batch = await session.call_tool(
                            "batch_check",
                            {
                                "queries": ["10.1000/custom", "10.1000/other"],
                                "mode": "metadata",
                                "concurrency": 2,
                            },
                        )
                        self.assertFalse(batch.is_error)
                        self.assertEqual(batch.structured_content["mode"], "metadata")
                        self.assertEqual(len(batch.structured_content["results"]), 2)
                        self.assertEqual(
                            batch.structured_content["results"][0]["probe_state"],
                            "likely_yes",
                        )
                        self.assertEqual(
                            batch.structured_content["results"][0]["source"], None
                        )
                        self.assertEqual(
                            batch.structured_content["results"][0][
                                "token_estimate_breakdown"
                            ],
                            None,
                        )

                        batch_resolved = await session.call_tool(
                            "batch_resolve",
                            {
                                "queries": ["10.1000/custom", "10.1000/other"],
                                "concurrency": 2,
                            },
                        )
                        self.assertFalse(batch_resolved.is_error)
                        self.assertEqual(
                            [
                                item["doi"]
                                for item in batch_resolved.structured_content["results"]
                            ],
                            ["10.1000/custom", "10.1000/other"],
                        )

                        batch_fetched = await session.call_tool(
                            "batch_fetch",
                            {
                                "queries": [
                                    "10.1000/batch-one",
                                    "10.1000/batch-two",
                                ],
                                "concurrency": 2,
                                "strategy": {"asset_profile": "none"},
                                "no_download": True,
                                "artifact_mode": "none",
                                "detail": "bounded",
                                "content_max_chars": 24,
                            },
                            progress_callback=batch_fetch_progress_callback,
                        )
                        self.assertFalse(batch_fetched.is_error)
                        self.assertEqual(
                            [
                                item["index"]
                                for item in batch_fetched.structured_content["results"]
                            ],
                            [1, 2],
                        )
                        self.assertEqual(
                            batch_fetched.structured_content["content_returned_chars"],
                            24,
                        )
                        self.assertTrue(
                            all(
                                "article" not in item and "markdown" not in item
                                for item in batch_fetched.structured_content["results"]
                            )
                        )
                        self.assertEqual(
                            batch_fetch_progress[0],
                            (0, 2, "Starting batch_fetch"),
                        )
                        self.assertEqual(
                            batch_fetch_progress[-1],
                            (2, 2, "batch_fetch complete"),
                        )

                        default_fetch = await session.call_tool(
                            "fetch_paper", {"query": "10.1000/default"}
                        )
                        self.assertFalse(default_fetch.is_error)
                        self.assertTrue(
                            any(
                                isinstance(
                                    message,
                                    mcp_types.ResourceListChangedNotification,
                                )
                                for message in protocol_messages
                            )
                        )

                        resources = await session.list_resources()
                        resource_uris = sorted(
                            str(resource.uri) for resource in resources.resources
                        )
                        self.assertIn(
                            "resource://paper-fetch/cache-index", resource_uris
                        )
                        self.assertIn(PROVIDER_CATALOG_RESOURCE_URI, resource_uris)
                        self.assertTrue(
                            any(
                                uri.startswith("resource://paper-fetch/cached/")
                                for uri in resource_uris
                            )
                        )
                        custom_scope_id = cache_scope_id(isolated_dir)
                        custom_index_uri = scoped_cache_index_resource_uri(
                            custom_scope_id
                        )
                        self.assertIn(custom_index_uri, resource_uris)
                        self.assertTrue(
                            any(
                                uri.startswith(
                                    scoped_cached_resource_uri_prefix(custom_scope_id)
                                )
                                for uri in resource_uris
                            )
                        )

                        templates = await session.list_resource_templates()
                        template_uris = [
                            str(template.uri_template)
                            for template in templates.resource_templates
                        ]
                        self.assertIn(
                            "resource://paper-fetch/cached/{entry_id}", template_uris
                        )

                        cache_index = await session.read_resource(
                            "resource://paper-fetch/cache-index"
                        )
                        cache_text = cache_index.contents[0].text
                        cache_payload = json.loads(cache_text)
                        self.assertEqual(
                            str(default_dir), cache_payload["download_dir"]
                        )
                        markdown_entry = next(
                            entry
                            for entry in cache_payload["entries"]
                            if entry["doi"] == "10.1000/default"
                            and entry["kind"] == "markdown"
                        )

                        provider_catalog = await session.read_resource(
                            PROVIDER_CATALOG_RESOURCE_URI
                        )
                        provider_catalog_payload = json.loads(
                            provider_catalog.contents[0].text
                        )
                        self.assertEqual(
                            provider_catalog_payload["resource_uri"],
                            PROVIDER_CATALOG_RESOURCE_URI,
                        )
                        self.assertEqual(
                            [
                                item["provider"]
                                for item in provider_catalog_payload["providers"]
                            ],
                            list(provider_status_order()),
                        )
                        self.assertEqual(
                            provider_catalog_payload["source_provider_map"],
                            dict(sorted(SOURCE_PROVIDER_MAP.items())),
                        )

                        markdown_resource = await session.read_resource(
                            f"resource://paper-fetch/cached/{markdown_entry['id']}"
                        )
                        self.assertIn(
                            "# Example Article", markdown_resource.contents[0].text
                        )

                        custom_cache_index = await session.read_resource(
                            custom_index_uri
                        )
                        custom_cache_payload = json.loads(
                            custom_cache_index.contents[0].text
                        )
                        self.assertEqual(
                            str(isolated_dir), custom_cache_payload["download_dir"]
                        )
                        custom_markdown_entry = next(
                            entry
                            for entry in custom_cache_payload["entries"]
                            if entry["doi"] == "10.1000/custom"
                            and entry["kind"] == "markdown"
                        )
                        custom_markdown_resource = await session.read_resource(
                            scoped_cached_resource_uri(
                                custom_scope_id, custom_markdown_entry["id"]
                            )
                        )
                        self.assertIn(
                            "# Example Article",
                            custom_markdown_resource.contents[0].text,
                        )

                        invalid = await session.call_tool(
                            "fetch_paper",
                            {"query": "10.1000/example", "modes": ["pdf"]},
                        )
                        self.assertTrue(invalid.is_error)
                        self.assertIsNone(invalid.structured_content)
                        self.assertIn(
                            "unsupported output modes",
                            invalid.content[0].text,
                        )


if __name__ == "__main__":
    unittest.main()
