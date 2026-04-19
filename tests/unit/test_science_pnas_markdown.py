from __future__ import annotations

import unittest

from paper_fetch.providers._science_pnas_html import SciencePnasHtmlFailure, extract_science_pnas_markdown
from tests.provider_benchmark_samples import provider_benchmark_sample
from tests.paths import FIXTURE_DIR


SCIENCE_SAMPLE = provider_benchmark_sample("science")
WILEY_SAMPLE = provider_benchmark_sample("wiley")
PNAS_SAMPLE = provider_benchmark_sample("pnas")


class SciencePnasMarkdownTests(unittest.TestCase):
    def test_science_fixture_extracts_fulltext_markdown(self) -> None:
        html = (FIXTURE_DIR / SCIENCE_SAMPLE.fixture_name).read_text(encoding="utf-8")

        markdown, info = extract_science_pnas_markdown(
            html,
            SCIENCE_SAMPLE.landing_url,
            "science",
            metadata={"doi": SCIENCE_SAMPLE.doi},
        )

        self.assertEqual(info["container_tag"], "main")
        self.assertIn("# Hyaluronic acid and tissue mechanics orchestrate mammalian digit tip regeneration", markdown)
        self.assertIn("Structured Abstract", markdown)
        self.assertIn("Discussion", markdown)
        self.assertIn("Materials and methods", markdown)
        self.assertIn("![Figure 1](", markdown)
        self.assertNotIn("**Figure 1.** .", markdown)
        self.assertIn("**Figure 1.** The niche discriminates regeneration from fibrosis after digit tip amputation. (**A**)", markdown)
        self.assertNotIn("amputation.(**A**)", markdown)

    def test_science_fixture_markdown_omits_frontmatter_and_collateral_noise(self) -> None:
        html = (FIXTURE_DIR / SCIENCE_SAMPLE.fixture_name).read_text(encoding="utf-8")

        markdown, _ = extract_science_pnas_markdown(
            html,
            SCIENCE_SAMPLE.landing_url,
            "science",
            metadata={"doi": SCIENCE_SAMPLE.doi},
        )

        self.assertNotIn("Full access", markdown)
        self.assertNotIn("Research Article", markdown)
        self.assertNotIn("Authors Info & Affiliations", markdown)
        self.assertNotIn("### Authors", markdown)
        self.assertNotIn("### Citations", markdown)
        self.assertNotIn("### View options", markdown)
        self.assertNotIn("View all articles by this author", markdown)
        self.assertNotIn("Purchase digital access to this article", markdown)
        self.assertNotIn("Copyright ©", markdown)

    def test_science_fixture_keeps_data_availability_but_filters_teaser_figure(self) -> None:
        html = (FIXTURE_DIR / SCIENCE_SAMPLE.fixture_name).read_text(encoding="utf-8")

        markdown, _ = extract_science_pnas_markdown(
            html,
            SCIENCE_SAMPLE.landing_url,
            "science",
            metadata={"doi": SCIENCE_SAMPLE.doi},
        )

        self.assertIn("## Data, code, and materials availability", markdown)
        self.assertNotIn("The ECM and tissue mechanics direct wound healing outcomes after digit amputations", markdown)
        self.assertIn("![Figure 1](", markdown)

    def test_pnas_abstract_fixture_is_rejected(self) -> None:
        html = (FIXTURE_DIR / "pnas_10.1073_pnas.2406303121.abstract.html").read_text(encoding="utf-8")

        with self.assertRaises(SciencePnasHtmlFailure) as ctx:
            extract_science_pnas_markdown(
                html,
                PNAS_SAMPLE.landing_url,
                "pnas",
                metadata={"doi": PNAS_SAMPLE.doi},
            )

        self.assertEqual(ctx.exception.reason, "insufficient_body")

    def test_pnas_full_fixture_extracts_body_sections_from_real_html(self) -> None:
        html = (FIXTURE_DIR / PNAS_SAMPLE.fixture_name).read_text(encoding="utf-8")

        markdown, info = extract_science_pnas_markdown(
            html,
            PNAS_SAMPLE.landing_url,
            "pnas",
            metadata={"doi": PNAS_SAMPLE.doi},
        )

        self.assertIn("# The kinetics of SARS-CoV-2 infection based on a human challenge study", markdown)
        self.assertIn("## Significance", markdown)
        self.assertIn("## Abstract", markdown)
        self.assertIn("Severe acute respiratory syndrome coronavirus 2 (SARS-CoV-2) continues to spread worldwide", markdown)
        self.assertIn("## Methods", markdown)
        self.assertIn("## Mathematical Models", markdown)
        self.assertIn("### Data", markdown)
        self.assertIn("### The Relationship between Total and Infectious Virus", markdown)
        self.assertNotIn("### Data.", markdown)
        self.assertNotIn("### The Relationship between Total and Infectious Virus.", markdown)
        self.assertIn("**Equation 1.**", markdown)
        self.assertIn("$$", markdown)
        self.assertRegex(markdown, r"\*\*Equation 1\.\*\*\n\n\$\$\nV_{i} = f\(V\) = BV\^{h},\n\$\$")
        self.assertRegex(markdown, r"\*\*Equation 2\.\*\*\n\n\$\$\n\\begin\{matrix\}")
        self.assertNotIn("**Equation 1.**$$", markdown)
        self.assertNotIn("**Equation 2.**$$", markdown)
        self.assertNotIn("$$Previously published data were used for this work", markdown)
        self.assertIn("![Figure 1](", markdown)
        self.assertIn("**Figure 1.**", markdown)
        self.assertLess(markdown.index("## Significance"), markdown.index("## Abstract"))
        self.assertLess(markdown.index("## Abstract"), markdown.index("## Methods"))
        diagnostics = info["availability_diagnostics"]
        self.assertTrue(diagnostics["accepted"])
        self.assertEqual(diagnostics["content_kind"], "fulltext")

    def test_pnas_full_fixture_omits_real_page_collateral_noise(self) -> None:
        html = (FIXTURE_DIR / PNAS_SAMPLE.fixture_name).read_text(encoding="utf-8")

        markdown, _ = extract_science_pnas_markdown(
            html,
            PNAS_SAMPLE.landing_url,
            "pnas",
            metadata={"doi": PNAS_SAMPLE.doi},
        )

        self.assertNotIn("Recommended articles", markdown)
        self.assertNotIn("Download PDF", markdown)
        self.assertNotIn("Request permissions", markdown)
        self.assertNotIn("Google Scholar", markdown)
        self.assertNotIn("Sign up for PNAS alerts", markdown)
        self.assertNotIn("Learn More", markdown)
        self.assertNotIn("Vi=fV=BVh", markdown)
        self.assertNotIn("dTdt=", markdown)

    def test_pnas_full_fixture_keeps_data_availability_and_renders_table_markdown(self) -> None:
        html = (FIXTURE_DIR / PNAS_SAMPLE.fixture_name).read_text(encoding="utf-8")

        markdown, _ = extract_science_pnas_markdown(
            html,
            PNAS_SAMPLE.landing_url,
            "pnas",
            metadata={"doi": PNAS_SAMPLE.doi},
        )

        self.assertIn("## Data, Materials, and Software Availability", markdown)
        self.assertEqual(markdown.count("## Data, Materials, and Software Availability"), 1)
        self.assertNotIn("#### Data, Materials, and Software Availability", markdown)
        self.assertIn("**Table 1.** Estimated population parameters for the DDRCM with humoral immune response", markdown)
        self.assertRegex(markdown, r"\| Parameter\s+\| Description\s+\| Fixed Effects \(R\.S\.E\., %\)\s+\|")
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
        self.assertNotIn("**Figure** Estimated population parameters for the DDRCM with humoral immune response", markdown)
        self.assertLess(markdown.index("**Figure 4.**"), markdown.index("**Table 1.**"))

    def test_pnas_collateral_data_availability_fixture_is_not_duplicated(self) -> None:
        html = (FIXTURE_DIR / "pnas_10.1073_pnas.2309123120.html").read_text(encoding="utf-8")

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.pnas.org/doi/full/10.1073/pnas.2309123120",
            "pnas",
            metadata={"doi": "10.1073/pnas.2309123120"},
        )

        self.assertEqual(markdown.count("## Data, Materials, and Software Availability"), 1)
        self.assertNotIn("#### Data, Materials, and Software Availability", markdown)

    def test_wiley_full_fixture_extracts_body_sections_from_real_html(self) -> None:
        html = (FIXTURE_DIR / WILEY_SAMPLE.fixture_name).read_text(encoding="utf-8")

        markdown, info = extract_science_pnas_markdown(
            html,
            WILEY_SAMPLE.landing_url,
            "wiley",
            metadata={"doi": WILEY_SAMPLE.doi},
        )

        self.assertIn(
            "# Contrasting temperature effects on the velocity of early- versus late-stage vegetation green-up in the Northern Hemisphere",
            markdown,
        )
        self.assertIn("## Abstract", markdown)
        self.assertIn("Global vegetation greening has been widely confirmed in previous studies", markdown)
        self.assertIn("## 1 INTRODUCTION", markdown)
        self.assertIn("## 2 MATERIALS AND METHODS", markdown)
        self.assertIn("## 3 RESULTS", markdown)
        self.assertIn("## 4 DISCUSSION", markdown)
        self.assertIn("![Figure 1](", markdown)
        self.assertIn("**Figure 1.**", markdown)
        self.assertIn("CO<sub>2</sub> emission", markdown)
        self.assertIn("m<sup>2</sup> m<sup>−2</sup> year<sup>−1</sup>", markdown)
        self.assertNotIn("CO2 emission", markdown)
        self.assertNotIn("m2 m−2 year−1", markdown)
        self.assertNotIn("## Abbreviations", markdown)
        self.assertLess(markdown.index("## Abstract"), markdown.index("## 1 INTRODUCTION"))
        diagnostics = info["availability_diagnostics"]
        self.assertTrue(diagnostics["accepted"])
        self.assertEqual(diagnostics["content_kind"], "fulltext")

    def test_wiley_full_fixture_omits_real_page_collateral_noise(self) -> None:
        html = (FIXTURE_DIR / WILEY_SAMPLE.fixture_name).read_text(encoding="utf-8")

        markdown, _ = extract_science_pnas_markdown(
            html,
            WILEY_SAMPLE.landing_url,
            "wiley",
            metadata={"doi": WILEY_SAMPLE.doi},
        )

        self.assertNotIn("Publication History", markdown)
        self.assertNotIn("Article navigation and tools", markdown)
        self.assertNotIn("Download PDF", markdown)
        self.assertNotIn("About Wiley Online Library", markdown)
        self.assertNotIn("Open in figure viewer", markdown)
        self.assertNotIn("PowerPoint", markdown)

    def test_wiley_full_fixture_keeps_data_availability_but_filters_other_back_matter(self) -> None:
        html = (FIXTURE_DIR / WILEY_SAMPLE.fixture_name).read_text(encoding="utf-8")

        markdown, _ = extract_science_pnas_markdown(
            html,
            WILEY_SAMPLE.landing_url,
            "wiley",
            metadata={"doi": WILEY_SAMPLE.doi},
        )

        self.assertIn("## DATA AVAILABILITY STATEMENT", markdown)
        self.assertNotIn("## CONFLICT OF INTEREST", markdown)
        self.assertNotIn("## Supporting Information", markdown)

    def test_wiley_fixture_renders_rule_table_as_markdown_table(self) -> None:
        html = (FIXTURE_DIR / "wiley_10.1111_cas.16395.html").read_text(encoding="utf-8")

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://onlinelibrary.wiley.com/doi/full/10.1111/cas.16395",
            "wiley",
            metadata={"doi": "10.1111/cas.16395"},
        )

        self.assertIn("**Table 1.** AI-SaMD approved as a medical device in the field of oncology in Japan (as of May 2024).", markdown)
        self.assertRegex(
            markdown,
            r"\| Research area\s+\| Approval number\s+\| Product\s+\| Manufacturer\s+\| Target inspection method\s+\| Class\s+\| Year of approval\s+\|",
        )
        self.assertNotIn("Research areaApproval numberProductManufacturerTarget inspection methodClassYear of approval", markdown)

    def test_science_perspective_fixture_extracts_fulltext_without_section_headings(self) -> None:
        html = (FIXTURE_DIR / "science_10.1126_science.aeg3511.html").read_text(encoding="utf-8")

        markdown, info = extract_science_pnas_markdown(
            html,
            "https://www.science.org/doi/full/10.1126/science.aeg3511",
            "science",
            metadata={"doi": "10.1126/science.aeg3511"},
        )

        self.assertEqual(info["container_tag"], "article")
        self.assertIn("# Magma plumbing beneath Yellowstone", markdown)
        self.assertIn("Yellowstone is one of the most seismically active areas", markdown)
        self.assertIn("The findings of Cao", markdown)
        self.assertIn("(*1–3*)", markdown)
        self.assertIn("(*6, 7*)", markdown)
        self.assertIn("(*11, 12*)", markdown)
        self.assertNotIn("*1**–**3*", markdown)
        self.assertNotIn("*6**,* *7*", markdown)
        self.assertNotIn("*11**,* *12*", markdown)
        diagnostics = info["availability_diagnostics"]
        self.assertTrue(diagnostics["accepted"])
        self.assertIn("body_sufficient", diagnostics["strong_positive_signals"])
        self.assertIn("aaas_user_entitled", diagnostics["strong_positive_signals"])
        self.assertGreaterEqual(diagnostics["figure_count"], 1)

    def test_science_adp0212_fixture_splits_display_equations_and_caption_sentences(self) -> None:
        html = (FIXTURE_DIR / "science_10.1126_science.adp0212.html").read_text(encoding="utf-8")

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.science.org/doi/full/10.1126/science.adp0212",
            "science",
            metadata={"doi": "10.1126/science.adp0212"},
        )

        self.assertRegex(markdown, r"\*\*Equation 1\.\*\*\n\n\$\$\n\\sigma P")
        self.assertRegex(markdown, r"\n\$\$\n\nwhere \*P\* is precipitation")
        self.assertNotIn("**Equation 1.**$$", markdown)
        self.assertNotIn("$$where *P* is precipitation", markdown)
        self.assertIn(
            "**Figure 2.** Regional change in daily precipitation variability from 1900 to 2020. Time series",
            markdown,
        )
        self.assertNotIn("2020.Time series", markdown)



if __name__ == "__main__":
    unittest.main()
