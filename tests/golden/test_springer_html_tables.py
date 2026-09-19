from __future__ import annotations
import re
import unittest
from bs4 import BeautifulSoup
from paper_fetch.providers import _springer_html as springer_html
from paper_fetch.providers import springer as springer_provider
from paper_fetch.extraction.html.tables import render_table_markdown
from paper_fetch.runtime import RuntimeContext
from tests.golden_criteria import golden_criteria_asset


SPRINGER_CLASSIC_DOI = "10.1007/s10584-011-0143-4"
SPRINGER_CLASSIC_TITLE = "Hydrological response to climate change in a glacierized catchment in the Himalayas"
SPRINGER_CLASSIC_LANDING_URL = (
    f"https://link.springer.com/article/{SPRINGER_CLASSIC_DOI}"
)
SPRINGER_CLASSIC_TABLE_URL = f"{SPRINGER_CLASSIC_LANDING_URL}/tables/1"
SPRINGER_CLASSIC_ARTICLE_FIXTURE = golden_criteria_asset(
    SPRINGER_CLASSIC_DOI, "article.html"
)
SPRINGER_CLASSIC_TABLE_FIXTURE = golden_criteria_asset(
    SPRINGER_CLASSIC_DOI, "table1.html"
)

SPRINGER_NATURE_DOI = "10.1038/s43247-024-01295-w"
SPRINGER_NATURE_TITLE = "Hydrological drought forecasts using precipitation data depend on catchment properties and human activities"
SPRINGER_NATURE_LANDING_URL = f"https://www.nature.com/articles/{SPRINGER_NATURE_DOI}"
SPRINGER_NATURE_TABLE_URL = (
    "https://www.nature.com/articles/s43247-024-01295-w/tables/1"
)
SPRINGER_NATURE_ARTICLE_FIXTURE = golden_criteria_asset(
    SPRINGER_NATURE_DOI, "original.html"
)
SPRINGER_NATURE_TABLE_FIXTURE = golden_criteria_asset(
    SPRINGER_NATURE_DOI, "table1.html"
)
OLD_NATURE_DOI = "10.1038/nature13376"
OLD_NATURE_TITLE = "Contribution of semi-arid ecosystems to interannual variability of the global carbon cycle"
OLD_NATURE_LANDING_URL = "https://www.nature.com/articles/nature13376"
OLD_NATURE_ARTICLE_FIXTURE = golden_criteria_asset(OLD_NATURE_DOI, "original.html")
GENERIC_EXTENDED_TABLE_DOI = "10.1038/s41586-020-1941-5"
GENERIC_EXTENDED_TABLE_TITLE = "Forest age and water yield"
GENERIC_EXTENDED_TABLE_LANDING_URL = "https://www.nature.com/articles/s41586-020-1941-5"
GENERIC_EXTENDED_TABLE_URL = f"{GENERIC_EXTENDED_TABLE_LANDING_URL}/tables/1"
GENERIC_EXTENDED_TABLE_ESM_IMAGE_URL = (
    "https://media.springernature.com/lw850/springer-static/esm/"
    "art%3A10.1038%2Fs41586-020-1941-5/MediaObjects/"
    "41586_2020_1941_Tab1_ESM.jpg"
)
NATURE_HEADER_SVG_URL = (
    "https://media.springernature.com/full/nature-cms/uploads/product/nature/"
    "header-86f1267ea01eccd46b530284be10585e.svg"
)


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
        request_policy=None,
    ):
        del (
            headers,
            query,
            timeout,
            retry_on_rate_limit,
            rate_limit_retries,
            max_rate_limit_wait_seconds,
        )
        del (
            retry_on_transient,
            transient_retries,
            transient_backoff_base_seconds,
            request_policy,
        )
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
    def _article_with_inline_table(
        self, *, label: str, caption: str, table_href: str
    ) -> bytes:
        label_text = label.rstrip(".")
        body_text = (
            "Planting and removal of forest affect average streamflow, but there is ongoing debate "
            "about how this long-term difference between precipitation and evapotranspiration is "
            "modulated by forest age, local conditions, and record length across catchments."
        )
        return f"""
        <html>
          <head>
            <title>{GENERIC_EXTENDED_TABLE_TITLE}</title>
            <meta name="citation_title" content="{GENERIC_EXTENDED_TABLE_TITLE}" />
            <meta name="citation_doi" content="{GENERIC_EXTENDED_TABLE_DOI}" />
            <meta name="citation_author" content="Adriaan J. Teuling" />
          </head>
          <body>
            <article>
              <h1>{GENERIC_EXTENDED_TABLE_TITLE}</h1>
              <div class="c-article-body">
                <div class="main-content">
                  <div class="c-article-section__content"><p>{body_text}</p></div>
                  <section data-title="Extended data figures and tables">
                    <div class="c-article-section">
                      <h2 class="c-article-section__title">Extended data figures and tables</h2>
                      <div class="c-article-section__content">
                        <div class="c-article-table" data-test="inline-table" data-container-section="table">
                          <figure>
                            <figcaption class="c-article-table__figcaption">
                              <b data-test="table-caption">{label_text} {caption}</b>
                            </figcaption>
                            <a data-test="table-link" href="{table_href}">Full size table</a>
                          </figure>
                        </div>
                      </div>
                    </div>
                  </section>
                </div>
              </div>
            </article>
          </body>
        </html>
        """.encode()

    def _prepare_generic_extended_table_attempt(
        self, responses: dict[str, dict[str, object] | Exception]
    ):
        metadata = {
            "doi": GENERIC_EXTENDED_TABLE_DOI,
            "title": GENERIC_EXTENDED_TABLE_TITLE,
            "landing_page_url": GENERIC_EXTENDED_TABLE_LANDING_URL,
            "fulltext_links": [],
        }
        transport = FakeTransport(responses)
        client = springer_provider.SpringerClient(transport=transport, env={})
        return client._prepare_html_attempt(
            GENERIC_EXTENDED_TABLE_DOI,
            metadata,
            context=RuntimeContext(env={}, transport=transport),
        )

    def test_springer_classic_fixture_strips_chrome_and_spaces_numbered_headings(
        self,
    ) -> None:
        html = SPRINGER_CLASSIC_ARTICLE_FIXTURE.read_text(
            encoding="utf-8", errors="ignore"
        )

        markdown = springer_html.extract_html_payload(
            html, SPRINGER_CLASSIC_LANDING_URL, title=SPRINGER_CLASSIC_TITLE
        )["markdown_text"]

        for chrome in (
            "Save article",
            "View saved research",
            "Aims and scope",
            "Submit manuscript",
        ):
            self.assertNotIn(chrome, markdown)
        self.assertIn("## 1 Introduction", markdown)
        self.assertIn("## 2 Study area", markdown)
        self.assertIn("### 3.1 Glaciers", markdown)
        self.assertNotIn("## 1Introduction", markdown)
        self.assertNotIn(f"## {SPRINGER_CLASSIC_TITLE}", markdown)

    def test_render_table_markdown_handles_real_springer_classic_table_page(
        self,
    ) -> None:
        soup = BeautifulSoup(
            SPRINGER_CLASSIC_TABLE_FIXTURE.read_text(encoding="utf-8"), "html.parser"
        )
        table = soup.find("table")
        assert table is not None

        markdown = render_table_markdown(
            table, label="Table 1.", caption="Model parameters"
        )

        self.assertIn("**Table 1.** Model parameters", markdown)
        self.assertRegex(
            markdown,
            r"\|\s*Parameter\s*\|\s*Description\s*\|\s*Value\s*\|\s*Units\s*\|",
        )
        self.assertIn("Equilibrium shear stress", markdown)
        self.assertIn("τ<sub>0</sub>", markdown)
        self.assertIn("N m<sup>-2</sup>", markdown)

    def test_springer_html_injects_real_nature_inline_table_page_with_flattened_headers(
        self,
    ) -> None:
        metadata = {
            "doi": SPRINGER_NATURE_DOI,
            "title": SPRINGER_NATURE_TITLE,
            "landing_page_url": SPRINGER_NATURE_LANDING_URL,
            "fulltext_links": [],
        }
        responses = {
            SPRINGER_NATURE_LANDING_URL: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": SPRINGER_NATURE_ARTICLE_FIXTURE.read_bytes(),
                "url": SPRINGER_NATURE_LANDING_URL,
                "status_code": 200,
            },
            SPRINGER_NATURE_TABLE_URL: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": SPRINGER_NATURE_TABLE_FIXTURE.read_bytes(),
                "url": SPRINGER_NATURE_TABLE_URL,
                "status_code": 200,
            },
        }
        client = springer_provider.SpringerClient(
            transport=FakeTransport(responses), env={}
        )

        raw_payload = client.fetch_raw_fulltext(SPRINGER_NATURE_DOI, metadata)
        article = client.to_article_model(metadata, raw_payload)
        assert raw_payload.content is not None
        markdown = raw_payload.content.markdown_text or ""

        self.assertEqual(raw_payload.content.route_kind, "html")
        self.assertEqual(article.source, "springer_html")
        self.assertNotIn("PAPER_FETCH_TABLE_PLACEHOLDER", markdown)
        self.assertIn("**Table 1.**", markdown)
        self.assertIn(
            "**Table 1.** The mean correlation values of SPI-x and SSI-1, and SPI-x and SGI-1 for each European region",
            markdown,
        )
        self.assertRegex(
            markdown,
            r"\|\s*Region in Europe\s*\|\s*SSI-1 / SPI-1\s*\|\s*SSI-1 / SPI-3\s*\|\s*SSI-1 / SPI-6\s*\|",
        )
        self.assertIn("SGI-1 / SPI-12", markdown)
        self.assertIn("**0.539**", markdown)
        self.assertIn("**0.579**", markdown)
        self.assertNotIn("View all journals", markdown)
        self.assertLess(
            markdown.index("catchment properties and human activities"),
            markdown.index("**Table 1.**"),
        )

    def test_springer_html_keeps_article_success_when_inline_table_page_has_no_table(
        self,
    ) -> None:
        metadata = {
            "doi": SPRINGER_CLASSIC_DOI,
            "title": SPRINGER_CLASSIC_TITLE,
            "landing_page_url": SPRINGER_CLASSIC_LANDING_URL,
            "fulltext_links": [],
        }
        responses = {
            SPRINGER_CLASSIC_LANDING_URL: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": SPRINGER_CLASSIC_ARTICLE_FIXTURE.read_bytes(),
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
        client = springer_provider.SpringerClient(
            transport=FakeTransport(responses), env={}
        )

        raw_payload = client.fetch_raw_fulltext(SPRINGER_CLASSIC_DOI, metadata)
        article = client.to_article_model(metadata, raw_payload)
        assert raw_payload.content is not None
        markdown = raw_payload.content.markdown_text or ""
        extracted_assets = list(
            raw_payload.content.extracted_assets
            if raw_payload.content is not None
            else []
        )

        self.assertEqual(article.source, "springer_html")
        self.assertNotIn("PAPER_FETCH_TABLE_PLACEHOLDER", markdown)
        self.assertNotRegex(markdown, r"\|\s*Parameter\s*\|\s*Description\s*\|")
        self.assertIn("**Table 1.** [Table body unavailable:", markdown)
        self.assertFalse(
            any(asset.get("kind") == "table" for asset in extracted_assets)
        )
        self.assertTrue(
            any(
                "did not include a table element" in warning
                for warning in article.quality.warnings
            ),
            article.quality.warnings,
        )

    def test_old_nature_extended_data_tables_render_table_image_or_degraded_placeholder(
        self,
    ) -> None:
        metadata = {
            "doi": OLD_NATURE_DOI,
            "title": OLD_NATURE_TITLE,
            "landing_page_url": OLD_NATURE_LANDING_URL,
            "fulltext_links": [],
        }
        table_1_url = f"{OLD_NATURE_LANDING_URL}/tables/1"
        table_2_url = f"{OLD_NATURE_LANDING_URL}/tables/2"
        table_3_url = f"{OLD_NATURE_LANDING_URL}/tables/3"
        table_4_url = f"{OLD_NATURE_LANDING_URL}/tables/4"
        table_1_image_url = "https://media.springernature.com/full/table-1.png"
        table_2_image_url = "https://media.springernature.com/full/table-2.png"
        responses = {
            OLD_NATURE_LANDING_URL: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": OLD_NATURE_ARTICLE_FIXTURE.read_bytes(),
                "url": OLD_NATURE_LANDING_URL,
                "status_code": 200,
            },
            table_1_url: {
                "headers": {"location": table_1_image_url},
                "body": b"<html><body>See Other</body></html>",
                "url": table_1_url,
                "status_code": 303,
            },
            table_1_image_url: {
                "headers": {"content-type": "image/png"},
                "body": b"\x89PNG\r\n\x1a\ntable-one-image",
                "url": table_1_image_url,
                "status_code": 200,
            },
            table_2_url: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": f"<html><body><img src='{table_2_image_url}'></body></html>".encode(),
                "url": table_2_url,
                "status_code": 200,
            },
            table_3_url: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": b"<html><body><p>Unavailable</p></body></html>",
                "url": table_3_url,
                "status_code": 200,
            },
            table_4_url: {
                "headers": {"content-type": "text/html; charset=utf-8"},
                "body": b"""
                <html><body><figure>
                  <figcaption>Extended Data Table 4 CMIP5 model summary</figcaption>
                  <table><thead><tr><th>Model</th><th>Scenario</th></tr></thead>
                  <tbody><tr><td>Model A</td><td>RCP8.5</td></tr></tbody></table>
                </figure></body></html>
                """,
                "url": table_4_url,
                "status_code": 200,
            },
        }
        client = springer_provider.SpringerClient(
            transport=FakeTransport(responses), env={}
        )

        raw_payload = client.fetch_raw_fulltext(OLD_NATURE_DOI, metadata)
        assert raw_payload.content is not None
        markdown = raw_payload.content.markdown_text or ""
        extracted_assets = list(
            raw_payload.content.extracted_assets
            if raw_payload.content is not None
            else []
        )

        for number in range(1, 5):
            label = f"Extended Data Table {number}"
            has_markdown_table = f"**{label}." in markdown and re.search(
                r"\|\s*Model\s*\|\s*Scenario\s*\|",
                markdown,
            )
            has_image_asset = any(
                asset.get("kind") == "table"
                and label in str(asset.get("heading") or "")
                and (asset.get("url") or asset.get("path"))
                for asset in extracted_assets
            )
            has_degraded_placeholder = (
                f"**{label}.** [Table body unavailable:" in markdown
            )
            self.assertTrue(
                has_markdown_table or has_image_asset or has_degraded_placeholder,
                f"{label} was not rendered as a table, image asset, or degraded placeholder",
            )
        self.assertIn(f"![Table 1]({table_1_image_url})", markdown)
        self.assertIn(
            "**Extended Data Table 1.** Global summary of annual NEE", markdown
        )
        self.assertIn(f"![Table 2]({table_2_image_url})", markdown)
        self.assertIn("**Extended Data Table 3.** [Table body unavailable:", markdown)
        self.assertIn("**Extended Data Table 4.** CMIP5 model summary", markdown)
        self.assertIn(
            table_1_image_url, [asset.get("url") for asset in extracted_assets]
        )


if __name__ == "__main__":
    unittest.main()


# Reduced from the verified nature13006 /tables/2 satellite page: the displayed
# table number differs from the page number and the bitmap has a Figa_ESM name.
NATURE13006_URL = "https://www.nature.com/articles/nature13006"
NATURE13006_TABLE_IMAGE = (
    "https://media.springernature.com/lw403/springer-static/image/"
    "art%3A10.1038%2Fnature13006/MediaObjects/41586_2014_BFnature13006_Figa_ESM.jpg"
)
NATURE13006_TABLE_HTML = f"""
<html><head><title>Extended Data Table 1 Sensitivity | Nature</title></head><body>
<header><img src="{NATURE_HEADER_SVG_URL}"></header>
<main><header><h1>Extended Data Table 1 Sensitivity</h1>
<p class="c-article-satellite-subtitle">From: <a href="/articles/nature13006">Amazon forests</a></p></header>
<div class="c-article-table-container"><div class="c-article-table-image">
<img alt="" src="{NATURE13006_TABLE_IMAGE}"></div></div></main></body></html>
"""
