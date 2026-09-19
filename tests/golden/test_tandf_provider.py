from __future__ import annotations
import pytest
from tests.support.test_evidence import evidence_cache as cache
from pathlib import Path
import re
from bs4 import BeautifulSoup, NavigableString, Tag
from paper_fetch.providers import _tandf_html
from paper_fetch.providers._atypon_browser_workflow_profiles import (
    publisher_profile,
)
from paper_fetch.providers._pdf_common import pdf_fetch_result_from_bytes
from paper_fetch.providers.atypon_browser_workflow.asset_scopes import (
    extract_browser_workflow_asset_html_scopes,
)
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.tandf import TandfClient
from paper_fetch.tracing import trace_from_markers


STRUCTURE_DOI = "10.1080/15481603.2026.2667034"
TABLE_DOI = "10.1080/10942912.2019.1597882"
FORMULA_DOI = "10.1080/08839514.2024.2375110"
MULTILINGUAL_DOI = "10.1080/19455224.2025.2547671"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _fixture_path(doi: str, filename: str = "original.html") -> Path:
    return (
        REPO_ROOT
        / "tests"
        / "fixtures"
        / "golden_criteria"
        / doi.replace("/", "_", 1)
        / filename
    )


@cache
def _extract_fixture(doi: str) -> tuple[str, dict]:
    source_url = f"https://www.tandfonline.com/doi/full/{doi}"
    html_text = _fixture_path(doi).read_text(encoding="utf-8")
    return TandfClient(None, {}).extract_markdown(
        html_text,
        source_url,
        metadata={"doi": doi},
    )


@cache
def _render_article_markdown(doi: str) -> str:
    source_url = f"https://www.tandfonline.com/doi/full/{doi}"
    html_text = _fixture_path(doi).read_text(encoding="utf-8")
    metadata = {
        "doi": doi,
        "authors": [],
        "references": [],
        "fulltext_links": [],
        "landing_page_url": source_url,
    }
    markdown, extraction = TandfClient(None, {}).extract_markdown(
        html_text,
        source_url,
        metadata=metadata,
    )
    payload = RawFulltextPayload(
        provider="tandf",
        source_url=source_url,
        content_type="text/html",
        body=html_text.encode("utf-8"),
        content=ProviderContent(
            route_kind="html",
            source_url=source_url,
            content_type="text/html",
            body=html_text.encode("utf-8"),
            markdown_text=markdown,
            diagnostics={
                "extraction": extraction,
                "availability_diagnostics": extraction["availability_diagnostics"],
            },
        ),
        trace=trace_from_markers(["fulltext:tandf_html_ok"]),
    )
    article = TandfClient(None, {}).to_article_model(metadata, payload)
    return article.to_ai_markdown(include_refs="all", max_tokens="full_text")


def test_tandf_article_assets_keep_body_figures_and_scope_supplement() -> None:
    html_text = _fixture_path(STRUCTURE_DOI).read_text(encoding="utf-8")
    source_url = f"https://www.tandfonline.com/doi/full/{STRUCTURE_DOI}"
    body_html, supplementary_html = extract_browser_workflow_asset_html_scopes(
        html_text,
        source_url,
        "tandf",
    )
    extractor = publisher_profile("tandf").scoped_asset_extractor
    assert extractor is not None

    body_assets = extractor(
        body_html,
        source_url,
        asset_profile="body",
        supplementary_html_text=supplementary_html,
    )
    all_assets = extractor(
        body_html,
        source_url,
        asset_profile="all",
        supplementary_html_text=supplementary_html,
    )

    figures = [asset for asset in body_assets if asset["kind"] == "figure"]
    assert len(figures) == 9
    assert all(asset.get("preview_accepted") == "true" for asset in figures)
    assert all(asset.get("full_size_url") != asset["preview_url"] for asset in figures)
    assert all(
        "official_full_size_not_exposed" not in asset.get("provenance", [])
        for asset in figures
    )
    assert figures[0]["full_size_url"] == (
        "https://www.tandfonline.com/cms/asset/2330a6f2-d28c-421f-bbdd-f618a6fd564c/"
        "tgrs_a_2667034_f0001_c.jpg"
    )
    assert any("_f0006_c.jpg" in asset["preview_url"] for asset in figures)
    assert not [asset for asset in body_assets if asset["kind"] == "supplementary"]
    supplementary = [asset for asset in all_assets if asset["kind"] == "supplementary"]
    assert len(supplementary) == 1
    assert "preview_accepted" not in supplementary[0]
    assert supplementary[0]["url"].startswith(
        "https://www.tandfonline.com/action/downloadSupplement?"
    )
    assert supplementary[0]["url"].endswith("tgrs_a_2667034_sm1980.docx")
    assert supplementary[0]["filename_hint"] == "tgrs_a_2667034_sm1980.docx"


def test_markdown_contract_structure_fixture() -> None:
    # markdown-review: purpose=structure doi=10.1080/15481603.2026.2667034
    markdown, extraction = _extract_fixture(STRUCTURE_DOI)

    assert "## Abstract" in markdown
    assert "## 1. Introduction" in markdown
    assert "### 4.1 Modeling approaches and comparative performance" in markdown
    assert "a 95.1% improvement over traditional Poisson regression" in markdown
    assert re.search(
        r"(?m)^\|\s*Variable abbreviation\s*\|\s*Description\s*\|", markdown
    )
    assert re.search(
        r"(?m)^\|\s*D_LST\s*\|\s*Current weekly daytime maximum LST \(°C\)",
        markdown,
    )
    assert "Sexes / Both sexes" in markdown
    assert "4340.046" in markdown
    # Original listgroup paragraphs retain both italic X and scientific scripts.
    assert "*X*<sup>2</sup>*D_LST_AT2" in markdown
    assert "*X*<sup>3</sup>*D_LST_AT3" in markdown
    assert "R<sup>2</sup> generally" in markdown
    assert "R<sup>2</sup> (below 0.30)" in markdown
    assert "## Funding" in markdown
    assert "National Natural Science Foundation of China" in markdown
    assert "Download Citation" not in markdown
    assert "Article Metrics" not in markdown
    assert "## Article highlights" in markdown
    assert "Citation" not in markdown
    assert "()" not in markdown
    assert "(Figure 1a)" in markdown
    assert extraction["availability_diagnostics"]["accepted"] is True


def test_markdown_contract_table_fixture() -> None:
    # markdown-review: purpose=table doi=10.1080/10942912.2019.1597882
    markdown, _ = _extract_fixture(TABLE_DOI)

    assert "**Table 1.**" in markdown
    assert "| Materials used | Sample tube (µL) | Control tube (µL) |" in markdown
    assert "| Total volume" in markdown
    assert "| Compounds | AChE / IC<sub>50</sub>(nM)" in markdown
    assert "AChE / r<sup>2</sup>" in markdown
    assert "α-Amylase<sup>a</sup> / IC<sub>50</sub>(nM)" in markdown
    assert "α-Glycosidase / K<sub>i</sub>(nM)" in markdown
    assert "Ki values could not be determined for α-amylase enzyme." in markdown
    assert "determined as µM levels, which taken from literatures" in markdown
    assert (
        "Tacrine was used as a positive control for acetylcholinesterase (AChE) enzyme."
        in markdown
    )
    assert "- Compounds: IC50 (nM); AChE: r2" not in markdown
    assert "Google Scholar" not in markdown
    assert "Display Table" not in markdown
    assert "Citation" not in markdown
    assert re.search(r"(?m)^\|.+\|$", markdown)


def test_markdown_contract_formula_fixture() -> None:
    # markdown-review: purpose=formula doi=10.1080/08839514.2024.2375110
    markdown, _ = _extract_fixture(FORMULA_DOI)

    assert "## Introduction" in markdown
    assert "[Formula unavailable]" not in markdown
    assert "![Formula](//:0)" not in markdown
    assert "MathJax Logo" not in markdown
    assert "Citation" not in markdown
    assert re.search(r"(?s)\$\$.+?\$\$|\\\(.+?\\\)", markdown)
    assert re.search(
        r"(?s)\\begin\{(?:p)?matrix\}.{0,200}"
        r"\{?0\.88\}?\^\{0\.37\}.{0,100}\{?0\.82\}?\^\{0\.21\}",
        markdown,
    )
    assert "Θ˜(ℏ˜ 1)=" not in markdown
    assert "A D 2 N˜ 2=" not in markdown
    assert r"0.51^{0.22}\rangle}" not in markdown
    assert r"{\widetilde{\Theta}}_{2}(\widetilde{\hslash})) =" not in markdown
    assert "(0.15}}" not in markdown
    assert "(0.24)}0.76" not in markdown
    assert "$$." not in markdown
    assert "$$," not in markdown
    assert "0.2415.(2) Score matrix" not in markdown
    assert "\n\n(2) Score matrix" in markdown


def test_tandf_formula_dom_repair_preserves_complex_math_structure() -> None:
    soup = BeautifulSoup(
        _fixture_path(FORMULA_DOI).read_text(encoding="utf-8"),
        _tandf_html.choose_parser(),
    )
    container = soup.select_one(".hlFld-Fulltext")
    assert isinstance(container, Tag)

    complex_inline = [
        node
        for node in container.select(".NLM_disp-formula.inline-formula")
        if node.find("mtable") is not None
    ]
    _tandf_html.tandf_before_block_normalization(container)

    assert len(complex_inline) == 11
    assert all("disp-formula" in (node.get("class") or ()) for node in complex_inline)

    for fenced in container.find_all("mfenced"):
        descendants = fenced.find_all(True)
        if not descendants:
            continue
        trailing = descendants[-1]
        if trailing.find_parent("mfenced") is fenced:
            assert _tandf_html._mathml_operator_text(trailing) != str(
                fenced.get("close") or ")"
            )

    for fenced in container.find_all("mfenced", attrs={"open": "⟨"}):
        for row in fenced.find_all("mrow"):
            children = [child for child in row.children if isinstance(child, Tag)]
            assert not any(
                current.find("msup") is not None and following.name == "mn"
                for current, following in zip(children, children[1:], strict=False)
            )

    exponent_repairs = 0
    for superscript in container.find_all("msup"):
        children = [child for child in superscript.children if isinstance(child, Tag)]
        if len(children) < 2:
            continue
        operators = [
            _tandf_html._mathml_operator_text(node)
            for node in children[1].find_all("mo")
        ]
        if "(" in operators:
            exponent_repairs += 1
            assert operators.count("(") == operators.count(")")
    assert exponent_repairs >= 22

    for wrapper in complex_inline:
        sibling = wrapper.next_sibling
        while isinstance(sibling, Tag) and "NLM_disp-formula-image" in set(
            sibling.get("class") or ()
        ):
            sibling = sibling.next_sibling
        if isinstance(sibling, NavigableString) and sibling.strip():
            assert not re.match(r"^\s*[.,;:]", str(sibling))


def test_markdown_contract_figure_fixture() -> None:
    # markdown-review: purpose=figure doi=10.1080/15481603.2026.2667034
    markdown, _ = _extract_fixture(STRUCTURE_DOI)

    assert "Figure 1" in markdown
    assert re.search(
        r"!\[Figure 1\]\(https://www\.tandfonline\.com/cms/asset/", markdown
    )
    assert "Open figure viewer" not in markdown
    assert "View large" not in markdown
    assert "Article Metrics" not in markdown

    baseline = _fixture_path(STRUCTURE_DOI, "extracted.md").read_text(encoding="utf-8")
    local_links = re.findall(
        r"!\[Figure \d+\]\((tests/fixtures/golden_criteria/"
        r"10\.1080_15481603\.2026\.2667034/body_assets/[^)]+\.jpg)\)",
        baseline,
    )
    assert len(local_links) == 9
    assert "![Figure 1](https://www.tandfonline.com/" not in baseline
    for relative_path in local_links:
        asset_path = REPO_ROOT / relative_path
        assert asset_path.is_file()
        assert asset_path.stat().st_size > 100_000


def test_markdown_contract_supplementary_fixture() -> None:
    # markdown-review: purpose=supplementary doi=10.1080/15481603.2026.2667034
    markdown, _ = _extract_fixture(STRUCTURE_DOI)

    assert markdown.count("## Supplemental material") == 1
    assert "Supplemental data for this article can be accessed" in markdown
    assert "Download Citation" not in markdown
    assert "Article Metrics" not in markdown


def test_markdown_contract_references_fixture() -> None:
    # markdown-review: purpose=references doi=10.1080/15481603.2026.2667034
    markdown = _render_article_markdown(STRUCTURE_DOI)

    assert "## References (103 total, showing 103)" in markdown
    assert "1. Aldrich, C. 2020." in markdown
    assert "Google Scholar" not in markdown
    assert "Article Metrics" not in markdown


def test_markdown_contract_pdf_fallback_fixture() -> None:
    # markdown-review: purpose=pdf_fallback doi=10.1080/15481603.2026.2667034
    pdf_path = _fixture_path(STRUCTURE_DOI, "original.pdf")
    source_url = f"https://www.tandfonline.com/doi/pdf/{STRUCTURE_DOI}"
    result = pdf_fetch_result_from_bytes(
        artifact_dir=None,
        source_url=source_url,
        final_url=source_url,
        pdf_bytes=pdf_path.read_bytes(),
    )

    assert "Quantifying cumulative heat effects" in result.markdown_text
    assert "Just a moment" not in result.markdown_text
    assert "Access Denied" not in result.markdown_text


def test_tandf_multilingual_fixture_is_authentic_and_keeps_parallel_abstracts() -> None:
    markdown, extraction = _extract_fixture(MULTILINGUAL_DOI)

    assert "The affective turn and the management of conservation" in markdown
    assert "Learning analytics summaries across two languages" not in markdown
    assert [section["heading"] for section in extraction["abstract_sections"]] == [
        "Abstract",
        "Resumen",
        "الملخص",
        "Resumo",
        "摘要",
    ]
    assert "Footnote" not in markdown
    assert "care[1]" in markdown
    assert "‘networks of care’[3]" in markdown
    assert "was also cited by the majority" in markdown
    repeated = "They are people who also contribute to the senior leadership of their institutions."
    # The publisher repeats this sentence in one visible paragraph. Removing
    # editorial repetition is not interface cleanup.
    assert _fixture_path(MULTILINGUAL_DOI).read_text().count(repeated) == 2
    assert markdown.count(repeated) == 2
    assert "## Conclusion" in markdown
    assert "### Acknowledgements" in markdown
    assert "## Additional information" in markdown
    assert "### Notes on contributors" in markdown
    assert "**Pip Laurenson**" in markdown
    assert "is Professor of Conservation, UCL" in markdown

    rendered = _render_article_markdown(MULTILINGUAL_DOI)
    assert "### Acknowledgements" in rendered
    assert "### Notes on contributors" in rendered
    assert "**Pip Laurenson**" in rendered
    assert "I would like to thank Jill Sterrett" in rendered
    assert "## References (87 total, showing 87)" in rendered
    assert "1. The first quotation in the abstract comes from" in rendered


@pytest.mark.parametrize(
    "doi,identifier",
    [
        ("10.1080/10942912.2019.1597882", "e_1_3_1_10_1:ISI"),
        ("10.1080/17538947.2022.2137254", "e_1_3_3_26_1:ISI"),
    ],
)
def test_original_isi_linkout_is_not_a_cited_work_doi(doi, identifier):
    from bs4 import BeautifulSoup
    from urllib.parse import unquote
    from paper_fetch.providers._tandf_html import extract_references
    from tests.golden_criteria import golden_criteria_asset

    raw = golden_criteria_asset(doi, "original.html").read_text()
    soup = BeautifulSoup(raw, "lxml")
    nodes = soup.select("ul.references.numeric-ordered-list > li")
    references = extract_references(raw)
    assert len(nodes) == len(references)
    found = []
    for node, reference in zip(nodes, references, strict=True):
        if any(identifier in unquote(a["href"]) for a in node.select("a[href]")):
            found.append(reference)
    assert len(found) == 1
    assert found[0]["doi"] is None
