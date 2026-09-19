"""P19/P22 source-object identity and position regressions."""

from types import SimpleNamespace

from bs4 import BeautifulSoup
import pytest

from paper_fetch.models.markdown import iter_markdown_images
from tests.golden_criteria import golden_criteria_sample_for_doi
from tests.golden_criteria import source_selections
from tests.paths import REPO_ROOT
from tests.support.canonical_content import source_prose_blocks
from tests.support.object_content import assert_object_position
from tests.support.test_evidence import evidence_cache
from tests.support.verified_source_inputs import (
    build_verified_source_article,
    inspect_original,
)


@evidence_cache
def _source(doi, provider):
    rows = source_selections()
    row = next((r for r in rows if r["doi"] == doi), None)
    if row is None:
        sample = golden_criteria_sample_for_doi(doi)
        row = dict(
            doi=doi,
            provider=provider,
            format="xml",
            sample_id=sample["sample_id"],
            source_url=sample["source_url"],
            source=f"tests/fixtures/golden_criteria/{doi.replace('/', '_', 1)}/original.xml",
        )
    raw = (REPO_ROOT / row["source"]).read_bytes()
    identity = inspect_original(raw, provider, doi, row["source_url"])
    assert identity and identity["identity"] == "matched"
    return BeautifulSoup(raw, "xml"), build_verified_source_article(
        {**row, "identity": identity}
    )


@pytest.mark.parametrize(
    "doi,journal,count",
    [
        ("10.1371/journal.pbio.0040298", "plosbiology", 1),
        ("10.1371/journal.pcbi.1003118", "ploscompbiol", 7),
    ],
)
def test_plos_eight_inline_graphics_keep_original_identity_and_position(
    doi, journal, count
):
    soup, article = _source(doi, "plos")
    formulas = soup.select("body inline-formula > inline-graphic")
    assert len(formulas) == count
    expected = []
    for graphic in formulas:
        href = graphic["xlink:href"]
        assert href.startswith(f"info:doi/{doi}.e")
        expected.append(
            f"https://journals.plos.org/{journal}/article/file?id={href.removeprefix('info:doi/')}&type=thumbnail"
        )
    markdown = article.to_ai_markdown(include_refs="all", asset_profile="all")
    images = [i for i in iter_markdown_images(markdown) if i.url in set(expected)]
    assert [i.url for i in images] == expected
    runs = [
        run
        for _, group in source_prose_blocks(
            SimpleNamespace(provider="plos", doi=doi), soup
        )
        for run in group
    ]
    for original, image in zip(formulas, images, strict=True):
        assert assert_object_position(
            original.parent, markdown, image.start, image.end, runs
        )
    assert set(expected) <= {
        a.url or a.original_url for a in article.assets if a.kind == "formula"
    }
    assert article.quality.semantic_losses.formula_missing_count == 0
    graphic_formulas = soup.select(
        "body inline-formula > inline-graphic, body disp-formula > graphic"
    )
    assert article.quality.semantic_losses.formula_fallback_count == len(
        graphic_formulas
    )
    assert "[Formula unavailable]" not in markdown


def test_copernicus_all_83_empty_xrefs_keep_their_101_bibliography_targets():
    import re

    doi = "10.5194/hess-28-1-2024"
    soup, article = _source(doi, "copernicus")
    nodes = soup.select('body xref[ref-type="bibr"]')
    empty = [n for n in nodes if not n.get_text(strip=True)]
    assert len(nodes) == 90 and len(empty) == 83
    refs = {r["id"]: r for r in soup.select("ref[id]")}
    assert sum(len(n["rid"].split()) for n in empty) == 101
    source = "https://hess.copernicus.org/articles/28/1/2024/hess-28-1-2024.xml"
    runs = [
        run
        for _, group in source_prose_blocks(
            SimpleNamespace(provider="copernicus", doi=doi), soup
        )
        for run in group
    ]
    expected = []
    for node in empty:
        links = []
        for rid in node["rid"].split():
            reference = refs[rid]
            label = " ".join(reference.label.get_text().split())
            assert ")" in label
            short = label.split(")", 1)[0] + ")"
            author, year = short.rsplit("(", 1)
            links.append(f"[{author.rstrip()} ({year}]({source}#{rid})")
        expected.append("; ".join(links))
    for mode in ("all", "partial", "none"):
        markdown = article.to_ai_markdown(include_refs=mode, asset_profile="all")
        cursor = 0
        for node, rendered in zip(empty, expected, strict=True):
            start = markdown.index(rendered, cursor)
            end = start + len(rendered)
            assert assert_object_position(node, markdown, start, end, runs), node["id"]
            cursor = end
        for node in nodes:
            if node.get_text(strip=True):
                assert " ".join(node.get_text().split()) in " ".join(markdown.split())
        assert "using the method of [Hargreaves and Samani (1982)]" in markdown
        assert "[Reference unavailable" not in markdown
        # Every restored target remains linked to the official source even when refs are filtered.
        all_empty = [
            n
            for n in soup.select('xref[ref-type="bibr"]')
            if not n.get_text(strip=True)
        ]
        outside_body = [n for n in all_empty if n.find_parent("body") is None]
        assert len(outside_body) == 1 and outside_body[0]["id"] == "paren.91"
        assert outside_body[0]["rid"] == "bib1.bibx76"
        assert "data compiled herein" in outside_body[0].parent.get_text()
        targets = [rid for n in all_empty for rid in n["rid"].split()]
        assert len(targets) == 102
        assert (
            re.findall(re.escape(source) + r"#(bib1\.bibx\d+)\)", markdown) == targets
        )
