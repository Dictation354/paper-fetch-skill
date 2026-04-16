from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path

from paper_fetch import service as paper_fetch
from paper_fetch.http import HttpTransport, RequestFailure
from paper_fetch.providers import html_generic
from paper_fetch.providers.base import RawFulltextPayload
from paper_fetch.providers.wiley import WileyClient
from paper_fetch.utils import choose_public_landing_page_url

from ._paper_fetch_support import (
    FixtureHtmlTransport,
    StubHtmlClient,
    StubProvider,
    fetch_paper_model,
    fulltext_pdf_bytes,
    sample_article,
    sample_html_article,
    short_pdf_bytes,
)


class RecordCaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class ServiceTests(unittest.TestCase):
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
                html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
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
                html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
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
                html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
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
                    html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
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
                    html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
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
                    html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
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
                    html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
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
                    html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
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
                        html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
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
                    allow_html_fallback=False,
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
                html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
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
                allow_html_fallback=False,
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
                html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
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
                    allow_html_fallback=False,
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
                html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
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
                "warnings",
                "source_trail",
                "token_estimate",
                "token_estimate_breakdown",
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
                        allow_html_fallback=False,
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
                    html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
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
                allow_html_fallback=False,
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
                html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
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
                                    "reason": "Downloaded full text from the Wiley browser workflow PDF fallback.",
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
                                        "Full text was extracted from PDF fallback after the HTML path was not usable."
                                    ],
                                    "source_trail": [
                                        "fulltext:wiley_html_fail",
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
                    html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
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
                    "source_trail": ["fulltext:wiley_pdf_fallback_ok"],
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
                    html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
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
                                    "reason": "Downloaded full text from the Wiley browser workflow PDF fallback.",
                                    "route": "pdf_fallback",
                                    "markdown_text": (
                                        "# Wiley PDF Article\n\n## Introduction\n\n"
                                        + ("Introduction text " * 60)
                                        + "\n\n## Results\n\n"
                                        + ("Results text " * 60)
                                    ),
                                    "source_trail": [
                                        "fulltext:wiley_html_fail",
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
                    html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
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
                html_client=StubHtmlClient(article=sample_html_article()),
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
        original_extract = html_generic.extract_article_markdown
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            html_generic.extract_article_markdown = lambda html, url: "\n".join(
                [
                    "# HTML Springer Article",
                    "",
                    "## Introduction",
                    ("Important body text for HTML fallback. " * 30).strip(),
                    "",
                    "## Results",
                    ("More important body text for HTML fallback. " * 30).strip(),
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
                self.assertIn("![Figure showing a woodland canopy.]", markdown)
                self.assertIn(str(asset_path), markdown)
        finally:
            paper_fetch.resolve_paper = original_resolve
            html_generic.extract_article_markdown = original_extract

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
                allow_html_fallback=False,
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
                html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
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
                html_client=StubHtmlClient(article=sample_html_article()),
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertFalse(article.quality.has_fulltext)
        self.assertIn("fallback:science_html_managed_by_provider", article.quality.source_trail)
        self.assertIn("fallback:metadata_only", article.quality.source_trail)

    def test_science_provider_public_source_and_asset_profile_downgrade_are_exposed(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1126/science.aeg3511",
            query_kind="doi",
            doi="10.1126/science.aeg3511",
            landing_url="https://www.science.org/doi/full/10.1126/science.aeg3511",
            provider_hint="science",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper

        def science_article_factory(metadata, raw_payload, *, downloaded_assets=None, asset_failures=None):
            article = sample_article()
            article.doi = "10.1126/science.aeg3511"
            article.source = "science"
            article.metadata.title = "Science Example"
            article.quality.source_trail = list(raw_payload.metadata.get("source_trail") or [])
            article.quality.warnings = list(raw_payload.metadata.get("warnings") or [])
            return article

        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            envelope = paper_fetch.fetch_paper(
                "10.1126/science.aeg3511",
                modes={"article", "markdown"},
                strategy=paper_fetch.FetchStrategy(asset_profile="body"),
                clients={
                    "science": StubProvider(
                        metadata=paper_fetch.ProviderFailure("not_supported", "Science metadata probe is route-only."),
                        raw_payload=RawFulltextPayload(
                            provider="science",
                            source_url=resolved.landing_url,
                            content_type="text/html",
                            body=b"<html />",
                            metadata={
                                "source_trail": ["fulltext:science_html_ok"],
                                "warnings": [],
                            },
                        ),
                        article_factory=science_article_factory,
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
                html_client=StubHtmlClient(error=paper_fetch.ProviderFailure("no_result", "HTML should not be used.")),
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(envelope.source, "science")
        self.assertIn("download:science_assets_skipped_text_only", envelope.source_trail)
        self.assertTrue(any("text-only full text" in warning for warning in envelope.warnings))
