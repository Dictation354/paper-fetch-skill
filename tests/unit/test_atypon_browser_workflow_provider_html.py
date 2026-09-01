# ruff: noqa: F403,F405
from __future__ import annotations

from ._atypon_browser_workflow_provider_support import *


class AtyponBrowserWorkflowProviderHtmlTests(AtyponBrowserWorkflowProviderTestCase):
    def test_science_provider_prefers_html_route(self) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", SCIENCE_SAMPLE.doi)
            mocked_pdf = mock.Mock()
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mock.Mock(
                    return_value=browser_runtime.BrowserFetchedHtml(
                        source_url=SCIENCE_SAMPLE.landing_url,
                        final_url=SCIENCE_SAMPLE.landing_url,
                        html="<html></html>",
                        response_status=200,
                        response_headers={"content-type": "text/html"},
                        title=SCIENCE_SAMPLE.title,
                        summary="Example summary",
                        browser_context_seed={},
                    )
                ),
                extract_atypon_browser_workflow_markdown=mock.Mock(
                    return_value=(
                        f"# {SCIENCE_SAMPLE.title}\n\n## Discussion\n\n"
                        + ("Body text " * 120),
                        {"title": SCIENCE_SAMPLE.title},
                    )
                ),
                fetch_pdf_with_browser=mocked_pdf,
            )
            raw_payload = client.fetch_raw_fulltext(
                SCIENCE_SAMPLE.doi,
                {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
            )
            article = client.to_article_model(
                {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                raw_payload,
            )

        mocked_pdf.assert_not_called()
        self.assertEqual(_payload_route(raw_payload), "html")
        self.assertEqual(article.source, "science")
        self.assertIn("fulltext:science_html_ok", article.quality.source_trail)

    def test_science_provider_rewrites_inline_figure_links_to_downloaded_local_assets(
        self,
    ) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        with tempfile.TemporaryDirectory() as tmpdir:
            asset_path = Path(tmpdir) / "science-figure-1.png"
            asset_path.write_bytes(b"science-figure")
            raw_payload = _typed_raw_payload(
                provider="science",
                source_url=SCIENCE_SAMPLE.landing_url,
                content_type="text/html",
                body=b"<html></html>",
                route="html",
                markdown_text="\n\n".join(
                    [
                        f"# {SCIENCE_SAMPLE.title}",
                        "## Results",
                        ("Body text " * 80).strip(),
                        "![Figure 1](https://www.science.org/images/figure-1.jpg)",
                        "**Figure 1.** Caption body for the science figure.",
                    ]
                ),
                source_trail=["fulltext:science_html_ok"],
            )

            article = client.to_article_model(
                {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                raw_payload,
                downloaded_assets=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "caption": "Caption body for the science figure.",
                        "path": str(asset_path),
                        "source_url": "https://www.science.org/images/figure-1.jpg",
                        "section": "body",
                    }
                ],
            )

        body_markdown = article.to_ai_markdown(asset_profile="none")
        self.assertIn(f"![Figure 1]({asset_path})", body_markdown)
        self.assertNotIn(
            "![Figure 1](https://www.science.org/images/figure-1.jpg)", body_markdown
        )

        markdown = article.to_ai_markdown(asset_profile="body")
        self.assertIn(f"![Figure 1]({asset_path})", markdown)
        self.assertNotIn(
            "![Figure 1](https://www.science.org/images/figure-1.jpg)", markdown
        )
        self.assertEqual(article.assets[0].path, str(asset_path))

    def test_science_provider_uses_extracted_dom_abstract_and_restores_lead_body_text(
        self,
    ) -> None:
        """rule: rule-provider-owned-authors"""
        scenario = json.loads(
            golden_criteria_scenario_asset(
                "provider_dom_abstract_fallback", "payload.json"
            ).read_text(encoding="utf-8")
        )
        client = science_provider.ScienceClient(transport=None, env={})
        raw_payload = _typed_raw_payload(
            provider=str(scenario["provider"]),
            source_url=str(scenario["source_url"]),
            content_type="text/html",
            body=str(scenario["body_html"]).encode("utf-8"),
            route="html",
            markdown_text=str(scenario["markdown_text"]),
            source_trail=["fulltext:science_html_ok"],
            extraction=scenario["extraction"],
        )

        article = client.to_article_model(
            {
                "doi": str(scenario["doi"]),
                "title": str(scenario["title"]),
                "abstract": str(scenario["metadata_abstract"]),
            },
            raw_payload,
        )

        self.assertEqual(article.metadata.abstract, "Short DOM abstract.")
        self.assertEqual(article.sections[0].heading, "Main Text")
        self.assertIn("Lead body paragraph", article.sections[0].text)
        self.assertEqual(article.sections[1].heading, "Results")

    def test_provider_owned_html_signals_populate_final_article_authors(self) -> None:
        """rule: rule-provider-owned-authors"""
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

    def test_science_provider_falls_back_to_dom_authors_when_datalayer_is_missing(
        self,
    ) -> None:
        client = science_provider.ScienceClient(transport=None, env={})
        doi = "10.1126/science.test-dom-authors"
        title = "Science DOM Author Fallback"
        landing_url = f"https://www.science.org/doi/full/{doi}"
        html = """
        <html>
          <body>
            <main class="article__fulltext">
              <article class="article-view">
                <h1>Science DOM Author Fallback</h1>
                <div class="contributors">
                  <div property="author">
                    <span property="givenName">Jamie</span>
                    <span property="familyName">Farrell</span>
                    <a href="https://orcid.org/0000-0000-0000-0001">https://orcid.org/0000-0000-0000-0001</a>
                  </div>
                  <div property="author"><span property="name">Taylor Example</span></div>
                  <div property="author">Jordan Example <a href="https://orcid.org/0000-0000-0000-0002">ORCID</a></div>
                  <div property="author">+12 authors</div>
                  <div property="author">Authors Info &amp; Affiliations</div>
                </div>
                <div id="abstracts">
                  <div class="core-container">
                    <section id="abstract" role="doc-abstract">
                      <h2>Abstract</h2>
                      <div role="paragraph">This abstract is long enough to remain stable in the final Science article model.</div>
                    </section>
                  </div>
                </div>
                <section class="article__body" data-extent="bodymatter" property="articleBody">
                  <h2>Results</h2>
                  <p>This body paragraph is long enough to satisfy availability checks and verify DOM author fallback.</p>
                  <p>This second body paragraph keeps the sample deterministic and clearly separated from the abstract.</p>
                </section>
              </article>
            </main>
          </body>
        </html>
        """
        markdown_text, extraction = client.extract_markdown(
            html,
            landing_url,
            metadata={"doi": doi, "title": title},
        )
        raw_payload = _typed_raw_payload(
            provider="science",
            source_url=landing_url,
            content_type="text/html",
            body=html.encode("utf-8"),
            route="html",
            markdown_text=markdown_text,
            source_trail=["fulltext:science_html_ok"],
            extraction=extraction,
        )

        article = client.to_article_model(
            {"doi": doi, "title": title},
            raw_payload,
        )

        self.assertEqual(
            article.metadata.authors,
            ["Jamie Farrell", "Taylor Example", "Jordan Example"],
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
