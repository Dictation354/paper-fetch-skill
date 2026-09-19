"""P06: independently registered bibliography/table identities from originals."""

from bs4 import BeautifulSoup
import pytest

from tests.golden_criteria import source_selections
from tests.paths import REPO_ROOT
from tests.support.object_content import assert_source_object_link
from tests.support.test_evidence import evidence_cache
from tests.support.verified_source_inputs import build_verified_source_article


# Reviewed source objects, not values inferred from renderer output.
OBJECTS = {
    "10.3390/math11030657": [
        (
            "B68-mathematics-11-00657",
            "B68-mathematics-11-00657",
            "Corporate governance and technological innovation: Comparison by industry.",
            "68",
        ),
        (
            "B69-mathematics-11-00657",
            "B69-mathematics-11-00657",
            "Industry classification guidelines for listed companies.",
            "69",
        ),
        (
            "table_body_display_mathematics-11-00657-t0A4",
            "mathematics-11-00657-t0A4",
            "Variables definition.",
            "Table A4",
        ),
    ],
    "10.1126/science.abp8622": [
        (
            "R43",
            "R43",
            "Materials and methods are available as supplementary materials.",
            "43",
        ),
    ],
    "10.1126/science.adp0212": [
        ("R49", "R49", "W. Zhang, Code for Paper", "49"),
    ],
}


@evidence_cache
def _source_article(doi):
    rows = source_selections()
    row = next(row for row in rows if row["doi"] == doi)
    soup = BeautifulSoup((REPO_ROOT / row["source"]).read_text(), "lxml")
    return doi, row["source_url"], soup, build_verified_source_article(row)


@pytest.fixture(params=list(OBJECTS))
def source_article(request):
    return _source_article(request.param)


@pytest.mark.parametrize("include_refs", ["all", "top10", "none"])
def test_five_retained_links_resolve_to_the_reviewed_source_object(
    source_article, include_refs
):
    doi, source_url, soup, article = source_article
    markdown = article.to_ai_markdown(include_refs=include_refs, asset_profile="all")
    for original_id, target_id, identity, label in OBJECTS[doi]:
        original = soup.find(id=original_id)
        target = soup.find(id=target_id)
        assert original is not None and target is not None
        assert identity in original.get_text(" ", strip=True)
        assert identity in target.get_text(" ", strip=True)
        calls = [
            a
            for a in soup.select(f'a[href="#{original_id}"]')
            if a.get_text(strip=True) == label
        ]
        assert calls, (doi, original_id, "missing source callout")
        if label == "Table A4":
            assert (
                original.select_one("table").select_one("th").get_text(strip=True)
                == "Variable"
            )
            assert target.select_one(f'a[href="#{original_id}"]') is not None
            assert "**Table A4.** Variables definition." in markdown
        else:
            reference = article.references[int(label) - 1]
            assert identity in reference.raw
            if original_id == "R49":
                assert "10.5281/zenodo.11531548" in reference.raw
            assert (reference.raw in markdown) == (include_refs == "all")
        rendered_label = f"*{label}*" if doi.startswith("10.1126/") else label
        link = f"[{rendered_label}]({source_url}#{target_id})"
        assert_source_object_link(
            soup,
            markdown,
            source_url=source_url,
            target_id=target_id,
            label=rendered_label,
        )
        other_target = "R1" if doi.startswith("10.1126/") else "B1-mathematics-11-00657"
        assert soup.find(id=other_target) is not None
        for damaged in (
            markdown.replace(link, f"[{rendered_label}]({source_url}#{other_target})"),
            markdown.replace(link, rendered_label),
            markdown.replace(link, f"[{rendered_label}]({source_url}#wrong-object)"),
            markdown.replace(link, f"[{rendered_label}](#missing)"),
        ):
            with pytest.raises(AssertionError):
                assert_source_object_link(
                    soup,
                    damaged,
                    source_url=source_url,
                    target_id=target_id,
                    label=rendered_label,
                )
        assert f"](#{original_id})" not in markdown


def test_filtered_mdpi_appendix_leaves_an_official_table_target():
    _, source_url, _, article = _source_article("10.3390/math11030657")
    # The public budget retains Table 3's note but excludes the appendix table.
    markdown = article.to_ai_markdown(include_refs="none", max_tokens=6000)
    assert "**Table A4.**" not in markdown
    assert f"[Table A4]({source_url}#mathematics-11-00657-t0A4)" in markdown
