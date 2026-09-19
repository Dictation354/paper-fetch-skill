"""Provider source URL boundaries for formula/table image fallbacks."""

import pytest
from bs4 import BeautifulSoup

from paper_fetch.providers._atypon_browser_workflow_profiles import publisher_profile
from paper_fetch.providers.atypon_browser_workflow.normalization import (
    _normalize_special_blocks,
)
from paper_fetch.providers.html_springer_nature import extract_springer_nature_markdown


@pytest.mark.parametrize(
    "publisher,prefix", [("wiley", "/cms/asset/"), ("ams", "/view/")]
)
def test_source_image_hook_resolves_only_provider_remote_paths(publisher, prefix):
    soup = BeautifulSoup(
        f'<div class="tableWrap"><img src="{prefix}math-1.gif" '
        f'data-full-size="{prefix}paper-math-0001.gif" data-src="{prefix}paper-math-0002.gif">'
        '<img src="paper_assets/math-2.gif"><img src="/tmp/math-3.gif">'
        '<img src="data:image/gif;base64,AA=="><img src="https://cdn.example/math-4.gif">'
        '<a href="#note">note</a></div>',
        "html.parser",
    )
    hook = publisher_profile(publisher).prepare_source_images
    hook(soup, "https://article.example/doi/full/example")
    images = soup.find_all("img")
    assert images[0]["src"] == f"https://article.example{prefix}math-1.gif"
    assert (
        images[0]["data-full-size"]
        == f"https://article.example{prefix}paper-math-0001.gif"
    )
    assert (
        images[0]["data-src"] == f"https://article.example{prefix}paper-math-0002.gif"
    )
    assert [image["src"] for image in images[1:]] == [
        "paper_assets/math-2.gif",
        "/tmp/math-3.gif",
        "data:image/gif;base64,AA==",
        "https://cdn.example/math-4.gif",
    ]
    assert soup.a["href"] == "#note"
    once = str(soup)
    hook(soup, "https://other.example/article")
    assert str(soup) == once


def test_existing_dom_hooks_keep_the_single_container_contract():
    assert publisher_profile("pnas").prepare_source_images is None
    soup = BeautifulSoup("<div><p>Body text.</p></div>", "html.parser")
    assert _normalize_special_blocks(soup.div, "pnas") == []
    assert soup.get_text() == "Body text."


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_springer_image_src_uses_article_scheme_and_preserves_other_urls(scheme):
    html = (
        '<article><p>Body.</p><figure><img src="//media.nature.com/lw767/a.jpg">'
        '</figure><figure><img src="paper_assets/b.jpg"></figure>'
        '<figure><img src="/tmp/c.jpg"></figure>'
        '<figure><img src="data:image/png;base64,AA=="></figure>'
        '<figure><img src="https://cdn.example/d.jpg"></figure>'
        "<p>Literal //example.com/page</p></article>"
    )
    rendered = extract_springer_nature_markdown(
        html, f"{scheme}://www.nature.com/articles/example"
    )
    assert f"]({scheme}://media.nature.com/lw767/a.jpg)" in rendered
    for url in (
        "paper_assets/b.jpg",
        "/tmp/c.jpg",
        "data:image/png;base64,AA==",
        "https://cdn.example/d.jpg",
    ):
        assert f"]({url})" in rendered
    assert "Literal //example.com/page" in rendered
