from __future__ import annotations

from dataclasses import replace
from functools import cache
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from paper_fetch.artifacts import ArtifactStore
from paper_fetch.extraction.html.signals import HtmlExtractionFailure
from paper_fetch.http import RequestFailure
from paper_fetch.models import article_from_markdown
from paper_fetch.models.markdown import iter_markdown_images
from paper_fetch.providers import _mdpi_html, browser_runtime
from paper_fetch.providers.mdpi import MdpiClient
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi
from tests.unit._browser_workflow_deps import install_browser_workflow_deps
from tests.unit._paper_fetch_support import fulltext_pdf_bytes

from ._atypon_browser_workflow_provider_support import (
    AtyponBrowserWorkflowProviderTestCase,
    AssetTransport,
    _payload_route,
    _typed_raw_payload,
    png_header,
)


MDPI_STRUCTURE_DOI = "10.3390/membranes15030093"
MDPI_TABLE_DOI = "10.3390/su12072826"
MDPI_FORMULA_DOI = "10.3390/math11030657"
MDPI_FIGURE_DOI = "10.3390/rs16010010"
MDPI_SUPPLEMENTARY_DOI = "10.3390/s23010001"
MDPI_REFERENCES_DOI = "10.3390/w15040758"
MDPI_PDF_FALLBACK_DOI = "10.3390/en16186655"
MDPI_EXTRA_STRUCTURE_DOIS = (
    "10.3390/foods10081757",
    "10.3390/ijerph18094484",
)
MDPI_HTML_DOIS = (
    MDPI_STRUCTURE_DOI,
    MDPI_TABLE_DOI,
    MDPI_FORMULA_DOI,
    MDPI_FIGURE_DOI,
    MDPI_SUPPLEMENTARY_DOI,
    MDPI_REFERENCES_DOI,
    *MDPI_EXTRA_STRUCTURE_DOIS,
)
MDPI_LANDING_URL = "https://www.mdpi.com/2077-0375/15/3/93"
MDPI_PDF_URL = "https://www.mdpi.com/2077-0375/15/3/93/pdf"
MDPI_XML_URL = "https://www.mdpi.com/2077-0375/15/3/93/xml"
MDPI_TITLE = (
    "Simulation of Carbon Dioxide Absorption in a Hollow Fiber Membrane Contactor "
    "Under Non-Isothermal Conditions"
)


def _fixture_metadata(doi: str) -> dict[str, object]:
    sample = golden_criteria_sample_for_doi(doi)
    return {
        "doi": doi,
        "title": sample.get("title"),
        "landing_page_url": sample.get("source_url") or sample.get("landing_url"),
    }


def _fixture_source_url(doi: str) -> str:
    sample = golden_criteria_sample_for_doi(doi)
    return str(sample.get("source_url") or sample.get("landing_url") or "")


def _fixture_html(doi: str) -> str:
    return golden_criteria_asset(doi, "original.html").read_text(
        encoding="utf-8",
        errors="ignore",
    )


def _fixture_html_payload(doi: str):
    html = _fixture_html(doi)
    source_url = _fixture_source_url(doi)
    return _typed_raw_payload(
        provider="mdpi",
        source_url=source_url,
        content_type="text/html",
        body=html.encode("utf-8"),
        route="html",
        source_trail=["fulltext:mdpi_html_ok"],
    )


def _markdown_image_alts(markdown: str) -> list[str]:
    return [image.alt for image in iter_markdown_images(markdown)]


def _inline_wrapper_regression_html() -> str:
    filler = " ".join(["body words for MDPI extraction threshold"] * 120)
    display_formula = """
<div class="html-disp-formula-info" id="FD1-inline-wrapper">
  <div class="f">
    <math display="block"><semantics><mrow><mi>E</mi><mo>=</mo><mi>m</mi></mrow></semantics></math>
  </div>
  <div class="l"><label>(1)</label></div>
</div>
"""
    return f"""
<html>
  <head>
    <meta name="citation_title" content="LESS Spark Ignition Engine: An Innovative Alternative to the Crankshaft Mechanism">
  </head>
  <body>
    <article>
      <div id="article-contents">
        <section class="html-abstract">
          <h2>Abstract</h2>
          <div class="html-p">Abstract text.</div>
        </section>
        <section class="html-body">
          <h2 data-nested="1">1. Inline Wrapper Regression</h2>
          <div class="html-p">{filler}</div>
          <div class="html-p">
            A display equation must remain a block:{display_formula}
            where <span class="html-italic">u</span>′ is the instantaneous velocity fluctuation,
            Γ is the efficiency function of the turbulent flow on the flame strain,
            <span class="html-bold">C</span> is a modelling constant,
            <span class="html-italic">Sc</span> is the Schmidt number, r<sub>bg</sub> is the current mean flame radius
            and <span class="html-italic">g</span> is a function accounting for the laminar-turbulent transition of the flame front.
          </div>
          <div class="html-p">
            where <div><span class="html-italic">u′</span></div> is the instantaneous velocity fluctuation,
            Γ is the efficiency function of the turbulent flow on the flame strain,
            <div><span class="html-bold">C</span></div> is a modelling constant,
            <div>Sc</div> is the Schmidt number, r<sub>bg</sub> is the current mean flame radius
            and <div>g</div> is a function accounting for the laminar-turbulent transition of the flame front.
          </div>
          <div class="html-p">
            where <div><span class="html-italic">L</span></div> is the distance between the piston and the cylinder head,
            and <div>ω<sub>eng</sub></div> is the engine speed in rad.s<sup>−1</sup>.
          </div>
        </section>
      </div>
    </article>
  </body>
</html>
"""


@cache
def _extract_fixture_markdown(doi: str) -> tuple[str, dict[str, object]]:
    return _mdpi_html.extract_markdown(
        _fixture_html(doi),
        _fixture_source_url(doi),
        metadata=_fixture_metadata(doi),
    )


class MdpiProviderTests(AtyponBrowserWorkflowProviderTestCase):
    def _metadata(self) -> dict[str, object]:
        return {
            "doi": MDPI_STRUCTURE_DOI,
            "title": MDPI_TITLE,
            "landing_page_url": MDPI_LANDING_URL,
            "fulltext_links": [
                {"url": MDPI_XML_URL, "content_type": "application/xml"},
                {"url": MDPI_PDF_URL, "content_type": "application/pdf"},
            ],
        }

    def test_mdpi_without_cdp_endpoint_uses_auto_managed_browser_runtime(self) -> None:
        client = MdpiClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = replace(
                self._runtime_config(tmpdir, "mdpi", MDPI_STRUCTURE_DOI),
                cdp_endpoint=None,
            )
            mocked_html = mock.Mock(
                return_value=browser_runtime.BrowserFetchedHtml(
                    source_url=MDPI_LANDING_URL,
                    final_url=MDPI_LANDING_URL,
                    html=(
                        "<html><head><meta name='citation_author' content='Ada Example'>"
                        f"<meta name='citation_title' content='{MDPI_TITLE}'></head>"
                        "<body><article><div id='article-contents'>"
                        "<section class='html-abstract'><h2>Abstract</h2><p>Abstract text.</p></section>"
                        "<section><h2>1. Introduction</h2>"
                        + (
                            "<p>Body text with enough words for MDPI extraction.</p>"
                            * 80
                        )
                        + "</section></div></article></body></html>"
                    ),
                    response_status=200,
                    response_headers={"content-type": "text/html"},
                    title=MDPI_TITLE,
                    summary="MDPI full text",
                    browser_context_seed={},
                )
            )
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mocked_html,
            )

            raw_payload = client.fetch_raw_fulltext(
                MDPI_STRUCTURE_DOI, self._metadata()
            )

        self.assertEqual(_payload_route(raw_payload), "html")
        self.assertIsNone(mocked_html.call_args.kwargs["config"].cdp_endpoint)

    def test_mdpi_html_route_uses_browser_landing_page_and_ignores_xml_url(
        self,
    ) -> None:
        client = MdpiClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "mdpi", MDPI_STRUCTURE_DOI)
            mocked_html = mock.Mock(
                return_value=browser_runtime.BrowserFetchedHtml(
                    source_url=MDPI_LANDING_URL,
                    final_url=MDPI_LANDING_URL,
                    html=(
                        "<html><head><meta name='citation_author' content='Ada Example'>"
                        f"<meta name='citation_title' content='{MDPI_TITLE}'></head>"
                        "<body><article><div id='article-contents'>"
                        "<section class='html-abstract'><h2>Abstract</h2><p>Abstract text.</p></section>"
                        "<section><h2>1. Introduction</h2>"
                        + (
                            "<p>Body text with enough words for MDPI extraction.</p>"
                            * 80
                        )
                        + "</section></div></article></body></html>"
                    ),
                    response_status=200,
                    response_headers={"content-type": "text/html"},
                    title=MDPI_TITLE,
                    summary="MDPI full text",
                    browser_context_seed={},
                )
            )
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mocked_html,
            )
            raw_payload = client.fetch_raw_fulltext(
                MDPI_STRUCTURE_DOI, self._metadata()
            )
            article = client.to_article_model(self._metadata(), raw_payload)

        attempted_html = list(mocked_html.call_args.args[0])
        self.assertEqual(
            attempted_html,
            [MDPI_LANDING_URL, f"https://doi.org/{MDPI_STRUCTURE_DOI}"],
        )
        self.assertNotIn(MDPI_XML_URL, attempted_html)
        self.assertEqual(_payload_route(raw_payload), "html")
        self.assertEqual(article.source, "mdpi_html")

    def test_mdpi_empty_intermediate_candidate_retries_next_html_before_pdf(
        self,
    ) -> None:
        client = MdpiClient(transport=None, env={})
        resolver_url = f"https://doi.org/{MDPI_STRUCTURE_DOI}"
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "mdpi", MDPI_STRUCTURE_DOI)
            mocked_html = mock.Mock(
                side_effect=[
                    browser_runtime.BrowserFetchedHtml(
                        source_url=MDPI_LANDING_URL,
                        final_url=MDPI_LANDING_URL,
                        html="<html><head><title>Loading</title></head></html>",
                        response_status=200,
                        response_headers={"content-type": "text/html"},
                        title="Loading",
                        summary="Loading",
                        browser_context_seed={},
                    ),
                    browser_runtime.BrowserFetchedHtml(
                        source_url=resolver_url,
                        final_url=MDPI_LANDING_URL,
                        html=(
                            "<html><body><article><h2>Results</h2>"
                            + ("<p>Complete MDPI body text.</p>" * 100)
                            + "</article></body></html>"
                        ),
                        response_status=200,
                        response_headers={"content-type": "text/html"},
                        title=MDPI_TITLE,
                        summary="Complete",
                        browser_context_seed={},
                    ),
                ]
            )
            mocked_extractor = mock.Mock(
                side_effect=[
                    HtmlExtractionFailure(
                        "article_container_not_found",
                        "The delayed MDPI body is not ready.",
                    ),
                    (
                        f"# {MDPI_TITLE}\n\n## Results\n\n" + ("Body text " * 120),
                        {"title": MDPI_TITLE},
                    ),
                ]
            )
            mocked_pdf = mock.Mock()
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mocked_html,
                extract_atypon_browser_workflow_markdown=mocked_extractor,
                fetch_pdf_with_browser=mocked_pdf,
            )

            raw_payload = client.fetch_raw_fulltext(
                MDPI_STRUCTURE_DOI,
                self._metadata(),
            )

        self.assertEqual(mocked_html.call_count, 2)
        self.assertEqual(
            mocked_html.call_args_list[0].args[0],
            [MDPI_LANDING_URL, resolver_url],
        )
        self.assertEqual(
            mocked_html.call_args_list[1].args[0],
            [resolver_url, MDPI_LANDING_URL],
        )
        mocked_pdf.assert_not_called()
        self.assertEqual(_payload_route(raw_payload), "html")

    def test_mdpi_pdf_fallback_uses_article_pdf_candidate(self) -> None:
        client = MdpiClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "mdpi", MDPI_STRUCTURE_DOI)
            mocked_pdf = mock.Mock(
                return_value=mock.Mock(
                    source_url=MDPI_PDF_URL,
                    final_url=MDPI_PDF_URL,
                    pdf_bytes=fulltext_pdf_bytes(),
                    markdown_text=f"# {MDPI_TITLE}\n\n## Results\n\n"
                    + ("Body text " * 120),
                    suggested_filename="mdpi.pdf",
                )
            )
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mock.Mock(
                    side_effect=browser_runtime.BrowserRuntimeFailure(
                        "insufficient_body",
                        "MDPI HTML did not expose enough body.",
                    )
                ),
                fetch_pdf_with_browser=mocked_pdf,
            )
            raw_payload = client.fetch_raw_fulltext(
                MDPI_STRUCTURE_DOI, self._metadata()
            )
            article = client.to_article_model(self._metadata(), raw_payload)

        self.assertIn(MDPI_PDF_URL, list(mocked_pdf.call_args.args[0]))
        self.assertEqual(_payload_route(raw_payload), "pdf_fallback")
        self.assertEqual(article.source, "mdpi_pdf")

    def test_mdpi_candidates_derive_article_url_from_known_doi(self) -> None:
        client = MdpiClient(transport=None, env={})
        metadata = {
            "doi": "10.3390/rs18101673",
            "landing_page_url": "https://doi.org/10.3390/rs18101673",
        }

        self.assertEqual(
            client.html_candidates("10.3390/rs18101673", metadata),
            [
                "https://www.mdpi.com/2072-4292/18/10/1673",
                "https://doi.org/10.3390/rs18101673",
            ],
        )
        self.assertIn(
            "https://www.mdpi.com/2072-4292/18/10/1673/pdf",
            client.pdf_candidates("10.3390/rs18101673", metadata),
        )

    def test_mdpi_structure_fixture_markdown(self) -> None:
        """rule: rule-mdpi-body-semantics-chrome-removal"""
        markdown, extraction = _extract_fixture_markdown(MDPI_STRUCTURE_DOI)

        self.assertIn("# Simulation of Carbon Dioxide Absorption", markdown)
        self.assertIn("## Abstract", markdown)
        self.assertIn("1. Introduction", markdown)
        self.assertRegex(markdown, r"(?m)^## 1\. Introduction")
        self.assertGreaterEqual(len(extraction["extracted_authors"]), 5)
        self.assertNotIn("Browse Figures", markdown)

    def test_mdpi_table_fixture_markdown(self) -> None:
        """rule: rule-mdpi-display-object-anchoring-dedupe"""
        markdown, _ = _extract_fixture_markdown(MDPI_TABLE_DOI)

        self.assertIn("Table 1", markdown)
        self.assertIn("ANP-Fuzzy", markdown)
        self.assertRegex(
            markdown,
            r"(?m)^\|\s*Scale\s*\|\s*Meaning Description\s*\|$",
        )
        self.assertEqual(markdown.count("1–9 Scaling method in judgment matrix."), 1)
        self.assertNotIn("\n\nTable 1.\n\n1–9 Scaling method", markdown)
        self.assertNotIn("Google Scholar", markdown)

    def test_mdpi_formula_fixture_markdown(self) -> None:
        """rule: rule-mdpi-formula-inline-display-rendering"""
        markdown, _ = _extract_fixture_markdown(MDPI_FORMULA_DOI)

        self.assertIn("Equation (1)", markdown)
        self.assertIn("$$", markdown)
        self.assertRegex(markdown, r"(?s)\$\$\n.*(?:\\sum|\\frac|_\{[^}]+\})")
        self.assertRegex(markdown, r"(?m)^\(1\)$")
        self.assertRegex(
            markdown,
            r"The random error term \$[^$\n]+\$ is mainly caused",
        )
        self.assertNotIn("Yi=fxi,βevi−ui", markdown)
        self.assertNotIn("lnYit=β0+∑βjlnxit+vit−uit", markdown)
        self.assertIn("Stochastic Frontier Production Model", markdown)
        self.assertNotIn("Download PDF", markdown)

    def test_mdpi_figure_fixture_markdown_and_assets(self) -> None:
        """rule: rule-mdpi-display-object-anchoring-dedupe"""
        markdown, _ = _extract_fixture_markdown(MDPI_FIGURE_DOI)
        assets = _mdpi_html.extract_scoped_html_assets(
            _fixture_html(MDPI_FIGURE_DOI),
            _fixture_source_url(MDPI_FIGURE_DOI),
            asset_profile="body",
        )

        self.assertIn("Figure 1", markdown)
        self.assertRegex(
            markdown,
            r"!\[Figure 1\]\(https://www\.mdpi\.com/.+remotesensing-16-00010-g001\.png\)",
        )
        self.assertLess(markdown.index("![Figure 1]("), markdown.index("**Figure 1.**"))
        self.assertTrue(any(asset.get("kind") == "figure" for asset in assets))
        self.assertNotIn("Article Metrics", markdown)

    def test_mdpi_markdown_image_alts_are_short_and_balanced(self) -> None:
        """rule: rule-mdpi-display-object-anchoring-dedupe
        """
        short_alt_pattern = (
            r"^(?:Figure [A-Za-z]?\d+[A-Za-z]?(?:\.\d+[A-Za-z]?)*|"
            r"Table [A-Za-z]?\d+[A-Za-z]?(?:\.\d+[A-Za-z]?)*|Formula|Image)$"
        )
        for doi in MDPI_HTML_DOIS:
            with self.subTest(doi=doi):
                markdown, _ = _extract_fixture_markdown(doi)
                for alt in _markdown_image_alts(markdown):
                    self.assertRegex(alt, short_alt_pattern)
                    self.assertNotIn("[", alt)
                    self.assertNotIn("]", alt)
                self.assertNotIn("[AO10]", "\n".join(_markdown_image_alts(markdown)))

    def test_mdpi_display_objects_are_anchored_and_deduplicated(self) -> None:
        """rule: rule-mdpi-display-object-anchoring-dedupe"""
        figure_markdown, _ = _extract_fixture_markdown(MDPI_FIGURE_DOI)
        first_figure_ref = figure_markdown.index(
            "Figure 1 illustrates the principle of satellite–earth TWSTT."
        )
        first_figure_image = figure_markdown.index("![Figure 1](")

        self.assertGreater(first_figure_image, first_figure_ref)
        self.assertLess(first_figure_image - first_figure_ref, 500)
        self.assertEqual(figure_markdown.count("The principle of TWSTT."), 1)
        self.assertNotIn("\n\nFigure 1.\n\nThe principle of TWSTT.", figure_markdown)

        table_markdown, _ = _extract_fixture_markdown(MDPI_TABLE_DOI)
        first_table_ref = table_markdown.index("Table 1) Thus the judgment matrix")
        first_table_block = table_markdown.index("**Table 1.**")

        self.assertGreater(first_table_block, first_table_ref)
        self.assertLess(first_table_block - first_table_ref, 1200)
        self.assertLess(first_table_block, table_markdown.index("### 2.2."))
        self.assertEqual(
            table_markdown.count("1–9 Scaling method in judgment matrix."), 1
        )

    def test_mdpi_abstract_keywords_do_not_render_as_abstract_body(self) -> None:
        """rule: rule-mdpi-body-semantics-chrome-removal"""
        for doi in MDPI_HTML_DOIS:
            with self.subTest(doi=doi):
                markdown, extraction = _extract_fixture_markdown(doi)
                abstract_text = str(extraction["abstract_text"] or "")

                self.assertNotIn("Keywords:", abstract_text)
                self.assertNotIn("Keywords:", markdown)
                self.assertNotIn("\n## Keywords", markdown)
                self.assertGreater(len(extraction["keywords"]), 0)

        client = MdpiClient(transport=None, env={})
        article = client.to_article_model(
            _fixture_metadata(MDPI_REFERENCES_DOI),
            _fixture_html_payload(MDPI_REFERENCES_DOI),
        )

        self.assertIn("acid orange 10", article.metadata.keywords)
        self.assertNotIn("Keywords:", article.metadata.abstract or "")

    def test_mdpi_formula_fallbacks_do_not_fragment_or_emit_unavailable(self) -> None:
        """rule: rule-mdpi-formula-inline-display-rendering"""
        for doi in (
            MDPI_REFERENCES_DOI,
            "10.3390/ijerph18094484",
            MDPI_SUPPLEMENTARY_DOI,
        ):
            with self.subTest(doi=doi):
                markdown, _ = _extract_fixture_markdown(doi)

                self.assertNotIn("[Formula unavailable]", markdown)

        water_markdown, _ = _extract_fixture_markdown(MDPI_REFERENCES_DOI)
        self.assertNotRegex(water_markdown, r"(?m)^IO$")
        self.assertNotRegex(water_markdown, r"(?m)^<sub>4</sub>$")
        self.assertNotRegex(water_markdown, r"(?m)^<sup>−</sup>$")

    def test_mdpi_paragraph_inline_wrappers_do_not_fragment_variable_explanations(
        self,
    ) -> None:
        """rule: rule-mdpi-formula-inline-display-rendering"""
        markdown, _ = _mdpi_html.extract_markdown(
            _inline_wrapper_regression_html(),
            "https://www.mdpi.com/1996-1073/16/18/6655",
            metadata={
                "doi": MDPI_PDF_FALLBACK_DOI,
                "title": "LESS Spark Ignition Engine: An Innovative Alternative to the Crankshaft Mechanism",
            },
        )

        for fragment in (
            "where L is the distance between the piston and the cylinder head",
            "where u′ is the instantaneous velocity fluctuation",
            "C is a modelling constant",
            "Sc is the Schmidt number",
            "ω<sub>eng</sub> is the engine speed in rad.s<sup>−1</sup>.",
        ):
            self.assertIn(fragment, markdown)
        for pattern in (
            r"(?m)^L$",
            r"(?m)^C$",
            r"(?m)^Sc$",
            r"(?m)^g$",
            r"(?m)^<sup>−1</sup>\.$",
        ):
            self.assertNotRegex(markdown, pattern)
        self.assertIn("$$", markdown)
        self.assertRegex(markdown, r"(?m)^\(1\)$")

    def test_mdpi_article_marks_inline_figure_assets_without_duplicate_tail_block(
        self,
    ) -> None:
        """rule: rule-mdpi-display-object-anchoring-dedupe"""
        figure_url = "https://www.mdpi.com/images/figure-4.png"
        local_path = "/tmp/paper-fetch-mdpi/body_assets/figure-4.png"
        article = article_from_markdown(
            source="mdpi_html",
            metadata={"title": "MDPI Inline Figure"},
            doi="10.3390/example",
            markdown_text="\n".join(
                [
                    "# MDPI Inline Figure",
                    "",
                    "## Results",
                    "",
                    "Body text " * 120,
                    "",
                    f"![Figure 4. Effect of [AO10] concentration]({figure_url})",
                    "",
                    "**Figure 4.** Effect of [AO10] concentration.",
                ]
            ),
            assets=[
                {
                    "kind": "figure",
                    "heading": "Figure 4. Effect of [AO10] concentration",
                    "caption": "Effect of [AO10] concentration.",
                    "url": figure_url,
                    "path": local_path,
                    "section": "body",
                }
            ],
        )

        markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        self.assertEqual(article.assets[0].render_state, "inline")
        self.assertEqual(markdown.count(local_path), 1)
        self.assertIn(f"![Figure 4]({local_path})", markdown)
        self.assertNotIn("![Figure 4. Effect", markdown)
        self.assertNotIn("\n## Figures\n", markdown)

    def test_mdpi_supplementary_fixture_markdown_and_all_assets(self) -> None:
        """rule: rule-mdpi-body-semantics-chrome-removal"""
        markdown, _ = _extract_fixture_markdown(MDPI_SUPPLEMENTARY_DOI)
        body_assets = _mdpi_html.extract_scoped_html_assets(
            _fixture_html(MDPI_SUPPLEMENTARY_DOI),
            _fixture_source_url(MDPI_SUPPLEMENTARY_DOI),
            asset_profile="body",
        )
        all_assets = _mdpi_html.extract_scoped_html_assets(
            _fixture_html(MDPI_SUPPLEMENTARY_DOI),
            _fixture_source_url(MDPI_SUPPLEMENTARY_DOI),
            asset_profile="all",
        )

        self.assertIn("Supplementary Spreadsheet", markdown)
        self.assertFalse(
            any(asset.get("kind") == "supplementary" for asset in body_assets)
        )
        self.assertTrue(
            any(asset.get("kind") == "supplementary" for asset in all_assets)
        )
        self.assertNotIn("Download Supplementary Material", markdown)

    def test_mdpi_references_fixture_markdown(self) -> None:
        """rule: rule-mdpi-references-numbering-link-cleanup"""
        markdown, extraction = _extract_fixture_markdown(MDPI_REFERENCES_DOI)
        references = extraction["references"]
        article = article_from_markdown(
            source="mdpi_html",
            metadata={
                **_fixture_metadata(MDPI_REFERENCES_DOI),
                "references": references,
            },
            doi=MDPI_REFERENCES_DOI,
            markdown_text=markdown,
        )
        rendered_markdown = article.to_ai_markdown(max_tokens="full_text")

        self.assertIn("Acid Orange 10", markdown)
        self.assertGreaterEqual(len(references), 20)
        self.assertTrue(
            str(references[0].get("raw") or "").startswith("1. Kumar, P.;"),
        )
        self.assertRegex(rendered_markdown, r"(?m)^1\. Kumar, P\.; Govindaraju")
        self.assertNotRegex(rendered_markdown, r"(?m)^- Kumar, P\.; Govindaraju")
        self.assertNotIn("CrossRef", rendered_markdown)

    def test_mdpi_reference_ui_tokens_are_removed_from_markdown_and_raw_references(
        self,
    ) -> None:
        """rule: rule-mdpi-references-numbering-link-cleanup"""
        noise_tokens = ("Google Scholar", "CrossRef", "PubMed", "Green Version")

        for doi in MDPI_HTML_DOIS:
            with self.subTest(doi=doi):
                markdown, extraction = _extract_fixture_markdown(doi)
                reference_text = "\n".join(
                    str(reference.get("raw") or "")
                    for reference in extraction["references"]
                )

                for token in noise_tokens:
                    self.assertNotIn(f"[ {token} ]", markdown)
                    self.assertNotIn(f"[ {token} ]", reference_text)
                    self.assertNotIn(token, reference_text)

    def test_mdpi_markdown_removes_abstract_colon_and_preserves_heading_levels(
        self,
    ) -> None:
        """rule: rule-mdpi-body-semantics-chrome-removal"""
        for doi in MDPI_HTML_DOIS:
            with self.subTest(doi=doi):
                markdown, _ = _extract_fixture_markdown(doi)

                self.assertNotIn("## Abstract\n\n:", markdown)
                self.assertNotRegex(markdown, r"(?m)^:\s*$")
                self.assertNotRegex(markdown, r"(?m)^#### \d+\.\d+\. ")

    def test_mdpi_download_related_assets_uses_browser_image_fetcher_after_http_403(
        self,
    ) -> None:
        """asset-download-contract: provider=mdpi"""

        figure_url = "https://www.mdpi.com/images/f1.png"
        html = f"""
<html><body><article><div id="article-contents">
  <section class="html-body">
    <div class="html-fig-wrap" id="f1">
      <img src="{figure_url}" />
      <div class="html-fig_description">Figure 1. Caption.</div>
    </div>
  </section>
</div></article></body></html>
"""
        transport = AssetTransport(
            {
                ("GET", figure_url): RequestFailure(
                    403,
                    "HTTP 403 for MDPI image",
                    body=b"<html>Forbidden</html>",
                    headers={"content-type": "text/html"},
                    url=figure_url,
                )
            }
        )
        client = MdpiClient(transport=transport, env={})
        shared_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": png_header(640, 480),
                "url": figure_url,
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "mdpi", MDPI_STRUCTURE_DOI)
            raw_payload = _typed_raw_payload(
                provider="mdpi",
                source_url=MDPI_LANDING_URL,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=f"# {MDPI_TITLE}\n\n## Results\n\n"
                + ("Body text " * 120),
                browser_context_seed={},
            )
            mocked_builder = mock.Mock(return_value=shared_fetcher)
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                _build_shared_browser_image_fetcher=mocked_builder,
            )

            result = client.download_related_assets(
                MDPI_STRUCTURE_DOI,
                self._metadata(),
                raw_payload,
                tmpdir,
                asset_profile="body",
            )
            saved_bytes = Path(result["assets"][0]["path"]).read_bytes()

        mocked_builder.assert_called_once()
        shared_fetcher.assert_called_once()
        self.assertEqual(shared_fetcher.call_args.args[0], figure_url)
        self.assertEqual(
            [call["url"] for call in transport.calls],
            [figure_url],
        )
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["assets"][0]["download_tier"], "preview")
        self.assertEqual(
            result["assets"][0]["downloaded_bytes"], len(png_header(640, 480))
        )
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(saved_bytes, png_header(640, 480))

    def test_mdpi_all_asset_failures_are_reported_by_artifacts(self) -> None:
        client = MdpiClient(transport=None, env={})
        failure = {
            "kind": "figure",
            "heading": "Figure 1",
            "source_url": "https://www.mdpi.com/images/f1.png",
            "reason": "cloudflare_challenge",
        }
        raw_payload = _typed_raw_payload(
            provider="mdpi",
            source_url=MDPI_LANDING_URL,
            content_type="text/html",
            body=b"<html></html>",
            route="html",
            markdown_text=f"# {MDPI_TITLE}\n\n## Results\n\n" + ("Body text " * 120),
        )
        article = client.to_article_model(
            self._metadata(),
            raw_payload,
            asset_failures=[failure],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            warnings = list(article.quality.warnings)
            ArtifactStore.from_download_dir(Path(tmpdir)).apply_provider_artifacts(
                provider_name="mdpi",
                artifacts=client.describe_artifacts(
                    raw_payload,
                    asset_failures=[failure],
                ),
                asset_profile="body",
                warnings=warnings,
                source_trail=[],
            )

        asset_warnings = [
            warning for warning in warnings if "related assets" in warning
        ]
        self.assertEqual(
            asset_warnings,
            ["MDPI related assets could not be downloaded (1 failed)."],
        )

    def test_mdpi_extra_real_html_fixtures_extract_fulltext(self) -> None:
        for doi in MDPI_EXTRA_STRUCTURE_DOIS:
            with self.subTest(doi=doi):
                markdown, extraction = _extract_fixture_markdown(doi)

                self.assertIn("## Abstract", markdown)
                self.assertGreater(len(markdown), 5000)
                self.assertGreaterEqual(len(extraction["section_hints"]), 5)
                self.assertNotIn("Submit to this Journal", markdown)

    def test_mdpi_html_fixtures_to_article_model_are_fulltext(self) -> None:
        client = MdpiClient(transport=None, env={})

        for doi in MDPI_HTML_DOIS:
            with self.subTest(doi=doi):
                article = client.to_article_model(
                    _fixture_metadata(doi),
                    _fixture_html_payload(doi),
                )

                self.assertEqual(article.source, "mdpi_html")
                self.assertEqual(article.quality.content_kind, "fulltext")
                self.assertTrue(article.quality.has_fulltext)
                self.assertGreater(len(article.sections), 3)
                self.assertGreater(article.quality.body_metrics.body_heading_count, 1)

    def test_mdpi_pdf_fallback_fixture_exists(self) -> None:
        pdf_path = golden_criteria_asset(MDPI_PDF_FALLBACK_DOI, "original.pdf")

        self.assertTrue(pdf_path.is_file())
        self.assertGreater(pdf_path.stat().st_size, 100_000)


if __name__ == "__main__":
    unittest.main()
