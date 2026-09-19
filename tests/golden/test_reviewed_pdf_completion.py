"""Remaining original PDFs through current provider/service assembly.

Only retrieval of the captured PDF and metadata is injected. The PDF parser,
route-aware provider assembly and service rendering are the current code.
"""

from unittest import mock
import pytest
from paper_fetch.http import HttpTransport
from paper_fetch.providers._pdf_common import pdf_fetch_result_from_bytes
from paper_fetch.providers._registry import provider_bundle
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from tests.golden_corpus import golden_corpus_fixture_for_doi
from tests.support.reviewed_block_provider_paths import _fetch_through_service


CASES = [
    ("10.1146/annurev-med-120811-171056", "annualreviews"),
    ("10.1021/acsomega.2c02828", "acs"),
]


@pytest.fixture(scope="module", params=CASES, ids=[case[1] for case in CASES])
def completed_pdf(request):
    doi, provider = request.param
    fixture = golden_corpus_fixture_for_doi(doi)
    body = fixture.raw_path.read_bytes()
    result = pdf_fetch_result_from_bytes(
        artifact_dir=None,
        source_url=fixture.source_url,
        final_url=fixture.source_url,
        pdf_bytes=body,
    )
    metadata = {
        "doi": doi,
        "title": fixture.title,
        "provider": provider,
        "official_provider": True,
    }
    payload = RawFulltextPayload(
        provider=provider,
        content=ProviderContent(
            route_kind="pdf_fallback",
            source_url=fixture.source_url,
            content_type="application/pdf",
            body=body,
            markdown_text=result.markdown_text,
            merged_metadata=metadata,
        ),
    )
    client = provider_bundle(provider).client_factory(HttpTransport(), {})
    with mock.patch.object(client, "fetch_raw_fulltext", return_value=payload):
        envelope = _fetch_through_service(client, fixture, metadata)
    assert envelope.article is not None
    return fixture, envelope.article, client, payload


def test_real_pdf_is_opaque_through_service(completed_pdf):
    _, article, _, payload = completed_pdf
    assert article.sections[0].text == payload.content.markdown_text
    assert article.references == []
    for mode in ("none", "top10", "all"):
        assert payload.content.markdown_text in article.to_ai_markdown(
            include_refs=mode
        )
    assert article.to_dict()["sections"][0]["text"] == payload.content.markdown_text
    assert len(article.to_ai_markdown(max_tokens=500)) < len(article.to_ai_markdown())
