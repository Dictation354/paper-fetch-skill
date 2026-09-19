"""P07: real sources through the legacy adapter without prefilled source titles."""

import hashlib
import json

from bs4 import BeautifulSoup
import pytest
import yaml

from tests.golden_corpus import build_article_from_fixture
from tests.golden_criteria import golden_criteria_sample
from tests.golden_criteria import source_selections
from tests.paths import REPO_ROOT
from tests.support.acquired_publisher_inputs import CapturedSourceFixture
from tests.support.reviewed_publisher_content import _words
from tests.support.verified_source_inputs import inspect_original


TITLES = {
    "10.1016/j.rse.2026.115369": "Sentinel-1 for offshore wind energy application",
    "10.1007/s10584-011-0143-4": "Hydrological response to climate change in a glacierized catchment in the Himalayas",
    "10.1038/nature12915": "A two-fold increase of carbon cycle sensitivity to tropical temperature variations",
}


@pytest.mark.parametrize("doi,expected_title", TITLES.items())
@pytest.mark.parametrize(
    "placeholder", [False, True], ids=["missing-title", "doi-title"]
)
def test_legacy_replay_json_yaml_h1_use_original_title(
    doi, expected_title, placeholder
):
    rows = source_selections()
    row = next(row for row in rows if row["doi"] == doi)
    body = (REPO_ROOT / row["source"]).read_bytes()
    assert hashlib.sha256(body).hexdigest() == row["source_sha256"]
    identity = inspect_original(body, row["provider"], doi, row["source_url"])
    assert identity and identity["identity"] == "matched"
    assert identity["title"] == expected_title
    sample = golden_criteria_sample(row["sample_id"])
    # Deliberately bypass build_verified_source_article's title injection.
    sample.pop("title", None)
    if placeholder:
        sample["title"] = doi
    sample.update(
        captured_source_path=row["source"],
        source_url=row["source_url"],
        landing_url=row["source_url"],
    )
    fixture = CapturedSourceFixture(row["sample_id"], sample)
    assert fixture.title == doi  # display fallback is not metadata evidence
    article = build_article_from_fixture(fixture)
    result = json.loads(article.to_json())
    markdown = article.to_ai_markdown(include_refs="all", asset_profile="all")
    _, frontmatter, content = markdown.split("---", 2)
    fields = yaml.safe_load(frontmatter)
    h1 = [line[2:] for line in content.splitlines() if line.startswith("# ")]
    assert result["metadata"]["title"] == fields["title"] == expected_title
    assert h1 == [expected_title]
    assert result["doi"] == fields["doi"] == doi
    assert article.quality.has_fulltext
    if doi == "10.1038/nature12915":
        # Reviewed source IDs establish eight body headings independently of
        # the output and of expected.json. The article H1 is not a ninth section.
        soup = BeautifulSoup(body.decode(), "lxml")
        source_headings = [
            soup.find(id=f"Sec{index}").get_text(" ", strip=True)
            for index in range(1, 9)
        ]
        expected_headings = [
            "Main",
            "Methods Summary",
            "Online Methods",
            "Atmospheric CO2 concentration",
            "Gridded climate fields",
            "Carbon fluxes and soil moisture from global ecosystem models",
            "Analyses",
            "Impacts of interannual CO2 variations on interannual temperature variations",
        ]
        assert list(map(_words, source_headings)) == list(
            map(_words, expected_headings)
        )
        body_headings = [s.heading for s in article.sections if s.kind == "body"]
        # Existing Springer normalization calls the source's Online Methods
        # section Methods; this repair does not change that convention.
        expected_headings[2] = "Methods"
        assert list(map(_words, body_headings)) == list(map(_words, expected_headings))
        assert len(article.sections) == 9  # eight body sections plus Abstract


def test_plos_scientific_identifier_survives_source_to_yaml_and_rendered_title():
    import xml.etree.ElementTree as ET
    from markdown_it import MarkdownIt
    from paper_fetch.models import article_from_markdown
    from paper_fetch.providers.plos import parse_plos_xml
    from tests.golden_criteria import golden_criteria_asset

    doi = "10.1371/journal.pone.0026949"
    raw = golden_criteria_asset(doi, "original.xml").read_bytes()
    source_title = ET.fromstring(raw).find(".//article-title")
    expected_title = "".join(source_title.itertext())
    assert "(HLA)-DRB1*01:01" in expected_title
    extraction = parse_plos_xml(
        raw,
        source_url=f"https://journals.plos.org/plosone/article/file?id={doi}&type=manuscript",
    )
    assert extraction.metadata["doi"] == doi
    article = article_from_markdown(
        source="plos_xml",
        metadata=extraction.metadata,
        doi=doi,
        markdown_text=extraction.markdown_text,
    )
    markdown = article.to_ai_markdown(max_tokens="full_text", include_refs="all")
    _, frontmatter, content = markdown.split("---", 2)
    fields = yaml.safe_load(frontmatter)
    title_html = BeautifulSoup(MarkdownIt().render(fields["title"]), "html.parser")
    body_html = BeautifulSoup(MarkdownIt().render(content), "html.parser")
    assert fields["doi"] == doi
    assert title_html.get_text().strip() == expected_title
    assert body_html.h1.get_text() == expected_title
    assert body_html.h1.find("em", string="-DRB1*01:01") is not None
