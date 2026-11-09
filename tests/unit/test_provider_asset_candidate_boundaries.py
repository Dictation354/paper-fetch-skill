"""Provider-specific removal of unsupported image fallback routes."""

from pathlib import Path
from unittest import mock

import pytest

from paper_fetch.providers.acs import AcsClient
from paper_fetch.providers.pnas import PnasClient
from paper_fetch.providers.browser_runtime import BrowserRuntimeConfig
from paper_fetch.runtime import RuntimeContext
from tests.support._atypon_browser_workflow_provider_support import (
    AssetTransport,
    _typed_raw_payload,
    png_header,
)
from tests.support._browser_workflow_deps import install_browser_workflow_deps


@pytest.mark.parametrize("provider", ["acs", "pnas"])
@pytest.mark.parametrize("serial_browser", [False, True])
def test_removed_fallback_is_never_requested(tmp_path, provider, serial_browser):
    original = "https://example.test/images/large/figure1.png"
    preview = "https://example.test/images/preview/figure1.png"
    viewer = "https://example.test/view-large/figure/1"
    transport = AssetTransport(
        {
            ("GET", original): {
                "status_code": 404,
                "headers": {"content-type": "text/plain"},
                "body": b"missing",
                "url": original,
            },
            ("GET", preview): {
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": png_header(640, 480),
                "url": preview,
            },
        }
    )
    client = {
        "acs": AcsClient,
        "pnas": PnasClient,
    }[provider](transport, {})
    fetch_page = mock.Mock(side_effect=AssertionError("unexpected figure-page request"))
    browser_urls = []

    def fetch_image(url, **kwargs):
        browser_urls.append(url)
        return None

    fetch_image.requires_caller_thread = serial_browser
    install_browser_workflow_deps(
        client,
        load_runtime_config=mock.Mock(
            return_value=BrowserRuntimeConfig(
                provider=provider,
                doi="10.5555/candidate-contract",
                artifact_dir=tmp_path,
                headless=True,
                user_agent="test",
            )
        ),
        ensure_runtime_ready=mock.Mock(),
        _build_shared_browser_image_fetcher=mock.Mock(return_value=fetch_image),
        fetch_html_with_browser=fetch_page,
    )
    asset = {
        "kind": "figure",
        "heading": "Figure 1",
        "url": preview,
        "preview_url": preview,
        "figure_page_url": viewer,
        "section": "body",
    }
    if provider == "pnas":
        asset["full_size_url"] = original
    raw = _typed_raw_payload(
        provider=provider,
        source_url="https://example.test/article",
        content_type="text/html",
        body=b"<article>Body</article>",
        route="html",
        markdown_text="Body",
        browser_context_seed={},
    )
    with RuntimeContext(env={}) as context:
        result = client._download_browser_backed_related_assets(
            "10.5555/candidate-contract",
            {},
            raw,
            tmp_path,
            asset_profile="body",
            context=context,
            assets=[asset],
        )
    fetch_page.assert_not_called()
    urls = [call["url"] for call in transport.calls] + browser_urls
    assert viewer not in urls
    if provider == "pnas":
        assert original in urls
        assert preview not in urls
        assert result["assets"] == []
        assert result["asset_failures"]
    else:
        assert urls == [preview]
        assert len(result["assets"]) == 1
        assert result["asset_failures"] == []


@pytest.mark.parametrize("state_mode", ["json", "native"])
@pytest.mark.parametrize("direct_status", [200, 403])
def test_pnas_direct_download_precedes_browser_in_both_state_modes(
    tmp_path, state_mode, direct_status
):
    url = "https://www.pnas.org/cms/asset/full.png"
    body = png_header(640, 480)
    transport = AssetTransport(
        {
            ("GET", url): {
                "status_code": direct_status,
                "headers": {
                    "content-type": "image/png" if direct_status == 200 else "text/html"
                },
                "body": body if direct_status == 200 else b"<html>Denied</html>",
                "url": url,
            }
        }
    )
    client = PnasClient(
        transport,
        {
            "PAPER_FETCH_PNAS_BROWSER_BACKEND": "byparr"
            if state_mode == "json"
            else "camoufox"
        },
    )
    raw = _typed_raw_payload(
        provider="pnas",
        source_url="https://www.pnas.org/doi/full/10.1073/test",
        content_type="text/html",
        body=f'<article><figure><img src="{url}"></figure></article>'.encode(),
        route="html",
        markdown_text="Body",
        browser_context_seed={},
    )
    fetcher = mock.Mock(
        return_value={
            "status_code": 200,
            "headers": {"content-type": "image/png"},
            "body": body,
            "url": url,
        }
    )
    fetcher.requires_caller_thread = True
    install_browser_workflow_deps(
        client,
        load_runtime_config=mock.Mock(
            return_value=BrowserRuntimeConfig(
                "pnas",
                "10.1073/test",
                tmp_path,
                True,
                None,
                state_mode=state_mode,
            )
        ),
        ensure_runtime_ready=mock.Mock(),
        _build_shared_browser_image_fetcher=mock.Mock(return_value=fetcher),
        _cached_browser_workflow_assets=mock.Mock(
            return_value=[
                {
                    "kind": "figure",
                    "url": url,
                    "full_size_url": url,
                    "section": "body",
                }
            ]
        ),
    )
    result = client.download_related_assets(
        "10.1073/test", {}, raw, tmp_path, asset_profile="body"
    )
    assert any(call["url"] == url for call in transport.calls)
    assert fetcher.call_count == int(direct_status == 403)
    assert not result["asset_failures"]
    assert Path(result["assets"][0]["path"]).read_bytes() == body
