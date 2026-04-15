from __future__ import annotations

import json
import unittest

from paper_fetch.resolve import query as resolve_query


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
            raise AssertionError(f"Missing fake response for {url}")
        return self.responses[key]


class ResolveQueryTests(unittest.TestCase):
    def test_direct_doi_query_is_normalized(self) -> None:
        result = resolve_query.resolve_query("10.1016/J.RSE.2026.115369")

        self.assertEqual(result.query_kind, "doi")
        self.assertEqual(result.doi, "10.1016/j.rse.2026.115369")
        self.assertEqual(result.provider_hint, "elsevier")
        self.assertEqual(result.confidence, 1.0)

    def test_direct_science_and_pnas_doi_queries_use_new_provider_hints(self) -> None:
        science_result = resolve_query.resolve_query("10.1126/science.ady3136")
        pnas_result = resolve_query.resolve_query("10.1073/pnas.81.23.7500")

        self.assertEqual(science_result.provider_hint, "science")
        self.assertEqual(pnas_result.provider_hint, "pnas")

    def test_doi_url_prefers_final_landing_domain(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://doi.org/10.1006/jaer.1996.0085"): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html"},
                    "body": b"<html><head><title>Example</title></head><body>Example</body></html>",
                    "url": "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
                }
            }
        )

        result = resolve_query.resolve_query("https://doi.org/10.1006/jaer.1996.0085", transport=transport, env={})

        self.assertEqual(result.query_kind, "url")
        self.assertEqual(result.doi, "10.1006/jaer.1996.0085")
        self.assertEqual(result.provider_hint, "elsevier")
        self.assertTrue(transport.calls[0]["retry_on_transient"])

    def test_direct_doi_query_uses_crossref_publisher_before_doi_fallback(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://api.crossref.org/works/10.1006%2Fjaer.1996.0085"): {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": json.dumps(
                        {
                            "message": {
                                "DOI": "10.1006/jaer.1996.0085",
                                "title": ["Journal of Environmental Research Article"],
                                "publisher": "Elsevier BV",
                                "URL": "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
                            }
                        }
                    ).encode("utf-8"),
                    "url": "https://api.crossref.org/works/10.1006%2Fjaer.1996.0085",
                }
            }
        )

        result = resolve_query.resolve_query("10.1006/jaer.1996.0085", transport=transport, env={})

        self.assertEqual(result.query_kind, "doi")
        self.assertEqual(result.doi, "10.1006/jaer.1996.0085")
        self.assertEqual(result.provider_hint, "elsevier")
        self.assertEqual(len(transport.calls), 1)

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
        self.assertTrue(transport.calls[0]["retry_on_transient"])

    def test_url_query_follows_relative_redirect_and_absolutizes_landing_url(self) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://nature.com/articles/sj.bdj.2017.900"): {
                    "status_code": 303,
                    "headers": {"location": "https://www.nature.com/articles/sj.bdj.2017.900"},
                    "body": b"",
                    "url": "https://nature.com/articles/sj.bdj.2017.900",
                },
                ("GET", "https://www.nature.com/articles/sj.bdj.2017.900"): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html"},
                    "body": (
                        b"<html><head>"
                        b"<title>Nature Example</title>"
                        b'<meta name="citation_doi" content="10.1038/sj.bdj.2017.900" />'
                        b'<meta name="citation_title" content="Nature Example" />'
                        b'<meta name="citation_public_url" content="/articles/sj.bdj.2017.900" />'
                        b"</head><body>Example</body></html>"
                    ),
                    "url": "https://www.nature.com/articles/sj.bdj.2017.900",
                },
            }
        )

        result = resolve_query.resolve_query("https://nature.com/articles/sj.bdj.2017.900", transport=transport, env={})

        self.assertEqual(result.query_kind, "url")
        self.assertEqual(result.doi, "10.1038/sj.bdj.2017.900")
        self.assertEqual(result.landing_url, "https://www.nature.com/articles/sj.bdj.2017.900")
        self.assertEqual(result.provider_hint, "springer")
        self.assertEqual(len(transport.calls), 2)

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

    def test_title_query_uses_crossref_publisher_and_landing_url_for_provider_hint(self) -> None:
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
                                        "DOI": "10.1006/jaer.1996.0085",
                                        "title": ["A Precise Elsevier Candidate"],
                                        "container-title": ["Journal of AI Research"],
                                        "publisher": "Elsevier BV",
                                        "URL": "https://linkinghub.elsevier.com/retrieve/pii/S0021863496900852",
                                    },
                                    {
                                        "DOI": "10.5555/other",
                                        "title": ["A Different Candidate"],
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

        result = resolve_query.resolve_query("A Precise Elsevier Candidate", transport=transport, env={})

        self.assertEqual(result.doi, "10.1006/jaer.1996.0085")
        self.assertEqual(result.provider_hint, "elsevier")

    def test_title_query_can_infer_science_provider_from_crossref_signals(self) -> None:
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
                                        "DOI": "10.1126/science.ady3136",
                                        "title": ["Hyaluronic acid and tissue mechanics orchestrate mammalian digit tip regeneration"],
                                        "container-title": ["Science"],
                                        "publisher": "American Association for the Advancement of Science",
                                        "URL": "https://www.science.org/doi/full/10.1126/science.ady3136",
                                    }
                                ]
                            }
                        }
                    ).encode("utf-8"),
                    "url": "https://api.crossref.org/works",
                }
            }
        )

        result = resolve_query.resolve_query(
            "Hyaluronic acid and tissue mechanics orchestrate mammalian digit tip regeneration",
            transport=transport,
            env={},
        )

        self.assertEqual(result.doi, "10.1126/science.ady3136")
        self.assertEqual(result.provider_hint, "science")

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
        self.assertTrue(transport.calls[0]["retry_on_transient"])
        self.assertEqual(transport.calls[1]["query"]["query.bibliographic"], result.title)

    def test_url_query_wraps_request_failure_from_landing_page_fetch(self) -> None:
        class FailingTransport:
            def request(self, *args, **kwargs):
                raise resolve_query.RequestFailure(502, "HTTP 502 for https://example.test/paper")

        with self.assertRaises(resolve_query.ProviderFailure) as context:
            resolve_query.resolve_query("https://example.test/paper", transport=FailingTransport(), env={})

        self.assertEqual(context.exception.code, "error")
        self.assertIn("Failed to fetch landing page", context.exception.message)

    def test_url_query_does_not_swallow_programming_errors(self) -> None:
        class BrokenTransport:
            def request(self, *args, **kwargs):
                raise AttributeError("broken transport")

        with self.assertRaises(AttributeError):
            resolve_query.resolve_query("https://example.test/paper", transport=BrokenTransport(), env={})

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
