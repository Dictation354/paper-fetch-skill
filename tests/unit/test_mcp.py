from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from paper_fetch.mcp import tools as mcp_tools
from paper_fetch.models import ArticleModel, FetchEnvelope, Metadata, Quality, RenderOptions, Section
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.resolve.query import ResolvedQuery
from paper_fetch.service import FetchStrategy, PaperFetchFailure


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
        quality=Quality(has_fulltext=True, token_estimate=128, warnings=["example warning"], source_trail=["source:ok"]),
    )


def sample_envelope(*, modes: set[str]) -> FetchEnvelope:
    article = sample_article()
    return FetchEnvelope(
        doi=article.doi,
        source="elsevier_xml",
        has_fulltext=True,
        warnings=["example warning"],
        source_trail=["source:ok"],
        token_estimate=article.quality.token_estimate,
        article=article if "article" in modes else None,
        markdown="# Example Article\n\nExample body.\n" if "markdown" in modes else None,
        metadata=article.metadata if "metadata" in modes else None,
    )


class McpToolTests(unittest.TestCase):
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
        ):
            payload = mcp_tools.fetch_paper_payload(query="10.1000/example")

        self.assertEqual(payload["doi"], "10.1000/example")
        self.assertEqual(captured["query"], "10.1000/example")
        self.assertEqual(captured["modes"], {"article", "markdown"})
        self.assertEqual(captured["download_dir"], default_download_dir)
        self.assertEqual(captured["env"], runtime_env)
        self.assertEqual(captured["render"], RenderOptions(include_refs=None, asset_profile="none", max_tokens="full_text"))
        self.assertEqual(
            captured["strategy"],
            FetchStrategy(
                allow_html_fallback=True,
                allow_metadata_only_fallback=True,
                preferred_providers=None,
                asset_profile="none",
            ),
        )

    def test_fetch_paper_payload_normalizes_preferred_providers(self) -> None:
        captured: dict[str, object] = {}

        def fake_fetch_paper(query, **kwargs):
            captured.update(kwargs)
            return sample_envelope(modes=kwargs["modes"])

        with (
            mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
            mock.patch.object(mcp_tools, "resolve_mcp_download_dir", return_value=Path("/tmp/downloads")),
            mock.patch.object(mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper),
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

    def test_fetch_paper_payload_accepts_full_text_and_asset_profile_strategy(self) -> None:
        captured: dict[str, object] = {}

        def fake_fetch_paper(query, **kwargs):
            captured.update(kwargs)
            return sample_envelope(modes=kwargs["modes"])

        with (
            mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
            mock.patch.object(mcp_tools, "resolve_mcp_download_dir", return_value=Path("/tmp/downloads")),
            mock.patch.object(mcp_tools, "service_fetch_paper", side_effect=fake_fetch_paper),
        ):
            mcp_tools.fetch_paper_payload(
                query="10.1000/example",
                strategy={"asset_profile": "body"},
                max_tokens="full_text",
            )

        self.assertEqual(captured["render"], RenderOptions(include_refs=None, asset_profile="body", max_tokens="full_text"))
        self.assertEqual(captured["strategy"], FetchStrategy(asset_profile="body"))

    def test_fetch_paper_tool_success_preserves_fixed_top_level_fields_and_null_payloads(self) -> None:
        envelope = sample_envelope(modes={"markdown"})

        with (
            mock.patch.object(mcp_tools, "build_runtime_env", return_value={}),
            mock.patch.object(mcp_tools, "resolve_mcp_download_dir", return_value=Path("/tmp/downloads")),
            mock.patch.object(mcp_tools, "service_fetch_paper", return_value=envelope),
        ):
            result = mcp_tools.fetch_paper_tool(query="10.1000/example", modes=["markdown"])

        self.assertFalse(result.isError)
        payload = result.structuredContent
        self.assertEqual(payload["source"], "elsevier_xml")
        self.assertTrue(payload["has_fulltext"])
        self.assertEqual(payload["warnings"], ["example warning"])
        self.assertEqual(payload["source_trail"], ["source:ok"])
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
        ):
            result = mcp_tools.fetch_paper_tool(query="10.1000/example", modes=["metadata"])

        self.assertFalse(result.isError)
        payload = result.structuredContent
        self.assertEqual(payload["article"], None)
        self.assertEqual(payload["markdown"], None)
        self.assertEqual(payload["metadata"]["title"], "Example Article")

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

    def test_fetch_paper_tool_returns_provider_failure_payload(self) -> None:
        with mock.patch.object(
            mcp_tools,
            "service_fetch_paper",
            side_effect=ProviderFailure("error", "Provider request failed."),
        ):
            result = mcp_tools.fetch_paper_tool(query="10.1000/example")

        self.assertTrue(result.isError)
        self.assertEqual(result.structuredContent["status"], "error")
        self.assertEqual(result.structuredContent["reason"], "Provider request failed.")

    def test_resolve_paper_tool_serializes_resolved_query(self) -> None:
        resolved = ResolvedQuery(
            query="10.1000/example",
            query_kind="doi",
            doi="10.1000/example",
            landing_url="https://example.test/article",
            provider_hint="crossref",
            confidence=1.0,
            candidates=[],
            title="Example Article",
        )

        with mock.patch.object(mcp_tools, "service_resolve_paper", return_value=resolved):
            result = mcp_tools.resolve_paper_tool(query="10.1000/example")

        self.assertFalse(result.isError)
        self.assertEqual(result.structuredContent["doi"], "10.1000/example")
        self.assertEqual(result.structuredContent["query_kind"], "doi")


if __name__ == "__main__":
    unittest.main()
