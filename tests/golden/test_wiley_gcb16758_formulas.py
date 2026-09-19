"""Real Wiley recapture retains each inline/display formula image identity."""

import hashlib
import json
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import pytest

from paper_fetch.models.markdown import iter_markdown_images
from paper_fetch.providers.browser_workflow.assets import (
    _cached_browser_workflow_assets,
)
from paper_fetch.providers.wiley import WileyClient
from paper_fetch.runtime import RuntimeContext
from tests.paths import REPO_ROOT
from tests.support.verified_source_inputs import (
    build_verified_source_article,
    inspect_original,
)


def test_gcb16758_all_26_formula_positions_keep_their_official_image():
    base = REPO_ROOT / "tests/fixtures/golden_criteria/10.1111_gcb.16758"
    path = base / "acquisition/problem-fixes-2026-09-18-p02/002-rendered-dom.html"
    source_url = "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16758"
    body = path.read_bytes()
    records = json.loads((base / "acquisition/provenance.json").read_text())["records"]
    record = next(r for r in records if r["body_file"] == str(path.relative_to(base)))
    assert record["sha256"] == hashlib.sha256(body).hexdigest()
    assert record["status_code"] == 200
    identity = inspect_original(body, "wiley", "10.1111/gcb.16758", source_url)
    assert identity and identity["identity"] == "matched"
    soup = BeautifulSoup(body.decode(), "lxml")
    expected = []
    for math in soup.select("math"):
        assert not math.get_text(strip=True)
        fallback = math.find_parent("mjx-container").find_previous_sibling()
        assert "fallback__mathEquation" in fallback.get("class", [])
        expected.append(urljoin(source_url, fallback["data-altimg"]))
    assert len(expected) == len(set(expected)) == 26
    article = build_verified_source_article(
        dict(
            sample_id="10.1111_gcb.16758",
            doi="10.1111/gcb.16758",
            provider="wiley",
            format="html",
            source=str(path.relative_to(REPO_ROOT)),
            source_url=source_url,
            identity=identity,
        )
    )
    markdown = article.to_ai_markdown(
        include_refs="all", max_tokens="full_text", asset_profile="all"
    )
    actual = [
        image.url
        for image in iter_markdown_images(markdown)
        if "gcb16758-math-" in image.url
    ]
    assert actual == expected
    assert "[Formula unavailable]" not in markdown
    assert "](/cms/asset/" not in markdown
    assert article.quality.has_fulltext
    assert article.quality.semantic_losses.formula_missing_count == 0
    assert article.quality.semantic_losses.formula_fallback_count == 26


@pytest.mark.parametrize(
    "filename", ["native-mathml-dom.html", "002-rendered-dom.html"]
)
def test_gcb16758_asset_pipeline_keeps_all_official_formula_urls(filename, tmp_path):
    base = REPO_ROOT / "tests/fixtures/golden_criteria/10.1111_gcb.16758"
    path = base / "acquisition/problem-fixes-2026-09-18-p02" / filename
    body = path.read_bytes()
    records = json.loads((base / "acquisition/provenance.json").read_text())["records"]
    record = next(r for r in records if r["body_file"] == str(path.relative_to(base)))
    assert record["sha256"] == hashlib.sha256(body).hexdigest()
    source_url = "https://onlinelibrary.wiley.com/doi/10.1111/gcb.16758"
    soup = BeautifulSoup(body, "lxml")
    assert (
        soup.select_one('meta[name="citation_doi"]')["content"] == "10.1111/gcb.16758"
    )
    expected = [
        urljoin(source_url, node["data-altimg"])
        for node in soup.select(".fallback__mathEquation[data-altimg]")
    ]
    assert len(expected) == len(set(expected)) == 26
    client = WileyClient(transport=None, env={})
    context = RuntimeContext(
        download_dir=tmp_path, artifact_mode="none", asset_profile="body"
    )
    try:
        assets = _cached_browser_workflow_assets(
            client, body.decode(), source_url, asset_profile="body", context=context
        )
    finally:
        context.close()
    formulas = [asset for asset in assets if asset["kind"] == "formula"]
    assert [asset["url"] for asset in formulas] == expected
    assert [asset["preview_url"] for asset in formulas] == expected
