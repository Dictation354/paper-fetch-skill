"""OUP signed image identity is distinct from its unchanged request URL."""

import pytest

from paper_fetch.providers.oxfordacademic import _merge_oxford_assets

OLD = "https://oup.silverchair-cdn.com/oup/paper/2/figure.jpeg?Expires=1&Signature=old&Key-Pair-Id=key"
NEW = "https://oup.silverchair-cdn.com/oup/paper/2/figure.jpeg?Expires=2&Signature=new&Key-Pair-Id=key"


def test_fresh_captured_figure_replaces_old_signature_without_changing_urls():
    old = {"kind": "figure", "url": OLD, "caption": "Original caption"}
    current = {"kind": "figure", "url": NEW, "path": "/captured/figure.jpeg"}
    assert _merge_oxford_assets([old], [current]) == [{**old, **current}]
    assert old["url"] == OLD
    assert current["url"] == NEW


@pytest.mark.parametrize(
    "other",
    [
        NEW.replace("figure.jpeg", "m_figure.jpeg"),
        NEW.replace("/paper/", "/other-paper/"),
        NEW + "&crop=left",
        NEW.replace("oup.silverchair-cdn.com", "elsewhere.example"),
    ],
)
def test_different_object_rendition_host_or_content_query_stays_separate(other):
    old = {"kind": "figure", "url": OLD}
    current = {"kind": "figure", "url": other, "path": "/captured/figure.jpeg"}
    assert _merge_oxford_assets([old], [current]) == [old, current]


def test_subpanels_share_viewer_but_keep_binary_object_identities():
    viewer = "https://academic.oup.com/article/figure/1"
    panels = [
        {"kind": "figure", "url": url, "figure_page_url": viewer}
        for url in (OLD, OLD.replace("figure.jpeg", "figure-b.jpeg"))
    ]
    downloaded = [
        {
            **panel,
            "url": panel["url"].replace("Signature=old", "Signature=new"),
            "path": f"/captured/{n}.jpeg",
        }
        for n, panel in enumerate(panels)
    ]
    merged = _merge_oxford_assets(panels, downloaded)
    assert merged == downloaded


def test_viewer_without_a_rendition_is_a_page_link():
    from paper_fetch.providers._oxfordacademic_html import extract_markdown

    url = "https://academic.oup.com/journal/article/1"
    viewer = "https://academic.oup.com/view-large/figure/123"
    html = f'<div class="widget-ArticleFulltext"><h2>Results</h2><div class="fig fig-section"><span class="fig-label">Fig. 1.</span><a href="{viewer}">View large</a></div></div>'
    result = extract_markdown(html, url, metadata={"doi": "10.1093/example"})
    assert f"[Fig. 1.]({viewer})" in result.markdown_text
    assert "![" not in result.markdown_text
    assert any(
        asset.get("figure_page_url") == viewer for asset in result.extracted_assets
    )
