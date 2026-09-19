"""Provider-specific removal of unsupported image fallback routes."""

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
