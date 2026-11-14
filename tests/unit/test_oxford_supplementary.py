"""Oxford supplementary indexes use attachment discovery without body extraction."""

from unittest import mock

import pytest

from paper_fetch.providers import _oxfordacademic_html
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers.oxfordacademic import OxfordAcademicClient
from paper_fetch.runtime import RuntimeContext
from tests.support._paper_fetch_support import RecordingTransport
from tests.support.supplementary import html_page


DOI = "10.1093/bioinformatics/btaa161"
URL = "https://academic.oup.com/bioinformatics/article/36/11/3409/5802463"
META = {"doi": DOI, "title": "Attachment contract", "landing_page_url": URL}
LINKS = '<div class="dataSuppLink"><a href="/suppl_file/data.csv">File 1</a></div>'


def index_transport(html):
    return RecordingTransport(
        {
            ("GET", URL): {
                "url": URL,
                "status_code": 200,
                "headers": {"content-type": "text/html"},
                "body": html.encode(),
            }
        }
    )


@pytest.mark.parametrize("profile", ["none", "body", "all"])
def test_paywalled_index_discovers_material_without_body_or_archival(
    monkeypatch, profile
):
    transport = index_transport(html_page(DOI, links=LINKS))
    client = OxfordAcademicClient(transport, {})
    forbidden = mock.Mock(side_effect=AssertionError("body or attachment download"))
    for method in (
        "fetch_raw_fulltext",
        "to_article_model",
        "pdf_candidates",
        "download_related_assets",
    ):
        monkeypatch.setattr(client, method, forbidden)
    monkeypatch.setattr(_oxfordacademic_html, "extract_markdown", forbidden)
    with RuntimeContext(
        env={}, transport=transport, artifact_mode="none", asset_profile=profile
    ) as context:
        result, acquisition = client.fetch_supplementary(
            DOI, META, None, context=context
        )
    assert result.identity_verified and result.discovery_complete
    assert result.source_urls == [URL]
    assert len(result.assets) == 1
    assert result.assets[0]["url"] == "https://academic.oup.com/suppl_file/data.csv"
    assert result.assets[0]["archive_state"] == "not_archived"
    assert result.status == "degraded"
    assert acquisition.provider == "oxfordacademic"
    assert acquisition.route == "supplementary" and acquisition.transport == "http"
    assert len(transport.calls) == 1
    forbidden.assert_not_called()


def test_index_uses_panel_signature_and_excludes_body_and_unrelated_assets():
    cdn = "https://oup.silverchair-cdn.com/oup/backfile/data.pdf"
    links = f'''<a href="{cdn}?part=1&amp;Signature=old">Supplementary data</a>
    <div class="dataSuppLink"><a href="{cdn}?part=1&amp;Signature=new&amp;Expires=123">File 1</a></div>
    <div class="dataSuppLink"><a href="{cdn}?part=2&amp;Signature=second">File 2</a></div>
    <a href="/article-pdf/1/main.pdf">Supplementary PDF</a>
    <a href="/doi/epdf/{DOI}">Supplementary PDF</a>
    <img src="/figure.png"><a href="https://example.org/reference.pdf">Reference</a>
    <a href="javascript:;">Supplementary Data</a>'''
    transport = index_transport(html_page(DOI, links=links))
    with RuntimeContext(env={}, transport=transport) as context:
        result, _ = OxfordAcademicClient(transport, {}).fetch_supplementary(
            DOI, META, None, context=context
        )
    assert [asset["url"] for asset in result.assets] == [
        cdn + "?part=1&Signature=new&Expires=123",
        cdn + "?part=2&Signature=second",
    ]


@pytest.mark.parametrize(
    "observed,code", [("10.1093/other", "identity_mismatch"), (None, "error")]
)
def test_invalid_identity_stops_before_download(monkeypatch, tmp_path, observed, code):
    page = (
        html_page(observed, links=LINKS)
        if observed
        else f"<html><body>{LINKS}</body></html>"
    )
    transport = index_transport(page)
    client = OxfordAcademicClient(transport, {})
    downloader = mock.Mock(side_effect=AssertionError("unverified attachment"))
    monkeypatch.setattr(client, "download_related_assets", downloader)
    with RuntimeContext(env={}, transport=transport) as context:
        with pytest.raises(ProviderFailure) as caught:
            client.fetch_supplementary(DOI, META, tmp_path, context=context)
    assert caught.value.code == code
    downloader.assert_not_called()


def test_verified_empty_index_returns_no_result():
    transport = index_transport(html_page(DOI, links=""))
    with RuntimeContext(env={}, transport=transport) as context:
        result, _ = OxfordAcademicClient(transport, {}).fetch_supplementary(
            DOI, META, None, context=context
        )
    assert result.identity_verified and result.discovery_complete
    assert result.assets == [] and result.status == "no_result"


def test_partial_download_preserves_failed_item_and_provider_diagnostics(
    monkeypatch, tmp_path
):
    transport = index_transport(
        html_page(DOI, links=LINKS + LINKS.replace("data.csv", "other.csv"))
    )
    client = OxfordAcademicClient(transport, {})
    failure = {
        "kind": "supplementary",
        "reason": "no_access",
        "message": "Attachment denied",
    }

    def download(doi, metadata, raw, output_dir, *, asset_profile, context):
        assert doi == DOI and output_dir == tmp_path and asset_profile == "all"
        assert raw.provider == "oxfordacademic" and raw.content.route_kind == "html"
        assert [asset["kind"] for asset in raw.content.extracted_assets] == [
            "supplementary"
        ] * 2
        return {
            "assets": [
                {**raw.content.extracted_assets[0], "path": str(tmp_path / "data.csv")}
            ],
            "asset_failures": [failure],
        }

    monkeypatch.setattr(client, "download_related_assets", download)
    with RuntimeContext(env={}, transport=transport, asset_profile="none") as context:
        result, _ = client.fetch_supplementary(DOI, META, tmp_path, context=context)
    assert len(result.assets) == 2
    assert result.assets[0]["path"] and not result.assets[1].get("path")
    assert result.asset_failures == [failure] and result.status == "degraded"
