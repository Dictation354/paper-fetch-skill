"""New full-paper baselines use original captures and complete persisted output."""

from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

from paper_fetch.artifacts import ArtifactStore
from paper_fetch.models import FetchEnvelope
from paper_fetch.models.markdown import iter_markdown_images
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.golden_corpus import (
    iter_golden_corpus_fixtures,
    golden_corpus_fixture_for_doi,
    replay_springer_pdf_fallback,
)
from tests.golden_criteria import golden_criteria_asset
from tests.support.replay import build_article_from_fixture, persisted_fixture_markdown

FIXTURES = [
    f
    for f in iter_golden_corpus_fixtures()
    if f.sample.get("baseline_completion") == "2026-10-21"
]


def test_completion_register_contains_every_executable_paper():
    assert len(FIXTURES) == 33
    assert len({f.doi for f in FIXTURES}) == 33
    assert (
        sum(
            f.provider == "arxiv"
            and f.doi.endswith(("0811.2625v2", "0905.2326v2", "2606.00587v2"))
            for f in FIXTURES
        )
        == 3
    )


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.sample_id)
def test_complete_persisted_markdown_matches_provider_replay(fixture, tmp_path):
    article = build_article_from_fixture(fixture)
    markdown = persisted_fixture_markdown(fixture, article)
    store = ArtifactStore.from_download_dir(tmp_path)
    output = store.write_text_file(tmp_path / "extracted.md", markdown)
    assert (
        output.read_text()
        == golden_criteria_asset(fixture.doi, "extracted.md").read_text()
    )
    assert article.quality.has_fulltext
    for image in iter_markdown_images(markdown):
        parts = urlsplit(image.url)
        if parts.scheme or image.url.startswith("//"):
            continue
        path = Path(unquote(parts.path))
        assert (
            golden_criteria_asset(fixture.doi, "extracted.md").parent / path
        ).is_file()


def test_nature_early_access_keeps_html_failure_pdf_identity_and_degraded_acceptance():
    from bs4 import BeautifulSoup
    from paper_fetch.providers import _springer_dom

    fixture = golden_corpus_fixture_for_doi("10.1038/s41586-026-11124-z")
    html = golden_criteria_asset(fixture.doi, "landing.html").read_text()
    soup = BeautifulSoup(html, "lxml")
    assert (
        soup.select_one('meta[name="citation_pdf_url"]')["content"]
        == fixture.source_url
    )
    assert (
        "Peking University"
        in soup.select_one('[data-test="access-message"]').get_text()
    )
    assert _springer_dom.early_access_without_body(html)
    article, payload, calls = replay_springer_pdf_fallback(fixture)
    assert calls and fixture.source_url in calls[0]
    assert payload.content.route_kind == "pdf_fallback"
    assert article.source == "springer_pdf"
    assert "fulltext:springer_html_fail" in article.quality.source_trail
    assert "fulltext:springer_pdf_fallback_ok" in article.quality.source_trail
    envelope = FetchEnvelope(
        doi=fixture.doi, source=article.source, has_fulltext=True, article=article
    )
    acceptance = evaluate_fetch_acceptance(
        envelope, expected_doi=fixture.doi, asset_profile="none"
    )
    assert acceptance.overall == "degraded"


@pytest.mark.parametrize(
    "arxiv_id,count", [("0811.2625v2", 2), ("0905.2326v2", 103), ("2606.00587v2", 1)]
)
def test_arxiv_complete_auxiliary_pages_discover_same_version_links_without_download(
    arxiv_id, count
):
    from paper_fetch.providers._arxiv_assets import discover_arxiv_ancillary_assets
    from paper_fetch.runtime import RuntimeContext
    from tests.support._paper_fetch_support import FixtureHtmlTransport

    doi = "10.48550/arxiv." + arxiv_id
    urls = [
        f"https://arxiv.org/abs/{arxiv_id}",
        f"https://arxiv.org/src/{arxiv_id}/anc",
    ]
    pages = ["acquisition/abstract-page.html", "acquisition/ancillary-page.html"]
    transport = FixtureHtmlTransport(
        {
            url: {
                "body": golden_criteria_asset(doi, name).read_bytes(),
                "headers": {"content-type": "text/html"},
            }
            for url, name in zip(urls, pages, strict=True)
        }
    )
    with RuntimeContext(env={}) as context:
        version, result = discover_arxiv_ancillary_assets(
            transport,
            arxiv_id,
            user_agent="offline captured replay",
            context=context,
        )
    assert version == arxiv_id
    assert not result["asset_failures"]
    assert len(result["assets"]) == count
    assert all(asset["url"].startswith(urls[1] + "/") for asset in result["assets"])
    assert [call["url"] for call in transport.calls] == urls


def test_arxiv_original_extended_data_panel_captions_are_complete_and_ordered():
    from bs4 import BeautifulSoup
    from tests.support.canonical_content import source_caption_runs
    from tests.support.scientific_content import scientific_text_key

    fixture = golden_corpus_fixture_for_doi("10.48550/arxiv.2606.00587v2")
    soup = BeautifulSoup(fixture.raw_path.read_text(), "lxml")
    panels = [
        node
        for node in soup.select("figure.ltx_figure p.ltx_figure_panel")
        if node.get_text(" ", strip=True).startswith("Extended Data Figure")
    ]
    assert len(panels) == 2
    article = build_article_from_fixture(fixture)
    rendered = scientific_text_key(
        article.to_ai_markdown(
            include_refs="all",
            max_tokens="full_text",
            asset_profile="all",
        )
    )
    cursor = 0
    for panel in panels:
        for run in source_caption_runs(panel):
            expected = scientific_text_key(run)
            if expected:
                position = rendered.find(expected, cursor)
                assert position >= 0, run
                cursor = position + len(expected)
