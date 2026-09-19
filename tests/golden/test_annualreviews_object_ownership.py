"""P08/P26 source-object identities, occurrence counts, content and positions."""

from collections import Counter
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import pytest

from paper_fetch.models.markdown import iter_markdown_images
from tests.golden_criteria import golden_criteria_sample_for_doi
from tests.golden_criteria import source_selections
from tests.paths import REPO_ROOT
from tests.support.canonical_content import source_prose_blocks
from tests.support.object_content import (
    assert_object_position,
    assert_source_tables,
    assert_image_occurrences,
)
from tests.support.reviewed_publisher_content import _words
from tests.support.test_evidence import evidence_cache
from tests.support.verified_source_inputs import (
    build_verified_source_article,
    inspect_original,
)
from types import SimpleNamespace


CONTROL = "10.1146/annurev-control-090419-075625"
CASES = {
    "10.1146/annurev-control-030123-013355": (
        ["t1", "t2", "t3"],
        "Terms And Definitions",
    ),
    CONTROL: (["t1"], None),
    "10.1146/annurev-environ-102511-084654": ([], "Terms And Definitions"),
    "10.1146/annurev-med-120811-171056": (["t1"], "Terms And Definitions"),
    "10.1146/annurev-neuro-062111-150343": ([], "Footnotes"),
}


@evidence_cache
def _source(doi):
    rows = source_selections()
    row = next((r for r in rows if r["doi"] == doi), None)
    if row is None:
        sample = golden_criteria_sample_for_doi(doi)
        row = dict(
            doi=doi,
            provider="annualreviews",
            format="html",
            sample_id=sample["sample_id"],
            source_url=sample["source_url"],
            source="tests/fixtures/golden_criteria/10.1146_annurev-neuro-062111-150343/acquisition/assets-2026-09-15/annualreviews-headed-all-001-browser_dom.html",
        )
    raw = (REPO_ROOT / row["source"]).read_bytes()
    identity = inspect_original(raw, "annualreviews", doi, row["source_url"])
    assert identity and identity["identity"] == "matched"
    article = build_verified_source_article({**row, "identity": identity})
    soup = BeautifulSoup(raw.decode(), "lxml")
    from tests.support.canonical_content import (
        bind_table_expectations,
        source_object_expectations,
    )

    tables = soup.select("#itemFullTextId table")
    if tables and CASES[doi][0]:
        bind_table_expectations(
            tables, source_object_expectations(doi, REPO_ROOT / row["source"])["tables"]
        )
    markdown = article.to_ai_markdown(include_refs="all", asset_profile="all")
    fixture = SimpleNamespace(provider="annualreviews", doi=doi)
    runs = [run for _, group in source_prose_blocks(fixture, soup) for run in group]
    return soup, article, markdown, row["source_url"], runs


def test_control_figure_and_all_formula_objects_render_once_in_source_positions():
    soup, article, markdown, source_url, runs = _source(CONTROL)
    body = soup.select_one("#itemFullTextId")
    formulas = body.select('img[src*="/eq-075625-"]')
    expected = [urljoin(source_url, n["src"]) for n in formulas]
    assert len(expected) == len(set(expected)) == 128
    images = list(iter_markdown_images(markdown))
    actual = [i for i in images if "/eq-075625-" in i.url]
    assert_image_occurrences(markdown, expected)
    for original, rendered in zip(formulas, actual, strict=True):
        checked = assert_object_position(
            original, markdown, rendered.start, rendered.end, runs
        )
        assert checked, ("formula lacks a retained prose boundary", original["src"])
    figures = body.select(".figure[id]")
    expected_figures = [
        urljoin(source_url, f.select_one(".image a.media-link")["href"])
        for f in figures
    ]
    actual_figures = [i for i in images if i.url in set(expected_figures)]
    assert_image_occurrences(markdown, expected_figures)
    assert Counter(i.url for i in actual_figures) == Counter(expected_figures)
    for original, rendered in zip(figures, actual_figures, strict=True):
        assert assert_object_position(
            original, markdown, rendered.start, rendered.end, runs
        )
    for image in [*actual_figures, *actual[-4:]]:
        for damaged in (
            markdown[: image.start] + markdown[image.end :],
            markdown + "\n" + image.text,
        ):
            with pytest.raises(AssertionError):
                assert_image_occurrences(
                    damaged, expected_figures if image in actual_figures else expected
                )
    figure = body.select_one("#f3")
    caption = figure.select_one(".caption")
    caption_formulas = [urljoin(source_url, n["src"]) for n in caption.select("img")]
    assert [u.rsplit("-", 1)[-1] for u in caption_formulas] == [
        "124.gif",
        "125.gif",
        "126.gif",
        "127.gif",
    ]
    rendered_caption = next(
        line for line in markdown.splitlines() if line.startswith("**Figure 3.**")
    )
    figure3_image = actual_figures[2]
    caption_end = markdown.index(rendered_caption) + len(rendered_caption)
    duplicated_block = markdown + "\n" + markdown[figure3_image.start : caption_end]
    with pytest.raises(AssertionError):
        assert_image_occurrences(duplicated_block, expected_figures)
    with pytest.raises(AssertionError):
        assert_image_occurrences(duplicated_block, expected)
    assert [i.url for i in iter_markdown_images(rendered_caption)] == caption_formulas
    assert _words(caption.get_text(" ", strip=True)) in _words(
        re.sub(r"!\[[^\]]*\]\([^)]+\)", "", rendered_caption)
    )
    originals = body.select("li.refbody")
    assert len(originals) == len(article.references) == 138
    cursor = markdown.index("## References")
    for index, (original, reference) in enumerate(
        zip(originals, article.references, strict=True), 1
    ):
        clone = BeautifulSoup(str(original), "lxml")
        for node in clone.select(
            ".citation-label, .js-references, a.externallink, a.js-externallink"
        ):
            node.decompose()
        assert _words(clone.get_text(" ", strip=True)) == _words(
            re.sub(r"^\d+\.\s*", "", reference.raw)
        )
        assert reference.raw.startswith(f"{index}.")
        cursor = markdown.index(reference.raw, cursor) + len(reference.raw)


@pytest.mark.parametrize("doi", CASES)
def test_nine_reviewed_table_and_backmatter_headings_keep_content_and_position(doi):
    soup, article, markdown, _, runs = _source(doi)
    table_ids, back_heading = CASES[doi]
    for table_id in table_ids:
        original = soup.select_one(
            f"#itemFullTextId #{table_id}.table-caption-container"
        )
        label = original.select_one(".table-label").get_text(" ", strip=True)
        assert label == f"Table {table_id[1:]}"
        marker = f"**{label}**"
        assert markdown.count(marker) == 1
        assert not re.search(rf"(?m)^#+ {re.escape(label)}\s*$", markdown)
        assert not any(s.heading == label for s in article.sections)
        start = markdown.index(marker)
        table = original.find_next("table")
        # Bound the table to its next retained prose, avoiding another table.
        end = markdown.find("\n\n", markdown.index("\n|", start))
        assert end > start
        scope = markdown[start:end]
        caption = original.find("p").get_text(" ", strip=True)
        assert _words(caption) in _words(scope)
        assert_source_tables([table], markdown[start:], provider="annualreviews")
        assert_object_position(original, markdown, start, end, runs)
    if back_heading:
        popup_id = (
            "viewFootnotePopup" if back_heading == "Footnotes" else "viewGlossaryPopup"
        )
        popup = soup.select_one(f"#itemFullTextId #{popup_id}")
        assert (
            popup.select_one(".modal-title").get_text(strip=True).title()
            == back_heading
        )
        marker = f"## {back_heading}\n"
        assert markdown.count(marker) == 1
        section = next(s for s in article.sections if s.heading == back_heading)
        assert section.level == 2
        start = markdown.index(marker)
        end_match = re.search(r"(?m)^## ", markdown[start + len(marker) :])
        end = start + len(marker) + end_match.start() if end_match else len(markdown)
        region = _words(markdown[start:end])
        cursor = 0
        items = popup.select(".glossary-item, .modal-body > div[id]")
        assert items
        for item in items:
            text = _words(item.get_text(" ", strip=True))
            cursor = region.index(text, cursor) + len(text)
        assert_object_position(popup, markdown, start, end, runs)
