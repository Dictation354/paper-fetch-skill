from __future__ import annotations

import unittest

from bs4 import BeautifulSoup

from paper_fetch.extraction.html._runtime import body_metrics
from paper_fetch.providers import _science_pnas_html
from paper_fetch.providers._html_references import extract_numbered_references_from_html
from paper_fetch.extraction.html.signals import SciencePnasHtmlFailure
from paper_fetch.providers._science_pnas_html import extract_science_pnas_markdown
from tests.golden_criteria import golden_criteria_asset
from tests.provider_benchmark_samples import provider_benchmark_sample
from tests.paths import FIXTURE_DIR


SCIENCE_SAMPLE = provider_benchmark_sample("science")
WILEY_SAMPLE = provider_benchmark_sample("wiley")
PNAS_SAMPLE = provider_benchmark_sample("pnas")
PNAS_COLLATERAL_FIXTURE = golden_criteria_asset("10.1073/pnas.2309123120", "original.html")
SCIENCE_PERSPECTIVE_FIXTURE = golden_criteria_asset("10.1126/science.aeg3511", "original.html")
SCIENCE_ADP0212_FIXTURE = golden_criteria_asset("10.1126/science.adp0212", "original.html")


class SciencePnasMarkdownTests(unittest.TestCase):
    def test_extract_numbered_references_from_bibliography_labels(self) -> None:
        html = """
        <section id="bibliography" role="doc-bibliography">
          <div role="list">
            <div role="listitem" data-has="label">
              <div class="label">1</div>
              <div class="citations">
                <div class="citation-content">First numbered reference.</div>
              </div>
            </div>
            <div role="listitem" data-has="label">
              <div class="label">2</div>
              <div class="citations">
                <div class="citation-content">Second numbered reference.</div>
              </div>
            </div>
          </div>
        </section>
        """

        references = extract_numbered_references_from_html(html)

        self.assertEqual(
            references,
            [
                {"label": "1", "raw": "First numbered reference.", "doi": None, "year": None},
                {"label": "2", "raw": "Second numbered reference.", "doi": None, "year": None},
            ],
        )

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
        return extract_science_pnas_markdown(
            html,
            source_url,
            publisher,
            metadata=metadata,
        )

    def _extract_sample_markdown(self, sample):
        return self._extract_fixture_markdown(
            FIXTURE_DIR / sample.fixture_name,
            sample.landing_url,
            sample.provider,
            sample.doi,
        )

    def test_science_fixture_extracts_fulltext_markdown(self) -> None:
        markdown, info = self._extract_sample_markdown(SCIENCE_SAMPLE)

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
        markdown, _ = self._extract_sample_markdown(SCIENCE_SAMPLE)

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
        markdown, _ = self._extract_sample_markdown(SCIENCE_SAMPLE)

        self.assertIn("## Data, code, and materials availability", markdown)
        self.assertNotIn("The ECM and tissue mechanics direct wound healing outcomes after digit amputations", markdown)
        self.assertIn("![Figure 1](", markdown)

    def test_pnas_abstract_fixture_is_rejected(self) -> None:
        html = golden_criteria_asset("10.1073/pnas.2406303121", "abstract.html").read_text(encoding="utf-8")

        with self.assertRaises(SciencePnasHtmlFailure) as ctx:
            extract_science_pnas_markdown(
                html,
                PNAS_SAMPLE.landing_url,
                "pnas",
                metadata={"doi": PNAS_SAMPLE.doi},
            )

        self.assertEqual(ctx.exception.reason, "abstract_only")

    def test_pnas_full_fixture_extracts_body_sections_from_real_html(self) -> None:
        markdown, info = self._extract_sample_markdown(PNAS_SAMPLE)

        self.assertIn("# The kinetics of SARS-CoV-2 infection based on a human challenge study", markdown)
        self.assertIn("## Significance", markdown)
        self.assertIn("## Abstract", markdown)
        self.assertIn("Severe acute respiratory syndrome coronavirus 2 (SARS-CoV-2) continues to spread worldwide", markdown)
        self.assertIn("## Methods", markdown)
        self.assertIn("## Mathematical Models", markdown)
        self.assertIn("### Data", markdown)
        self.assertIn("### The Relationship between Total and Infectious Virus", markdown)
        self.assertIn("**Equation 1.**", markdown)
        self.assertIn("$$", markdown)
        self.assertIn("**Equation 2.**", markdown)
        self.assertIn("![Figure 1](", markdown)
        self.assertIn("**Figure 1.**", markdown)
        self.assertLess(markdown.index("## Significance"), markdown.index("## Abstract"))
        self.assertLess(markdown.index("## Abstract"), markdown.index("## Methods"))
        diagnostics = info["availability_diagnostics"]
        self.assertTrue(diagnostics["accepted"])
        self.assertEqual(diagnostics["content_kind"], "fulltext")

    def test_pnas_full_fixture_omits_real_page_collateral_noise(self) -> None:
        """rule: rule-filter-publisher-ui-noise"""
        markdown, _ = self._extract_sample_markdown(PNAS_SAMPLE)

        self.assertNotIn("Recommended articles", markdown)
        self.assertNotIn("Download PDF", markdown)
        self.assertNotIn("Request permissions", markdown)
        self.assertNotIn("Google Scholar", markdown)
        self.assertNotIn("Sign up for PNAS alerts", markdown)
        self.assertNotIn("Learn More", markdown)
        self.assertNotIn("Vi=fV=BVh", markdown)
        self.assertNotIn("dTdt=", markdown)

    def test_pnas_full_fixture_keeps_data_availability_and_renders_table_markdown(self) -> None:
        markdown, _ = self._extract_sample_markdown(PNAS_SAMPLE)

        self.assertIn("## Data, Materials, and Software Availability", markdown)
        self.assertEqual(markdown.count("## Data, Materials, and Software Availability"), 1)
        self.assertNotIn("#### Data, Materials, and Software Availability", markdown)
        self.assertIn("**Table 1.** Estimated population parameters for the DDRCM with humoral immune response", markdown)
        self.assertRegex(markdown, r"\| Parameter\s+\| Description\s+\| Fixed Effects \(R\.S\.E\., %\)\s+\|")
        self.assertNotIn("**Figure** Estimated population parameters for the DDRCM with humoral immune response", markdown)
        self.assertLess(markdown.index("**Figure 4.**"), markdown.index("**Table 1.**"))

    def test_pnas_collateral_data_availability_fixture_is_not_duplicated(self) -> None:
        markdown, info = self._extract_fixture_markdown(
            PNAS_COLLATERAL_FIXTURE,
            "https://www.pnas.org/doi/full/10.1073/pnas.2309123120",
            "pnas",
            "10.1073/pnas.2309123120",
        )

        self.assertIn(info["container_tag"], {"article", "main", "body"})
        self.assertEqual(markdown.count("## Data, Materials, and Software Availability"), 1)
        self.assertEqual(markdown.count("## Significance"), 1)
        self.assertEqual(markdown.count("## Abstract"), 1)
        self.assertNotIn("#### Data, Materials, and Software Availability", markdown)
        self.assertNotIn("community water fluoridation", markdown.lower())
        self.assertNotIn("tattoo ink accumulation", markdown.lower())
        self.assertEqual(
            [section["heading"] for section in info["abstract_sections"]],
            ["Significance", "Abstract"],
        )

    def test_wiley_full_fixture_extracts_body_sections_from_real_html(self) -> None:
        markdown, info = self._extract_sample_markdown(WILEY_SAMPLE)

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
        markdown, _ = self._extract_sample_markdown(WILEY_SAMPLE)

        self.assertNotIn("Publication History", markdown)
        self.assertNotIn("Article navigation and tools", markdown)
        self.assertNotIn("Download PDF", markdown)
        self.assertNotIn("About Wiley Online Library", markdown)

    def test_wiley_full_fixture_keeps_data_availability_but_filters_other_back_matter(self) -> None:
        markdown, _ = self._extract_sample_markdown(WILEY_SAMPLE)

        self.assertIn("## DATA AVAILABILITY STATEMENT", markdown)
        self.assertNotIn("## CONFLICT OF INTEREST", markdown)
        self.assertNotIn("## Supporting Information", markdown)

    def test_wiley_formula_image_fallbacks_are_preserved(self) -> None:
        markdown, _ = self._extract_fixture_markdown(
            golden_criteria_asset("10.1111/gcb.15322", "original.html"),
            "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.15322",
            "wiley",
            "10.1111/gcb.15322",
        )

        self.assertIn("**Equation 1.**", markdown)
        self.assertIn("![Formula](/cms/asset/", markdown)
        self.assertIn("gcb15322-math-0001.png", markdown)
        self.assertNotIn("**Equation 1.**![Formula]", markdown)

    def test_wiley_real_fixture_does_not_count_research_funding_as_body(self) -> None:
        fixture_path = golden_criteria_asset("10.1111/gcb.15322", "original.html")
        html = fixture_path.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("research funding", html.casefold())

        markdown, info = self._extract_fixture_markdown(
            fixture_path,
            "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.15322",
            "wiley",
            "10.1111/gcb.15322",
        )
        metrics = body_metrics(
            markdown,
            {"doi": "10.1111/gcb.15322"},
            section_hints=info.get("section_hints"),
            noise_profile="wiley",
        )

        self.assertNotIn("research funding", markdown.casefold())
        self.assertNotIn("research funding", metrics["text"].casefold())

    def test_science_real_fixture_does_not_leak_competing_interests_modal(self) -> None:
        fixture_path = golden_criteria_asset("10.1126/sciadv.abg9690", "original.html")
        html = fixture_path.read_text(encoding="utf-8", errors="ignore")
        self.assertIn("statement of competing interests", html.casefold())

        markdown, info = self._extract_fixture_markdown(
            fixture_path,
            "https://www.science.org/doi/10.1126/sciadv.abg9690",
            "science",
            "10.1126/sciadv.abg9690",
        )
        metrics = body_metrics(
            markdown,
            {"doi": "10.1126/sciadv.abg9690"},
            section_hints=info.get("section_hints"),
            noise_profile="science",
        )

        self.assertNotIn("statement of competing interests", markdown.casefold())
        self.assertNotIn("statement of competing interests", metrics["text"].casefold())

    def test_wiley_inline_mathml_with_fallback_span_does_not_emit_placeholder(self) -> None:
        soup = BeautifulSoup(
            """
            <div class="article-section__content">
              <p>
                Intro text.
                <span class="fallback__mathEquation" data-altimg="/cms/asset/example-math-0002.png"></span>
                <math display="inline">
                  <semantics>
                    <mrow><mi>β</mi></mrow>
                  </semantics>
                </math>
                <sub>FVC</sub>
                represents the linear effect of FVC on d(LST)/dt.
              </p>
            </div>
            """,
            "html.parser",
        )

        container = soup.select_one(".article-section__content")
        self.assertIsNotNone(container)
        _science_pnas_html._normalize_display_formula_blocks(container)
        _science_pnas_html._normalize_inline_math_nodes(container)
        _science_pnas_html._normalize_non_table_inline_blocks(container)

        rendered = str(container)
        self.assertNotIn("[Formula unavailable]", rendered)
        self.assertIn("$\\beta$", rendered)
        self.assertIn("represents the linear effect of FVC on d(LST)/dt.", rendered)

    def test_wiley_display_formula_can_fall_back_to_alt_image_span(self) -> None:
        soup = BeautifulSoup(
            """
            <div class="article-section__content">
              <p>
                <span class="fallback__mathEquation" data-altimg="/cms/asset/example-math-0001.png"></span>
                <math display="block">
                  <semantics>
                    <mrow />
                  </semantics>
                </math>
              </p>
            </div>
            """,
            "html.parser",
        )

        container = soup.select_one(".article-section__content")
        self.assertIsNotNone(container)
        _science_pnas_html._normalize_display_formula_blocks(container)

        rendered = str(container)
        self.assertNotIn("[Formula unavailable]", rendered)
        self.assertIn("![Formula](/cms/asset/example-math-0001.png)", rendered)

    def test_wiley_references_use_visible_citation_text_not_doi_only(self) -> None:
        """rule: rule-wiley-reference-text"""
        cases = (
            (
                "10.1111/gcb.15322",
                ("Atkinson", "Inter-comparison of four models", "Remote Sensing of Environment"),
            ),
            (
                "10.1111/gcb.16998",
                ("AghaKouchak", "Remote sensing of drought", "Reviews of Geophysics"),
            ),
        )

        for doi, expected_tokens in cases:
            with self.subTest(doi=doi):
                html = golden_criteria_asset(doi, "original.html").read_text(encoding="utf-8")

                references = extract_numbered_references_from_html(html)

                self.assertGreater(len(references), 20)
                for token in expected_tokens:
                    self.assertIn(token, references[0]["raw"])
                self.assertNotEqual(references[0]["raw"], references[0]["doi"])
                self.assertNotIn("Google Scholar", references[0]["raw"])

    def test_wiley_fixture_renders_rule_table_as_markdown_table(self) -> None:
        markdown, _ = self._extract_fixture_markdown(
            golden_criteria_asset("10.1111/cas.16395", "original.html"),
            "https://onlinelibrary.wiley.com/doi/full/10.1111/cas.16395",
            "wiley",
            "10.1111/cas.16395",
        )

        self.assertIn("**Table 1.** AI-SaMD approved as a medical device in the field of oncology in Japan (as of May 2024).", markdown)
        self.assertRegex(
            markdown,
            r"\| Research area\s+\| Approval number\s+\| Product\s+\| Manufacturer\s+\| Target inspection method\s+\| Class\s+\| Year of approval\s+\|",
        )
        self.assertNotIn("Research areaApproval numberProductManufacturerTarget inspection methodClassYear of approval", markdown)

    def test_wiley_multilingual_abstract_keeps_parallel_abstract_sections(self) -> None:
        html = """
        <html>
          <body>
            <article>
              <h1>Test bilingual abstract handling</h1>
              <div id="abstracts">
                <section class="article-section article-section__abstract" lang="en" data-lang="en" id="section-1-en">
                  <h2>Abstract</h2>
                  <div class="lang-container">
                    <a class="lang active" href="#section-1-en" hreflang="en" data-lang-of="en">en</a>
                    <a class="lang" href="#section-2-pt" hreflang="pt" data-lang-of="pt">pt</a>
                  </div>
                  <div class="article-section__content en main">
                    <p>English abstract sentence one. English abstract sentence two. English abstract sentence three. English abstract sentence four. English abstract sentence five.</p>
                  </div>
                </section>
                <section class="article-section article-section__abstract" lang="pt" data-lang="pt" lang-name="Portuguese" id="section-2-pt" style="display: none;">
                  <h2>Resumo</h2>
                  <div class="lang-container">
                    <a class="lang active" href="#section-1-en" hreflang="en" data-lang-of="en">en</a>
                    <a class="lang" href="#section-2-pt" hreflang="pt" data-lang-of="pt">pt</a>
                  </div>
                  <div class="article-section__content pt main">
                    <p>Resumo em portugues com o mesmo conteudo do abstract e deve permanecer como segunda secao de resumo.</p>
                  </div>
                </section>
              </div>
              <section class="article-section article-section__full">
                <h2>1 INTRODUCTION</h2>
                <div class="article-section__content">
                  <p>This introduction paragraph is long enough to be treated as article body prose and should remain in the extracted markdown output for the Wiley article sample.</p>
                  <p>This second introduction paragraph adds more body content so the extractor can clearly separate abstract text from main text without relying on the Portuguese translation block.</p>
                </div>
              </section>
            </article>
          </body>
        </html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://onlinelibrary.wiley.com/doi/full/10.1111/test-bilingual",
            "wiley",
            metadata={"doi": "10.1111/test-bilingual"},
        )

        self.assertIn("## Abstract", markdown)
        self.assertIn("## Resumo", markdown)
        self.assertIn("English abstract sentence one.", markdown)
        self.assertIn("Resumo em portugues com o mesmo conteudo", markdown)
        self.assertIn("This introduction paragraph is long enough", markdown)
        self.assertEqual(markdown.count("Test bilingual abstract handling"), 1)
        main_text_index = markdown.index("## Main Text")
        self.assertGreater(main_text_index, markdown.index("## Resumo"))
        self.assertLess(
            main_text_index,
            markdown.index("This introduction paragraph is long enough"),
        )

    def test_wiley_nested_article_prefers_language_scoped_article_root(self) -> None:
        html = """
        <html>
          <body>
            <article>
              <div class="issue-item__body">
                <p>This wrapper synopsis belongs to the issue listing rather than the article body and should not leak into the extracted markdown output.</p>
                <article lang="en">
                  <h1>Nested Wiley Example</h1>
                  <div class="abstract-group metis-abstract">
                    <section class="article-section article-section__abstract" id="section-1-en">
                      <h2>Abstract</h2>
                      <div class="article-section__content en main">
                        <p>Inner article abstract paragraph that should be preserved exactly once in the markdown output.</p>
                      </div>
                    </section>
                  </div>
                  <section class="article-section article-section__full">
                    <h2>1 INTRODUCTION</h2>
                    <div class="article-section__content">
                      <p>The first real body paragraph belongs to the inner article and should remain after the abstract block.</p>
                      <p>The second body paragraph keeps the article comfortably above the body sufficiency threshold.</p>
                    </div>
                  </section>
                </article>
              </div>
            </article>
          </body>
        </html>
        """

        markdown, info = extract_science_pnas_markdown(
            html,
            "https://onlinelibrary.wiley.com/doi/full/10.1111/test-nested",
            "wiley",
            metadata={"doi": "10.1111/test-nested"},
        )

        self.assertIn("# Nested Wiley Example", markdown)
        self.assertEqual(markdown.count("## Abstract"), 1)
        self.assertIn("Inner article abstract paragraph that should be preserved exactly once", markdown)
        self.assertIn("## Main Text", markdown)
        self.assertIn("The first real body paragraph belongs to the inner article", markdown)
        self.assertNotIn("wrapper synopsis belongs to the issue listing", markdown.lower())
        self.assertLess(markdown.index("## Abstract"), markdown.index("## Main Text"))
        self.assertLess(
            markdown.index("## Main Text"),
            markdown.index("The first real body paragraph belongs to the inner article"),
        )
        self.assertEqual(
            [section["heading"] for section in info["abstract_sections"]],
            ["Abstract"],
        )

    def test_science_browser_workflow_does_not_reinject_teaser_before_structured_abstract(self) -> None:
        html = """
        <html>
          <body>
            <main class="article__fulltext">
              <article>
                <h1>The drivers and impacts of Amazon forest degradation</h1>
                <div id="abstracts">
                  <div class="core-container">
                    <section id="editor-abstract" role="doc-abstract">
                      <h2>Losing the Amazon</h2>
                      <div role="paragraph">The teaser summary for this analytical review explains why the Amazon is under mounting pressure and should appear exactly once in the extracted markdown output.</div>
                    </section>
                    <section id="structured-abstract" role="doc-abstract">
                      <h2>Structured Abstract</h2>
                      <section id="abs-sec-1">
                        <h3>BACKGROUND</h3>
                        <div role="paragraph">The structured abstract background paragraph is long enough to survive extraction and should remain between the teaser line and the canonical abstract paragraph.</div>
                      </section>
                    </section>
                    <section id="abstract" role="doc-abstract">
                      <h2>Abstract</h2>
                      <div role="paragraph">The one-paragraph canonical abstract follows here and should remain attached to the Abstract heading instead of being pushed under Main Text.</div>
                    </section>
                  </div>
                </div>
                <section class="article__body">
                  <p>The first true body paragraph begins here and is long enough to trigger the browser workflow full-text checks without needing a body heading.</p>
                  <p>The second body paragraph makes the body boundary obvious so the markdown output can insert Main Text at the correct place.</p>
                </section>
              </article>
            </main>
          </body>
        </html>
        """

        markdown, info = extract_science_pnas_markdown(
            html,
            "https://www.science.org/doi/full/10.1126/science.abp8622",
            "science",
            metadata={"doi": "10.1126/science.abp8622"},
        )

        self.assertEqual(markdown.count("## Losing the Amazon"), 1)
        self.assertEqual(markdown.count("## Structured Abstract"), 1)
        self.assertIn("## Abstract", markdown)
        self.assertIn("The one-paragraph canonical abstract follows here", markdown)
        self.assertIn("The first true body paragraph begins here", markdown)
        self.assertLess(
            markdown.index("The one-paragraph canonical abstract follows here"),
            markdown.index("## Main Text"),
        )
        self.assertLess(
            markdown.index("## Main Text"),
            markdown.index("The first true body paragraph begins here"),
        )
        self.assertEqual(
            [section["heading"] for section in info["abstract_sections"]],
            ["Abstract"],
        )
        self.assertEqual(
            [item["heading"] for item in info["section_hints"][:2]],
            ["Losing the Amazon", "Structured Abstract"],
        )
        self.assertEqual(
            [item["kind"] for item in info["section_hints"][:2]],
            ["body", "body"],
        )

    def test_browser_workflow_preserves_parallel_multilingual_abstract_sections(self) -> None:
        html = """
        <html>
          <body>
            <article>
              <h1>Science Browser Workflow Example</h1>
              <section class="abstract" lang="en">
                <h2>Abstract</h2>
                <p>English abstract sentence one. English abstract sentence two. English abstract sentence three. English abstract sentence four.</p>
              </section>
              <section class="abstract" lang="es" data-lang="es">
                <h2>Resumen</h2>
                <p>Resumen en espanol que debe permanecer como un segundo bloque de resumen.</p>
              </section>
              <section class="article__body">
                <h2>Results</h2>
                <p>This results paragraph is long enough to satisfy browser-workflow availability checks and should remain in the extracted markdown output for the Science test case.</p>
                <p>This second results paragraph keeps the English body content clearly separate from the non-English section that should be removed before markdown extraction happens.</p>
              </section>
            </article>
          </body>
        </html>
        """

        markdown, info = extract_science_pnas_markdown(
            html,
            "https://www.science.org/doi/full/10.1126/test-browser-language-filter",
            "science",
            metadata={"doi": "10.1126/test-browser-language-filter"},
        )

        self.assertIn("## Abstract", markdown)
        self.assertIn("## Resumen", markdown)
        self.assertIn("This results paragraph is long enough", markdown)
        self.assertIn("Resumen en espanol que debe permanecer", markdown)
        self.assertEqual([item["heading"] for item in info["abstract_sections"]], ["Abstract", "Resumen"])
        self.assertTrue(all(item["kind"] == "abstract" for item in info["abstract_sections"]))
        self.assertEqual([item["heading"] for item in info["section_hints"]], ["Results"])
        self.assertEqual([item["kind"] for item in info["section_hints"]], ["body"])

    def test_browser_workflow_returns_section_hints_for_structural_data_availability(self) -> None:
        html = """
        <html>
          <body>
            <article>
              <h1>Science Browser Workflow Example</h1>
              <section class="abstract" lang="en">
                <h2>Abstract</h2>
                <p>English abstract sentence one. English abstract sentence two.</p>
              </section>
              <section class="article__body">
                <h2>Results</h2>
                <p>This results paragraph is long enough to satisfy browser-workflow availability checks and should remain in the extracted markdown output.</p>
              </section>
              <section id="data-availability">
                <h2>Availability Statement</h2>
                <p>Supporting data are archived in a public repository.</p>
              </section>
            </article>
          </body>
        </html>
        """

        _, info = extract_science_pnas_markdown(
            html,
            "https://www.science.org/doi/full/10.1126/test-browser-section-hints",
            "science",
            metadata={"doi": "10.1126/test-browser-section-hints"},
        )

        self.assertEqual(
            [(item["heading"], item["kind"]) for item in info["section_hints"]],
            [("Results", "body"), ("Availability Statement", "data_availability")],
        )

    def test_browser_workflow_returns_section_hints_for_structural_code_availability(self) -> None:
        html = """
        <html>
          <body>
            <article>
              <h1>Science Browser Workflow Example</h1>
              <section class="abstract" lang="en">
                <h2>Abstract</h2>
                <p>English abstract sentence one. English abstract sentence two.</p>
              </section>
              <section class="article__body">
                <h2>Results</h2>
                <p>This results paragraph is long enough to satisfy browser-workflow availability checks and should remain in the extracted markdown output.</p>
              </section>
              <section id="code-availability">
                <h2>Availability Statement</h2>
                <p>Analysis code is archived in a public repository.</p>
              </section>
            </article>
          </body>
        </html>
        """

        markdown, info = extract_science_pnas_markdown(
            html,
            "https://www.science.org/doi/full/10.1126/test-browser-code-section-hints",
            "science",
            metadata={"doi": "10.1126/test-browser-code-section-hints"},
        )

        self.assertIn("## Availability Statement", markdown)
        self.assertEqual(
            [(item["heading"], item["kind"]) for item in info["section_hints"]],
            [("Results", "body"), ("Availability Statement", "code_availability")],
        )

    def test_browser_workflow_keeps_non_english_article_when_no_parallel_language_variant_exists(self) -> None:
        html = """
        <html>
          <body>
            <article>
              <h1>Exemplo de artigo em portugues</h1>
              <section class="abstract" lang="pt">
                <h2>Resumo</h2>
                <p>Resumo em portugues que deve permanecer porque nao existe bloco paralelo em outro idioma.</p>
              </section>
              <section class="article__body" lang="pt">
                <h2>Resultados</h2>
                <p>Este paragrafo em portugues deve permanecer no markdown extraido porque o artigo nao possui variante inglesa concorrente para o mesmo bloco.</p>
                <p>Este segundo paragrafo adiciona corpo suficiente para passar pelas verificacoes de disponibilidade do fluxo browser workflow.</p>
              </section>
            </article>
          </body>
        </html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.science.org/doi/full/10.1126/test-browser-portuguese-only",
            "science",
            metadata={"doi": "10.1126/test-browser-portuguese-only"},
        )

        self.assertIn("# Exemplo de artigo em portugues", markdown)
        self.assertIn("## Resumo", markdown)
        self.assertIn("Resumo em portugues que deve permanecer", markdown)
        self.assertIn("Este paragrafo em portugues deve permanecer", markdown)

    def test_science_perspective_fixture_extracts_fulltext_without_section_headings(self) -> None:
        markdown, info = self._extract_fixture_markdown(
            SCIENCE_PERSPECTIVE_FIXTURE,
            "https://www.science.org/doi/full/10.1126/science.aeg3511",
            "science",
            "10.1126/science.aeg3511",
        )

        self.assertIn(info["container_tag"], {"article", "main"})
        self.assertIn("# Magma plumbing beneath Yellowstone", markdown)
        self.assertIn("Yellowstone is one of the most seismically active areas", markdown)
        self.assertIn("The findings of Cao", markdown)
        self.assertIn("<sup>1–3</sup>", markdown)
        self.assertIn("<sup>6, 7</sup>", markdown)
        self.assertIn("<sup>11, 12</sup>", markdown)
        self.assertNotIn("(*1–3*)", markdown)
        self.assertNotIn("(*6, 7*)", markdown)
        self.assertNotIn("(*11, 12*)", markdown)
        diagnostics = info["availability_diagnostics"]
        self.assertTrue(diagnostics["accepted"])
        self.assertIn("body_sufficient", diagnostics["strong_positive_signals"])
        self.assertIn("aaas_user_entitled", diagnostics["strong_positive_signals"])
        self.assertGreaterEqual(diagnostics["figure_count"], 1)

    def test_science_numeric_citations_become_superscripts_without_touching_numeric_parentheses(self) -> None:
        html = """
        <html>
          <body>
            <main class="article__fulltext">
              <article>
                <h1>Science Citation Regression</h1>
                <section class="article__body">
                  <p>The Yellowstone volcanic system remains one of the most closely observed caldera systems on Earth, and recent geophysical work suggests that magma storage and crustal deformation can be reconciled by tectonic forcing alone <i><a href="#core-collateral-R1" role="doc-biblioref" data-xml-rid="R1">1</a> – <a href="#core-collateral-R3" role="doc-biblioref" data-xml-rid="R3">3</a></i>. We also decompose the NBP from CS76Land since it includes more atmospheric measurement stations (9) during the 1976 to 2020 period.</p>
                  <p>The second paragraph is intentionally long enough to keep the browser-workflow article comfortably above the full-text sufficiency threshold while exercising the inline citation handling codepath for narrative Science prose.</p>
                </section>
              </article>
            </main>
          </body>
        </html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.science.org/doi/full/10.1126/test-citation-regression",
            "science",
            metadata={"doi": "10.1126/test-citation-regression"},
        )

        self.assertIn("<sup>1–3</sup>", markdown)
        self.assertIn("stations (9)", markdown)
        self.assertNotIn("(*1–3*)", markdown)
        self.assertNotIn("<sup>9</sup>", markdown)

    def test_pnas_numeric_biblioref_anchors_become_superscripts(self) -> None:
        html = """
        <html>
          <body>
            <main class="article__fulltext">
              <article>
                <h1>PNAS Citation Regression</h1>
                <section id="abstract" role="doc-abstract">
                  <h2>Abstract</h2>
                  <div role="paragraph">This abstract is long enough to survive extraction and introduces the body with a realistic amount of narrative text for the PNAS browser workflow tests.</div>
                </section>
                <section class="article__body">
                  <h2>Methods</h2>
                  <div role="paragraph">The fitted model follows earlier challenge studies <a href="#core-collateral-r8" role="doc-biblioref" data-xml-rid="r8">8</a>, <a href="#core-collateral-r10" role="doc-biblioref" data-xml-rid="r10">10</a>, <a href="#core-collateral-r11" role="doc-biblioref" data-xml-rid="r11">11</a> and remains numerically stable during estimation.</div>
                  <div role="paragraph">A second long paragraph keeps the extracted document above the body threshold and confirms that numeric bibliography anchors are rendered consistently as superscript citations in the final markdown output.</div>
                </section>
              </article>
            </main>
          </body>
        </html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://www.pnas.org/doi/full/10.1073/pnas.test-citation-regression",
            "pnas",
            metadata={"doi": "10.1073/pnas.test-citation-regression"},
        )

        self.assertIn("<sup>8, 10, 11</sup>", markdown)

    def test_wiley_author_year_bibliography_links_remain_body_text(self) -> None:
        html = """
        <html>
          <body>
            <article lang="en">
              <h1>Wiley Author-Year Regression</h1>
              <div id="abstracts">
                <section class="article-section article-section__abstract" id="section-1-en">
                  <h2>Abstract</h2>
                  <div class="article-section__content en main">
                    <p>This abstract is long enough to survive extraction and provides realistic prose for the Wiley browser workflow regression tests.</p>
                  </div>
                </section>
              </div>
              <section class="article-section article-section__full">
                <h2>1 INTRODUCTION</h2>
                <div class="article-section__content">
                  <p>Global vegetation greening has been widely discussed in the recent literature, including the synthesis by Zhu et al. (<span><a href="#gcb-test-bib-0059" class="bibLink tab-link" data-tab="pane-pcw-references">2016</a></span>), and this author-year reference must remain inline body text rather than becoming a superscript citation.</p>
                  <p>The second paragraph adds enough prose to make the full-text boundary obvious while confirming that bibliography links with four-digit years are preserved as narrative author-year references in Wiley content.</p>
                </div>
              </section>
            </article>
          </body>
        </html>
        """

        markdown, _ = extract_science_pnas_markdown(
            html,
            "https://onlinelibrary.wiley.com/doi/full/10.1111/test-author-year-regression",
            "wiley",
            metadata={"doi": "10.1111/test-author-year-regression"},
        )

        self.assertIn("Zhu et al. (2016)", markdown)
        self.assertNotIn("<sup>2016</sup>", markdown)

    def test_science_adp0212_fixture_splits_display_equations_and_caption_sentences(self) -> None:
        markdown, _ = self._extract_fixture_markdown(
            SCIENCE_ADP0212_FIXTURE,
            "https://www.science.org/doi/full/10.1126/science.adp0212",
            "science",
            "10.1126/science.adp0212",
        )

        self.assertIn("**Equation 1.**", markdown)
        self.assertIn("$$", markdown)
        self.assertIn("where *P* is precipitation", markdown)
        self.assertLess(markdown.index("**Equation 1.**"), markdown.index("where *P* is precipitation"))
        self.assertIn(
            "**Figure 2.** Regional change in daily precipitation variability from 1900 to 2020. Time series",
            markdown,
        )



if __name__ == "__main__":
    unittest.main()
