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


def test_persisted_formula_positions_resolve_to_their_own_capture():
    import hashlib
    import json
    from pathlib import Path
    from urllib.parse import urlsplit

    from paper_fetch.models.markdown import iter_markdown_images

    source = BeautifulSoup(
        golden_criteria_asset(DOI, "original.html").read_text(), "lxml"
    )
    urls = [node["src"] for node in source.select('img[src*="/eq-075625-"]')]
    records = json.loads(
        golden_criteria_asset(DOI, "acquisition/provenance.json").read_text()
    )["records"]
    baseline = golden_criteria_asset(DOI, "extracted.md")
    images = [
        i for i in iter_markdown_images(baseline.read_text()) if i.alt == "Formula"
    ]
    hashes = set()
    for url, image in zip(urls, images, strict=True):
        name = Path(urlsplit(url).path).name
        matches = {
            r["sha256"]
            for r in records
            if Path(r.get("original_body_file") or r["body_file"]).name.endswith(name)
            or any(
                Path(urlsplit(str(r.get(k) or "")).path).name == name
                for k in ("requested_url", "final_url")
            )
        }
        digest = hashlib.sha256((baseline.parent / image.url).read_bytes()).hexdigest()
        assert matches == {digest}, name
        hashes.add(digest)
    assert (len(images), len(hashes)) == (128, 94)
