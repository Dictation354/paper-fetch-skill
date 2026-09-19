"""Minimal PLOS query-identity, partial download and binary denominator contract."""

from pathlib import Path

import pytest

from paper_fetch.models import FetchEnvelope, RenderOptions
from paper_fetch.models.markdown import iter_markdown_images
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.providers.plos import PlosClient
from paper_fetch.quality.assets import build_asset_quality_summary
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from paper_fetch.workflow.rendering import rewrite_markdown_asset_links
from tests.support._paper_fetch_support import FixtureHtmlTransport

DOI = "10.1371/journal.pcbi.1234567"


@pytest.mark.parametrize("downloaded_count", [0, 1, 2])
def test_plos_same_endpoint_formulas_keep_exact_identity_with_partial_download(
    downloaded_count,
    tmp_path,
):
    urls = [
        f"https://journals.plos.org/ploscompbiol/article/file?id={DOI}.e00{i}&type=thumbnail"
        for i in (1, 2)
    ]
    assets = [
        {
            "kind": "formula",
            "heading": "Formula",
            "section": "body",
            "url": url,
            "original_url": f"info:doi/{DOI}.e00{i}",
            "anchor_key": f"info:doi/{DOI}.e00{i}",
        }
        for i, url in enumerate(urls, 1)
    ]
    body = (
        "# Results\n\nBefore ![Formula]("
        + urls[0]
        + ") middle ![Formula]("
        + urls[1]
        + ") after.\n"
    )
    payload = RawFulltextPayload(
        provider="plos",
        content=ProviderContent(
            route_kind="xml",
            source_url="https://journals.plos.org/ploscompbiol/article?id=" + DOI,
            content_type="text/xml",
            body=b"",
            markdown_text=body,
            merged_metadata={"doi": DOI, "title": "Identity example"},
            extracted_assets=assets,
        ),
    )
    downloaded = [
        {**asset, "path": str(tmp_path / f"e00{i}.png"), "download_url": asset["url"]}
        for i, asset in enumerate(assets[:downloaded_count], 1)
    ]
    for asset in downloaded:
        Path(asset["path"]).write_bytes(b"local asset boundary")
    article = PlosClient(FixtureHtmlTransport({}), {}).to_article_model(
        {}, payload, downloaded_assets=downloaded
    )
    expected = [
        str(tmp_path / f"e00{i}.png") if i <= downloaded_count else url
        for i, url in enumerate(urls, 1)
    ]
    for profile in ("body", "all"):
        markdown = article.to_ai_markdown(asset_profile=profile, max_tokens="full_text")
        assert [i.url for i in iter_markdown_images(markdown)] == expected
        assert (
            article.to_ai_markdown(asset_profile=profile, max_tokens="full_text")
            == markdown
        )
        assert "info:doi/" not in markdown
        saved = rewrite_markdown_asset_links(
            markdown,
            FetchEnvelope(
                doi=DOI, source=article.source, article=article, has_fulltext=True
            ),
            target_path=tmp_path / "article.md",
            render=RenderOptions(asset_profile=profile),
        )
        assert [i.url for i in iter_markdown_images(saved)] == [
            f"e00{i}.png" if i <= downloaded_count else url
            for i, url in enumerate(urls, 1)
        ]
    # Profile none preserves formula fallbacks already present in body text.
    assert [
        i.url
        for i in iter_markdown_images(article.to_ai_markdown(asset_profile="none"))
    ] == expected
    assert all("info:doi/" not in section.text for section in article.sections)
    assert [asset.source_url for asset in article.assets] == urls
    assert [asset.original_url for asset in article.assets] == [
        f"info:doi/{DOI}.e001",
        f"info:doi/{DOI}.e002",
    ]
    if downloaded_count == 0:
        article.quality.asset_summary = build_asset_quality_summary(
            article.assets, asset_profile="body", archive_enabled=True
        )
        acceptance = evaluate_fetch_acceptance(
            FetchEnvelope(
                doi=DOI, source=article.source, article=article, has_fulltext=False
            ),
            asset_profile="body",
            require_local_body_assets=True,
        )
        assert acceptance.asset.body_discovered == 2
        assert acceptance.asset.body_local == 0
        assert not acceptance.asset.local_body_assets_satisfied
