from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from bs4 import BeautifulSoup

from paper_fetch.common_patterns import (
    FIGURE_LABEL_PATTERN,
    TABLE_LABEL_PATTERN,
    is_extended_data_prefix,
    table_label_prefix_for_match,
)
from paper_fetch.extraction.html import assets as html_assets
from paper_fetch.extraction.html import _metadata as html_metadata
from paper_fetch.extraction.html import _runtime as html_runtime
from paper_fetch.extraction.html import shared as html_shared
from paper_fetch.extraction.html.cleanup_policy import classify_markdown_cleanup_line
from paper_fetch.extraction.html.formula_rules import (
    GENERIC_FORMULA_CONTAINER_TOKENS,
    GENERIC_DISPLAY_FORMULA_SELECTORS,
    formula_heading_for_image,
    formula_image_url_from_node,
    is_display_formula_node,
    looks_like_formula_image,
)
from paper_fetch.extraction.html.provider_rules import (
    availability_rules_for_provider,
    cleanup_policy_for_profile,
    extraction_cleanup_selectors_for_profile,
    extraction_drop_keywords_for_profile,
    front_matter_contains_tokens_for_profile,
    front_matter_exact_texts_for_profile,
    front_matter_publication_keywords_for_profile,
    markdown_promo_tokens_for_profile,
    provider_display_formula_selectors,
    provider_html_rules,
    provider_supplementary_text_tokens,
)
from paper_fetch.extraction.html.inline import normalize_html_inline_text
from paper_fetch.extraction.markdown_render.figures import is_html_figure_container
from paper_fetch.extraction.html.tables import render_table_markdown
from paper_fetch.http import HttpTransport
from paper_fetch.image_tools import ImageConversionFailure, SourceImageConversion
from paper_fetch.providers._html_section_markdown import (
    render_clean_text_from_html,
    render_container_markdown,
    render_heading_text_from_html,
)
from paper_fetch.providers import _springer_html as springer_html
import paper_fetch.providers._wiley_html as wiley_html
from paper_fetch.providers.atypon_browser_workflow import (
    asset_scopes as atypon_browser_workflow_asset_scopes,
)
from paper_fetch.providers.atypon_browser_workflow import (
    profile as atypon_browser_workflow_profile,
)
from tests.block_fixtures import block_asset
from tests.golden_criteria import golden_criteria_asset, golden_criteria_scenario_asset


class _DelayedAssetTransport(HttpTransport):
    def __init__(self, delays: dict[str, float]) -> None:
        self.delays = delays
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def request(self, method, url, **kwargs):
        del method, kwargs
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(self.delays.get(url, 0.0))
            return {
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": b"\x89PNG\r\n\x1a\n" + f"payload:{url}".encode(),
                "url": url,
            }
        finally:
            with self.lock:
                self.active -= 1


class _StaticAssetTransport(HttpTransport):
    def __init__(self, responses: dict[tuple[str, str], dict[str, object]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, "kwargs": dict(kwargs)})
        response = self.responses[(method, url)]
        return dict(response)


class SharedHtmlHelperTests(unittest.TestCase):
    def test_common_label_patterns_and_extended_data_prefix_helpers(self) -> None:
        self.assertIsNotNone(FIGURE_LABEL_PATTERN.search("see Fig. 2a."))
        self.assertIsNotNone(TABLE_LABEL_PATTERN.search("Table 3 reports values"))
        self.assertTrue(is_extended_data_prefix("Extended Data Table"))
        self.assertEqual(
            table_label_prefix_for_match("extended data table"), "Extended Data Table"
        )
        self.assertEqual(table_label_prefix_for_match("table"), "Table")

    def test_shared_dom_helpers_normalize_common_tag_operations(self) -> None:
        soup = BeautifulSoup(
            """
<article class=" core-container  article ">
  <p>First <b>paragraph</b></p>
  <div><span>Nested</span></div>
</article>
""",
            "html.parser",
        )
        article = soup.find("article")
        assert article is not None

        children = html_shared.direct_child_tags(article)

        self.assertEqual([child.name for child in children], ["p", "div"])
        self.assertEqual(
            html_shared.class_tokens(article), {"core-container", "article"}
        )
        self.assertEqual(html_shared.short_text(article.find("p")), "First paragraph")
        self.assertIs(html_shared.soup_root(article), soup)

        html_shared.append_text_block(article, "Appended text", tag_name="aside")

        appended = article.find("aside")
        self.assertIsNotNone(appended)
        self.assertEqual(appended.get_text(strip=True), "Appended text")

    def test_shared_payload_helpers_unescape_html_snippets_and_detect_images(
        self,
    ) -> None:
        body = b"<html><head><title>Sign&nbsp;in</title></head><body>A &amp; B</body></html>"

        self.assertEqual(html_shared.html_title_snippet(body), "Sign in")
        self.assertEqual(html_shared.html_text_snippet(body), "Sign in A & B")
        self.assertEqual(
            html_shared.image_magic_type(b"\x89PNG\r\n\x1a\npayload"), "image/png"
        )

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

        metadata = html_metadata.parse_html_metadata(
            html, "https://example.test/article"
        )

        self.assertEqual(metadata["title"], "Example HTML Article")
        self.assertEqual(metadata["authors"], ["Alice Example", "Bob Example"])
        self.assertEqual(metadata["doi"], "10.1234/example")
        self.assertEqual(metadata["journal_title"], "Journal of HTML")
        self.assertEqual(metadata["published"], "2026-01-15")

    def test_parse_html_metadata_does_not_treat_generic_description_as_abstract(
        self,
    ) -> None:
        """rule: rule-generic-metadata-boundaries"""
        html = golden_criteria_scenario_asset(
            "generic_metadata_boundaries", "generic_description.html"
        ).read_text(encoding="utf-8")

        metadata = html_metadata.parse_html_metadata(
            html, "https://www.pnas.org/doi/full/10.1073/pnas.2317456120"
        )

        self.assertIsNone(metadata["abstract"])

    def test_parse_html_metadata_uses_redirect_stub_lookup_title(self) -> None:
        """rule: rule-generic-metadata-boundaries"""
        html = golden_criteria_scenario_asset(
            "generic_metadata_boundaries", "redirect_stub.html"
        ).read_text(encoding="utf-8")

        metadata = html_metadata.parse_html_metadata(
            html, "https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525"
        )

        self.assertEqual(metadata["title"], "Stub Article Title")
        self.assertEqual(metadata["lookup_title"], "Stub Article Title")
        self.assertEqual(
            metadata["lookup_redirect_url"],
            "https://www.sciencedirect.com/science/article/pii/S0034425725000525",
        )
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

    def test_extract_figure_assets_reads_silverchair_figure_sections(self) -> None:
        html = """
<html>
  <body>
    <div data-content-id="btaa823-f4" class="fig fig-section js-fig-section">
      <div class="graphic-wrap">
        <img class="content-image" src="/content/m_btaa823f4.jpeg" alt="Basic TM on abstracts and full-texts. Equation 1." />
        <div class="graphic-bottom">
          <div class="label fig-label">Fig. 4.</div>
          <div class="caption fig-caption">
            <p>Basic TM on abstracts and full-texts. The performance was calculated by Equation 1.</p>
          </div>
        </div>
      </div>
    </div>
  </body>
</html>
"""

        assets = html_assets.extract_figure_assets(
            html, "https://academic.oup.com/article"
        )

        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["kind"], "figure")
        self.assertEqual(assets[0]["heading"], "Fig. 4.")
        self.assertIn("Basic TM on abstracts and full-texts", assets[0]["caption"])
        self.assertEqual(
            assets[0]["url"], "https://academic.oup.com/content/m_btaa823f4.jpeg"
        )

    def test_extract_figure_assets_reads_silverchair_view_large_page(self) -> None:
        preview_url = (
            "https://acs.silverchair-cdn.com/acs/content_public/journal/"
            "acsodf/9/33/m_ao4c03987_0001.png?Expires=1"
        )
        html = f"""
        <div data-id="fig1" class="fig fig-section">
          <a class="fig-link"
             href="/view-large/figure/165496527/ao4c03987_0001.tif">
            <img class="content-image" src="{preview_url}" />
          </a>
          <a class="fig-view-orig"
             aria-label="View large Figure 1."
             href="/view-large/figure/165496527/ao4c03987_0001.tif">
            View Large
          </a>
          <div class="fig-label">Figure 1</div>
          <div class="fig-caption">Benzimidazole-based drug molecules.</div>
        </div>
        """

        assets = html_assets.extract_figure_assets(
            html,
            "https://pubs.acs.org/acsodf/article/example",
        )

        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["url"], preview_url)
        self.assertEqual(assets[0]["preview_url"], preview_url)
        self.assertNotIn("full_size_url", assets[0])
        self.assertEqual(
            assets[0]["figure_page_url"],
            "https://pubs.acs.org/view-large/figure/165496527/ao4c03987_0001.tif",
        )

    def test_silverchair_figure_section_images_are_not_formula_assets(self) -> None:
        html = """
<html>
  <body>
    <div data-content-id="btaa823-f4" class="fig fig-section js-fig-section">
      <div class="graphic-wrap">
        <img class="content-image" src="/content/m_btaa823f4.jpeg" alt="Basic TM on abstracts and full-texts. Equation 1." />
        <div class="graphic-bottom">
          <div class="label fig-label">Fig. 4.</div>
          <div class="caption fig-caption">Basic TM on abstracts and full-texts.</div>
        </div>
      </div>
    </div>
  </body>
</html>
"""

        formula_assets = html_assets.extract_formula_assets(
            html,
            "https://academic.oup.com/article",
        )
        scoped_assets = html_assets.extract_scoped_html_assets(
            html,
            "https://academic.oup.com/article",
            asset_profile="body",
        )

        self.assertEqual(formula_assets, [])
        self.assertEqual([asset["kind"] for asset in scoped_assets], ["figure"])

    def test_pnas_caption_formula_image_is_not_a_figure_asset(self) -> None:
        html = """
<html>
  <body>
    <figure id="F2">
      <div class="graphic">
        <img src="/cms/asset/main/assets/graphic/zpq9990969600002.jpeg" alt="Figure 2" />
      </div>
      <figcaption>
        <span class="label">Figure 2.</span>
        Statistical analysis.
        <div class="display-formula">
          <div class="equation" role="math">
            <div class="inner">
              <img src="/cms/asset/formula/assets/graphic/zpq01009-6960-m02.jpeg" />
            </div>
          </div>
        </div>
        where n = 86.
      </figcaption>
    </figure>
  </body>
</html>
"""

        figure_assets = html_assets.extract_figure_assets(
            html,
            "https://www.pnas.org/doi/full/10.1073/pnas.0810156106",
        )
        formula_assets = html_assets.extract_formula_assets(
            html,
            "https://www.pnas.org/doi/full/10.1073/pnas.0810156106",
            noise_profile="pnas",
        )
        scoped_assets = html_assets.extract_scoped_html_assets(
            html,
            "https://www.pnas.org/doi/full/10.1073/pnas.0810156106",
            asset_profile="body",
            noise_profile="pnas",
        )

        self.assertEqual(len(figure_assets), 1)
        self.assertEqual(figure_assets[0]["kind"], "figure")
        self.assertIn("zpq9990969600002.jpeg", figure_assets[0]["url"])
        self.assertNotIn("zpq01009-6960-m02.jpeg", figure_assets[0]["url"])
        self.assertEqual(len(formula_assets), 1)
        self.assertEqual(formula_assets[0]["kind"], "formula")
        self.assertIn("zpq01009-6960-m02.jpeg", formula_assets[0]["url"])
        self.assertEqual(
            [asset["kind"] for asset in scoped_assets], ["figure", "formula"]
        )

    def test_scoped_assets_prefer_formula_when_figure_reuses_formula_url(self) -> None:
        html = """
<html>
  <body>
    <figure id="F1">
      <img src="/cms/asset/shared/assets/graphic/zpq01009-6960-m01.jpeg" alt="Figure 1" />
      <figcaption>Figure 1. Reused equation artwork.</figcaption>
    </figure>
    <div class="display-formula">
      <div class="equation" role="math">
        <img src="/cms/asset/shared/assets/graphic/zpq01009-6960-m01.jpeg" />
      </div>
    </div>
  </body>
</html>
"""

        scoped_assets = html_assets.extract_scoped_html_assets(
            html,
            "https://www.pnas.org/doi/full/10.1073/pnas.0810156106",
            asset_profile="body",
            noise_profile="pnas",
        )

        self.assertEqual(len(scoped_assets), 1)
        self.assertEqual(scoped_assets[0]["kind"], "formula")
        self.assertIn("zpq01009-6960-m01.jpeg", scoped_assets[0]["url"])

    def test_shared_figure_container_rules_do_not_promote_article_wrappers(
        self,
    ) -> None:
        soup = BeautifulSoup(
            """
<article id="html-foods-10-01757">
  <div id="article-contents">
    <section id="sec2-foods-10-01757">
      <h2>2. Materials</h2>
      <p>Body text.</p>
      <img src="/foods-10-01757-g001.png" alt="Figure 1" />
    </section>
  </div>
</article>
<div id="itemFullTextId" class="articleBody">
  <div id="section-future" class="articleSection">
    <h2>Future Directions</h2>
    <div class="image">
      <a class="media-link"
         href="/docserver/fulltext/energy/38/1/eg380001.f1.gif"
         id="/content/figure/10.1146/example.f1">
        <img src="/docserver/ahah/fulltext/energy/38/1/eg380001.f1_thmb.gif" alt="Figure 1" />
      </a>
    </div>
  </div>
</div>
""",
            "html.parser",
        )

        self.assertFalse(is_html_figure_container(soup.select_one("article")))
        self.assertFalse(is_html_figure_container(soup.select_one("#article-contents")))
        self.assertFalse(
            is_html_figure_container(soup.select_one("#sec2-foods-10-01757"))
        )
        self.assertFalse(is_html_figure_container(soup.select_one("#itemFullTextId")))
        self.assertFalse(is_html_figure_container(soup.select_one("#section-future")))
        self.assertFalse(is_html_figure_container(soup.select_one("a.media-link")))

    def test_silverchair_figure_container_rules_remain_explicit(self) -> None:
        soup = BeautifulSoup(
            """
<div data-content-id="btaa823-f4" class="fig fig-section js-fig-section">
  <div class="graphic-wrap">
    <img class="content-image" src="/content/m_btaa823f4.jpeg" alt="Calculated by Equation 1." />
    <div class="graphic-bottom">
      <div class="label fig-label">Fig. 4.</div>
      <div class="caption fig-caption">Caption text.</div>
    </div>
  </div>
</div>
""",
            "html.parser",
        )
        figure = soup.select_one(".fig-section")
        graphic = soup.select_one(".graphic-wrap")
        image = soup.select_one("img")

        self.assertTrue(is_html_figure_container(figure))
        self.assertTrue(is_html_figure_container(graphic))
        self.assertFalse(looks_like_formula_image(image))

    def test_explicit_generic_figure_class_still_renders_as_figure(self) -> None:
        soup = BeautifulSoup(
            """
<div class="figure figure-full" id="fig1">
  <a href="/large.gif"><img src="/small.gif" alt="System overview" /></a>
  <div class="figcaption"><span class="title">Fig. 1.</span> Example system overview.</div>
</div>
<div class="figure-links-panel">
  <a href="/figures/1"><img src="/thumbnail.gif" alt="Figure link" /></a>
</div>
""",
            "html.parser",
        )

        self.assertTrue(is_html_figure_container(soup.select_one(".figure-full")))
        self.assertFalse(
            is_html_figure_container(soup.select_one(".figure-links-panel"))
        )

    def test_figure_context_precedes_formula_image_url_signal(self) -> None:
        soup = BeautifulSoup(
            """
<figure id="fig-equation-overview">
  <img src="/images/system-equation-overview.png" alt="Calculated by Equation 3." />
  <figcaption>Figure 1. System overview with equation labels.</figcaption>
</figure>
""",
            "html.parser",
        )
        html = str(soup)

        self.assertFalse(looks_like_formula_image(soup.select_one("img")))
        self.assertEqual(
            [
                asset["kind"]
                for asset in html_assets.extract_figure_assets(
                    html, "https://example.test/article"
                )
            ],
            ["figure"],
        )
        self.assertEqual(
            html_assets.extract_formula_assets(html, "https://example.test/article"),
            [],
        )
        self.assertEqual(
            [
                asset["kind"]
                for asset in html_assets.extract_scoped_html_assets(
                    html,
                    "https://example.test/article",
                    asset_profile="body",
                )
            ],
            ["figure"],
        )

    def test_extract_figure_assets_reads_multi_image_multi_caption_figure_blocks(
        self,
    ) -> None:
        html = """
<html>
  <body>
    <figure id="F10">
      <div><img src="/fig9.png" id="F10.g1" alt="Refer to caption" /></div>
      <figcaption>Figure 9. First result.</figcaption>
      <div><img src="/fig10.png" id="F10.g2" alt="Refer to caption" /></div>
      <figcaption>Figure 10. Second result.</figcaption>
    </figure>
  </body>
</html>
"""

        assets = html_assets.extract_figure_assets(html, "https://example.test/article")

        self.assertEqual(len(assets), 2)
        self.assertEqual(
            [
                (asset["caption"], asset["url"], asset["dom_id"], asset["image_id"])
                for asset in assets
            ],
            [
                (
                    "Figure 9. First result.",
                    "https://example.test/fig9.png",
                    "F10",
                    "F10.g1",
                ),
                (
                    "Figure 10. Second result.",
                    "https://example.test/fig10.png",
                    "F10",
                    "F10.g2",
                ),
            ],
        )

    def test_section_renderer_outputs_multi_figcaption_blocks_separately(self) -> None:
        soup = BeautifulSoup(
            """
<article>
  <figure id="F10">
    <img src="/fig9.png" />
    <figcaption>Figure 9. First result.</figcaption>
    <img src="/fig10.png" />
    <figcaption>Figure 10. Second result.</figcaption>
  </figure>
</article>
""",
            "html.parser",
        )
        lines: list[str] = []
        render_container_markdown(
            soup.article, lines, level=2, section_content_selectors=()
        )
        markdown = "\n".join(lines)

        self.assertIn("**Figure 9.** First result.", markdown)
        self.assertIn("**Figure 10.** Second result.", markdown)
        self.assertNotIn("First result. Second result.", markdown)

    def test_extract_supplementary_assets_reads_supported_links(self) -> None:
        html = """
<html>
  <body>
    <a href="/supplement.pdf">Supplementary Data</a>
  </body>
</html>
"""

        assets = html_assets.extract_supplementary_assets(
            html, "https://example.test/article"
        )

        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["heading"], "Supplementary Data")
        self.assertEqual(assets[0]["url"], "https://example.test/supplement.pdf")

    def test_wiley_supplementary_data_attributes_are_provider_owned(self) -> None:
        html = """
<html>
  <body>
    <a href="/doi/suppl/10.1111/example" data-test="supp-info-link" data-track-action="view supplementary info">Open</a>
  </body>
</html>
"""

        self.assertEqual(
            html_assets.extract_supplementary_assets(
                html, "https://example.test/article"
            ),
            [],
        )
        assets = wiley_html.extract_scoped_html_assets(
            "",
            "https://onlinelibrary.wiley.com/doi/full/10.1111/example",
            asset_profile="all",
            supplementary_html_text=html,
        )

        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["heading"], "Open")
        self.assertEqual(
            assets[0]["url"],
            "https://onlinelibrary.wiley.com/doi/suppl/10.1111/example",
        )

    def test_extract_scoped_html_assets_uses_separate_body_and_supplementary_scopes(
        self,
    ) -> None:
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

    def test_wiley_asset_scopes_only_collect_supporting_information_downloads(
        self,
    ) -> None:
        """rule: rule-wiley-supporting-information-assets"""
        source_url = "https://onlinelibrary.wiley.com/doi/full/10.1111/example"
        html_text = """
<html>
  <body>
    <article lang="en">
      <section class="article-section article-section__full">
        <section class="article-section__content">
          <figure class="figure" id="example-fig-0001">
            <a href="/cms/asset/full/example-fig-0001.jpg">
              <img src="/cms/asset/preview/example-fig-0001.png" data-lg-src="/cms/asset/full/example-fig-0001.jpg" alt="Example figure" />
            </a>
            <figcaption>Figure 1. Example figure.</figcaption>
          </figure>
        </section>
      </section>
      <section class="article-section article-section__supporting" data-suppl="/doi/suppl/10.1111/example?onlyLog=true">
        <div class="accordion article-accordion">
          <h2>
            <a class="accordion__control" role="button" aria-controls="example-supInfo-0001" aria-expanded="false">
              <div tabindex="0" class="section__title" id="support-information-section"><span>Supporting Information</span></div>
            </a>
          </h2>
          <div class="accordion__content" role="region" aria-labelledby="support-information-section" id="example-supInfo-0001">
            <table class="support-info__table table article-section__table">
              <tbody>
                <tr>
                  <td headers="article-filename">
                    <a href="/action/downloadSupplement?doi=10.1111%2Fexample&amp;file=example-sup-0001-DataS1.docx">example-sup-0001-DataS1.docx</a>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </article>
  </body>
</html>
"""

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

        self.assertIn("downloadSupplement", supplementary_html)
        self.assertNotIn("downloadSupplement", body_html)
        self.assertEqual(
            [(asset["kind"], asset["section"]) for asset in assets],
            [("figure", "body"), ("supplementary", "supplementary")],
        )
        self.assertEqual(
            assets[1]["url"],
            "https://onlinelibrary.wiley.com/action/downloadSupplement?doi=10.1111%2Fexample&file=example-sup-0001-DataS1.docx",
        )
        self.assertEqual(assets[1]["filename_hint"], "example-sup-0001-DataS1.docx")
        self.assertFalse(
            any(
                "fig-0001" in asset.get("url", "")
                for asset in assets
                if asset["kind"] == "supplementary"
            )
        )

    def test_wiley_real_fixture_supporting_information_only_yields_true_supplementary_asset(
        self,
    ) -> None:
        """rule: rule-wiley-supporting-information-assets"""
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

    def test_download_assets_supplementary_kind_uses_wiley_filename_hint_for_octet_stream(
        self,
    ) -> None:
        supplement_url = (
            "https://onlinelibrary.wiley.com/action/downloadSupplement?"
            "doi=10.1111%2Fgcb.16414&file=gcb16414-sup-0001-FigureS1.docx"
        )

        def opener_requester(opener, url, **kwargs):
            del opener, kwargs
            self.assertEqual(url, supplement_url)
            return {
                "status_code": 200,
                "headers": {"content-type": "application/octet-stream"},
                "body": b"supplementary-docx",
                "url": "https://onlinelibrary.wiley.com/action/downloadSupplement",
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_assets(
                html_assets.SUPPLEMENTARY_KIND,
                HttpTransport(),
                article_id="10.1111/gcb.16414",
                assets=[
                    {
                        "kind": "supplementary",
                        "heading": "gcb16414-sup-0001-FigureS1.docx",
                        "url": supplement_url,
                        "section": "supplementary",
                        "filename_hint": "gcb16414-sup-0001-FigureS1.docx",
                    }
                ],
                output_dir=Path(tmpdir),
                user_agent="paper-fetch-test",
                asset_profile="all",
                cookie_opener_builder=lambda *args, **kwargs: object(),
                opener_requester=opener_requester,
            )

        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(
            Path(result["assets"][0]["path"]).name, "gcb16414-sup-0001-FigureS1.docx"
        )

    def test_download_assets_supplementary_kind_routes_source_data_into_subdirectory(
        self,
    ) -> None:
        """rule: rule-springer-supplementary-scope"""
        responses = {
            "https://example.test/supplement.pdf": {
                "status_code": 200,
                "headers": {"content-type": "application/pdf"},
                "body": b"supplementary-pdf",
                "url": "https://example.test/supplement.pdf",
            },
            "https://example.test/source-data.csv": {
                "status_code": 200,
                "headers": {"content-type": "text/plain"},
                "body": b"source-data",
                "url": "https://example.test/source-data.csv",
            },
        }

        def opener_requester(opener, url, **kwargs):
            del opener, kwargs
            return responses[url]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_assets(
                html_assets.SUPPLEMENTARY_KIND,
                HttpTransport(),
                article_id="10.1000/example",
                assets=[
                    {
                        "kind": "supplementary",
                        "heading": "Supplementary Information",
                        "url": "https://example.test/supplement.pdf",
                        "section": "supplementary",
                    },
                    {
                        "kind": "supplementary",
                        "heading": "Source Data Fig. 1",
                        "url": "https://example.test/source-data.csv",
                        "section": "supplementary",
                        "asset_kind": "source_data",
                    },
                ],
                output_dir=Path(tmpdir),
                user_agent="paper-fetch-test",
                asset_profile="all",
                cookie_opener_builder=lambda *args, **kwargs: object(),
                opener_requester=opener_requester,
            )

            asset_paths = [Path(asset["path"]) for asset in result["assets"]]

            self.assertEqual(result["asset_failures"], [])
            self.assertEqual(asset_paths[0].parent.name, "10.1000_example_assets")
            self.assertEqual(asset_paths[1].parent.name, "source_data")
            self.assertEqual(
                asset_paths[1].parent.parent.name, "10.1000_example_assets"
            )

    def test_download_assets_supplementary_kind_with_only_source_data_creates_only_source_data_subdirectory(
        self,
    ) -> None:
        """rule: rule-springer-supplementary-scope"""

        def opener_requester(opener, url, **kwargs):
            del opener, kwargs
            return {
                "status_code": 200,
                "headers": {"content-type": "text/csv"},
                "body": b"source-data-only",
                "url": url,
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = html_assets.download_assets(
                html_assets.SUPPLEMENTARY_KIND,
                HttpTransport(),
                article_id="10.1000/source-only",
                assets=[
                    {
                        "kind": "supplementary",
                        "heading": "Source Data Fig. 1",
                        "url": "https://example.test/source-data-only.csv",
                        "section": "supplementary",
                        "asset_kind": "source_data",
                    }
                ],
                output_dir=output_dir,
                user_agent="paper-fetch-test",
                asset_profile="all",
                cookie_opener_builder=lambda *args, **kwargs: object(),
                opener_requester=opener_requester,
            )

            asset_root = output_dir / "10.1000_source-only_assets"
            root_entries = sorted(path.name for path in asset_root.iterdir())

            self.assertEqual(result["asset_failures"], [])
            self.assertEqual(
                Path(result["assets"][0]["path"]).parent.name, "source_data"
            )
            self.assertEqual(root_entries, ["source_data"])

    def test_wiley_body_figures_are_not_promoted_to_supplementary_without_supporting_information(
        self,
    ) -> None:
        """rule: rule-wiley-supporting-information-assets
        rule: rule-supplementary-discovery-explicit-scope"""
        body_html = """
<section class="article-section__content">
  <figure class="figure" id="example-fig-0001">
    <a href="/cms/asset/full/example-fig-0001.jpg">
      <img src="/cms/asset/preview/example-fig-0001.png" data-lg-src="/cms/asset/full/example-fig-0001.jpg" alt="Example figure" />
    </a>
    <figcaption>Figure 1. Example figure.</figcaption>
  </figure>
</section>
"""

        assets = wiley_html.extract_scoped_html_assets(
            body_html,
            "https://onlinelibrary.wiley.com/doi/full/10.1111/example",
            asset_profile="all",
            supplementary_html_text="",
        )

        self.assertEqual([asset["kind"] for asset in assets], ["figure"])
        self.assertFalse(any(asset["kind"] == "supplementary" for asset in assets))

    def test_wiley_supplementary_assets_parse_path_and_filename_query(self) -> None:
        supplementary_html = """
<section class="article-section__supporting">
  <a href="/action/track?next=/action/downloadSupplement">Tracking link</a>
  <a href="/action/downloadSupplement?doi=10.1111%2Fexample&amp;download=true">Generic download</a>
  <a href="/action/downloadSupplement?doi=10.1111%2Fexample&amp;attachment=example-sup-0002-DataS2.xlsx">Data S2</a>
  <a href="/action/downloadSupplement?doi=10.1111%2Fexample&amp;filename=example-sup-0003-DataS3.csv">Data S3</a>
  <a href="/action/downloadSupplement?doi=10.1111%2Fexample&amp;download=example-sup-0004-DataS4.zip">Data S4</a>
</section>
"""

        assets = wiley_html.extract_scoped_html_assets(
            "<article></article>",
            "https://onlinelibrary.wiley.com/doi/full/10.1111/example",
            asset_profile="all",
            supplementary_html_text=supplementary_html,
        )

        self.assertEqual(len(assets), 4)
        self.assertEqual(
            assets[0]["url"],
            "https://onlinelibrary.wiley.com/action/downloadSupplement?doi=10.1111%2Fexample&download=true",
        )
        self.assertNotIn("filename_hint", assets[0])
        self.assertEqual(
            assets[1]["url"],
            "https://onlinelibrary.wiley.com/action/downloadSupplement?doi=10.1111%2Fexample&attachment=example-sup-0002-DataS2.xlsx",
        )
        self.assertEqual(assets[1]["filename_hint"], "example-sup-0002-DataS2.xlsx")
        self.assertEqual(assets[2]["filename_hint"], "example-sup-0003-DataS3.csv")
        self.assertEqual(assets[3]["filename_hint"], "example-sup-0004-DataS4.zip")

    def test_extract_scoped_html_assets_empty_supplementary_scope_does_not_scan_body(
        self,
    ) -> None:
        """rule: rule-atypon-browser-workflow-supplementary-sections
        rule: rule-supplementary-discovery-explicit-scope"""
        body_html = """
<html>
  <body>
    <a href="https://example.test/data.csv">Data file, not supplementary material.</a>
  </body>
</html>
"""

        assets = html_assets.extract_scoped_html_assets(
            body_html,
            "https://example.test/article",
            asset_profile="all",
            supplementary_html_text="",
        )

        self.assertFalse(any(asset["kind"] == "supplementary" for asset in assets))

    def test_science_real_fixture_supplementary_comes_only_from_supplementary_section(
        self,
    ) -> None:
        """rule: rule-atypon-browser-workflow-supplementary-sections"""
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

    def test_pnas_real_fixture_supplementary_ignores_body_anchor_to_section(
        self,
    ) -> None:
        """rule: rule-atypon-browser-workflow-supplementary-sections"""
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

    def test_supplementary_response_block_reason_detects_challenge_html(self) -> None:
        body = b"<html><head><title>Just a moment...</title></head><body>Checking your browser before accessing</body></html>"

        reason = html_assets.supplementary_response_block_reason(
            "text/html; charset=utf-8", body
        )

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

    def test_download_assets_figure_kind_converts_eps_source_to_png_and_keeps_original(
        self,
    ) -> None:
        source_url = "https://example.test/images/example-f1.eps"
        full_url = "https://example.test/images/full-example-f1.jpg"
        source_body = b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\n"
        converted_body = b"\x89PNG\r\n\x1a\nconverted"
        transport = _StaticAssetTransport(
            {
                ("GET", source_url): {
                    "status_code": 200,
                    "headers": {"content-type": "application/postscript"},
                    "body": source_body,
                    "url": "/images/example-f1.eps",
                }
            }
        )
        image_document_fetcher = mock.Mock()

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            mock.patch(
                "paper_fetch.extraction.html.assets.download.convert_source_image_response_to_png",
                return_value=SourceImageConversion(
                    body=converted_body,
                    content_type="image/png",
                    source_format="eps",
                    tool="ghostscript",
                ),
            ) as converter,
        ):
            result = html_assets.download_assets(
                html_assets.FIGURE_KIND,
                transport,
                article_id="10.5555/eps-source",
                assets=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "caption": "EPS source",
                        "download_url": source_url,
                        "full_size_url": full_url,
                        "url": full_url,
                        "section": "body",
                    }
                ],
                output_dir=Path(tmpdir),
                user_agent="paper-fetch-test",
                asset_profile="all",
                image_document_fetcher=image_document_fetcher,
            )

            self.assertEqual([call["url"] for call in transport.calls], [source_url])
            image_document_fetcher.assert_not_called()
            converter.assert_called_once()
            self.assertEqual(result["asset_failures"], [])
            self.assertEqual(len(result["assets"]), 1)
            asset = result["assets"][0]
            self.assertEqual(Path(asset["path"]).suffix, ".png")
            self.assertEqual(Path(asset["path"]).read_bytes(), converted_body)
            self.assertEqual(Path(asset["original_source_path"]).suffix, ".eps")
            self.assertEqual(
                Path(asset["original_source_path"]).read_bytes(),
                source_body,
            )
            self.assertEqual(asset["download_url"], source_url)
            self.assertEqual(asset["source_url"], source_url)
            self.assertEqual(asset["download_tier"], "source_converted")
            self.assertEqual(asset["conversion_source_format"], "eps")
            self.assertEqual(asset["conversion_output_format"], "png")
            self.assertEqual(asset["conversion_tool"], "ghostscript")
            self.assertEqual(asset["original_download_url"], source_url)
            self.assertEqual(asset["full_size_url"], full_url)

    def test_download_assets_figure_kind_falls_back_when_source_conversion_fails(
        self,
    ) -> None:
        source_url = "https://example.test/images/example-f1.eps"
        full_url = "https://example.test/images/full-example-f1.png"
        fallback_body = b"\x89PNG\r\n\x1a\nfallback"
        transport = _StaticAssetTransport(
            {
                ("GET", source_url): {
                    "status_code": 200,
                    "headers": {"content-type": "application/postscript"},
                    "body": b"%!PS-Adobe-3.0 EPSF-3.0\n",
                    "url": source_url,
                },
                ("GET", full_url): {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": fallback_body,
                    "url": full_url,
                },
            }
        )

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            mock.patch(
                "paper_fetch.extraction.html.assets.download.convert_source_image_response_to_png",
                side_effect=ImageConversionFailure("missing ghostscript"),
            ) as converter,
        ):
            result = html_assets.download_assets(
                html_assets.FIGURE_KIND,
                transport,
                article_id="10.5555/eps-source-fallback",
                assets=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "caption": "EPS source",
                        "download_url": source_url,
                        "full_size_url": full_url,
                        "url": full_url,
                        "section": "body",
                    }
                ],
                output_dir=Path(tmpdir),
                user_agent="paper-fetch-test",
                asset_profile="all",
            )

            self.assertEqual(
                [call["url"] for call in transport.calls],
                [source_url, full_url],
            )
            converter.assert_called_once()
            self.assertEqual(result["asset_failures"], [])
            self.assertEqual(len(result["assets"]), 1)
            asset = result["assets"][0]
            self.assertEqual(asset["download_url"], full_url)
            self.assertEqual(asset["download_tier"], "full_size")
            self.assertEqual(asset["provenance"], ["conversion_degraded"])
            self.assertNotIn("original_source_path", asset)
            self.assertEqual(Path(asset["path"]).read_bytes(), fallback_body)

    def test_conversion_backend_missing_has_distinct_asset_reason_code(self) -> None:
        source_url = "https://example.test/images/example-f1.eps"
        transport = _StaticAssetTransport(
            {
                ("GET", source_url): {
                    "status_code": 200,
                    "headers": {"content-type": "application/postscript"},
                    "body": b"%!PS-Adobe-3.0 EPSF-3.0\n",
                    "url": source_url,
                }
            }
        )

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            mock.patch(
                "paper_fetch.extraction.html.assets.download.convert_source_image_response_to_png",
                side_effect=ImageConversionFailure(
                    "missing ghostscript",
                    reason_code="image_conversion_backend_missing",
                ),
            ),
        ):
            result = html_assets.download_assets(
                html_assets.FIGURE_KIND,
                transport,
                article_id="10.5555/eps-source-missing-backend",
                assets=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "caption": "EPS source",
                        "download_url": source_url,
                        "url": source_url,
                        "section": "body",
                    }
                ],
                output_dir=Path(tmpdir),
                user_agent="paper-fetch-test",
                asset_profile="all",
            )

        self.assertEqual(result["assets"], [])
        self.assertEqual(len(result["asset_failures"]), 1)
        self.assertEqual(
            result["asset_failures"][0]["reason"],
            "image_conversion_backend_missing: missing ghostscript",
        )

    def test_download_assets_figure_kind_resolves_http_candidates_in_parallel_but_writes_in_order(
        self,
    ) -> None:
        urls = [f"https://example.test/fig{i}.png" for i in range(4)]
        transport = _DelayedAssetTransport({url: 0.05 for url in urls})
        assets = [
            {
                "kind": "figure",
                "heading": f"Figure {index}",
                "caption": "",
                "url": url,
                "section": "body",
            }
            for index, url in enumerate(urls)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_assets(
                html_assets.FIGURE_KIND,
                transport,
                article_id="10.5555/parallel",
                assets=assets,
                output_dir=Path(tmpdir),
                user_agent="paper-fetch-test",
                asset_profile="all",
            )

        self.assertGreater(transport.max_active, 1)
        self.assertEqual(
            [asset["heading"] for asset in result["assets"]],
            [asset["heading"] for asset in assets],
        )
        self.assertEqual(result["asset_failures"], [])

    def test_download_assets_figure_kind_respects_explicit_concurrency_limit(
        self,
    ) -> None:
        urls = [f"https://example.test/serial-fig{i}.png" for i in range(3)]
        transport = _DelayedAssetTransport({url: 0.01 for url in urls})
        assets = [
            {
                "kind": "figure",
                "heading": f"Figure {index}",
                "caption": "",
                "url": url,
                "section": "body",
            }
            for index, url in enumerate(urls)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_assets(
                html_assets.FIGURE_KIND,
                transport,
                article_id="10.5555/serial",
                assets=assets,
                output_dir=Path(tmpdir),
                user_agent="paper-fetch-test",
                asset_profile="all",
                asset_download_concurrency=1,
            )

        self.assertEqual(transport.max_active, 1)
        self.assertEqual(
            [asset["heading"] for asset in result["assets"]],
            [asset["heading"] for asset in assets],
        )

    def test_download_assets_supplementary_kind_resolves_files_in_parallel_but_writes_in_order(
        self,
    ) -> None:
        urls = [f"https://example.test/supp{i}.pdf" for i in range(4)]
        state = {"active": 0, "max_active": 0}
        lock = threading.Lock()

        def opener_requester(opener, url, **kwargs):
            del opener, kwargs
            with lock:
                state["active"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
            try:
                time.sleep(0.05)
                return {
                    "status_code": 200,
                    "headers": {"content-type": "application/pdf"},
                    "body": f"payload:{url}".encode(),
                    "url": url,
                }
            finally:
                with lock:
                    state["active"] -= 1

        assets = [
            {
                "kind": "supplementary",
                "heading": f"Supplement {index}",
                "url": url,
                "section": "supplementary",
            }
            for index, url in enumerate(urls)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_assets(
                html_assets.SUPPLEMENTARY_KIND,
                HttpTransport(),
                article_id="10.5555/parallel",
                assets=assets,
                output_dir=Path(tmpdir),
                user_agent="paper-fetch-test",
                asset_profile="all",
                cookie_opener_builder=lambda *args, **kwargs: object(),
                opener_requester=opener_requester,
            )

        self.assertGreater(state["max_active"], 1)
        self.assertEqual(
            [asset["heading"] for asset in result["assets"]],
            [asset["heading"] for asset in assets],
        )
        self.assertEqual(result["asset_failures"], [])

    def test_download_assets_supplementary_kind_respects_explicit_concurrency_limit(
        self,
    ) -> None:
        urls = [f"https://example.test/serial-supp{i}.pdf" for i in range(3)]
        state = {"active": 0, "max_active": 0}
        lock = threading.Lock()

        def opener_requester(opener, url, **kwargs):
            del opener, kwargs
            with lock:
                state["active"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
            try:
                time.sleep(0.01)
                return {
                    "status_code": 200,
                    "headers": {"content-type": "application/pdf"},
                    "body": f"payload:{url}".encode(),
                    "url": url,
                }
            finally:
                with lock:
                    state["active"] -= 1

        assets = [
            {
                "kind": "supplementary",
                "heading": f"Supplement {index}",
                "url": url,
                "section": "supplementary",
            }
            for index, url in enumerate(urls)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_assets(
                html_assets.SUPPLEMENTARY_KIND,
                HttpTransport(),
                article_id="10.5555/serial",
                assets=assets,
                output_dir=Path(tmpdir),
                user_agent="paper-fetch-test",
                asset_profile="all",
                cookie_opener_builder=lambda *args, **kwargs: object(),
                opener_requester=opener_requester,
                asset_download_concurrency=1,
            )

        self.assertEqual(state["max_active"], 1)
        self.assertEqual(
            [asset["heading"] for asset in result["assets"]],
            [asset["heading"] for asset in assets],
        )

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

    def test_decode_html_uses_http_charset_after_utf8_fails(self) -> None:
        """rule: rule-html-byte-decoding-and-cleanup-bounds"""
        body = "<html><body><p>Résumé</p></body></html>".encode("iso-8859-1")

        decoded = html_runtime.decode_html(
            body,
            content_type="text/html; charset=iso-8859-1",
        )

        self.assertIn("Résumé", decoded)

    def test_decode_html_reads_meta_charset_after_utf8_fails(self) -> None:
        """rule: rule-html-byte-decoding-and-cleanup-bounds"""
        body = (
            '<html><head><meta charset="windows-1252"></head>'
            "<body><p>“quoted”</p></body></html>"
        ).encode("windows-1252")

        decoded = html_runtime.decode_html(body)

        self.assertIn("“quoted”", decoded)

    def test_decode_html_uses_charset_normalizer_before_replace_fallback(self) -> None:
        """rule: rule-html-byte-decoding-and-cleanup-bounds"""
        body = b"\xffnot-utf8"
        original = html_runtime._charset_normalizer_from_bytes

        class _FakeBest:
            def __str__(self) -> str:
                return "detected text"

        class _FakeMatches:
            def best(self) -> _FakeBest:
                return _FakeBest()

        try:
            html_runtime._charset_normalizer_from_bytes = lambda value: _FakeMatches()
            decoded = html_runtime.decode_html(body)
        finally:
            html_runtime._charset_normalizer_from_bytes = original

        self.assertEqual(decoded, "detected text")

    def test_decode_html_short_circuits_valid_utf8(self) -> None:
        """rule: rule-html-byte-decoding-and-cleanup-bounds"""
        original = html_runtime._charset_normalizer_from_bytes

        def fail_if_called(_: bytes):
            raise AssertionError("charset-normalizer should not run for UTF-8")

        try:
            html_runtime._charset_normalizer_from_bytes = fail_if_called
            decoded = html_runtime.decode_html("naïve UTF-8".encode())
        finally:
            html_runtime._charset_normalizer_from_bytes = original

        self.assertEqual(decoded, "naïve UTF-8")

    def test_no_root_cleanup_skips_per_node_classification(self) -> None:
        """rule: rule-html-byte-decoding-and-cleanup-bounds"""
        html = """
<html>
  <body>
    <script>bad()</script>
    <div><p>Important body text.</p></div>
    <a href="https://orcid.org/0000-0000-0000-0001">ORCID</a>
  </body>
</html>
"""
        original = html_runtime.should_drop_html_element
        calls = 0

        def count_calls(*args, **kwargs):
            nonlocal calls
            calls += 1
            return original(*args, **kwargs)

        try:
            html_runtime.should_drop_html_element = count_calls
            cleaned = html_runtime.clean_html_for_extraction(html)
        finally:
            html_runtime.should_drop_html_element = original

        self.assertEqual(calls, 0)
        self.assertIn("Important body text.", cleaned)
        self.assertNotIn("bad()", cleaned)
        self.assertNotIn("orcid.org", cleaned)

    def test_raw_trafilatura_fallback_skips_large_raw_html(self) -> None:
        """rule: rule-html-byte-decoding-and-cleanup-bounds"""
        calls: list[str] = []

        class _Backend:
            def extract(self, html_text: str, **kwargs) -> str | None:
                del kwargs
                calls.append(html_text)
                return None

        cleaned_html = "<article><p>Fallback body text remains.</p></article>"
        raw_html = "x" * (html_runtime.RAW_TRAFILATURA_FALLBACK_CHAR_LIMIT + 1)

        markdown = html_runtime.extract_article_markdown_from_cleaned_html(
            cleaned_html,
            "https://example.test/article",
            trafilatura_backend=_Backend(),
            raw_html=raw_html,
        )

        self.assertEqual(calls, [cleaned_html])
        self.assertIn("Fallback body text remains.", markdown)

    def test_extract_article_markdown_falls_back_without_trafilatura(self) -> None:
        """rule: rule-html-byte-decoding-and-cleanup-bounds"""
        original_import_module = html_runtime.importlib.import_module
        original_trafilatura = html_runtime.trafilatura

        def import_without_trafilatura(name: str, *args, **kwargs):
            if name == "trafilatura":
                raise ImportError("missing trafilatura")
            return original_import_module(name, *args, **kwargs)

        html = """
<html>
  <body>
    <article>
      <h1>Fallback Article</h1>
      <p>Fallback body text remains readable.</p>
    </article>
  </body>
</html>
"""

        html_runtime._import_trafilatura.cache_clear()
        try:
            html_runtime.trafilatura = html_runtime._TRAFILATURA_UNSET
            with mock.patch.object(
                html_runtime.importlib,
                "import_module",
                side_effect=import_without_trafilatura,
            ):
                markdown = html_runtime.extract_article_markdown(
                    html, "https://example.test/article"
                )
        finally:
            html_runtime.trafilatura = original_trafilatura
            html_runtime._import_trafilatura.cache_clear()

        self.assertIn("# Fallback Article", markdown)
        self.assertIn("Fallback body text remains readable.", markdown)

    def test_orcid_href_pattern_is_module_constant_used_by_pruning(self) -> None:
        """rule: rule-html-byte-decoding-and-cleanup-bounds"""
        self.assertIsNotNone(
            html_runtime.ORCID_HREF_PATTERN.search("https://orcid.org/0000")
        )
        soup = BeautifulSoup(
            '<article><p>Body</p><a href="https://orcid.org/0000">ORCID</a></article>',
            "html.parser",
        )

        html_runtime.prune_html_tree(soup)

        self.assertNotIn("orcid.org", str(soup))

    def test_prune_html_tree_ignores_semantic_attributes_for_noise_tokens(self) -> None:
        soup = BeautifulSoup(
            """
            <article>
              <div
                class="c-article-section__figure"
                id="figure-2"
                data-title="Nature-related increases in PD."
              >
                <figure>
                  <figcaption>Fig. 2: Nature-related increases in PD.</figcaption>
                  <p>Current and additional default probability values.</p>
                </figure>
              </div>
              <div class="related-articles" id="recommended-reading">
                <p>Recommended articles</p>
              </div>
            </article>
            """,
            "html.parser",
        )

        html_runtime.prune_html_tree(soup)

        self.assertIsNotNone(soup.find(id="figure-2"))
        self.assertIsNone(soup.find(id="recommended-reading"))

    def test_extract_html_section_hints_reads_structural_data_availability(
        self,
    ) -> None:
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

    def test_extract_html_section_hints_reads_structural_code_availability(
        self,
    ) -> None:
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
            markdown = html_runtime.extract_article_markdown(
                html, "https://example.test/article"
            )
        finally:
            html_runtime.trafilatura = original_trafilatura

        self.assertIn("## Results", markdown)
        self.assertIn("## Data Availability", markdown)
        self.assertIn(
            "The data are available from the corresponding author on request.", markdown
        )

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

    def test_clean_markdown_learn_more_preserves_body_sentences(self) -> None:
        policy = cleanup_policy_for_profile(None)
        body_sentences = (
            "We aim to learn more efficient representations of the input distribution.",
            "Readers who want to learn more about this dataset can consult the appendix.",
        )
        for sentence in body_sentences:
            with self.subTest(sentence=sentence):
                decision = classify_markdown_cleanup_line(sentence, policy=policy)
                self.assertEqual("keep", decision.action)

        markdown = f"""
# Article

## Results

{body_sentences[1]}

Learn more
"""

        cleaned = html_runtime.clean_markdown(markdown)

        self.assertIn(body_sentences[1], cleaned)
        self.assertNotIn("Learn more", cleaned.splitlines())

    def test_body_metrics_learn_more_preserves_body_sentence(self) -> None:
        body_sentence = "Readers who want to learn more about this dataset can consult the appendix."
        metrics = html_runtime.body_metrics(
            f"# Example\n\n## Results\n\n{body_sentence}\n\nLearn more",
            {"title": "Example", "abstract": ""},
        )

        self.assertIn(body_sentence, metrics["text"])
        self.assertNotIn("Learn more", metrics["text"])

    def test_html_cleanup_rules_merge_generic_and_provider_tokens(self) -> None:
        generic_cleanup = html_runtime.html_cleanup_rules()
        pnas_cleanup = html_runtime.html_cleanup_rules("pnas")

        self.assertIn("toolbar", generic_cleanup.attr_tokens)
        self.assertIn("toolbar", pnas_cleanup.attr_tokens)
        self.assertNotIn("signup-alert-ad", generic_cleanup.attr_tokens)
        self.assertIn("signup-alert-ad", pnas_cleanup.attr_tokens)
        self.assertNotIn(
            "sign up for pnas alerts",
            generic_cleanup.markdown_promo_tokens,
        )
        self.assertIn(
            "sign up for pnas alerts",
            pnas_cleanup.markdown_promo_tokens,
        )

    def test_cleanup_policy_preserves_generic_runtime_tokens(self) -> None:
        policy = cleanup_policy_for_profile(None)

        self.assertEqual(policy.dom_drop_selectors, html_runtime.HTML_DROP_SELECTORS)
        self.assertEqual(policy.dom_exact_texts, html_runtime.HTML_EXACT_NOISE_TEXTS)
        self.assertEqual(policy.dom_prefix_texts, html_runtime.HTML_PREFIX_NOISE_TEXTS)
        self.assertEqual(
            policy.markdown_exact_texts, html_runtime.MARKDOWN_EXACT_NOISE_TEXTS
        )
        self.assertEqual(
            policy.markdown_prefix_texts, html_runtime.MARKDOWN_PREFIX_NOISE_TEXTS
        )
        self.assertEqual(
            policy.markdown_short_tokens, html_runtime.MARKDOWN_SHORT_NOISE_TOKENS
        )

    def test_cleanup_policy_preserves_provider_markdown_promo_tokens(self) -> None:
        pnas_policy = cleanup_policy_for_profile("pnas")

        self.assertEqual(
            markdown_promo_tokens_for_profile("pnas"),
            pnas_policy.markdown_contains_tokens,
        )
        self.assertIn("learn more", pnas_policy.markdown_contains_tokens)
        self.assertIn("sign up for pnas alerts", pnas_policy.markdown_contains_tokens)
        self.assertEqual(
            provider_html_rules("pnas").cleanup.markdown_promo_tokens,
            pnas_policy.provider_markdown_promo_tokens,
        )

    def test_cleanup_policy_preserves_provider_front_matter_tokens(self) -> None:
        science_policy = cleanup_policy_for_profile("science")

        self.assertEqual(
            front_matter_exact_texts_for_profile("science"),
            science_policy.front_matter_exact_texts,
        )
        self.assertEqual(
            front_matter_contains_tokens_for_profile("science"),
            science_policy.front_matter_contains_tokens,
        )
        self.assertEqual(
            front_matter_publication_keywords_for_profile("science"),
            science_policy.front_matter_publication_keywords,
        )

    def test_cleanup_policy_preserves_ieee_extraction_cleanup_selectors(self) -> None:
        ieee_policy = cleanup_policy_for_profile("ieee")

        self.assertEqual(
            extraction_cleanup_selectors_for_profile("ieee"),
            ieee_policy.extraction_cleanup_selectors,
        )
        self.assertEqual(
            extraction_drop_keywords_for_profile("ieee"),
            ieee_policy.extraction_drop_keywords,
        )
        self.assertIn(".document-actions", ieee_policy.extraction_cleanup_selectors)
        self.assertIn(
            "document-actions",
            availability_rules_for_provider("ieee").container_rules.drop_keywords,
        )

    def test_cleanup_policy_exposes_springer_nature_chrome_policy(self) -> None:
        policy = cleanup_policy_for_profile("springer_nature")

        self.assertIn("open access", policy.chrome_section_headings)
        self.assertIn("rights and permissions", policy.chrome_section_headings)
        self.assertIn("article-actions", policy.chrome_attr_tokens)
        self.assertEqual(policy.license_link_hosts, ("creativecommons.org",))
        self.assertEqual(policy.license_link_path_prefixes, ("/licenses/",))
        self.assertEqual(policy.license_word_limit, 180)

    def test_cleanup_policy_exposes_ams_dom_postprocess_selectors(self) -> None:
        policy = cleanup_policy_for_profile("ams")

        self.assertIn(".gallery-link", policy.dom_postprocess_cleanup_selectors)
        self.assertIn(
            ".component-image-gallery", policy.dom_postprocess_cleanup_selectors
        )
        self.assertNotIn(".gallery-link", policy.extraction_cleanup_selectors)
        self.assertNotIn(
            ".gallery-link",
            extraction_cleanup_selectors_for_profile("ams"),
        )

    def test_provider_html_rules_exposes_facet_rule_objects(self) -> None:
        rules = provider_html_rules("springer_nature")

        self.assertEqual(
            cleanup_policy_for_profile("springer_nature").name,
            rules.noise_profile,
        )
        self.assertEqual(
            rules.availability.overrides,
            availability_rules_for_provider("springer_nature").overrides,
        )
        self.assertEqual(
            rules.formula.display_selectors,
            provider_display_formula_selectors("springer_nature"),
        )
        self.assertEqual(
            rules.assets.supplementary_text_tokens,
            provider_supplementary_text_tokens("springer_nature"),
        )
        self.assertEqual(
            rules.availability.overrides,
            availability_rules_for_provider("springer_nature").overrides,
        )

    def test_front_matter_publication_keywords_keep_atypon_browser_workflow_provider_scoped(
        self,
    ) -> None:
        self.assertNotIn("science", html_runtime.FRONT_MATTER_PUBLICATION_KEYWORDS)
        self.assertNotIn("pnas", html_runtime.FRONT_MATTER_PUBLICATION_KEYWORDS)
        self.assertFalse(html_runtime._looks_like_publication_watermark("Science"))
        self.assertFalse(html_runtime._looks_like_publication_watermark("PNAS Nexus"))
        self.assertTrue(
            html_runtime._looks_like_publication_watermark(
                "Science Robotics",
                noise_profile="science",
            )
        )
        self.assertTrue(
            atypon_browser_workflow_profile._looks_like_publication_watermark(
                "PNAS Nexus",
                publisher="pnas",
            )
        )
        self.assertTrue(
            html_runtime._looks_like_publication_watermark(
                "BAMS",
                noise_profile="ams",
            )
        )

    def test_front_matter_publication_watermarks_require_short_label_shape(
        self,
    ) -> None:
        examples = (
            (
                "science",
                "Science and PNAS are mentioned here as part of a normal sentence.",
            ),
            (
                "pnas",
                "This PNAS Nexus article is discussed in the results, not the masthead.",
            ),
            (
                "ams",
                "BAMS appears in the body when comparing forecast verification datasets.",
            ),
        )

        for profile, text in examples:
            with self.subTest(profile=profile):
                self.assertFalse(
                    html_runtime._looks_like_publication_watermark(
                        text,
                        noise_profile=profile,
                    )
                )
                self.assertFalse(
                    atypon_browser_workflow_profile._looks_like_publication_watermark(
                        text,
                        publisher=profile,
                    )
                )

    def test_front_matter_byline_is_removed_only_before_body_starts(self) -> None:
        metrics = html_runtime.body_metrics(
            "# Example\n\nBy Alice Example\n\n## Results\n\nMeasured body text.",
            {"title": "Example", "abstract": ""},
        )

        self.assertNotIn("By Alice Example", metrics["text"])
        self.assertIn("Measured body text.", metrics["text"])

    def test_body_paragraph_starting_with_by_is_preserved(self) -> None:
        long_sentence = (
            "By measuring isotope changes across many basins, the study isolates "
            "hydrologic responses that vary with land cover and climate forcing."
        )
        metrics = html_runtime.body_metrics(
            f"# Example\n\n## Results\n\n{long_sentence}",
            {"title": "Example", "abstract": ""},
        )

        self.assertIn(long_sentence, metrics["text"])

    def test_multi_sentence_by_paragraph_is_preserved(self) -> None:
        paragraph = (
            "By Alice Example. This paragraph introduces the article rather than "
            "serving as a standalone author byline."
        )
        metrics = html_runtime.body_metrics(
            f"# Example\n\n## Results\n\n{paragraph}",
            {"title": "Example", "abstract": ""},
        )

        self.assertIn(paragraph, metrics["text"])

    def test_late_byline_shaped_body_text_is_preserved(self) -> None:
        metrics = html_runtime.body_metrics(
            "# Example\n\n## Results\n\nFirst body paragraph.\n\nBy Alice Example",
            {"title": "Example", "abstract": ""},
        )

        self.assertIn("First body paragraph.", metrics["text"])
        self.assertIn("By Alice Example", metrics["text"])

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

    def test_inline_normalization_is_shared_for_body_heading_and_table_text(
        self,
    ) -> None:
        """rule: rule-preserve-inline-semantics-in-body-and-tables"""
        raw_text = "CO <sub> 2 </sub> emission </sup> +"

        self.assertEqual(
            normalize_html_inline_text("CO <sub> 2 </sub> emissions"),
            "CO<sub>2</sub> emissions",
        )
        self.assertEqual(
            normalize_html_inline_text("m <sup> -2 </sup> )", policy="body"),
            "m<sup>-2</sup>)",
        )
        self.assertEqual(
            normalize_html_inline_text("m <sup> -2 </sup> )", policy="table_cell"),
            "m<sup>-2</sup> )",
        )
        self.assertEqual(
            normalize_html_inline_text(raw_text, policy="heading"),
            "CO<sub>2</sub> emission</sup>+",
        )

    def test_inline_normalization_preserves_isotope_superscript_spacing(self) -> None:
        """rule: rule-preserve-inline-semantics-in-body-and-tables"""
        self.assertEqual(
            normalize_html_inline_text("gas of <sup>6</sup>Li atoms"),
            "gas of <sup>6</sup>Li atoms",
        )
        self.assertEqual(
            normalize_html_inline_text("states of <sup>6</sup>Li"),
            "states of <sup>6</sup>Li",
        )

    def test_inline_normalization_tightens_high_confidence_sup_sub_spacing(
        self,
    ) -> None:
        """rule: rule-preserve-inline-semantics-in-body-and-tables"""
        self.assertEqual(
            normalize_html_inline_text("[ <sup>17</sup>]"), "[<sup>17</sup>]"
        )
        self.assertEqual(
            normalize_html_inline_text("m <sup> -2 </sup>"), "m<sup>-2</sup>"
        )
        self.assertEqual(
            normalize_html_inline_text("km <sup>2</sup>"), "km<sup>2</sup>"
        )
        self.assertEqual(
            normalize_html_inline_text("CO <sub>2</sub>"), "CO<sub>2</sub>"
        )
        self.assertEqual(
            normalize_html_inline_text("H <sub>2</sub>O"), "H<sub>2</sub>O"
        )
        self.assertEqual(
            normalize_html_inline_text("kg <sup>-1</sup>"), "kg<sup>-1</sup>"
        )
        self.assertEqual(
            normalize_html_inline_text("AB <sub>3</sub>"), "AB<sub>3</sub>"
        )
        self.assertEqual(normalize_html_inline_text("x <sup>2</sup>"), "x<sup>2</sup>")
        self.assertEqual(
            normalize_html_inline_text("*h* <sub>0</sub>"), "*h*<sub>0</sub>"
        )
        self.assertEqual(
            normalize_html_inline_text("number of <sup>6</sup>Li"),
            "number of <sup>6</sup>Li",
        )
        self.assertEqual(
            normalize_html_inline_text("state of <sub>2</sub>"), "state of <sub>2</sub>"
        )

    def test_inline_token_joiner_is_shared_by_body_heading_and_table_cells(
        self,
    ) -> None:
        """rule: rule-preserve-inline-semantics-in-body-and-tables"""
        soup = BeautifulSoup(
            """
<article>
  <h2>CO <sub>2</sub> and x <sup>2</sup></h2>
  <p>kg <sup>-1</sup> flux and number of <sup>6</sup>Li atoms.</p>
  <table><tr><th>Compound</th></tr><tr><td>AB <sub>3</sub></td></tr></table>
</article>
""",
            "html.parser",
        )

        body_text = render_clean_text_from_html(soup.p)
        heading_text = render_heading_text_from_html(soup.h2)
        table_markdown = render_table_markdown(soup.table, label="", caption="")

        self.assertEqual(heading_text, "CO<sub>2</sub> and x<sup>2</sup>")
        self.assertEqual(
            body_text, "kg<sup>-1</sup> flux and number of <sup>6</sup>Li atoms."
        )
        self.assertIn("AB<sub>3</sub>", table_markdown)

    def test_table_header_flattening_removes_redundant_global_spanner(self) -> None:
        soup = BeautifulSoup(
            """
<table>
  <thead>
    <tr><th colspan="2">Production MoE models</th></tr>
    <tr><th>Model</th><th>Parameters</th></tr>
  </thead>
  <tbody><tr><td>A</td><td>1B</td></tr></tbody>
</table>
""",
            "html.parser",
        )

        markdown = render_table_markdown(soup.table, label="", caption="")

        self.assertTrue(markdown.startswith("Production MoE models\n\n| Model"))
        self.assertIn("| Model | Parameters |", markdown)
        self.assertNotIn("Production MoE models / Model", markdown)

    def test_table_header_flattening_lifts_full_width_title_and_keeps_pipe_rows_valid(
        self,
    ) -> None:
        soup = BeautifulSoup(
            r"""
<table>
  <tr><th colspan="5">Probability of quota violations
  with $(1,x,y)$ uniform on $\{1&lt;x&lt;y\}$</th></tr>
  <tr><th>Method</th><td>M</td><td>Theoretical Probability</td><td>Sample Probability</td><td>95% Confidence Interval</td></tr>
  <tr><th>Huntington-Hill</th><td>10</td><td>0.257</td><td>0.257</td><td>(0.254, 0.260)</td></tr>
</table>
""",
            "html.parser",
        )

        markdown = render_table_markdown(soup.table, label="", caption="")
        pipe_lines = [line for line in markdown.splitlines() if line.startswith("|")]

        self.assertIn(
            "Probability of quota violations with $(1,x,y)$ uniform", markdown
        )
        self.assertIn("| Method", markdown)
        self.assertFalse(markdown.splitlines()[0].startswith("|"))
        self.assertTrue(pipe_lines)
        self.assertEqual({line.count("|") for line in pipe_lines}, {6})

    def test_table_markdown_escapes_edge_cells_and_pads_ragged_rows(self) -> None:
        soup = BeautifulSoup(
            """
<table>
  <thead><tr><th>Name</th><th>Value|Unit</th></tr></thead>
  <tbody>
    <tr><td>A|B</td><td>first<br/>second</td></tr>
    <tr><td>ragged</td><td></td></tr>
  </tbody>
</table>
""",
            "html.parser",
        )

        markdown = render_table_markdown(soup.table, label="", caption="")
        pipe_lines = [line for line in markdown.splitlines() if line.startswith("|")]

        self.assertIn(r"Value\|Unit", markdown)
        self.assertIn(r"A\|B", markdown)
        self.assertIn("first<br>second", markdown)
        self.assertTrue(pipe_lines)
        self.assertEqual(
            {line.replace(r"\|", "").count("|") for line in pipe_lines}, {3}
        )

    def test_table_header_flattening_preserves_distinguishing_group_spanners(
        self,
    ) -> None:
        soup = BeautifulSoup(
            """
<table>
  <thead>
    <tr><th colspan="2">Configuration</th><th colspan="2">Inference</th></tr>
    <tr><th>n_r</th><th>k</th><th>MMLU</th><th>GPQA</th></tr>
  </thead>
  <tbody><tr><td>2</td><td>4</td><td>80</td><td>50</td></tr></tbody>
</table>
""",
            "html.parser",
        )

        markdown = render_table_markdown(soup.table, label="", caption="")

        self.assertIn("Configuration / n_r", markdown)
        self.assertIn("Inference / MMLU", markdown)

    def test_section_renderer_collapses_prose_hard_linebreaks_without_touching_blocks(
        self,
    ) -> None:
        soup = BeautifulSoup(
            """
<article>
  <p>Drosophila melanogaster
  embryos possess
  coordinated cell cycles with <math><mi>x</mi></math>
  checkpoints.</p>
  <math display="block"><mi>E</mi><mo>=</mo><mi>m</mi></math>
  <ul>
    <li>First item
    wraps across source lines.</li>
    <li>Second item.</li>
  </ul>
</article>
""",
            "html.parser",
        )
        lines: list[str] = []
        render_container_markdown(
            soup.article, lines, level=2, section_content_selectors=()
        )
        markdown = "\n".join(lines)

        self.assertIn(
            "Drosophila melanogaster embryos possess coordinated cell cycles", markdown
        )
        self.assertNotIn("melanogaster\nembryos", markdown)
        self.assertIn("$$\nE = m\n$$", markdown)
        self.assertIn("- First item wraps across source lines.", markdown)
        self.assertIn("- Second item.", markdown)

    def test_inline_math_operators_are_preserved_in_body_and_table_cells(self) -> None:
        soup = BeautifulSoup(
            """
<article>
  <p>Spin <math><mi>s</mi><mo>(</mo><mi>s</mi><mo>+</mo><mn>1</mn><mo>)</mo></math>
  and <math><mo>(</mo><mi>D</mi><mo>+</mo><mn>1</mn><mo>)</mo></math>-dimensional terms.</p>
</article>
""",
            "html.parser",
        )
        lines: list[str] = []
        render_container_markdown(
            soup.article, lines, level=2, section_content_selectors=()
        )
        markdown = "\n".join(lines)

        self.assertIn("$s(s + 1)$", markdown)
        self.assertIn("$(D + 1)$-dimensional", markdown)
        self.assertNotIn("s(s 1)", markdown)
        self.assertNotIn("(D 1)-dimensional", markdown)

        table = BeautifulSoup(
            """
<table>
  <tr><th>Expression</th></tr>
  <tr><td><math><mi>s</mi><mo>+</mo><mn>1</mn></math></td></tr>
</table>
""",
            "html.parser",
        )
        table_markdown = render_table_markdown(
            table.table,
            label="",
            caption="",
            render_inline_text=render_clean_text_from_html,
        )
        self.assertIn("s + 1", table_markdown)

    def test_inline_tex_formula_container_renders_with_math_delimiters(self) -> None:
        soup = BeautifulSoup(
            """
<p>Let <span class="inline-equation"><script type="math/tex">x+y</script></span> stay inline.</p>
""",
            "html.parser",
        )

        body_text = render_clean_text_from_html(soup.p)

        self.assertEqual(body_text, "Let $x+y$ stay inline.")

    def test_formula_rules_detect_real_formula_image_urls(self) -> None:
        """rule: rule-preserve-formula-image-fallbacks"""
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

    def test_formula_publisher_tokens_are_registered_as_provider_extensions(
        self,
    ) -> None:
        springer_rules = provider_html_rules("springer")
        wiley_rules = provider_html_rules("wiley")

        self.assertNotIn("c-article-equation", GENERIC_FORMULA_CONTAINER_TOKENS)
        self.assertNotIn("fallback__mathequation", GENERIC_FORMULA_CONTAINER_TOKENS)
        self.assertNotIn(".c-article-equation", GENERIC_DISPLAY_FORMULA_SELECTORS)
        self.assertIn("c-article-equation", springer_rules.formula.container_tokens)
        self.assertIn(".c-article-equation", springer_rules.formula.display_selectors)
        self.assertIn("fallback__mathequation", wiley_rules.formula.container_tokens)

    def test_provider_formula_container_tokens_require_explicit_profile(self) -> None:
        soup = BeautifulSoup(
            '<div id="EqCustom" class="c-article-equation"><img src="/rendered.png" alt="rendered"/></div>',
            "html.parser",
        )
        image = soup.select_one("img")
        self.assertIsNotNone(image)

        self.assertFalse(looks_like_formula_image(image))
        self.assertTrue(
            looks_like_formula_image(
                image,
                noise_profile="springer_nature",
            )
        )
        self.assertEqual(
            formula_heading_for_image(
                image,
                1,
                noise_profile="springer_nature",
            ),
            "EqCustom",
        )

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

    def test_wiley_formula_asset_extractor_accepts_altimg_fallback_span(self) -> None:
        html = """
        <div class="article-section__content">
          <div id="gcb70901-disp-0001" class="inline-equation">
            <span class="fallback__mathEquation"
                  data-altimg="/cms/asset/d936e789/gcb70901-math-0001.png"></span>
            <math display="block" location="graphic/gcb70901-math-0001.png"><mrow /></math>
          </div>
        </div>
        """

        assets = wiley_html.extract_scoped_html_assets(
            html,
            "https://onlinelibrary.wiley.com/doi/10.1111/gcb.70901",
            asset_profile="body",
        )

        formula_assets = [asset for asset in assets if asset["kind"] == "formula"]
        self.assertEqual(len(formula_assets), 1)
        self.assertEqual(formula_assets[0]["heading"], "gcb70901-disp-0001")
        self.assertEqual(
            formula_assets[0]["url"],
            "https://onlinelibrary.wiley.com/cms/asset/d936e789/gcb70901-math-0001.png",
        )

    def test_springer_formula_asset_extractor_injects_provider_profile(self) -> None:
        html = (
            '<div id="EqCustom" class="c-article-equation">'
            '<img src="/rendered.png" alt="rendered"/>'
            "</div>"
        )

        assets = springer_html.extract_scoped_html_assets(
            html,
            "https://www.nature.com/articles/example",
            asset_profile="body",
        )

        formula_assets = [asset for asset in assets if asset["kind"] == "formula"]
        self.assertEqual(len(formula_assets), 1)
        self.assertEqual(formula_assets[0]["heading"], "EqCustom")
        self.assertEqual(
            formula_assets[0]["url"],
            "https://www.nature.com/rendered.png",
        )

    def test_supplementary_nature_text_tokens_are_provider_extensions(self) -> None:
        html = '<a href="/files/source-data">Source data</a>'

        generic_assets = html_assets.extract_supplementary_assets(
            html, "https://example.test/article"
        )
        springer_assets = html_assets.extract_supplementary_assets(
            html,
            "https://example.test/article",
            noise_profile="springer_nature",
        )

        self.assertEqual(generic_assets, [])
        self.assertEqual(springer_assets[0]["heading"], "Source data")

    def test_clean_markdown_registers_springer_nature_profile(self) -> None:
        """rule: rule-springer-article-root-chrome-pruning"""
        markdown = """
# Article

Sign up for alerts

## Results

Important body text.
"""

        generic_cleaned = html_runtime.clean_markdown(markdown)
        springer_cleaned = html_runtime.clean_markdown(
            markdown, noise_profile="springer_nature"
        )

        self.assertIn("Sign up for alerts", generic_cleaned)
        self.assertNotIn("Sign up for alerts", springer_cleaned)
