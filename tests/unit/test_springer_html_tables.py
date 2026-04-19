from __future__ import annotations

import unittest

from bs4 import BeautifulSoup

from paper_fetch.providers import springer as springer_provider
from paper_fetch.providers._html_tables import render_table_markdown


SPRINGER_CLASSIC_DOI = "10.1007/s10584-011-0143-4"
SPRINGER_CLASSIC_TITLE = "Hydrological response to climate change in a glacierized catchment in the Himalayas"
SPRINGER_CLASSIC_LANDING_URL = f"https://link.springer.com/article/{SPRINGER_CLASSIC_DOI}"
SPRINGER_CLASSIC_TABLE_URL = f"{SPRINGER_CLASSIC_LANDING_URL}/tables/1"

SPRINGER_CLASSIC_ARTICLE_HTML = f"""
<html>
  <head>
    <meta name="citation_title" content="{SPRINGER_CLASSIC_TITLE}" />
    <meta name="citation_doi" content="{SPRINGER_CLASSIC_DOI}" />
  </head>
  <body>
    <main>
      <article>
        <h1>{SPRINGER_CLASSIC_TITLE}</h1>
        <p>
          The combined cryospheric hydrological model resolves glacier movement, ablation, runoff, and
          base flow at high spatial resolution. This introductory paragraph is intentionally long enough
          to keep the HTML route above the full-text threshold and mirrors the narrative style of the
          original article while remaining compact for the test fixture.
        </p>
        <p>
          The model parameters related to glacier modeling are shown in Table <a href="/article/{SPRINGER_CLASSIC_DOI}#Tab1">1</a>.
          Additional body text continues here to ensure the extraction pipeline retains a robust Springer
          body section before the inline table placeholder is encountered in the HTML document.
        </p>
        <div class="c-article-table" data-test="inline-table" data-container-section="table" id="table-1">
          <figure>
            <figcaption class="c-article-table__figcaption">
              <b id="Tab1" data-test="table-caption">Table 1 Model parameters</b>
            </figcaption>
            <div class="u-text-right u-hide-print">
              <a
                class="c-article__pill-button"
                data-test="table-link"
                href="/article/{SPRINGER_CLASSIC_DOI}/tables/1"
                rel="nofollow"
              >
                Full size table
              </a>
            </div>
          </figure>
        </div>
        <h3>3.2 Hydrological processes</h3>
        <p>
          Further discussion explains how precipitation lapse rates, runoff partitioning, and glacier
          recession interact under climate change. This extra paragraph keeps the body length comfortably
          above the acceptance threshold after the inline table block has been replaced by a placeholder.
        </p>
      </article>
    </main>
  </body>
</html>
"""

SPRINGER_CLASSIC_TABLE_HTML = """
<html>
  <head>
    <title>Table 1 | Hydrological response to climate change in a glacierized catchment in the Himalayas</title>
  </head>
  <body>
    <div class="c-article-table-container">
      <div class="c-table-scroll-wrapper__content" data-component-scroll-wrapper="">
        <table class="data last-table">
          <thead class="c-article-table-head">
            <tr>
              <th class="u-text-left"><p>Parameter</p></th>
              <th class="u-text-left"><p>Description</p></th>
              <th class="u-text-left"><p>Value</p></th>
              <th class="u-text-left"><p>Units</p></th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="u-text-left"><p>ρ</p></td>
              <td class="u-text-left"><p>Ice density</p></td>
              <td class="u-text-left"><p>916.7</p></td>
              <td class="u-text-left"><p>kg m<sup>-3</sup></p></td>
            </tr>
            <tr>
              <td class="u-text-left"><p>τ<sub>0</sub></p></td>
              <td class="u-text-left"><p>Equilibrium shear stress</p></td>
              <td class="u-text-left"><p>80000</p></td>
              <td class="u-text-left"><p>N m<sup>-2</sup></p></td>
            </tr>
            <tr>
              <td class="u-text-left"><p>λ<sub>t</sub></p></td>
              <td class="u-text-left"><p>Temperature lapse rate</p></td>
              <td class="u-text-left"><p>-0.0063</p></td>
              <td class="u-text-left"><p>°C m<sup>-1</sup></p></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </body>
</html>
"""

SPRINGER_NATURE_DOI = "10.1038/s43247-024-01295-w"
SPRINGER_NATURE_TITLE = "Hydrological drought forecasts using precipitation data depend on catchment properties and human activities"
SPRINGER_NATURE_LANDING_URL = f"https://www.nature.com/articles/{SPRINGER_NATURE_DOI}"
SPRINGER_NATURE_TABLE_URL = f"{SPRINGER_NATURE_LANDING_URL}/tables/1"

SPRINGER_NATURE_ARTICLE_HTML = f"""
<html>
  <head>
    <meta name="citation_title" content="{SPRINGER_NATURE_TITLE}" />
    <meta name="citation_doi" content="{SPRINGER_NATURE_DOI}" />
  </head>
  <body>
    <main>
      <article>
        <h1>{SPRINGER_NATURE_TITLE}</h1>
        <p>
          The correlation analysis evaluates how precipitation accumulation periods relate to hydrological
          drought indicators across Europe. This opening paragraph provides enough narrative text for the
          live HTML route and mirrors the natural-geography use case that motivated the regression.
        </p>
        <p>
          To summarize the correlation patterns, we present the correlation values for each SPI-x and
          European region in Table 1. The article continues with additional explanatory text so the
          extraction pipeline preserves the inline table location inside the main body.
        </p>
        <div class="c-article-table" data-test="inline-table" data-container-section="table" id="table-1">
          <figure>
            <figcaption class="c-article-table__figcaption">
              <b id="Tab1" data-test="table-caption">Table 1 The mean correlation values of SPI-x and SSI-1, and SPI-x and SGI-1 for each European region</b>
            </figcaption>
            <div class="u-text-right u-hide-print">
              <a
                class="c-article__pill-button"
                data-test="table-link"
                href="/articles/{SPRINGER_NATURE_DOI}/tables/1"
                rel="nofollow"
              >
                Full size table
              </a>
            </div>
          </figure>
        </div>
        <p>
          In addition to catchment properties, anthropogenic activities influence the relationship between
          precipitation-based indicators and hydrological drought metrics. This trailing paragraph ensures
          the body remains well above the extraction threshold after table normalization.
        </p>
      </article>
    </main>
  </body>
</html>
"""

SPRINGER_NATURE_TABLE_HTML = """
<html>
  <head>
    <title>Table 1 The mean correlation values of SPI-x and SSI-1, and SPI-x and SGI-1 for each European region</title>
  </head>
  <body>
    <div class="c-article-table-container">
      <div class="c-table-scroll-wrapper__content" data-component-scroll-wrapper="">
        <table class="data last-table">
          <thead class="c-article-table-head">
            <tr>
              <th class="u-text-left"><p>Region in Europe</p></th>
              <th colspan="4"><p>SSI-1</p></th>
              <th colspan="4"><p>SGI-1</p></th>
            </tr>
            <tr>
              <th class="u-text-left"><p>&nbsp;</p></th>
              <th class="u-text-left"><p>SPI-1</p></th>
              <th class="u-text-left"><p>SPI-3</p></th>
              <th class="u-text-left"><p>SPI-6</p></th>
              <th class="u-text-left"><p>SPI-12</p></th>
              <th class="u-text-left"><p>SPI-1</p></th>
              <th class="u-text-left"><p>SPI-3</p></th>
              <th class="u-text-left"><p>SPI-6</p></th>
              <th class="u-text-left"><p>SPI-12</p></th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="u-text-left"><p>WE</p></td>
              <td class="u-text-left"><p>0.007</p></td>
              <td class="u-text-left"><p><b>0.539</b></p></td>
              <td class="u-text-left"><p>0.531</p></td>
              <td class="u-text-left"><p>0.434</p></td>
              <td class="u-text-left"><p>0.354</p></td>
              <td class="u-text-left"><p>0.600</p></td>
              <td class="u-text-left"><p><b>0.678</b></p></td>
              <td class="u-text-left"><p>0.631</p></td>
            </tr>
            <tr>
              <td class="u-text-left"><p>CE</p></td>
              <td class="u-text-left"><p>-0.002</p></td>
              <td class="u-text-left"><p>0.441</p></td>
              <td class="u-text-left"><p><b>0.462</b></p></td>
              <td class="u-text-left"><p>0.398</p></td>
              <td class="u-text-left"><p>0.235</p></td>
              <td class="u-text-left"><p>0.449</p></td>
              <td class="u-text-left"><p>0.553</p></td>
              <td class="u-text-left"><p><b>0.579</b></p></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </body>
</html>
"""


class FakeTransport:
    def __init__(self, responses: dict[str, dict[str, object] | Exception]) -> None:
        self.responses = responses

    def request(
        self,
        method,
        url,
        *,
        headers=None,
        query=None,
        timeout=20,
        retry_on_rate_limit=False,
        rate_limit_retries=1,
        max_rate_limit_wait_seconds=5,
        retry_on_transient=False,
        transient_retries=2,
        transient_backoff_base_seconds=0.5,
    ):
        del headers, query, timeout, retry_on_rate_limit, rate_limit_retries, max_rate_limit_wait_seconds
        del retry_on_transient, transient_retries, transient_backoff_base_seconds
        key = str(url)
        if method != "GET":
            raise AssertionError(f"Unexpected method {method}")
        if key not in self.responses:
            raise AssertionError(f"Missing fake response for {key}")
        response = self.responses[key]
        if isinstance(response, Exception):
            raise response
        return response


class SpringerHtmlTableTests(unittest.TestCase):
    def test_render_table_markdown_handles_real_springer_classic_table_page(self) -> None:
        soup = BeautifulSoup(SPRINGER_CLASSIC_TABLE_HTML, "html.parser")
        table = soup.find("table")
        assert table is not None

        markdown = render_table_markdown(table, label="Table 1.", caption="Model parameters")

        self.assertIn("**Table 1.** Model parameters", markdown)
        self.assertRegex(markdown, r"\|\s*Parameter\s*\|\s*Description\s*\|\s*Value\s*\|\s*Units\s*\|")
        self.assertIn("Equilibrium shear stress", markdown)
        self.assertIn("τ<sub>0</sub>", markdown)
        self.assertIn("N m<sup>-2</sup>", markdown)

    def test_springer_html_injects_real_nature_inline_table_page_with_flattened_headers(self) -> None:
        metadata = {
            "doi": SPRINGER_NATURE_DOI,
            "title": SPRINGER_NATURE_TITLE,
            "landing_page_url": SPRINGER_NATURE_LANDING_URL,
            "fulltext_links": [],
        }
        responses = {
            SPRINGER_NATURE_LANDING_URL: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": SPRINGER_NATURE_ARTICLE_HTML.encode("utf-8"),
                "url": SPRINGER_NATURE_LANDING_URL,
                "status_code": 200,
            },
            SPRINGER_NATURE_TABLE_URL: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": SPRINGER_NATURE_TABLE_HTML.encode("utf-8"),
                "url": SPRINGER_NATURE_TABLE_URL,
                "status_code": 200,
            },
        }
        client = springer_provider.SpringerClient(transport=FakeTransport(responses), env={})

        raw_payload = client.fetch_raw_fulltext(SPRINGER_NATURE_DOI, metadata)
        article = client.to_article_model(metadata, raw_payload)
        markdown = raw_payload.metadata["markdown_text"]

        self.assertEqual(raw_payload.metadata["route"], "html")
        self.assertEqual(article.source, "springer_html")
        self.assertNotIn("PAPER_FETCH_TABLE_PLACEHOLDER", markdown)
        self.assertIn("**Table 1.** The mean correlation values of SPI-x and SSI-1, and SPI-x and SGI-1 for each European region", markdown)
        self.assertRegex(
            markdown,
            r"\|\s*Region in Europe\s*\|\s*SSI-1 / SPI-1\s*\|\s*SSI-1 / SPI-3\s*\|\s*SSI-1 / SPI-6\s*\|",
        )
        self.assertIn("SGI-1 / SPI-12", markdown)
        self.assertIn("**0.539**", markdown)
        self.assertIn("**0.579**", markdown)
        self.assertLess(markdown.index("To summarize the correlation patterns"), markdown.index("**Table 1.**"))

    def test_springer_html_keeps_article_success_when_inline_table_page_has_no_table(self) -> None:
        metadata = {
            "doi": SPRINGER_CLASSIC_DOI,
            "title": SPRINGER_CLASSIC_TITLE,
            "landing_page_url": SPRINGER_CLASSIC_LANDING_URL,
            "fulltext_links": [],
        }
        responses = {
            SPRINGER_CLASSIC_LANDING_URL: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": SPRINGER_CLASSIC_ARTICLE_HTML.encode("utf-8"),
                "url": SPRINGER_CLASSIC_LANDING_URL,
                "status_code": 200,
            },
            SPRINGER_CLASSIC_TABLE_URL: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": b"<html><head><title>Table 1</title></head><body><p>Unavailable</p></body></html>",
                "url": SPRINGER_CLASSIC_TABLE_URL,
                "status_code": 200,
            },
        }
        client = springer_provider.SpringerClient(transport=FakeTransport(responses), env={})

        raw_payload = client.fetch_raw_fulltext(SPRINGER_CLASSIC_DOI, metadata)
        article = client.to_article_model(metadata, raw_payload)
        markdown = raw_payload.metadata["markdown_text"]

        self.assertEqual(article.source, "springer_html")
        self.assertNotIn("PAPER_FETCH_TABLE_PLACEHOLDER", markdown)
        self.assertNotRegex(markdown, r"\|\s*Parameter\s*\|\s*Description\s*\|")
        self.assertTrue(
            any("did not include a table element" in warning for warning in article.quality.warnings),
            article.quality.warnings,
        )


if __name__ == "__main__":
    unittest.main()
