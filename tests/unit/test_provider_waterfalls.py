from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch.providers import _flaresolverr, _science_pnas, elsevier as elsevier_provider, springer as springer_provider, wiley as wiley_provider
from paper_fetch.providers.base import ProviderFailure, RawFulltextPayload
from tests.paths import FIXTURE_DIR
from tests.unit._paper_fetch_support import fulltext_pdf_bytes


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
            min_interval_seconds=20,
            max_requests_per_hour=30,
            max_requests_per_day=200,
            rate_limit_file=tmp / "rate_limits.json",
        )

    def test_elsevier_official_xml_success_keeps_elsevier_xml_source(self) -> None:
        doi = "10.1016/j.rse.2026.115369"
        metadata = {
            "doi": doi,
            "title": "Sentinel-1 for offshore wind energy application",
            "landing_page_url": "https://www.sciencedirect.com/science/article/pii/S0034425726001030",
        }
        xml_body = (FIXTURE_DIR / "elsevier_10.1016_j.rse.2026.115369.xml").read_bytes()
        official_payload = RawFulltextPayload(
            provider="elsevier",
            source_url="https://api.elsevier.com/content/article/doi/10.1016%2Fj.rse.2026.115369",
            content_type="text/xml",
            body=xml_body,
            metadata={"route": "official", "reason": "Downloaded full text from the official Elsevier API."},
        )
        client = elsevier_provider.ElsevierClient(transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"})

        with (
            mock.patch.object(client, "_fetch_official_payload", return_value=official_payload),
            mock.patch.object(client, "_official_payload_is_usable", return_value=True),
            mock.patch.object(elsevier_provider, "load_runtime_config") as mocked_runtime,
        ):
            raw_payload = client.fetch_raw_fulltext(doi, metadata)
            article = client.to_article_model(metadata, raw_payload)

        mocked_runtime.assert_not_called()
        self.assertEqual(raw_payload.provider, "elsevier")
        self.assertEqual(article.source, "elsevier_xml")
        self.assertTrue(article.quality.has_fulltext)

    def test_elsevier_falls_back_to_browser_html(self) -> None:
        doi = "10.1016/j.browser.2026.0001"
        metadata = {
            "doi": doi,
            "title": "Elsevier Browser Article",
            "landing_page_url": "https://www.sciencedirect.com/science/article/pii/S0034425726001030",
            "fulltext_links": [],
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
            '<meta name="citation_title" content="Elsevier Browser Article" />'
            f'<meta name="citation_doi" content="{doi}" />'
            "</head><body><article><h1>Elsevier Browser Article</h1></article></body></html>"
        )
        client = elsevier_provider.ElsevierClient(transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"})

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "elsevier", doi)
            with (
                mock.patch.object(client, "_fetch_official_payload", return_value=official_payload),
                mock.patch.object(client, "_official_payload_is_usable", return_value=False),
                mock.patch.object(elsevier_provider, "load_runtime_config", return_value=runtime),
                mock.patch.object(elsevier_provider, "ensure_runtime_ready"),
                mock.patch.object(
                    elsevier_provider,
                    "fetch_html_with_flaresolverr",
                    return_value=_flaresolverr.FetchedPublisherHtml(
                        source_url=metadata["landing_page_url"],
                        final_url=metadata["landing_page_url"],
                        html=html,
                        response_status=200,
                        response_headers={"content-type": "text/html"},
                        title="Elsevier Browser Article",
                        summary="Elsevier summary",
                        browser_context_seed={},
                    ),
                ),
                mock.patch.object(
                    elsevier_provider.html_generic,
                    "extract_article_markdown",
                    return_value="# Elsevier Browser Article\n\n## Results\n\n" + ("Body text " * 120),
                ),
            ):
                raw_payload = client.fetch_raw_fulltext(doi, metadata)
                article = client.to_article_model(metadata, raw_payload)

        self.assertEqual(raw_payload.provider, "elsevier_browser")
        self.assertEqual(raw_payload.metadata["route"], "html")
        self.assertEqual(article.source, "elsevier_browser")
        self.assertIn("fulltext:elsevier_xml_fail", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_html_ok", article.quality.source_trail)

    def test_elsevier_html_challenge_stops_before_pdf_fallback(self) -> None:
        doi = "10.1016/j.browser.2026.0002"
        metadata = {
            "doi": doi,
            "title": "Elsevier Challenge Article",
            "landing_page_url": "https://www.sciencedirect.com/science/article/pii/S0034425726001030",
            "fulltext_links": [],
        }
        official_payload = RawFulltextPayload(
            provider="elsevier",
            source_url="https://api.elsevier.com/content/article/doi/example",
            content_type="text/xml",
            body=b"<xml />",
            metadata={"route": "official", "reason": "Downloaded full text from the official Elsevier API."},
        )
        client = elsevier_provider.ElsevierClient(transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"})

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "elsevier", doi)
            with (
                mock.patch.object(client, "_fetch_official_payload", return_value=official_payload),
                mock.patch.object(client, "_official_payload_is_usable", return_value=False),
                mock.patch.object(elsevier_provider, "load_runtime_config", return_value=runtime),
                mock.patch.object(elsevier_provider, "ensure_runtime_ready"),
                mock.patch.object(
                    elsevier_provider,
                    "fetch_html_with_flaresolverr",
                    side_effect=_flaresolverr.FlareSolverrFailure(
                        "cloudflare_challenge",
                        "Challenge page detected.",
                    ),
                ),
                mock.patch.object(
                    elsevier_provider,
                    "warm_browser_context_with_flaresolverr",
                    create=True,
                ) as mocked_warm,
                mock.patch.object(
                    elsevier_provider,
                    "fetch_pdf_with_playwright",
                    create=True,
                ) as mocked_pdf,
            ):
                with self.assertRaises(ProviderFailure) as ctx:
                    client.fetch_raw_fulltext(doi, metadata)

        mocked_warm.assert_not_called()
        mocked_pdf.assert_not_called()
        self.assertEqual(ctx.exception.code, "no_result")
        self.assertIn("fulltext:elsevier_xml_fail", ctx.exception.source_trail)
        self.assertIn("fulltext:elsevier_html_fail", ctx.exception.source_trail)
        self.assertIn("via XML/API or HTML", ctx.exception.message)
        self.assertNotIn("PDF fallback", ctx.exception.message)

    def test_elsevier_insufficient_html_stops_before_pdf_fallback(self) -> None:
        doi = "10.1016/j.browser.2026.0003"
        metadata = {
            "doi": doi,
            "title": "Elsevier Short HTML Article",
            "landing_page_url": "https://www.sciencedirect.com/science/article/pii/S0034425726001030",
            "fulltext_links": [],
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
            f'<meta name="citation_doi" content="{doi}" />'
            "</head><body><article><h1>Elsevier Short HTML Article</h1></article></body></html>"
        )
        client = elsevier_provider.ElsevierClient(transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"})

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "elsevier", doi)
            with (
                mock.patch.object(client, "_fetch_official_payload", return_value=official_payload),
                mock.patch.object(client, "_official_payload_is_usable", return_value=False),
                mock.patch.object(elsevier_provider, "load_runtime_config", return_value=runtime),
                mock.patch.object(elsevier_provider, "ensure_runtime_ready"),
                mock.patch.object(
                    elsevier_provider,
                    "fetch_html_with_flaresolverr",
                    return_value=_flaresolverr.FetchedPublisherHtml(
                        source_url=metadata["landing_page_url"],
                        final_url=metadata["landing_page_url"],
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
                mock.patch.object(
                    elsevier_provider,
                    "warm_browser_context_with_flaresolverr",
                    create=True,
                ) as mocked_warm,
                mock.patch.object(
                    elsevier_provider,
                    "fetch_pdf_with_playwright",
                    create=True,
                ) as mocked_pdf,
            ):
                with self.assertRaises(ProviderFailure) as ctx:
                    client.fetch_raw_fulltext(doi, metadata)

        mocked_warm.assert_not_called()
        mocked_pdf.assert_not_called()
        self.assertEqual(ctx.exception.code, "no_result")
        self.assertIn("fulltext:elsevier_xml_fail", ctx.exception.source_trail)
        self.assertIn("fulltext:elsevier_html_fail", ctx.exception.source_trail)
        self.assertIn("enough article body text", ctx.exception.message)
        self.assertNotIn("PDF fallback", ctx.exception.message)

    def test_springer_html_success_keeps_springer_html_source(self) -> None:
        doi = "10.1038/example"
        landing_url = "https://www.nature.com/articles/example"
        metadata = {
            "doi": doi,
            "title": "Nature HTML Article",
            "landing_page_url": landing_url,
            "fulltext_links": [],
        }
        response = {
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": (
                b"<html><head>"
                b'<meta name="citation_title" content="Nature HTML Article" />'
                b'<meta name="citation_doi" content="10.1038/example" />'
                b"</head><body><article><h1>Nature HTML Article</h1></article></body></html>"
            ),
            "url": landing_url,
        }
        client = springer_provider.SpringerClient(transport=mock.Mock(), env={})

        with (
            mock.patch.object(client, "_fetch_html_response", return_value=(response, landing_url)),
            mock.patch.object(
                springer_provider.html_generic,
                "extract_article_markdown",
                return_value="# Nature HTML Article\n\n## Results\n\n" + ("Body text " * 120),
            ),
            mock.patch.object(springer_provider, "fetch_pdf_over_http") as mocked_pdf,
        ):
            raw_payload = client.fetch_raw_fulltext(doi, metadata)
            article = client.to_article_model(metadata, raw_payload)

        mocked_pdf.assert_not_called()
        self.assertEqual(raw_payload.metadata["route"], "html")
        self.assertEqual(article.source, "springer_html")
        self.assertIn("fulltext:springer_html_ok", article.quality.source_trail)

    def test_springer_falls_back_to_direct_http_pdf(self) -> None:
        doi = "10.1038/example-pdf"
        landing_url = "https://www.nature.com/articles/example-pdf"
        metadata = {
            "doi": doi,
            "title": "Nature PDF Article",
            "landing_page_url": landing_url,
            "fulltext_links": [{"url": "https://www.nature.com/articles/example-pdf.pdf", "content_type": "application/pdf"}],
        }
        response = {
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": (
                b"<html><head>"
                b'<meta name="citation_title" content="Nature PDF Article" />'
                b'<meta name="citation_doi" content="10.1038/example-pdf" />'
                b'<meta name="citation_pdf_url" content="https://www.nature.com/articles/example-pdf.pdf" />'
                b"</head><body><article><h1>Nature PDF Article</h1></article></body></html>"
            ),
            "url": landing_url,
        }
        client = springer_provider.SpringerClient(transport=mock.Mock(), env={})

        with (
            mock.patch.object(client, "_fetch_html_response", return_value=(response, landing_url)),
            mock.patch.object(
                springer_provider.html_generic,
                "extract_article_markdown",
                return_value="# Nature PDF Article\n\nShort abstract only.",
            ),
            mock.patch.object(
                springer_provider,
                "fetch_pdf_over_http",
                return_value=mock.Mock(
                    source_url="https://www.nature.com/articles/example-pdf.pdf",
                    final_url="https://www.nature.com/articles/example-pdf.pdf",
                    pdf_bytes=fulltext_pdf_bytes(),
                    markdown_text="# Nature PDF Article\n\n## Results\n\n" + ("Body text " * 120),
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

    def test_wiley_uses_official_tdm_api_pdf_when_html_is_not_usable(self) -> None:
        doi = "10.1111/j.1745-4506.1980.tb00241.x"
        metadata = {
            "doi": doi,
            "title": "Classic Wiley Article",
            "landing_page_url": f"https://onlinelibrary.wiley.com/doi/{doi}",
        }
        client = wiley_provider.WileyClient(
            transport=mock.Mock(),
            env={wiley_provider.WILEY_TDM_CLIENT_TOKEN_ENV_VAR: "secret"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "wiley", doi)
            with (
                mock.patch.object(_science_pnas, "load_runtime_config", return_value=runtime),
                mock.patch.object(_science_pnas, "ensure_runtime_ready"),
                mock.patch.object(
                    _science_pnas,
                    "fetch_html_with_flaresolverr",
                    side_effect=_science_pnas.SciencePnasHtmlFailure(
                        "insufficient_fulltext",
                        "HTML content does not look like a complete full-text article.",
                    ),
                ),
                mock.patch.object(
                    wiley_provider,
                    "_fetch_wiley_tdm_pdf_result",
                    return_value=mock.Mock(
                        source_url=f"https://api.wiley.com/onlinelibrary/tdm/v1/articles/{doi}",
                        final_url=f"https://api.wiley.com/onlinelibrary/tdm/v1/articles/{doi}",
                        pdf_bytes=fulltext_pdf_bytes(),
                        markdown_text="# Classic Wiley Article\n\n## Results\n\n" + ("Body text " * 120),
                        suggested_filename="article.pdf",
                    ),
                ) as mocked_api,
                mock.patch.object(_science_pnas, "fetch_pdf_with_playwright") as mocked_browser_pdf,
            ):
                raw_payload = client.fetch_raw_fulltext(doi, metadata)
                article = client.to_article_model(metadata, raw_payload)

        mocked_api.assert_called_once()
        mocked_browser_pdf.assert_not_called()
        self.assertEqual(raw_payload.metadata["route"], "pdf_fallback")
        self.assertEqual(article.source, "wiley_browser")
        self.assertIn("fulltext:wiley_pdf_api_ok", article.quality.source_trail)
        self.assertIn("fulltext:wiley_pdf_fallback_ok", article.quality.source_trail)
        api_headers = mocked_api.call_args.kwargs["headers"]
        self.assertEqual(api_headers["Wiley-TDM-Client-Token"], "secret")

    def test_wiley_missing_tdm_token_returns_provider_failure_without_browser_pdf_attempt(self) -> None:
        doi = "10.1111/j.1745-4506.1980.tb00241.x"
        metadata = {
            "doi": doi,
            "title": "Classic Wiley Article",
            "landing_page_url": f"https://onlinelibrary.wiley.com/doi/{doi}",
        }
        client = wiley_provider.WileyClient(transport=mock.Mock(), env={})

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "wiley", doi)
            with (
                mock.patch.object(_science_pnas, "load_runtime_config", return_value=runtime),
                mock.patch.object(_science_pnas, "ensure_runtime_ready"),
                mock.patch.object(
                    _science_pnas,
                    "fetch_html_with_flaresolverr",
                    side_effect=_science_pnas.SciencePnasHtmlFailure(
                        "insufficient_fulltext",
                        "HTML content does not look like a complete full-text article.",
                    ),
                ),
                mock.patch.object(wiley_provider, "_fetch_wiley_tdm_pdf_result") as mocked_api,
                mock.patch.object(_science_pnas, "fetch_pdf_with_playwright") as mocked_browser_pdf,
            ):
                with self.assertRaises(ProviderFailure) as raised:
                    client.fetch_raw_fulltext(doi, metadata)

        mocked_api.assert_not_called()
        mocked_browser_pdf.assert_not_called()
        self.assertEqual(raised.exception.code, "no_result")
        self.assertIn("WILEY_TDM_CLIENT_TOKEN is missing", raised.exception.message)
        self.assertIn("fulltext:wiley_html_fail", raised.exception.source_trail)
        self.assertIn("fulltext:wiley_pdf_api_fail", raised.exception.source_trail)

    def test_wiley_can_use_official_tdm_api_when_browser_runtime_is_not_configured(self) -> None:
        doi = "10.1111/j.1745-4506.1980.tb00241.x"
        metadata = {
            "doi": doi,
            "title": "Classic Wiley Article",
            "landing_page_url": f"https://onlinelibrary.wiley.com/doi/{doi}",
        }
        client = wiley_provider.WileyClient(
            transport=mock.Mock(),
            env={wiley_provider.WILEY_TDM_CLIENT_TOKEN_ENV_VAR: "secret"},
        )

        with (
            mock.patch.object(
                _science_pnas,
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
                    markdown_text="# Classic Wiley Article\n\n## Results\n\n" + ("Body text " * 120),
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
