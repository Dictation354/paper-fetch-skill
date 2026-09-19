"""Independent original-source assertions before exact baseline updates."""

from bs4 import BeautifulSoup
import pytest
from tests.golden_corpus import golden_corpus_fixture_for_doi
from tests.support.replay import build_article_from_fixture
from tests.support.reviewed_publisher_content import _words


@pytest.mark.parametrize(
    "doi", ["10.1093/bioinformatics/btaa161", "10.1093/bioinformatics/btaa823"]
)
def test_original_oup_table_notes_complete_and_in_place(doi):
    fixture = golden_corpus_fixture_for_doi(doi)
    soup = BeautifulSoup(fixture.raw_path.read_text(), "lxml")
    article = build_article_from_fixture(fixture)
    md = article.to_ai_markdown(
        include_refs="all", asset_profile="all", max_tokens="full_text"
    )
    rendered = _words(md)
    notes = soup.select(".article-body .table-wrap-foot")
    assert len(notes) == (1 if doi.endswith("161") else 3)
    cursor = 0
    for foot in notes:
        # MathML is asserted separately: source plaintext omits TeX syntax.
        original = BeautifulSoup(str(foot), "lxml")
        for math in original.select(".inline-formula"):
            math.replace_with("FORMULA")
        pieces = original.get_text(" ", strip=True).split("FORMULA")
        for piece in pieces:
            expected = _words(piece)
            cursor = rendered.index(expected, cursor) + len(expected)
        wrapper = foot.find_parent(class_="table-wrap")
        # Compare source cells carrying footnote letters as well as the notes;
        # flattening a superscript must not silently drop its marker.
        for marker in wrapper.find("table").select("sup"):
            if marker.get_text(strip=True) in {"a", "b", "c", "d", "e", "f"}:
                cell = marker.find_parent(["td", "th"])
                assert _words(cell.get_text(" ", strip=True)) in rendered
        table_label = _words(wrapper.select_one(".label").get_text())
        assert rendered.rfind(table_label, 0, cursor) >= 0
        following = wrapper.find_next_sibling()
        if following and following.get_text(strip=True):
            assert (
                rendered.index(
                    _words(following.get_text(" ", strip=True))[:100], cursor
                )
                >= cursor
            )
    if doi.endswith("161"):
        assert "$p \\leq 0.05$" in md and "$q \\leq 0.25$" in md
        assert "*p* = Number of features" in md
    else:
        assert "a AND and OR query" in md
        assert "f Ratio of *L*<sub>int</sub> and *L*<sub>tot</sub>." in md


@pytest.mark.parametrize(
    "doi",
    [
        "10.1126/sciadv.adl6155",
        "10.1126/sciadv.adm9732",
        "10.1126/science.ade0347",
        "10.1126/sciadv.abj3309",
        "10.1126/science.abp8622",
        "10.1126/science.adp0212",
    ],
)
def test_original_science_statement_text_links_kind_and_rendering(doi):
    fixture = golden_corpus_fixture_for_doi(doi)
    soup = BeautifulSoup(fixture.raw_path.read_text(), "lxml")
    paragraphs = [
        p
        for p in soup.select('#bodymatter #acknowledgments div[role="paragraph"]')
        if p.get_text(strip=True).startswith("Data and materials availability:")
    ]
    assert len(paragraphs) == 1
    original = paragraphs[0]
    heading = original.b.extract().get_text().rstrip(":")
    article = build_article_from_fixture(fixture)
    sections = [s for s in article.sections if s.heading == heading]
    assert len(sections) == 1 and sections[0].kind == "data_availability"
    md = article.to_ai_markdown(
        include_refs="all", asset_profile="all", max_tokens="full_text"
    )
    expected = _words(original.get_text(" ", strip=True))
    assert _words(md).count(expected) == 1
    assert md.count("## " + heading) == 1
    for link in original.select("a[href^=http]"):
        assert f"[{link.get_text()}]({link['href']})" in md
