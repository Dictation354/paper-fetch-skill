from __future__ import annotations

import json
import unittest

from paper_fetch.extraction.html.figure_links import inject_inline_figure_links
from paper_fetch.providers.atypon_browser_workflow import (
    extract_atypon_browser_workflow_markdown,
    rewrite_inline_figure_links,
)
from tests.golden_criteria import golden_criteria_asset, golden_criteria_scenario_asset


WILEY_FULL_FIXTURE = golden_criteria_asset("10.1111/gcb.16414", "original.html")
WILEY_ABBREV_FIXTURE = golden_criteria_asset("10.1111/cas.16395", "original.html")
WILEY_METHODS_FIXTURE = golden_criteria_asset("10.1111/gcb.16455", "original.html")
PNAS_FULL_FIXTURE = golden_criteria_asset("10.1073/pnas.2406303121", "original.html")
PNAS_COMMENTARY_FIXTURE = golden_criteria_asset(
    "10.1073/pnas.2317456120", "commentary.html"
)
SCIENCE_FORMULA_FIXTURE = golden_criteria_asset(
    "10.1126/science.adp0212", "original.html"
)
SCIENCE_FRONTMATTER_FIXTURE = golden_criteria_asset(
    "10.1126/science.abp8622", "original.html"
)
SCIADV_ABF8021_FIXTURE = golden_criteria_asset(
    "10.1126/sciadv.abf8021", "original.html"
)
SCIADV_ABG9690_FIXTURE = golden_criteria_asset(
    "10.1126/sciadv.abg9690", "original.html"
)
SCIADV_ADM9732_FIXTURE = golden_criteria_asset(
    "10.1126/sciadv.adm9732", "original.html"
)


class AtyponBrowserWorkflowPostprocessTests(unittest.TestCase):
    def _assert_equation_blocks_are_normalized(self, markdown: str) -> None:
        self.assertRegex(markdown, r"\*\*Equation \d+[A-Za-z]?\.\*\*\n\n\$\$\n")
        self.assertNotRegex(markdown, r"\*\*Equation \d+[A-Za-z]?\.\*\*\$\$")
        self.assertNotRegex(markdown, r"\$\$(?=[^\s\n])")

    def test_inline_figure_injection_skips_body_reference_for_existing_image_label(
        self,
    ) -> None:
        markdown = "\n\n".join(
            [
                "## Results",
                "![Figure 2](assets/jgrd14507-fig-0002-m.png)",
                "The response is summarized in Figure 2.",
            ]
        )
        figure_assets = [
            {
                "kind": "figure",
                "heading": "Figure 2",
                "path": "assets/jgrd14507-fig-0002-m.png",
            },
            {
                "kind": "figure",
                "heading": "Figure 2",
                "path": "assets/jgrd14507-fig-0002-duplicate.png",
            },
        ]

        result = inject_inline_figure_links(
            markdown,
            figure_assets=figure_assets,
            clean_markdown_fn=lambda text: text,
        )

        self.assertEqual(result.count("![Figure 2]("), 1)
        self.assertNotIn("jgrd14507-fig-0002-duplicate.png", result)

    def _assert_pnas_table_inline_semantics(self, markdown: str) -> None:
        self.assertIn("TCID<sub>50</sub>", markdown)
        self.assertIn("log<sub>10</sub> copies/mL", markdown)
        self.assertIn("delay of length *t*<sub>d</sub> days", markdown)
        self.assertIn("where *h*<sub>0</sub> is the baseline value", markdown)
        self.assertIn("and *σ*<sub>h</sub> is the exponential decay rate", markdown)
        self.assertIn("*β*(mL/FFU/d)", markdown)
        self.assertIn("8.3 × 10<sup>–4</sup> (22.2)", markdown)
        self.assertIn("*ρ*<sub>0</sub>(/d)", markdown)
        self.assertIn("*K*<sub>ρ</sub>(cells)", markdown)
        self.assertIn("*h*<sub>0</sub>", markdown)
        self.assertIn("*σ*<sub>h</sub>(/d)", markdown)
        self.assertNotIn("TCID50 of the virus", markdown)
        self.assertNotIn("3 log 10 copies/mL", markdown)
        self.assertNotIn("delay of length td days", markdown)
        self.assertNotIn("where h0 is the baseline value", markdown)
        self.assertNotIn("σh is the exponential decay rate", markdown)
        self.assertNotIn("10 –4", markdown)
        self.assertNotIn("ρ 0", markdown)
        self.assertNotIn("K ρ", markdown)
        self.assertNotIn("σ h", markdown)

    def _extract_fixture_markdown(
        self,
        fixture_path,
        source_url: str,
        publisher: str,
        doi: str,
        *,
        title: str | None = None,
    ):
        metadata = {"doi": doi}
        if title:
            metadata["title"] = title
        html = fixture_path.read_text(encoding="utf-8")
        return extract_atypon_browser_workflow_markdown(
            html,
            source_url,
            publisher,
            metadata=metadata,
        )

    def test_wiley_real_fixture_filters_frontmatter_and_viewer_noise(self) -> None:
        markdown, _ = self._extract_fixture_markdown(
            WILEY_FULL_FIXTURE,
            "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16414",
            "wiley",
            "10.1111/gcb.16414",
        )

        self.assertIn(
            "# Contrasting temperature effects on the velocity of early- versus late-stage vegetation green-up in the Northern Hemisphere",
            markdown,
        )
        self.assertIn("## Abstract", markdown)
        self.assertIn("## 1 INTRODUCTION", markdown)
        self.assertNotIn("Open in figure viewer", markdown)
        self.assertNotIn("PowerPoint", markdown)

    def test_wiley_real_fixture_appends_abbreviations_after_body_content(self) -> None:
        markdown, _ = self._extract_fixture_markdown(
            WILEY_ABBREV_FIXTURE,
            "https://onlinelibrary.wiley.com/doi/full/10.1111/cas.16395",
            "wiley",
            "10.1111/cas.16395",
        )

        self.assertIn("## 1 INTRODUCTION", markdown)
        self.assertIn("## Abbreviations", markdown)
        self.assertIn("AI: artificial intelligence", markdown)
        self.assertIn("LLM: large language model", markdown)
        self.assertIn(
            "**Table 1.** AI-SaMD approved as a medical device in the field of oncology in Japan (as of May 2024).",
            markdown,
        )
        self.assertGreater(
            markdown.index("## Abbreviations"), markdown.index("## 1 INTRODUCTION")
        )
        self.assertGreater(
            markdown.index("## Abbreviations"), markdown.index("**Table 1.**")
        )

    def test_wiley_abbreviations_scenario_moves_frontmatter_glossary_after_body(
        self,
    ) -> None:
        markdown, _ = self._extract_fixture_markdown(
            golden_criteria_scenario_asset(
                "wiley_abbreviations_trailing", "original.html"
            ),
            "https://onlinelibrary.wiley.com/doi/full/10.1111/wiley-abbrev-scenario",
            "wiley",
            "10.1111/wiley-abbrev-scenario",
        )

        self.assertIn("## 1 INTRODUCTION", markdown)
        self.assertIn("**Table 1.** Scenario table.", markdown)
        self.assertIn("## Abbreviations", markdown)
        self.assertIn("AI: artificial intelligence", markdown)
        self.assertGreater(
            markdown.index("## Abbreviations"), markdown.index("## 1 INTRODUCTION")
        )
        self.assertGreater(
            markdown.index("## Abbreviations"), markdown.index("**Table 1.**")
        )

    def test_wiley_real_fixture_keeps_methods_subcontent_in_body(self) -> None:
        markdown, _ = self._extract_fixture_markdown(
            WILEY_METHODS_FIXTURE,
            "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16455",
            "wiley",
            "10.1111/gcb.16455",
        )

        self.assertIn("## 2 MATERIALS AND METHODS", markdown)
        self.assertIn("Workflow summary", markdown)
        self.assertIn("three main assessments", markdown)
        self.assertIn("## 3 RESULTS", markdown)
        self.assertNotIn("## Abbreviations", markdown)
        self.assertLess(
            markdown.index("## 2 MATERIALS AND METHODS"), markdown.index("## 3 RESULTS")
        )

    def test_pnas_real_fixture_keeps_significance_and_abstract_before_main_text(
        self,
    ) -> None:
        markdown, _ = self._extract_fixture_markdown(
            PNAS_FULL_FIXTURE,
            "https://www.pnas.org/doi/full/10.1073/pnas.2406303121",
            "pnas",
            "10.1073/pnas.2406303121",
        )

        self.assertIn("## Significance", markdown)
        self.assertIn("## Abstract", markdown)
        self.assertIn("## Main Text", markdown)
        self.assertIn("## Methods", markdown)
        self.assertLess(
            markdown.index("## Significance"), markdown.index("## Abstract")
        )
        self.assertLess(markdown.index("## Abstract"), markdown.index("## Main Text"))
        self.assertLess(markdown.index("## Main Text"), markdown.index("## Methods"))

    def test_pnas_real_fixture_preserves_figures_equations_and_heading_trimming(
        self,
    ) -> None:
        markdown, _ = self._extract_fixture_markdown(
            PNAS_FULL_FIXTURE,
            "https://www.pnas.org/doi/full/10.1073/pnas.2406303121",
            "pnas",
            "10.1073/pnas.2406303121",
        )

        self.assertIn("### Data", markdown)
        self.assertNotIn("### Data.", markdown)
        self.assertNotIn(
            "### The Relationship between Total and Infectious Virus.", markdown
        )
        self.assertIn("**Equation 1.**", markdown)
        self.assertIn("**Equation 2.**", markdown)
        self.assertIn("$$", markdown)
        self.assertIn("![Figure 1](", markdown)
        self.assertIn("**Figure 1.**", markdown)
        self._assert_equation_blocks_are_normalized(markdown)
        self.assertNotIn(
            "$$Previously published data were used for this work", markdown
        )

    def test_pnas_real_fixture_renders_table_and_inline_cell_formatting(self) -> None:
        markdown, _ = self._extract_fixture_markdown(
            PNAS_FULL_FIXTURE,
            "https://www.pnas.org/doi/full/10.1073/pnas.2406303121",
            "pnas",
            "10.1073/pnas.2406303121",
        )

        self.assertIn(
            "**Table 1.** Estimated population parameters for the DDRCM with humoral immune response",
            markdown,
        )
        self._assert_pnas_table_inline_semantics(markdown)

    def test_pnas_real_commentary_keeps_headingless_body_flat(self) -> None:
        markdown, _ = self._extract_fixture_markdown(
            PNAS_COMMENTARY_FIXTURE,
            "https://www.pnas.org/doi/full/10.1073/pnas.2317456120",
            "pnas",
            "10.1073/pnas.2317456120",
            title="Amazon deforestation implications in local/regional climate change",
        )

        self.assertIn(
            "# Amazon deforestation implications in local/regional climate change",
            markdown,
        )
        self.assertNotIn(
            "## Amazon deforestation implications in local/regional climate change",
            markdown,
        )
        self.assertNotIn("## Full Text", markdown)
        self.assertNotIn("## Abstract", markdown)

    def test_science_real_fixture_keeps_formula_and_figure_caption_spacing(
        self,
    ) -> None:
        markdown, _ = self._extract_fixture_markdown(
            SCIENCE_FORMULA_FIXTURE,
            "https://www.science.org/doi/full/10.1126/science.adp0212",
            "science",
            "10.1126/science.adp0212",
        )

        self._assert_equation_blocks_are_normalized(markdown)
        self.assertRegex(markdown, r"\*\*Equation 1\.\*\*\n\n\$\$\n\\sigma P")
        self.assertRegex(markdown, r"\n\$\$\n\nwhere \*P\* is precipitation")
        self.assertIn(
            "**Figure 2.** Regional change in daily precipitation variability from 1900 to 2020. Time series",
            markdown,
        )
        self.assertNotIn("$$where *P* is precipitation", markdown)
        self.assertNotIn("2020.Time series", markdown)

    def test_shared_equation_normalization_handles_real_science_and_pnas_fixtures(
        self,
    ) -> None:
        fixture_specs = (
            (
                "10.1126/sciadv.abf8021",
                SCIADV_ABF8021_FIXTURE,
                "science",
                "https://www.science.org/doi/full/10.1126/sciadv.abf8021",
            ),
            (
                "10.1126/sciadv.abg9690",
                SCIADV_ABG9690_FIXTURE,
                "science",
                "https://www.science.org/doi/full/10.1126/sciadv.abg9690",
            ),
            (
                "10.1126/sciadv.adm9732",
                SCIADV_ADM9732_FIXTURE,
                "science",
                "https://www.science.org/doi/full/10.1126/sciadv.adm9732",
            ),
            (
                "10.1073/pnas.2406303121",
                PNAS_FULL_FIXTURE,
                "pnas",
                "https://www.pnas.org/doi/full/10.1073/pnas.2406303121",
            ),
        )

        for doi, fixture_path, publisher, source_url in fixture_specs:
            with self.subTest(doi=doi):
                markdown, _ = self._extract_fixture_markdown(
                    fixture_path,
                    source_url,
                    publisher,
                    doi,
                )

                self._assert_equation_blocks_are_normalized(markdown)

    def test_science_real_frontmatter_fixture_preserves_structured_summaries_and_main_text(
        self,
    ) -> None:
        markdown, _ = self._extract_fixture_markdown(
            SCIENCE_FRONTMATTER_FIXTURE,
            "https://www.science.org/doi/full/10.1126/science.abp8622",
            "science",
            "10.1126/science.abp8622",
        )

        self.assertIn(
            "# The drivers and impacts of Amazon forest degradation", markdown
        )
        self.assertIn("## Losing the Amazon", markdown)
        self.assertIn("## Structured Abstract", markdown)
        self.assertIn("## Abstract", markdown)
        self.assertIn("## Main Text", markdown)
        self.assertIn("Policies to tackle degradation", markdown)
        self.assertIn("log<sub>10</sub>", markdown)
        self.assertIn("CO<sub>2</sub>", markdown)
        self.assertIn("**Box 1.** Defining Amazonia’s degradation regime.", markdown)
        self.assertIn(
            "**Co-occurrence:** The incidence of different forms of disturbance",
            markdown,
        )
        self.assertNotIn("**Figure 2.** Box 1.", markdown)
        self.assertEqual(markdown.count("![Figure 2]("), 1)
        self.assertEqual(markdown.count("**Figure 2.**"), 1)
        self.assertLess(
            markdown.index("## Losing the Amazon"),
            markdown.index("## Structured Abstract"),
        )
        self.assertLess(
            markdown.index("## Structured Abstract"), markdown.index("## Abstract")
        )
        self.assertLess(markdown.index("## Abstract"), markdown.index("## Main Text"))

    def test_rewrite_inline_figure_links_prefers_local_paths_for_existing_science_image_blocks(
        self,
    ) -> None:
        markdown = "\n\n".join(
            [
                "# Science Figure Example",
                "## Results",
                "Narrative paragraph before the figure.",
                "![Figure 1](https://www.science.org/images/figure-1.jpg)",
                "**Figure 1.** Caption body for the science figure.",
            ]
        )

        rewritten = rewrite_inline_figure_links(
            markdown,
            figure_assets=[
                {
                    "kind": "figure",
                    "heading": "Figure 1",
                    "caption": "Caption body for the science figure.",
                    "source_url": "https://www.science.org/images/figure-1.jpg",
                    "path": "downloads/science-figure-1.png",
                    "section": "body",
                }
            ],
            publisher="science",
        )

        self.assertIn("![Figure 1](downloads/science-figure-1.png)", rewritten)
        self.assertNotIn(
            "![Figure 1](https://www.science.org/images/figure-1.jpg)", rewritten
        )

    def test_rewrite_inline_figure_links_treats_fig_caption_as_existing_caption(
        self,
    ) -> None:
        markdown = "\n\n".join(
            [
                "# AIP Figure Example",
                "## Results",
                "Narrative paragraph cites Fig. 1 before the image.",
                "![Figure 1](https://aipp.silverchair-cdn.com/figure-1.jpeg)",
                "**FIG. 1.** Caption body for the AIP figure.",
            ]
        )

        rewritten = rewrite_inline_figure_links(
            markdown,
            figure_assets=[
                {
                    "kind": "figure",
                    "heading": "FIG. 1. Caption body for the AIP figure.",
                    "caption": "FIG. 1. Caption body for the AIP figure.",
                    "url": "https://aipp.silverchair-cdn.com/figure-1.jpeg",
                    "path": "downloads/aip-figure-1.jpeg",
                    "section": "body",
                }
            ],
            publisher="aip",
        )

        self.assertEqual(rewritten.count("![Figure 1](downloads/aip-figure-1.jpeg)"), 1)
        self.assertIn("**FIG. 1.** Caption body for the AIP figure.", rewritten)

    def test_rewrite_inline_figure_links_is_data_driven_for_non_legacy_publisher(
        self,
    ) -> None:
        markdown = "\n\n".join(
            [
                "# Springer Figure Example",
                "## Results",
                "Narrative paragraph before the figure.",
                "**Figure 2.** Caption body for the springer figure.",
            ]
        )

        rewritten = rewrite_inline_figure_links(
            markdown,
            figure_assets=[
                {
                    "kind": "figure",
                    "heading": "Figure 2",
                    "caption": "Caption body for the springer figure.",
                    "path": "downloads/springer-figure-2.png",
                    "section": "body",
                }
            ],
            publisher="springer",
        )

        self.assertIn("![Figure 2](downloads/springer-figure-2.png)", rewritten)
        self.assertIn("**Figure 2.** Caption body for the springer figure.", rewritten)
        self.assertLess(
            rewritten.index("![Figure 2](downloads/springer-figure-2.png)"),
            rewritten.index("**Figure 2.** Caption body for the springer figure."),
        )

    def test_rewrite_inline_figure_links_ignores_cross_references_in_asset_captions(
        self,
    ) -> None:
        markdown = golden_criteria_scenario_asset(
            "inline_figure_link_rewrite", "article.md"
        ).read_text(encoding="utf-8")
        figure_assets = json.loads(
            golden_criteria_scenario_asset(
                "inline_figure_link_rewrite", "assets.json"
            ).read_text(encoding="utf-8")
        )

        rewritten = rewrite_inline_figure_links(
            markdown,
            figure_assets=figure_assets,
            publisher="pnas",
        )

        self.assertEqual(
            rewritten.count("![Figure 1](downloads/pnas.example.fig01.jpeg)"), 1
        )
        self.assertEqual(
            rewritten.count("![Figure 4](downloads/pnas.example.fig04.jpeg)"), 1
        )
        self.assertNotIn("![Figure 1](downloads/pnas.example.fig04.jpeg)", rewritten)

    def test_figure_link_injection_and_rewrite_share_path_preference(self) -> None:
        markdown = "\n\n".join(
            [
                "# Figure Link Example",
                "## Results",
                "**Figure 3.** Caption body.",
            ]
        )
        figure_assets = [
            {
                "kind": "figure",
                "heading": "Figure 3",
                "caption": "Caption body.",
                "url": "https://example.test/figure3.png",
                "path": "downloads/figure3.png",
                "section": "body",
            }
        ]

        rewritten = rewrite_inline_figure_links(
            markdown, figure_assets=figure_assets, publisher="science"
        )
        injected = inject_inline_figure_links(
            markdown,
            figure_assets=figure_assets,
            clean_markdown_fn=lambda value: value,
        )

        self.assertEqual(rewritten, injected)
        self.assertIn("![Figure 3](downloads/figure3.png)", rewritten)

    def test_inject_inline_figure_links_preserves_table_image_blocks(self) -> None:
        markdown = "\n\n".join(
            [
                "# Figure Link Example",
                "## Results",
                "![Table 1.](table-t1.jpg)",
                "![Extended Data Table 1](extended-table-1.jpg)",
                "![Supplementary Table 2](supplementary-table-2.jpg)",
                "**Figure 2.** Caption body.",
            ]
        )

        injected = inject_inline_figure_links(
            markdown,
            figure_assets=[
                {
                    "kind": "figure",
                    "heading": "Figure 2",
                    "caption": "Caption body.",
                    "path": "downloads/figure2.png",
                    "section": "body",
                }
            ],
            clean_markdown_fn=lambda value: value,
        )

        self.assertIn("![Table 1.](table-t1.jpg)", injected)
        self.assertIn("![Extended Data Table 1](extended-table-1.jpg)", injected)
        self.assertIn("![Supplementary Table 2](supplementary-table-2.jpg)", injected)
        self.assertIn("![Figure 2](downloads/figure2.png)", injected)
        self.assertNotIn("![Table 1.](downloads/figure2.png)", injected)
        self.assertLess(
            injected.index("![Figure 2](downloads/figure2.png)"),
            injected.index("**Figure 2.** Caption body."),
        )

    def test_inject_inline_figure_links_preserves_formula_image_blocks(self) -> None:
        markdown = "\n\n".join(
            [
                "# Formula Figure Boundary",
                "## Results",
                "![Formula](formula-m01.jpeg)",
                "The result is summarized in Fig. 1.",
                "**Figure 1.** Caption body.",
            ]
        )

        injected = inject_inline_figure_links(
            markdown,
            figure_assets=[
                {
                    "kind": "figure",
                    "heading": "Downloaded body image",
                    "caption": "Caption body.",
                    "path": "downloads/body-image.png",
                    "section": "body",
                }
            ],
            clean_markdown_fn=lambda value: value,
        )

        self.assertIn("![Formula](formula-m01.jpeg)", injected)
        self.assertIn("![Figure 1](downloads/body-image.png)", injected)
        self.assertLess(
            injected.index("![Formula](formula-m01.jpeg)"),
            injected.index("![Figure 1](downloads/body-image.png)"),
        )

    def test_inject_inline_figure_links_falls_back_to_first_body_reference(
        self,
    ) -> None:
        markdown = "\n\n".join(
            [
                "# Figure Link Example",
                "## Abstract",
                "The graphical summary in Figure 1 is front matter and should not receive the image.",
                "## Results",
                "The main comparison appears in figures 1 and 2.",
                "Additional text mentions Fig. 2 again.",
                "## References",
                "Reference title mentioning Figure 1.",
                "## Figures",
                "- Figure captions are listed here.",
            ]
        )

        injected = inject_inline_figure_links(
            markdown,
            figure_assets=[
                {
                    "kind": "figure",
                    "heading": "Figure 1",
                    "path": "downloads/figure1.png",
                    "section": "body",
                },
                {
                    "kind": "figure",
                    "heading": "Figure 2",
                    "path": "downloads/figure2.png",
                    "section": "body",
                },
            ],
            clean_markdown_fn=lambda value: value,
        )

        self.assertIn("![Figure 1](downloads/figure1.png)", injected)
        self.assertIn("![Figure 2](downloads/figure2.png)", injected)
        self.assertLess(
            injected.index("The main comparison appears in figures 1 and 2."),
            injected.index("![Figure 1](downloads/figure1.png)"),
        )
        self.assertLess(
            injected.index("![Figure 2](downloads/figure2.png)"),
            injected.index("Additional text mentions Fig. 2 again."),
        )
        self.assertLess(
            injected.index("![Figure 1](downloads/figure1.png)"),
            injected.index("## References"),
        )

    def test_inject_inline_figure_links_caption_block_takes_priority_over_body_reference(
        self,
    ) -> None:
        markdown = "\n\n".join(
            [
                "# Figure Link Example",
                "## Results",
                "The first paragraph mentions Figure 3 before the caption.",
                "**Figure 3.** Caption body.",
            ]
        )

        injected = inject_inline_figure_links(
            markdown,
            figure_assets=[
                {
                    "kind": "figure",
                    "heading": "Figure 3",
                    "path": "downloads/figure3.png",
                    "section": "body",
                }
            ],
            clean_markdown_fn=lambda value: value,
        )

        self.assertEqual(injected.count("![Figure 3](downloads/figure3.png)"), 1)
        self.assertLess(
            injected.index("![Figure 3](downloads/figure3.png)"),
            injected.index("**Figure 3.** Caption body."),
        )


if __name__ == "__main__":
    unittest.main()
