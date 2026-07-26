# ruff: noqa: F403,F405
from __future__ import annotations

from paper_fetch.providers import (
    _ieee_block_page,
    _ieee_browser_html,
    _ieee_html,
    _ieee_metadata,
    _ieee_url,
    browser_runtime,
)

from ._ieee_provider_support import *


class IeeeProviderRouteTests(unittest.TestCase):
    def test_landing_nonrecoverable_statuses_do_not_load_browser_runtime(self) -> None:
        doi = "10.1109/example.landing"
        landing_url = f"https://doi.org/{doi}"
        for status in (404, 410, 429, 500):
            with self.subTest(status=status):
                client = IeeeClient(
                    RecordingTransport(
                        {
                            ("GET", landing_url): RequestFailure(
                                status,
                                f"HTTP {status} for {landing_url}",
                                url=landing_url,
                            )
                        }
                    ),
                    {},
                )
                with (
                    mock.patch.object(
                        ieee_provider.browser_runtime, "load_runtime_config"
                    ) as mocked_runtime,
                    self.assertRaises(ieee_provider.ProviderFailure),
                ):
                    client._fetch_landing_attempt(
                        doi, {"doi": doi, "landing_page_url": landing_url}
                    )
                mocked_runtime.assert_not_called()

    def test_direct_rest_rate_limit_skips_browser_and_continues_to_pdf(self) -> None:
        doi = "10.1109/example.429"
        article_number = "429429"
        landing_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        rest_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/"
            "?logAccess=true"
        )
        transport = RecordingTransport(
            {
                ("GET", landing_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": _landing_html(
                        doi=doi, article_number=article_number, dynamic=False
                    ),
                    "url": landing_url,
                },
                ("GET", rest_url): RequestFailure(
                    429,
                    f"HTTP 429 for {rest_url}",
                    url=rest_url,
                    retry_after_seconds=30,
                ),
            }
        )
        client = IeeeClient(transport, {})
        pdf_result = PdfFetchResult(
            source_url=f"https://ieeexplore.ieee.org/iel7/{article_number}.pdf",
            final_url=f"https://ieeexplore.ieee.org/iel7/{article_number}.pdf",
            pdf_bytes=b"%PDF-1.7 ieee",
            markdown_text="# IEEE PDF Article\n\n## Results\n\n"
            + ("PDF body text " * 160),
            suggested_filename=f"{article_number}.pdf",
        )

        with (
            mock.patch.object(client, "_fetch_browser_html_payload") as mocked_browser,
            mock.patch.object(
                ieee_provider, "fetch_pdf_over_http", return_value=pdf_result
            ),
        ):
            raw_payload = client.fetch_raw_fulltext(
                doi, {"doi": doi, "landing_page_url": landing_url}
            )

        mocked_browser.assert_not_called()
        self.assertEqual(raw_payload.content.route_kind, "pdf_fallback")
        article = client.to_article_model({"doi": doi}, raw_payload)
        self.assertNotIn(
            "fulltext:ieee_browser_html_fail", article.quality.source_trail
        )
        self.assertIn(
            "browser recovery is not eligible", "\n".join(raw_payload.warnings)
        )

    def test_landing_403_uses_selected_browser_and_preserves_seed(self) -> None:
        doi = "10.1109/ACCESS.2024.3352924"
        article_number = "10388355"
        landing_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        transport = RecordingTransport(
            {
                ("GET", landing_url): RequestFailure(
                    403,
                    f"HTTP 403 for {landing_url}",
                    headers={"content-type": "text/html"},
                    url=landing_url,
                )
            }
        )
        client = IeeeClient(transport, {})
        runtime = mock.Mock(backend="camoufox")
        browser_result = browser_runtime.BrowserFetchedHtml(
            source_url=landing_url,
            final_url=landing_url,
            html=_landing_html(doi=doi, article_number=article_number).decode("utf-8"),
            response_status=200,
            response_headers={"content-type": "text/html"},
            title="IEEE Dynamic Article",
            summary="IEEE landing metadata",
            browser_context_seed={
                "browser_cookies": [{"name": "sid", "value": "one"}],
                "browser_final_url": landing_url,
                "paper_fetch_html_fetcher": "camoufox",
            },
        )

        with (
            mock.patch.object(
                browser_runtime, "load_runtime_config", return_value=runtime
            ) as mocked_load,
            mock.patch.object(
                browser_runtime,
                "fetch_html_with_browser",
                return_value=browser_result,
            ) as mocked_browser,
        ):
            attempt = client._fetch_landing_attempt(
                doi, {"doi": doi, "landing_page_url": landing_url}
            )

        self.assertEqual(attempt.article_number, article_number)
        self.assertEqual(attempt.acquisition_source, "camoufox_browser")
        self.assertEqual(
            attempt.browser_context_seed["browser_cookies"][0]["name"], "sid"
        )
        self.assertTrue(attempt.diagnostics["browser_attempted"])
        self.assertEqual(attempt.diagnostics["browser_backend"], "camoufox")
        mocked_load.assert_called_once()
        mocked_browser.assert_called_once()

    def test_ieee_preferred_provider_is_accepted(self) -> None:
        strategy = FetchStrategy(preferred_providers=["ieee"])

        self.assertEqual(strategy.normalized_preferred_providers(), {"ieee"})

    def test_landing_metadata_and_article_number_parsing(self) -> None:
        html = _landing_html(article_number="10388355").decode("utf-8")
        metadata = _ieee_metadata._parse_landing_metadata(html)

        self.assertEqual(metadata["articleNumber"], "10388355")
        self.assertEqual(
            _ieee_url._article_number_from_url(
                "https://ieeexplore.ieee.org/document/10388355/"
            ),
            "10388355",
        )
        self.assertEqual(
            _ieee_url._article_number_from_url(
                "https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=10388355"
            ),
            "",
        )
        self.assertEqual(
            _ieee_url._article_number_from_url(
                "https://ieeexplore.ieee.org/rest/document/10388355/references"
            ),
            "",
        )
        self.assertTrue(metadata["isDynamicHtml"])

    def test_ieee_block_page_detection_is_cached_in_runtime_context(self) -> None:
        context = RuntimeContext(env={})
        html = "<html><body>Your request has been blocked. Verify you are human.</body></html>"
        try:
            with mock.patch.object(
                _ieee_block_page,
                "_scan_ieee_block_page_tokens",
                wraps=_ieee_block_page._scan_ieee_block_page_tokens,
            ) as scanner:
                for _ in range(2):
                    with self.assertRaises(ieee_provider.ProviderFailure):
                        _ieee_html._extract_ieee_html(
                            html,
                            "https://ieeexplore.ieee.org/rest/document/10388355/?logAccess=true",
                            metadata={"title": "Blocked"},
                            context=context,
                        )
                self.assertEqual(scanner.call_count, 1)
        finally:
            context.close()

    def test_landing_attempt_merges_ieee_keywords_and_reference_text(self) -> None:
        """rule: rule-ieee-landing-metadata-references
        rule: rule-fulltext-reference-priority"""
        doi = "10.1109/ACCESS.2024.3352924"
        article_number = "10388355"
        landing_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        references_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/references"
        )
        landing_metadata = {
            "articleNumber": article_number,
            "articleId": article_number,
            "doi": doi,
            "title": "IEEE Dynamic Article",
            "publicationTitle": "IEEE Access",
            "publicationDate": "2024",
            "abstract": "IEEE abstract text.",
            "authors": [{"name": "Alice Example"}],
            "isDynamicHtml": True,
            "ml_html_flag": True,
            "referenceCount": 1,
            "keywords": [
                {"type": "IEEE Keywords", "kwd": ["Random access memory"]},
                {"type": "Author Keywords", "kwd": ["near-data processing"]},
            ],
        }
        landing_html = (
            "<html><body><script>xplGlobal = {document: {}}; xplGlobal.document.metadata = "
            + json.dumps(landing_metadata)
            + ";</script></body></html>"
        ).encode("utf-8")
        references_json = json.dumps(
            {
                "references": [
                    {
                        "order": "1",
                        "text": "A. Author, “Full IEEE reference title,” <em>Proc. Test</em>, 2024.",
                        "title": "Full IEEE reference title",
                        "links": {
                            "crossRefLink": "https://doi.org/10.1109/TEST.2024.1"
                        },
                    }
                ]
            }
        ).encode("utf-8")
        transport = RecordingTransport(
            {
                ("GET", landing_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": landing_html,
                    "url": landing_url,
                },
                ("GET", references_url): {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": references_json,
                    "url": references_url,
                },
            }
        )
        client = IeeeClient(transport, {})

        attempt = client._fetch_landing_attempt(
            doi,
            {
                "doi": doi,
                "landing_page_url": landing_url,
                "references": [
                    {"title": "Metadata fallback title without IEEE citation text"},
                    {"doi": "10.1109/test.2024.2"},
                ],
            },
        )

        self.assertEqual(
            attempt.merged_metadata["keywords"],
            ["Random access memory", "near-data processing"],
        )
        self.assertEqual(len(attempt.merged_metadata["references"]), 1)
        self.assertEqual(attempt.merged_metadata["references"][0]["label"], "1")
        self.assertIn(
            "Full IEEE reference title", attempt.merged_metadata["references"][0]["raw"]
        )
        self.assertEqual(
            attempt.merged_metadata["references"][0]["doi"], "10.1109/test.2024.1"
        )
        self.assertNotIn(
            "Metadata fallback title without IEEE citation text",
            json.dumps(attempt.merged_metadata["references"]),
        )

    def test_landing_attempt_keeps_metadata_references_when_ieee_payload_is_empty(
        self,
    ) -> None:
        """rule: rule-ieee-landing-metadata-references
        rule: rule-fulltext-reference-priority"""
        doi = "10.1109/ACCESS.2024.3352924"
        article_number = "10388355"
        landing_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        references_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/references"
        )
        landing_metadata = {
            "articleNumber": article_number,
            "articleId": article_number,
            "doi": doi,
            "title": "IEEE Dynamic Article",
            "publicationTitle": "IEEE Access",
            "publicationDate": "2024",
            "abstract": "IEEE abstract text.",
            "authors": [{"name": "Alice Example"}],
            "isDynamicHtml": True,
            "ml_html_flag": True,
            "referenceCount": 1,
        }
        landing_html = (
            "<html><body><script>xplGlobal = {document: {}}; xplGlobal.document.metadata = "
            + json.dumps(landing_metadata)
            + ";</script></body></html>"
        ).encode("utf-8")
        fallback_references = [
            {"title": "Metadata fallback title", "doi": "10.5555/fallback"},
        ]
        transport = RecordingTransport(
            {
                ("GET", landing_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": landing_html,
                    "url": landing_url,
                },
                ("GET", references_url): {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": json.dumps({"references": []}).encode("utf-8"),
                    "url": references_url,
                },
            }
        )
        client = IeeeClient(transport, {})

        attempt = client._fetch_landing_attempt(
            doi,
            {
                "doi": doi,
                "landing_page_url": landing_url,
                "references": fallback_references,
            },
        )

        self.assertEqual(attempt.merged_metadata["references"], fallback_references)

    def test_dynamic_html_success_uses_ieee_html_source_and_rest_headers(self) -> None:
        doi = "10.1109/ACCESS.2024.3352924"
        article_number = "10388355"
        landing_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        rest_url = f"https://ieeexplore.ieee.org/rest/document/{article_number}/?logAccess=true"
        transport = RecordingTransport(
            {
                ("GET", landing_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": _landing_html(doi=doi, article_number=article_number),
                    "url": landing_url,
                },
                ("GET", rest_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": _dynamic_html(article_number),
                    "url": rest_url,
                },
            }
        )
        client = IeeeClient(transport, {})

        with mock.patch.object(browser_runtime, "load_runtime_config") as mocked_load:
            raw_payload = client.fetch_raw_fulltext(
                doi, {"doi": doi, "landing_page_url": landing_url}
            )
        mocked_load.assert_not_called()
        article = client.to_article_model({"doi": doi}, raw_payload)

        self.assertEqual(raw_payload.content.route_kind, "html")
        self.assertEqual(article.source, "ieee_html")
        self.assertEqual(article.metadata.authors, ["Alice Example", "Bob Example"])
        self.assertEqual(article.quality.content_kind, "fulltext")
        self.assertIn("fulltext:ieee_html_ok", article.quality.source_trail)
        rest_call = transport.calls[1]
        self.assertEqual(rest_call["url"], rest_url)
        self.assertEqual(rest_call["timeout"], DEFAULT_FULLTEXT_TIMEOUT_SECONDS)
        self.assertTrue(rest_call["retry_on_transient"])
        headers = rest_call["headers"]
        self.assertEqual(headers["Referer"], landing_url)
        self.assertEqual(headers["x-security-request"], "required")
        self.assertIn("application/json", headers["Accept"])
        diagnostics = raw_payload.content.diagnostics["extraction"]
        self.assertGreaterEqual(diagnostics["marker_counts"]["sections"], 2)
        self.assertGreaterEqual(diagnostics["marker_counts"]["formulas"], 1)

    def test_direct_rest_401_uses_browser_html_fallback_before_pdf(self) -> None:
        doi = "10.1109/TIM.2024.3509573"
        article_number = "10772041"
        landing_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        rest_url = f"https://ieeexplore.ieee.org/rest/document/{article_number}/?logAccess=true"
        transport = RecordingTransport(
            {
                ("GET", landing_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": _landing_html(doi=doi, article_number=article_number),
                    "url": landing_url,
                },
                ("GET", rest_url): RequestFailure(
                    401, f"HTTP 401 for {rest_url}", url=rest_url
                ),
            }
        )
        client = IeeeClient(transport, {})
        browser_payload = _raw_ieee_html_payload(
            doi=doi,
            article_number=article_number,
            html_text=_dynamic_html(article_number).decode("utf-8"),
            source_url=rest_url,
            trace_markers=[
                "fulltext:ieee_html_fail",
                "fulltext:ieee_browser_html_ok",
                "fulltext:ieee_html_ok",
            ],
        )

        with (
            mock.patch.object(
                client, "_fetch_browser_html_payload", return_value=browser_payload
            ) as mocked_browser,
            mock.patch.object(ieee_provider, "fetch_pdf_over_http") as mocked_pdf,
        ):
            raw_payload = client.fetch_raw_fulltext(
                doi, {"doi": doi, "landing_page_url": landing_url}
            )
            article = client.to_article_model({"doi": doi}, raw_payload)

        self.assertEqual(raw_payload.content.route_kind, "html")
        self.assertEqual(raw_payload.content.fetcher, "playwright_html")
        self.assertEqual(article.source, "ieee_html")
        self.assertEqual(article.quality.content_kind, "fulltext")
        self.assertIn("fulltext:ieee_browser_html_ok", article.quality.source_trail)
        self.assertIn("fulltext:ieee_html_ok", article.quality.source_trail)
        mocked_browser.assert_called_once()
        self.assertEqual(
            mocked_browser.call_args.kwargs["direct_html_failure"].code, "no_access"
        )
        mocked_pdf.assert_not_called()

    def test_browser_html_fallback_uses_response_listener_without_wait_for_response_api(
        self,
    ) -> None:
        doi = "10.1109/TIM.2024.3509573"
        article_number = "10772041"
        document_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        rest_url = f"https://ieeexplore.ieee.org/rest/document/{article_number}/?logAccess=true"
        landing_attempt = _ieee_metadata.IeeeLandingAttempt(
            normalized_doi=doi,
            landing_url=document_url,
            response_url=document_url,
            html_text=_landing_html(doi=doi, article_number=article_number).decode(
                "utf-8"
            ),
            merged_metadata={
                "doi": doi,
                "title": "IEEE Dynamic Article",
                "abstract": "IEEE abstract text.",
                "article_number": article_number,
                "articleNumber": article_number,
                "landing_page_url": document_url,
            },
            article_number=article_number,
            landing_metadata={},
        )

        class FakeResponse:
            url = rest_url
            status = 200
            headers = {"content-type": "text/html;charset=utf-8"}

            def body(self):
                return _dynamic_html(article_number)

            def all_headers(self):
                return dict(self.headers)

        class FakeRequest:
            resource_type = "xhr"

        class FakeRoute:
            request = FakeRequest()

            def continue_(self):
                return None

        class FakePage:
            url = document_url

            def __init__(self):
                self._response_handler = None
                self.closed = False

            def on(self, event_name, handler):
                assert event_name == "response"
                self._response_handler = handler

            def goto(self, url, **kwargs):
                assert url == document_url
                del kwargs
                if self._response_handler is not None:
                    self._response_handler(FakeResponse())
                return None

            def wait_for_timeout(self, timeout):
                assert (
                    timeout == _ieee_browser_html.IEEE_BROWSER_HTML_REST_WAIT_TIMEOUT_MS
                )

            def close(self):
                self.closed = True

        class FakeBrowserContext:
            def __init__(self):
                self.page = FakePage()
                self.closed = False
                self.route_pattern = ""

            def route(self, pattern, handler):
                self.route_pattern = pattern
                handler(FakeRoute())

            def new_page(self):
                return self.page

            def close(self):
                self.closed = True

        fake_browser_context = FakeBrowserContext()
        fake_runtime = mock.Mock()
        fake_runtime.env = {"PAPER_FETCH_BROWSER_BACKEND": "camoufox"}
        fake_runtime.new_browser_context_for_runtime_config.return_value = (
            fake_browser_context
        )
        client = IeeeClient(RecordingTransport({}), {})

        raw_payload = client._fetch_browser_html_payload(
            landing_attempt,
            direct_html_failure=ieee_provider.ProviderFailure(
                "no_access", "Forced direct failure."
            ),
            context=fake_runtime,
        )

        self.assertEqual(raw_payload.content.route_kind, "html")
        self.assertEqual(raw_payload.content.fetcher, "camoufox_ieee_html")
        self.assertEqual(
            raw_payload.content.diagnostics["browser_html"]["payload_source"],
            "rest_response",
        )
        self.assertEqual(
            raw_payload.content.diagnostics["browser_html"]["direct_html_failure"][
                "code"
            ],
            "no_access",
        )
        self.assertEqual(fake_browser_context.route_pattern, "**/*")
        self.assertTrue(fake_browser_context.closed)
        self.assertTrue(fake_browser_context.page.closed)

    def test_direct_rest_and_browser_html_failures_continue_to_pdf_fallback(
        self,
    ) -> None:
        doi = "10.1109/MPER.1985.5526567"
        article_number = "5526567"
        landing_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        rest_url = f"https://ieeexplore.ieee.org/rest/document/{article_number}/?logAccess=true"
        transport = RecordingTransport(
            {
                ("GET", landing_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": _landing_html(
                        doi=doi, article_number=article_number, dynamic=False
                    ),
                    "url": landing_url,
                },
                ("GET", rest_url): RequestFailure(
                    401, f"HTTP 401 for {rest_url}", url=rest_url
                ),
            }
        )
        client = IeeeClient(transport, {})
        browser_failure = ieee_provider.ProviderFailure(
            "no_result", "Browser HTML did not expose #article."
        )
        pdf_result = PdfFetchResult(
            source_url=f"https://ieeexplore.ieee.org/iel7/{article_number}.pdf",
            final_url=f"https://ieeexplore.ieee.org/iel7/{article_number}.pdf",
            pdf_bytes=b"%PDF-1.7 ieee",
            markdown_text="# IEEE PDF Article\n\n## Results\n\n"
            + ("PDF body text " * 160),
            suggested_filename=f"{article_number}.pdf",
            assets=[
                {
                    "kind": "figure",
                    "heading": "Figure 1",
                    "url": "body_assets/ieee-f1.png",
                    "path": "/tmp/ieee-f1.png",
                    "section": "body",
                    "render_state": "inline",
                }
            ],
        )

        with (
            mock.patch.object(
                client, "_fetch_browser_html_payload", side_effect=browser_failure
            ) as mocked_browser,
            mock.patch.object(
                ieee_provider, "fetch_pdf_over_http", return_value=pdf_result
            ) as mocked_pdf,
        ):
            raw_payload = client.fetch_raw_fulltext(
                doi, {"doi": doi, "landing_page_url": landing_url}
            )
            article = client.to_article_model({"doi": doi}, raw_payload)

        self.assertEqual(raw_payload.content.route_kind, "pdf_fallback")
        self.assertEqual(article.source, "ieee_pdf")
        self.assertIn("fulltext:ieee_html_fail", article.quality.source_trail)
        self.assertIn("fulltext:ieee_browser_html_fail", article.quality.source_trail)
        self.assertIn("fulltext:ieee_pdf_fallback_ok", article.quality.source_trail)
        self.assertEqual(
            raw_payload.content.extracted_assets[0]["url"], "body_assets/ieee-f1.png"
        )
        self.assertEqual(article.assets[0].url, "body_assets/ieee-f1.png")
        self.assertEqual(article.assets[0].section, "body")
        self.assertIn(
            "Browser HTML fallback: Browser HTML did not expose #article.",
            raw_payload.content.html_failure_message,
        )
        mocked_browser.assert_called_once()
        mocked_pdf.assert_called_once()

    def test_direct_rest_browser_html_and_pdf_failures_return_abstract_only(
        self,
    ) -> None:
        doi = "10.1109/PGEC.1967.264619"
        article_number = "4038993"
        landing_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        rest_url = f"https://ieeexplore.ieee.org/rest/document/{article_number}/?logAccess=true"
        transport = RecordingTransport(
            {
                ("GET", landing_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": _landing_html(
                        doi=doi,
                        article_number=article_number,
                        dynamic=False,
                        abstract="Legacy IEEE abstract only.",
                    ),
                    "url": landing_url,
                },
                ("GET", rest_url): RequestFailure(
                    401, f"HTTP 401 for {rest_url}", url=rest_url
                ),
            }
        )
        client = IeeeClient(transport, {})
        browser_failure = ieee_provider.ProviderFailure(
            "no_result", "Browser HTML did not expose #article."
        )

        with (
            mock.patch.object(
                client, "_fetch_browser_html_payload", side_effect=browser_failure
            ),
            mock.patch.object(
                ieee_provider,
                "fetch_pdf_over_http",
                side_effect=PdfFetchFailure(
                    "downloaded_file_not_pdf",
                    "Direct PDF did not return a PDF file.",
                    details={"status": 200, "content_type": "text/html"},
                ),
            ),
            mock.patch.object(
                ieee_provider,
                "fetch_pdf_with_playwright",
                side_effect=PdfFetchFailure(
                    "publisher_access_challenge", "Browser PDF reached an access page."
                ),
            ),
        ):
            raw_payload = client.fetch_raw_fulltext(
                doi, {"doi": doi, "landing_page_url": landing_url}
            )
            article = client.to_article_model({"doi": doi}, raw_payload)

        self.assertEqual(raw_payload.content.route_kind, "abstract_only")
        self.assertEqual(article.quality.content_kind, "abstract_only")
        self.assertIn("fulltext:ieee_html_fail", article.quality.source_trail)
        self.assertIn("fulltext:ieee_browser_html_fail", article.quality.source_trail)
        self.assertIn("fulltext:ieee_pdf_fail", article.quality.source_trail)
        warning_blob = "\n".join(raw_payload.warnings)
        self.assertIn("IEEE dynamic HTML route was not usable", warning_blob)
        self.assertIn("IEEE browser HTML fallback was not usable", warning_blob)
        self.assertIn("IEEE PDF fallback was not usable", warning_blob)
        diagnostics = raw_payload.content.diagnostics
        self.assertEqual(diagnostics["html_failure"]["code"], "no_access")
        self.assertEqual(
            diagnostics["browser_html_failure"]["message"],
            "Browser HTML did not expose #article.",
        )
