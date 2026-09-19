"""Independent review of existing Elsevier/IEEE/arXiv/T&F originals.

Long prose runs exclude math/asset payloads; bitmap tables do not prove cells.
IEEE pagination below is a constructed transport around real entries, not a
capture of multiple publisher pages. Ancillary fixtures are original excerpts.
"""

from copy import deepcopy
from tests.support.test_evidence import evidence_cache as cache
import hashlib
import html
import json
import re
from bs4 import BeautifulSoup
import pytest
from paper_fetch.providers import _ieee_metadata
from tests.fixture_catalog import fixture_catalog
from tests.golden_corpus import GoldenCorpusFixture
from tests.support.replay import build_article_from_fixture
from tests.golden_criteria import (
    golden_criteria_asset,
    golden_criteria_manifest,
    golden_criteria_sample_for_doi,
)
from tests.support.reviewed_publisher_content import _words
from tests.support.reviewed_html_publisher_content import _table_cell


ELSEVIER = "10.1016/j.agrformet.2024.109975"
IEEE = "10.1109/TDEI.2024.3373549"
ARXIV = "10.48550/arxiv.2605.06663v1"
TANDF = "10.1080/17538947.2022.2137254"

# The IEEE HTML capture starts with an XML declaration but is HTML.
pytestmark = pytest.mark.filterwarnings(
    "ignore:It looks like.*:bs4.XMLParsedAsHTMLWarning"
)


@cache
def _review(doi):
    sample = golden_criteria_sample_for_doi(doi)
    fixture = GoldenCorpusFixture(sample["sample_id"], sample)
    soup = BeautifulSoup(
        fixture.raw_path.read_text(encoding="utf-8"),
        "xml" if fixture.raw_path.suffix == ".xml" else "lxml",
    )
    article = build_article_from_fixture(fixture)
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="all", max_tokens="full_text"
    )
    return soup, article, markdown


@pytest.mark.parametrize(
    "doi,count", [(ELSEVIER, 45), (IEEE, 22), (ARXIV, 50), (TANDF, 64)]
)
def test_all_original_reference_entries_and_rendered_order(doi, count):
    soup, article, markdown = _review(doi)
    assert len(article.references) == count
    rendered = _words(html.unescape(markdown.split("## References", 1)[1]))
    cursor = 0
    if doi == IEEE:
        originals = json.loads(
            golden_criteria_asset(doi, "references.json").read_text()
        )["references"]
    else:
        originals = soup.select(
            {ELSEVIER: "bib-reference", ARXIV: ".ltx_bibitem", TANDF: 'li[id^="CIT"]'}[
                doi
            ]
        )
    assert len(originals) == count
    for index, (node, reference) in enumerate(
        zip(originals, article.references, strict=True), 1
    ):
        if doi == ELSEVIER:
            # Structured XML reorders author initials/date. Check every supplied
            # field independently, excluding the duplicate source-text record.
            original = node.find("reference")
            assert original is not None
            for field in original.find_all(
                [
                    "given-name",
                    "surname",
                    "maintitle",
                    "volume-nr",
                    "issue-nr",
                    "date",
                    "first-page",
                    "last-page",
                    "doi",
                ]
            ):
                assert _words(field.get_text()) in _words(reference.raw), (index, field)
            assert node.find("label").get_text() in reference.raw
            doi_node = original.find("doi")
            link = original.find("inter-ref")
            source_doi = (
                doi_node.get_text().lower()
                if doi_node
                else (
                    link.get("xlink:href", "").removeprefix("https://doi.org/")
                    if link
                    else None
                )
            )
            assert reference.doi == source_doi
            expected = _words(reference.raw)
        else:
            if doi == IEEE:
                expected = _words(
                    BeautifulSoup(node["text"], "lxml").get_text(" ", strip=True)
                )
                assert reference.raw.startswith(f"{node['order']}.")
            else:
                original = deepcopy(node)
                for control in original.select(
                    ".extra-links, .ltx_tag_bibitem, .ltx_bib_cited"
                ):
                    control.decompose()
                for block in original.select(".ltx_bibblock"):
                    if block.get_text(strip=True).startswith("External Links:"):
                        block.decompose()
                expected = _words(original.get_text(" ", strip=True))
            raw_without_label = re.sub(r"^(?:\d+\.|\[\d+\])\s*", "", reference.raw)
            assert _words(raw_without_label) == expected, (doi, index)
        cursor = rendered.index(expected, cursor) + len(expected)


@pytest.mark.parametrize(
    "doi,selector,minimum",
    [
        (ELSEVIER, "body", 50),
        (IEEE, "#article", 50),
        (ARXIV, "article", 100),
        (TANDF, ".hlFld-Fulltext", 40),
    ],
)
def test_major_sections_and_long_prose_including_arxiv_appendices(
    doi, selector, minimum
):
    soup, _, markdown = _review(doi)
    body = soup.select_one(selector)
    assert body is not None
    rendered = _words(
        re.sub(
            r"\$\$.*?\$\$|\$[^$\n]+\$",
            "",
            markdown.split("## References", 1)[0],
            flags=re.S,
        )
    )
    cursor = checked = 0
    for node in body.find_all(["h2", "h3", "h4", "section-title", "p", "para"]):
        if node.find_parent(
            [
                "figure",
                "table",
                "bib-reference",
                "conflict-of-interest",
                "acknowledgment",
                "acknowledgments",
            ]
        ) or node.find_parent(class_="ltx_bibliography"):
            continue
        if any(
            node.find_parent(class_=c)
            for c in (
                "figure",
                "figureView",
                "tableView",
                "ltx_abstract",
                "ltx_bibitem",
            )
        ):
            continue
        if doi == ELSEVIER and any(
            parent.find("section-title", recursive=False)
            and parent.find("section-title", recursive=False).get_text()
            == "Supplementary materials"
            for parent in node.find_parents("section")
        ):
            continue
        is_heading = node.name in {"h2", "h3", "h4", "section-title"}
        title = node.get_text(" ", strip=True)
        if not title or (
            is_heading
            and title in {"References", "Acknowledgments", "Supplementary materials"}
        ):
            continue
        if node.find(["p", "para"]):
            continue
        if is_heading:
            # MathML heading text contains duplicate presentation/TeX branches.
            original = deepcopy(node)
            for math in original.find_all("math"):
                math.replace_with("")
            runs = [original.get_text(" ", strip=True)]
        else:
            runs = [
                str(t)
                for t in node.strings
                if len(_words(str(t))) >= 55
                and not t.find_parent(
                    [
                        "math",
                        "tex-math",
                        "disp-formula",
                        "inline-formula",
                        "script",
                        "style",
                    ]
                )
            ]
        for run in runs:
            expected = _words(run)
            assert expected in rendered[cursor:], (doi, node.name, run[:220])
            cursor = rendered.index(expected, cursor) + len(expected)
            checked += 1
    assert checked >= minimum, (doi, checked)


@pytest.mark.parametrize(
    "doi,index,author,title,identifier",
    [
        (
            ELSEVIER,
            0,
            "Anav",
            "Spatiotemporal patterns of terrestrial gross primary production",
            "10.1002/2015rg000483",
        ),
        (ELSEVIER, 22, "Liu", "Simulating the onset of spring vegetation growth", None),
        (
            ELSEVIER,
            44,
            "Zscheischler",
            "Impact of large-scale climate extremes",
            "10.1002/2014gb004826",
        ),
        (
            IEEE,
            0,
            "Hu",
            "DC flashover performance of ice-covered insulators",
            "10.1049/iet-gtd.2015.1463",
        ),
        (
            IEEE,
            11,
            "Gouda",
            "Pollution severity monitoring",
            "10.1109/access.2022.3175515",
        ),
        (
            IEEE,
            21,
            "Du",
            "Recurrence plot analysis of discharge currents",
            "10.1109/tdei.2008.4591218",
        ),
        (ARXIV, 0, "Bisk", "PIQA: reasoning about physical commonsense", None),
        (ARXIV, 25, "Mihaylov", "Can a suit of armor conduct electricity", None),
        (ARXIV, 49, "Zellers", "HellaSwag", "10.18653/v1/p19-1472"),
        (
            TANDF,
            0,
            "Alavipanah",
            "Monitoring Spatiotemporal Changes of Heat Island",
            None,
        ),
        (
            TANDF,
            32,
            "Karnieli",
            "Use of NDVI and Land Surface Temperature for Drought Assessment",
            "10.1175/2009jcli2900.1",
        ),
        (
            TANDF,
            63,
            "Zhao",
            "Normalization of the Temporal Effect",
            "10.1016/j.isprsjprs.2019.04.008",
        ),
    ],
)
def test_reviewed_first_middle_last_reference_identity(
    doi, index, author, title, identifier
):
    _, article, _ = _review(doi)
    reference = article.references[index]
    assert _words(author) in _words(reference.raw)
    assert _words(title) in _words(reference.raw)
    assert reference.doi == identifier


def test_arxiv_full_table_one_keeps_all_numeric_rows_and_columns():
    soup, _, markdown = _review(ARXIV)
    table = soup.find("table", id="S5.T1.1")
    originals = [
        [
            _table_cell(c.get_text(" ", strip=True))
            for c in row.find_all(["th", "td"], recursive=False)
        ]
        for row in table.select("tr")
    ]
    rows = [
        [_table_cell(c) for c in line.strip().strip("|").split("|")]
        for line in markdown.splitlines()
        if line.startswith("|")
    ]
    assert len(originals) == 7
    cursor = 0
    for row in originals:
        cursor = rows.index(row, cursor) + 1


@pytest.mark.parametrize(
    "doi,equations",
    [
        (ELSEVIER, [r"F_{crit} = \sum\limits_{t_{p}}^{SOS_{y0}}R_{f}"]),
        (
            ARXIV,
            [
                r"\mathcal{L}_{\mathrm{CE}}=-\sum\limits_{t=1}^{T}\log P(x_{t}\mid x_{<t}),",
                r"\mathcal{L}=\mathcal{L}_{\mathrm{CE}}+\alpha\mathcal{L}_{\mathrm{LB}}+\beta\mathcal{L}_{\mathrm{RZ}},",
                r"d\sim\mathcal{U}\{k,\dots,n_{r}\}.",
            ],
        ),
    ],
)
def test_complete_reviewed_equations(doi, equations):
    _, _, markdown = _review(doi)
    blocks = [
        re.sub(r"\s+", "", b) for b in re.findall(r"\$\$(.*?)\$\$", markdown, re.S)
    ]
    for equation in equations:
        assert re.sub(r"\s+", "", equation) in blocks


@pytest.mark.parametrize(
    "arxiv_id,count", [("0811.2625v2", 2), ("2606.00587v2", 1), ("0905.2326v2", 103)]
)
def test_archived_ancillary_excerpts_preserve_source_date_version_and_complete_list(
    arxiv_id, count
):
    paths = []
    for filename, url in [
        ("abstract-excerpt.html", f"https://arxiv.org/abs/{arxiv_id}"),
        ("ancillary-excerpt.html", f"https://arxiv.org/src/{arxiv_id}/anc"),
    ]:
        path = golden_criteria_asset(f"10.48550/arxiv.{arxiv_id}", filename)
        sample_id = f"10.48550_arxiv.{arxiv_id}_{filename.removesuffix('.html')}"
        sample = golden_criteria_manifest()["samples"][sample_id]
        record = fixture_catalog()[sample["assets"][filename]]
        assert record.origin_kind == "real_excerpt"
        assert record.source_url == url
        assert sample["retrieved_at"] == "2026-09-08"
        assert sample["arxiv_id"] == arxiv_id
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sample["sha256"]
        soup = BeautifulSoup(path.read_text(), "lxml")
        links = [n["href"] for n in soup.select("a.anc-file-name")]
        assert len(links) == len(set(links)) == count
        assert all(link.startswith(f"/src/{arxiv_id}/anc/") for link in links)
        paths.append(links)
    assert paths[0] == paths[1]


@pytest.mark.parametrize("expected_count", [0, 22, 23])
def test_ieee_original_short_api_response_keeps_every_entry_without_second_request(
    expected_count,
):
    payload = golden_criteria_asset(IEEE, "references.json").read_bytes()

    class Transport:
        def __init__(self):
            self.urls = []

        def request(self, method, url, **kwargs):
            self.urls.append(url)
            return {"body": payload}

    transport = Transport()
    references = _ieee_metadata.fetch_ieee_reference_metadata(
        transport,
        "10459335",
        headers={},
        decode_body=lambda body: body.decode(),
        expected_count=expected_count,
    )
    originals = json.loads(payload)["references"]
    assert len(references) == len(originals) == 22
    assert transport.urls == [
        "https://ieeexplore.ieee.org/rest/document/10459335/references"
    ]
    for original, reference in zip(originals, references, strict=True):
        assert reference["label"] == original["order"]
        assert _words(reference["raw"]) == _words(
            BeautifulSoup(original["text"], "lxml").get_text(" ")
        )
        assert reference["title"] == original["title"]
    # Publisher display text is truncated; authoritative link has the final 3.
    assert references[0]["raw"].endswith("10.1049/iet-gtd.2015.146.")
    assert references[0]["doi"] == "10.1049/iet-gtd.2015.1463"


@pytest.mark.parametrize(
    "doi,selector,index,callout,target",
    [
        (
            ELSEVIER,
            'cross-ref[refid="bib0001"]',
            0,
            "ecosystem level (Beer et al., 2010; Anav et al., 2015)",
            "Spatiotemporal patterns of terrestrial gross primary production",
        ),
        (
            IEEE,
            'a[anchor="ref1"]',
            0,
            "ice flashovers in the worst conditions<sup>1</sup>",
            "DC flashover performance of ice-covered insulators",
        ),
        (
            ARXIV,
            'a[href="#bib.bib27"]',
            0,
            "PIQA (Bisk et al., 2020)",
            "PIQA: reasoning about physical commonsense",
        ),
        (
            TANDF,
            'a[data-rid="CIT0033"]',
            32,
            "Zhang, Odeh, and Han 2009; Karnieli et al. 2010; Firozjaei",
            "Use of NDVI and Land Surface Temperature for Drought Assessment",
        ),
    ],
)
def test_source_body_callout_maps_to_preserved_reference(
    doi, selector, index, callout, target
):
    soup, article, markdown = _review(doi)
    assert soup.select_one(selector) is not None
    assert _words(callout) in _words(
        re.sub(
            r"\$\$.*?\$\$|\$[^$\n]+\$",
            "",
            markdown.split("## References", 1)[0],
            flags=re.S,
        )
    )
    assert _words(target) in _words(article.references[index].raw)


def test_elsevier_ice_phenology_table_preserves_every_data_cell_and_column():
    soup, _, markdown = _review("10.1016/j.rse.2024.114346")
    table = soup.find("table", id="t0005")
    originals = [
        [
            _table_cell(c.get_text(" ", strip=True))
            for c in row.find_all("entry", recursive=False)
        ]
        for row in table.find("tbody").find_all("row")
    ]
    rows = [
        [_table_cell(c) for c in line.strip().strip("|").split("|")]
        for line in markdown.splitlines()
        if line.startswith("|")
    ]
    assert len(originals) == 4
    cursor = 0
    for row in originals:
        assert len(row) == 7
        cursor = rows.index(row, cursor) + 1
    assert rows[0] == [
        _table_cell(c)
        for c in [
            "Region",
            "Freeze-up date / Mean value (DOY)",
            "Freeze-up date / Trend (days per decade)",
            "Break-up date / Mean value (DOY)",
            "Break-up date / Trend (days per decade)",
            "Ice duration / Mean value (days)",
            "Ice duration / Trend (days per decade)",
        ]
    ]


def test_tandf_cited_work_dois_come_from_original_reference_controls():
    soup, article, _ = _review(TANDF)
    checked = 0
    for node, reference in zip(
        soup.select('li[id^="CIT"]'), article.references, strict=True
    ):
        target = node.select_one(".getFTR[data-target]")
        if target:
            assert reference.doi == target["data-target"].lower()
            checked += 1
    assert checked >= 50
    # First source record only supplies the current article's DOI in linkouts.
    assert article.references[0].doi is None
    assert all(r.doi != TANDF for r in article.references)


@pytest.mark.parametrize("limit", [0, 31, 51])
def test_ieee_constructed_overlapping_pages_of_real_entries_merge_at_boundary(limit):
    # Existing TBME JSON supplies 51 real entries in one saved payload. Splitting
    # and duplicating entry 30 here tests merging only, not real pagination.
    original = json.loads(
        golden_criteria_asset(
            "10.1109/TBME.2024.3434477", "references.json"
        ).read_text()
    )
    entries = original["references"]
    assert len(entries) == 51

    class Transport:
        def __init__(self):
            self.urls = []

        def request(self, method, url, **kwargs):
            self.urls.append(url)
            page = entries[:30] if len(self.urls) == 1 else entries[29:]
            assert len(self.urls) <= 2
            return {"body": json.dumps({"references": page}).encode()}

    transport = Transport()
    references = _ieee_metadata.fetch_ieee_reference_metadata(
        transport,
        str(original["articleNumber"]),
        headers={},
        decode_body=lambda body: body.decode(),
        expected_count=limit,
    )
    assert len(references) == (limit or 51)
    assert len(transport.urls) == 2
    assert transport.urls[-1].endswith("?start=30&rowsPerPage=30")
    assert [r["label"] for r in references] == [
        n["order"] for n in entries[: limit or 51]
    ]
    for node, ref in zip(entries, references, strict=False):
        assert _words(ref["raw"]) == _words(
            BeautifulSoup(node["text"], "lxml").get_text(" ")
        )
        assert ref["title"] == node["title"]
