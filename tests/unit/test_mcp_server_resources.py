# ruff: noqa: F403,F405
from __future__ import annotations

from ._mcp_support import *


class McpServerResourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_paper_server_notifies_when_default_resources_change(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "default"
            ctx = FakeContext()

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools, "resolve_mcp_download_dir", return_value=default_dir
                ),
                mock.patch.object(
                    mcp_tools,
                    "service_fetch_paper",
                    side_effect=fake_service_fetch_with_cached_downloads,
                ),
            ):
                server = build_server()
                result = await server._tool_manager.call_tool(
                    "fetch_paper",
                    {"query": "10.1000/example"},
                    context=ctx,
                )

        self.assertFalse(result.is_error)
        self.assertEqual(ctx.session.resource_list_changed_calls, 1)
        resource_uris = set(server._resource_manager._resources)
        self.assertTrue(
            any(
                uri.startswith("resource://paper-fetch/cached/")
                for uri in resource_uris
            )
        )

    async def test_fetch_paper_server_passes_artifact_mode_to_payload_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "default"
            ctx = FakeContext()
            captured: dict[str, object] = {}

            def fake_fetch_paper(query, **kwargs):
                captured.update(kwargs)
                return sample_envelope(modes=kwargs["modes"], doi=query)

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools, "resolve_mcp_download_dir", return_value=default_dir
                ),
                mock.patch.object(
                    mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper
                ),
            ):
                server = build_server()
                result = await server._tool_manager.call_tool(
                    "fetch_paper",
                    {"query": "10.1000/example", "artifact_mode": "none"},
                    context=ctx,
                )

        self.assertFalse(result.is_error)
        self.assertEqual(captured["context"].download_dir, default_dir)
        self.assertEqual(captured["context"].artifact_mode, "none")

    async def test_fetch_paper_server_skips_resource_sync_when_no_download_without_markdown_save(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "default"
            ctx = FakeContext()

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools, "resolve_mcp_download_dir", return_value=default_dir
                ),
                mock.patch.object(
                    mcp_tools,
                    "service_fetch_paper",
                    return_value=sample_envelope(
                        modes={"article", "markdown"}, doi="10.1000/example"
                    ),
                ),
            ):
                server = build_server()
                result = await server._tool_manager.call_tool(
                    "fetch_paper",
                    {"query": "10.1000/example", "no_download": True},
                    context=ctx,
                )

        self.assertFalse(result.is_error)
        self.assertEqual(ctx.session.resource_list_changed_calls, 0)

    async def test_fetch_paper_server_syncs_resources_for_no_download_markdown_save(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "default"
            isolated_dir = Path(tmpdir) / "isolated"
            ctx = FakeContext()

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools, "resolve_mcp_download_dir", return_value=default_dir
                ),
                mock.patch.object(
                    mcp_tools,
                    "service_fetch_paper",
                    return_value=sample_envelope(
                        modes={"article", "markdown"}, doi="10.1000/example"
                    ),
                ),
            ):
                server = build_server()
                result = await server._tool_manager.call_tool(
                    "fetch_paper",
                    {
                        "query": "10.1000/example",
                        "no_download": True,
                        "save_markdown": True,
                        "download_dir": str(isolated_dir),
                    },
                    context=ctx,
                )

        self.assertFalse(result.is_error)
        self.assertEqual(
            result.structured_content["saved_markdown_path"],
            str(isolated_dir / "Example_2026_Example_Article.md"),
        )
        self.assertIsNone(result.structured_content["markdown"])
        self.assertIsNone(result.structured_content["article"])
        self.assertEqual(ctx.session.resource_list_changed_calls, 1)
        scope_id = cache_scope_id(isolated_dir)
        resource_uris = set(server._resource_manager._resources)
        self.assertIn(scoped_cache_index_resource_uri(scope_id), resource_uris)
        self.assertTrue(
            any(
                uri.startswith(scoped_cached_resource_uri_prefix(scope_id))
                for uri in resource_uris
            )
        )

    async def test_batch_fetch_server_syncs_saved_markdown_resource_uris(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "default"
            isolated_dir = Path(tmpdir) / "isolated"
            ctx = FakeContext()

            def fake_fetch(query, **kwargs):
                return sample_envelope(modes=kwargs["modes"], doi=query)

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools, "resolve_mcp_download_dir", return_value=default_dir
                ),
                mock.patch.object(
                    mcp_tools, "service_fetch_paper", side_effect=fake_fetch
                ),
            ):
                server = build_server()
                result = await server._tool_manager.call_tool(
                    "batch_fetch",
                    {
                        "queries": ["10.1000/one", "10.1000/two"],
                        "concurrency": 2,
                        "strategy": {"asset_profile": "none"},
                        "no_download": True,
                        "artifact_mode": "none",
                        "save_markdown": True,
                        "download_dir": str(isolated_dir),
                    },
                    context=ctx,
                )

        self.assertFalse(result.is_error)
        self.assertEqual(result.structured_content["summary"]["saved_markdown"], 2)
        scope_id = cache_scope_id(isolated_dir)
        expected_prefix = scoped_cached_resource_uri_prefix(scope_id)
        returned_uris = {
            item["resource_uri"] for item in result.structured_content["results"]
        }
        self.assertTrue(all(uri.startswith(expected_prefix) for uri in returned_uris))
        resource_uris = set(server._resource_manager._resources)
        self.assertTrue(returned_uris <= resource_uris)
        self.assertEqual(ctx.session.resource_list_changed_calls, 1)

    async def test_fetch_paper_server_no_download_skipped_markdown_save_does_not_sync_resources(
        self,
    ) -> None:
        envelope = FetchEnvelope(
            doi="10.1000/example",
            source="metadata_only",
            has_fulltext=False,
            content_kind="metadata_only",
            article=None,
            markdown=None,
            metadata=Metadata(title="Metadata Only"),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "default"
            isolated_dir = Path(tmpdir) / "isolated"
            ctx = FakeContext()

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools, "resolve_mcp_download_dir", return_value=default_dir
                ),
                mock.patch.object(
                    mcp_tools, "service_fetch_paper", return_value=envelope
                ),
            ):
                server = build_server()
                result = await server._tool_manager.call_tool(
                    "fetch_paper",
                    {
                        "query": "10.1000/example",
                        "no_download": True,
                        "save_markdown": True,
                        "download_dir": str(isolated_dir),
                    },
                    context=ctx,
                )

        self.assertFalse(result.is_error)
        self.assertNotIn("saved_markdown_path", result.structured_content)
        self.assertEqual(ctx.session.resource_list_changed_calls, 0)

    async def test_fetch_paper_server_notifies_when_scoped_resources_change(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "default"
            isolated_dir = Path(tmpdir) / "isolated"
            ctx = FakeContext()

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools, "resolve_mcp_download_dir", return_value=default_dir
                ),
                mock.patch.object(
                    mcp_tools,
                    "service_fetch_paper",
                    side_effect=fake_service_fetch_with_cached_downloads,
                ),
            ):
                server = build_server()
                result = await server._tool_manager.call_tool(
                    "fetch_paper",
                    {"query": "10.1000/custom", "download_dir": str(isolated_dir)},
                    context=ctx,
                )

        self.assertFalse(result.is_error)
        self.assertEqual(ctx.session.resource_list_changed_calls, 1)
        scope_id = cache_scope_id(isolated_dir)
        resource_uris = set(server._resource_manager._resources)
        self.assertIn(scoped_cache_index_resource_uri(scope_id), resource_uris)
        self.assertTrue(
            any(
                uri.startswith(scoped_cached_resource_uri_prefix(scope_id))
                for uri in resource_uris
            )
        )

    async def test_list_cached_and_get_cached_server_notify_on_external_cache_changes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "default"
            isolated_dir = Path(tmpdir) / "isolated"
            ctx = FakeContext()

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools, "resolve_mcp_download_dir", return_value=default_dir
                ),
            ):
                server = build_server()

                create_cached_downloads(default_dir, "10.1000/default")
                mcp_tools.refresh_cache_index_for_doi(default_dir, "10.1000/default")
                listed = await server._tool_manager.call_tool(
                    "list_cached", {}, context=ctx
                )

                create_cached_downloads(isolated_dir, "10.1000/custom")
                mcp_tools.refresh_cache_index_for_doi(isolated_dir, "10.1000/custom")
                cached = await server._tool_manager.call_tool(
                    "get_cached",
                    {"doi": "10.1000/custom", "download_dir": str(isolated_dir)},
                    context=ctx,
                )

        self.assertFalse(listed.is_error)
        self.assertFalse(cached.is_error)
        self.assertEqual(len(listed.structured_content["entries"]), 3)
        self.assertEqual(cached.structured_content["status"], "hit")
        self.assertEqual(ctx.session.resource_list_changed_calls, 2)

    async def test_fetch_paper_server_does_not_notify_when_resource_uris_are_unchanged(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "default"
            ctx = FakeContext()

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools, "resolve_mcp_download_dir", return_value=default_dir
                ),
                mock.patch.object(
                    mcp_tools,
                    "service_fetch_paper",
                    side_effect=fake_service_fetch_with_cached_downloads,
                ),
            ):
                server = build_server()
                first = await server._tool_manager.call_tool(
                    "fetch_paper",
                    {"query": "10.1000/example"},
                    context=ctx,
                )
                second = await server._tool_manager.call_tool(
                    "fetch_paper",
                    {"query": "10.1000/example"},
                    context=ctx,
                )

        self.assertFalse(first.is_error)
        self.assertFalse(second.is_error)
        self.assertEqual(ctx.session.resource_list_changed_calls, 1)
