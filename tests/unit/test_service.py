from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path

from paper_fetch import service as paper_fetch
from paper_fetch.artifacts import ArtifactStore
from paper_fetch.runtime import RuntimeContext
from paper_fetch.http import HttpTransport, RequestFailure
from paper_fetch.providers import _springer_html as springer_html_helper, pnas as pnas_provider, science as science_provider
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.wiley import WileyClient
from paper_fetch.utils import choose_public_landing_page_url

from ._paper_fetch_support import (
    FixtureHtmlTransport,
    StubProvider,
    fetch_paper_model,
    fulltext_pdf_bytes,
    sample_article,
)


class RecordCaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class ServiceTests(unittest.TestCase):
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
                            raw_payload=RawFulltextPayload(
                                provider="science",
                                source_url=resolved.landing_url,
                                content_type="text/html",
                                body=b"<html></html>",
                                metadata={
                                    "route": "html",
                                    "markdown_text": "# Example Article\n\n## Results\n\n" + ("Body text " * 80),
                                    "source_trail": ["fulltext:science_html_ok"],
                                },
                            ),
                            article=sample_article(),
                            related_asset_factory=lambda _doi, _metadata, _payload, output_dir, **_kwargs: (
                                asset_output_dirs.append(output_dir) or {"assets": [], "asset_failures": []}
                            ),
                        )
                    },
                    download_dir=Path(tmpdir),
                )

                envelope = paper_fetch.fetch_paper(
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

    def test_fetch_paper_legacy_keywords_override_runtime_context(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1126/science.override",
            query_kind="doi",
            doi="10.1126/science.override",
            landing_url="https://www.science.org/doi/full/10.1126/science.override",
            provider_hint="science",
            confidence=1.0,
        )
        captured: dict[str, object] = {}
        context_asset_dirs: list[Path | None] = []
        override_asset_dirs: list[Path | None] = []
        context_transport = HttpTransport()
        override_transport = HttpTransport()
        context_env = {"CROSSREF_MAILTO": "context@example.test"}
        override_env = {"CROSSREF_MAILTO": "override@example.test"}
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda query, *, transport=None, env=None: (
                captured.update({"transport": transport, "env": env}) or resolved
            )
            with tempfile.TemporaryDirectory() as context_tmpdir, tempfile.TemporaryDirectory() as override_tmpdir:
                context = RuntimeContext(
                    env=context_env,
                    transport=context_transport,
                    clients={
                        "science": StubProvider(
                            raw_payload=RawFulltextPayload(
                                provider="science",
                                source_url=resolved.landing_url,
                                content_type="text/html",
                                body=b"<html></html>",
                                metadata={
                                    "route": "html",
                                    "markdown_text": "# Context Article\n\n## Results\n\n" + ("Body text " * 80),
                                },
                            ),
                            article=sample_article(),
                            related_asset_factory=lambda _doi, _metadata, _payload, output_dir, **_kwargs: (
                                context_asset_dirs.append(output_dir) or {"assets": [], "asset_failures": []}
                            ),
                        )
                    },
                    download_dir=Path(context_tmpdir),
                )
                override_dir = Path(override_tmpdir)

                envelope = paper_fetch.fetch_paper(
                    resolved.query,
                    modes={"article"},
                    strategy=paper_fetch.FetchStrategy(asset_profile="body"),
                    context=context,
                    env=override_env,
                    transport=override_transport,
                    clients={
                        "science": StubProvider(
                            raw_payload=RawFulltextPayload(
                                provider="science",
                                source_url=resolved.landing_url,
                                content_type="text/html",
                                body=b"<html></html>",
                                metadata={
                                    "route": "html",
                                    "markdown_text": "# Override Article\n\n## Results\n\n" + ("Body text " * 80),
                                },
                            ),
                            article=sample_article(),
                            related_asset_factory=lambda _doi, _metadata, _payload, output_dir, **_kwargs: (
                                override_asset_dirs.append(output_dir) or {"assets": [], "asset_failures": []}
                            ),
                        )
                    },
                    download_dir=override_dir,
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertIsNotNone(envelope.article)
        self.assertIs(captured["transport"], override_transport)
        self.assertEqual(captured["env"], override_env)
        self.assertEqual(context_asset_dirs, [])
        self.assertEqual(override_asset_dirs, [override_dir])

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

            saved_paths = list(Path(tmpdir).glob("*"))

        self.assertEqual(saved_trail, ["download:wiley_saved"])
        self.assertTrue(any("Wiley official full text was downloaded as PDF/binary to" in item for item in saved_warnings))
        self.assertEqual(html_warnings, [])
        self.assertEqual(html_trail, ["download:springer_html_saved"])
        self.assertTrue(any(path.name.endswith(".pdf") for path in saved_paths))
        self.assertTrue(any(path.name.endswith("_original.html") for path in saved_paths))

    def test_fetch_paper_omitted_asset_profile_defaults_to_body_for_scoped_html_providers(self) -> None:
        cases = [
            ("springer", "10.1007/test", "https://www.nature.com/articles/example"),
            ("wiley", "10.1111/test", "https://example.test/wiley"),
            ("science", "10.1126/science.test", "https://www.science.org/doi/full/10.1126/science.test"),
            ("pnas", "10.1073/pnas.test", "https://www.pnas.org/doi/10.1073/pnas.test"),
        ]
        original_resolve = paper_fetch.resolve_paper
        try:
            for provider_name, doi, landing_url in cases:
                with self.subTest(provider=provider_name):
                    related_asset_calls: list[str] = []
                    resolved = paper_fetch.ResolvedQuery(
                        query=doi,
                        query_kind="doi",
                        doi=doi,
                        landing_url=landing_url,
                        provider_hint=provider_name,
                        confidence=1.0,
                    )
                    paper_fetch.resolve_paper = lambda *args, _resolved=resolved, **kwargs: _resolved
                    with tempfile.TemporaryDirectory() as tmpdir:
                        envelope = paper_fetch.fetch_paper(
                            doi,
                            modes={"article"},
                            strategy=paper_fetch.FetchStrategy(),
                            download_dir=Path(tmpdir),
                            clients={
                                provider_name: StubProvider(
                                    raw_payload=RawFulltextPayload(
                                        provider=provider_name,
                                        source_url=landing_url,
                                        content_type="text/html",
                                        body=b"<html></html>",
                                        metadata={
                                            "route": "html",
                                            "markdown_text": "# Example Article\n\n## Results\n\n" + ("Body text " * 80),
                                            "source_trail": [f"fulltext:{provider_name}_html_ok"],
                                        },
                                    ),
                                    article=sample_article(),
                                    related_asset_factory=lambda *args, **kwargs: (
                                        related_asset_calls.append(kwargs["asset_profile"]) or {"assets": [], "asset_failures": []}
                                    ),
                                ),
                                "crossref": StubProvider(
                                    metadata={
                                        "provider": "crossref",
                                        "official_provider": False,
                                        "doi": doi,
                                        "title": "Example Article",
                                        "landing_page_url": landing_url,
                                        "authors": ["Alice Example"],
                                        "fulltext_links": [],
                                        "references": [],
                                    }
                                ),
                            },
                        )

                    self.assertIsNotNone(envelope.article)
                    self.assertEqual(related_asset_calls, ["body"])
        finally:
            paper_fetch.resolve_paper = original_resolve

    def test_fetch_paper_explicit_asset_profile_none_disables_scoped_provider_asset_downloads(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1126/science.test",
            query_kind="doi",
            doi="10.1126/science.test",
            landing_url="https://www.science.org/doi/full/10.1126/science.test",
            provider_hint="science",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                envelope = paper_fetch.fetch_paper(
                    resolved.query,
                    modes={"article"},
                    strategy=paper_fetch.FetchStrategy(asset_profile="none"),
                    download_dir=Path(tmpdir),
                    clients={
                        "science": StubProvider(
                            raw_payload=RawFulltextPayload(
                                provider="science",
                                source_url=resolved.landing_url,
                                content_type="text/html",
                                body=b"<html></html>",
                                metadata={
                                    "route": "html",
                                    "markdown_text": "# Example Article\n\n## Results\n\n" + ("Body text " * 80),
                                    "source_trail": ["fulltext:science_html_ok"],
                                },
                            ),
                            article=sample_article(),
                            related_asset_factory=lambda *args, **kwargs: (_ for _ in ()).throw(
                                AssertionError("asset downloads should stay disabled when asset_profile='none'")
                            ),
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": resolved.doi,
                                "title": "Example Article",
                                "landing_page_url": resolved.landing_url,
                                "authors": ["Alice Example"],
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertIn("download:science_assets_skipped_profile_none", envelope.source_trail)

    def test_fetch_paper_warns_when_scoped_provider_falls_back_to_preview_images(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1126/science.preview",
            query_kind="doi",
            doi="10.1126/science.preview",
            landing_url="https://www.science.org/doi/full/10.1126/science.preview",
            provider_hint="science",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                preview_path = Path(tmpdir) / "figure-preview.png"
                preview_path.write_bytes(b"preview")
                envelope = paper_fetch.fetch_paper(
                    resolved.query,
                    modes={"article"},
                    strategy=paper_fetch.FetchStrategy(),
                    download_dir=Path(tmpdir),
                    clients={
                        "science": StubProvider(
                            raw_payload=RawFulltextPayload(
                                provider="science",
                                source_url=resolved.landing_url,
                                content_type="text/html",
                                body=b"<html></html>",
                                metadata={
                                    "route": "html",
                                    "markdown_text": "# Example Article\n\n## Results\n\n" + ("Body text " * 80),
                                    "source_trail": ["fulltext:science_html_ok"],
                                },
                            ),
                            article=sample_article(),
                            related_assets={
                                "assets": [
                                    {
                                        "kind": "figure",
                                        "heading": "Figure 1",
                                        "caption": "Preview figure",
                                        "path": str(preview_path),
                                        "section": "body",
                                        "download_tier": "preview",
                                    }
                                ],
                                "asset_failures": [],
                            },
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": resolved.doi,
                                "title": "Example Article",
                                "landing_page_url": resolved.landing_url,
                                "authors": ["Alice Example"],
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertTrue(any("fell back to preview images" in warning for warning in envelope.warnings))

    def test_fetch_paper_accepts_preview_images_with_sufficient_dimensions(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1126/science.preview.accepted",
            query_kind="doi",
            doi="10.1126/science.preview.accepted",
            landing_url="https://www.science.org/doi/full/10.1126/science.preview.accepted",
            provider_hint="science",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                preview_path = Path(tmpdir) / "figure-preview.png"
                preview_path.write_bytes(b"preview")
                envelope = paper_fetch.fetch_paper(
                    resolved.query,
                    modes={"article"},
                    strategy=paper_fetch.FetchStrategy(),
                    download_dir=Path(tmpdir),
                    clients={
                        "science": StubProvider(
                            raw_payload=RawFulltextPayload(
                                provider="science",
                                source_url=resolved.landing_url,
                                content_type="text/html",
                                body=b"<html></html>",
                                metadata={
                                    "route": "html",
                                    "markdown_text": "# Example Article\n\n## Results\n\n" + ("Body text " * 80),
                                    "source_trail": ["fulltext:science_html_ok"],
                                },
                            ),
                            article=sample_article(),
                            related_assets={
                                "assets": [
                                    {
                                        "kind": "figure",
                                        "heading": "Figure 1",
                                        "caption": "Accepted preview figure",
                                        "path": str(preview_path),
                                        "section": "body",
                                        "download_tier": "preview",
                                        "width": 640,
                                        "height": 480,
                                    }
                                ],
                                "asset_failures": [],
                            },
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": resolved.doi,
                                "title": "Example Article",
                                "landing_page_url": resolved.landing_url,
                                "authors": ["Alice Example"],
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertIn("download:science_assets_preview_accepted", envelope.source_trail)
        self.assertNotIn("download:science_assets_preview_fallback", envelope.source_trail)
        self.assertTrue(any("used preview images" in warning for warning in envelope.warnings))

    def test_probe_has_fulltext_uses_crossref_license_signal(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1000/license",
            query_kind="doi",
            doi="10.1000/license",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            result = paper_fetch.probe_has_fulltext(
                "10.1000/license",
                clients={
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "doi": "10.1000/license",
                            "title": "Licensed Article",
                            "license_urls": ["https://license.example/test"],
                            "fulltext_links": [],
                            "references": [],
                        }
                    )
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(result.state, "likely_yes")
        self.assertEqual(result.doi, "10.1000/license")
        self.assertEqual(result.title, "Licensed Article")
        self.assertEqual(result.evidence, ["crossref_license"])
        self.assertEqual(result.warnings, [])

    def test_probe_has_fulltext_uses_crossref_fulltext_link_signal(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1000/fulltext",
            query_kind="doi",
            doi="10.1000/fulltext",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            result = paper_fetch.probe_has_fulltext(
                "10.1000/fulltext",
                clients={
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "doi": "10.1000/fulltext",
                            "title": "Linked Article",
                            "license_urls": [],
                            "fulltext_links": [{"url": "https://fulltext.example/test.pdf"}],
                            "references": [],
                        }
                    )
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(result.state, "likely_yes")
        self.assertEqual(result.evidence, ["crossref_fulltext_link"])

    def test_probe_has_fulltext_uses_provider_metadata_probe_signal(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            result = paper_fetch.probe_has_fulltext(
                "10.1016/test",
                clients={
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "doi": "10.1016/test",
                            "title": "Crossref Article",
                            "publisher": "Elsevier BV",
                            "landing_page_url": "https://example.test/article",
                            "license_urls": [],
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                    "elsevier": StubProvider(
                        metadata={
                            "provider": "elsevier",
                            "doi": "10.1016/test",
                            "title": "Official Elsevier Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(result.state, "likely_yes")
        self.assertEqual(result.title, "Official Elsevier Article")
        self.assertEqual(result.evidence, ["provider_probe:elsevier"])

    def test_probe_has_fulltext_uses_landing_page_citation_pdf_url_signal(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="https://example.test/article",
            query_kind="url",
            doi=None,
            landing_url="https://example.test/article",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            result = paper_fetch.probe_has_fulltext(
                "https://example.test/article",
                transport=FixtureHtmlTransport(
                    {
                        "https://example.test/article": {
                            "body": (
                                b"<html><head>"
                                b"<meta name='citation_title' content='Landing Page Article' />"
                                b"<meta name='citation_pdf_url' content='https://example.test/article.pdf' />"
                                b"</head><body></body></html>"
                            )
                        }
                    }
                ),
                clients={},
                env={"PAPER_FETCH_SKILL_USER_AGENT": "unit-test"},
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(result.state, "likely_yes")
        self.assertEqual(result.title, "Landing Page Article")
        self.assertEqual(result.evidence, ["landing_page_citation_pdf_url"])

    def test_probe_has_fulltext_uses_crossref_only_for_springer_signals(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1007/test",
            query_kind="doi",
            doi="10.1007/test",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            result = paper_fetch.probe_has_fulltext(
                "10.1007/test",
                transport=FixtureHtmlTransport(
                    {
                        "https://example.test/article": {
                            "headers": {"content-type": "text/html; charset=utf-8"},
                            "body": b"<html><head><title>Example</title></head><body>Example</body></html>",
                        }
                    }
                ),
                clients={
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "doi": "10.1007/test",
                            "title": "Crossref Article",
                            "publisher": "Springer Science and Business Media LLC",
                            "landing_page_url": "https://example.test/article",
                            "license_urls": [],
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                    "springer": StubProvider(
                        metadata=paper_fetch.ProviderFailure("not_supported", "Springer metadata probe should not be used.")
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(result.state, "unknown")
        self.assertEqual(result.evidence, [])
        self.assertEqual(result.warnings, [])

    def test_fetch_paper_model_prefers_raw_xml_pipeline(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            provider_hint="elsevier",
            confidence=1.0,
        )
        official_article = sample_article()
        official_article.source = "elsevier_xml"
        official_article.quality.has_fulltext = True
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1016/test",
                clients={
                    "elsevier": StubProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                            content_type="text/xml",
                            body=b"<xml/>",
                            metadata={"reason": "Downloaded full text from the official Elsevier API."},
                        ),
                        article=official_article,
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "authors": ["Alice Example"],
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "elsevier_xml")
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("fulltext:elsevier_article_ok", article.quality.source_trail)

    def test_fetch_paper_model_emits_service_debug_logs_for_official_provider(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            provider_hint="elsevier",
            confidence=1.0,
        )
        official_article = sample_article()
        original_resolve = paper_fetch.resolve_paper
        service_logger = logging.getLogger("paper_fetch.service")
        original_level = service_logger.level
        handler = RecordCaptureHandler()
        service_logger.addHandler(handler)
        service_logger.setLevel(logging.DEBUG)
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            fetch_paper_model(
                "10.1016/test",
                clients={
                    "elsevier": StubProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                            content_type="text/xml",
                            body=b"<xml/>",
                            metadata={"reason": "Downloaded full text from the official Elsevier API."},
                        ),
                        article=official_article,
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "authors": ["Alice Example"],
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve
            service_logger.removeHandler(handler)
            service_logger.setLevel(original_level)

        rendered_logs = "\n".join(record.getMessage() for record in handler.records)
        self.assertIn("provider=elsevier", rendered_logs)
        self.assertIn("status=success", rendered_logs)
        self.assertIn("elapsed_ms=", rendered_logs)
        payloads = [
            record.structured_data
            for record in handler.records
            if isinstance(getattr(record, "structured_data", None), dict)
        ]
        self.assertIn(
            {
                "event": "official_provider_attempt",
                "provider": "elsevier",
                "url": "https://example.test/article",
                "status": "attempt",
                "elapsed_ms": 0.0,
                "attempt": 1,
            },
            payloads,
        )
        self.assertTrue(
            any(
                payload.get("event") == "official_provider_result"
                and payload.get("provider") == "elsevier"
                and payload.get("status") == "success"
                and isinstance(payload.get("elapsed_ms"), float)
                for payload in payloads
            )
        )

    def test_fetch_paper_model_uses_official_pipeline_for_resolved_elsevier_url(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525",
            query_kind="url",
            doi="10.1016/test",
            landing_url="https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525",
            provider_hint="elsevier",
            confidence=1.0,
            title="Example Article",
        )
        official_article = sample_article()
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                resolved.query,
                clients={
                    "elsevier": StubProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                            content_type="text/xml",
                            body=b"<xml/>",
                            metadata={"reason": "Downloaded full text from the official Elsevier API."},
                        ),
                        article=official_article,
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": resolved.landing_url,
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "elsevier_xml")
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("resolve:url", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_article_ok", article.quality.source_trail)
        self.assertNotIn("fallback:metadata_only", article.quality.source_trail)

    def test_fetch_paper_model_downloads_related_assets_for_official_xml(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        official_article = sample_article()

        def write_related_assets(doi, metadata, raw_payload, output_dir, *, asset_profile="all"):
            asset_dir = output_dir / "10.1016_test_assets"
            asset_dir.mkdir(parents=True, exist_ok=True)
            figure_path = asset_dir / "figure-1.png"
            supplement_path = asset_dir / "supplement.pdf"
            figure_path.write_bytes(b"fake-image")
            supplement_path.write_bytes(b"%PDF-1.7 fake supplement")
            return {
                "assets": [
                    {
                        "asset_type": "image",
                        "path": str(figure_path),
                    },
                    {
                        "asset_type": "supplementary",
                        "path": str(supplement_path),
                    },
                ],
                "asset_failures": [],
            }

        original_resolve = paper_fetch.resolve_paper
        raw_payload = RawFulltextPayload(
            provider="elsevier",
            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
            content_type="text/xml",
            body=b"<xml/>",
            metadata={"reason": "Downloaded full text from the official Elsevier API."},
        )
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1016/test",
                    asset_profile="all",
                    output_dir=Path(tmpdir),
                    clients={
                        "elsevier": StubProvider(
                            metadata={
                                "provider": "elsevier",
                                "official_provider": True,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            },
                            raw_payload=raw_payload,
                            article=official_article,
                            related_asset_factory=write_related_assets,
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
                asset_dir = Path(tmpdir) / "10.1016_test_assets"
                self.assertTrue((asset_dir / "figure-1.png").exists())
                self.assertTrue((asset_dir / "supplement.pdf").exists())
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertIn("download:elsevier_assets_saved_profile_all", article.quality.source_trail)
        self.assertEqual(raw_payload.metadata, {"reason": "Downloaded full text from the official Elsevier API."})

    def test_fetch_paper_model_skips_related_asset_downloads_when_no_download_is_set(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        official_article = sample_article()
        related_asset_calls: list[str] = []

        def write_related_assets(doi, metadata, raw_payload, output_dir, *, asset_profile="all"):
            related_asset_calls.append(doi)
            return {}

        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1016/test",
                    allow_downloads=False,
                    asset_profile="all",
                    output_dir=Path(tmpdir),
                    clients={
                        "elsevier": StubProvider(
                            metadata={
                                "provider": "elsevier",
                                "official_provider": True,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            },
                            raw_payload=RawFulltextPayload(
                                provider="elsevier",
                                source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                                content_type="text/xml",
                                body=b"<xml/>",
                                metadata={"reason": "Downloaded full text from the official Elsevier API."},
                            ),
                            article=official_article,
                            related_asset_factory=write_related_assets,
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(related_asset_calls, [])
        self.assertNotIn("download:elsevier_assets_saved", article.quality.source_trail)

    def test_fetch_paper_model_skips_related_asset_downloads_for_profile_none(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        official_article = sample_article()
        related_asset_calls: list[str] = []

        def write_related_assets(doi, metadata, raw_payload, output_dir, *, asset_profile="all"):
            related_asset_calls.append(asset_profile)
            return {}

        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1016/test",
                    asset_profile="none",
                    output_dir=Path(tmpdir),
                    clients={
                        "elsevier": StubProvider(
                            metadata={
                                "provider": "elsevier",
                                "official_provider": True,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            },
                            raw_payload=RawFulltextPayload(
                                provider="elsevier",
                                source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                                content_type="text/xml",
                                body=b"<xml/>",
                                metadata={"reason": "Downloaded full text from the official Elsevier API."},
                            ),
                            article=official_article,
                            related_asset_factory=write_related_assets,
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(related_asset_calls, [])
        self.assertIn("download:elsevier_assets_skipped_profile_none", article.quality.source_trail)

    def test_fetch_paper_model_treats_request_failure_during_asset_download_as_warning(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1016/test",
                    asset_profile="all",
                    output_dir=Path(tmpdir),
                    clients={
                        "elsevier": StubProvider(
                            metadata={
                                "provider": "elsevier",
                                "official_provider": True,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            },
                            raw_payload=RawFulltextPayload(
                                provider="elsevier",
                                source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                                content_type="text/xml",
                                body=b"<xml/>",
                                metadata={"reason": "Downloaded full text from the official Elsevier API."},
                            ),
                            article=sample_article(),
                            related_asset_error=RequestFailure(503, "HTTP 503 for https://example.test/asset"),
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "elsevier_xml")
        self.assertIn("fulltext:elsevier_article_ok", article.quality.source_trail)
        self.assertIn("download:elsevier_assets_failed", article.quality.source_trail)
        self.assertTrue(any("HTTP 503" in warning for warning in article.quality.warnings))

    def test_fetch_paper_model_treats_oserror_during_asset_download_as_warning(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1016/test",
                    asset_profile="all",
                    output_dir=Path(tmpdir),
                    clients={
                        "elsevier": StubProvider(
                            metadata={
                                "provider": "elsevier",
                                "official_provider": True,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            },
                            raw_payload=RawFulltextPayload(
                                provider="elsevier",
                                source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                                content_type="text/xml",
                                body=b"<xml/>",
                                metadata={"reason": "Downloaded full text from the official Elsevier API."},
                            ),
                            article=sample_article(),
                            related_asset_error=OSError("disk full"),
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "elsevier_xml")
        self.assertIn("fulltext:elsevier_article_ok", article.quality.source_trail)
        self.assertIn("download:elsevier_assets_failed", article.quality.source_trail)
        self.assertTrue(any("disk full" in warning for warning in article.quality.warnings))

    def test_fetch_paper_model_does_not_swallow_programming_errors_during_asset_download(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                with self.assertRaises(AttributeError):
                    fetch_paper_model(
                        "10.1016/test",
                        asset_profile="all",
                        output_dir=Path(tmpdir),
                        clients={
                            "elsevier": StubProvider(
                                metadata={
                                    "provider": "elsevier",
                                    "official_provider": True,
                                    "doi": "10.1016/test",
                                    "title": "Example Article",
                                    "landing_page_url": "https://example.test/article",
                                    "fulltext_links": [],
                                    "references": [],
                                },
                                raw_payload=RawFulltextPayload(
                                    provider="elsevier",
                                    source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                                    content_type="text/xml",
                                    body=b"<xml/>",
                                    metadata={"reason": "Downloaded full text from the official Elsevier API."},
                                ),
                                article=sample_article(),
                                related_asset_error=AttributeError("buggy asset pipeline"),
                            ),
                            "crossref": StubProvider(
                                metadata={
                                    "provider": "crossref",
                                    "official_provider": False,
                                    "doi": "10.1016/test",
                                    "title": "Example Article",
                                    "landing_page_url": "https://example.test/article",
                                    "fulltext_links": [],
                                    "references": [],
                                }
                            ),
                        },
                    )
        finally:
            paper_fetch.resolve_paper = original_resolve

    def test_fetch_metadata_uses_crossref_signal_without_public_crossref_source(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1006/jaer.1996.0085",
            query_kind="doi",
            doi="10.1006/jaer.1996.0085",
            provider_hint=None,
            confidence=1.0,
        )

        metadata, provider_name, source_trail = paper_fetch.fetch_metadata_for_resolved_query(
            resolved,
            clients={
                "elsevier": StubProvider(
                    metadata={
                        "provider": "elsevier",
                        "official_provider": True,
                        "doi": "10.1006/jaer.1996.0085",
                        "title": "Official Elsevier Title",
                        "landing_page_url": "https://api.elsevier.com/content/abstract/scopus_id/0012465826",
                        "authors": ["Alice Example"],
                        "fulltext_links": [],
                        "references": [],
                    }
                ),
                "crossref": StubProvider(
                    metadata={
                        "provider": "crossref",
                        "official_provider": False,
                        "doi": "10.1006/jaer.1996.0085",
                        "title": "Crossref Title",
                        "publisher": "Elsevier BV",
                        "landing_page_url": "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
                        "authors": ["Alice Example"],
                        "fulltext_links": [],
                        "references": [],
                    }
                ),
            },
            strategy=paper_fetch.FetchStrategy(preferred_providers=["elsevier"]),
        )

        self.assertEqual(provider_name, "elsevier")
        self.assertEqual(metadata["title"], "Official Elsevier Title")
        self.assertEqual(metadata["landing_page_url"], "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852")
        self.assertIn("route:crossref_signal_ok", source_trail)
        self.assertIn("route:signal_domain_elsevier", source_trail)
        self.assertIn("route:signal_publisher_elsevier", source_trail)
        self.assertIn("route:probe_elsevier_positive", source_trail)
        self.assertIn("route:provider_selected_elsevier", source_trail)
        self.assertIn("metadata:elsevier_ok", source_trail)
        self.assertNotIn("metadata:crossref_ok", source_trail)

    def test_fetch_metadata_records_unknown_probe_and_uses_crossref_public_metadata(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1007/test",
            query_kind="doi",
            doi="10.1007/test",
            provider_hint="springer",
            confidence=1.0,
        )

        metadata, provider_name, source_trail = paper_fetch.fetch_metadata_for_resolved_query(
            resolved,
            clients={
                "springer": StubProvider(
                    metadata=paper_fetch.ProviderFailure("not_supported", "Springer metadata probe is not supported.")
                ),
                "crossref": StubProvider(
                    metadata={
                        "provider": "crossref",
                        "official_provider": False,
                        "doi": "10.1007/test",
                        "title": "Crossref Fallback",
                        "landing_page_url": "https://example.test/article",
                        "authors": [],
                        "fulltext_links": [],
                        "references": [],
                    }
                ),
            },
            strategy=paper_fetch.FetchStrategy(),
        )

        self.assertEqual(provider_name, "springer")
        self.assertEqual(metadata["title"], "Crossref Fallback")
        self.assertIn("route:probe_springer_unknown", source_trail)
        self.assertIn("route:provider_selected_springer", source_trail)
        self.assertIn("metadata:crossref_ok", source_trail)

    def test_fetch_paper_model_routes_10_1006_doi_to_elsevier_via_crossref_signal(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1006/jaer.1996.0085",
            query_kind="doi",
            doi="10.1006/jaer.1996.0085",
            provider_hint=None,
            confidence=1.0,
        )
        official_article = sample_article()
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = paper_fetch.fetch_paper(
                "10.1006/jaer.1996.0085",
                modes={"article"},
                strategy=paper_fetch.FetchStrategy(
                    preferred_providers=["elsevier"],
                ),
                clients={
                    "elsevier": StubProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1006/jaer.1996.0085",
                            "title": "Official Elsevier Title",
                            "landing_page_url": "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1006%2Fjaer.1996.0085",
                            content_type="text/xml",
                            body=b"<xml/>",
                        ),
                        article=official_article,
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1006/jaer.1996.0085",
                            "title": "Crossref Title",
                            "publisher": "Elsevier BV",
                            "landing_page_url": "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            ).article
        finally:
            paper_fetch.resolve_paper = original_resolve

        assert article is not None
        self.assertEqual(article.source, "elsevier_xml")
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("route:crossref_signal_ok", article.quality.source_trail)
        self.assertIn("route:provider_selected_elsevier", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_article_ok", article.quality.source_trail)
        self.assertNotIn("metadata:crossref_ok", article.quality.source_trail)

    def test_fetch_paper_model_weak_negative_metadata_probe_still_attempts_official_fulltext(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1006/jaer.1996.0085",
            query_kind="doi",
            doi="10.1006/jaer.1996.0085",
            provider_hint=None,
            confidence=1.0,
        )
        official_article = sample_article()
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1006/jaer.1996.0085",
                clients={
                    "elsevier": StubProvider(
                        metadata=paper_fetch.ProviderFailure("no_result", "Elsevier metadata probe missed."),
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1006%2Fjaer.1996.0085",
                            content_type="text/xml",
                            body=b"<xml/>",
                        ),
                        article=official_article,
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1006/jaer.1996.0085",
                            "title": "Crossref Title",
                            "publisher": "Elsevier BV",
                            "landing_page_url": "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "elsevier_xml")
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("route:probe_elsevier_negative", article.quality.source_trail)
        self.assertIn("route:provider_selected_elsevier", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_attempt", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_article_ok", article.quality.source_trail)

    def test_fetch_paper_crossref_only_strategy_skips_official_probes(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            provider_hint="elsevier",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            envelope = paper_fetch.fetch_paper(
                "10.1016/test",
                modes={"article"},
                strategy=paper_fetch.FetchStrategy(
                    preferred_providers=["crossref"],
                ),
                clients={
                    "elsevier": StubProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1016/test",
                            "title": "Official Elsevier Title",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                            content_type="text/xml",
                            body=b"<xml/>",
                        ),
                        article=sample_article(),
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1016/test",
                            "title": "Crossref Title",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        assert envelope.article is not None
        self.assertEqual(envelope.article.source, "crossref_meta")
        self.assertIn("metadata:crossref_ok", envelope.article.quality.source_trail)
        self.assertNotIn("route:probe_elsevier_positive", envelope.article.quality.source_trail)
        self.assertNotIn("fulltext:elsevier_attempt", envelope.article.quality.source_trail)

    def test_fetch_paper_returns_fixed_envelope_shape_with_public_source_mapping(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1111/test",
            query_kind="doi",
            doi="10.1111/test",
            landing_url="https://example.test/wiley",
            provider_hint="wiley",
            confidence=1.0,
        )
        official_article = sample_article()
        official_article.source = "wiley_browser"
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            envelope = paper_fetch.fetch_paper(
                "10.1111/test",
                modes={"markdown"},
                strategy=paper_fetch.FetchStrategy(),
                clients={
                    "wiley": StubProvider(
                        metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                        raw_payload=RawFulltextPayload(
                            provider="wiley",
                            source_url="https://example.test/wiley.pdf",
                            content_type="application/pdf",
                            body=b"%PDF-1.4",
                        ),
                        article=official_article,
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1111/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/wiley",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(
            set(envelope.to_dict().keys()),
            {
                "doi",
                "source",
                "has_fulltext",
                "content_kind",
                "has_abstract",
                "warnings",
                "source_trail",
                "trace",
                "token_estimate",
                "token_estimate_breakdown",
                "quality",
                "article",
                "markdown",
                "metadata",
            },
        )
        self.assertEqual(envelope.source, "wiley_browser")
        self.assertIsNone(envelope.article)
        self.assertIsNone(envelope.metadata)
        self.assertTrue(envelope.markdown)
        self.assertTrue(envelope.has_fulltext)

    def test_fetch_paper_only_populates_envelope_metadata_when_requested(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        official_article = sample_article()
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            without_metadata = paper_fetch.fetch_paper(
                "10.1016/test",
                modes={"article"},
                strategy=paper_fetch.FetchStrategy(),
                clients={
                    "elsevier": StubProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                            content_type="text/xml",
                            body=b"<xml/>",
                        ),
                        article=official_article,
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
            with_metadata = paper_fetch.fetch_paper(
                "10.1016/test",
                modes={"article", "metadata"},
                strategy=paper_fetch.FetchStrategy(),
                clients={
                    "elsevier": StubProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_payload=RawFulltextPayload(
                            provider="elsevier",
                            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                            content_type="text/xml",
                            body=b"<xml/>",
                        ),
                        article=official_article,
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertIsNone(without_metadata.metadata)
        self.assertIsNotNone(with_metadata.metadata)
        self.assertEqual(with_metadata.metadata.title, with_metadata.article.metadata.title)

    def test_fetch_paper_non_provider_landing_page_returns_metadata_only_without_generic_html_attempt(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1000/test",
            query_kind="doi",
            doi="10.1000/test",
            landing_url="https://example.test/article-abstract",
            provider_hint=None,
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1000/test",
                clients={
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1000/test",
                            "title": "Abstract Only Article",
                            "abstract": "Crossref abstract",
                            "landing_page_url": "https://example.test/article-abstract",
                            "fulltext_links": [],
                            "references": [],
                        }
                    )
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertEqual(article.quality.content_kind, "abstract_only")
        self.assertIn("fallback:metadata_only", article.quality.source_trail)
        self.assertNotIn("fallback:html_attempt", article.quality.source_trail)
        self.assertNotIn("fallback:html_abstract_only", article.quality.source_trail)

    def test_fetch_paper_raises_when_metadata_only_fallback_is_disabled(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with self.assertRaises(paper_fetch.PaperFetchFailure):
                paper_fetch.fetch_paper(
                    "10.1016/test",
                    modes={"article"},
                    strategy=paper_fetch.FetchStrategy(
                        allow_metadata_only_fallback=False,
                    ),
                    clients={
                        "elsevier": StubProvider(
                            metadata={
                                "provider": "elsevier",
                                "official_provider": True,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            },
                            raw_error=paper_fetch.ProviderFailure("no_result", "No full text."),
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "abstract": "Fallback abstract",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

    def test_fetch_paper_model_records_rate_limited_fulltext_trail(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1016/test",
                clients={
                    "elsevier": StubProvider(
                        metadata={
                            "provider": "elsevier",
                            "official_provider": True,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "fulltext_links": [],
                            "references": [],
                        },
                        raw_error=paper_fetch.ProviderFailure(
                            "rate_limited",
                            "HTTP 429 for https://api.elsevier.com/content/article/doi/10.1016%2Ftest (Retry-After: 3s)",
                            retry_after_seconds=3,
                        ),
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1016/test",
                            "title": "Example Article",
                            "landing_page_url": "https://example.test/article",
                            "authors": ["Alice Example"],
                            "abstract": "Fallback abstract",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertIn("fulltext:elsevier_rate_limited", article.quality.source_trail)
        self.assertIn("fallback:metadata_only", article.quality.source_trail)
        self.assertTrue(any("Retry-After: 3s" in warning for warning in article.quality.warnings))

    def test_merge_metadata_preserves_explicit_blank_primary_scalar(self) -> None:
        merged = paper_fetch.merge_primary_secondary_metadata(
            {"abstract": "", "title": "Primary Title"},
            {"abstract": "Crossref abstract", "title": "Secondary Title"},
        )

        self.assertIsNone(merged["abstract"])
        self.assertEqual(merged["title"], "Primary Title")

    def test_merge_metadata_dedupes_semantic_author_names(self) -> None:
        merged = paper_fetch.merge_primary_secondary_metadata(
            {"authors": ["Zhang, San", "Alice Example"]},
            {"authors": ["San Zhang", "Alice Example"]},
        )

        self.assertEqual(merged["authors"], ["Zhang, San", "Alice Example"])

    def test_merge_metadata_prefers_public_landing_page_over_api_endpoint(self) -> None:
        merged = paper_fetch.merge_primary_secondary_metadata(
            {"landing_page_url": "https://api.elsevier.com/content/abstract/scopus_id/0012465826"},
            {"landing_page_url": "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852"},
        )

        self.assertEqual(
            merged["landing_page_url"],
            "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
        )

    def test_choose_public_landing_page_url_ignores_elsevier_link_flags_and_scopus_urls(self) -> None:
        selected = choose_public_landing_page_url(
            [
                {
                    "@_fa": "true",
                    "@rel": "self",
                    "@href": "https://api.elsevier.com/content/abstract/scopus_id/0012465826",
                },
                {
                    "@_fa": "true",
                    "@rel": "scopus",
                    "@href": "https://www.scopus.com/inward/record.uri?partnerID=HzOxMe3b&scp=0012465826&origin=inward",
                },
            ],
            "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
        )

        self.assertEqual(selected, "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852")

    def test_wiley_pdf_fallback_is_downloaded_and_extracted_into_fulltext(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1111/test",
            query_kind="doi",
            doi="10.1111/test",
            landing_url="https://example.test/wiley",
            provider_hint="wiley",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1111/test",
                    output_dir=Path(tmpdir),
                    clients={
                        "wiley": StubProvider(
                            metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                            raw_payload=RawFulltextPayload(
                                provider="wiley",
                                source_url="https://example.test/wiley.pdf",
                                content_type="application/pdf",
                                body=fulltext_pdf_bytes(),
                                metadata={
                                    "reason": "Downloaded full text from the Wiley TDM API PDF fallback.",
                                    "route": "pdf_fallback",
                                    "markdown_text": (
                                        "# Wiley PDF Article\n\n## Introduction\n\n"
                                        + ("Introduction text " * 60)
                                        + "\n\n## Methods\n\n"
                                        + ("Methods text " * 60)
                                        + "\n\n## Results\n\n"
                                        + ("Results text " * 60)
                                    ),
                                    "warnings": [
                                        "Full text was extracted from the Wiley TDM API PDF fallback after the HTML path was not usable."
                                    ],
                                    "source_trail": [
                                        "fulltext:wiley_html_fail",
                                        "fulltext:wiley_pdf_api_ok",
                                        "fulltext:wiley_pdf_fallback_ok",
                                    ],
                                },
                                needs_local_copy=True,
                            ),
                            article_factory=WileyClient(HttpTransport(), {}).to_article_model,
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1111/test",
                                "title": "Wiley PDF Article",
                                "landing_page_url": "https://example.test/wiley",
                                "authors": ["Alice Example"],
                                "abstract": "Fallback abstract",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
                downloaded = Path(tmpdir) / "10.1111_test.pdf"
                self.assertTrue(downloaded.exists())
                self.assertTrue(downloaded.read_bytes().startswith(b"%PDF"))
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "wiley_browser")
        self.assertTrue(article.quality.has_fulltext)
        self.assertTrue(any("downloaded as PDF/binary" in warning for warning in article.quality.warnings))
        self.assertTrue(any("PDF fallback" in warning for warning in article.quality.warnings))
        self.assertIn("fulltext:wiley_pdf_api_ok", article.quality.source_trail)
        self.assertIn("fulltext:wiley_pdf_fallback_ok", article.quality.source_trail)
        self.assertIn("download:wiley_saved", article.quality.source_trail)

    def test_wiley_pdf_fallback_markdown_creates_multiple_sections_with_heading_priority(self) -> None:
        article = WileyClient(HttpTransport(), {}).to_article_model(
            {
                "doi": "10.1111/test",
                "title": "Wiley PDF Article",
                "authors": ["Alice Example"],
            },
            RawFulltextPayload(
                provider="wiley",
                source_url="https://example.test/wiley.pdf",
                content_type="application/pdf",
                body=fulltext_pdf_bytes(),
                metadata={
                    "route": "pdf_fallback",
                    "markdown_text": (
                        "# Wiley PDF Article\n\n## Introduction\n\n"
                        + ("Introduction text " * 60)
                        + "\n\n## Methods\n\n"
                        + ("Methods text " * 60)
                        + "\n\n## Results\n\n"
                        + ("Results text " * 60)
                        + "\n\n## Discussion\n\n"
                        + ("Discussion text " * 60)
                    ),
                    "source_trail": ["fulltext:wiley_pdf_api_ok", "fulltext:wiley_pdf_fallback_ok"],
                },
            ),
        )

        headings = [section.heading for section in article.sections]
        self.assertIn("Introduction", headings)
        self.assertIn("Methods", headings)
        self.assertIn("Results", headings)

        truncated_markdown = article.to_ai_markdown(max_tokens=500)
        self.assertIn("## Introduction", truncated_markdown)
        self.assertIn("## Methods", truncated_markdown)
        self.assertNotIn("## Discussion", truncated_markdown)

    def test_binary_downloads_follow_payload_semantics_not_provider_name(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://example.test/article",
            provider_hint="elsevier",
            confidence=1.0,
        )
        official_article = sample_article()
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1016/test",
                    output_dir=Path(tmpdir),
                    clients={
                        "elsevier": StubProvider(
                            metadata={
                                "provider": "elsevier",
                                "official_provider": True,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            },
                            raw_payload=RawFulltextPayload(
                                provider="custompdf",
                                source_url="https://example.test/custom.pdf",
                                content_type="application/pdf",
                                body=fulltext_pdf_bytes(),
                                metadata={"reason": "Downloaded full text from a custom PDF endpoint."},
                                needs_local_copy=True,
                            ),
                            article=official_article,
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1016/test",
                                "title": "Example Article",
                                "landing_page_url": "https://example.test/article",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
                downloaded = Path(tmpdir) / "10.1016_test.pdf"
                self.assertTrue(downloaded.exists())
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertIn("download:custompdf_saved", article.quality.source_trail)
        self.assertNotIn("download:elsevier_saved", article.quality.source_trail)

    def test_wiley_pdf_fallback_can_be_processed_without_download_side_effects(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1111/test",
            query_kind="doi",
            doi="10.1111/test",
            landing_url="https://example.test/wiley",
            provider_hint="wiley",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1111/test",
                    allow_downloads=False,
                    output_dir=Path(tmpdir),
                    clients={
                        "wiley": StubProvider(
                            metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                            raw_payload=RawFulltextPayload(
                                provider="wiley",
                                source_url="https://example.test/wiley.pdf",
                                content_type="application/pdf",
                                body=fulltext_pdf_bytes(),
                                metadata={
                                    "reason": "Downloaded full text from the Wiley TDM API PDF fallback.",
                                    "route": "pdf_fallback",
                                    "markdown_text": (
                                        "# Wiley PDF Article\n\n## Introduction\n\n"
                                        + ("Introduction text " * 60)
                                        + "\n\n## Results\n\n"
                                        + ("Results text " * 60)
                                    ),
                                    "source_trail": [
                                        "fulltext:wiley_html_fail",
                                        "fulltext:wiley_pdf_api_ok",
                                        "fulltext:wiley_pdf_fallback_ok",
                                    ],
                                },
                                needs_local_copy=True,
                            ),
                            article_factory=WileyClient(HttpTransport(), {}).to_article_model,
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1111/test",
                                "title": "Wiley PDF Article",
                                "landing_page_url": "https://example.test/wiley",
                                "authors": ["Alice Example"],
                                "abstract": "Fallback abstract",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
                downloaded = Path(tmpdir) / "10.1111_test.pdf"
                self.assertFalse(downloaded.exists())
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("download:wiley_skipped", article.quality.source_trail)
        self.assertTrue(any("--no-download" in warning for warning in article.quality.warnings))

    def test_wiley_provider_skips_generic_html_fallback_after_provider_failure(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1111/test",
            query_kind="doi",
            doi="10.1111/test",
            landing_url="https://example.test/wiley",
            provider_hint="wiley",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1111/test",
                allow_downloads=False,
                clients={
                    "wiley": StubProvider(
                        metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                        raw_error=paper_fetch.ProviderFailure("no_result", "Browser workflow failed."),
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1111/test",
                            "title": "Wiley PDF Article",
                            "landing_page_url": "https://example.test/wiley",
                            "authors": ["Alice Example"],
                            "abstract": "Fallback abstract",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertFalse(article.quality.has_fulltext)
        self.assertIn("fulltext:wiley_fail", article.quality.source_trail)
        self.assertIn("fallback:wiley_html_managed_by_provider", article.quality.source_trail)
        self.assertIn("fallback:metadata_only", article.quality.source_trail)

    def test_springer_provider_owned_html_downloads_figure_assets_when_enabled(self) -> None:
        landing_url = "https://www.nature.com/articles/example"
        figure_page_url = "https://www.nature.com/articles/example/figures/1"
        preview_image_url = "https://media.springernature.com/lw685/springer-static/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png"
        full_image_url = "https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png"
        preview_bytes = b"preview-image"
        full_bytes = b"full-size-image"
        resolved = paper_fetch.ResolvedQuery(
            query="10.1007/test",
            query_kind="doi",
            doi="10.1007/test",
            landing_url=landing_url,
            provider_hint="springer",
            confidence=1.0,
        )
        transport = FixtureHtmlTransport(
            {
                landing_url: {
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": (
                        b"<html><head>"
                        b'<meta name="citation_title" content="HTML Springer Article" />'
                        b'<meta name="citation_doi" content="10.1007/test" />'
                        b"</head><body>"
                        b'<div class="c-article-section__figure-item">'
                        b'<picture class="c-article-section__figure-picture">'
                        b'<img aria-describedby="figure-1-desc" src="//media.springernature.com/lw685/springer-static/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png" alt="Preview image" />'
                        b"</picture>"
                        b'<div class="c-article-section__figure-link"><a href="/articles/example/figures/1" aria-label="Full size image figure 1">Full size image</a></div>'
                        b"</div>"
                        b'<div class="c-article-section__figure-description" id="figure-1-desc"><p>Figure showing a woodland canopy.</p></div>'
                        b"</body></html>"
                    ),
                },
                figure_page_url: {
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": (
                        b"<html><head>"
                        b'<meta name="twitter:image" content="https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png" />'
                        b"</head><body>"
                        b'<img src="//media.springernature.com/full/springer-static/image/art%3A10.1007%2Ftest/MediaObjects/Fig1.png" />'
                        b"</body></html>"
                    ),
                },
                preview_image_url: {
                    "headers": {"content-type": "image/png"},
                    "body": preview_bytes,
                },
                full_image_url: {
                    "headers": {"content-type": "image/png"},
                    "body": full_bytes,
                },
            }
        )
        original_resolve = paper_fetch.resolve_paper
        original_extract = springer_html_helper.extract_article_markdown
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            springer_html_helper.extract_article_markdown = lambda html, url: "\n".join(
                [
                    "# HTML Springer Article",
                    "",
                    "## Introduction",
                    ("Important body text for HTML fallback. " * 30).strip(),
                    "",
                    "## Results",
                    ("More important body text for HTML fallback. " * 30).strip(),
                    "",
                    "**Figure 1.** Figure showing a woodland canopy.",
                ]
            )
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1007/test",
                    asset_profile="body",
                    output_dir=Path(tmpdir),
                    clients={
                        "springer": paper_fetch.build_clients(transport, {})["springer"],
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1007/test",
                                "title": "HTML Springer Article",
                                "landing_page_url": landing_url,
                                "authors": ["Alice Example"],
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                    transport=transport,
                )
                markdown = article.to_ai_markdown(asset_profile="body")
                self.assertEqual(article.source, "springer_html")
                self.assertTrue(article.quality.has_fulltext)
                self.assertEqual(len(article.assets), 1)
                self.assertEqual(article.assets[0].section, "body")
                self.assertIsNotNone(article.assets[0].path)
                asset_path = Path(article.assets[0].path or "")
                self.assertTrue(asset_path.exists())
                self.assertEqual(asset_path.parent.name, "10.1007_test_assets")
                self.assertEqual(asset_path.read_bytes(), full_bytes)
                self.assertIn("![Figure 1](", markdown)
                self.assertIn(str(asset_path), markdown)
                self.assertNotIn("## Figures", markdown)
        finally:
            paper_fetch.resolve_paper = original_resolve
            springer_html_helper.extract_article_markdown = original_extract

        self.assertIn("fulltext:springer_html_ok", article.quality.source_trail)
        self.assertIn("download:springer_assets_saved_profile_body", article.quality.source_trail)

    def test_wiley_provider_failure_returns_metadata_only_without_generic_html_fallback(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1111/test",
            query_kind="doi",
            doi="10.1111/test",
            landing_url="https://example.test/wiley",
            provider_hint="wiley",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1111/test",
                allow_downloads=False,
                clients={
                    "wiley": StubProvider(
                        metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                        raw_error=paper_fetch.ProviderFailure("no_result", "Browser workflow failed."),
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1111/test",
                            "title": "Wiley PDF Article",
                            "landing_page_url": "https://example.test/wiley",
                            "authors": ["Alice Example"],
                            "abstract": "Fallback abstract",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertFalse(article.quality.has_fulltext)
        self.assertIn("fulltext:wiley_fail", article.quality.source_trail)
        self.assertIn("fallback:wiley_html_managed_by_provider", article.quality.source_trail)
        self.assertIn("fallback:metadata_only", article.quality.source_trail)
        self.assertTrue(any("Full text was not available" in warning for warning in article.quality.warnings))

    def test_science_provider_skips_generic_html_fallback_after_provider_failure(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1126/science.ady3136",
            query_kind="doi",
            doi="10.1126/science.ady3136",
            landing_url="https://www.science.org/doi/full/10.1126/science.ady3136",
            provider_hint="science",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1126/science.ady3136",
                clients={
                    "science": StubProvider(
                        metadata=paper_fetch.ProviderFailure("not_supported", "Science metadata probe is route-only."),
                        raw_error=paper_fetch.ProviderFailure("no_result", "Science provider failed."),
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1126/science.ady3136",
                            "title": "Science Example",
                            "publisher": "American Association for the Advancement of Science",
                            "landing_page_url": resolved.landing_url,
                            "authors": ["Alice Example"],
                            "abstract": "Fallback abstract",
                            "fulltext_links": [],
                            "references": [],
                        }
                    ),
                },
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertFalse(article.quality.has_fulltext)
        self.assertIn("fallback:science_html_managed_by_provider", article.quality.source_trail)
        self.assertIn("fallback:metadata_only", article.quality.source_trail)

    def test_science_provider_public_source_and_html_assets_are_exposed(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1126/science.aeg3511",
            query_kind="doi",
            doi="10.1126/science.aeg3511",
            landing_url="https://www.science.org/doi/full/10.1126/science.aeg3511",
            provider_hint="science",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                asset_path = Path(tmpdir) / "science-figure.png"
                asset_path.write_bytes(b"science-figure")
                envelope = paper_fetch.fetch_paper(
                    "10.1126/science.aeg3511",
                    modes={"article", "markdown"},
                    strategy=paper_fetch.FetchStrategy(asset_profile="body"),
                    download_dir=Path(tmpdir),
                    clients={
                        "science": StubProvider(
                            metadata=paper_fetch.ProviderFailure("not_supported", "Science metadata probe is route-only."),
                            raw_payload=RawFulltextPayload(
                                provider="science",
                                source_url=resolved.landing_url,
                                content_type="text/html",
                                body=b"<html />",
                                metadata={
                                    "route": "html",
                                    "markdown_text": "# Science Example\n\n## Results\n\n" + ("Body text " * 80),
                                    "source_trail": ["fulltext:science_html_ok"],
                                    "warnings": [],
                                },
                            ),
                            article_factory=science_provider.ScienceClient(HttpTransport(), {}).to_article_model,
                            related_assets={
                                "assets": [
                                    {
                                        "kind": "figure",
                                        "heading": "Figure 1",
                                        "caption": "Science figure",
                                        "path": str(asset_path),
                                        "source_url": "https://www.science.org/images/large/figure1.png",
                                        "section": "body",
                                    }
                                ],
                                "asset_failures": [],
                            },
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1126/science.aeg3511",
                                "title": "Science Example",
                                "publisher": "American Association for the Advancement of Science",
                                "landing_page_url": resolved.landing_url,
                                "authors": ["Alice Example"],
                                "abstract": "Fallback abstract",
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(envelope.source, "science")
        self.assertIn("download:science_assets_saved_profile_body", envelope.source_trail)
        self.assertFalse(any("text-only full text" in warning for warning in envelope.warnings))
        assert envelope.article is not None
        self.assertEqual(len(envelope.article.assets), 1)
        self.assertEqual(envelope.article.assets[0].section, "body")
        self.assertEqual(envelope.article.assets[0].path, str(asset_path))

    def test_wiley_provider_public_source_and_html_body_assets_are_exposed(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1111/test",
            query_kind="doi",
            doi="10.1111/test",
            landing_url="https://example.test/wiley",
            provider_hint="wiley",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                asset_path = Path(tmpdir) / "wiley-figure.png"
                asset_path.write_bytes(b"wiley-figure")
                article = fetch_paper_model(
                    "10.1111/test",
                    asset_profile="body",
                    output_dir=Path(tmpdir),
                    clients={
                        "wiley": StubProvider(
                            metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                            raw_payload=RawFulltextPayload(
                                provider="wiley",
                                source_url=resolved.landing_url,
                                content_type="text/html",
                                body=b"<html></html>",
                                metadata={
                                    "route": "html",
                                    "markdown_text": "# Wiley HTML Article\n\n## Results\n\n" + ("Body text " * 80),
                                    "warnings": [],
                                    "source_trail": ["fulltext:wiley_html_ok"],
                                },
                            ),
                            article_factory=WileyClient(HttpTransport(), {}).to_article_model,
                            related_assets={
                                "assets": [
                                    {
                                        "kind": "figure",
                                        "heading": "Figure 1",
                                        "caption": "Wiley figure",
                                        "path": str(asset_path),
                                        "source_url": "https://example.test/wiley/figure1.png",
                                        "section": "body",
                                    }
                                ],
                                "asset_failures": [],
                            },
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1111/test",
                                "title": "Wiley HTML Article",
                                "landing_page_url": resolved.landing_url,
                                "authors": ["Alice Example"],
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "wiley_browser")
        self.assertIn("download:wiley_assets_saved_profile_body", article.quality.source_trail)
        self.assertEqual(len(article.assets), 1)
        self.assertEqual(article.assets[0].section, "body")
        self.assertFalse(any("text-only full text" in warning for warning in article.quality.warnings))

    def test_pnas_provider_public_source_and_html_all_assets_are_exposed(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1073/pnas.test",
            query_kind="doi",
            doi="10.1073/pnas.test",
            landing_url="https://www.pnas.org/doi/10.1073/pnas.test",
            provider_hint="pnas",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                figure_path = Path(tmpdir) / "pnas-figure.png"
                figure_path.write_bytes(b"pnas-figure")
                supplementary_path = Path(tmpdir) / "pnas-supp.pdf"
                supplementary_path.write_bytes(b"%PDF-pnas-supp")
                article = fetch_paper_model(
                    "10.1073/pnas.test",
                    asset_profile="all",
                    output_dir=Path(tmpdir),
                    clients={
                        "pnas": StubProvider(
                            metadata=paper_fetch.ProviderFailure("not_supported", "PNAS metadata probe is route-only."),
                            raw_payload=RawFulltextPayload(
                                provider="pnas",
                                source_url=resolved.landing_url,
                                content_type="text/html",
                                body=b"<html></html>",
                                metadata={
                                    "route": "html",
                                    "markdown_text": "# PNAS HTML Article\n\n## Results\n\n" + ("Body text " * 80),
                                    "warnings": [],
                                    "source_trail": ["fulltext:pnas_html_ok"],
                                },
                            ),
                            article_factory=pnas_provider.PnasClient(HttpTransport(), {}).to_article_model,
                            related_assets={
                                "assets": [
                                    {
                                        "kind": "figure",
                                        "heading": "Figure 1",
                                        "caption": "PNAS figure",
                                        "path": str(figure_path),
                                        "source_url": "https://www.pnas.org/images/figure1.png",
                                        "section": "body",
                                    },
                                    {
                                        "kind": "supplementary",
                                        "heading": "Supplementary Data",
                                        "caption": "PNAS supplementary",
                                        "path": str(supplementary_path),
                                        "source_url": "https://www.pnas.org/supp/s1.pdf",
                                        "section": "supplementary",
                                    },
                                ],
                                "asset_failures": [],
                            },
                        ),
                        "crossref": StubProvider(
                            metadata={
                                "provider": "crossref",
                                "official_provider": False,
                                "doi": "10.1073/pnas.test",
                                "title": "PNAS HTML Article",
                                "landing_page_url": resolved.landing_url,
                                "authors": ["Alice Example"],
                                "fulltext_links": [],
                                "references": [],
                            }
                        ),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "pnas")
        self.assertIn("download:pnas_assets_saved_profile_all", article.quality.source_trail)
        self.assertEqual({asset.kind for asset in article.assets}, {"figure", "supplementary"})
        self.assertFalse(any("text-only full text" in warning for warning in article.quality.warnings))

    def test_browser_workflow_html_final_markdown_prefers_downloaded_local_figure_links(self) -> None:
        cases = [
            {
                "provider_name": "science",
                "doi": "10.1126/science.aeg3511",
                "landing_url": "https://www.science.org/doi/full/10.1126/science.aeg3511",
                "expected_source": "science",
                "asset_profile": "body",
                "title": "Science Example",
                "remote_url": "https://www.science.org/images/large/figure1.png",
                "asset_name": "science-figure.png",
                "article_factory": science_provider.ScienceClient(HttpTransport(), {}).to_article_model,
            },
            {
                "provider_name": "wiley",
                "doi": "10.1111/test",
                "landing_url": "https://example.test/wiley",
                "expected_source": "wiley_browser",
                "asset_profile": "body",
                "title": "Wiley HTML Article",
                "remote_url": "https://example.test/wiley/figure1.png",
                "asset_name": "wiley-figure.png",
                "article_factory": WileyClient(HttpTransport(), {}).to_article_model,
            },
            {
                "provider_name": "pnas",
                "doi": "10.1073/pnas.test",
                "landing_url": "https://www.pnas.org/doi/10.1073/pnas.test",
                "expected_source": "pnas",
                "asset_profile": "all",
                "title": "PNAS HTML Article",
                "remote_url": "https://www.pnas.org/images/figure1.png",
                "asset_name": "pnas-figure.png",
                "article_factory": pnas_provider.PnasClient(HttpTransport(), {}).to_article_model,
            },
        ]
        original_resolve = paper_fetch.resolve_paper
        try:
            for case in cases:
                with self.subTest(provider=case["provider_name"]):
                    resolved = paper_fetch.ResolvedQuery(
                        query=case["doi"],
                        query_kind="doi",
                        doi=case["doi"],
                        landing_url=case["landing_url"],
                        provider_hint=case["provider_name"],
                        confidence=1.0,
                    )
                    paper_fetch.resolve_paper = lambda *args, _resolved=resolved, **kwargs: _resolved
                    with tempfile.TemporaryDirectory() as tmpdir:
                        asset_path = Path(tmpdir) / case["asset_name"]
                        asset_path.write_bytes(f"{case['provider_name']}-figure".encode("utf-8"))
                        envelope = paper_fetch.fetch_paper(
                            case["doi"],
                            modes={"article", "markdown"},
                            strategy=paper_fetch.FetchStrategy(asset_profile=case["asset_profile"]),
                            download_dir=Path(tmpdir),
                            clients={
                                case["provider_name"]: StubProvider(
                                    metadata=paper_fetch.ProviderFailure(
                                        "not_supported",
                                        "Browser-workflow provider metadata is route-only.",
                                    ),
                                    raw_payload=RawFulltextPayload(
                                        provider=case["provider_name"],
                                        source_url=case["landing_url"],
                                        content_type="text/html",
                                        body=b"<html></html>",
                                        metadata={
                                            "route": "html",
                                            "markdown_text": "\n\n".join(
                                                [
                                                    f"# {case['title']}",
                                                    "## Results",
                                                    ("Body text " * 80).strip(),
                                                    f"![Figure 1]({case['remote_url']})",
                                                    "**Figure 1.** Caption body for the browser HTML figure.",
                                                ]
                                            ),
                                            "warnings": [],
                                            "source_trail": [f"fulltext:{case['provider_name']}_html_ok"],
                                        },
                                    ),
                                    article_factory=case["article_factory"],
                                    related_assets={
                                        "assets": [
                                            {
                                                "kind": "figure",
                                                "heading": "Figure 1",
                                                "caption": "Caption body for the browser HTML figure.",
                                                "path": str(asset_path),
                                                "source_url": case["remote_url"],
                                                "section": "body",
                                            }
                                        ],
                                        "asset_failures": [],
                                    },
                                ),
                                "crossref": StubProvider(
                                    metadata={
                                        "provider": "crossref",
                                        "official_provider": False,
                                        "doi": case["doi"],
                                        "title": case["title"],
                                        "landing_page_url": case["landing_url"],
                                        "authors": ["Alice Example"],
                                        "fulltext_links": [],
                                        "references": [],
                                    }
                                ),
                            },
                        )

                    self.assertEqual(envelope.source, case["expected_source"])
                    assert envelope.article is not None
                    assert envelope.markdown is not None
                    self.assertEqual(envelope.article.assets[0].path, str(asset_path))
                    self.assertIn(f"![Figure 1]({asset_path})", envelope.markdown)
                    self.assertNotIn(f"![Figure 1]({case['remote_url']})", envelope.markdown)
        finally:
            paper_fetch.resolve_paper = original_resolve

    def test_browser_workflow_pdf_fallback_routes_still_skip_asset_downloads(self) -> None:
        cases = [
            ("wiley", "10.1111/test", "https://example.test/wiley", WileyClient(HttpTransport(), {}).to_article_model, "wiley_browser"),
            ("science", "10.1126/science.test", "https://www.science.org/doi/full/10.1126/science.test", science_provider.ScienceClient(HttpTransport(), {}).to_article_model, "science"),
            ("pnas", "10.1073/pnas.test", "https://www.pnas.org/doi/10.1073/pnas.test", pnas_provider.PnasClient(HttpTransport(), {}).to_article_model, "pnas"),
        ]
        original_resolve = paper_fetch.resolve_paper
        try:
            for provider_name, doi, landing_url, article_factory, expected_source in cases:
                with self.subTest(provider=provider_name):
                    resolved = paper_fetch.ResolvedQuery(
                        query=doi,
                        query_kind="doi",
                        doi=doi,
                        landing_url=landing_url,
                        provider_hint=provider_name,
                        confidence=1.0,
                    )
                    paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
                    with tempfile.TemporaryDirectory() as tmpdir:
                        article = fetch_paper_model(
                            doi,
                            asset_profile="body",
                            output_dir=Path(tmpdir),
                            clients={
                                provider_name: StubProvider(
                                    metadata=paper_fetch.ProviderFailure("not_supported", "Route-only provider metadata."),
                                    raw_payload=RawFulltextPayload(
                                        provider=provider_name,
                                        source_url=f"{landing_url}.pdf",
                                        content_type="application/pdf",
                                        body=fulltext_pdf_bytes(),
                                        metadata={
                                            "route": "pdf_fallback",
                                            "markdown_text": f"# {provider_name.title()} PDF Article\n\n## Results\n\n" + ("Body text " * 80),
                                            "warnings": [
                                                "Full text was extracted from PDF fallback after the HTML path was not usable."
                                            ],
                                            "source_trail": [
                                                f"fulltext:{provider_name}_html_fail",
                                                f"fulltext:{provider_name}_pdf_fallback_ok",
                                            ],
                                        },
                                        needs_local_copy=True,
                                    ),
                                    article_factory=article_factory,
                                    related_asset_factory=lambda *args, **kwargs: (_ for _ in ()).throw(
                                        AssertionError("PDF fallback routes should not attempt asset downloads.")
                                    ),
                                ),
                                "crossref": StubProvider(
                                    metadata={
                                        "provider": "crossref",
                                        "official_provider": False,
                                        "doi": doi,
                                        "title": f"{provider_name.title()} PDF Article",
                                        "landing_page_url": landing_url,
                                        "authors": ["Alice Example"],
                                        "fulltext_links": [],
                                        "references": [],
                                    }
                                ),
                            },
                        )

                    self.assertEqual(article.source, expected_source)
                    self.assertIn(f"download:{provider_name}_assets_skipped_text_only", article.quality.source_trail)
                    self.assertTrue(any("text-only full text" in warning for warning in article.quality.warnings))
        finally:
            paper_fetch.resolve_paper = original_resolve
