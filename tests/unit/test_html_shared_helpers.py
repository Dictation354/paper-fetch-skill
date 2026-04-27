from __future__ import annotations

import unittest

from bs4 import BeautifulSoup

from paper_fetch.extraction.html import _assets as html_assets
from paper_fetch.extraction.html import _metadata as html_metadata
from paper_fetch.extraction.html import _runtime as html_runtime
from paper_fetch.extraction.html.formula_rules import (
    formula_image_url_from_node,
    is_display_formula_node,
    looks_like_formula_image,
    mathml_element_from_html_node,
)
from paper_fetch.extraction.html.inline import normalize_html_inline_text
from paper_fetch.http import HttpTransport


class SharedHtmlHelperTests(unittest.TestCase):
    def test_parse_html_metadata_reads_citation_fields(self) -> None:
        html = """
<html>
  <head>
    <meta name="citation_title" content="Example HTML Article" />
    <meta name="citation_author" content="Alice Example" />
    <meta name="citation_author" content="Bob Example" />
    <meta name="citation_doi" content="10.1234/example" />
    <meta name="citation_journal_title" content="Journal of HTML" />
    <meta name="citation_publication_date" content="2026-01-15" />
  </head>
</html>
"""

        metadata = html_metadata.parse_html_metadata(html, "https://example.test/article")

        self.assertEqual(metadata["title"], "Example HTML Article")
        self.assertEqual(metadata["authors"], ["Alice Example", "Bob Example"])
        self.assertEqual(metadata["doi"], "10.1234/example")
        self.assertEqual(metadata["journal_title"], "Journal of HTML")
        self.assertEqual(metadata["published"], "2026-01-15")

    def test_parse_html_metadata_does_not_treat_generic_description_as_abstract(self) -> None:
        html = """
<html>
  <head>
    <meta name="citation_title" content="Amazon deforestation implications in local/regional climate change" />
    <meta name="dc.Description" content="Amazon deforestation implications in local/regional climate change" />
    <meta name="Description" content="Amazon deforestation implications in local/regional climate change" />
    <meta property="og:description" content="Amazon deforestation implications in local/regional climate change" />
  </head>
</html>
"""

        metadata = html_metadata.parse_html_metadata(html, "https://www.pnas.org/doi/full/10.1073/pnas.2317456120")

        self.assertIsNone(metadata["abstract"])

    def test_parse_html_metadata_uses_redirect_stub_lookup_title(self) -> None:
        html = """
<html>
  <head>
    <title>Redirecting</title>
    <meta http-equiv="refresh" content="2; url='/retrieve/articleSelectSinglePerm'" />
  </head>
  <body>
    <input type="hidden" name="redirectURL" value="https%3A%2F%2Fwww.sciencedirect.com%2Fscience%2Farticle%2Fpii%2FS0034425725000525" />
    <script>
      siteCatalyst.pageDataLoad({ articleName : 'Stub Article Title', identifierValue : 'S0034425725000525' });
    </script>
  </body>
</html>
"""

        metadata = html_metadata.parse_html_metadata(html, "https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525")

        self.assertEqual(metadata["title"], "Stub Article Title")
        self.assertEqual(metadata["lookup_title"], "Stub Article Title")
        self.assertEqual(metadata["lookup_redirect_url"], "https://www.sciencedirect.com/science/article/pii/S0034425725000525")
        self.assertEqual(metadata["identifier_value"], "S0034425725000525")

    def test_extract_figure_assets_reads_generic_figure_blocks(self) -> None:
        html = """
<html>
  <body>
    <figure>
      <img src="/fig1.png" alt="Overview figure" />
      <figcaption>Figure 1. Overview figure.</figcaption>
    </figure>
  </body>
</html>
"""

        assets = html_assets.extract_figure_assets(html, "https://example.test/article")

        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["heading"], "Figure 1. Overview figure.")
        self.assertEqual(assets[0]["caption"], "Figure 1. Overview figure.")
        self.assertEqual(assets[0]["url"], "https://example.test/fig1.png")

    def test_extract_supplementary_assets_reads_supported_links(self) -> None:
        html = """
<html>
  <body>
    <a href="/supplement.pdf">Supplementary Data</a>
  </body>
</html>
"""

        assets = html_assets.extract_supplementary_assets(html, "https://example.test/article")

        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["heading"], "Supplementary Data")
        self.assertEqual(assets[0]["url"], "https://example.test/supplement.pdf")

    def test_extract_scoped_html_assets_uses_separate_body_and_supplementary_scopes(self) -> None:
        body_html = """
<html>
  <body>
    <figure>
      <img src="/fig1.png" alt="Overview figure" />
      <figcaption>Figure 1. Overview figure.</figcaption>
    </figure>
  </body>
</html>
"""
        supplementary_html = """
<html>
  <body>
    <a href="/supplement.pdf">Supplementary Data</a>
  </body>
</html>
"""

        assets = html_assets.extract_scoped_html_assets(
            body_html,
            "https://example.test/article",
            asset_profile="all",
            supplementary_html_text=supplementary_html,
        )

        self.assertEqual(
            [(asset["kind"], asset["section"]) for asset in assets],
            [("figure", "body"), ("supplementary", "supplementary")],
        )

    def test_supplementary_response_block_reason_detects_challenge_html(self) -> None:
        body = b"<html><head><title>Just a moment...</title></head><body>Checking your browser before accessing</body></html>"

        reason = html_assets.supplementary_response_block_reason("text/html; charset=utf-8", body)

        self.assertEqual(reason, "cloudflare_challenge")

    def test_figure_download_candidates_prefers_figure_page_full_size_url(self) -> None:
        candidates = html_assets.figure_download_candidates(
            HttpTransport(),
            asset={
                "figure_page_url": "https://example.test/article/figures/1",
                "url": "https://example.test/preview.png",
            },
            user_agent="paper-fetch-test",
            figure_page_fetcher=lambda url: (
                """
<html>
  <head>
    <meta name="twitter:image" content="https://example.test/full.png" />
  </head>
</html>
""",
                url,
            ),
        )

        self.assertEqual(candidates[0], "https://example.test/full.png")

    def test_clean_html_for_extraction_removes_noise_but_keeps_sections(self) -> None:
        html = """
<html>
  <body>
    <nav>Skip to main content</nav>
    <article>
      <h2>Introduction</h2>
      <p>Important body text.</p>
    </article>
  </body>
</html>
"""

        cleaned = html_runtime.clean_html_for_extraction(html)

        self.assertIn("Introduction", cleaned)
        self.assertIn("Important body text.", cleaned)
        self.assertNotIn("Skip to main content", cleaned)

    def test_extract_html_section_hints_reads_structural_data_availability(self) -> None:
        html = """
<html>
  <body>
    <section class="data-availability">
      <h2>Availability Statement</h2>
      <p>Data are archived in a public repository.</p>
    </section>
  </body>
</html>
"""

        hints = html_runtime.extract_html_section_hints(html)

        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0]["heading"], "Availability Statement")
        self.assertEqual(hints[0]["kind"], "data_availability")

    def test_extract_html_section_hints_reads_structural_code_availability(self) -> None:
        html = """
<html>
  <body>
    <section id="code-availability">
      <h2>Availability Statement</h2>
      <p>Analysis code is archived in a public repository.</p>
    </section>
  </body>
</html>
"""

        hints = html_runtime.extract_html_section_hints(html)

        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0]["heading"], "Availability Statement")
        self.assertEqual(hints[0]["kind"], "code_availability")

    def test_extract_article_markdown_preserves_data_availability_section(self) -> None:
        html = """
<html>
  <body>
    <article>
      <h1>Example Article</h1>
      <h2>Results</h2>
      <p>Important body text that remains in the shared markdown output.</p>
      <h2>Data Availability</h2>
      <p>The data are available from the corresponding author on request.</p>
    </article>
  </body>
</html>
"""

        original_trafilatura = html_runtime.trafilatura
        try:
            html_runtime.trafilatura = None
            markdown = html_runtime.extract_article_markdown(html, "https://example.test/article")
        finally:
            html_runtime.trafilatura = original_trafilatura

        self.assertIn("## Results", markdown)
        self.assertIn("## Data Availability", markdown)
        self.assertIn("The data are available from the corresponding author on request.", markdown)

    def test_clean_markdown_pnas_alerts_require_pnas_profile(self) -> None:
        markdown = """
# Article

Sign up for PNAS alerts.

## Results

Important body text.
"""

        generic_cleaned = html_runtime.clean_markdown(markdown)
        pnas_cleaned = html_runtime.clean_markdown(markdown, noise_profile="pnas")

        self.assertIn("Sign up for PNAS alerts.", generic_cleaned)
        self.assertNotIn("Sign up for PNAS alerts.", pnas_cleaned)

    def test_inline_normalization_is_shared_for_body_heading_and_table_text(self) -> None:
        raw_text = "CO <sub> 2 </sub> emission </sup> +"

        self.assertEqual(normalize_html_inline_text("CO <sub> 2 </sub> emissions"), "CO<sub>2</sub> emissions")
        self.assertEqual(normalize_html_inline_text("m <sup> -2 </sup> )", policy="body"), "m<sup>-2</sup>)")
        self.assertEqual(
            normalize_html_inline_text("m <sup> -2 </sup> )", policy="table_cell"),
            "m<sup>-2</sup> )",
        )
        self.assertEqual(normalize_html_inline_text(raw_text, policy="heading"), "CO<sub>2</sub> emission</sup>+")

    def test_formula_rules_detect_mathml_display_and_formula_image_urls(self) -> None:
        soup = BeautifulSoup(
            """
<div class="display-equation" id="eq1">
  <math display="block"><mi>x</mi><mo>=</mo><mn>1</mn></math>
</div>
<span class="inline-equation"><img data-altimg="/article/math-0001.png" alt="Equation image" /></span>
""",
            "html.parser",
        )
        display = soup.select_one(".display-equation")
        image = soup.find("img")

        self.assertTrue(is_display_formula_node(display))
        self.assertIsNotNone(mathml_element_from_html_node(display))
        self.assertEqual(formula_image_url_from_node(image), "/article/math-0001.png")
        self.assertTrue(looks_like_formula_image(image))

    def test_extract_formula_assets_reuses_shared_formula_rules(self) -> None:
        html = """
<html>
  <body>
    <div class="display-equation" id="Eq1">
      <img data-altimg="/asset/equation-1.png" alt="Formula" />
    </div>
  </body>
</html>
"""

        assets = html_assets.extract_formula_assets(html, "https://example.test/article")

        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["kind"], "formula")
        self.assertEqual(assets[0]["heading"], "Eq1")
        self.assertEqual(assets[0]["url"], "https://example.test/asset/equation-1.png")

    def test_clean_markdown_registers_springer_nature_profile(self) -> None:
        markdown = """
# Article

Sign up for alerts

## Results

Important body text.
"""

        generic_cleaned = html_runtime.clean_markdown(markdown)
        springer_cleaned = html_runtime.clean_markdown(markdown, noise_profile="springer_nature")

        self.assertIn("Sign up for alerts", generic_cleaned)
        self.assertNotIn("Sign up for alerts", springer_cleaned)
