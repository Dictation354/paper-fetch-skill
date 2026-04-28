from __future__ import annotations

import base64
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch.http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, DEFAULT_TIMEOUT_SECONDS, RequestFailure
from paper_fetch.extraction.html import _assets as asset_impl
from paper_fetch.providers import _flaresolverr, browser_workflow, html_assets
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.crossref import CrossrefClient
from paper_fetch.providers.elsevier import ElsevierClient, download_elsevier_related_assets, filter_elsevier_asset_references
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


class _FakeQueuedImagePage:
    def __init__(self, results: list[dict[str, object]]) -> None:
        self.results = list(results)
        self.evaluate_calls: list[tuple[str, object]] = []

    def evaluate(self, script, arg):
        self.evaluate_calls.append((script, arg))
        if not self.results:
            raise AssertionError("No queued fake image page result")
        return self.results.pop(0)


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

    def test_browser_workflow_flaresolverr_fast_path_uses_conservative_fallback_after_challenge(self) -> None:
        doi = "10.1002/ece3.9361"
        runtime = _flaresolverr.FlareSolverrRuntimeConfig(
            provider="wiley",
            doi=doi,
            url="http://127.0.0.1:8191/v1",
            env_file=Path("/tmp/.env.flaresolverr"),
            source_dir=Path("/tmp/vendor/flaresolverr"),
            artifact_dir=Path("/tmp/artifacts"),
            headless=True,
        )
        fallback_html = _flaresolverr.FetchedPublisherHtml(
            source_url="https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
            final_url="https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
            html="<html><article>Fallback full text</article></html>",
            response_status=200,
            response_headers={"content-type": "text/html"},
            title="Example Wiley Article",
            summary="Fallback full text",
            browser_context_seed={},
        )

        client = WileyClient(transport=None, env={})
        with (
            mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
            mock.patch.object(browser_workflow, "ensure_runtime_ready"),
            mock.patch.object(
                browser_workflow,
                "fetch_html_with_flaresolverr",
                side_effect=[
                    browser_workflow.FlareSolverrFailure(
                        "cloudflare_challenge",
                        "Encountered a challenge page.",
                    ),
                    fallback_html,
                ],
            ) as mocked_fetch,
            mock.patch.object(
                browser_workflow,
                "extract_science_pnas_markdown",
                return_value=("# Example Wiley Article\n\n## Results\n\n" + ("Body text " * 120), {"title": "Example"}),
            ),
        ):
            payload = client.fetch_raw_fulltext(
                doi,
                {"doi": doi, "landing_page_url": "https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361"},
            )

        self.assertEqual(mocked_fetch.call_count, 2)
        self.assertEqual(mocked_fetch.call_args_list[0].kwargs["wait_seconds"], 0)
        self.assertEqual(mocked_fetch.call_args_list[0].kwargs["warm_wait_seconds"], 0)
        self.assertIs(mocked_fetch.call_args_list[0].kwargs["disable_media"], True)
        self.assertEqual(mocked_fetch.call_args_list[1].kwargs["wait_seconds"], 8)
        self.assertEqual(mocked_fetch.call_args_list[1].kwargs["warm_wait_seconds"], 1)
        self.assertIs(mocked_fetch.call_args_list[1].kwargs["disable_media"], False)
        self.assertEqual(payload.metadata["html_fetcher"], "flaresolverr")
        self.assertIn("fulltext:wiley_html_ok", payload.metadata["source_trail"])

    def test_browser_workflow_flaresolverr_fast_path_falls_back_after_insufficient_body(self) -> None:
        doi = "10.1002/ece3.9361"
        runtime = _flaresolverr.FlareSolverrRuntimeConfig(
            provider="wiley",
            doi=doi,
            url="http://127.0.0.1:8191/v1",
            env_file=Path("/tmp/.env.flaresolverr"),
            source_dir=Path("/tmp/vendor/flaresolverr"),
            artifact_dir=Path("/tmp/artifacts"),
            headless=True,
        )
        fast_html = _flaresolverr.FetchedPublisherHtml(
            source_url="https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
            final_url="https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
            html="<html><article>Abstract only</article></html>",
            response_status=200,
            response_headers={"content-type": "text/html"},
            title="Example Wiley Article",
            summary="Abstract only",
            browser_context_seed={},
        )
        fallback_html = _flaresolverr.FetchedPublisherHtml(
            source_url="https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
            final_url="https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
            html="<html><article>Fallback full text</article></html>",
            response_status=200,
            response_headers={"content-type": "text/html"},
            title="Example Wiley Article",
            summary="Fallback full text",
            browser_context_seed={},
        )

        client = WileyClient(transport=None, env={})
        with (
            mock.patch.object(browser_workflow, "load_runtime_config", return_value=runtime),
            mock.patch.object(browser_workflow, "ensure_runtime_ready"),
            mock.patch.object(
                browser_workflow,
                "fetch_html_with_flaresolverr",
                side_effect=[fast_html, fallback_html],
            ) as mocked_fetch,
            mock.patch.object(
                browser_workflow,
                "extract_science_pnas_markdown",
                side_effect=[
                    browser_workflow.SciencePnasHtmlFailure(
                        "insufficient_body",
                        "HTML extraction did not produce enough article body text.",
                    ),
                    ("# Example Wiley Article\n\n## Results\n\n" + ("Body text " * 120), {"title": "Example"}),
                ],
            ),
        ):
            payload = client.fetch_raw_fulltext(
                doi,
                {"doi": doi, "landing_page_url": "https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361"},
            )

        self.assertEqual(mocked_fetch.call_count, 2)
        self.assertIs(mocked_fetch.call_args_list[0].kwargs["disable_media"], True)
        self.assertIs(mocked_fetch.call_args_list[1].kwargs["disable_media"], False)
        self.assertEqual(payload.metadata["html_fetcher"], "flaresolverr")
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

    def test_html_supplementary_download_records_challenge_failure_diagnostics(self) -> None:
        transport = RecordingTransport({})
        opener_builder = mock.Mock(return_value=object())
        opener_requester = mock.Mock(
            return_value={
                "status_code": 403,
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": (
                    b"<html><head><title>Just a moment...</title></head>"
                    b"<body>Checking your browser before accessing</body></html>"
                ),
                "url": "https://example.test/supplement.pdf",
            }
        )
        file_fetcher = mock.Mock(return_value=None)
        file_fetcher.failure_for = mock.Mock(
            return_value={
                "recovery_attempts": [
                    {
                        "status": "failed",
                        "url": "https://example.test/article",
                        "reason": "cloudflare_challenge",
                    }
                ]
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = asset_impl.download_supplementary_assets(
                transport,
                article_id="10.1000/example",
                assets=[
                    {
                        "kind": "supplementary",
                        "heading": "Supplementary Data",
                        "caption": "",
                        "url": "https://example.test/supplement.pdf",
                        "section": "supplementary",
                    }
                ],
                output_dir=Path(tmpdir),
                user_agent="unit-test",
                asset_profile="all",
                file_document_fetcher=file_fetcher,
                cookie_opener_builder=opener_builder,
                opener_requester=opener_requester,
            )

        self.assertEqual(result["assets"], [])
        self.assertEqual(len(result["asset_failures"]), 1)
        self.assertEqual(result["asset_failures"][0]["reason"], "cloudflare_challenge")
        self.assertEqual(result["asset_failures"][0]["status"], 403)
        self.assertEqual(result["asset_failures"][0]["title_snippet"], "Just a moment...")
        self.assertIn("Checking your browser", result["asset_failures"][0]["body_snippet"])
        self.assertEqual(result["asset_failures"][0]["recovery_attempts"][0]["status"], "failed")

    def test_elsevier_all_asset_profile_maps_supplementary_download_to_unified_fields(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<full-text-retrieval-response xmlns="http://www.elsevier.com/xml/svapi/article/dtd" xmlns:ce="http://www.elsevier.com/xml/common/dtd">
  <attachments>
    <attachment>
      <ce:attachment-eid>mmc1</ce:attachment-eid>
      <ce:attachment-type>Supplementary</ce:attachment-type>
      <ce:filename>supplement.pdf</ce:filename>
      <ce:extension>pdf</ce:extension>
    </attachment>
  </attachments>
</full-text-retrieval-response>
"""
        opener_builder = mock.Mock(return_value=object())
        opener_requester = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "application/pdf"},
                "body": b"%PDF-1.7 supplementary",
                "url": "https://api.elsevier.com/content/object/eid/mmc1?httpAccept=%2A%2F%2A",
            }
        )

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            mock.patch.object(html_assets, "_build_cookie_seeded_opener", opener_builder),
            mock.patch.object(html_assets, "_request_with_opener", opener_requester),
        ):
            result = download_elsevier_related_assets(
                RecordingTransport({}),
                doi="10.1016/test",
                xml_body=xml_body,
                output_dir=Path(tmpdir),
                headers={"User-Agent": "unit-test", "X-ELS-APIKey": "secret"},
                asset_profile="all",
            )

        self.assertEqual(len(result["assets"]), 1)
        asset = result["assets"][0]
        self.assertEqual(asset["kind"], "supplementary")
        self.assertEqual(asset["asset_type"], "supplementary")
        self.assertEqual(asset["section"], "supplementary")
        self.assertEqual(asset["download_tier"], "supplementary_file")
        self.assertEqual(asset["source_ref"], "mmc1")
        self.assertEqual(asset["content_type"], "application/pdf")
        self.assertEqual(asset["downloaded_bytes"], len(b"%PDF-1.7 supplementary"))
        self.assertEqual(result["asset_failures"], [])

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
        self.assertEqual(
            fetcher.failure_for("https://example.test/cdn/figure.jpg")["reason"],
            "image_fetch_timeout",
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

        result = fetcher._wait_for_primary_image(page, "https://example.test/cdn/figure.jpg")

        self.assertIsNone(result)
        self.assertEqual(page.wait_for_timeout_calls, [])

    def test_playwright_image_wait_timeout_records_no_loaded_image(self) -> None:
        page = _FakeImagePage(
            {
                "ready": False,
                "imageCount": 0,
                "title": "Image viewer",
                "contentType": "text/html",
            }
        )
        fetcher = browser_workflow._SharedPlaywrightImageDocumentFetcher(
            browser_context_seed_getter=lambda: {},
            seed_urls_getter=lambda: [],
        )

        with mock.patch.object(browser_workflow.time, "monotonic", side_effect=[0.0, 16.0]):
            result = fetcher._wait_for_primary_image(page, "https://example.test/cdn/figure.jpg")

        self.assertIsNone(result)
        self.assertEqual(
            fetcher.failure_for("https://example.test/cdn/figure.jpg")["reason"],
            "no_loaded_image",
        )

    def test_playwright_image_page_fetch_records_non_image_response_reason(self) -> None:
        image_url = "https://example.test/cdn/figure.png"
        page = _FakeImagePage(
            {
                "ok": True,
                "status": 200,
                "url": image_url,
                "contentType": "text/html",
                "nonImage": True,
                "title": "Access denied",
                "bodySnippet": "<html><body>Institutional login required</body></html>",
            }
        )
        fetcher = browser_workflow._SharedPlaywrightImageDocumentFetcher(
            browser_context_seed_getter=lambda: {},
            seed_urls_getter=lambda: [],
        )

        result = fetcher._payload_from_page_fetch_url(page, image_url)

        self.assertIsNone(result)
        self.assertEqual(fetcher.failure_for(image_url)["reason"], "non_image_response")

    def test_playwright_image_payload_uses_loaded_image_when_fetch_is_challenged(self) -> None:
        image_body = b"\x89PNG\r\n\x1a\nloaded-image"
        image_url = "https://example.test/cdn/figure.png"
        page = _FakeQueuedImagePage(
            [
                {
                    "ok": True,
                    "status": 200,
                    "url": image_url,
                    "contentType": "text/html",
                    "nonImage": True,
                    "title": "Just a moment...",
                    "bodySnippet": "<title>Just a moment...</title>",
                },
                {
                    "ok": True,
                    "status": 200,
                    "url": image_url,
                    "contentType": "image/png",
                    "bodyB64": base64.b64encode(image_body).decode("ascii"),
                    "width": 500,
                    "height": 198,
                },
            ]
        )
        fetcher = browser_workflow._SharedPlaywrightImageDocumentFetcher(
            browser_context_seed_getter=lambda: {},
            seed_urls_getter=lambda: [],
        )

        result = fetcher._payload_from_page_fetch(page, {"src": image_url, "width": 500, "height": 198})

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["body"], image_body)
        self.assertEqual(result["headers"]["content-type"], "image/png")
        self.assertEqual(result["dimensions"], {"width": 500, "height": 198})
        self.assertEqual(len(page.evaluate_calls), 2)

    def test_playwright_loaded_image_canvas_failure_reasons_are_preserved(self) -> None:
        image_url = "https://example.test/cdn/figure.png"
        for reason, error in (
            ("missing_canvas_context", ""),
            ("canvas_tainted", "SecurityError"),
            ("canvas_serialization_failed", "TypeError"),
        ):
            page = _FakeImagePage(
                {
                    "ok": False,
                    "reason": reason,
                    "error": error,
                    "url": image_url,
                    "title": "Figure image",
                    "contentType": "image/png",
                }
            )
            fetcher = browser_workflow._SharedPlaywrightImageDocumentFetcher(
                browser_context_seed_getter=lambda: {},
                seed_urls_getter=lambda: [],
            )

            result = fetcher._payload_from_loaded_image(page, {"src": image_url, "width": 500, "height": 198})

            self.assertIsNone(result)
            self.assertEqual(fetcher.failure_for(image_url)["reason"], reason)

    def test_flaresolverr_image_document_payload_requires_image_payload(self) -> None:
        result = _flaresolverr.FetchedPublisherHtml(
            source_url="https://example.test/figure.png",
            final_url="https://example.test/figure.png",
            html="<html><title>figure.png (40×30)</title></html>",
            response_status=200,
            response_headers={},
            title="figure.png (40×30)",
            summary="",
            browser_context_seed={},
            screenshot_b64=base64.b64encode(b"fake-screenshot").decode("ascii"),
        )

        payload = browser_workflow._flaresolverr_image_document_payload(result)

        self.assertIsNone(payload)

    def test_flaresolverr_image_document_payload_prefers_browser_exported_pixels(self) -> None:
        image_body = b"\x89PNG\r\n\x1a\ncanvas-export"
        result = _flaresolverr.FetchedPublisherHtml(
            source_url="https://example.test/figure.png",
            final_url="https://example.test/figure.png",
            html="<html></html>",
            response_status=200,
            response_headers={},
            title="figure.png (40x30)",
            summary="",
            browser_context_seed={},
            screenshot_b64=None,
            image_payload={
                "status": 200,
                "url": "https://example.test/figure.png",
                "contentType": "image/png",
                "bodyB64": base64.b64encode(image_body).decode("ascii"),
                "width": 40,
                "height": 30,
            },
        )

        payload = browser_workflow._flaresolverr_image_document_payload(result)

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["body"], image_body)
        self.assertEqual(payload["dimensions"], {"width": 40, "height": 30})

    def test_flaresolverr_image_document_payload_rejects_invalid_payload(self) -> None:
        result = _flaresolverr.FetchedPublisherHtml(
            source_url="https://example.test/figure.png",
            final_url="https://example.test/figure.png",
            html="<html></html>",
            response_status=200,
            response_headers={},
            title="figure.png (40x30)",
            summary="",
            browser_context_seed={},
            screenshot_b64=None,
            image_payload={
                "status": 200,
                "url": "https://example.test/figure.png",
                "contentType": "text/html",
                "bodyB64": base64.b64encode(b"<html>challenge</html>").decode("ascii"),
                "width": 40,
                "height": 30,
            },
        )

        payload = browser_workflow._flaresolverr_image_document_payload(result)

        self.assertIsNone(payload)

    def test_challenge_recovery_payload_is_not_recorded_in_failure_diagnostics(self) -> None:
        image_body = b"\x89PNG\r\n\x1a\nloaded-image"
        image_url = "https://example.test/cdn/figure.png"
        fetcher = browser_workflow._SharedPlaywrightImageDocumentFetcher(
            browser_context_seed_getter=lambda: {},
            seed_urls_getter=lambda: [],
            challenge_recovery=lambda *_args: {
                "status": "ok",
                "image_payload": {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": image_body,
                    "url": image_url,
                    "dimensions": {"width": 500, "height": 198},
                },
            },
        )

        recovered = fetcher._attempt_challenge_recovery(
            image_url,
            {"kind": "figure"},
            {"reason": "cloudflare_challenge"},
        )

        self.assertTrue(recovered)
        self.assertEqual(fetcher._recovered_payload_by_url[image_url]["body"], image_body)
        self.assertNotIn("image_payload", fetcher.failure_for(image_url)["recovery_attempts"][0])

    def test_download_figure_assets_with_image_document_fetcher_runs_in_parallel_and_keeps_order(self) -> None:
        class TrackingFetcher:
            def __init__(self) -> None:
                self.lock = threading.Lock()
                self.active = 0
                self.max_active = 0

            def __call__(self, image_url: str, _asset: dict[str, object]) -> dict[str, object]:
                with self.lock:
                    self.active += 1
                    self.max_active = max(self.max_active, self.active)
                try:
                    if image_url.endswith("figure-1.png"):
                        time.sleep(0.05)
                    elif image_url.endswith("figure-2.png"):
                        time.sleep(0.02)
                    else:
                        time.sleep(0.01)
                    return {
                        "status_code": 200,
                        "headers": {"content-type": "image/png"},
                        "body": b"\x89PNG\r\n\x1a\nparallel",
                        "url": image_url,
                    }
                finally:
                    with self.lock:
                        self.active -= 1

            def failure_for(self, _image_url: str) -> dict[str, object] | None:
                return None

        fetcher = TrackingFetcher()
        assets = [
            {
                "kind": "figure",
                "heading": "Figure 1",
                "caption": "First",
                "url": "https://example.test/figure-1.png",
                "preview_url": "https://example.test/figure-1.png",
                "section": "body",
            },
            {
                "kind": "figure",
                "heading": "Figure 2",
                "caption": "Second",
                "url": "https://example.test/figure-2.png",
                "preview_url": "https://example.test/figure-2.png",
                "section": "body",
            },
            {
                "kind": "figure",
                "heading": "Figure 3",
                "caption": "Third",
                "url": "https://example.test/figure-3.png",
                "preview_url": "https://example.test/figure-3.png",
                "section": "body",
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = asset_impl.download_figure_assets_with_image_document_fetcher(
                RecordingTransport({}),
                article_id="10.1000/example",
                assets=assets,
                output_dir=Path(tmpdir),
                user_agent="unit-test",
                asset_profile="body",
                candidate_builder=lambda *_args, **kwargs: [kwargs["asset"]["url"]],
                image_document_fetcher=fetcher,
            )

        self.assertGreaterEqual(fetcher.max_active, 2)
        self.assertEqual([asset["heading"] for asset in result["assets"]], ["Figure 1", "Figure 2", "Figure 3"])

    def test_shared_playwright_file_fetcher_recovers_after_cloudflare_challenge(self) -> None:
        file_url = "https://example.test/supplement.pdf"
        article_url = "https://example.test/article"
        challenge_recovery = mock.Mock(
            return_value={
                "status": "ok",
                "url": article_url,
                "title_snippet": "Article page",
            }
        )
        fetcher = browser_workflow._build_shared_playwright_file_fetcher(
            browser_context_seed_getter=lambda: {
                "browser_cookies": [{"name": "cf_clearance", "value": "seed", "domain": ".example.test", "path": "/"}],
                "browser_user_agent": "Mozilla/5.0",
                "browser_final_url": article_url,
            },
            seed_urls_getter=lambda: [article_url],
            browser_user_agent="Mozilla/5.0",
            challenge_recovery=challenge_recovery,
        )
        fetcher._ensure_context = mock.Mock(return_value=object())
        fetcher._sync_context_cookies = mock.Mock()
        fetcher._warm_seed_urls = mock.Mock()

        def side_effect(current_url: str):
            if fetcher.failure_for(current_url) is None:
                fetcher._record_failure(
                    current_url,
                    status=403,
                    content_type="text/html; charset=UTF-8",
                    title_snippet="Just a moment...",
                    body_snippet="Just a moment...",
                    reason="cloudflare_challenge",
                )
                return None
            return {
                "status_code": 200,
                "headers": {"content-type": "application/pdf"},
                "body": b"%PDF-1.7 recovered",
                "url": current_url,
            }

        fetcher._fetch_with_context_request = mock.Mock(side_effect=side_effect)

        try:
            result = fetcher(file_url, {"kind": "supplementary", "section": "supplementary"})
        finally:
            fetcher.close()

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["body"], b"%PDF-1.7 recovered")
        challenge_recovery.assert_called_once()
        self.assertEqual(challenge_recovery.call_args.args[0], file_url)
        self.assertEqual(challenge_recovery.call_args.args[2]["status"], 403)
        self.assertEqual(fetcher._warm_seed_urls.call_args_list[0].kwargs["force"], False)
        self.assertEqual(fetcher._warm_seed_urls.call_args_list[1].kwargs["force"], True)

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
