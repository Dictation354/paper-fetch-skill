"""Minimal source metadata contracts for the canonical replay adapter."""

import pytest

from paper_fetch.extraction.html._metadata import parse_html_metadata
from paper_fetch.models import metadata_only_article
from paper_fetch.providers.elsevier import extract_elsevier_xml_identity
from tests.golden_corpus import (
    GoldenCorpusFixture,
    _base_metadata,
    _build_elsevier_article,
    _build_springer_article,
    _merge_replay_source_metadata,
)
from tests.support.acquired_publisher_inputs import CapturedSourceFixture


DOI = "10.1234/example"


def _fixture(title):
    return GoldenCorpusFixture("example", {"doi": DOI, "title": title})


@pytest.mark.parametrize(
    "title", [None, "", "  ", DOI, "https://doi.org/10.1234/EXAMPLE"]
)
@pytest.mark.parametrize("format", ["html", "xml"])
def test_missing_and_doi_placeholder_titles_allow_source_metadata(title, format):
    base = _base_metadata(_fixture(title))
    assert "title" not in base
    if format == "html":
        source = parse_html_metadata(
            f'<meta name="citation_doi" content="{DOI}">'
            '<meta name="citation_title" content="Observed source title">',
            "https://example.org/article",
        )
    else:
        source = extract_elsevier_xml_identity(
            f"<root><coredata><doi>{DOI}</doi><title>Observed source title</title></coredata></root>".encode()
        )["identity_evidence"]
    merged = _merge_replay_source_metadata(base, dict(source))
    assert merged["title"] == "Observed source title"
    assert merged["doi"] == DOI
    assert "title" not in base


def test_real_fixture_title_keeps_existing_base_first_merge_priority():
    base = _base_metadata(_fixture("Curated bibliographic title"))
    merged = _merge_replay_source_metadata(
        base, {"doi": DOI, "title": "Source title variant"}
    )
    assert merged["title"] == "Curated bibliographic title"
    assert merged["doi"] == DOI


def test_pdf_replay_metadata_stays_outside_html_xml_title_repair():
    fixture = GoldenCorpusFixture("example", {"doi": DOI, "route_kind": "pdf_fallback"})
    assert _base_metadata(fixture)["title"] == DOI


@pytest.mark.parametrize("source", [{}, {"doi": DOI}, {"doi": DOI, "title": ""}])
def test_no_source_title_remains_missing_instead_of_becoming_doi(source):
    metadata = _merge_replay_source_metadata(_base_metadata(_fixture(None)), source)
    assert metadata.get("title") is None
    article = metadata_only_article(source="springer_html", metadata=metadata, doi=DOI)
    assert article.to_dict()["metadata"]["title"] is None
    markdown = article.to_ai_markdown()
    assert "\ntitle:" not in markdown
    assert "# Untitled Article" in markdown
    assert f"# {DOI}" not in markdown
    assert article.doi == DOI


@pytest.mark.parametrize("provider", ["elsevier", "springer"])
def test_replay_rejects_other_article_source_before_content_conversion(
    tmp_path, provider
):
    body = (
        "<root><coredata><doi>10.1234/other</doi><title>Other article</title></coredata></root>"
        if provider == "elsevier"
        else '<meta name="citation_doi" content="10.1234/other">'
        '<meta name="citation_title" content="Other article">'
    )
    path = tmp_path / ("source.xml" if provider == "elsevier" else "source.html")
    path.write_text(body)
    fixture = CapturedSourceFixture(
        "example",
        {"doi": DOI, "publisher": provider, "captured_source_path": str(path)},
    )
    builder = (
        _build_elsevier_article if provider == "elsevier" else _build_springer_article
    )
    with pytest.raises(ValueError, match="response DOI does not match"):
        builder(fixture)
