"""P28–P30: image identity and local-asset acceptance boundary contracts."""

import pytest

from paper_fetch.models import FetchEnvelope
from paper_fetch.providers._arxiv_assets import (
    _match_source_figures_to_html_placeholders,
    inline_arxiv_source_assets_in_markdown,
)
from paper_fetch.providers.arxiv import ArxivClient
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.workflow.acceptance import evaluate_fetch_acceptance
from tests.support._paper_fetch_support import RecordingTransport


def test_source_identity_ignores_archive_order_and_allows_legitimate_reuse():
    placeholders = [
        {
            "url": "https://arxiv.org/html/1234.56789v1/images/right.png",
            "caption": caption,
        }
        for caption in ("Figure 1: An image", "Figure 9: Reused image")
    ]
    figures = [
        {"source_path": "wrong.png", "caption": "An image"},
        {"source_path": "images/right.png", "caption": "A different TeX caption"},
    ]
    assert [
        s["source_path"]
        for _, s in _match_source_figures_to_html_placeholders(placeholders, figures)
    ] == ["images/right.png"] * 2


@pytest.mark.parametrize("url", ["", "https://arxiv.org/html/1234.56789v1/missing.png"])
def test_source_identity_does_not_fill_an_unmatched_slot(url):
    assert (
        _match_source_figures_to_html_placeholders(
            [{"url": url, "caption": "Directed graphical model"}],
            [{"source_path": "faces.jpg", "caption": "Nearest neighbours"}],
        )[0][1]
        is None
    )


def test_caption_only_match_must_be_unambiguous():
    assert (
        _match_source_figures_to_html_placeholders(
            [{"caption": "Figure 1: Sample panels"}],
            [
                {"source_path": p, "caption": "Sample panels"}
                for p in ("a.png", "b.png")
            ],
        )[0][1]
        is None
    )


def test_source_alias_is_not_inserted_again_and_other_occurrence_is_retained():
    remote = "https://arxiv.org/html/1234.56789v1/shared.png"
    markdown = f"![Figure 1]({remote})\n\n**Figure 1.** First\n\n**Figure 2.** Second"
    assets = [
        {
            "heading": f"Figure {n}",
            "url": "arxiv-source://1234.56789v1/shared.png",
            "original_url": remote,
            "download_tier": "arxiv_source",
        }
        for n in (1, 2)
    ]
    output = inline_arxiv_source_assets_in_markdown(markdown, assets)
    assert output.count("![Figure 1]") == 1
    assert output.count("![Figure 2]") == 1
    assert output.index("![Figure 2]") < output.index("**Figure 2.")


@pytest.mark.parametrize("discovered", [False, True])
def test_remote_body_reference_cannot_pass_strict_local_acceptance(discovered):
    url = "https://arxiv.org/html/1234.56789v1/missing.png"
    payload = RawFulltextPayload(
        provider="arxiv",
        content=ProviderContent(
            route_kind="html",
            source_url="https://arxiv.org/html/1234.56789v1",
            content_type="text/html",
            body=f'<article><figure><img src="{url}"></figure></article>'.encode(),
            markdown_text=f"## Results\n\nBody.\n\n![Figure 1]({url})",
            extracted_assets=[
                {"kind": "figure", "section": "body", "url": url, "heading": "Figure 1"}
            ]
            if discovered
            else [],
        ),
    )
    client = ArxivClient(RecordingTransport({}), {})
    article = client.to_article_model({}, payload)
    markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")
    acceptance = evaluate_fetch_acceptance(
        FetchEnvelope(
            doi="10.48550/arxiv.1234.56789v1",
            source="arxiv_html",
            has_fulltext=True,
            article=article,
            markdown=markdown,
        ),
        asset_profile="body",
        require_local_body_assets=True,
    )
    assert len(article.assets) == 1
    assert not acceptance.asset.local_body_assets_satisfied


def test_article_frontmatter_icons_do_not_enter_body_asset_denominator():
    from paper_fetch.providers._arxiv_assets import reconcile_arxiv_body_assets

    icon = "https://arxiv.org/html/1234.56789v1/blog.png"
    image = "https://arxiv.org/html/1234.56789v1/body.png"
    assets = reconcile_arxiv_body_assets(
        f"![Figure]({icon})\n\n![Figure 1]({image})",
        [],
        [],
        article_html=f'<article><p><a href="blog"><img src="{icon}"></a></p><figure><img src="{image}"></figure></article>',
        source_url="https://arxiv.org/html/1234.56789v1",
    )
    assert [asset["url"] for asset in assets] == [image]


def test_generic_caption_subset_is_not_sufficient_source_identity():
    assert (
        _match_source_figures_to_html_placeholders(
            [{"caption": "Generated samples"}],
            [
                {
                    "source_path": "unrelated.png",
                    "caption": "Generated samples of a completely different experiment and dataset",
                }
            ],
        )[0][1]
        is None
    )


@pytest.mark.parametrize(
    "alt,expected",
    [("Figure 13", "Figure 13"), ("Figure", "Figure 1"), ("", "Figure 1")],
)
def test_localization_keeps_occurrence_label_through_file_rendering(
    tmp_path, alt, expected
):
    from paper_fetch.models import RenderOptions, article_from_markdown
    from paper_fetch.workflow.rendering import rewrite_markdown_asset_links
    from paper_fetch.models.markdown import iter_markdown_images
    from paper_fetch.models.render import rewrite_markdown_asset_links as bind_images

    path = tmp_path / "shared.png"
    path.write_bytes(b"local asset boundary")
    remote = "https://arxiv.org/html/1234.56789v1/shared.png"
    article = article_from_markdown(
        source="arxiv_html",
        doi=None,
        metadata={"title": "Reused figure"},
        markdown_text=f"## Results\n\n![Figure 1]({remote})\n\n![{alt}]({remote})",
        assets=[
            {"kind": "figure", "heading": "Figure 1", "url": remote, "path": str(path)}
        ],
    )
    markdown = bind_images(
        f"![Figure 1]({remote})\n\n![{alt}]({remote})", article.assets
    )
    assert [i.alt for i in iter_markdown_images(markdown)] == ["Figure 1", expected]
    rendered = rewrite_markdown_asset_links(
        markdown,
        FetchEnvelope(
            doi=None, source=article.source, article=article, has_fulltext=True
        ),
        target_path=tmp_path / "article.md",
        render=RenderOptions(),
    )
    assert [(i.alt, i.url) for i in iter_markdown_images(rendered)] == [
        ("Figure 1", "shared.png"),
        (expected, "shared.png"),
    ]
