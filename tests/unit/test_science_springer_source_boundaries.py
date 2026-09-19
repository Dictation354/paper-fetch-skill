"""Minimal provider-local table and Methods classification boundaries."""

from bs4 import BeautifulSoup
import pytest

from paper_fetch.providers._science_html import render_table_with_missing_trailing_cells
from paper_fetch.providers._springer_dom import extract_html_extraction_sidecars


def test_science_short_unspanned_row_keeps_columns_without_inventing_text():
    table = BeautifulSoup(
        "<table><tr><th>A</th><th>B</th><th>C</th></tr><tr><td>first</td><td>ends at year</td></tr></table>",
        "lxml",
    ).table
    original = str(table)
    rendered = render_table_with_missing_trailing_cells(
        table, label="Table 1", caption=""
    )
    assert [
        cell.strip()
        for cell in next(
            line for line in rendered.splitlines() if line.startswith("| first")
        )
        .strip("|")
        .split("|")
    ] == ["first", "ends at year", ""]
    assert "data row 1 supplies 2 of 3 cells" in rendered
    assert str(table) == original


@pytest.mark.parametrize(
    "row", ['<td colspan="2">x</td>', "<td>x</td><td>y</td><td>z</td>", ""]
)
def test_science_short_row_handler_does_not_guess_spans_overwide_or_empty_rows(row):
    table = BeautifulSoup(
        "<table><tr><th>A</th><th>B</th></tr><tr>" + row + "</tr></table>", "lxml"
    ).table
    assert render_table_with_missing_trailing_cells(table, label="", caption="") is None


def test_springer_ethics_hint_requires_methods_dom_ancestor():
    html = '<article><section data-title="Methods"><h2>Methods</h2><div id="method"><h3>Ethics statement</h3><p>Permit ABC123.</p></div></section><section data-title="Ethics declarations"><h2>Ethics declarations</h2><div id="back"><h3>Ethics statement</h3><p>Back matter.</p><h3>Competing interests</h3></div></section></article>'
    hints = extract_html_extraction_sidecars(
        html, "https://www.nature.com/articles/example"
    )["section_hints"]
    ethics = [hint for hint in hints if hint["heading"] == "Ethics statement"]
    assert [hint["kind"] for hint in ethics] == ["body", "references"]
    assert (
        next(hint for hint in hints if hint["heading"] == "Competing interests")["kind"]
        == "references"
    )


@pytest.mark.parametrize("publisher, padded", [("science", True), ("pnas", False)])
def test_table_padding_is_science_only(publisher, padded):
    from paper_fetch.providers.atypon_browser_workflow.normalization import (
        _normalize_table_blocks,
    )

    soup = BeautifulSoup(
        "<article><table><tr><th>A</th><th>B</th></tr><tr><td>source</td></tr></table></article>",
        "lxml",
    )
    entries = _normalize_table_blocks(soup.article, publisher)
    assert len(entries) == 1
    assert ("missing trailing cells are left blank" in entries[0]["markdown"]) is padded
