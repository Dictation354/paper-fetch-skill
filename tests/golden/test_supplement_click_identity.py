"""Original publisher links remain usable without changing body discovery."""

from urllib.parse import urljoin, urlsplit
import json

from bs4 import BeautifulSoup
import pytest

from paper_fetch.providers import (
    _annualreviews_html,
    _iop_html,
    _mdpi_assets,
    royalsocietypublishing,
)
from paper_fetch.providers._ieee_supplementary import (
    _supplementary_assets_from_ieee_multimedia_payload,
)
from paper_fetch.providers.browser_workflow.asset_download import (
    _CLICK_SUPPLEMENT_PROVIDERS,
    plan_browser_asset_download,
)
from paper_fetch.runtime import RuntimeContext
from tests.golden_criteria import golden_criteria_asset
from tests.provider_benchmark_samples import provider_benchmark_sample
from tests.support.acquired_article_assets import CLIENTS


@pytest.mark.parametrize(
    "provider", sorted(_CLICK_SUPPLEMENT_PROVIDERS - {"ieee", "iop"})
)
def test_real_article_supplement_href_and_body_scope(provider, tmp_path):
    sample = provider_benchmark_sample(provider)
    doi, source_url = sample.doi, sample.landing_url
    if provider == "science":
        doi = "10.1126/sciadv.adl6155"
        source_url = "https://www.science.org/doi/full/" + doi
    elif provider == "mdpi":
        doi = "10.3390/s23010001"
        source_url = "https://www.mdpi.com/1424-8220/23/1/1"
    elif provider == "annualreviews":
        doi = "10.1146/annurev-neuro-062111-150343"
        source_url = "https://www.annualreviews.org/content/journals/" + doi
    raw = golden_criteria_asset(doi, "original.html").read_text()
    owner = {"mdpi": _mdpi_assets, "annualreviews": _annualreviews_html}.get(provider)
    if owner is not None:
        all_assets = owner.extract_scoped_html_assets(
            raw, source_url, asset_profile="all"
        )
        body_assets = owner.extract_scoped_html_assets(
            raw, source_url, asset_profile="body"
        )
    else:
        client_class = (
            royalsocietypublishing.RoyalsocietypublishingClient
            if provider == "royalsocietypublishing"
            else CLIENTS[provider]
        )
        client = client_class(None, {})
        with RuntimeContext(env={}) as runtime:

            def plan(profile):
                return plan_browser_asset_download(
                    article_id=doi,
                    output_dir=tmp_path,
                    html_text=raw,
                    source_url=source_url,
                    profile={
                        "client": client,
                        "context": runtime,
                        "asset_profile": profile,
                    },
                    deps=client.deps,
                )

            all_plan, body_plan = plan("all"), plan("body")
            all_assets = all_plan.body_assets + all_plan.supplementary_assets
            body_assets = body_plan.body_assets
            assert not body_plan.supplementary_assets
    supplements = [asset for asset in all_assets if asset["kind"] == "supplementary"]
    assert body_assets == [
        asset for asset in all_assets if asset["kind"] != "supplementary"
    ]
    hrefs = {node.get("href") for node in BeautifulSoup(raw, "lxml").select("a[href]")}
    for asset in supplements:
        assert asset["source_href"] in hrefs
        assert asset["source_page_url"] == source_url
        if provider == "mdpi":
            assert urlsplit(urljoin(source_url, asset["source_href"])).path == (
                urlsplit(source_url).path + "/s1"
            )
        else:
            assert urljoin(source_url, asset["source_href"]) == asset["url"]
    if provider in {"mdpi", "annualreviews", "science", "wiley"}:
        assert supplements, "Known captured article must retain its attachments"


def test_real_ieee_multimedia_retains_filename_and_click_page():
    doi = "10.1109/RITA.2026.3668995"
    payload = json.loads(golden_criteria_asset(doi, "multimedia.json").read_text())
    source = "https://ieeexplore.ieee.org/document/11417163/"
    assets = _supplementary_assets_from_ieee_multimedia_payload(payload, source)
    assert assets
    for asset in assets:
        assert asset["source_page_url"] == source
        assert asset["source_href"] == asset["url"]
        assert any(
            item.get("fileName") == asset.get("filename_hint")
            for item in payload["multimedia"]
        )


def test_real_iop_directory_retains_attachment_id_and_original_link():
    doi = "10.1088/1748-9326/ab7d02"
    source = "https://iopscience.iop.org/article/" + doi + "/data"
    raw = golden_criteria_asset(
        doi, "acquisition/network-repair/supplementary-index.html"
    ).read_text()
    assets = _iop_html.extract_supplementary_data_assets(raw, source, expected_doi=doi)
    assert assets
    soup = BeautifulSoup(raw, "lxml")
    for asset in assets:
        anchor = soup.find(id=asset["source_ref"])
        assert anchor is not None
        assert anchor.get("href") == asset["source_href"]
        assert asset["source_page_url"] == source


@pytest.mark.parametrize(
    "provider", ["science", "wiley", "mdpi", "annualreviews", "acs", "iop"]
)
def test_independent_supplementary_scope_replays_publisher_material_links(provider):
    from paper_fetch.providers.supplementary import _html_assets
    from paper_fetch.extraction.html._metadata import parse_html_metadata
    from paper_fetch.providers import annualreviews, mdpi

    sample = provider_benchmark_sample(provider)
    doi, url = sample.doi, sample.landing_url
    if provider == "science":
        doi, url = (
            "10.1126/sciadv.adl6155",
            "https://www.science.org/doi/full/10.1126/sciadv.adl6155",
        )
    elif provider == "mdpi":
        doi, url = "10.3390/s23010001", "https://www.mdpi.com/1424-8220/23/1/1"
    elif provider == "annualreviews":
        doi = "10.1146/annurev-neuro-062111-150343"
        url = "https://www.annualreviews.org/content/journals/" + doi
    html = golden_criteria_asset(doi, "original.html").read_text()
    client_class = {
        "mdpi": mdpi.MdpiClient,
        "annualreviews": annualreviews.AnnualreviewsClient,
    }.get(provider, CLIENTS.get(provider))
    client = client_class(None, {})
    with RuntimeContext(env={}) as context:
        assets = _html_assets(client, html, url, context)
    assert assets
    assert all(
        asset.get("kind") == "supplementary" or asset.get("section") == "supplementary"
        for asset in assets
    )
    pdf_url = parse_html_metadata(html, url).get("citation_pdf_url")
    assert not pdf_url or all(asset.get("url") != pdf_url for asset in assets)
    source_links = {
        urljoin(url, str(a.get("href")))
        for a in BeautifulSoup(html, "lxml").select("a[href]")
    }
    for asset in assets:
        assert any(
            asset.get(field) in source_links
            for field in ("url", "download_url", "original_url")
        )


def test_independent_springer_scope_keeps_extended_and_source_data():
    from paper_fetch.providers.supplementary import _html_assets
    from paper_fetch.providers.springer import SpringerClient

    doi = "10.1038/s41561-022-00912-7"
    html = golden_criteria_asset(doi, "original.html").read_text()
    with RuntimeContext(env={}) as context:
        assets = _html_assets(
            SpringerClient(None, {}),
            html,
            "https://www.nature.com/articles/s41561-022-00912-7",
            context,
        )
    assert any(asset.get("asset_kind") == "source_data" for asset in assets)
    assert any("Extended Data" in asset.get("heading", "") for asset in assets)
    assert all(
        asset.get("kind") == "supplementary" or asset.get("section") == "supplementary"
        for asset in assets
    )
