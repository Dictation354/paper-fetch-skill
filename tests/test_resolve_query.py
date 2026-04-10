from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "resolve_query.py"
SPEC = importlib.util.spec_from_file_location("resolve_query", SCRIPT_PATH)
resolve_query = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = resolve_query
SPEC.loader.exec_module(resolve_query)


class RecordingTransport(resolve_query.HttpTransport):
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

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
            }
        )
        key = (method, url)
        if key not in self.responses:
            raise AssertionError(f"Missing fake response for {url}")
        return self.responses[key]


class ResolveQueryTests(unittest.TestCase):
    def test_direct_doi_query_is_normalized(self) -> None:
        result = resolve_query.resolve_query("10.1016/J.RSE.2026.115369")

        self.assertEqual(result.query_kind, "doi")
        self.assertEqual(result.doi, "10.1016/j.rse.2026.115369")
        self.assertEqual(result.provider_hint, "elsevier")
        self.assertEqual(result.confidence, 1.0)

    def test_doi_url_is_resolved_without_network(self) -> None:
        result = resolve_query.resolve_query("https://doi.org/10.1007/s00376-024-4012-9")

        self.assertEqual(result.query_kind, "url")
        self.assertEqual(result.doi, "10.1007/s00376-024-4012-9")
        self.assertEqual(result.provider_hint, "springer")

    def test_landing_url_extracts_doi_from_meta_tags(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://example.test/paper"): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html"},
                    "body": (
                        b"<html><head>"
                        b'<meta name="citation_title" content="Example Article" />'
                        b'<meta name="citation_doi" content="10.1111/example.doi" />'
                        b"</head><body>Example</body></html>"
                    ),
                    "url": "https://example.test/paper",
                }
            }
        )

        result = resolve_query.resolve_query("https://example.test/paper", transport=transport, env={})

        self.assertEqual(result.query_kind, "url")
        self.assertEqual(result.doi, "10.1111/example.doi")
        self.assertEqual(result.provider_hint, "wiley")
        self.assertEqual(transport.calls[0]["timeout"], 20)
        self.assertIn("User-Agent", transport.calls[0]["headers"])

    def test_title_query_selects_unique_crossref_match(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://api.crossref.org/works"): {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": json.dumps(
                        {
                            "message": {
                                "items": [
                                    {
                                        "DOI": "10.1016/test",
                                        "title": ["Deep learning for land cover classification"],
                                        "container-title": ["Remote Sensing Letters"],
                                        "publisher": "Elsevier",
                                        "URL": "https://example.test/deep-learning",
                                    },
                                    {
                                        "DOI": "10.5555/other",
                                        "title": ["A distant candidate on crop modelling"],
                                        "container-title": ["Other Journal"],
                                        "publisher": "Other Publisher",
                                        "URL": "https://example.test/other",
                                    },
                                ]
                            }
                        }
                    ).encode("utf-8"),
                    "url": "https://api.crossref.org/works",
                }
            }
        )

        result = resolve_query.resolve_query(
            "Deep learning for land cover classification",
            transport=transport,
            env={},
        )

        self.assertEqual(result.query_kind, "title")
        self.assertEqual(result.doi, "10.1016/test")
        self.assertEqual(result.provider_hint, "elsevier")
        self.assertGreaterEqual(result.confidence, 0.9)
        self.assertEqual(result.candidates, [])
        self.assertEqual(transport.calls[0]["query"]["query.bibliographic"], "Deep learning for land cover classification")

    def test_url_query_skips_crossref_lookup_for_invalid_html_title(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://example.test/paper"): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html"},
                    "body": b"<html><head><title>Just a moment...</title></head><body>Shield</body></html>",
                    "url": "https://example.test/paper",
                }
            }
        )

        result = resolve_query.resolve_query("https://example.test/paper", transport=transport, env={})

        self.assertIsNone(result.doi)
        self.assertIsNone(result.title)
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(len(transport.calls), 1)

    def test_url_query_clears_candidates_after_confident_crossref_match(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://example.test/paper"): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html"},
                    "body": b"<html><head><title>Deep learning for land cover classification</title></head><body>Paper</body></html>",
                    "url": "https://example.test/paper",
                },
                ("GET", "https://api.crossref.org/works"): {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": json.dumps(
                        {
                            "message": {
                                "items": [
                                    {
                                        "DOI": "10.1016/test",
                                        "title": ["Deep learning for land cover classification"],
                                        "container-title": ["Remote Sensing Letters"],
                                        "publisher": "Elsevier",
                                        "URL": "https://example.test/deep-learning",
                                    },
                                    {
                                        "DOI": "10.5555/other",
                                        "title": ["A distant candidate on crop modelling"],
                                        "container-title": ["Other Journal"],
                                        "publisher": "Other Publisher",
                                        "URL": "https://example.test/other",
                                    },
                                ]
                            }
                        }
                    ).encode("utf-8"),
                    "url": "https://api.crossref.org/works",
                },
            }
        )

        result = resolve_query.resolve_query("https://example.test/paper", transport=transport, env={})

        self.assertEqual(result.doi, "10.1016/test")
        self.assertEqual(result.candidates, [])
        self.assertEqual(result.title, "Deep learning for land cover classification")

    def test_url_query_uses_lookup_title_from_redirect_stub(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://example.test/paper"): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html"},
                    "body": (
                        b"<html><head>"
                        b"<title>Redirecting</title>"
                        b'<meta http-equiv="refresh" content="2; url=\'/retrieve/articleSelectSinglePerm\'" />'
                        b"</head><body>"
                        b'<input type="hidden" name="redirectURL" value="https%3A%2F%2Fwww.sciencedirect.com%2Fscience%2Farticle%2Fpii%2FS0034425725000525" />'
                        b"<script>"
                        b"siteCatalyst.pageDataLoad({ articleName : 'Seasonality of vegetation greenness in Southeast Asia unveiled by geostationary satellite observations', identifierValue : 'S0034425725000525' });"
                        b"</script>"
                        b"</body></html>"
                    ),
                    "url": "https://example.test/paper",
                },
                ("GET", "https://api.crossref.org/works"): {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": json.dumps(
                        {
                            "message": {
                                "items": [
                                    {
                                        "DOI": "10.1016/j.rse.2025.114648",
                                        "title": ["Seasonality of vegetation greenness in Southeast Asia unveiled by geostationary satellite observations"],
                                        "container-title": ["Remote Sensing of Environment"],
                                        "publisher": "Elsevier",
                                        "URL": "https://example.test/landing",
                                    }
                                ]
                            }
                        }
                    ).encode("utf-8"),
                    "url": "https://api.crossref.org/works",
                },
            }
        )

        result = resolve_query.resolve_query(
            "https://example.test/paper",
            transport=transport,
            env={"PAPER_FETCH_SKILL_USER_AGENT": "ResolveTest/1.0"},
        )

        self.assertEqual(result.doi, "10.1016/j.rse.2025.114648")
        self.assertEqual(result.provider_hint, "elsevier")
        self.assertEqual(
            result.title,
            "Seasonality of vegetation greenness in Southeast Asia unveiled by geostationary satellite observations",
        )
        self.assertEqual(transport.calls[0]["headers"]["User-Agent"], "ResolveTest/1.0")
        self.assertEqual(transport.calls[1]["query"]["query.bibliographic"], result.title)

    def test_title_query_returns_candidates_when_ambiguous(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://api.crossref.org/works"): {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": json.dumps(
                        {
                            "message": {
                                "items": [
                                    {
                                        "DOI": "10.1000/a",
                                        "title": ["Climate change impacts on crop yield"],
                                        "container-title": ["Journal A"],
                                        "publisher": "Publisher A",
                                        "URL": "https://example.test/a",
                                    },
                                    {
                                        "DOI": "10.1000/b",
                                        "title": ["Climate change impacts on crops"],
                                        "container-title": ["Journal B"],
                                        "publisher": "Publisher B",
                                        "URL": "https://example.test/b",
                                    },
                                ]
                            }
                        }
                    ).encode("utf-8"),
                    "url": "https://api.crossref.org/works",
                }
            }
        )

        result = resolve_query.resolve_query("Climate change impacts on crop", transport=transport, env={})

        self.assertIsNone(result.doi)
        self.assertEqual(len(result.candidates), 2)
        self.assertGreater(result.candidates[0]["score"], 0)

    def test_no_title_results_raise_provider_failure(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://api.crossref.org/works"): {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": b'{"message": {"items": []}}',
                    "url": "https://api.crossref.org/works",
                }
            }
        )

        with self.assertRaises(resolve_query.ProviderFailure) as ctx:
            resolve_query.resolve_query("A title that does not exist", transport=transport, env={})

        self.assertEqual(ctx.exception.code, "no_result")


if __name__ == "__main__":
    unittest.main()
