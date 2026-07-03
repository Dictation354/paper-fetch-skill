from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

from paper_fetch.providers import (
    copernicus as copernicus_provider,
    elsevier as elsevier_provider,
    frontiers as frontiers_provider,
    oxfordacademic as oxford_provider,
    plos as plos_provider,
    springer as springer_provider,
)
from paper_fetch.providers.base import (
    ProviderContent,
    ProviderFailure,
    RawFulltextPayload,
)
from paper_fetch.reason_codes import (
    ERROR,
    NO_ACCESS,
    NO_RESULT,
    PDF_FALLBACK,
    RATE_LIMITED,
)


DOI = "10.1000/example"
PDF_FAILURE_CODES = (NO_RESULT, NO_ACCESS, RATE_LIMITED, ERROR)


def _failure(code: str) -> ProviderFailure:
    return ProviderFailure(code, f"{code} route failed.")


def _pdf_payload(provider: str) -> RawFulltextPayload:
    body = b"%PDF-1.7\n"
    return RawFulltextPayload(
        provider=provider,
        source_url="https://example.test/article.pdf",
        content_type="application/pdf",
        body=body,
        content=ProviderContent(
            route_kind=PDF_FALLBACK,
            source_url="https://example.test/article.pdf",
            content_type="application/pdf",
            body=body,
            reason="Downloaded PDF fallback.",
        ),
    )


@pytest.mark.parametrize("code", PDF_FAILURE_CODES)
def test_elsevier_xml_failure_codes_reach_pdf_fallback(code: str) -> None:
    client = elsevier_provider.ElsevierClient(
        transport=mock.Mock(), env={"ELSEVIER_API_KEY": "secret"}
    )
    with (
        mock.patch.object(
            client, "_fetch_official_xml_payload", side_effect=_failure(code)
        ),
        mock.patch.object(
            client, "_fetch_official_pdf_payload", return_value=_pdf_payload("elsevier")
        ) as pdf,
    ):
        payload = client.fetch_raw_fulltext(DOI, {"doi": DOI})

    assert payload.content is not None
    assert payload.content.route_kind == PDF_FALLBACK
    pdf.assert_called_once()


@pytest.mark.parametrize("code", PDF_FAILURE_CODES)
def test_springer_html_failure_codes_reach_pdf_fallback(code: str) -> None:
    client = springer_provider.SpringerClient(transport=mock.Mock(), env={})
    with (
        mock.patch.object(client, "_prepare_html_attempt", side_effect=_failure(code)),
        mock.patch.object(
            client,
            "_fetch_pdf_payload_from_html_attempt",
            return_value=_pdf_payload("springer"),
        ) as pdf,
    ):
        payload = client.fetch_raw_fulltext(DOI, {"doi": DOI})

    assert payload.content is not None
    assert payload.content.route_kind == PDF_FALLBACK
    pdf.assert_called_once()


@pytest.mark.parametrize("code", PDF_FAILURE_CODES)
def test_copernicus_xml_failure_codes_reach_pdf_fallback(code: str) -> None:
    client = copernicus_provider.CopernicusClient(transport=mock.Mock(), env={})
    landing_attempt = SimpleNamespace(source_trail=["fulltext:copernicus_landing_ok"])
    with (
        mock.patch.object(
            client, "_prepare_landing_attempt", return_value=landing_attempt
        ),
        mock.patch.object(client, "_fetch_xml_payload", side_effect=_failure(code)),
        mock.patch.object(
            client, "_fetch_pdf_payload", return_value=_pdf_payload("copernicus")
        ) as pdf,
    ):
        payload = client.fetch_raw_fulltext(DOI, {"doi": DOI})

    assert payload.content is not None
    assert payload.content.route_kind == PDF_FALLBACK
    pdf.assert_called_once()


@pytest.mark.parametrize("code", PDF_FAILURE_CODES)
def test_oxford_html_failure_codes_reach_pdf_fallback(code: str) -> None:
    client = oxford_provider.OxfordAcademicClient(transport=mock.Mock(), env={})
    with (
        mock.patch.object(client, "_fetch_article_attempt", side_effect=_failure(code)),
        mock.patch.object(
            client, "_fetch_pdf_payload", return_value=_pdf_payload("oxfordacademic")
        ) as pdf,
    ):
        payload = client.fetch_raw_fulltext(DOI, {"doi": DOI})

    assert payload.content is not None
    assert payload.content.route_kind == PDF_FALLBACK
    pdf.assert_called_once()


def test_oxford_pdf_fallback_reports_text_only_artifact_marker() -> None:
    client = oxford_provider.OxfordAcademicClient(transport=mock.Mock(), env={})

    artifacts = client.describe_artifacts(_pdf_payload("oxfordacademic"))

    assert not artifacts.allow_related_assets
    assert artifacts.text_only
    assert [event.marker() for event in artifacts.skip_trace] == [
        "download:oxfordacademic_assets_skipped_text_only"
    ]


@pytest.mark.parametrize("code", PDF_FAILURE_CODES)
def test_plos_xml_failure_codes_reach_pdf_fallback(code: str) -> None:
    client = plos_provider.PlosClient(transport=mock.Mock(), env={})
    with (
        mock.patch.object(client, "_fetch_xml_payload", side_effect=_failure(code)),
        mock.patch.object(
            client, "_fetch_pdf_payload", return_value=_pdf_payload("plos")
        ) as pdf,
    ):
        payload = client.fetch_raw_fulltext(DOI, {"doi": DOI})

    assert payload.content is not None
    assert payload.content.route_kind == PDF_FALLBACK
    pdf.assert_called_once()


@pytest.mark.parametrize("code", PDF_FAILURE_CODES)
def test_frontiers_xml_failure_codes_reach_pdf_fallback(code: str) -> None:
    client = frontiers_provider.FrontiersClient(transport=mock.Mock(), env={})
    route = SimpleNamespace()
    with (
        mock.patch.object(client, "route_candidates", return_value=[route]),
        mock.patch.object(client, "_fetch_xml_payload", side_effect=_failure(code)),
        mock.patch.object(
            client, "_fetch_pdf_payload", return_value=_pdf_payload("frontiers")
        ) as pdf,
    ):
        payload = client.fetch_raw_fulltext(DOI, {"doi": DOI})

    assert payload.content is not None
    assert payload.content.route_kind == PDF_FALLBACK
    pdf.assert_called_once()
