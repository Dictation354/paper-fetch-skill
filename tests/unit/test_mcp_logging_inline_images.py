from __future__ import annotations

import asyncio
import logging
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch.mcp.fetch_cache import FetchCache
from paper_fetch.mcp.fetch_tool import (
    _inline_image_contents,
    build_fetch_tool_result,
    fetch_paper_payload,
    fetch_paper_tool_async,
    resolve_paper_tool,
)
from paper_fetch.mcp.log_bridge import (
    parse_structured_log_message,
    structured_log_payload_from_record,
)
from paper_fetch.mcp.schemas import FetchPaperRequest
from paper_fetch.models import Asset, FetchEnvelope
from paper_fetch.runtime import RuntimeContext

from ._mcp_support import (
    create_cached_fetch_envelope,
    mcp_test_deps,
    sample_article,
    sample_envelope,
    sample_resolved_query,
    write_binary,
)


class McpLoggingInlineImageTests(unittest.TestCase):
    def test_async_inline_images_match_on_fresh_fetch_and_cache_hit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            figure_path = download_dir / "figure-1.png"
            write_binary(figure_path, size=32)
            fetch = mock.Mock()

            def fetch_paper(query, **kwargs):
                envelope = sample_envelope(modes=set(kwargs["modes"]), doi=query)
                assert envelope.article is not None
                envelope.article.assets = [
                    Asset(
                        kind="figure",
                        heading="Figure 1",
                        caption="Body figure",
                        path=str(figure_path),
                        section="body",
                        downloaded_bytes=32,
                    )
                ]
                fetch(query, **kwargs)
                return envelope

            arguments = {
                "query": "10.1000/inline-cache",
                "modes": ["markdown"],
                "strategy": {
                    "asset_profile": "body",
                    "inline_image_budget": {"max_images": 1},
                },
                "prefer_cache": True,
                "download_dir": download_dir,
                "deps": mcp_test_deps(
                    build_runtime_env=lambda _env=None: {},
                    service_fetch_paper=fetch_paper,
                ),
            }

            fresh = asyncio.run(fetch_paper_tool_async(**arguments))
            cached = asyncio.run(
                fetch_paper_tool_async(
                    **{
                        **arguments,
                        "strategy": {
                            "asset_profile": "body",
                            "inline_image_budget": {"max_images": 3},
                        },
                    }
                )
            )

        self.assertEqual(
            [content.type for content in fresh.content], ["text", "text", "image"]
        )
        self.assertEqual(
            [content.type for content in cached.content], ["text", "text", "image"]
        )
        self.assertIsNone(fresh.structured_content["article"])
        self.assertIsNone(cached.structured_content["article"])
        self.assertEqual(fetch.call_count, 1)

    def test_inline_image_request_misses_old_sidecar_without_article(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            old_request = FetchPaperRequest(
                query="10.1000/inline-old",
                modes=["markdown"],
                prefer_cache=True,
                strategy={
                    "asset_profile": "body",
                    "inline_image_budget": {"max_images": 0},
                },
            )
            old_envelope = sample_envelope(modes={"markdown"}, doi=old_request.query)
            cache = FetchCache(download_dir)
            cache.write_fetch_envelope(old_envelope, old_request)
            active_request = FetchPaperRequest(
                query=old_request.query,
                modes=["markdown"],
                prefer_cache=True,
                strategy={
                    "asset_profile": "body",
                    "inline_image_budget": {"max_images": 2},
                },
            )

            inspection = cache.get_payload(
                old_request.query,
                request=active_request,
                detail="compact",
            )
            with RuntimeContext(env={}, download_dir=download_dir) as context:
                loaded = cache.load_fetch_envelope(
                    active_request,
                    resolve_paper_fn=mock.Mock(),
                    context=context,
                )

        self.assertFalse(inspection["request_satisfied"])
        self.assertFalse(inspection["sidecar"]["payload_satisfies_request"])
        self.assertIsNone(loaded)

    def test_disabled_inline_budget_accepts_sidecar_without_article(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            request = FetchPaperRequest(
                query="10.1000/inline-disabled",
                modes=["markdown"],
                prefer_cache=True,
                strategy={
                    "asset_profile": "body",
                    "inline_image_budget": {"max_images": 0},
                },
            )
            cache = FetchCache(download_dir)
            cache.write_fetch_envelope(
                sample_envelope(modes={"markdown"}, doi=request.query), request
            )

            inspection = cache.get_payload(
                request.query,
                request=request,
                detail="compact",
            )

        self.assertTrue(inspection["request_satisfied"])

    def test_parse_structured_log_message_extracts_fields(self) -> None:
        payload = parse_structured_log_message(
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
            "landing_url": "https://publisher.example/article?token=secret",
            "request_headers": {"Authorization": "Bearer secret"},
        }

        payload = structured_log_payload_from_record(record)

        self.assertEqual(
            payload,
            {
                "event": "official_provider_result",
                "provider": "wiley",
                "note": "message with spaces",
                "landing_url": "https://publisher.example/article",
                "request_headers": {"Authorization": "***"},
                "logger": "paper_fetch.service",
            },
        )

    def test_log_bridge_defensively_redacts_unstructured_provider_secret(self) -> None:
        record = logging.LogRecord(
            name="paper_fetch.service",
            level=logging.WARNING,
            pathname=__file__,
            lineno=1,
            msg=(
                "provider failure headers={'Wiley-TDM-Client-Token': "
                "'private-token'} url=https://cdn.example/file?token=private"
            ),
            args=(),
            exc_info=None,
        )

        payload = structured_log_payload_from_record(record)

        self.assertNotIn("private-token", str(payload))
        self.assertNotIn("token=private", str(payload))

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
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Body 1",
                    path=str(figure_paths[0]),
                    section="body",
                ),
                Asset(
                    kind="figure",
                    heading="Figure 2",
                    caption="Body 2",
                    path=str(figure_paths[1]),
                    section="body",
                ),
                Asset(
                    kind="figure",
                    heading="Figure 3",
                    caption="Body 3",
                    path=str(figure_paths[2]),
                    section="body",
                ),
                Asset(
                    kind="figure",
                    heading="Figure 4",
                    caption="Body 4",
                    path=str(figure_paths[3]),
                    section="body",
                ),
                Asset(
                    kind="figure",
                    heading="Supplement",
                    caption="Skip",
                    path=str(figure_paths[0]),
                    section="supplementary",
                ),
                Asset(
                    kind="figure",
                    heading="Too big",
                    caption="Skip",
                    path=str(oversized_path),
                    section="body",
                ),
                Asset(
                    kind="figure",
                    heading="Text file",
                    caption="Skip",
                    path=str(text_path),
                    section="body",
                ),
            ]

            contents, warnings = _inline_image_contents(
                article,
                budget=FetchPaperRequest(
                    query="10.1000/example"
                ).strategy.resolved_inline_image_budget(),
                download_dir=root,
            )

        self.assertEqual(len(contents), 6)
        self.assertEqual(
            [content.type for content in contents],
            ["text", "image", "text", "image", "text", "image"],
        )
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
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Body 1",
                    path=str(first_image),
                    section="body",
                ),
                Asset(
                    kind="figure",
                    heading="Figure 2",
                    caption="Body 2",
                    path=str(second_image),
                    section="body",
                ),
            ]
            budget = FetchPaperRequest(
                query="10.1000/example",
                strategy={"inline_image_budget": {"max_total_bytes": 40}},
            ).strategy.resolved_inline_image_budget()

            contents, warnings = _inline_image_contents(
                article, budget=budget, download_dir=root
            )

        self.assertEqual([content.type for content in contents], ["text", "image"])
        self.assertEqual(len(warnings), 1)
        self.assertIn("omitted from inline MCP image output", warnings[0])

    def test_inline_image_contents_disabled_budget_suppresses_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "figure-1.png"
            write_binary(image_path, size=32)

            article = sample_article()
            article.assets = [
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Body figure",
                    path=str(image_path),
                    section="body",
                )
            ]
            budget = FetchPaperRequest(
                query="10.1000/example",
                strategy={"inline_image_budget": {"max_images": 0}},
            ).strategy.resolved_inline_image_budget()

            contents, warnings = _inline_image_contents(
                article, budget=budget, download_dir=Path(tmpdir)
            )

        self.assertEqual(contents, [])
        self.assertEqual(warnings, [])

    def test_inline_images_reject_out_of_scope_symlink_and_size_mismatch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            scope = base / "scope"
            scope.mkdir()
            outside = base / "outside.png"
            write_binary(outside, size=32)
            symlink = scope / "linked.png"
            symlink.symlink_to(outside)
            in_scope = scope / "figure.png"
            write_binary(in_scope, size=32)
            budget = FetchPaperRequest(
                query="10.1000/example"
            ).strategy.resolved_inline_image_budget()

            for path, recorded_size in (
                (outside, 32),
                (symlink, 32),
                (in_scope, 31),
            ):
                article = sample_article()
                article.assets = [
                    Asset(
                        kind="figure",
                        heading="Unsafe",
                        path=str(path),
                        section="body",
                        downloaded_bytes=recorded_size,
                    )
                ]
                contents, warnings = _inline_image_contents(
                    article, budget=budget, download_dir=scope
                )
                self.assertEqual(contents, [])
                self.assertIn("omitted from inline MCP image output", warnings[0])

    def test_cached_envelope_with_out_of_scope_asset_is_not_reused(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            scope = base / "scope"
            scope.mkdir()
            outside = base / "outside.png"
            write_binary(outside, size=32)
            article = sample_article()
            article.assets = [
                Asset(
                    kind="figure",
                    heading="Outside",
                    path=str(outside),
                    section="body",
                    downloaded_bytes=32,
                )
            ]
            envelope = FetchEnvelope(
                doi=article.doi,
                source=article.source,
                has_fulltext=True,
                article=article,
                markdown="# Example",
            )
            request = FetchPaperRequest(
                query="10.1000/example",
                modes=["article"],
                prefer_cache=True,
            )
            cache = FetchCache(scope)
            cache.write_fetch_envelope(envelope, request)

            restored = cache.load_fetch_envelope(
                request,
                resolve_paper_fn=lambda *_args, **_kwargs: sample_resolved_query(
                    "10.1000/example"
                ),
                context=RuntimeContext(env={}, download_dir=scope),
            )

        self.assertIsNone(restored)

    def test_fetch_paper_payload_prefer_cache_reuses_old_sidecar_when_only_inline_budget_changes(
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
                strategy={"inline_image_budget": {"max_images": 1}},
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
        mocked_fetch.assert_not_called()

    def test_build_fetch_tool_result_keeps_article_hidden_while_attaching_budgeted_images(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            first_image = Path(tmpdir) / "figure-1.png"
            second_image = Path(tmpdir) / "figure-2.png"
            write_binary(first_image, size=32)
            write_binary(second_image, size=32)

            article = sample_article()
            article.assets = [
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Body figure",
                    path=str(first_image),
                    section="body",
                ),
                Asset(
                    kind="figure",
                    heading="Figure 2",
                    caption="Body figure",
                    path=str(second_image),
                    section="body",
                ),
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
            request = FetchPaperRequest(
                query="10.1000/example",
                modes=["markdown"],
                strategy={
                    "asset_profile": "body",
                    "inline_image_budget": {"max_images": 1},
                },
            )

            result = build_fetch_tool_result(
                envelope, request, download_dir=Path(tmpdir)
            )

        self.assertFalse(result.is_error)
        self.assertEqual(result.structured_content["article"], None)
        self.assertEqual(
            [content.type for content in result.content], ["text", "text", "image"]
        )

    def test_build_fetch_tool_result_save_markdown_suppresses_inline_images(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            figure_path = Path(tmpdir) / "figure-1.png"
            write_binary(figure_path, size=32)

            article = sample_article()
            article.assets = [
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Body figure",
                    path=str(figure_path),
                    section="body",
                )
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
            request = FetchPaperRequest(
                query="10.1000/example",
                modes=["markdown"],
                save_markdown=True,
                strategy={
                    "asset_profile": "body",
                    "inline_image_budget": {"max_images": 1},
                },
            )

            result = build_fetch_tool_result(
                envelope, request, download_dir=Path(tmpdir)
            )

        self.assertFalse(result.is_error)
        self.assertIsNone(result.structured_content["markdown"])
        self.assertIsNone(result.structured_content["article"])
        self.assertEqual(
            result.structured_content["metadata"]["title"], "Example Article"
        )
        self.assertEqual([content.type for content in result.content], ["text"])

    def test_build_fetch_tool_result_asset_profile_none_keeps_remote_markdown_without_inline_images(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            figure_path = Path(tmpdir) / "figure-1.png"
            write_binary(figure_path, size=32)

            article = sample_article()
            article.assets = [
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Body figure",
                    path=str(figure_path),
                    section="body",
                )
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
                markdown="# Example Article\n\n![Figure 1](https://example.test/figure-1.png)\n\nBody text.\n",
                metadata=None,
            )
            request = FetchPaperRequest(
                query="10.1000/example",
                modes=["markdown"],
                strategy={
                    "asset_profile": "none",
                    "inline_image_budget": {"max_images": 1},
                },
            )

            result = build_fetch_tool_result(
                envelope, request, download_dir=Path(tmpdir)
            )

        self.assertFalse(result.is_error)
        self.assertIn(
            "![Figure 1](https://example.test/figure-1.png)",
            result.structured_content["markdown"],
        )
        self.assertEqual([content.type for content in result.content], ["text"])

    def test_build_fetch_tool_result_uses_provider_default_asset_profile_for_inline_images(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            figure_path = Path(tmpdir) / "figure-1.png"
            write_binary(figure_path, size=32)

            article = sample_article()
            article.source = "science"
            article.assets = [
                Asset(
                    kind="figure",
                    heading="Figure 1",
                    caption="Body figure",
                    path=str(figure_path),
                    section="body",
                ),
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
            request = FetchPaperRequest(
                query="10.1000/example",
                modes=["markdown"],
                strategy={"inline_image_budget": {"max_images": 1}},
            )

            result = build_fetch_tool_result(
                envelope, request, download_dir=Path(tmpdir)
            )

        self.assertFalse(result.is_error)
        self.assertEqual(
            [content.type for content in result.content], ["text", "text", "image"]
        )

    def test_resolve_paper_tool_serializes_resolved_query(self) -> None:
        resolved = sample_resolved_query("10.1000/example")

        result = resolve_paper_tool(
            query="10.1000/example",
            deps=mcp_test_deps(
                service_resolve_paper=lambda *_args, **_kwargs: resolved
            ),
        )

        self.assertFalse(result.is_error)
        self.assertEqual(result.structured_content["doi"], "10.1000/example")
        self.assertEqual(result.structured_content["query_kind"], "doi")
