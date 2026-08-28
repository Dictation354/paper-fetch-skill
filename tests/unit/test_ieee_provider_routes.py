# ruff: noqa: F403,F405
from __future__ import annotations

from paper_fetch.providers import (
    _ieee_block_page,
    _ieee_browser_html,
    _ieee_html,
    _ieee_landing,
    _ieee_metadata,
    _ieee_url,
    browser_runtime,
)
from paper_fetch.extraction.html.html_tags import HTML_DROP_TAGS

from ._ieee_provider_support import *


class _FakeIeeeBrowserResponse:
    def __init__(
        self,
        url: str,
        body: bytes,
        *,
        status: int | None = 200,
        content_type: str | None = "text/html;charset=utf-8",
    ) -> None:
        self.url = url
        self.status = status
        self.headers = (
            {"content-type": content_type} if content_type is not None else {}
        )
        self._body = body
        self.body_calls = 0

    def body(self) -> bytes:
        self.body_calls += 1
        return self._body

    def all_headers(self) -> dict[str, str]:
        return dict(self.headers)


class _FakeIeeeBrowserLocator:
    def __init__(self, page: _FakeIeeeBrowserPage) -> None:
        self._page = page

    def count(self) -> int:
        return int(_ieee_html._find_ieee_article(self._page.html_text) is not None)


class _FakeIeeeBrowserPage:
    def __init__(
        self,
        document_url: str,
        *,
        initial_responses: list[_FakeIeeeBrowserResponse] | None = None,
        delayed_responses: list[_FakeIeeeBrowserResponse] | None = None,
        html_text: str = "<html><body>IEEE document shell</body></html>",
        delayed_html_text: str | None = None,
    ) -> None:
        self.url = document_url
        self.html_text = html_text
        self.initial_responses = list(initial_responses or [])
        self.delayed_responses = list(delayed_responses or [])
        self.delayed_html_text = delayed_html_text
        self.closed = False
        self._response_handler = None
        self.route_pattern = ""
        self.route_handler = None

    def route(self, pattern, handler):
        self.route_pattern = pattern
        self.route_handler = handler

    def on(self, event_name, handler):
        assert event_name == "response"
        self._response_handler = handler

    def _emit(self, responses: list[_FakeIeeeBrowserResponse]) -> None:
        if self._response_handler is None:
            return
        for response in responses:
            self._response_handler(response)

    def goto(self, url, **kwargs):
        assert url == self.url
        del kwargs
        self._emit(self.initial_responses)
        return mock.Mock(status=200)

    def wait_for_timeout(self, timeout):
        assert timeout > 0
        delayed, self.delayed_responses = self.delayed_responses, []
        self._emit(delayed)
        if self.delayed_html_text is not None:
            self.html_text, self.delayed_html_text = self.delayed_html_text, None

    def locator(self, selector):
        assert selector == "#article"
        return _FakeIeeeBrowserLocator(self)

    def content(self):
        return self.html_text

    def title(self):
        return "IEEE Dynamic Article"

    def evaluate(self, expression):
        assert expression == "() => navigator.userAgent"
        return "Mozilla/5.0 Fake IEEE Browser"

    def close(self):
        self.closed = True


class _FakeIeeeBrowserContext:
    def __init__(self, page: _FakeIeeeBrowserPage) -> None:
        self.page = page
        self.closed = False
        self.route_pattern = ""
        self.route_handler = None

    def route(self, pattern, handler):
        self.route_pattern = pattern
        self.route_handler = handler

    def new_page(self):
        return self.page

    def cookies(self, urls=None):
        del urls
        return []

    def close(self):
        self.closed = True


def _browser_landing_attempt(
    doi: str,
    article_number: str,
) -> _ieee_metadata.IeeeLandingAttempt:
    document_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
    return _ieee_metadata.IeeeLandingAttempt(
        normalized_doi=doi,
        landing_url=document_url,
        response_url=document_url,
        html_text=_landing_html(doi=doi, article_number=article_number).decode("utf-8"),
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


class IeeeProviderRouteTests(unittest.TestCase):
    def test_browser_html_accepts_native_final_url_without_context_route(self) -> None:
        doi = "10.1109/TIM.2024.3509573"
        article_number = "10772041"
        landing_attempt = _browser_landing_attempt(doi, article_number)
        document_url = landing_attempt.landing_url
        rest_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/"
            "?logAccess=true"
        )

        class RedirectPage(_FakeIeeeBrowserPage):
            def goto(self, url, **kwargs):
                response = super().goto(url, **kwargs)
                self.url = "http://127.0.0.1/internal"
                return response

        page = RedirectPage(
            document_url,
            html_text=_dynamic_html(article_number).decode("utf-8"),
        )
        fake_context = _FakeIeeeBrowserContext(page)
        fake_runtime = mock.Mock()
        fake_runtime.env = {"PAPER_FETCH_BROWSER_BACKEND": "camoufox"}
        fake_runtime.new_browser_context_for_runtime_config.return_value = fake_context
        runtime_config = browser_runtime.BrowserRuntimeConfig(
            provider="ieee",
            doi=doi,
            artifact_dir=Path(tempfile.mkdtemp()),
            headless=True,
            user_agent=None,
            backend="camoufox",
        )
        result = _ieee_browser_html.fetch_ieee_browser_html_payload(
            provider_name="ieee",
            browser_user_agent=None,
            landing_attempt=landing_attempt,
            document_url=document_url,
            rest_url=rest_url,
            direct_html_failure=None,
            context=fake_runtime,
            runtime_config=runtime_config,
            extraction_assets=lambda _extraction, _landing: [],
        )

        self.assertEqual(result.content.route_kind, "html")
        self.assertEqual(fake_context.route_pattern, "")
        self.assertEqual(page.route_pattern, "**/*")

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
        browser_kwargs = mocked_browser.call_args.kwargs
        self.assertEqual(
            browser_kwargs["wait_seconds"],
            _ieee_landing.IEEE_LANDING_BROWSER_READINESS_WAIT_SECONDS,
        )
        readiness = browser_kwargs["readiness"]
        self.assertEqual(readiness.selector, "#article")
        self.assertEqual(readiness.selector_text, article_number)
        self.assertTrue(readiness.require_selector)

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
        """rule: rule-ieee-html-access-waterfall"""
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

    def test_ieee_block_page_detection_ignores_nonvisible_html_tags(self) -> None:
        """rule: rule-ieee-html-access-waterfall"""
        article_number = "10772041"
        source_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/"
            "?logAccess=true"
        )
        article_html = _dynamic_html(article_number).decode("utf-8")

        for tag_name in HTML_DROP_TAGS:
            with self.subTest(tag_name=tag_name):
                html = article_html.replace(
                    "</response>",
                    f"<{tag_name}>captcha verify you are human</{tag_name}></response>",
                )

                self.assertFalse(_ieee_block_page._looks_like_ieee_block_page(html))
                extraction = _ieee_html._extract_ieee_html(
                    html,
                    source_url,
                    metadata={"title": "IEEE Dynamic Article"},
                )
                self.assertIn("Introduction", extraction.markdown_text)
                self.assertIn("Results", extraction.markdown_text)

    def test_ieee_block_page_detection_rejects_visible_challenge_with_article(
        self,
    ) -> None:
        """rule: rule-ieee-html-access-waterfall"""
        article_number = "10772041"
        html = (
            _dynamic_html(article_number)
            .decode("utf-8")
            .replace(
                "</response>",
                "<div class='challenge'>Captcha: verify you are human.</div></response>",
            )
        )

        self.assertTrue(_ieee_block_page._looks_like_ieee_block_page(html))
        with self.assertRaises(ieee_provider.ProviderFailure):
            _ieee_html._extract_ieee_html(
                html,
                f"https://ieeexplore.ieee.org/rest/document/{article_number}/"
                "?logAccess=true",
                metadata={"title": "IEEE Dynamic Article"},
            )

    def test_ieee_block_page_cache_key_tracks_visible_text_scanner(self) -> None:
        context = RuntimeContext(env={})
        html = "<html><body>Verify you are human.</body></html>"
        try:
            with mock.patch.object(
                context,
                "build_parse_cache_key",
                wraps=context.build_parse_cache_key,
            ) as build_cache_key:
                self.assertTrue(
                    _ieee_block_page._looks_like_ieee_block_page(
                        html,
                        context=context,
                        source_url="https://ieeexplore.ieee.org/document/10772041/",
                    )
                )

            config = build_cache_key.call_args.kwargs["config"]
            self.assertEqual(
                config["scanner_version"],
                _ieee_block_page.IEEE_BLOCK_PAGE_SCANNER_VERSION,
            )
            self.assertEqual(config["drop_tags"], HTML_DROP_TAGS)
        finally:
            context.close()

    def test_landing_attempt_merges_ieee_keywords_and_reference_text(self) -> None:
        """rule: rule-ieee-landing-metadata-references"""
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
        """rule: rule-ieee-landing-metadata-references"""
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
                raise AssertionError("IEEE REST browser body must not be read")

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
                raise AssertionError(f"ready DOM must not poll: {timeout}")

            def locator(self, selector):
                assert selector == "#article"
                return SimpleNamespace(count=lambda: 1)

            def content(self):
                return _dynamic_html(article_number).decode("utf-8")

            def title(self):
                return "IEEE Dynamic Article"

            def evaluate(self, expression):
                assert expression == "() => navigator.userAgent"
                return "Mozilla/5.0 Fake IEEE Browser"

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

        # The response listener sees REST metadata, while the page DOM
        # is the only full-text body source.
        fake_browser_context = _FakeIeeeBrowserContext(
            _FakeIeeeBrowserPage(
                document_url,
                initial_responses=[
                    _FakeIeeeBrowserResponse(rest_url, _dynamic_html(article_number))
                ],
                html_text=_dynamic_html(article_number).decode("utf-8"),
            )
        )
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
            "dom_article",
        )
        self.assertEqual(
            raw_payload.content.diagnostics["browser_html"]["direct_html_failure"][
                "code"
            ],
            "no_access",
        )
        self.assertEqual(fake_browser_context.route_pattern, "")
        self.assertEqual(fake_browser_context.page.route_pattern, "**/*")
        self.assertTrue(fake_browser_context.closed)
        self.assertTrue(fake_browser_context.page.closed)

    def test_browser_rest_selection_keeps_metadata_without_reading_body(self) -> None:
        article_number = "10772041"
        rest_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/"
            "?logAccess=true"
        )
        valid_response = _FakeIeeeBrowserResponse(
            rest_url,
            _dynamic_html(article_number),
        )
        invalid_response = _FakeIeeeBrowserResponse(
            rest_url,
            b"<html><body>Temporary IEEE REST shell</body></html>",
        )

        selection = _ieee_browser_html._capture_rest_html(
            [valid_response, invalid_response],
            rest_url,
        )

        self.assertIsNone(selection.selected)
        self.assertEqual(selection.response_count, 2)
        self.assertEqual(selection.invalid_response_count, 2)
        self.assertIsNotNone(selection.latest_invalid)
        self.assertEqual(selection.latest_invalid.html_text, "")
        self.assertEqual(valid_response.body_calls, 0)
        self.assertEqual(invalid_response.body_calls, 0)

    def test_browser_rest_selection_rejects_mismatched_article_number(self) -> None:
        article_number = "10772041"
        rest_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/"
            "?logAccess=true"
        )

        selection = _ieee_browser_html._capture_rest_html(
            [
                _FakeIeeeBrowserResponse(
                    rest_url,
                    _dynamic_html("99999999"),
                )
            ],
            rest_url,
            article_number,
        )

        self.assertIsNone(selection.selected)
        self.assertEqual(selection.response_count, 1)
        self.assertEqual(selection.invalid_response_count, 1)
        self.assertIsNotNone(selection.latest_invalid)

    def test_browser_rest_selection_rejects_non_html_and_non_success_status(
        self,
    ) -> None:
        article_number = "10772041"
        rest_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/"
            "?logAccess=true"
        )
        html_body = _dynamic_html(article_number)
        selection = _ieee_browser_html._capture_rest_html(
            [
                _FakeIeeeBrowserResponse(
                    rest_url,
                    html_body,
                    content_type="application/json",
                ),
                _FakeIeeeBrowserResponse(rest_url, html_body, status=503),
            ],
            rest_url,
        )

        self.assertIsNone(selection.selected)
        self.assertEqual(selection.response_count, 2)
        self.assertEqual(selection.invalid_response_count, 2)

    def test_browser_rest_unknown_metadata_remains_non_body_candidate(self) -> None:
        article_number = "10772041"
        rest_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/"
            "?logAccess=true"
        )

        selection = _ieee_browser_html._capture_rest_html(
            [
                _FakeIeeeBrowserResponse(
                    rest_url,
                    _dynamic_html(article_number),
                    status=None,
                    content_type=None,
                )
            ],
            rest_url,
        )

        self.assertIsNone(selection.selected)
        self.assertEqual(selection.response_count, 1)
        self.assertEqual(selection.invalid_response_count, 1)

    def test_browser_html_waits_for_dom_while_rest_bodies_remain_unread(self) -> None:
        doi = "10.1109/TIM.2024.3509573"
        article_number = "10772041"
        document_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        rest_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/"
            "?logAccess=true"
        )
        page = _FakeIeeeBrowserPage(
            document_url,
            initial_responses=[
                _FakeIeeeBrowserResponse(
                    rest_url,
                    b"<html><body>Temporary IEEE REST shell</body></html>",
                )
            ],
            delayed_responses=[
                _FakeIeeeBrowserResponse(rest_url, _dynamic_html(article_number))
            ],
            delayed_html_text=_dynamic_html(article_number).decode("utf-8"),
        )
        fake_browser_context = _FakeIeeeBrowserContext(page)
        fake_runtime = mock.Mock()
        fake_runtime.env = {"PAPER_FETCH_BROWSER_BACKEND": "camoufox"}
        fake_runtime.new_browser_context_for_runtime_config.return_value = (
            fake_browser_context
        )
        client = IeeeClient(RecordingTransport({}), {})

        raw_payload = client._fetch_browser_html_payload(
            _browser_landing_attempt(doi, article_number),
            direct_html_failure=ieee_provider.ProviderFailure(
                "no_access", "Forced direct failure."
            ),
            context=fake_runtime,
        )

        browser_diagnostics = raw_payload.content.diagnostics["browser_html"]
        self.assertEqual(browser_diagnostics["payload_source"], "dom_article")
        self.assertEqual(browser_diagnostics["rest_response_count"], 2)
        self.assertEqual(browser_diagnostics["invalid_rest_response_count"], 2)
        self.assertTrue(fake_browser_context.closed)
        self.assertTrue(page.closed)

    def test_browser_html_uses_ready_dom_after_invalid_rest_response(self) -> None:
        doi = "10.1109/TIM.2024.3509573"
        article_number = "10772041"
        document_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        rest_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/"
            "?logAccess=true"
        )
        page = _FakeIeeeBrowserPage(
            document_url,
            initial_responses=[
                _FakeIeeeBrowserResponse(
                    rest_url,
                    b"<html><body>Temporary IEEE REST shell</body></html>",
                )
            ],
            html_text=_dynamic_html(article_number).decode("utf-8"),
        )
        fake_browser_context = _FakeIeeeBrowserContext(page)
        fake_runtime = mock.Mock()
        fake_runtime.env = {"PAPER_FETCH_BROWSER_BACKEND": "camoufox"}
        fake_runtime.new_browser_context_for_runtime_config.return_value = (
            fake_browser_context
        )
        client = IeeeClient(RecordingTransport({}), {})

        raw_payload = client._fetch_browser_html_payload(
            _browser_landing_attempt(doi, article_number),
            direct_html_failure=ieee_provider.ProviderFailure(
                "no_access", "Forced direct failure."
            ),
            context=fake_runtime,
        )

        browser_diagnostics = raw_payload.content.diagnostics["browser_html"]
        self.assertEqual(browser_diagnostics["payload_source"], "dom_article")
        self.assertEqual(browser_diagnostics["rest_response_count"], 1)
        self.assertEqual(browser_diagnostics["invalid_rest_response_count"], 1)

    def test_browser_html_waits_past_mismatched_article_dom(self) -> None:
        doi = "10.1109/TIM.2024.3509573"
        article_number = "10772041"
        document_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        page = _FakeIeeeBrowserPage(
            document_url,
            html_text=(
                "<html><body><article id='article'>99999999</article></body></html>"
            ),
            delayed_html_text=_dynamic_html(article_number).decode("utf-8"),
        )
        fake_browser_context = _FakeIeeeBrowserContext(page)
        fake_runtime = mock.Mock()
        fake_runtime.env = {"PAPER_FETCH_BROWSER_BACKEND": "camoufox"}
        fake_runtime.new_browser_context_for_runtime_config.return_value = (
            fake_browser_context
        )
        client = IeeeClient(RecordingTransport({}), {})

        raw_payload = client._fetch_browser_html_payload(
            _browser_landing_attempt(doi, article_number),
            direct_html_failure=ieee_provider.ProviderFailure(
                "no_access", "Forced direct failure."
            ),
            context=fake_runtime,
        )

        self.assertEqual(
            raw_payload.content.diagnostics["browser_html"]["payload_source"],
            "dom_article",
        )
        self.assertIsNone(page.delayed_html_text)

    def test_ready_browser_article_ignores_hidden_aws_waf_script(self) -> None:
        doi = "10.1109/TIM.2024.3509573"
        article_number = "10772041"
        document_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        article_html = (
            _dynamic_html(article_number)
            .decode("utf-8")
            .replace(
                "</response>",
                (
                    "<script src='https://example.token.awswaf.com/challenge.js'>"
                    "</script><noscript>Verify you're not a robot.</noscript></response>"
                ),
            )
        )
        page = _FakeIeeeBrowserPage(document_url, html_text=article_html)
        fake_browser_context = _FakeIeeeBrowserContext(page)
        fake_runtime = mock.Mock()
        fake_runtime.env = {"PAPER_FETCH_BROWSER_BACKEND": "camoufox"}
        fake_runtime.new_browser_context_for_runtime_config.return_value = (
            fake_browser_context
        )
        client = IeeeClient(RecordingTransport({}), {})

        raw_payload = client._fetch_browser_html_payload(
            _browser_landing_attempt(doi, article_number),
            direct_html_failure=ieee_provider.ProviderFailure(
                "no_access", "Forced direct failure."
            ),
            context=fake_runtime,
        )

        self.assertEqual(
            raw_payload.content.diagnostics["browser_html"]["payload_source"],
            "dom_article",
        )

    def test_invalid_browser_rest_timeout_persists_page_diagnostics(self) -> None:
        doi = "10.1109/TIM.2024.3509573"
        article_number = "10772041"
        document_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        rest_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/"
            "?logAccess=true"
        )
        page = _FakeIeeeBrowserPage(
            document_url,
            initial_responses=[
                _FakeIeeeBrowserResponse(
                    rest_url,
                    b"<html><body>Temporary IEEE REST shell</body></html>",
                )
            ],
            html_text="<html><body>Temporary IEEE document shell</body></html>",
        )
        fake_browser_context = _FakeIeeeBrowserContext(page)
        client = IeeeClient(RecordingTransport({}), {})

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            runtime = RuntimeContext(
                env={
                    "PAPER_FETCH_BROWSER_BACKEND": "camoufox",
                    "PAPER_FETCH_BROWSER_USER_DATA_DIR": str(
                        output_dir / "browser-profile"
                    ),
                },
                download_dir=output_dir,
                artifact_mode="all",
            )
            try:
                with (
                    mock.patch.object(
                        runtime,
                        "new_browser_context_for_runtime_config",
                        return_value=fake_browser_context,
                    ),
                    mock.patch.object(
                        _ieee_browser_html,
                        "IEEE_BROWSER_HTML_REST_WAIT_TIMEOUT_MS",
                        1,
                    ),
                    self.assertRaises(ieee_provider.ProviderFailure) as raised,
                ):
                    client._fetch_browser_html_payload(
                        _browser_landing_attempt(doi, article_number),
                        direct_html_failure=ieee_provider.ProviderFailure(
                            "no_access", "Forced direct failure."
                        ),
                        context=runtime,
                    )

                failure = raised.exception
                self.assertEqual(failure.error_category, "browser_rest_wait_timeout")
                self.assertTrue(failure.retryable)
                self.assertEqual(failure.stage, "rest_readiness")
                self.assertEqual(failure.details["rest_response_count"], 1)
                self.assertEqual(failure.details["invalid_rest_response_count"], 1)
                self.assertEqual(len(runtime.diagnostic_artifacts), 4)
                for artifact in runtime.diagnostic_artifacts:
                    self.assertTrue(Path(artifact["path"]).is_file())
                self.assertEqual(
                    {artifact["route"] for artifact in runtime.diagnostic_artifacts},
                    {"browser_html_rest", "browser_html_dom"},
                )
            finally:
                runtime.close()

    def test_browser_rest_challenge_body_is_not_materialized(self) -> None:
        doi = "10.1109/TIM.2024.3509573"
        article_number = "10772041"
        document_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        rest_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/"
            "?logAccess=true"
        )
        page = _FakeIeeeBrowserPage(
            document_url,
            initial_responses=[
                _FakeIeeeBrowserResponse(
                    rest_url,
                    b"<html><body>Cloudflare: verify you are human</body></html>",
                )
            ],
            html_text="<html><body>IEEE document shell</body></html>",
        )
        fake_browser_context = _FakeIeeeBrowserContext(page)
        client = IeeeClient(RecordingTransport({}), {})

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = RuntimeContext(
                env={
                    "PAPER_FETCH_BROWSER_BACKEND": "camoufox",
                    "PAPER_FETCH_BROWSER_USER_DATA_DIR": str(
                        Path(tmpdir) / "browser-profile"
                    ),
                },
                artifact_mode="none",
            )
            try:
                with (
                    mock.patch.object(
                        runtime,
                        "new_browser_context_for_runtime_config",
                        return_value=fake_browser_context,
                    ),
                    mock.patch.object(
                        _ieee_browser_html,
                        "IEEE_BROWSER_HTML_REST_WAIT_TIMEOUT_MS",
                        1,
                    ),
                    self.assertRaises(ieee_provider.ProviderFailure) as raised,
                ):
                    client._fetch_browser_html_payload(
                        _browser_landing_attempt(doi, article_number),
                        direct_html_failure=ieee_provider.ProviderFailure(
                            "no_access", "Forced direct failure."
                        ),
                        context=runtime,
                    )

                failure = raised.exception
                self.assertEqual(failure.error_category, "browser_rest_wait_timeout")
                self.assertTrue(failure.retryable)
                self.assertEqual(failure.stage, "rest_readiness")
                self.assertEqual(page.initial_responses[0].body_calls, 0)
            finally:
                runtime.close()

    def test_formal_browser_html_reports_persistent_aws_waf(self) -> None:
        doi = "10.1109/TIM.2024.3509573"
        article_number = "10772041"
        document_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        rest_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/"
            "?logAccess=true"
        )
        waf_html = (
            b"<html><head><script src='https://example.token.awswaf.com/"
            b"challenge.js'></script></head><body><div id='challenge-container'>"
            b"</div><noscript>Verify you're not a robot.</noscript></body></html>"
        )
        page = _FakeIeeeBrowserPage(
            document_url,
            initial_responses=[
                _FakeIeeeBrowserResponse(rest_url, waf_html, status=202)
            ],
            html_text=waf_html.decode("utf-8"),
        )
        fake_browser_context = _FakeIeeeBrowserContext(page)
        client = IeeeClient(RecordingTransport({}), {})

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = RuntimeContext(
                env={
                    "PAPER_FETCH_BROWSER_BACKEND": "camoufox",
                    "PAPER_FETCH_BROWSER_USER_DATA_DIR": str(
                        Path(tmpdir) / "browser-profile"
                    ),
                },
                artifact_mode="none",
            )
            try:
                with (
                    mock.patch.object(
                        runtime,
                        "new_browser_context_for_runtime_config",
                        return_value=fake_browser_context,
                    ),
                    mock.patch.object(
                        _ieee_browser_html,
                        "IEEE_BROWSER_HTML_REST_WAIT_TIMEOUT_MS",
                        1,
                    ),
                    self.assertRaises(ieee_provider.ProviderFailure) as raised,
                ):
                    client._fetch_browser_html_payload(
                        _browser_landing_attempt(doi, article_number),
                        direct_html_failure=ieee_provider.ProviderFailure(
                            "no_access", "Forced direct failure."
                        ),
                        context=runtime,
                    )

                failure = raised.exception
                self.assertEqual(failure.error_category, "aws_waf_challenge")
                self.assertFalse(failure.retryable)
                self.assertEqual(failure.stage, "block_detection")
                self.assertEqual(failure.details["challenge_provider"], "aws_waf")
                self.assertEqual(
                    failure.details["legacy_reason_code"],
                    "cloudflare_challenge",
                )
            finally:
                runtime.close()

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
