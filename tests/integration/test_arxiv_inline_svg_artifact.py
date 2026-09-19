"""Filesystem and budget contract for acquired inline vectors; synthetic SVG only."""

import base64
from pathlib import Path

from paper_fetch.asset_budget import AssetBudget
from paper_fetch.providers._arxiv_graphics import INLINE_SVG_PREFIX
from paper_fetch.providers.arxiv import ArxivClient
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.runtime import RuntimeContext


class NoNetwork:
    def request(self, *args, **kwargs):
        raise AssertionError("Inline SVG must not issue a network request")


def test_inline_svg_client_publishes_bytes_and_honors_profile_and_budget(tmp_path):
    body = b'<svg xmlns="http://www.w3.org/2000/svg" id="F1.pic1"><path d="M 1 1 L 2 2"/></svg>'
    asset = {
        "kind": "figure",
        "section": "body",
        "image_id": "F1.pic1",
        "dom_id": "F1.pic1",
        "heading": "Figure 1",
        "source_kind": "arxiv_inline_svg",
        "url": INLINE_SVG_PREFIX + base64.b64encode(body).decode(),
    }
    payload = RawFulltextPayload(
        provider="arxiv",
        content=ProviderContent(
            route_kind="html",
            content_type="text/html",
            body=b"",
            source_url="https://arxiv.org/html/2006.11239v2",
            merged_metadata={"arxiv_id": "2006.11239v2"},
            extracted_assets=[asset],
        ),
    )
    client = ArxivClient(NoNetwork(), {})
    assert client.download_related_assets(
        "", {}, payload, tmp_path, asset_profile="none"
    ) == {"assets": [], "asset_failures": []}
    assert not list(tmp_path.rglob("*.svg"))
    result = client.download_related_assets(
        "", {}, payload, tmp_path, asset_profile="body"
    )
    saved = result["assets"][0]
    assert Path(saved["path"]).read_bytes() == body
    assert saved["source_url"].endswith("#F1.pic1")
    assert saved["downloaded_bytes"] == len(body)
    assert saved["download_tier"] == "full_size"
    assert result["asset_failures"] == []
    limited = tmp_path / "limited"
    context = RuntimeContext(
        env={}, download_dir=limited, asset_budget=AssetBudget(max_files=0)
    )
    denied = client.download_related_assets(
        "", {}, payload, limited, asset_profile="body", context=context
    )
    assert denied["assets"] == []
    assert denied["asset_failures"][0]["reason"] == "asset_file_limit_exceeded"
    assert not list(limited.rglob("*.svg"))


def test_object_svg_uses_existing_download_pipeline_without_source_archive(tmp_path):
    from tests.support._paper_fetch_support import FixtureHtmlTransport, http_response

    url = "https://arxiv.org/html/2006.11239v2/images/panel.svg"
    body = b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><path d="M 1 1 L 99 99"/></svg>'
    transport = FixtureHtmlTransport({url: http_response(url, body, "image/svg+xml")})
    asset = {
        "kind": "figure",
        "section": "body",
        "image_id": "F1.g1",
        "heading": "Figure 1",
        "source_kind": "arxiv_html_object",
        "url": url,
        "full_size_url": url,
    }
    payload = RawFulltextPayload(
        provider="arxiv",
        content=ProviderContent(
            route_kind="html",
            source_url="https://arxiv.org/html/2006.11239v2",
            content_type="text/html",
            body=b"",
            merged_metadata={"arxiv_id": "2006.11239v2"},
            extracted_assets=[asset],
        ),
    )
    result = ArxivClient(transport, {}).download_related_assets(
        "", {}, payload, tmp_path, asset_profile="body"
    )
    assert result["asset_failures"] == []
    assert len(result["assets"]) == 1
    asset = result["assets"][0]
    assert Path(asset["path"]).read_bytes() == body
    assert asset["download_tier"] == "full_size"
    assert {call["url"] for call in transport.calls} == {url}
