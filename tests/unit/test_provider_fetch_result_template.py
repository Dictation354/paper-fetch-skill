from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from collections.abc import Mapping

from paper_fetch.artifacts import ArtifactStore
from paper_fetch.models import article_from_markdown
from paper_fetch.providers._waterfall import (
    DEFAULT_WATERFALL_CONTINUE_CODES,
    ProviderWaterfallStep,
    run_provider_waterfall,
)
from paper_fetch.providers.base import (
    combine_provider_failures,
    ProviderFailure,
    ProviderClient,
    ProviderContent,
    RawFulltextPayload,
)
from paper_fetch.runtime import RuntimeContext
from paper_fetch.tracing import trace_event, trace_from_markers


def _payload(
    *,
    source_url: str = "https://example.test/article",
    markers: list[str] | None = None,
) -> RawFulltextPayload:
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
        trace=trace_from_markers(
            list(["fulltext:template_html_ok"] if markers is None else markers)
        ),
    )


class ProviderWaterfallRunnerTests(unittest.TestCase):
    def test_step_default_continue_codes_match_provider_fallback_contract(self) -> None:
        step = ProviderWaterfallStep(label="html", run=lambda _state: _payload())

        self.assertEqual(step.continue_codes, DEFAULT_WATERFALL_CONTINUE_CODES)

    def test_runner_accumulates_warnings_and_stops_after_success(self) -> None:
        calls: list[str] = []

        def first(_state):
            calls.append("first")
            raise ProviderFailure(
                "no_result",
                "HTML was abstract only.",
                warnings=["first warning", "trying pdf"],
            )

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
        self.assertEqual(
            payload.warnings, ["first warning", "trying pdf", "pdf success"]
        )
        self.assertEqual(
            [event.marker() for event in payload.trace if event.marker()],
            [
                "fulltext:template_html_fail",
                "fulltext:template_pdf_ok",
                "fulltext:html_fail",
                "fulltext:pdf_ok",
            ],
        )

    def test_runner_combines_failures_when_all_steps_fail(self) -> None:
        with self.assertRaises(ProviderFailure) as raised:
            run_provider_waterfall(
                [
                    ProviderWaterfallStep(
                        label="html",
                        run=lambda _state: (_ for _ in ()).throw(
                            ProviderFailure("no_result", "HTML failed.")
                        ),
                        failure_marker="fulltext:template_html_fail",
                    ),
                    ProviderWaterfallStep(
                        label="pdf",
                        run=lambda _state: (_ for _ in ()).throw(
                            ProviderFailure("no_result", "PDF failed.")
                        ),
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

    def test_runner_combines_initial_trail_when_all_steps_fail(self) -> None:
        with self.assertRaises(ProviderFailure) as raised:
            run_provider_waterfall(
                [
                    ProviderWaterfallStep(
                        label="html",
                        run=lambda _state: (_ for _ in ()).throw(
                            ProviderFailure(
                                "no_result",
                                "HTML failed.",
                                source_trail=["fulltext:template_html_fail"],
                            )
                        ),
                    )
                ],
                initial_source_trail=["fulltext:template_landing_ok"],
            )

        self.assertEqual(
            raised.exception.source_trail,
            ["fulltext:template_landing_ok", "fulltext:template_html_fail"],
        )

    def test_runner_short_circuit_failure_keeps_prior_state(self) -> None:
        with self.assertRaises(ProviderFailure) as raised:
            run_provider_waterfall(
                [
                    ProviderWaterfallStep(
                        label="html",
                        run=lambda _state: (_ for _ in ()).throw(
                            ProviderFailure(
                                "rate_limited",
                                "HTML was rate limited.",
                                retry_after_seconds=9,
                                warnings=["html warning"],
                            )
                        ),
                        failure_marker="fulltext:template_html_fail",
                    ),
                    ProviderWaterfallStep(
                        label="pdf",
                        run=lambda _state: (_ for _ in ()).throw(
                            ProviderFailure("no_access", "PDF was blocked.")
                        ),
                        failure_marker="fulltext:template_pdf_fail",
                        continue_codes=(),
                    ),
                ]
            )

        self.assertEqual(raised.exception.code, "no_access")
        self.assertEqual(raised.exception.retry_after_seconds, 9)
        self.assertEqual(raised.exception.warnings, ["html warning"])
        self.assertEqual(
            raised.exception.source_trail,
            ["fulltext:template_html_fail", "fulltext:template_pdf_fail"],
        )

    def test_runner_custom_final_failure_keeps_state_fields(self) -> None:
        def final_failure(_state):
            return ProviderFailure("error", "Custom final failure.")

        with self.assertRaises(ProviderFailure) as raised:
            run_provider_waterfall(
                [
                    ProviderWaterfallStep(
                        label="html",
                        run=lambda _state: (_ for _ in ()).throw(
                            ProviderFailure(
                                "rate_limited",
                                "HTML was rate limited.",
                                retry_after_seconds=11,
                                missing_env=["HTML_TOKEN"],
                                warnings=["html warning"],
                            )
                        ),
                        failure_marker="fulltext:template_html_fail",
                    )
                ],
                final_failure_factory=final_failure,
            )

        self.assertEqual(raised.exception.code, "error")
        self.assertEqual(raised.exception.retry_after_seconds, 11)
        self.assertEqual(raised.exception.missing_env, ["HTML_TOKEN"])
        self.assertEqual(raised.exception.warnings, ["html warning"])
        self.assertEqual(raised.exception.source_trail, ["fulltext:template_html_fail"])

    def test_combine_provider_failures_preserves_retry_after_and_dedupes_details(
        self,
    ) -> None:
        combined = combine_provider_failures(
            [
                (
                    "html",
                    ProviderFailure(
                        "no_result",
                        "HTML failed.",
                        warnings=["shared", "html warning"],
                        source_trail=["fulltext:template_html_fail", "shared_marker"],
                    ),
                ),
                (
                    "pdf",
                    ProviderFailure(
                        "rate_limited",
                        "PDF was rate limited.",
                        retry_after_seconds=7,
                        warnings=["shared", "pdf warning"],
                        source_trail=["shared_marker", "fulltext:template_pdf_fail"],
                    ),
                ),
            ]
        )

        self.assertEqual(combined.code, "no_result")
        self.assertEqual(combined.retry_after_seconds, 7)
        self.assertEqual(combined.warnings, ["shared", "html warning", "pdf warning"])
        self.assertEqual(
            combined.source_trail,
            [
                "fulltext:template_html_fail",
                "shared_marker",
                "fulltext:template_pdf_fail",
            ],
        )

    def test_runner_skips_step_when_condition_is_false(self) -> None:
        calls: list[str] = []

        def first(_state):
            calls.append("first")
            raise ProviderFailure("no_result", "HTML failed.")

        def skipped(_state):
            calls.append("skipped")
            return _payload()

        def second(_state):
            calls.append("second")
            return _payload(markers=["fulltext:template_pdf_ok"])

        payload = run_provider_waterfall(
            [
                ProviderWaterfallStep(
                    label="html",
                    run=first,
                    failure_marker="fulltext:template_html_fail",
                ),
                ProviderWaterfallStep(
                    label="conditional",
                    run=skipped,
                    condition=lambda state: state.failure("html") is None,
                    failure_marker="fulltext:template_conditional_fail",
                ),
                ProviderWaterfallStep(label="pdf", run=second),
            ]
        )

        self.assertEqual(calls, ["first", "second"])
        self.assertEqual(payload.content.source_url, "https://example.test/article")

    def test_runner_preserves_structured_failure_trace_on_fallback_success(
        self,
    ) -> None:
        payload = _payload()
        payload.trace = [
            trace_event(
                "fulltext",
                "template_html",
                "fail",
                code="browser_runtime_prepare_timeout",
                message="Camoufox runtime preparation timed out.",
            )
        ]

        result = run_provider_waterfall(
            [
                ProviderWaterfallStep(
                    label="pdf",
                    run=lambda _state: payload,
                    success_markers=("fulltext:template_pdf_fallback_ok",),
                )
            ],
            initial_source_trail=["fulltext:template_html_fail"],
        )

        html_event = next(
            event
            for event in result.trace
            if event.marker() == "fulltext:template_html_fail"
        )
        self.assertEqual(html_event.code, "browser_runtime_prepare_timeout")
        self.assertEqual(html_event.message, "Camoufox runtime preparation timed out.")


class _TemplateClient(ProviderClient):
    name = "template"

    def fetch_raw_fulltext(
        self, doi: str, metadata: Mapping[str, object], *, context=None
    ) -> RawFulltextPayload:
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
            markdown_text=raw_payload.content.markdown_text
            if raw_payload.content is not None
            else "",
            warnings=list(raw_payload.warnings),
            trace=list(raw_payload.trace),
        )

    def download_related_assets(
        self,
        doi,
        metadata,
        raw_payload,
        output_dir,
        *,
        asset_profile="all",
        context=None,
    ):
        del context
        raise ProviderFailure("error", "asset backend failed")

    def asset_download_failure_warning(self, exc):
        message = exc.message if isinstance(exc, ProviderFailure) else str(exc)
        return f"custom asset warning: {message}"


class ProviderFetchResultTemplateTests(unittest.TestCase):
    def test_base_fetch_result_returns_content_updated_by_asset_hook(self) -> None:
        final_markdown = "# Template Article\n\n## Results\n\nFinal body " * 80

        class UpdatingAssetClient(_TemplateClient):
            def download_related_assets(
                self,
                doi,
                metadata,
                raw_payload,
                output_dir,
                *,
                asset_profile="all",
                context=None,
            ):
                del doi, metadata, output_dir, asset_profile, context
                raw_payload.content = replace(
                    raw_payload.content,
                    markdown_text=final_markdown,
                    source_url="https://example.test/final",
                )
                return {"assets": [], "asset_failures": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            result = UpdatingAssetClient().fetch_result(
                "10.5555/template",
                {"doi": "10.5555/template", "title": "Template Article"},
                Path(tmpdir),
                asset_profile="body",
            )

        self.assertEqual(result.content.source_url, "https://example.test/final")
        self.assertEqual(result.content.markdown_text, final_markdown)
        self.assertIn("Final body", result.article.to_ai_markdown())

    def test_base_fetch_result_auto_converts_html_fulltext_to_markdown(self) -> None:
        body = (
            "<html><body><article><h1>Auto HTML Article</h1><h2>Results</h2><p>"
            + ("Automatic conversion works. " * 80)
            + "</p></article></body></html>"
        ).encode()

        class HtmlOnlyClient(_TemplateClient):
            def fetch_raw_fulltext(self, doi, metadata, *, context=None):
                del context
                return RawFulltextPayload(
                    provider="template",
                    source_url="https://example.test/article",
                    content_type="text/html",
                    body=body,
                    content=ProviderContent(
                        route_kind="html",
                        source_url="https://example.test/article",
                        content_type="text/html",
                        body=body,
                    ),
                    trace=trace_from_markers(["fulltext:template_html_ok"]),
                )

        result = HtmlOnlyClient().fetch_result(
            "10.5555/template",
            {"doi": "10.5555/template", "title": "Auto HTML Article"},
            None,
        )

        self.assertIsNotNone(result.content)
        assert result.content is not None
        self.assertIn("Automatic conversion works", result.content.markdown_text or "")
        self.assertIn("Automatic conversion works", result.article.to_ai_markdown())

    def test_base_fetch_result_decodes_html_with_payload_charset(self) -> None:
        body = (
            "<html><body><article><h1>Charset Article</h1><h2>Results</h2><p>"
            + ("Café conversion works. " * 80)
            + "</p></article></body></html>"
        ).encode("iso-8859-1")

        class LatinHtmlClient(_TemplateClient):
            def fetch_raw_fulltext(self, doi, metadata, *, context=None):
                del doi, metadata, context
                return RawFulltextPayload(
                    provider="template",
                    source_url="https://example.test/article",
                    content_type="text/html; charset=iso-8859-1",
                    body=body,
                    content=ProviderContent(
                        route_kind="html",
                        source_url="https://example.test/article",
                        content_type="text/html; charset=iso-8859-1",
                        body=body,
                    ),
                    trace=trace_from_markers(["fulltext:template_html_ok"]),
                )

        result = LatinHtmlClient().fetch_result(
            "10.5555/template",
            {"doi": "10.5555/template", "title": "Charset Article"},
            None,
        )

        self.assertIsNotNone(result.content)
        assert result.content is not None
        self.assertIn("Café conversion works", result.content.markdown_text or "")

    def test_runtime_parse_cache_returns_copies_for_mutable_payloads(self) -> None:
        context = RuntimeContext(env={})
        key = context.build_parse_cache_key(
            provider="template",
            role="html_payload",
            source="https://example.test/article",
            body="<article>body</article>",
            parser="BeautifulSoup:html.parser",
        )
        cached = context.get_or_set_parse_cache(
            key,
            lambda: {"authors": ["Alice Example"]},
        )
        cached["authors"].append("Mutation")

        self.assertEqual(
            context.get_or_set_parse_cache(
                key,
                lambda: self.fail("cached parse factory should not run"),
            ),
            {"authors": ["Alice Example"]},
        )

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
        self.assertIn(
            "download:template_assets_failed",
            [event.marker() for event in result.trace if event.marker()],
        )

    def test_base_fetch_result_passes_same_runtime_context_to_all_provider_hooks(
        self,
    ) -> None:
        seen: list[object] = []

        class ContextRecordingClient(_TemplateClient):
            def fetch_raw_fulltext(self, doi, metadata, *, context=None):
                seen.append(context)
                return super().fetch_raw_fulltext(doi, metadata, context=context)

            def download_related_assets(
                self,
                doi,
                metadata,
                raw_payload,
                output_dir,
                *,
                asset_profile="all",
                context=None,
            ):
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

    def test_base_fetch_result_uses_artifact_store_download_dir_when_supplied(
        self,
    ) -> None:
        client = _TemplateClient()
        output_dirs: list[Path | None] = []

        def fake_download_related_assets(
            doi, metadata, raw_payload, output_dir, *, asset_profile="all", context=None
        ):
            del context
            output_dirs.append(output_dir)
            return {"assets": [], "asset_failures": []}

        client.download_related_assets = fake_download_related_assets
        with (
            tempfile.TemporaryDirectory() as legacy_tmpdir,
            tempfile.TemporaryDirectory() as artifact_tmpdir,
        ):
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
