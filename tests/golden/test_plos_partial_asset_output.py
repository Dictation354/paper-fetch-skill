"""Real formula bytes remain tied to their JATS objects through final output."""

import pytest

from paper_fetch.models import FetchEnvelope, RenderOptions
from paper_fetch.models.markdown import iter_markdown_images
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.plos import PlosClient, parse_plos_xml
from paper_fetch.workflow.rendering import rewrite_markdown_asset_links
from tests.golden_corpus import golden_corpus_fixture_for_doi
from tests.support._paper_fetch_support import FixtureHtmlTransport


@pytest.mark.parametrize("downloaded_count", [0, 1, 2, 7])
def test_captured_plos_partial_formulas_keep_identity_in_saved_markdown(
    tmp_path, downloaded_count
):
    fixture = golden_corpus_fixture_for_doi("10.1371/journal.pcbi.1003118")
    body = fixture.raw_path.read_bytes()
    extracted = parse_plos_xml(
        body, source_url=fixture.source_url, base_metadata={"doi": fixture.doi}
    )
    formulas = [a for a in extracted.assets if a.get("kind") == "formula"]
    assert len(formulas) == 7
    downloads = []
    for index, asset in enumerate(formulas[:downloaded_count], 1):
        original = next(
            fixture.raw_path.parent.glob(
                f"acquisition/official-reacquisition-2026-09-19/assets/*e00{index}.png"
            )
        )
        path = tmp_path / f"e00{index}.png"
        path.write_bytes(original.read_bytes())
        downloads.append({**asset, "path": str(path), "download_url": asset["link"]})
    payload = RawFulltextPayload(
        provider="plos",
        content=ProviderContent(
            route_kind="xml",
            source_url=fixture.source_url,
            content_type="text/xml",
            body=body,
            markdown_text=extracted.markdown_text,
            merged_metadata=extracted.metadata,
            extracted_assets=extracted.assets,
        ),
    )
    article = PlosClient(FixtureHtmlTransport({}), {}).to_article_model(
        {}, payload, downloaded_assets=downloads
    )
    markdown = article.to_ai_markdown(
        include_refs="all", max_tokens="full_text", asset_profile="body"
    )
    saved = rewrite_markdown_asset_links(
        markdown,
        FetchEnvelope(
            doi=fixture.doi, source=article.source, article=article, has_fulltext=True
        ),
        target_path=tmp_path / "article.md",
        render=RenderOptions(),
    )
    assert [i.url for i in iter_markdown_images(saved) if i.alt == "Formula"] == [
        f"e00{index}.png" if index <= downloaded_count else asset["link"]
        for index, asset in enumerate(formulas, 1)
    ]
