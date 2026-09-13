"""HTML-derived semantic oracle for the LST article (not a generated snapshot)."""

from __future__ import annotations

from functools import cache
import re

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
import pytest

from paper_fetch.extraction.html.formula_rules import (
    display_formula_nodes,
    is_display_formula_node,
    is_formula_container,
)
from paper_fetch.models import SemanticLosses
from paper_fetch.providers import _tandf_html
from paper_fetch.providers.atypon_browser_workflow.normalization import (
    _normalize_special_blocks,
)
from paper_fetch.providers.atypon_browser_workflow.formulas import (
    _normalize_display_formula_blocks,
    _normalize_inline_math_nodes,
)
from paper_fetch.providers.tandf import TandfClient
from paper_fetch.utils import normalize_text
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi
from tests.golden_corpus import GoldenCorpusFixture, build_article_from_fixture

DOI = "10.1080/17538947.2022.2137254"
URL = f"https://www.tandfonline.com/doi/full/{DOI}"


def source_html():
    return golden_criteria_asset(DOI, "original.html").read_text(encoding="utf-8")


@cache
def extraction():
    return TandfClient(None, {}).extract_markdown(
        source_html(), URL, metadata={"doi": DOI}
    )


def fixture_article():
    sample = golden_criteria_sample_for_doi(DOI)
    return build_article_from_fixture(GoldenCorpusFixture(sample["sample_id"], sample))


# Independently transcribed from the publisher MathML. Check operands, operations,
# subscripts and ranges; harmless grouping/spacing from the backend is ignored.
FORMULA_PARTS = {
    1: [
        r"Rg",
        r"S_{0}",
        r"\sum\limits_{t}",
        r"M(\alpha_{t})",
        r"\cos(\theta_{t})D_{t}",
        r"\Delta t",
    ],
    2: [
        r"CRg",
        r"S_{0}\int\limits_{t_{1}}^{t_{2}}",
        r"G_{Bt} + G_{Dt} + G_{Gt}",
        r"D_{t}",
        "dt",
    ],
    3: [r"NDVI", r"\frac{{Re}f_{5} - {Re}f_{4}}{{Re}f_{5} + {Re}f_{4}}"],
    4: [
        r"Wetness",
        r"0.1115{Re}f_{2} + 0.1973{Re}f_{3} + 0.3283{Re}f_{4} + 0.3407{Re}f_{5} - 0.7117{Re}f_{6} - 0.4559{Re}f_{7}",
    ],
    5: [
        r"Albedo",
        r"0.356{Re}f_{2} + 0.130{Re}f_{3} + 0.373{Re}f_{4} + 0.085{Re}f_{5} + 0.072{Re}f_{6} + 0.072{Re}f_{7} - 0.0018",
    ],
    6: [r"{NLS}T_{GPLS}", r"{LST}", r" - {{LS}T_{modelGPLS}}"],
    7: [
        r"{LS}T_{modelGPLS}",
        r"a_{1}",
        r"1 - {Albedo}",
        r"\times {CRg}",
        r"+ a_{2}",
        r"{DEM}",
        r"+ a_{3}",
        r"{NDVI}",
        r"+ a_{4}",
        r"{Wetness}",
    ],
    8: [r"{NLS}T_{LPLS}", r"{LST}", r" - {{LS}T_{modelLPLS}}"],
    9: [
        r"{LS}T_{modelLPLS}",
        r"a_{1}(i,",
        r"1 - {Albedo}",
        r"\times {CRg}",
        r"+ a_{2}(i,",
        r"{DEM}",
        r"+ a_{3}(i,",
        r"{NDVI}",
        r"+ a_{4}(i,",
        r"{Wetness}",
    ],
    10: [r"{NLS}T_{GRFR}", r"{LST}", r" - {{LS}T_{modelGRFR}}"],
    11: [
        r"{LS}T_{modelGRFR}",
        r"= f(",
        r"1 - {Albedo}",
        r"\times {CRg}",
        r"{DEM}",
        r"{NDVI}",
        r"{Wetness}",
    ],
    12: [r"{NLS}T_{LRFR}", r"{LST}", r" - {{LS}T_{modelLPLS}}"],
    13: [
        r"{LS}T_{modelLRFR}",
        r"= f_{({i,j})}",
        r"1 - {Albedo}",
        r"\times {CRg}",
        r"{DEM}",
        r"{NDVI}",
        r"{Wetness}",
    ],
}


def assert_formulas(markdown):
    blocks = re.findall(r"\*\*Equation (\d+)\.\*\*\s*\n\$\$\n([^\n]+)\n\$\$", markdown)
    assert [int(n) for n, _ in blocks] == list(range(1, 14))
    assert len(re.findall(r"(?m)^\$\$$", markdown)) == 26
    assert "[Formula unavailable]" not in markdown
    for number, formula in blocks:
        for part in FORMULA_PARTS[int(number)]:

            def canonical(value):
                return re.sub(r"\\(?:;|,|limits)|[{}\s\u2061]", "", value).replace(
                    r"\cos", "cos"
                )

            assert canonical(part) in canonical(formula), (number, part, formula)
        assert "=" in formula
        if int(number) >= 6:
            assert "i," in formula and "j" in formula
    solar = re.search(r"\$([^$]+)\$ is the solar radiation constant", markdown)
    alpha = re.search(r"\$([^$]+)\$ is the solar zenith angle", markdown)
    assert solar and solar.group(1).replace("{", "").replace("}", "") == "S_0"
    assert alpha and alpha.group(1).replace("{", "").replace("}", "") == r"\alpha_t"
    assert "are are the corrected" in markdown  # publisher wording, not a typo to fix


def test_lst_formula_oracle_and_references():
    markdown, diagnostics = extraction()
    assert_formulas(markdown)
    assert not any(diagnostics["semantic_losses"].values())
    soup = BeautifulSoup(source_html(), "lxml")
    refs = soup.select('a[data-label="equation"]')
    assert len(refs) == 11
    assert len([n for n in soup.select(".hidden") if n.find("math")]) == 11
    expected_refs = [
        "Eq. (1)",
        "Eq. (1)",
        "Eq. (2)",
        "Eq. (3)",
        "Eq. (3)",
        "Eq. (4)",
        "Eq. (4)",
        "Eq. (5)",
        "Eq. (5)",
        "(7)",
        "(9)",
    ]
    assert (
        re.findall(r"Eq\. \(\d+\)|(?<=equations )\(7\)|(?<=and )\(9\)", markdown)
        == expected_refs
    )
    assert "In equations (7) and (9), the regression coefficient" in markdown
    article = fixture_article()
    citations = soup.select('li[id^="CIT"]')
    assert len(citations) == len(article.references) == 64
    for index, (node, reference) in enumerate(
        zip(citations, article.references, strict=True), 1
    ):
        for control in node.select(".extra-links"):
            control.decompose()
        assert re.sub(r"\s+", "", reference.raw) == re.sub(
            r"\s+", "", f"{index}. {node.get_text(' ', strip=True)}"
        )


def test_lst_structure_tables_and_figures():
    markdown, _ = extraction()
    soup = BeautifulSoup(source_html(), "lxml")
    headers = [
        normalize_text(n.text)
        for n in soup.select(
            ".hlFld-Fulltext h2, .hlFld-Fulltext h3, .hlFld-Fulltext h4, .hlFld-Fulltext h5"
        )
        if normalize_text(n.text)
    ]
    assert re.findall(r"(?m)^#{2,5} (.+)$", markdown) == headers
    for text in ["a) Vegetation", "b) Wetness", "c) Surface albedo"]:
        assert markdown.count(f"**{text}**") == 1
    for heading in ["Data availability statement", "Disclosure statement"]:
        node = next(n for n in soup.find_all("h2") if normalize_text(n.text) == heading)
        assert normalize_text(node.find_next("p").text) in markdown
    figures = re.findall(
        r"!\[Figure (\d+)\]\(([^)]+)\)\s*\n\s*\*\*Figure \1\.\*\* ([^\n]+)", markdown
    )
    assert [int(n) for n, _, _ in figures] == list(range(1, 13))
    for number, url, caption in figures:
        assert url.endswith(f"_f{int(number):04}_oc.jpg")
        source = next(
            n
            for n in soup.select(".captionText")
            if normalize_text(n.text).startswith(f"Figure {number}. ")
        )
        assert source is not None
        assert (
            normalize_text(source.text)
            == f"Figure {number}. {BeautifulSoup(caption, 'lxml').get_text()}"
        )
    rendered = BeautifulSoup(
        MarkdownIt("commonmark").enable("table").render(markdown), "lxml"
    )
    tables = rendered.find_all("table")
    assert len(tables) == 3
    payload = _tandf_html._tandf_viewer_payload(soup)
    # Independent grid expansion verifies every original cell, including spans.
    for entry, table in zip(payload["tables"], tables, strict=True):
        original = BeautifulSoup(entry["content"], "lxml").table
        grid = {}
        for row_idx, row in enumerate(original.find_all("tr")):
            col = 0
            for cell in row.find_all(["th", "td"], recursive=False):
                while (row_idx, col) in grid:
                    col += 1
                for dr in range(int(cell.get("rowspan", 1))):
                    for dc in range(int(cell.get("colspan", 1))):
                        grid[row_idx + dr, col + dc] = normalize_text(
                            cell.get_text(" ", strip=True)
                        )
                col += int(cell.get("colspan", 1))
        expected = [
            [grid.get((r, c), "") for c in range(1 + max(c for _, c in grid))]
            for r in range(1 + max(r for r, _ in grid))
        ]
        actual = [
            [normalize_text(c.text) for c in r.find_all(["th", "td"])]
            for r in table.find_all("tr")
        ]
        if len(original.select("thead tr")) == 2:
            expected = [
                [
                    expected[0][i]
                    if expected[0][i] == expected[1][i]
                    else f"{expected[0][i]} / {expected[1][i]}"
                    for i in range(len(expected[0]))
                ],
                *expected[2:],
            ]
        assert actual == expected


def test_lst_normalization_is_idempotent():
    soup = BeautifulSoup(_tandf_html.prepare_html_for_extraction(source_html()), "lxml")
    container = soup.select_one(".hlFld-Fulltext")
    losses = SemanticLosses()
    _normalize_special_blocks(container, "tandf", losses)
    before = str(container)
    _normalize_special_blocks(container, "tandf", losses)
    assert str(container) == before
    assert losses == SemanticLosses()


@pytest.mark.parametrize(
    "html,display",
    [
        ('<span class="NLM_disp-formula"><math><mi>x</mi></math></span>', False),
        (
            '<div class="disp-formula"><span class="inline-equation"><math><mi>x</mi></math></span></div>',
            False,
        ),
        (
            '<div class="disp-formula"><math display="inline"><mi>x</mi></math></div>',
            False,
        ),
        ('<span class="display-equation"><math><mi>x</mi></math></span>', True),
        ('<span class="hidden"><math display="block"><mi>x</mi></math></span>', True),
        (
            '<span aria-hidden="true"><math display="inline"><mi>x</mi></math></span>',
            False,
        ),
    ],
)
def test_shared_nearest_formula_classification(html, display):
    soup = BeautifulSoup(html, "lxml")
    assert is_display_formula_node(soup.math) is display


@pytest.mark.parametrize(
    "html",
    [
        '<span class="ref-lnk disp-formula"><a data-label="equation">Eq. (3)</a></span>',
        '<a class="display-equation" href="#eq3">Eq. (3)</a>',
        '<xref class="disp-formula" ref-type="disp-formula" rid="eq3">Eq. (3)</xref>',
    ],
)
def test_shared_formula_references_are_prose(html):
    soup = BeautifulSoup(f"<div>{html}</div>", "lxml")
    assert not display_formula_nodes(soup.div)
    assert not is_formula_container(soup.div.contents[0])
    losses = SemanticLosses()
    _normalize_display_formula_blocks(soup.div, losses)
    _normalize_inline_math_nodes(soup.div, losses)
    assert soup.div.get_text() == "Eq. (3)"
    assert losses == SemanticLosses()


def test_tandf_preserves_unique_hidden_math():
    soup = BeautifulSoup(
        '<div><span class="hidden" id="unique"><math><mi>x</mi></math></span><span class="hidden" id="M1"><math><mi>y</mi></math></span></div>',
        "lxml",
    )
    _tandf_html.tandf_before_block_normalization(soup.div)
    assert len(soup.find_all("math")) == 2


def test_lst_all_prose_paragraphs_survive_in_order():
    soup = BeautifulSoup(source_html(), "lxml").select_one(".hlFld-Fulltext")
    for node in list(
        soup.select(
            ".hidden, .off-screen, .NLM_disp-formula, .NLM_disp-formula-image, .figureView, .tableView, table, script, style"
        )
    ):
        if node.parent:
            node.decompose()
    markdown, _ = extraction()
    without_math = re.sub(
        r"\$\$.*?\$\$|\$[^$\n]+\$|\*\*Equation \d+\.\*\*", "", markdown, flags=re.S
    )
    rendered = BeautifulSoup(MarkdownIt().render(without_math), "lxml").get_text(" ")

    def canonical(text):
        return re.sub(r"\W", "", text).lower()

    remaining = canonical(rendered)
    checked = 0
    for paragraph in soup.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        if len(text) < 30:
            continue
        needle = canonical(text)
        index = remaining.find(needle)
        assert index >= 0, text
        remaining = remaining[index + len(needle) :]
        checked += 1
    assert checked == 44
    assert "\u2063" not in markdown
    assert not re.search(r"[,;:]\\;*\$", markdown)


def test_lst_every_inline_math_preserves_operands_and_scripts():
    soup = BeautifulSoup(source_html(), "lxml")
    # Remove only identified previews; source formulas otherwise stay untouched.
    _tandf_html._drop_tandf_formula_previews(soup)
    originals = [
        n.math
        for n in soup.select(".NLM_disp-formula")
        if "disp-formula" not in n.get("class", [])
    ]
    inline = re.findall(r"(?<!\$)\$(?!\$)([^$\n]+)\$(?!\$)", extraction()[0])
    assert len(originals) == len(inline) == 61
    symbols = {"α": r"\alpha", "θ": r"\theta", "Δ": r"\Delta"}
    for math, latex in zip(originals, inline, strict=True):
        assert latex.count("_") == len(math.find_all("msub"))
        assert latex.count("^") == len(math.find_all("msup"))
        assert latex.count(r"\frac") == len(math.find_all("mfrac"))
        for operand in math.find_all(["mi", "mn"]):
            text = normalize_text(operand.text)
            assert symbols.get(text, text) in latex, (str(math), latex, text)
