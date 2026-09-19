from __future__ import annotations
from __future__ import annotations
from tests.golden_criteria import golden_criteria_asset, golden_criteria_scenario_asset
import unittest
from paper_fetch.providers.atypon_browser_workflow import (
    extract_atypon_browser_workflow_markdown,
    rewrite_inline_figure_links,
)
import json
from paper_fetch.extraction.html.figure_links import inject_inline_figure_links


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


if __name__ == "__main__":
    unittest.main()

if __name__ == "__main__":
    unittest.main()
