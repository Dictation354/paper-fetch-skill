"""Real PDF bytes through current providers and article rendering.

The converter result is opaque; bibliography/layout quality is not asserted.
The failed HTML/XML responses are injected; this is offline recovery evidence.
"""

import pytest
from paper_fetch.providers.oxfordacademic import OxfordAcademicClient
from paper_fetch.providers.plos import PlosClient
from tests.golden_corpus import golden_corpus_fixture_for_doi
from tests.support._paper_fetch_support import FixtureHtmlTransport, http_response


@pytest.fixture(scope="module", params=["plos", "oxfordacademic"])
def recovered_pdf(request):
    provider = request.param
    doi = {
        "plos": "10.1371/journal.pbio.0040298",
        "oxfordacademic": "10.1093/bioinformatics/btaa153",
    }[provider]
    fixture = golden_corpus_fixture_for_doi(doi)
    pdf_url = fixture.source_url
    transport = FixtureHtmlTransport(
        {
            pdf_url: http_response(
                pdf_url, fixture.raw_path.read_bytes(), "application/pdf"
            )
        }
    )
    client_type = PlosClient if provider == "plos" else OxfordAcademicClient
    client = client_type(transport, {})
    metadata = {"doi": doi, "source_url": pdf_url}
    payload = client.fetch_raw_fulltext(doi, metadata)
    article = client.to_article_model(metadata, payload)
    assert article.source == f"{provider}_pdf"
    assert article.quality.has_fulltext
    return provider, article, payload.content.markdown_text


def test_real_pdf_recovery_keeps_converter_output(recovered_pdf):
    _, article, converted = recovered_pdf
    assert article.sections[0].text == converted
    assert article.references == []
    assert article.to_dict()["sections"][0]["text"] == converted
    for mode in ("none", "top10", "all"):
        assert converted in article.to_ai_markdown(include_refs=mode)
