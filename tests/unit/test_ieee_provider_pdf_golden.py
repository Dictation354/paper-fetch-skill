# ruff: noqa: F403,F405
from __future__ import annotations

import re

from paper_fetch.providers import _ieee_html, _ieee_metadata, _ieee_url

from ._ieee_provider_support import *


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

    def test_legacy_fixture_pdf_candidates_preserve_pdf_url_pdf_path_stamp_order(
        self,
    ) -> None:
        fixtures = [
            ("10.1109/MPER.1985.5526567", "5526567"),
            ("10.1109/PGEC.1967.264619", "4038993"),
        ]

        for doi, article_number in fixtures:
            with self.subTest(doi=doi):
                landing_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
                html = golden_criteria_asset(doi, "landing.html").read_text(
                    encoding="utf-8"
                )
                landing_metadata = _ieee_metadata._parse_landing_metadata(html)
                attempt = _ieee_metadata.IeeeLandingAttempt(
                    normalized_doi=doi,
                    landing_url=landing_url,
                    response_url=landing_url,
                    html_text=html,
                    merged_metadata={
                        "pdfUrl": landing_metadata["pdfUrl"],
                        "pdfPath": landing_metadata["pdfPath"],
                    },
                    article_number=article_number,
                    landing_metadata=landing_metadata,
                )

                self.assertEqual(
                    _ieee_url._pdf_candidates(attempt),
                    [
                        f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={article_number}",
                        f"https://ieeexplore.ieee.org/iel7/{article_number}.pdf",
                        f"https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber={article_number}",
                    ],
                )

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
                    "fetch_pdf_with_playwright",
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

        self.assertEqual(raw_payload.content.route_kind, "pdf_fallback")
        self.assertEqual(article.source, "ieee_pdf")
        self.assertIn("fulltext:ieee_pdf_fallback_ok", article.quality.source_trail)
        diagnostics = raw_payload.content.diagnostics["pdf_fallback"]
        self.assertEqual(diagnostics["fetcher"], "camoufox_browser")
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
                "fetch_pdf_with_playwright",
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

    def test_real_ieee_html_golden_samples_preserve_semantics(self) -> None:
        """rule: rule-ieee-html-structure"""
        for label, (doi, article_number) in IEEE_REAL_HTML_SAMPLES.items():
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as tmpdir:
                    extraction, article, markdown = _real_ieee_fixture_article(
                        doi=doi,
                        article_number=article_number,
                        tmpdir=Path(tmpdir),
                    )

                    self.assertNotIn("[Formula unavailable]", markdown)
                    self.assertNotIn("[Formula unavailable]", extraction.markdown_text)
                    self.assertEqual(
                        article.quality.semantic_losses.formula_missing_count, 0
                    )
                    self.assertNotIn("SECTION I.", markdown)
                    self.assertNotIn(",,", markdown)
                    self.assertNotIn("(e.g., and)", markdown)
                    self.assertNotIn("## Figures", markdown)
                    self.assertNotIn("## Tables", markdown)
                    self.assertGreater(len(article.references), 0)
                    self.assertTrue(
                        any(
                            not reference.raw.lower().startswith("10.")
                            for reference in article.references
                        ),
                        msg=f"{label} references should use IEEE raw citation text, not DOI-only metadata.",
                    )
                    self.assertNotRegex(
                        markdown.split("## References", 1)[1],
                        r"(?m)^-\s+",
                        msg=f"{label} references should not append fallback bullet entries after IEEE numbered references.",
                    )

                    if label == "ACCESS":
                        self.assertIn("## Introduction", markdown)
                        self.assertIn(
                            "### A. Background on Near-Data Processing", markdown
                        )
                        section_text = "\n\n".join(
                            section.text for section in article.sections
                        )
                        for prefix, listing in [
                            ("standard processing system.", "Listing 1"),
                            ("post-processing.", "Listing 2"),
                            ("NDPmulator).", "Listing 3"),
                            ("ndaccAlloc).", "Listing 4"),
                        ]:
                            with self.subTest(listing=listing):
                                self.assertRegex(
                                    section_text,
                                    re.escape(prefix)
                                    + r"\n\n!\["
                                    + re.escape(listing)
                                    + r"\]\(",
                                )
                                self.assertNotIn(f"{prefix}![{listing}]", section_text)
                    elif label == "CICTN":
                        self.assertGreaterEqual(extraction.marker_counts["formulas"], 4)
                        self.assertGreaterEqual(len(article.assets), 10)
                    elif label == "TBME":
                        table_iii = next(
                            asset
                            for asset in article.assets
                            if asset.heading.upper().startswith("TABLE III")
                        )
                        self.assertEqual(table_iii.kind, "table")
                        self.assertTrue(table_iii.path)
                        self.assertTrue(Path(table_iii.path).is_file())
                        self.assertNotIn("Formula 1", json.dumps(article.to_dict()))
                    elif label == "TCOMM":
                        self.assertIn("### Theorem 1:", markdown)
                        self.assertIn("#### Proof:", markdown)
                        self.assertNotIn("introduced in, is now", markdown)
                    elif label == "TDEI":
                        self.assertGreaterEqual(markdown.count("!["), 10)
                    elif label == "TE":
                        self.assertIn("## Appendix A", markdown)
                        self.assertIn("## Appendix B", markdown)
                    elif label == "TIM":
                        section_levels = {
                            section.heading: section.level
                            for section in article.sections
                        }
                        self.assertEqual(section_levels["A. Problem Definition"], 3)
                        self.assertEqual(section_levels["1) NTU RGB+D 120:"], 4)
                        self.assertGreater(len(article.metadata.keywords), 0)

    def test_ieee_tim_fixture_original_html_is_parsed_as_body(self) -> None:
        """rule: rule-ieee-html-structure"""
        fixture = golden_criteria_asset("10.1109/TIM.2024.3509573", "original.html")
        source_url = (
            "https://ieeexplore.ieee.org/rest/document/10772041/?logAccess=true"
        )

        extraction = _ieee_html._extract_ieee_html(
            fixture.read_text(encoding="utf-8"),
            source_url,
            metadata={"title": "IEEE TIM Article"},
        )

        self.assertIn("Overall Framework", extraction.markdown_text)
        self.assertIn(
            "Adaptive Multimetric Distance Aggregation Module", extraction.markdown_text
        )
        self.assertGreaterEqual(extraction.marker_counts["sections"], 2)
        self.assertGreaterEqual(extraction.marker_counts["formulas"], 1)
        self.assertGreaterEqual(extraction.marker_counts["tables"], 1)

    def test_ieee_golden_criteria_manifest_records_expected_shapes(self) -> None:
        samples = golden_criteria_manifest()["samples"]
        expected_shapes = {
            "10.1109/ACCESS.2024.3352924": (
                "10388355",
                "ieee_html",
                "dynamic_html",
                "original.html",
            ),
            "10.1109/TBME.2024.3434477": (
                "10612240",
                "ieee_html",
                "dynamic_html",
                "original.html",
            ),
            "10.1109/TCOMM.2024.3395332": (
                "10511075",
                "ieee_html",
                "dynamic_html",
                "original.html",
            ),
            "10.1109/TDEI.2024.3373549": (
                "10459335",
                "ieee_html",
                "dynamic_html",
                "original.html",
            ),
            "10.1109/TIM.2024.3509573": (
                "10772041",
                "ieee_html",
                "dynamic_html",
                "original.html",
            ),
            "10.1109/TE.2024.3376795": (
                "10496257",
                "ieee_html",
                "dynamic_html",
                "original.html",
            ),
            "10.1109/CICTN64563.2025.10932570": (
                "10932570",
                "ieee_html",
                "dynamic_html",
                "original.html",
            ),
            "10.1109/RITA.2026.3668995": (
                "11417163",
                "ieee_html",
                "dynamic_html",
                "multimedia.json",
            ),
            "10.1109/MPER.1985.5526567": (
                "5526567",
                "ieee_pdf",
                "pdf_fallback",
                "landing.html",
            ),
            "10.1109/PGEC.1967.264619": (
                "4038993",
                "ieee_pdf",
                "pdf_fallback",
                "landing.html",
            ),
        }

        ieee_samples = {
            sample["doi"]: sample
            for sample in samples.values()
            if sample.get("publisher") == "ieee"
        }

        self.assertEqual(set(ieee_samples), set(expected_shapes))
        for doi, (
            article_number,
            expected_source,
            expected_route,
            required_asset,
        ) in expected_shapes.items():
            with self.subTest(doi=doi):
                sample = ieee_samples[doi]
                self.assertEqual(sample["article_number"], article_number)
                self.assertEqual(sample["expected_source"], expected_source)
                self.assertEqual(sample["expected_route"], expected_route)
                self.assertEqual(sample["expected_content_kind"], "fulltext")
                self.assertEqual(sample["expected_live_status"], "fulltext")
                self.assertNotIn("expected_review_status", sample)
                self.assertNotIn("out_of_scope_reason", sample)
                self.assertIn(required_asset, sample["assets"])
                for fixture_path in sample["assets"].values():
                    self.assertTrue(
                        (REPO_ROOT / fixture_path).is_file(), msg=fixture_path
                    )
