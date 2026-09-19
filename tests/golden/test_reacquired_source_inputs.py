"""P12 replacements: original response identity and current HTML/XML assembly."""

import html
import re
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup
import pytest

from tests.golden_criteria import golden_criteria_sample_for_doi
from tests.golden_corpus import build_article_from_fixture
from tests.support.acquired_publisher_inputs import CapturedSourceFixture, _record
from tests.support.reviewed_publisher_content import _words
from tests.golden_criteria import golden_criteria_asset


CASES = [
    (
        "10.1007/s13158-025-00473-x",
        "springer",
        "Stagnated Development of Home Language Vocabulary",
        "000-http_response_entity.html",
    ),
    (
        "10.1038/d41586-022-01795-9",
        "springer",
        "After COVID, African countries",
        "000-http_response_entity.html",
    ),
    (
        "10.1038/d41586-023-01829-w",
        "springer",
        "How to make the workplace fairer",
        "000-http_response_entity.html",
    ),
    (
        "10.1038/s41561-022-00983-6",
        "springer",
        "Ozone depletion over the Arctic",
        "000-http_response_entity.html",
    ),
    (
        "10.1111/cas.16117",
        "wiley",
        "Cell cycle heterogeneity and plasticity",
        "000-browser_rendered_dom.html",
    ),
    (
        "10.1111/gcb.16386",
        "wiley",
        "Cerrado deforestation threatens regional climate",
        "000-browser_rendered_dom.html",
    ),
]


@pytest.mark.parametrize("doi,provider,title,filename", CASES)
def test_reacquired_article_uses_captured_identity_and_body(
    doi, provider, title, filename
):
    path = "acquisition/provenance-repair-2026-09-17/" + filename
    record, body = _record(doi, path)
    sample = golden_criteria_sample_for_doi(doi)
    soup = BeautifulSoup(body, "lxml")
    # Do not establish identity from a target DOI injected into the model.
    declared = soup.select_one('meta[name="citation_doi"], meta[name="DOI"]')
    assert declared is not None and declared["content"].casefold() == doi.casefold()
    title_meta = soup.select_one(
        'meta[name="citation_title"], meta[property="og:title"]'
    )
    assert title_meta is not None and title in title_meta["content"]
    sample.update(
        captured_source_path=sample["assets"][path],
        source_url=record["final_url"],
        landing_url=record["final_url"],
        route_kind="html",
        title=title_meta["content"],
    )
    article = build_article_from_fixture(
        CapturedSourceFixture(sample["sample_id"], sample)
    )
    assert article.doi.casefold() == doi.casefold()
    assert article.metadata.title == title_meta["content"]
    assert article.quality.has_fulltext
    rendered = article.to_ai_markdown(include_refs="all", max_tokens="full_text")
    assert rendered and "[Formula unavailable]" not in rendered
    # Real HTTP403 Wiley DOM is retained with its actual status, not relabelled 200.
    if doi == "10.1111/cas.16117":
        assert record["status_code"] == 403
        assert "LGR5" in rendered and "CARCINOGENESIS" in rendered


@pytest.mark.parametrize(
    "doi,path,title,node_count,empty_labels",
    [
        (
            "10.1126/science.abo2812",
            "acquisition/template-browser-repeat4-2026-09-16/003-1-http_response_entity.html",
            "Satellites reveal widespread decline",
            100,
            [],
        ),
        (
            "10.1073/pnas.2406303121",
            "acquisition/provenance-camoufox-retry-2026-09-17/000-browser_rendered_dom.html",
            "The kinetics of SARS-CoV-2 infection",
            78,
            [],
        ),
        (
            "10.1073/pnas.2317456120",
            "acquisition/provenance-continued-2026-09-17/000-browser_rendered_dom.html",
            "Amazon deforestation implications",
            22,
            ["22"],
        ),
    ],
)
def test_science_pnas_captured_full_article_preserves_bibliography(
    doi, path, title, node_count, empty_labels
):
    record, body = _record(doi, path)
    soup = BeautifulSoup(body, "lxml")
    assert (
        soup.select_one('meta[name="citation_doi"], meta[name="publication_doi"]')[
            "content"
        ]
        == doi
    )
    assert soup.select_one("#bodymatter") is not None
    sample = golden_criteria_sample_for_doi(doi)
    sample.update(
        captured_source_path=sample["assets"][path],
        source_url=record["final_url"],
        route_kind="html",
    )
    article = build_article_from_fixture(
        CapturedSourceFixture(sample["sample_id"], sample)
    )
    assert article.quality.has_fulltext
    assert title in article.metadata.title
    assert article.metadata.authors
    originals = soup.select("#bibliography .biblioentry")
    assert len(originals) == node_count
    empty = [node for node in originals if not node.select_one(".citation-content")]
    assert [
        node.select_one(".label").get_text(strip=True) for node in empty
    ] == empty_labels
    for node in empty:
        # The captured commentary's r22 contains no citation or DOI to recover.
        citations = node.select_one(".citations")
        assert str(citations) == '<div class="citations" id="r22"></div>'
    if empty_labels:
        assert golden_criteria_asset(doi, "commentary.html").read_bytes() == body
    nonempty = [node for node in originals if node not in empty]
    assert len(article.references) == node_count - len(empty_labels)
    rendered = article.to_ai_markdown(include_refs="all", max_tokens="full_text")
    rendered_references = _words(html.unescape(rendered.split("## References", 1)[1]))
    cursor = 0
    for node, reference in zip(nonempty, article.references, strict=True):
        label = node.select_one(".label").get_text(strip=True)
        text = node.select_one(".citation-content").get_text(" ", strip=True)
        # Whitespace around inline elements is insignificant; every other source
        # character, including punctuation and case, must survive in raw text.
        assert reference.raw.startswith(f"{label}. ")
        citation = reference.raw.removeprefix(f"{label}. ")
        assert re.sub(r"\s+", "", citation) == re.sub(r"\s+", "", text), label
        doi_links = [
            unquote(urlsplit(anchor["href"]).path.lstrip("/")).lower()
            for anchor in node.select("a[href]")
            if urlsplit(anchor["href"]).hostname in {"doi.org", "dx.doi.org"}
        ]
        assert reference.doi == (doi_links[0] if doi_links else None), label
        expected = _words(text)
        cursor = rendered_references.index(expected, cursor) + len(expected)
