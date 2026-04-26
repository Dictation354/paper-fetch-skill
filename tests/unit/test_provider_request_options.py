from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch.http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, DEFAULT_TIMEOUT_SECONDS, RequestFailure
from paper_fetch.extraction.html import _assets as asset_impl
from paper_fetch.providers import _flaresolverr, browser_workflow, html_assets
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.crossref import CrossrefClient
from paper_fetch.providers.elsevier import ElsevierClient, filter_elsevier_asset_references
from paper_fetch.providers.springer import SpringerClient
from paper_fetch.providers.wiley import WileyClient


class RecordingTransport:
    def __init__(self, responses: dict[tuple[str, str], dict[str, object]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def request(
        self,
        method,
        url,
        *,
        headers=None,
        query=None,
        timeout=DEFAULT_TIMEOUT_SECONDS,
        retry_on_rate_limit=False,
        rate_limit_retries=1,
        max_rate_limit_wait_seconds=5,
        retry_on_transient=False,
        transient_retries=2,
        transient_backoff_base_seconds=0.5,
    ):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "query": dict(query or {}),
                "timeout": timeout,
                "retry_on_rate_limit": retry_on_rate_limit,
                "rate_limit_retries": rate_limit_retries,
                "max_rate_limit_wait_seconds": max_rate_limit_wait_seconds,
                "retry_on_transient": retry_on_transient,
                "transient_retries": transient_retries,
                "transient_backoff_base_seconds": transient_backoff_base_seconds,
            }
        )
        key = (method, url)
        if key not in self.responses:
            raise AssertionError(f"Missing fake response for {method} {url}")
        response = self.responses[key]
        if isinstance(response, Exception):
            raise response
        return response


class _FakeImagePage:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.evaluate_calls: list[tuple[str, object]] = []
        self.wait_for_timeout_calls: list[int] = []

    def evaluate(self, script, arg):
        self.evaluate_calls.append((script, arg))
        return self.result

    def wait_for_timeout(self, milliseconds: int) -> None:
        self.wait_for_timeout_calls.append(milliseconds)


class ProviderRequestOptionsTests(unittest.TestCase):
    def test_crossref_metadata_uses_default_timeout_and_rate_limit_retry(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://api.crossref.org/works/10.1234%2Fexample"): {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": json.dumps(
                        {
                            "message": {
                                "DOI": "10.1234/example",
                                "title": ["Example"],
                                "container-title": ["Journal"],
                                "publisher": "Publisher",
                                "URL": "https://example.test/article",
                            }
                        }
                    ).encode("utf-8"),
                    "url": "https://api.crossref.org/works/10.1234%2Fexample",
                }
            }
        )

        client = CrossrefClient(transport, {"CROSSREF_MAILTO": "alice@example.com"})
        metadata = client.fetch_metadata({"doi": "10.1234/example"})

        self.assertEqual(metadata["doi"], "10.1234/example")
        self.assertEqual(transport.calls[0]["timeout"], DEFAULT_TIMEOUT_SECONDS)
        self.assertTrue(transport.calls[0]["retry_on_rate_limit"])
        self.assertTrue(transport.calls[0]["retry_on_transient"])

    def test_elsevier_fulltext_uses_extended_timeout(self) -> None:
        doi = "10.1016/test"
        transport = RecordingTransport(
            {
                ("GET", "https://api.elsevier.com/content/article/doi/10.1016%2Ftest"): {
                    "status_code": 200,
                    "headers": {"content-type": "text/xml"},
                    "body": b"<xml />",
                    "url": "https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                }
            }
        )

        client = ElsevierClient(transport, {"ELSEVIER_API_KEY": "secret"})
        with mock.patch.object(client, "_official_payload_is_usable", return_value=True):
            payload = client.fetch_raw_fulltext(doi, {})

        self.assertEqual(payload.content_type, "text/xml")
        self.assertEqual(transport.calls[0]["timeout"], DEFAULT_FULLTEXT_TIMEOUT_SECONDS)
        self.assertTrue(transport.calls[0]["retry_on_rate_limit"])
        self.assertTrue(transport.calls[0]["retry_on_transient"])

    def test_springer_direct_html_fulltext_uses_extended_timeout(self) -> None:
        doi = "10.1186/1471-2105-11-421"
        transport = RecordingTransport(
            {
                ("GET", "https://www.nature.com/articles/example"): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": (
                        b"<html><head>"
                        b'<meta name="citation_title" content="Springer HTML Article" />'
                        b'<meta name="citation_doi" content="10.1186/1471-2105-11-421" />'
                        b"</head><body>"
                        b"<article><h1>Springer HTML Article</h1><h2>Introduction</h2>"
                        b"<p>"
                        + (b"Important body text. " * 200)
                        + b"</p></article></body></html>"
                    ),
                    "url": "https://www.nature.com/articles/example",
                }
            }
        )

        client = SpringerClient(transport, {})
        payload = client.fetch_raw_fulltext(doi, {"landing_page_url": "https://www.nature.com/articles/example"})

        self.assertEqual(payload.content_type, "text/html; charset=utf-8")
        self.assertEqual(transport.calls[0]["timeout"], DEFAULT_FULLTEXT_TIMEOUT_SECONDS)
        self.assertTrue(transport.calls[0]["retry_on_transient"])
        self.assertEqual(transport.calls[0]["url"], "https://www.nature.com/articles/example")

    def test_springer_direct_html_follows_http_redirects(self) -> None:
        doi = "10.1186/s13059-024-03246-2"
        transport = RecordingTransport(
            {
                ("GET", "https://genomebiology.biomedcentral.com/articles/10.1186/s13059-024-03246-2"): {
                    "status_code": 301,
                    "headers": {
                        "content-type": "text/html; charset=utf-8",
                        "location": "https://link.springer.com/article/10.1186/s13059-024-03246-2",
                    },
                    "body": b"<html><head><title>301 Moved Permanently</title></head><body>Moved</body></html>",
                    "url": "/articles/10.1186/s13059-024-03246-2",
                },
                ("GET", "https://link.springer.com/article/10.1186/s13059-024-03246-2"): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": (
                        b"<html><head>"
                        b'<meta name="citation_title" content="Single Cell Atlas" />'
                        b'<meta name="citation_doi" content="10.1186/s13059-024-03246-2" />'
                        b"</head><body>"
                        b"<article><h1>Single Cell Atlas</h1><h2>Abstract</h2>"
                        b"<p>Short abstract summary.</p><h2>Results</h2><p>"
                        + (b"Important body text. " * 200)
                        + b"</p></article></body></html>"
                    ),
                    "url": "https://link.springer.com/article/10.1186/s13059-024-03246-2",
                },
            }
        )

        client = SpringerClient(transport, {})
        payload = client.fetch_raw_fulltext(
            doi,
            {"landing_page_url": "https://genomebiology.biomedcentral.com/articles/10.1186/s13059-024-03246-2"},
        )

        self.assertEqual(payload.source_url, "https://link.springer.com/article/10.1186/s13059-024-03246-2")
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(
            [call["url"] for call in transport.calls],
            [
                "https://genomebiology.biomedcentral.com/articles/10.1186/s13059-024-03246-2",
                "https://link.springer.com/article/10.1186/s13059-024-03246-2",
            ],
        )
        self.assertTrue(all(call["retry_on_transient"] for call in transport.calls))
        self.assertTrue(all(call["timeout"] == DEFAULT_FULLTEXT_TIMEOUT_SECONDS for call in transport.calls))

    def test_wiley_browser_workflow_prefers_html_route(self) -> None:
        doi = "10.1002/ece3.9361"
        runtime = _flaresolverr.FlareSolverrRuntimeConfig(
            provider="wiley",
            doi=doi,
            url="http://127.0.0.1:8191/v1",
            env_file=Path("/tmp/.env.flaresolverr"),
            source_dir=Path("/tmp/vendor/flaresolverr"),
            artifact_dir=Path("/tmp/artifacts"),
            headless=True,
            min_interval_seconds=20,
            max_requests_per_hour=30,
            max_requests_per_day=200,
            rate_limit_file=Path("/tmp/rate_limits.json"),
        )

        client = WileyClient(transport=None, env={})
        with (
            mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
            mock.patch.object(browser_workflow, "ensure_runtime_ready"),
            mock.patch.object(
                browser_workflow,
                "fetch_html_with_flaresolverr",
                return_value=_flaresolverr.FetchedPublisherHtml(
                    source_url="https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
                    final_url="https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
                    html="<html></html>",
                    response_status=200,
                    response_headers={"content-type": "text/html"},
                    title="Example Wiley Article",
                    summary="Example summary",
                    browser_context_seed={},
                ),
            ),
            mock.patch.object(
                browser_workflow,
                "extract_science_pnas_markdown",
                return_value=("# Example Wiley Article\n\n## Results\n\n" + ("Body text " * 120), {"title": "Example"}),
            ),
            mock.patch.object(browser_workflow, "fetch_pdf_with_playwright") as mocked_pdf,
        ):
            payload = client.fetch_raw_fulltext(
                doi,
                {"doi": doi, "landing_page_url": "https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361"},
            )

        mocked_pdf.assert_not_called()
        self.assertEqual(payload.metadata["route"], "html")
        self.assertEqual(payload.content_type, "text/html")

    def test_html_asset_download_prefers_direct_full_size_url_before_preview(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://example.test/images/large/figure1.png"): {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": b"large-image",
                    "url": "https://example.test/images/large/figure1.png",
                },
                ("GET", "https://example.test/images/preview/figure1.png"): {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": b"preview-image",
                    "url": "https://example.test/images/preview/figure1.png",
                },
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_figure_assets(
                transport,
                article_id="10.1000/example",
                assets=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "caption": "Direct full-size figure",
                        "url": "https://example.test/images/large/figure1.png",
                        "preview_url": "https://example.test/images/preview/figure1.png",
                        "section": "body",
                    }
                ],
                output_dir=Path(tmpdir),
                user_agent="unit-test",
                asset_profile="body",
            )

            self.assertEqual([call["url"] for call in transport.calls], ["https://example.test/images/large/figure1.png"])
            self.assertEqual(len(result["assets"]), 1)
            self.assertEqual(Path(result["assets"][0]["path"]).read_bytes(), b"large-image")

    def test_html_asset_download_accepts_explicit_cookie_opener_injection(self) -> None:
        transport = RecordingTransport({})
        opener = object()
        opener_builder = mock.Mock(return_value=opener)
        opener_requester = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": b"injected-image",
                "url": "https://example.test/images/figure1.png",
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = asset_impl.download_figure_assets(
                transport,
                article_id="10.1000/example",
                assets=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "caption": "Injected opener",
                        "url": "https://example.test/images/figure1.png",
                        "section": "body",
                    }
                ],
                output_dir=Path(tmpdir),
                user_agent="unit-test",
                asset_profile="body",
                browser_context_seed={
                    "browser_final_url": "https://example.test/article",
                    "browser_cookies": [
                        {
                            "name": "session",
                            "value": "abc",
                            "domain": "example.test",
                            "path": "/",
                        }
                    ],
                },
                candidate_builder=lambda *_args, **_kwargs: ["https://example.test/images/figure1.png"],
                cookie_opener_builder=opener_builder,
                opener_requester=opener_requester,
            )

        opener_builder.assert_called_once()
        opener_requester.assert_called_once()
        self.assertEqual(transport.calls, [])
        self.assertEqual(result["assets"][0]["downloaded_bytes"], len(b"injected-image"))

    def test_html_asset_facade_passes_patchable_hooks_without_mutating_asset_impl_globals(self) -> None:
        transport = RecordingTransport({})
        impl_opener_builder = mock.Mock(return_value=object())
        facade_opener_builder = mock.Mock(return_value=object())
        facade_requester = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": b"facade-image",
                "url": "https://example.test/images/figure1.png",
            }
        )

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            mock.patch.object(asset_impl, "_build_cookie_seeded_opener", impl_opener_builder),
            mock.patch.object(html_assets, "_build_cookie_seeded_opener", facade_opener_builder),
            mock.patch.object(html_assets, "_request_with_opener", facade_requester),
        ):
            result = html_assets.download_figure_assets(
                transport,
                article_id="10.1000/example",
                assets=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "caption": "Facade opener",
                        "url": "https://example.test/images/figure1.png",
                        "section": "body",
                    }
                ],
                output_dir=Path(tmpdir),
                user_agent="unit-test",
                asset_profile="body",
                browser_context_seed={
                    "browser_cookies": [
                        {
                            "name": "session",
                            "value": "abc",
                            "domain": "example.test",
                            "path": "/",
                        }
                    ],
                },
                candidate_builder=lambda *_args, **_kwargs: ["https://example.test/images/figure1.png"],
            )

        impl_opener_builder.assert_not_called()
        facade_opener_builder.assert_called_once()
        facade_requester.assert_called_once()
        self.assertEqual(result["assets"][0]["downloaded_bytes"], len(b"facade-image"))

    def test_playwright_image_page_fetch_is_abortable_and_does_not_cache_challenge_pages(self) -> None:
        page = _FakeImagePage({"ok": False, "error": "AbortError", "timedOut": True})
        fetcher = browser_workflow._SharedPlaywrightImageDocumentFetcher(
            browser_context_seed_getter=lambda: {},
            seed_urls_getter=lambda: [],
        )

        result = fetcher._payload_from_page_fetch_url(page, "https://example.test/cdn/figure.jpg")

        self.assertIsNone(result)
        script, arg = page.evaluate_calls[0]
        self.assertIn("AbortController", script)
        self.assertIn("cache: 'no-store'", script)
        self.assertEqual(
            arg,
            ["https://example.test/cdn/figure.jpg", browser_workflow._IMAGE_DOCUMENT_FETCH_TIMEOUT_MS],
        )

    def test_playwright_image_wait_stops_immediately_on_cloudflare_challenge_title(self) -> None:
        page = _FakeImagePage(
            {
                "ready": False,
                "imageCount": 0,
                "title": "Just a moment...",
                "contentType": "text/html",
            }
        )
        fetcher = browser_workflow._SharedPlaywrightImageDocumentFetcher(
            browser_context_seed_getter=lambda: {},
            seed_urls_getter=lambda: [],
        )

        result = fetcher._wait_for_primary_image(page)

        self.assertIsNone(result)
        self.assertEqual(page.wait_for_timeout_calls, [])

    def test_html_asset_download_uses_figure_page_full_size_before_preview(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://example.test/figures/figure-1"): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": (
                        b"<html><head>"
                        b"<meta property='og:image' content='https://example.test/images/original/figure1.png' />"
                        b"</head><body></body></html>"
                    ),
                    "url": "https://example.test/figures/figure-1",
                },
                ("GET", "https://example.test/images/original/figure1.png"): {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": b"original-image",
                    "url": "https://example.test/images/original/figure1.png",
                },
                ("GET", "https://example.test/images/preview/figure1.png"): {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": b"preview-image",
                    "url": "https://example.test/images/preview/figure1.png",
                },
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_figure_assets(
                transport,
                article_id="10.1000/example",
                assets=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "caption": "Figure page full-size",
                        "url": "https://example.test/images/preview/figure1.png",
                        "figure_page_url": "https://example.test/figures/figure-1",
                        "section": "body",
                    }
                ],
                output_dir=Path(tmpdir),
                user_agent="unit-test",
                asset_profile="body",
            )

            self.assertEqual(
                [call["url"] for call in transport.calls],
                [
                    "https://example.test/figures/figure-1",
                    "https://example.test/images/original/figure1.png",
                ],
            )
            self.assertEqual(Path(result["assets"][0]["path"]).read_bytes(), b"original-image")

    def test_html_asset_download_falls_back_to_preview_when_full_size_fetch_fails(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://example.test/figures/figure-1"): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": (
                        b"<html><head>"
                        b"<meta property='og:image' content='https://example.test/images/original/figure1.png' />"
                        b"</head><body></body></html>"
                    ),
                    "url": "https://example.test/figures/figure-1",
                },
                ("GET", "https://example.test/images/original/figure1.png"): RequestFailure(
                    403,
                    "Forbidden",
                    url="https://example.test/images/original/figure1.png",
                ),
                ("GET", "https://example.test/images/preview/figure1.png"): {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": b"preview-image",
                    "url": "https://example.test/images/preview/figure1.png",
                },
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_figure_assets(
                transport,
                article_id="10.1000/example",
                assets=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "caption": "Preview fallback",
                        "url": "https://example.test/images/preview/figure1.png",
                        "figure_page_url": "https://example.test/figures/figure-1",
                        "section": "body",
                    }
                ],
                output_dir=Path(tmpdir),
                user_agent="unit-test",
                asset_profile="body",
            )

            self.assertEqual(
                [call["url"] for call in transport.calls],
                [
                    "https://example.test/figures/figure-1",
                    "https://example.test/images/original/figure1.png",
                    "https://example.test/images/preview/figure1.png",
                ],
            )
            self.assertEqual(len(result["assets"]), 1)
            self.assertEqual(result["asset_failures"], [])
            self.assertEqual(Path(result["assets"][0]["path"]).read_bytes(), b"preview-image")

    def test_springer_body_asset_profile_ignores_supplementary_download_pdf_links(self) -> None:
        figure_url = "https://media.springernature.com/full/example-figure-1.png"
        transport = RecordingTransport(
            {
                ("GET", figure_url): {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": b"springer-figure-1",
                    "url": figure_url,
                }
            }
        )
        client = SpringerClient(transport, {})
        raw_payload = RawFulltextPayload(
            provider="springer",
            source_url="https://link.springer.com/article/10.1000/example",
            content_type="text/html",
            body=b"<html></html>",
            content=ProviderContent(
                route_kind="html",
                source_url="https://link.springer.com/article/10.1000/example",
                content_type="text/html",
                body=b"<html></html>",
                extracted_assets=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "caption": "Body figure",
                        "url": figure_url,
                        "section": "body",
                    },
                    {
                        "kind": "supplementary",
                        "heading": "Download PDF",
                        "caption": "",
                        "url": "https://link.springer.com/content/pdf/10.1000/example.pdf",
                        "section": "supplementary",
                    },
                ],
                merged_metadata={"doi": "10.1000/example"},
            ),
            merged_metadata={"doi": "10.1000/example"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = client.download_related_assets(
                "10.1000/example",
                {"doi": "10.1000/example", "title": "Example"},
                raw_payload,
                Path(tmpdir),
                asset_profile="body",
            )
            saved_path = Path(result["assets"][0]["path"])
            saved_bytes = saved_path.read_bytes()

        self.assertEqual([call["url"] for call in transport.calls], [figure_url])
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["assets"][0]["kind"], "figure")
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(saved_bytes, b"springer-figure-1")

    def test_elsevier_body_asset_profile_excludes_appendix_and_supplementary(self) -> None:
        references = [
            {"asset_type": "image", "source_ref": "fx1"},
            {"asset_type": "table_asset", "source_ref": "tx1"},
            {"asset_type": "appendix_image", "source_ref": "app1"},
            {"asset_type": "supplementary", "source_ref": "sup1"},
            {"asset_type": "graphical_abstract", "source_ref": "ga1"},
        ]

        filtered = filter_elsevier_asset_references(references, asset_profile="body")

        self.assertEqual(
            [reference["asset_type"] for reference in filtered],
            ["image", "table_asset"],
        )

if __name__ == "__main__":
    unittest.main()
