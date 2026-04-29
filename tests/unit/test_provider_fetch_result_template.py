from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Mapping

from paper_fetch.artifacts import ArtifactStore
from paper_fetch.models import article_from_markdown
from paper_fetch.providers._waterfall import ProviderWaterfallStep, run_provider_waterfall
from paper_fetch.providers.base import (
    ProviderFailure,
    ProviderClient,
    ProviderContent,
    RawFulltextPayload,
)
from paper_fetch.runtime import RuntimeContext
from paper_fetch.tracing import trace_from_markers


def _payload(*, source_url: str = "https://example.test/article", markers: list[str] | None = None) -> RawFulltextPayload:
    body = b"<html><body>Article</body></html>"
    return RawFulltextPayload(
        provider="template",
        source_url=source_url,
        content_type="text/html",
        body=body,
        content=ProviderContent(
            route_kind="html",
            source_url=source_url,
            content_type="text/html",
            body=body,
            markdown_text="# Template Article\n\n## Results\n\n" + ("Body text " * 80),
        ),
        trace=trace_from_markers(list(markers or ["fulltext:template_html_ok"])),
    )


class ProviderWaterfallRunnerTests(unittest.TestCase):
    def test_runner_accumulates_warnings_and_stops_after_success(self) -> None:
        calls: list[str] = []

        def first(_state):
            calls.append("first")
            raise ProviderFailure("no_result", "HTML was abstract only.", warnings=["first warning"])

        def second(_state):
            calls.append("second")
            return _payload(markers=[])

        def third(_state):
            calls.append("third")
            return _payload()

        payload = run_provider_waterfall(
            [
                ProviderWaterfallStep(
                    label="html",
                    run=first,
                    failure_marker="fulltext:template_html_fail",
                    failure_warning="trying pdf",
                ),
                ProviderWaterfallStep(
                    label="pdf",
                    run=second,
                    success_markers=("fulltext:template_pdf_ok",),
                    success_warning="pdf success",
                ),
                ProviderWaterfallStep(label="unused", run=third),
            ]
        )

        self.assertEqual(calls, ["first", "second"])
        self.assertEqual(payload.warnings, ["first warning", "trying pdf", "pdf success"])
        self.assertEqual(
            [event.marker() for event in payload.trace if event.marker()],
            ["fulltext:template_html_fail", "fulltext:template_pdf_ok"],
        )

    def test_runner_combines_failures_when_all_steps_fail(self) -> None:
        with self.assertRaises(ProviderFailure) as raised:
            run_provider_waterfall(
                [
                    ProviderWaterfallStep(
                        label="html",
                        run=lambda _state: (_ for _ in ()).throw(ProviderFailure("no_result", "HTML failed.")),
                        failure_marker="fulltext:template_html_fail",
                    ),
                    ProviderWaterfallStep(
                        label="pdf",
                        run=lambda _state: (_ for _ in ()).throw(ProviderFailure("no_result", "PDF failed.")),
                        failure_marker="fulltext:template_pdf_fail",
                    ),
                ]
            )

        self.assertEqual(raised.exception.code, "no_result")
        self.assertIn("html: HTML failed.", raised.exception.message)
        self.assertIn("pdf: PDF failed.", raised.exception.message)
        self.assertEqual(
            raised.exception.source_trail,
            ["fulltext:template_html_fail", "fulltext:template_pdf_fail"],
        )


class RawFulltextPayloadMetadataCompatibilityTests(unittest.TestCase):
    def test_metadata_magic_keys_are_not_ingested_as_structured_payload_fields(self) -> None:
        payload = RawFulltextPayload(
            provider="template",
            source_url="https://example.test/article",
            content_type="text/html",
            body=b"<html></html>",
            metadata={
                "route": "html",
                "reason": "legacy reason",
                "markdown_text": "# Legacy\n\nBody text",
                "merged_metadata": {"title": "Merged Legacy Title"},
                "availability_diagnostics": {"accepted": True, "reason": "body_sufficient"},
                "html_fetcher": "flaresolverr",
                "browser_context_seed": {"browser_final_url": "https://example.test/final"},
                "suggested_filename": "legacy.html",
                "html_failure_reason": "abstract_only",
                "html_failure_message": "HTML exposed only abstract content.",
                "extracted_assets": [{"kind": "figure", "url": "https://example.test/f1.png"}],
                "warnings": ["legacy warning"],
                "source_trail": ["fulltext:template_html_ok"],
                "custom_passthrough": "kept",
            },
        )

        self.assertIsNone(payload.content)
        self.assertEqual(payload.warnings, [])
        self.assertEqual(payload.trace, [])
        self.assertIsNone(payload.merged_metadata)
        for key in (
            "route",
            "reason",
            "markdown_text",
            "merged_metadata",
            "availability_diagnostics",
            "html_fetcher",
            "browser_context_seed",
            "suggested_filename",
            "html_failure_reason",
            "html_failure_message",
            "extracted_assets",
            "warnings",
            "source_trail",
        ):
            self.assertNotIn(key, payload.metadata)
        self.assertEqual(payload.metadata["custom_passthrough"], "kept")

    def test_metadata_export_is_derived_from_typed_payload_fields(self) -> None:
        body = b"<html></html>"
        payload = RawFulltextPayload(
            provider="template",
            source_url="https://example.test/article",
            content_type="text/html",
            body=body,
            content=ProviderContent(
                route_kind="html",
                source_url="https://example.test/article",
                content_type="text/html",
                body=body,
                markdown_text="# Typed\n\nBody text",
                merged_metadata={"title": "Merged Typed Title"},
                diagnostics={"availability_diagnostics": {"accepted": True, "reason": "body_sufficient"}},
                reason="typed reason",
                fetcher="flaresolverr",
                browser_context_seed={"browser_final_url": "https://example.test/final"},
                suggested_filename="typed.html",
                html_failure_reason="abstract_only",
                html_failure_message="HTML exposed only abstract content.",
                extracted_assets=[{"kind": "figure", "url": "https://example.test/f1.png"}],
            ),
            warnings=["typed warning"],
            trace=trace_from_markers(["fulltext:template_html_ok"]),
            metadata={"custom_passthrough": "kept"},
        )

        self.assertEqual(payload.metadata["route"], "html")
        self.assertEqual(payload.metadata["reason"], "typed reason")
        self.assertEqual(payload.metadata["markdown_text"], "# Typed\n\nBody text")
        self.assertEqual(payload.metadata["merged_metadata"], {"title": "Merged Typed Title"})
        self.assertEqual(payload.metadata["availability_diagnostics"], {"accepted": True, "reason": "body_sufficient"})
        self.assertEqual(payload.metadata["html_fetcher"], "flaresolverr")
        self.assertEqual(payload.metadata["browser_context_seed"], {"browser_final_url": "https://example.test/final"})
        self.assertEqual(payload.metadata["suggested_filename"], "typed.html")
        self.assertEqual(payload.metadata["html_failure_reason"], "abstract_only")
        self.assertEqual(payload.metadata["html_failure_message"], "HTML exposed only abstract content.")
        self.assertEqual(payload.metadata["extracted_assets"], [{"kind": "figure", "url": "https://example.test/f1.png"}])
        self.assertEqual(payload.metadata["warnings"], ["typed warning"])
        self.assertEqual(payload.metadata["source_trail"], ["fulltext:template_html_ok"])
        self.assertEqual(payload.metadata["custom_passthrough"], "kept")


class _TemplateClient(ProviderClient):
    name = "template"

    def fetch_raw_fulltext(self, doi: str, metadata: Mapping[str, object], *, context=None) -> RawFulltextPayload:
        del context
        return _payload()

    def to_article_model(
        self,
        metadata: Mapping[str, object],
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets=None,
        asset_failures=None,
        context=None,
    ):
        del context
        return article_from_markdown(
            source="template",
            metadata=metadata,
            doi=str(metadata.get("doi") or "") or None,
            markdown_text=raw_payload.content.markdown_text if raw_payload.content is not None else "",
            warnings=list(raw_payload.warnings),
            trace=list(raw_payload.trace),
        )

    def download_related_assets(self, doi, metadata, raw_payload, output_dir, *, asset_profile="all", context=None):
        del context
        raise ProviderFailure("error", "asset backend failed")

    def asset_download_failure_warning(self, exc):
        message = exc.message if isinstance(exc, ProviderFailure) else str(exc)
        return f"custom asset warning: {message}"


class ProviderFetchResultTemplateTests(unittest.TestCase):
    def test_runtime_parse_cache_returns_copies_for_mutable_payloads(self) -> None:
        context = RuntimeContext(env={})
        key = context.build_parse_cache_key(
            provider="template",
            role="html_payload",
            source="https://example.test/article",
            body="<article>body</article>",
            parser="BeautifulSoup:html.parser",
        )
        context.set_parse_cache(key, {"authors": ["Alice Example"]})

        cached = context.get_parse_cache(key)
        cached["authors"].append("Mutation")

        self.assertEqual(context.get_parse_cache(key), {"authors": ["Alice Example"]})

    def test_base_fetch_result_uses_asset_failure_warning_hook(self) -> None:
        client = _TemplateClient()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = client.fetch_result(
                "10.5555/template",
                {"doi": "10.5555/template", "title": "Template Article"},
                Path(tmpdir),
                asset_profile="all",
            )

        self.assertIn("custom asset warning: asset backend failed", result.warnings)
        self.assertIn("download:template_assets_failed", [event.marker() for event in result.trace if event.marker()])

    def test_base_fetch_result_passes_same_runtime_context_to_all_provider_hooks(self) -> None:
        seen: list[object] = []

        class ContextRecordingClient(_TemplateClient):
            def fetch_raw_fulltext(self, doi, metadata, *, context=None):
                seen.append(context)
                return super().fetch_raw_fulltext(doi, metadata, context=context)

            def download_related_assets(self, doi, metadata, raw_payload, output_dir, *, asset_profile="all", context=None):
                seen.append(context)
                return {"assets": [], "asset_failures": []}

            def to_article_model(
                self,
                metadata,
                raw_payload,
                *,
                downloaded_assets=None,
                asset_failures=None,
                context=None,
            ):
                seen.append(context)
                return super().to_article_model(
                    metadata,
                    raw_payload,
                    downloaded_assets=downloaded_assets,
                    asset_failures=asset_failures,
                    context=context,
                )

        runtime_context = RuntimeContext(env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            ContextRecordingClient().fetch_result(
                "10.5555/template",
                {"doi": "10.5555/template", "title": "Template Article"},
                Path(tmpdir),
                asset_profile="all",
                context=runtime_context,
            )

        self.assertEqual(seen, [runtime_context, runtime_context, runtime_context])

    def test_base_fetch_result_uses_artifact_store_download_dir_when_supplied(self) -> None:
        client = _TemplateClient()
        output_dirs: list[Path | None] = []

        def fake_download_related_assets(doi, metadata, raw_payload, output_dir, *, asset_profile="all", context=None):
            del context
            output_dirs.append(output_dir)
            return {"assets": [], "asset_failures": []}

        client.download_related_assets = fake_download_related_assets
        with tempfile.TemporaryDirectory() as legacy_tmpdir, tempfile.TemporaryDirectory() as artifact_tmpdir:
            artifact_dir = Path(artifact_tmpdir)
            result = client.fetch_result(
                "10.5555/template",
                {"doi": "10.5555/template", "title": "Template Article"},
                Path(legacy_tmpdir),
                asset_profile="all",
                artifact_store=ArtifactStore.from_download_dir(artifact_dir),
            )

        self.assertEqual(output_dirs, [artifact_dir])
        self.assertEqual(result.provider, "template")


if __name__ == "__main__":
    unittest.main()
