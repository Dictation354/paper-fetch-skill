"""Article entitlement stops requests, with local degradation and evidence."""

import pytest
from paper_fetch.providers.base import (
    ProviderFailure,
)
from paper_fetch.quality.access_boundary import (
    confirmed_paywall,
    html_paywall_diagnostics,
)
from tests.block_fixtures import iter_block_samples
from tests.support._paper_fetch_support import RecordingTransport, http_response


DOI = "10.1111/example"
URL = "https://onlinelibrary.wiley.com/doi/" + DOI
ABSTRACT = "Received abstract about the measured properties."
PAGE = f'<meta name="citation_doi" content="{DOI}"><meta name="citation_title" content="Target article"><article><div class="abstract">{ABSTRACT}</div><div id="no-access-message">You do not currently have access to this article.</div></article>'
BODY = (
    "<div class='article-body'><h2>Results</h2>"
    + "<p>"
    + "The measured properties establish reproducible findings. " * 35
    + "</p></div>"
)


@pytest.mark.parametrize(
    "doi",
    [
        "10.1038/nature12915",
        "10.1093/reseval/rvag052",
        "10.1080/01431161.2025.2516689",
        "10.1088/0034-4885/53/3/002",
        "10.1146/annurev-neuro-062111-150343",
    ],
)
def test_real_subscription_pages_confirm_same_article_and_preserve_abstract(doi):
    fixture = next(f for f in iter_block_samples() if f.doi == doi)
    diagnostics = html_paywall_diagnostics(
        fixture.raw_path.read_bytes(),
        metadata={"doi": doi},
        source_url=fixture.source_url,
        provider=fixture.provider,
    )
    assert confirmed_paywall(diagnostics)
    assert diagnostics["content_kind"] == "abstract_only"
    assert diagnostics["received_metadata"]["abstract"]


def test_real_official_api_entitlement_stops_xml_pdf_pii_and_abstract_requests():
    from paper_fetch.providers.elsevier import ElsevierClient
    from tests.golden_criteria import golden_criteria_asset

    doi = "10.1016/0034-4257(94)90046-9"
    body = golden_criteria_asset(
        doi, "acquisition/subscription-2026-09-15/entitlement-response-1.bin"
    ).read_bytes()
    transport = RecordingTransport({})
    client = ElsevierClient(transport, {"ELSEVIER_API_KEY": "test"})
    url = client._official_article_url(doi)
    transport.responses[("GET", url)] = http_response(url, body, "text/xml")
    result = client.fetch_result(
        doi,
        {"doi": doi, "pii": "S0034425794000469", "abstract": ABSTRACT},
        None,
        asset_profile="all",
    )
    assert [call["url"] for call in transport.calls] == [url]
    assert result.article.metadata.abstract == ABSTRACT
    assert result.article.quality.content_kind == "abstract_only"


@pytest.mark.parametrize("provider", ["springer", "oxfordacademic", "ieee"])
def test_http_error_with_real_article_gate_stops_before_browser_or_pdf(provider):
    from paper_fetch.http import RequestFailure
    from paper_fetch.providers.springer import SpringerClient
    from paper_fetch.providers.oxfordacademic import OxfordAcademicClient
    from paper_fetch.providers.ieee import IeeeClient
    from paper_fetch.runtime import RuntimeContext
    from tests.support.acquired_ieee_paywall_flow import (
        _captured_landing,
        URL as IEEE_URL,
    )

    if provider == "ieee":
        html, metadata = _captured_landing()
        url = IEEE_URL
    else:
        doi = (
            "10.1038/nature12915"
            if provider == "springer"
            else "10.1093/reseval/rvag052"
        )
        fixture = next(f for f in iter_block_samples() if f.doi == doi)
        html = fixture.raw_path.read_text()
        url = fixture.source_url
        metadata = {"doi": doi, "landing_page_url": url, "url": url}
    transport = RecordingTransport(
        {
            ("GET", url): RequestFailure(
                403,
                "Forbidden",
                body=html.encode(),
                headers={"content-type": "text/html"},
                url=url,
            )
        }
    )
    client = {
        "springer": SpringerClient,
        "oxfordacademic": OxfordAcademicClient,
        "ieee": IeeeClient,
    }[provider](transport, {})
    with pytest.raises(ProviderFailure) as exc:
        if provider == "springer":
            with RuntimeContext(env={}, transport=transport) as context:
                client._fetch_html_landing(url, context=context)
        elif provider == "oxfordacademic":
            client._fetch_article_attempt(metadata["doi"], metadata)
        else:
            client._fetch_landing_attempt(metadata["doi"], metadata)
    assert confirmed_paywall(exc.value)
    assert [call["url"] for call in transport.calls] == [url]
