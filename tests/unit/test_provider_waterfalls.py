from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch.http import RequestFailure
from paper_fetch.providers import _flaresolverr, browser_workflow, elsevier as elsevier_provider, springer as springer_provider, wiley as wiley_provider
from paper_fetch.providers.base import ProviderContent, ProviderFailure, RawFulltextPayload
from paper_fetch.runtime import RuntimeContext
from tests.golden_criteria import golden_criteria_scenario_asset
from tests.provider_benchmark_samples import WILEY_PDF_FALLBACK_SAMPLE, provider_benchmark_sample
from tests.paths import FIXTURE_DIR
from tests.unit._paper_fetch_support import fulltext_pdf_bytes


ELSEVIER_SAMPLE = provider_benchmark_sample("elsevier")
SPRINGER_SAMPLE = provider_benchmark_sample("springer")
WILEY_SAMPLE = provider_benchmark_sample("wiley")
WILEY_PDF_SAMPLE = WILEY_PDF_FALLBACK_SAMPLE


class PublisherWaterfallTests(unittest.TestCase):
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
        )

    def test_elsevier_official_xml_success_keeps_elsevier_xml_source(self) -> None:
        doi = ELSEVIER_SAMPLE.doi
        metadata = {
            "doi": doi,
            "title": ELSEVIER_SAMPLE.title,
            "landing_page_url": ELSEVIER_SAMPLE.landing_url,
        }
        xml_body = (FIXTURE_DIR / ELSEVIER_SAMPLE.fixture_name).read_bytes()
        official_payload = RawFulltextPayload(
            provider="elsevier",
            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Fj.rse.2025.114648",
            content_type="text/xml",
            body=xml_body,
            content=ProviderContent(
                route_kind="official",
                source_url="https://api.elsevier.com/content/article/doi/10.1016%2Fj.rse.2025.114648",
                content_type="text/xml",
                body=xml_body,
                reason="Downloaded full text from the official Elsevier API.",
            ),
        )
        client = elsevier_provider.ElsevierClient(transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"})

        with (
            mock.patch.object(client, "_fetch_official_xml_payload", return_value=official_payload),
            mock.patch.object(client, "_official_payload_is_usable", return_value=True),
            mock.patch.object(client, "_fetch_official_pdf_payload") as mocked_pdf,
        ):
            raw_payload = client.fetch_raw_fulltext(doi, metadata)
            article = client.to_article_model(metadata, raw_payload)

        mocked_pdf.assert_not_called()
        self.assertEqual(raw_payload.provider, "elsevier")
        self.assertEqual(article.source, "elsevier_xml")
        self.assertTrue(article.quality.has_fulltext)

    def test_elsevier_xml_route_populates_article_authors_from_author_groups(self) -> None:
        metadata = {
            "doi": "10.1016/test-authors",
            "title": "Elsevier Author Example",
            "landing_page_url": "https://example.test/article",
        }
        xml_body = golden_criteria_scenario_asset("elsevier_author_groups_minimal", "original.xml").read_bytes()
        raw_payload = RawFulltextPayload(
            provider="elsevier",
            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest-authors",
            content_type="text/xml",
            body=xml_body,
            content=ProviderContent(
                route_kind="official",
                source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest-authors",
                content_type="text/xml",
                body=xml_body,
                reason="Downloaded full text from the official Elsevier API.",
            ),
        )
        client = elsevier_provider.ElsevierClient(transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"})

        article = client.to_article_model(metadata, raw_payload)

        self.assertEqual(article.source, "elsevier_xml")
        self.assertEqual(article.metadata.authors, ["Jane Doe", "Smith, J.", "Open Climate Consortium"])

    def test_elsevier_xml_root_is_reused_across_asset_and_article_conversion(self) -> None:
        metadata = {
            "doi": "10.1016/test-authors",
            "title": "Elsevier Author Example",
            "landing_page_url": "https://example.test/article",
        }
        xml_body = golden_criteria_scenario_asset("elsevier_author_groups_minimal", "original.xml").read_bytes()
        raw_payload = RawFulltextPayload(
            provider="elsevier",
            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest-authors",
            content_type="text/xml",
            body=xml_body,
            content=ProviderContent(
                route_kind="official",
                source_url="https://api.elsevier.com/content/article/doi/10.1016%2Ftest-authors",
                content_type="text/xml",
                body=xml_body,
                reason="Downloaded full text from the official Elsevier API.",
            ),
        )
        context = RuntimeContext(env={"ELSEVIER_API_KEY": "secret"}, transport=mock.Mock())
        client = elsevier_provider.ElsevierClient(transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"})

        with mock.patch.object(elsevier_provider.ET, "fromstring", wraps=elsevier_provider.ET.fromstring) as fromstring:
            elsevier_provider.extract_elsevier_asset_references(
                raw_payload.body,
                context=context,
                source_url=raw_payload.source_url,
            )
            article = client.to_article_model(metadata, raw_payload, context=context)

        self.assertEqual(fromstring.call_count, 1)
        self.assertEqual(article.source, "elsevier_xml")

    def test_elsevier_official_xml_usable_records_structured_diagnostics(self) -> None:
        doi = ELSEVIER_SAMPLE.doi
        metadata = {
            "doi": doi,
            "title": ELSEVIER_SAMPLE.title,
            "landing_page_url": ELSEVIER_SAMPLE.landing_url,
        }
        xml_body = (FIXTURE_DIR / ELSEVIER_SAMPLE.fixture_name).read_bytes()
        raw_payload = RawFulltextPayload(
            provider="elsevier",
            source_url="https://api.elsevier.com/content/article/doi/example",
            content_type="text/xml",
            body=xml_body,
            content=ProviderContent(
                route_kind="official",
                source_url="https://api.elsevier.com/content/article/doi/example",
                content_type="text/xml",
                body=xml_body,
                reason="Downloaded full text from the official Elsevier API.",
            ),
        )
        client = elsevier_provider.ElsevierClient(transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"})

        usable = client._official_payload_is_usable(metadata, raw_payload)

        self.assertTrue(usable)
        diagnostics = raw_payload.metadata["availability_diagnostics"]
        self.assertEqual(diagnostics["content_kind"], "fulltext")
        self.assertTrue(diagnostics["accepted"])
        self.assertEqual(diagnostics["reason"], "structured_body_sections")

    def test_elsevier_official_plain_text_uses_body_sufficiency(self) -> None:
        raw_payload = RawFulltextPayload(
            provider="elsevier",
            source_url="https://api.elsevier.com/content/article/doi/example",
            content_type="text/plain",
            body=("# Example Article\n\n## Results\n\n" + ("Body text " * 120)).encode("utf-8"),
            content=ProviderContent(
                route_kind="official",
                source_url="https://api.elsevier.com/content/article/doi/example",
                content_type="text/plain",
                body=("# Example Article\n\n## Results\n\n" + ("Body text " * 120)).encode("utf-8"),
                reason="Downloaded full text from the official Elsevier API.",
            ),
        )
        client = elsevier_provider.ElsevierClient(transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"})

        usable = client._official_payload_is_usable(
            {"doi": "10.1016/example", "title": "Example Article"},
            raw_payload,
        )

        self.assertTrue(usable)
        diagnostics = raw_payload.metadata["availability_diagnostics"]
        self.assertEqual(diagnostics["content_kind"], "fulltext")
        self.assertTrue(diagnostics["accepted"])
        self.assertEqual(diagnostics["reason"], "body_sufficient")

    def test_elsevier_official_xml_without_body_sections_is_unusable(self) -> None:
        raw_payload = RawFulltextPayload(
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
        fake_article = mock.Mock()
        fake_article.quality = mock.Mock(has_fulltext=True)
        fake_article.sections = [mock.Mock(kind="abstract", text="Abstract only.")]
        fake_article.assets = []
        fake_article.metadata = mock.Mock(title="Example Article")
        client = elsevier_provider.ElsevierClient(transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"})

        with mock.patch.object(client, "to_article_model", return_value=fake_article):
            usable = client._official_payload_is_usable(
                {"doi": "10.1016/example", "title": "Example Article"},
                raw_payload,
            )

        self.assertFalse(usable)
        diagnostics = raw_payload.metadata["availability_diagnostics"]
        self.assertEqual(diagnostics["content_kind"], "abstract_only")
        self.assertFalse(diagnostics["accepted"])
        self.assertEqual(diagnostics["reason"], "structured_missing_body_sections")

    def test_elsevier_falls_back_to_official_pdf_when_xml_is_unusable(self) -> None:
        doi = ELSEVIER_SAMPLE.doi
        metadata = {
            "doi": doi,
            "title": ELSEVIER_SAMPLE.title,
            "landing_page_url": ELSEVIER_SAMPLE.landing_url,
            "fulltext_links": [],
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
                markdown_text=f"# {ELSEVIER_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
            ),
            needs_local_copy=True,
        )
        client = elsevier_provider.ElsevierClient(transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"})

        with (
            mock.patch.object(client, "_fetch_official_xml_payload", return_value=xml_payload),
            mock.patch.object(client, "_official_payload_is_usable", return_value=False),
            mock.patch.object(client, "_fetch_official_pdf_payload", return_value=pdf_payload),
        ):
            raw_payload = client.fetch_raw_fulltext(doi, metadata)
            article = client.to_article_model(metadata, raw_payload)

        self.assertEqual(raw_payload.provider, "elsevier")
        self.assertEqual(raw_payload.metadata["route"], "pdf_fallback")
        self.assertEqual(article.source, "elsevier_pdf")
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("fulltext:elsevier_xml_fail", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_pdf_api_ok", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_pdf_fallback_ok", article.quality.source_trail)
        self.assertNotIn("fulltext:elsevier_html_ok", article.quality.source_trail)
        self.assertTrue(
            any(
                "Elsevier official XML response did not produce enough article body text" in item
                for item in raw_payload.warnings
            )
        )
        self.assertIn(
            "Full text was extracted from the Elsevier API PDF fallback after the XML route was not usable.",
            raw_payload.warnings,
        )

    def test_elsevier_xml_transport_failures_can_use_official_pdf_fallback(self) -> None:
        doi = "10.1016/test-old-paper"
        metadata = {
            "doi": doi,
            "title": "Elsevier Legacy Article",
            "landing_page_url": "https://linkinghub.elsevier.com/retrieve/pii/S0304416596000542",
            "fulltext_links": [],
        }

        class RecordingTransport:
            def __init__(self, xml_status_code: int) -> None:
                self.xml_status_code = xml_status_code
                self.calls: list[dict[str, object]] = []

            def request(self, method, url, *, headers=None, query=None, **_kwargs):
                call = {
                    "method": method,
                    "url": url,
                    "headers": dict(headers or {}),
                    "query": dict(query or {}),
                }
                self.calls.append(call)
                accept = str((headers or {}).get("Accept") or "")
                if accept == "text/xml":
                    raise RequestFailure(self.xml_status_code, f"HTTP {self.xml_status_code} for {url}?view=FULL")
                if accept == "application/pdf":
                    return {
                        "status_code": 200,
                        "headers": {"content-type": "application/pdf"},
                        "body": fulltext_pdf_bytes(),
                        "url": f"{url}?view=FULL",
                    }
                raise AssertionError(f"Unexpected Accept header: {accept}")

        for status_code in (404, 406, 415):
            with self.subTest(status_code=status_code):
                transport = RecordingTransport(status_code)
                client = elsevier_provider.ElsevierClient(transport=transport, env={"ELSEVIER_API_KEY": "secret"})
                with mock.patch.object(
                    elsevier_provider,
                    "pdf_fetch_result_from_bytes",
                    return_value=mock.Mock(
                        final_url=f"https://api.elsevier.com/content/article/doi/{doi}?view=FULL",
                        pdf_bytes=fulltext_pdf_bytes(),
                        markdown_text="# Elsevier Legacy Article\n\n## Results\n\n" + ("Body text " * 80),
                        suggested_filename="legacy.pdf",
                    ),
                ):
                    raw_payload = client.fetch_raw_fulltext(doi, metadata)
                    article = client.to_article_model(metadata, raw_payload)

                self.assertEqual(raw_payload.metadata["route"], "pdf_fallback")
                self.assertIn("fulltext:elsevier_xml_fail", raw_payload.metadata["source_trail"])
                self.assertIn("fulltext:elsevier_pdf_api_ok", raw_payload.metadata["source_trail"])
                self.assertIn("fulltext:elsevier_pdf_fallback_ok", raw_payload.metadata["source_trail"])
                self.assertEqual(article.source, "elsevier_pdf")
                self.assertEqual(
                    [str(call["headers"].get("Accept") or "") for call in transport.calls],
                    ["text/xml", "application/pdf"],
                )
                self.assertEqual(
                    [str(call["url"]) for call in transport.calls],
                    [
                        "https://api.elsevier.com/content/article/doi/10.1016%2Ftest-old-paper",
                        "https://api.elsevier.com/content/article/doi/10.1016%2Ftest-old-paper",
                    ],
                )
                self.assertEqual(
                    [call["query"] for call in transport.calls],
                    [{"view": "FULL"}, {"view": "FULL"}],
                )

    def test_elsevier_xml_and_pdf_failures_are_combined_without_html_markers(self) -> None:
        doi = "10.1016/test-no-fulltext"
        metadata = {
            "doi": doi,
            "title": "Elsevier Missing Article",
            "landing_page_url": "https://linkinghub.elsevier.com/retrieve/pii/S0304416596000542",
            "fulltext_links": [],
        }
        client = elsevier_provider.ElsevierClient(transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"})

        with (
            mock.patch.object(
                client,
                "_fetch_official_xml_payload",
                side_effect=ProviderFailure("no_result", "Elsevier official XML representation is not available."),
            ),
            mock.patch.object(
                client,
                "_fetch_official_pdf_payload",
                side_effect=ProviderFailure("no_result", "Elsevier official PDF representation is not available."),
            ),
        ):
            with self.assertRaises(ProviderFailure) as ctx:
                client.fetch_raw_fulltext(doi, metadata)

        self.assertEqual(ctx.exception.code, "no_result")
        self.assertIn("fulltext:elsevier_xml_fail", ctx.exception.source_trail)
        self.assertIn("fulltext:elsevier_pdf_api_fail", ctx.exception.source_trail)
        self.assertNotIn("fulltext:elsevier_html_fail", ctx.exception.source_trail)
        self.assertIn("Elsevier official XML representation is not available.", ctx.exception.message)
        self.assertIn("Elsevier official PDF representation is not available.", ctx.exception.message)

    def test_springer_html_success_keeps_springer_html_source(self) -> None:
        doi = SPRINGER_SAMPLE.doi
        landing_url = SPRINGER_SAMPLE.landing_url
        metadata = {
            "doi": doi,
            "title": SPRINGER_SAMPLE.title,
            "landing_page_url": landing_url,
            "fulltext_links": [],
        }
        response = {
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": (
                b"<html><head>"
                + f'<meta name="citation_title" content="{SPRINGER_SAMPLE.title}" />'.encode()
                + f'<meta name="citation_doi" content="{SPRINGER_SAMPLE.doi}" />'.encode()
                + f"</head><body><article><h1>{SPRINGER_SAMPLE.title}</h1></article></body></html>".encode()
            ),
            "url": landing_url,
        }
        client = springer_provider.SpringerClient(transport=mock.Mock(), env={})

        with (
            mock.patch.object(client, "_fetch_html_response", return_value=(response, landing_url)),
            mock.patch.object(
                springer_provider._springer_html,
                "extract_article_markdown",
                return_value=f"# {SPRINGER_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
            ),
            mock.patch.object(springer_provider, "fetch_pdf_over_http") as mocked_pdf,
        ):
            raw_payload = client.fetch_raw_fulltext(doi, metadata)
            article = client.to_article_model(metadata, raw_payload)

        mocked_pdf.assert_not_called()
        self.assertEqual(raw_payload.metadata["route"], "html")
        self.assertEqual(article.source, "springer_html")
        self.assertIn("fulltext:springer_html_ok", article.quality.source_trail)

    def test_springer_html_route_uses_provider_extracted_authors_when_shared_metadata_has_none(self) -> None:
        doi = SPRINGER_SAMPLE.doi
        landing_url = SPRINGER_SAMPLE.landing_url
        metadata = {
            "doi": doi,
            "title": SPRINGER_SAMPLE.title,
            "landing_page_url": landing_url,
            "authors": [],
            "fulltext_links": [],
        }
        response = {
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": (
                b"<html><head>"
                + f'<meta name="citation_title" content="{SPRINGER_SAMPLE.title}" />'.encode()
                + f'<meta name="citation_doi" content="{SPRINGER_SAMPLE.doi}" />'.encode()
                + b'<meta name="citation_author" content="Alice Example" />'
                + b'<meta name="citation_author" content="Bob Example" />'
                + f"</head><body><article><h1>{SPRINGER_SAMPLE.title}</h1></article></body></html>".encode()
            ),
            "url": landing_url,
        }
        client = springer_provider.SpringerClient(transport=mock.Mock(), env={})

        with (
            mock.patch.object(client, "_fetch_html_response", return_value=(response, landing_url)),
            mock.patch.object(
                springer_provider._springer_html,
                "parse_html_metadata",
                return_value={
                    "title": SPRINGER_SAMPLE.title,
                    "doi": SPRINGER_SAMPLE.doi,
                    "landing_page_url": landing_url,
                    "authors": [],
                    "raw_meta": {},
                },
            ),
            mock.patch.object(
                springer_provider._springer_html,
                "extract_article_markdown",
                return_value=f"# {SPRINGER_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
            ),
            mock.patch.object(springer_provider, "fetch_pdf_over_http") as mocked_pdf,
        ):
            raw_payload = client.fetch_raw_fulltext(doi, metadata)
            article = client.to_article_model(metadata, raw_payload)

        mocked_pdf.assert_not_called()
        self.assertEqual(article.metadata.authors, ["Alice Example", "Bob Example"])

    def test_springer_extract_authors_uses_ld_json_main_entity_when_meta_missing(self) -> None:
        html = """
        <html>
          <head>
            <script type="application/ld+json">
              {
                "@context": "https://schema.org",
                "@type": "WebPage",
                "mainEntity": {
                  "@type": "ScholarlyArticle",
                  "author": [
                    {"@type": "Person", "name": "Ada Example"},
                    {"@type": "Person", "name": "Bruno Example"}
                  ]
                }
              }
            </script>
          </head>
          <body><article><h1>LD JSON Example</h1></article></body>
        </html>
        """

        authors = springer_provider._springer_html.extract_authors(html)

        self.assertEqual(authors, ["Ada Example", "Bruno Example"])

    def test_springer_extract_authors_normalizes_simple_comma_names(self) -> None:
        html = """
        <html>
          <head>
            <meta name="citation_author" content="Li, Yang" />
            <meta name="citation_author" content="von Randow, Celso" />
          </head>
          <body><article><h1>Meta Author Example</h1></article></body>
        </html>
        """

        authors = springer_provider._springer_html.extract_authors(html)

        self.assertEqual(authors, ["Yang Li", "Celso von Randow"])

    def test_springer_extract_authors_does_not_rewrite_collective_or_multi_comma_names(self) -> None:
        html = """
        <html>
          <head>
            <meta name="citation_author" content="The ENCODE Project Consortium, et al." />
            <meta name="citation_author" content="Smith, John, Jr." />
          </head>
          <body><article><h1>Collective Author Example</h1></article></body>
        </html>
        """

        authors = springer_provider._springer_html.extract_authors(html)

        self.assertEqual(authors, ["The ENCODE Project Consortium, et al.", "Smith, John, Jr."])

    def test_springer_extract_authors_does_not_leak_reference_metadata(self) -> None:
        html = """
        <html>
          <head>
            <meta name="citation_reference" content="author=Reference Author; title=Reference Title" />
            <script type="application/ld+json">
              {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": []}
            </script>
          </head>
          <body><article><h1>No Article Author Signal</h1></article></body>
        </html>
        """

        authors = springer_provider._springer_html.extract_authors(html)

        self.assertEqual(authors, [])

    def test_springer_to_article_model_prefers_normalized_provider_authors_over_crossref_display(self) -> None:
        doi = SPRINGER_SAMPLE.doi
        title = SPRINGER_SAMPLE.title
        landing_url = SPRINGER_SAMPLE.landing_url
        client = springer_provider.SpringerClient(transport=mock.Mock(), env={})
        raw_payload = springer_provider.RawFulltextPayload(
            provider="springer",
            source_url=landing_url,
            content_type="text/html",
            body=b"<html></html>",
            content=springer_provider.ProviderContent(
                route_kind="html",
                source_url=landing_url,
                content_type="text/html",
                body=b"<html></html>",
                markdown_text=f"# {title}\n\n" + ("Body text " * 60),
                diagnostics={
                    "extraction": {
                        "extracted_authors": ["Li, Yang", "von Randow, Celso"],
                    }
                },
            ),
        )

        article = client.to_article_model(
            {
                "doi": doi,
                "title": title,
                "authors": ["Yang Li", "Celso von Randow", "Crossref Fallback"],
            },
            raw_payload,
        )

        self.assertEqual(article.metadata.authors[:3], ["Yang Li", "Celso von Randow", "Crossref Fallback"])

    def test_springer_to_article_model_keeps_extracted_figures_without_downloads(self) -> None:
        doi = SPRINGER_SAMPLE.doi
        title = SPRINGER_SAMPLE.title
        landing_url = SPRINGER_SAMPLE.landing_url
        client = springer_provider.SpringerClient(transport=mock.Mock(), env={})
        raw_payload = springer_provider.RawFulltextPayload(
            provider="springer",
            source_url=landing_url,
            content_type="text/html",
            body=b"<html></html>",
            content=springer_provider.ProviderContent(
                route_kind="html",
                source_url=landing_url,
                content_type="text/html",
                body=b"<html></html>",
                markdown_text=f"# {title}\n\n## Results\n\n" + ("Body text " * 60),
                extracted_assets=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "caption": "Figure showing a woodland canopy.",
                        "url": "https://media.springernature.com/full/example-figure-1.png",
                        "section": "body",
                    }
                ],
            ),
        )

        article = client.to_article_model(
            {
                "doi": doi,
                "title": title,
                "authors": ["Crossref Fallback"],
            },
            raw_payload,
        )
        markdown = article.to_ai_markdown(max_tokens="full_text")

        self.assertEqual(len(article.assets), 1)
        self.assertEqual(article.assets[0].heading, "Figure 1")
        self.assertEqual(article.assets[0].caption, "Figure showing a woodland canopy.")
        self.assertIsNone(article.assets[0].url)
        self.assertIn("## Figures", markdown)
        self.assertIn("- Figure 1: Figure showing a woodland canopy.", markdown)

    def test_springer_falls_back_to_direct_http_pdf(self) -> None:
        doi = SPRINGER_SAMPLE.doi
        landing_url = SPRINGER_SAMPLE.landing_url
        metadata = {
            "doi": doi,
            "title": SPRINGER_SAMPLE.title,
            "landing_page_url": landing_url,
            "fulltext_links": [{"url": f"{landing_url}.pdf", "content_type": "application/pdf"}],
        }
        response = {
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": (
                b"<html><head>"
                + f'<meta name="citation_title" content="{SPRINGER_SAMPLE.title}" />'.encode()
                + f'<meta name="citation_doi" content="{SPRINGER_SAMPLE.doi}" />'.encode()
                + f'<meta name="citation_pdf_url" content="{landing_url}.pdf" />'.encode()
                + f"</head><body><article><h1>{SPRINGER_SAMPLE.title}</h1></article></body></html>".encode()
            ),
            "url": landing_url,
        }
        client = springer_provider.SpringerClient(transport=mock.Mock(), env={})

        with (
            mock.patch.object(client, "_fetch_html_response", return_value=(response, landing_url)),
            mock.patch.object(
                springer_provider._springer_html,
                "extract_article_markdown",
                return_value=f"# {SPRINGER_SAMPLE.title}\n\nShort abstract only.",
            ),
            mock.patch.object(
                springer_provider,
                "fetch_pdf_over_http",
                return_value=mock.Mock(
                    source_url=f"{landing_url}.pdf",
                    final_url=f"{landing_url}.pdf",
                    pdf_bytes=fulltext_pdf_bytes(),
                    markdown_text=f"# {SPRINGER_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                    suggested_filename="nature-article.pdf",
                ),
            ) as mocked_pdf,
        ):
            raw_payload = client.fetch_raw_fulltext(doi, metadata)
            article = client.to_article_model(metadata, raw_payload)

        mocked_pdf.assert_called_once()
        self.assertEqual(mocked_pdf.call_args.kwargs["seed_urls"], [landing_url])
        self.assertEqual(raw_payload.metadata["route"], "pdf_fallback")
        self.assertTrue(raw_payload.needs_local_copy)
        self.assertEqual(article.source, "springer_html")
        self.assertIn("fulltext:springer_html_fail", article.quality.source_trail)
        self.assertIn("fulltext:springer_pdf_fallback_ok", article.quality.source_trail)
        self.assertTrue(
            any("Springer HTML route was not usable" in item for item in raw_payload.warnings)
        )
        self.assertIn(
            "Full text was extracted from PDF fallback after the Springer HTML path was not usable.",
            raw_payload.warnings,
        )

    def test_springer_fetch_result_returns_abstract_only_when_pdf_fallback_fails(self) -> None:
        doi = SPRINGER_SAMPLE.doi
        landing_url = SPRINGER_SAMPLE.landing_url
        metadata = {
            "doi": doi,
            "title": SPRINGER_SAMPLE.title,
            "landing_page_url": landing_url,
            "fulltext_links": [{"url": f"{landing_url}.pdf", "content_type": "application/pdf"}],
        }
        response = {
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": (
                b"<html><head>"
                + f'<meta name="citation_title" content="{SPRINGER_SAMPLE.title}" />'.encode()
                + f'<meta name="citation_doi" content="{SPRINGER_SAMPLE.doi}" />'.encode()
                + b"</head><body><article></article></body></html>"
            ),
            "url": landing_url,
        }
        client = springer_provider.SpringerClient(transport=mock.Mock(), env={})

        with (
            mock.patch.object(client, "_fetch_html_response", return_value=(response, landing_url)),
            mock.patch.object(
                springer_provider._springer_html,
                "extract_html_payload",
                return_value={
                    "markdown_text": f"# {SPRINGER_SAMPLE.title}\n\n## Abstract\n\nHTML abstract only.",
                    "abstract_sections": [{"kind": "abstract", "heading": "Abstract", "text": "HTML abstract only."}],
                    "section_hints": [],
                    "extracted_authors": [],
                },
            ),
            mock.patch.object(
                springer_provider,
                "fetch_pdf_over_http",
                side_effect=springer_provider.PdfFetchFailure("pdf_download_failed", "Springer PDF fallback failed."),
            ),
        ):
            result = client.fetch_result(doi, metadata, None)

        self.assertEqual(result.article.source, "springer_html")
        self.assertEqual(result.article.quality.content_kind, "abstract_only")
        self.assertEqual(result.article.metadata.abstract, "HTML abstract only.")
        self.assertIn("fulltext:springer_html_fail", result.article.quality.source_trail)
        self.assertIn("fulltext:springer_abstract_only", result.article.quality.source_trail)
        self.assertNotIn("fallback:metadata_only", result.article.quality.source_trail)
        self.assertTrue(any("returning abstract-only content" in warning for warning in result.article.quality.warnings))

    def test_springer_fetch_result_returns_metadata_only_when_no_abstract_and_pdf_fallback_fails(self) -> None:
        doi = SPRINGER_SAMPLE.doi
        landing_url = SPRINGER_SAMPLE.landing_url
        metadata = {
            "doi": doi,
            "title": SPRINGER_SAMPLE.title,
            "landing_page_url": landing_url,
            "fulltext_links": [{"url": f"{landing_url}.pdf", "content_type": "application/pdf"}],
        }
        response = {
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": (
                b"<html><head>"
                + f'<meta name="citation_title" content="{SPRINGER_SAMPLE.title}" />'.encode()
                + f'<meta name="citation_doi" content="{SPRINGER_SAMPLE.doi}" />'.encode()
                + b"</head><body><article></article></body></html>"
            ),
            "url": landing_url,
        }
        client = springer_provider.SpringerClient(transport=mock.Mock(), env={})

        with (
            mock.patch.object(client, "_fetch_html_response", return_value=(response, landing_url)),
            mock.patch.object(
                springer_provider._springer_html,
                "extract_html_payload",
                return_value={
                    "markdown_text": f"# {SPRINGER_SAMPLE.title}\n\nAccess restricted.",
                    "abstract_sections": [],
                    "section_hints": [],
                    "extracted_authors": [],
                },
            ),
            mock.patch.object(
                springer_provider,
                "fetch_pdf_over_http",
                side_effect=springer_provider.PdfFetchFailure("pdf_download_failed", "Springer PDF fallback failed."),
            ),
        ):
            result = client.fetch_result(doi, metadata, None)

        self.assertEqual(result.article.source, "springer_html")
        self.assertEqual(result.article.quality.content_kind, "metadata_only")
        self.assertNotIn("fulltext:springer_abstract_only", result.article.quality.source_trail)

    def test_springer_fetch_result_recovers_pdf_after_abstract_only_html(self) -> None:
        doi = SPRINGER_SAMPLE.doi
        landing_url = SPRINGER_SAMPLE.landing_url
        metadata = {
            "doi": doi,
            "title": SPRINGER_SAMPLE.title,
            "landing_page_url": landing_url,
            "fulltext_links": [{"url": f"{landing_url}.pdf", "content_type": "application/pdf"}],
        }
        response = {
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": (
                b"<html><head>"
                + f'<meta name="citation_title" content="{SPRINGER_SAMPLE.title}" />'.encode()
                + f'<meta name="citation_doi" content="{SPRINGER_SAMPLE.doi}" />'.encode()
                + b"</head><body><article></article></body></html>"
            ),
            "url": landing_url,
        }
        client = springer_provider.SpringerClient(transport=mock.Mock(), env={})

        with (
            mock.patch.object(client, "_fetch_html_response", return_value=(response, landing_url)),
            mock.patch.object(
                springer_provider._springer_html,
                "extract_html_payload",
                return_value={
                    "markdown_text": f"# {SPRINGER_SAMPLE.title}\n\n## Abstract\n\nHTML abstract only.",
                    "abstract_sections": [{"kind": "abstract", "heading": "Abstract", "text": "HTML abstract only."}],
                    "section_hints": [],
                    "extracted_authors": [],
                },
            ),
            mock.patch.object(
                springer_provider,
                "fetch_pdf_over_http",
                return_value=mock.Mock(
                    source_url=f"{landing_url}.pdf",
                    final_url=f"{landing_url}.pdf",
                    pdf_bytes=fulltext_pdf_bytes(),
                    markdown_text=f"# {SPRINGER_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                    suggested_filename="nature-article.pdf",
                ),
            ),
        ):
            result = client.fetch_result(doi, metadata, None)

        self.assertEqual(result.article.source, "springer_html")
        self.assertEqual(result.article.quality.content_kind, "fulltext")
        self.assertIn("fulltext:springer_html_fail", result.article.quality.source_trail)
        self.assertIn("fulltext:springer_pdf_fallback_ok", result.article.quality.source_trail)

    def test_wiley_html_success_keeps_wiley_browser_source(self) -> None:
        doi = WILEY_SAMPLE.doi
        metadata = {
            "doi": doi,
            "title": WILEY_SAMPLE.title,
            "landing_page_url": WILEY_SAMPLE.landing_url,
            "fulltext_links": [],
        }
        client = wiley_provider.WileyClient(transport=mock.Mock(), env={})

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "wiley", doi)
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "fetch_html_with_flaresolverr",
                    return_value=_flaresolverr.FetchedPublisherHtml(
                        source_url=WILEY_SAMPLE.landing_url,
                        final_url=WILEY_SAMPLE.landing_url,
                        html="<html></html>",
                        response_status=200,
                        response_headers={"content-type": "text/html"},
                        title=WILEY_SAMPLE.title,
                        summary="Wiley summary",
                        browser_context_seed={},
                    ),
                ),
                mock.patch.object(
                    browser_workflow,
                    "extract_science_pnas_markdown",
                    return_value=(f"# {WILEY_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120), {"title": WILEY_SAMPLE.title}),
                ),
                mock.patch.object(wiley_provider, "_fetch_wiley_tdm_pdf_result") as mocked_api,
                mock.patch.object(browser_workflow, "fetch_pdf_with_playwright") as mocked_browser_pdf,
            ):
                raw_payload = client.fetch_raw_fulltext(doi, metadata)
                article = client.to_article_model(metadata, raw_payload)

        mocked_api.assert_not_called()
        mocked_browser_pdf.assert_not_called()
        self.assertEqual(raw_payload.metadata["route"], "html")
        self.assertEqual(article.source, "wiley_browser")
        self.assertIn("fulltext:wiley_html_ok", article.quality.source_trail)

    def test_wiley_prefers_browser_pdf_over_tdm_api_when_html_is_not_usable(self) -> None:
        doi = WILEY_PDF_SAMPLE.doi
        metadata = {
            "doi": doi,
            "title": WILEY_PDF_SAMPLE.title,
            "landing_page_url": WILEY_PDF_SAMPLE.landing_url,
        }
        client = wiley_provider.WileyClient(
            transport=mock.Mock(),
            env={wiley_provider.WILEY_TDM_CLIENT_TOKEN_ENV_VAR: "secret"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "wiley", doi)
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "fetch_html_with_flaresolverr",
                    side_effect=browser_workflow.SciencePnasHtmlFailure(
                        "insufficient_fulltext",
                        "HTML content does not look like a complete full-text article.",
                    ),
                ),
                mock.patch.object(
                    browser_workflow,
                    "fetch_seeded_browser_pdf_payload",
                    return_value=RawFulltextPayload(
                        provider="wiley",
                        source_url=f"https://onlinelibrary.wiley.com/doi/epdf/{doi}",
                        content_type="application/pdf",
                        body=fulltext_pdf_bytes(),
                        content=ProviderContent(
                            route_kind="pdf_fallback",
                            source_url=f"https://onlinelibrary.wiley.com/doi/epdf/{doi}",
                            content_type="application/pdf",
                            body=fulltext_pdf_bytes(),
                            markdown_text=f"# {WILEY_PDF_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                            suggested_filename="article.pdf",
                        ),
                        needs_local_copy=True,
                    ),
                ) as mocked_browser_pdf,
                mock.patch.object(wiley_provider, "_fetch_wiley_tdm_pdf_result") as mocked_api,
            ):
                raw_payload = client.fetch_raw_fulltext(doi, metadata)
                article = client.to_article_model(metadata, raw_payload)

        mocked_browser_pdf.assert_called_once()
        mocked_api.assert_not_called()
        self.assertEqual(raw_payload.metadata["route"], "pdf_fallback")
        self.assertEqual(article.source, "wiley_browser")
        self.assertIn("fulltext:wiley_pdf_browser_ok", article.quality.source_trail)
        self.assertIn("fulltext:wiley_pdf_fallback_ok", article.quality.source_trail)
        self.assertNotIn("fulltext:wiley_pdf_api_ok", article.quality.source_trail)

    def test_wiley_missing_tdm_token_can_use_browser_pdf_fallback(self) -> None:
        doi = WILEY_PDF_SAMPLE.doi
        metadata = {
            "doi": doi,
            "title": WILEY_PDF_SAMPLE.title,
            "landing_page_url": WILEY_PDF_SAMPLE.landing_url,
        }
        client = wiley_provider.WileyClient(transport=mock.Mock(), env={})

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "wiley", doi)
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "fetch_html_with_flaresolverr",
                    side_effect=browser_workflow.FlareSolverrFailure(
                        "redirected_to_abstract",
                        "HTML redirected to abstract.",
                        browser_context_seed={
                            "browser_cookies": [
                                {"name": "cf_clearance", "value": "seed", "domain": ".wiley.com", "path": "/"}
                            ],
                            "browser_user_agent": "Mozilla/5.0",
                            "browser_final_url": WILEY_PDF_SAMPLE.landing_url,
                        },
                    ),
                ),
                mock.patch.object(
                    browser_workflow,
                    "warm_browser_context_with_flaresolverr",
                    return_value={
                        "browser_cookies": [
                            {"name": "cf_clearance", "value": "seed", "domain": ".wiley.com", "path": "/"},
                            {"name": "sessionid", "value": "warm", "domain": ".wiley.com", "path": "/"},
                        ],
                        "browser_user_agent": "Mozilla/5.0",
                        "browser_final_url": WILEY_PDF_SAMPLE.landing_url,
                    },
                ) as mocked_warm,
                mock.patch.object(wiley_provider, "_fetch_wiley_tdm_pdf_result") as mocked_api,
                mock.patch.object(
                    browser_workflow,
                    "fetch_pdf_with_playwright",
                    return_value=mock.Mock(
                        source_url=f"https://onlinelibrary.wiley.com/doi/epdf/{doi}",
                        final_url=f"https://onlinelibrary.wiley.com/doi/epdf/{doi}",
                        pdf_bytes=fulltext_pdf_bytes(),
                        markdown_text=f"# {WILEY_PDF_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                        suggested_filename="article.pdf",
                    ),
                ) as mocked_browser_pdf,
            ):
                raw_payload = client.fetch_raw_fulltext(doi, metadata)
                article = client.to_article_model(metadata, raw_payload)

        mocked_warm.assert_called_once()
        mocked_api.assert_not_called()
        mocked_browser_pdf.assert_called_once()
        self.assertEqual(raw_payload.metadata["route"], "pdf_fallback")
        self.assertEqual(article.source, "wiley_browser")
        self.assertIn("fulltext:wiley_pdf_browser_ok", article.quality.source_trail)
        self.assertIn("fulltext:wiley_pdf_fallback_ok", article.quality.source_trail)
        self.assertNotIn("fulltext:wiley_pdf_api_fail", article.quality.source_trail)
        self.assertEqual(
            list(mocked_browser_pdf.call_args.args[0])[:4],
            [
                f"https://onlinelibrary.wiley.com/doi/epdf/{doi}",
                f"https://onlinelibrary.wiley.com/doi/pdf/{doi}",
                f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}",
                f"https://onlinelibrary.wiley.com/wol1/doi/{doi}/fullpdf",
            ],
        )

    def test_wiley_falls_back_to_tdm_api_after_browser_pdf_failure(self) -> None:
        doi = WILEY_PDF_SAMPLE.doi
        metadata = {
            "doi": doi,
            "title": WILEY_PDF_SAMPLE.title,
            "landing_page_url": WILEY_PDF_SAMPLE.landing_url,
        }
        client = wiley_provider.WileyClient(
            transport=mock.Mock(),
            env={wiley_provider.WILEY_TDM_CLIENT_TOKEN_ENV_VAR: "secret"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "wiley", doi)
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "fetch_html_with_flaresolverr",
                    side_effect=browser_workflow.FlareSolverrFailure(
                        "redirected_to_abstract",
                        "HTML redirected to abstract.",
                        browser_context_seed={
                            "browser_cookies": [
                                {"name": "cf_clearance", "value": "seed", "domain": ".wiley.com", "path": "/"}
                            ],
                            "browser_user_agent": "Mozilla/5.0",
                            "browser_final_url": WILEY_PDF_SAMPLE.landing_url,
                        },
                    ),
                ),
                mock.patch.object(
                    browser_workflow,
                    "fetch_seeded_browser_pdf_payload",
                    side_effect=browser_workflow.PdfFallbackFailure(
                        "download_not_triggered",
                        "Browser PDF download was not triggered.",
                    ),
                ) as mocked_browser_pdf,
                mock.patch.object(
                    wiley_provider,
                    "_fetch_wiley_tdm_pdf_result",
                    return_value=mock.Mock(
                        source_url=f"https://api.wiley.com/onlinelibrary/tdm/v1/articles/{doi}",
                        final_url=f"https://api.wiley.com/onlinelibrary/tdm/v1/articles/{doi}",
                        pdf_bytes=fulltext_pdf_bytes(),
                        markdown_text=f"# {WILEY_PDF_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                        suggested_filename="article.pdf",
                    ),
                ) as mocked_api,
            ):
                raw_payload = client.fetch_raw_fulltext(doi, metadata)
                article = client.to_article_model(metadata, raw_payload)

        mocked_browser_pdf.assert_called_once()
        mocked_api.assert_called_once()
        self.assertEqual(raw_payload.metadata["route"], "pdf_fallback")
        self.assertEqual(article.source, "wiley_browser")
        self.assertIn("fulltext:wiley_pdf_browser_fail", article.quality.source_trail)
        self.assertIn("fulltext:wiley_pdf_api_ok", article.quality.source_trail)
        self.assertIn("fulltext:wiley_pdf_fallback_ok", article.quality.source_trail)
        self.assertNotIn("fulltext:wiley_pdf_browser_ok", article.quality.source_trail)

    def test_wiley_reports_api_and_browser_pdf_failures_after_html_failure(self) -> None:
        doi = WILEY_PDF_SAMPLE.doi
        metadata = {
            "doi": doi,
            "title": WILEY_PDF_SAMPLE.title,
            "landing_page_url": WILEY_PDF_SAMPLE.landing_url,
        }
        client = wiley_provider.WileyClient(
            transport=mock.Mock(),
            env={wiley_provider.WILEY_TDM_CLIENT_TOKEN_ENV_VAR: "secret"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "wiley", doi)
            with (
                mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
                mock.patch.object(browser_workflow, "ensure_runtime_ready"),
                mock.patch.object(
                    browser_workflow,
                    "fetch_html_with_flaresolverr",
                    side_effect=browser_workflow.SciencePnasHtmlFailure(
                        "insufficient_fulltext",
                        "HTML content does not look like a complete full-text article.",
                    ),
                ),
                mock.patch.object(
                    browser_workflow,
                    "fetch_seeded_browser_pdf_payload",
                    side_effect=browser_workflow.PdfFallbackFailure(
                        "download_not_triggered",
                        "Browser PDF download was not triggered.",
                    ),
                ) as mocked_browser_pdf,
                mock.patch.object(
                    wiley_provider,
                    "_fetch_wiley_tdm_pdf_result",
                    side_effect=wiley_provider.PdfFallbackFailure(
                        "downloaded_file_not_pdf",
                        "Wiley API PDF fallback did not return a PDF file.",
                    ),
                ) as mocked_api,
            ):
                with self.assertRaises(ProviderFailure) as raised:
                    client.fetch_raw_fulltext(doi, metadata)

        mocked_browser_pdf.assert_called_once()
        mocked_api.assert_called_once()
        self.assertEqual(raised.exception.code, "no_result")
        self.assertIn("fulltext:wiley_html_fail", raised.exception.source_trail)
        self.assertIn("fulltext:wiley_pdf_browser_fail", raised.exception.source_trail)
        self.assertIn("fulltext:wiley_pdf_api_fail", raised.exception.source_trail)
        self.assertIn("Wiley browser PDF failure", raised.exception.message)
        self.assertIn("Wiley API PDF failure", raised.exception.message)

    def test_wiley_can_use_official_tdm_api_when_browser_runtime_is_not_configured(self) -> None:
        doi = WILEY_PDF_SAMPLE.doi
        metadata = {
            "doi": doi,
            "title": WILEY_PDF_SAMPLE.title,
            "landing_page_url": WILEY_PDF_SAMPLE.landing_url,
        }
        client = wiley_provider.WileyClient(
            transport=mock.Mock(),
            env={wiley_provider.WILEY_TDM_CLIENT_TOKEN_ENV_VAR: "secret"},
        )

        with (
            mock.patch.object(
                browser_workflow,
                "load_runtime_config",
                side_effect=ProviderFailure(
                    "not_configured",
                    "Wiley browser workflow is not configured.",
                    missing_env=["FLARESOLVERR_ENV_FILE"],
                ),
            ),
                mock.patch.object(
                wiley_provider,
                "_fetch_wiley_tdm_pdf_result",
                return_value=mock.Mock(
                    source_url=f"https://api.wiley.com/onlinelibrary/tdm/v1/articles/{doi}",
                    final_url=f"https://api.wiley.com/onlinelibrary/tdm/v1/articles/{doi}",
                    pdf_bytes=fulltext_pdf_bytes(),
                    markdown_text=f"# {WILEY_PDF_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                    suggested_filename="article.pdf",
                ),
            ) as mocked_api,
        ):
            raw_payload = client.fetch_raw_fulltext(doi, metadata)
            article = client.to_article_model(metadata, raw_payload)

        mocked_api.assert_called_once()
        self.assertEqual(raw_payload.metadata["route"], "pdf_fallback")
        self.assertEqual(article.source, "wiley_browser")
        self.assertIn("fulltext:wiley_pdf_api_ok", article.quality.source_trail)

    def test_wiley_tdm_api_helper_follows_redirect_to_pdf_payload(self) -> None:
        api_url = "https://api.wiley.com/onlinelibrary/tdm/v1/articles/10.1111%2Fexample"
        download_url = "https://alm.wiley.com/alm/api/v2/download/example"

        class RedirectingTransport:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str, dict[str, str]]] = []

            def request(self, method, url, *, headers=None, timeout=20, retry_on_transient=False, **kwargs):
                self.calls.append((method, url, dict(headers or {})))
                if url == api_url:
                    return {
                        "status_code": 302,
                        "headers": {"location": download_url},
                        "body": b"",
                        "url": api_url,
                    }
                if url == download_url:
                    return {
                        "status_code": 200,
                        "headers": {
                            "content-type": "application/pdf",
                            "content-disposition": 'inline; filename="example.pdf"',
                        },
                        "body": fulltext_pdf_bytes(),
                        "url": download_url,
                    }
                raise AssertionError(f"unexpected url {url}")

        transport = RedirectingTransport()
        result = wiley_provider._fetch_wiley_tdm_pdf_result(
            transport,
            api_url=api_url,
            headers={"Wiley-TDM-Client-Token": "secret"},
        )

        self.assertEqual(result.final_url, download_url)
        self.assertEqual(result.suggested_filename, "example.pdf")
        self.assertEqual(
            [call[1] for call in transport.calls],
            [api_url, download_url],
        )


if __name__ == "__main__":
    unittest.main()
