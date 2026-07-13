# ruff: noqa: F403,F405
from __future__ import annotations

from ._mcp_support import *


class McpPayloadCacheTests(unittest.TestCase):
    def test_build_server_exposes_output_schemas_for_all_tools(self) -> None:
        server = build_server()
        expected_contract_fields = {
            "schema_version",
            "code",
            "http_status",
            "error_category",
            "retry_after_seconds",
            "provider",
            "warnings",
            "source_trail",
        }
        for name, tool in server._tool_manager._tools.items():
            self.assertIsNotNone(tool.output_schema, name)
            properties = (tool.output_schema or {}).get("properties", {})
            self.assertTrue(
                expected_contract_fields <= set(properties),
                f"{name} output schema missing MCP contract fields",
            )

    def test_build_server_exposes_expected_tool_annotations(self) -> None:
        server = build_server()
        expected = {
            "resolve_paper": {"readOnlyHint": True, "openWorldHint": True},
            "has_fulltext": {"readOnlyHint": True, "openWorldHint": True},
            "fetch_paper": {
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            },
            "batch_fetch": {
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            },
            "list_cached": {"readOnlyHint": True, "openWorldHint": False},
            "get_cached": {"readOnlyHint": True, "openWorldHint": False},
            "batch_resolve": {"readOnlyHint": True, "openWorldHint": True},
            "batch_check": {"readOnlyHint": True, "openWorldHint": True},
            "browser_preflight": {
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            },
            "provider_status": {"readOnlyHint": True, "openWorldHint": False},
        }

        self.assertEqual(set(server._tool_manager._tools), set(expected))
        for name, tool in server._tool_manager._tools.items():
            self.assertIsNotNone(tool.annotations, name)
            for field_name, value in expected[name].items():
                self.assertEqual(
                    getattr(tool.annotations, field_name), value, f"{name}.{field_name}"
                )

    def test_fetch_output_schema_exposes_asset_audit_and_provenance(self) -> None:
        schema = build_server()._tool_manager._tools["fetch_paper"].output_schema or {}
        definitions = schema.get("$defs", {})

        self.assertIn("provenance", definitions["AssetOutput"]["properties"])
        self.assertIn("asset_summary", definitions["QualityOutput"]["properties"])
        self.assertEqual(
            definitions["AssetQualitySummaryOutput"]["properties"]["by_kind"],
            {"$ref": "#/$defs/AssetByKindOutput"},
        )

    def test_provider_status_tool_returns_success_when_providers_are_unconfigured(
        self,
    ) -> None:
        blank_env = {
            "CROSSREF_MAILTO": "",
            "ELSEVIER_API_KEY": "",
        }
        with mock.patch.object(mcp_tools, "build_runtime_env", return_value=blank_env):
            result = mcp_tools.provider_status_tool()

        self.assertFalse(result.isError)
        providers = result.structuredContent["providers"]
        self.assertEqual(
            [entry["provider"] for entry in providers],
            list(mcp_tools._PROVIDER_STATUS_ORDER),
        )
        self.assertEqual(providers[0]["provider"], "crossref")
        self.assertEqual(providers[0]["status"], "ready")
        self.assertTrue(
            any(
                entry["provider"] == "elsevier" and entry["status"] == "not_configured"
                for entry in providers
            )
        )
        self.assertTrue(
            any(
                entry["provider"] == "science" and entry["status"] == "ready"
                for entry in providers
            )
        )
        self.assertTrue(all(entry["checks"] for entry in providers))

    def test_fetch_paper_payload_uses_default_arguments_and_mcp_download_dir(
        self,
    ) -> None:
        captured: dict[str, object] = {}
        runtime_env = {"CROSSREF_MAILTO": "unit@example.test"}
        default_download_dir = Path("/tmp/paper-fetch-mcp-downloads")

        def fake_fetch_paper(query, **kwargs):
            captured["query"] = query
            captured.update(kwargs)
            return sample_envelope(modes=kwargs["modes"])

        with (
            mock.patch.object(mcp_tools, "build_runtime_env", return_value=runtime_env),
            mock.patch.object(
                mcp_tools, "resolve_mcp_download_dir", return_value=default_download_dir
            ),
            mock.patch.object(
                mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper
            ),
            mock.patch.object(mcp_tools, "refresh_cache_index_for_doi"),
        ):
            payload = mcp_tools.fetch_paper_payload(query="10.1000/example")

        self.assertEqual(payload["doi"], "10.1000/example")
        self.assertEqual(captured["query"], "10.1000/example")
        self.assertEqual(captured["modes"], {"article", "markdown"})
        self.assertEqual(captured["context"].download_dir, default_download_dir)
        self.assertEqual(captured["context"].artifact_mode, "markdown-assets")
        self.assertEqual(captured["context"].env, runtime_env)
        self.assertEqual(
            captured["render"],
            RenderOptions(
                include_refs=None, asset_profile=None, max_tokens="full_text"
            ),
        )
        self.assertEqual(
            captured["strategy"],
            FetchStrategy(
                allow_metadata_only_fallback=True,
                preferred_providers=None,
                asset_profile=None,
            ),
        )

    def test_fetch_paper_payload_passes_explicit_artifact_mode_to_runtime(self) -> None:
        for artifact_mode in ("all", "none"):
            with (
                self.subTest(artifact_mode=artifact_mode),
                tempfile.TemporaryDirectory() as tmpdir,
            ):
                captured: dict[str, object] = {}
                download_dir = Path(tmpdir)

                def fake_fetch_paper(query, captured=captured, **kwargs):
                    captured.update(kwargs)
                    return sample_envelope(modes=kwargs["modes"], doi=query)

                with (
                    mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                    mock.patch.object(
                        mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper
                    ),
                ):
                    payload = mcp_tools.fetch_paper_payload(
                        query="10.1000/example",
                        artifact_mode=artifact_mode,
                        download_dir=download_dir,
                    )

                self.assertEqual(payload["doi"], "10.1000/example")
                self.assertEqual(captured["context"].download_dir, download_dir)
                self.assertEqual(captured["context"].artifact_mode, artifact_mode)

    def test_fetch_paper_payload_artifact_mode_none_still_writes_mcp_sidecar(
        self,
    ) -> None:
        captured: dict[str, object] = {}

        def fake_fetch_paper(query, **kwargs):
            captured.update(kwargs)
            return sample_envelope(modes=kwargs["modes"], doi=query)

        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper
                ),
            ):
                payload = mcp_tools.fetch_paper_payload(
                    query="10.1000/example",
                    artifact_mode="none",
                    download_dir=download_dir,
                )

            sidecar_path = download_dir / "10.1000_example.fetch-envelope.json"
            sidecar_exists = sidecar_path.exists()
            listed_kinds = {
                entry["kind"]
                for entry in mcp_tools.list_cached_payload(download_dir=download_dir)[
                    "entries"
                ]
            }

        self.assertEqual(payload["doi"], "10.1000/example")
        self.assertEqual(captured["context"].artifact_mode, "none")
        self.assertTrue(sidecar_exists)
        self.assertIn("fetch_envelope", listed_kinds)

    def test_fetch_paper_payload_explicit_download_dir_overrides_env_default(
        self,
    ) -> None:
        captured: dict[str, object] = {}
        explicit_download_dir = Path("/tmp/isolated-paper-fetch")

        def fake_fetch_paper(query, **kwargs):
            captured.update(kwargs)
            return sample_envelope(modes=kwargs["modes"])

        with (
            mock.patch.object(
                mcp_tools,
                "build_runtime_env",
                return_value={"PAPER_FETCH_DOWNLOAD_DIR": "/tmp/shared"},
            ),
            mock.patch.object(mcp_tools, "resolve_mcp_download_dir") as mocked_resolve,
            mock.patch.object(
                mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper
            ),
            mock.patch.object(mcp_tools, "refresh_cache_index_for_doi"),
        ):
            mcp_tools.fetch_paper_payload(
                query="10.1000/example",
                download_dir=explicit_download_dir,
            )

        mocked_resolve.assert_not_called()
        self.assertEqual(captured["context"].download_dir, explicit_download_dir)

    def test_fetch_paper_payload_prefer_cache_defaults_false_and_does_not_read_sidecar(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            create_cached_fetch_envelope(
                download_dir, "10.1000/example", modes=["markdown"]
            )

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(mcp_tools, "service_resolve_paper") as mocked_resolve,
                mock.patch.object(
                    mcp_tools,
                    "service_fetch_paper",
                    return_value=sample_envelope(
                        modes={"markdown"}, doi="10.1000/example"
                    ),
                ) as mocked_fetch,
            ):
                payload = mcp_tools.fetch_paper_payload(
                    query="10.1000/example",
                    modes=["markdown"],
                    download_dir=download_dir,
                )

        self.assertEqual(payload["doi"], "10.1000/example")
        mocked_resolve.assert_not_called()
        mocked_fetch.assert_called_once()

    def test_fetch_paper_payload_no_download_passes_none_download_dir_and_skips_sidecar_write(
        self,
    ) -> None:
        captured: dict[str, object] = {}

        def fake_fetch_paper(query, **kwargs):
            captured.update(kwargs)
            return sample_envelope(modes=kwargs["modes"], doi=query)

        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir) / "downloads"
            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper
                ),
                mock.patch.object(
                    mcp_tools, "refresh_cache_index_for_doi"
                ) as mocked_refresh,
            ):
                payload = mcp_tools.fetch_paper_payload(
                    query="10.1000/example",
                    no_download=True,
                    download_dir=download_dir,
                )

            self.assertEqual(payload["doi"], "10.1000/example")
            self.assertIsNone(captured["context"].download_dir)
            self.assertEqual(captured["context"].artifact_mode, "none")
            self.assertFalse(download_dir.exists())
            mocked_refresh.assert_not_called()

    def test_fetch_paper_payload_save_markdown_writes_file_and_returns_path(
        self,
    ) -> None:
        captured: dict[str, object] = {}

        def fake_fetch_paper(query, **kwargs):
            captured.update(kwargs)
            return sample_envelope(modes=kwargs["modes"], doi=query)

        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper
                ),
            ):
                payload = mcp_tools.fetch_paper_payload(
                    query="10.1000/example",
                    save_markdown=True,
                    markdown_filename="custom.md",
                    download_dir=download_dir,
                )

            saved_path = download_dir / "custom.md"
            self.assertEqual(payload["saved_markdown_path"], str(saved_path))
            self.assertIsNone(payload["markdown"])
            self.assertIsNone(payload["article"])
            self.assertEqual(payload["metadata"]["title"], "Example Article")
            self.assertTrue(saved_path.exists())
            self.assertIn("# Example Article", saved_path.read_text(encoding="utf-8"))
            self.assertEqual(captured["modes"], {"article", "markdown"})
            self.assertIn("download:markdown_saved", payload["source_trail"])

    def test_fetch_paper_payload_save_markdown_skips_when_fulltext_markdown_unavailable(
        self,
    ) -> None:
        envelope = FetchEnvelope(
            doi="10.1000/example",
            source="metadata_only",
            has_fulltext=False,
            content_kind="metadata_only",
            warnings=[],
            source_trail=["fallback:metadata_only"],
            token_estimate=0,
            article=None,
            markdown=None,
            metadata=Metadata(title="Metadata Only"),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools, "service_fetch_paper", return_value=envelope
                ),
            ):
                payload = mcp_tools.fetch_paper_payload(
                    query="10.1000/example",
                    save_markdown=True,
                    download_dir=download_dir,
                )

            self.assertNotIn("saved_markdown_path", payload)
            self.assertIsNone(payload["markdown"])
            self.assertIsNone(payload["article"])
            self.assertFalse(
                (download_dir / "unknown_unknown_Metadata_Only.md").exists()
            )
            self.assertIn(
                "download:markdown_skipped_no_fulltext", payload["source_trail"]
            )
            self.assertTrue(
                any(
                    "nothing written to disk" in warning
                    for warning in payload["warnings"]
                )
            )

    def test_fetch_paper_payload_no_download_save_markdown_writes_only_markdown_and_index(
        self,
    ) -> None:
        captured: dict[str, object] = {}

        def fake_fetch_paper(query, **kwargs):
            captured.update(kwargs)
            if kwargs["context"].download_dir is not None:
                create_cached_downloads(kwargs["context"].download_dir, query)
            return sample_envelope(modes=kwargs["modes"], doi=query)

        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper
                ),
            ):
                payload = mcp_tools.fetch_paper_payload(
                    query="10.1000/example",
                    no_download=True,
                    save_markdown=True,
                    download_dir=download_dir,
                )

            self.assertIsNone(captured["context"].download_dir)
            self.assertTrue((download_dir / "Example_2026_Example_Article.md").exists())
            self.assertFalse(
                (download_dir / "10.1000_example.fetch-envelope.json").exists()
            )
            self.assertFalse((download_dir / "10.1000_example.xml").exists())
            self.assertFalse((download_dir / "10.1000_example_assets").exists())
            self.assertEqual(
                payload["saved_markdown_path"],
                str(download_dir / "Example_2026_Example_Article.md"),
            )
            self.assertIsNone(payload["markdown"])
            self.assertIsNone(payload["article"])
            listed = mcp_tools.list_cached_payload(download_dir=download_dir)
            self.assertEqual(
                [entry["kind"] for entry in listed["entries"]], ["markdown"]
            )
            self.assertEqual(
                listed["entries"][0]["identity_proof"],
                IDENTITY_PROOF_MARKDOWN_REGISTRATION,
            )
            self.assertEqual(listed["entries"][0]["doi"], "10.1000/example")

    def test_fetch_paper_payload_normalizes_preferred_providers(self) -> None:
        captured: dict[str, object] = {}

        def fake_fetch_paper(query, **kwargs):
            captured.update(kwargs)
            return sample_envelope(modes=kwargs["modes"])

        with (
            mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
            mock.patch.object(
                mcp_tools,
                "resolve_mcp_download_dir",
                return_value=Path("/tmp/downloads"),
            ),
            mock.patch.object(
                mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper
            ),
            mock.patch.object(mcp_tools, "refresh_cache_index_for_doi"),
        ):
            mcp_tools.fetch_paper_payload(
                query="10.1000/example",
                strategy={"preferred_providers": [" Wiley ", "crossref", "wiley", ""]},
            )

        strategy = captured["strategy"]
        assert isinstance(strategy, FetchStrategy)
        self.assertEqual(strategy.preferred_providers, ["wiley", "crossref"])

    def test_fetch_paper_tool_rejects_invalid_modes_before_service_call(self) -> None:
        with mock.patch.object(mcp_tools, "service_fetch_paper") as mocked_fetch:
            result = asyncio.run(
                mcp_tools.fetch_paper_tool_async(query="10.1000/example", modes=["pdf"])
            )

        self.assertTrue(result.isError)
        self.assertIn("unsupported output modes", result.structuredContent["reason"])
        mocked_fetch.assert_not_called()

    def test_fetch_paper_tool_rejects_invalid_include_refs_before_service_call(
        self,
    ) -> None:
        with mock.patch.object(mcp_tools, "service_fetch_paper") as mocked_fetch:
            result = asyncio.run(
                mcp_tools.fetch_paper_tool_async(
                    query="10.1000/example", include_refs="summary"
                )
            )

        self.assertTrue(result.isError)
        self.assertIn(
            "unsupported include_refs value", result.structuredContent["reason"]
        )
        mocked_fetch.assert_not_called()

    def test_fetch_paper_tool_rejects_invalid_asset_profile_before_service_call(
        self,
    ) -> None:
        with mock.patch.object(mcp_tools, "service_fetch_paper") as mocked_fetch:
            result = asyncio.run(
                mcp_tools.fetch_paper_tool_async(
                    query="10.1000/example",
                    strategy={"asset_profile": "full"},
                )
            )

        self.assertTrue(result.isError)
        self.assertIn(
            "unsupported asset_profile value", result.structuredContent["reason"]
        )
        mocked_fetch.assert_not_called()

    def test_fetch_paper_tool_rejects_invalid_artifact_mode_before_service_call(
        self,
    ) -> None:
        with mock.patch.object(mcp_tools, "service_fetch_paper") as mocked_fetch:
            result = asyncio.run(
                mcp_tools.fetch_paper_tool_async(
                    query="10.1000/example",
                    artifact_mode="debug",
                )
            )

        self.assertTrue(result.isError)
        self.assertIn(
            "unsupported artifact_mode value", result.structuredContent["reason"]
        )
        mocked_fetch.assert_not_called()

    def test_fetch_paper_payload_prefer_cache_short_circuits_network_when_cached_envelope_matches(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            create_cached_fetch_envelope(
                download_dir, "10.1000/example", modes=["markdown"]
            )

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools,
                    "service_resolve_paper",
                    return_value=sample_resolved_query("10.1000/example"),
                ),
                mock.patch.object(mcp_tools, "service_fetch_paper") as mocked_fetch,
            ):
                payload = mcp_tools.fetch_paper_payload(
                    query="10.1000/example",
                    modes=["markdown"],
                    prefer_cache=True,
                    download_dir=download_dir,
                )

        self.assertEqual(payload["doi"], "10.1000/example")
        self.assertEqual(payload["markdown"], "# Example Article\n\nExample body.\n")
        self.assertIn(
            QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION, payload["quality"]["flags"]
        )
        mocked_fetch.assert_not_called()

    def test_fetch_paper_payload_prefer_cache_reads_sidecar_with_artifact_mode_none(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            create_cached_fetch_envelope(
                download_dir, "10.1000/example", modes=["markdown"]
            )

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools,
                    "service_resolve_paper",
                    return_value=sample_resolved_query("10.1000/example"),
                ),
                mock.patch.object(mcp_tools, "service_fetch_paper") as mocked_fetch,
            ):
                payload = mcp_tools.fetch_paper_payload(
                    query="10.1000/example",
                    modes=["markdown"],
                    prefer_cache=True,
                    artifact_mode="none",
                    download_dir=download_dir,
                )

        self.assertEqual(payload["doi"], "10.1000/example")
        self.assertEqual(payload["markdown"], "# Example Article\n\nExample body.\n")
        mocked_fetch.assert_not_called()

    def test_fetch_paper_payload_save_markdown_compacts_cached_sidecar_response(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            create_cached_fetch_envelope(download_dir, "10.1000/example")

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools,
                    "service_resolve_paper",
                    return_value=sample_resolved_query("10.1000/example"),
                ),
                mock.patch.object(mcp_tools, "service_fetch_paper") as mocked_fetch,
            ):
                payload = mcp_tools.fetch_paper_payload(
                    query="10.1000/example",
                    modes=["markdown"],
                    prefer_cache=True,
                    save_markdown=True,
                    download_dir=download_dir,
                )

            saved_path = download_dir / "Example_2026_Example_Article.md"
            self.assertEqual(payload["saved_markdown_path"], str(saved_path))
            self.assertTrue(saved_path.exists())
        self.assertIsNone(payload["markdown"])
        self.assertIsNone(payload["article"])
        self.assertEqual(payload["metadata"]["title"], "Example Article")
        self.assertIn(
            QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION, payload["quality"]["flags"]
        )
        mocked_fetch.assert_not_called()

    def test_fetch_paper_payload_prefer_cache_falls_back_on_mode_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            create_cached_fetch_envelope(
                download_dir, "10.1000/example", modes=["markdown"]
            )

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools,
                    "service_resolve_paper",
                    return_value=sample_resolved_query("10.1000/example"),
                ),
                mock.patch.object(
                    mcp_tools,
                    "service_fetch_paper",
                    return_value=sample_envelope(
                        modes={"article"}, doi="10.1000/example"
                    ),
                ) as mocked_fetch,
            ):
                payload = mcp_tools.fetch_paper_payload(
                    query="10.1000/example",
                    modes=["article"],
                    prefer_cache=True,
                    download_dir=download_dir,
                )

        self.assertEqual(payload["doi"], "10.1000/example")
        self.assertIsNotNone(payload["article"])
        mocked_fetch.assert_called_once()

    def test_fetch_paper_payload_prefer_cache_derives_breakdown_from_legacy_sidecar_payload(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            create_cached_fetch_envelope(
                download_dir, "10.1000/example", modes=["article", "metadata"]
            )
            cache_path = mcp_tools._fetch_envelope_cache_path(
                download_dir, "10.1000/example"
            )
            cache_payload = json.loads(cache_path.read_text(encoding="utf-8"))
            cache_payload["payload"].pop("token_estimate_breakdown", None)
            cache_payload["payload"]["article"]["quality"].pop(
                "token_estimate_breakdown", None
            )
            cache_path.write_text(
                json.dumps(cache_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools,
                    "service_resolve_paper",
                    return_value=sample_resolved_query("10.1000/example"),
                ),
                mock.patch.object(mcp_tools, "service_fetch_paper") as mocked_fetch,
            ):
                payload = mcp_tools.fetch_paper_payload(
                    query="10.1000/example",
                    modes=["article", "metadata"],
                    prefer_cache=True,
                    download_dir=download_dir,
                )

        self.assertEqual(
            payload["token_estimate_breakdown"], {"abstract": 4, "body": 4, "refs": 0}
        )
        self.assertEqual(
            payload["article"]["quality"]["token_estimate_breakdown"],
            {"abstract": 4, "body": 4, "refs": 0},
        )
        self.assertEqual(payload["quality"]["extraction_revision"], EXTRACTION_REVISION)
        self.assertIn(
            QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION, payload["quality"]["flags"]
        )
        mocked_fetch.assert_not_called()

    def test_article_payload_preserves_asset_download_diagnostics(self) -> None:
        """rule: rule-asset-download-diagnostic-fields"""
        payload = json.loads(
            golden_criteria_scenario_asset(
                "asset_download_diagnostics", "article_payload.json"
            ).read_text(encoding="utf-8")
        )
        payload["assets"][0]["provenance"] = [
            "conversion_degraded",
            "conversion_degraded",
        ]
        article = mcp_tools._article_from_payload(payload)

        self.assertIsNotNone(article)
        assert article is not None
        asset = article.assets[0]
        self.assertEqual(asset.render_state, "appendix")
        self.assertEqual(asset.anchor_key, "F1")
        self.assertEqual(asset.download_tier, "preview")
        self.assertEqual(asset.download_url, "https://example.test/figure-preview.png")
        self.assertEqual(asset.width, 640)
        self.assertEqual(asset.height, 480)
        self.assertEqual(asset.provenance, ["conversion_degraded"])

    def test_fetch_envelope_payload_preserves_quality_asset_failures(self) -> None:
        request = mcp_tools.FetchPaperRequest(
            query="10.1000/example", modes=["article"]
        )
        envelope = sample_envelope(modes={"article"}, doi="10.1000/example")
        assert envelope.article is not None
        envelope.article.quality.asset_failures = [
            {
                "kind": "figure",
                "heading": "Figure 1",
                "source_url": "https://example.test/figure-1.png",
                "status": 403,
                "content_type": "text/html; charset=UTF-8",
                "title_snippet": "Just a moment...",
                "body_snippet": "Just a moment... Please enable JavaScript and Cookies.",
                "reason": "cloudflare_challenge",
                "recovery_attempts": [
                    {
                        "status": "failed",
                        "url": "https://example.test/figure-page",
                        "reason": "cloudflare_challenge",
                    }
                ],
            }
        ]
        envelope.quality = envelope.article.quality

        payload = mcp_tools._payload_from_envelope(envelope, request)
        round_trip = mcp_tools._envelope_from_payload(payload)

        self.assertEqual(payload["quality"]["asset_failures"][0]["status"], 403)
        self.assertEqual(
            payload["quality"]["asset_failures"][0]["reason"], "cloudflare_challenge"
        )
        self.assertIsNotNone(round_trip)
        assert round_trip is not None
        self.assertEqual(
            round_trip.quality.asset_failures[0]["title_snippet"], "Just a moment..."
        )
        self.assertEqual(
            round_trip.quality.asset_failures[0]["recovery_attempts"][0]["status"],
            "failed",
        )

    def test_fetch_paper_payload_prefer_cache_misses_when_revision_differs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            create_cached_fetch_envelope(
                download_dir,
                "10.1000/example",
                modes=["markdown"],
                extraction_revision=EXTRACTION_REVISION - 1,
            )

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools,
                    "service_resolve_paper",
                    return_value=sample_resolved_query("10.1000/example"),
                ),
                mock.patch.object(
                    mcp_tools,
                    "service_fetch_paper",
                    return_value=sample_envelope(
                        modes={"markdown"}, doi="10.1000/example"
                    ),
                ) as mocked_fetch,
            ):
                payload = mcp_tools.fetch_paper_payload(
                    query="10.1000/example",
                    modes=["markdown"],
                    prefer_cache=True,
                    download_dir=download_dir,
                )

        self.assertEqual(payload["doi"], "10.1000/example")
        self.assertNotIn(
            QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION, payload["quality"]["flags"]
        )
        mocked_fetch.assert_called_once()

    def test_fetch_cache_write_refreshes_index_with_scoped_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            request = mcp_tools.FetchPaperRequest(
                query="10.1000/example", modes=["markdown"]
            )
            envelope = sample_envelope(modes={"markdown"}, doi="10.1000/example")

            FetchCache(download_dir).write_fetch_envelope(envelope, request)
            entries = mcp_tools.list_cached_payload(download_dir=download_dir)[
                "entries"
            ]
            lock_dir_exists = cache_lock_dir(download_dir).is_dir()

        self.assertEqual([entry["kind"] for entry in entries], ["fetch_envelope"])
        self.assertEqual(entries[0]["doi"], "10.1000/example")
        self.assertTrue(lock_dir_exists)
        self.assertFalse(
            any(LOCK_DIRNAME in str(entry.get("path") or "") for entry in entries)
        )
