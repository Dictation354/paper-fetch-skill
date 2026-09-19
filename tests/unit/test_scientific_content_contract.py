"""Negative controls for content assertions, not publisher evidence."""

from bs4 import BeautifulSoup
import pytest

from tests.support.canonical_content import comparable_cell, formula_route
from tests.support.scientific_content import scientific_text_key, assert_mathml_formulas


@pytest.mark.parametrize(
    "left,right",
    [
        ("1.5 mg", "15 mg"),
        ("-0.5", "0.5"),
        ("x²", "x₂"),
        ("$x^{2}$", "$x_{2}$"),
        ("1e-5", "1e5"),
        ("M", "m"),
        (r"$x_{2}\hspace{40pt}$", r"$x_{3}\hspace{40pt}$"),
    ],
)
def test_scientific_comparisons_reject_changed_meaning(left, right):
    assert scientific_text_key(left) != scientific_text_key(right)
    assert comparable_cell(left) != comparable_cell(right)


@pytest.mark.parametrize(
    "left,right",
    [
        ("x²", "x<sup>2</sup>"),
        ("x₂", "$x_{2}$"),
        ("−0.5", "-0.5"),
        ("**1.5 mg**", "1.5 mg"),
        (r"$x_{2}\hspace{40pt}$", "$x_{2}$"),
    ],
)
def test_scientific_comparisons_accept_equivalent_presentation(left, right):
    assert scientific_text_key(left) == scientific_text_key(right)
    assert comparable_cell(left) == comparable_cell(right)


@pytest.mark.parametrize(
    "alt,route",
    [
        ("", "mathml"),
        ("  ", "mathml"),
        ("No alternative text available", "mathml"),
        (" no alternative text available ", "mathml"),
        ("x", "tex"),
    ],
)
def test_formula_route_never_treats_placeholder_as_tex(alt, route):
    node = BeautifulSoup("<math><mi>x</mi></math>", "xml").math
    node["alttext"] = alt
    assert formula_route(node) == route
    if route == "mathml":
        assert assert_mathml_formulas([node], "$x$") == 1
        with pytest.raises(AssertionError):
            assert_mathml_formulas([node], "")


def test_cell_fraction_grouping_is_not_flattened():
    assert comparable_cell(r"$\frac{ab}{c}$") != comparable_cell(r"$\frac{a}{bc}$")


def test_math_oracle_ignores_spacing_dimensions_but_rejects_changed_numbers():
    node = BeautifulSoup("<math><mi>x</mi><mo>=</mo><mn>2</mn></math>", "xml").math
    assert assert_mathml_formulas([node], r"$x=2\hspace{40pt}$") == 1
    with pytest.raises(AssertionError):
        assert_mathml_formulas([node], r"$x=3\hspace{2pt}$")


def test_copernicus_table_oracle_resolves_source_bibliography_and_detects_loss():
    from tests.support.object_content import assert_source_tables

    soup = BeautifulSoup(
        '<article><body><table><tr><td>Data</td><td><xref ref-type="bibr" rid="r1"/></td></tr></table></body>'
        '<back><ref id="r1"><label>Smith(2020)Smith and Jones</label></ref></back></article>',
        "xml",
    )
    # Fixed source expectation: the empty xref targets the original r1 label.
    soup.table.find_all("td")[1].__dict__["_source_text"] = "Smith(2020)"
    good = "| Data | [Smith (2020)](https://example.org/article#r1) |"
    assert assert_source_tables([soup.table], good, provider="copernicus") == 1
    for bad in ("| Data |  |", good.replace("2020", "2021")):
        with pytest.raises(AssertionError):
            assert_source_tables([soup.table], bad, provider="copernicus")


def test_plos_formula_oracle_requires_exact_source_identity_and_official_route():
    from tests.support.object_content import image_matches_source

    source = '<inline-formula><inline-graphic href="info:doi/10.1371/journal.pcbi.1003118.e001"/></inline-formula>'
    url = "https://journals.plos.org/ploscompbiol/article/file?id=10.1371/journal.pcbi.1003118.e001&type=thumbnail"
    assert image_matches_source(url, None, source, "plos")
    for wrong in (
        url.replace(".e001", ".e002"),
        url.replace("journals.plos.org", "unrelated.example"),
        url.replace("ploscompbiol", "plosbiology"),
    ):
        assert not image_matches_source(wrong, None, source, "plos")


def test_table_objects_cannot_reuse_or_exchange_rows():
    from tests.support.object_content import assert_source_tables

    tables = BeautifulSoup(
        "<body><table><tr><th>A</th><th>B</th></tr><tr><td>x</td><td>1.5</td></tr></table><table><tr><th>A</th><th>B</th></tr><tr><td>y</td><td>-0.5</td></tr></table></body>",
        "lxml",
    ).find_all("table")
    first = "| A | B |\n| --- | --- |\n| x | 1.5 |"
    second = "| A | B |\n| --- | --- |\n| y | -0.5 |"
    assert assert_source_tables(tables, first + "\n\n" + second) == 4
    for damaged in [second + "\n\n" + first, first, first + "\n\n" + first]:
        with pytest.raises(AssertionError):
            assert_source_tables(tables, damaged)
    with pytest.raises(AssertionError):
        assert_source_tables([tables[0], tables[0]], first)

    # A float callout without a paragraph anchor still checks every table row.
    soup = BeautifulSoup(
        '<article><cross-ref refid="t1">Table 1</cross-ref><floats>'
        '<table id="t1"><tr><td>x</td><td>1.5</td></tr>'
        "<tr><td>y</td><td>-0.5</td></tr></table></floats></article>",
        "xml",
    )
    complete = first + "\n| y | -0.5 |"
    assert (
        assert_source_tables([soup.table], complete, prose_runs=[], provider="elsevier")
        == 2
    )
    with pytest.raises(AssertionError):
        assert_source_tables([soup.table], first, prose_runs=[], provider="elsevier")


def test_object_position_rejects_moving_complete_table():
    from tests.support.object_content import assert_source_tables

    before = "The preceding experimental paragraph establishes the source location for this table."
    after = "The following experimental paragraph discusses the observations from this table."
    soup = BeautifulSoup(
        f"<body><p>{before}</p><table><tr><th>A</th><th>B</th></tr><tr><td>x</td><td>1.5</td></tr></table><p>{after}</p></body>",
        "lxml",
    )
    table = "| A | B |\n| --- | --- |\n| x | 1.5 |"
    assert_source_tables(
        [soup.table],
        before + "\n\n" + table + "\n\n" + after,
        prose_runs=[before, after],
    )
    with pytest.raises(AssertionError):
        assert_source_tables(
            [soup.table],
            before + "\n\n" + after + "\n\n" + table,
            prose_runs=[before, after],
        )


def test_figure_caption_must_belong_to_own_image():
    from types import SimpleNamespace
    from tests.support.object_content import assert_figure_bindings

    fixture = SimpleNamespace(provider="pnas", doi="contract")
    article = SimpleNamespace(assets=[])
    soup = BeautifulSoup(
        '<div id="bodymatter"><figure class="graphic"><img src="https://example.org/one.png"/><figcaption>Figure 1. First experiment at 1.5 mg.</figcaption></figure><figure class="graphic"><img src="https://example.org/two.png"/><figcaption>Figure 2. Second experiment at -0.5 mg.</figcaption></figure></div>',
        "lxml",
    )
    first = "![Figure 1](https://example.org/one.png)\n\nFigure 1. First experiment at 1.5 mg."
    second = "![Figure 2](https://example.org/two.png)\n\nFigure 2. Second experiment at -0.5 mg."
    markdown = first + "\n\n" + second
    assert assert_figure_bindings(fixture, soup, article, markdown) == 2
    with pytest.raises(AssertionError):
        assert_figure_bindings(
            fixture, soup, article, markdown.replace("Figure 1", "Figure 9")
        )
    swapped = (
        markdown.replace("one.png", "TEMP.png")
        .replace("two.png", "one.png")
        .replace("TEMP.png", "two.png")
    )
    with pytest.raises(AssertionError):
        assert_figure_bindings(fixture, soup, article, swapped)


def test_elsevier_main_table_fallback_respects_reference_identity():
    from paper_fetch.providers._article_markdown_elsevier_tables import (
        paragraph_mentions_table,
    )

    assert paragraph_mentions_table("The results are shown in Table 1.", "Table 1")
    assert not paragraph_mentions_table("The results are shown in Table 10.", "Table 1")
    assert not paragraph_mentions_table(
        "The results are shown in Table 1 of Appendix C.", "Table 1"
    )
    assert not paragraph_mentions_table("See Supplementary Table 1.", "Table 1")


def test_plos_figure_oracle_requires_same_object_and_official_rendition():
    from tests.support.object_content import image_matches_source

    source = '<fig><graphic xlink:href="info:doi/10.1371/journal.pone.123.g001"/></fig>'
    url = "https://journals.plos.org/plosone/article/figure/image?size=large&id=10.1371/journal.pone.123.g001"
    assert image_matches_source(url, None, source, "plos")
    for wrong in (
        url.replace("g001", "g002"),
        url.replace("pone.123", "pone.456"),
        url.replace("large", "small"),
        url.replace("plosone", "plosbiology"),
    ):
        assert not image_matches_source(wrong, None, source, "plos")
