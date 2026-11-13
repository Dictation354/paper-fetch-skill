from __future__ import annotations
from tests.support.transport import RecordedStreamTransport

import unittest
from typing import Any
from collections.abc import Mapping

from paper_fetch.extraction.html.landing import fetch_landing_html


class FakeLandingTransport(RecordedStreamTransport):
    def __init__(self, responses: Mapping[str, Mapping[str, Any]]) -> None:
        self.responses = dict(responses)
        self.urls: list[str] = []

    def request(self, method: str, url: str, **_kwargs: Any) -> Mapping[str, Any]:
        self.urls.append(url)
        self.assert_method = method
        return self.responses[url]


class LandingHtmlFetchTests(unittest.TestCase):
    def test_relative_redirects_resolve_against_requested_url(self) -> None:
        transport = FakeLandingTransport(
            {
                "https://doi.org/10.1234/example": {
                    "status_code": 302,
                    "url": "https://resolver.example/ignored/base",
                    "headers": {"location": "../article"},
                    "body": b"",
                },
                "https://doi.org/article": {
                    "status_code": 200,
                    "url": "https://publisher.example/article",
                    "headers": {"content-type": "text/html"},
                    "body": b"<html><title>Article</title></html>",
                },
            }
        )

        result = fetch_landing_html(
            "https://doi.org/10.1234/example",
            transport=transport,  # type: ignore[arg-type]
            max_redirects=1,
            decoder=lambda body: body.decode("utf-8"),
            metadata_parser=lambda _html, url: {"landing_page_url": url},
        )

        self.assertEqual(
            transport.urls,
            [
                "https://doi.org/10.1234/example",
                "https://doi.org/article",
            ],
        )
        self.assertEqual(result.final_url, "https://publisher.example/article")


if __name__ == "__main__":
    unittest.main()
