"""Reviewed publisher originals: prose order, complete visible references and cells.

Image-only equations/tables prove source identity, never OCR transcription.
Old Nature, modern Nature and Springer Classic are separate original templates.
"""

import re
import html
from urllib.parse import urljoin
from tests.support.test_evidence import evidence_cache as cache
from bs4 import BeautifulSoup
import pytest
from tests.golden_corpus import GoldenCorpusFixture
from tests.support.replay import build_article_from_fixture
from tests.golden_criteria import golden_criteria_sample_for_doi
from tests.support.reviewed_publisher_content import _words
from tests.support.reviewed_html_publisher_content import _table_cell


CASES = [
    (
        "10.1111/gcb.16414",
        ".article-section__full",
        ".article-section__references li",
        59,
    ),
    ("10.1126/science.ady3136", "#bodymatter", '#bibliography [role="listitem"]', 71),
    ("10.1073/pnas.2406303121", "#bodymatter", '#bibliography [role="listitem"]', 78),
    ("10.1038/nature12915", ".main-content", ".c-article-references__text", 51),
    ("10.1038/s41561-022-00912-7", ".main-content", ".c-article-references__text", 95),
    ("10.1007/s10584-011-0143-4", ".main-content", ".c-article-references__text", 39),
    (
        "10.1175/jamc-d-24-0048.1",
        "#articleBody",
        "#contentRoot .reference > p.citationText",
        44,
    ),
]


@cache
def _review(doi):
    sample = golden_criteria_sample_for_doi(doi)
    fixture = GoldenCorpusFixture(sample_id=sample["sample_id"], sample=sample)
    soup = BeautifulSoup(fixture.raw_path.read_text(), "lxml")
    article = build_article_from_fixture(fixture)
    return (
        soup,
        article,
        article.to_ai_markdown(
            include_refs="all", asset_profile="all", max_tokens="full_text"
        ),
    )


@pytest.mark.parametrize("doi,body_selector,ref_selector,count", CASES)
def test_all_visible_reference_entries_preserve_text_and_order(
    doi, body_selector, ref_selector, count
):
    soup, article, markdown = _review(doi)
    originals = soup.select(ref_selector)
    assert len(originals) == len(article.references) == count
    rendered = _words(html.unescape(markdown.split("## References", 1)[1]))
    cursor = 0
    for index, (node, ref) in enumerate(
        zip(originals, article.references, strict=True), 1
    ):
        original = BeautifulSoup(str(node), "lxml")
        for ui in original.select(
            ".label, .citation-label, .citation-links, .extra-links, .ref-links, .external-links"
        ):
            ui.decompose()
        expected = _words(original.get_text(" ", strip=True))
        assert _words(html.unescape(re.sub(r"^\d+\.\s*", "", ref.raw))) == expected, (
            doi,
            index,
            ref.raw,
            original.get_text(" ", strip=True),
        )
        cursor = rendered.index(expected, cursor) + len(expected)


@pytest.mark.parametrize("doi,body_selector,ref_selector,count", CASES)
def test_major_body_sections_prose_runs_remain_in_source_order(
    doi, body_selector, ref_selector, count
):
    soup, _, markdown = _review(doi)
    body = soup.select_one(body_selector)
    assert body is not None
    rendered = _words(markdown.split("## References", 1)[0])
    cursor = checked = 0
    for node in body.select("h2,h3,h4,p,div[role=paragraph]"):
        if (
            node.find_parent(["figure", "table"])
            or node.find_parent(class_="c-article-references__item")
            or node.find_parent(class_="reference")
        ):
            continue
        title = node.get_text(" ", strip=True)
        if node.name.startswith("h") and title.casefold().rstrip(".") in {
            "references",
            "references and notes",
            "acknowledgments",
            "acknowledgements",
            "author contributions",
            "change history",
        }:
            break
        if node.name in {"p", "div"} and node.find(["p", "h2", "h3", "h4"]):
            continue
        if not title:
            continue
        runs = (
            [title]
            if node.name.startswith("h")
            else [str(t) for t in node.strings if len(_words(str(t))) >= 55]
        )
        for run in runs:
            if doi == "10.1038/nature12915" and run == "Online Methods":
                run = "Methods"
            expected = _words(re.sub(r"\brefs?\.\s*$", "", run))
            assert expected in rendered[cursor:], (doi, node.name, run[:230])
            cursor = rendered.index(expected, cursor) + len(expected)
            checked += 1
    assert checked >= 25, (doi, checked)


@pytest.mark.parametrize("doi", ["10.1073/pnas.2406303121"])
def test_complete_representative_table_preserves_every_value_and_column(doi):
    soup, _, markdown = _review(doi)
    originals = [
        [
            _table_cell(c.get_text(" ", strip=True))
            for c in tr.find_all(["td", "th"], recursive=False)
        ]
        for tr in soup.select_one("table").select("tr")
    ]
    rows = [
        [_table_cell(c) for c in line.strip().strip("|").split("|")]
        for line in markdown.splitlines()
        if line.startswith("|")
    ]
    assert len(originals) == 13
    cursor = 0
    for row in originals:
        assert row in rows[cursor:], (doi, row)
        cursor = rows.index(row, cursor) + 1


@pytest.mark.parametrize(
    "doi,index,author,title,identifier",
    [
        (
            CASES[0][0],
            0,
            "Arora",
            "Small temperature benefits provided by realistic afforestation efforts",
            "10.1038/ngeo1182",
        ),
        (
            CASES[0][0],
            29,
            "Lian",
            "Biophysical impacts of northern vegetation changes on seasonal warming patterns",
            "10.1038/s41467-022-31671-z",
        ),
        (
            CASES[0][0],
            58,
            "Zhu",
            "Greening of the Earth and its drivers",
            "10.1038/nclimate3004",
        ),
        (
            CASES[1][0],
            0,
            "Mutsaers",
            "The impact of fibrotic diseases on global mortality from 1990 to 2019",
            "10.1186/s12967-023-04690-7",
        ),
        (
            CASES[1][0],
            35,
            "Currie",
            "Live Imaging of Axolotl Digit Regeneration Reveals Spatiotemporal Choreography",
            "10.1016/j.devcel.2016.10.013",
        ),
        (
            CASES[1][0],
            70,
            "Mui",
            "JosephJYW/HA_TissueMechanics_Science2026",
            "10.5281/zenodo.18458384",
        ),
        (
            CASES[2][0],
            0,
            "World Health Organization",
            "Number of COVID-19 deaths reported to WHO",
            None,
        ),
        (CASES[2][0], 39, "Samuel", "Antiviral actions of interferons", None),
        (
            CASES[2][0],
            77,
            "Miao",
            "On identifiability of nonlinear ODE models and applications in viral dynamics",
            "10.1137/090757009",
        ),
        (
            CASES[3][0],
            0,
            "Cox",
            "Acceleration of global warming due to carbon-cycle feedbacks",
            None,
        ),
        (
            CASES[3][0],
            25,
            "Schwalm",
            "Does terrestrial drought explain global CO2 flux anomalies",
            None,
        ),
        (
            CASES[3][0],
            50,
            "Alexander",
            "Climate Change 2013: The Physical Science Basis",
            None,
        ),
        (CASES[4][0], 0, "Ligtvoet", "The Geography of Future Water Challenges", None),
        (
            CASES[4][0],
            47,
            "Findell",
            "Rising temperatures increase importance of oceanic evaporation",
            "10.1175/jcli-d-19-0145.1",
        ),
        (
            CASES[4][0],
            94,
            "Pfahl",
            "On the relationship between extratropical cyclone precipitation and intensity",
            "10.1002/2016gl068018",
        ),
        (
            CASES[5][0],
            0,
            "Aerts",
            "Climate change in contrasting river basins",
            "10.1079/9780851998350.0000",
        ),
        (
            CASES[5][0],
            19,
            "Mae",
            "Thermail drilling and temperature measurements",
            None,
        ),
        (
            CASES[5][0],
            38,
            "Zhang",
            "Observed degree-day factors and their spatial variation",
            "10.3189/172756406781811952",
        ),
        (
            CASES[6][0],
            0,
            "Akter",
            "Climatology of the premonsoon Indian dryline",
            "10.1002/joc.4968",
        ),
        (
            CASES[6][0],
            22,
            "Jiménez",
            "Assessment of the GOES-16 clear sky mask product",
            "10.3390/rs12101630",
        ),
        (
            CASES[6][0],
            43,
            "Ziegler",
            "Convective initiation at the dryline: A modeling study",
            "10.1175/1520-0493(1997)125<1001:ciatda>2.0.co;2",
        ),
    ],
)
def test_reviewed_first_middle_last_reference_identity(
    doi, index, author, title, identifier
):
    _, article, _ = _review(doi)
    ref = article.references[index]
    assert author in ref.raw and title in ref.raw
    assert ref.doi == identifier


def test_wiley_complete_approved_device_table_preserves_all_rows():
    soup, _, markdown = _review("10.1111/cas.16395")
    original = soup.select_one("table.article-section__table")
    rows = [
        [_table_cell(c) for c in line.strip().strip("|").split("|")]
        for line in markdown.splitlines()
        if line.startswith("|")
    ]
    cursor = 0
    for tr in original.select("tr"):
        row = [
            _table_cell(c.get_text(" ", strip=True))
            for c in tr.find_all(["th", "td"], recursive=False)
        ]
        assert len(row) == 7
        assert row in rows[cursor:], row
        cursor = rows.index(row, cursor) + 1
    assert cursor == 20


def test_science_entire_precipitation_variability_equation():
    soup, _, markdown = _review("10.1126/science.adp0212")
    formula = soup.select_one('math[display="block"]')
    assert formula.get_text(" ", strip=True) == "σ P ≈ σ − ω m q l g"
    expected = r"\sigma P \approx \sigma(- \frac{\omega_{\text{m}}q_{\text{l}}}{g})"
    blocks = [
        re.sub(r"\s+", "", v) for v in re.findall(r"\$\$(.*?)\$\$", markdown, re.S)
    ]
    assert re.sub(r"\s+", "", expected) in blocks


def test_wiley_original_figure_and_image_only_formula_identity():
    from paper_fetch.providers.atypon_browser_workflow import (
        extract_atypon_browser_workflow_markdown,
    )
    from tests.golden_criteria import golden_criteria_asset

    soup, _, markdown = _review("10.1111/gcb.16414")
    image_url = (
        "/cms/asset/6ec811d9-e77c-4f0b-86f6-b34f4f936ff2/gcb16414-fig-0001-m.jpg"
    )
    assert soup.select_one(".article-section__full img")["data-lg-src"] == image_url
    assert image_url in markdown
    doi = "10.1111/gcb.15322"
    raw = golden_criteria_asset(doi, "original.html").read_text()
    soup = BeautifulSoup(raw, "lxml")
    image_url = "/cms/asset/9841141f-ff64-4347-a2f1-c0fa2b92a994/gcb15322-math-0001.png"
    node = soup.select_one(f'img[src="{image_url}"]')
    assert node is not None
    # No alt equation text is supplied for this bitmap; preserve identity only.
    assert node["alt"] == "urn:x-wiley:13541013:media:gcb15322:gcb15322-math-0001"
    source_url = f"https://onlinelibrary.wiley.com/doi/full/{doi}"
    markdown, _ = extract_atypon_browser_workflow_markdown(
        raw,
        source_url,
        "wiley",
        metadata={"doi": doi},
    )
    assert f"![Formula]({urljoin(source_url, image_url)})" in markdown
    assert markdown.index("**Equation 1.**") < markdown.index(image_url)


def test_ams_full_boundary_layer_water_equation_and_table_bitmap_boundary():
    soup, _, markdown = _review("10.1175/jamc-d-24-0048.1")
    original = soup.select_one('#contentRoot .formula script[type="math/mml"]')
    assert original is not None and "<msubsup><mo>∫</mo>" in original.string
    expected = r"\text{BLPW} = \frac{1}{\rho_{w}}\int_{z_{\text{sfc}}}^{z_{b}}\rho q_{\upsilon}dz = \frac{-1}{\rho_{w}g}\int_{p_{s}}^{p_{b}}q_{\upsilon}dp(\text{in mm}),"

    # Ignore renderer-only grouping braces/delimiter sizing; retain the complete
    # ordered operator/operand/subscript/superscript token sequence.
    def tokens(value):
        return re.sub(r"[{}\s]", "", value.replace(r"\left", "").replace(r"\right", ""))

    blocks = re.findall(r"\$\$(.*?)\$\$", markdown, re.S)
    assert tokens(expected) in [tokens(b) for b in blocks]
    path = "/view/journals/apme/63/12/full-JAMC-D-24-0048.1-t1.jpg"
    assert soup.select_one(f'img[data-image-src="{path}"]') is not None
    assert path in markdown
    # This capture provides a table image, no HTML cells to mislabel as parsed.
    table = soup.select_one("#contentRoot .tableWrap")
    assert table is not None and table.select_one("table") is None


@pytest.mark.parametrize("doi,body_selector,ref_selector,count", CASES)
def test_original_body_citations_map_to_preserved_reference_entries(
    doi, body_selector, ref_selector, count
):
    soup, article, markdown = _review(doi)
    body = soup.select_one(body_selector)
    originals = soup.select(ref_selector)
    targets = {}
    for index, node in enumerate(originals):
        # AMS reference paragraph is inside refList_bibN; Wiley owns data-bib-id.
        for candidate in [node, *list(node.parents)[:2], *node.select("[id]")]:
            key = candidate.get("id") or candidate.get("data-bib-id")
            if key:
                targets[key] = index
    checked = 0
    for anchor in body.select("a[href]"):
        key = str(anchor["href"]).partition("#")[2].replace("core-collateral-", "")
        if key not in targets:
            continue
        label = anchor.get_text(" ", strip=True)
        if not label:
            continue
        ref = article.references[targets[key]]
        assert _words(label) in _words(markdown.split("## References", 1)[0])
        assert _words(html.unescape(ref.raw)) in _words(
            html.unescape(markdown.split("## References", 1)[1])
        )
        if doi.startswith("10.1038/"):
            assert re.sub(r"\D", "", label) == str(targets[key] + 1)
            assert ref.raw.startswith(f"{targets[key] + 1}.")
        checked += 1
    assert checked >= 10, (doi, checked)
