# ruff: noqa: F403,F405
from __future__ import annotations

from paper_fetch.capability_scope import CapabilityScopeBuilder
from paper_fetch.mcp.cache_index import (
    cached_resource_uri,
    read_cache_index,
    scoped_cached_resource_uri,
)

from ._mcp_support import *


class McpServerResourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_resource_uri_rechecks_changed_sidecar_scope(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "default"
            doi = "10.1000/mutated-resource-scope"
            FetchCache(default_dir).write_fetch_envelope(
                sample_envelope(modes={"markdown"}, doi=doi),
                FetchPaperRequest(query=doi, modes=["markdown"]),
            )
            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools,
                    "resolve_mcp_download_dir",
                    return_value=default_dir,
                ),
            ):
                server = build_server()
            entry = next(
                entry
                for entry in read_cache_index(default_dir).entries
                if entry["kind"] == "fetch_envelope"
            )
            resource = server._resource_manager._resources[
                cached_resource_uri(str(entry["id"]))
            ]
            assert await resource.read()

            sidecar_path = Path(str(entry["path"]))
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            sidecar["credential_scope"] = "credential:" + ("9" * 64)
            sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

            with self.assertRaisesRegex(
                (FileNotFoundError, ValueError), "unauthorized"
            ):
                await resource.read()

    async def test_existing_resource_uri_reauthorizes_on_every_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "default"
            isolated_dir = Path(tmpdir) / "isolated"
            env = {"ELSEVIER_API_KEY": "mutable-resource-secret"}
            active_env = dict(env)
            private_scope = CapabilityScopeBuilder(env).build()
            private_doi = "10.1000/private-live-resource"
            public_doi = "10.1000/public-live-resource"
            custom_doi = "10.1000/custom-live-resource"
            FetchCache(
                default_dir, credential_scope=private_scope
            ).write_fetch_envelope(
                sample_envelope(modes={"markdown"}, doi=private_doi),
                FetchPaperRequest(query=private_doi, modes=["markdown"]),
            )
            FetchCache(default_dir).write_fetch_envelope(
                sample_envelope(modes={"markdown"}, doi=public_doi),
                FetchPaperRequest(query=public_doi, modes=["markdown"]),
            )
            FetchCache(
                isolated_dir, credential_scope=private_scope
            ).write_fetch_envelope(
                sample_envelope(modes={"markdown"}, doi=custom_doi),
                FetchPaperRequest(query=custom_doi, modes=["markdown"]),
            )

            def current_env(*_args, **_kwargs):
                return dict(active_env)

            with (
                mock.patch.object(
                    mcp_tools,
                    "build_runtime_env",
                    side_effect=current_env,
                ),
                mock.patch.object(
                    mcp_tools,
                    "resolve_mcp_download_dir",
                    return_value=default_dir,
                ),
            ):
                server = build_server()

            custom_deps = mcp_test_deps(
                build_runtime_env=current_env,
                resolve_mcp_download_dir=lambda _env: default_dir,
            )
            mcp_server._sync_resources_for_download_dir(
                server,
                isolated_dir,
                deps=custom_deps,
            )
            default_entries = read_cache_index(default_dir).entries
            private_entry = next(
                entry
                for entry in default_entries
                if entry["doi"] == private_doi and entry["kind"] == "fetch_envelope"
            )
            public_entry = next(
                entry
                for entry in default_entries
                if entry["doi"] == public_doi and entry["kind"] == "fetch_envelope"
            )
            custom_entry = next(
                entry
                for entry in read_cache_index(isolated_dir).entries
                if entry["kind"] == "fetch_envelope"
            )
            private_resource = server._resource_manager._resources[
                cached_resource_uri(str(private_entry["id"]))
            ]
            public_resource = server._resource_manager._resources[
                cached_resource_uri(str(public_entry["id"]))
            ]
            custom_resource = server._resource_manager._resources[
                scoped_cached_resource_uri(
                    cache_scope_id(isolated_dir),
                    str(custom_entry["id"]),
                )
            ]

            assert await private_resource.read()
            assert await public_resource.read()
            assert await custom_resource.read()
            active_env.clear()

            with self.assertRaisesRegex(
                (FileNotFoundError, ValueError), "unauthorized"
            ):
                await private_resource.read()
            with self.assertRaisesRegex(
                (FileNotFoundError, ValueError), "unauthorized"
            ):
                await custom_resource.read()
            assert await public_resource.read()

    async def test_private_cache_resources_require_the_exact_runtime_scope(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "default"
            env = {"ELSEVIER_API_KEY": "resource-secret"}
            scope = CapabilityScopeBuilder(env).build()
            request = FetchPaperRequest(
                query="10.1000/private-resource",
                modes=["markdown"],
            )
            FetchCache(default_dir, credential_scope=scope).write_fetch_envelope(
                sample_envelope(modes={"markdown"}, doi="10.1000/private-resource"),
                request,
            )

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools,
                    "resolve_mcp_download_dir",
                    return_value=default_dir,
                ),
            ):
                public_server = build_server()
            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value=env),
                mock.patch.object(
                    mcp_tools,
                    "resolve_mcp_download_dir",
                    return_value=default_dir,
                ),
            ):
                private_server = build_server()

        public_uris = set(public_server._resource_manager._resources)
        private_uris = set(private_server._resource_manager._resources)
        assert not any(
            uri.startswith("resource://paper-fetch/cached/") for uri in public_uris
        )
        assert any(
            uri.startswith("resource://paper-fetch/cached/") for uri in private_uris
        )

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
            resolved_queries: list[str] = []

            def fake_fetch(query, **kwargs):
                return sample_envelope(modes=kwargs["modes"], doi=query)

            def fake_resolve(query, *, context=None):
                del context
                resolved_queries.append(query)
                return sample_resolved_query(query)

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools, "resolve_mcp_download_dir", return_value=default_dir
                ),
                mock.patch.object(
                    mcp_tools, "service_fetch_paper", side_effect=fake_fetch
                ),
                mock.patch.object(
                    mcp_tools, "service_resolve_paper", side_effect=fake_resolve
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
        self.assertEqual(sorted(resolved_queries), ["10.1000/one", "10.1000/two"])
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
        self.assertEqual(len(listed.structured_content["entries"]), 1)
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
