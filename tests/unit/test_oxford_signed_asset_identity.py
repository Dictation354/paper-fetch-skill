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
