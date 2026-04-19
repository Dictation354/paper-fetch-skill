from __future__ import annotations

import unittest

from paper_fetch.providers._science_pnas_html import extract_science_pnas_markdown, rewrite_inline_figure_links



class SciencePnasPostprocessTests(unittest.TestCase):
    def test_extract_science_pnas_markdown_cleans_synthetic_wiley_html(self) -> None:
        html = """
        <html><body>
        <article>
          <h1>Wiley Example</h1>
          <div class="publicationHistory">Received: 1 Jan 2025</div>
          <section class="article-section__abstract">
            <h2>Abstract</h2>
            <p>Short abstract with two sentences. It should be retained.</p>
          </section>
          <div class="article-section__content">
            <h2>Results</h2>
            <p>This is the first body paragraph with enough narrative detail to count as article text. It has a second sentence. This Wiley example keeps adding prose so the cleaned markdown clearly exceeds the minimum body threshold and behaves like a real article section.</p>
            <p>This is the second body paragraph and it should remain in the cleaned markdown output. It adds more narrative detail about methods, results, interpretation, and implications so the synthetic example looks like a usable full-text HTML extraction.</p>
            <h2>View options</h2>
            <p>Purchase digital access to this article</p>
          </div>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://onlinelibrary.wiley.com/doi/full/10.1111/example",
            "wiley",
            metadata={"doi": "10.1111/example", "title": "Wiley Example"},
        )

        self.assertIn("# Wiley Example", markdown)
        self.assertIn("## Abstract", markdown)
        self.assertIn("This is the second body paragraph", markdown)
        self.assertNotIn("Received: 1 Jan 2025", markdown)
        self.assertNotIn("View options", markdown)
        self.assertNotIn("Purchase digital access to this article", markdown)

    def test_extract_science_pnas_markdown_cleans_synthetic_pnas_html(self) -> None:
        html = """
        <html><body>
        <article>
          <div class="article__header">
            <span>Research Article</span>
          </div>
          <h1>PNAS Example</h1>
          <section role="doc-abstract">
            <h2>Abstract</h2>
            <p>Compact abstract summary. It stays.</p>
          </section>
          <div property="articleBody">
            <h2>Results</h2>
            <p>This paragraph represents the start of the article body and should survive cleanup. It has a second sentence. The synthetic PNAS body continues with enough detail to exceed the full-text threshold and mimic a short but usable article section.</p>
            <p>A second paragraph adds methodological and interpretive prose so the cleaned output remains clearly beyond abstract-only content and we can verify that citation boilerplate is trimmed away.</p>
            <h2>Citations</h2>
            <p>Select the format you want to export the citation of this publication.</p>
          </div>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.pnas.org/doi/full/10.1073/pnas.example",
            "pnas",
            metadata={"doi": "10.1073/pnas.example", "title": "PNAS Example"},
        )

        self.assertIn("# PNAS Example", markdown)
        self.assertIn("## Abstract", markdown)
        self.assertIn("This paragraph represents the start of the article body", markdown)
        self.assertNotIn("Research Article", markdown)
        self.assertNotIn("### Citations", markdown)
        self.assertNotIn("Select the format you want to export the citation", markdown)

    def test_extract_science_pnas_markdown_keeps_pnas_significance_and_abstract_separate(self) -> None:
        html = """
        <html><body>
        <article>
          <h1>PNAS Example</h1>
          <div id="abstracts">
            <section id="executive-summary-abstract" property="abstract" typeof="Text" role="doc-abstract">
              <h2>Significance</h2>
              <div role="paragraph">This significance summary stays before the abstract and is kept as a distinct block with enough prose to survive the markdown cleanup stage.</div>
            </section>
            <section id="abstract" property="abstract" typeof="Text" role="doc-abstract">
              <h2>Abstract</h2>
              <div role="paragraph">This abstract summary should remain separate from the body so the extracted markdown has an explicit abstract section before the main prose begins.</div>
            </section>
          </div>
          <section id="bodymatter" property="articleBody">
            <h2>Introduction</h2>
            <p>This paragraph represents the start of the article body and should appear after the abstract blocks. It contains enough prose to count as usable full text for the synthetic regression case.</p>
          </section>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.pnas.org/doi/full/10.1073/pnas.example-abstracts",
            "pnas",
            metadata={"doi": "10.1073/pnas.example-abstracts", "title": "PNAS Example"},
        )

        self.assertIn("## Significance", markdown)
        self.assertIn("## Abstract", markdown)
        self.assertLess(markdown.index("## Significance"), markdown.index("## Abstract"))
        self.assertLess(
            markdown.index("## Abstract"),
            markdown.index("This paragraph represents the start of the article body"),
        )

    def test_extract_science_pnas_markdown_inserts_main_text_boundary_after_pnas_abstract(self) -> None:
        html = """
        <html><body>
        <article>
          <h1>PNAS Main Text Example</h1>
          <section id="abstract" property="abstract" typeof="Text" role="doc-abstract">
            <h2>Abstract</h2>
            <p>This abstract paragraph should stay inside the abstract section and remain visually distinct from the body. A second sentence keeps the regression case realistic.</p>
          </section>
          <section id="bodymatter" property="articleBody">
            <p>This lead body paragraph appears before the first formal section heading on the publisher page. It should trigger a synthetic main-text boundary instead of being absorbed into the abstract block.</p>
            <h2>Results and Discussion</h2>
            <p>This second body paragraph stays under the explicit body heading and confirms the synthetic boundary does not suppress later headings.</p>
          </section>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.pnas.org/doi/full/10.1073/pnas.main-text-example",
            "pnas",
            metadata={"doi": "10.1073/pnas.main-text-example", "title": "PNAS Main Text Example"},
        )

        self.assertIn("## Abstract", markdown)
        self.assertIn("## Main Text", markdown)
        self.assertIn("## Results and Discussion", markdown)
        self.assertLess(markdown.index("## Abstract"), markdown.index("## Main Text"))
        self.assertLess(markdown.index("## Main Text"), markdown.index("## Results and Discussion"))
        self.assertLess(markdown.index("## Main Text"), markdown.index("This lead body paragraph appears before the first formal section heading"))

    def test_extract_science_pnas_markdown_inserts_main_text_boundary_after_science_abstract(self) -> None:
        html = """
        <html><body>
        <article>
          <h1>Science Main Text Example</h1>
          <section id="abstract" property="abstract" typeof="Text" role="doc-abstract">
            <h2>Abstract</h2>
            <div role="paragraph">This abstract paragraph should stay inside the abstract section and remain visually distinct from the body. A second sentence keeps the regression case realistic.</div>
          </section>
          <section id="bodymatter" property="articleBody">
            <div role="paragraph">This lead body paragraph appears before the first formal section heading on the publisher page. It should trigger a synthetic main-text boundary instead of being absorbed into the abstract block.</div>
            <h2>Results and Discussion</h2>
            <div role="paragraph">This second body paragraph stays under the explicit body heading and confirms the synthetic boundary does not suppress later headings.</div>
          </section>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.science.org/doi/full/10.1126/science.main-text-example",
            "science",
            metadata={"doi": "10.1126/science.main-text-example", "title": "Science Main Text Example"},
        )

        self.assertIn("## Abstract", markdown)
        self.assertIn("## Main Text", markdown)
        self.assertIn("## Results and Discussion", markdown)
        self.assertLess(markdown.index("## Abstract"), markdown.index("## Main Text"))
        self.assertLess(markdown.index("## Main Text"), markdown.index("## Results and Discussion"))
        self.assertLess(markdown.index("## Main Text"), markdown.index("This lead body paragraph appears before the first formal section heading"))

    def test_extract_science_pnas_markdown_inlines_pnas_figure_links_and_trims_heading_periods(self) -> None:
        html = """
        <html><body>
        <article>
          <h1>PNAS Figure Example</h1>
          <section role="doc-abstract">
            <h2>Abstract</h2>
            <p>Short abstract with two sentences. It should be retained as a distinct abstract section.</p>
          </section>
          <section id="bodymatter" property="articleBody">
            <h3>Data.</h3>
            <p>This paragraph introduces the figure and contains enough narrative detail to survive cleanup. A second sentence keeps the synthetic example above the body sufficiency threshold.</p>
            <figure>
              <img src="/images/figure-1.jpg" alt="Example figure" />
              <figcaption>
                <span class="label">Figure 1.</span>
                <span class="figure__caption-text">Caption body for the PNAS figure.</span>
              </figcaption>
            </figure>
            <p>This second body paragraph confirms the figure remains embedded inside the article body after markdown postprocessing.</p>
          </section>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.pnas.org/doi/full/10.1073/pnas.figure-example",
            "pnas",
            metadata={"doi": "10.1073/pnas.figure-example", "title": "PNAS Figure Example"},
        )

        self.assertIn("### Data", markdown)
        self.assertNotIn("### Data.", markdown)
        self.assertIn("![Figure 1](https://www.pnas.org/images/figure-1.jpg)", markdown)
        self.assertIn("**Figure 1.** Caption body for the PNAS figure.", markdown)
        self.assertLess(
            markdown.index("![Figure 1](https://www.pnas.org/images/figure-1.jpg)"),
            markdown.index("**Figure 1.** Caption body for the PNAS figure."),
        )

    def test_extract_science_pnas_markdown_matches_science_figure_links_by_label(self) -> None:
        html = """
        <html><body>
        <article>
          <h1>Science Figure Example</h1>
          <section role="doc-abstract">
            <h2>Abstract</h2>
            <p>Short abstract with two sentences. It should be retained as a distinct abstract section.</p>
          </section>
          <section property="articleBody">
            <h2>Results</h2>
            <p>This paragraph introduces the figure and contains enough narrative detail to survive cleanup. A second sentence keeps the synthetic example above the body sufficiency threshold.</p>
            <figure class="summary-figure">
              <img src="/images/hero.jpg" alt="Graphical abstract" />
              <figcaption>Graphical abstract for the study.</figcaption>
            </figure>
            <figure>
              <img src="/images/figure-1.jpg" alt="Science figure" />
              <figcaption>
                <span class="label">Fig. 1.</span>
                <span class="figure__caption-text">Caption body for the science figure.</span>
              </figcaption>
            </figure>
            <p>This second body paragraph confirms the figure remains embedded inside the article body after markdown postprocessing.</p>
          </section>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.science.org/doi/full/10.1126/science.figure-example",
            "science",
            metadata={"doi": "10.1126/science.figure-example", "title": "Science Figure Example"},
        )

        self.assertIn("![Figure 1](https://www.science.org/images/figure-1.jpg)", markdown)
        self.assertNotIn("![Figure 1](https://www.science.org/images/hero.jpg)", markdown)
        self.assertIn("**Figure 1.** Caption body for the science figure.", markdown)
        self.assertNotIn("**Figure 1.** .", markdown)
        self.assertLess(
            markdown.index("![Figure 1](https://www.science.org/images/figure-1.jpg)"),
            markdown.index("**Figure 1.** Caption body for the science figure."),
        )

    def test_extract_science_pnas_markdown_normalizes_title_subscript_line_breaks(self) -> None:
        html = """
        <html><body>
        <article>
          <h1>
            Projections of future forest degradation and CO
            <sub>2</sub>
            emissions for the Brazilian Amazon
          </h1>
          <section role="doc-abstract">
            <h2>Abstract</h2>
            <p>Short abstract summary remains available.</p>
          </section>
          <section property="articleBody">
            <h2>Results</h2>
            <p>This paragraph represents the body of the article and should remain after title normalization.</p>
          </section>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.science.org/doi/full/10.1126/science.example-subscript-title",
            "science",
            metadata={"doi": "10.1126/science.example-subscript-title"},
        )

        self.assertIn(
            "# Projections of future forest degradation and CO<sub>2</sub> emissions for the Brazilian Amazon",
            markdown,
        )
        self.assertNotIn("CO\n<sub>2</sub>", markdown)

    def test_rewrite_inline_figure_links_prefers_local_paths_for_existing_science_image_blocks(self) -> None:
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
        self.assertNotIn("![Figure 1](https://www.science.org/images/figure-1.jpg)", rewritten)

    def test_rewrite_inline_figure_links_is_data_driven_for_non_legacy_publisher(self) -> None:
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

    def test_extract_science_pnas_markdown_trims_heading_periods_for_science(self) -> None:
        html = """
        <html><body>
        <article>
          <h1>Science Heading Period Example</h1>
          <section role="doc-abstract">
            <h2>Abstract</h2>
            <p>Short abstract with two sentences. It should be retained as a distinct abstract section.</p>
          </section>
          <section property="articleBody">
            <h2>Results.</h2>
            <p>This paragraph represents the body of the article and should remain after heading normalization. A second sentence keeps the synthetic sample above the body sufficiency threshold.</p>
          </section>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.science.org/doi/full/10.1126/science.heading-period-example",
            "science",
            metadata={"doi": "10.1126/science.heading-period-example"},
        )

        self.assertIn("## Results", markdown)
        self.assertNotIn("## Results.", markdown)

    def test_extract_science_pnas_markdown_moves_wiley_abbreviations_to_end(self) -> None:
        html = """
        <html><body>
        <main>
          <article>
            <h1>Wiley Example</h1>
            <div class="article__content">
              <h3 class="list-paired__title">Abbreviations</h3>
              <div class="list-paired">
                <table>
                  <tr><th><li>AI</li></th><td><li>artificial intelligence</li></td></tr>
                  <tr><th><li>LLM</li></th><td><li>large language model</li></td></tr>
                </table>
              </div>
              <section class="article-section__content">
                <h2>1 INTRODUCTION</h2>
                <p>This is the first body paragraph with enough narrative detail to count as article text. It has a second sentence so the synthetic Wiley sample clearly behaves like usable full text.</p>
              </section>
              <section class="article-section__content">
                <h2>2 RESULTS</h2>
                <p>This second section adds more narrative detail about methods, results, and implications so the extracted markdown keeps multiple body sections before the abbreviations appendix is appended.</p>
              </section>
              <section id="references" class="article-section__content">
                <h2>References</h2>
                <p>1. Example cited work.</p>
              </section>
            </div>
          </article>
        </main>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://onlinelibrary.wiley.com/doi/full/10.1111/example-abbrev",
            "wiley",
            metadata={"doi": "10.1111/example-abbrev", "title": "Wiley Example"},
        )

        self.assertIn("## 1 INTRODUCTION", markdown)
        self.assertIn("## 2 RESULTS", markdown)
        self.assertIn("## Abbreviations", markdown)
        self.assertGreater(markdown.index("## Abbreviations"), markdown.index("## 2 RESULTS"))
        self.assertIn("AI: artificial intelligence", markdown)
        self.assertIn("LLM: large language model", markdown)
        self.assertNotIn("## References", markdown)

    def test_extract_science_pnas_markdown_formats_formula_and_figure_blocks(self) -> None:
        html = """
        <html><body>
        <article>
          <h1>Formula Example</h1>
          <section role="doc-abstract">
            <h2>Abstract</h2>
            <p>Short abstract with two sentences. It should be retained as a distinct abstract section.</p>
          </section>
          <section property="articleBody">
            <h2>Results</h2>
            <p>This body paragraph includes enough narrative detail to keep the synthetic example above the full-text threshold. It also sets up the formula and figure normalization checks that follow.</p>
            <div class="display-formula">
              <span class="label">(1)</span>
              <mjx-assistive-mml>
                <math xmlns="http://www.w3.org/1998/Math/MathML" display="block">
                  <msub><mi>V</mi><mi>i</mi></msub>
                  <mo>=</mo>
                  <mi>f</mi>
                  <mo>(</mo>
                  <mi>V</mi>
                  <mo>)</mo>
                </math>
              </mjx-assistive-mml>
            </div>
            <figure>
              <img src="/images/figure-1.jpg" alt="Figure preview" />
              <div class="figure-extra">Open in Viewer PowerPoint</div>
              <figcaption>
                <span class="label">Figure 1.</span>
                <span class="figure__caption-text">Caption body for the figure.</span>
              </figcaption>
            </figure>
            <p>This second body paragraph keeps the example comfortably in full-text territory after the auxiliary blocks have been normalized.</p>
          </section>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://example.test/formula",
            "science",
            metadata={"doi": "10.1000/formula", "title": "Formula Example"},
        )

        self.assertIn("**Equation 1.**", markdown)
        self.assertIn("$$", markdown)
        self.assertIn("V_{i} = f(V)", markdown)
        self.assertIn("![Figure 1](https://example.test/images/figure-1.jpg)", markdown)
        self.assertIn("**Figure 1.** Caption body for the figure.", markdown)
        self.assertNotIn("Open in Viewer", markdown)
        self.assertNotIn("PowerPoint", markdown)

    def test_extract_science_pnas_markdown_treats_pnas_table_wrapper_as_table_block(self) -> None:
        html = """
        <html><body>
        <article>
          <h1>PNAS Table Example</h1>
          <section role="doc-abstract">
            <h2>Abstract</h2>
            <p>Short abstract with two sentences. It should be retained as a distinct abstract section.</p>
          </section>
          <section id="bodymatter" property="articleBody">
            <h2>Results</h2>
            <p>This body paragraph introduces the table and keeps the synthetic example above the full-text threshold. It includes a second sentence for narrative structure.</p>
            <div class="figure-wrap">
              <header><div class="label">Table 1.</div></header>
              <figure class="table">
                <figcaption>Estimated model parameters.</figcaption>
                <div class="table-wrap">
                  <table>
                    <thead>
                      <tr><th>Parameter</th><th>Value</th></tr>
                    </thead>
                    <tbody>
                      <tr><td>beta</td><td>0.87</td></tr>
                      <tr><td>delta</td><td>2.17</td></tr>
                    </tbody>
                  </table>
                </div>
              </figure>
            </div>
            <p>This trailing body paragraph confirms the table remains in place after markdown postprocessing.</p>
          </section>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.pnas.org/doi/full/10.1073/pnas.table-example",
            "pnas",
            metadata={"doi": "10.1073/pnas.table-example", "title": "PNAS Table Example"},
        )

        self.assertIn("**Table 1.** Estimated model parameters.", markdown)
        self.assertRegex(markdown, r"\| Parameter\s+\| Value\s+\|")
        self.assertNotIn("**Figure** Estimated model parameters.", markdown)

    def test_extract_science_pnas_markdown_preserves_inline_table_cell_formatting(self) -> None:
        html = """
        <html><body>
        <article>
          <h1>PNAS Inline Table Example</h1>
          <section role="doc-abstract">
            <h2>Abstract</h2>
            <p>Short abstract with two sentences. It should be retained as a distinct abstract section.</p>
          </section>
          <section id="bodymatter" property="articleBody">
            <h2>Results</h2>
            <p>This body paragraph introduces the table and keeps the synthetic example above the full-text threshold. It includes a second sentence for narrative structure.</p>
            <div class="figure-wrap">
              <header><div class="label">Table 1.</div></header>
              <figure class="table">
                <figcaption>Estimated parameters.</figcaption>
                <div class="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Parameter</th>
                        <th>Fixed Effects (R.S.E., %)<sup>a</sup></th>
                        <th>Description</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td><i>β</i>(mL/FFU/d)</td>
                        <td>8.3 × 10<sup>–4</sup> (22.2)</td>
                        <td>Virus infection rate</td>
                      </tr>
                      <tr>
                        <td><i>ρ</i><sub>0</sub>(/d)</td>
                        <td><i>h</i><sub>0</sub></td>
                        <td>See ref. <a href="#core-r10">10</a></td>
                      </tr>
                      <tr>
                        <td><i>K<sub>ρ</sub></i>(cells)</td>
                        <td><i>σ<sub>h</sub></i>(/d)</td>
                        <td><a href="#core-r11">Anchor only text</a></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </figure>
            </div>
            <p>This trailing body paragraph confirms the table remains in place after markdown postprocessing.</p>
          </section>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.pnas.org/doi/full/10.1073/pnas.inline-table-example",
            "pnas",
            metadata={"doi": "10.1073/pnas.inline-table-example", "title": "PNAS Inline Table Example"},
        )

        self.assertIn("Fixed Effects (R.S.E., %)<sup>a</sup>", markdown)
        self.assertIn("*β*(mL/FFU/d)", markdown)
        self.assertIn("8.3 × 10<sup>–4</sup> (22.2)", markdown)
        self.assertIn("*ρ*<sub>0</sub>(/d)", markdown)
        self.assertIn("*K*<sub>ρ</sub>(cells)", markdown)
        self.assertIn("*h*<sub>0</sub>", markdown)
        self.assertIn("*σ*<sub>h</sub>(/d)", markdown)
        self.assertIn("See ref. 10", markdown)
        self.assertIn("Anchor only text", markdown)
        self.assertNotIn("[10](", markdown)
        self.assertNotIn("[Anchor only text](", markdown)

    def test_extract_science_pnas_markdown_flattens_multilevel_table_headers(self) -> None:
        html = """
        <html><body>
        <article>
          <h1>Science Multiheader Table Example</h1>
          <section role="doc-abstract">
            <h2>Abstract</h2>
            <p>Short abstract with two sentences. It should be retained as a distinct abstract section.</p>
          </section>
          <section property="articleBody">
            <h2>Results</h2>
            <p>This body paragraph introduces the multiheader table and keeps the synthetic example above the full-text threshold. It includes a second sentence for narrative structure.</p>
            <figure class="table">
              <figcaption><span class="label">Table 1.</span> Spatial lag regressions.</figcaption>
              <table>
                <thead>
                  <tr>
                    <th colspan="3">Nondegraded forest</th>
                    <th colspan="3">Degradation in normal precipitation years</th>
                    <th colspan="3">Degradation in extreme drought years</th>
                  </tr>
                  <tr>
                    <th>Variable</th>
                    <th>Estimate</th>
                    <th>P value</th>
                    <th>Variable</th>
                    <th>Estimate</th>
                    <th>P value</th>
                    <th>Variable</th>
                    <th>Estimate</th>
                    <th>P value</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Spatial coefficient</td>
                    <td>0.90</td>
                    <td>0.000</td>
                    <td>Spatial coefficient</td>
                    <td>0.824</td>
                    <td>0.000</td>
                    <td>Spatial coefficient</td>
                    <td>0.773</td>
                    <td>0.000</td>
                  </tr>
                </tbody>
              </table>
            </figure>
          </section>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.science.org/doi/full/10.1126/science.multiheader-table-example",
            "science",
            metadata={"doi": "10.1126/science.multiheader-table-example", "title": "Science Multiheader Table Example"},
        )

        self.assertIn("**Table 1.** Spatial lag regressions.", markdown)
        self.assertIn("| Nondegraded forest / Variable |", markdown)
        self.assertIn("Degradation in normal precipitation years / Estimate", markdown)
        self.assertIn("Degradation in extreme drought years / P value", markdown)
        self.assertRegex(
            markdown,
            r"\|\s*Spatial coefficient\s*\|\s*0\.90\s*\|\s*0\.000\s*\|\s*Spatial coefficient\s*\|\s*0\.824\s*\|\s*0\.000\s*\|\s*Spatial coefficient\s*\|\s*0\.773\s*\|\s*0\.000\s*\|",
        )

    def test_extract_science_pnas_markdown_flattens_rowspan_table_body_cells(self) -> None:
        html = """
        <html><body>
        <article>
          <h1>Science Rowspan Table Example</h1>
          <section role="doc-abstract">
            <h2>Abstract</h2>
            <p>Short abstract with two sentences. It should be retained as a distinct abstract section.</p>
          </section>
          <section property="articleBody">
            <h2>Results</h2>
            <p>This body paragraph introduces the rowspan table and keeps the synthetic example above the full-text threshold. It includes a second sentence for narrative structure.</p>
            <figure class="table">
              <figcaption><span class="label">Table 2.</span> CO<sub>2</sub> balance simulated in the scenarios.</figcaption>
              <table>
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Period</th>
                    <th>Sustainable scenario</th>
                    <th>Fragmentation scenario</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <th rowspan="2">CO<sub>2</sub> (Gt CO<sub>2</sub>)</th>
                    <td>1960–2019</td>
                    <td>37.23</td>
                    <td>36.99</td>
                  </tr>
                  <tr>
                    <td>2020–2050</td>
                    <td>1.31</td>
                    <td>24.07</td>
                  </tr>
                </tbody>
              </table>
            </figure>
          </section>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.science.org/doi/full/10.1126/science.rowspan-table-example",
            "science",
            metadata={"doi": "10.1126/science.rowspan-table-example", "title": "Science Rowspan Table Example"},
        )

        self.assertIn("**Table 2.** CO<sub>2</sub> balance simulated in the scenarios.", markdown)
        self.assertRegex(
            markdown,
            r"\|\s*Metric\s*\|\s*Period\s*\|\s*Sustainable scenario\s*\|\s*Fragmentation scenario\s*\|",
        )
        self.assertRegex(
            markdown,
            r"\|\s*CO<sub>2</sub>\s*\(Gt CO<sub>2</sub>\)\s*\|\s*1960–2019\s*\|\s*37\.23\s*\|\s*36\.99\s*\|",
        )
        self.assertRegex(
            markdown,
            r"\|\s*CO<sub>2</sub>\s*\(Gt CO<sub>2</sub>\)\s*\|\s*2020–2050\s*\|\s*1\.31\s*\|\s*24\.07\s*\|",
        )

    def test_extract_science_pnas_markdown_preserves_non_table_inline_formatting(self) -> None:
        html = """
        <html><body>
        <article>
          <h1>PNAS Inline Prose Example</h1>
          <section role="doc-abstract">
            <p>Abstract keeps log<sub>10</sub> units and ref. <a href="#core-r9">9</a>. A second sentence keeps the abstract distinct.</p>
          </section>
          <section id="bodymatter" property="articleBody">
            <h2>Results</h2>
            <div role="paragraph">We challenged volunteers with 10 TCID<sub>50</sub> of virus and estimated <i>t<sub>d</sub></i> from the early data. The same analysis tracked <i>h</i><sub>0</sub> and <i>σ<sub>h</sub></i> across the humoral response.</div>
            <p>Cell-mediated immune response involves antigen-specific CD<sup>8</sup>+ T cells, and the paragraph keeps normal prose spacing after inline markers. A second sentence keeps the synthetic sample above the full-text threshold.</p>
            <figure>
              <img src="/images/figure-1.jpg" alt="Figure preview" />
              <figcaption>
                <span class="label">Figure 1.</span>
                <span class="figure__caption-text">Caption keeps log<sub>10</sub> scaling and ref. <a href="#core-r10">10</a>.</span>
              </figcaption>
            </figure>
          </section>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.pnas.org/doi/full/10.1073/pnas.inline-prose-example",
            "pnas",
            metadata={"doi": "10.1073/pnas.inline-prose-example", "title": "PNAS Inline Prose Example"},
        )

        self.assertIn("## Abstract", markdown)
        self.assertIn("log<sub>10</sub>", markdown)
        self.assertIn("TCID<sub>50</sub>", markdown)
        self.assertIn("*t*<sub>d</sub>", markdown)
        self.assertIn("*h*<sub>0</sub>", markdown)
        self.assertIn("*σ*<sub>h</sub>", markdown)
        self.assertIn("CD<sup>8</sup>+", markdown)
        self.assertIn("**Figure 1.** Caption keeps log<sub>10</sub> scaling and ref. 10.", markdown)
        self.assertIn("ref. 9", markdown)
        self.assertNotIn("[9](", markdown)
        self.assertNotIn("[10](", markdown)

    def test_extract_science_pnas_markdown_falls_back_complex_table_to_bullets(self) -> None:
        html = """
        <html><body>
        <article>
          <h1>Complex Table Example</h1>
          <section role="doc-abstract">
            <h2>Abstract</h2>
            <p>Short abstract with two sentences. It should be retained as a distinct abstract section.</p>
          </section>
          <section property="articleBody">
            <h2>Results</h2>
            <p>This body paragraph introduces the complex table and keeps the synthetic example above the full-text threshold. It includes a second sentence for narrative structure.</p>
            <div class="article-table-content">
              <header class="article-table-caption">
                <span class="table-caption__label">TABLE 1.</span>
                Complex grouped values.
              </header>
              <div class="article-table-content-wrapper">
                <table class="table article-section__table">
                  <thead>
                    <tr><th>Group</th><th colspan="2">Values</th></tr>
                  </thead>
                  <tbody>
                    <tr><td>Group A</td><td>Alpha / Beta</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
            <p>This trailing body paragraph confirms the complex table remains in place after markdown postprocessing.</p>
          </section>
        </article>
        </body></html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://onlinelibrary.wiley.com/doi/full/10.1111/complex-table-example",
            "wiley",
            metadata={"doi": "10.1111/complex-table-example", "title": "Complex Table Example"},
        )

        self.assertIn("**Table 1.** Complex grouped values.", markdown)
        self.assertIn("- Group: Group A; Values: Alpha / Beta", markdown)
        self.assertNotIn("| Group | Values |", markdown)



if __name__ == "__main__":
    unittest.main()
