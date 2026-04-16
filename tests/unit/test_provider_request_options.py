from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch.http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, DEFAULT_TIMEOUT_SECONDS
from paper_fetch.providers import _flaresolverr, _science_pnas
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
        with mock.patch.object(client, "_official_payload_is_usable", return_value=True):
            payload = client.fetch_raw_fulltext(doi, {})

        self.assertEqual(payload.content_type, "text/xml")
        self.assertEqual(transport.calls[0]["timeout"], DEFAULT_FULLTEXT_TIMEOUT_SECONDS)
        self.assertTrue(transport.calls[0]["retry_on_rate_limit"])
        self.assertTrue(transport.calls[0]["retry_on_transient"])

    def test_springer_direct_html_fulltext_uses_extended_timeout(self) -> None:
        doi = "10.1186/1471-2105-11-421"
        transport = RecordingTransport(
            {
                ("GET", "https://www.nature.com/articles/example"): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": (
                        b"<html><head>"
                        b'<meta name="citation_title" content="Springer HTML Article" />'
                        b'<meta name="citation_doi" content="10.1186/1471-2105-11-421" />'
                        b"</head><body>"
                        b"<article><h1>Springer HTML Article</h1><h2>Introduction</h2>"
                        b"<p>"
                        + (b"Important body text. " * 200)
                        + b"</p></article></body></html>"
                    ),
                    "url": "https://www.nature.com/articles/example",
                }
            }
        )

        client = SpringerClient(transport, {})
        payload = client.fetch_raw_fulltext(doi, {"landing_page_url": "https://www.nature.com/articles/example"})

        self.assertEqual(payload.content_type, "text/html; charset=utf-8")
        self.assertEqual(transport.calls[0]["timeout"], DEFAULT_FULLTEXT_TIMEOUT_SECONDS)
        self.assertTrue(transport.calls[0]["retry_on_transient"])
        self.assertEqual(transport.calls[0]["url"], "https://www.nature.com/articles/example")

    def test_springer_direct_html_follows_http_redirects(self) -> None:
        doi = "10.1186/s13059-024-03246-2"
        transport = RecordingTransport(
            {
                ("GET", "https://genomebiology.biomedcentral.com/articles/10.1186/s13059-024-03246-2"): {
                    "status_code": 301,
                    "headers": {
                        "content-type": "text/html; charset=utf-8",
                        "location": "https://link.springer.com/article/10.1186/s13059-024-03246-2",
                    },
                    "body": b"<html><head><title>301 Moved Permanently</title></head><body>Moved</body></html>",
                    "url": "/articles/10.1186/s13059-024-03246-2",
                },
                ("GET", "https://link.springer.com/article/10.1186/s13059-024-03246-2"): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": (
                        b"<html><head>"
                        b'<meta name="citation_title" content="Single Cell Atlas" />'
                        b'<meta name="citation_doi" content="10.1186/s13059-024-03246-2" />'
                        b"</head><body>"
                        b"<article><h1>Single Cell Atlas</h1><h2>Abstract</h2>"
                        b"<p>"
                        + (b"Important body text. " * 200)
                        + b"</p></article></body></html>"
                    ),
                    "url": "https://link.springer.com/article/10.1186/s13059-024-03246-2",
                },
            }
        )

        client = SpringerClient(transport, {})
        payload = client.fetch_raw_fulltext(
            doi,
            {"landing_page_url": "https://genomebiology.biomedcentral.com/articles/10.1186/s13059-024-03246-2"},
        )

        self.assertEqual(payload.source_url, "https://link.springer.com/article/10.1186/s13059-024-03246-2")
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(
            [call["url"] for call in transport.calls],
            [
                "https://genomebiology.biomedcentral.com/articles/10.1186/s13059-024-03246-2",
                "https://link.springer.com/article/10.1186/s13059-024-03246-2",
            ],
        )
        self.assertTrue(all(call["retry_on_transient"] for call in transport.calls))
        self.assertTrue(all(call["timeout"] == DEFAULT_FULLTEXT_TIMEOUT_SECONDS for call in transport.calls))

    def test_wiley_browser_workflow_prefers_html_route(self) -> None:
        doi = "10.1002/ece3.9361"
        runtime = _flaresolverr.FlareSolverrRuntimeConfig(
            provider="wiley",
            doi=doi,
            url="http://127.0.0.1:8191/v1",
            env_file=Path("/tmp/.env.flaresolverr"),
            source_dir=Path("/tmp/vendor/flaresolverr"),
            artifact_dir=Path("/tmp/artifacts"),
            headless=True,
            min_interval_seconds=20,
            max_requests_per_hour=30,
            max_requests_per_day=200,
            rate_limit_file=Path("/tmp/rate_limits.json"),
        )

        client = WileyClient(transport=None, env={})
        with (
            mock.patch.object(_science_pnas, "load_runtime_config", return_value=runtime),
            mock.patch.object(_science_pnas, "ensure_runtime_ready"),
            mock.patch.object(
                _science_pnas,
                "fetch_html_with_flaresolverr",
                return_value=_flaresolverr.FetchedPublisherHtml(
                    source_url="https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
                    final_url="https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361",
                    html="<html></html>",
                    response_status=200,
                    response_headers={"content-type": "text/html"},
                    title="Example Wiley Article",
                    summary="Example summary",
                    browser_context_seed={},
                ),
            ),
            mock.patch.object(
                _science_pnas,
                "extract_science_pnas_markdown",
                return_value=("# Example Wiley Article\n\n## Results\n\n" + ("Body text " * 120), {"title": "Example"}),
            ),
            mock.patch.object(_science_pnas, "fetch_pdf_with_playwright") as mocked_pdf,
        ):
            payload = client.fetch_raw_fulltext(
                doi,
                {"doi": doi, "landing_page_url": "https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.9361"},
            )

        mocked_pdf.assert_not_called()
        self.assertEqual(payload.metadata["route"], "html")
        self.assertEqual(payload.content_type, "text/html")

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
