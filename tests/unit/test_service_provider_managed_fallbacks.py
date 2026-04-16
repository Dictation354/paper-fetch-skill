from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch import service as paper_fetch
from paper_fetch.providers import _flaresolverr, elsevier as elsevier_provider
from paper_fetch.providers.base import RawFulltextPayload

from ._paper_fetch_support import StubHtmlClient, StubProvider, fetch_paper_model, sample_article, sample_html_article


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


class ProviderManagedFallbackServiceTests(unittest.TestCase):
    def _runtime_config(self, tmpdir: str, provider: str, doi: str) -> _flaresolverr.FlareSolverrRuntimeConfig:
        tmp = Path(tmpdir)
        return _flaresolverr.FlareSolverrRuntimeConfig(
            provider=provider,
            doi=doi,
            url="http://127.0.0.1:8191/v1",
            env_file=tmp / ".env.flaresolverr",
            source_dir=tmp / "vendor" / "flaresolverr",
            artifact_dir=tmp / "artifacts",
            headless=True,
            min_interval_seconds=20,
            max_requests_per_hour=30,
            max_requests_per_day=200,
            rate_limit_file=tmp / "rate_limits.json",
        )

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
                html_client=StubHtmlClient(article=sample_html_article()),
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertIn("fallback:elsevier_html_managed_by_provider", article.quality.source_trail)
        self.assertNotIn("fallback:html_ok", article.quality.source_trail)

    def test_elsevier_html_challenge_returns_metadata_only_without_generic_html_fallback(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test-challenge",
            query_kind="doi",
            doi="10.1016/test-challenge",
            landing_url="https://www.sciencedirect.com/science/article/pii/S0034425725000525",
            provider_hint="elsevier",
            confidence=1.0,
        )
        metadata = {
            "provider": "crossref",
            "official_provider": False,
            "doi": "10.1016/test-challenge",
            "title": "Elsevier Metadata",
            "landing_page_url": resolved.landing_url,
            "authors": ["Alice Example"],
            "abstract": "Fallback abstract",
            "fulltext_links": [],
            "references": [],
        }
        official_payload = RawFulltextPayload(
            provider="elsevier",
            source_url="https://api.elsevier.com/content/article/doi/example",
            content_type="text/xml",
            body=b"<xml />",
            metadata={"route": "official", "reason": "Downloaded full text from the official Elsevier API."},
        )
        client = elsevier_provider.ElsevierClient(transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"})
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                runtime = self._runtime_config(tmpdir, "elsevier", resolved.doi)
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
                    mock.patch.object(client, "_fetch_official_payload", return_value=official_payload),
                    mock.patch.object(client, "_official_payload_is_usable", return_value=False),
                    mock.patch.object(elsevier_provider, "load_runtime_config", return_value=runtime),
                    mock.patch.object(elsevier_provider, "ensure_runtime_ready"),
                    mock.patch.object(
                        elsevier_provider,
                        "fetch_html_with_flaresolverr",
                        side_effect=_flaresolverr.FlareSolverrFailure(
                            "cloudflare_challenge",
                            "Encountered a challenge page.",
                        ),
                    ),
                ):
                    article = fetch_paper_model(
                        "10.1016/test-challenge",
                        allow_downloads=False,
                        clients={
                            "elsevier": client,
                            "crossref": StubProvider(metadata=metadata),
                        },
                        html_client=StubHtmlClient(article=sample_html_article()),
                    )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertFalse(article.quality.has_fulltext)
        self.assertIn("fulltext:elsevier_html_fail", article.quality.source_trail)
        self.assertIn("fallback:elsevier_html_managed_by_provider", article.quality.source_trail)
        self.assertIn("fallback:metadata_only", article.quality.source_trail)
        self.assertNotIn("fallback:html_ok", article.quality.source_trail)
        self.assertNotIn("fulltext:elsevier_pdf_fallback_ok", article.quality.source_trail)

    def test_elsevier_insufficient_html_returns_metadata_only_without_generic_html_fallback(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test-short-html",
            query_kind="doi",
            doi="10.1016/test-short-html",
            landing_url="https://www.sciencedirect.com/science/article/pii/S0034425725000525",
            provider_hint="elsevier",
            confidence=1.0,
        )
        metadata = {
            "provider": "crossref",
            "official_provider": False,
            "doi": "10.1016/test-short-html",
            "title": "Elsevier Metadata",
            "landing_page_url": resolved.landing_url,
            "authors": ["Alice Example"],
            "abstract": "Fallback abstract",
            "fulltext_links": [],
            "references": [],
        }
        official_payload = RawFulltextPayload(
            provider="elsevier",
            source_url="https://api.elsevier.com/content/article/doi/example",
            content_type="text/xml",
            body=b"<xml />",
            metadata={"route": "official", "reason": "Downloaded full text from the official Elsevier API."},
        )
        html = (
            "<html><head>"
            '<meta name="citation_title" content="Elsevier Short HTML Article" />'
            '<meta name="citation_doi" content="10.1016/test-short-html" />'
            "</head><body><article><h1>Elsevier Short HTML Article</h1></article></body></html>"
        )
        client = elsevier_provider.ElsevierClient(transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"})
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                runtime = self._runtime_config(tmpdir, "elsevier", resolved.doi)
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
                    mock.patch.object(client, "_fetch_official_payload", return_value=official_payload),
                    mock.patch.object(client, "_official_payload_is_usable", return_value=False),
                    mock.patch.object(elsevier_provider, "load_runtime_config", return_value=runtime),
                    mock.patch.object(elsevier_provider, "ensure_runtime_ready"),
                    mock.patch.object(
                        elsevier_provider,
                        "fetch_html_with_flaresolverr",
                        return_value=_flaresolverr.FetchedPublisherHtml(
                            source_url=resolved.landing_url,
                            final_url=resolved.landing_url,
                            html=html,
                            response_status=200,
                            response_headers={"content-type": "text/html"},
                            title="Elsevier Short HTML Article",
                            summary="Elsevier summary",
                            browser_context_seed={},
                        ),
                    ),
                    mock.patch.object(
                        elsevier_provider.html_generic,
                        "extract_article_markdown",
                        return_value="# Elsevier Short HTML Article\n\nShort abstract only.",
                    ),
                ):
                    article = fetch_paper_model(
                        "10.1016/test-short-html",
                        allow_downloads=False,
                        clients={
                            "elsevier": client,
                            "crossref": StubProvider(metadata=metadata),
                        },
                        html_client=StubHtmlClient(article=sample_html_article()),
                    )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertFalse(article.quality.has_fulltext)
        self.assertIn("fulltext:elsevier_html_fail", article.quality.source_trail)
        self.assertIn("fallback:elsevier_html_managed_by_provider", article.quality.source_trail)
        self.assertIn("fallback:metadata_only", article.quality.source_trail)
        self.assertNotIn("fallback:html_ok", article.quality.source_trail)
        self.assertNotIn("fulltext:elsevier_pdf_fallback_ok", article.quality.source_trail)

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
                html_client=StubHtmlClient(article=sample_html_article()),
            )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "crossref_meta")
        self.assertIn("fallback:springer_html_managed_by_provider", article.quality.source_trail)
        self.assertNotIn("fallback:html_ok", article.quality.source_trail)

    def test_elsevier_browser_route_skips_asset_downloads_with_warning(self) -> None:
        resolved = paper_fetch.ResolvedQuery(
            query="10.1016/test-browser",
            query_kind="doi",
            doi="10.1016/test-browser",
            landing_url="https://www.sciencedirect.com/science/article/pii/S0034425725000525",
            provider_hint="elsevier",
            confidence=1.0,
        )
        metadata = {
            "provider": "crossref",
            "official_provider": False,
            "doi": "10.1016/test-browser",
            "title": "Elsevier Browser Article",
            "landing_page_url": resolved.landing_url,
            "authors": ["Alice Example"],
            "fulltext_links": [],
            "references": [],
        }
        raw_payload = RawFulltextPayload(
            provider="elsevier_browser",
            source_url=resolved.landing_url,
            content_type="text/html",
            body=b"<html></html>",
            metadata={
                "route": "html",
                "markdown_text": "# Elsevier Browser Article\n\n## Results\n\n" + ("Body text " * 80),
                "source_trail": ["fulltext:elsevier_xml_fail", "fulltext:elsevier_html_ok"],
            },
            needs_local_copy=False,
        )
        original_resolve = paper_fetch.resolve_paper
        try:
            paper_fetch.resolve_paper = lambda *args, **kwargs: resolved
            with tempfile.TemporaryDirectory() as tmpdir:
                article = fetch_paper_model(
                    "10.1016/test-browser",
                    asset_profile="body",
                    output_dir=Path(tmpdir),
                    clients={
                        "elsevier": StubProvider(
                            metadata=paper_fetch.ProviderFailure("not_supported", "No official metadata."),
                            raw_payload=raw_payload,
                            article_factory=_article_factory_with_source("elsevier_browser"),
                            related_asset_factory=lambda *args, **kwargs: (_ for _ in ()).throw(
                                AssertionError("Elsevier browser route should skip asset downloads.")
                            ),
                        ),
                        "crossref": StubProvider(metadata=metadata),
                    },
                )
        finally:
            paper_fetch.resolve_paper = original_resolve

        self.assertEqual(article.source, "elsevier_browser")
        self.assertIn("download:elsevier_assets_skipped_text_only", article.quality.source_trail)
        self.assertTrue(any("Elsevier browser fallback currently returns text-only" in warning for warning in article.quality.warnings))

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
            metadata={
                "route": "pdf_fallback",
                "markdown_text": "# Nature PDF Article\n\n## Results\n\n" + ("Body text " * 80),
                "source_trail": ["fulltext:springer_html_fail", "fulltext:springer_pdf_fallback_ok"],
            },
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
