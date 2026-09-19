"""Original HTML contracts reviewed from publisher DOM, never extracted.md.

Prose uses source text runs to avoid silently adding an OCR contract. References
compare every visible entry; IOP's unopened bibliography instead exposes honest
citation_reference metadata evidence. Fixed equations/rows were transcribed from
MathML, IOP's embedded TeX and the original HTML table cells.
"""

from tests.support.reviewed_html_publisher_content import _table_cell
import re
from copy import deepcopy
from bs4 import BeautifulSoup
import pytest
from tests.golden_corpus import golden_corpus_fixture_for_doi
from tests.support.replay import build_article_from_fixture
from tests.golden_criteria import golden_criteria_asset
from tests.support.reviewed_publisher_content import _words


CASES = [
    ("10.1021/acsomega.4c03987", ".article-body", ".ref-list .ref", 45),
    ("10.1088/2058-9565/ac3460", ".wd-jnl-art-full-text", None, 44),
    ("10.3390/membranes15030093", ".html-body", "#html-references_list li", 44),
    ("10.1098/rsta.2019.0558", ".article-body", ".ref-list .ref", 102),
    (
        "10.1146/annurev-control-030123-013355",
        "#itemFullTextId",
        "#itemFullTextId li.refbody",
        121,
    ),
]


@pytest.fixture(scope="module", params=CASES, ids=[c[0] for c in CASES])
def reviewed_html(request):
    doi, body_selector, ref_selector, count = request.param
    soup = BeautifulSoup(
        golden_criteria_asset(doi, "original.html").read_text(), "lxml"
    )
    article = build_article_from_fixture(golden_corpus_fixture_for_doi(doi))
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="all", max_tokens="full_text"
    )
    return doi, body_selector, ref_selector, count, soup, article, markdown


def test_reviewed_html_references_preserve_source_entries_and_order(reviewed_html):
    doi, _, selector, count, soup, article, markdown = reviewed_html
    assert len(article.references) == count
    cursor = 0
    rendered = _words(markdown.split("## References", 1)[1])
    if selector is None:
        originals = soup.select('meta[name="citation_reference"]')
        # The captured visible bibliography is not loaded. Independently inspect
        # all author/title/journal/date/page/DOI metadata, not a synthetic Smith ref.
        assert not soup.select("#references-wrapper li")
        # Slot 31 is empty in the publisher original; retain the later labels.
        assert len(originals) == count + 1
        assert originals[30]["content"] == ""
        originals = [n for n in originals if n["content"]]
        for node, reference in zip(originals, article.references, strict=True):
            fields = [part.partition("=") for part in node["content"].split(";")]
            for key, separator, value in fields:
                if not separator or not value.strip():
                    continue
                assert _words(value) in _words(reference.raw), (doi, key, value)
                if key.strip() == "citation_doi":
                    assert reference.doi == value.strip().lower()
            expected = _words(reference.raw)
            cursor = rendered.index(expected, cursor) + len(expected)
        return
    originals = soup.select(selector)
    assert len(originals) == count
    for index, (node, reference) in enumerate(
        zip(originals, article.references, strict=True), 1
    ):
        original = deepcopy(node)
        for ui in original.select(
            ".label, .citation-label, .citation-links, .crossref-doi, .adsDoiReference, "
            ".xslopenurl, a.google-scholar, a.cross-ref, .js-references, a.externallink, a.js-externallink"
        ):
            ui.decompose()
        expected = _words(original.get_text(" ", strip=True))
        assert reference.raw.startswith(f"{index}.")
        assert _words(re.sub(r"^\d+\.\s*", "", reference.raw)) == expected, (doi, index)
        cursor = rendered.index(expected, cursor) + len(expected)


def test_reviewed_html_body_runs_and_headings_preserve_order(reviewed_html):
    doi, selector, _, _, soup, _, markdown = reviewed_html
    body = soup.select_one(selector)
    assert body is not None
    rendered = _words(markdown.split("## References", 1)[0])
    cursor = checked = 0
    for node in body.select(
        "h2, h3, h4, p, div.html-p, .section-title, .tl-main-part.title"
    ):
        if node.find_parent(class_="ref-list") or node.find_parent(
            "li", class_="refbody"
        ):
            continue
        if (
            node.find_parent(class_="table-wrap")
            or node.find_parent("table")
            or node.find_parent(class_="fig")
            or node.find_parent(class_="figure")
        ):
            continue
        heading = node.name in {"h2", "h3", "h4"} or bool(
            {"section-title", "tl-main-part"} & set(node.get("class", []))
        )
        if heading and not node.get_text(" ", strip=True):
            continue
        if heading and node.get_text(" ", strip=True) in {
            "References",
            "Reference",
            "Literature Cited",
        }:
            break
        if heading and node.get_text(" ", strip=True).casefold() in {
            "acknowledgments",
            "acknowledgements",
            "supporting information",
        }:
            break
        if node.get_text(" ", strip=True) == "Visual Abstract":
            continue
        if not heading and (
            node.find(["p", "h2", "h3", "h4"]) or node.select_one("div.html-p")
        ):
            continue
        runs = (
            [node.get_text(" ", strip=True)]
            if heading
            else [str(t) for t in node.strings if len(_words(str(t))) >= 55]
        )
        for run in runs:
            expected = _words(run)
            assert expected in rendered[cursor:], (doi, node.name, run[:220])
            cursor = rendered.index(expected, cursor) + len(expected)
            checked += 1
    assert checked >= 25, (doi, checked)


@pytest.mark.parametrize(
    "doi,equations",
    [
        (
            "10.1021/acsomega.3c06992",
            [
                r"ln(P_{(n)}) = a + b(n - 1) + cS_{CNE}",
                r"P_{LC(n)} = a + b(n - 1) + cS_{CNE}",
            ],
        ),
        (
            "10.1088/2058-9565/ac3460",
            [
                r"\begin{equation}\vert {\psi }_{\text{in}}\rangle =\left\vert {I}_{1},{I}_{2},\dots ,{I}_{M}\right\rangle =\left(\prod\limits _{k}\frac{{\hat{a}}_{k}^{{\dagger}{I}_{k}}}{\sqrt{{I}_{k}!}}\right)\left\vert 0\right\rangle ,\end{equation}\tag{1}",
            ],
        ),
        # The source MathML really uses plain xi, vi, ui inside the function/exponent;
        # do not silently repair those to subscripts in the expected equation.
        (
            "10.3390/math11030657",
            [
                r"Y_{i} = f(xi,\beta)e^{vi - ui}(i = 1,2,…,N),",
                r"lnY_{it} = \beta_{0} + \sum\beta_{j}lnx_{it} + v_{it} - u_{it}(i = 1,2,…,N; t = 1,2,…,T),",
            ],
        ),
    ],
)
def test_reviewed_complete_html_equations(doi, equations):
    article = build_article_from_fixture(golden_corpus_fixture_for_doi(doi))
    markdown = article.to_ai_markdown(max_tokens="full_text")
    blocks = [
        re.sub(r"\s+", "", b) for b in re.findall(r"\$\$(.*?)\$\$", markdown, re.S)
    ]
    for equation in equations:
        assert re.sub(r"\s+", "", equation) in blocks


@pytest.mark.parametrize(
    "doi,selector",
    [
        ("10.1021/acsomega.3c06992", 'table[role="table"]'),
        ("10.1088/2058-9565/ac3460", 'table[data-toolbar-link="qstac3460t1"]'),
        ("10.3390/math11030657", "table"),
        ("10.3390/su12072826", "table"),
    ],
)
def test_reviewed_table_all_rows_preserve_column_assignment(doi, selector):
    soup = BeautifulSoup(
        golden_criteria_asset(doi, "original.html").read_text(), "lxml"
    )
    # ACS supplies an accessible table and an aria-hidden duplicate. The first
    # accessible table is PEI/Delta-PEI for n=1..20, reviewed cell by cell.
    table = soup.select_one(
        'table[role="table"]' if doi.startswith("10.1021/") else selector
    )
    assert table is not None
    article = build_article_from_fixture(golden_corpus_fixture_for_doi(doi))
    markdown = article.to_ai_markdown(max_tokens="full_text")
    rows = [
        [_table_cell(c) for c in line.strip().strip("|").split("|")]
        for line in markdown.splitlines()
        if line.startswith("|")
    ]
    originals = [
        [
            _table_cell(c.get_text(" ", strip=True))
            for c in tr.find_all(["th", "td"], recursive=False)
        ]
        for tr in table.select("tr")
    ]
    assert len(originals) >= 6
    cursor = 0
    for row in originals:
        assert row in rows[cursor:], (doi, row, rows[:2])
        cursor = rows.index(row, cursor) + 1


def test_iop_missing_original_reference_slot_does_not_shift_later_citations():
    doi = "10.1088/2058-9565/ac3460"
    soup = BeautifulSoup(
        golden_criteria_asset(doi, "original.html").read_text(), "lxml"
    )
    assert soup.select('meta[name="citation_reference"]')[30]["content"] == ""
    cite = soup.select_one('a[href="#qstac3460bib45"]')
    assert cite is not None and cite.get_text(strip=True) == "45"
    assert "extremely randomized trees (ERTs)" in cite.parent.get_text()
    article = build_article_from_fixture(golden_corpus_fixture_for_doi(doi))
    reference = article.references[-1]
    assert reference.raw.startswith("45.")
    assert "Geurts P" in reference.raw
    assert "Extremely randomized trees" in reference.raw
    assert reference.doi == "10.1007/s10994-006-6226-1"
    markdown = article.to_ai_markdown(include_refs="all", max_tokens="full_text")
    assert "45. Geurts P" in markdown
    assert "44. Geurts P" not in markdown
    assert _words("extremely randomized trees (ERTs) [45]") in _words(
        markdown.split("## References", 1)[0]
    )


def test_reviewed_supplements_source_identity_and_body_all_scopes():
    from paper_fetch.providers import (
        _annualreviews_html,
        _mdpi_assets,
        _royalsocietypublishing_html,
    )

    doi = "10.3390/s23010001"
    fixture = golden_corpus_fixture_for_doi(doi)
    raw = fixture.raw_path.read_text()
    soup = BeautifulSoup(raw, "lxml")
    download = soup.select_one('a[href="/1424-8220/23/1/1/s1?version=1671522668"]')
    assert download is not None and download.get_text(strip=True) == "ZIP-Document"
    supplements = [
        a
        for a in _mdpi_assets.extract_scoped_html_assets(
            raw, fixture.source_url, asset_profile="all"
        )
        if a["kind"] == "supplementary"
    ]
    assert len(supplements) == 1
    assert supplements[0]["url"] == "https://www.mdpi.com/article/10.3390/s23010001/s1"
    assert "Table S1: Sources used in SLR." in supplements[0]["caption"]
    assert supplements[0]["section"] == "supplementary"
    assert not [
        a
        for a in _mdpi_assets.extract_scoped_html_assets(
            raw, fixture.source_url, asset_profile="body"
        )
        if a["kind"] == "supplementary"
    ]
    # This source identifies the S1 ZIP endpoint, not a downloaded archive filename.

    doi = "10.1098/rsif.2019.0334"
    fixture = golden_corpus_fixture_for_doi(doi)
    raw = fixture.raw_path.read_text()
    extracted = _royalsocietypublishing_html.extract_markdown(
        raw, fixture.source_url, asset_profile="all"
    )
    supplements = [
        a for a in extracted.extracted_assets if a["kind"] == "supplementary"
    ]
    assert [(a["url"], a["heading"], a["section"]) for a in supplements] == [
        (
            "https://royalsocietypublishing.org/rsif/article-supplement/87174/pdf/rsif20190334supp1/",
            "sp1",
            "supplementary",
        )
    ]
    body_extracted = _royalsocietypublishing_html.extract_markdown(
        raw, fixture.source_url, asset_profile="body"
    )
    assert not [
        a for a in body_extracted.extracted_assets if a["kind"] == "supplementary"
    ]

    doi = "10.1146/annurev-neuro-062111-150343"
    fixture = golden_corpus_fixture_for_doi(doi)
    raw = fixture.raw_path.read_text()
    supplements = [
        a
        for a in _annualreviews_html.extract_scoped_html_assets(
            raw, fixture.source_url, asset_profile="all"
        )
        if a["kind"] == "supplementary"
    ]
    filenames = [
        "ne36_schiller_supmat.pdf",
        *[f"schiller_video{i}.mpg" for i in range(1, 5)],
    ]
    assert [a["url"] for a in supplements] == [
        f"https://www.annualreviews.org/deliver/fulltext/neuro/36/1/{name}?itemId=/content/suppdata/{doi}/1"
        for name in filenames
    ]
    assert [a["heading"] for a in supplements] == [
        "Supplemental Material",
        *[f"Supplemental Video {i}" for i in range(1, 5)],
    ]
    assert all(a["section"] == "supplementary" for a in supplements)
    assert "Supplemental Figures 1-6" in supplements[0]["caption"]
    assert not [
        a
        for a in _annualreviews_html.extract_scoped_html_assets(
            raw, fixture.source_url, asset_profile="body"
        )
        if a["kind"] == "supplementary"
    ]


@pytest.mark.parametrize(
    "doi,index,author,title,identifier",
    [
        (
            CASES[0][0],
            0,
            "Liu",
            "Metal Catalysts for Heterogeneous Catalysis",
            "10.1021/acs.chemrev.7b00776",
        ),
        (
            CASES[0][0],
            22,
            "Fiorio",
            "Recent Advances in the Use of Nitrogen-Doped Carbon Materials",
            "10.1016/j.ccr.2023.215053",
        ),
        (
            CASES[0][0],
            44,
            "Tashrifi",
            "Recent Advances in the Oxidative Conversion of Benzylamines",
            "10.1016/j.tet.2021.131990",
        ),
        (
            CASES[1][0],
            0,
            "Montanaro A",
            "Quantum algorithms: an overview",
            "10.1038/npjqi.2015.23",
        ),
        (
            CASES[1][0],
            22,
            "Devoret M H",
            "Superconducting circuits for quantum information: an outlook",
            "10.1126/science.1231930",
        ),
        (
            CASES[2][0],
            0,
            "Gkotsis",
            "Membrane-Based Technologies for Post-Combustion CO2 Capture",
            "10.3390/membranes13120898",
        ),
        (
            CASES[2][0],
            22,
            "Bozonc",
            "3D-CFD Modeling of Hollow-Fiber Membrane Contactor",
            "10.3390/membranes14040086",
        ),
        (
            CASES[2][0],
            43,
            "Shirazian",
            "Theoretical investigations on the effect of absorbent type",
            "10.1371/journal.pone.0236367",
        ),
        (
            CASES[3][0],
            0,
            "Niederer SA",
            "Computational models in cardiology",
            "10.1038/s41569-018-0104-y",
        ),
        (
            CASES[3][0],
            51,
            "Corrado C",
            "Identification of weakly coupled multiphysics problems",
            "10.1016/j.jcp.2014.11.041",
        ),
        (
            CASES[3][0],
            101,
            "Sengupta PP",
            "The new wave of cardiovascular biomechanics",
            "10.1016/j.jcmg.2019.05.013",
        ),
        (CASES[4][0], 0, "Shah D", "Shape changing robots", "10.1002/adma.202002882"),
        (
            CASES[4][0],
            60,
            "Saguin-Sprynski N",
            "Surfaces reconstruction via inertial sensors for monitoring",
            None,
        ),
        (
            CASES[4][0],
            120,
            "El-Atab N",
            "Soft actuators for soft robotic applications: a review",
            "10.1002/aisy.202000128",
        ),
    ],
)
def test_reviewed_html_reference_author_title_and_doi(
    doi, index, author, title, identifier
):
    article = build_article_from_fixture(golden_corpus_fixture_for_doi(doi))
    ref = article.references[index]
    assert _words(author) in _words(ref.raw)
    assert _words(title) in _words(ref.raw)
    assert ref.doi == identifier


@pytest.mark.parametrize(
    "doi,callout,target",
    [
        (
            CASES[0][0],
            "used heterogeneous catalysts. (1)",
            "Metal Catalysts for Heterogeneous Catalysis",
        ),
        (CASES[1][0], "quantum algorithms [1]", "Quantum algorithms: an overview"),
        (
            CASES[2][0],
            "emission from large-scale industrial sources [1]",
            "Membrane-Based Technologies for Post-Combustion",
        ),
        (
            CASES[3][0],
            "moving patient-specific modelling into the clinic [1]",
            "Computational models in cardiology",
        ),
        (CASES[4][0], "that changes shape (1)", "Shape changing robots"),
    ],
)
def test_reviewed_html_body_callout_maps_to_first_reference(doi, callout, target):
    article = build_article_from_fixture(golden_corpus_fixture_for_doi(doi))
    markdown = article.to_ai_markdown(include_refs="all", max_tokens="full_text")
    assert _words(callout) in _words(markdown.split("## References", 1)[0])
    assert _words(target) in _words(article.references[0].raw)
