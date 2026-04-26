from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch import service as paper_fetch
from paper_fetch.providers import elsevier as elsevier_provider
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.tracing import trace_from_markers

from ._paper_fetch_support import StubProvider, fetch_paper_model, fulltext_pdf_bytes, sample_article, sample_html_article


def _article_factory_with_source(source: str):
    def factory(metadata, raw_payload, *, downloaded_assets=None, asset_failures=None):
        article = sample_article()
        article.source = source
        article.doi = str(metadata.get("doi") or article.doi)
        article.metadata.title = str(metadata.get("title") or article.metadata.title)
        article.quality.source_trail = list(raw_payload.metadata.get("source_trail") or [])
        article.quality.warnings = list(raw_payload.metadata.get("warnings") or [])
        return article

    return factory


def _abstract_only_article_factory(source: str):
    def factory(metadata, raw_payload, *, downloaded_assets=None, asset_failures=None):
        article = sample_html_article()
        article.source = source
        article.doi = str(metadata.get("doi") or article.doi)
        article.metadata.title = str(metadata.get("title") or article.metadata.title)
        article.metadata.abstract = "Provider abstract only."
        article.sections = []
        article.quality.content_kind = "abstract_only"
        article.quality.has_fulltext = False
        article.quality.has_abstract = True
        article.quality.source_trail = list(raw_payload.metadata.get("source_trail") or [])
        article.quality.trace = trace_from_markers(article.quality.source_trail)
        article.quality.warnings = list(raw_payload.metadata.get("warnings") or [])
        return article

    return factory


def _metadata_only_article_factory(source: str):
    def factory(metadata, raw_payload, *, downloaded_assets=None, asset_failures=None):
        article = sample_html_article()
        article.source = source
        article.doi = str(metadata.get("doi") or article.doi)
        article.metadata.title = str(metadata.get("title") or article.metadata.title)
        article.metadata.abstract = None
        article.sections = []
        article.quality.content_kind = "metadata_only"
        article.quality.has_fulltext = False
        article.quality.has_abstract = False
        article.quality.source_trail = list(raw_payload.metadata.get("source_trail") or [])
        article.quality.trace = trace_from_markers(article.quality.source_trail)
        article.quality.warnings = list(raw_payload.metadata.get("warnings") or [])
        return article

    return factory


class ProviderManagedFallbackServiceTests(unittest.TestCase):
    def test_elsevier_provider_failure_skips_generic_html_fallback(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test",
            query_kind="doi",
            doi="10.1016/test",
            landing_url="https://www.sciencedirect.com/science/article/pii/S0034425725000525",
            provider_hint="elsevier",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1016/test",
                allow_downloads=False,
                clients={
                    "elsevier": StubProvider(
                        metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                        raw_error=paper_fetch.ProviderFailure("no_result", "Elsevier provider failed."),
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1016/test",
                            "title": "Elsevier Metadata",
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
        self.assertIn("fallback:elsevier_html_managed_by_provider", article.quality.source_trail)
        self.assertNotIn("fallback:html_ok", article.quality.source_trail)

    def test_elsevier_xml_unusable_then_pdf_success_returns_fulltext_without_generic_html_fallback(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test-pdf-success",
            query_kind="doi",
            doi="10.1016/test-pdf-success",
            landing_url="https://www.sciencedirect.com/science/article/pii/S0034425725000525",
            provider_hint="elsevier",
            confidence=1.0,
        )
        metadata = {
            "provider": "crossref",
            "official_provider": False,
            "doi": "10.1016/test-pdf-success",
            "title": "Elsevier Metadata",
            "landing_page_url": resolved.landing_url,
            "authors": ["Alice Example"],
            "abstract": "Fallback abstract",
            "fulltext_links": [],
            "references": [],
        }
        xml_payload = RawFulltextPayload(
            provider="elsevier",
            source_url="https://api.elsevier.com/content/article/doi/example",
            content_type="text/xml",
            body=b"<xml />",
            content=ProviderContent(
                route_kind="official",
                source_url="https://api.elsevier.com/content/article/doi/example",
                content_type="text/xml",
                body=b"<xml />",
                reason="Downloaded full text from the official Elsevier API.",
            ),
        )
        pdf_payload = RawFulltextPayload(
            provider="elsevier",
            source_url="https://api.elsevier.com/content/article/doi/example.pdf",
            content_type="application/pdf",
            body=fulltext_pdf_bytes(),
            content=ProviderContent(
                route_kind="pdf_fallback",
                source_url="https://api.elsevier.com/content/article/doi/example.pdf",
                content_type="application/pdf",
                body=fulltext_pdf_bytes(),
                reason="Downloaded full text from the official Elsevier API PDF fallback.",
                markdown_text="# Elsevier PDF Article\n\n## Results\n\n" + ("Body text " * 80),
            ),
            needs_local_copy=True,
        )
        client = elsevier_provider.ElsevierClient(transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"})
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with (
                mock.patch.object(
                    client,
                    "fetch_metadata",
                    return_value={
                        "provider": "elsevier",
                        "official_provider": True,
                        "doi": resolved.doi,
                        "title": "Elsevier Metadata",
                        "landing_page_url": resolved.landing_url,
                        "publisher": "Elsevier",
                        "fulltext_links": [],
                        "references": [],
                    },
                ),
                mock.patch.object(client, "_fetch_official_xml_payload", return_value=xml_payload),
                mock.patch.object(client, "_official_payload_is_usable", return_value=False),
                mock.patch.object(client, "_fetch_official_pdf_payload", return_value=pdf_payload),
            ):
                article = fetch_paper_model(
                    "10.1016/test-pdf-success",
                    allow_downloads=False,
                    clients={
                        "elsevier": client,
                        "crossref": StubProvider(metadata=metadata),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "elsevier_pdf")
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("fulltext:elsevier_xml_fail", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_pdf_api_ok", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_pdf_fallback_ok", article.quality.source_trail)
        self.assertNotIn("fallback:html_ok", article.quality.source_trail)
        self.assertNotIn("fulltext:elsevier_html_fail", article.quality.source_trail)

    def test_elsevier_xml_and_pdf_failures_return_metadata_only_without_generic_html_fallback(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test-pdf-fail",
            query_kind="doi",
            doi="10.1016/test-pdf-fail",
            landing_url="https://www.sciencedirect.com/science/article/pii/S0034425725000525",
            provider_hint="elsevier",
            confidence=1.0,
        )
        metadata = {
            "provider": "crossref",
            "official_provider": False,
            "doi": "10.1016/test-pdf-fail",
            "title": "Elsevier Metadata",
            "landing_page_url": resolved.landing_url,
            "authors": ["Alice Example"],
            "abstract": "Fallback abstract",
            "fulltext_links": [],
            "references": [],
        }
        xml_payload = RawFulltextPayload(
            provider="elsevier",
            source_url="https://api.elsevier.com/content/article/doi/example",
            content_type="text/xml",
            body=b"<xml />",
            content=ProviderContent(
                route_kind="official",
                source_url="https://api.elsevier.com/content/article/doi/example",
                content_type="text/xml",
                body=b"<xml />",
                reason="Downloaded full text from the official Elsevier API.",
            ),
        )
        client = elsevier_provider.ElsevierClient(transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"})
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with (
                mock.patch.object(
                    client,
                    "fetch_metadata",
                    return_value={
                        "provider": "elsevier",
                        "official_provider": True,
                        "doi": resolved.doi,
                        "title": "Elsevier Metadata",
                        "landing_page_url": resolved.landing_url,
                        "publisher": "Elsevier",
                        "fulltext_links": [],
                        "references": [],
                    },
                ),
                mock.patch.object(client, "_fetch_official_xml_payload", return_value=xml_payload),
                mock.patch.object(client, "_official_payload_is_usable", return_value=False),
                mock.patch.object(
                    client,
                    "_fetch_official_pdf_payload",
                    side_effect=paper_fetch.ProviderFailure(
                        "no_result",
                        "Elsevier official PDF representation is not available.",
                    ),
                ),
            ):
                article = fetch_paper_model(
                    "10.1016/test-pdf-fail",
                    allow_downloads=False,
                    clients={
                        "elsevier": client,
                        "crossref": StubProvider(metadata=metadata),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertFalse(article.quality.has_fulltext)
        self.assertIn("fulltext:elsevier_xml_fail", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_pdf_api_fail", article.quality.source_trail)
        self.assertIn("fallback:elsevier_html_managed_by_provider", article.quality.source_trail)
        self.assertIn("fallback:metadata_only", article.quality.source_trail)
        self.assertNotIn("fallback:html_ok", article.quality.source_trail)
        self.assertNotIn("fulltext:elsevier_html_fail", article.quality.source_trail)

    def test_springer_provider_failure_skips_generic_html_fallback(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1038/test",
            query_kind="doi",
            doi="10.1038/test",
            landing_url="https://www.nature.com/articles/test",
            provider_hint="springer",
            confidence=1.0,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            article = fetch_paper_model(
                "10.1038/test",
                allow_downloads=False,
                clients={
                    "springer": StubProvider(
                        metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                        raw_error=paper_fetch.ProviderFailure("no_result", "Springer provider failed."),
                    ),
                    "crossref": StubProvider(
                        metadata={
                            "provider": "crossref",
                            "official_provider": False,
                            "doi": "10.1038/test",
                            "title": "Nature Metadata",
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
        self.assertIn("fallback:springer_html_managed_by_provider", article.quality.source_trail)
        self.assertNotIn("fallback:html_ok", article.quality.source_trail)

    def test_provider_managed_abstract_only_results_return_provider_article_directly(self) -> None:
        provider_cases = {
            "springer": ("springer_html", "10.1038/test-abstract", "https://www.nature.com/articles/test-abstract"),
            "wiley": ("wiley_browser", "10.1111/test-abstract", "https://onlinelibrary.wiley.com/doi/full/10.1111/test-abstract"),
            "science": ("science", "10.1126/science.test-abstract", "https://www.science.org/doi/full/10.1126/science.test-abstract"),
            "pnas": ("pnas", "10.1073/pnas.test-abstract", "https://www.pnas.org/doi/full/10.1073/pnas.test-abstract"),
        }

        for provider_name, (source_name, doi, landing_url) in provider_cases.items():
            with self.subTest(provider=provider_name):
                resolved = paper_fetch.ResolvedQuery(
                    query=doi,
                    query_kind="doi",
                    doi=doi,
                    landing_url=landing_url,
                    provider_hint=provider_name,
                    confidence=1.0,
                )
                metadata = {
                    "provider": "crossref",
                    "official_provider": False,
                    "doi": resolved.doi,
                    "title": f"{provider_name.title()} Metadata",
                    "landing_page_url": resolved.landing_url,
                    "authors": ["Alice Example"],
                    "abstract": "Crossref abstract",
                    "fulltext_links": [],
                    "references": [],
                }
                raw_payload = RawFulltextPayload(
                    provider=provider_name,
                    source_url=resolved.landing_url,
                    content_type="text/html",
                    body=b"<html></html>",
                    content=ProviderContent(
                        route_kind="html",
                        source_url=resolved.landing_url,
                        content_type="text/html",
                        body=b"<html></html>",
                    ),
                    warnings=["Provider abstract-only warning."],
                    trace=trace_from_markers([f"fulltext:{provider_name}_abstract_only"]),
                )
                original_resolve = paper_fetch.resolve_paper
                try:
                    paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
                    article = fetch_paper_model(
                        resolved.doi or "",
                        allow_downloads=False,
                        clients={
                            provider_name: StubProvider(
                                metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                                raw_payload=raw_payload,
                                article_factory=_abstract_only_article_factory(source_name),
                            ),
                            "crossref": StubProvider(metadata=metadata),
                        },
                    )
                finally:
                    paper_fetch.resolve_paper = original_resolve

                self.assertEqual(article.source, source_name)
                self.assertEqual(article.quality.content_kind, "abstract_only")
                self.assertIn(f"fulltext:{provider_name}_abstract_only", article.quality.source_trail)
                self.assertNotIn("fallback:metadata_only", article.quality.source_trail)
                self.assertNotIn(f"fallback:{provider_name}_html_managed_by_provider", article.quality.source_trail)

    def test_provider_managed_metadata_only_results_still_fall_back_to_crossref_metadata(self) -> None:
        provider_cases = {
            "springer": ("springer_html", "10.1038/test-metadata", "https://www.nature.com/articles/test-metadata"),
            "wiley": ("wiley_browser", "10.1111/test-metadata", "https://onlinelibrary.wiley.com/doi/full/10.1111/test-metadata"),
            "science": ("science", "10.1126/science.test-metadata", "https://www.science.org/doi/full/10.1126/science.test-metadata"),
            "pnas": ("pnas", "10.1073/pnas.test-metadata", "https://www.pnas.org/doi/full/10.1073/pnas.test-metadata"),
        }

        for provider_name, (source_name, doi, landing_url) in provider_cases.items():
            with self.subTest(provider=provider_name):
                resolved = paper_fetch.ResolvedQuery(
                    query=doi,
                    query_kind="doi",
                    doi=doi,
                    landing_url=landing_url,
                    provider_hint=provider_name,
                    confidence=1.0,
                )
                metadata = {
                    "provider": "crossref",
                    "official_provider": False,
                    "doi": resolved.doi,
                    "title": f"{provider_name.title()} Metadata",
                    "landing_page_url": resolved.landing_url,
                    "authors": ["Alice Example"],
                    "abstract": "Crossref abstract",
                    "fulltext_links": [],
                    "references": [],
                }
                raw_payload = RawFulltextPayload(
                    provider=provider_name,
                    source_url=resolved.landing_url,
                    content_type="text/html",
                    body=b"<html></html>",
                    content=ProviderContent(
                        route_kind="html",
                        source_url=resolved.landing_url,
                        content_type="text/html",
                        body=b"<html></html>",
                    ),
                    warnings=["Provider metadata-only warning."],
                    trace=trace_from_markers([f"fulltext:{provider_name}_html_fail"]),
                )
                original_resolve = paper_fetch.resolve_paper
                try:
                    paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
                    article = fetch_paper_model(
                        resolved.doi or "",
                        allow_downloads=False,
                        clients={
                            provider_name: StubProvider(
                                metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                                raw_payload=raw_payload,
                                article_factory=_metadata_only_article_factory(source_name),
                            ),
                            "crossref": StubProvider(metadata=metadata),
                        },
                    )
                finally:
                    paper_fetch.resolve_paper = original_resolve

                self.assertEqual(article.source, "crossref_meta")
                self.assertEqual(article.quality.content_kind, "abstract_only")
                self.assertIn(f"fallback:{provider_name}_html_managed_by_provider", article.quality.source_trail)
                self.assertIn("fallback:metadata_only", article.quality.source_trail)

    def test_elsevier_pdf_route_skips_asset_downloads_with_warning(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test-pdf-assets",
            query_kind="doi",
            doi="10.1016/test-pdf-assets",
            landing_url="https://www.sciencedirect.com/science/article/pii/S0034425725000525",
            provider_hint="elsevier",
            confidence=1.0,
        )
        metadata = {
            "provider": "crossref",
            "official_provider": False,
            "doi": "10.1016/test-pdf-assets",
            "title": "Elsevier PDF Article",
            "landing_page_url": resolved.landing_url,
            "authors": ["Alice Example"],
            "fulltext_links": [],
            "references": [],
        }
        raw_payload = RawFulltextPayload(
            provider="elsevier",
            source_url=f"{resolved.landing_url}.pdf",
            content_type="application/pdf",
            body=fulltext_pdf_bytes(),
            content=ProviderContent(
                route_kind="pdf_fallback",
                source_url=f"{resolved.landing_url}.pdf",
                content_type="application/pdf",
                body=fulltext_pdf_bytes(),
                markdown_text="# Elsevier PDF Article\n\n## Results\n\n" + ("Body text " * 80),
            ),
            trace=trace_from_markers(
                [
                    "fulltext:elsevier_xml_fail",
                    "fulltext:elsevier_pdf_api_ok",
                    "fulltext:elsevier_pdf_fallback_ok",
                ]
            ),
            needs_local_copy=True,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1016/test-pdf-assets",
                    asset_profile="body",
                    output_dir=Path(tmpdir),
                    clients={
                        "elsevier": StubProvider(
                            metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                            raw_payload=raw_payload,
                            article_factory=_article_factory_with_source("elsevier_pdf"),
                            related_asset_factory=lambda *args, **kwargs: (_ for _ in ()).throw(
                                AssertionError("Elsevier PDF fallback should skip asset downloads.")
                            ),
                        ),
                        "crossref": StubProvider(metadata=metadata),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "elsevier_pdf")
        self.assertIn("download:elsevier_assets_skipped_text_only", article.quality.source_trail)
        self.assertTrue(any("Elsevier PDF fallback currently returns text-only" in warning for warning in article.quality.warnings))

    def test_springer_pdf_route_skips_asset_downloads_with_warning(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1038/test-pdf",
            query_kind="doi",
            doi="10.1038/test-pdf",
            landing_url="https://www.nature.com/articles/test-pdf",
            provider_hint="springer",
            confidence=1.0,
        )
        metadata = {
            "provider": "crossref",
            "official_provider": False,
            "doi": "10.1038/test-pdf",
            "title": "Nature PDF Article",
            "landing_page_url": resolved.landing_url,
            "authors": ["Alice Example"],
            "fulltext_links": [],
            "references": [],
        }
        raw_payload = RawFulltextPayload(
            provider="springer",
            source_url=f"{resolved.landing_url}.pdf",
            content_type="application/pdf",
            body=b"%PDF-1.7 fake",
            content=ProviderContent(
                route_kind="pdf_fallback",
                source_url=f"{resolved.landing_url}.pdf",
                content_type="application/pdf",
                body=b"%PDF-1.7 fake",
                markdown_text="# Nature PDF Article\n\n## Results\n\n" + ("Body text " * 80),
            ),
            trace=trace_from_markers(["fulltext:springer_html_fail", "fulltext:springer_pdf_fallback_ok"]),
            needs_local_copy=True,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1038/test-pdf",
                    asset_profile="body",
                    output_dir=Path(tmpdir),
                    clients={
                        "springer": StubProvider(
                            metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                            raw_payload=raw_payload,
                            article_factory=_article_factory_with_source("springer_html"),
                            related_asset_factory=lambda *args, **kwargs: (_ for _ in ()).throw(
                                AssertionError("Springer PDF fallback should skip asset downloads.")
                            ),
                        ),
                        "crossref": StubProvider(metadata=metadata),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "springer_html")
        self.assertIn("download:springer_assets_skipped_text_only", article.quality.source_trail)
        self.assertTrue(any("Springer PDF fallback currently returns text-only" in warning for warning in article.quality.warnings))


if __name__ == "__main__":
    unittest.main()
