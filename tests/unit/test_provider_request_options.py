from __future__ import annotations

import base64
import inspect
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch.http import (
    DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    RequestFailure,
)
from paper_fetch.extraction.html import assets as html_assets
from paper_fetch.extraction.html.assets import download as asset_impl
from paper_fetch.providers import browser_runtime, browser_workflow
from paper_fetch.providers.browser_workflow import fetchers as browser_fetchers
from paper_fetch.providers.browser_workflow.fetchers import context as fetcher_context
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.crossref import CrossrefClient
from paper_fetch.providers.elsevier import (
    ElsevierClient,
    download_elsevier_related_assets,
    filter_elsevier_asset_references,
)
from paper_fetch.providers.springer import SpringerClient
from paper_fetch.providers.wiley import WileyClient
from paper_fetch.runtime import RuntimeContext
from tests.unit._browser_workflow_deps import browser_workflow_deps
from tests.unit._paper_fetch_support import RecordingTransport


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


def png_body(label: bytes) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + label


def elsevier_body_asset_xml(urls: list[str]) -> bytes:
    return (
        b"<?xml version='1.0'?><full-text-retrieval-response>"
        + b"".join(
            (
                f"<object type='IMAGE-HIGH-RES' mimetype='image/png' ref='fig{index}'>"
                f"{url}</object>"
            ).encode()
            for index, url in enumerate(urls)
        )
        + b"</full-text-retrieval-response>"
    )


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

    def test_crossref_bibliographic_search_can_filter_by_doi_prefix(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://api.crossref.org/works"): {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": json.dumps(
                        {
                            "message": {
                                "items": [
                                    {
                                        "DOI": "10.1088/example",
                                        "title": ["IOP Example"],
                                        "container-title": ["Journal"],
                                        "publisher": "IOP Publishing",
                                        "URL": "https://iopscience.iop.org/article/10.1088/example",
                                    }
                                ]
                            }
                        }
                    ).encode("utf-8"),
                    "url": "https://api.crossref.org/works",
                }
            }
        )

        client = CrossrefClient(transport, {"CROSSREF_MAILTO": "alice@example.com"})
        candidates = client.search_bibliographic_candidates(
            "IOP table article",
            doi_prefix="10.1088/",
            rows=3,
        )

        self.assertEqual(candidates[0]["doi"], "10.1088/example")
        self.assertEqual(transport.calls[0]["query"]["filter"], "prefix:10.1088")
        self.assertEqual(transport.calls[0]["query"]["rows"], "3")
        self.assertEqual(
            transport.calls[0]["query"]["query.bibliographic"],
            "IOP table article",
        )

    def test_elsevier_fulltext_uses_extended_timeout(self) -> None:
        doi = "10.1016/test"
        transport = RecordingTransport(
            {
                (
                    "GET",
                    "https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                ): {
                    "status_code": 200,
                    "headers": {"content-type": "text/xml"},
                    "body": b"<xml />",
                    "url": "https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                }
            }
        )

        legacy_elsevier_env = {
            f"ELSEVIER_{name}": "ignored"
            for name in ("INSTTOKEN", "AUTHTOKEN", "CLICKTHROUGH_TOKEN")
        }
        client = ElsevierClient(
            transport, {"ELSEVIER_API_KEY": "secret", **legacy_elsevier_env}
        )
        with mock.patch.object(
            client, "_official_payload_is_usable", return_value=True
        ):
            payload = client.fetch_raw_fulltext(doi, {})

        self.assertEqual(payload.content_type, "text/xml")
        self.assertEqual(transport.calls[0]["headers"]["X-ELS-APIKey"], "secret")
        self.assertNotIn("X-ELS-" + "Insttoken", transport.calls[0]["headers"])
        self.assertNotIn("Authorization", transport.calls[0]["headers"])
        self.assertNotIn(
            "CR-" + "Clickthrough-Client-Token", transport.calls[0]["headers"]
        )
        self.assertEqual(
            transport.calls[0]["timeout"], DEFAULT_FULLTEXT_TIMEOUT_SECONDS
        )
        self.assertTrue(transport.calls[0]["retry_on_rate_limit"])
        self.assertTrue(transport.calls[0]["retry_on_transient"])

    def test_elsevier_metadata_can_resolve_sciencedirect_pii(self) -> None:
        pii = "S0959378017300134"
        url = f"https://api.elsevier.com/content/abstract/pii/{pii}"
        transport = RecordingTransport(
            {
                ("GET", url): {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": json.dumps(
                        {
                            "abstracts-retrieval-response": {
                                "coredata": {
                                    "prism:doi": "10.1016/j.gloenvcha.2017.01.002",
                                    "dc:title": "Trees, forests and water",
                                    "prism:publicationName": "Global Environmental Change",
                                    "dc:publisher": "Elsevier",
                                    "prism:coverDate": "2017-03-01",
                                }
                            }
                        }
                    ).encode("utf-8"),
                    "url": f"{url}?view=META_ABS",
                }
            }
        )
        client = ElsevierClient(transport, {"ELSEVIER_API_KEY": "secret"})

        metadata = client.fetch_metadata({"doi": None, "pii": pii})

        self.assertEqual(metadata["doi"], "10.1016/j.gloenvcha.2017.01.002")
        self.assertEqual(metadata["pii"], pii)
        self.assertEqual(metadata["title"], "Trees, forests and water")
        self.assertEqual(transport.calls[0]["url"], url)
        self.assertEqual(transport.calls[0]["query"], {"view": "META_ABS"})
        self.assertEqual(transport.calls[0]["headers"]["Accept"], "application/json")

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
        payload = client.fetch_raw_fulltext(
            doi, {"landing_page_url": "https://www.nature.com/articles/example"}
        )

        self.assertEqual(payload.content_type, "text/html; charset=utf-8")
        self.assertEqual(
            transport.calls[0]["timeout"], DEFAULT_FULLTEXT_TIMEOUT_SECONDS
        )
        self.assertTrue(transport.calls[0]["retry_on_transient"])
        self.assertEqual(
            transport.calls[0]["url"], "https://www.nature.com/articles/example"
        )

    def test_springer_direct_html_follows_http_redirects(self) -> None:
        doi = "10.1186/s13059-024-03246-2"
        transport = RecordingTransport(
            {
                (
                    "GET",
                    "https://genomebiology.biomedcentral.com/articles/10.1186/s13059-024-03246-2",
                ): {
                    "status_code": 301,
                    "headers": {
                        "content-type": "text/html; charset=utf-8",
                        "location": "https://link.springer.com/article/10.1186/s13059-024-03246-2",
                    },
                    "body": b"<html><head><title>301 Moved Permanently</title></head><body>Moved</body></html>",
                    "url": "/articles/10.1186/s13059-024-03246-2",
                },
                (
                    "GET",
                    "https://link.springer.com/article/10.1186/s13059-024-03246-2",
                ): {
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
            {
                "landing_page_url": "https://genomebiology.biomedcentral.com/articles/10.1186/s13059-024-03246-2"
            },
        )

        self.assertEqual(
            payload.source_url,
            "https://link.springer.com/article/10.1186/s13059-024-03246-2",
        )
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(
            [call["url"] for call in transport.calls],
            [
                "https://genomebiology.biomedcentral.com/articles/10.1186/s13059-024-03246-2",
                "https://link.springer.com/article/10.1186/s13059-024-03246-2",
            ],
        )
        self.assertTrue(all(call["retry_on_transient"] for call in transport.calls))
        self.assertTrue(
            all(
                call["timeout"] == DEFAULT_FULLTEXT_TIMEOUT_SECONDS
                for call in transport.calls
            )
        )

    def test_wiley_browser_workflow_prefers_html_route(self) -> None:
        doi = "10.1002/ece3.9361"
        runtime = browser_runtime.BrowserRuntimeConfig(
            provider="wiley",
            doi=doi,
            artifact_dir=Path("/tmp/artifacts"),
            headless=True,
            user_agent="paper-fetch-test/1",
        )

        mocked_pdf = mock.Mock()
        deps = browser_workflow_deps(
            load_runtime_config=mock.Mock(return_value=runtime),
            ensure_runtime_ready=mock.Mock(),
            fetch_html_with_browser=mock.Mock(
                return_value=browser_runtime.BrowserFetchedHtml(
                    source_url="https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
                    final_url="https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
                    html="<html></html>",
                    response_status=200,
                    response_headers={"content-type": "text/html"},
                    title="Example Wiley Article",
                    summary="Example summary",
                    browser_context_seed={},
                )
            ),
            extract_atypon_browser_workflow_markdown=mock.Mock(
                return_value=(
                    "# Example Wiley Article\n\n## Results\n\n" + ("Body text " * 120),
                    {"title": "Example"},
                )
            ),
            fetch_pdf_with_browser=mocked_pdf,
        )
        client = WileyClient(transport=None, env={}, deps=deps)
        payload = client.fetch_raw_fulltext(
            doi,
            {
                "doi": doi,
                "landing_page_url": "https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
            },
        )

        mocked_pdf.assert_not_called()
        self.assertIsNotNone(payload.content)
        assert payload.content is not None
        self.assertEqual(payload.content.route_kind, "html")
        self.assertEqual(payload.content_type, "text/html")

    def test_browser_workflow_fast_path_uses_conservative_fallback_after_challenge(
        self,
    ) -> None:
        doi = "10.1002/ece3.9361"
        runtime = browser_runtime.BrowserRuntimeConfig(
            provider="wiley",
            doi=doi,
            artifact_dir=Path("/tmp/artifacts"),
            headless=True,
            user_agent="paper-fetch-test/1",
        )
        fallback_html = browser_runtime.BrowserFetchedHtml(
            source_url="https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
            final_url="https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
            html="<html><article>Fallback full text</article></html>",
            response_status=200,
            response_headers={"content-type": "text/html"},
            title="Example Wiley Article",
            summary="Fallback full text",
            browser_context_seed={},
        )

        mocked_fetch = mock.Mock(
            side_effect=[
                browser_runtime.BrowserRuntimeFailure(
                    "cloudflare_challenge",
                    "Encountered a challenge page.",
                ),
                fallback_html,
            ]
        )
        deps = browser_workflow_deps(
            load_runtime_config=mock.Mock(return_value=runtime),
            ensure_runtime_ready=mock.Mock(),
            fetch_html_with_browser=mocked_fetch,
            extract_atypon_browser_workflow_markdown=mock.Mock(
                return_value=(
                    "# Example Wiley Article\n\n## Results\n\n" + ("Body text " * 120),
                    {"title": "Example"},
                )
            ),
        )
        client = WileyClient(transport=None, env={}, deps=deps)
        payload = client.fetch_raw_fulltext(
            doi,
            {
                "doi": doi,
                "landing_page_url": "https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
            },
        )

        self.assertEqual(mocked_fetch.call_count, 2)
        self.assertEqual(mocked_fetch.call_args_list[0].kwargs["wait_seconds"], 0)
        self.assertEqual(mocked_fetch.call_args_list[0].kwargs["warm_wait_seconds"], 0)
        self.assertIs(mocked_fetch.call_args_list[0].kwargs["disable_media"], True)
        self.assertEqual(mocked_fetch.call_args_list[1].kwargs["wait_seconds"], 8)
        self.assertEqual(mocked_fetch.call_args_list[1].kwargs["warm_wait_seconds"], 1)
        self.assertIs(mocked_fetch.call_args_list[1].kwargs["disable_media"], False)
        self.assertIsNotNone(payload.content)
        assert payload.content is not None
        self.assertEqual(payload.content.fetcher, "cloakbrowser")
        self.assertIn(
            "fulltext:wiley_html_ok",
            [event.marker() for event in payload.trace if event.marker()],
        )

    def test_browser_workflow_fast_path_falls_back_after_insufficient_body(
        self,
    ) -> None:
        doi = "10.1002/ece3.9361"
        runtime = browser_runtime.BrowserRuntimeConfig(
            provider="wiley",
            doi=doi,
            artifact_dir=Path("/tmp/artifacts"),
            headless=True,
            user_agent="paper-fetch-test/1",
        )
        fast_html = browser_runtime.BrowserFetchedHtml(
            source_url="https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
            final_url="https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
            html="<html><article>Abstract only</article></html>",
            response_status=200,
            response_headers={"content-type": "text/html"},
            title="Example Wiley Article",
            summary="Abstract only",
            browser_context_seed={},
        )
        fallback_html = browser_runtime.BrowserFetchedHtml(
            source_url="https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
            final_url="https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
            html="<html><article>Fallback full text</article></html>",
            response_status=200,
            response_headers={"content-type": "text/html"},
            title="Example Wiley Article",
            summary="Fallback full text",
            browser_context_seed={},
        )

        mocked_fetch = mock.Mock(side_effect=[fast_html, fallback_html])
        deps = browser_workflow_deps(
            load_runtime_config=mock.Mock(return_value=runtime),
            ensure_runtime_ready=mock.Mock(),
            fetch_html_with_browser=mocked_fetch,
            extract_atypon_browser_workflow_markdown=mock.Mock(
                side_effect=[
                    browser_workflow.HtmlExtractionFailure(
                        "insufficient_body",
                        "HTML extraction did not produce enough article body text.",
                    ),
                    (
                        "# Example Wiley Article\n\n## Results\n\n"
                        + ("Body text " * 120),
                        {"title": "Example"},
                    ),
                ]
            ),
        )
        client = WileyClient(transport=None, env={}, deps=deps)
        payload = client.fetch_raw_fulltext(
            doi,
            {
                "doi": doi,
                "landing_page_url": "https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
            },
        )

        self.assertEqual(mocked_fetch.call_count, 2)
        self.assertIs(mocked_fetch.call_args_list[0].kwargs["disable_media"], True)
        self.assertIs(mocked_fetch.call_args_list[1].kwargs["disable_media"], False)
        self.assertIsNotNone(payload.content)
        assert payload.content is not None
        self.assertEqual(payload.content.fetcher, "cloakbrowser")
        self.assertEqual(payload.content_type, "text/html")

    def test_html_asset_download_prefers_direct_full_size_url_before_preview(
        self,
    ) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://example.test/images/large/figure1.png"): {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": png_body(b"large-image"),
                    "url": "https://example.test/images/large/figure1.png",
                },
                ("GET", "https://example.test/images/preview/figure1.png"): {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": png_body(b"preview-image"),
                    "url": "https://example.test/images/preview/figure1.png",
                },
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_assets(
                html_assets.FIGURE_KIND,
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

            self.assertEqual(
                [call["url"] for call in transport.calls],
                ["https://example.test/images/large/figure1.png"],
            )
            self.assertEqual(len(result["assets"]), 1)
            self.assertEqual(
                Path(result["assets"][0]["path"]).read_bytes(), png_body(b"large-image")
            )

    def test_html_asset_download_accepts_explicit_cookie_opener_injection(self) -> None:
        transport = RecordingTransport({})
        opener = object()
        opener_builder = mock.Mock(return_value=opener)
        opener_requester = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": png_body(b"injected-image"),
                "url": "https://example.test/images/figure1.png",
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = asset_impl.download_assets(
                asset_impl.FIGURE_KIND,
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
                candidate_builder=lambda *_args, **_kwargs: [
                    "https://example.test/images/figure1.png"
                ],
                cookie_opener_builder=opener_builder,
                opener_requester=opener_requester,
            )

        opener_builder.assert_called_once()
        opener_requester.assert_called_once()
        self.assertEqual(transport.calls, [])
        self.assertEqual(
            result["assets"][0]["downloaded_bytes"], len(png_body(b"injected-image"))
        )

    def test_html_asset_downloads_pass_patchable_hooks_without_mutating_asset_impl_globals(
        self,
    ) -> None:
        transport = RecordingTransport({})
        impl_opener_builder = mock.Mock(return_value=object())
        facade_opener_builder = mock.Mock(return_value=object())
        facade_requester = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": png_body(b"facade-image"),
                "url": "https://example.test/images/figure1.png",
            }
        )

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            mock.patch.object(
                asset_impl, "_build_cookie_seeded_opener", impl_opener_builder
            ),
            mock.patch.object(
                html_assets, "_build_cookie_seeded_opener", facade_opener_builder
            ),
            mock.patch.object(html_assets, "_request_with_opener", facade_requester),
        ):
            result = html_assets.download_assets(
                html_assets.FIGURE_KIND,
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
                candidate_builder=lambda *_args, **_kwargs: [
                    "https://example.test/images/figure1.png"
                ],
            )

        impl_opener_builder.assert_not_called()
        facade_opener_builder.assert_called_once()
        facade_requester.assert_called_once()
        self.assertEqual(
            result["assets"][0]["downloaded_bytes"], len(png_body(b"facade-image"))
        )

    def test_html_supplementary_download_records_challenge_failure_diagnostics(
        self,
    ) -> None:
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
                "reason": "cloudflare_challenge",
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = asset_impl.download_assets(
                asset_impl.SUPPLEMENTARY_KIND,
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
        self.assertEqual(
            result["asset_failures"][0]["title_snippet"], "Just a moment..."
        )
        self.assertIn(
            "Checking your browser", result["asset_failures"][0]["body_snippet"]
        )
        self.assertNotIn("recovery_attempts", result["asset_failures"][0])

    def test_elsevier_all_asset_profile_maps_supplementary_download_to_unified_fields(
        self,
    ) -> None:
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
            mock.patch.object(
                html_assets, "_build_cookie_seeded_opener", opener_builder
            ),
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

    def test_elsevier_body_asset_download_uses_runtime_asset_concurrency_env(
        self,
    ) -> None:
        urls = [
            f"https://api.elsevier.com/content/object/eid/fig{index}"
            for index in range(3)
        ]
        xml_body = (
            b"<?xml version='1.0'?><full-text-retrieval-response>"
            + b"".join(
                (
                    f"<object type='IMAGE-HIGH-RES' mimetype='image/png' ref='fig{index}'>"
                    f"{url}</object>"
                ).encode()
                for index, url in enumerate(urls)
            )
            + b"</full-text-retrieval-response>"
        )
        state = {"active": 0, "max_active": 0}
        lock = threading.Lock()

        class DelayedRecordingTransport(RecordingTransport):
            def request(self, method, url, **kwargs):
                with lock:
                    state["active"] += 1
                    state["max_active"] = max(state["max_active"], state["active"])
                try:
                    time.sleep(0.01)
                    return {
                        "status_code": 200,
                        "headers": {"content-type": "image/png"},
                        "body": f"payload:{url}".encode(),
                        "url": url,
                    }
                finally:
                    with lock:
                        state["active"] -= 1

        transport = DelayedRecordingTransport({})
        context = RuntimeContext(
            env={"PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY": "1"},
            transport=transport,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_elsevier_related_assets(
                transport,
                doi="10.1016/test",
                xml_body=xml_body,
                output_dir=Path(tmpdir),
                headers={"User-Agent": "unit-test", "X-ELS-APIKey": "secret"},
                asset_profile="body",
                context=context,
            )

        self.assertEqual(state["max_active"], 1)
        self.assertEqual([asset["download_url"] for asset in result["assets"]], urls)
        self.assertEqual(result["asset_failures"], [])

    def test_elsevier_body_asset_transient_failure_is_retried_once_and_removed(
        self,
    ) -> None:
        urls = [
            f"https://api.elsevier.com/content/object/eid/fig{index}"
            for index in range(4)
        ]
        failed_url = urls[2]
        transport = RecordingTransport(
            {
                ("GET", urls[0]): {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": png_body(b"fig0"),
                    "url": urls[0],
                },
                ("GET", urls[1]): {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": png_body(b"fig1"),
                    "url": urls[1],
                },
                ("GET", failed_url): [
                    RequestFailure(
                        None, "Network error: timed out", error_category="timeout"
                    ),
                    {
                        "status_code": 200,
                        "headers": {"content-type": "image/png"},
                        "body": png_body(b"fig2-retry"),
                        "url": failed_url,
                    },
                ],
                ("GET", urls[3]): {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": png_body(b"fig3"),
                    "url": urls[3],
                },
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_elsevier_related_assets(
                transport,
                doi="10.1016/test",
                xml_body=elsevier_body_asset_xml(urls),
                output_dir=Path(tmpdir),
                headers={"User-Agent": "unit-test", "X-ELS-APIKey": "secret"},
                asset_profile="body",
            )

        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(len(result["assets"]), 4)
        self.assertEqual(
            [asset["download_url"] for asset in result["assets"]],
            [urls[0], urls[1], urls[3], urls[2]],
        )
        self.assertEqual([call["url"] for call in transport.calls].count(failed_url), 2)

    def test_elsevier_body_asset_http_status_failure_is_not_retried(self) -> None:
        url = "https://api.elsevier.com/content/object/eid/fig0"
        transport = RecordingTransport(
            {
                ("GET", url): RequestFailure(
                    403, "HTTP 403 for Elsevier object", url=url
                ),
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_elsevier_related_assets(
                transport,
                doi="10.1016/test",
                xml_body=elsevier_body_asset_xml([url]),
                output_dir=Path(tmpdir),
                headers={"User-Agent": "unit-test", "X-ELS-APIKey": "secret"},
                asset_profile="body",
            )

        self.assertEqual(result["assets"], [])
        self.assertEqual(len(result["asset_failures"]), 1)
        self.assertEqual(result["asset_failures"][0]["status"], 403)
        self.assertEqual([call["url"] for call in transport.calls], [url])

    def test_elsevier_body_asset_retry_failure_replaces_initial_failure(self) -> None:
        url = "https://api.elsevier.com/content/object/eid/fig0"
        transport = RecordingTransport(
            {
                ("GET", url): [
                    RequestFailure(
                        None, "Network error: timed out", error_category="timeout"
                    ),
                    RequestFailure(
                        None,
                        "connection reset by peer",
                        error_category="connection_reset",
                    ),
                ],
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_elsevier_related_assets(
                transport,
                doi="10.1016/test",
                xml_body=elsevier_body_asset_xml([url]),
                output_dir=Path(tmpdir),
                headers={"User-Agent": "unit-test", "X-ELS-APIKey": "secret"},
                asset_profile="body",
            )

        self.assertEqual(result["assets"], [])
        self.assertEqual(len(result["asset_failures"]), 1)
        self.assertIn("connection reset", result["asset_failures"][0]["reason"])
        self.assertEqual(
            result["asset_failures"][0]["error_category"], "connection_reset"
        )
        self.assertEqual([call["url"] for call in transport.calls], [url, url])

    def test_elsevier_body_asset_retry_successes_are_appended_in_reference_order(
        self,
    ) -> None:
        urls = [
            f"https://api.elsevier.com/content/object/eid/fig{index}"
            for index in range(4)
        ]
        transport = RecordingTransport(
            {
                ("GET", urls[0]): [
                    RequestFailure(
                        None, "Network error: timed out", error_category="timeout"
                    ),
                    {
                        "status_code": 200,
                        "headers": {"content-type": "image/png"},
                        "body": png_body(b"fig0-retry"),
                        "url": urls[0],
                    },
                ],
                ("GET", urls[1]): {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": png_body(b"fig1"),
                    "url": urls[1],
                },
                ("GET", urls[2]): [
                    RequestFailure(
                        None,
                        "temporary failure in name resolution",
                        error_category="dns_error",
                    ),
                    {
                        "status_code": 200,
                        "headers": {"content-type": "image/png"},
                        "body": png_body(b"fig2-retry"),
                        "url": urls[2],
                    },
                ],
                ("GET", urls[3]): {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": png_body(b"fig3"),
                    "url": urls[3],
                },
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_elsevier_related_assets(
                transport,
                doi="10.1016/test",
                xml_body=elsevier_body_asset_xml(urls),
                output_dir=Path(tmpdir),
                headers={"User-Agent": "unit-test", "X-ELS-APIKey": "secret"},
                asset_profile="body",
            )

        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(
            [asset["download_url"] for asset in result["assets"]],
            [urls[1], urls[3], urls[0], urls[2]],
        )

    def test_browser_image_page_fetch_is_abortable_and_does_not_cache_challenge_pages(
        self,
    ) -> None:
        page = _FakeImagePage({"ok": False, "error": "AbortError", "timedOut": True})
        fetcher = browser_fetchers._SharedBrowserImageDocumentFetcher(
            browser_context_seed_getter=lambda: {},
            seed_urls_getter=lambda: [],
        )

        result = fetcher._payload_from_page_fetch_url(
            page, "https://example.test/cdn/figure.jpg"
        )

        self.assertIsNone(result)
        script, arg = page.evaluate_calls[0]
        self.assertIn("AbortController", script)
        self.assertIn("cache: 'no-store'", script)
        self.assertEqual(
            arg,
            [
                "https://example.test/cdn/figure.jpg",
                browser_workflow._IMAGE_DOCUMENT_FETCH_TIMEOUT_MS,
            ],
        )
        self.assertEqual(
            fetcher.failure_for("https://example.test/cdn/figure.jpg")["reason"],
            "image_fetch_timeout",
        )

    def test_no_direct_sync_playwright_in_fetchers(self) -> None:
        self.assertNotIn("sync_playwright(", inspect.getsource(fetcher_context))

    def test_failure_diagnostic_uses_browser_reason(self) -> None:
        image_url = "https://example.test/context-error.png"
        fetcher = browser_fetchers._build_shared_browser_image_fetcher(
            browser_context_seed_getter=lambda: {
                "browser_user_agent": "UnitTestAgent/1.0"
            },
            seed_urls_getter=lambda: [],
            browser_user_agent="UnitTestAgent/1.0",
            use_runtime_shared_browser=False,
        )

        try:
            with mock.patch.object(
                fetcher_context,
                "_new_browser_context",
                side_effect=RuntimeError("browser context already active"),
            ):
                result = fetcher(image_url, {"kind": "figure"})
        finally:
            fetcher.close()

        failure = fetcher.failure_for(image_url)
        self.assertIsNone(result)
        self.assertIsNotNone(failure)
        assert failure is not None
        self.assertEqual(failure["reason"], browser_fetchers.BROWSER_CONTEXT_ERROR)
        self.assertEqual(failure["error_type"], "RuntimeError")
        self.assertEqual(failure["error_message"], "browser context already active")

    def test_browser_image_wait_stops_immediately_on_cloudflare_challenge_title(
        self,
    ) -> None:
        page = _FakeImagePage(
            {
                "ready": False,
                "imageCount": 0,
                "title": "Just a moment...",
                "contentType": "text/html",
            }
        )
        fetcher = browser_fetchers._SharedBrowserImageDocumentFetcher(
            browser_context_seed_getter=lambda: {},
            seed_urls_getter=lambda: [],
        )

        result = fetcher._wait_for_primary_image(
            page, "https://example.test/cdn/figure.jpg"
        )

        self.assertIsNone(result)
        self.assertEqual(page.wait_for_timeout_calls, [])

    def test_browser_image_wait_timeout_records_no_loaded_image(self) -> None:
        page = _FakeImagePage(
            {
                "ready": False,
                "imageCount": 0,
                "title": "Image viewer",
                "contentType": "text/html",
            }
        )
        fetcher = browser_fetchers._SharedBrowserImageDocumentFetcher(
            browser_context_seed_getter=lambda: {},
            seed_urls_getter=lambda: [],
        )

        with mock.patch.object(
            browser_workflow.time, "monotonic", side_effect=[0.0, 16.0]
        ):
            result = fetcher._wait_for_primary_image(
                page, "https://example.test/cdn/figure.jpg"
            )

        self.assertIsNone(result)
        self.assertEqual(
            fetcher.failure_for("https://example.test/cdn/figure.jpg")["reason"],
            "no_loaded_image",
        )

    def test_browser_image_page_fetch_records_non_image_response_reason(self) -> None:
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
        fetcher = browser_fetchers._SharedBrowserImageDocumentFetcher(
            browser_context_seed_getter=lambda: {},
            seed_urls_getter=lambda: [],
        )

        result = fetcher._payload_from_page_fetch_url(page, image_url)

        self.assertIsNone(result)
        self.assertEqual(fetcher.failure_for(image_url)["reason"], "non_image_response")

    def test_browser_image_fetcher_prefers_warmed_article_image_before_direct_request(
        self,
    ) -> None:
        image_body = png_body(b"article-page-image")
        image_url = "https://example.test/cdn/figure.png"
        page = _FakeImagePage(
            {
                "ok": True,
                "found": True,
                "status": 200,
                "url": image_url,
                "contentType": "image/png",
                "bodyB64": base64.b64encode(image_body).decode("ascii"),
                "width": 640,
                "height": 480,
            }
        )
        fetcher = browser_fetchers._SharedBrowserImageDocumentFetcher(
            browser_context_seed_getter=lambda: {},
            seed_urls_getter=lambda: [],
        )
        fetcher._page = page

        with (
            mock.patch.object(
                fetcher,
                "_payload_from_context_request",
                side_effect=AssertionError("direct request should not run"),
            ),
            mock.patch.object(
                fetcher,
                "_payload_from_page_fetch_url",
                side_effect=AssertionError("page fetch should not run"),
            ),
        ):
            result = fetcher._fetch_with_page(image_url)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["body"], image_body)
        self.assertEqual(result["headers"]["content-type"], "image/png")
        self.assertEqual(result["dimensions"], {"width": 640, "height": 480})
        self.assertEqual(len(page.evaluate_calls), 1)

    def test_browser_image_fetcher_falls_back_when_warmed_article_lacks_target(
        self,
    ) -> None:
        image_url = "https://example.test/cdn/figure.png"
        direct_payload = {
            "status_code": 200,
            "headers": {"content-type": "image/png"},
            "body": png_body(b"direct-image"),
            "url": image_url,
            "dimensions": {"width": 320, "height": 240},
        }
        page = _FakeImagePage(
            {
                "ok": False,
                "found": False,
                "reason": "target_image_not_found",
                "url": image_url,
                "title": "Article",
                "contentType": "text/html",
                "imageCount": 4,
            }
        )
        fetcher = browser_fetchers._SharedBrowserImageDocumentFetcher(
            browser_context_seed_getter=lambda: {},
            seed_urls_getter=lambda: [],
        )
        fetcher._page = page

        with (
            mock.patch.object(
                fetcher,
                "_payload_from_page_fetch_url",
                return_value=None,
            ) as mocked_page_fetch,
            mock.patch.object(
                fetcher,
                "_payload_from_context_request",
                return_value=direct_payload,
            ) as mocked_direct,
        ):
            result = fetcher._fetch_with_page(image_url)

        self.assertEqual(result, direct_payload)
        mocked_page_fetch.assert_called_once_with(page, image_url)
        mocked_direct.assert_called_once_with(image_url)
        self.assertEqual(fetcher.failure_for(image_url), None)

    def test_browser_image_fetcher_fetches_unloaded_article_target_from_page_context(
        self,
    ) -> None:
        image_body = png_body(b"article-page-fetch-image")
        image_url = "https://example.test/cdn/figure.png"
        page = _FakeQueuedImagePage(
            [
                {
                    "ok": False,
                    "found": True,
                    "reason": "target_image_not_loaded",
                    "url": image_url,
                    "width": 570,
                    "height": 820,
                    "title": "Article",
                    "contentType": "text/html",
                },
                {
                    "ok": True,
                    "status": 200,
                    "url": image_url,
                    "contentType": "image/png;charset=UTF-8",
                    "bodyB64": base64.b64encode(image_body).decode("ascii"),
                },
            ]
        )
        fetcher = browser_fetchers._SharedBrowserImageDocumentFetcher(
            browser_context_seed_getter=lambda: {},
            seed_urls_getter=lambda: [],
        )

        result = fetcher._payload_from_warmed_article_image(page, image_url)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["body"], image_body)
        self.assertEqual(result["headers"]["content-type"], "image/png;charset=UTF-8")
        self.assertEqual(result["dimensions"], {"width": 570, "height": 820})
        self.assertEqual(len(page.evaluate_calls), 2)

    def test_browser_image_fetcher_records_challenge_from_article_page_fetch(
        self,
    ) -> None:
        image_url = "https://example.test/cdn/figure.png"
        page = _FakeQueuedImagePage(
            [
                {
                    "ok": False,
                    "found": True,
                    "reason": "target_image_not_loaded",
                    "url": image_url,
                    "width": 0,
                    "height": 0,
                    "title": "Article",
                    "contentType": "text/html",
                },
                {
                    "ok": True,
                    "status": 403,
                    "url": image_url,
                    "contentType": "text/html",
                    "nonImage": True,
                    "title": "Just a moment...",
                    "bodySnippet": "<title>Just a moment...</title>",
                },
            ]
        )
        fetcher = browser_fetchers._SharedBrowserImageDocumentFetcher(
            browser_context_seed_getter=lambda: {},
            seed_urls_getter=lambda: [],
        )

        result = fetcher._payload_from_warmed_article_image(page, image_url)

        self.assertIsNone(result)
        self.assertEqual(
            fetcher.failure_for(image_url)["reason"], "cloudflare_challenge"
        )

    def test_browser_image_payload_uses_loaded_image_when_fetch_is_challenged(
        self,
    ) -> None:
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
        fetcher = browser_fetchers._SharedBrowserImageDocumentFetcher(
            browser_context_seed_getter=lambda: {},
            seed_urls_getter=lambda: [],
        )

        result = fetcher._payload_from_page_fetch(
            page, {"src": image_url, "width": 500, "height": 198}
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["body"], image_body)
        self.assertEqual(result["headers"]["content-type"], "image/png")
        self.assertEqual(result["dimensions"], {"width": 500, "height": 198})
        self.assertEqual(len(page.evaluate_calls), 2)

    def test_browser_loaded_image_canvas_failure_reasons_are_preserved(self) -> None:
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
            fetcher = browser_fetchers._SharedBrowserImageDocumentFetcher(
                browser_context_seed_getter=lambda: {},
                seed_urls_getter=lambda: [],
            )

            result = fetcher._payload_from_loaded_image(
                page, {"src": image_url, "width": 500, "height": 198}
            )

            self.assertIsNone(result)
            self.assertEqual(fetcher.failure_for(image_url)["reason"], reason)

    def test_browser_image_document_payload_requires_image_payload(self) -> None:
        result = browser_runtime.BrowserFetchedHtml(
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

        payload = browser_fetchers._browser_image_document_payload(result)

        self.assertIsNone(payload)

    def test_browser_image_document_payload_prefers_browser_exported_pixels(
        self,
    ) -> None:
        image_body = b"\x89PNG\r\n\x1a\ncanvas-export"
        result = browser_runtime.BrowserFetchedHtml(
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

        payload = browser_fetchers._browser_image_document_payload(result)

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["body"], image_body)
        self.assertEqual(payload["dimensions"], {"width": 40, "height": 30})

    def test_browser_image_document_payload_rejects_invalid_payload(self) -> None:
        result = browser_runtime.BrowserFetchedHtml(
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

        payload = browser_fetchers._browser_image_document_payload(result)

        self.assertIsNone(payload)

    def test_browser_image_document_payload_accepts_svg_payload(self) -> None:
        svg_body = b"\xef\xbb\xbf\n<?xml version='1.0'?><svg xmlns='http://www.w3.org/2000/svg'></svg>"
        result = browser_runtime.BrowserFetchedHtml(
            source_url="https://example.test/figure.svg",
            final_url="https://example.test/figure.svg",
            html=svg_body.decode("utf-8-sig"),
            response_status=200,
            response_headers={"content-type": "image/svg+xml"},
            title="figure.svg",
            summary="",
            browser_context_seed={},
            screenshot_b64=None,
            image_payload={
                "status": 200,
                "url": "https://example.test/figure.svg",
                "contentType": "image/svg+xml",
                "bodyB64": base64.b64encode(svg_body).decode("ascii"),
                "width": 0,
                "height": 0,
            },
        )

        payload = browser_fetchers._browser_image_document_payload(result)

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["headers"]["content-type"], "image/svg+xml")
        self.assertEqual(payload["body"], svg_body)

    def test_browser_image_document_payload_rejects_svg_content_type_with_html_body(
        self,
    ) -> None:
        result = browser_runtime.BrowserFetchedHtml(
            source_url="https://example.test/figure.svg",
            final_url="https://example.test/figure.svg",
            html="<html><title>Just a moment...</title></html>",
            response_status=403,
            response_headers={"content-type": "text/html"},
            title="Just a moment...",
            summary="",
            browser_context_seed={},
            screenshot_b64=None,
            image_payload={
                "status": 403,
                "url": "https://example.test/figure.svg",
                "contentType": "image/svg+xml",
                "bodyB64": base64.b64encode(b"<html>challenge</html>").decode("ascii"),
            },
        )

        payload = browser_fetchers._browser_image_document_payload(result)

        self.assertIsNone(payload)

    def test_browser_image_fetcher_records_challenge_failure_without_recovery(
        self,
    ) -> None:
        image_url = "https://example.test/cdn/figure.png"
        fetcher = browser_fetchers._SharedBrowserImageDocumentFetcher(
            browser_context_seed_getter=lambda: {},
            seed_urls_getter=lambda: [],
        )
        fetcher._ensure_page = mock.Mock(return_value=object())
        fetcher._sync_context_cookies = mock.Mock()
        fetcher._warm_seed_urls = mock.Mock()
        fetcher._fetch_with_page = mock.Mock(
            side_effect=lambda current_url: (
                fetcher._record_failure(
                    current_url,
                    status=403,
                    content_type="text/html; charset=UTF-8",
                    title_snippet="Just a moment...",
                    body_snippet="Just a moment...",
                    reason="cloudflare_challenge",
                )
                or None
            )
        )

        try:
            result = fetcher(image_url, {"kind": "figure"})
        finally:
            fetcher.close()

        self.assertIsNone(result)
        self.assertEqual(fetcher._fetch_with_page.call_count, 2)
        failure = fetcher.failure_for(image_url)
        assert failure is not None
        self.assertEqual(failure["reason"], "cloudflare_challenge")
        self.assertNotIn("recovery_attempts", failure)

    def test_download_assets_figure_kind_with_image_document_fetcher_runs_in_parallel_and_keeps_order(
        self,
    ) -> None:
        class TrackingFetcher:
            def __init__(self) -> None:
                self.lock = threading.Lock()
                self.active = 0
                self.max_active = 0

            def __call__(
                self, image_url: str, _asset: dict[str, object]
            ) -> dict[str, object]:
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
            result = asset_impl.download_assets(
                asset_impl.FIGURE_KIND,
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
        self.assertEqual(
            [asset["heading"] for asset in result["assets"]],
            ["Figure 1", "Figure 2", "Figure 3"],
        )

    def test_download_assets_figure_kind_with_image_document_fetcher_runs_single_asset_in_worker_thread(
        self,
    ) -> None:
        image_url = "https://example.test/single-figure.png"
        main_thread_id = threading.get_ident()
        thread_ids: list[int] = []

        def fetcher(current_url: str, _asset: dict[str, object]) -> dict[str, object]:
            thread_ids.append(threading.get_ident())
            return {
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": b"\x89PNG\r\n\x1a\nsingle-worker",
                "url": current_url,
            }

        fetcher.failure_for = lambda _image_url: None  # type: ignore[attr-defined]
        assets = [
            {
                "kind": "figure",
                "heading": "Figure 1",
                "caption": "Single",
                "url": image_url,
                "preview_url": image_url,
                "section": "body",
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = asset_impl.download_assets(
                asset_impl.FIGURE_KIND,
                RecordingTransport({}),
                article_id="10.1000/example",
                assets=assets,
                output_dir=Path(tmpdir),
                user_agent="unit-test",
                asset_profile="body",
                candidate_builder=lambda *_args, **kwargs: [kwargs["asset"]["url"]],
                image_document_fetcher=fetcher,
                asset_download_concurrency=1,
            )

        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(len(thread_ids), 1)
        self.assertNotEqual(thread_ids[0], main_thread_id)

    def test_download_assets_figure_kind_with_caller_thread_fetcher_stays_on_caller_thread(
        self,
    ) -> None:
        image_url = "https://example.test/runtime-shared-figure.png"
        main_thread_id = threading.get_ident()

        class CallerThreadFetcher:
            requires_caller_thread = True

            def __init__(self) -> None:
                self.thread_ids: list[int] = []

            def __call__(
                self, current_url: str, _asset: dict[str, object]
            ) -> dict[str, object]:
                self.thread_ids.append(threading.get_ident())
                return {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": b"\x89PNG\r\n\x1a\ncaller-thread",
                    "url": current_url,
                }

            def failure_for(self, _image_url: str) -> dict[str, object] | None:
                return None

        fetcher = CallerThreadFetcher()
        assets = [
            {
                "kind": "figure",
                "heading": "Figure 1",
                "caption": "Caller thread",
                "url": image_url,
                "preview_url": image_url,
                "section": "body",
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = asset_impl.download_assets(
                asset_impl.FIGURE_KIND,
                RecordingTransport({}),
                article_id="10.1000/example",
                assets=assets,
                output_dir=Path(tmpdir),
                user_agent="unit-test",
                asset_profile="body",
                candidate_builder=lambda *_args, **kwargs: [kwargs["asset"]["url"]],
                image_document_fetcher=fetcher,
                asset_download_concurrency=4,
            )

        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(fetcher.thread_ids, [main_thread_id])

    def test_download_assets_figure_kind_with_image_document_fetcher_single_asset_survives_main_thread_conflict(
        self,
    ) -> None:
        image_url = "https://example.test/browser-conflict.png"

        class MainThreadFailingFetcher:
            def __init__(self) -> None:
                self.main_thread_id = threading.get_ident()
                self.thread_ids: list[int] = []
                self.failed_on_main_thread = False

            def __call__(
                self, current_url: str, _asset: dict[str, object]
            ) -> dict[str, object] | None:
                current_thread_id = threading.get_ident()
                self.thread_ids.append(current_thread_id)
                if current_thread_id == self.main_thread_id:
                    self.failed_on_main_thread = True
                    return None
                return {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": b"\x89PNG\r\n\x1a\nworker-success",
                    "url": current_url,
                }

            def failure_for(self, _image_url: str) -> dict[str, object] | None:
                if not self.failed_on_main_thread:
                    return None
                return {
                    "reason": "browser_context_error",
                    "error_type": "RuntimeError",
                    "error_message": "browser context already active",
                }

        fetcher = MainThreadFailingFetcher()
        assets = [
            {
                "kind": "figure",
                "heading": "Figure 1",
                "caption": "Conflict",
                "url": image_url,
                "preview_url": image_url,
                "section": "body",
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = asset_impl.download_assets(
                asset_impl.FIGURE_KIND,
                RecordingTransport({}),
                article_id="10.1000/example",
                assets=assets,
                output_dir=Path(tmpdir),
                user_agent="unit-test",
                asset_profile="body",
                candidate_builder=lambda *_args, **kwargs: [kwargs["asset"]["url"]],
                image_document_fetcher=fetcher,
                asset_download_concurrency=1,
            )

        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(len(result["assets"]), 1)
        self.assertFalse(fetcher.failed_on_main_thread)
        self.assertTrue(fetcher.thread_ids)
        self.assertNotEqual(fetcher.thread_ids[0], fetcher.main_thread_id)

    def test_download_assets_figure_kind_with_image_document_fetcher_preserves_context_error_diagnostic(
        self,
    ) -> None:
        image_url = "https://example.test/context-error.png"

        class FailingFetcher:
            def __call__(
                self, _image_url: str, _asset: dict[str, object]
            ) -> dict[str, object] | None:
                return None

            def failure_for(self, _image_url: str) -> dict[str, object]:
                return {
                    "reason": "browser_context_error",
                    "error_type": "RuntimeError",
                    "error_message": "browser context already active",
                }

        assets = [
            {
                "kind": "figure",
                "heading": "Figure 1",
                "caption": "Context error",
                "url": image_url,
                "preview_url": image_url,
                "section": "body",
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = asset_impl.download_assets(
                asset_impl.FIGURE_KIND,
                RecordingTransport({}),
                article_id="10.1000/example",
                assets=assets,
                output_dir=Path(tmpdir),
                user_agent="unit-test",
                asset_profile="body",
                candidate_builder=lambda *_args, **kwargs: [kwargs["asset"]["url"]],
                image_document_fetcher=FailingFetcher(),
                asset_download_concurrency=1,
            )

        self.assertEqual(len(result["asset_failures"]), 1)
        failure = result["asset_failures"][0]
        self.assertEqual(failure["reason"], "browser_context_error")
        self.assertEqual(failure["error_type"], "RuntimeError")
        self.assertEqual(failure["error_message"], "browser context already active")

    def test_download_assets_figure_kind_with_image_document_fetcher_saves_svg_payload(
        self,
    ) -> None:
        svg_body = (
            b"<svg xmlns='http://www.w3.org/2000/svg'><path d='M0 0h1v1H0z'/></svg>"
        )
        image_url = "https://example.test/figure.svg"

        def fetcher(_image_url: str, _asset: dict[str, object]) -> dict[str, object]:
            return {
                "status_code": 200,
                "headers": {"content-type": "image/svg+xml"},
                "body": svg_body,
                "url": image_url,
            }

        assets = [
            {
                "kind": "figure",
                "heading": "Figure SVG",
                "caption": "Vector figure",
                "url": image_url,
                "preview_url": image_url,
                "section": "body",
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = asset_impl.download_assets(
                asset_impl.FIGURE_KIND,
                RecordingTransport({}),
                article_id="10.1000/example",
                assets=assets,
                output_dir=Path(tmpdir),
                user_agent="unit-test",
                asset_profile="body",
                candidate_builder=lambda *_args, **kwargs: [kwargs["asset"]["url"]],
                image_document_fetcher=fetcher,
            )

            saved_path = Path(result["assets"][0]["path"])
            saved_body = saved_path.read_bytes()

        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["assets"][0]["content_type"], "image/svg+xml")
        self.assertEqual(saved_path.suffix, ".svg")
        self.assertEqual(saved_body, svg_body)

    def test_browser_workflow_asset_downloads_pass_runtime_asset_concurrency_env(
        self,
    ) -> None:
        doi = "10.1126/science.assets"
        runtime = browser_runtime.BrowserRuntimeConfig(
            provider="science",
            doi=doi,
            artifact_dir=Path("/tmp/artifacts"),
            headless=True,
            user_agent="paper-fetch-test/1",
        )
        raw_payload = RawFulltextPayload(
            provider="science",
            source_url="https://www.science.org/doi/full/10.1126/science.assets",
            content_type="text/html",
            body=b"<html></html>",
            content=ProviderContent(
                route_kind="html",
                source_url="https://www.science.org/doi/full/10.1126/science.assets",
                content_type="text/html",
                body=b"<html></html>",
                browser_context_seed={
                    "browser_final_url": "https://www.science.org/doi/full/10.1126/science.assets"
                },
            ),
        )
        mocked_download_assets = mock.Mock(
            return_value={"assets": [], "asset_failures": []}
        )
        deps = browser_workflow_deps(
            load_runtime_config=mock.Mock(return_value=runtime),
            ensure_runtime_ready=mock.Mock(),
            _cached_browser_workflow_assets=mock.Mock(
                return_value=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "url": "https://example.test/figure.png",
                        "section": "body",
                    },
                    {
                        "kind": "supplementary",
                        "heading": "Supplement 1",
                        "url": "https://example.test/supplement.pdf",
                        "section": "supplementary",
                    },
                ]
            ),
            download_assets=mocked_download_assets,
        )
        client = browser_workflow.BrowserWorkflowClient(
            RecordingTransport({}), {}, deps=deps
        )
        client.name = "science"

        with tempfile.TemporaryDirectory() as tmpdir:
            result = client.download_related_assets(
                doi,
                {"doi": doi, "title": "Asset Concurrency"},
                raw_payload,
                Path(tmpdir),
                asset_profile="body",
                context=RuntimeContext(
                    env={"PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY": "6"}
                ),
            )

        self.assertEqual(result, {"assets": [], "asset_failures": []})
        self.assertEqual(
            [
                call.kwargs["asset_download_concurrency"]
                for call in mocked_download_assets.call_args_list
            ],
            [6, 6],
        )
        self.assertEqual(
            [call.args[0] for call in mocked_download_assets.call_args_list],
            [html_assets.FIGURE_KIND, html_assets.SUPPLEMENTARY_KIND],
        )

    def test_browser_workflow_external_cdp_asset_downloads_are_serial(self) -> None:
        doi = "10.1126/science.assets"
        runtime = browser_runtime.BrowserRuntimeConfig(
            provider="science",
            doi=doi,
            artifact_dir=Path("/tmp/artifacts"),
            headless=True,
            user_agent="paper-fetch-test/1",
            cdp_endpoint="ws://127.0.0.1:9222/devtools/browser/test",
        )
        raw_payload = RawFulltextPayload(
            provider="science",
            source_url="https://www.science.org/doi/full/10.1126/science.assets",
            content_type="text/html",
            body=b"<html></html>",
            content=ProviderContent(
                route_kind="html",
                source_url="https://www.science.org/doi/full/10.1126/science.assets",
                content_type="text/html",
                body=b"<html></html>",
                browser_context_seed={
                    "browser_final_url": "https://www.science.org/doi/full/10.1126/science.assets"
                },
            ),
        )
        mocked_download_assets = mock.Mock(
            return_value={"assets": [], "asset_failures": []}
        )
        deps = browser_workflow_deps(
            load_runtime_config=mock.Mock(return_value=runtime),
            ensure_runtime_ready=mock.Mock(),
            _cached_browser_workflow_assets=mock.Mock(
                return_value=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "url": "https://example.test/figure.png",
                        "section": "body",
                    },
                    {
                        "kind": "supplementary",
                        "heading": "Supplement 1",
                        "url": "https://example.test/supplement.pdf",
                        "section": "supplementary",
                    },
                ]
            ),
            download_assets=mocked_download_assets,
        )
        client = browser_workflow.BrowserWorkflowClient(
            RecordingTransport({}), {}, deps=deps
        )
        client.name = "science"

        with tempfile.TemporaryDirectory() as tmpdir:
            result = client.download_related_assets(
                doi,
                {"doi": doi, "title": "Asset Concurrency"},
                raw_payload,
                Path(tmpdir),
                asset_profile="body",
                context=RuntimeContext(
                    env={"PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY": "6"}
                ),
            )

        self.assertEqual(result, {"assets": [], "asset_failures": []})
        self.assertEqual(
            [
                call.kwargs["asset_download_concurrency"]
                for call in mocked_download_assets.call_args_list
            ],
            [1, 1],
        )
        self.assertEqual(
            [call.args[0] for call in mocked_download_assets.call_args_list],
            [html_assets.FIGURE_KIND, html_assets.SUPPLEMENTARY_KIND],
        )

    def test_shared_browser_file_fetcher_records_cloudflare_challenge_without_recovery(
        self,
    ) -> None:
        file_url = "https://example.test/supplement.pdf"
        article_url = "https://example.test/article"
        fetcher = browser_fetchers._build_shared_browser_file_fetcher(
            browser_context_seed_getter=lambda: {
                "browser_cookies": [
                    {
                        "name": "cf_clearance",
                        "value": "seed",
                        "domain": ".example.test",
                        "path": "/",
                    }
                ],
                "browser_user_agent": "Mozilla/5.0",
                "browser_final_url": article_url,
            },
            seed_urls_getter=lambda: [article_url],
            browser_user_agent="Mozilla/5.0",
        )
        fetcher._ensure_context = mock.Mock(return_value=object())
        fetcher._sync_context_cookies = mock.Mock()
        fetcher._warm_seed_urls = mock.Mock()

        def side_effect(current_url: str, _asset: object):
            fetcher._record_failure(
                current_url,
                status=403,
                content_type="text/html; charset=UTF-8",
                title_snippet="Just a moment...",
                body_snippet="Just a moment...",
                reason="cloudflare_challenge",
            )
            return None

        fetcher._fetch_with_context_request = mock.Mock(side_effect=side_effect)

        try:
            result = fetcher(
                file_url, {"kind": "supplementary", "section": "supplementary"}
            )
        finally:
            fetcher.close()

        self.assertIsNone(result)
        self.assertEqual(
            fetcher._warm_seed_urls.call_args_list[0].kwargs["force"], False
        )
        self.assertEqual(
            fetcher._warm_seed_urls.call_args_list[1].kwargs["force"], True
        )
        self.assertEqual(fetcher._fetch_with_context_request.call_count, 2)
        failure = fetcher.failure_for(file_url)
        assert failure is not None
        self.assertEqual(failure["reason"], "cloudflare_challenge")
        self.assertNotIn("recovery_attempts", failure)

    def test_html_asset_download_uses_figure_page_full_size_before_preview(
        self,
    ) -> None:
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
                    "body": png_body(b"original-image"),
                    "url": "https://example.test/images/original/figure1.png",
                },
                ("GET", "https://example.test/images/preview/figure1.png"): {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": png_body(b"preview-image"),
                    "url": "https://example.test/images/preview/figure1.png",
                },
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_assets(
                html_assets.FIGURE_KIND,
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
            self.assertEqual(
                Path(result["assets"][0]["path"]).read_bytes(),
                png_body(b"original-image"),
            )

    def test_html_asset_download_falls_back_to_preview_when_full_size_fetch_fails(
        self,
    ) -> None:
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
                (
                    "GET",
                    "https://example.test/images/original/figure1.png",
                ): RequestFailure(
                    403,
                    "Forbidden",
                    url="https://example.test/images/original/figure1.png",
                ),
                ("GET", "https://example.test/images/preview/figure1.png"): {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": png_body(b"preview-image"),
                    "url": "https://example.test/images/preview/figure1.png",
                },
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_assets(
                html_assets.FIGURE_KIND,
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
            self.assertEqual(
                Path(result["assets"][0]["path"]).read_bytes(),
                png_body(b"preview-image"),
            )

    def test_html_asset_download_retries_seeded_full_size_before_preview(self) -> None:
        large_url = "https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932570/garg1-large.gif"
        preview_url = "https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932570/garg1-small.gif"
        landing_url = "https://ieeexplore.ieee.org/document/10932570/"
        opener_builder = mock.Mock(side_effect=[object(), object()])
        requested_urls: list[str] = []

        def opener_requester(opener, url, **kwargs):
            del opener
            requested_urls.append(url)
            self.assertEqual(kwargs["headers"]["Referer"], landing_url)
            if len(requested_urls) == 1:
                raise RequestFailure(403, "Forbidden", url=url)
            return {
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": png_body(b"large-after-seed-refresh"),
                "url": url,
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_assets(
                html_assets.FIGURE_KIND,
                RecordingTransport({}),
                article_id="10.1109/example",
                assets=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "caption": "Seeded full-size retry",
                        "url": large_url,
                        "full_size_url": large_url,
                        "preview_url": preview_url,
                        "section": "body",
                    }
                ],
                output_dir=Path(tmpdir),
                user_agent="unit-test",
                asset_profile="body",
                headers={"Referer": landing_url},
                seed_urls=[landing_url],
                cookie_opener_builder=opener_builder,
                opener_requester=opener_requester,
                asset_download_concurrency=1,
            )
            saved_bytes = Path(result["assets"][0]["path"]).read_bytes()

        self.assertEqual(requested_urls, [large_url, large_url])
        self.assertEqual(opener_builder.call_count, 2)
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["assets"][0]["download_tier"], "full_size")
        self.assertEqual(result["assets"][0]["full_size_url"], large_url)
        self.assertEqual(result["assets"][0]["preview_url"], preview_url)
        self.assertEqual(result["assets"][0]["original_url"], large_url)
        self.assertEqual(saved_bytes, png_body(b"large-after-seed-refresh"))

    def test_html_asset_download_preserves_mapping_when_seeded_preview_fallback_succeeds(
        self,
    ) -> None:
        large_url = "https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932570/garg2-large.gif"
        preview_url = "https://ieeexplore.ieee.org/mediastore/IEEE/content/media/10932570/garg2-small.gif"
        landing_url = "https://ieeexplore.ieee.org/document/10932570/"
        opener_builder = mock.Mock(side_effect=[object(), object(), object()])
        requested_urls: list[str] = []

        def opener_requester(opener, url, **kwargs):
            del opener
            requested_urls.append(url)
            self.assertEqual(kwargs["headers"]["Referer"], landing_url)
            if len(requested_urls) == 1:
                raise RequestFailure(403, "Forbidden", url=url)
            if len(requested_urls) == 2:
                return {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": b"<html><title>Access denied</title></html>",
                    "url": url,
                }
            return {
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": png_body(b"preview-after-full-size-failure"),
                "url": url,
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_assets(
                html_assets.FIGURE_KIND,
                RecordingTransport({}),
                article_id="10.1109/example",
                assets=[
                    {
                        "kind": "figure",
                        "heading": "Figure 2",
                        "caption": "Preview fallback after seeded retry",
                        "url": large_url,
                        "full_size_url": large_url,
                        "preview_url": preview_url,
                        "section": "body",
                    }
                ],
                output_dir=Path(tmpdir),
                user_agent="unit-test",
                asset_profile="body",
                headers={"Referer": landing_url},
                seed_urls=[landing_url],
                cookie_opener_builder=opener_builder,
                opener_requester=opener_requester,
                asset_download_concurrency=1,
            )
            saved_bytes = Path(result["assets"][0]["path"]).read_bytes()

        self.assertEqual(requested_urls, [large_url, large_url, preview_url])
        self.assertEqual(opener_builder.call_count, 3)
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["assets"][0]["download_tier"], "preview")
        self.assertEqual(result["assets"][0]["full_size_url"], large_url)
        self.assertEqual(result["assets"][0]["preview_url"], preview_url)
        self.assertEqual(result["assets"][0]["original_url"], large_url)
        self.assertEqual(result["assets"][0]["download_url"], preview_url)
        self.assertEqual(saved_bytes, png_body(b"preview-after-full-size-failure"))

    def test_html_asset_download_preserves_provider_preview_acceptance_hint(
        self,
    ) -> None:
        preview_url = "https://content.cld.iop.org/journals/example/f1_online.jpg"
        transport = RecordingTransport(
            {
                ("GET", preview_url): {
                    "status_code": 200,
                    "headers": {"content-type": "image/jpeg"},
                    "body": b"\xff\xd8\xff\xd9",
                    "url": preview_url,
                }
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_assets(
                html_assets.FIGURE_KIND,
                transport,
                article_id="10.1088/example",
                assets=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "caption": "Provider accepted preview figure",
                        "url": preview_url,
                        "preview_url": preview_url,
                        "preview_accepted": True,
                        "section": "body",
                    }
                ],
                output_dir=Path(tmpdir),
                user_agent="unit-test",
                asset_profile="body",
            )

        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["assets"][0]["download_tier"], "preview")
        self.assertTrue(result["assets"][0]["preview_accepted"])

    def test_springer_body_asset_profile_ignores_supplementary_download_pdf_links(
        self,
    ) -> None:
        figure_url = "https://media.springernature.com/full/example-figure-1.png"
        transport = RecordingTransport(
            {
                ("GET", figure_url): {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": png_body(b"springer-figure-1"),
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
        self.assertEqual(saved_bytes, png_body(b"springer-figure-1"))

    def test_elsevier_body_asset_profile_excludes_appendix_and_supplementary(
        self,
    ) -> None:
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
