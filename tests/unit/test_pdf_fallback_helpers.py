from __future__ import annotations

import unittest
from unittest import mock

from paper_fetch.providers import _pdf_candidates, _pdf_common, _pdf_fallback


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
        timeout=20,
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
                "timeout": timeout,
                "retry_on_transient": retry_on_transient,
            }
        )
        return self.responses[(method, url)]


class PdfFallbackHelperTests(unittest.TestCase):
    def test_extract_pdf_candidate_urls_from_html_finds_meta_and_download_links(self) -> None:
        html = """
        <html><head>
          <meta name="citation_pdf_url" content="/article.pdf" />
        </head><body>
          <a href="/download?id=1">Download PDF</a>
          <a href="/content/pdfft?download=true">View PDF</a>
        </body></html>
        """

        candidates = _pdf_candidates.extract_pdf_candidate_urls_from_html(html, "https://example.org/articles/test")

        self.assertEqual(
            candidates,
            [
                "https://example.org/article.pdf",
                "https://example.org/download?id=1",
                "https://example.org/content/pdfft?download=true",
            ],
        )

    def test_extract_pdf_candidate_urls_from_html_finds_iframe_pdf_sources(self) -> None:
        html = """
        <html><body>
          <iframe src="/viewer.html?file=/doi/pdfdirect/10.1111/test" type="application/pdf"></iframe>
        </body></html>
        """

        candidates = _pdf_candidates.extract_pdf_candidate_urls_from_html(
            html,
            "https://example.org/articles/test",
        )

        self.assertIn("https://example.org/viewer.html?file=/doi/pdfdirect/10.1111/test", candidates)
        self.assertIn("https://example.org/doi/pdfdirect/10.1111/test", candidates)

    def test_rule_based_pdf_candidates_cover_springer(self) -> None:
        springer_candidates = _pdf_candidates.build_springer_pdf_candidates(
            "10.1038/example",
            {"landing_page_url": "https://www.nature.com/articles/example", "fulltext_links": []},
            html_text="<html></html>",
            source_url="https://www.nature.com/articles/example",
        )

        self.assertIn("https://www.nature.com/articles/example.pdf", springer_candidates)
        self.assertIn("https://link.springer.com/content/pdf/10.1038%2Fexample.pdf", springer_candidates)

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
            result = _pdf_fallback.fetch_pdf_over_http(transport, [first_url, second_url])

        self.assertEqual(result.source_url, second_url)
        self.assertEqual(len(transport.calls), 2)
        self.assertIn("application/pdf", str(transport.calls[0]["headers"].get("Accept")))

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
                _pdf_common.PdfFetchFailure("empty_pdf_markdown", "PDF fallback produced empty Markdown."),
                _pdf_common.PdfFetchResult(
                    source_url=second_url,
                    final_url=second_url,
                    pdf_bytes=b"%PDF-1.7 second",
                    markdown_text="# Example\n\n## Results\n\nBody text",
                    suggested_filename="article.pdf",
                ),
            ],
        ):
            result = _pdf_fallback.fetch_pdf_over_http(transport, [first_url, second_url])

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
            mock.patch.object(_pdf_fallback.urllib.request, "build_opener", return_value=FakeOpener()),
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
                open_calls.append({"url": request.full_url, "headers": dict(request.headers)})
                if request.full_url != pdf_url:
                    raise AssertionError(f"unexpected url {request.full_url}")
                return FakeResponse(pdf_url, "application/pdf", b"%PDF-1.7 cookie-seeded")

        with mock.patch.object(
            _pdf_fallback,
            "pdf_fetch_result_from_bytes",
            return_value=_pdf_common.PdfFetchResult(
                source_url=pdf_url,
                final_url=pdf_url,
                pdf_bytes=b"%PDF-1.7 cookie-seeded",
                markdown_text="# Example\n\n## Results\n\nBody text",
                suggested_filename="article.pdf",
            ),
        ), mock.patch.object(_pdf_fallback.urllib.request, "build_opener", return_value=FakeOpener()):
            result = _pdf_fallback.fetch_pdf_over_http(
                RecordingTransport({}),
                [pdf_url],
                browser_cookies=[
                    {"name": "cf_clearance", "value": "token", "domain": ".example.org", "path": "/", "secure": True},
                    {"name": "other", "value": "ignored", "domain": ".other.org", "path": "/", "secure": True},
                ],
            )

        self.assertEqual(result.source_url, pdf_url)
        self.assertEqual(open_calls[0]["headers"].get("Cookie"), "cf_clearance=token")


if __name__ == "__main__":
    unittest.main()
