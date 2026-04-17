from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch.providers import _flaresolverr, _science_pnas, pnas as pnas_provider, science as science_provider
from tests.provider_benchmark_samples import provider_benchmark_sample
from tests.unit._paper_fetch_support import fulltext_pdf_bytes


SCIENCE_SAMPLE = provider_benchmark_sample("science")
PNAS_SAMPLE = provider_benchmark_sample("pnas")


class SciencePnasProviderTests(unittest.TestCase):
    def _runtime_config(self, tmpdir: str, provider: str, doi: str) -> _flaresolverr.FlareSolverrRuntimeConfig:
        tmp = Path(tmpdir)
        return _flaresolverr.FlareSolverrRuntimeConfig(
            provider=provider,
            doi=doi,
            url="http://127.0.0.1:8191/v1",
            env_file=tmp / ".env.flaresolverr",
            source_dir=tmp / "vendor" / "flaresolverr",
            artifact_dir=tmp / "artifacts",
            headless=True,
            min_interval_seconds=20,
            max_requests_per_hour=30,
            max_requests_per_day=200,
            rate_limit_file=tmp / "rate_limits.json",
        )

    def test_science_provider_prefers_html_route(self) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", SCIENCE_SAMPLE.doi)
            with (
                mock.patch.object(_science_pnas, "load_runtime_config", return_value=runtime),
                mock.patch.object(_science_pnas, "ensure_runtime_ready"),
                mock.patch.object(
                    _science_pnas,
                    "fetch_html_with_flaresolverr",
                    return_value=_flaresolverr.FetchedPublisherHtml(
                        source_url=SCIENCE_SAMPLE.landing_url,
                        final_url=SCIENCE_SAMPLE.landing_url,
                        html="<html></html>",
                        response_status=200,
                        response_headers={"content-type": "text/html"},
                        title=SCIENCE_SAMPLE.title,
                        summary="Example summary",
                        browser_context_seed={},
                    ),
                ),
                mock.patch.object(
                    _science_pnas,
                    "extract_science_pnas_markdown",
                    return_value=(f"# {SCIENCE_SAMPLE.title}\n\n## Discussion\n\n" + ("Body text " * 120), {"title": SCIENCE_SAMPLE.title}),
                ),
                mock.patch.object(_science_pnas, "fetch_pdf_with_playwright") as mocked_pdf,
            ):
                raw_payload = client.fetch_raw_fulltext(
                    SCIENCE_SAMPLE.doi,
                    {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                )
                article = client.to_article_model(
                    {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                    raw_payload,
                )

        mocked_pdf.assert_not_called()
        self.assertEqual(raw_payload.metadata["route"], "html")
        self.assertEqual(article.source, "science")
        self.assertIn("fulltext:science_html_ok", article.quality.source_trail)

    def test_science_provider_falls_back_to_pdf_with_browser_seed(self) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", SCIENCE_SAMPLE.doi)
            seed = {
                "browser_cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".science.org", "path": "/"}],
                "browser_user_agent": "Mozilla/5.0",
            }
            preflight_seed = {
                "browser_cookies": [{"name": "sessionid", "value": "warm", "domain": ".science.org", "path": "/"}],
                "browser_user_agent": "Mozilla/5.0",
            }
            with (
                mock.patch.object(_science_pnas, "load_runtime_config", return_value=runtime),
                mock.patch.object(_science_pnas, "ensure_runtime_ready"),
                mock.patch.object(
                    _science_pnas,
                    "fetch_html_with_flaresolverr",
                    side_effect=_flaresolverr.FlareSolverrFailure(
                        "redirected_to_abstract",
                        "Abstract redirect",
                        browser_context_seed=seed,
                    ),
                ),
                mock.patch.object(
                    _science_pnas,
                    "warm_browser_context_with_flaresolverr",
                    return_value={
                        "browser_cookies": [seed["browser_cookies"][0], preflight_seed["browser_cookies"][0]],
                        "browser_user_agent": "Mozilla/5.0",
                        "browser_final_url": f"https://www.science.org/doi/{SCIENCE_SAMPLE.doi}",
                    },
                ) as mocked_warm,
                mock.patch.object(
                    _science_pnas,
                    "fetch_pdf_with_playwright",
                    return_value=mock.Mock(
                        source_url=f"https://www.science.org/doi/epdf/{SCIENCE_SAMPLE.doi}",
                        final_url=f"https://www.science.org/doi/epdf/{SCIENCE_SAMPLE.doi}",
                        pdf_bytes=fulltext_pdf_bytes(),
                        markdown_text=f"# {SCIENCE_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                        suggested_filename="article.pdf",
                    ),
                ) as mocked_pdf,
            ):
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
        self.assertEqual(
            mocked_pdf.call_args.kwargs["seed_urls"],
            [SCIENCE_SAMPLE.landing_url],
        )
        self.assertIn(
            f"https://www.science.org/doi/epdf/{SCIENCE_SAMPLE.doi}",
            list(mocked_pdf.call_args.args[0]),
        )
        self.assertEqual(raw_payload.metadata["route"], "pdf_fallback")
        self.assertTrue(raw_payload.needs_local_copy)
        self.assertEqual(article.source, "science")
        self.assertIn("fulltext:science_pdf_fallback_ok", article.quality.source_trail)

    def test_pnas_provider_prefers_html_route(self) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", PNAS_SAMPLE.doi)
            with (
                mock.patch.object(_science_pnas, "load_runtime_config", return_value=runtime),
                mock.patch.object(_science_pnas, "ensure_runtime_ready"),
                mock.patch.object(
                    _science_pnas,
                    "fetch_html_with_flaresolverr",
                    return_value=_flaresolverr.FetchedPublisherHtml(
                        source_url=PNAS_SAMPLE.landing_url,
                        final_url=PNAS_SAMPLE.landing_url,
                        html="<html></html>",
                        response_status=200,
                        response_headers={"content-type": "text/html"},
                        title=PNAS_SAMPLE.title,
                        summary="Example summary",
                        browser_context_seed={},
                    ),
                ),
                mock.patch.object(
                    _science_pnas,
                    "extract_science_pnas_markdown",
                    return_value=(f"# {PNAS_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120), {"title": PNAS_SAMPLE.title}),
                ),
                mock.patch.object(_science_pnas, "fetch_pdf_with_playwright") as mocked_pdf,
            ):
                raw_payload = client.fetch_raw_fulltext(
                    PNAS_SAMPLE.doi,
                    {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
                )
                article = client.to_article_model(
                    {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
                    raw_payload,
                )

        mocked_pdf.assert_not_called()
        self.assertEqual(raw_payload.metadata["route"], "html")
        self.assertEqual(article.source, "pnas")
        self.assertIn("fulltext:pnas_html_ok", article.quality.source_trail)

    def test_pnas_provider_falls_back_to_pdf_with_browser_seed(self) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", PNAS_SAMPLE.doi)
            seed = {
                "browser_cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".pnas.org", "path": "/"}],
                "browser_user_agent": "Mozilla/5.0",
            }
            preflight_seed = {
                "browser_cookies": [{"name": "sessionid", "value": "warm", "domain": ".pnas.org", "path": "/"}],
                "browser_user_agent": "Mozilla/5.0",
            }
            with (
                mock.patch.object(_science_pnas, "load_runtime_config", return_value=runtime),
                mock.patch.object(_science_pnas, "ensure_runtime_ready"),
                mock.patch.object(
                    _science_pnas,
                    "fetch_html_with_flaresolverr",
                    side_effect=_flaresolverr.FlareSolverrFailure(
                        "redirected_to_abstract",
                        "Abstract redirect",
                        browser_context_seed=seed,
                    ),
                ),
                mock.patch.object(
                    _science_pnas,
                    "warm_browser_context_with_flaresolverr",
                    return_value={
                        "browser_cookies": [seed["browser_cookies"][0], preflight_seed["browser_cookies"][0]],
                        "browser_user_agent": "Mozilla/5.0",
                        "browser_final_url": f"https://www.pnas.org/doi/{PNAS_SAMPLE.doi}",
                    },
                ) as mocked_warm,
                mock.patch.object(
                    _science_pnas,
                    "fetch_pdf_with_playwright",
                    return_value=mock.Mock(
                        source_url=f"https://www.pnas.org/doi/pdf/{PNAS_SAMPLE.doi}",
                        final_url=f"https://www.pnas.org/doi/pdf/{PNAS_SAMPLE.doi}",
                        pdf_bytes=fulltext_pdf_bytes(),
                        markdown_text=f"# {PNAS_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                        suggested_filename="article.pdf",
                    ),
                ) as mocked_pdf,
            ):
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
        self.assertEqual(kwargs["seed_urls"], [f"https://www.pnas.org/doi/{PNAS_SAMPLE.doi}"])
        self.assertEqual(
            list(mocked_pdf.call_args.args[0])[:3],
            [
                f"https://www.pnas.org/doi/epdf/{PNAS_SAMPLE.doi}",
                f"https://www.pnas.org/doi/pdf/{PNAS_SAMPLE.doi}?download=true",
                f"https://www.pnas.org/doi/pdf/{PNAS_SAMPLE.doi}",
            ],
        )
        self.assertEqual(raw_payload.metadata["route"], "pdf_fallback")
        self.assertTrue(raw_payload.needs_local_copy)
        self.assertEqual(article.source, "pnas")
        self.assertIn("fulltext:pnas_pdf_fallback_ok", article.quality.source_trail)


if __name__ == "__main__":
    unittest.main()
