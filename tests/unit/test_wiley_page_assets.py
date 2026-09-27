import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from paper_fetch.asset_budget import AssetBudget, AssetBudgetExceeded
from paper_fetch.extraction.html.assets import (
    AssetDownloadOptions,
    FIGURE_KIND,
    download_assets,
)
from paper_fetch.http import RequestCancelledError
from paper_fetch.providers._wiley_page_assets import WileyPageAssetFetcher, asset_urls
from tests.support.wiley_page_assets import WEBP_1X1, formula, png_bytes

ROOT = "https://onlinelibrary.wiley.com"


def fetcher_for(assets):
    fetcher = WileyPageAssetFetcher(
        assets=assets,
        browser_context_seed_getter=lambda: {},
        seed_urls_getter=lambda: [ROOT + "/doi/10.1111/test"],
    )
    fetcher._budget = AssetBudget()
    return fetcher


def capture(fetcher, url, body, *, status=200, headers=None):
    response = Mock(url=url, status=status)
    response.all_headers.return_value = headers or {"content-type": "image/png"}
    response.body.return_value = body
    request = Mock(url=url, response=lambda: response)
    fetcher._active_url = url
    fetcher._requests.add(request)
    fetcher._capture(request)
    return response


def test_exact_urls_and_late_responses_are_isolated():
    urls = [ROOT + "/A.png?size=1", ROOT + "/a.png?size=1"]
    fetcher = fetcher_for([formula(url) for url in urls])
    assert asset_urls({"url": urls[0] + "#x", "preview_url": urls[0]}) == [urls[0]]
    fetcher._active_url = urls[1]
    old = Mock(url=urls[0])
    fetcher._capture(old)
    old.response.assert_not_called()
    capture(fetcher, urls[1], WEBP_1X1)
    duplicate = capture(fetcher, urls[1], b"wrong")
    duplicate.body.assert_not_called()
    assert fetcher._responses[urls[1]][0]["body"] == WEBP_1X1
    fetcher.close()
    assert fetcher._budget.snapshot()["reserved_bytes"] == 0


@pytest.mark.parametrize(
    "status,body", [(403, WEBP_1X1), (200, b"<html>denied</html>"), (200, b"")]
)
def test_bad_responses_rejected(status, body):
    url = ROOT + "/math.png"
    fetcher = fetcher_for([formula(url)])
    capture(fetcher, url, body, status=status)
    assert not fetcher._responses
    assert fetcher.failure_for(url)
    assert fetcher._budget.snapshot()["reserved_bytes"] == 0
    fetcher.close()


@pytest.mark.parametrize("mitigated", [None, "challenge"])
def test_failed_response_records_evidence_without_secrets(mitigated):
    url = ROOT + "/math.png"
    fetcher = fetcher_for([formula(url)])
    body = (
        b"<title>Just a moment...</title><script>window._cf_chl_opt = "
        b"{token: 'private-body-token'};</script>"
    )
    headers = {
        "Server": "cloudflare",
        "CF-Ray": "abc123-LHR",
        "Content-Type": "text/html",
        "Set-Cookie": "secret-cookie",
        "Authorization": "Bearer private-header-token",
    }
    if mitigated:
        headers["CF-Mitigated"] = mitigated
    capture(fetcher, url, body, status=403, headers=headers)
    failure = fetcher.failure_for(url)
    assert failure["reason"] == "wiley_page_image_response"
    assert failure["status"] == 403
    diagnostic = failure["response_diagnostic"]
    assert diagnostic["headers"]["cf-ray"] == "abc123-LHR"
    assert diagnostic["cf_mitigated_challenge"] is (mitigated == "challenge")
    assert diagnostic["body_sha256"] == hashlib.sha256(body).hexdigest()
    assert diagnostic["body_bytes"] == len(body)
    assert diagnostic["body_markers"] == ["just a moment", "_cf_chl_opt"]
    assert not diagnostic["body_scan_truncated"]
    serialized = json.dumps(failure)
    for secret in ("secret-cookie", "private-header-token", "private-body-token"):
        assert secret not in serialized
    assert not fetcher._responses
    assert fetcher._budget.snapshot()["reserved_bytes"] == 0
    fetcher.close()


def test_generic_cloudflare_403_is_not_confirmed_as_challenge():
    url = ROOT + "/math.png"
    fetcher = fetcher_for([formula(url)])
    capture(fetcher, url, b"Forbidden", status=403, headers={"server": "cloudflare"})
    diagnostic = fetcher.failure_for(url)["response_diagnostic"]
    assert diagnostic["cf_mitigated_challenge"] is False
    assert diagnostic["body_markers"] == []
    fetcher.close()


def test_large_failure_body_is_not_read():
    url = ROOT + "/math.png"
    fetcher = fetcher_for([formula(url)])
    response = capture(
        fetcher,
        url,
        b"unused",
        status=403,
        headers={"content-length": str(65537), "cf-mitigated": "challenge"},
    )
    response.body.assert_not_called()
    diagnostic = fetcher.failure_for(url)["response_diagnostic"]
    assert diagnostic["cf_mitigated_challenge"] is True
    assert diagnostic["body_state"] == "skipped_declared_size"
    fetcher.close()


@pytest.mark.parametrize("stage", ["all_headers", "body"])
def test_failure_diagnostic_error_preserves_original_status(stage):
    url = ROOT + "/math.png"
    fetcher = fetcher_for([formula(url)])
    response = Mock(status=403)
    response.all_headers.return_value = {"cf-mitigated": "challenge"}
    getattr(response, stage).side_effect = RuntimeError("private-error-token")
    request = Mock(url=url, response=lambda: response)
    fetcher._active_url = url
    fetcher._requests.add(request)
    fetcher._capture(request)
    failure = fetcher.failure_for(url)
    assert failure["status"] == 403
    assert failure["reason"] == "wiley_page_image_response"
    assert failure["response_diagnostic"]["diagnostic_error_type"] == "RuntimeError"
    assert "private-error-token" not in json.dumps(failure)
    assert fetcher._budget.snapshot()["reserved_bytes"] == 0
    fetcher.close()


def test_failure_body_respects_budget_and_preserves_status():
    url = ROOT + "/math.png"
    fetcher = fetcher_for([formula(url)])
    fetcher._budget = AssetBudget(max_bytes_per_asset=10)
    response = capture(
        fetcher, url, b"unused", status=403, headers={"content-length": "100"}
    )
    response.body.assert_not_called()
    assert fetcher.failure_for(url)["status"] == 403
    with pytest.raises(AssetBudgetExceeded):
        fetcher(url, formula(url))
    assert fetcher._closed
    assert fetcher._budget.snapshot()["reserved_bytes"] == 0


def test_capture_respects_shared_byte_budget_before_reading_body():
    url = ROOT + "/math.png"
    fetcher = fetcher_for([formula(url)])
    fetcher._budget = AssetBudget(max_bytes_per_asset=10)
    response = capture(fetcher, url, WEBP_1X1, headers={"content-length": "100"})
    response.body.assert_not_called()
    with pytest.raises(AssetBudgetExceeded):
        fetcher(url, formula(url))
    assert fetcher._closed
    assert not fetcher._responses


def test_png_url_webp_response_keeps_bytes_and_mime_extension(tmp_path):
    url = ROOT + "/math.png"
    asset = formula(url)
    fetcher = fetcher_for([asset])
    fetcher._opened = True
    fetcher._page = Mock()
    fetcher._page.url = url
    fetcher._page.evaluate.return_value = True
    fetcher._page.goto.side_effect = lambda *a, **kw: capture(fetcher, url, WEBP_1X1)
    transport = Mock()
    result = download_assets(
        FIGURE_KIND,
        transport,
        article_id="10.1111/test",
        assets=[asset],
        output_dir=tmp_path,
        user_agent="test",
        asset_profile="body",
        options=AssetDownloadOptions(
            image_document_fetcher=fetcher, fetch_policy="browser_only"
        ),
    )
    assert not result["asset_failures"]
    assert len(result["assets"]) == 1
    path = Path(result["assets"][0]["path"])
    assert path.suffix == ".webp"
    assert path.read_bytes() == WEBP_1X1
    transport.request.assert_not_called()
    fetcher.close()


@pytest.mark.parametrize(
    "fetcher",
    [None, Mock(return_value=None), Mock(return_value={"body": b"<html>bad</html>"})],
)
def test_browser_only_failure_never_uses_http(tmp_path, fetcher):
    url = ROOT + "/math.png"
    transport = Mock()
    result = download_assets(
        FIGURE_KIND,
        transport,
        article_id="10.1111/test",
        assets=[formula(url)],
        output_dir=tmp_path,
        user_agent="test",
        asset_profile="body",
        options=AssetDownloadOptions(
            image_document_fetcher=fetcher, fetch_policy="browser_only"
        ),
    )
    assert result["asset_failures"]
    assert not result["assets"]
    transport.request.assert_not_called()


def test_browser_only_propagates_cancellation(tmp_path):
    transport = Mock()
    fetcher = Mock(side_effect=RequestCancelledError("cancelled"))
    with pytest.raises(RequestCancelledError):
        download_assets(
            FIGURE_KIND,
            transport,
            article_id="10.1111/test",
            assets=[formula(ROOT + "/math.png")],
            output_dir=tmp_path,
            user_agent="test",
            options=AssetDownloadOptions(
                image_document_fetcher=fetcher, fetch_policy="browser_only"
            ),
        )
    transport.request.assert_not_called()


@pytest.mark.parametrize("profile", ["none", "body"])
def test_wiley_default_policy_has_no_direct_probe_figure_page_or_refresh(
    tmp_path, monkeypatch, profile
):
    from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
    from paper_fetch.providers.wiley import WileyClient
    from paper_fetch.runtime import RuntimeContext
    from tests.support._browser_workflow_deps import install_browser_workflow_deps
    from tests.support.wiley_page_assets import figure

    transport = Mock()
    client = WileyClient(transport, {})
    runtime = SimpleNamespace(headless=True, user_agent="test")
    assets = [figure(ROOT, 1), formula(ROOT + "/math.png")]
    raw = RawFulltextPayload(
        provider="wiley",
        content=ProviderContent(
            route_kind="html",
            source_url=ROOT + "/doi/10.1111/test",
            content_type="text/html",
            body=b"<article></article>",
            browser_context_seed={
                "browser_cookies": [
                    {
                        "name": "seed",
                        "value": "value",
                        "domain": "onlinelibrary.wiley.com",
                        "path": "/",
                    }
                ]
            },
        ),
    )
    factory = Mock(return_value=Mock(return_value=None))
    monkeypatch.setattr(client, "_browser_asset_image_fetcher", factory)
    refresh = Mock()
    figure_page = Mock()
    deps = install_browser_workflow_deps(
        client,
        load_runtime_config=Mock(return_value=runtime),
        ensure_runtime_ready=Mock(),
        refresh_browser_context_seed=refresh,
        _cached_browser_workflow_assets=Mock(return_value=assets),
        fetch_html_with_browser=figure_page,
    )
    with RuntimeContext(env={}) as context:
        result = client.download_related_assets(
            "10.1111/test", {}, raw, tmp_path, asset_profile=profile, context=context
        )
    transport.request.assert_not_called()
    refresh.assert_not_called()
    figure_page.assert_not_called()
    if profile == "none":
        factory.assert_not_called()
        deps.load_runtime_config.assert_not_called()
    else:
        factory.assert_called_once()
        request = factory.call_args.kwargs
        assert request["attempt_body_assets"][0]["kind"] == "formula"
        assert (
            request["browser_context_seed_getter"]()["browser_cookies"][0]["name"]
            == "seed"
        )
        assert result["asset_failures"]
        factory.return_value.close.assert_called_once()


def test_wiley_preview_fallback_remains_degraded_even_for_large_preview(tmp_path):
    from paper_fetch.providers.browser_workflow.asset_download import (
        BrowserAssetDownloadPlan,
        BrowserAssetRecoveryContext,
        download_browser_backed_related_assets,
    )
    from paper_fetch.quality.assets import preview_asset_is_accepted
    from tests.support._browser_workflow_deps import browser_workflow_deps
    from tests.support.wiley_page_assets import figure

    asset = figure(ROOT, 1)

    def response(url, _asset):
        if url == asset["preview_url"]:
            return {
                "body": png_bytes(800, 600),
                "url": url,
                "headers": {"content-type": "image/png"},
                "status_code": 200,
                "_paper_fetch_recovery_attempts": [
                    {"stage": "full_size", "status": 403}
                ],
            }
        return None

    fetcher = Mock(side_effect=response)
    transport = Mock()
    refresh = Mock()
    result = download_browser_backed_related_assets(
        BrowserAssetDownloadPlan(
            article_id="10.1111/test",
            output_dir=tmp_path,
            asset_profile="body",
            body_assets=[asset],
            supplementary_assets=[],
            fetch_policy="browser_only",
            figure_page_discovery=False,
        ),
        BrowserAssetRecoveryContext(
            runtime=SimpleNamespace(headless=True, user_agent="test"),
            provider="wiley",
            user_agent="test",
            browser_context_seed={},
            browser_cookies=[],
            active_seed_urls=[],
        ),
        image_fetcher_factory=lambda **kwargs: fetcher,
        file_fetcher_factory=lambda **kwargs: None,
        download_settings={"transport": transport},
        deps=browser_workflow_deps(refresh_browser_context_seed=refresh),
    )
    assert len(result["assets"]) == 1
    preview = result["assets"][0]
    assert preview["download_tier"] == "preview"
    assert not preview_asset_is_accepted(preview)
    assert preview["recovery_attempts"][0] == {"stage": "full_size", "status": 403}
    assert preview["recovery_attempts"][-1]["stage"] == "preview_fallback"
    transport.request.assert_not_called()
    refresh.assert_not_called()


def test_browser_only_never_invokes_figure_page_or_deferred_candidates(tmp_path):
    from tests.support.wiley_page_assets import figure

    asset = figure(ROOT, 1)
    asset["figure_page_url"] = ROOT + "/doi/figure/10.1111/test"
    transport = Mock()
    figure_page = Mock()
    fallback = Mock()
    result = download_assets(
        FIGURE_KIND,
        transport,
        article_id="10.1111/test",
        assets=[asset],
        output_dir=tmp_path,
        user_agent="test",
        asset_profile="body",
        options=AssetDownloadOptions(
            image_document_fetcher=Mock(return_value=None),
            figure_page_fetcher=figure_page,
            _fallback_candidate_builder=fallback,
            fetch_policy="browser_only",
        ),
    )
    assert result["asset_failures"]
    assert not result["assets"]
    transport.request.assert_not_called()
    figure_page.assert_not_called()
    fallback.assert_not_called()


def waiting_fetcher(monkeypatch, assets):
    clock = [100.0]
    monkeypatch.setattr(
        "paper_fetch.providers._wiley_page_assets.time.monotonic", lambda: clock[0]
    )
    fetcher = fetcher_for(assets)
    page = Mock()
    page.evaluate.return_value = True
    page.wait_for_timeout.side_effect = lambda ms: clock.__setitem__(
        0, clock[0] + ms / 1000
    )
    fetcher._opened = True
    fetcher._page = page
    return fetcher, page, clock


def test_same_url_challenge_then_success_keeps_timeline(monkeypatch):
    asset = formula(ROOT + "/math.png")
    url = asset["url"]
    fetcher, page, clock = waiting_fetcher(monkeypatch, [asset])
    page.url = url
    page.goto.side_effect = lambda *a, **kw: capture(
        fetcher, url, b"challenge", status=403, headers={"cf-mitigated": "challenge"}
    )

    def finish(ms):
        clock[0] += ms / 1000
        capture(fetcher, url, WEBP_1X1)

    page.wait_for_timeout.side_effect = finish
    response = fetcher(url, asset)
    assert response["body"] == WEBP_1X1
    assert [a["reason"] for a in response["_paper_fetch_recovery_attempts"]] == [
        "cloudflare_challenge",
        "recovered",
    ]
    assert fetcher.failure_for(url) is None
    page.goto.assert_called_once_with(url, wait_until="commit", timeout=30000)
    assert fetcher._budget.snapshot()["reserved_bytes"] == 0
    fetcher.close()


def test_persistent_challenge_uses_shared_30_seconds_and_next_asset_survives(
    monkeypatch,
):
    from tests.support.wiley_page_assets import figure

    asset = figure(ROOT, 1)
    other = formula(ROOT + "/next.png")
    fetcher, page, clock = waiting_fetcher(monkeypatch, [asset, other])

    def navigate(url, **kwargs):
        page.url = url
        if url == other["url"]:
            capture(fetcher, url, WEBP_1X1)
        else:
            capture(
                fetcher,
                url,
                b"challenge",
                status=403,
                headers={"cf-mitigated": "challenge"},
            )

    page.goto.side_effect = navigate
    assert fetcher(asset["url"], asset) is None
    assert clock[0] == pytest.approx(130)
    assert fetcher.failure_for(asset["url"])["reason"] == "cloudflare_challenge"
    assert fetcher(asset["preview_url"], asset) is None
    skipped = fetcher.failure_for(asset["preview_url"])
    assert skipped["reason"] == "cloudflare_challenge"
    assert skipped["candidate_not_navigated"] and "status" not in skipped
    assert skipped["recovery_attempts"][0]["source_url"] == asset["url"]
    assert page.goto.call_count == 1
    assert fetcher(other["url"], other)["body"] == WEBP_1X1
    assert not fetcher._closed
    fetcher.close()


def test_plain_403_returns_early_leaving_time_for_preview(monkeypatch):
    from tests.support.wiley_page_assets import figure

    asset = figure(ROOT, 1)
    fetcher, page, clock = waiting_fetcher(monkeypatch, [asset])

    def navigate(url, **kwargs):
        page.url = url
        clock[0] += 2
        capture(
            fetcher,
            url,
            b"Forbidden" if url == asset["url"] else png_bytes(),
            status=403 if url == asset["url"] else 200,
        )

    page.goto.side_effect = navigate
    assert fetcher(asset["url"], asset) is None
    assert fetcher(asset["preview_url"], asset)
    assert page.goto.call_args.kwargs["timeout"] == 28000
    assert fetcher.failure_for(asset["url"])["status"] == 403
    fetcher.close()


def test_request_identity_and_redirect_chain_exclude_previous_navigation():
    asset = formula(ROOT + "/math.png")
    fetcher = fetcher_for([asset])
    page = fetcher._page = Mock()
    fetcher._active_url = asset["url"]

    def request(url, previous=None):
        return Mock(
            url=url,
            frame=page.main_frame,
            redirected_from=previous,
            is_navigation_request=lambda: True,
        )

    old = request(asset["url"])
    fetcher._track_request(old)
    fetcher._requests.clear()  # next candidate, even if a redirect reuses its URL
    late = request(asset["url"], old)
    fetcher._track_request(late)
    fetcher._capture(late)
    late.response.assert_not_called()
    current = request(asset["url"])
    fetcher._track_request(current)
    redirected = request(ROOT + "/actual.webp", current)
    fetcher._track_request(redirected)
    response = Mock(url=redirected.url, status=200)
    response.all_headers.return_value = {}
    response.body.return_value = WEBP_1X1
    redirected.response.return_value = response
    fetcher._capture(redirected)
    assert fetcher._responses[asset["url"]][0]["url"] == redirected.url
    page.url = asset["url"]
    assert fetcher._loaded_response(asset["url"]) is None
    page.url = redirected.url
    assert fetcher._loaded_response(asset["url"])["body"] == WEBP_1X1
    fetcher.close()


def test_initial_cookies_never_overwrite_updated_browser_state(monkeypatch):
    assets = [formula(ROOT + f"/{i}.png") for i in range(2)]
    fetcher = fetcher_for(assets)
    cookies = [
        {
            "name": "seed",
            "value": "old",
            "domain": "onlinelibrary.wiley.com",
            "path": "/",
        }
    ]
    fetcher._browser_context_seed_getter = lambda: {"browser_cookies": cookies}
    context = Mock()
    page = context.new_page.return_value
    factory = Mock(return_value=(None, None, context))
    monkeypatch.setattr(
        "paper_fetch.providers.browser_workflow.fetchers.context._new_browser_context",
        factory,
    )

    def navigate(url, **kwargs):
        page.url = url
        capture(fetcher, url, WEBP_1X1)

    page.goto.side_effect = navigate
    for asset in assets:
        assert fetcher(asset["url"], asset)
    factory.assert_called_once()
    context.new_page.assert_called_once()
    context.add_cookies.assert_called_once_with(cookies)
    fetcher.close()


def test_total_deadline_and_cancel_release_captured_bytes(monkeypatch):
    from paper_fetch.runtime import RuntimeContext

    asset = formula(ROOT + "/math.png")
    fetcher, page, clock = waiting_fetcher(monkeypatch, [asset])
    runtime = RuntimeContext(env={})
    fetcher._runtime_context = runtime
    runtime.deadline_monotonic = 100.2
    page.evaluate.return_value = False
    page.url = asset["url"]
    page.goto.side_effect = lambda *a, **kw: capture(fetcher, asset["url"], WEBP_1X1)
    try:
        assert fetcher(asset["url"], asset) is None
        assert fetcher._closed
        assert clock[0] == pytest.approx(100.2)
        assert fetcher._budget.snapshot()["reserved_bytes"] == 0
    finally:
        runtime.close()


def test_wrong_thread_cannot_operate_or_clear_session(monkeypatch):
    asset = formula(ROOT + "/math.png")
    fetcher = fetcher_for([asset])
    with monkeypatch.context() as patch:
        patch.setattr(
            "paper_fetch.providers._wiley_page_assets.threading.get_ident",
            lambda: fetcher._owner + 1,
        )
        with pytest.raises(RuntimeError, match="owning thread"):
            fetcher(asset["url"], asset)
        with pytest.raises(RuntimeError, match="owning thread"):
            fetcher.close()
    assert not fetcher._attempted and not fetcher._closed
    fetcher.close()
