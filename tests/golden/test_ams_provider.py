from __future__ import annotations
from tests.support.test_evidence import evidence_cache as cache
from pathlib import Path
import tempfile
from tests.support.captured_images import download_captured_images
import re
import unittest
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from paper_fetch.models import article_from_markdown
from paper_fetch.providers import (
    _ams_assets,
    _ams_markdown,
)
from paper_fetch.providers.atypon_browser_workflow.asset_scopes import (
    extract_browser_workflow_asset_html_scopes,
)
from paper_fetch.providers.atypon_browser_workflow.markdown import (
    extract_atypon_browser_workflow_markdown,
)
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi
from tests.support._atypon_browser_workflow_provider_support import (
    AtyponBrowserWorkflowProviderTestCase,
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

    def test_ams_fixture_extracts_mixed_tiff_and_eps_download_figure_sources(
        self,
    ) -> None:
        doi = "10.1175/jamc-d-24-0048.1"
        assets = _ams_assets.scoped_asset_extractor(
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

    def test_ams_bams_fixture_keeps_late_body_sections(self) -> None:
        """ """
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
                soup = BeautifulSoup(_fixture_html(doi), "lxml")
                self.assertIsNotNone(
                    soup.select_one(
                        f'.tableWrap img[data-image-src="{full_size_path}"], '
                        f'.tableWrap a[href="{full_size_path}"]'
                    )
                )
                full_size_url = urljoin(_fixture_source_url(doi), full_size_path)
                markdown, _ = _extract_fixture_markdown(doi)
                assets = _ams_assets.scoped_asset_extractor(
                    _fixture_html(doi),
                    _fixture_source_url(doi),
                    asset_profile="body",
                )
                table_assets = [
                    asset for asset in assets if asset.get("kind") == "table"
                ]

                self.assertTrue(table_assets)
                self.assertTrue(
                    any(full_size_url == asset.get("url") for asset in table_assets)
                )
                self.assertIn("**Table 1.**", markdown)
                self.assertIn(f"![Table 1]({full_size_url})", markdown)
                self.assertLess(
                    markdown.index("**Table 1.**"),
                    markdown.index(f"![Table 1]({full_size_url})"),
                )

    def test_ams_aies_table_image_is_not_rewritten_to_next_figure(self) -> None:
        doi = "10.1175/aies-d-23-0093.1"
        markdown, _ = _extract_fixture_markdown(doi)
        table_path = "/view/journals/aies/3/4/full-AIES-D-23-0093.1-t1.jpg"
        soup = BeautifulSoup(_fixture_html(doi), "lxml")
        self.assertIsNotNone(
            soup.select_one(
                f'.tableWrap img[data-image-src="{table_path}"], '
                f'.tableWrap a[href="{table_path}"]'
            )
        )
        table_image = f"![Table 1]({urljoin(_fixture_source_url(doi), table_path)})"
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
                    "denoted as $p(\\mu_{n},\\sigma_{n}^{2}",
                )
            )
        )
        self.assertIn("(*μ*<sub>n</sub>, $\\sigma_{n}^{2}$)", markdown)
        self.assertIn("climatology: $\\text{BSS}", markdown)
        self.assertIn("*ν*<sub>n</sub> > 0", markdown)
        self.assertIn("*α*<sub>n,1</sub>", markdown)

    def test_ams_caption_inline_markup_is_preserved(self) -> None:
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
                        "$\\overset{\\cdot}{q}(q,\\phi_{2})$ (blue)",
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
        """ """
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

        normalized = _ams_markdown._normalize_ams_markdown_text(
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
            rendered = _ams_markdown.normalize_article_model(article).to_ai_markdown(
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

    def test_ams_downloaded_inline_figure_and_table_assets_do_not_repeat_at_tail(
        self,
    ) -> None:
        doi = "10.1175/jamc-d-24-0048.1"
        markdown, extraction = _extract_fixture_markdown(doi)
        assets = _ams_assets.scoped_asset_extractor(
            _fixture_html(doi),
            _fixture_source_url(doi),
            asset_profile="body",
        )
        selected = [
            asset
            for asset in assets
            if any(
                token in asset.get("url", "")
                for token in (
                    "full-JAMC-D-24-0048.1-f2.jpg",
                    "full-JAMC-D-24-0048.1-t1.jpg",
                )
            )
        ]
        self.assertEqual(len(selected), 2)
        tmpdir = self.enterContext(tempfile.TemporaryDirectory())
        downloaded_assets = download_captured_images(doi, selected, Path(tmpdir))

        article = article_from_markdown(
            source="ams_html",
            metadata=_fixture_metadata(doi),
            doi=doi,
            markdown_text=markdown,
            section_hints=list(extraction.get("section_hints") or []),
            assets=downloaded_assets,
        )
        rendered = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        for asset, label in zip(
            downloaded_assets, ("Figure 2", "Table 1"), strict=True
        ):
            self.assertIn(f"![{label}]({asset['path']})", rendered)
            self.assertEqual(rendered.count(f"]({asset['path']})"), 1)
        self.assertNotIn("\n## Figures\n", rendered)
        self.assertNotIn("\n## Tables\n", rendered)


if __name__ == "__main__":
    unittest.main()


def test_ams_inline_supplements_are_scoped_to_parent_and_deduplicated() -> None:
    body, supplements = extract_browser_workflow_asset_html_scopes(
        _fixture_html(AMS_DOI), AMS_LANDING_URL, "ams"
    )
    assets = _ams_assets.scoped_asset_extractor(
        body, AMS_LANDING_URL, asset_profile="all", supplementary_html_text=supplements
    )
    found = [a for a in assets if a["kind"] == "supplementary"]
    assert len(found) == 1
    assert found[0]["url"].endswith("10.1175_JCLI-D-23-0738.s1.pdf")
    url = found[0]["url"]
    rejected = [
        url.replace("JCLI-D-23-0738.1.xml", "JCLI-D-23-9999.1.xml"),
        url.replace("journals.ametsoc.org", "example.org"),
        AMS_PDF_URL,
        "javascript:;",
    ]
    assert (
        _ams_assets._extract_ams_supplementary_assets(
            "".join(
                f'<a href="{href}">Supplementary material</a>' for href in rejected
            ),
            AMS_LANDING_URL,
        )
        == []
    )
