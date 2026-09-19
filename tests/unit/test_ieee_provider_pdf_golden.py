from __future__ import annotations
from paper_fetch.providers import _ieee_metadata
from tests.support._ieee_provider_support import *
# ruff: noqa: F403,F405


class IeeeProviderPdfGoldenTests(unittest.TestCase):
    def test_ieee_pdf_browser_recovery_uses_frozen_allow_list(self) -> None:
        for status in (404, 410, 429):
            with self.subTest(status=status):
                self.assertFalse(
                    ieee_provider._ieee_pdf_browser_recovery_allowed(
                        PdfFetchFailure(
                            "pdf_download_failed",
                            f"HTTP {status}",
                            details={
                                "status": status,
                                "content_type": "text/html",
                            },
                        )
                    )
                )

        for failure in (
            PdfFetchFailure(
                "pdf_download_failed",
                "HTTP 403",
                details={"status": 403, "content_type": "text/html"},
            ),
            PdfFetchFailure(
                "downloaded_file_not_pdf",
                "HTML challenge",
                details={
                    "status": 200,
                    "content_type": "text/html",
                    "reason": "publisher_access_challenge",
                },
            ),
            PdfFetchFailure(
                "pdf_download_failed",
                "timed out",
                details={"error_category": "timeout"},
            ),
        ):
            with self.subTest(message=failure.message):
                self.assertTrue(
                    ieee_provider._ieee_pdf_browser_recovery_allowed(failure)
                )

    def test_ieee_direct_pdf_404_does_not_load_browser_runtime(self) -> None:
        doi = "10.1109/example.404"
        article_number = "404404"
        landing_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        transport = RecordingTransport({})
        client = IeeeClient(transport, {})
        landing_attempt = _ieee_metadata.IeeeLandingAttempt(
            normalized_doi=doi,
            landing_url=landing_url,
            response_url=landing_url,
            html_text="",
            merged_metadata={"doi": doi, "article_number": article_number},
            article_number=article_number,
            landing_metadata={},
        )
        context = RuntimeContext(env={}, transport=transport)

        with (
            mock.patch.object(
                ieee_provider,
                "fetch_pdf_over_http",
                side_effect=PdfFetchFailure(
                    "pdf_download_failed",
                    "HTTP 404",
                    details={"status": 404, "content_type": "text/html"},
                ),
            ),
            mock.patch.object(
                ieee_provider.browser_runtime, "load_runtime_config"
            ) as mocked_runtime,
            self.assertRaises(PdfFetchFailure),
        ):
            client._fetch_pdf_payload(
                landing_attempt,
                html_failure_message="HTML unavailable.",
                warnings=[],
                context=context,
            )

        mocked_runtime.assert_not_called()

    def test_empty_dynamic_html_falls_back_to_pdf_text_only(self) -> None:
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
                ("GET", rest_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": b'<?xml version="1.0"?><div id="BodyWrapper"><div id="article"/></div>',
                    "url": rest_url,
                },
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
            mock.patch.object(
                client,
                "_fetch_browser_html_payload",
                side_effect=ieee_provider.ProviderFailure(
                    "no_result", "Browser HTML did not expose #article."
                ),
            ),
            mock.patch.object(
                ieee_provider, "fetch_pdf_over_http", return_value=pdf_result
            ) as mocked_pdf,
        ):
            raw_payload = client.fetch_raw_fulltext(
                doi, {"doi": doi, "landing_page_url": landing_url}
            )
            article = client.to_article_model({"doi": doi}, raw_payload)

        self.assertEqual(raw_payload.content.route_kind, "pdf_fallback")
        self.assertTrue(raw_payload.content.needs_local_copy)
        self.assertEqual(article.source, "ieee_pdf")
        self.assertEqual(article.quality.content_kind, "fulltext")
        self.assertIn("fulltext:ieee_html_fail", article.quality.source_trail)
        self.assertIn("fulltext:ieee_pdf_fallback_ok", article.quality.source_trail)
        artifacts = client.describe_artifacts(raw_payload)
        self.assertFalse(artifacts.allow_related_assets)
        self.assertTrue(artifacts.text_only)
        self.assertIn(
            "download:ieee_assets_skipped_text_only",
            [event.marker() for event in artifacts.skip_trace],
        )
        candidates = mocked_pdf.call_args.args[1]
        self.assertEqual(
            candidates,
            [
                f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={article_number}",
                f"https://ieeexplore.ieee.org/iel7/6287639/10380310/{article_number}.pdf",
                f"https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber={article_number}",
            ],
        )
        headers = mocked_pdf.call_args.kwargs["headers"]
        self.assertEqual(headers["Referer"], landing_url)

    def test_direct_pdf_html_wrapper_enters_seeded_browser_pdf_fallback(self) -> None:
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
                ("GET", rest_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": b'<?xml version="1.0"?><div id="BodyWrapper"><div id="article"/></div>',
                    "url": rest_url,
                },
            }
        )
        client = IeeeClient(transport, {})
        direct_failure = PdfFetchFailure(
            "downloaded_file_not_pdf",
            "Direct PDF fallback candidate did not return a PDF file.",
            details={
                "candidate_url": f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={article_number}",
                "final_url": f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={article_number}",
                "status": 200,
                "content_type": "text/html",
                "title_snippet": "IEEE Xplore Full-Text PDF",
                "body_snippet": "Please wait while the PDF loads.",
                "reason": "non_pdf_html",
            },
        )
        browser_result = PdfFetchResult(
            source_url=f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={article_number}",
            final_url=f"https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber={article_number}",
            pdf_bytes=b"%PDF-1.7 ieee",
            markdown_text="# IEEE PDF Article\n\n## Results\n\n"
            + ("PDF body text " * 160),
            suggested_filename=f"{article_number}.pdf",
            diagnostics={
                "browser_pdf_response": "ieee_stamp_iframe",
                "identity": {"status": "match"},
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = RuntimeContext(
                env={}, transport=transport, download_dir=Path(tmpdir)
            )
            with (
                mock.patch.object(
                    client,
                    "_fetch_browser_html_payload",
                    side_effect=ieee_provider.ProviderFailure(
                        "no_result", "Browser HTML did not expose #article."
                    ),
                ),
                mock.patch.object(
                    ieee_provider, "fetch_pdf_over_http", side_effect=direct_failure
                ) as mocked_direct,
                mock.patch.object(
                    ieee_provider,
                    "fetch_pdf_with_browser",
                    return_value=browser_result,
                ) as mocked_browser,
            ):
                raw_payload = client.fetch_raw_fulltext(
                    doi,
                    {"doi": doi, "landing_page_url": landing_url},
                    context=runtime,
                )
                article = client.to_article_model({"doi": doi}, raw_payload)

            self.assertEqual(mocked_direct.call_count, 1)
            mocked_browser.assert_called_once()
            self.assertEqual(
                mocked_browser.call_args.kwargs["artifact_dir"],
                Path(tmpdir) / "ieee_pdf_fallback",
            )
            self.assertEqual(mocked_browser.call_args.kwargs["referer"], landing_url)
            self.assertEqual(
                mocked_browser.call_args.kwargs["seed_urls"], [landing_url]
            )
            browser_request = mocked_browser.call_args.kwargs["request"]
            self.assertIs(browser_request.runtime, runtime)
            self.assertEqual(browser_request.expected_identity, {"doi": doi.lower()})

        self.assertEqual(raw_payload.content.route_kind, "pdf_fallback")
        self.assertEqual(article.source, "ieee_pdf")
        self.assertIn("fulltext:ieee_pdf_fallback_ok", article.quality.source_trail)
        diagnostics = raw_payload.content.diagnostics["pdf_fallback"]
        self.assertEqual(diagnostics["fetcher"], "camoufox_browser")
        self.assertEqual(diagnostics["browser_pdf_response"], "ieee_stamp_iframe")
        self.assertEqual(diagnostics["identity"]["status"], "match")
        self.assertEqual(raw_payload.content.route_name, "browser_pdf")
        self.assertIn("HTML", raw_payload.content.html_failure_message)
        from paper_fetch.models import FetchEnvelope
        from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance

        envelope = FetchEnvelope(
            doi=doi,
            source=article.source,
            has_fulltext=article.quality.has_fulltext,
            article=article,
            quality=article.quality,
            trace=raw_payload.trace,
        )
        acceptance = evaluate_fetch_acceptance(
            envelope,
            expected_doi=doi,
            asset_profile="none",
            requested_outputs={"article"},
        )
        self.assertEqual(acceptance.overall, "degraded")

        self.assertEqual(
            diagnostics["direct_failure"]["kind"], "downloaded_file_not_pdf"
        )
        self.assertEqual(
            diagnostics["direct_failure"]["details"]["title_snippet"],
            "IEEE Xplore Full-Text PDF",
        )

    def test_pdf_html_payload_is_rejected_then_provider_returns_abstract_only(
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
                ("GET", rest_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": b'<?xml version="1.0"?><div id="BodyWrapper"><div id="article"/></div>',
                    "url": rest_url,
                },
            }
        )
        client = IeeeClient(transport, {})

        with (
            mock.patch.object(
                client,
                "_fetch_browser_html_payload",
                side_effect=ieee_provider.ProviderFailure(
                    "no_result", "Browser HTML did not expose #article."
                ),
            ),
            mock.patch.object(
                ieee_provider,
                "fetch_pdf_over_http",
                side_effect=PdfFetchFailure(
                    "downloaded_file_not_pdf",
                    "Direct PDF fallback candidate did not return a PDF file.",
                    details={"status": 200, "content_type": "text/html"},
                ),
            ),
            mock.patch.object(
                ieee_provider,
                "fetch_pdf_with_browser",
                side_effect=PdfFetchFailure(
                    "publisher_access_challenge",
                    "Browser PDF fallback reached an access or challenge page.",
                    details={
                        "candidate_url": f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={article_number}",
                        "final_url": f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={article_number}",
                        "status": 200,
                        "content_type": "text/html",
                        "title_snippet": "IEEE Xplore Temporary Unavailable",
                        "body_snippet": "This service is temporarily unavailable.",
                        "reason": "publisher_temporary_unavailable",
                    },
                ),
            ),
        ):
            raw_payload = client.fetch_raw_fulltext(
                doi, {"doi": doi, "landing_page_url": landing_url}
            )
            article = client.to_article_model({"doi": doi}, raw_payload)

        self.assertEqual(raw_payload.content.route_kind, "abstract_only")
        self.assertEqual(article.source, "ieee_html")
        self.assertEqual(article.quality.content_kind, "abstract_only")
        self.assertIn("fulltext:ieee_pdf_fail", article.quality.source_trail)
        self.assertIn("Legacy IEEE abstract only.", article.metadata.abstract)
        diagnostics = raw_payload.content.diagnostics["pdf_fallback"]
        self.assertEqual(diagnostics["kind"], "publisher_access_challenge")
        self.assertEqual(
            diagnostics["details"]["browser_failure"]["details"]["reason"],
            "publisher_temporary_unavailable",
        )
