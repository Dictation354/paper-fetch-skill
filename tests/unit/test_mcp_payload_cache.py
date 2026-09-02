from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest import mock

from paper_fetch.mcp import fetch_tool as mcp_fetch_tool
from paper_fetch.mcp._deps import default_mcp_deps
from paper_fetch.mcp.cache_index import (
    IDENTITY_PROOF_MARKDOWN_REGISTRATION,
    LOCK_DIRNAME,
    cache_lock_dir,
)
from paper_fetch.mcp.cache_payloads import list_cached_payload
from paper_fetch.mcp.fetch_cache import (
    FETCH_ENVELOPE_CACHE_VERSION,
    PUBLIC_CREDENTIAL_SCOPE,
    FetchCache,
    article_from_payload,
    cache_request_fingerprint,
    envelope_from_payload,
    fetch_envelope_cache_path,
    payload_from_envelope,
    request_cache_payload,
)
from paper_fetch.mcp.fetch_tool import (
    _PROVIDER_STATUS_ORDER,
    fetch_paper_payload,
    fetch_paper_tool_async,
    provider_status_tool,
)
from paper_fetch.mcp.schemas import FetchPaperRequest
from paper_fetch.mcp.server import build_server
from paper_fetch.models import (
    EXTRACTION_REVISION,
    QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION,
    Asset,
    FetchEnvelope,
    Metadata,
    Quality,
    RenderOptions,
)
from paper_fetch.providers.browser_runtime.backends import camoufox as camoufox_backend
from paper_fetch.runtime import RuntimeContext
from paper_fetch.service import FetchStrategy
from paper_fetch.tracing import TraceContext, trace_event
from tests.golden_criteria import golden_criteria_scenario_asset

from ._mcp_support import (
    create_cached_downloads,
    create_cached_fetch_envelope,
    mcp_test_deps,
    sample_envelope,
    sample_resolved_query,
)


class McpPayloadCacheTests(unittest.TestCase):
    def test_strict_asset_strategy_is_normalized_and_changes_cache_fingerprint(
        self,
    ) -> None:
        default_request = FetchPaperRequest.model_validate(
            {
                "query": "10.1000/strict-cache",
                "strategy": {"asset_profile": "body"},
            }
        )
        strict_request = FetchPaperRequest.model_validate(
            {
                "query": "10.1000/strict-cache",
                "strategy": {
                    "asset_profile": "body",
                    "require_full_size_body_assets": True,
                },
            }
        )

        strict_payload = request_cache_payload(strict_request)
        self.assertTrue(strict_request.strategy.require_local_body_assets)
        self.assertTrue(strict_payload["strategy"]["require_local_body_assets"])
        self.assertTrue(strict_payload["strategy"]["require_full_size_body_assets"])
        self.assertNotEqual(
            cache_request_fingerprint(
                default_request.query,
                request_cache_payload(default_request),
            ),
            cache_request_fingerprint(
                strict_request.query,
                strict_payload,
            ),
        )

    def test_sync_fetch_payload_owns_one_context_through_markdown_commit(
        self,
    ) -> None:
        instances: list[RuntimeContext] = []
        captured: dict[str, object] = {}
        original_save = mcp_fetch_tool.save_markdown_to_disk

        class TrackingRuntimeContext(RuntimeContext):
            close_count = 0

            def __post_init__(self) -> None:
                super().__post_init__()
                instances.append(self)

            def close(self) -> None:
                self.close_count += 1
                super().close()

        def fake_fetch(request, *, context=None, **_kwargs):
            captured["fetch_context"] = context
            return sample_envelope(
                modes=set(request.requested_modes()),
                doi=request.query,
            )

        def tracked_save(*args, **kwargs):
            captured["save_guard"] = kwargs.get("commit_guard")
            return original_save(*args, **kwargs)

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                mock.patch.object(
                    mcp_fetch_tool, "RuntimeContext", TrackingRuntimeContext
                ),
                mock.patch.object(
                    mcp_fetch_tool, "save_markdown_to_disk", side_effect=tracked_save
                ),
            ):
                payload = mcp_fetch_tool.fetch_paper_payload(
                    query="10.1000/one-context",
                    save_markdown=True,
                    markdown_filename="one.md",
                    download_dir=Path(tmpdir),
                    deps=replace(default_mcp_deps(), fetch_paper_envelope=fake_fetch),
                )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(len(instances), 1)
        self.assertIs(captured["fetch_context"], instances[0])
        self.assertIs(captured["save_guard"], instances[0].commit_guard)
        self.assertEqual(instances[0].close_count, 1)

    def test_v2_writer_has_one_top_level_trace_owner_and_preserves_retries(
        self,
    ) -> None:
        request = FetchPaperRequest(
            query="10.1000/trace-v2",
            modes=["article", "markdown"],
        )
        envelope = sample_envelope(
            modes={"article", "markdown"},
            doi=request.query,
        )
        envelope.trace = [
            trace_event(
                "fulltext",
                "springer_html",
                "fail",
                code="publisher_paywall",
                context=TraceContext(attempt=1, attempt_id="html-1"),
            ),
            trace_event(
                "fulltext",
                "springer_html",
                "fail",
                code="publisher_paywall",
                context=TraceContext(attempt=2, attempt_id="html-2"),
            ),
        ]

        payload = payload_from_envelope(envelope, request)
        round_trip = envelope_from_payload(payload)

        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(len(payload["trace"]), 2)
        self.assertNotIn("trace", payload["quality"])
        self.assertNotIn("trace", payload["article"]["quality"])
        self.assertEqual(
            [event.attempt_id for event in round_trip.trace],
            ["html-1", "html-2"],
        )

    def test_v5_sidecar_reader_projects_legacy_quality_fields_to_one_owner(
        self,
    ) -> None:
        request = FetchPaperRequest(
            query="10.1000/quality-owner",
            modes=["article", "markdown"],
        )
        envelope = sample_envelope(
            modes={"article", "markdown"},
            doi=request.query,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            FetchCache(download_dir).write_fetch_envelope(envelope, request)
            sidecar = json.loads(
                fetch_envelope_cache_path(download_dir, request.query).read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(FETCH_ENVELOPE_CACHE_VERSION, 5)
        self.assertEqual(sidecar["version"], 5)
        self.assertEqual(sidecar["payload"]["schema_version"], 2)
        self.assertIn("has_fulltext", sidecar["payload"])
        self.assertIn("token_estimate_breakdown", sidecar["payload"])

        round_trip = envelope_from_payload(sidecar["payload"])
        assert round_trip.article is not None
        self.assertIs(round_trip.quality, round_trip.article.quality)
        self.assertIs(round_trip.warnings, round_trip.quality.warnings)
        self.assertIs(round_trip.source_trail, round_trip.quality.source_trail)
        self.assertIs(
            round_trip.token_estimate_breakdown,
            round_trip.quality.token_estimate_breakdown,
        )

        round_trip.warnings.append("cache projection mutation")
        round_trip.article.quality.token_estimate = 654

        self.assertIn("cache projection mutation", round_trip.article.quality.warnings)
        self.assertEqual(round_trip.token_estimate, 654)

    def test_build_server_omits_output_schemas_for_all_tools(self) -> None:
        server = build_server()
        for tool in asyncio.run(server.list_native_tools()):
            self.assertIsNone(tool.output_schema, tool.name)

    def test_build_server_exposes_expected_tool_annotations(self) -> None:
        server = build_server()
        expected = {
            "resolve_paper": {"read_only_hint": True, "open_world_hint": True},
            "has_fulltext": {"read_only_hint": True, "open_world_hint": True},
            "fetch_paper": {
                "read_only_hint": False,
                "destructive_hint": False,
                "idempotent_hint": False,
                "open_world_hint": True,
            },
            "batch_fetch": {
                "read_only_hint": False,
                "destructive_hint": False,
                "idempotent_hint": False,
                "open_world_hint": True,
            },
            "list_cached": {"read_only_hint": True, "open_world_hint": False},
            "get_cached": {"read_only_hint": True, "open_world_hint": False},
            "batch_resolve": {"read_only_hint": True, "open_world_hint": True},
            "batch_check": {"read_only_hint": True, "open_world_hint": True},
            "browser_preflight": {
                "read_only_hint": False,
                "destructive_hint": False,
                "idempotent_hint": False,
                "open_world_hint": True,
            },
            "provider_status": {
                "read_only_hint": True,
                "open_world_hint": False,
            },
        }

        tools = {tool.name: tool for tool in asyncio.run(server.list_native_tools())}
        self.assertEqual(set(tools), set(expected))
        for name, tool in tools.items():
            self.assertIsNotNone(tool.annotations, name)
            for field_name, value in expected[name].items():
                self.assertEqual(
                    getattr(tool.annotations, field_name), value, f"{name}.{field_name}"
                )

    def test_provider_status_tool_returns_success_when_providers_are_unconfigured(
        self,
    ) -> None:
        blank_env = {
            "CROSSREF_MAILTO": "",
            "ELSEVIER_API_KEY": "",
        }
        missing_dependencies = {
            "probe": "unit_test",
            "packages": {"playwright": False, "camoufox": False},
        }
        with mock.patch.object(
            camoufox_backend,
            "_dependency_details",
            return_value=missing_dependencies,
        ):
            result = provider_status_tool(
                deps=mcp_test_deps(build_runtime_env=lambda _env=None: blank_env)
            )

        self.assertFalse(result.is_error)
        providers = result.structured_content["providers"]
        self.assertEqual(
            [entry["provider"] for entry in providers],
            list(_PROVIDER_STATUS_ORDER),
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
                entry["provider"] == "science" and entry["status"] == "not_configured"
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

        payload = fetch_paper_payload(
            query="10.1000/example",
            deps=mcp_test_deps(
                build_runtime_env=lambda _env=None: runtime_env,
                resolve_mcp_download_dir=lambda _env: default_download_dir,
                service_fetch_paper=fake_fetch_paper,
            ),
        )

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

                payload = fetch_paper_payload(
                    query="10.1000/example",
                    artifact_mode=artifact_mode,
                    download_dir=download_dir,
                    deps=mcp_test_deps(
                        build_runtime_env=lambda _env=None: {},
                        service_fetch_paper=fake_fetch_paper,
                    ),
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
            payload = fetch_paper_payload(
                query="10.1000/example",
                artifact_mode="none",
                download_dir=download_dir,
                deps=mcp_test_deps(
                    build_runtime_env=lambda _env=None: {},
                    service_fetch_paper=fake_fetch_paper,
                ),
            )

            sidecar_path = download_dir / "10.1000_example.fetch-envelope.json"
            sidecar_exists = sidecar_path.exists()
            listed_kinds = {
                entry["kind"]
                for entry in list_cached_payload(download_dir=download_dir)["entries"]
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

        mocked_resolve = mock.Mock()
        fetch_paper_payload(
            query="10.1000/example",
            download_dir=explicit_download_dir,
            deps=mcp_test_deps(
                build_runtime_env=lambda _env=None: {
                    "PAPER_FETCH_DOWNLOAD_DIR": "/tmp/shared"
                },
                resolve_mcp_download_dir=mocked_resolve,
                service_fetch_paper=fake_fetch_paper,
            ),
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

            mocked_resolve = mock.Mock()
            mocked_fetch = mock.Mock(
                return_value=sample_envelope(modes={"markdown"}, doi="10.1000/example")
            )
            payload = fetch_paper_payload(
                query="10.1000/example",
                modes=["markdown"],
                download_dir=download_dir,
                deps=mcp_test_deps(
                    build_runtime_env=lambda _env=None: {},
                    service_resolve_paper=mocked_resolve,
                    service_fetch_paper=mocked_fetch,
                ),
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
            payload = fetch_paper_payload(
                query="10.1000/example",
                no_download=True,
                download_dir=download_dir,
                deps=mcp_test_deps(
                    build_runtime_env=lambda _env=None: {},
                    service_fetch_paper=fake_fetch_paper,
                ),
            )

            self.assertEqual(payload["doi"], "10.1000/example")
            self.assertIsNone(captured["context"].download_dir)
            self.assertEqual(captured["context"].artifact_mode, "none")
            self.assertFalse(download_dir.exists())

    def test_fetch_paper_payload_save_markdown_writes_file_and_returns_path(
        self,
    ) -> None:
        captured: dict[str, object] = {}

        def fake_fetch_paper(query, **kwargs):
            captured.update(kwargs)
            return sample_envelope(modes=kwargs["modes"], doi=query)

        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            payload = fetch_paper_payload(
                query="10.1000/example",
                save_markdown=True,
                markdown_filename="custom.md",
                download_dir=download_dir,
                deps=mcp_test_deps(
                    build_runtime_env=lambda _env=None: {},
                    service_fetch_paper=fake_fetch_paper,
                ),
            )

            saved_path = download_dir / "custom.md"
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
            payload = fetch_paper_payload(
                query="10.1000/example",
                save_markdown=True,
                download_dir=download_dir,
                deps=mcp_test_deps(
                    build_runtime_env=lambda _env=None: {},
                    service_fetch_paper=lambda *_args, **_kwargs: envelope,
                ),
            )

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
            payload = fetch_paper_payload(
                query="10.1000/example",
                no_download=True,
                save_markdown=True,
                download_dir=download_dir,
                deps=mcp_test_deps(
                    build_runtime_env=lambda _env=None: {},
                    service_fetch_paper=fake_fetch_paper,
                ),
            )

            self.assertIsNone(captured["context"].download_dir)
            self.assertTrue((download_dir / "Example_2026_Example_Article.md").exists())
            self.assertFalse(
                (download_dir / "10.1000_example.fetch-envelope.json").exists()
            )
            self.assertFalse((download_dir / "10.1000_example.xml").exists())
            self.assertFalse((download_dir / "10.1000_example_assets").exists())
            self.assertIsNone(payload["markdown"])
            self.assertIsNone(payload["article"])
            listed = list_cached_payload(download_dir=download_dir)
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

        fetch_paper_payload(
            query="10.1000/example",
            strategy={"preferred_providers": [" Wiley ", "crossref", "wiley", ""]},
            deps=mcp_test_deps(
                build_runtime_env=lambda _env=None: {},
                resolve_mcp_download_dir=lambda _env: Path("/tmp/downloads"),
                service_fetch_paper=fake_fetch_paper,
            ),
        )

        strategy = captured["strategy"]
        assert isinstance(strategy, FetchStrategy)
        self.assertEqual(strategy.preferred_providers, ["wiley", "crossref"])

    def test_fetch_paper_tool_rejects_invalid_modes_before_service_call(self) -> None:
        mocked_fetch = mock.Mock()
        result = asyncio.run(
            fetch_paper_tool_async(
                query="10.1000/example",
                modes=["pdf"],
                deps=mcp_test_deps(service_fetch_paper=mocked_fetch),
            )
        )

        self.assertTrue(result.is_error)
        self.assertIn("unsupported output modes", result.structured_content["reason"])
        mocked_fetch.assert_not_called()

    def test_fetch_paper_tool_rejects_invalid_include_refs_before_service_call(
        self,
    ) -> None:
        mocked_fetch = mock.Mock()
        result = asyncio.run(
            fetch_paper_tool_async(
                query="10.1000/example",
                include_refs="summary",
                deps=mcp_test_deps(service_fetch_paper=mocked_fetch),
            )
        )

        self.assertTrue(result.is_error)
        self.assertIn(
            "unsupported include_refs value", result.structured_content["reason"]
        )
        mocked_fetch.assert_not_called()

    def test_fetch_paper_tool_rejects_invalid_asset_profile_before_service_call(
        self,
    ) -> None:
        mocked_fetch = mock.Mock()
        result = asyncio.run(
            fetch_paper_tool_async(
                query="10.1000/example",
                strategy={"asset_profile": "full"},
                deps=mcp_test_deps(service_fetch_paper=mocked_fetch),
            )
        )

        self.assertTrue(result.is_error)
        self.assertIn(
            "unsupported asset_profile value", result.structured_content["reason"]
        )
        mocked_fetch.assert_not_called()

    def test_fetch_paper_tool_rejects_invalid_artifact_mode_before_service_call(
        self,
    ) -> None:
        mocked_fetch = mock.Mock()
        result = asyncio.run(
            fetch_paper_tool_async(
                query="10.1000/example",
                artifact_mode="debug",
                deps=mcp_test_deps(service_fetch_paper=mocked_fetch),
            )
        )

        self.assertTrue(result.is_error)
        self.assertIn(
            "unsupported artifact_mode value", result.structured_content["reason"]
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

            mocked_fetch = mock.Mock()
            payload = fetch_paper_payload(
                query="10.1000/example",
                modes=["markdown"],
                prefer_cache=True,
                download_dir=download_dir,
                deps=mcp_test_deps(
                    build_runtime_env=lambda _env=None: {},
                    service_resolve_paper=lambda *_args, **_kwargs: (
                        sample_resolved_query("10.1000/example")
                    ),
                    service_fetch_paper=mocked_fetch,
                ),
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

            mocked_fetch = mock.Mock()
            payload = fetch_paper_payload(
                query="10.1000/example",
                modes=["markdown"],
                prefer_cache=True,
                artifact_mode="none",
                download_dir=download_dir,
                deps=mcp_test_deps(
                    build_runtime_env=lambda _env=None: {},
                    service_resolve_paper=lambda *_args, **_kwargs: (
                        sample_resolved_query("10.1000/example")
                    ),
                    service_fetch_paper=mocked_fetch,
                ),
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

            mocked_fetch = mock.Mock()
            payload = fetch_paper_payload(
                query="10.1000/example",
                modes=["markdown"],
                prefer_cache=True,
                save_markdown=True,
                download_dir=download_dir,
                deps=mcp_test_deps(
                    build_runtime_env=lambda _env=None: {},
                    service_resolve_paper=lambda *_args, **_kwargs: (
                        sample_resolved_query("10.1000/example")
                    ),
                    service_fetch_paper=mocked_fetch,
                ),
            )

            saved_path = download_dir / "Example_2026_Example_Article.md"
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

            mocked_fetch = mock.Mock(
                return_value=sample_envelope(modes={"article"}, doi="10.1000/example")
            )
            payload = fetch_paper_payload(
                query="10.1000/example",
                modes=["article"],
                prefer_cache=True,
                download_dir=download_dir,
                deps=mcp_test_deps(
                    build_runtime_env=lambda _env=None: {},
                    service_resolve_paper=lambda *_args, **_kwargs: (
                        sample_resolved_query("10.1000/example")
                    ),
                    service_fetch_paper=mocked_fetch,
                ),
            )

        self.assertEqual(payload["doi"], "10.1000/example")
        self.assertIsNotNone(payload["article"])
        mocked_fetch.assert_called_once()

    def test_article_payload_preserves_asset_download_diagnostics(self) -> None:
        payload = json.loads(
            golden_criteria_scenario_asset(
                "asset_download_diagnostics", "article_payload.json"
            ).read_text(encoding="utf-8")
        )
        payload["assets"][0]["provenance"] = [
            "conversion_degraded",
            "conversion_degraded",
        ]
        payload["assets"][0]["browser_backend"] = "camoufox"
        payload["assets"][0]["final_fetcher"] = "camoufox"
        payload["assets"][0]["recovery_attempts"] = [
            {"stage": "direct", "status": 403},
            {
                "stage": "browser",
                "browser_backend": "camoufox",
                "reason": "recovered",
            },
        ]
        payload["quality"] = asdict(Quality())
        article = article_from_payload(payload)

        self.assertIsNotNone(article)
        assert article is not None
        asset = article.assets[0]
        self.assertEqual(asset.render_state, "appendix")
        self.assertEqual(asset.anchor_key, "F1")
        self.assertEqual(asset.download_tier, "preview")
        self.assertEqual(asset.download_url, "https://example.test/figure-preview.png")
        self.assertEqual(asset.width, 640)
        self.assertEqual(asset.height, 480)
        self.assertEqual(asset.browser_backend, "camoufox")
        self.assertEqual(asset.final_fetcher, "camoufox")
        self.assertEqual(asset.recovery_attempts[0]["status"], 403)
        self.assertEqual(asset.provenance, ["conversion_degraded"])

    def test_fetch_envelope_payload_preserves_quality_asset_failures(self) -> None:
        request = FetchPaperRequest(query="10.1000/example", modes=["article"])
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
                "reason": "aws_waf_challenge",
                "challenge_provider": "aws_waf",
                "recovery_attempts": [
                    {
                        "status": "failed",
                        "url": "https://example.test/figure-page",
                        "reason": "aws_waf_challenge",
                    }
                ],
            }
        ]
        envelope.quality = envelope.article.quality
        envelope.article.assets = [
            Asset(
                kind="figure",
                heading="Figure 1",
                download_tier="full_size",
                browser_backend="camoufox",
                final_fetcher="camoufox",
                recovery_attempts=[
                    {"stage": "direct", "status": 403},
                    {"stage": "browser", "reason": "recovered"},
                ],
            )
        ]

        payload = payload_from_envelope(envelope, request)
        round_trip = envelope_from_payload(payload)

        self.assertEqual(payload["quality"]["asset_failures"][0]["status"], 403)
        self.assertEqual(
            payload["quality"]["asset_failures"][0]["reason"], "aws_waf_challenge"
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
        self.assertEqual(
            round_trip.quality.asset_failures[0]["challenge_provider"], "aws_waf"
        )
        self.assertEqual(payload["article"]["assets"][0]["browser_backend"], "camoufox")
        self.assertEqual(round_trip.article.assets[0].final_fetcher, "camoufox")
        self.assertEqual(
            round_trip.article.assets[0].recovery_attempts[0]["status"], 403
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

            mocked_fetch = mock.Mock(
                return_value=sample_envelope(modes={"markdown"}, doi="10.1000/example")
            )
            payload = fetch_paper_payload(
                query="10.1000/example",
                modes=["markdown"],
                prefer_cache=True,
                download_dir=download_dir,
                deps=mcp_test_deps(
                    build_runtime_env=lambda _env=None: {},
                    service_resolve_paper=lambda *_args, **_kwargs: (
                        sample_resolved_query("10.1000/example")
                    ),
                    service_fetch_paper=mocked_fetch,
                ),
            )

        self.assertEqual(payload["doi"], "10.1000/example")
        self.assertNotIn(
            QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION, payload["quality"]["flags"]
        )
        mocked_fetch.assert_called_once()

    def test_fetch_cache_write_refreshes_index_with_scoped_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            request = FetchPaperRequest(query="10.1000/example", modes=["markdown"])
            envelope = sample_envelope(modes={"markdown"}, doi="10.1000/example")

            FetchCache(download_dir).write_fetch_envelope(envelope, request)
            entries = list_cached_payload(download_dir=download_dir)["entries"]
            lock_dir_exists = cache_lock_dir(download_dir).is_dir()

        self.assertEqual([entry["kind"] for entry in entries], ["fetch_envelope"])
        self.assertEqual(entries[0]["doi"], "10.1000/example")
        self.assertTrue(lock_dir_exists)
        self.assertFalse(
            any(LOCK_DIRNAME in str(entry.get("path") or "") for entry in entries)
        )

    def test_fetch_cache_keeps_request_variants_and_credential_scopes_separate(
        self,
    ) -> None:
        doi = "10.1000/example"
        credential_scope = "credential:" + ("a" * 64)
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            public_cache = FetchCache(
                download_dir,
                credential_scope=PUBLIC_CREDENTIAL_SCOPE,
            )
            credential_cache = FetchCache(
                download_dir,
                credential_scope=credential_scope,
            )
            markdown_request = FetchPaperRequest(
                query=doi,
                modes=["markdown"],
                prefer_cache=True,
            )
            metadata_request = FetchPaperRequest(
                query=doi,
                modes=["metadata"],
                prefer_cache=True,
            )
            public_markdown = sample_envelope(modes={"markdown"}, doi=doi)
            public_markdown.markdown = "# Public markdown\n"
            public_metadata = sample_envelope(modes={"metadata"}, doi=doi)
            assert public_metadata.metadata is not None
            public_metadata.metadata.title = "Public metadata"
            private_markdown = sample_envelope(modes={"markdown"}, doi=doi)
            private_markdown.markdown = "# Credential markdown\n"

            public_cache.write_fetch_envelope(public_markdown, markdown_request)
            public_cache.write_fetch_envelope(public_metadata, metadata_request)
            credential_cache.write_fetch_envelope(
                private_markdown,
                markdown_request,
            )

            variant_paths = list(
                download_dir.glob("10.1000_example.*.fetch-envelope.json")
            )
            with RuntimeContext(env={}, download_dir=download_dir) as context:
                public_markdown_hit = public_cache.load_fetch_envelope(
                    markdown_request,
                    resolve_paper_fn=lambda *_args, **_kwargs: sample_resolved_query(
                        doi
                    ),
                    context=context,
                )
                public_metadata_hit = public_cache.load_fetch_envelope(
                    metadata_request,
                    resolve_paper_fn=lambda *_args, **_kwargs: sample_resolved_query(
                        doi
                    ),
                    context=context,
                )
                credential_hit = credential_cache.load_fetch_envelope(
                    markdown_request,
                    resolve_paper_fn=lambda *_args, **_kwargs: sample_resolved_query(
                        doi
                    ),
                    context=context,
                )

        self.assertEqual(len(variant_paths), 3)
        self.assertEqual(public_markdown_hit.markdown, "# Public markdown\n")
        self.assertEqual(public_metadata_hit.metadata.title, "Public metadata")
        self.assertEqual(credential_hit.markdown, "# Credential markdown\n")
