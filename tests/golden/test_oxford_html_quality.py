"""Replay the captured warming article and existing Oxford HTML samples."""

from tests.support.markdown_presentation import visible_markdown

import hashlib
import json
import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
import pytest

from paper_fetch.providers import _oxfordacademic_html
from paper_fetch.providers.oxfordacademic import OxfordAcademicClient
from paper_fetch.extraction.image_payloads import image_dimensions_from_bytes
from paper_fetch.quality.assets import build_asset_quality_summary
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi
from tests.paths import FIXTURE_DIR
from tests.support.oxford_html import (
    build_oxford_html_article,
    build_oxford_html_payload,
)
from tests.support._paper_fetch_support import FixtureHtmlTransport, http_response
from tests.support.verified_source_inputs import inspect_original


def test_nwae442_source_and_final_markdown_contract():
    folder = FIXTURE_DIR / "golden_criteria/_scenarios/oxford_nwae442"
    source = json.loads((folder / "source.json").read_text())
    body = (folder / source["file"]).read_bytes()
    assert hashlib.sha256(body).hexdigest() == source["sha256"]
    assert len(body) == source["size"]
    assert (
        inspect_original(body, source["provider"], source["doi"], source["source_url"])[
            "identity"
        ]
        == "matched"
    )
    html = body.decode()
    soup = BeautifulSoup(html, "lxml")
    article = build_oxford_html_article(html, source["source_url"], source["doi"])
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="all", max_tokens="full_text"
    )
    assert article.quality.has_fulltext
    assert article.doi == source["doi"]
    assert "CO<sub>2</sub>-increasing scenario" in markdown
    for noise in (
        "Split View",
        "Select Format",
        "OpenURL Placeholder",
        "Share Icon",
        "PDF\n",
        "citationLinks",
        "<!--",
    ):
        assert noise not in markdown
    captions = re.findall(r"(?m)^\*\*Figure (\d)\.\*\* (.+)$", markdown)
    assert [number for number, _ in captions] == [str(i) for i in range(1, 7)]
    assert len(soup.select(".fig-section")) == 6
    assert len(article.assets) == markdown.count("![") == 6
    assert not re.search(r"(?m)^- Figure \d", markdown)
    for _, caption in captions:
        assert markdown.count(caption) == 1
    assert re.search(
        r"\[nwae442\\_Supplemental\\_File\]\(https://oup\.silverchair-cdn\.com/[^\n]+\.docx\?",
        markdown,
    )
    assert "Equally contributed to this work." in markdown
    assert not re.search(r"[^\n]+: Equally contributed to this work\.", markdown)
    references = article.references
    source_references = soup.select(".ref-list .ref")
    assert len(references) == len(source_references) == 50
    for index, (reference, node) in enumerate(
        zip(references, source_references, strict=True), 1
    ):
        assert reference.raw.startswith(f"{index}.")
        title = node.select_one(".article-title")
        if title:
            assert re.sub(r"\s+", "", title.get_text()) in re.sub(
                r"\s+", "", reference.raw
            )
    assert references[20].raw.count("10.1029/2023GL105796") == 1
    assert "10. 1029" not in references[20].raw
    assert "\\mathop" in markdown
    assert "\\begin{equation}" in markdown
    assert "|$" not in markdown and "$|" not in markdown
    assert len(re.findall(r"(?m)^\$\$$", markdown)) == 8


def test_nwae442_downloads_six_originals_once_inline(tmp_path, record_property):
    folder = FIXTURE_DIR / "golden_criteria/_scenarios/oxford_nwae442"
    source = json.loads((folder / "source.json").read_text())
    captures = json.loads((folder / "acquisition/provenance.json").read_text())[
        "records"
    ]
    payload = build_oxford_html_payload(
        (folder / source["file"]).read_text(),
        source["source_url"],
        source["doi"],
        asset_profile="body",
    )
    figures = payload.content.extracted_assets
    assert len(figures) == len(captures) == 6
    responses = {}
    for asset, capture in zip(figures, captures, strict=True):
        body = (folder / capture["body_file"]).read_bytes()
        assert len(body) == capture["size"]
        assert hashlib.sha256(body).hexdigest() == capture["sha256"]
        assert image_dimensions_from_bytes(body) == (
            capture["width"],
            capture["height"],
        )
        assert asset["full_size_url"] == capture["requested_url"]
        assert asset["preview_url"] != capture["requested_url"]
        responses[capture["requested_url"]] = http_response(
            capture["requested_url"], body, "image/jpeg"
        )
    transport = FixtureHtmlTransport(responses)
    client = OxfordAcademicClient(transport, {})
    started = time.monotonic()
    result = client.download_related_assets(
        source["doi"], {}, payload, tmp_path, asset_profile="body"
    )
    record_property("asset_replay_seconds", time.monotonic() - started)
    assert not result["asset_failures"]
    assert len(transport.calls) == 6
    assert sorted(call["url"] for call in transport.calls) == sorted(responses)
    assert sum(asset["downloaded_bytes"] for asset in result["assets"]) == 2_191_549
    article = client.to_article_model({}, payload, downloaded_assets=result["assets"])
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="body", max_tokens="full_text"
    )
    assert len(article.assets) == markdown.count("![") == 6
    assert "## Figures" not in markdown
    captions = re.findall(r"(?m)^\*\*Figure (\d)\.\*\* (.+)$", markdown)
    assert [number for number, _ in captions] == [str(n) for n in range(1, 7)]
    for _, caption in captions:
        assert markdown.count(caption) == 1
    for asset, capture in zip(result["assets"], captures, strict=True):
        assert asset["download_tier"] == "full_size"
        assert markdown.count(f"]({asset['path']})") == 1
        assert asset["preview_url"] not in markdown
        assert (
            Path(asset["path"]).read_bytes()
            == (folder / capture["body_file"]).read_bytes()
        )
        assert (asset["width"], asset["height"]) == (
            capture["width"],
            capture["height"],
        )
    summary = build_asset_quality_summary(
        article.assets, asset_profile="body", archive_enabled=True
    )
    assert summary.full_size == summary.local == 6
    assert summary.preview == summary.failed == 0
    assert not summary.issue_codes


@pytest.mark.parametrize(
    "doi",
    [
        "10.1093/bioinformatics/btaa161",
        "10.1093/bioinformatics/btaa823",
        "10.1093/bioinformatics/btaa153",
        "10.1093/beheco/arag047",
        "10.1093/molehr/gaaf013",
    ],
)
def test_existing_oxford_html_samples_preserve_identity_abstract_and_reference_order(
    doi,
):
    sample = golden_criteria_sample_for_doi(doi)
    filename = (
        "acquisition/source-completion-2026-09-18/001-http_response_entity.html"
        if doi.endswith("btaa153")
        else "original.html"
    )
    html = golden_criteria_asset(doi, filename).read_text()
    soup = BeautifulSoup(html, "lxml")
    assert visible_markdown(
        inspect_original(html.encode(), "oxfordacademic", doi, sample["source_url"])[
            "identity"
        ]
    ) == visible_markdown("matched")
    extraction = _oxfordacademic_html.extract_markdown(
        html, sample["source_url"], metadata={"doi": doi}, asset_profile="none"
    )
    article = build_oxford_html_article(html, sample["source_url"], doi)
    markdown = article.to_ai_markdown(
        include_refs="all", asset_profile="all", max_tokens="full_text"
    )
    assert article.quality.has_fulltext
    assert article.doi == doi
    assert extraction.abstract_sections
    assert all(
        visible_markdown(block["text"]) in visible_markdown(markdown)
        for block in extraction.abstract_sections
    )
    nodes = soup.select(".ref-list .ref")
    assert len(article.references) == len(nodes)
    for index, (reference, node) in enumerate(
        zip(article.references, nodes, strict=True), 1
    ):
        label = node.select_one(".label")
        expected = label.get_text(strip=True) if label else f"{index}."
        assert visible_markdown(
            extraction.metadata["references"][index - 1]["label"]
        ) == visible_markdown(expected)
        # Source authors/titles independently bind each reference to its order.
        title = node.select_one(".article-title")
        if title:
            assert visible_markdown(
                re.sub(r"\s+", "", title.get_text())
            ) in visible_markdown(re.sub(r"\s+", "", reference.raw))
    assert "<!--" not in markdown and "citationLinks" not in markdown
