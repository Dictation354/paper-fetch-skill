from __future__ import annotations

import json
import time
import unittest

import pytest

from paper_fetch.extraction.html._metadata import parse_html_metadata
from paper_fetch.http import RequestCancelledError, RequestFailure
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.resolve import query as resolve_query
from paper_fetch.runtime import RuntimeContext
from tests.golden_criteria import golden_criteria_scenario_asset
from tests.support._paper_fetch_support import RecordingTransport
from tests.support.transport import RecordedStreamTransport


@pytest.mark.parametrize(
    ("html_title", "title", "interstitial"),
    [
        ("Redirecting to ScienceDirect...", "Stub Article Title", True),
        ("Redirecting to ScienceDirect", "Stub Article Title", True),
        ("Redirecting...", "Stub Article Title", True),
        (
            "Redirecting T Cells to Solid Tumors",
            "Redirecting T Cells to Solid Tumors",
            False,
        ),
    ],
)
def test_html_metadata_distinguishes_redirect_interstitials_from_article_titles(
    html_title, title, interstitial
):
    html = golden_criteria_scenario_asset(
        "generic_metadata_boundaries", "redirect_stub.html"
    ).read_text(encoding="utf-8")
    metadata = parse_html_metadata(
        html.replace("<title>Redirecting</title>", f"<title>{html_title}</title>"),
        "https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525",
    )
    assert metadata["lookup_title"] == "Stub Article Title"
    assert metadata["title"] == title
    assert bool(metadata.get("lookup_challenge_title")) is interstitial


@pytest.mark.parametrize(
    ("url", "article_id", "database", "converter_error"),
    [
        ("https://pmc.ncbi.nlm.nih.gov/articles/pmc123/", "PMC123", "pmc", True),
        ("https://www.ncbi.nlm.nih.gov/pmc/articles/PMC123", "PMC123", "pmc", False),
        (
            "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/pdf/test.pdf",
            "PMC123",
            "pmc",
            False,
        ),
        ("https://pubmed.ncbi.nlm.nih.gov/123/?query=1", "123", "pubmed", False),
    ],
)
def test_ncbi_url_uses_official_ids_then_crossref(
    url, article_id, database, converter_error
):
    converter = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
    summary = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    crossref = "https://api.crossref.org/works/10.1016%2Fexample"
    publisher = "https://www.sciencedirect.com/science/article/pii/example"
    doi = "10.1016/EXAMPLE"

    def response(endpoint, data):
        return {"url": endpoint, "body": json.dumps(data).encode()}

    responses = {
        ("GET", converter): response(
            converter,
            {
                "records": [
                    {"doi": "10.1000/unrelated", "pmcid": "PMC999"},
                    {
                        "doi": "10.1000/error",
                        "requested-id": article_id,
                        "status": "error",
                    },
                    {"doi": doi, "requested-id": article_id.lower()},
                ]
            },
        ),
        ("GET", crossref): response(
            crossref,
            {
                "message": {
                    "DOI": doi,
                    "title": ["Example article"],
                    "resource": {"primary": {"URL": publisher}},
                }
            },
        ),
    }
    if converter_error or database == "pubmed":
        responses["GET", converter] = (
            RequestFailure(
                None, "Connection closed", error_category="connection_closed"
            )
            if converter_error
            else response(converter, {"records": [{}]})
        )
        responses["GET", summary] = response(
            summary,
            {
                "result": {
                    "123": {
                        "articleids": [
                            {"idtype": "pmid", "value": "123"},
                            {"idtype": "doi", "value": doi},
                        ]
                    },
                }
            },
        )
    transport = RecordingTransport(responses)
    result = resolve_query.resolve_query(
        url, transport=transport, env={"CROSSREF_MAILTO": "reader@example.test"}
    )
    assert (
        result.query_kind,
        result.doi,
        result.title,
        result.landing_url,
        result.provider_hint,
        result.confidence,
    ) == ("url", doi.lower(), "Example article", publisher, "elsevier", 1.0)
    assert transport.calls[0]["query"] == {
        "ids": article_id,
        "format": "json",
        "tool": "paper-fetch",
    }
    assert transport.calls[0]["retry_on_transient"] is True
    if ("GET", summary) in responses:
        assert transport.calls[1]["query"] == {
            "db": database,
            "id": "123",
            "retmode": "json",
            "tool": "paper-fetch",
        }
    assert transport.calls[-1]["url"] == crossref
    assert all(call["timeout"] == 15 for call in transport.calls)
    assert "reader@example.test" not in str([call["query"] for call in transport.calls])


@pytest.mark.parametrize(
    "title",
    [
        "Please wait while we check your browser",
        "One moment while we are preparing your request",
        "Verifying you because attention required",
        "Checking your connection in a security check",
        "Bot check before you may continue browsing",
    ],
)
def test_challenge_title_does_not_trigger_bibliographic_search(title):
    url = "https://pubmed.ncbi.nlm.nih.gov/123/"
    converter = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
    summary = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    transport = RecordingTransport(
        {
            ("GET", converter): {"url": converter, "body": b'{"records": []}'},
            ("GET", summary): {"url": summary, "body": b'{"result": {}}'},
            ("GET", url): {
                "url": url,
                "status_code": 200,
                "headers": {"content-type": "text/html"},
                "body": f"<html><title>{title}</title></html>".encode(),
            },
        }
    )
    result = resolve_query.resolve_query(url, transport=transport, env={})
    assert result.doi is None and result.title is None and result.landing_url is None
    assert [call["url"] for call in transport.calls] == [converter, summary, url]


@pytest.mark.parametrize(
    "url",
    [
        "https://pubmed.ncbi.nlm.nih.gov/123/not-a-page",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/figures/",
        "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC123/pdf/path/file.pdf",
        "https://pmc.ncbi.nlm.nih.gov.evil.test/articles/PMC123/",
    ],
)
def test_ncbi_rejects_non_article_id_paths(url):
    assert resolve_query._ncbi_article_id(url) is None


@pytest.mark.parametrize("stage", ["initial", "esummary", "crossref"])
@pytest.mark.parametrize("cancelled", [True, False])
def test_ncbi_context_is_checked_before_each_network_operation(stage, cancelled):
    url = "https://pubmed.ncbi.nlm.nih.gov/123/"
    converter = resolve_query._PMC_ID_CONVERTER
    calls = []
    state = {"cancelled": False}

    def stop():
        if cancelled:
            state["cancelled"] = True
        else:
            context.deadline_monotonic = time.monotonic() - 1

    class InjectedTransport:
        def request(self, method, endpoint, **kwargs):
            calls.append(endpoint)
            assert endpoint == converter
            assert 0 < kwargs["timeout"] <= 10
            stop()
            records = (
                [{"pmid": "123", "doi": "10.1016/example"}]
                if stage == "crossref"
                else []
            )
            return {"url": endpoint, "body": json.dumps({"records": records}).encode()}

    transport = InjectedTransport()
    with RuntimeContext(
        env={}, transport=transport, cancel_check=lambda: state["cancelled"]
    ) as context:
        context.initialize_deadline(10)
        if stage == "initial":
            stop()
        with pytest.raises(RequestCancelledError if cancelled else ProviderFailure):
            resolve_query.resolve_query(
                url, transport=transport, context=context, env={}
            )
    assert calls == ([] if stage == "initial" else [converter])


@pytest.mark.parametrize(
    "title",
    [
        "Checking Your Privilege: A Survey of Discourse",
        "Securing Your Browser Against Timing Attacks",
        "Cookie Preferences and Privacy Expectations",
    ],
)
def test_real_titles_with_challenge_words_are_kept(title):
    url = "https://example.test/article"
    transport = RecordingTransport(
        {
            ("GET", url): {
                "url": url,
                "status_code": 200,
                "body": f"<title>{title}</title><meta name='citation_doi' content='10.1016/example'>".encode(),
            },
        }
    )
    result = resolve_query.resolve_query(url, transport=transport, env={})
    assert result.title == title and result.landing_url == url


class ResolveQueryTests(unittest.TestCase):
    def test_direct_doi_query_is_normalized(self) -> None:
        result = resolve_query.resolve_query("10.1016/J.RSE.2026.115369")

        self.assertEqual(result.query_kind, "doi")
        self.assertEqual(result.doi, "10.1016/j.rse.2026.115369")
        self.assertEqual(result.provider_hint, "elsevier")
        self.assertEqual(result.confidence, 1.0)

    def test_only_modern_nature_article_paths_resolve_without_a_landing_request(self):
        article_id = "s41586-020-1941-5"
        for host in ("nature.com", "www.nature.com"):
            url = f"https://{host}/articles/{article_id}?tracking=1#Main"
            transport = RecordingTransport({})
            result = resolve_query.resolve_query(url, transport=transport, env={})
            self.assertEqual(result.doi, f"10.1038/{article_id}")
            self.assertEqual(result.landing_url, url)
            self.assertEqual(result.provider_hint, "springer")
            self.assertFalse(transport.calls)

        for url in (
            "https://www.nature.com/articles/nature12345",
            f"https://www.nature.com/articles/{article_id}/tables/1",
            f"https://www.nature.com/articles/{article_id}.pdf",
            f"https://other.nature.com/articles/{article_id}",
            f"https://nature.com.example.org/articles/{article_id}",
        ):
            with self.subTest(url=url):
                transport = RecordingTransport(
                    {
                        ("GET", url): {
                            "status_code": 200,
                            "headers": {"content-type": "text/html"},
                            "body": b'<meta name="citation_doi" content="10.1038/legacy">',
                            "url": url,
                        }
                    }
                )
                result = resolve_query.resolve_query(url, transport=transport, env={})
                self.assertEqual(result.doi, "10.1038/legacy")
                self.assertEqual(len(transport.calls), 1)

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

        result = resolve_query.resolve_query(
            "https://doi.org/10.1006/jaer.1996.0085", transport=transport, env={}
        )

        self.assertEqual(result.query_kind, "url")
        self.assertEqual(result.doi, "10.1006/jaer.1996.0085")
        self.assertEqual(result.provider_hint, "elsevier")
        self.assertTrue(transport.calls[0]["retry_on_transient"])

    def test_url_with_embedded_doi_and_provider_hint_skips_landing_fetch(self) -> None:
        transport = RecordingTransport({})

        result = resolve_query.resolve_query(
            "https://www.science.org/doi/full/10.1126/science.adp0212",
            transport=transport,
            env={},
        )

        self.assertEqual(result.query_kind, "url")
        self.assertEqual(result.doi, "10.1126/science.adp0212")
        self.assertEqual(result.provider_hint, "science")
        self.assertEqual(
            result.landing_url,
            "https://www.science.org/doi/full/10.1126/science.adp0212",
        )
        self.assertEqual(transport.calls, [])

    def test_frontiers_url_strips_route_suffix_and_skips_landing_fetch(self) -> None:
        transport = RecordingTransport({})
        url = "https://www.frontiersin.org/journals/marine-science/articles/10.3389/fmars.2023.1101972/full"

        result = resolve_query.resolve_query(url, transport=transport, env={})

        self.assertEqual(result.query_kind, "url")
        self.assertEqual(result.doi, "10.3389/fmars.2023.1101972")
        self.assertEqual(result.provider_hint, "frontiers")
        self.assertEqual(result.landing_url, url)
        self.assertEqual(transport.calls, [])

    def test_iop_pdf_url_strips_route_suffix_and_skips_landing_fetch(self) -> None:
        transport = RecordingTransport({})
        url = "https://iopscience.iop.org/article/10.1088/1748-9326/ab7d02/pdf?download=true"

        result = resolve_query.resolve_query(url, transport=transport, env={})

        self.assertEqual(result.query_kind, "url")
        self.assertEqual(result.doi, "10.1088/1748-9326/ab7d02")
        self.assertEqual(result.provider_hint, "iop")
        self.assertEqual(result.landing_url, url)
        self.assertEqual(transport.calls, [])

    def test_plos_file_url_extracts_query_parameter_doi_without_landing_fetch(
        self,
    ) -> None:
        transport = RecordingTransport({})
        url = "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0123456&type=manuscript"

        result = resolve_query.resolve_query(url, transport=transport, env={})

        self.assertEqual(result.query_kind, "url")
        self.assertEqual(result.doi, "10.1371/journal.pone.0123456")
        self.assertEqual(result.provider_hint, "plos")
        self.assertEqual(result.landing_url, url)
        self.assertEqual(transport.calls, [])

    def test_ams_old_style_article_url_derives_sici_doi_without_landing_fetch(
        self,
    ) -> None:
        transport = RecordingTransport({})
        url = "https://journals.ametsoc.org/view/journals/atsc/24/3/1520-0469_1967_024_0241_teotaw_2_0_co_2.xml"

        result = resolve_query.resolve_query(url, transport=transport, env={})

        self.assertEqual(result.query_kind, "url")
        self.assertEqual(result.doi, "10.1175/1520-0469(1967)024<0241:teotaw>2.0.co;2")
        self.assertEqual(result.provider_hint, "ams")
        self.assertEqual(result.landing_url, url)
        self.assertEqual(transport.calls, [])

    def test_ams_old_style_pdf_url_derives_sici_doi_without_landing_fetch(self) -> None:
        transport = RecordingTransport({})
        url = "https://journals.ametsoc.org/downloadpdf/view/journals/atsc/24/3/1520-0469_1967_024_0241_teotaw_2_0_co_2.pdf"

        result = resolve_query.resolve_query(url, transport=transport, env={})

        self.assertEqual(result.query_kind, "url")
        self.assertEqual(result.doi, "10.1175/1520-0469(1967)024<0241:teotaw>2.0.co;2")
        self.assertEqual(result.provider_hint, "ams")
        self.assertEqual(result.landing_url, url)
        self.assertEqual(transport.calls, [])

    def test_sciencedirect_pii_url_skips_landing_fetch_and_keeps_provider_identifier(
        self,
    ) -> None:
        transport = RecordingTransport({})

        result = resolve_query.resolve_query(
            "https://www.sciencedirect.com/science/article/pii/S0959378017300134",
            transport=transport,
            env={},
        )

        self.assertEqual(result.query_kind, "url")
        self.assertIsNone(result.doi)
        self.assertEqual(result.provider_hint, "elsevier")
        self.assertEqual(result.provider_identifiers, {"pii": "S0959378017300134"})
        self.assertEqual(
            result.landing_url,
            "https://www.sciencedirect.com/science/article/pii/S0959378017300134",
        )
        self.assertEqual(transport.calls, [])

    def test_mdpi_numeric_article_url_derives_doi_without_landing_fetch(self) -> None:
        transport = RecordingTransport({})

        result = resolve_query.resolve_query(
            "https://www.mdpi.com/2072-4292/18/10/1673",
            transport=transport,
            env={},
        )

        self.assertEqual(result.query_kind, "url")
        self.assertEqual(result.doi, "10.3390/rs18101673")
        self.assertEqual(result.provider_hint, "mdpi")
        self.assertEqual(
            result.landing_url, "https://www.mdpi.com/2072-4292/18/10/1673"
        )
        self.assertEqual(result.confidence, 1.0)
        self.assertEqual(transport.calls, [])

    def test_mdpi_numeric_article_url_derives_padded_doi_segments(self) -> None:
        transport = RecordingTransport({})

        result = resolve_query.resolve_query(
            "https://www.mdpi.com/2077-0375/15/3/93",
            transport=transport,
            env={},
        )

        self.assertEqual(result.doi, "10.3390/membranes15030093")
        self.assertEqual(result.provider_hint, "mdpi")
        self.assertEqual(transport.calls, [])

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

        result = resolve_query.resolve_query(
            "10.1006/jaer.1996.0085", transport=transport, env={}
        )

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

        result = resolve_query.resolve_query(
            "https://example.test/paper", transport=transport, env={}
        )

        self.assertEqual(result.query_kind, "url")
        self.assertEqual(result.doi, "10.1111/example.doi")
        self.assertEqual(result.provider_hint, "wiley")
        self.assertEqual(transport.calls[0]["timeout"], 20)
        self.assertIn("User-Agent", transport.calls[0]["headers"])
        self.assertIn("Chrome/", str(transport.calls[0]["headers"]["User-Agent"]))
        self.assertEqual(
            transport.calls[0]["headers"]["Accept-Language"], "en-US,en;q=0.9"
        )
        self.assertTrue(transport.calls[0]["retry_on_transient"])

    def test_url_query_follows_relative_redirect_and_absolutizes_landing_url(
        self,
    ) -> None:
        transport = RecordingTransport(
            {
                ("GET", "https://nature.com/articles/sj.bdj.2017.900"): {
                    "status_code": 303,
                    "headers": {
                        "location": "https://www.nature.com/articles/sj.bdj.2017.900"
                    },
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

        result = resolve_query.resolve_query(
            "https://nature.com/articles/sj.bdj.2017.900", transport=transport, env={}
        )

        self.assertEqual(result.query_kind, "url")
        self.assertEqual(result.doi, "10.1038/sj.bdj.2017.900")
        self.assertEqual(
            result.landing_url, "https://www.nature.com/articles/sj.bdj.2017.900"
        )
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
                                        "title": [
                                            "Deep learning for land cover classification"
                                        ],
                                        "container-title": ["Remote Sensing Letters"],
                                        "publisher": "Elsevier",
                                        "URL": "https://example.test/deep-learning",
                                    },
                                    {
                                        "DOI": "10.5555/other",
                                        "title": [
                                            "A distant candidate on crop modelling"
                                        ],
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
        self.assertEqual(
            transport.calls[0]["query"]["query.bibliographic"],
            "Deep learning for land cover classification",
        )

    def test_title_query_uses_crossref_publisher_and_landing_url_for_provider_hint(
        self,
    ) -> None:
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

        result = resolve_query.resolve_query(
            "A Precise Elsevier Candidate", transport=transport, env={}
        )

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
                                        "title": [
                                            "Hyaluronic acid and tissue mechanics orchestrate mammalian digit tip regeneration"
                                        ],
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

        result = resolve_query.resolve_query(
            "https://example.test/paper", transport=transport, env={}
        )

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
                                        "title": [
                                            "Deep learning for land cover classification"
                                        ],
                                        "container-title": ["Remote Sensing Letters"],
                                        "publisher": "Elsevier",
                                        "URL": "https://example.test/deep-learning",
                                    },
                                    {
                                        "DOI": "10.5555/other",
                                        "title": [
                                            "A distant candidate on crop modelling"
                                        ],
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

        result = resolve_query.resolve_query(
            "https://example.test/paper", transport=transport, env={}
        )

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
                        b"<title>Redirecting to ScienceDirect...</title>"
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
                                        "title": [
                                            "Seasonality of vegetation greenness in Southeast Asia unveiled by geostationary satellite observations"
                                        ],
                                        "container-title": [
                                            "Remote Sensing of Environment"
                                        ],
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
        self.assertIn("Chrome/", transport.calls[0]["headers"]["User-Agent"])
        self.assertEqual(
            transport.calls[0]["headers"]["Accept-Language"], "en-US,en;q=0.9"
        )
        self.assertTrue(transport.calls[0]["retry_on_transient"])
        self.assertEqual(
            transport.calls[1]["query"]["query.bibliographic"], result.title
        )

    def test_url_query_wraps_request_failure_from_landing_page_fetch(self) -> None:
        class FailingTransport(RecordedStreamTransport):
            def request(self, *args, **kwargs):
                raise resolve_query.RequestFailure(
                    502, "HTTP 502 for https://example.test/paper"
                )

        with self.assertRaises(resolve_query.ProviderFailure) as context:
            resolve_query.resolve_query(
                "https://example.test/paper", transport=FailingTransport(), env={}
            )

        self.assertEqual(context.exception.code, "error")
        self.assertIn("Failed to fetch landing page", context.exception.message)

    def test_url_query_with_embedded_doi_falls_back_to_doi_when_landing_page_is_blocked(
        self,
    ) -> None:
        class FailingTransport(RecordedStreamTransport):
            def request(self, *args, **kwargs):
                raise resolve_query.RequestFailure(
                    403,
                    "HTTP 403 for https://www.science.org/doi/epdf/10.1126/science.adp0212",
                )

        result = resolve_query.resolve_query(
            "https://www.science.org/doi/epdf/10.1126/science.adp0212",
            transport=FailingTransport(),
            env={},
        )

        self.assertEqual(result.query_kind, "url")
        self.assertEqual(result.doi, "10.1126/science.adp0212")
        self.assertEqual(
            result.landing_url,
            "https://www.science.org/doi/epdf/10.1126/science.adp0212",
        )
        self.assertEqual(result.provider_hint, "science")
        self.assertEqual(result.confidence, 1.0)

    def test_url_query_does_not_swallow_programming_errors(self) -> None:
        class BrokenTransport(RecordedStreamTransport):
            def request(self, *args, **kwargs):
                raise AttributeError("broken transport")

        with self.assertRaises(AttributeError):
            resolve_query.resolve_query(
                "https://example.test/paper", transport=BrokenTransport(), env={}
            )

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
                                        "title": [
                                            "Climate change impacts on crop yield"
                                        ],
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

        result = resolve_query.resolve_query(
            "Climate change impacts on crop", transport=transport, env={}
        )

        self.assertIsNone(result.doi)
        self.assertEqual(len(result.candidates), 2)
        self.assertGreater(result.candidates[0]["score"], 0)

    def test_title_query_prefers_formal_article_over_preprint_when_scores_tie(
        self,
    ) -> None:
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
                                        "DOI": "10.1101/2021.08.20.457106",
                                        "title": [
                                            "Avifauna recovers faster in areas less accessible to trapping in regenerating tropical forests"
                                        ],
                                        "URL": "http://biorxiv.org/lookup/doi/10.1101/2021.08.20.457106",
                                    },
                                    {
                                        "DOI": "10.1016/j.biocon.2023.109901",
                                        "title": [
                                            "Avifauna recovers faster in areas less accessible to trapping in regenerating tropical forests"
                                        ],
                                        "container-title": ["Biological Conservation"],
                                        "publisher": "Elsevier BV",
                                        "URL": "https://linkinghub.elsevier.com/retrieve/pii/S0006320723000010",
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
            "Avifauna recovers faster in areas less accessible to trapping in regenerating tropical forests",
            transport=transport,
            env={},
        )

        self.assertEqual(result.doi, "10.1016/j.biocon.2023.109901")
        self.assertEqual(result.provider_hint, "elsevier")
        self.assertEqual(result.candidates, [])

    def test_title_query_prefers_wiley_formal_article_over_authorea_preprint(
        self,
    ) -> None:
        title = "The direct and legacy effects of drying-rewetting cycles on active and relatively resistant soil carbon decomposition"
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
                                        "DOI": "10.22541/au.163646098.88346733/v1",
                                        "title": [title],
                                        "publisher": "Authorea, Inc.",
                                        "URL": "https://www.authorea.com/doi/full/10.22541/au.163646098.88346733/v1",
                                    },
                                    {
                                        "DOI": "10.1002/ldr.4594",
                                        "title": [title],
                                        "container-title": [
                                            "Land Degradation & Development"
                                        ],
                                        "publisher": "Wiley",
                                        "URL": "https://onlinelibrary.wiley.com/doi/10.1002/ldr.4594",
                                    },
                                ]
                            }
                        }
                    ).encode("utf-8"),
                    "url": "https://api.crossref.org/works",
                }
            }
        )

        result = resolve_query.resolve_query(title, transport=transport, env={})

        self.assertEqual(result.doi, "10.1002/ldr.4594")
        self.assertEqual(result.provider_hint, "wiley")
        self.assertEqual(result.candidates, [])

    def test_title_query_with_near_match_selects_single_formal_candidate_over_preprint_conflict(
        self,
    ) -> None:
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
                                        "DOI": "10.1111/cobi.14205",
                                        "title": [
                                            "Identifying global conservation priorities for terrestrial vertebrates based on multiple dimensions of biodiversity"
                                        ],
                                        "container-title": ["Conservation Biology"],
                                        "publisher": "Wiley",
                                        "URL": "https://conbio.onlinelibrary.wiley.com/doi/10.1111/cobi.14205",
                                    },
                                    {
                                        "DOI": "10.1101/2024.01.01.000001",
                                        "title": [
                                            "Identifying global conservation priorities for terrestrial vertebrates based on multidimensions of biodiversity"
                                        ],
                                        "URL": "https://www.biorxiv.org/content/10.1101/2024.01.01.000001v1",
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
            "Identifying global conservation priorities for terrestrial vertebrates based on multidimensions of biodiversity",
            transport=transport,
            env={},
        )

        self.assertEqual(result.doi, "10.1111/cobi.14205")
        self.assertEqual(result.provider_hint, "wiley")
        self.assertEqual(result.candidates, [])

    def test_title_query_keeps_ambiguous_when_multiple_formal_candidates_are_close(
        self,
    ) -> None:
        query = "Climate change impacts on crop"
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
                                        "title": [
                                            "Climate change impacts on crop yield"
                                        ],
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
                                    {
                                        "DOI": "10.1101/2024.01.01.000001",
                                        "title": [query],
                                        "URL": "https://www.biorxiv.org/content/10.1101/2024.01.01.000001v1",
                                    },
                                ]
                            }
                        }
                    ).encode("utf-8"),
                    "url": "https://api.crossref.org/works",
                }
            }
        )

        result = resolve_query.resolve_query(query, transport=transport, env={})

        self.assertIsNone(result.doi)
        self.assertEqual(len(result.candidates), 3)

    def test_structured_title_query_uses_authors_without_query_concatenation(
        self,
    ) -> None:
        title = "Shared structured resolve title"
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
                                        "DOI": "10.1000/wrong-author",
                                        "title": [title],
                                        "author": [
                                            {
                                                "given": "Bob",
                                                "family": "Example",
                                            }
                                        ],
                                        "issued": {"date-parts": [[2024]]},
                                        "container-title": ["Journal A"],
                                    },
                                    {
                                        "DOI": "10.1000/right-author",
                                        "title": [title],
                                        "author": [
                                            {
                                                "given": "Alice",
                                                "family": "Example",
                                            }
                                        ],
                                        "issued": {"date-parts": [[2024]]},
                                        "container-title": ["Journal B"],
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
            resolve_query.StructuredResolveRequest(
                title=title, authors=("Alice Example",), year=2024
            ),
            transport=transport,
            env={},
        )

        self.assertEqual(result.doi, "10.1000/right-author")
        self.assertEqual(
            transport.calls[0]["query"]["query.bibliographic"],
            title,
        )

    def test_structured_title_query_uses_year_as_independent_signal(self) -> None:
        title = "Shared year resolve title"
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
                                        "DOI": "10.1000/old",
                                        "title": [title],
                                        "issued": {"date-parts": [[2020]]},
                                        "container-title": ["Journal A"],
                                    },
                                    {
                                        "DOI": "10.1000/new",
                                        "title": [title],
                                        "issued": {"date-parts": [[2024]]},
                                        "container-title": ["Journal B"],
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
            resolve_query.StructuredResolveRequest(title=title, year=2024),
            transport=transport,
            env={},
        )

        self.assertEqual(result.doi, "10.1000/new")

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
            resolve_query.resolve_query(
                "A title that does not exist", transport=transport, env={}
            )

        self.assertEqual(ctx.exception.code, "no_result")


if __name__ == "__main__":
    unittest.main()
