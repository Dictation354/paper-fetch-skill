from __future__ import annotations
import pytest
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers.plos import (
    PLOS_JOURNAL_PATHS,
    PlosClient,
    _fetch_plos_redirected_response,
)
from tests.support._paper_fetch_support import FixtureHtmlTransport, http_response


STRUCTURE_DOI = "10.1371/journal.pone.0263725"
TABLE_DOI = "10.1371/journal.pone.0304873"
FORMULA_DOI = "10.1371/journal.pone.0126635"
FIGURE_DOI = "10.1371/journal.pone.0015338"
SUPPLEMENTARY_DOI = "10.1371/journal.pone.0218513"
REFERENCES_DOI = "10.1371/journal.pone.0026949"
PDF_FALLBACK_DOI = "10.1371/journal.pbio.0040298"
STRUCTURE_XML_URL = "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0263725&type=manuscript"
FIGURE_XML_URL = "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0015338&type=manuscript"
PDF_FALLBACK_XML_URL = "https://journals.plos.org/plosbiology/article/file?id=10.1371/journal.pbio.0040298&type=manuscript"
PDF_FALLBACK_URL = "https://journals.plos.org/plosbiology/article/file?id=10.1371/journal.pbio.0040298&type=printable"


def test_unknown_plos_journal_code_uses_canonical_metadata_route() -> None:
    doi = "10.1371/journal.pnew.0000001"
    client = PlosClient(FixtureHtmlTransport({}), {})

    journal_path, reason = client._resolve_journal_path(
        doi,
        {
            "doi": doi,
            "landing_page_url": (f"https://journals.plos.org/plosnew/article?id={doi}"),
        },
    )

    assert journal_path == "plosnew"
    assert reason == "metadata_landing"


def test_unknown_plos_journal_code_uses_doi_resolver_without_persisting_rule() -> None:
    doi = "10.1371/journal.pnew.0000002"
    resolver_url = f"https://doi.org/{doi}"
    canonical_url = f"https://journals.plos.org/plosnew/article?id={doi}"
    resolver_response = http_response(resolver_url, b"", "text/html")
    resolver_response["url"] = canonical_url
    client = PlosClient(
        FixtureHtmlTransport({resolver_url: resolver_response}),
        {},
    )

    journal_path, reason = client._resolve_journal_path(doi, {"doi": doi})

    assert journal_path == "plosnew"
    assert reason == "doi_resolver"
    assert "pnew" not in PLOS_JOURNAL_PATHS


def test_unknown_plos_journal_code_rejects_non_plos_resolver_target() -> None:
    doi = "10.1371/journal.pwrong.0000001"
    resolver_url = f"https://doi.org/{doi}"
    resolver_response = http_response(resolver_url, b"", "text/html")
    resolver_response["url"] = "https://example.org/article"
    client = PlosClient(
        FixtureHtmlTransport({resolver_url: resolver_response}),
        {},
    )

    with pytest.raises(ProviderFailure, match="safe journal route"):
        client._resolve_journal_path(doi, {"doi": doi})


def test_plos_redirect_helper_rejects_invalid_redirect_chains() -> None:
    start_url = "https://journals.plos.org/plosone/article/file?id=test"
    loop_url = "https://journals.plos.org/plosone/article/file?id=loop"
    loop_transport = FixtureHtmlTransport(
        {
            start_url: http_response(
                start_url,
                b"",
                "text/html",
                status_code=302,
                headers={"location": loop_url},
            ),
            loop_url: http_response(
                loop_url,
                b"",
                "text/html",
                status_code=302,
                headers={"location": start_url},
            ),
        }
    )
    missing_location_transport = FixtureHtmlTransport(
        {
            start_url: http_response(
                start_url,
                b"",
                "text/html",
                status_code=302,
            )
        }
    )
    invalid_scheme_transport = FixtureHtmlTransport(
        {
            start_url: http_response(
                start_url,
                b"",
                "text/html",
                status_code=302,
                headers={"location": "file:///tmp/plos.xml"},
            )
        }
    )
    redirect_urls = [
        f"https://journals.plos.org/plosone/article/file?id=hop-{index}"
        for index in range(5)
    ]
    redirect_limit_transport = FixtureHtmlTransport(
        {
            redirect_urls[index]: http_response(
                redirect_urls[index],
                b"",
                "text/html",
                status_code=302,
                headers={
                    "location": (
                        redirect_urls[index + 1]
                        if index + 1 < len(redirect_urls)
                        else f"{redirect_urls[index]}-next"
                    )
                },
            )
            for index in range(len(redirect_urls))
        }
    )

    assert (
        _fetch_plos_redirected_response(loop_transport, start_url, headers={}) is None
    )
    assert (
        _fetch_plos_redirected_response(
            missing_location_transport, start_url, headers={}
        )
        is None
    )
    assert (
        _fetch_plos_redirected_response(invalid_scheme_transport, start_url, headers={})
        is None
    )
    assert (
        _fetch_plos_redirected_response(
            redirect_limit_transport, redirect_urls[0], headers={}
        )
        is None
    )
