"""P17: source-owned identities and positions for every captured T&F formula."""

import json
from types import SimpleNamespace
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from paper_fetch.models.markdown import iter_markdown_images
from paper_fetch.providers._atypon_browser_workflow_profiles import publisher_profile
from paper_fetch.providers.atypon_browser_workflow.asset_scopes import (
    extract_browser_workflow_asset_html_scopes,
)
from tests.golden_criteria import source_selections
from tests.paths import REPO_ROOT
from tests.support.canonical_content import source_prose_blocks
from tests.support.object_content import assert_object_position
from tests.support.test_evidence import evidence_cache
from tests.support.verified_source_inputs import (
    build_verified_source_article,
    inspect_original,
)

DOI = "10.1080/08839514.2024.2375110"


@evidence_cache
def _source():
    rows = source_selections()
    row = next(r for r in rows if r["doi"] == DOI)
    raw = (REPO_ROOT / row["source"]).read_bytes()
    identity = inspect_original(raw, "tandf", DOI, row["source_url"])
    assert identity and identity["identity"] == "matched"
    article = build_verified_source_article({**row, "identity": identity})
    return BeautifulSoup(raw.decode(), "lxml"), article, row["source_url"]


def test_all_captured_formula_pairs_keep_source_identity_order_and_position():
    soup, article, source_url = _source()
    body = soup.select_one(".hlFld-Fulltext")
    pairs = body.select(".NLM_disp-formula-image")
    assert len(pairs) == 232
    expected = []
    display = []
    for pair in pairs:
        image = pair.select_one('img[src="//:0"][data-formula-source]')
        data = json.loads(image["data-formula-source"])
        assert data["type"] == "image"
        assert data["src"].startswith("/cms/asset/")
        representation = pair.find_next_sibling()
        assert "NLM_disp-formula" in representation.get("class", [])
        placeholder = representation.select_one('img[src="//:0"][data-formula-source]')
        assert json.loads(placeholder["data-formula-source"])["type"] == "mathjax"
        assert representation.select_one("mjx-container mjx-math") is not None
        assert (
            representation.select_one('math, tex-math, script[type^="math/tex"]')
            is None
        )
        expected.append(urljoin(source_url, data["src"]))
        if "disp-formula" in representation["class"]:
            display.append((representation, expected[-1]))
    assert len(set(expected)) == 232
    assert (
        len(display) == 46
    )  # 92 old invalid outputs were two representations per equation.
    markdown = article.to_ai_markdown(include_refs="all", asset_profile="all")
    actual = [i for i in iter_markdown_images(markdown) if i.url in set(expected)]
    assert [i.url for i in actual] == expected
    runs = [
        run
        for _, group in source_prose_blocks(
            SimpleNamespace(provider="tandf", doi=DOI), soup
        )
        for run in group
    ]
    for pair, rendered in zip(pairs, actual, strict=True):
        assert assert_object_position(
            pair, markdown, rendered.start, rendered.end, runs
        ), pair
    for representation, url in display:
        image = next(i for i in actual if i.url == url)
        label = representation.select_one(".disp_formula_label_div")
        if label:
            number = label.get_text(strip=True).strip("()")
            assert (
                f"**Equation {number}.**"
                in markdown[max(0, image.start - 65) : image.start]
            )
    assert "//:0" not in markdown and "[Formula unavailable]" not in markdown
    assert article.quality.semantic_losses.formula_fallback_count == 232
    assert article.quality.semantic_losses.formula_missing_count == 0
    body_html, supplementary_html = extract_browser_workflow_asset_html_scopes(
        str(soup), source_url, "tandf"
    )
    assets = publisher_profile("tandf").scoped_asset_extractor(
        body_html,
        source_url,
        asset_profile="body",
        supplementary_html_text=supplementary_html,
    )
    formula_assets = [a for a in assets if a["url"] in set(expected)]
    assert [a["url"] for a in formula_assets] == expected
    assert {a["kind"] for a in formula_assets} == {"formula"}
