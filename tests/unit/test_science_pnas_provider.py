from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch.providers import _flaresolverr, _science_pnas, pnas as pnas_provider, science as science_provider
from tests.unit._paper_fetch_support import fulltext_pdf_bytes


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
            runtime = self._runtime_config(tmpdir, "science", "10.1126/science.ady3136")
            with (
                mock.patch.object(_science_pnas, "load_runtime_config", return_value=runtime),
                mock.patch.object(_science_pnas, "ensure_runtime_ready"),
                mock.patch.object(
                    _science_pnas,
                    "fetch_html_with_flaresolverr",
                    return_value=_flaresolverr.FetchedPublisherHtml(
                        source_url="https://www.science.org/doi/full/10.1126/science.ady3136",
                        final_url="https://www.science.org/doi/full/10.1126/science.ady3136",
                        html="<html></html>",
                        response_status=200,
                        response_headers={"content-type": "text/html"},
                        title="Example Science Article",
                        summary="Example summary",
                        browser_context_seed={},
                    ),
                ),
                mock.patch.object(
                    _science_pnas,
                    "extract_science_pnas_markdown",
                    return_value=("# Example Science Article\n\n## Discussion\n\n" + ("Body text " * 120), {"title": "Example"}),
                ),
                mock.patch.object(_science_pnas, "fetch_pdf_with_playwright") as mocked_pdf,
            ):
                raw_payload = client.fetch_raw_fulltext(
                    "10.1126/science.ady3136",
                    {"doi": "10.1126/science.ady3136", "title": "Example Science Article"},
                )
                article = client.to_article_model(
                    {"doi": "10.1126/science.ady3136", "title": "Example Science Article"},
                    raw_payload,
                )

        mocked_pdf.assert_not_called()
        self.assertEqual(raw_payload.metadata["route"], "html")
        self.assertEqual(article.source, "science")
        self.assertIn("fulltext:science_html_ok", article.quality.source_trail)

    def test_pnas_provider_falls_back_to_pdf_with_browser_seed(self) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", "10.1073/pnas.81.23.7500")
            seed = {
                "browser_cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".pnas.org", "path": "/"}],
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
                    "fetch_pdf_with_playwright",
                    return_value=mock.Mock(
                        source_url="https://www.pnas.org/doi/pdf/10.1073/pnas.81.23.7500",
                        final_url="https://www.pnas.org/doi/pdf/10.1073/pnas.81.23.7500",
                        pdf_bytes=fulltext_pdf_bytes(),
                        markdown_text="# Classic PNAS Example\n\n## Results\n\n" + ("Body text " * 120),
                        suggested_filename="article.pdf",
                    ),
                ) as mocked_pdf,
            ):
                raw_payload = client.fetch_raw_fulltext(
                    "10.1073/pnas.81.23.7500",
                    {"doi": "10.1073/pnas.81.23.7500", "title": "Classic PNAS Example"},
                )
                article = client.to_article_model(
                    {"doi": "10.1073/pnas.81.23.7500", "title": "Classic PNAS Example"},
                    raw_payload,
                )

        mocked_pdf.assert_called_once()
        kwargs = mocked_pdf.call_args.kwargs
        self.assertEqual(kwargs["browser_cookies"], seed["browser_cookies"])
        self.assertEqual(raw_payload.metadata["route"], "pdf_fallback")
        self.assertTrue(raw_payload.needs_local_copy)
        self.assertEqual(article.source, "pnas")
        self.assertIn("fulltext:pnas_pdf_fallback_ok", article.quality.source_trail)


if __name__ == "__main__":
    unittest.main()
