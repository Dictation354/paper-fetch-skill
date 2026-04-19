from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch.http import RequestFailure
from paper_fetch.providers import html_assets
from paper_fetch.providers import _flaresolverr, _science_pnas, pnas as pnas_provider, science as science_provider
from paper_fetch.providers.base import RawFulltextPayload
from tests.provider_benchmark_samples import provider_benchmark_sample
from tests.unit._paper_fetch_support import fulltext_pdf_bytes


SCIENCE_SAMPLE = provider_benchmark_sample("science")
PNAS_SAMPLE = provider_benchmark_sample("pnas")


class AssetTransport:
    def __init__(self, responses: dict[tuple[str, str], dict[str, object] | Exception]) -> None:
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
                "query": dict(query or {}),
                "timeout": timeout,
                "retry_on_rate_limit": retry_on_rate_limit,
                "retry_on_transient": retry_on_transient,
            }
        )
        key = (method, url)
        if key not in self.responses:
            raise AssertionError(f"Missing fake response for {method} {url}")
        response = self.responses[key]
        if isinstance(response, Exception):
            raise response
        return response


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

    def test_science_provider_rewrites_inline_figure_links_to_downloaded_local_assets(self) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            asset_path = Path(tmpdir) / "science-figure-1.png"
            asset_path.write_bytes(b"science-figure")
            raw_payload = RawFulltextPayload(
                provider="science",
                source_url=SCIENCE_SAMPLE.landing_url,
                content_type="text/html",
                body=b"<html></html>",
                metadata={
                    "route": "html",
                    "markdown_text": "\n\n".join(
                        [
                            f"# {SCIENCE_SAMPLE.title}",
                            "## Results",
                            ("Body text " * 80).strip(),
                            "![Figure 1](https://www.science.org/images/figure-1.jpg)",
                            "**Figure 1.** Caption body for the science figure.",
                        ]
                    ),
                    "source_trail": ["fulltext:science_html_ok"],
                },
            )

            article = client.to_article_model(
                {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                raw_payload,
                downloaded_assets=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "caption": "Caption body for the science figure.",
                        "path": str(asset_path),
                        "source_url": "https://www.science.org/images/figure-1.jpg",
                        "section": "body",
                    }
                ],
            )

        body_markdown = article.to_ai_markdown(asset_profile="none")
        self.assertIn(f"![Figure 1]({asset_path})", body_markdown)
        self.assertNotIn("![Figure 1](https://www.science.org/images/figure-1.jpg)", body_markdown)

        markdown = article.to_ai_markdown(asset_profile="body")
        self.assertIn(f"![Figure 1]({asset_path})", markdown)
        self.assertNotIn("![Figure 1](https://www.science.org/images/figure-1.jpg)", markdown)
        self.assertEqual(article.assets[0].path, str(asset_path))

    def test_science_provider_uses_extracted_dom_abstract_and_restores_lead_body_text(self) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        raw_payload = RawFulltextPayload(
            provider="science",
            source_url=SCIENCE_SAMPLE.landing_url,
            content_type="text/html",
            body=b"<html></html>",
            metadata={
                "route": "html",
                "markdown_text": "\n\n".join(
                    [
                        f"# {SCIENCE_SAMPLE.title}",
                        "## Results",
                        "Results body paragraph.",
                    ]
                ),
                "source_trail": ["fulltext:science_html_ok"],
                "extraction": {
                    "title": SCIENCE_SAMPLE.title,
                    "abstract_text": "Short DOM abstract.",
                },
            },
        )

        article = client.to_article_model(
            {
                "doi": SCIENCE_SAMPLE.doi,
                "title": SCIENCE_SAMPLE.title,
                "abstract": "Short DOM abstract. Lead body paragraph that should not remain in the abstract.",
            },
            raw_payload,
        )

        self.assertEqual(article.metadata.abstract, "Short DOM abstract.")
        self.assertEqual(article.sections[0].heading, "Main Text")
        self.assertIn("Lead body paragraph", article.sections[0].text)
        self.assertEqual(article.sections[1].heading, "Results")

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

    def test_science_provider_download_related_assets_body_profile_ignores_supplementary(self) -> None:
        html = """
<article>
  <figure>
    <img src="https://www.science.org/images/large/figure1.png" alt="Figure 1 alt" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
  <a href="https://www.science.org/supp/appendix.pdf">Supplementary Information</a>
</article>
"""
        transport = AssetTransport(
            {
                ("GET", "https://www.science.org/images/large/figure1.png"): {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": b"figure-1",
                    "url": "https://www.science.org/images/large/figure1.png",
                }
            }
        )
        client = science_provider.ScienceClient(transport=transport, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", SCIENCE_SAMPLE.doi)
            raw_payload = RawFulltextPayload(
                provider="science",
                source_url=SCIENCE_SAMPLE.landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                metadata={
                    "route": "html",
                    "markdown_text": f"# {SCIENCE_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                    "browser_context_seed": {},
                },
            )
            with (
                mock.patch.object(_science_pnas, "load_runtime_config", return_value=runtime),
                mock.patch.object(_science_pnas, "ensure_runtime_ready"),
                mock.patch.object(_science_pnas, "fetch_html_with_flaresolverr") as mocked_fetch,
                mock.patch.object(html_assets, "_build_cookie_seeded_opener", return_value=None),
            ):
                result = client.download_related_assets(
                    SCIENCE_SAMPLE.doi,
                    {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )
                saved_path = Path(result["assets"][0]["path"])
                saved_bytes = saved_path.read_bytes()

        mocked_fetch.assert_not_called()
        self.assertEqual([call["url"] for call in transport.calls], ["https://www.science.org/images/large/figure1.png"])
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["assets"][0]["kind"], "figure")
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(saved_bytes, b"figure-1")

    def test_pnas_provider_download_related_assets_uses_figure_page_and_falls_back_to_preview(self) -> None:
        figure_page_url = "https://www.pnas.org/figures/figure-1"
        preview_url = "https://www.pnas.org/images/preview/figure1.png"
        full_size_url = "https://www.pnas.org/images/original/figure1.png"
        html = f"""
<article>
  <figure>
    <a href="{figure_page_url}">View figure</a>
    <img src="{preview_url}" alt="Preview figure" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
</article>
"""
        transport = AssetTransport({})
        client = pnas_provider.PnasClient(transport=transport, env={})
        request_calls: list[dict[str, object]] = []
        initial_seed = {
            "browser_cookies": [{"name": "cf_clearance", "value": "secret", "domain": ".pnas.org", "path": "/"}],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": PNAS_SAMPLE.landing_url,
        }
        warmed_seed = {
            "browser_cookies": [{"name": "sessionid", "value": "warm", "domain": ".pnas.org", "path": "/"}],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": figure_page_url,
        }

        def fake_request_with_opener(_opener, url, *, headers, timeout):
            request_calls.append({"url": url, "headers": dict(headers), "timeout": timeout})
            if url == full_size_url:
                raise RequestFailure(403, "Forbidden", url=url)
            if url == preview_url:
                return {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": b"preview-image",
                    "url": url,
                }
            raise AssertionError(f"Unexpected opener request for {url}")

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", PNAS_SAMPLE.doi)
            raw_payload = RawFulltextPayload(
                provider="pnas",
                source_url=PNAS_SAMPLE.landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                metadata={
                    "route": "html",
                    "markdown_text": f"# {PNAS_SAMPLE.title}\n\n## Results\n\n" + ("Body text " * 120),
                    "browser_context_seed": initial_seed,
                },
            )
            with (
                mock.patch.object(_science_pnas, "load_runtime_config", return_value=runtime),
                mock.patch.object(_science_pnas, "ensure_runtime_ready"),
                mock.patch.object(
                    _science_pnas,
                    "fetch_html_with_flaresolverr",
                    return_value=_flaresolverr.FetchedPublisherHtml(
                        source_url=figure_page_url,
                        final_url=figure_page_url,
                        html=(
                            "<html><head>"
                            f"<meta property='og:image' content='{full_size_url}' />"
                            "</head><body></body></html>"
                        ),
                        response_status=200,
                        response_headers={"content-type": "text/html"},
                        title="Figure page",
                        summary="Figure page summary",
                        browser_context_seed=warmed_seed,
                    ),
                ) as mocked_fetch,
                mock.patch.object(html_assets, "_build_cookie_seeded_opener", return_value=object()),
                mock.patch.object(html_assets, "_request_with_opener", side_effect=fake_request_with_opener),
                ):
                result = client.download_related_assets(
                    PNAS_SAMPLE.doi,
                    {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )
                saved_path = Path(result["assets"][0]["path"])
                saved_bytes = saved_path.read_bytes()

        mocked_fetch.assert_called_once()
        self.assertEqual(mocked_fetch.call_args.args[0], [figure_page_url])
        self.assertEqual([call["url"] for call in request_calls], [full_size_url, preview_url])
        self.assertIn("sessionid=warm", str(request_calls[0]["headers"].get("Cookie") or ""))
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(saved_bytes, b"preview-image")


if __name__ == "__main__":
    unittest.main()
