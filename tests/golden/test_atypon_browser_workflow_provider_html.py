from __future__ import annotations
from tests.support._atypon_browser_workflow_provider_support import *

# ruff: noqa: F403,F405


class AtyponBrowserWorkflowProviderHtmlTests(AtyponBrowserWorkflowProviderTestCase):
    def test_provider_owned_html_signals_populate_final_article_authors(self) -> None:
        cases = (
            {
                "provider": "science",
                "client": science_provider.ScienceClient(transport=None, env={}),
                "html_fixture": SCIENCE_DATALAYER_AUTHOR_FIXTURE,
                "doi": "10.1126/science.adp0212",
                "title": "Anthropogenic amplification of precipitation variability over the past century",
                "landing_url": "https://www.science.org/doi/full/10.1126/science.adp0212",
                "expected_authors": ["Wenxia Zhang", "Tianjun Zhou", "Peili Wu"],
            },
            {
                "provider": "wiley",
                "client": wiley_provider.WileyClient(transport=None, env={}),
                "html_fixture": WILEY_REGRESSION_FIXTURE,
                "doi": "10.1111/gcb.16998",
                "title": "Drought thresholds that impact vegetation reveal the divergent responses of vegetation growth to drought across China",
                "landing_url": "https://onlinelibrary.wiley.com/doi/10.1111/gcb.16998",
                "expected_authors": ["Mingze Sun", "Xiangyi Li", "Hao Xu"],
            },
            {
                "provider": "pnas",
                "client": pnas_provider.PnasClient(transport=None, env={}),
                "html_fixture": PNAS_REGRESSION_FIXTURE,
                "doi": "10.1073/pnas.2309123120",
                "title": "Amazon deforestation causes strong regional warming",
                "landing_url": "https://www.pnas.org/doi/full/10.1073/pnas.2309123120",
                "expected_authors": [
                    "Edward W. Butt",
                    "Jessica C. A. Baker",
                    "Francisco G. Silva Bezerra",
                ],
            },
        )

        for case in cases:
            with self.subTest(provider=case["provider"], doi=case["doi"]):
                self._assert_provider_owned_author_case(
                    client=case["client"],
                    html_fixture=case["html_fixture"],
                    doi=case["doi"],
                    title=case["title"],
                    landing_url=case["landing_url"],
                    expected_authors=case["expected_authors"],
                )

    def test_pnas_provider_renders_headingless_commentary_without_synthetic_title_section(
        self,
    ) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        doi = "10.1073/pnas.2317456120"
        title = "Amazon deforestation implications in local/regional climate change"
        landing_url = f"https://www.pnas.org/doi/full/{doi}"
        article, _, _ = self._build_browser_fixture_article(
            client,
            html=PNAS_COMMENTARY_FIXTURE.read_text(encoding="utf-8"),
            landing_url=landing_url,
            article_metadata={"doi": doi, "title": title, "authors": []},
            extraction_metadata={"doi": doi, "title": title},
        )
        rendered = article.to_ai_markdown(max_tokens="full_text")

        self.assertIsNone(article.metadata.abstract)
        self.assertEqual(article.metadata.authors, ["Paulo Artaxo"])
        self.assertEqual(article.sections[0].heading, "")
        self.assertEqual(article.sections[0].kind, "body")
        self.assertIn(
            "# Amazon deforestation implications in local/regional climate change",
            rendered,
        )
        self.assertNotIn(
            "## Amazon deforestation implications in local/regional climate change",
            rendered,
        )
        self.assertNotIn("## Full Text", rendered)

    def test_science_provider_keeps_frontmatter_sections_but_only_one_abstract_in_final_article(
        self,
    ) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        doi = "10.1126/science.abp8622"
        title = "The drivers and impacts of Amazon forest degradation"
        landing_url = f"https://www.science.org/doi/full/{doi}"
        article, _, _ = self._build_browser_fixture_article(
            client,
            html=SCIENCE_FRONTMATTER_REGRESSION_FIXTURE.read_text(encoding="utf-8"),
            landing_url=landing_url,
            article_metadata={"doi": doi, "title": title},
        )
        rendered = article.to_ai_markdown(max_tokens="full_text")

        self.assertEqual(
            article.metadata.authors[:3],
            ["David M. Lapola", "Patricia Pinho", "Jos Barlow"],
        )
        self.assertGreater(len(article.metadata.authors), 3)
        self.assertIn("Policies to tackle degradation", article.metadata.abstract or "")
        self.assertEqual(
            [
                section.heading
                for section in article.sections
                if section.kind == "abstract"
            ],
            ["Abstract"],
        )
        self.assertEqual(
            [section.heading for section in article.sections[:4]],
            ["Abstract", "Losing the Amazon", "Structured Abstract", "Main Text"],
        )
        self.assertEqual(article.sections[1].kind, "body")
        self.assertEqual(article.sections[2].kind, "body")
        self.assertEqual(rendered.count("## Abstract"), 1)
        self.assertIn("## Losing the Amazon", rendered)
        self.assertIn("## Structured Abstract", rendered)

    def test_science_provider_replay_for_adl6155_keeps_materials_and_methods_wrapper_heading(
        self,
    ) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        doi = "10.1126/sciadv.adl6155"
        landing_url = f"https://www.science.org/doi/{doi}"
        html = SCIENCE_ADL6155_ROOT_CAUSE_FIXTURE.read_text(encoding="utf-8")
        metadata = self._metadata_from_golden_criteria(SCIENCE_ADL6155_METADATA, doi)
        metadata.setdefault(
            "title",
            "A two-fold increase of carbon cycle sensitivity to tropical temperature variations",
        )
        metadata.setdefault("landing_page_url", landing_url)

        extracted_assets = html_assets.extract_html_assets(
            html, landing_url, asset_profile="body"
        )
        downloaded_assets = self._map_local_assets_by_basename(
            extracted_assets,
            asset_dir=SCIENCE_ADL6155_ASSET_DIR,
        )
        self.assertEqual(len(downloaded_assets), len(extracted_assets))

        article, _, _ = self._build_browser_fixture_article(
            client,
            html=html,
            landing_url=landing_url,
            article_metadata=metadata,
            downloaded_assets=downloaded_assets,
        )
        rendered = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        self.assertIn("## MATERIALS AND METHODS", rendered)
        self.assertIn("### Experimental design", rendered)
        self.assertLess(
            rendered.index("## MATERIALS AND METHODS"),
            rendered.index("### Experimental design"),
        )

    def test_wiley_provider_deduplicates_near_matching_abstract_in_final_article_render(
        self,
    ) -> None:
        client = wiley_provider.WileyClient(transport=None, env={})
        doi = "10.1111/gcb.16998"
        title = "Drought thresholds that impact vegetation reveal the divergent responses of vegetation growth to drought across China"
        landing_url = f"https://onlinelibrary.wiley.com/doi/{doi}"
        html = WILEY_REGRESSION_FIXTURE.read_text(encoding="utf-8")
        _, extraction, raw_payload = self._build_browser_html_raw_payload(
            client,
            html=html,
            landing_url=landing_url,
            extraction_metadata={"doi": doi, "title": title},
        )

        article = client.to_article_model(
            {"doi": doi, "title": title, "abstract": extraction.get("abstract_text")},
            raw_payload,
        )
        rendered = article.to_ai_markdown(max_tokens="full_text")

        self.assertEqual(rendered.count("## Abstract"), 1)
        self.assertEqual(
            len(
                [section for section in article.sections if section.kind == "abstract"]
            ),
            1,
        )

    def test_wiley_provider_replay_for_2004gb002273_body_assets_avoid_trailing_figures_noise(
        self,
    ) -> None:
        client = wiley_provider.WileyClient(transport=None, env={})
        doi = "10.1029/2004GB002273"
        landing_url = "https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2004GB002273"
        html = WILEY_2004GB002273_ROOT_CAUSE_FIXTURE.read_text(encoding="utf-8")
        metadata = self._metadata_from_golden_criteria(WILEY_2004GB002273_METADATA, doi)
        metadata.setdefault(
            "title", "Terrestrial mechanisms of interannual CO2 variability"
        )
        metadata.setdefault("landing_page_url", landing_url)

        extracted_assets = html_assets.extract_html_assets(
            html, landing_url, asset_profile="body"
        )
        downloaded_assets = self._map_local_assets_by_basename(
            extracted_assets,
            asset_dir=WILEY_2004GB002273_ASSET_DIR,
        )
        extracted_figures = [
            asset for asset in extracted_assets if asset.get("kind") == "figure"
        ]
        downloaded_figures = [
            asset for asset in downloaded_assets if asset.get("kind") == "figure"
        ]
        self.assertEqual(len(downloaded_figures), len(extracted_figures))

        article, _, _ = self._build_browser_fixture_article(
            client,
            html=html,
            landing_url=landing_url,
            article_metadata=metadata,
            downloaded_assets=downloaded_assets,
        )
        rendered = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        self.assertNotIn("\n## Figures\n", rendered)
        self.assertNotIn("Open in figure viewer", rendered)
        self.assertNotIn("PowerPoint", rendered)

    def test_pnas_provider_keeps_frontmatter_once_and_filters_collateral_noise_in_final_render(
        self,
    ) -> None:
        client = pnas_provider.PnasClient(transport=None, env={})
        doi = "10.1073/pnas.2309123120"
        title = "Amazon deforestation causes strong regional warming"
        landing_url = f"https://www.pnas.org/doi/full/{doi}"
        html = PNAS_REGRESSION_FIXTURE.read_text(encoding="utf-8")
        _, extraction, raw_payload = self._build_browser_html_raw_payload(
            client,
            html=html,
            landing_url=landing_url,
            extraction_metadata={"doi": doi, "title": title},
        )
        article = client.to_article_model(
            {"doi": doi, "title": title, "abstract": extraction.get("abstract_text")},
            raw_payload,
        )
        rendered = article.to_ai_markdown(max_tokens="full_text")

        self.assertEqual(rendered.count("## Significance"), 1)
        self.assertEqual(rendered.count("## Abstract"), 1)
        self.assertNotIn("community water fluoridation", rendered.lower())
        self.assertNotIn("tattoo ink", rendered.lower())
        self.assertNotIn("negative social ties", rendered.lower())
        self.assertNotIn("sign up for pnas alerts", rendered.lower())
