# ruff: noqa: F403,F405
from __future__ import annotations

from ._service_support import *


class ServiceOfficialPipelineTests(unittest.TestCase):
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

    def test_fetch_paper_model_emits_service_debug_logs_for_official_provider(
        self,
    ) -> None:
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

    def test_fetch_paper_model_uses_official_pipeline_for_resolved_elsevier_url(
        self,
    ) -> None:
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

    def test_fetch_paper_model_uses_elsevier_pii_metadata_for_url_without_doi(
        self,
    ) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="https://www.sciencedirect.com/science/article/pii/S0959378017300134",
            query_kind="url",
            landing_url="https://www.sciencedirect.com/science/article/pii/S0959378017300134",
            provider_hint="elsevier",
            confidence=1.0,
            provider_identifiers={"pii": "S0959378017300134"},
        )

        class PiiAwareProvider(StubProvider):
            def __init__(self):
                super().__init__(
                    raw_payload=RawFulltextPayload(
                        provider="elsevier",
                        source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                        content_type="text/xml",
                        body=b"<xml/>",
                    ),
                    article=sample_article(),
                )
                self.metadata_queries = []

            def fetch_metadata(self, query):
                self.metadata_queries.append(dict(query))
                return {
                    "provider": "elsevier",
                    "official_provider": True,
                    "doi": "10.1016/test",
                    "pii": "S0959378017300134",
                    "title": "Example Article",
                    "landing_page_url": resolved.landing_url,
                    "fulltext_links": [],
                    "references": [],
                }

        provider = PiiAwareProvider()
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(resolved.query, clients={"elsevier": provider})
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(
            provider.metadata_queries, [{"doi": None, "pii": "S0959378017300134"}]
        )
        self.assertEqual(article.source, "elsevier_xml")
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("metadata:elsevier_ok", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_article_ok", article.quality.source_trail)

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

        def write_related_assets(
            doi, metadata, raw_payload, output_dir, *, asset_profile="all"
        ):
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
        raw_payload = _typed_payload(
            provider="elsevier",
            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
            content_type="text/xml",
            body=b"<xml/>",
            route_kind="official",
            reason="Downloaded full text from the official Elsevier API.",
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

        self.assertIn(
            "download:elsevier_assets_saved_profile_all", article.quality.source_trail
        )
        self.assertIsNotNone(raw_payload.content)
        assert raw_payload.content is not None
        self.assertEqual(raw_payload.content.route_kind, "official")
        self.assertEqual(
            raw_payload.content.reason,
            "Downloaded full text from the official Elsevier API.",
        )

    def test_fetch_paper_model_skips_related_asset_downloads_when_no_download_is_set(
        self,
    ) -> None:
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

        def write_related_assets(
            doi, metadata, raw_payload, output_dir, *, asset_profile="all"
        ):
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

    def test_fetch_paper_model_skips_related_asset_downloads_for_profile_none(
        self,
    ) -> None:
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

        def write_related_assets(
            doi, metadata, raw_payload, output_dir, *, asset_profile="all"
        ):
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
        self.assertIn(
            "download:elsevier_assets_skipped_profile_none",
            article.quality.source_trail,
        )

    def test_fetch_paper_model_treats_request_failure_during_asset_download_as_warning(
        self,
    ) -> None:
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
                            ),
                            article=sample_article(),
                            related_asset_error=RequestFailure(
                                503, "HTTP 503 for https://example.test/asset"
                            ),
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
        self.assertTrue(
            any("HTTP 503" in warning for warning in article.quality.warnings)
        )

    def test_fetch_paper_model_treats_oserror_during_asset_download_as_warning(
        self,
    ) -> None:
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
        self.assertTrue(
            any("disk full" in warning for warning in article.quality.warnings)
        )

    def test_fetch_paper_model_does_not_swallow_programming_errors_during_asset_download(
        self,
    ) -> None:
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
                                ),
                                article=sample_article(),
                                related_asset_error=AttributeError(
                                    "buggy asset pipeline"
                                ),
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
