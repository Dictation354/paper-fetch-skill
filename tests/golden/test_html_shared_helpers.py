from __future__ import annotations
from __future__ import annotations
from __future__ import annotations
from paper_fetch.extraction.html.formula_rules import (
    looks_like_formula_image,
)
import unittest
from bs4 import BeautifulSoup
from paper_fetch.extraction.html import assets as html_assets
from paper_fetch.extraction.html.formula_rules import (
    formula_image_url_from_node,
    is_display_formula_node,
)
from paper_fetch.providers import _springer_html as springer_html
import paper_fetch.providers._wiley_html as wiley_html
from paper_fetch.providers.atypon_browser_workflow import (
    asset_scopes as atypon_browser_workflow_asset_scopes,
)
from tests.golden_criteria import golden_criteria_asset
from tests.block_fixtures import block_asset


class SharedHtmlHelperTests(unittest.TestCase):
    def test_wiley_real_fixture_supporting_information_only_yields_true_supplementary_asset(
        self,
    ) -> None:
        source_url = "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16414"
        html_text = golden_criteria_asset(
            "10.1111/gcb.16414", "original.html"
        ).read_text(encoding="utf-8")

        body_html, supplementary_html = (
            atypon_browser_workflow_asset_scopes.extract_browser_workflow_asset_html_scopes(
                html_text,
                source_url,
                "wiley",
            )
        )
        assets = wiley_html.extract_scoped_html_assets(
            body_html,
            source_url,
            asset_profile="all",
            supplementary_html_text=supplementary_html,
        )
        figure_assets = [asset for asset in assets if asset["kind"] == "figure"]
        supplementary_assets = [
            asset for asset in assets if asset["kind"] == "supplementary"
        ]

        self.assertEqual(
            [asset["heading"] for asset in supplementary_assets],
            ["gcb16414-sup-0001-FigureS1.docx"],
        )
        self.assertEqual(
            [asset["url"] for asset in supplementary_assets],
            [
                "https://onlinelibrary.wiley.com/action/downloadSupplement?doi=10.1111%2Fgcb.16414&file=gcb16414-sup-0001-FigureS1.docx"
            ],
        )
        self.assertEqual(
            [asset["filename_hint"] for asset in supplementary_assets],
            ["gcb16414-sup-0001-FigureS1.docx"],
        )
        self.assertTrue(
            any(
                "gcb16414-fig-0001-m.jpg" in asset.get("url", "")
                for asset in figure_assets
            )
        )
        self.assertFalse(
            any(
                "gcb16414-fig-" in asset.get("url", "")
                for asset in supplementary_assets
            )
        )
        self.assertNotIn("gcb16414-sup-0001-FigureS1.docx", body_html)

    def test_science_real_fixture_supplementary_comes_only_from_supplementary_section(
        self,
    ) -> None:
        source_url = "https://www.science.org/doi/full/10.1126/sciadv.adl6155"
        html_text = golden_criteria_asset(
            "10.1126/sciadv.adl6155", "original.html"
        ).read_text(
            encoding="utf-8",
            errors="ignore",
        )

        body_html, supplementary_html = (
            atypon_browser_workflow_asset_scopes.extract_browser_workflow_asset_html_scopes(
                html_text,
                source_url,
                "science",
            )
        )
        assets = atypon_browser_workflow_asset_scopes.extract_scoped_html_assets(
            body_html,
            source_url,
            asset_profile="all",
            supplementary_html_text=supplementary_html,
        )
        supplementary_assets = [
            asset for asset in assets if asset["kind"] == "supplementary"
        ]

        self.assertIn("co2_gr_mlo.txt", body_html)
        self.assertNotIn("co2_gr_mlo.txt", supplementary_html)
        self.assertIn("sciadv.adl6155_sm.pdf", supplementary_html)
        self.assertEqual(
            [asset["url"] for asset in supplementary_assets],
            [
                "https://www.science.org/doi/suppl/10.1126/sciadv.adl6155/suppl_file/sciadv.adl6155_sm.pdf"
            ],
        )

    def test_real_nature_fixture_keeps_source_data_without_chrome_sections(
        self,
    ) -> None:
        source_data_html = golden_criteria_asset(
            "10.1038/s41561-022-00912-7", "original.html"
        ).read_text(
            encoding="utf-8",
            errors="ignore",
        )
        self.assertTrue("source data fig." in source_data_html.casefold())

        source_data_markdown = springer_html.extract_html_payload(
            source_data_html,
            "https://www.nature.com/articles/s41561-022-00912-7",
        )["markdown_text"]

        self.assertIn("Source data", source_data_markdown)

        chrome_html = golden_criteria_asset(
            "10.1038/nature13376", "original.html"
        ).read_text(
            encoding="utf-8",
            errors="ignore",
        )
        chrome_html_text = chrome_html.casefold()
        self.assertTrue("rights and permissions" in chrome_html_text)
        self.assertTrue("open access" in chrome_html_text)

        chrome_markdown = springer_html.extract_html_payload(
            chrome_html,
            "https://www.nature.com/articles/nature13376",
        )["markdown_text"]

        self.assertNotIn("## Permissions", chrome_markdown)
        self.assertNotIn("## Open Access", chrome_markdown)
        self.assertNotIn("## Rights and permissions", chrome_markdown)

    def test_pnas_real_fixture_supplementary_ignores_body_anchor_to_section(
        self,
    ) -> None:
        source_url = "https://www.pnas.org/doi/full/10.1073/pnas.2509692123"
        html_text = block_asset("10.1073/pnas.2509692123", "raw.html").read_text(
            encoding="utf-8",
            errors="ignore",
        )

        body_html, supplementary_html = (
            atypon_browser_workflow_asset_scopes.extract_browser_workflow_asset_html_scopes(
                html_text,
                source_url,
                "pnas",
            )
        )
        assets = atypon_browser_workflow_asset_scopes.extract_scoped_html_assets(
            body_html,
            source_url,
            asset_profile="all",
            supplementary_html_text=supplementary_html,
        )
        supplementary_assets = [
            asset for asset in assets if asset["kind"] == "supplementary"
        ]

        self.assertIn("#supplementary-materials", body_html)
        self.assertNotIn("#supplementary-materials", supplementary_html)
        self.assertIn("pnas.2509692123.sapp.pdf", supplementary_html)
        self.assertEqual(
            [asset["url"] for asset in supplementary_assets],
            [
                "https://www.pnas.org/doi/suppl/10.1073/pnas.2509692123/suppl_file/pnas.2509692123.sapp.pdf",
                "https://www.pnas.org/doi/suppl/10.1073/pnas.2509692123/suppl_file/pnas.2509692123.sd01.xlsx",
            ],
        )

    def test_formula_rules_detect_real_formula_image_urls(self) -> None:
        wiley_html = golden_criteria_asset(
            "10.1111/gcb.15322", "original.html"
        ).read_text(
            encoding="utf-8",
            errors="ignore",
        )
        nature_html = golden_criteria_asset(
            "10.1038/nature12915", "original.html"
        ).read_text(
            encoding="utf-8",
            errors="ignore",
        )
        wiley_soup = BeautifulSoup(wiley_html, "html.parser")
        nature_soup = BeautifulSoup(nature_html, "html.parser")
        image = wiley_soup.select_one(".inline-equation img")
        nature_display = nature_soup.select_one(".c-article-equation")
        nature_image = nature_soup.select_one("img[src*='_Equ1_HTML']")
        figure_image = nature_soup.select_one("img[src*='Fig1_HTML']")

        self.assertIn("gcb15322-math-0001.png", formula_image_url_from_node(image))
        self.assertTrue(looks_like_formula_image(image))
        self.assertFalse(is_display_formula_node(nature_display))
        self.assertTrue(
            is_display_formula_node(
                nature_display,
                noise_profile="springer_nature",
            )
        )
        self.assertIn("_Equ1_HTML.jpg", formula_image_url_from_node(nature_image))
        self.assertTrue(looks_like_formula_image(nature_image))
        self.assertFalse(looks_like_formula_image(figure_image))

    def test_extract_formula_assets_reuses_shared_formula_rules(self) -> None:
        html = golden_criteria_asset("10.1038/nature12915", "original.html").read_text(
            encoding="utf-8",
            errors="ignore",
        )

        assets = html_assets.extract_formula_assets(
            html,
            "https://www.nature.com/articles/nature12915",
            noise_profile="springer_nature",
        )

        self.assertGreaterEqual(len(assets), 2)
        self.assertTrue(all(asset["kind"] == "formula" for asset in assets))
        self.assertTrue(
            any(
                asset["heading"] == "Equ1" and "_Equ1_HTML.jpg" in asset["url"]
                for asset in assets
            )
        )
        self.assertTrue(
            any(
                asset["heading"] == "Equ2" and "_Equ2_HTML.jpg" in asset["url"]
                for asset in assets
            )
        )
        self.assertFalse(any("Fig1_HTML" in asset["url"] for asset in assets))
