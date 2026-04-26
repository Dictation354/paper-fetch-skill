from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch.mcp.cache_index import (
    cache_scope_id,
    scoped_cache_index_resource_uri,
    scoped_cached_resource_uri_prefix,
)
from paper_fetch.mcp import server as mcp_server
from paper_fetch.mcp import tools as mcp_tools
from paper_fetch.mcp.fetch_cache import FetchCache
from paper_fetch.mcp.server import build_server
from paper_fetch.models import (
    ArticleModel,
    Asset,
    EXTRACTION_REVISION,
    FetchEnvelope,
    Metadata,
    Quality,
    QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION,
    RenderOptions,
    Section,
    TokenEstimateBreakdown,
)
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.resolve.query import ResolvedQuery
from paper_fetch.service import FetchStrategy, HasFulltextProbeResult, PaperFetchFailure
from paper_fetch.utils import sanitize_filename


def sample_article() -> ArticleModel:
    return ArticleModel(
        doi="10.1000/example",
        source="elsevier_xml",
        metadata=Metadata(
            title="Example Article",
            authors=["Alice Example"],
            abstract="Example abstract",
            journal="Example Journal",
            published="2026-01-01",
        ),
        sections=[Section(heading="Introduction", level=2, kind="body", text="Example body.")],
        references=[],
        assets=[],
        quality=Quality(
            has_fulltext=True,
            token_estimate=128,
            warnings=["example warning"],
            source_trail=["source:ok"],
            token_estimate_breakdown=TokenEstimateBreakdown(abstract=32, body=96, refs=24),
        ),
    )


def sample_envelope(*, modes: set[str], doi: str = "10.1000/example") -> FetchEnvelope:
    article = sample_article()
    article.doi = doi
    article.metadata.title = "Example Article" if doi == "10.1000/example" else f"Article for {doi}"
    return FetchEnvelope(
        doi=doi,
        source="elsevier_xml",
        has_fulltext=True,
        warnings=["example warning"],
        source_trail=["source:ok"],
        token_estimate=article.quality.token_estimate,
        token_estimate_breakdown=article.quality.token_estimate_breakdown,
        quality=article.quality,
        article=article if "article" in modes else None,
        markdown="# Example Article\n\nExample body.\n" if "markdown" in modes else None,
        metadata=article.metadata if "metadata" in modes else None,
    )


def sample_resolved_query(query: str) -> ResolvedQuery:
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


def sample_probe_result(
    query: str,
    *,
    doi: str | None = None,
    title: str | None = None,
    state: str = "likely_yes",
    evidence: list[str] | None = None,
    warnings: list[str] | None = None,
) -> HasFulltextProbeResult:
    return HasFulltextProbeResult(
        query=query,
        doi=doi or (query if query.startswith("10.") else "10.1000/example"),
        title=title or f"Article for {query}",
        state=state,
        evidence=list(evidence or ["crossref_fulltext_link"]),
        warnings=list(warnings or []),
    )


def create_cached_downloads(download_dir: Path, doi: str) -> None:
    base = sanitize_filename(doi)
    download_dir.mkdir(parents=True, exist_ok=True)
    (download_dir / f"{base}.xml").write_text("<article />", encoding="utf-8")
    (download_dir / f"{base}.md").write_text("# Cached Markdown\n", encoding="utf-8")
    asset_dir = download_dir / f"{base}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "figure-1.png").write_bytes(b"\x89PNG\r\n")


def create_cached_fetch_envelope(
    download_dir: Path,
    doi: str,
    *,
    modes: list[str] | None = None,
    extraction_revision: int = EXTRACTION_REVISION,
) -> None:
    request = {
        "modes": list(modes or ["article", "markdown"]),
        "strategy": {
            "allow_metadata_only_fallback": True,
            "preferred_providers": None,
            "asset_profile": None,
        },
        "include_refs": None,
        "max_tokens": "full_text",
    }
    payload = sample_envelope(modes=set(request["modes"]), doi=doi).to_dict()
    path = mcp_tools._fetch_envelope_cache_path(download_dir, doi)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": mcp_tools._FETCH_ENVELOPE_CACHE_VERSION,
                "extraction_revision": extraction_revision,
                "request": request,
                "payload": payload,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    mcp_tools.refresh_cache_index_for_doi(download_dir, doi)


def write_binary(path: Path, size: int = 8) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n" + (b"x" * max(0, size - 6)))


def fake_service_fetch_with_cached_downloads(query, *, modes=None, download_dir=None, **kwargs):
    if download_dir is not None:
        create_cached_downloads(download_dir, query)
    return sample_envelope(modes=set(modes or []), doi=query)


async def wait_for_threading_event(event: threading.Event, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if event.is_set():
            return True
        await asyncio.sleep(0.01)
    return event.is_set()


class FakeSession:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []
        self.resource_list_changed_calls = 0

    async def send_log_message(self, *, level, data, logger=None, related_request_id=None) -> None:
        self.messages.append(
            {
                "level": level,
                "data": data,
                "logger": logger,
                "related_request_id": related_request_id,
            }
        )

    async def send_resource_list_changed(self) -> None:
        self.resource_list_changed_calls += 1


class FakeContext:
    def __init__(self) -> None:
        self.progress: list[tuple[float, float | None, str | None]] = []
        self.session = FakeSession()
        self.request_id = "unit-request"

    async def report_progress(self, progress: float, total: float | None = None, message: str | None = None) -> None:
        self.progress.append((progress, total, message))


class McpToolTests(unittest.TestCase):
    def test_build_server_exposes_output_schemas_for_all_tools(self) -> None:
        server = build_server()
        for name, tool in server._tool_manager._tools.items():
            self.assertIsNotNone(tool.output_schema, name)

    def test_build_server_advertises_resource_list_changed_capability(self) -> None:
        server = build_server()

        options = server._mcp_server.create_initialization_options()

        self.assertIsNotNone(options.capabilities.resources)
        self.assertTrue(options.capabilities.resources.listChanged)

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
            "list_cached": {"readOnlyHint": True, "openWorldHint": False},
            "get_cached": {"readOnlyHint": True, "openWorldHint": False},
            "batch_resolve": {"readOnlyHint": True, "openWorldHint": True},
            "batch_check": {"readOnlyHint": True, "openWorldHint": True},
            "provider_status": {"readOnlyHint": True, "openWorldHint": False},
        }

        self.assertEqual(set(server._tool_manager._tools), set(expected))
        for name, tool in server._tool_manager._tools.items():
            self.assertIsNotNone(tool.annotations, name)
            for field_name, value in expected[name].items():
                self.assertEqual(getattr(tool.annotations, field_name), value, f"{name}.{field_name}")

    def test_provider_status_tool_returns_success_when_providers_are_unconfigured(self) -> None:
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
        self.assertTrue(any(entry["provider"] == "elsevier" and entry["status"] == "not_configured" for entry in providers))
        self.assertTrue(any(entry["provider"] == "science" and entry["status"] == "not_configured" for entry in providers))
        self.assertTrue(all(entry["checks"] for entry in providers))

    def test_fetch_paper_payload_uses_default_arguments_and_mcp_download_dir(self) -> None:
        captured: dict[str, object] = {}
        runtime_env = {"CROSSREF_MAILTO": "unit@example.test"}
        default_download_dir = Path("/tmp/paper-fetch-mcp-downloads")

        def fake_fetch_paper(query, **kwargs):
            captured["query"] = query
            captured.update(kwargs)
            return sample_envelope(modes=kwargs["modes"])

        with (
            mock.patch.object(mcp_tools, "build_runtime_env", return_value=runtime_env),
            mock.patch.object(mcp_tools, "resolve_mcp_download_dir", return_value=default_download_dir),
            mock.patch.object(mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper),
            mock.patch.object(mcp_tools, "refresh_cache_index_for_doi"),
        ):
            payload = mcp_tools.fetch_paper_payload(query="10.1000/example")

        self.assertEqual(payload["doi"], "10.1000/example")
        self.assertEqual(captured["query"], "10.1000/example")
        self.assertEqual(captured["modes"], {"article", "markdown"})
        self.assertEqual(captured["download_dir"], default_download_dir)
        self.assertEqual(captured["env"], runtime_env)
        self.assertEqual(captured["render"], RenderOptions(include_refs=None, asset_profile=None, max_tokens="full_text"))
        self.assertEqual(
            captured["strategy"],
            FetchStrategy(
                allow_metadata_only_fallback=True,
                preferred_providers=None,
                asset_profile=None,
            ),
        )

    def test_fetch_paper_payload_explicit_download_dir_overrides_env_default(self) -> None:
        captured: dict[str, object] = {}
        explicit_download_dir = Path("/tmp/isolated-paper-fetch")

        def fake_fetch_paper(query, **kwargs):
            captured.update(kwargs)
            return sample_envelope(modes=kwargs["modes"])

        with (
            mock.patch.object(mcp_tools, "build_runtime_env", return_value={"PAPER_FETCH_DOWNLOAD_DIR": "/tmp/shared"}),
            mock.patch.object(mcp_tools, "resolve_mcp_download_dir") as mocked_resolve,
            mock.patch.object(mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper),
            mock.patch.object(mcp_tools, "refresh_cache_index_for_doi"),
        ):
            mcp_tools.fetch_paper_payload(
                query="10.1000/example",
                download_dir=explicit_download_dir,
            )

        mocked_resolve.assert_not_called()
        self.assertEqual(captured["download_dir"], explicit_download_dir)

    def test_fetch_paper_payload_normalizes_preferred_providers(self) -> None:
        captured: dict[str, object] = {}

        def fake_fetch_paper(query, **kwargs):
            captured.update(kwargs)
            return sample_envelope(modes=kwargs["modes"])

        with (
            mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
            mock.patch.object(mcp_tools, "resolve_mcp_download_dir", return_value=Path("/tmp/downloads")),
            mock.patch.object(mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper),
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
            result = mcp_tools.fetch_paper_tool(query="10.1000/example", modes=["pdf"])

        self.assertTrue(result.isError)
        self.assertIn("unsupported output modes", result.structuredContent["reason"])
        mocked_fetch.assert_not_called()

    def test_fetch_paper_tool_rejects_invalid_include_refs_before_service_call(self) -> None:
        with mock.patch.object(mcp_tools, "service_fetch_paper") as mocked_fetch:
            result = mcp_tools.fetch_paper_tool(query="10.1000/example", include_refs="summary")

        self.assertTrue(result.isError)
        self.assertIn("unsupported include_refs value", result.structuredContent["reason"])
        mocked_fetch.assert_not_called()

    def test_fetch_paper_payload_prefer_cache_short_circuits_network_when_cached_envelope_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            create_cached_fetch_envelope(download_dir, "10.1000/example", modes=["markdown"])

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
        self.assertIn(QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION, payload["quality"]["flags"])
        mocked_fetch.assert_not_called()

    def test_fetch_paper_payload_prefer_cache_falls_back_on_mode_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            create_cached_fetch_envelope(download_dir, "10.1000/example", modes=["markdown"])

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
                    return_value=sample_envelope(modes={"article"}, doi="10.1000/example"),
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

    def test_fetch_paper_payload_prefer_cache_derives_breakdown_from_legacy_sidecar_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            create_cached_fetch_envelope(download_dir, "10.1000/example", modes=["article", "metadata"])
            cache_path = mcp_tools._fetch_envelope_cache_path(download_dir, "10.1000/example")
            cache_payload = json.loads(cache_path.read_text(encoding="utf-8"))
            cache_payload["payload"].pop("token_estimate_breakdown", None)
            cache_payload["payload"]["article"]["quality"].pop("token_estimate_breakdown", None)
            cache_path.write_text(json.dumps(cache_payload, ensure_ascii=False, indent=2), encoding="utf-8")

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

        self.assertEqual(payload["token_estimate_breakdown"], {"abstract": 4, "body": 4, "refs": 0})
        self.assertEqual(
            payload["article"]["quality"]["token_estimate_breakdown"],
            {"abstract": 4, "body": 4, "refs": 0},
        )
        self.assertEqual(payload["quality"]["extraction_revision"], EXTRACTION_REVISION)
        self.assertIn(QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION, payload["quality"]["flags"])
        mocked_fetch.assert_not_called()

    def test_article_payload_preserves_asset_download_diagnostics(self) -> None:
        article = mcp_tools._article_from_payload(
            {
                "doi": "10.1000/assets",
                "source": "science",
                "metadata": {"title": "Asset Diagnostics", "authors": ["Alice Example"]},
                "sections": [{"heading": "Results", "level": 2, "kind": "body", "text": "Body text."}],
                "assets": [
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "caption": "Preview figure.",
                        "path": "downloads/figure-1.png",
                        "section": "body",
                        "render_state": "appendix",
                        "anchor_key": "F1",
                        "download_tier": "preview",
                        "download_url": "https://example.test/figure-preview.png",
                        "original_url": "https://example.test/figure-original.png",
                        "content_type": "image/png",
                        "downloaded_bytes": 128,
                        "width": 640,
                        "height": 480,
                    }
                ],
            }
        )

        self.assertIsNotNone(article)
        assert article is not None
        asset = article.assets[0]
        self.assertEqual(asset.render_state, "appendix")
        self.assertEqual(asset.anchor_key, "F1")
        self.assertEqual(asset.download_tier, "preview")
        self.assertEqual(asset.download_url, "https://example.test/figure-preview.png")
        self.assertEqual(asset.width, 640)
        self.assertEqual(asset.height, 480)

    def test_fetch_paper_payload_prefer_cache_misses_when_revision_differs(self) -> None:
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
                    return_value=sample_envelope(modes={"markdown"}, doi="10.1000/example"),
                ) as mocked_fetch,
            ):
                payload = mcp_tools.fetch_paper_payload(
                    query="10.1000/example",
                    modes=["markdown"],
                    prefer_cache=True,
                    download_dir=download_dir,
                )

        self.assertEqual(payload["doi"], "10.1000/example")
        self.assertNotIn(QUALITY_FLAG_CACHED_WITH_CURRENT_REVISION, payload["quality"]["flags"])
        mocked_fetch.assert_called_once()

    def test_fetch_cache_write_refreshes_index_with_scoped_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            request = mcp_tools.FetchPaperRequest(query="10.1000/example", modes=["markdown"])
            envelope = sample_envelope(modes={"markdown"}, doi="10.1000/example")

            FetchCache(download_dir).write_fetch_envelope(envelope, request)
            entries = mcp_tools.list_cached_payload(download_dir=download_dir)["entries"]

        self.assertEqual([entry["kind"] for entry in entries], ["fetch_envelope"])
        self.assertEqual(entries[0]["doi"], "10.1000/example")

    def test_fetch_paper_payload_accepts_full_text_and_asset_profile_strategy(self) -> None:
        captured: dict[str, object] = {}

        def fake_fetch_paper(query, **kwargs):
            captured.update(kwargs)
            return sample_envelope(modes=kwargs["modes"])

        with (
            mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
            mock.patch.object(mcp_tools, "resolve_mcp_download_dir", return_value=Path("/tmp/downloads")),
            mock.patch.object(mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper),
            mock.patch.object(mcp_tools, "refresh_cache_index_for_doi"),
        ):
            mcp_tools.fetch_paper_payload(
                query="10.1000/example",
                strategy={"asset_profile": "body"},
                max_tokens="full_text",
            )

        self.assertEqual(captured["render"], RenderOptions(include_refs=None, asset_profile="body", max_tokens="full_text"))
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

    def test_fetch_paper_payload_inline_image_budget_does_not_change_service_strategy(self) -> None:
        captured: dict[str, object] = {}

        def fake_fetch_paper(query, **kwargs):
            captured.update(kwargs)
            return sample_envelope(modes=kwargs["modes"])

        with (
            mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
            mock.patch.object(mcp_tools, "resolve_mcp_download_dir", return_value=Path("/tmp/downloads")),
            mock.patch.object(mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper),
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

    def test_fetch_paper_tool_success_preserves_fixed_top_level_fields_and_null_payloads(self) -> None:
        envelope = sample_envelope(modes={"markdown"})

        with (
            mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
            mock.patch.object(mcp_tools, "resolve_mcp_download_dir", return_value=Path("/tmp/downloads")),
            mock.patch.object(mcp_tools, "service_fetch_paper", return_value=envelope),
            mock.patch.object(mcp_tools, "refresh_cache_index_for_doi"),
        ):
            result = mcp_tools.fetch_paper_tool(query="10.1000/example", modes=["markdown"])

        self.assertFalse(result.isError)
        payload = result.structuredContent
        self.assertEqual(payload["source"], "elsevier_xml")
        self.assertTrue(payload["has_fulltext"])
        self.assertEqual(payload["warnings"], ["example warning"])
        self.assertEqual(payload["source_trail"], ["source:ok"])
        self.assertEqual(payload["token_estimate_breakdown"], {"abstract": 32, "body": 96, "refs": 24})
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
            mock.patch.object(mcp_tools, "resolve_mcp_download_dir", return_value=Path("/tmp/downloads")),
            mock.patch.object(mcp_tools, "service_fetch_paper", return_value=envelope),
            mock.patch.object(mcp_tools, "refresh_cache_index_for_doi"),
        ):
            result = mcp_tools.fetch_paper_tool(query="10.1000/example", modes=["metadata"])

        self.assertFalse(result.isError)
        payload = result.structuredContent
        self.assertEqual(payload["article"], None)
        self.assertEqual(payload["markdown"], None)
        self.assertEqual(payload["metadata"]["title"], "Example Article")
        self.assertEqual(payload["token_estimate_breakdown"], {"abstract": 32, "body": 96, "refs": 24})
        self.assertEqual(payload["quality"]["body_metrics"]["figure_count"], 0)

    def test_fetch_paper_tool_returns_ambiguous_error_payload(self) -> None:
        error = PaperFetchFailure(
            "ambiguous",
            "Need user confirmation.",
            candidates=[{"doi": "10.1000/example", "title": "Example Article"}],
        )

        with mock.patch.object(mcp_tools, "service_fetch_paper", side_effect=error):
            result = mcp_tools.fetch_paper_tool(query="ambiguous title")

        self.assertTrue(result.isError)
        self.assertEqual(result.structuredContent["status"], "ambiguous")
        self.assertEqual(result.structuredContent["candidates"][0]["doi"], "10.1000/example")

    def test_fetch_paper_tool_returns_provider_failure_payload_with_specific_status(self) -> None:
        with mock.patch.object(
            mcp_tools,
            "service_fetch_paper",
            side_effect=ProviderFailure("no_access", "Provider request failed."),
        ):
            result = mcp_tools.fetch_paper_tool(query="10.1000/example")

        self.assertTrue(result.isError)
        self.assertEqual(result.structuredContent["status"], "no_access")
        self.assertEqual(result.structuredContent["reason"], "Provider request failed.")
        self.assertIsNone(result.structuredContent["missing_env"])

    def test_error_payload_from_exception_exposes_missing_env_and_promotes_not_configured(self) -> None:
        payload = mcp_tools.error_payload_from_exception(
            ProviderFailure(
                "not_configured",
                "ELSEVIER_API_KEY is not configured.",
                missing_env=["ELSEVIER_API_KEY"],
            )
        )

        self.assertEqual(payload["status"], "no_access")
        self.assertEqual(payload["missing_env"], ["ELSEVIER_API_KEY"])

    def test_fetch_paper_tool_missing_env_payload_matches_output_schema(self) -> None:
        server = build_server()
        tool_schema = server._tool_manager._tools["fetch_paper"].fn_metadata.output_model
        assert tool_schema is not None

        with mock.patch.object(
            mcp_tools,
            "service_fetch_paper",
            side_effect=ProviderFailure(
                "not_configured",
                "ELSEVIER_API_KEY is not configured.",
                missing_env=["ELSEVIER_API_KEY"],
            ),
        ):
            result = mcp_tools.fetch_paper_tool(query="10.1000/example")

        self.assertTrue(result.isError)
        self.assertEqual(result.structuredContent["status"], "no_access")
        self.assertEqual(result.structuredContent["missing_env"], ["ELSEVIER_API_KEY"])
        tool_schema.model_validate(result.structuredContent)

    def test_fetch_paper_payload_updates_cache_index_for_saved_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)

            def fake_fetch_paper(query, **kwargs):
                create_cached_downloads(kwargs["download_dir"], query)
                return sample_envelope(modes=kwargs["modes"], doi=query)

            with (
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper),
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

    def test_get_cached_payload_refreshes_single_doi_and_returns_preferred_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            create_cached_downloads(download_dir, "10.1000/example")

            payload = mcp_tools.get_cached_payload(
                doi="10.1000/example",
                download_dir=download_dir,
            )
            listed = mcp_tools.list_cached_payload(download_dir=download_dir)

        self.assertEqual(payload["status"], "hit")
        self.assertEqual(len(payload["entries"]), 3)
        self.assertIsNotNone(payload["preferred"]["markdown"])
        self.assertIsNotNone(payload["preferred"]["primary_payload"])
        self.assertEqual(len(payload["preferred"]["assets"]), 1)
        self.assertEqual(len(listed["entries"]), 3)

    def test_batch_resolve_payload_reuses_transport_and_aborts_on_rate_limit(self) -> None:
        transport_ids: list[int] = []
        seen_queries: list[str] = []

        def fake_resolve(query, *, transport=None, env=None):
            seen_queries.append(query)
            transport_ids.append(id(transport))
            if query == "second":
                raise ProviderFailure("rate_limited", "Slow down.")
            return sample_resolved_query(query)

        with mock.patch.object(mcp_tools, "service_resolve_paper", side_effect=fake_resolve):
            payload = mcp_tools.batch_resolve_payload(queries=["first", "second", "third"])

        self.assertTrue(payload["aborted"])
        self.assertEqual(payload["abort_reason"]["status"], "rate_limited")
        self.assertEqual(len(payload["results"]), 2)
        self.assertEqual(seen_queries, ["first", "second"])
        self.assertEqual(len(set(transport_ids)), 1)

    def test_batch_resolve_payload_supports_optional_concurrency(self) -> None:
        active = 0
        max_active = 0
        lock = threading.Lock()
        barrier = threading.Barrier(2)

        def fake_resolve(query, *, transport=None, env=None):
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

        with mock.patch.object(mcp_tools, "service_resolve_paper", side_effect=fake_resolve):
            payload = mcp_tools.batch_resolve_payload(
                queries=["first", "second", "third"],
                concurrency=2,
            )

        self.assertFalse(payload["aborted"])
        self.assertEqual([item["query"] for item in payload["results"]], ["first", "second", "third"])
        self.assertGreaterEqual(max_active, 2)

    def test_batch_resolve_tool_rejects_too_many_queries(self) -> None:
        result = mcp_tools.batch_resolve_tool(
            queries=[f"10.1000/{index}" for index in range(51)],
        )

        self.assertTrue(result.isError)
        self.assertEqual(result.structuredContent["status"], "error")
        self.assertIn("queries must contain at most 50 entries.", result.structuredContent["reason"])

    def test_batch_check_payload_uses_lightweight_results_and_no_downloads(self) -> None:
        transport_ids: list[int] = []

        def fake_probe(query, *, transport=None, env=None):
            transport_ids.append(id(transport))
            return sample_probe_result(query, doi=query, title=f"Title for {query}")

        with (
            mock.patch.object(mcp_tools, "service_probe_has_fulltext", side_effect=fake_probe),
            mock.patch.object(mcp_tools, "service_fetch_paper") as mocked_fetch,
        ):
            payload = mcp_tools.batch_check_payload(queries=["10.1000/one", "10.1000/two"], mode="metadata")

        self.assertEqual(payload["mode"], "metadata")
        self.assertFalse(payload["aborted"])
        self.assertEqual(len(payload["results"]), 2)
        self.assertEqual(payload["results"][0]["query"], "10.1000/one")
        self.assertEqual(payload["results"][0]["doi"], "10.1000/one")
        self.assertEqual(payload["results"][0]["title"], "Title for 10.1000/one")
        self.assertEqual(payload["results"][0]["has_fulltext"], True)
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
            payload = mcp_tools.batch_check_payload(queries=["10.1000/one"], mode="article")

        self.assertEqual(payload["results"][0]["token_estimate"], 128)
        self.assertEqual(
            payload["results"][0]["token_estimate_breakdown"],
            {"abstract": 32, "body": 96, "refs": 24},
        )

    def test_batch_check_tool_rejects_invalid_concurrency(self) -> None:
        result = mcp_tools.batch_check_tool(
            queries=["10.1000/one"],
            mode="metadata",
            concurrency=0,
        )

        self.assertTrue(result.isError)
        self.assertEqual(result.structuredContent["status"], "error")
        self.assertIn("greater than or equal to 1", result.structuredContent["reason"])

    def test_batch_check_tool_rejects_too_many_queries(self) -> None:
        result = mcp_tools.batch_check_tool(
            queries=[f"10.1000/{index}" for index in range(51)],
            mode="metadata",
        )

        self.assertTrue(result.isError)
        self.assertEqual(result.structuredContent["status"], "error")
        self.assertIn("queries must contain at most 50 entries.", result.structuredContent["reason"])

    def test_batch_check_payload_aborts_on_rate_limit(self) -> None:
        seen_queries: list[str] = []

        def fake_fetch_paper(query, **kwargs):
            seen_queries.append(query)
            if query == "10.1000/two":
                raise ProviderFailure("rate_limited", "Slow down.")
            return sample_envelope(modes=kwargs["modes"], doi=query)

        with mock.patch.object(mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper):
            payload = mcp_tools.batch_check_payload(
                queries=["10.1000/one", "10.1000/two", "10.1000/three"],
                mode="article",
            )

        self.assertTrue(payload["aborted"])
        self.assertEqual(payload["abort_reason"]["status"], "rate_limited")
        self.assertEqual(seen_queries, ["10.1000/one", "10.1000/two"])
        self.assertEqual(len(payload["results"]), 2)

    def test_resolve_paper_payload_composes_structured_query(self) -> None:
        captured: dict[str, object] = {}

        def fake_resolve(query, *, transport=None, env=None):
            captured["query"] = query
            return sample_resolved_query(query)

        with mock.patch.object(mcp_tools, "service_resolve_paper", side_effect=fake_resolve):
            payload = mcp_tools.resolve_paper_payload(
                title="Example title",
                authors=[" Alice Example ", "Bob Example", "Alice Example", "Carol Example", "Dana Example"],
                year=2024,
            )

        self.assertEqual(captured["query"], "Example title Alice Example Bob Example Carol Example 2024")
        self.assertEqual(payload["query"], "Example title Alice Example Bob Example Carol Example 2024")

    def test_resolve_paper_tool_rejects_mixed_query_and_structured_fields(self) -> None:
        result = mcp_tools.resolve_paper_tool(
            query="10.1000/example",
            title="Example Article",
        )

        self.assertTrue(result.isError)
        self.assertEqual(result.structuredContent["status"], "error")
        self.assertIn("either query or structured title/authors/year", result.structuredContent["reason"])

    def test_has_fulltext_tool_serializes_probe_result(self) -> None:
        server = build_server()
        tool_schema = server._tool_manager._tools["has_fulltext"].fn_metadata.output_model
        assert tool_schema is not None
        with mock.patch.object(
            mcp_tools,
            "service_probe_has_fulltext",
            return_value=sample_probe_result("10.1000/example", title="Example Article"),
        ):
            result = mcp_tools.has_fulltext_tool(query="10.1000/example")

        self.assertFalse(result.isError)
        self.assertEqual(result.structuredContent["doi"], "10.1000/example")
        self.assertEqual(result.structuredContent["state"], "likely_yes")
        self.assertEqual(result.structuredContent["evidence"], ["crossref_fulltext_link"])
        self.assertNotIn("title", result.structuredContent)
        tool_schema.model_validate(result.structuredContent)

    def test_has_fulltext_tool_keeps_ambiguous_error_payload(self) -> None:
        error = PaperFetchFailure(
            "ambiguous",
            "Query resolution is ambiguous; choose one of the DOI candidates.",
            candidates=[{"doi": "10.1000/one"}],
        )
        server = build_server()
        tool_schema = server._tool_manager._tools["has_fulltext"].fn_metadata.output_model
        assert tool_schema is not None
        with mock.patch.object(mcp_tools, "service_probe_has_fulltext", side_effect=error):
            result = mcp_tools.has_fulltext_tool(query="Example title")

        self.assertTrue(result.isError)
        self.assertEqual(result.structuredContent["status"], "ambiguous")
        self.assertEqual(result.structuredContent["candidates"], [{"doi": "10.1000/one"}])
        tool_schema.model_validate(result.structuredContent)

    def test_fetch_paper_tool_error_payload_matches_output_schema(self) -> None:
        server = build_server()
        tool_schema = server._tool_manager._tools["fetch_paper"].fn_metadata.output_model
        assert tool_schema is not None

        result = mcp_tools.fetch_paper_tool(query="10.1000/example", modes=["pdf"])

        self.assertTrue(result.isError)
        self.assertEqual(result.structuredContent["status"], "error")
        tool_schema.model_validate(result.structuredContent)

    def test_fetch_paper_tool_rejects_negative_inline_image_budget_before_service_call(self) -> None:
        with mock.patch.object(mcp_tools, "service_fetch_paper") as mocked_fetch:
            result = mcp_tools.fetch_paper_tool(
                query="10.1000/example",
                strategy={"inline_image_budget": {"max_images": -1}},
            )

        self.assertTrue(result.isError)
        self.assertIn("greater than or equal to 0", result.structuredContent["reason"])
        mocked_fetch.assert_not_called()

    def test_parse_structured_log_message_extracts_fields(self) -> None:
        payload = mcp_tools.parse_structured_log_message(
            "http_request_success method=GET status=200 elapsed_ms=12.5 attempt=1",
            logger_name="paper_fetch.http",
        )

        self.assertEqual(
            payload,
            {
                "event": "http_request_success",
                "logger": "paper_fetch.http",
                "method": "GET",
                "status": 200,
                "elapsed_ms": 12.5,
                "attempt": 1,
            },
        )

    def test_structured_log_payload_from_record_prefers_record_payload(self) -> None:
        record = logging.LogRecord(
            name="paper_fetch.service",
            level=logging.DEBUG,
            pathname=__file__,
            lineno=1,
            msg="official_provider_result provider=wiley note=message with spaces",
            args=(),
            exc_info=None,
        )
        record.structured_data = {
            "event": "official_provider_result",
            "provider": "wiley",
            "note": "message with spaces",
        }

        payload = mcp_tools.structured_log_payload_from_record(record)

        self.assertEqual(
            payload,
            {
                "event": "official_provider_result",
                "provider": "wiley",
                "note": "message with spaces",
                "logger": "paper_fetch.service",
            },
        )

    def test_inline_image_contents_limits_and_filters_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            figure_paths = [root / f"figure-{index}.png" for index in range(1, 5)]
            for path in figure_paths:
                write_binary(path, size=32)
            oversized_path = root / "oversized.png"
            write_binary(oversized_path, size=(2 * 1024 * 1024) + 1)
            text_path = root / "figure.txt"
            text_path.write_text("not an image", encoding="utf-8")

            article = sample_article()
            article.assets = [
                Asset(kind="figure", heading="Figure 1", caption="Body 1", path=str(figure_paths[0]), section="body"),
                Asset(kind="figure", heading="Figure 2", caption="Body 2", path=str(figure_paths[1]), section="body"),
                Asset(kind="figure", heading="Figure 3", caption="Body 3", path=str(figure_paths[2]), section="body"),
                Asset(kind="figure", heading="Figure 4", caption="Body 4", path=str(figure_paths[3]), section="body"),
                Asset(kind="figure", heading="Supplement", caption="Skip", path=str(figure_paths[0]), section="supplementary"),
                Asset(kind="figure", heading="Too big", caption="Skip", path=str(oversized_path), section="body"),
                Asset(kind="figure", heading="Text file", caption="Skip", path=str(text_path), section="body"),
            ]

            contents, warnings = mcp_tools._inline_image_contents(
                article,
                budget=mcp_tools.FetchPaperRequest(query="10.1000/example").strategy.resolved_inline_image_budget(),
            )

        self.assertEqual(len(contents), 6)
        self.assertEqual([content.type for content in contents], ["text", "image", "text", "image", "text", "image"])
        self.assertEqual(len(warnings), 1)
        self.assertIn("omitted from inline MCP image output", warnings[0])

    def test_inline_image_contents_honors_total_byte_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first_image = root / "figure-1.png"
            second_image = root / "figure-2.png"
            write_binary(first_image, size=32)
            write_binary(second_image, size=32)

            article = sample_article()
            article.assets = [
                Asset(kind="figure", heading="Figure 1", caption="Body 1", path=str(first_image), section="body"),
                Asset(kind="figure", heading="Figure 2", caption="Body 2", path=str(second_image), section="body"),
            ]
            budget = mcp_tools.FetchPaperRequest(
                query="10.1000/example",
                strategy={"inline_image_budget": {"max_total_bytes": 40}},
            ).strategy.resolved_inline_image_budget()

            contents, warnings = mcp_tools._inline_image_contents(article, budget=budget)

        self.assertEqual([content.type for content in contents], ["text", "image"])
        self.assertEqual(len(warnings), 1)
        self.assertIn("omitted from inline MCP image output", warnings[0])

    def test_inline_image_contents_disabled_budget_suppresses_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "figure-1.png"
            write_binary(image_path, size=32)

            article = sample_article()
            article.assets = [
                Asset(kind="figure", heading="Figure 1", caption="Body figure", path=str(image_path), section="body")
            ]
            budget = mcp_tools.FetchPaperRequest(
                query="10.1000/example",
                strategy={"inline_image_budget": {"max_images": 0}},
            ).strategy.resolved_inline_image_budget()

            contents, warnings = mcp_tools._inline_image_contents(article, budget=budget)

        self.assertEqual(contents, [])
        self.assertEqual(warnings, [])

    def test_fetch_paper_payload_prefer_cache_reuses_old_sidecar_when_only_inline_budget_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            create_cached_fetch_envelope(download_dir, "10.1000/example", modes=["markdown"])

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
                    strategy={"inline_image_budget": {"max_images": 1}},
                    prefer_cache=True,
                    download_dir=download_dir,
                )

        self.assertEqual(payload["doi"], "10.1000/example")
        self.assertEqual(payload["markdown"], "# Example Article\n\nExample body.\n")
        mocked_fetch.assert_not_called()

    def test_build_fetch_tool_result_keeps_article_hidden_while_attaching_budgeted_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            first_image = Path(tmpdir) / "figure-1.png"
            second_image = Path(tmpdir) / "figure-2.png"
            write_binary(first_image, size=32)
            write_binary(second_image, size=32)

            article = sample_article()
            article.assets = [
                Asset(kind="figure", heading="Figure 1", caption="Body figure", path=str(first_image), section="body"),
                Asset(kind="figure", heading="Figure 2", caption="Body figure", path=str(second_image), section="body"),
            ]
            envelope = FetchEnvelope(
                doi=article.doi,
                source="elsevier_xml",
                has_fulltext=True,
                warnings=[],
                source_trail=["source:ok"],
                token_estimate=article.quality.token_estimate,
                token_estimate_breakdown=article.quality.token_estimate_breakdown,
                article=article,
                markdown="# Example Article\n\nExample body.\n",
                metadata=None,
            )
            request = mcp_tools.FetchPaperRequest(
                query="10.1000/example",
                modes=["markdown"],
                strategy={"asset_profile": "body", "inline_image_budget": {"max_images": 1}},
            )

            result = mcp_tools.build_fetch_tool_result(envelope, request)

        self.assertFalse(result.isError)
        self.assertEqual(result.structuredContent["article"], None)
        self.assertEqual([content.type for content in result.content], ["text", "text", "image"])

    def test_build_fetch_tool_result_uses_provider_default_asset_profile_for_inline_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            figure_path = Path(tmpdir) / "figure-1.png"
            write_binary(figure_path, size=32)

            article = sample_article()
            article.source = "science"
            article.assets = [
                Asset(kind="figure", heading="Figure 1", caption="Body figure", path=str(figure_path), section="body"),
            ]
            envelope = FetchEnvelope(
                doi=article.doi,
                source="science",
                has_fulltext=True,
                warnings=[],
                source_trail=["source:ok"],
                token_estimate=article.quality.token_estimate,
                token_estimate_breakdown=article.quality.token_estimate_breakdown,
                article=article,
                markdown="# Example Article\n\nExample body.\n",
                metadata=None,
            )
            request = mcp_tools.FetchPaperRequest(
                query="10.1000/example",
                modes=["markdown"],
                strategy={"inline_image_budget": {"max_images": 1}},
            )

            result = mcp_tools.build_fetch_tool_result(envelope, request)

        self.assertFalse(result.isError)
        self.assertEqual([content.type for content in result.content], ["text", "text", "image"])

    def test_resolve_paper_tool_serializes_resolved_query(self) -> None:
        resolved = sample_resolved_query("10.1000/example")

        with mock.patch.object(mcp_tools, "service_resolve_paper", return_value=resolved):
            result = mcp_tools.resolve_paper_tool(query="10.1000/example")

        self.assertFalse(result.isError)
        self.assertEqual(result.structuredContent["doi"], "10.1000/example")
        self.assertEqual(result.structuredContent["query_kind"], "doi")


class McpServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_paper_server_notifies_when_default_resources_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "default"
            ctx = FakeContext()

            with (
                mock.patch.object(mcp_server, "build_runtime_env", return_value={}),
                mock.patch.object(mcp_server, "resolve_mcp_download_dir", return_value=default_dir),
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(mcp_tools, "resolve_mcp_download_dir", return_value=default_dir),
                mock.patch.object(mcp_tools, "service_fetch_paper", side_effect=fake_service_fetch_with_cached_downloads),
            ):
                server = build_server()
                result = await server._tool_manager.call_tool(
                    "fetch_paper",
                    {"query": "10.1000/example"},
                    context=ctx,
                )

        self.assertFalse(result.isError)
        self.assertEqual(ctx.session.resource_list_changed_calls, 1)
        resource_uris = set(server._resource_manager._resources)
        self.assertTrue(any(uri.startswith("resource://paper-fetch/cached/") for uri in resource_uris))

    async def test_fetch_paper_server_notifies_when_scoped_resources_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "default"
            isolated_dir = Path(tmpdir) / "isolated"
            ctx = FakeContext()

            with (
                mock.patch.object(mcp_server, "build_runtime_env", return_value={}),
                mock.patch.object(mcp_server, "resolve_mcp_download_dir", return_value=default_dir),
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(mcp_tools, "resolve_mcp_download_dir", return_value=default_dir),
                mock.patch.object(mcp_tools, "service_fetch_paper", side_effect=fake_service_fetch_with_cached_downloads),
            ):
                server = build_server()
                result = await server._tool_manager.call_tool(
                    "fetch_paper",
                    {"query": "10.1000/custom", "download_dir": str(isolated_dir)},
                    context=ctx,
                )

        self.assertFalse(result.isError)
        self.assertEqual(ctx.session.resource_list_changed_calls, 1)
        scope_id = cache_scope_id(isolated_dir)
        resource_uris = set(server._resource_manager._resources)
        self.assertIn(scoped_cache_index_resource_uri(scope_id), resource_uris)
        self.assertTrue(any(uri.startswith(scoped_cached_resource_uri_prefix(scope_id)) for uri in resource_uris))

    async def test_list_cached_and_get_cached_server_notify_on_external_cache_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "default"
            isolated_dir = Path(tmpdir) / "isolated"
            ctx = FakeContext()

            with (
                mock.patch.object(mcp_server, "build_runtime_env", return_value={}),
                mock.patch.object(mcp_server, "resolve_mcp_download_dir", return_value=default_dir),
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(mcp_tools, "resolve_mcp_download_dir", return_value=default_dir),
            ):
                server = build_server()

                create_cached_downloads(default_dir, "10.1000/default")
                mcp_tools.refresh_cache_index_for_doi(default_dir, "10.1000/default")
                listed = await server._tool_manager.call_tool("list_cached", {}, context=ctx)

                create_cached_downloads(isolated_dir, "10.1000/custom")
                mcp_tools.refresh_cache_index_for_doi(isolated_dir, "10.1000/custom")
                cached = await server._tool_manager.call_tool(
                    "get_cached",
                    {"doi": "10.1000/custom", "download_dir": str(isolated_dir)},
                    context=ctx,
                )

        self.assertFalse(listed.isError)
        self.assertFalse(cached.isError)
        self.assertEqual(len(listed.structuredContent["entries"]), 3)
        self.assertEqual(cached.structuredContent["status"], "hit")
        self.assertEqual(ctx.session.resource_list_changed_calls, 2)

    async def test_fetch_paper_server_does_not_notify_when_resource_uris_are_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "default"
            ctx = FakeContext()

            with (
                mock.patch.object(mcp_server, "build_runtime_env", return_value={}),
                mock.patch.object(mcp_server, "resolve_mcp_download_dir", return_value=default_dir),
                mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
                mock.patch.object(mcp_tools, "resolve_mcp_download_dir", return_value=default_dir),
                mock.patch.object(mcp_tools, "service_fetch_paper", side_effect=fake_service_fetch_with_cached_downloads),
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

        self.assertFalse(first.isError)
        self.assertFalse(second.isError)
        self.assertEqual(ctx.session.resource_list_changed_calls, 1)


class McpAsyncToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_structured_log_notification_handler_prefers_structured_data_with_spaces(self) -> None:
        ctx = FakeContext()
        handler = mcp_tools.StructuredLogNotificationHandler(ctx=ctx, loop=asyncio.get_running_loop())
        record = logging.LogRecord(
            name="paper_fetch.service",
            level=logging.DEBUG,
            pathname=__file__,
            lineno=1,
            msg="official_provider_result provider=wiley note=message with spaces",
            args=(),
            exc_info=None,
        )
        record.structured_data = {
            "event": "official_provider_result",
            "provider": "wiley",
            "note": "message with spaces",
        }

        handler.emit(record)
        await asyncio.sleep(0.05)

        self.assertEqual(
            ctx.session.messages[0]["data"],
            {
                "event": "official_provider_result",
                "provider": "wiley",
                "note": "message with spaces",
                "logger": "paper_fetch.service",
            },
        )

    async def test_fetch_paper_tool_async_reports_progress_and_bridges_logs(self) -> None:
        ctx = FakeContext()

        def fake_fetch_paper(query, **kwargs):
            logging.getLogger("paper_fetch.service").debug("fetch_stage query=%s attempt=%s", query, 1)
            return sample_envelope(modes=kwargs["modes"], doi=query)

        with (
            mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
            mock.patch.object(mcp_tools, "resolve_mcp_download_dir", return_value=Path("/tmp/downloads")),
            mock.patch.object(mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper),
            mock.patch.object(mcp_tools, "refresh_cache_index_for_doi"),
        ):
            result = await mcp_tools.fetch_paper_tool_async(
                query="10.1000/example",
                ctx=ctx,
            )
            await asyncio.sleep(0.05)

        self.assertFalse(result.isError)
        self.assertEqual(
            ctx.progress,
            [
                (0, 4, "Validating fetch_paper request"),
                (1, 4, "Fetching paper content"),
                (3, 4, "Shaping MCP result"),
                (4, 4, "fetch_paper complete"),
            ],
        )
        self.assertEqual(ctx.session.messages[0]["data"]["event"], "fetch_stage")
        self.assertEqual(ctx.session.messages[0]["data"]["query"], "10.1000/example")

    async def test_fetch_paper_tool_async_sets_cancellation_flag_for_worker_transport(self) -> None:
        started = threading.Event()
        cancelled_seen = threading.Event()

        def fake_fetch_envelope(request, *, env, download_dir, transport, include_article_for_assets):
            started.set()
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                if transport is not None and transport.cancelled:
                    cancelled_seen.set()
                    raise mcp_tools.RequestCancelledError("Request cancelled.")
                time.sleep(0.01)
            return sample_envelope(modes={"article", "markdown"})

        with mock.patch.object(mcp_tools, "_fetch_paper_envelope", side_effect=fake_fetch_envelope):
            task = asyncio.create_task(mcp_tools.fetch_paper_tool_async(query="10.1000/example"))
            await wait_for_threading_event(started, 1.0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            await wait_for_threading_event(cancelled_seen, 1.0)

        self.assertTrue(cancelled_seen.is_set())

    async def test_batch_check_tool_async_reports_per_query_progress(self) -> None:
        ctx = FakeContext()

        def fake_probe(query, *, transport=None, env=None):
            logging.getLogger("paper_fetch.http").debug("batch_check_item query=%s status=%s", query, "ok")
            return sample_probe_result(query, doi=query, title=f"Title for {query}")

        with mock.patch.object(mcp_tools, "service_probe_has_fulltext", side_effect=fake_probe):
            result = await mcp_tools.batch_check_tool_async(
                queries=["10.1000/one", "10.1000/two"],
                mode="metadata",
                ctx=ctx,
            )
            await asyncio.sleep(0.05)

        self.assertFalse(result.isError)
        self.assertEqual(
            ctx.progress,
            [
                (0, 2, "Starting batch_check"),
                (1, 2, "Checked 1 of 2 queries"),
                (2, 2, "Checked 2 of 2 queries"),
                (2, 2, "batch_check complete"),
            ],
        )
        self.assertTrue(any(message["data"]["event"] == "batch_check_item" for message in ctx.session.messages))

    async def test_batch_check_tool_async_rejects_too_many_queries(self) -> None:
        result = await mcp_tools.batch_check_tool_async(
            queries=[f"10.1000/{index}" for index in range(51)],
            mode="metadata",
        )

        self.assertTrue(result.isError)
        self.assertEqual(result.structuredContent["status"], "error")
        self.assertIn("queries must contain at most 50 entries.", result.structuredContent["reason"])

    async def test_batch_resolve_tool_async_reports_per_query_progress(self) -> None:
        ctx = FakeContext()

        def fake_resolve(query, *, transport=None, env=None):
            logging.getLogger("paper_fetch.service").debug("batch_resolve_item query=%s status=%s", query, "ok")
            return sample_resolved_query(query)

        with mock.patch.object(mcp_tools, "service_resolve_paper", side_effect=fake_resolve):
            result = await mcp_tools.batch_resolve_tool_async(
                queries=["10.1000/one", "10.1000/two"],
                ctx=ctx,
            )
            await asyncio.sleep(0.05)

        self.assertFalse(result.isError)
        self.assertEqual(
            ctx.progress,
            [
                (0, 2, "Starting batch_resolve"),
                (1, 2, "Resolved 1 of 2 queries"),
                (2, 2, "Resolved 2 of 2 queries"),
                (2, 2, "batch_resolve complete"),
            ],
        )
        self.assertTrue(any(message["data"]["event"] == "batch_resolve_item" for message in ctx.session.messages))

    async def test_batch_resolve_tool_async_rejects_too_many_queries(self) -> None:
        result = await mcp_tools.batch_resolve_tool_async(
            queries=[f"10.1000/{index}" for index in range(51)],
        )

        self.assertTrue(result.isError)
        self.assertEqual(result.structuredContent["status"], "error")
        self.assertIn("queries must contain at most 50 entries.", result.structuredContent["reason"])


if __name__ == "__main__":
    unittest.main()
