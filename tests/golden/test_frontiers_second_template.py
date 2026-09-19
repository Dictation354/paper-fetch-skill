"""Reviewed NLM 2.3 Frontiers article with an internal id unlike its DOI suffix."""

import re
from bs4 import BeautifulSoup

from tests.golden_corpus import golden_corpus_fixture_for_doi
from tests.support.replay import build_article_from_fixture
from tests.support.reviewed_publisher_content import _words
from tests.support.reviewed_html_publisher_content import _table_cell

DOI = "10.3389/fpls.2020.01216"


def test_real_frontiers_nlm23_structure_prose_references_and_tables():
    fixture = golden_corpus_fixture_for_doi(DOI)
    raw = fixture.raw_path.read_text()
    soup = BeautifulSoup(raw, "xml")
    assert soup.article["dtd-version"] == "2.3"
    assert soup.select_one('article-id[pub-id-type="doi"]').text == DOI
    article = build_article_from_fixture(fixture)
    rendered = article.to_ai_markdown(
        include_refs="all", asset_profile="body", max_tokens="full_text"
    )
    headings = [
        "Introduction",
        "Materials and Methods",
        "Results",
        "Discussion",
        "Conclusion",
        "Data Availability Statement",
        "Author Contributions",
        "Funding",
        "Conflict of Interest",
    ]
    assert [
        n.title.text for n in soup.body.find_all("sec", recursive=False)
    ] == headings
    cursor = 0
    for title in headings[:7]:
        cursor = rendered.index("## " + title, cursor) + len(title)
    for anchor in [
        "Leaf temperature changes with incident light",
        "Chazdon and Pearcy (1986a)",
        "we proposed an empirical method to sequentially correct",
        "concurrent increases in leaf temperature with light",
    ]:
        assert _words(anchor) in _words(rendered)
    refs = soup.select("ref-list ref")
    assert len(refs) == len(article.references) == 56
    for node, ref in zip(refs, article.references, strict=True):
        for label in node.select("label"):
            label.decompose()
        assert _words(node.get_text(" ", strip=True)) == _words(
            re.sub(r"^\d+\.\s*", "", ref.raw)
        )
    # All body rows of all three tables, including the complete last table.
    assert len(soup.select("table-wrap")) == 3
    for table in soup.select("table-wrap"):
        for row in table.select("tbody tr"):
            cells = row.find_all(["td", "th"], recursive=False)
            if any(c.find("math") for c in cells):
                cells = [c for c in cells if not c.find("math")]
            values = [_table_cell(c.get_text(" ", strip=True)) for c in cells]
            assert any(
                all(value in _table_cell(line) for value in values)
                for line in rendered.splitlines()
                if line.startswith("|")
            )
    # Independently transcribed from the actual MathML (not the mechanism XML).
    assert len(soup.select("disp-formula")) == 8
    equations = re.sub(
        r"\s+", "", rendered.replace("∗", r"\ast").replace(r"\exp", "exp")
    )
    assert (
        re.sub(
            r"\s+",
            "",
            r"A(t) = \frac{a_{1} - a_{2}}{1 + e^{(t - t_{0})}/\Delta t_{A}} + a_{2}",
        )
        in equations
    )
    assert (
        re.sub(
            r"\s+",
            "",
            r"V_{c}(t) = V_{\text{c,f}} - (V_{\text{c,f}} - V_{\text{c,ini}}) \ast exp(- t/\tau_{\text{Rubisco}})",
        )
        in equations
    ), re.findall(r"\$\$(.*?)\$\$", rendered, re.S)[-1]
