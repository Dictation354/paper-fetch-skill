"""Problem-list regressions checked against captured originals."""

from copy import deepcopy
from pathlib import Path
import re

from bs4 import BeautifulSoup
import pytest

from paper_fetch.providers._arxiv_graphics import (
    INLINE_SVG_PREFIX,
    save_arxiv_inline_svgs,
)
from paper_fetch.providers._arxiv_html import _extract_arxiv_html_markdown
from paper_fetch.runtime import RuntimeContext
from tests.golden_corpus import golden_corpus_fixture_for_doi
from tests.support.replay import build_article_from_fixture
from tests.support.scientific_content import scientific_text_key
from tests.support.scientific_content import preserve_dom_scripts


def source_article(doi):
    fixture = golden_corpus_fixture_for_doi(doi)
    soup = BeautifulSoup(
        fixture.raw_path.read_text(),
        "xml" if fixture.raw_path.suffix == ".xml" else "lxml",
    )
    article = build_article_from_fixture(fixture)
    return (
        fixture,
        soup,
        article,
        article.to_ai_markdown(asset_profile="all", include_refs="all"),
    )


def test_pnas_original_integral_nodes_keep_variables_outside_control_words():
    _, soup, _, markdown = source_article("10.1073/pnas.2322622121")
    integral = soup.find("math", id="i182")
    assert integral is not None
    assert [n.get_text() for n in integral.select("mo, mi")] == ["∫", "S", "M", "B"]
    assert r"\int SMB" in markdown
    assert not re.search(r"\\int(?:SMB|D)", markdown)


def test_acs_original_table_note_supplement_link_keeps_publisher_origin():
    _, soup, _, markdown = source_article("10.1021/acsomega.3c06992")
    href = "/acsodf/article-supplement/341563/pdf/ao3c06992_si_001/"
    link = soup.select_one(f'.table-wrap-foot a[href="{href}"]')
    assert link is not None and link.get_text() == "Table S1"
    assert f"[Table S1](https://pubs.acs.org{href})" in markdown


@pytest.mark.parametrize(
    "doi",
    [
        "10.48550/arxiv.2605.06653v1",
        "10.48550/arxiv.2605.06663v1",
        "10.48550/arxiv.2605.06665v1",
        "10.5194/gmd-17-1-2024",
    ],
)
def test_original_footnotes_render_once_in_notes_before_references(doi):
    _, soup, _, markdown = source_article(doi)
    nodes = (
        soup.select(".ltx_note.ltx_role_footnote")
        if "arxiv" in doi
        else soup.select("body p fn")
    )
    assert nodes
    assert "## Notes" in markdown
    body, notes = markdown.split("## Notes", 1)
    notes = notes.split("## References", 1)[0]
    for node in nodes:
        note = deepcopy(node.select_one(".ltx_note_content") or node)
        for marker in list(note.select(".ltx_note_mark, .ltx_tag_note, label")):
            marker.decompose()
        for string in note.strings:
            if string.find_parent(["math", "annotation"]):
                continue
            expected = scientific_text_key(str(string))
            if expected:
                assert expected in scientific_text_key(notes)
        first_prose = next(
            (
                scientific_text_key(str(s))
                for s in note.strings
                if not s.find_parent(["math", "annotation"])
                and len(scientific_text_key(str(s))) > 30
            ),
            "",
        )
        if first_prose:
            assert first_prose not in scientific_text_key(body)
    if "gmd" in doi:
        assert "21 February 2020<sup>1</sup> with the release" in body
        assert re.search(r"\n2\n\n\$\$", markdown)
        assert re.search(r"\n3\n\n\$\$", markdown)


def test_original_arxiv_appendix_vectors_are_saved_with_their_text(tmp_path):
    fixture = golden_corpus_fixture_for_doi("10.48550/arxiv.2605.06663v1")
    original = fixture.raw_path.read_text()
    source = BeautifulSoup(original, "lxml").select("svg.ltx_picture")
    assert len(source) == 21
    extraction = _extract_arxiv_html_markdown(
        original, fixture.source_url, metadata={"doi": fixture.doi}
    )
    assets = [
        a for a in extraction.extracted_assets if a["url"].startswith(INLINE_SVG_PREFIX)
    ]
    assert len(assets) == len(source)
    result = save_arxiv_inline_svgs(
        assets,
        output_dir=tmp_path,
        article_id=fixture.doi,
        source_url=fixture.source_url,
        context=RuntimeContext(),
    )
    assert not result["asset_failures"]
    for asset, svg in zip(result["assets"], source, strict=True):
        saved = Path(asset["path"]).read_text()
        assert asset["image_id"] == svg["id"]
        assert svg.select_one("foreignobject").get_text(
            " ", strip=True
        ) in BeautifulSoup(saved, "xml").get_text(" ", strip=True)
        assert asset["url"] in extraction.markdown_text


def test_original_science_model_statistics_and_covariate_order():
    _, soup, _, markdown = source_article("10.1126/sciadv.adm9732")
    table = soup.find("table")
    assert table is not None
    model_rows = [r for r in table.select("tbody > tr") if r.find("th", rowspan=True)]
    assert [r.th.get_text() for r in model_rows] == [
        "Composition + Disturbance",
        "Composition",
        "Disturbance",
    ]
    rendered_rows = [
        line
        for line in markdown.splitlines()
        if line.startswith("| Composition") or line.startswith("| Disturbance")
    ]
    assert len(rendered_rows) == 3
    assert markdown.count("0.624") == 1
    assert r"MAP\*Pdev" in rendered_rows[0]
    assert "MAP" in rendered_rows[2] and "1/√YSD" in rendered_rows[2]


def test_captured_springer_independent_tables_use_full_acquisition_path():
    for doi in ("10.1007/s10584-011-0143-4", "10.1038/s43247-024-01295-w"):
        fixture, _, _, markdown = source_article(doi)
        page = BeautifulSoup(
            (fixture.raw_path.parent / "table1.html").read_text(), "lxml"
        )
        table = page.find("table")
        assert table is not None
        for row in table.select("tbody tr"):
            for cell in row.find_all(["th", "td"], recursive=False):
                preserve_dom_scripts(cell)
                expected = scientific_text_key(cell.get_text(" ", strip=True))
                if expected:
                    assert expected in scientific_text_key(markdown)
        assert "Missing fixture response" not in markdown


def test_original_mdpi_cell_image_and_list_boundaries():
    _, soup, _, markdown = source_article("10.3390/w15040758")
    image = soup.select_one("table img")
    assert image is not None
    assert image["data-lsrc"] in markdown
    _, soup, _, markdown = source_article("10.3390/s23010001")
    assert soup.select("dl.html-simple dd")
    assert not re.search(r"(?m)^–$", markdown)
    assert "<br>• " in markdown
    assert "## Abbreviations" in markdown


def test_original_xml_lists_keep_equations_inside_their_source_items():
    _, soup, _, markdown = source_article("10.1371/journal.pone.0126635")
    formulas = soup.select("list-item disp-formula")
    assert len(formulas) >= 16
    for formula in formulas:
        label = formula.find("label")
        if label is not None:
            assert label.get_text(strip=True) in markdown
    assert "   $$" in markdown or "  $$" in markdown
    assert not re.search(r"\\(?:mkern|mspace)\{?(?:3480|720|\d{5,})mu", markdown)
