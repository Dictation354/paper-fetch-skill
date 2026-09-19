"""Existing full papers promoted only after source structure/content review."""

import re
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
import pytest

from tests.golden_corpus import golden_corpus_fixture_for_doi
from tests.support.replay import build_article_from_fixture
from tests.support.reviewed_publisher_content import _words
from tests.support.reviewed_html_publisher_content import _table_cell
from tests.support.variant_content_scenarios import VARIANTS


@pytest.mark.parametrize("doi,headings,anchors,references", VARIANTS)
def test_reviewed_variant_structure_and_content(doi, headings, anchors, references):
    fixture = golden_corpus_fixture_for_doi(doi)
    soup = BeautifulSoup(fixture.raw_path.read_text(), "html.parser")
    article = build_article_from_fixture(fixture)
    rendered = article.to_ai_markdown(
        include_refs="all", asset_profile="body", max_tokens="full_text"
    )
    assert article.quality.has_fulltext
    assert article.doi == doi
    assert len(article.references) == references
    cursor = 0
    for heading in headings:
        assert _words(heading) in _words(soup.get_text(" ", strip=True))
        normalized = _words(
            "\n".join(line for line in rendered.splitlines() if line.startswith("#"))
        )
        cursor = normalized.index(_words(heading), cursor) + len(_words(heading))
    for anchor in anchors:
        assert _words(anchor) in _words(soup.get_text(" ", strip=True))
        assert _words(anchor) in _words(rendered)
    if fixture.provider == "arxiv":
        # Check the complete visible bibliography, not only its count.
        nodes = soup.select(".ltx_bibitem")
        assert len(nodes) == references
        for node, reference in zip(nodes, article.references, strict=True):
            for label in node.select(".ltx_tag"):
                label.decompose()
            for run in node.strings:
                if len(_words(run)) > 40:
                    assert _words(run) in _words(reference.raw)
        # A real in-body citation must refer to an existing bibliography entry.
        callouts = soup.select(".ltx_cite a[href]")
        assert callouts
        assert any(
            soup.find(id=urlsplit(a["href"]).fragment) is not None
            for a in callouts
            if urlsplit(a["href"]).fragment
        )


@pytest.mark.parametrize(
    "doi,rows", [("10.1093/beheco/arag047", 6), ("10.1093/molehr/gaaf013", 18)]
)
def test_oup_metric_tables_are_not_manuscript_tables(doi, rows):
    fixture = golden_corpus_fixture_for_doi(doi)
    soup = BeautifulSoup(fixture.raw_path.read_text(), "html.parser")
    # The only table in each capture is the site's hidden monthly view counter.
    table = soup.select_one("#MetricsModalContents table")
    assert table is not None
    assert len(table.select("tbody tr")) == rows
    assert len(soup.select("table")) == 1
    article = build_article_from_fixture(fixture)
    rendered = article.to_ai_markdown(
        include_refs="none", asset_profile="body", max_tokens="full_text"
    )
    assert "Month: Total Views:" not in rendered
    assert not [a for a in article.assets if a.kind == "table"]


def test_arxiv_unipool_full_data_table_and_kubo_methods_after_bibliography():
    # These variants exercise data tables and a Methods section after the
    # source bibliography; existing mechanism tests cover panel/list rendering.
    doi = "10.48550/arxiv.2605.06665v1"
    fixture = golden_corpus_fixture_for_doi(doi)
    soup = BeautifulSoup(fixture.raw_path.read_text(), "html.parser")
    markdown = build_article_from_fixture(fixture).to_ai_markdown(
        max_tokens="full_text"
    )
    table = soup.select_one("figure.ltx_table table")
    assert table is not None
    for math_node in table.select("math[alttext]"):
        math_node.replace_with(math_node["alttext"])
    for row in table.select("tr"):
        values = [
            _table_cell(c.get_text(" ", strip=True))
            for c in row.find_all(["td", "th"], recursive=False)
        ]
        assert any(
            all(v in _table_cell(line).replace("$", "") for v in values)
            for line in markdown.splitlines()
            if line.startswith("|")
        )
    fixture = golden_corpus_fixture_for_doi("10.48550/arxiv.2605.06666v1")
    soup = BeautifulSoup(fixture.raw_path.read_text(), "html.parser")
    source_nodes = list(soup.find_all(True))
    methods = next(
        h for h in soup.select("h3") if "Preparation of highly imbalanced" in h.text
    )
    assert source_nodes.index(
        soup.select_one(".ltx_bibliography")
    ) < source_nodes.index(methods)

    markdown = build_article_from_fixture(fixture).to_ai_markdown(
        include_refs="all", max_tokens="full_text"
    )
    assert markdown.index("Preparation of highly imbalanced") < markdown.index(
        "## References"
    )
    # Native TeX source in this variant supplies the actual equation identity.
    math = soup.select_one("math[alttext]")
    assert math is not None
    assert re.sub(r"\s+", "", math["alttext"]) in re.sub(r"\s+", "", markdown)
