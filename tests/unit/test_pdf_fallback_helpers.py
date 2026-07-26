from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
import threading
import tempfile
import types
import unittest
from unittest import mock

from paper_fetch.providers import (
    browser_runtime,
    _pdf_candidates,
    _pdf_common,
    _pdf_fallback,
)
from paper_fetch.providers.browser_workflow import pdf_fallback as browser_pdf_fallback
from paper_fetch.runtime import RuntimeContext
from tests.unit._browser_workflow_deps import browser_workflow_deps
from tests.unit._paper_fetch_support import RecordingTransport


class PdfFallbackHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        _pdf_common._clear_pdf_markdown_render_cache()

    def tearDown(self) -> None:
        _pdf_common._clear_pdf_markdown_render_cache()

    def test_sanitize_storage_state_uses_shared_cloudflare_cookie_tokens(self) -> None:
        self.assertIs(
            _pdf_common.CLOUDFLARE_COOKIE_NAMES,
            browser_runtime.CLOUDFLARE_COOKIE_NAMES,
        )
        self.assertIs(
            _pdf_common._CLOUDFLARE_COOKIE_PREFIXES,
            browser_runtime._CLOUDFLARE_COOKIE_PREFIXES,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "cookies": [
                            {"name": "_cfuvid", "value": "1"},
                            {"name": "__cf_bm", "value": "2"},
                            {"name": "cf_clearance", "value": "3"},
                            {"name": "cf_chl_rc_ni", "value": "4"},
                            {"name": "session", "value": "kept"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            sanitized_path = _pdf_common.sanitize_storage_state(state_path)
            try:
                sanitized = json.loads(sanitized_path.read_text(encoding="utf-8"))
            finally:
                sanitized_path.unlink(missing_ok=True)

        self.assertEqual(sanitized["cookies"], [{"name": "session", "value": "kept"}])

    def test_seeded_browser_pdf_payload_uses_lightweight_warm_and_skips_seed_when_cookie_seeded(
        self,
    ) -> None:
        pdf_url = "https://example.test/article.pdf"
        article_url = "https://example.test/article"
        warmed_seed = {
            "browser_cookies": [
                {
                    "name": "sessionid",
                    "value": "warm",
                    "domain": ".example.test",
                    "path": "/",
                }
            ],
            "browser_user_agent": "UnitTest/1.0",
            "browser_final_url": article_url,
        }
        mocked_warm = mock.Mock(return_value=warmed_seed)
        mocked_fetch_pdf = mock.Mock(
            return_value=_pdf_common.PdfFetchResult(
                source_url=pdf_url,
                final_url=pdf_url,
                pdf_bytes=b"%PDF-1.7 browser",
                markdown_text="# PDF\n\nBody",
                suggested_filename="article.pdf",
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = types.SimpleNamespace(
                backend="camoufox",
                artifact_dir=Path(tmpdir),
                headless=True,
                user_agent="UnitTest/1.0",
                storage_state_path=None,
                profile_dir=None,
                user_data_dir=None,
            )
            payload = browser_pdf_fallback.fetch_seeded_browser_pdf_payload(
                provider="wiley",
                doi="10.1000/example",
                runtime=runtime,
                pdf_candidates=[pdf_url],
                html_candidates=[article_url],
                landing_page_url=article_url,
                user_agent="UnitTest/1.0",
                browser_context_seed={},
                html_failure_reason="html_blocked",
                html_failure_message="HTML blocked",
                html_failure_diagnostics={
                    "browser_failure": {
                        "stage": "cdp_connect",
                        "code": "cdp_connect_failed",
                    }
                },
                deps=browser_workflow_deps(
                    pdf_browser_context_seed=mocked_warm,
                    fetch_pdf_with_browser=mocked_fetch_pdf,
                ),
            )

        self.assertEqual(payload.content.route_kind, "pdf_fallback")
        self.assertEqual(
            payload.content.diagnostics["html_failure"]["browser_failure"]["stage"],
            "cdp_connect",
        )
        self.assertEqual(payload.trace[0].code, "html_blocked")
        self.assertEqual(payload.trace[0].message, "HTML blocked")
        mocked_warm.assert_called_once()
        self.assertTrue(mocked_warm.call_args.kwargs["lightweight"])
        mocked_fetch_pdf.assert_called_once()
        self.assertEqual(mocked_fetch_pdf.call_args.kwargs["referer"], article_url)
        self.assertIsNone(mocked_fetch_pdf.call_args.kwargs["seed_urls"])
        self.assertEqual(
            mocked_fetch_pdf.call_args.kwargs["browser_cookies"],
            warmed_seed["browser_cookies"],
        )

    def test_pdf_fallback_strategy_delegates_http_fetch_options(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_fetcher(transport, candidate_urls, **kwargs):
            calls.append(
                {
                    "transport": transport,
                    "candidate_urls": list(candidate_urls),
                    **kwargs,
                }
            )
            return _pdf_common.PdfFetchResult(
                source_url="https://example.org/article.pdf",
                final_url="https://example.org/article.pdf",
                pdf_bytes=b"%PDF-1.7 strategy",
                markdown_text="# Example\n\n## Results\n\nBody text",
                suggested_filename="article.pdf",
            )

        transport = RecordingTransport({})
        strategy = _pdf_fallback.PdfFallbackStrategy(
            transport=transport,
            headers={"User-Agent": "UnitTest/1.0"},
            timeout=42,
            artifact_dir=Path("artifacts/pdf"),
            seed_urls=["https://example.org/article"],
            browser_cookies=[
                {"name": "token", "value": "abc", "domain": ".example.org"}
            ],
            fetcher=fake_fetcher,
        )

        result = strategy.fetch(["https://example.org/article.pdf"])

        self.assertEqual(result.final_url, "https://example.org/article.pdf")
        self.assertEqual(calls[0]["transport"], transport)
        self.assertEqual(
            calls[0]["candidate_urls"], ["https://example.org/article.pdf"]
        )
        self.assertEqual(calls[0]["headers"], {"User-Agent": "UnitTest/1.0"})
        self.assertEqual(calls[0]["timeout"], 42)
        self.assertEqual(calls[0]["artifact_dir"], Path("artifacts/pdf"))
        self.assertEqual(calls[0]["seed_urls"], ["https://example.org/article"])
        self.assertEqual(
            calls[0]["browser_cookies"],
            [{"name": "token", "value": "abc", "domain": ".example.org"}],
        )
        self.assertTrue(calls[0]["allow_pdf_only"])

    def test_pdf_fallback_uses_camoufox(self) -> None:
        pdf_url = "https://example.org/article.pdf"
        final_url = "https://example.org/downloaded/article.pdf"

        class FakeDownload:
            suggested_filename = "article.pdf"

            def save_as(self, path: str) -> None:
                Path(path).write_bytes(b"%PDF-1.7 camoufox")

        class FakeDownloadInfo:
            value = FakeDownload()

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        class FakePage:
            def __init__(self) -> None:
                self.url = ""
                self.goto_calls: list[dict[str, object]] = []
                self.expect_download_calls: list[int] = []

            def expect_download(self, *, timeout: int):
                self.expect_download_calls.append(timeout)
                return FakeDownloadInfo()

            def goto(self, url: str, **kwargs):
                self.url = final_url
                self.goto_calls.append({"url": url, **kwargs})
                return mock.Mock()

        class FakeBrowserContext:
            def __init__(self) -> None:
                self.page = FakePage()
                self.close_count = 0

            def new_page(self) -> FakePage:
                return self.page

            def close(self) -> None:
                self.close_count += 1

        fake_context = FakeBrowserContext()
        pdf_results: list[dict[str, object]] = []

        def fake_pdf_result_from_bytes(**kwargs):
            pdf_results.append(dict(kwargs))
            return _pdf_common.PdfFetchResult(
                source_url=str(kwargs["source_url"]),
                final_url=str(kwargs["final_url"]),
                pdf_bytes=bytes(kwargs["pdf_bytes"]),
                markdown_text="# Example\n\n## Results\n\nBody text",
                suggested_filename=str(kwargs["suggested_filename"]),
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                mock.patch(
                    "paper_fetch.runtime_browser.BrowserContextManager.new_context",
                    return_value=fake_context,
                ) as mocked_new_context,
                mock.patch(
                    "playwright.sync_api.sync_playwright",
                    side_effect=AssertionError("stock Playwright should not be used"),
                ) as mocked_sync_playwright,
                mock.patch.object(
                    _pdf_fallback,
                    "pdf_fetch_result_from_bytes",
                    side_effect=fake_pdf_result_from_bytes,
                ),
            ):
                result = _pdf_fallback.fetch_pdf_with_browser(
                    [pdf_url],
                    artifact_dir=Path(tmpdir),
                    browser_user_agent="UnitTest/1.0",
                    headless=False,
                )

        mocked_new_context.assert_called_once()
        self.assertFalse(mocked_new_context.call_args.kwargs["headless"])
        self.assertEqual(
            mocked_new_context.call_args.kwargs["user_agent"], "UnitTest/1.0"
        )
        mocked_sync_playwright.assert_not_called()
        self.assertEqual(fake_context.page.goto_calls[0]["url"], pdf_url)
        self.assertEqual(fake_context.page.expect_download_calls, [30000])
        self.assertEqual(result.final_url, final_url)
        self.assertEqual(pdf_results[0]["final_url"], final_url)
        self.assertEqual(fake_context.close_count, 1)

    def test_pdf_fallback_hands_sync_browser_work_to_thread_inside_asyncio_loop(
        self,
    ) -> None:
        pdf_url = "https://example.org/article.pdf"
        main_thread_id = threading.get_ident()
        new_context_thread_ids: list[int] = []

        class FakeDownload:
            suggested_filename = "article.pdf"

            def save_as(self, path: str) -> None:
                Path(path).write_bytes(b"%PDF-1.7 camoufox")

        class FakeDownloadInfo:
            value = FakeDownload()

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        class FakePage:
            url = "https://example.org/downloaded/article.pdf"

            def expect_download(self, *, timeout: int):
                return FakeDownloadInfo()

            def goto(self, url: str, **kwargs):
                return mock.Mock()

        class FakeBrowserContext:
            def new_page(self) -> FakePage:
                return FakePage()

            def close(self) -> None:
                return None

        def fake_new_context(*args, **kwargs):
            with self.assertRaises(RuntimeError):
                asyncio.get_running_loop()
            new_context_thread_ids.append(threading.get_ident())
            return FakeBrowserContext()

        async def run_fetch(artifact_dir: Path) -> _pdf_common.PdfFetchResult:
            return _pdf_fallback.fetch_pdf_with_browser(
                [pdf_url],
                artifact_dir=artifact_dir,
                headless=True,
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                mock.patch(
                    "paper_fetch.runtime_browser.BrowserContextManager.new_context",
                    side_effect=fake_new_context,
                ),
                mock.patch(
                    "playwright.sync_api.sync_playwright",
                    side_effect=AssertionError("stock Playwright should not be used"),
                ),
                mock.patch.object(
                    _pdf_fallback,
                    "pdf_fetch_result_from_bytes",
                    return_value=_pdf_common.PdfFetchResult(
                        source_url=pdf_url,
                        final_url="https://example.org/downloaded/article.pdf",
                        pdf_bytes=b"%PDF-1.7 camoufox",
                        markdown_text="# Example\n\n## Results\n\nBody text",
                        suggested_filename="article.pdf",
                    ),
                ),
            ):
                result = asyncio.run(run_fetch(Path(tmpdir)))

        self.assertEqual(result.final_url, "https://example.org/downloaded/article.pdf")
        self.assertEqual(len(new_context_thread_ids), 1)
        self.assertNotEqual(new_context_thread_ids[0], main_thread_id)

    def test_pdf_fallback_thread_handoff_uses_thread_local_browser_manager(
        self,
    ) -> None:
        pdf_url = "https://example.org/article.pdf"
        test_case = self
        main_thread_id = threading.get_ident()
        new_context_thread_ids: list[int] = []
        manager_init_kwargs: list[dict[str, object]] = []

        class FakeDownload:
            suggested_filename = "article.pdf"

            def save_as(self, path: str) -> None:
                Path(path).write_bytes(b"%PDF-1.7 camoufox")

        class FakeDownloadInfo:
            value = FakeDownload()

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        class FakePage:
            url = "https://example.org/downloaded/article.pdf"

            def expect_download(self, *, timeout: int):
                return FakeDownloadInfo()

            def goto(self, url: str, **kwargs):
                return mock.Mock()

        class FakeBrowserContext:
            def new_page(self) -> FakePage:
                return FakePage()

            def close(self) -> None:
                return None

        class FakeBrowserContextManager:
            def __init__(self, **kwargs) -> None:
                manager_init_kwargs.append(dict(kwargs))

            def new_context(self, *args, **kwargs):
                with test_case.assertRaises(RuntimeError):
                    asyncio.get_running_loop()
                new_context_thread_ids.append(threading.get_ident())
                return FakeBrowserContext()

            def close(self) -> None:
                return None

        async def run_fetch(
            artifact_dir: Path,
            runtime_context: RuntimeContext,
            profile_dir: Path,
            user_data_dir: Path,
        ) -> _pdf_common.PdfFetchResult:
            return _pdf_fallback.fetch_pdf_with_browser(
                [pdf_url],
                artifact_dir=artifact_dir,
                headless=True,
                profile_dir=profile_dir,
                user_data_dir=user_data_dir,
                context=runtime_context,
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            runtime_context = RuntimeContext(env={})
            profile_dir = tmp_path / "profile"
            user_data_dir = tmp_path / "user-data"
            with (
                mock.patch.object(
                    runtime_context,
                    "new_browser_context_for_config",
                    side_effect=AssertionError(
                        "runtime browser manager must not cross threads"
                    ),
                ) as mocked_runtime_new_context,
                mock.patch(
                    "paper_fetch.runtime_browser.BrowserContextManager",
                    FakeBrowserContextManager,
                ),
                mock.patch.object(
                    _pdf_fallback,
                    "pdf_fetch_result_from_bytes",
                    return_value=_pdf_common.PdfFetchResult(
                        source_url=pdf_url,
                        final_url="https://example.org/downloaded/article.pdf",
                        pdf_bytes=b"%PDF-1.7 camoufox",
                        markdown_text="# Example\n\n## Results\n\nBody text",
                        suggested_filename="article.pdf",
                    ),
                ),
            ):
                result = asyncio.run(
                    run_fetch(tmp_path, runtime_context, profile_dir, user_data_dir)
                )

        self.assertEqual(result.final_url, "https://example.org/downloaded/article.pdf")
        mocked_runtime_new_context.assert_not_called()
        self.assertEqual(len(new_context_thread_ids), 1)
        self.assertNotEqual(new_context_thread_ids[0], main_thread_id)
        self.assertEqual(
            manager_init_kwargs,
            [
                {
                    "binary_path": None,
                    "cdp_endpoint": None,
                    "external_new_context": False,
                    "profile_dir": profile_dir,
                    "user_data_dir": user_data_dir,
                }
            ],
        )

    def test_seeded_browser_pdf_fallback_tries_browser_like_http_first(self) -> None:
        pdf_url = "https://pubs.acs.org/doi/pdf/10.1021/example"
        seed_url = "https://pubs.acs.org/doi/10.1021/example"
        expected = _pdf_common.PdfFetchResult(
            source_url=pdf_url,
            final_url=pdf_url,
            pdf_bytes=b"%PDF-1.7 acs",
            markdown_text="# Example\n\n## Results\n\nBody text",
            suggested_filename="article.pdf",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                mock.patch.object(
                    _pdf_fallback,
                    "fetch_pdf_over_http",
                    return_value=expected,
                ) as mocked_http,
                mock.patch(
                    "paper_fetch.runtime_browser.BrowserContextManager.new_context",
                    side_effect=AssertionError(
                        "seeded direct PDF should not launch browser"
                    ),
                ),
            ):
                result = _pdf_fallback.fetch_pdf_with_browser(
                    [pdf_url],
                    artifact_dir=Path(tmpdir),
                    seed_urls=[seed_url],
                )

        self.assertIs(result, expected)
        _, attempted_urls = mocked_http.call_args.args[:2]
        self.assertEqual(attempted_urls, [pdf_url])
        headers = mocked_http.call_args.kwargs["headers"]
        self.assertIn("Chrome/", headers["User-Agent"])
        self.assertEqual(headers["Referer"], seed_url)
        self.assertEqual(headers["Sec-Fetch-Site"], "same-origin")
        self.assertEqual(headers["Sec-Fetch-Mode"], "navigate")
        self.assertEqual(headers["Sec-Fetch-Dest"], "document")
        self.assertEqual(mocked_http.call_args.kwargs["seed_urls"], [seed_url])

    def test_extract_pdf_candidate_urls_from_html_finds_meta_and_download_links(
        self,
    ) -> None:
        html = """
        <html><head>
          <meta name="citation_pdf_url" content="/article.pdf" />
        </head><body>
          <a href="/download?id=1">Download PDF</a>
          <a href="/content/pdfft?download=true">View PDF</a>
        </body></html>
        """

        candidates = _pdf_candidates.extract_pdf_candidate_urls_from_html(
            html, "https://example.org/articles/test"
        )

        self.assertEqual(
            candidates,
            [
                "https://example.org/article.pdf",
                "https://example.org/download?id=1",
                "https://example.org/content/pdfft?download=true",
            ],
        )

    def test_browser_pdf_viewer_html_response_refetches_pdf_from_request_context(
        self,
    ) -> None:
        class FakeNavigationResponse:
            headers = {"content-type": "application/pdf"}

            def body(self) -> bytes:
                return b"<!doctype html><html><body>PDF viewer shell</body></html>"

        class FakeRequestResponse:
            status = 200
            headers = {
                "content-type": "application/pdf",
                "content-disposition": 'inline; filename="article.pdf"',
            }

            def body(self) -> bytes:
                return b"%PDF-1.7 annualreviews"

        class FakeRequestContext:
            def __init__(self) -> None:
                self.urls: list[str] = []

            def get(self, url: str, **_kwargs: object) -> FakeRequestResponse:
                self.urls.append(url)
                return FakeRequestResponse()

        request_context = FakeRequestContext()
        page = types.SimpleNamespace(request=request_context)
        expected = _pdf_common.PdfFetchResult(
            source_url="https://example.org/doi/pdf/10.1146/example",
            final_url="https://example.org/docserver/fulltext/example.pdf?token=1",
            pdf_bytes=b"%PDF-1.7 annualreviews",
            markdown_text="# Example",
            suggested_filename="article.pdf",
        )

        with mock.patch.object(
            _pdf_fallback,
            "pdf_fetch_result_from_bytes",
            side_effect=[
                _pdf_common.PdfFetchFailure(
                    "downloaded_file_not_pdf",
                    "PDF fallback did not produce a PDF file.",
                ),
                expected,
            ],
        ) as mocked_from_bytes:
            result = _pdf_fallback._response_to_pdf_result(
                FakeNavigationResponse(),
                artifact_dir=Path("/tmp/pdf"),
                source_url="https://example.org/doi/pdf/10.1146/example",
                final_url="https://example.org/docserver/fulltext/example.pdf?token=1",
                page=page,
            )

        self.assertIs(result, expected)
        self.assertEqual(
            request_context.urls,
            ["https://example.org/docserver/fulltext/example.pdf?token=1"],
        )
        self.assertEqual(
            mocked_from_bytes.call_args.kwargs["pdf_bytes"], b"%PDF-1.7 annualreviews"
        )

    def test_extract_pdf_candidate_urls_from_html_finds_iframe_pdf_sources(
        self,
    ) -> None:
        html = """
        <html><body>
          <iframe src="/viewer.html?file=/doi/pdfdirect/10.1111/test" type="application/pdf"></iframe>
        </body></html>
        """

        candidates = _pdf_candidates.extract_pdf_candidate_urls_from_html(
            html,
            "https://example.org/articles/test",
        )

        self.assertIn(
            "https://example.org/viewer.html?file=/doi/pdfdirect/10.1111/test",
            candidates,
        )
        self.assertIn("https://example.org/doi/pdfdirect/10.1111/test", candidates)

    def test_pdf_url_token_groups_document_shared_and_route_specific_semantics(
        self,
    ) -> None:
        for token in _pdf_candidates.PDF_URL_COMMON_TOKENS:
            self.assertIn(token, _pdf_candidates.PDF_HREF_TOKENS)
            self.assertIn(token, _pdf_candidates.BROWSER_WORKFLOW_PDF_URL_TOKENS)

        self.assertIn("/pdfft", _pdf_candidates.PDF_HREF_TOKENS)
        self.assertNotIn("/pdfft", _pdf_candidates.BROWSER_WORKFLOW_PDF_URL_TOKENS)
        self.assertIn("/fullpdf", _pdf_candidates.BROWSER_WORKFLOW_PDF_URL_TOKENS)

    def test_rule_based_pdf_candidates_cover_springer(self) -> None:
        springer_candidates = _pdf_candidates.build_springer_pdf_candidates(
            "10.1038/example",
            {
                "landing_page_url": "https://www.nature.com/articles/example",
                "fulltext_links": [],
            },
            html_text="<html></html>",
            source_url="https://www.nature.com/articles/example",
        )

        self.assertIn(
            "https://www.nature.com/articles/example.pdf", springer_candidates
        )
        self.assertIn(
            "https://link.springer.com/content/pdf/10.1038%2Fexample.pdf",
            springer_candidates,
        )

    def test_springer_pdf_candidates_preserve_snapshot_order(self) -> None:
        candidates = _pdf_candidates.build_springer_pdf_candidates(
            "10.1038/example",
            {
                "landing_page_url": "https://www.nature.com/articles/example",
                "fulltext_links": [
                    {
                        "url": "https://metadata.example/article.pdf",
                        "content_type": "application/pdf",
                    }
                ],
            },
            html_text="""
            <html><head>
              <meta name="citation_pdf_url" content="/articles/example.pdf" />
            </head><body>
              <a href="/content/pdf/10.1038/example.pdf">Download PDF</a>
            </body></html>
            """,
            source_url="https://www.nature.com/articles/example",
        )

        self.assertEqual(
            candidates,
            [
                "https://metadata.example/article.pdf",
                "https://www.nature.com/articles/example.pdf",
                "https://www.nature.com/content/pdf/10.1038/example.pdf",
                "https://link.springer.com/content/pdf/10.1038%2Fexample.pdf",
            ],
        )

    def test_fetch_pdf_over_http_skips_non_pdf_payloads(self) -> None:
        first_url = "https://example.org/not-pdf"
        second_url = "https://example.org/article.pdf"
        transport = RecordingTransport(
            {
                ("GET", first_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html"},
                    "body": b"<html>Not a PDF</html>",
                    "url": first_url,
                },
                ("GET", second_url): {
                    "status_code": 200,
                    "headers": {"content-type": "application/pdf"},
                    "body": b"%PDF-1.7 second",
                    "url": second_url,
                },
            }
        )

        with mock.patch.object(
            _pdf_fallback,
            "pdf_fetch_result_from_bytes",
            return_value=_pdf_common.PdfFetchResult(
                source_url=second_url,
                final_url=second_url,
                pdf_bytes=b"%PDF-1.7 second",
                markdown_text="# Example\n\n## Results\n\nBody text",
                suggested_filename="article.pdf",
            ),
        ):
            result = _pdf_fallback.fetch_pdf_over_http(
                transport, [first_url, second_url]
            )

        self.assertEqual(result.source_url, second_url)
        self.assertEqual(len(transport.calls), 2)
        self.assertIn(
            "application/pdf", str(transport.calls[0]["headers"].get("Accept"))
        )

    def test_fetch_pdf_over_http_records_non_pdf_html_diagnostics_and_artifact(
        self,
    ) -> None:
        pdf_url = "https://example.org/stamp/stamp.jsp?arnumber=123"
        html = b"""
        <html>
          <head><title>IEEE Xplore Full-Text PDF</title></head>
          <body><script>window.location = '/stampPDF/getPDF.jsp?arnumber=123';</script>Please wait.</body>
        </html>
        """
        transport = RecordingTransport(
            {
                ("GET", pdf_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": html,
                    "url": pdf_url,
                },
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(_pdf_common.PdfFetchFailure) as ctx:
                _pdf_fallback.fetch_pdf_over_http(
                    transport,
                    [pdf_url],
                    artifact_dir=Path(tmpdir),
                )

            failure_html = Path(tmpdir) / "pdf.failure.html"
            self.assertTrue(failure_html.is_file())
            self.assertIn(
                "IEEE Xplore Full-Text PDF", failure_html.read_text(encoding="utf-8")
            )

        self.assertEqual(ctx.exception.kind, "downloaded_file_not_pdf")
        details = ctx.exception.details
        self.assertEqual(details["candidate_url"], pdf_url)
        self.assertEqual(details["final_url"], pdf_url)
        self.assertEqual(details["status"], 200)
        self.assertEqual(details["content_type"], "text/html; charset=utf-8")
        self.assertEqual(details["title_snippet"], "IEEE Xplore Full-Text PDF")
        self.assertIn("Please wait", details["body_snippet"])
        self.assertEqual(details["reason"], "non_pdf_html")

    def test_fetch_pdf_over_http_retries_after_empty_markdown(self) -> None:
        first_url = "https://example.org/empty.pdf"
        second_url = "https://example.org/article.pdf"
        transport = RecordingTransport(
            {
                ("GET", first_url): {
                    "status_code": 200,
                    "headers": {"content-type": "application/pdf"},
                    "body": b"%PDF-1.7 first",
                    "url": first_url,
                },
                ("GET", second_url): {
                    "status_code": 200,
                    "headers": {"content-type": "application/pdf"},
                    "body": b"%PDF-1.7 second",
                    "url": second_url,
                },
            }
        )

        with mock.patch.object(
            _pdf_fallback,
            "pdf_fetch_result_from_bytes",
            side_effect=[
                _pdf_common.PdfFetchFailure(
                    "empty_pdf_markdown", "PDF fallback produced empty Markdown."
                ),
                _pdf_common.PdfFetchResult(
                    source_url=second_url,
                    final_url=second_url,
                    pdf_bytes=b"%PDF-1.7 second",
                    markdown_text="# Example\n\n## Results\n\nBody text",
                    suggested_filename="article.pdf",
                ),
            ],
        ):
            result = _pdf_fallback.fetch_pdf_over_http(
                transport, [first_url, second_url]
            )

        self.assertEqual(result.source_url, second_url)
        self.assertEqual(len(transport.calls), 2)

    def test_pdf_fetch_result_allows_pdf_only_when_markdown_render_fails(self) -> None:
        pdf_url = "https://example.org/scanned.pdf"

        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(
                _pdf_common,
                "render_pdf_markdown_result",
                side_effect=_pdf_common.PdfFetchFailure(
                    "insufficient_pdf_markdown",
                    "PDF text extraction did not produce enough usable Markdown.",
                ),
            ):
                result = _pdf_common.pdf_fetch_result_from_bytes(
                    artifact_dir=Path(tmpdir),
                    source_url=pdf_url,
                    final_url=pdf_url,
                    pdf_bytes=b"%PDF-1.7 scanned",
                    suggested_filename="scanned.pdf",
                    allow_pdf_only=True,
                )

            self.assertTrue(list(Path(tmpdir).glob("*.pdf")))

        self.assertEqual(result.markdown_text, "")
        self.assertEqual(result.pdf_bytes, b"%PDF-1.7 scanned")
        self.assertIn(_pdf_common.PDF_ONLY_MARKDOWN_WARNING, result.warnings)

    def test_render_pdf_markdown_uses_default_when_markdown_is_usable(self) -> None:
        pdf_path = Path("article.pdf")
        default_markdown = "# Example\n\n" + ("body text " * 140)

        with (
            mock.patch.object(
                _pdf_common,
                "_render_default_pdf_markdown",
                return_value=default_markdown,
            ),
            mock.patch.object(_pdf_common, "_pdf_text_layer_stats") as mocked_stats,
            mock.patch.object(
                _pdf_common, "_render_transparent_pdf_markdown"
            ) as mocked_transparent,
        ):
            result = _pdf_common.render_pdf_markdown(pdf_path)

        self.assertEqual(result, default_markdown)
        mocked_stats.assert_not_called()
        mocked_transparent.assert_not_called()

    def test_pdf_markdown_structure_promotes_missing_alpha_subsection(self) -> None:
        markdown = "\n".join(
            [
                "# _a. First project_",
                "",
                "First body.",
                "",
                "# _b. Second project_",
                "",
                "Second body.",
                "",
                "_c. Third project_",
                "",
                "Third body.",
            ]
        )

        normalized = _pdf_common._normalize_pdf_markdown_structure(markdown)

        self.assertIn("# _c. Third project_", normalized)

    def test_pdf_markdown_structure_removes_empty_preamble_noise_heading(self) -> None:
        markdown = "\n".join(
            [
                "## **<u>Further</u>**",
                "",
                "###### ANNUAL REVIEWS",
                "",
                "Publisher details.",
                "",
                "## Introduction",
                "",
                "Body.",
            ]
        )

        normalized = _pdf_common._normalize_pdf_markdown_structure(markdown)

        self.assertNotIn("Further", normalized)
        self.assertIn("###### ANNUAL REVIEWS", normalized)

    def test_pdf_markdown_structure_removes_empty_title_h1_in_preamble(self) -> None:
        markdown = "\n".join(
            [
                "Cover text.",
                "",
                "## Article category",
                "",
                "# A sufficiently descriptive article title",
                "",
                "### First Author and Second Author",
                "",
                "## Abstract",
                "",
                "Abstract body.",
            ]
        )

        normalized = _pdf_common._normalize_pdf_markdown_structure(markdown)

        self.assertNotIn("# A sufficiently descriptive article title", normalized)
        self.assertIn("Article category", normalized)
        self.assertIn("### First Author and Second Author", normalized)

    def test_pdf_markdown_structure_removes_first_prose_h1_before_author_heading(
        self,
    ) -> None:
        markdown = "\n".join(
            [
                "Cover text.",
                "",
                "# A sufficiently descriptive article title",
                "",
                "### First Author and Second Author",
                "",
                "## Abstract",
                "",
                "Abstract body.",
            ]
        )

        normalized = _pdf_common._normalize_pdf_markdown_structure(markdown)

        self.assertNotIn("# A sufficiently descriptive article title", normalized)

    def test_pdf_markdown_structure_preserves_fragment_h1_before_author_heading(
        self,
    ) -> None:
        markdown = "\n".join(
            [
                "Cover text.",
                "",
                "# _− i_ **C** 3 **H** 7 **I and C** 3 **H** 8",
                "",
                "### First Author and Second Author",
                "",
                "## Abstract",
                "",
                "Abstract body.",
            ]
        )

        normalized = _pdf_common._normalize_pdf_markdown_structure(markdown)

        self.assertIn("# _− i_ **C** 3 **H** 7 **I and C** 3 **H** 8", normalized)

    def test_pdf_markdown_structure_preserves_h1_with_body(self) -> None:
        markdown = "\n".join(
            [
                "# A sufficiently descriptive article title",
                "",
                "Author and abstract text.",
                "",
                "## Introduction",
                "",
                "Body.",
            ]
        )

        normalized = _pdf_common._normalize_pdf_markdown_structure(markdown)

        self.assertIn("# A sufficiently descriptive article title", normalized)

    def test_pdf_markdown_structure_demotes_repeated_running_header(self) -> None:
        running_header = "Author et al.: A repeated running header"
        markdown = "\n".join(
            [
                running_header,
                "",
                "## Introduction",
                "",
                "Page one.",
                "",
                f"## {running_header}",
                "",
                "Page two.",
                "",
                running_header,
                "",
                f"## {running_header}",
                "",
                "Page three.",
            ]
        )

        normalized = _pdf_common._normalize_pdf_markdown_structure(markdown)

        self.assertNotIn(f"## {running_header}", normalized)
        self.assertEqual(normalized.count(running_header), 4)

    def test_pdf_markdown_structure_preserves_valid_empty_parent_headings(self) -> None:
        markdown = "\n".join(
            [
                "## 2. Methods",
                "",
                "### 2.1 Sampling",
                "",
                "Methods body.",
                "",
                "## 3. Results",
                "",
                "### 3.1 Primary result",
                "",
                "Results body.",
            ]
        )

        normalized = _pdf_common._normalize_pdf_markdown_structure(markdown)

        self.assertEqual(normalized, markdown)

    def test_default_pdf_markdown_protects_pymupdf_text_subprocess_decoding(
        self,
    ) -> None:
        calls: list[dict[str, object]] = []

        def fake_run(*args, **kwargs):
            calls.append(dict(kwargs))
            return mock.Mock(returncode=1, stdout="", stderr="")

        def fake_to_markdown(path: str) -> str:
            self.assertEqual(path, "sample.pdf")
            _pdf_common.subprocess.run(
                "where tesseract",
                shell=True,
                capture_output=True,
                text=True,
            )
            return "## Results\n\nExtracted PDF body."

        fake_pymupdf4llm = types.SimpleNamespace(to_markdown=fake_to_markdown)

        with (
            mock.patch.dict(sys.modules, {"pymupdf4llm": fake_pymupdf4llm}),
            mock.patch.object(_pdf_common.subprocess, "run", side_effect=fake_run),
        ):
            result = _pdf_common._render_default_pdf_markdown(Path("sample.pdf"))

        self.assertEqual(result, "## Results\n\nExtracted PDF body.")
        self.assertEqual(calls[0]["errors"], "replace")

    def test_default_pdf_markdown_subprocess_patch_only_mutates_owner_thread(
        self,
    ) -> None:
        calls: list[tuple[str, dict[str, object]]] = []
        owner_entered = threading.Event()
        release_owner = threading.Event()

        def fake_run(*args, **kwargs):
            label = str(args[0][0])
            calls.append((label, dict(kwargs)))
            return mock.Mock(returncode=1, stdout="", stderr="")

        def fake_to_markdown(path: str) -> str:
            self.assertEqual(path, "sample.pdf")
            _pdf_common.subprocess.run(["owner"], text=True)
            owner_entered.set()
            self.assertTrue(release_owner.wait(timeout=5))
            return "# Example\n\n" + ("owner body " * 140)

        fake_pymupdf4llm = types.SimpleNamespace(to_markdown=fake_to_markdown)
        result_holder: list[str] = []

        with (
            mock.patch.dict(sys.modules, {"pymupdf4llm": fake_pymupdf4llm}),
            mock.patch.object(_pdf_common.subprocess, "run", side_effect=fake_run),
        ):
            worker = threading.Thread(
                target=lambda: result_holder.append(
                    _pdf_common._render_default_pdf_markdown(Path("sample.pdf"))
                )
            )
            worker.start()
            self.assertTrue(owner_entered.wait(timeout=5))
            _pdf_common.subprocess.run(["other"], text=True)
            release_owner.set()
            worker.join(timeout=5)

        self.assertFalse(worker.is_alive())
        self.assertEqual(len(result_holder), 1)
        kwargs_by_label = {label: kwargs for label, kwargs in calls}
        self.assertEqual(kwargs_by_label["owner"]["errors"], "replace")
        self.assertNotIn("errors", kwargs_by_label["other"])

    def test_render_pdf_markdown_result_does_not_write_images_for_asset_profile_none(
        self,
    ) -> None:
        calls: list[dict[str, object]] = []

        def fake_to_markdown(path: str, **kwargs) -> str:
            self.assertEqual(path, "paper.pdf")
            calls.append(dict(kwargs))
            return "# Example\n\n" + ("body text " * 140)

        fake_pymupdf4llm = types.SimpleNamespace(to_markdown=fake_to_markdown)

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            mock.patch.dict(sys.modules, {"pymupdf4llm": fake_pymupdf4llm}),
        ):
            result = _pdf_common.render_pdf_markdown_result(
                Path("paper.pdf"),
                asset_profile="none",
                asset_output_dir=Path(tmpdir),
                source_url="https://example.org/paper.pdf",
            )

        self.assertEqual(calls, [{}])
        self.assertEqual(result.assets, [])

    def test_pdf_fetch_result_from_bytes_reuses_cached_markdown_for_same_pdf(
        self,
    ) -> None:
        calls: list[str] = []

        def fake_to_markdown(path: str, **kwargs) -> str:
            calls.append(path)
            self.assertEqual(kwargs, {})
            return "# Example\n\n" + ("cached body text " * 140)

        fake_pymupdf4llm = types.SimpleNamespace(to_markdown=fake_to_markdown)
        pdf_bytes = b"%PDF-1.7 cached bytes"

        with (
            mock.patch.dict(sys.modules, {"pymupdf4llm": fake_pymupdf4llm}),
            mock.patch.object(_pdf_common, "_pdf_page_count", return_value=3),
        ):
            first = _pdf_common.pdf_fetch_result_from_bytes(
                artifact_dir=None,
                source_url="https://example.org/one.pdf",
                final_url="https://example.org/one.pdf",
                pdf_bytes=pdf_bytes,
                suggested_filename="one.pdf",
            )
            second = _pdf_common.pdf_fetch_result_from_bytes(
                artifact_dir=None,
                source_url="https://example.org/two.pdf",
                final_url="https://example.org/two.pdf",
                pdf_bytes=pdf_bytes,
                suggested_filename="two.pdf",
            )

        self.assertEqual(len(calls), 1)
        self.assertEqual(first.markdown_text, second.markdown_text)
        self.assertEqual(first.diagnostics["pdf_markdown_cache"]["status"], "miss")
        self.assertEqual(second.diagnostics["pdf_markdown_cache"]["status"], "hit")
        self.assertEqual(second.diagnostics["pdf_pages"], 3)
        self.assertEqual(second.diagnostics["pdf_bytes"], len(pdf_bytes))

    def test_pdf_fetch_result_from_bytes_rejects_pdf_larger_than_guard(self) -> None:
        with (
            mock.patch.dict(os.environ, {"PAPER_FETCH_PDF_MAX_BYTES": "8"}),
            mock.patch.object(
                _pdf_common, "render_pdf_markdown_result"
            ) as mocked_render,
        ):
            with self.assertRaises(_pdf_common.PdfFetchFailure) as ctx:
                _pdf_common.pdf_fetch_result_from_bytes(
                    artifact_dir=None,
                    source_url="https://example.org/large.pdf",
                    final_url="https://example.org/large.pdf",
                    pdf_bytes=b"%PDF-1.7 large payload",
                )

        self.assertEqual(ctx.exception.kind, "pdf_too_large")
        self.assertEqual(ctx.exception.details["max_pdf_bytes"], 8)
        mocked_render.assert_not_called()

    def test_pdf_fetch_result_from_bytes_rejects_too_many_pages_before_render(
        self,
    ) -> None:
        with (
            mock.patch.dict(os.environ, {"PAPER_FETCH_PDF_MAX_PAGES": "2"}),
            mock.patch.object(_pdf_common, "_pdf_page_count", return_value=3),
            mock.patch.object(
                _pdf_common, "render_pdf_markdown_result"
            ) as mocked_render,
        ):
            with self.assertRaises(_pdf_common.PdfFetchFailure) as ctx:
                _pdf_common.pdf_fetch_result_from_bytes(
                    artifact_dir=None,
                    source_url="https://example.org/long.pdf",
                    final_url="https://example.org/long.pdf",
                    pdf_bytes=b"%PDF-1.7 long payload",
                )

        self.assertEqual(ctx.exception.kind, "pdf_too_many_pages")
        self.assertEqual(ctx.exception.details["pdf_pages"], 3)
        self.assertEqual(ctx.exception.details["max_pdf_pages"], 2)
        mocked_render.assert_not_called()

    def test_pdf_asset_output_dir_uses_doi_asset_dir_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "downloads"
            context = RuntimeContext(
                env={}, download_dir=output_dir, artifact_mode="markdown-assets"
            )

            self.assertEqual(
                _pdf_common.pdf_asset_output_dir(
                    context,
                    asset_profile="body",
                    doi="10.1016/test",
                ),
                output_dir / "10.1016_test_assets",
            )
            self.assertIsNone(
                _pdf_common.pdf_asset_output_dir(
                    context,
                    asset_profile="none",
                    doi="10.1016/test",
                )
            )

    def test_render_pdf_markdown_result_writes_doi_images_for_body_asset_profile(
        self,
    ) -> None:
        calls: list[dict[str, object]] = []

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            image_dir = output_dir / "10.1234_test_assets"
            image_path = image_dir / "paper-0001-00.png"

            def fake_to_markdown(path: str, **kwargs) -> str:
                self.assertEqual(path, "paper.pdf")
                calls.append(dict(kwargs))
                image_dir.mkdir(parents=True, exist_ok=True)
                image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
                return f"# Example\n\n![]({image_path})\n\n" + ("body text " * 140)

            fake_pymupdf4llm = types.SimpleNamespace(to_markdown=fake_to_markdown)

            with mock.patch.dict(sys.modules, {"pymupdf4llm": fake_pymupdf4llm}):
                result = _pdf_common.render_pdf_markdown_result(
                    Path("paper.pdf"),
                    asset_profile="body",
                    asset_output_dir=image_dir,
                    source_url="https://example.org/paper.pdf",
                )

        self.assertEqual(calls[0]["write_images"], True)
        self.assertEqual(calls[0]["image_path"], str(image_dir))
        self.assertIn(
            "![Figure 1](10.1234_test_assets/paper-0001-00.png)", result.markdown_text
        )
        self.assertEqual(len(result.assets), 1)
        self.assertEqual(result.assets[0]["kind"], "figure")
        self.assertEqual(result.assets[0]["section"], "body")
        self.assertEqual(result.assets[0]["render_state"], "inline")
        self.assertEqual(
            result.assets[0]["url"], "10.1234_test_assets/paper-0001-00.png"
        )
        self.assertEqual(result.assets[0]["path"], str(image_path))

    def test_pdf_fetch_result_from_bytes_does_not_keep_temp_images_without_asset_output_dir(
        self,
    ) -> None:
        calls: list[dict[str, object]] = []

        def fake_to_markdown(path: str, **kwargs) -> str:
            self.assertTrue(path.endswith(".pdf"))
            calls.append(dict(kwargs))
            return "# Example\n\n" + ("body text " * 140)

        fake_pymupdf4llm = types.SimpleNamespace(to_markdown=fake_to_markdown)

        with mock.patch.dict(sys.modules, {"pymupdf4llm": fake_pymupdf4llm}):
            result = _pdf_common.pdf_fetch_result_from_bytes(
                artifact_dir=None,
                asset_profile="body",
                asset_output_dir=None,
                source_url="https://example.org/paper.pdf",
                final_url="https://example.org/paper.pdf",
                pdf_bytes=b"%PDF-1.7 body",
                suggested_filename="paper.pdf",
            )

        self.assertEqual(calls, [{}])
        self.assertEqual(result.assets, [])

    def test_transparent_pdf_markdown_protects_pymupdf_text_subprocess_decoding(
        self,
    ) -> None:
        calls: list[dict[str, object]] = []

        def fake_run(*args, **kwargs):
            calls.append(dict(kwargs))
            return mock.Mock(returncode=1, stdout="", stderr="")

        def fake_to_markdown(path: str, *, ignore_alpha: bool, hdr_info: bool) -> str:
            self.assertEqual(path, "transparent.pdf")
            self.assertTrue(ignore_alpha)
            self.assertFalse(hdr_info)
            _pdf_common.subprocess.run(
                "where tesseract",
                shell=True,
                capture_output=True,
                text=True,
            )
            return "## Results\n\nTransparent PDF body."

        fake_pymupdf_rag = types.SimpleNamespace(to_markdown=fake_to_markdown)
        fake_pymupdf4llm = types.ModuleType("pymupdf4llm")
        fake_helpers = types.ModuleType("pymupdf4llm.helpers")
        fake_helpers.pymupdf_rag = fake_pymupdf_rag
        fake_pymupdf4llm.helpers = fake_helpers

        with (
            mock.patch.dict(
                sys.modules,
                {
                    "pymupdf4llm": fake_pymupdf4llm,
                    "pymupdf4llm.helpers": fake_helpers,
                    "pymupdf4llm.helpers.pymupdf_rag": fake_pymupdf_rag,
                },
            ),
            mock.patch.object(_pdf_common.subprocess, "run", side_effect=fake_run),
        ):
            result = _pdf_common._render_transparent_pdf_markdown(
                Path("transparent.pdf")
            )

        self.assertEqual(result, "## Results\n\nTransparent PDF body.")
        self.assertEqual(calls[0]["errors"], "replace")

    def test_render_pdf_markdown_uses_transparent_fallback_for_license_footer(
        self,
    ) -> None:
        pdf_path = Path("legacy-ieee.pdf")
        default_markdown = "\n".join(
            [
                "Authorized licensed use limited to: Example University. "
                "Downloaded on January 1, 2026 from IEEE Xplore. Restrictions apply."
            ]
            * 3
        )
        legacy_markdown = "# Example\n\n" + ("transparent body text " * 260)

        with (
            mock.patch.object(
                _pdf_common,
                "_render_default_pdf_markdown",
                return_value=default_markdown,
            ),
            mock.patch.object(
                _pdf_common,
                "_pdf_text_layer_stats",
                return_value=_pdf_common._PdfTextLayerStats(
                    raw_words=900,
                    visible_words=45,
                    transparent_words=855,
                ),
            ),
            mock.patch.object(
                _pdf_common,
                "_render_transparent_pdf_markdown",
                return_value=legacy_markdown,
            ) as mocked_transparent,
        ):
            result = _pdf_common.render_pdf_markdown(pdf_path)

        self.assertEqual(result, legacy_markdown)
        mocked_transparent.assert_called_once_with(pdf_path)

    def test_render_pdf_markdown_does_not_use_transparent_fallback_without_transparent_text(
        self,
    ) -> None:
        default_markdown = "# Example\n\n" + ("short body " * 20)

        with (
            mock.patch.object(
                _pdf_common,
                "_render_default_pdf_markdown",
                return_value=default_markdown,
            ),
            mock.patch.object(
                _pdf_common,
                "_pdf_text_layer_stats",
                return_value=_pdf_common._PdfTextLayerStats(
                    raw_words=42,
                    visible_words=42,
                    transparent_words=0,
                ),
            ),
            mock.patch.object(
                _pdf_common, "_render_transparent_pdf_markdown"
            ) as mocked_transparent,
        ):
            with self.assertRaises(_pdf_common.PdfFetchFailure) as ctx:
                _pdf_common.render_pdf_markdown(Path("short.pdf"))

        self.assertEqual(ctx.exception.kind, "insufficient_pdf_markdown")
        mocked_transparent.assert_not_called()

    def test_render_pdf_markdown_preserves_empty_result_without_transparent_text(
        self,
    ) -> None:
        with (
            mock.patch.object(
                _pdf_common, "_render_default_pdf_markdown", return_value=""
            ),
            mock.patch.object(
                _pdf_common,
                "_pdf_text_layer_stats",
                return_value=_pdf_common._PdfTextLayerStats(
                    raw_words=0,
                    visible_words=0,
                    transparent_words=0,
                ),
            ),
            mock.patch.object(
                _pdf_common, "_render_transparent_pdf_markdown"
            ) as mocked_transparent,
        ):
            result = _pdf_common.render_pdf_markdown(Path("empty.pdf"))

        self.assertEqual(result, "")
        mocked_transparent.assert_not_called()

    def test_render_pdf_markdown_rejects_bad_transparent_fallback_output(self) -> None:
        default_markdown = (
            "Authorized licensed use limited to: Example University. "
            "Downloaded on January 1, 2026 from IEEE Xplore. Restrictions apply."
        )
        legacy_markdown = "Authorized licensed use limited to: Example University. Restrictions apply."

        with (
            mock.patch.object(
                _pdf_common,
                "_render_default_pdf_markdown",
                return_value=default_markdown,
            ),
            mock.patch.object(
                _pdf_common,
                "_pdf_text_layer_stats",
                return_value=_pdf_common._PdfTextLayerStats(
                    raw_words=800,
                    visible_words=20,
                    transparent_words=780,
                ),
            ),
            mock.patch.object(
                _pdf_common,
                "_render_transparent_pdf_markdown",
                return_value=legacy_markdown,
            ),
        ):
            with self.assertRaises(_pdf_common.PdfFetchFailure) as ctx:
                _pdf_common.render_pdf_markdown(Path("legacy-ieee.pdf"))

        self.assertEqual(ctx.exception.kind, "insufficient_pdf_markdown")
        self.assertTrue(ctx.exception.details["legacy_license_only"])

    def test_fetch_pdf_over_http_retries_after_insufficient_markdown(self) -> None:
        first_url = "https://example.org/insufficient.pdf"
        second_url = "https://example.org/article.pdf"
        transport = RecordingTransport(
            {
                ("GET", first_url): {
                    "status_code": 200,
                    "headers": {"content-type": "application/pdf"},
                    "body": b"%PDF-1.7 first",
                    "url": first_url,
                },
                ("GET", second_url): {
                    "status_code": 200,
                    "headers": {"content-type": "application/pdf"},
                    "body": b"%PDF-1.7 second",
                    "url": second_url,
                },
            }
        )

        with mock.patch.object(
            _pdf_fallback,
            "pdf_fetch_result_from_bytes",
            side_effect=[
                _pdf_common.PdfFetchFailure(
                    "insufficient_pdf_markdown",
                    "PDF fallback produced insufficient Markdown.",
                ),
                _pdf_common.PdfFetchResult(
                    source_url=second_url,
                    final_url=second_url,
                    pdf_bytes=b"%PDF-1.7 second",
                    markdown_text="# Example\n\n## Results\n\nBody text",
                    suggested_filename="article.pdf",
                ),
            ],
        ):
            result = _pdf_fallback.fetch_pdf_over_http(
                transport, [first_url, second_url]
            )

        self.assertEqual(result.source_url, second_url)
        self.assertEqual(len(transport.calls), 2)

    def test_fetch_pdf_over_http_can_seed_cookie_context(self) -> None:
        seed_url = "https://example.org/article"
        pdf_url = "https://example.org/article.pdf"
        transport = RecordingTransport({})
        open_calls: list[str] = []

        class FakeResponse:
            def __init__(self, url: str, content_type: str, body: bytes) -> None:
                self.status = 200
                self._url = url
                self.headers = {"content-type": content_type}
                self._body = body

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def read(self, _size: int = -1) -> bytes:
                return self._body

            def geturl(self) -> str:
                return self._url

            def getcode(self) -> int:
                return self.status

        class FakeOpener:
            def open(self, request, timeout=20):
                open_calls.append(request.full_url)
                if request.full_url == seed_url:
                    return FakeResponse(seed_url, "text/html", b"<html>landing</html>")
                if request.full_url == pdf_url:
                    return FakeResponse(pdf_url, "application/pdf", b"%PDF-1.7 seeded")
                raise AssertionError(f"unexpected url {request.full_url}")

        with (
            mock.patch.object(
                _pdf_fallback.urllib.request, "build_opener", return_value=FakeOpener()
            ),
            mock.patch.object(
                _pdf_fallback,
                "pdf_fetch_result_from_bytes",
                return_value=_pdf_common.PdfFetchResult(
                    source_url=pdf_url,
                    final_url=pdf_url,
                    pdf_bytes=b"%PDF-1.7 seeded",
                    markdown_text="# Example\n\n## Results\n\nBody text",
                    suggested_filename="article.pdf",
                ),
            ),
        ):
            result = _pdf_fallback.fetch_pdf_over_http(
                transport,
                [pdf_url],
                seed_urls=[seed_url],
                headers={"User-Agent": "UnitTest/1.0"},
            )

        self.assertEqual(result.source_url, pdf_url)
        self.assertEqual(open_calls, [seed_url, pdf_url])
        self.assertEqual(transport.calls, [])

    def test_fetch_pdf_over_http_can_attach_browser_cookies(self) -> None:
        pdf_url = "https://example.org/article.pdf"
        open_calls: list[dict[str, object]] = []

        class FakeResponse:
            def __init__(self, url: str, content_type: str, body: bytes) -> None:
                self.status = 200
                self._url = url
                self.headers = {"content-type": content_type}
                self._body = body

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def read(self, _size: int = -1) -> bytes:
                return self._body

            def geturl(self) -> str:
                return self._url

            def getcode(self) -> int:
                return self.status

        class FakeOpener:
            def open(self, request, timeout=20):
                open_calls.append(
                    {"url": request.full_url, "headers": dict(request.headers)}
                )
                if request.full_url != pdf_url:
                    raise AssertionError(f"unexpected url {request.full_url}")
                return FakeResponse(
                    pdf_url, "application/pdf", b"%PDF-1.7 cookie-seeded"
                )

        with (
            mock.patch.object(
                _pdf_fallback,
                "pdf_fetch_result_from_bytes",
                return_value=_pdf_common.PdfFetchResult(
                    source_url=pdf_url,
                    final_url=pdf_url,
                    pdf_bytes=b"%PDF-1.7 cookie-seeded",
                    markdown_text="# Example\n\n## Results\n\nBody text",
                    suggested_filename="article.pdf",
                ),
            ),
            mock.patch.object(
                _pdf_fallback.urllib.request, "build_opener", return_value=FakeOpener()
            ),
        ):
            result = _pdf_fallback.fetch_pdf_over_http(
                RecordingTransport({}),
                [pdf_url],
                browser_cookies=[
                    {
                        "name": "cf_clearance",
                        "value": "token",
                        "domain": ".example.org",
                        "path": "/",
                        "secure": True,
                    },
                    {
                        "name": "other",
                        "value": "ignored",
                        "domain": ".other.org",
                        "path": "/",
                        "secure": True,
                    },
                ],
            )

        self.assertEqual(result.source_url, pdf_url)
        self.assertEqual(open_calls[0]["headers"].get("Cookie"), "cf_clearance=token")


if __name__ == "__main__":
    unittest.main()
