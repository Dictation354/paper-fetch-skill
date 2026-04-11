from __future__ import annotations

import json
import unittest

from paper_fetch.http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, DEFAULT_TIMEOUT_SECONDS
from paper_fetch.providers.crossref import CrossrefClient
from paper_fetch.providers.elsevier import ElsevierClient, filter_elsevier_asset_references
from paper_fetch.providers.springer import SpringerClient, extract_springer_asset_references, filter_springer_asset_references
from paper_fetch.providers.wiley import WileyClient


class RecordingTransport:
    def __init__(self, responses: dict[tuple[str, str], dict[str, object]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def request(
        self,
        method,
        url,
        *,
        headers=None,
        query=None,
        timeout=DEFAULT_TIMEOUT_SECONDS,
        retry_on_rate_limit=False,
        rate_limit_retries=1,
        max_rate_limit_wait_seconds=5,
        retry_on_transient=False,
        transient_retries=2,
        transient_backoff_base_seconds=0.5,
    ):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "query": dict(query or {}),
                "timeout": timeout,
                "retry_on_rate_limit": retry_on_rate_limit,
                "rate_limit_retries": rate_limit_retries,
                "max_rate_limit_wait_seconds": max_rate_limit_wait_seconds,
                "retry_on_transient": retry_on_transient,
                "transient_retries": transient_retries,
                "transient_backoff_base_seconds": transient_backoff_base_seconds,
            }
        )
        key = (method, url)
        if key not in self.responses:
            raise AssertionError(f"Missing fake response for {method} {url}")
        return self.responses[key]


class ProviderRequestOptionsTests(unittest.TestCase):
    def test_crossref_metadata_uses_default_timeout_and_rate_limit_retry(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://api.crossref.org/works/10.1234%2Fexample"): {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": json.dumps(
                        {
                            "message": {
                                "DOI": "10.1234/example",
                                "title": ["Example"],
                                "container-title": ["Journal"],
                                "publisher": "Publisher",
                                "URL": "https://example.test/article",
                            }
                        }
                    ).encode("utf-8"),
                    "url": "https://api.crossref.org/works/10.1234%2Fexample",
                }
            }
        )

        client = CrossrefClient(transport, {"CROSSREF_MAILTO": "alice@example.com"})
        metadata = client.fetch_metadata({"doi": "10.1234/example"})

        self.assertEqual(metadata["doi"], "10.1234/example")
        self.assertEqual(transport.calls[0]["timeout"], DEFAULT_TIMEOUT_SECONDS)
        self.assertTrue(transport.calls[0]["retry_on_rate_limit"])
        self.assertTrue(transport.calls[0]["retry_on_transient"])

    def test_elsevier_fulltext_uses_extended_timeout(self) -> None:
        doi = "10.1016/test"
        transport = RecordingTransport(
            {
                ("GET", "https://api.elsevier.com/content/article/doi/10.1016%2Ftest"): {
                    "status_code": 200,
                    "headers": {"content-type": "text/xml"},
                    "body": b"<xml />",
                    "url": "https://api.elsevier.com/content/article/doi/10.1016%2Ftest",
                }
            }
        )

        client = ElsevierClient(transport, {"ELSEVIER_API_KEY": "secret"})
        payload = client.fetch_raw_fulltext(doi, {})

        self.assertEqual(payload.content_type, "text/xml")
        self.assertEqual(transport.calls[0]["timeout"], DEFAULT_FULLTEXT_TIMEOUT_SECONDS)
        self.assertTrue(transport.calls[0]["retry_on_rate_limit"])
        self.assertTrue(transport.calls[0]["retry_on_transient"])

    def test_springer_openaccess_fulltext_uses_extended_timeout(self) -> None:
        doi = "10.1186/1471-2105-11-421"
        transport = RecordingTransport(
            {
                ("GET", "https://api.springernature.com/openaccess/jats"): {
                    "status_code": 200,
                    "headers": {"content-type": "application/xml"},
                    "body": b"<article />",
                    "url": "https://api.springernature.com/openaccess/jats",
                }
            }
        )

        client = SpringerClient(transport, {"SPRINGER_OPENACCESS_API_KEY": "secret"})
        payload = client.fetch_raw_fulltext(doi, {})

        self.assertEqual(payload.content_type, "application/xml")
        self.assertEqual(transport.calls[0]["timeout"], DEFAULT_FULLTEXT_TIMEOUT_SECONDS)
        self.assertTrue(transport.calls[0]["retry_on_rate_limit"])
        self.assertTrue(transport.calls[0]["retry_on_transient"])

    def test_wiley_fulltext_uses_extended_timeout(self) -> None:
        doi = "10.1002/ece3.9361"
        transport = RecordingTransport(
            {
                ("GET", "https://api.wiley.com/onlinelibrary/tdm/v1/articles/10.1002%2Fece3.9361"): {
                    "status_code": 200,
                    "headers": {"content-type": "application/pdf"},
                    "body": b"%PDF-1.4",
                    "url": "https://api.wiley.com/onlinelibrary/tdm/v1/articles/10.1002%2Fece3.9361",
                }
            }
        )

        client = WileyClient(
            transport,
            {
                "WILEY_TDM_URL_TEMPLATE": "https://api.wiley.com/onlinelibrary/tdm/v1/articles/{doi}",
                "WILEY_TDM_TOKEN": "secret",
            },
        )
        payload = client.fetch_raw_fulltext(doi, {})

        self.assertEqual(payload.content_type, "application/pdf")
        self.assertEqual(transport.calls[0]["timeout"], DEFAULT_FULLTEXT_TIMEOUT_SECONDS)
        self.assertTrue(transport.calls[0]["retry_on_rate_limit"])
        self.assertTrue(transport.calls[0]["retry_on_transient"])

    def test_elsevier_body_asset_profile_excludes_appendix_and_supplementary(self) -> None:
        references = [
            {"asset_type": "image", "source_ref": "fx1"},
            {"asset_type": "table_asset", "source_ref": "tx1"},
            {"asset_type": "appendix_image", "source_ref": "app1"},
            {"asset_type": "supplementary", "source_ref": "sup1"},
            {"asset_type": "graphical_abstract", "source_ref": "ga1"},
        ]

        filtered = filter_elsevier_asset_references(references, asset_profile="body")

        self.assertEqual(
            [reference["asset_type"] for reference in filtered],
            ["image", "table_asset"],
        )

    def test_springer_body_asset_profile_excludes_appendix_and_supplementary(self) -> None:
        xml_body = b"""<?xml version="1.0"?>
<response xmlns:xlink="http://www.w3.org/1999/xlink">
  <records>
    <article>
      <body>
        <sec>
          <fig id="Fig1"><graphic xlink:href="MediaObjects/Fig1.png" /></fig>
          <table-wrap id="Tab1"><graphic xlink:href="MediaObjects/Tab1.png" /></table-wrap>
        </sec>
      </body>
      <app-group>
        <app id="App1">
          <sec>
            <fig id="FigA1"><graphic xlink:href="MediaObjects/FigA1.png" /></fig>
            <supplementary-material id="Sup1"><media xlink:href="MediaObjects/Sup1.pdf" /></supplementary-material>
          </sec>
        </app>
      </app-group>
    </article>
  </records>
</response>
"""

        references = extract_springer_asset_references(xml_body, "10.1007/test")
        filtered = filter_springer_asset_references(references, asset_profile="body")

        self.assertEqual(
            [(reference["asset_type"], reference["section"]) for reference in filtered],
            [("image", "body"), ("table_asset", "body")],
        )


if __name__ == "__main__":
    unittest.main()
