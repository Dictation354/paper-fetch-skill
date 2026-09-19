from __future__ import annotations
from tests.support._atypon_browser_workflow_provider_support import *
# ruff: noqa: F403,F405


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
