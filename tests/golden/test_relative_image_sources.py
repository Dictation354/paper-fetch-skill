"""P03/P04: recorded relative image URLs survive full article rendering."""

from urllib.parse import urljoin

import pytest
from bs4 import BeautifulSoup

from paper_fetch.providers._atypon_browser_workflow_profiles import publisher_profile
from paper_fetch.providers._springer_assets import extract_figure_assets
from paper_fetch.providers._springer_dom import extract_html_extraction_sidecars
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi
from tests.golden_corpus import build_article_from_fixture
from tests.support.acquired_publisher_inputs import CapturedSourceFixture, _record


@pytest.mark.parametrize(
    "doi,path,count",
    [
        (
            "10.1029/2004GB002273",
            "acquisition/known-gaps-2026-09-16/000-browser_rendered_dom.html",
            1,
        ),
        (
            "10.1175/jtech-d-24-0028.1",
            "acquisition/subscription-2026-09-15/response-002.bin",
            2,
        ),
        (
            "10.1175/jamc-d-24-0048.1",
            "acquisition/assets-2026-09-15/ams-headless-body-001-browser_dom.html",
            5,
        ),
    ],
)
def test_recorded_relative_images_render_with_the_same_article_origin(doi, path, count):
    record, body = _record(doi, path)
    soup = BeautifulSoup(body, "lxml")
    declared = soup.select_one('meta[name="citation_doi"], meta[name="DOI"]')
    assert declared["content"].casefold() == doi.casefold()
    sample = golden_criteria_sample_for_doi(doi)
    sample.update(
        captured_source_path=sample["assets"][path],
        source_url=record["final_url"],
        landing_url=record["final_url"],
        route_kind="html",
    )
    if count == 1:
        originals = [
            ("Formula", soup.select_one('img[src*="gbc1137-math-0001"]')["src"])
        ]
    else:
        originals = []
        for number, table in enumerate(soup.select(".tableWrap"), 1):
            candidates = {a["href"] for a in table.select('a[href*="/full-"]')}
            candidates.update(
                img["data-image-src"]
                for img in table.select('img[data-image-src*="/full-"]')
            )
            assert len(candidates) == 1
            originals.append((f"Table {number}", candidates.pop()))
    assert len(originals) == count
    profile = publisher_profile("wiley" if count == 1 else "ams")
    assets_before = profile.scoped_asset_extractor(
        body.decode(), record["final_url"], asset_profile="body"
    )
    profile.prepare_source_images(soup, record["final_url"])
    assets_after = profile.scoped_asset_extractor(
        str(soup), record["final_url"], asset_profile="body"
    )
    # Resolving renderer input changes neither rendition selection nor download state.
    assert assets_after == assets_before
    article = build_article_from_fixture(
        CapturedSourceFixture(sample["sample_id"], sample)
    )
    assert article.quality.has_fulltext
    rendered = article.to_ai_markdown(include_refs="all", max_tokens="full_text")
    for label, original in originals:
        assert original.startswith("/cms/asset/" if count == 1 else "/view/")
        expected = urljoin(record["final_url"], original)
        assert rendered.count(f"![{label}]({expected})") == 1
        assert f"]({original})" not in rendered
        asset = next(asset for asset in assets_after if asset["url"] == expected)
        assert not asset.get("path")
        assert not asset.get("downloaded_bytes")
        if count == 1:
            assert asset["preview_accepted"] == "true"
        else:
            assert not asset.get("preview_accepted")
            assert asset["full_size_url"] == expected
            assert "/inline-" in asset["preview_url"]


@pytest.mark.parametrize(
    "doi,path,selector",
    [
        (
            "10.1038/s42003-021-02908-2",
            "acquisition/template-gaps-2026-09-16/article-response.html",
            ".c-article-box__content > img",
        ),
        (
            "10.1038/d41586-022-01795-9",
            "acquisition/provenance-repair-2026-09-17/000-http_response_entity.html",
            'article picture.embed img[src*="23214848"]',
        ),
        (
            "10.1038/d41586-023-01829-w",
            "acquisition/provenance-repair-2026-09-17/000-http_response_entity.html",
            'article picture.embed img[src*="25382112"]',
        ),
    ],
)
def test_nature_protocol_relative_images_keep_source_rendition(doi, path, selector):
    record, body = _record(doi, path)
    if "d41586" in doi:
        assert golden_criteria_asset(doi, "original.html").read_bytes() == body
    soup = BeautifulSoup(body, "lxml")
    assert soup.select_one('meta[name="DOI"]')["content"] == doi
    originals = soup.select(selector)
    assert len(originals) == 1
    original = originals[0]["src"]
    assert original.startswith("//media.")
    expected = urljoin(record["final_url"], original)

    cleaned = extract_html_extraction_sidecars(body.decode(), record["final_url"])[
        "cleaned_html"
    ]
    assets_before = extract_figure_assets(cleaned, record["final_url"])
    normalized = BeautifulSoup(cleaned, "lxml")
    for image in normalized.select('img[src^="//"]'):
        image["src"] = urljoin(record["final_url"], image["src"])
    # The protocol supplies context only; existing rendition choices stay intact.
    assert extract_figure_assets(str(normalized), record["final_url"]) == assets_before
    asset = next(
        asset for asset in assets_before if asset.get("preview_url") == expected
    )
    assert not asset.get("path")
    assert not asset.get("downloaded_bytes")
    assert not asset.get("preview_accepted")

    sample = golden_criteria_sample_for_doi(doi)
    sample.update(
        captured_source_path=sample["assets"][path],
        source_url=record["final_url"],
        landing_url=record["final_url"],
        route_kind="html",
    )
    article = build_article_from_fixture(
        CapturedSourceFixture(sample["sample_id"], sample)
    )
    assert article.quality.has_fulltext
    rendered = article.to_ai_markdown(include_refs="all", max_tokens="full_text")
    # Existing identity-based injection may select the asset's recorded full URL.
    target = asset.get("full_size_url") or asset["url"]
    assert target.rsplit("/", 1)[-1] == expected.rsplit("/", 1)[-1]
    assert rendered.count(f"]({target})") == 1
    assert f"]({original})" not in rendered
