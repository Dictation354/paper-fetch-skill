from __future__ import annotations
from unittest import mock
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from paper_fetch.providers import _acs_html
from paper_fetch.providers.atypon_browser_workflow import (
    extract_atypon_browser_workflow_markdown,
)
from paper_fetch.providers.atypon_browser_workflow.asset_scopes import (
    extract_browser_workflow_asset_html_scopes,
)
from paper_fetch.providers.browser_workflow.assets import (
    _discover_browser_workflow_figure_original_url,
)
from tests.golden_criteria import golden_criteria_asset


ACS_SAMPLE_DOI = "10.1021/acsomega.4c03987"
ACS_SAMPLE_LANDING = f"https://pubs.acs.org/doi/{ACS_SAMPLE_DOI}"
ACS_FORMULA_DOI = "10.1021/acsomega.3c06992"


def test_acs_silverchair_structure_fixture_extracts_complete_current_article() -> None:

    html = golden_criteria_asset(ACS_SAMPLE_DOI, "original.html").read_text(
        encoding="utf-8"
    )
    # The original already contains a loaded nested Figshare article. Verify
    # this positive template separately from the oversized injected viewer.
    soup = BeautifulSoup(html, "lxml")
    viewer = soup.select_one("figshare-widget article")
    assert viewer is not None
    assert "Skip to fig share navigation" in viewer.get_text(" ", strip=True)

    markdown, extraction = extract_atypon_browser_workflow_markdown(
        html,
        ACS_SAMPLE_LANDING,
        "acs",
        metadata={
            "doi": ACS_SAMPLE_DOI,
            "title": (
                "Functionalized Metal-Free Carbon Nanosphere Catalyst for the "
                "Selective C–N Bond Formation under Open-Air Conditions"
            ),
        },
    )
    body_html, supplementary_html = extract_browser_workflow_asset_html_scopes(
        html,
        ACS_SAMPLE_LANDING,
        "acs",
    )
    assets = _acs_html.scoped_asset_extractor(
        body_html,
        ACS_SAMPLE_LANDING,
        asset_profile="all",
        supplementary_html_text=supplementary_html,
    )

    assert len(markdown) > 30_000
    assert "## 1. Introduction" in markdown
    assert "## 5. Conclusions" in markdown
    assert "Open figure viewer" not in markdown
    assert "Close modal" not in markdown
    assert "View Large" not in markdown
    assert "Skip to fig share navigation" not in markdown
    assert len(extraction["references"]) == 45
    assert extraction["references"][0]["year"] == "2018"
    assert sum(asset["kind"] == "figure" for asset in assets) == 10
    figures = [asset for asset in assets if asset.get("dom_id", "").startswith("fig")]
    table_graphics = [
        asset for asset in assets if asset.get("dom_id") in {"gr8", "gr9"}
    ]
    assert len(table_graphics) == 2
    assert all("Expires=" in asset["url"] for asset in table_graphics)
    assert all(not asset.get("full_size_url") for asset in table_graphics)
    assert all(
        urlparse(figure["full_size_url"]).hostname == "acs.silverchair-cdn.com"
        for figure in figures
    )
    assert [
        urlparse(figure["full_size_url"]).path.rsplit("/", 1)[-1] for figure in figures
    ] == [f"ao4c03987_{index:04d}.png" for index in range(1, 9)]
    assert [asset["url"] for asset in assets if asset["kind"] == "supplementary"] == [
        "https://pubs.acs.org/acsodf/article-supplement/358560/pdf/ao4c03987_si_001/"
    ]

    figure_page_fetcher = mock.Mock()
    assert (
        _discover_browser_workflow_figure_original_url(
            figures[0],
            figure_page_fetcher=figure_page_fetcher,
            direct_original_first=True,
        )
        == ""
    )
    figure_page_fetcher.assert_not_called()


def test_acs_silverchair_formula_fixture_preserves_mathml_and_tables() -> None:
    html = golden_criteria_asset(ACS_FORMULA_DOI, "original.html").read_text(
        encoding="utf-8"
    )

    markdown, extraction = extract_atypon_browser_workflow_markdown(
        html,
        f"https://pubs.acs.org/doi/{ACS_FORMULA_DOI}",
        "acs",
        metadata={
            "doi": ACS_FORMULA_DOI,
            "title": (
                "General Equation to Estimate the Physicochemical Properties "
                "of Aliphatic Amines"
            ),
        },
    )

    assert len(markdown) > 45_000
    assert markdown.count("$$") == 42
    assert "S_{CNE}" in markdown
    assert "| *n* | PEI |" in markdown
    assert "## 3. Conclusions" in markdown
    assert len(extraction["references"]) == 20
    assert extraction["references"][0]["year"] == "2015"
