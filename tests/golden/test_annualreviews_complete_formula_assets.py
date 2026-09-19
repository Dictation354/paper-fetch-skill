"""Legacy inline equation GIFs remain discoverable alongside display equations."""

from urllib.parse import urljoin
from bs4 import BeautifulSoup
from paper_fetch.providers import _annualreviews_html
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi


DOI = "10.1146/annurev-control-090419-075625"


def test_every_source_equation_gif_has_one_discovered_asset():
    sample = golden_criteria_sample_for_doi(DOI)
    source_url = sample["source_url"]
    raw = golden_criteria_asset(DOI, "original.html").read_text()
    soup = BeautifulSoup(raw, "lxml")
    expected = {
        urljoin(source_url, image["src"])
        for image in soup.select('img[src*="/eq-075625-"]')
    }
    assert len(expected) == 128
    assets = _annualreviews_html.extract_scoped_html_assets(
        raw, source_url, asset_profile="body"
    )
    formulas = [a for a in assets if "/eq-075625-" in a.get("url", "")]
    assert {a["url"] for a in formulas} == expected
    assert len(formulas) == len(expected)
    assert all(a["kind"] == "formula" for a in formulas)
    cleaned, _ = _annualreviews_html.extract_asset_html_scopes(raw, source_url)
    assert all(
        image["src"].startswith("https://")
        for image in BeautifulSoup(cleaned, "lxml").select("img.inline-formula[src]")
    )
