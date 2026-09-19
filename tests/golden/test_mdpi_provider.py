from __future__ import annotations
from tests.support.test_evidence import evidence_cache as cache
import unittest
from paper_fetch.models import article_from_markdown
from paper_fetch.models.markdown import iter_markdown_images
from paper_fetch.providers import _mdpi_assets, _mdpi_markdown
from paper_fetch.providers.mdpi import MdpiClient
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi
from tests.support._atypon_browser_workflow_provider_support import (
    AtyponBrowserWorkflowProviderTestCase,
    _typed_raw_payload,
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


@cache
def _extract_fixture_markdown(doi: str) -> tuple[str, dict[str, object]]:
    return _mdpi_markdown.extract_markdown(
        _fixture_html(doi),
        _fixture_source_url(doi),
        metadata=_fixture_metadata(doi),
    )


class MdpiProviderTests(AtyponBrowserWorkflowProviderTestCase):
    def test_mdpi_browser_dom_mathjax_formulas_are_not_duplicated(self) -> None:
        html = golden_criteria_asset(
            MDPI_SUPPLEMENTARY_DOI,
            "acquisition/assets-2026-09-15/mdpi-headless-002-browser_dom.html",
        ).read_text(encoding="utf-8")
        source_url = _fixture_source_url(MDPI_SUPPLEMENTARY_DOI)
        metadata = _fixture_metadata(MDPI_SUPPLEMENTARY_DOI)
        markdown, extraction = _mdpi_markdown.extract_markdown(
            html, source_url, metadata=metadata
        )
        self.assertEqual(markdown.count("$CO_{2}$"), 2)
        self.assertNotIn("[Formula unavailable]", markdown)
        self.assertIn("$CO_{2}$ emissions in comparison", markdown)
        self.assertIn("$CO_{2}$ emissions from the building category", markdown)
        self.assertEqual(extraction["semantic_losses"]["formula_missing_count"], 0)
        article = MdpiClient(transport=None, env={}).to_article_model(
            metadata,
            _typed_raw_payload(
                provider="mdpi",
                source_url=source_url,
                content_type="text/html",
                body=html.encode(),
                route="html",
            ),
        )
        self.assertEqual(article.quality.semantic_losses.formula_missing_count, 0)
        final_markdown = article.to_ai_markdown()
        self.assertEqual(final_markdown.count("$CO_{2}$"), 2)
        self.assertNotIn("[Formula unavailable]", final_markdown)

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

    def test_mdpi_structure_fixture_markdown(self) -> None:
        markdown, extraction = _extract_fixture_markdown(MDPI_STRUCTURE_DOI)

        self.assertIn("# Simulation of Carbon Dioxide Absorption", markdown)
        self.assertIn("## Abstract", markdown)
        self.assertIn("1. Introduction", markdown)
        self.assertRegex(markdown, r"(?m)^## 1\. Introduction")
        self.assertGreaterEqual(len(extraction["extracted_authors"]), 5)
        self.assertNotIn("Browse Figures", markdown)

    def test_mdpi_table_fixture_markdown(self) -> None:
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
        markdown, _ = _extract_fixture_markdown(MDPI_FIGURE_DOI)
        assets = _mdpi_assets.extract_scoped_html_assets(
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

    def test_mdpi_supplementary_fixture_markdown_and_all_assets(self) -> None:
        markdown, _ = _extract_fixture_markdown(MDPI_SUPPLEMENTARY_DOI)
        body_assets = _mdpi_assets.extract_scoped_html_assets(
            _fixture_html(MDPI_SUPPLEMENTARY_DOI),
            _fixture_source_url(MDPI_SUPPLEMENTARY_DOI),
            asset_profile="body",
        )
        all_assets = _mdpi_assets.extract_scoped_html_assets(
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
        for doi in MDPI_HTML_DOIS:
            with self.subTest(doi=doi):
                markdown, _ = _extract_fixture_markdown(doi)

                self.assertNotIn("## Abstract\n\n:", markdown)
                self.assertNotRegex(markdown, r"(?m)^:\s*$")
                self.assertNotRegex(markdown, r"(?m)^#### \d+\.\d+\. ")

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
