# ruff: noqa: F403,F405
from __future__ import annotations

from paper_fetch.runtime import RuntimeContext

from ._mcp_support import *


class McpBatchResolvePayloadTests(unittest.TestCase):
    def test_batch_resolve_parent_runtime_is_closed_exactly_once(self) -> None:
        parents: list[RuntimeContext] = []

        class TrackingRuntimeContext(RuntimeContext):
            close_count = 0

            def __post_init__(self) -> None:
                super().__post_init__()
                parents.append(self)

            def close(self) -> None:
                self.close_count += 1
                super().close()

        with (
            mock.patch.object(mcp_batch, "RuntimeContext", TrackingRuntimeContext),
            mock.patch.object(
                mcp_tools,
                "service_resolve_paper",
                return_value=sample_resolved_query("10.1000/one"),
            ),
        ):
            payload = mcp_tools.batch_resolve_payload(queries=["10.1000/one"])

        self.assertFalse(payload["aborted"])
        self.assertEqual(len(parents), 1)
        self.assertEqual(parents[0].close_count, 1)

    def test_fetch_paper_payload_accepts_full_text_and_asset_profile_strategy(
        self,
    ) -> None:
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
                strategy={"asset_profile": "body"},
                max_tokens="full_text",
            )

        self.assertEqual(
            captured["render"],
            RenderOptions(
                include_refs=None, asset_profile="body", max_tokens="full_text"
            ),
        )
        self.assertEqual(captured["strategy"], FetchStrategy(asset_profile="body"))

    def test_fetch_strategy_input_resolves_partial_inline_image_budget(self) -> None:
        request = mcp_tools.FetchPaperRequest(
            query="10.1000/example",
            strategy={
                "asset_profile": "body",
                "inline_image_budget": {
                    "max_images": 1,
                },
            },
        )

        budget = request.strategy.resolved_inline_image_budget()

        self.assertEqual(budget.max_images, 1)
        self.assertEqual(budget.max_bytes_per_image, 2 * 1024 * 1024)
        self.assertEqual(budget.max_total_bytes, 8 * 1024 * 1024)

    def test_fetch_paper_payload_inline_image_budget_does_not_change_service_strategy(
        self,
    ) -> None:
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
            mock.patch.object(mcp_tools, "_write_cached_fetch_envelope"),
        ):
            mcp_tools.fetch_paper_payload(
                query="10.1000/example",
                strategy={
                    "asset_profile": "body",
                    "inline_image_budget": {
                        "max_images": 1,
                        "max_total_bytes": 1024,
                    },
                },
            )

        self.assertEqual(captured["strategy"], FetchStrategy(asset_profile="body"))

    def test_fetch_paper_tool_success_preserves_fixed_top_level_fields_and_null_payloads(
        self,
    ) -> None:
        envelope = sample_envelope(modes={"markdown"})

        with (
            mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
            mock.patch.object(
                mcp_tools,
                "resolve_mcp_download_dir",
                return_value=Path("/tmp/downloads"),
            ),
            mock.patch.object(mcp_tools, "service_fetch_paper", return_value=envelope),
            mock.patch.object(mcp_tools, "refresh_cache_index_for_doi"),
        ):
            result = asyncio.run(
                mcp_tools.fetch_paper_tool_async(
                    query="10.1000/example", modes=["markdown"]
                )
            )

        self.assertFalse(result.is_error)
        payload = result.structured_content
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["source"], "elsevier_xml")
        self.assertTrue(payload["has_fulltext"])
        self.assertEqual(payload["warnings"], ["example warning"])
        self.assertEqual(payload["source_trail"], ["source:ok"])
        self.assertEqual(
            payload["token_estimate_breakdown"],
            {"abstract": 32, "body": 96, "refs": 24},
        )
        self.assertEqual(payload["quality"]["extraction_revision"], EXTRACTION_REVISION)
        self.assertEqual(payload["quality"]["confidence"], "medium")
        self.assertEqual(payload["article"], None)
        self.assertIsNotNone(payload["markdown"])
        self.assertEqual(payload["metadata"], None)
        self.assertIn('"source": "elsevier_xml"', result.content[0].text)

    def test_fetch_paper_tool_metadata_mode_populates_metadata_field(self) -> None:
        envelope = sample_envelope(modes={"metadata"})

        with (
            mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
            mock.patch.object(
                mcp_tools,
                "resolve_mcp_download_dir",
                return_value=Path("/tmp/downloads"),
            ),
            mock.patch.object(mcp_tools, "service_fetch_paper", return_value=envelope),
            mock.patch.object(mcp_tools, "refresh_cache_index_for_doi"),
        ):
            result = asyncio.run(
                mcp_tools.fetch_paper_tool_async(
                    query="10.1000/example", modes=["metadata"]
                )
            )

        self.assertFalse(result.is_error)
        payload = result.structured_content
        self.assertEqual(payload["article"], None)
        self.assertEqual(payload["markdown"], None)
        self.assertEqual(payload["metadata"]["title"], "Example Article")
        self.assertEqual(
            payload["token_estimate_breakdown"],
            {"abstract": 32, "body": 96, "refs": 24},
        )
        self.assertEqual(payload["quality"]["body_metrics"]["figure_count"], 0)

    def test_fetch_paper_tool_returns_ambiguous_error_payload(self) -> None:
        error = PaperFetchFailure(
            "ambiguous",
            "Need user confirmation.",
            candidates=[{"doi": "10.1000/example", "title": "Example Article"}],
        )

        with mock.patch.object(mcp_tools, "service_fetch_paper", side_effect=error):
            result = asyncio.run(
                mcp_tools.fetch_paper_tool_async(query="ambiguous title")
            )

        self.assertTrue(result.is_error)
        self.assertEqual(result.structured_content["status"], "ambiguous")
        self.assertEqual(result.structured_content["schema_version"], 2)
        self.assertEqual(result.structured_content["code"], "ambiguous")
        self.assertEqual(
            result.structured_content["candidates"][0]["doi"], "10.1000/example"
        )

    def test_fetch_paper_tool_returns_provider_failure_payload_with_specific_status(
        self,
    ) -> None:
        with mock.patch.object(
            mcp_tools,
            "service_fetch_paper",
            side_effect=ProviderFailure(
                "no_access",
                "Provider request failed.",
                warnings=["provider warning"],
                source_trail=["fulltext:provider_failed"],
            ),
        ):
            result = asyncio.run(
                mcp_tools.fetch_paper_tool_async(query="10.1000/example")
            )

        self.assertTrue(result.is_error)
        self.assertEqual(result.structured_content["schema_version"], 2)
        self.assertEqual(result.structured_content["status"], "no_access")
        self.assertEqual(result.structured_content["code"], "no_access")
        self.assertEqual(result.structured_content["error_category"], "no_access")
        self.assertEqual(
            result.structured_content["reason"], "Provider request failed."
        )
        self.assertEqual(result.structured_content["warnings"], ["provider warning"])
        self.assertEqual(
            result.structured_content["source_trail"], ["fulltext:provider_failed"]
        )
        self.assertIsNone(result.structured_content["missing_env"])

    def test_error_payload_from_exception_preserves_provider_failure_code(
        self,
    ) -> None:
        payload = mcp_tools.error_payload_from_exception(
            ProviderFailure(
                "no_result",
                "Provider returned no full text.",
                retry_after_seconds=7,
                warnings=["temporary provider issue"],
                source_trail=["fulltext:provider_no_result"],
            )
        )

        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["code"], "no_result")
        self.assertEqual(payload["error_category"], "no_result")
        self.assertEqual(payload["retry_after_seconds"], 7)
        self.assertEqual(payload["warnings"], ["temporary provider issue"])
        self.assertEqual(payload["source_trail"], ["fulltext:provider_no_result"])

    def test_error_payload_from_exception_exposes_missing_env_and_promotes_not_configured(
        self,
    ) -> None:
        payload = mcp_tools.error_payload_from_exception(
            ProviderFailure(
                "not_configured",
                "ELSEVIER_API_KEY is not configured.",
                missing_env=["ELSEVIER_API_KEY"],
            )
        )

        self.assertEqual(payload["status"], "no_access")
        self.assertEqual(payload["code"], "not_configured")
        self.assertEqual(payload["error_category"], "not_configured")
        self.assertEqual(payload["missing_env"], ["ELSEVIER_API_KEY"])

    def test_error_payload_from_exception_maps_http_rate_limit_details(self) -> None:
        payload = mcp_tools.error_payload_from_exception(
            RequestFailure(429, "HTTP 429 for provider", retry_after_seconds=4)
        )

        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["status"], "rate_limited")
        self.assertEqual(payload["code"], "http_429")
        self.assertEqual(payload["http_status"], 429)
        self.assertEqual(payload["error_category"], "rate_limited")
        self.assertEqual(payload["retry_after_seconds"], 4)

    def test_fetch_paper_tool_missing_env_payload_survives_without_output_schema(
        self,
    ) -> None:
        server = build_server()

        with mock.patch.object(
            mcp_tools,
            "service_fetch_paper",
            side_effect=ProviderFailure(
                "not_configured",
                "ELSEVIER_API_KEY is not configured.",
                missing_env=["ELSEVIER_API_KEY"],
            ),
        ):
            result = asyncio.run(
                mcp_tools.fetch_paper_tool_async(query="10.1000/example")
            )

        self.assertTrue(result.is_error)
        self.assertEqual(result.structured_content["status"], "no_access")
        self.assertNotIn("acceptance", result.structured_content)
        self.assertEqual(result.structured_content["missing_env"], ["ELSEVIER_API_KEY"])
        assert_mcp_tool_omits_output_schema(
            server, "fetch_paper", result.structured_content
        )

    def test_fetch_paper_payload_updates_cache_index_for_saved_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)

            def fake_fetch_paper(query, **kwargs):
                create_cached_downloads(kwargs["context"].download_dir, query)
                return sample_envelope(modes=kwargs["modes"], doi=query)

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(
                    mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper
                ),
            ):
                payload = mcp_tools.fetch_paper_payload(
                    query="10.1000/example",
                    download_dir=download_dir,
                )

            self.assertEqual(payload["doi"], "10.1000/example")
            listed = mcp_tools.list_cached_payload(download_dir=download_dir)
            self.assertEqual(len(listed["entries"]), 4)
            self.assertTrue((download_dir / ".paper-fetch-mcp-cache.json").exists())
            self.assertEqual(
                {entry["kind"] for entry in listed["entries"]},
                {"asset", "fetch_envelope", "markdown", "primary_payload"},
            )

    def test_list_cached_payload_reads_manifest_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            create_cached_downloads(download_dir, "10.1000/example")

            listed = mcp_tools.list_cached_payload(download_dir=download_dir)

        self.assertEqual(listed["entries"], [])

    def test_get_cached_payload_refreshes_single_doi_and_returns_preferred_paths(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            create_cached_downloads(download_dir, "10.1000/example")

            payload = mcp_tools.get_cached_payload(
                doi="10.1000/example",
                download_dir=download_dir,
            )
            listed = mcp_tools.list_cached_payload(download_dir=download_dir)

        self.assertEqual(payload["status"], "hit")
        self.assertEqual(len(payload["entries"]), 1)
        self.assertIsNotNone(payload["preferred"]["markdown"])
        self.assertIsNone(payload["preferred"]["primary_payload"])
        self.assertEqual(payload["preferred"]["assets"], [])
        self.assertEqual(len(listed["entries"]), 1)

    def test_batch_resolve_payload_reuses_transport_and_aborts_on_rate_limit(
        self,
    ) -> None:
        transport_ids: list[int] = []
        seen_queries: list[str] = []

        def fake_resolve(query, *, context=None):
            seen_queries.append(query)
            transport_ids.append(id(context.transport if context is not None else None))
            if query == "second":
                raise ProviderFailure(
                    "rate_limited",
                    "Slow down.",
                    retry_after_seconds=3,
                    source_trail=["fulltext:rate_limited"],
                )
            return sample_resolved_query(query)

        with mock.patch.object(
            mcp_tools, "service_resolve_paper", side_effect=fake_resolve
        ):
            payload = mcp_tools.batch_resolve_payload(
                queries=["first", "second", "third"]
            )

        self.assertTrue(payload["aborted"])
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["abort_reason"]["status"], "rate_limited")
        self.assertEqual(payload["abort_reason"]["code"], "rate_limited")
        self.assertEqual(payload["abort_reason"]["retry_after_seconds"], 3)
        self.assertEqual(
            payload["abort_reason"]["source_trail"], ["fulltext:rate_limited"]
        )
        self.assertEqual(len(payload["results"]), 3)
        self.assertEqual([item["index"] for item in payload["results"]], [1, 2, 3])
        self.assertEqual(payload["results"][2]["status"], "not_scheduled")
        self.assertEqual(
            payload["progress"],
            {"total": 3, "terminal": 3, "completed": 2, "not_scheduled": 1},
        )
        self.assertEqual(seen_queries, ["first", "second"])
        self.assertEqual(len(set(transport_ids)), 1)

    def test_batch_resolve_payload_aborts_on_retry_after_machine_field(
        self,
    ) -> None:
        seen_queries: list[str] = []

        def fake_resolve(query, *, context=None):
            seen_queries.append(query)
            if query == "second":
                raise ProviderFailure(
                    "error",
                    "Provider asked to retry later.",
                    retry_after_seconds=12,
                )
            return sample_resolved_query(query)

        with mock.patch.object(
            mcp_tools, "service_resolve_paper", side_effect=fake_resolve
        ):
            payload = mcp_tools.batch_resolve_payload(
                queries=["first", "second", "third"]
            )

        self.assertTrue(payload["aborted"])
        self.assertEqual(payload["abort_reason"]["status"], "error")
        self.assertEqual(payload["abort_reason"]["code"], "error")
        self.assertEqual(payload["abort_reason"]["retry_after_seconds"], 12)
        self.assertEqual(seen_queries, ["first", "second"])

    def test_batch_resolve_payload_supports_optional_concurrency(self) -> None:
        active = 0
        max_active = 0
        lock = threading.Lock()
        barrier = threading.Barrier(2)

        def fake_resolve(query, *, context=None):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            try:
                if query in {"first", "second"}:
                    barrier.wait(timeout=1)
                time.sleep(0.02)
                return sample_resolved_query(query)
            finally:
                with lock:
                    active -= 1

        with mock.patch.object(
            mcp_tools, "service_resolve_paper", side_effect=fake_resolve
        ):
            payload = mcp_tools.batch_resolve_payload(
                queries=["first", "second", "third"],
                concurrency=2,
            )

        self.assertFalse(payload["aborted"])
        self.assertEqual(
            [item["query"] for item in payload["results"]], ["first", "second", "third"]
        )
        self.assertGreaterEqual(max_active, 2)

    def test_batch_resolve_tool_rejects_too_many_queries(self) -> None:
        result = asyncio.run(
            mcp_tools.batch_resolve_tool_async(
                queries=[f"10.1000/{index}" for index in range(51)],
            )
        )

        self.assertTrue(result.is_error)
        self.assertEqual(result.structured_content["status"], "error")
        self.assertIn(
            "queries must contain at most 50 entries.",
            result.structured_content["reason"],
        )

    def test_batch_check_payload_uses_lightweight_results_and_no_downloads(
        self,
    ) -> None:
        transport_ids: list[int] = []

        def fake_probe(query, *, context=None):
            transport_ids.append(id(context.transport if context is not None else None))
            return sample_probe_result(query, doi=query, title=f"Title for {query}")

        with (
            mock.patch.object(
                mcp_tools, "service_probe_has_fulltext", side_effect=fake_probe
            ),
            mock.patch.object(mcp_tools, "service_fetch_paper") as mocked_fetch,
        ):
            payload = mcp_tools.batch_check_payload(
                queries=["10.1000/one", "10.1000/two"], mode="metadata"
            )

        self.assertEqual(payload["mode"], "metadata")
        self.assertFalse(payload["aborted"])
        self.assertEqual(len(payload["results"]), 2)
        self.assertEqual(payload["results"][0]["schema_version"], 2)
        self.assertEqual(payload["results"][0]["query"], "10.1000/one")
        self.assertEqual(payload["results"][0]["doi"], "10.1000/one")
        self.assertEqual(payload["results"][0]["title"], "Title for 10.1000/one")
        self.assertIsNone(payload["results"][0]["has_fulltext"])
        self.assertTrue(payload["results"][0]["likely_has_fulltext"])
        self.assertEqual(payload["results"][0]["probe_state"], "likely_yes")
        self.assertEqual(payload["results"][0]["source"], None)
        self.assertEqual(payload["results"][0]["source_trail"], [])
        self.assertEqual(payload["results"][0]["token_estimate"], None)
        self.assertEqual(payload["results"][0]["token_estimate_breakdown"], None)
        self.assertEqual(len(set(transport_ids)), 1)
        mocked_fetch.assert_not_called()

    def test_batch_check_payload_article_mode_keeps_breakdown(self) -> None:
        with mock.patch.object(
            mcp_tools,
            "service_fetch_paper",
            return_value=sample_envelope(modes={"article"}, doi="10.1000/one"),
        ):
            payload = mcp_tools.batch_check_payload(
                queries=["10.1000/one"], mode="article"
            )

        self.assertEqual(payload["results"][0]["token_estimate"], 128)
        self.assertEqual(
            payload["results"][0]["token_estimate_breakdown"],
            {"abstract": 32, "body": 96, "refs": 24},
        )

    def test_batch_check_article_context_trace_and_request_state_are_isolated(
        self,
    ) -> None:
        barrier = threading.Barrier(2)
        context_ids: list[int] = []
        transport_ids: list[int] = []
        session_ids: list[int] = []

        def fake_fetch(query, *, context=None, modes=None, **_kwargs):
            assert context is not None
            context_ids.append(id(context))
            transport_ids.append(id(context.transport))
            session_ids.append(id(context.session_cache))
            context.fetch_trace[:] = [
                trace_event("fetch", "isolated", "ok", code=query)
            ]
            context.stage_timings["query_marker"] = float(len(query))
            context.session_cache[("query",)] = query
            context.diagnostic_artifacts.append({"query": query})
            barrier.wait(timeout=2)
            envelope = sample_envelope(modes=modes, doi=query)
            envelope.trace = list(context.fetch_trace)
            return envelope

        with mock.patch.object(
            mcp_tools, "service_fetch_paper", side_effect=fake_fetch
        ):
            payload = mcp_tools.batch_check_payload(
                queries=["10.1000/one", "10.1000/two"],
                mode="article",
                concurrency=2,
            )

        self.assertEqual(len(set(context_ids)), 2)
        self.assertEqual(len(set(session_ids)), 2)
        self.assertEqual(len(set(transport_ids)), 1)
        self.assertEqual(
            [item["trace"][0]["code"] for item in payload["results"]],
            ["10.1000/one", "10.1000/two"],
        )

    def test_batch_check_tool_rejects_invalid_concurrency(self) -> None:
        result = asyncio.run(
            mcp_tools.batch_check_tool_async(
                queries=["10.1000/one"],
                mode="metadata",
                concurrency=0,
            )
        )

        self.assertTrue(result.is_error)
        self.assertEqual(result.structured_content["status"], "error")
        self.assertIn("greater than or equal to 1", result.structured_content["reason"])

    def test_batch_check_tool_rejects_too_many_queries(self) -> None:
        result = asyncio.run(
            mcp_tools.batch_check_tool_async(
                queries=[f"10.1000/{index}" for index in range(51)],
                mode="metadata",
            )
        )

        self.assertTrue(result.is_error)
        self.assertEqual(result.structured_content["status"], "error")
        self.assertIn(
            "queries must contain at most 50 entries.",
            result.structured_content["reason"],
        )

    def test_batch_check_payload_aborts_on_rate_limit(self) -> None:
        seen_queries: list[str] = []

        def fake_fetch_paper(query, **kwargs):
            seen_queries.append(query)
            if query == "10.1000/two":
                raise ProviderFailure("rate_limited", "Slow down.")
            return sample_envelope(modes=kwargs["modes"], doi=query)

        with mock.patch.object(
            mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper
        ):
            payload = mcp_tools.batch_check_payload(
                queries=["10.1000/one", "10.1000/two", "10.1000/three"],
                mode="article",
            )

        self.assertTrue(payload["aborted"])
        self.assertEqual(payload["abort_reason"]["status"], "rate_limited")
        self.assertEqual(seen_queries, ["10.1000/one", "10.1000/two"])
        self.assertEqual(len(payload["results"]), 3)
        self.assertEqual(payload["results"][2]["status"], "not_scheduled")

    def test_batch_check_title_queries_use_resolved_provider_lanes(self) -> None:
        providers = {
            "title-a-first": "provider-a",
            "title-b": "provider-b",
            "title-a-later": "provider-a",
        }
        fetch_calls: list[str] = []

        def fake_resolve(query, *, context=None):
            resolved = sample_resolved_query(query)
            resolved.doi = f"10.1000/{query}"
            resolved.provider_hint = providers[query]
            return resolved

        def fake_fetch_paper(query, **kwargs):
            fetch_calls.append(query)
            if query == "title-a-first":
                raise ProviderFailure("rate_limited", "provider A cooldown")
            return sample_envelope(modes=kwargs["modes"], doi="10.1000/title-b")

        with (
            mock.patch.object(
                mcp_tools, "service_resolve_paper", side_effect=fake_resolve
            ),
            mock.patch.object(
                mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper
            ),
        ):
            payload = mcp_tools.batch_check_payload(
                queries=list(providers),
                mode="article",
                concurrency=1,
            )

        self.assertEqual(fetch_calls, ["title-a-first", "title-b"])
        self.assertEqual(
            [item["provider_lane"] for item in payload["results"]],
            ["provider-a", "provider-b", "provider-a"],
        )
        self.assertEqual(
            [item["status"] for item in payload["results"]],
            ["rate_limited", "succeeded", "not_scheduled"],
        )

    def test_batch_check_async_known_dois_use_distinct_local_lanes(self) -> None:
        queries = [
            "10.1016/first",
            "10.1002/other",
            "10.1016/later",
        ]
        fetch_calls: list[str] = []

        def fake_fetch_paper(query, **kwargs):
            fetch_calls.append(query)
            if query == queries[0]:
                raise ProviderFailure("rate_limited", "Elsevier cooldown")
            return sample_envelope(modes=kwargs["modes"], doi=query)

        with (
            mock.patch.object(mcp_tools, "service_resolve_paper") as resolver,
            mock.patch.object(
                mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper
            ),
        ):
            result = asyncio.run(
                mcp_tools.batch_check_tool_async(
                    queries=queries,
                    mode="article",
                    concurrency=1,
                )
            )

        payload = result.structured_content
        self.assertFalse(result.is_error)
        resolver.assert_not_called()
        self.assertEqual(fetch_calls, queries[:2])
        self.assertEqual(
            [item["provider_lane"] for item in payload["results"]],
            ["elsevier", "wiley", "elsevier"],
        )
        self.assertEqual(payload["results"][2]["status"], "not_scheduled")

    def test_batch_resolve_reports_provider_resolved_during_operation(self) -> None:
        resolved = sample_resolved_query("A title query")
        resolved.provider_hint = "wiley"
        with mock.patch.object(
            mcp_tools,
            "service_resolve_paper",
            return_value=resolved,
        ):
            payload = mcp_tools.batch_resolve_payload(queries=["A title query"])

        self.assertEqual(payload["results"][0]["provider_lane"], "wiley")

    def test_batch_check_uses_catalog_source_when_title_lane_stays_generic(
        self,
    ) -> None:
        with (
            mock.patch.object(
                mcp_tools,
                "service_resolve_paper",
                side_effect=RuntimeError("resolver unavailable"),
            ),
            mock.patch.object(
                mcp_tools,
                "service_fetch_paper",
                return_value=sample_envelope(
                    modes={"article"},
                    doi="10.1000/unknown-prefix",
                ),
            ),
        ):
            payload = mcp_tools.batch_check_payload(
                queries=["An unresolved title"],
                mode="article",
            )

        self.assertEqual(payload["results"][0]["provider_lane"], "elsevier")

    def test_resolve_paper_payload_preserves_structured_query(self) -> None:
        captured: dict[str, object] = {}

        def fake_resolve(query, *, context=None):
            captured["query"] = query
            return sample_resolved_query(query.lookup_query)

        with mock.patch.object(
            mcp_tools, "service_resolve_paper", side_effect=fake_resolve
        ):
            payload = mcp_tools.resolve_paper_payload(
                title="Example title",
                authors=[
                    " Alice Example ",
                    "Bob Example",
                    "Alice Example",
                    "Carol Example",
                    "Dana Example",
                ],
                year=2024,
            )

        request = captured["query"]
        self.assertEqual(request.lookup_query, "Example title")
        self.assertEqual(
            request.authors,
            ("Alice Example", "Bob Example", "Carol Example", "Dana Example"),
        )
        self.assertEqual(request.year, 2024)
        self.assertEqual(payload["query"], "Example title")

    def test_resolve_paper_tool_rejects_mixed_query_and_structured_fields(self) -> None:
        result = mcp_tools.resolve_paper_tool(
            query="10.1000/example",
            title="Example Article",
        )

        self.assertTrue(result.is_error)
        self.assertEqual(result.structured_content["status"], "error")
        self.assertIn(
            "either query or structured title/authors/year",
            result.structured_content["reason"],
        )

    def test_has_fulltext_tool_serializes_probe_result(self) -> None:
        server = build_server()
        with mock.patch.object(
            mcp_tools,
            "service_probe_has_fulltext",
            return_value=sample_probe_result(
                "10.1000/example", title="Example Article"
            ),
        ):
            result = mcp_tools.has_fulltext_tool(query="10.1000/example")

        self.assertFalse(result.is_error)
        self.assertEqual(result.structured_content["doi"], "10.1000/example")
        self.assertEqual(result.structured_content["state"], "likely_yes")
        self.assertEqual(
            result.structured_content["evidence"], ["crossref_fulltext_link"]
        )
        self.assertNotIn("title", result.structured_content)
        assert_mcp_tool_omits_output_schema(
            server, "has_fulltext", result.structured_content
        )

    def test_has_fulltext_tool_keeps_ambiguous_error_payload(self) -> None:
        error = PaperFetchFailure(
            "ambiguous",
            "Query resolution is ambiguous; choose one of the DOI candidates.",
            candidates=[{"doi": "10.1000/one"}],
        )
        server = build_server()
        with mock.patch.object(
            mcp_tools, "service_probe_has_fulltext", side_effect=error
        ):
            result = mcp_tools.has_fulltext_tool(query="Example title")

        self.assertTrue(result.is_error)
        self.assertEqual(result.structured_content["status"], "ambiguous")
        self.assertEqual(
            result.structured_content["candidates"], [{"doi": "10.1000/one"}]
        )
        assert_mcp_tool_omits_output_schema(
            server, "has_fulltext", result.structured_content
        )

    def test_fetch_paper_tool_error_payload_survives_without_output_schema(
        self,
    ) -> None:
        server = build_server()

        result = asyncio.run(
            mcp_tools.fetch_paper_tool_async(query="10.1000/example", modes=["pdf"])
        )

        self.assertTrue(result.is_error)
        self.assertEqual(result.structured_content["status"], "error")
        self.assertNotIn("acceptance", result.structured_content)
        assert_mcp_tool_omits_output_schema(
            server, "fetch_paper", result.structured_content
        )

    def test_fetch_paper_tool_rejects_negative_inline_image_budget_before_service_call(
        self,
    ) -> None:
        with mock.patch.object(mcp_tools, "service_fetch_paper") as mocked_fetch:
            result = asyncio.run(
                mcp_tools.fetch_paper_tool_async(
                    query="10.1000/example",
                    strategy={"inline_image_budget": {"max_images": -1}},
                )
            )

        self.assertTrue(result.is_error)
        self.assertIn("greater than or equal to 0", result.structured_content["reason"])
        mocked_fetch.assert_not_called()
