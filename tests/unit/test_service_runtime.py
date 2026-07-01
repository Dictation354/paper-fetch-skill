# ruff: noqa: F403,F405
from __future__ import annotations

from ._service_support import *


class ServiceRuntimeTests(unittest.TestCase):
    def test_probe_then_fetch_reuses_crossref_metadata_in_same_runtime_context(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1126/science.cache",
            query_kind="doi",
            doi="10.1126/science.cache",
            landing_url="https://www.science.org/doi/full/10.1126/science.cache",
            provider_hint="science",
            confidence=1.0,
        )
        crossref = StubProvider(
            metadata={
                "provider": "crossref",
                "official_provider": False,
                "doi": resolved.doi,
                "title": "Cached Crossref Article",
                "publisher": "American Association for the Advancement of Science",
                "landing_page_url": resolved.landing_url,
                "license_urls": ["https://license.example/science-cache"],
                "fulltext_links": [],
                "references": [],
            }
        )
        crossref_calls = {"count": 0}
        original_fetch_metadata = crossref.fetch_metadata

        def counted_fetch_metadata(query):
            crossref_calls["count"] += 1
            return original_fetch_metadata(query)

        crossref.fetch_metadata = counted_fetch_metadata
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            context = RuntimeContext(
                env={},
                clients={
                    "crossref": crossref,
                    "science": StubProvider(
                        raw_payload=_typed_payload(
                            provider="science",
                            source_url=resolved.landing_url,
                            content_type="text/html",
                            body=b"<html></html>",
                            route_kind="html",
                            markdown_text="# Example Article\n\n## Results\n\n" + ("Body text " * 80),
                            source_trail=["fulltext:science_html_ok"],
                        ),
                        article=sample_article(),
                    ),
                },
            )

            probe = _probe_has_fulltext(resolved.query, context=context)
            envelope = _fetch_paper(
                resolved.query,
                modes={"article"},
                strategy=paper_fetch.FetchStrategy(asset_profile="none"),
                context=context,
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(probe.evidence, ["crossref_license"])
        self.assertIsNotNone(envelope.article)
        self.assertEqual(crossref_calls["count"], 1)
    def test_landing_citation_pdf_probe_is_reused_by_fetch_metadata_links(self) -> None:
        landing_url = "https://example.test/article"
        resolved = paper_fetch.ResolvedQuery(
            query=landing_url,
            query_kind="url",
            doi="10.1126/science.landing",
            landing_url=landing_url,
            provider_hint="science",
            confidence=1.0,
        )
        captured_metadata: list[dict[str, object]] = []
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            context = RuntimeContext(
                env={"PAPER_FETCH_SKILL_USER_AGENT": "unit-test"},
                transport=FixtureHtmlTransport(
                    {
                        landing_url: {
                            "body": (
                                b"<html><head>"
                                b"<meta name='citation_title' content='Landing Cache Article' />"
                                b"<meta name='citation_pdf_url' content='/article.pdf' />"
                                b"</head><body></body></html>"
                            )
                        }
                    }
                ),
                clients={
                    "science": StubProvider(
                        raw_payload=_typed_payload(
                            provider="science",
                            source_url=landing_url,
                            content_type="text/html",
                            body=b"<html></html>",
                            route_kind="html",
                            markdown_text="# Example Article\n\n## Results\n\n" + ("Body text " * 80),
                            source_trail=["fulltext:science_html_ok"],
                        ),
                        article_factory=lambda metadata, raw_payload, **kwargs: (
                            captured_metadata.append(dict(metadata)) or sample_article()
                        ),
                    )
                },
            )

            probe = _probe_has_fulltext(landing_url, context=context)
            envelope = _fetch_paper(
                landing_url,
                modes={"article"},
                strategy=paper_fetch.FetchStrategy(asset_profile="none"),
                context=context,
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(probe.evidence, ["landing_page_citation_pdf_url"])
        self.assertIsNotNone(envelope.article)
        links = captured_metadata[0]["fulltext_links"]
        self.assertIn(
            {
                "url": "https://example.test/article.pdf",
                "content_type": "application/pdf",
                "content_version": None,
                "intended_application": "full_text",
            },
            links,
        )
    def test_session_cache_does_not_cross_runtime_contexts_or_contextless_calls(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1126/science.cache-isolated",
            query_kind="doi",
            doi="10.1126/science.cache-isolated",
            landing_url="https://www.science.org/doi/full/10.1126/science.cache-isolated",
            provider_hint="science",
            confidence=1.0,
        )

        def counting_crossref(counter: dict[str, int]) -> StubProvider:
            provider = StubProvider(
                metadata={
                    "provider": "crossref",
                    "official_provider": False,
                    "doi": resolved.doi,
                    "title": "Isolated Crossref Article",
                    "publisher": "American Association for the Advancement of Science",
                    "landing_page_url": resolved.landing_url,
                    "license_urls": ["https://license.example/science-cache-isolated"],
                    "fulltext_links": [],
                    "references": [],
                }
            )
            original_fetch_metadata = provider.fetch_metadata

            def counted_fetch_metadata(query):
                counter["count"] += 1
                return original_fetch_metadata(query)

            provider.fetch_metadata = counted_fetch_metadata
            return provider

        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            different_context_counter = {"count": 0}
            first_context = RuntimeContext(env={}, clients={"crossref": counting_crossref(different_context_counter)})
            second_context = RuntimeContext(env={}, clients={"crossref": counting_crossref(different_context_counter)})

            _probe_has_fulltext(resolved.query, context=first_context)
            _probe_has_fulltext(resolved.query, context=second_context)

            contextless_counter = {"count": 0}
            _probe_has_fulltext(
                resolved.query,
                clients={"crossref": counting_crossref(contextless_counter)},
            )
            _probe_has_fulltext(
                resolved.query,
                clients={"crossref": counting_crossref(contextless_counter)},
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(different_context_counter["count"], 2)
        self.assertEqual(contextless_counter["count"], 2)
    def test_fetch_paper_uses_runtime_context_dependencies_when_legacy_keywords_are_omitted(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1126/science.context",
            query_kind="doi",
            doi="10.1126/science.context",
            landing_url="https://www.science.org/doi/full/10.1126/science.context",
            provider_hint="science",
            confidence=1.0,
        )
        captured: dict[str, object] = {}
        asset_output_dirs: list[Path | None] = []
        runtime_transport = HttpTransport()
        runtime_env = {"CROSSREF_MAILTO": "runtime@example.test"}
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda query, *, transport=None, env=None: (
                captured.update({"transport": transport, "env": env}) or resolved
            )
            with tempfile.TemporaryDirectory() as tmpdir:
                context = RuntimeContext(
                    env=runtime_env,
                    transport=runtime_transport,
                    clients={
                        "science": StubProvider(
                            raw_payload=_typed_payload(
                                provider="science",
                                source_url=resolved.landing_url,
                                content_type="text/html",
                                body=b"<html></html>",
                                route_kind="html",
                                markdown_text="# Example Article\n\n## Results\n\n" + ("Body text " * 80),
                                source_trail=["fulltext:science_html_ok"],
                            ),
                            article=sample_article(),
                            related_asset_factory=lambda _doi, _metadata, _payload, output_dir, **_kwargs: (
                                asset_output_dirs.append(output_dir) or {"assets": [], "asset_failures": []}
                            ),
                        )
                    },
                    download_dir=Path(tmpdir),
                )

                envelope = _fetch_paper(
                    resolved.query,
                    modes={"article"},
                    strategy=paper_fetch.FetchStrategy(asset_profile="body"),
                    context=context,
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertIsNotNone(envelope.article)
        self.assertIs(captured["transport"], runtime_transport)
        self.assertEqual(captured["env"], runtime_env)
        self.assertEqual(asset_output_dirs, [context.download_dir])
    def test_provider_client_fetch_result_accumulates_asset_timing(self) -> None:
        class TimedProvider(ProviderClient):
            name = "timed"

            def fetch_raw_fulltext(self, doi, metadata, *, context=None):
                return _typed_payload(
                    provider="timed",
                    source_url="https://example.test/article",
                    content_type="text/xml",
                    body=b"<xml/>",
                    route_kind="official",
                )

            def to_article_model(
                self,
                metadata,
                raw_payload,
                *,
                downloaded_assets=None,
                asset_failures=None,
                context=None,
            ):
                return sample_article()

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
                return {"assets": [], "asset_failures": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            context = RuntimeContext(env={}, download_dir=Path(tmpdir))
            original_monotonic = runtime_module.time.monotonic
            monotonic_values = iter([100.0, 100.2])
            try:
                runtime_module.time.monotonic = lambda: next(monotonic_values)
                TimedProvider().fetch_result(
                    "10.1000/timed",
                    {"title": "Timed"},
                    Path(tmpdir),
                    asset_profile="body",
                    context=context,
                )
            finally:
                runtime_module.time.monotonic = original_monotonic

        self.assertEqual(context.stage_timings["asset_seconds"], 0.2)
    def test_raw_fulltext_provider_branch_accumulates_asset_timing(self) -> None:
        class RawTimedProvider:
            name = "raw_timed"

            def fetch_raw_fulltext(self, doi, metadata, *, context=None):
                return _typed_payload(
                    provider="raw_timed",
                    source_url="https://example.test/article",
                    content_type="text/xml",
                    body=b"<xml/>",
                    route_kind="official",
                )

            def to_article_model(
                self,
                metadata,
                raw_payload,
                *,
                downloaded_assets=None,
                asset_failures=None,
                context=None,
            ):
                return sample_article()

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
                return {"assets": [], "asset_failures": []}

            def asset_download_failure_warning(self, exc):
                return str(exc)

        with tempfile.TemporaryDirectory() as tmpdir:
            context = RuntimeContext(env={}, download_dir=Path(tmpdir))
            artifact_store = ArtifactStore.from_download_dir(Path(tmpdir))
            original_monotonic = runtime_module.time.monotonic
            monotonic_values = iter([200.0, 200.3])
            try:
                runtime_module.time.monotonic = lambda: next(monotonic_values)
                _provider_fetch_result(
                    RawTimedProvider(),
                    doi="10.1000/raw-timed",
                    metadata={"title": "Raw Timed"},
                    artifact_store=artifact_store,
                    asset_profile="body",
                    context=context,
                )
            finally:
                runtime_module.time.monotonic = original_monotonic

        self.assertEqual(context.stage_timings["asset_seconds"], 0.3)
    def test_provider_fetch_result_passes_artifact_store_to_fulltext_provider(self) -> None:
        seen: dict[str, object] = {}

        class RecordingProvider:
            name = "recording"

            def fetch_result(
                self,
                doi,
                metadata,
                output_dir,
                *,
                asset_profile="none",
                artifact_store=None,
                context=None,
            ):
                seen["output_dir"] = output_dir
                seen["artifact_store"] = artifact_store
                seen["context"] = context
                return ProviderFetchResult(provider="recording", article=sample_article())

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_store = ArtifactStore.from_download_dir(Path(tmpdir))
            context = RuntimeContext(env={}, download_dir=Path(tmpdir))
            _provider_fetch_result(
                RecordingProvider(),
                doi="10.1000/recording",
                metadata={"title": "Recording"},
                artifact_store=artifact_store,
                asset_profile="body",
                context=context,
            )

        self.assertEqual(seen["output_dir"], artifact_store.download_dir)
        self.assertIs(seen["artifact_store"], artifact_store)
        self.assertIs(seen["context"], context)
    def test_fetch_paper_rejects_legacy_runtime_keywords(self) -> None:
        with self.assertRaises(TypeError):
            paper_fetch.fetch_paper("10.1126/science.override", clients={})

        with self.assertRaises(TypeError):
            paper_fetch.fetch_paper("10.1126/science.override", download_dir=Path("/tmp/paper-fetch-test"))
    def test_probe_has_fulltext_rejects_legacy_runtime_keywords(self) -> None:
        with self.assertRaises(TypeError):
            paper_fetch.probe_has_fulltext("10.1126/science.override", clients={})
    def test_artifact_store_preserves_provider_payload_and_springer_html_markers(self) -> None:
        pdf_content = ProviderContent(
            route_kind="pdf_fallback",
            source_url="https://example.test/article.pdf",
            content_type="application/pdf",
            body=fulltext_pdf_bytes(),
            needs_local_copy=True,
        )
        html_content = ProviderContent(
            route_kind="html",
            source_url="https://www.nature.com/articles/example",
            content_type="text/html; charset=utf-8",
            body=b"<html><body>Springer article</body></html>",
        )

        skipped_warnings, skipped_trail = ArtifactStore.from_download_dir(None).save_provider_payload(
            "wiley",
            content=pdf_content,
            doi="10.1111/example",
            metadata={"title": "Example Article"},
        )
        self.assertEqual(
            skipped_warnings,
            ["Wiley official PDF/binary was not written to disk because --no-download was set."],
        )
        self.assertEqual(skipped_trail, ["download:wiley_skipped"])
        ieee_skipped_warnings, ieee_skipped_trail = ArtifactStore.from_download_dir(None).save_provider_payload(
            "ieee",
            content=pdf_content,
            doi="10.1109/example",
            metadata={"title": "IEEE Example"},
        )
        self.assertEqual(
            ieee_skipped_warnings,
            ["IEEE official PDF/binary was not written to disk because --no-download was set."],
        )
        self.assertEqual(ieee_skipped_trail, ["download:ieee_skipped"])

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore.from_download_dir(Path(tmpdir))
            saved_warnings, saved_trail = store.save_provider_payload(
                "wiley",
                content=pdf_content,
                doi="10.1111/example",
                metadata={"title": "Example Article"},
            )
            html_warnings, html_trail = store.save_provider_html_payload(
                "springer",
                content=html_content,
                doi="10.1007/example",
                metadata={"title": "Springer Example"},
            )
            wiley_html_warnings, wiley_html_trail = store.save_provider_html_payload(
                "wiley",
                content=html_content,
                doi="10.1111/example",
                metadata={"title": "Wiley Example"},
            )

            saved_paths = list(Path(tmpdir).glob("*"))

        self.assertEqual(saved_trail, ["download:wiley_saved"])
        self.assertTrue(any("Wiley official full text was downloaded as PDF/binary to" in item for item in saved_warnings))
        self.assertEqual(html_warnings, [])
        self.assertEqual(html_trail, ["download:springer_html_saved"])
        self.assertEqual(wiley_html_warnings, [])
        self.assertEqual(wiley_html_trail, [])
        self.assertTrue(any(path.name.endswith(".pdf") for path in saved_paths))
        self.assertTrue(any(path.name.endswith("_original.html") for path in saved_paths))

    def test_artifact_store_markdown_assets_keeps_pdf_fallback_but_skips_raw_html(self) -> None:
        pdf_content = ProviderContent(
            route_kind="pdf_fallback",
            source_url="https://example.test/article.pdf",
            content_type="application/pdf",
            body=fulltext_pdf_bytes(),
            needs_local_copy=True,
        )
        html_content = ProviderContent(
            route_kind="html",
            source_url="https://www.nature.com/articles/example",
            content_type="text/html; charset=utf-8",
            body=b"<html><body>Springer article</body></html>",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore.from_download_dir(
                Path(tmpdir), artifact_mode="markdown-assets"
            )
            saved_warnings, saved_trail = store.save_provider_payload(
                "wiley",
                content=pdf_content,
                doi="10.1111/example",
                metadata={"title": "Example Article"},
            )
            html_warnings, html_trail = store.save_provider_html_payload(
                "springer",
                content=html_content,
                doi="10.1007/example",
                metadata={"title": "Springer Example"},
            )
            saved_paths = list(Path(tmpdir).glob("*"))

        self.assertEqual(saved_trail, ["download:wiley_saved"])
        self.assertTrue(any("Wiley official full text was downloaded as PDF/binary to" in item for item in saved_warnings))
        self.assertEqual(html_warnings, [])
        self.assertEqual(html_trail, [])
        self.assertTrue(any(path.name.endswith(".pdf") for path in saved_paths))
        self.assertFalse(any(path.name.endswith("_original.html") for path in saved_paths))

    def test_artifact_store_uses_payload_merged_metadata_for_pdf_payload_filename(self) -> None:
        pdf_content = ProviderContent(
            route_kind="pdf_fallback",
            source_url="https://arxiv.org/pdf/2510.02576",
            content_type="application/pdf",
            body=fulltext_pdf_bytes(),
            merged_metadata={
                "doi": "10.48550/arxiv.2510.02576",
                "title": "Deep learning for flash drought forecasting and interpretation",
                "authors": [
                    "Qian Zhao",
                    "Xuwei Tan",
                    "Xueru Zhang",
                    "Pierre Gentine",
                    "Yanlan Liu",
                ],
                "published": "2025-10-02",
            },
            needs_local_copy=True,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore.from_download_dir(
                Path(tmpdir), artifact_mode="markdown-assets"
            )
            saved_warnings, saved_trail = store.save_provider_payload(
                "arxiv",
                content=pdf_content,
                doi="10.48550/arxiv.2510.02576",
                metadata={
                    "doi": "10.48550/arxiv.2510.02576",
                    "journal_title": "arXiv",
                },
            )
            saved_paths = list(Path(tmpdir).iterdir())

        self.assertEqual(saved_trail, ["download:arxiv_saved"])
        self.assertTrue(
            any(
                "arXiv official full text was downloaded as PDF/binary to" in item
                for item in saved_warnings
            )
        )
        self.assertEqual(
            [path.name for path in saved_paths],
            [
                "Zhao_et_al_2025_Deep_learning_for_flash_drought_forecasting_and_interpretation.pdf"
            ],
        )

    def test_artifact_store_none_skips_provider_payload_and_assets(self) -> None:
        pdf_content = ProviderContent(
            route_kind="pdf_fallback",
            source_url="https://example.test/article.pdf",
            content_type="application/pdf",
            body=fulltext_pdf_bytes(),
            needs_local_copy=True,
        )
        warnings: list[str] = []
        source_trail: list[str] = []

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ArtifactStore.from_download_dir(Path(tmpdir), artifact_mode="none")
            saved_warnings, saved_trail = store.save_provider_payload(
                "wiley",
                content=pdf_content,
                doi="10.1111/example",
                metadata={"title": "Example Article"},
            )
            store.apply_provider_artifacts(
                provider_name="wiley",
                artifacts=ProviderArtifacts(
                    assets=[{"path": str(Path(tmpdir) / "asset.png"), "download_tier": "full_size"}]
                ),
                asset_profile="body",
                warnings=warnings,
                source_trail=source_trail,
            )
            saved_paths = list(Path(tmpdir).glob("*"))

        self.assertEqual(saved_warnings, [])
        self.assertEqual(saved_trail, [])
        self.assertEqual(warnings, [])
        self.assertEqual(source_trail, [])
        self.assertEqual(saved_paths, [])
