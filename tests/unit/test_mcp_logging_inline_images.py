# ruff: noqa: F403,F405
from __future__ import annotations

from ._mcp_support import *


class McpLoggingInlineImageTests(unittest.TestCase):
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

            contents, warnings = mcp_tools._inline_image_contents(
                article,
                budget=mcp_tools.FetchPaperRequest(
                    query="10.1000/example"
                ).strategy.resolved_inline_image_budget(),
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
            budget = mcp_tools.FetchPaperRequest(
                query="10.1000/example",
                strategy={"inline_image_budget": {"max_total_bytes": 40}},
            ).strategy.resolved_inline_image_budget()

            contents, warnings = mcp_tools._inline_image_contents(
                article, budget=budget
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
            budget = mcp_tools.FetchPaperRequest(
                query="10.1000/example",
                strategy={"inline_image_budget": {"max_images": 0}},
            ).strategy.resolved_inline_image_budget()

            contents, warnings = mcp_tools._inline_image_contents(
                article, budget=budget
            )

        self.assertEqual(contents, [])
        self.assertEqual(warnings, [])

    def test_fetch_paper_payload_prefer_cache_reuses_old_sidecar_when_only_inline_budget_changes(
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
                    strategy={"inline_image_budget": {"max_images": 1}},
                    prefer_cache=True,
                    download_dir=download_dir,
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
            request = mcp_tools.FetchPaperRequest(
                query="10.1000/example",
                modes=["markdown"],
                strategy={
                    "asset_profile": "body",
                    "inline_image_budget": {"max_images": 1},
                },
            )

            result = mcp_tools.build_fetch_tool_result(envelope, request)

        self.assertFalse(result.isError)
        self.assertEqual(result.structuredContent["article"], None)
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
            request = mcp_tools.FetchPaperRequest(
                query="10.1000/example",
                modes=["markdown"],
                save_markdown=True,
                strategy={
                    "asset_profile": "body",
                    "inline_image_budget": {"max_images": 1},
                },
            )

            result = mcp_tools.build_fetch_tool_result(envelope, request)

        self.assertFalse(result.isError)
        self.assertIsNone(result.structuredContent["markdown"])
        self.assertIsNone(result.structuredContent["article"])
        self.assertEqual(
            result.structuredContent["metadata"]["title"], "Example Article"
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
            request = mcp_tools.FetchPaperRequest(
                query="10.1000/example",
                modes=["markdown"],
                strategy={
                    "asset_profile": "none",
                    "inline_image_budget": {"max_images": 1},
                },
            )

            result = mcp_tools.build_fetch_tool_result(envelope, request)

        self.assertFalse(result.isError)
        self.assertIn(
            "![Figure 1](https://example.test/figure-1.png)",
            result.structuredContent["markdown"],
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
            request = mcp_tools.FetchPaperRequest(
                query="10.1000/example",
                modes=["markdown"],
                strategy={"inline_image_budget": {"max_images": 1}},
            )

            result = mcp_tools.build_fetch_tool_result(envelope, request)

        self.assertFalse(result.isError)
        self.assertEqual(
            [content.type for content in result.content], ["text", "text", "image"]
        )

    def test_resolve_paper_tool_serializes_resolved_query(self) -> None:
        resolved = sample_resolved_query("10.1000/example")

        with mock.patch.object(
            mcp_tools, "service_resolve_paper", return_value=resolved
        ):
            result = mcp_tools.resolve_paper_tool(query="10.1000/example")

        self.assertFalse(result.isError)
        self.assertEqual(result.structuredContent["doi"], "10.1000/example")
        self.assertEqual(result.structuredContent["query_kind"], "doi")
