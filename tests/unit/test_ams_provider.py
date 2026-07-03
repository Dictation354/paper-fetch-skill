from __future__ import annotations

from functools import cache
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from paper_fetch.models import article_from_markdown
from paper_fetch.providers import _ams_html, browser_workflow
from paper_fetch.providers.ams import AmsClient
from paper_fetch.providers.atypon_browser_workflow.asset_scopes import (
    extract_browser_workflow_asset_html_scopes,
)
from paper_fetch.providers.atypon_browser_workflow.markdown import (
    extract_atypon_browser_workflow_markdown,
)
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi
from tests.unit._browser_workflow_deps import install_browser_workflow_deps

from ._atypon_browser_workflow_provider_support import (
    AssetTransport,
    AtyponBrowserWorkflowProviderTestCase,
    _payload_route,
    _payload_source_trail,
    _typed_raw_payload,
    fulltext_pdf_bytes,
)


AMS_DOI = "10.1175/jcli-d-23-0738.1"
AMS_TITLE = "Human Influence Has Increased the Likelihood of Extreme Autumn Fire Weather in California"
AMS_LANDING_URL = (
    "https://journals.ametsoc.org/view/journals/clim/37/24/JCLI-D-23-0738.1.xml"
)
AMS_PDF_URL = (
    "https://journals.ametsoc.org/downloadpdf/journals/clim/37/24/JCLI-D-23-0738.1.xml"
)
AMS_XML_URL = (
    "https://journals.ametsoc.org/doc/journals/clim/37/24/JCLI-D-23-0738.1.xml"
)


def _fixture_metadata(doi: str) -> dict[str, object]:
    sample = golden_criteria_sample_for_doi(doi)
    return {
        "doi": doi,
        "title": sample.get("title"),
        "landing_page_url": sample.get("landing_url") or sample.get("source_url"),
    }


def _fixture_source_url(doi: str) -> str:
    sample = golden_criteria_sample_for_doi(doi)
    return str(sample.get("source_url") or sample.get("landing_url") or "")


def _fixture_html(doi: str) -> str:
    return golden_criteria_asset(doi, "original.html").read_text(
        encoding="utf-8",
        errors="ignore",
    )


def _equation_labels(markdown: str) -> list[str]:
    return re.findall(r"\*\*Equation ([0-9]+[A-Za-z]?)\.\*\*", markdown)


@cache
def _extract_fixture_markdown(doi: str) -> tuple[str, dict[str, object]]:
    return extract_atypon_browser_workflow_markdown(
        _fixture_html(doi),
        _fixture_source_url(doi),
        "ams",
        metadata=_fixture_metadata(doi),
    )


def _fake_downloaded_ams_assets(
    assets: list[dict[str, str]],
    *,
    basenames: set[str],
) -> list[dict[str, str]]:
    downloaded: list[dict[str, str]] = []
    for asset in assets:
        url_blob = " ".join(
            str(asset.get(field) or "")
            for field in (
                "url",
                "full_size_url",
                "preview_url",
                "source_url",
                "download_url",
                "original_url",
            )
        )
        matched = next((basename for basename in basenames if basename in url_blob), "")
        if not matched:
            continue
        local_asset = dict(asset)
        local_asset["path"] = str(Path("/tmp") / matched)
        downloaded.append(local_asset)
    return downloaded


class AmsProviderTests(AtyponBrowserWorkflowProviderTestCase):
    def _metadata(self) -> dict[str, object]:
        return {
            "doi": AMS_DOI,
            "title": AMS_TITLE,
            "landing_page_url": AMS_LANDING_URL,
            "fulltext_links": [
                {
                    "url": AMS_XML_URL,
                    "content_type": "application/xml",
                    "intended_application": "text-mining",
                },
                {
                    "url": AMS_PDF_URL,
                    "content_type": "text/html",
                    "intended_application": "similarity-checking",
                },
            ],
        }

    def test_ams_ignores_browser_runtime_env_on_direct_http_success(self) -> None:
        html = (
            "<html><head><meta name='citation_author' content='Ada Example'></head>"
            "<body><div id='articleBody'><section id='bodymatter'><h2>Results</h2>"
            "<p>Body text.</p></section></div></body></html>"
        )
        transport = AssetTransport(
            {
                ("GET", AMS_LANDING_URL): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": html.encode("utf-8"),
                    "url": AMS_LANDING_URL,
                }
            }
        )
        client = AmsClient(
            transport=transport,
            env={"PAPER_FETCH_AMS_STORAGE_STATE_JSON": "/tmp/unused.json"},
        )
        mocked_load_runtime = mock.Mock()
        mocked_ensure_runtime = mock.Mock()
        mocked_browser_html = mock.Mock()
        install_browser_workflow_deps(
            client,
            load_runtime_config=mocked_load_runtime,
            ensure_runtime_ready=mocked_ensure_runtime,
            fetch_html_with_browser=mocked_browser_html,
            _cached_browser_workflow_markdown=mock.Mock(
                return_value=(
                    f"# {AMS_TITLE}\n\n## Results\n\n" + ("Body text " * 120),
                    {"title": AMS_TITLE},
                )
            ),
        )

        raw_payload = client.fetch_raw_fulltext(AMS_DOI, self._metadata())

        self.assertEqual(_payload_route(raw_payload), "html")
        self.assertEqual(raw_payload.content.fetcher, "direct_http")
        mocked_load_runtime.assert_not_called()
        mocked_ensure_runtime.assert_not_called()
        mocked_browser_html.assert_not_called()

    def test_ams_direct_http_route_ignores_citation_xml_url(self) -> None:
        html = (
            "<html><head><meta name='citation_author' content='Ada Example'></head>"
            "<body><div id='articleBody'><section id='bodymatter'><h2>Results</h2>"
            "<p>Body text.</p></section></div></body></html>"
        )
        transport = AssetTransport(
            {
                ("GET", AMS_LANDING_URL): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": html.encode("utf-8"),
                    "url": AMS_LANDING_URL,
                }
            }
        )
        client = AmsClient(transport=transport, env={})
        install_browser_workflow_deps(
            client,
            _cached_browser_workflow_markdown=mock.Mock(
                return_value=(
                    f"# {AMS_TITLE}\n\n## Results\n\n" + ("Body text " * 120),
                    {"title": AMS_TITLE},
                )
            ),
        )

        raw_payload = client.fetch_raw_fulltext(AMS_DOI, self._metadata())
        article = client.to_article_model(self._metadata(), raw_payload)

        attempted_html = [call["url"] for call in transport.calls]
        self.assertEqual(attempted_html, [AMS_LANDING_URL])
        self.assertFalse(any("/doc/" in candidate for candidate in attempted_html))
        self.assertFalse(any(candidate == AMS_XML_URL for candidate in attempted_html))
        self.assertEqual(_payload_route(raw_payload), "html")
        self.assertEqual(article.source, "ams_html")
        self.assertIn("fulltext:ams_html_ok", article.quality.source_trail)

    def test_ams_direct_http_preflight_succeeds_without_browser_runtime(self) -> None:
        html = (
            "<html><head><meta name='citation_author' content='Ada Example'></head>"
            "<body><div id='articleBody'><section id='bodymatter'><h2>Results</h2>"
            "<p>Body text.</p></section></div></body></html>"
        )
        transport = AssetTransport(
            {
                ("GET", AMS_LANDING_URL): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": html.encode("utf-8"),
                    "url": AMS_LANDING_URL,
                }
            }
        )
        client = AmsClient(transport=transport, env={})
        mocked_load_runtime = mock.Mock()
        mocked_ensure_runtime = mock.Mock()
        mocked_browser_html = mock.Mock()
        install_browser_workflow_deps(
            client,
            load_runtime_config=mocked_load_runtime,
            ensure_runtime_ready=mocked_ensure_runtime,
            fetch_html_with_browser=mocked_browser_html,
            _cached_browser_workflow_markdown=mock.Mock(
                return_value=(
                    f"# {AMS_TITLE}\n\n## Results\n\n" + ("Body text " * 120),
                    {"title": AMS_TITLE},
                )
            ),
        )

        raw_payload = client.fetch_raw_fulltext(AMS_DOI, self._metadata())

        self.assertEqual(_payload_route(raw_payload), "html")
        self.assertEqual(raw_payload.source_url, AMS_LANDING_URL)
        self.assertEqual(raw_payload.content.fetcher, "direct_http")
        self.assertEqual(
            raw_payload.content.diagnostics["html_fetcher"],
            "direct_http",
        )
        self.assertEqual(
            raw_payload.content.browser_context_seed["paper_fetch_html_fetcher"],
            "direct_http",
        )
        self.assertIn(
            "Chrome/",
            raw_payload.content.browser_context_seed["browser_user_agent"],
        )
        mocked_load_runtime.assert_not_called()
        mocked_ensure_runtime.assert_not_called()
        mocked_browser_html.assert_not_called()
        self.assertEqual(len(transport.calls), 1)
        request_headers = transport.calls[0]["headers"]
        self.assertIn("Chrome/", request_headers["User-Agent"])
        self.assertEqual(request_headers["Referer"], AMS_LANDING_URL)

    def test_ams_direct_http_preflight_follows_doi_redirect_without_browser_runtime(
        self,
    ) -> None:
        doi_landing_url = "https://journals.ametsoc.org/doi/10.1175/JCLI-D-23-0738.1"
        html = (
            "<html><head><meta name='citation_author' content='Ada Example'></head>"
            "<body><div id='articleBody'><section id='bodymatter'><h2>Results</h2>"
            "<p>Body text.</p></section></div></body></html>"
        )
        transport = AssetTransport(
            {
                ("GET", doi_landing_url): {
                    "status_code": 301,
                    "headers": {
                        "content-type": "text/html; charset=utf-8",
                        "location": AMS_LANDING_URL,
                    },
                    "body": b"<html><body>DOI Resolve</body></html>",
                    "url": doi_landing_url,
                },
                ("GET", AMS_LANDING_URL): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": html.encode("utf-8"),
                    "url": AMS_LANDING_URL,
                },
            }
        )
        metadata = {**self._metadata(), "landing_page_url": doi_landing_url}
        client = AmsClient(transport=transport, env={})
        mocked_load_runtime = mock.Mock()
        mocked_ensure_runtime = mock.Mock()
        mocked_browser_html = mock.Mock()
        install_browser_workflow_deps(
            client,
            load_runtime_config=mocked_load_runtime,
            ensure_runtime_ready=mocked_ensure_runtime,
            fetch_html_with_browser=mocked_browser_html,
            _cached_browser_workflow_markdown=mock.Mock(
                return_value=(
                    f"# {AMS_TITLE}\n\n## Results\n\n" + ("Body text " * 120),
                    {"title": AMS_TITLE},
                )
            ),
        )

        raw_payload = client.fetch_raw_fulltext(AMS_DOI, metadata)

        self.assertEqual(_payload_route(raw_payload), "html")
        self.assertEqual(raw_payload.source_url, AMS_LANDING_URL)
        self.assertEqual(raw_payload.content.fetcher, "direct_http")
        self.assertEqual(
            raw_payload.content.browser_context_seed["browser_final_url"],
            AMS_LANDING_URL,
        )
        mocked_load_runtime.assert_not_called()
        mocked_ensure_runtime.assert_not_called()
        mocked_browser_html.assert_not_called()
        self.assertEqual(
            [call["url"] for call in transport.calls],
            [doi_landing_url, AMS_LANDING_URL],
        )
        self.assertIn("Chrome/", transport.calls[0]["headers"]["User-Agent"])
        self.assertEqual(transport.calls[0]["headers"]["Referer"], doi_landing_url)
        self.assertEqual(transport.calls[1]["headers"]["Referer"], doi_landing_url)

    def test_ams_direct_http_preflight_fails_when_redirect_reaches_challenge(
        self,
    ) -> None:
        doi_landing_url = "https://journals.ametsoc.org/doi/10.1175/JCLI-D-23-0738.1"
        challenge_url = (
            "https://journals.ametsoc.org/view/journals/clim/37/24/JCLI-D-23-0738.1.xml"
        )
        transport = AssetTransport(
            {
                ("GET", doi_landing_url): {
                    "status_code": 301,
                    "headers": {
                        "content-type": "text/html; charset=utf-8",
                        "location": challenge_url,
                    },
                    "body": b"<html><body>DOI Resolve</body></html>",
                    "url": doi_landing_url,
                },
                ("GET", challenge_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": (
                        b"<html><body><h1>Let's confirm you are human</h1>"
                        b"<p>Complete the security check before continuing.</p></body></html>"
                    ),
                    "url": challenge_url,
                },
                ("GET", AMS_PDF_URL): {
                    "status_code": 200,
                    "headers": {"content-type": "application/pdf"},
                    "body": fulltext_pdf_bytes(),
                    "url": AMS_PDF_URL,
                },
            }
        )
        metadata = {**self._metadata(), "landing_page_url": doi_landing_url}
        client = AmsClient(transport=transport, env={})
        mocked_browser_html = mock.Mock()
        install_browser_workflow_deps(
            client,
            fetch_html_with_browser=mocked_browser_html,
        )

        raw_payload = client.fetch_raw_fulltext(AMS_DOI, metadata)

        self.assertEqual(_payload_route(raw_payload), "pdf_fallback")
        self.assertIn(
            "fulltext:ams_pdf_fallback_ok", _payload_source_trail(raw_payload)
        )
        mocked_browser_html.assert_not_called()
        self.assertEqual(
            [call["url"] for call in transport.calls],
            [doi_landing_url, challenge_url, AMS_PDF_URL],
        )

    def test_ams_direct_http_preflight_does_not_fall_back_to_browser_on_403(
        self,
    ) -> None:
        transport = AssetTransport(
            {
                ("GET", AMS_LANDING_URL): {
                    "status_code": 403,
                    "headers": {"content-type": "text/html"},
                    "body": b"<html><title>Forbidden</title></html>",
                    "url": AMS_LANDING_URL,
                },
                ("GET", AMS_PDF_URL): {
                    "status_code": 200,
                    "headers": {"content-type": "application/pdf"},
                    "body": fulltext_pdf_bytes(),
                    "url": AMS_PDF_URL,
                },
            }
        )
        client = AmsClient(transport=transport, env={})
        mocked_browser_html = mock.Mock()
        install_browser_workflow_deps(
            client,
            fetch_html_with_browser=mocked_browser_html,
        )

        raw_payload = client.fetch_raw_fulltext(AMS_DOI, self._metadata())

        self.assertEqual(_payload_route(raw_payload), "pdf_fallback")
        self.assertIn(
            "fulltext:ams_pdf_fallback_ok", _payload_source_trail(raw_payload)
        )
        mocked_browser_html.assert_not_called()
        self.assertEqual(
            [call["url"] for call in transport.calls], [AMS_LANDING_URL, AMS_PDF_URL]
        )

    def test_ams_direct_http_asset_download_uses_browser_seed_without_runtime(
        self,
    ) -> None:
        browser_user_agent = (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        raw_payload = _typed_raw_payload(
            provider="ams",
            source_url=AMS_LANDING_URL,
            content_type="text/html",
            body=b"<html></html>",
            route="html",
            browser_context_seed={
                "browser_final_url": AMS_LANDING_URL,
                "browser_user_agent": browser_user_agent,
                "paper_fetch_html_fetcher": "direct_http",
            },
        )
        client = AmsClient(transport=AssetTransport({}), env={})
        mocked_load_runtime = mock.Mock()
        mocked_ensure_runtime = mock.Mock()
        mocked_image_builder = mock.Mock()
        mocked_download_assets = mock.Mock(
            return_value={"assets": [], "asset_failures": []}
        )
        install_browser_workflow_deps(
            client,
            load_runtime_config=mocked_load_runtime,
            ensure_runtime_ready=mocked_ensure_runtime,
            _build_shared_browser_image_fetcher=mocked_image_builder,
            download_assets=mocked_download_assets,
        )
        figure_asset = {
            "kind": "figure",
            "heading": "Figure 1",
            "download_url": "https://journals.ametsoc.org/view/journals/clim/37/24/JCLI-D-23-0738.1-f1.eps",
            "full_size_url": "https://journals.ametsoc.org/view/journals/clim/37/24/full-JCLI-D-23-0738.1-f1.jpg",
            "section": "body",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = client._download_browser_backed_related_assets(
                AMS_DOI,
                self._metadata(),
                raw_payload,
                Path(tmpdir),
                asset_profile="body",
                assets=[figure_asset],
            )

        self.assertEqual(result, {"assets": [], "asset_failures": []})
        mocked_load_runtime.assert_not_called()
        mocked_ensure_runtime.assert_not_called()
        mocked_image_builder.assert_not_called()
        mocked_download_assets.assert_called_once()
        call = mocked_download_assets.call_args
        self.assertEqual(call.kwargs["headers"], {"Referer": AMS_LANDING_URL})
        self.assertEqual(
            call.kwargs["browser_context_seed"]["browser_user_agent"],
            browser_user_agent,
        )
        self.assertEqual(
            call.kwargs["seed_urls"],
            [AMS_LANDING_URL],
        )

    def test_ams_direct_http_failure_uses_direct_pdf_not_browser_pdf_fallback(
        self,
    ) -> None:
        transport = AssetTransport(
            {
                ("GET", AMS_LANDING_URL): {
                    "status_code": 403,
                    "headers": {"content-type": "text/html"},
                    "body": b"<html><title>Forbidden</title></html>",
                    "url": AMS_LANDING_URL,
                },
                ("GET", AMS_PDF_URL): {
                    "status_code": 200,
                    "headers": {"content-type": "application/pdf"},
                    "body": fulltext_pdf_bytes(),
                    "url": AMS_PDF_URL,
                },
            }
        )
        client = AmsClient(transport=transport, env={})
        mocked_pdf = mock.Mock()
        install_browser_workflow_deps(client, fetch_pdf_with_browser=mocked_pdf)

        raw_payload = client.fetch_raw_fulltext(AMS_DOI, self._metadata())

        self.assertEqual(_payload_route(raw_payload), "pdf_fallback")
        self.assertEqual(raw_payload.content.fetcher, None)
        mocked_pdf.assert_not_called()

    def test_ams_old_style_doi_builds_html_candidate_and_uses_explicit_pdf_candidates(
        self,
    ) -> None:
        client = AmsClient(transport=None, env={})
        old_doi = "10.1175/1520-0469(1967)024<0241:teotaw>2.0.co;2"
        old_landing = (
            "https://journals.ametsoc.org/view/journals/atsc/24/3/"
            "1520-0469_1967_024_0241_teotaw_2_0_co_2.xml"
        )
        old_pdf = (
            "https://journals.ametsoc.org/downloadpdf/view/journals/atsc/24/3/"
            "1520-0469_1967_024_0241_teotaw_2_0_co_2.pdf"
        )

        self.assertEqual(
            client.html_candidates(old_doi, {"doi": old_doi}),
            [
                "https://doi.org/10.1175/1520-0469%281967%29024%3C0241%3Ateotaw%3E2.0.co%3B2"
            ],
        )
        self.assertEqual(
            client.pdf_candidates(
                old_doi, {"doi": old_doi, "landing_page_url": old_landing}
            ),
            [],
        )
        self.assertEqual(
            client.pdf_candidates(
                old_doi, {"doi": old_doi, "landing_page_url": old_pdf}
            ),
            [old_pdf],
        )

    def test_ams_html_extraction_failure_uses_citation_pdf_url_directly(self) -> None:
        citation_pdf_url = (
            "https://journals.ametsoc.org/downloadpdf/journals/clim/38/1/AMS-TEST.1.xml"
        )
        html = f"""
        <html><head><meta name="citation_pdf_url" content="{citation_pdf_url}"></head>
        <body><article><section role="doc-abstract"><p>Abstract only.</p></section></article></body></html>
        """
        transport = AssetTransport(
            {
                ("GET", AMS_LANDING_URL): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": html.encode("utf-8"),
                    "url": AMS_LANDING_URL,
                },
                ("GET", citation_pdf_url): {
                    "status_code": 200,
                    "headers": {"content-type": "application/pdf"},
                    "body": fulltext_pdf_bytes(),
                    "url": citation_pdf_url,
                },
            }
        )
        client = AmsClient(transport=transport, env={})
        mocked_pdf = mock.Mock()
        install_browser_workflow_deps(
            client,
            _cached_browser_workflow_markdown=mock.Mock(
                side_effect=browser_workflow.HtmlExtractionFailure(
                    "abstract_only", "Abstract only."
                )
            ),
            fetch_pdf_with_browser=mocked_pdf,
        )

        raw_payload = client.fetch_raw_fulltext(
            AMS_DOI,
            {
                "doi": AMS_DOI,
                "title": AMS_TITLE,
                "landing_page_url": AMS_LANDING_URL,
            },
        )

        self.assertEqual(_payload_route(raw_payload), "pdf_fallback")
        self.assertEqual(raw_payload.source_url, citation_pdf_url)
        mocked_pdf.assert_not_called()

    def test_ams_asset_extractor_uses_lazy_image_and_gallery_link(self) -> None:
        html = """
        <article>
          <figure>
            <a class="figure-link">
              <img
                data-image-src="/view/journals/clim/37/24/inline-JCLI-D-23-0738.1-f1.jpg"
                src="/skin/site/img/Blank.svg"
                alt="Fig. 1."
              />
            </a>
            <pf-box class="figure-popover">
              <img
                data-image-src="/view/journals/clim/37/24/full-JCLI-D-23-0738.1-f1.jpg"
                src="/skin/site/img/Blank.svg"
                alt="Fig. 1."
              />
            </pf-box>
            <a
              title="View in gallery"
              href="/view/journals/clim/37/24/full-JCLI-D-23-0738.1-f1.jpg"
            >View in gallery</a>
            <figcaption><b>Fig. 1.</b> Schematic.</figcaption>
          </figure>
        </article>
        """

        assets = _ams_html.scoped_asset_extractor(
            html,
            AMS_LANDING_URL,
            asset_profile="body",
        )

        self.assertEqual(len(assets), 1)
        self.assertEqual(
            assets[0]["url"],
            "https://journals.ametsoc.org/view/journals/clim/37/24/full-JCLI-D-23-0738.1-f1.jpg",
        )
        self.assertEqual(
            assets[0]["preview_url"],
            "https://journals.ametsoc.org/view/journals/clim/37/24/inline-JCLI-D-23-0738.1-f1.jpg",
        )
        self.assertEqual(
            assets[0]["full_size_url"],
            "https://journals.ametsoc.org/view/journals/clim/37/24/full-JCLI-D-23-0738.1-f1.jpg",
        )
        self.assertNotIn("Blank.svg", assets[0]["url"])

    def test_ams_formula_asset_extractor_uses_lazy_formula_image(self) -> None:
        html = """
        <article>
          <figure>
            <img
              data-image-src="/view/journals/hydr/20/1/images/inline-jhm-d-18-0159_1-f1.jpg"
              src="/skin/site/img/Blank.svg"
              alt="Fig. 1."
            />
            <figcaption><b>Fig. 1.</b> Schematic.</figcaption>
          </figure>
          <section>
            <h2>1. Introduction</h2>
            <p>
              This article section contains enough narrative body text for the
              AMS HTML quality gate while keeping the fixture
              focused on lazy formula image handling. The paragraph describes
              atmospheric moisture transport, precipitation recycling, regional
              source attribution, and trajectory-based diagnostics in ordinary
              prose so that extraction can distinguish it from a gallery shell.
              The text intentionally continues with additional body content
              about evaporation, precipitable water, local and external source
              regions, and hydrologic interpretation before the equation image.
            </p>
            <div class="formula" id="e1">
              <div class="image-wrapper flex flex-col flex-align-start">
                <img
                  data-image-src="/view/journals/hydr/20/1/images/inline-jhm-d-18-0159_1-e1.gif"
                  src="/skin/site/img/Blank.svg"
                  alt="e1"
                />
              </div>
            </div>
            <p>
              The following sentence confirms that normal article prose resumes
              after the equation and remains separate from the formula image.
            </p>
          </section>
        </article>
        """

        assets = _ams_html.scoped_asset_extractor(
            html,
            "https://journals.ametsoc.org/view/journals/hydr/20/1/jhm-d-18-0159_1.xml",
            asset_profile="body",
        )
        figure_assets = [asset for asset in assets if asset.get("kind") == "figure"]
        formula_assets = [asset for asset in assets if asset.get("kind") == "formula"]

        self.assertEqual(len(figure_assets), 1)
        self.assertEqual(len(formula_assets), 1)
        self.assertEqual(formula_assets[0]["heading"], "e1")
        self.assertEqual(
            formula_assets[0]["url"],
            (
                "https://journals.ametsoc.org/view/journals/hydr/20/1/images/"
                "inline-jhm-d-18-0159_1-e1.gif"
            ),
        )
        self.assertNotIn("Blank.svg", formula_assets[0]["url"])
        self.assertEqual(figure_assets[0]["kind"], "figure")

        markdown, _ = extract_atypon_browser_workflow_markdown(
            html,
            "https://journals.ametsoc.org/view/journals/hydr/20/1/jhm-d-18-0159_1.xml",
            "ams",
            metadata={"doi": "10.1175/JHM-D-18-0159.1"},
        )

        self.assertIn(
            "![Formula](/view/journals/hydr/20/1/images/inline-jhm-d-18-0159_1-e1.gif)",
            markdown,
        )
        self.assertNotIn("![Formula](/skin/site/img/Blank.svg)", markdown)

    def test_ams_asset_extractor_prefers_download_figure_source_file(self) -> None:
        html = """
        <article>
          <div id="fig2" class="figure">
            <figure>
              <div class="figure-image-wrapper">
                <img
                  data-image-src="/view/journals/apme/63/12/inline-JAMC-D-24-0048.1-f2.jpg"
                  src="/skin/site/img/Blank.svg"
                  alt="Fig. 2."
                />
                <pf-box class="figure-popover">
                  <img
                    data-image-src="/view/journals/apme/63/12/full-JAMC-D-24-0048.1-f2.jpg"
                    src="/skin/site/img/Blank.svg"
                    alt="Fig. 2."
                  />
                </pf-box>
              </div>
              <div class="figure-text-wrapper">
                <figcaption>Fig. 2.</figcaption>
                <p>U-Net model architecture is shown here.</p>
                <ul>
                  <li class="download-figure">
                    <a download="JAMC-D-24-0048.1-f2.eps"
                       href="/view/journals/apme/63/12/JAMC-D-24-0048.1-f2.eps">Download Figure</a>
                  </li>
                  <li class="download-figure">
                    <a href="#" class="export-figure-ppt"
                       data-image-uris="/view/journals/apme/63/12/full-JAMC-D-24-0048.1-f2.jpg">
                       Download figure as PowerPoint slide
                    </a>
                  </li>
                </ul>
              </div>
            </figure>
          </div>
        </article>
        """

        assets = _ams_html.scoped_asset_extractor(
            html,
            AMS_LANDING_URL,
            asset_profile="body",
        )

        self.assertEqual(len(assets), 1)
        self.assertEqual(
            assets[0]["download_url"],
            "https://journals.ametsoc.org/view/journals/apme/63/12/JAMC-D-24-0048.1-f2.eps",
        )
        self.assertEqual(assets[0]["source_asset_format"], "eps")
        self.assertEqual(assets[0]["source_filename"], "JAMC-D-24-0048.1-f2.eps")
        self.assertEqual(
            assets[0]["full_size_url"],
            "https://journals.ametsoc.org/view/journals/apme/63/12/full-JAMC-D-24-0048.1-f2.jpg",
        )
        self.assertNotEqual(assets[0]["download_url"], "#")

    def test_ams_browser_asset_scope_preserves_download_figure_source_after_cleanup(
        self,
    ) -> None:
        html = """
        <html>
          <body>
            <div id="articleBody">
              <p>
                Drought monitoring body text with enough prose to select the
                article body container for browser workflow asset extraction.
              </p>
              <div id="fig2" class="figure">
                <figure>
                  <div class="figure-image-wrapper">
                    <img
                      data-image-src="/view/journals/apme/63/12/inline-JAMC-D-24-0048.1-f2.jpg"
                      src="/skin/site/img/Blank.svg"
                      alt="Fig. 2."
                    />
                    <pf-box class="figure-popover">
                      <img
                        data-image-src="/view/journals/apme/63/12/full-JAMC-D-24-0048.1-f2.jpg"
                        src="/skin/site/img/Blank.svg"
                        alt="Fig. 2."
                      />
                    </pf-box>
                  </div>
                  <div class="figure-text-wrapper">
                    <figcaption>Fig. 2.</figcaption>
                    <p>U-Net model architecture is shown here.</p>
                    <ul>
                      <li class="download-figure">
                        <a download="JAMC-D-24-0048.1-f2.eps"
                           href="/view/journals/apme/63/12/JAMC-D-24-0048.1-f2.eps">Download Figure</a>
                      </li>
                      <li class="download-figure">
                        <a href="#" class="export-figure-ppt"
                           data-image-uris="/view/journals/apme/63/12/full-JAMC-D-24-0048.1-f2.jpg">
                           Download figure as PowerPoint slide
                        </a>
                      </li>
                    </ul>
                  </div>
                </figure>
              </div>
            </div>
          </body>
        </html>
        """

        body_html, supplementary_html = extract_browser_workflow_asset_html_scopes(
            html,
            AMS_LANDING_URL,
            "ams",
        )
        assets = _ams_html.scoped_asset_extractor(
            body_html,
            AMS_LANDING_URL,
            asset_profile="body",
            supplementary_html_text=supplementary_html,
        )

        self.assertEqual(len(assets), 1)
        self.assertEqual(
            assets[0]["download_url"],
            "https://journals.ametsoc.org/view/journals/apme/63/12/JAMC-D-24-0048.1-f2.eps",
        )
        self.assertEqual(assets[0]["source_asset_format"], "eps")
        self.assertEqual(assets[0]["source_filename"], "JAMC-D-24-0048.1-f2.eps")

    def test_ams_fixture_extracts_mixed_tiff_and_eps_download_figure_sources(
        self,
    ) -> None:
        doi = "10.1175/jamc-d-24-0048.1"
        assets = _ams_html.scoped_asset_extractor(
            _fixture_html(doi),
            _fixture_source_url(doi),
            asset_profile="body",
        )
        figures = [asset for asset in assets if asset.get("kind") == "figure"]

        figure1 = next(
            asset
            for asset in figures
            if str(asset.get("full_size_url", "")).endswith("-f1.jpg")
        )
        figure2 = next(
            asset
            for asset in figures
            if str(asset.get("full_size_url", "")).endswith("-f2.jpg")
        )

        self.assertTrue(str(figure1.get("download_url", "")).endswith("-f1.tif"))
        self.assertEqual(figure1.get("source_asset_format"), "tiff")
        self.assertTrue(str(figure2.get("download_url", "")).endswith("-f2.eps"))
        self.assertEqual(figure2.get("source_asset_format"), "eps")

    def test_ams_tablewrap_image_does_not_duplicate_generic_figure_asset(self) -> None:
        html = """
        <article>
          <figure class="tableWrap" id="tbl1">
            <span class="tableWrapLabel">Table 1.</span>
            <span class="tableWrapCaption"><p>Observed values.</p></span>
            <img
              data-image-src="/view/journals/clim/37/24/full-JCLI-D-23-0738.1-t1.jpg"
              src="/skin/site/img/Blank.svg"
              alt="Table 1."
            />
          </figure>
        </article>
        """

        assets = _ams_html.scoped_asset_extractor(
            html,
            AMS_LANDING_URL,
            asset_profile="body",
        )

        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["kind"], "table")
        self.assertEqual(assets[0]["heading"], "Table 1.")
        self.assertIn("full-JCLI-D-23-0738.1-t1.jpg", assets[0]["url"])

    def test_ams_author_and_reference_helpers_use_shared_extractors(self) -> None:
        self.assertEqual(
            _ams_html.extract_authors(
                """
                <html><head>
                  <meta name="dc.Creator" content="Ada Example">
                </head><body></body></html>
                """
            ),
            ["Ada Example"],
        )
        self.assertEqual(
            _ams_html.extract_authors(
                """
                <html><body>
                  <div class="authors"><a>Grace Fallback</a></div>
                </body></html>
                """
            ),
            ["Grace Fallback"],
        )

        references = _ams_html.extract_references(
            """
            <html><head>
              <meta name="citation_reference" content="Stale meta reference">
            </head><body>
              <section data-title="References">
                <ol><li>Numbered Reference (2024). https://doi.org/10.1175/example</li></ol>
              </section>
            </body></html>
            """
        )

        self.assertEqual(len(references), 1)
        self.assertEqual(references[0]["label"], "1.")
        self.assertIn("Numbered Reference", str(references[0]["raw"]))
        self.assertNotIn("Stale meta reference", str(references[0]["raw"]))

    def test_ams_bams_fixture_keeps_late_body_sections(self) -> None:
        """
        rule: rule-ams-html-body-assets-formulas
        rule: rule-ams-footnotes-stay-linked-to-body-markers
        """
        doi = "10.1175/bams-d-24-0223.1"
        markdown, extraction = _extract_fixture_markdown(doi)

        for expected in (
            "## 2. The history of WAVEWATCH III",
            "## 3. From open source to open science",
            "## 6. Lessons learned",
            "## Acknowledgments",
            "## Data availability statement",
        ):
            self.assertIn(expected, markdown)

        self.assertIn("## Footnotes", markdown)
        self.assertIn("<sup>1</sup> https://www.top500.org.", markdown)
        self.assertIn("<sup>16</sup> The preference of open-source licensing", markdown)
        self.assertLess(
            markdown.index("## 2. The history of WAVEWATCH III"),
            markdown.index("## 6. Lessons learned"),
        )
        self.assertLess(
            markdown.index("## Footnotes"), markdown.index("## Acknowledgments")
        )
        self.assertLess(
            markdown.index("## Acknowledgments"),
            markdown.index("## Data availability statement"),
        )
        self.assertNotIn("\n\nhttps://www.top500.org.\n\n", markdown)
        self.assertNotIn("\n\nhttps://git-scm.com/docs.\n\n", markdown)
        self.assertNotIn("Fig .", markdown)
        self.assertNotIn("<sup><sup>", markdown)
        self.assertNotIn("<sup>,</sup>", markdown)

        article = article_from_markdown(
            source="ams_html",
            metadata=_fixture_metadata(doi),
            doi=doi,
            markdown_text=markdown,
            section_hints=list(extraction.get("section_hints") or []),
        )
        rendered = article.to_ai_markdown(max_tokens="full_text")

        self.assertIn("## Acknowledgments", rendered)
        self.assertIn("## Data availability statement", rendered)
        self.assertIn("## Footnotes", rendered)
        self.assertIn(
            "data_availability",
            {
                section.kind
                for section in article.sections
                if section.heading == "Data availability statement"
            },
        )

    def test_ams_table_images_are_extracted_and_rendered_inline(self) -> None:
        """rule: rule-ams-html-body-assets-formulas"""
        cases = (
            (
                "10.1175/jamc-d-24-0048.1",
                "/view/journals/apme/63/12/full-JAMC-D-24-0048.1-t1.jpg",
            ),
            (
                "10.1175/waf-d-24-0019.1",
                "/view/journals/wefo/39/12/full-WAF-D-24-0019.1-t1.jpg",
            ),
            (
                "10.1175/jpo-d-23-0234.1",
                "/view/journals/phoc/54/12/full-JPO-D-23-0234.1-t1.jpg",
            ),
            (
                "10.1175/jtech-d-24-0028.1",
                "/view/journals/atot/41/12/full-JTECH-D-24-0028.1-t1.jpg",
            ),
        )
        for doi, full_size_path in cases:
            with self.subTest(doi=doi):
                markdown, _ = _extract_fixture_markdown(doi)
                assets = _ams_html.scoped_asset_extractor(
                    _fixture_html(doi),
                    _fixture_source_url(doi),
                    asset_profile="body",
                )
                table_assets = [
                    asset for asset in assets if asset.get("kind") == "table"
                ]

                self.assertTrue(table_assets)
                self.assertTrue(
                    any(
                        full_size_path in str(asset.get("url") or "")
                        for asset in table_assets
                    )
                )
                self.assertIn("**Table 1.**", markdown)
                self.assertIn(f"![Table 1]({full_size_path})", markdown)
                self.assertLess(
                    markdown.index("**Table 1.**"),
                    markdown.index(f"![Table 1]({full_size_path})"),
                )

    def test_ams_aies_table_image_is_not_rewritten_to_next_figure(self) -> None:
        """rule: rule-ams-html-body-assets-formulas"""
        markdown, _ = _extract_fixture_markdown("10.1175/aies-d-23-0093.1")
        table_image = "![Table 1](/view/journals/aies/3/4/full-AIES-D-23-0093.1-t1.jpg)"
        figure2_image = (
            "![Figure 2](https://journals.ametsoc.org/view/journals/aies/3/4/"
            "full-AIES-D-23-0093.1-f2.jpg)"
        )

        table_image_blocks = [
            block for block in markdown.split("\n\n") if block.startswith("![Table 1](")
        ]
        figure2_image_blocks = [
            block
            for block in markdown.split("\n\n")
            if "full-AIES-D-23-0093.1-f2.jpg" in block
        ]

        self.assertEqual(table_image_blocks, [table_image])
        self.assertEqual(figure2_image_blocks, [figure2_image])
        self.assertLess(markdown.index("**Table 1.**"), markdown.index(table_image))
        self.assertLess(markdown.index(table_image), markdown.index(figure2_image))
        self.assertLess(markdown.index(figure2_image), markdown.index("**Figure 2.**"))

    def test_ams_figures_are_inline_with_complete_caption_without_chrome(self) -> None:
        """rule: rule-ams-html-body-assets-formulas"""
        markdown, _ = _extract_fixture_markdown("10.1175/jamc-d-24-0048.1")
        image = (
            "![Figure 2](https://journals.ametsoc.org/view/journals/apme/63/12/"
            "full-JAMC-D-24-0048.1-f2.jpg)"
        )
        caption = "**Figure 2.** U-Net model architecture is shown here."

        self.assertIn(image, markdown)
        self.assertIn(caption, markdown)
        self.assertLess(markdown.index(image), markdown.index(caption))
        self.assertEqual(markdown.count(image), 1)
        self.assertEqual(markdown.count("**Figure 2.**"), 1)
        for noise in ("Fig .", "Download Figure", "View Full Size", "PowerPoint"):
            self.assertNotIn(noise, markdown)
        self.assertNotIn("\n## Figures\n", markdown)

    def test_ams_formula_cleanup_removes_mathjax_fallback_noise(self) -> None:
        """rule: rule-ams-html-body-assets-formulas"""
        markdown, _ = _extract_fixture_markdown("10.1175/waf-d-24-0019.1")
        jamc_markdown, _ = _extract_fixture_markdown("10.1175/jamc-d-24-0048.1")

        self.assertIn("\\text{YJ}", markdown)
        self.assertIn("\\text{BLPW}", jamc_markdown)
        self.assertNotIn("**Equation 1.**\n\nwhere", jamc_markdown)
        for noise in (
            "YJ(x;λ)=",
            "ifλ",
            "MathJax",
            "MJXc",
            "<sup><sup>",
            "<sub><sub>",
            "Fig .",
            "Table .",
        ):
            self.assertNotIn(noise, markdown)

    def test_ams_numbered_display_equations_use_source_labels_only(self) -> None:
        """rule: rule-ams-html-body-assets-formulas"""
        cases = (
            (
                "10.1175/jpo-d-23-0234.1",
                [
                    "1",
                    "2",
                    "3",
                    "4",
                    "5",
                    "6",
                    "7a",
                    "7b",
                    "7c",
                    "7d",
                    "7e",
                    "8",
                    "9a",
                    "9b",
                    "9c",
                    "9d",
                    "10",
                    "11",
                    "13a",
                    "13b",
                    "14",
                    "15",
                    "16",
                    "17",
                    "18",
                ],
            ),
            (
                "10.1175/waf-d-24-0019.1",
                ["1", "2", "3", "4", "5"],
            ),
        )
        for doi, expected_labels in cases:
            with self.subTest(doi=doi):
                markdown, _ = _extract_fixture_markdown(doi)
                labels = _equation_labels(markdown)

                self.assertEqual(labels, expected_labels)
                self.assertEqual(len(labels), len(set(labels)))

        jpo_markdown, _ = _extract_fixture_markdown("10.1175/jpo-d-23-0234.1")
        self.assertEqual(jpo_markdown.count("**Equation 1.**"), 1)
        self.assertEqual(jpo_markdown.count("**Equation 14.**"), 1)
        self.assertEqual(jpo_markdown.count("**Equation 15.**"), 1)

    def test_ams_aies_fixture_preserves_inline_mathml_formulas(self) -> None:
        """rule: rule-preserve-inline-semantics-in-body-and-tables"""
        markdown, _ = _extract_fixture_markdown("10.1175/aies-d-23-0093.1")

        for noise in (
            "by predicting.",
            "Here,.",
            "denoted as,",
            "climatology:,",
            "(*μ*<sub>n</sub>,)",
            "νn",
            "αn",
            "βn",
            "γn",
            "<sub>n</sub><sub>,",
        ):
            self.assertNotIn(noise, markdown)

        self.assertRegex(markdown, r"by predicting \$(?:\\mathbf\{)?\\hat\{p\}")
        self.assertIn("Here, $S \\equiv", markdown)
        self.assertTrue(
            any(
                candidate in markdown
                for candidate in (
                    "denoted as $p(\\mu_{n}, \\sigma_{n}^{2}",
                    "denoted as $p{({\\mu_{n},\\sigma_{n}^{2}",
                )
            )
        )
        self.assertIn("(*μ*<sub>n</sub>, $\\sigma_{n}^{2}$)", markdown)
        self.assertIn("climatology: $\\text{BSS}", markdown)
        self.assertIn("*ν*<sub>n</sub> > 0", markdown)
        self.assertIn("*α*<sub>n,1</sub>", markdown)

    def test_ams_caption_inline_markup_is_preserved(self) -> None:
        """rule: rule-preserve-inline-semantics-in-body-and-tables"""
        cases = (
            (
                "10.1175/aies-d-23-0093.1",
                ("σ 2",),
                ("Gaussian (*μ*, *σ*<sup>2</sup>)",),
            ),
            (
                "10.1175/jpo-d-23-0234.1",
                ("γ 1", "A N", "ϕ ON", "ϕ 2", "</sub>(blue)"),
                (
                    "*γ*<sub>1</sub>",
                    "*A*<sub>N</sub>",
                    "*ϕ*<sub>ON</sub>",
                    (
                        "$\\overset{\\cdot}{q}(q, \\phi_{2})$ (blue)",
                        "$\\overset{˙}{q}{({q,\\phi_{2}})}$ (blue)",
                    ),
                    "*ϕ*<sub>OFF</sub> (blue)",
                ),
            ),
            (
                "10.1175/waf-d-24-0019.1",
                ("α 3 and β 3",),
                ("*α*<sub>3</sub> and *β*<sub>3</sub>",),
            ),
            (
                "10.1175/jtech-d-24-0028.1",
                ("m s −1", "m s -1"),
                ("m s<sup>−1</sup>", "W m<sup>−2</sup>"),
            ),
        )
        for doi, forbidden_values, expected_values in cases:
            with self.subTest(doi=doi):
                markdown, _ = _extract_fixture_markdown(doi)
                for forbidden in forbidden_values:
                    self.assertNotIn(forbidden, markdown)
                for expected in expected_values:
                    if isinstance(expected, tuple):
                        self.assertTrue(
                            any(candidate in markdown for candidate in expected)
                        )
                    else:
                        self.assertIn(expected, markdown)

    def test_ams_inline_renderer_preserves_body_subscripts_and_spacing(self) -> None:
        """rule: rule-preserve-inline-semantics-in-body-and-tables"""
        cases = (
            (
                "10.1175/waf-d-24-0019.1",
                "</sub>(see appendix",
                "*β*<sub>3</sub> (see appendix B)",
            ),
            (
                "10.1175/jamc-d-24-0048.1",
                "</sub>(low-level",
                "*T*<sub>b</sub> (low-level water vapor channel)",
            ),
            (
                "10.1175/mwr-d-24-0060.1",
                "</sub>(Kumjian",
                "*Z*<sub>DR</sub> (Kumjian et al. 2014)",
            ),
        )
        for doi, forbidden, expected in cases:
            with self.subTest(doi=doi):
                markdown, _ = _extract_fixture_markdown(doi)

                self.assertNotIn(forbidden, markdown)
                self.assertIn(expected, markdown)

    def test_ams_inline_spacing_repairs_prose_parentheses_conservatively(self) -> None:
        """
        rule: rule-ams-html-body-assets-formulas
        rule: rule-preserve-inline-semantics-in-body-and-tables
        """
        jpo_markdown, jpo_extraction = _extract_fixture_markdown(
            "10.1175/jpo-d-23-0234.1"
        )
        mwr_markdown, mwr_extraction = _extract_fixture_markdown(
            "10.1175/mwr-d-24-0060.1"
        )

        for forbidden in (
            "</sub>(i.e.",
            "</sub>(and therefore",
            "</sub>(Fig.",
            "</sub>(Reimel",
            "*qϕ* <sub>2</sub>",
        ):
            self.assertNotIn(forbidden, jpo_markdown)
            self.assertNotIn(forbidden, mwr_markdown)

        self.assertIn("*ϕ*<sub>3</sub> (i.e., *S*<sub>S</sub>)", jpo_markdown)
        self.assertIn("*qϕ*<sub>2</sub>", jpo_markdown)
        self.assertIn("*K*<sub>DP</sub> (and therefore lightning)", mwr_markdown)
        self.assertIn("*K*<sub>DP</sub> (Fig. 7b)", mwr_markdown)
        self.assertIn("*K*<sub>DP</sub> (Reimel and Kumjian 2021)", mwr_markdown)
        self.assertIn("10<sup>−5</sup>", mwr_markdown)
        self.assertIn("*K*<sub>DP</sub>", mwr_markdown)

        normalized = _ams_html._normalize_ams_markdown_text(
            "*Z*<sub>H</sub>(Montazeri et al. 2025) and *f*<sub>n</sub>(x)."
        )
        self.assertIn("*Z*<sub>H</sub> (Montazeri et al. 2025)", normalized)
        self.assertIn("*f*<sub>n</sub>(x)", normalized)

        for doi, markdown, extraction in (
            ("10.1175/jpo-d-23-0234.1", jpo_markdown, jpo_extraction),
            ("10.1175/mwr-d-24-0060.1", mwr_markdown, mwr_extraction),
        ):
            article = article_from_markdown(
                source="ams_html",
                metadata=_fixture_metadata(doi),
                doi=doi,
                markdown_text=markdown,
                section_hints=list(extraction.get("section_hints") or []),
            )
            rendered = _ams_html.normalize_article_model(article).to_ai_markdown(
                max_tokens="full_text"
            )
            for forbidden in (
                "</sub>(i.e.",
                "</sub>(and therefore",
                "</sub>(Fig.",
                "</sub>(Reimel",
                "*qϕ* <sub>2</sub>",
            ):
                self.assertNotIn(forbidden, rendered)

    def test_ams_data_availability_stays_before_appendix(self) -> None:
        """rule: rule-ams-html-body-assets-formulas"""
        for doi in ("10.1175/jpo-d-23-0234.1", "10.1175/waf-d-24-0019.1"):
            with self.subTest(doi=doi):
                markdown, extraction = _extract_fixture_markdown(doi)

                self.assertLess(
                    markdown.index("## Acknowledgments"),
                    markdown.index("## Data availability statement"),
                )
                self.assertLess(
                    markdown.index("## Data availability statement"),
                    markdown.index("## APPENDIX"),
                )
                article = article_from_markdown(
                    source="ams_html",
                    metadata=_fixture_metadata(doi),
                    doi=doi,
                    markdown_text=markdown,
                    section_hints=list(extraction.get("section_hints") or []),
                )
                rendered = article.to_ai_markdown(max_tokens="full_text")
                self.assertLess(
                    rendered.index("## Acknowledgments"),
                    rendered.index("## Data availability statement"),
                )
                self.assertLess(
                    rendered.index("## Data availability statement"),
                    rendered.index("## APPENDIX"),
                )

    def test_ams_normalize_markdown_moves_data_availability_before_appendix(
        self,
    ) -> None:
        """rule: rule-ams-html-body-assets-formulas"""
        markdown = "\n\n".join(
            [
                "# Title",
                "## Acknowledgments",
                "Thanks.",
                "## APPENDIX A",
                "Appendix figure and table text stays in place.",
                "## Data availability statement",
                "Data are archived.",
            ]
        )

        normalized = _ams_html.ams_normalize_markdown(markdown)

        self.assertLess(
            normalized.index("## Acknowledgments"),
            normalized.index("## Data availability statement"),
        )
        self.assertLess(
            normalized.index("## Data availability statement"),
            normalized.index("## APPENDIX A"),
        )
        self.assertLess(
            normalized.index("## APPENDIX A"),
            normalized.index("Appendix figure and table text stays in place."),
        )

    def test_ams_downloaded_inline_figure_and_table_assets_do_not_repeat_at_tail(
        self,
    ) -> None:
        """rule: rule-ams-html-body-assets-formulas"""
        doi = "10.1175/jamc-d-24-0048.1"
        markdown, extraction = _extract_fixture_markdown(doi)
        assets = _ams_html.scoped_asset_extractor(
            _fixture_html(doi),
            _fixture_source_url(doi),
            asset_profile="body",
        )
        downloaded_assets = _fake_downloaded_ams_assets(
            assets,
            basenames={
                "full-JAMC-D-24-0048.1-f2.jpg",
                "full-JAMC-D-24-0048.1-t1.jpg",
            },
        )

        article = article_from_markdown(
            source="ams_html",
            metadata=_fixture_metadata(doi),
            doi=doi,
            markdown_text=markdown,
            section_hints=list(extraction.get("section_hints") or []),
            assets=downloaded_assets,
        )
        rendered = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        self.assertIn("![Figure 2](/tmp/full-JAMC-D-24-0048.1-f2.jpg)", rendered)
        self.assertIn("![Table 1](/tmp/full-JAMC-D-24-0048.1-t1.jpg)", rendered)
        self.assertEqual(rendered.count("full-JAMC-D-24-0048.1-f2.jpg"), 1)
        self.assertEqual(rendered.count("full-JAMC-D-24-0048.1-t1.jpg"), 1)
        self.assertNotIn("\n## Figures\n", rendered)
        self.assertNotIn("\n## Tables\n", rendered)


if __name__ == "__main__":
    unittest.main()
