"""Real author structures: natural fallback and coexisting sources stay distinct."""

import pytest
from bs4 import BeautifulSoup

from paper_fetch.providers import (
    _arxiv_authors,
    _pnas_html,
    _science_html,
    _springer_authors,
    _wiley_html,
)
from tests.golden_criteria import golden_criteria_asset

SPRINGER_AUTHORS = [
    "Felipe Bastida",
    "Carlos García",
    "Noah Fierer",
    "David J. Eldridge",
    "Matthew A. Bowker",
    "Sebastián Abades",
    "Fernando D. Alfaro",
    "Asmeret Asefaw Berhe",
    "Nick A. Cutler",
    "Antonio Gallardo",
    "Laura García-Velázquez",
    "Stephen C. Hart",
    "Patrick E. Hayes",
    "Teresa Hernández",
    "Zeng-Yei Hseu",
    "Nico Jehmlich",
    "Martin Kirchmair",
    "Hans Lambers",
    "Sigrid Neuhauser",
    "Víctor M. Peña-Ramírez",
    "Cecilia A. Pérez",
    "Sasha C. Reed",
    "Fernanda Santos",
    "Christina Siebe",
    "Benjamin W. Sullivan",
    "Pankaj Trivedi",
    "Alfonso Vera",
    "Mark A. Williams",
    "José Luis Moreno",
    "Manuel Delgado-Baquerizo",
]


@pytest.mark.parametrize(
    "doi,expected",
    [
        ("10.48550/arxiv.2605.06556v1", ["Tyler C. Wunder", "Joseph W. Cutrone"]),
        ("10.48550/arxiv.2605.06653v1", ["Xingyang Yu"]),
    ],
)
def test_original_arxiv_naturally_uses_person_name_fallback(doi, expected):
    html = golden_criteria_asset(doi, "original.html").read_text()
    soup = BeautifulSoup(html, "lxml")
    assert len(soup.select("article .ltx_creator.ltx_role_author")) == 1
    assert _arxiv_authors._extract_arxiv_creator_authors(html) == []
    assert _arxiv_authors._extract_arxiv_person_authors(html) == expected
    assert _arxiv_authors._AUTHOR_PIPELINE(html) == expected


@pytest.mark.parametrize(
    "doi,asset,module,primary,secondary,expected",
    [
        (
            "10.1029/2004GB002273",
            "original.html",
            _wiley_html,
            "meta",
            ("dom",),
            ["N. Zeng", "A. Mariotti", "P. Wetzel"],
        ),
        (
            "10.1038/s41467-019-11472-7",
            "acquisition/requested-templates-2026-09-16/article-response.html",
            _springer_authors,
            "meta",
            ("jsonld", "dom"),
            SPRINGER_AUTHORS,
        ),
        (
            "10.1126/sciadv.abf8021",
            "original.html",
            _science_html,
            "datalayer",
            ("dom",),
            [
                "Wenxia Zhang",
                "Kalli Furtado",
                "Peili Wu",
                "Tianjun Zhou",
                "Robin Chadwick",
                "Charline Marzin",
                "John Rostron",
                "David Sexton",
            ],
        ),
        (
            "10.1073/pnas.2309123120",
            "original.html",
            _pnas_html,
            "dom",
            ("meta",),
            [
                "Edward W. Butt",
                "Jessica C. A. Baker",
                "Francisco G. Silva Bezerra",
                "Celso von Randow",
                "Ana P. D. Aguiar",
                "Dominick V. Spracklen",
            ],
        ),
    ],
)
def test_original_coexisting_author_sources_preserve_names(
    doi, asset, module, primary, secondary, expected
):
    html = golden_criteria_asset(doi, asset).read_text()
    extractors = {step.name: step.extractor for step in module._AUTHOR_PIPELINE.steps}
    assert extractors[primary](html) == expected
    for name in secondary:
        assert extractors[name](html) == expected
    # Nothing is removed from the original: presence does not prove natural fallback.
    assert module._AUTHOR_PIPELINE(html) == expected


def test_original_springer_table_page_uses_jsonld_without_author_meta():
    html = golden_criteria_asset(
        "10.1038/nature13376",
        "acquisition/template-gaps-2026-09-16/table1-response.html",
    ).read_text()
    soup = BeautifulSoup(html, "lxml")
    assert not soup.select('meta[name="citation_author"]')
    assert "Table 1" in soup.title.get_text()
    expected = [
        "Benjamin Poulter",
        "David Frank",
        "Philippe Ciais",
        "Ranga B. Myneni",
        "Niels Andela",
        "Jian Bi",
        "Gregoire Broquet",
        "Josep G. Canadell",
        "Frederic Chevallier",
        "Yi Y. Liu",
        "Steven W. Running",
        "Stephen Sitch",
        "Guido R. van der Werf",
    ]
    assert _springer_authors._extract_meta_authors(html) == []
    assert _springer_authors._extract_jsonld_authors(html) == expected
    assert _springer_authors.extract_authors(html) == expected
