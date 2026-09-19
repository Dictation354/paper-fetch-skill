"""Real asset entities and full source denominators after bounded acquisition."""

import hashlib
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup
import pymupdf
import pytest

from paper_fetch.models.markdown import iter_markdown_images
from tests.support.arxiv_graphic_replay import GRAPHIC_IDS
from tests.golden_criteria import golden_criteria_asset
from tests.support.canonical_content import source_prose_blocks
from tests.support.object_content import assert_object_position
from tests.support.asset_evidence_replay import (
    replay_arxiv_captured_graphics,
    replay_completed_signed_paper,
    replay_plos_captured_inline_formulas,
)

ARXIV_BODY_COUNTS = {
    "1406.2661v1": 10,
    "2006.11239v2": 23,
    "2605.06659v1": 1,
    "2605.06663v1": 13,
    "2605.06665v1": 9,
    "2605.06666v1": 6,
    "2605.06667v1": 16,
}
SIGNED_COUNTS = {
    "10.1021/acsomega.3c06992": 8,
    "10.1021/acsomega.4c03987": 10,
    "10.1063/5.0188905": 6,
    "10.1093/bioinformatics/btaa823": 9,
    "10.1098/rsif.2019.0334": 5,
    "10.1098/rsos.150470": 5,
    "10.1098/rsos.201188": 3,
    "10.1098/rsos.201200": 3,
    "10.1098/rspb.2020.0097": 2,
    "10.1098/rsta.2019.0558": 2,
}


def assert_actual_local_images(markdown, downloaded):
    images = list(iter_markdown_images(markdown))
    for asset in downloaded:
        path = Path(asset["path"])
        body = path.read_bytes()
        assert len(body) == asset["downloaded_bytes"] > 0
        assert sum(image.url == str(path) for image in images) == 1
        if path.suffix == ".svg":
            assert ET.fromstring(body).tag.rsplit("}", 1)[-1] == "svg"
        else:
            image = pymupdf.Pixmap(body)
            assert image.width > 0 and image.height > 0


@pytest.mark.parametrize("arxiv_id", GRAPHIC_IDS)
def test_p18_all_target_vectors_are_local_without_hiding_other_source_images(
    arxiv_id, tmp_path
):
    article, markdown, acceptance, downloaded, records, discovered = (
        replay_arxiv_captured_graphics(arxiv_id, tmp_path)
    )
    assert_actual_local_images(markdown, downloaded)
    assert len(downloaded) == len(GRAPHIC_IDS[arxiv_id])
    if records:
        assert {
            hashlib.sha256(Path(asset["path"]).read_bytes()).hexdigest()
            for asset in downloaded
        } == {r["sha256"] for r in records}
    assert article.quality.has_fulltext
    assert acceptance.asset.body_discovered == ARXIV_BODY_COUNTS[arxiv_id]
    assert acceptance.asset.body_local == len(downloaded)
    assert acceptance.asset.local_body_assets_satisfied == (
        len(downloaded) == ARXIV_BODY_COUNTS[arxiv_id]
    )
    assert len(discovered) >= len(downloaded)


@pytest.mark.parametrize("doi", SIGNED_COUNTS)
def test_p05_all_original_signed_objects_assemble_with_real_entities(doi, tmp_path):
    article, markdown, acceptance, downloaded, historical, _ = (
        replay_completed_signed_paper(doi, tmp_path)
    )
    assert_actual_local_images(markdown, downloaded)
    assert article.quality.has_fulltext
    assert len(downloaded) == len(historical["mappings"]) == SIGNED_COUNTS[doi]
    assert not any(mapping["old_url"] in markdown for mapping in historical["mappings"])
    assert acceptance.asset.body_discovered == SIGNED_COUNTS[doi]
    assert acceptance.asset.body_local == SIGNED_COUNTS[doi]
    assert acceptance.asset.local_body_assets_satisfied


@pytest.mark.parametrize(
    "doi,count",
    [("10.1371/journal.pbio.0040298", 1), ("10.1371/journal.pcbi.1003118", 7)],
)
def test_p19_real_inline_formula_pixels_assemble_with_full_source_asset_denominator(
    doi, count, tmp_path
):
    article, markdown, acceptance, downloaded, records, discovered = (
        replay_plos_captured_inline_formulas(doi, tmp_path)
    )
    assert_actual_local_images(markdown, downloaded)
    assert len(downloaded) == len(records) == count
    assert all(asset["kind"] == "formula" for asset in downloaded)
    source_file = (
        "acquisition/source-completion-2026-09-18/001-http_response_entity.xml"
        if "pbio" in doi
        else "original.xml"
    )
    soup = BeautifulSoup(golden_criteria_asset(doi, source_file).read_bytes(), "xml")
    runs = [
        run
        for _, group in source_prose_blocks(
            SimpleNamespace(provider="plos", doi=doi), soup
        )
        for run in group
    ]
    previous = -1
    for graphic in soup.select("body inline-formula > inline-graphic"):
        source_id = graphic["xlink:href"].removeprefix("info:doi/")
        record = next(
            r
            for r in records
            if parse_qs(urlsplit(r["requested_url"]).query)["id"] == [source_id]
        )
        asset = next(
            a for a in downloaded if a["download_url"] == record["requested_url"]
        )
        assert (
            hashlib.sha256(Path(asset["path"]).read_bytes()).hexdigest()
            == record["sha256"]
        )
        image = next(
            i for i in iter_markdown_images(markdown) if i.url == asset["path"]
        )
        assert image.start > previous
        assert assert_object_position(
            graphic.parent, markdown, image.start, image.end, runs
        )
        previous = image.start
    assert acceptance.asset.body_local == count
    # Independent original full-article candidates, including other formulas
    # and figures, remain in the audit rather than only the selected downloads.
    assert acceptance.asset.body_discovered == len(
        [
            a
            for a in discovered
            if a.get("kind") in {"formula", "figure", "table"}
            and a.get("section") != "supplementary"
        ]
    )
    assert article.quality.semantic_losses.formula_missing_count == 0
    assert {
        hashlib.sha256(Path(asset["path"]).read_bytes()).hexdigest()
        for asset in downloaded
    } == {r["sha256"] for r in records}
