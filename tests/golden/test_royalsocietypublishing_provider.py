from __future__ import annotations
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from bs4 import BeautifulSoup
from paper_fetch.providers import (
    _royalsocietypublishing_html,
)
from tests.golden_corpus import GoldenCorpusFixture, build_article_from_fixture
from tests.golden_criteria import golden_criteria_sample_for_doi
from tests.support.acquired_publisher_inputs import CapturedSourceFixture, _record


def test_recorded_section_links_resolve_to_original_heading_targets() -> None:
    doi = "10.1098/rsif.2019.0334"
    path = "acquisition/article-response-2026-09-15.bin"
    record, body = _record(doi, path)
    soup = BeautifulSoup(body, "lxml")
    assert soup.select_one('meta[name="citation_doi"]')["content"] == doi
    links = soup.select('.article-body a[href="#s2"], .article-body a[href="#s3"]')
    assert [a["href"] for a in links] == ["#s2", "#s3", "#s2", "#s2", "#s2", "#s3"]
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
    markdown = article.to_ai_markdown(include_refs="all", max_tokens="full_text")
    cursor = 0
    for link in links:
        legacy_id = link["href"][1:]
        targets = soup.select(f'.article-body h2[data-legacyid="{legacy_id}"]')
        assert len(targets) == 1
        target = targets[0]
        assert target["id"] == {"s2": "19033670", "s3": "19033689"}[legacy_id]
        assert soup.find(id=target["id"]) is target
        assert f"## {target.get_text(' ', strip=True)}" in markdown
        expected = (
            f"[{link.get_text(strip=True)}]({record['final_url']}#{target['id']})"
        )
        cursor = markdown.index(expected, cursor) + len(expected)
        assert f"]({link['href']})" not in markdown
    assert markdown.count(f"]({record['final_url']}#19033670)") == 4
    assert markdown.count(f"]({record['final_url']}#19033689)") == 2
    external = soup.select_one(
        '.article-body a[href="https://github.com/ogplexus/WAIT"]'
    )
    assert f"GitHub ({external['href']})" in markdown
    rendered_html = _royalsocietypublishing_html._markdown_render_html(
        str(soup.select_one(".article-body")), record["final_url"]
    )
    rendered_external = BeautifulSoup(rendered_html, "lxml").select_one(
        'a[href="https://github.com/ogplexus/WAIT"]'
    )
    assert rendered_external == external


def _render_markdown_for_fixture(doi: str) -> str:
    sample = golden_criteria_sample_for_doi(doi)
    fixture = GoldenCorpusFixture(sample_id=str(sample["sample_id"]), sample=sample)
    article = build_article_from_fixture(fixture)
    return article.to_ai_markdown(include_refs="all")


def test_royal_fixture_extracts_signed_original_viewer_and_preview_urls() -> None:
    fixture_path = Path(
        "tests/fixtures/golden_criteria/10.1098_rsta.2019.0558/original.html"
    )
    extraction = _royalsocietypublishing_html.extract_markdown(
        fixture_path.read_text(encoding="utf-8"),
        "https://royalsocietypublishing.org/doi/10.1098/rsta.2019.0558",
    )
    figures = [
        asset for asset in extraction.extracted_assets if asset.get("kind") == "figure"
    ]

    assert len(figures) == 2
    for index, asset in enumerate(figures, start=1):
        full_size_url = str(asset["full_size_url"])
        preview_url = str(asset["preview_url"])
        figure_page_url = str(asset["figure_page_url"])
        assert asset["url"] == full_size_url
        assert f"rsta20190558f0{index}.png" in urlparse(full_size_url).path
        assert f"m_rsta20190558f0{index}.png" in urlparse(preview_url).path
        assert "/view-large/figure/" in figure_page_url
        assert urlparse(figure_page_url).path.endswith(f"rsta20190558f0{index}.tif")
        assert set(parse_qs(urlparse(full_size_url).query)) >= {
            "Expires",
            "Signature",
            "Key-Pair-Id",
        }
        assert "/view-large/figure/" not in full_size_url


def test_royal_grouped_slide_url_is_not_assigned_to_the_wrong_figure() -> None:
    fixture_path = Path(
        "tests/fixtures/golden_criteria/10.1098_rsos.150470/original.html"
    )
    extraction = _royalsocietypublishing_html.extract_markdown(
        fixture_path.read_text(encoding="utf-8"),
        "https://royalsocietypublishing.org/doi/10.1098/rsos.150470",
    )
    figures = {
        str(asset["heading"]): asset
        for asset in extraction.extracted_assets
        if asset.get("kind") == "figure"
    }

    assert len(figures) == 5
    assert "full_size_url" not in figures["Figure 1"]
    assert "/m_rsos150470f01.jpeg" in figures["Figure 1"]["preview_url"]
    assert "/rsos150470f02.jpeg" in figures["Figure 2"]["full_size_url"]
    assert "full_size_url" not in figures["Figure 3"]
    assert "/rsos150470f04.jpeg" in figures["Figure 4"]["full_size_url"]


def test_markdown_contract_structure_fixture() -> None:

    # markdown-review: purpose=structure doi=10.1098/rsta.2019.0558
    markdown = _render_markdown_for_fixture("10.1098/rsta.2019.0558")
    assert (
        "# Creation and application of virtual patient cohorts of heart models"
        in markdown
    )
    assert "# 10.1098/rsta.2019.0558" not in markdown
    assert "## Abstract" in markdown
    assert markdown.count("## Abstract") == 1
    assert "virtual patient cohorts" in markdown
    assert "Schematic of the strategies for obtaining a virtual cohort" in markdown
    assert (
        "| [9] | 35 samples from ex vivo RAA | atrial model calibration | 0D | RVAC |"
        in markdown
    )
    assert (
        "The parameter set for each member of the virtual cohort can be obtained in three ways"
        in markdown
    )
    assert (
        "| [22] | $70\\,\\text{(training)} + 60\\,\\text{(test)} + 3\\,(12\\, k\\,\\text{samples})$ | shape uncertainty | LA | SID |"
        in markdown
    )
    assert (
        "| [23,24] | 5 PsAF | patient-specific modelling of atrial action potentials |  | 1:1 |"
        in markdown
    )
    assert "| [ |" not in markdown
    assert "## Authors' contributions" in markdown
    assert "## Competing interests" in markdown
    assert "## Funding" in markdown
    assert "We declare we have no competing interest." in markdown
    assert "RF Government Act No. 211" in markdown
    assert "Bootstrap methods: another look at the jackknife" in markdown
    assert "A new optimizer using particle swarm theory" in markdown
    assert re.search(r"(?m)^1\. Niederer SA", markdown)
    assert not re.search(r"(?m)^- Niederer SA", markdown)
    assert not re.search(r"(?m)^- Efron B\\s*\\.?\\s*1992\\s*$", markdown)
    assert not re.search(r"(?m)^- Eberhart R, Kennedy J\\s*\\.?\\s*1995\\s*$", markdown)
    assert "creativecommons" not in markdown.lower()
    assert "which permits unrestricted use" not in markdown
    assert "Close navigation menu" not in markdown
    assert "Open figure viewer" not in markdown
    assert "javascript:;" not in markdown
    assert not re.search(r"(?m)^- Figure$", markdown)
    assert "\n## Figures\n" not in markdown


def test_markdown_contract_table_fixture() -> None:
    # markdown-review: purpose=table doi=10.1098/rspb.2020.0097
    markdown = _render_markdown_for_fixture("10.1098/rspb.2020.0097")
    assert "table 1" in markdown
    assert "male reproductive success" in markdown
    assert "Table 1: Results from PCA for male dominance" in markdown
    assert (
        "Table 2: Full model outputs from generalized linear negative binomial model"
        in markdown
    )
    assert markdown.count("|  | PC1 | PC2 |") == 1
    assert (
        markdown.count(r"| parameter | estimate | s.e. | z-value | Pr(>\|z\|) |") == 1
    )
    # Original table cells use a superscript Roman numeral for this estimator.
    assert re.search(r"(?m)^\| F <sup>III</sup> \| .+ \|$", markdown)
    assert re.search(r"(?m)^\| PC2: F <sup>III</sup> \| .+ \|$", markdown)
    assert not re.search(r"(?m)^(?:F|PC2: F) <sup>III</sup> \|", markdown)
    assert "## Ethics" in markdown
    assert "## Data accessibility" in markdown
    assert "Dryad Digital Repository" in markdown
    assert "## Acknowledgements" in markdown
    assert "Daniel Nugent" in markdown
    assert "Download slide" not in markdown
    assert "Article navigation" not in markdown
    assert re.search("(?m)^\\|.+\\|$", markdown)


def test_markdown_contract_formula_fixture() -> None:
    # markdown-review: purpose=formula doi=10.1098/rsos.201188
    markdown = _render_markdown_for_fixture("10.1098/rsos.201188")
    assert "Black" in markdown
    assert "Scholes" in markdown
    assert r"\text{price} = \text{BS}(S_{0},K,T,\sigma)." in markdown
    assert r"x_{t}^{i} = \sum\limits_{\, j = 1}^{n}a_{ij}x_{t - 1}^{j}" in markdown
    assert "consensus to $" in markdown
    assert r"}{\overset{\sim}{X}}_{t - 1}e_{t}" not in markdown
    assert r"\text{and\textbackslash~}" not in markdown
    assert "Atand" not in markdown
    assert "εinot" not in markdown
    assert "- —" not in markdown
    assert "Open figure viewer" not in markdown
    assert "Download slide" not in markdown
    assert "javascript:;" not in markdown
    assert re.search(r"(?m)^1\. Schinckus C", markdown)
    assert not re.search(r"(?m)^- Schinckus C", markdown)
    assert re.search("(?:\\$|Equation|BS)", markdown)


def test_markdown_contract_figure_fixture() -> None:

    # markdown-review: purpose=figure doi=10.1098/rsos.150470
    markdown = _render_markdown_for_fixture("10.1098/rsos.150470")
    assert "figures 1" in markdown
    assert "Plesiochelys" in markdown
    assert "Palaeobiogeographic distribution" in markdown
    assert "### 3.3 Referred material" in markdown
    assert "NHMUK R3370, a basicranium" in markdown
    assert "### 3.9 Referred material" in markdown
    assert "NHMUK OR44178b" in markdown
    assert "Download slide" not in markdown
    assert "Article navigation" not in markdown
    assert not re.search(r"(?m)^- Figure$", markdown)
    assert re.search("(?:figure|figures 1)", markdown)
    assert "\n## Figures\n" not in markdown


def test_markdown_contract_supplementary_fixture() -> None:
    # markdown-review: purpose=supplementary doi=10.1098/rsif.2019.0334
    markdown = _render_markdown_for_fixture("10.1098/rsif.2019.0334")
    assert "electronic supplementary material" in markdown
    assert "hepatitis C virus" in markdown
    assert "\nEquation 3.2:" in markdown
    assert not re.search(r"Equation 3\.1: .+ Equation 3\.2:", markdown)
    assert "Download citation" not in markdown
    assert "Article navigation" not in markdown


def test_markdown_contract_references_fixture() -> None:
    # markdown-review: purpose=references doi=10.1098/rsos.201200
    markdown = _render_markdown_for_fixture("10.1098/rsos.201200")
    assert "## References" in markdown
    assert re.search(r"(?m)^1\. Wright PA", markdown)
    assert re.search(r"(?m)^2\. Zimmer AM", markdown)
    assert not re.search(r"(?m)^- Wright PA", markdown)
    assert "Reference" in markdown
    assert "Google Scholar" not in markdown
    assert "Download citation" not in markdown


def test_markdown_contract_pdf_fallback_fixture() -> None:
    """PDF fallback Markdown uses the shared text-only PDF conversion baseline."""

    # markdown-review: purpose=pdf_fallback doi=10.1098/rsta.2020.0108
    markdown = _render_markdown_for_fixture("10.1098/rsta.2020.0108")
    assert markdown.strip()
    assert re.search(r"(?m)^#{1,6}\s+\S+", markdown) or re.search(
        r"[A-Za-z]{20,}", markdown
    )
    assert "## 1. Introduction" in markdown
    assert "Many recent and spectacular advances in the world of materials" in markdown
    assert "Access Denied" not in markdown
    assert "<html" not in markdown.lower()
    assert "Object moved" not in markdown
