from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Mapping

from paper_fetch.models import article_from_markdown
from paper_fetch.providers._waterfall import ProviderWaterfallStep, run_provider_waterfall
from paper_fetch.providers.base import (
    ProviderFailure,
    ProviderClient,
    ProviderContent,
    RawFulltextPayload,
)


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
        metadata={"source_trail": list(markers or ["fulltext:template_html_ok"])},
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
            payload.metadata["source_trail"],
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


class _TemplateClient(ProviderClient):
    name = "template"

    def fetch_raw_fulltext(self, doi: str, metadata: Mapping[str, object]) -> RawFulltextPayload:
        return _payload()

    def to_article_model(
        self,
        metadata: Mapping[str, object],
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets=None,
        asset_failures=None,
    ):
        return article_from_markdown(
            source="template",
            metadata=metadata,
            doi=str(metadata.get("doi") or "") or None,
            markdown_text=raw_payload.content.markdown_text if raw_payload.content is not None else "",
            warnings=list(raw_payload.warnings),
            trace=list(raw_payload.trace),
        )

    def download_related_assets(self, doi, metadata, raw_payload, output_dir, *, asset_profile="all"):
        raise ProviderFailure("error", "asset backend failed")

    def asset_download_failure_warning(self, exc):
        message = exc.message if isinstance(exc, ProviderFailure) else str(exc)
        return f"custom asset warning: {message}"


class ProviderFetchResultTemplateTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
