"""Reviewed original-source contracts, independent of extracted.md snapshots.

The DOM selections below were reviewed against the captured publisher originals.
They deliberately compare prose and visible bibliography, not equation/image
transcriptions. Whitespace and typographic punctuation are ignored; words,
numbers and their order are preserved. No expected text comes from the renderer.
"""

from tests.support.reviewed_publisher_content import _words
import re
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
import pytest
from tests.golden_corpus import golden_corpus_fixture_for_doi
from tests.support.replay import build_article_from_fixture
from tests.golden_criteria import golden_criteria_asset


CASES = [
    ("10.1371/journal.pone.0263725", "xml", 60),
    ("10.5194/acp-24-1-2024", "xml", 105),
    ("10.3389/fmars.2023.1101972", "xml", 74),
    ("10.1063/5.0129134", "html", 31),
    ("10.1093/bioinformatics/btaa161", "html", 43),
]


@pytest.fixture(scope="module", params=CASES, ids=[c[0] for c in CASES])
def reviewed_article(request):
    doi, kind, reference_count = request.param
    raw = golden_criteria_asset(doi, f"original.{kind}").read_text()
    soup = BeautifulSoup(raw, "xml" if kind == "xml" else "lxml")
    article = build_article_from_fixture(golden_corpus_fixture_for_doi(doi))
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="all", max_tokens="full_text"
    )
    return doi, kind, reference_count, soup, article, markdown


def test_reviewed_visible_references_preserve_every_entry_in_order(reviewed_article):
    doi, kind, count, soup, article, markdown = reviewed_article
    refs = soup.select("ref-list ref" if kind == "xml" else ".ref-list .ref")
    assert len(refs) == len(article.references) == count
    rendered = _words(markdown.split("## References", 1)[1])
    cursor = 0
    for index, (original, reference) in enumerate(
        zip(refs, article.references, strict=True), 1
    ):
        original = BeautifulSoup(str(original), "xml" if kind == "xml" else "lxml")
        for ui in original.select(".citation-links, label, .label"):
            ui.decompose()
        expected = _words(original.get_text(" ", strip=True))
        # Explicit numbering catches duplicates/reordering even for similar entries.
        assert reference.raw.startswith(f"{index}.")
        assert _words(re.sub(r"^\d+\.\s*", "", reference.raw)) == expected, (doi, index)
        cursor = rendered.index(expected, cursor) + len(expected)


def test_reviewed_body_prose_runs_and_headings_remain_in_source_order(reviewed_article):
    doi, kind, _, soup, _, markdown = reviewed_article
    body = (
        soup.body
        if kind == "xml"
        else soup.select_one('[data-widgetname="ArticleFulltext"]')
    )
    assert body is not None
    rendered = _words(markdown.split("## References", 1)[0])
    cursor = 0
    checked = 0
    # Inspect every section, including AIP's Methods after Conclusions and the
    # Frontiers data/author sections. Reference, figure and table prose is separate.
    for node in body.find_all(
        ["title", "p"] if kind == "xml" else ["h2", "h3", "h4", "p"]
    ):
        if node.find_parent(["fig", "table-wrap", "ref-list"]) or node.find_parent(
            class_="ref-list"
        ):
            continue
        if node.name == "p" and node.find(["p", "h2", "h3", "h4"]):
            continue
        if kind == "xml" and node.name == "title" and node.parent.name != "sec":
            continue
        if kind == "html" and (
            node.find_parent(class_="fig") or node.find_parent(class_="table-wrap")
        ):
            continue
        if node.get_text(" ", strip=True).casefold() == "references":
            break
        # Long uninterrupted prose nodes avoid imposing an OCR/math contract.
        # They include first, middle and last paragraphs, not just section labels.
        runs = [str(t) for t in node.strings if len(_words(str(t))) >= 55]
        if node.name in {"title", "h2", "h3", "h4"}:
            runs = [node.get_text(" ", strip=True)]
        for run in runs:
            expected = _words(run)
            assert expected in rendered[cursor:], (doi, node.name, run[:220])
            cursor = rendered.index(expected, cursor) + len(expected)
            checked += 1
    assert checked >= 25, (doi, checked)


@pytest.mark.parametrize(
    "doi,author,title,identifier,index",
    [
        (
            CASES[0][0],
            "Smith ZL",
            "Longitudinal relationship between social media activity and article citations",
            "10.1016/j.gie.2019.03.028",
            59,
        ),
        (
            CASES[1][0],
            "Ma, L.",
            "Kinetics and mass yields of aqueous secondary organic aerosol",
            "10.1021/acs.est.1c00575",
            52,
        ),
        (
            CASES[1][0],
            "Zuo, Y.",
            "Formation of hydrogen peroxide and depletion of oxalic acid",
            "10.1021/es00029a022",
            104,
        ),
        (
            CASES[2][0],
            "Widdicombe S.",
            "Impact of CO2-induced seawater acidification",
            "10.3354/meps341111",
            73,
        ),
        # AIP's captured bibliography omits titles; assert its actual visible journal.
        (
            CASES[3][0],
            "M. Seitanidou",
            "Adv. Healthcare Mater.",
            "10.1002/adhm.201900813",
            0,
        ),
        (CASES[3][0], "A. Prindle", "Nature", "10.1038/nature15709", 15),
        (CASES[3][0], "P. Pansodtee", "PLoS One", "10.1371/journal.pone.0257167", 30),
    ],
)
def test_reviewed_reference_identifiers(doi, author, title, identifier, index):
    article = build_article_from_fixture(golden_corpus_fixture_for_doi(doi))
    reference = article.references[index]
    assert author in reference.raw
    assert title in reference.raw
    assert reference.doi == identifier


def test_real_aip_supplement_identity_and_scope():
    from paper_fetch.providers import _aip_html

    fixture = golden_corpus_fixture_for_doi(CASES[3][0])
    raw = fixture.raw_path.read_text()
    all_assets = _aip_html.scoped_asset_extractor(
        raw, fixture.source_url, asset_profile="all"
    )
    body_assets = _aip_html.scoped_asset_extractor(
        raw, fixture.source_url, asset_profile="body"
    )
    supplements = [a for a in all_assets if a["kind"] == "supplementary"]
    assert {a["url"] for a in supplements} == {
        "https://pubs.aip.org/adv/article-supplement/2820011/zip/125205_1_epaps/"
    }
    assert supplements[0]["filename_hint"] == "125205_1_epaps.zip"
    assert not [a for a in body_assets if a["kind"] == "supplementary"]


def test_real_jats_supplements_retain_source_identity_without_claiming_download():
    for doi, href, heading in [
        (CASES[1][0], "https://doi.org/10.5194/acp-24-1-2024-supplement", "pdf"),
        (CASES[2][0], "Table_1.docx", "Supplementary material"),
    ]:
        article = build_article_from_fixture(golden_corpus_fixture_for_doi(doi))
        supplements = [a for a in article.assets if a.kind == "supplementary"]
        assert len(supplements) == 1
        asset = supplements[0]
        assert asset.source_href == href
        assert asset.heading == heading
        assert asset.section == "supplementary"
        assert asset.path is None and asset.downloaded_bytes is None
        assert href in asset.original_url


def test_real_plos_supporting_files_preserve_all_18_identities():
    doi = "10.1371/journal.pone.0218513"
    article = build_article_from_fixture(golden_corpus_fixture_for_doi(doi))
    soup = BeautifulSoup(golden_criteria_asset(doi, "original.xml").read_text(), "xml")
    originals = soup.find_all("supplementary-material")
    assets = [a for a in article.assets if a.kind == "supplementary"]
    assert len(originals) == len(assets) == 18
    for number, (node, asset) in enumerate(zip(originals, assets, strict=True), 1):
        assert asset.original_url == f"info:doi/{doi}.s{number:03d}"
        assert _words(node.get_text(" ", strip=True)) == _words(asset.heading)
        assert asset.section == "supplementary"
        assert asset.path is None
    assert (
        assets[-1].content_type
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_real_oxford_supplement_has_stable_article_file_identity():
    article = build_article_from_fixture(golden_corpus_fixture_for_doi(CASES[4][0]))
    supplements = [a for a in article.assets if a.kind == "supplementary"]
    assert len(supplements) == 1
    asset = supplements[0]
    assert urlsplit(asset.original_url).path == (
        "/oup/backfile/Content_public/Journal/bioinformatics/36/11/"
        "10.1093_bioinformatics_btaa161/6/bioinformatics_36_11_3409_s1.pdf"
    )
    assert asset.heading == "btaa161_Supplementary_Materials"
    assert asset.section == "supplementary"
    assert asset.path is None


def test_real_oxford_journal_crossref_link_is_not_a_reference_doi():
    article = build_article_from_fixture(golden_corpus_fixture_for_doi(CASES[4][0]))
    reference = article.references[-1]
    assert "Youden W.J. (1950) Index for rating diagnostic tests" in reference.raw
    assert reference.doi is None


def test_reviewed_citations_still_identify_the_visible_reference(reviewed_article):
    doi, _, _, _, article, markdown = reviewed_article
    # These visible callouts and their target entries were checked in the raw
    # xref/anchor markup. The model intentionally renders text, not citation URLs.
    callout, index, target = {
        CASES[0][0]: (
            "traditional metrics or indicators [31]",
            30,
            "Can Google Scholar and Mendeley help",
        ),
        CASES[1][0]: (
            "(Ma et al., 2021",
            52,
            "Kinetics and mass yields of aqueous secondary organic aerosol",
        ),
        CASES[2][0]: (
            "Lewinsohn and Fishelson, 1967",
            37,
            "The second Israel south red Sea expedition 1965",
        ),
        CASES[3][0]: (
            "design demonstrated by Pansodtee et al.31",
            30,
            "10.1371/journal.pone.0257167",
        ),
        CASES[4][0]: (
            "Martinussen and Scheike (2006)",
            21,
            "Dynamic Regression Models for Survival Data",
        ),
    }[doi]
    body = markdown.split("## References", 1)[0]
    assert _words(callout) in _words(body)
    assert target in article.references[index].raw


def test_retained_back_matter_precedes_references(reviewed_article):
    doi, _, _, _, article, markdown = reviewed_article
    anchors = {
        CASES[2][0]: [
            "Author contributions",
            "EV and CC contributed to conception and design",
        ],
        CASES[4][0]: [
            "Acknowledgements",
            "The authors would like to thank the reviewers",
        ],
    }.get(doi)
    if anchors is None:
        return
    body = markdown.split("## References", 1)[0]
    for anchor in anchors:
        assert anchor in body
        assert all(anchor not in reference.raw for reference in article.references)


# Anchors transcribed from original PDF pages (title, middle-page prose, last
# page prose/reference), not extracted.md. These constrain parsing and page
# ordering, and do not claim that a live HTML/XML failure reached these PDFs.
