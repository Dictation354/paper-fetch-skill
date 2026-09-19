from __future__ import annotations
from paper_fetch.providers.base import ProviderFailure
from tests.support._atypon_browser_workflow_provider_support import *
# ruff: noqa: F403,F405


class AtyponBrowserWorkflowProviderFallbackTests(AtyponBrowserWorkflowProviderTestCase):
    def test_science_provider_falls_back_to_pdf_with_browser_seed(self) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", SCIENCE_SAMPLE.doi)
            seed = {
                "browser_cookies": [
                    {
                        "name": "cf_clearance",
                        "value": "secret",
                        "domain": ".science.org",
                        "path": "/",
                    }
                ],
                "browser_user_agent": "Mozilla/5.0",
            }
            preflight_seed = {
                "browser_cookies": [
                    {
                        "name": "sessionid",
                        "value": "warm",
                        "domain": ".science.org",
                        "path": "/",
                    }
                ],
                "browser_user_agent": "Mozilla/5.0",
            }
            mocked_warm = mock.Mock(
                return_value={
                    "browser_cookies": [
                        seed["browser_cookies"][0],
                        preflight_seed["browser_cookies"][0],
                    ],
                    "browser_user_agent": "Mozilla/5.0",
                    "browser_final_url": f"https://www.science.org/doi/{SCIENCE_SAMPLE.doi}",
                }
            )
            mocked_pdf = mock.Mock(
                return_value=mock.Mock(
                    source_url=f"https://www.science.org/doi/epdf/{SCIENCE_SAMPLE.doi}",
                    final_url=f"https://www.science.org/doi/epdf/{SCIENCE_SAMPLE.doi}",
                    pdf_bytes=fulltext_pdf_bytes(),
                    markdown_text=f"# {SCIENCE_SAMPLE.title}\n\n## Results\n\n"
                    + ("Body text " * 120),
                    suggested_filename="article.pdf",
                )
            )
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mock.Mock(
                    side_effect=browser_runtime.BrowserRuntimeFailure(
                        "redirected_to_abstract",
                        "Abstract redirect",
                        browser_context_seed=seed,
                    )
                ),
                warm_browser_context=mocked_warm,
                fetch_pdf_with_browser=mocked_pdf,
            )
            raw_payload = client.fetch_raw_fulltext(
                SCIENCE_SAMPLE.doi,
                {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
            )
            article = client.to_article_model(
                {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                raw_payload,
            )

        mocked_warm.assert_called_once()
        mocked_pdf.assert_called_once()
        self.assertEqual(
            mocked_pdf.call_args.kwargs["browser_cookies"],
            [seed["browser_cookies"][0], preflight_seed["browser_cookies"][0]],
        )
        self.assertTrue(mocked_warm.call_args.kwargs["lightweight"])
        self.assertIsNone(mocked_pdf.call_args.kwargs["seed_urls"])
        self.assertEqual(
            mocked_pdf.call_args.kwargs["referer"], SCIENCE_SAMPLE.landing_url
        )
        self.assertTrue(mocked_pdf.call_args.kwargs["allow_pdf_only"])
        self.assertIn(
            f"https://www.science.org/doi/epdf/{SCIENCE_SAMPLE.doi}",
            list(mocked_pdf.call_args.args[0]),
        )
        self.assertEqual(_payload_route(raw_payload), "pdf_fallback")
        self.assertTrue(raw_payload.needs_local_copy)
        self.assertEqual(article.source, "science")
        self.assertIn("fulltext:science_pdf_fallback_ok", article.quality.source_trail)

    def test_pnas_provider_prefers_html_route(self) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", PNAS_SAMPLE.doi)
            mocked_pdf = mock.Mock()
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mock.Mock(
                    return_value=browser_runtime.BrowserFetchedHtml(
                        source_url=PNAS_SAMPLE.landing_url,
                        final_url=PNAS_SAMPLE.landing_url,
                        html="<html></html>",
                        response_status=200,
                        response_headers={"content-type": "text/html"},
                        title=PNAS_SAMPLE.title,
                        summary="Example summary",
                        browser_context_seed={},
                    )
                ),
                extract_atypon_browser_workflow_markdown=mock.Mock(
                    return_value=(
                        f"# {PNAS_SAMPLE.title}\n\n## Results\n\n"
                        + ("Body text " * 120),
                        {"title": PNAS_SAMPLE.title},
                    )
                ),
                fetch_pdf_with_browser=mocked_pdf,
            )
            raw_payload = client.fetch_raw_fulltext(
                PNAS_SAMPLE.doi,
                {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
            )
            article = client.to_article_model(
                {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
                raw_payload,
            )

        mocked_pdf.assert_not_called()
        self.assertEqual(_payload_route(raw_payload), "html")
        self.assertEqual(article.source, "pnas")
        self.assertIn("fulltext:pnas_html_ok", article.quality.source_trail)

    def test_pnas_provider_uses_normal_browser_html_path(self) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        seed = {
            "browser_cookies": [
                {
                    "name": "sessionid",
                    "value": "direct",
                    "domain": ".pnas.org",
                    "path": "/",
                }
            ],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": PNAS_SAMPLE.landing_url,
        }
        mocked_runtime = mock.Mock(
            return_value=browser_runtime.BrowserRuntimeConfig(
                provider="pnas",
                doi=PNAS_SAMPLE.doi,
                artifact_dir=Path("/tmp/paper-fetch-test-pnas"),
                headless=True,
                user_agent=None,
            )
        )
        mocked_browser = mock.Mock(
            return_value=browser_runtime.BrowserFetchedHtml(
                source_url=PNAS_SAMPLE.landing_url,
                final_url=PNAS_SAMPLE.landing_url,
                html="<html><body><main>PNAS browser full text</main></body></html>",
                response_status=200,
                response_headers={"content-type": "text/html"},
                title=PNAS_SAMPLE.title,
                summary="PNAS browser full text",
                browser_context_seed=seed,
            )
        )
        install_browser_workflow_deps(
            client,
            load_runtime_config=mocked_runtime,
            ensure_runtime_ready=mock.Mock(),
            fetch_html_with_browser=mocked_browser,
            extract_atypon_browser_workflow_markdown=mock.Mock(
                return_value=(
                    f"# {PNAS_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                    {"title": PNAS_SAMPLE.title},
                )
            ),
        )
        raw_payload = client.fetch_raw_fulltext(
            PNAS_SAMPLE.doi,
            {
                "doi": PNAS_SAMPLE.doi,
                "title": PNAS_SAMPLE.title,
                "landing_page_url": f"https://www.pnas.org/doi/{PNAS_SAMPLE.doi}",
            },
        )

        mocked_runtime.assert_called_once()
        mocked_browser.assert_called_once()
        self.assertEqual(
            list(mocked_browser.call_args.args[0]),
            [
                f"https://www.pnas.org/doi/full/{PNAS_SAMPLE.doi}",
                f"https://www.pnas.org/doi/{PNAS_SAMPLE.doi}",
                f"https://doi.org/{PNAS_SAMPLE.doi}",
            ],
        )
        self.assertIs(
            mocked_browser.call_args.kwargs["config"], mocked_runtime.return_value
        )
        self.assertIsNotNone(raw_payload.content)
        assert raw_payload.content is not None
        self.assertEqual(raw_payload.content.route_kind, "html")
        self.assertEqual(raw_payload.content.fetcher, "camoufox")
        self.assertEqual(raw_payload.content.diagnostics["html_fetcher"], "camoufox")
        self.assertEqual(raw_payload.content.browser_context_seed, seed)
        self.assertIn("fulltext:pnas_html_ok", _payload_source_trail(raw_payload))

    def test_pnas_html_uses_one_normal_browser_fetcher_attempt(self) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", PNAS_SAMPLE.doi)
            mocked_runtime = mock.Mock(return_value=runtime)
            mocked_browser = mock.Mock(
                return_value=browser_runtime.BrowserFetchedHtml(
                    source_url=PNAS_SAMPLE.landing_url,
                    final_url=PNAS_SAMPLE.landing_url,
                    html="<html></html>",
                    response_status=200,
                    response_headers={"content-type": "text/html"},
                    title=PNAS_SAMPLE.title,
                    summary="Example summary",
                    browser_context_seed={},
                )
            )
            install_browser_workflow_deps(
                client,
                load_runtime_config=mocked_runtime,
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mocked_browser,
                extract_atypon_browser_workflow_markdown=mock.Mock(
                    return_value=(
                        f"# {PNAS_SAMPLE.title}\n\n## Results\n\n"
                        + ("Body text " * 120),
                        {"title": PNAS_SAMPLE.title},
                    )
                ),
            )
            raw_payload = client.fetch_raw_fulltext(
                PNAS_SAMPLE.doi,
                {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
            )

        mocked_runtime.assert_called_once()
        mocked_browser.assert_called_once()
        self.assertFalse(mocked_browser.call_args.kwargs["disable_media"])
        self.assertEqual(mocked_browser.call_args.kwargs["wait_seconds"], 8)
        self.assertEqual(
            mocked_browser.call_args.kwargs["options"].readiness_budget_seconds,
            8.0,
        )
        self.assertIsNotNone(raw_payload.content)
        assert raw_payload.content is not None
        self.assertEqual(raw_payload.content.fetcher, "camoufox")

    def test_wiley_provider_fetch_result_returns_abstract_only_when_pdf_recovery_fails(
        self,
    ) -> None:
        client = wiley_provider.WileyClient(transport=None, env={})
        doi = "10.1111/gcb.16998"
        title = "Wiley Abstract Only Example"
        landing_url = f"https://onlinelibrary.wiley.com/doi/full/{doi}"
        html_payload = _typed_raw_payload(
            provider="wiley",
            source_url=landing_url,
            content_type="text/html",
            body=b"<html></html>",
            route="html",
            markdown_text=f"# {title}\n\n## Abstract\n\nWiley abstract only.",
            source_trail=["fulltext:wiley_html_ok"],
            browser_context_seed={
                "browser_cookies": [
                    {
                        "name": "cf_clearance",
                        "value": "secret",
                        "domain": ".wiley.com",
                        "path": "/",
                    }
                ],
                "browser_user_agent": "Mozilla/5.0",
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "wiley", doi)
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_seeded_browser_pdf_payload=mock.Mock(
                    side_effect=browser_workflow.PdfFallbackFailure(
                        "pdf_download_failed", "Wiley PDF fallback failed."
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

        self.assertEqual(result.article.source, "wiley_browser")
        self.assertEqual(result.article.quality.content_kind, "abstract_only")
        self.assertIn("fulltext:wiley_html_ok", result.article.quality.source_trail)
        self.assertIn(
            "fulltext:wiley_abstract_only", result.article.quality.source_trail
        )
        self.assertNotIn(
            "fulltext:wiley_pdf_fallback_ok", result.article.quality.source_trail
        )
        self.assertTrue(
            any(
                "returning abstract-only content" in warning
                for warning in result.article.quality.warnings
            )
        )

    def test_wiley_cloudflare_html_failure_falls_back_to_browser_pdf(self) -> None:
        client = wiley_provider.WileyClient(transport=None, env={})
        doi = "10.1111/gcb.70541"
        title = "Wiley HTML First Example"
        landing_url = f"https://onlinelibrary.wiley.com/doi/full/{doi}"
        seed = {
            "browser_cookies": [
                {
                    "name": "cf_clearance",
                    "value": "secret",
                    "domain": ".wiley.com",
                    "path": "/",
                }
            ],
            "browser_user_agent": "Mozilla/5.0",
        }
        pdf_payload = _typed_raw_payload(
            provider="wiley",
            source_url=f"https://onlinelibrary.wiley.com/doi/epdf/{doi}",
            content_type="application/pdf",
            body=fulltext_pdf_bytes(),
            route="pdf_fallback",
            markdown_text=f"# {title}\n\n## Results\n\n"
            + ("Wiley fallback body. " * 80),
            suggested_filename="wiley.pdf",
        )
        mocked_pdf = mock.Mock(return_value=pdf_payload)

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "wiley", doi)
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mock.Mock(
                    side_effect=browser_runtime.BrowserRuntimeFailure(
                        "cloudflare_challenge",
                        "Encountered a challenge or CAPTCHA page while loading publisher HTML.",
                        browser_context_seed=seed,
                    )
                ),
                fetch_seeded_browser_pdf_payload=mocked_pdf,
            )
            raw_payload = client.fetch_raw_fulltext(
                doi,
                {
                    "doi": doi,
                    "title": title,
                    "landing_page_url": landing_url,
                },
            )

        mocked_pdf.assert_called_once()
        self.assertEqual(mocked_pdf.call_args.kwargs["browser_context_seed"], seed)
        self.assertEqual(
            mocked_pdf.call_args.kwargs["html_failure_reason"], "cloudflare_challenge"
        )
        self.assertIn(
            "challenge", mocked_pdf.call_args.kwargs["html_failure_message"].lower()
        )
        self.assertEqual(_payload_route(raw_payload), "pdf_fallback")
        self.assertIn("fulltext:wiley_html_fail", _payload_source_trail(raw_payload))
        self.assertIn(
            "fulltext:wiley_pdf_browser_ok", _payload_source_trail(raw_payload)
        )
        self.assertIn(
            "fulltext:wiley_pdf_fallback_ok", _payload_source_trail(raw_payload)
        )

    def test_wiley_access_gate_remains_no_access_when_pdf_fallback_fails(
        self,
    ) -> None:
        client = wiley_provider.WileyClient(transport=None, env={})
        doi = "10.1111/gcb.70541"
        landing_url = f"https://onlinelibrary.wiley.com/doi/full/{doi}"

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "wiley", doi)
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mock.Mock(
                    side_effect=browser_runtime.BrowserRuntimeFailure(
                        "cloudflare_challenge",
                        "Encountered a challenge page.",
                    )
                ),
                fetch_seeded_browser_pdf_payload=mock.Mock(
                    side_effect=browser_workflow.PdfFallbackFailure(
                        "pdf_download_failed",
                        "Wiley PDF fallback failed.",
                    )
                ),
            )
            with self.assertRaises(ProviderFailure) as raised:
                client.fetch_raw_fulltext(
                    doi,
                    {
                        "doi": doi,
                        "title": "Wiley HTML First Example",
                        "landing_page_url": landing_url,
                    },
                )

        self.assertEqual(raised.exception.code, "no_access")

    def test_pnas_provider_falls_back_to_pdf_with_browser_seed(self) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", PNAS_SAMPLE.doi)
            seed = {
                "browser_cookies": [
                    {
                        "name": "cf_clearance",
                        "value": "secret",
                        "domain": ".pnas.org",
                        "path": "/",
                    }
                ],
                "browser_user_agent": "Mozilla/5.0",
            }
            preflight_seed = {
                "browser_cookies": [
                    {
                        "name": "sessionid",
                        "value": "warm",
                        "domain": ".pnas.org",
                        "path": "/",
                    }
                ],
                "browser_user_agent": "Mozilla/5.0",
            }
            mocked_warm = mock.Mock(
                return_value={
                    "browser_cookies": [
                        seed["browser_cookies"][0],
                        preflight_seed["browser_cookies"][0],
                    ],
                    "browser_user_agent": "Mozilla/5.0",
                    "browser_final_url": f"https://www.pnas.org/doi/{PNAS_SAMPLE.doi}",
                }
            )
            mocked_pdf = mock.Mock(
                return_value=mock.Mock(
                    source_url=f"https://www.pnas.org/doi/pdf/{PNAS_SAMPLE.doi}",
                    final_url=f"https://www.pnas.org/doi/pdf/{PNAS_SAMPLE.doi}",
                    pdf_bytes=fulltext_pdf_bytes(),
                    markdown_text=f"# {PNAS_SAMPLE.title}\n\n## Results\n\n"
                    + ("Body text " * 120),
                    suggested_filename="article.pdf",
                )
            )
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mock.Mock(
                    side_effect=browser_runtime.BrowserRuntimeFailure(
                        "redirected_to_abstract",
                        "Abstract redirect",
                        browser_context_seed=seed,
                    )
                ),
                warm_browser_context=mocked_warm,
                fetch_pdf_with_browser=mocked_pdf,
            )
            raw_payload = client.fetch_raw_fulltext(
                PNAS_SAMPLE.doi,
                {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
            )
            article = client.to_article_model(
                {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
                raw_payload,
            )

        mocked_warm.assert_called_once()
        mocked_pdf.assert_called_once()
        kwargs = mocked_pdf.call_args.kwargs
        self.assertEqual(
            kwargs["browser_cookies"],
            [seed["browser_cookies"][0], preflight_seed["browser_cookies"][0]],
        )
        self.assertTrue(mocked_warm.call_args.kwargs["lightweight"])
        self.assertIsNone(kwargs["seed_urls"])
        self.assertEqual(
            kwargs["referer"], f"https://www.pnas.org/doi/full/{PNAS_SAMPLE.doi}"
        )
        self.assertEqual(
            list(mocked_pdf.call_args.args[0])[:3],
            [
                f"https://www.pnas.org/doi/epdf/{PNAS_SAMPLE.doi}",
                f"https://www.pnas.org/doi/pdf/{PNAS_SAMPLE.doi}?download=true",
                f"https://www.pnas.org/doi/pdf/{PNAS_SAMPLE.doi}",
            ],
        )
        self.assertEqual(_payload_route(raw_payload), "pdf_fallback")
        self.assertTrue(raw_payload.needs_local_copy)
        self.assertEqual(article.source, "pnas")
        self.assertIn("fulltext:pnas_pdf_fallback_ok", article.quality.source_trail)
