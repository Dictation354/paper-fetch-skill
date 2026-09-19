from __future__ import annotations
from functools import cache
import tempfile
import unittest
from unittest import mock
from paper_fetch.providers import (
    _ams_assets,
    _ams_authors,
    _ams_markdown,
    _ams_references,
    browser_runtime,
    browser_workflow,
)
from paper_fetch.providers.ams import AmsClient
from paper_fetch.quality.assets import build_asset_quality_summary
from paper_fetch.providers.atypon_browser_workflow.asset_scopes import (
    extract_browser_workflow_asset_html_scopes,
)
from paper_fetch.providers.atypon_browser_workflow.markdown import (
    extract_atypon_browser_workflow_markdown,
)
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi
from tests.support._browser_workflow_deps import install_browser_workflow_deps
from tests.support._atypon_browser_workflow_provider_support import (
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


@cache
def _extract_fixture_markdown(doi: str) -> tuple[str, dict[str, object]]:
    return extract_atypon_browser_workflow_markdown(
        _fixture_html(doi),
        _fixture_source_url(doi),
        "ams",
        metadata=_fixture_metadata(doi),
    )


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

    def test_ams_uses_browser_html_by_default_without_direct_http(self) -> None:
        html = (
            "<html><head><meta name='citation_author' content='Ada Example'></head>"
            "<body><div id='articleBody'><section id='bodymatter'><h2>Results</h2>"
            "<p>Body text.</p></section></div></body></html>"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "ams", AMS_DOI)
            transport = mock.Mock()
            client = AmsClient(transport=transport, env={})
            mocked_load_runtime = mock.Mock(return_value=runtime)
            mocked_ensure_runtime = mock.Mock()
            mocked_browser_html = mock.Mock(
                return_value=browser_runtime.BrowserFetchedHtml(
                    source_url=AMS_LANDING_URL,
                    final_url=AMS_LANDING_URL,
                    html=html,
                    response_status=200,
                    response_headers={"content-type": "text/html"},
                    title=AMS_TITLE,
                    summary="AMS article body",
                    browser_context_seed={
                        "browser_final_url": AMS_LANDING_URL,
                        "paper_fetch_html_fetcher": "camoufox",
                    },
                )
            )
            install_browser_workflow_deps(
                client,
                load_runtime_config=mocked_load_runtime,
                ensure_runtime_ready=mocked_ensure_runtime,
                fetch_html_with_browser=mocked_browser_html,
                extract_atypon_browser_workflow_markdown=mock.Mock(
                    return_value=(
                        f"# {AMS_TITLE}\n\n## Results\n\n" + ("Body text " * 120),
                        {"title": AMS_TITLE},
                    )
                ),
            )

            raw_payload = client.fetch_raw_fulltext(AMS_DOI, self._metadata())
            article = client.to_article_model(self._metadata(), raw_payload)

        self.assertEqual(_payload_route(raw_payload), "html")
        self.assertEqual(raw_payload.content.fetcher, "camoufox")
        self.assertEqual(article.source, "ams_html")
        self.assertIn("fulltext:ams_html_ok", article.quality.source_trail)
        mocked_load_runtime.assert_called_once_with(
            {},
            provider="ams",
            doi=AMS_DOI,
        )
        mocked_ensure_runtime.assert_called_once_with(runtime)
        mocked_browser_html.assert_called_once()
        self.assertEqual(
            list(mocked_browser_html.call_args.args[0]),
            [AMS_LANDING_URL],
        )
        self.assertFalse(
            any(
                candidate == AMS_XML_URL or "/doc/" in candidate
                for candidate in mocked_browser_html.call_args.args[0]
            )
        )
        transport.request.assert_not_called()

    def test_ams_browser_html_failure_uses_seeded_browser_pdf(self) -> None:
        seed = {
            "browser_cookies": [
                {
                    "name": "aws-waf-token",
                    "value": "saved",
                    "domain": ".ametsoc.org",
                    "path": "/",
                }
            ],
            "browser_final_url": AMS_LANDING_URL,
        }
        pdf_payload = _typed_raw_payload(
            provider="ams",
            source_url=AMS_PDF_URL,
            content_type="application/pdf",
            body=fulltext_pdf_bytes(),
            route="pdf_fallback",
            markdown_text=f"# {AMS_TITLE}\n\n## Results\n\n" + ("Body text " * 120),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "ams", AMS_DOI)
            client = AmsClient(transport=mock.Mock(), env={})
            mocked_pdf = mock.Mock(return_value=pdf_payload)
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mock.Mock(
                    side_effect=browser_runtime.BrowserRuntimeFailure(
                        "cloudflare_challenge",
                        "AWS WAF verification page remained active.",
                        browser_context_seed=seed,
                    )
                ),
                fetch_seeded_browser_pdf_payload=mocked_pdf,
            )

            raw_payload = client.fetch_raw_fulltext(AMS_DOI, self._metadata())
            article = client.to_article_model(self._metadata(), raw_payload)

        mocked_pdf.assert_called_once()
        self.assertEqual(mocked_pdf.call_args.kwargs["provider"], "ams")
        self.assertEqual(
            mocked_pdf.call_args.kwargs["browser_context_seed"],
            seed,
        )
        self.assertEqual(
            mocked_pdf.call_args.kwargs["html_failure_reason"],
            "cloudflare_challenge",
        )
        self.assertIn(AMS_PDF_URL, mocked_pdf.call_args.kwargs["pdf_candidates"])
        self.assertEqual(_payload_route(raw_payload), "pdf_fallback")
        self.assertEqual(article.source, "ams_pdf")
        self.assertIn(
            "fulltext:ams_pdf_fallback_ok", _payload_source_trail(raw_payload)
        )

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

    def test_ams_html_extraction_failure_seeds_browser_pdf_from_citation_url(
        self,
    ) -> None:
        citation_pdf_url = (
            "https://journals.ametsoc.org/downloadpdf/journals/clim/38/1/AMS-TEST.1.xml"
        )
        html = f"""
        <html><head><meta name="citation_pdf_url" content="{citation_pdf_url}"></head>
        <body><article><section role="doc-abstract"><p>Abstract only.</p></section></article></body></html>
        """
        browser_html = browser_runtime.BrowserFetchedHtml(
            source_url=AMS_LANDING_URL,
            final_url=AMS_LANDING_URL,
            html=html,
            response_status=200,
            response_headers={"content-type": "text/html"},
            title=AMS_TITLE,
            summary="Abstract only.",
            browser_context_seed={"browser_final_url": AMS_LANDING_URL},
        )
        pdf_payload = _typed_raw_payload(
            provider="ams",
            source_url=citation_pdf_url,
            content_type="application/pdf",
            body=fulltext_pdf_bytes(),
            route="pdf_fallback",
            markdown_text=f"# {AMS_TITLE}\n\n## Results\n\n" + ("Body text " * 120),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "ams", AMS_DOI)
            client = AmsClient(transport=mock.Mock(), env={})
            mocked_pdf = mock.Mock(return_value=pdf_payload)
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mock.Mock(return_value=browser_html),
                extract_atypon_browser_workflow_markdown=mock.Mock(
                    side_effect=browser_workflow.HtmlExtractionFailure(
                        "abstract_only", "Abstract only."
                    )
                ),
                fetch_seeded_browser_pdf_payload=mocked_pdf,
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
        mocked_pdf.assert_called_once()
        self.assertEqual(
            mocked_pdf.call_args.kwargs["pdf_candidates"][0],
            citation_pdf_url,
        )

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

        assets = _ams_assets.scoped_asset_extractor(
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

        assets = _ams_assets.scoped_asset_extractor(
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
        asset_summary = build_asset_quality_summary(
            assets,
            asset_profile="none",
            archive_enabled=False,
        )
        self.assertEqual(asset_summary.by_kind["figure"].total, 1)
        self.assertEqual(asset_summary.by_kind["formula"].total, 1)

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

        assets = _ams_assets.scoped_asset_extractor(
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
        assets = _ams_assets.scoped_asset_extractor(
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

        assets = _ams_assets.scoped_asset_extractor(
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
            _ams_authors.extract_authors(
                """
                <html><head>
                  <meta name="dc.Creator" content="Ada Example">
                </head><body></body></html>
                """
            ),
            ["Ada Example"],
        )
        self.assertEqual(
            _ams_authors.extract_authors(
                """
                <html><body>
                  <div class="authors"><a>Grace Fallback</a></div>
                </body></html>
                """
            ),
            ["Grace Fallback"],
        )

        references = _ams_references.extract_references(
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

    def test_ams_normalize_markdown_moves_data_availability_before_appendix(
        self,
    ) -> None:
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

        normalized = _ams_markdown.ams_normalize_markdown(markdown)

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


if __name__ == "__main__":
    unittest.main()
