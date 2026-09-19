from __future__ import annotations
from paper_fetch.extraction.html._metadata import parse_html_metadata
from tests.support._atypon_browser_workflow_provider_support import *
# ruff: noqa: F403,F405


def _provisional_abstract_markdown(raw_path, url):
    # Mechanism tests below inject a provisional payload. Actual rejection and
    # routing of this raw page are tested in test_reviewed_block_provider_paths.
    metadata = parse_html_metadata(raw_path.read_text(), url)
    return f"# {metadata.get('title')}\n\n## Abstract\n\n{metadata.get('abstract')}"


class AtyponBrowserWorkflowProviderFallbackTests(AtyponBrowserWorkflowProviderTestCase):
    def test_pnas_confirmed_gate_stops_even_when_pdf_recovery_would_succeed(
        self,
    ) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        doi = "10.1073/pnas.2509692123"
        title = "A discrete serotonergic circuit involved in the generation of tinnitus behavior"
        landing_url = f"https://www.pnas.org/doi/full/{doi}"
        html_payload = _typed_raw_payload(
            provider="pnas",
            source_url=landing_url,
            content_type="text/html",
            body=PNAS_PAYWALL_SAMPLE_RAW.read_bytes(),
            route="html",
            markdown_text=_provisional_abstract_markdown(
                PNAS_PAYWALL_SAMPLE_RAW, landing_url
            ),
            source_trail=["fulltext:pnas_html_ok"],
            browser_context_seed={
                "browser_cookies": [
                    {
                        "name": "cf_clearance",
                        "value": "secret",
                        "domain": ".pnas.org",
                        "path": "/",
                    }
                ],
                "browser_user_agent": "Mozilla/5.0",
            },
        )
        pdf_payload = _typed_raw_payload(
            provider="pnas",
            source_url=f"https://www.pnas.org/doi/pdf/{doi}",
            content_type="application/pdf",
            body=fulltext_pdf_bytes(),
            route="pdf_fallback",
            markdown_text=f"# {title}\n\n## Results\n\n"
            + ("Injected PNAS PDF mechanism text. " * 100),
            source_trail=[
                "fulltext:pnas_html_ok",
                "fulltext:pnas_abstract_only",
                "fulltext:pnas_pdf_fallback_ok",
            ],
            suggested_filename="archive.pdf",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", doi)
            mocked_pdf = mock.Mock(return_value=pdf_payload)
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_seeded_browser_pdf_payload=mocked_pdf,
            )
            with mock.patch.object(
                client, "fetch_raw_fulltext", return_value=html_payload
            ):
                result = client.fetch_result(
                    doi,
                    {"doi": doi, "title": title, "landing_page_url": landing_url},
                    None,
                )

        mocked_pdf.assert_not_called()
        self.assertFalse(result.article.quality.has_fulltext)
        self.assertEqual(result.article.quality.content_kind, "abstract_only")
        self.assertTrue(result.article.metadata.abstract)
        self.assertIn("confirmed_article_paywall", result.article.quality.source_trail)
        self.assertNotIn(
            "fulltext:pnas_pdf_fallback_ok", result.article.quality.source_trail
        )

    def test_science_provider_fetch_result_recovers_pdf_for_paywall_sample_markdown(
        self,
    ) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        doi = "10.1126/science.aeg3511"
        title = "Magma plumbing beneath Yellowstone"
        landing_url = f"https://www.science.org/doi/full/{doi}"
        markdown_text = _provisional_abstract_markdown(
            SCIENCE_PAYWALL_SAMPLE_RAW, landing_url
        )
        html_text = SCIENCE_PAYWALL_SAMPLE_RAW.read_text(encoding="utf-8")
        diagnostics = assess_html_fulltext_availability(
            markdown_text,
            {
                "title": title,
                "doi": doi,
                "abstract": markdown_text.split("## Access the full article", 1)[0]
                .split("## Abstract", 1)[1]
                .strip(),
            },
            provider="science",
            html_text=html_text,
            title=title,
            final_url=landing_url,
        )
        html_payload = _typed_raw_payload(
            provider="science",
            source_url=landing_url,
            content_type="text/html",
            body=SCIENCE_PAYWALL_SAMPLE_RAW.read_bytes(),
            route="html",
            markdown_text=markdown_text,
            source_trail=["fulltext:science_html_ok"],
            availability_diagnostics=diagnostics.to_dict(),
            browser_context_seed={
                "browser_cookies": [
                    {
                        "name": "cf_clearance",
                        "value": "secret",
                        "domain": ".science.org",
                        "path": "/",
                    }
                ],
                "browser_user_agent": "Mozilla/5.0",
            },
        )
        pdf_payload = _typed_raw_payload(
            provider="science",
            source_url=f"https://www.science.org/doi/epdf/{doi}",
            content_type="application/pdf",
            body=fulltext_pdf_bytes(),
            route="pdf_fallback",
            markdown_text=f"# {title}\n\n## Results\n\n"
            + ("Injected Science PDF mechanism text. " * 100),
            source_trail=[
                "fulltext:science_html_ok",
                "fulltext:science_abstract_only",
                "fulltext:science_pdf_fallback_ok",
            ],
            suggested_filename="science-paywall.pdf",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", doi)
            mocked_pdf = mock.Mock(return_value=pdf_payload)
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_seeded_browser_pdf_payload=mocked_pdf,
            )
            with mock.patch.object(
                client, "fetch_raw_fulltext", return_value=html_payload
            ):
                result = client.fetch_result(
                    doi,
                    {"doi": doi, "title": title, "landing_page_url": landing_url},
                    None,
                )

        mocked_pdf.assert_not_called()
        self.assertEqual(result.article.quality.content_kind, "abstract_only")
        self.assertTrue(result.article.metadata.abstract)
        self.assertIn("access_gate_detected", result.article.quality.flags)

    def test_pnas_confirmed_gate_never_attempts_failing_pdf_recovery(
        self,
    ) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        doi = "10.1073/pnas.2509692123"
        title = "A discrete serotonergic circuit involved in the generation of tinnitus behavior"
        landing_url = f"https://www.pnas.org/doi/full/{doi}"
        html_payload = _typed_raw_payload(
            provider="pnas",
            source_url=landing_url,
            content_type="text/html",
            body=PNAS_PAYWALL_SAMPLE_RAW.read_bytes(),
            route="html",
            markdown_text=_provisional_abstract_markdown(
                PNAS_PAYWALL_SAMPLE_RAW, landing_url
            ),
            source_trail=["fulltext:pnas_html_ok"],
            browser_context_seed={
                "browser_cookies": [
                    {
                        "name": "cf_clearance",
                        "value": "secret",
                        "domain": ".pnas.org",
                        "path": "/",
                    }
                ],
                "browser_user_agent": "Mozilla/5.0",
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", doi)
            mocked_pdf = mock.Mock(
                side_effect=browser_workflow.PdfFallbackFailure(
                    "pdf_download_failed", "PNAS PDF fallback failed."
                )
            )
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_seeded_browser_pdf_payload=mocked_pdf,
            )
            with mock.patch.object(
                client, "fetch_raw_fulltext", return_value=html_payload
            ):
                result = client.fetch_result(
                    doi,
                    {"doi": doi, "title": title, "landing_page_url": landing_url},
                    None,
                )

        mocked_pdf.assert_not_called()
        self.assertFalse(result.article.quality.has_fulltext)
        self.assertEqual(result.article.quality.content_kind, "abstract_only")
        self.assertTrue(result.article.metadata.abstract)
        self.assertIn("confirmed_article_paywall", result.article.quality.source_trail)
        self.assertNotIn(
            "fulltext:pnas_pdf_fallback_ok", result.article.quality.source_trail
        )

    def test_science_provider_fetch_result_returns_abstract_only_when_pdf_recovery_fails(
        self,
    ) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        doi = "10.1126/science.aeg3511"
        title = "Magma plumbing beneath Yellowstone"
        landing_url = f"https://www.science.org/doi/full/{doi}"
        html_text = SCIENCE_PAYWALL_SAMPLE_RAW.read_text(encoding="utf-8")
        markdown_text = _provisional_abstract_markdown(
            SCIENCE_PAYWALL_SAMPLE_RAW, landing_url
        )
        diagnostics = assess_html_fulltext_availability(
            markdown_text,
            {
                "title": title,
                "doi": doi,
                "abstract": markdown_text.split("## Access the full article", 1)[0]
                .split("## Abstract", 1)[1]
                .strip(),
            },
            provider="science",
            html_text=html_text,
            title=title,
            final_url=landing_url,
        )
        html_payload = _typed_raw_payload(
            provider="science",
            source_url=landing_url,
            content_type="text/html",
            body=SCIENCE_PAYWALL_SAMPLE_RAW.read_bytes(),
            route="html",
            markdown_text=markdown_text,
            source_trail=["fulltext:science_html_ok"],
            availability_diagnostics=diagnostics.to_dict(),
            browser_context_seed={
                "browser_cookies": [
                    {
                        "name": "cf_clearance",
                        "value": "secret",
                        "domain": ".science.org",
                        "path": "/",
                    }
                ],
                "browser_user_agent": "Mozilla/5.0",
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", doi)
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_seeded_browser_pdf_payload=mock.Mock(
                    side_effect=browser_workflow.PdfFallbackFailure(
                        "pdf_download_failed", "Science PDF fallback failed."
                    )
                ),
            )
            with mock.patch.object(
                client, "fetch_raw_fulltext", return_value=html_payload
            ):
                result = client.fetch_result(
                    doi,
                    {"doi": doi, "title": title, "landing_page_url": landing_url},
                    None,
                )

        client.deps.fetch_seeded_browser_pdf_payload.assert_not_called()
        self.assertEqual(result.article.quality.content_kind, "abstract_only")
        self.assertTrue(result.article.metadata.abstract)
        self.assertIn("access_gate_detected", result.article.quality.flags)
