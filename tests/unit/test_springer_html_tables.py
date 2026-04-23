from __future__ import annotations

import unittest

from bs4 import BeautifulSoup

from paper_fetch.providers import springer as springer_provider
from paper_fetch.providers._html_tables import render_table_markdown
from tests.golden_criteria import golden_criteria_asset


SPRINGER_CLASSIC_DOI = "10.1007/s10584-011-0143-4"
SPRINGER_CLASSIC_TITLE = "Hydrological response to climate change in a glacierized catchment in the Himalayas"
SPRINGER_CLASSIC_LANDING_URL = f"https://link.springer.com/article/{SPRINGER_CLASSIC_DOI}"
SPRINGER_CLASSIC_TABLE_URL = f"{SPRINGER_CLASSIC_LANDING_URL}/tables/1"
SPRINGER_CLASSIC_ARTICLE_FIXTURE = golden_criteria_asset(SPRINGER_CLASSIC_DOI, "article.html")
SPRINGER_CLASSIC_TABLE_FIXTURE = golden_criteria_asset(SPRINGER_CLASSIC_DOI, "table1.html")

SPRINGER_NATURE_DOI = "10.1038/s43247-024-01295-w"
SPRINGER_NATURE_TITLE = "Hydrological drought forecasts using precipitation data depend on catchment properties and human activities"
SPRINGER_NATURE_LANDING_URL = f"https://www.nature.com/articles/{SPRINGER_NATURE_DOI}"
SPRINGER_NATURE_TABLE_URL = "https://www.nature.com/articles/s43247-024-01295-w/tables/1"
SPRINGER_NATURE_ARTICLE_FIXTURE = golden_criteria_asset(SPRINGER_NATURE_DOI, "original.html")
SPRINGER_NATURE_TABLE_FIXTURE = golden_criteria_asset(SPRINGER_NATURE_DOI, "table1.html")


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
        soup = BeautifulSoup(SPRINGER_CLASSIC_TABLE_FIXTURE.read_text(encoding="utf-8"), "html.parser")
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
        client = springer_provider.SpringerClient(transport=FakeTransport(responses), env={})

        raw_payload = client.fetch_raw_fulltext(SPRINGER_NATURE_DOI, metadata)
        article = client.to_article_model(metadata, raw_payload)
        markdown = raw_payload.metadata["markdown_text"]

        self.assertEqual(raw_payload.metadata["route"], "html")
        self.assertEqual(article.source, "springer_html")
        self.assertNotIn("PAPER_FETCH_TABLE_PLACEHOLDER", markdown)
        self.assertIn("**Table 1.**", markdown)
        self.assertIn("**Table 1.** The mean correlation values of SPI-x and SSI-1, and SPI-x and SGI-1 for each European region", markdown)
        self.assertRegex(
            markdown,
            r"\|\s*Region in Europe\s*\|\s*SSI-1 / SPI-1\s*\|\s*SSI-1 / SPI-3\s*\|\s*SSI-1 / SPI-6\s*\|",
        )
        self.assertIn("SGI-1 / SPI-12", markdown)
        self.assertIn("**0.539**", markdown)
        self.assertIn("**0.579**", markdown)
        self.assertNotIn("View all journals", markdown)
        self.assertLess(markdown.index("catchment properties and human activities"), markdown.index("**Table 1.**"))

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
