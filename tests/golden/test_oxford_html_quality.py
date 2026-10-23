"""Replay the captured warming article and existing Oxford HTML samples."""

from tests.support.markdown_presentation import visible_markdown

import hashlib
import json
import re

from bs4 import BeautifulSoup
import pytest

from paper_fetch.providers import _oxfordacademic_html
from tests.golden_criteria import golden_criteria_asset, golden_criteria_sample_for_doi
from tests.paths import FIXTURE_DIR
from tests.support.oxford_html import build_oxford_html_article
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
