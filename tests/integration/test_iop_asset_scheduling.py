"""IOP download owner: parallel HTTP and browser operations on its caller thread."""

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from paper_fetch.http import RequestCancelledError, RequestFailure
from paper_fetch.providers.browser_workflow.asset_download import (
    BrowserAssetDownloadPlan,
    BrowserAssetRecoveryContext,
    run_browser_asset_download_attempt,
)
from paper_fetch.runtime import RuntimeContext
from paper_fetch.providers.browser_workflow import asset_download as download_owner
from paper_fetch.asset_budget import AssetBudget
from tests.support._atypon_browser_workflow_provider_support import png_header
from tests.support._browser_workflow_deps import browser_workflow_deps
from tests.support._paper_fetch_support import RecordingTransport, http_response


@pytest.mark.parametrize(
    "mode", ["http", "recover", "multihost", "browser_failure", "cancel"]
)
def test_iop_overlaps_first_two_downloads_and_recovers_on_owner(
    tmp_path, mode, monkeypatch
):
    owner = threading.get_ident()
    barrier = threading.Barrier(2, timeout=5)
    first_started = threading.Event()
    browser_active = threading.Event()
    cancelled = threading.Event()
    calls = []
    browser_calls = []
    lock = threading.Lock()
    image = png_header(640, 480)

    class AuditedExecutor(ThreadPoolExecutor):
        def submit(self, *args, **kwargs):
            assert not browser_active.is_set(), (
                "new HTTP task submitted during browser recovery"
            )
            return super().submit(*args, **kwargs)

    monkeypatch.setattr(download_owner, "ThreadPoolExecutor", AuditedExecutor)
    urls = [f"https://cdn.example.test/figure{n}_hr.png" for n in range(4)]
    if mode == "multihost":
        urls[2] = "https://other.example.test/figure2_hr.png"

    class Transport(RecordingTransport):
        def request(self, method, url, **kwargs):
            assert threading.get_ident() != owner
            with lock:
                calls.append(url)
            if url == urls[0]:
                first_started.set()
                barrier.wait()
            elif url == urls[1]:
                assert first_started.wait(5)
                barrier.wait()
            if mode == "cancel" and url == urls[0]:
                cancelled.set()
                raise RequestCancelledError("cancelled")
            if mode != "http" and url in urls[:2]:
                raise RequestFailure(403, "Forbidden", url=url)
            return http_response(url, body=image, content_type="image/png")

    def fetch_image(url, _asset):
        assert threading.get_ident() == owner
        browser_active.set()
        try:
            browser_calls.append(url)
            assert mode not in {"http", "cancel"}
            if mode == "browser_failure":
                return {
                    "status_code": 403,
                    "body": b"Forbidden",
                    "headers": {"content-type": "text/html"},
                    "url": url,
                }
            return http_response(url, body=image, content_type="image/png")
        finally:
            browser_active.clear()

    fetch_image.requires_caller_thread = True
    fetch_image.close = mock.Mock()
    assets = [
        dict(
            kind="figure",
            heading=f"Figure {n}",
            source_ref=f"f{n}",
            url=url,
            original_url=url,
            full_size_url=url,
            section="body",
        )
        for n, url in enumerate(urls)
    ]
    plan = BrowserAssetDownloadPlan(
        article_id="10.1088/test",
        output_dir=tmp_path,
        asset_profile="body",
        body_assets=assets,
        supplementary_assets=[],
        candidate_builder=lambda *_a, asset, **_k: [asset["original_url"]],
        figure_page_discovery=False,
        preview_fallback=False,
    )
    with RuntimeContext(env={}, cancel_check=cancelled.is_set) as context:
        recovery = BrowserAssetRecoveryContext(
            runtime=SimpleNamespace(backend="camoufox", headless=True),
            provider="iop",
            user_agent="test",
            browser_context_seed={},
            browser_cookies=[],
            active_seed_urls=[],
            runtime_context=context,
        )

        def run():
            return run_browser_asset_download_attempt(
                plan,
                recovery,
                image_fetcher_factory=lambda **_k: fetch_image,
                file_fetcher_factory=lambda **_k: None,
                download_settings={
                    "transport": Transport({}),
                    "asset_download_concurrency": 4,
                    "serial_browser_assets": True,
                },
                deps=browser_workflow_deps(),
            )

        if mode == "cancel":
            with pytest.raises(RequestCancelledError):
                run()
            assert not list(tmp_path.rglob("*.png"))
            assert not list(tmp_path.rglob("*.part"))
            assert context.asset_budget.cancelled
        else:
            result = run()
            if mode == "browser_failure":
                assert len(result.failures) == 2
                assert all(
                    [attempt["stage"] for attempt in failure["recovery_attempts"]]
                    == ["direct", "browser"]
                    for failure in result.failures
                )
                assert len(result.body_results) == 2
                assert set(calls) == set(urls)
            else:
                assert not result.failures
                assert [a["source_ref"] for a in result.body_results] == [
                    f"f{n}" for n in range(4)
                ]
                for asset in result.body_results:
                    assert Path(asset["path"]).read_bytes() == image
                    assert asset["width"] == 640 and asset["height"] == 480
                if mode == "http":
                    assert set(calls) == set(urls) and not browser_calls
                else:
                    assert set(calls) == set(
                        urls[:2] + ([urls[2]] if mode == "multihost" else [])
                    )
                    assert urls[3] in browser_calls
                    assert (
                        result.body_results[0]["recovery_attempts"][0]["stage"]
                        == "direct"
                    )
                    assert result.body_results[3]["asset_timing"]["queue_ms"] > 0
    fetch_image.close.assert_called_once()


@pytest.mark.parametrize("max_files", [1, None])
def test_iop_scheduler_respects_budget_and_route_caps(tmp_path, max_files):
    active = 0
    peak = 0
    lock = threading.Lock()
    calls = []
    image = png_header(640, 480)
    budget = AssetBudget(max_files=max_files, max_concurrency=1)

    class Transport(RecordingTransport):
        def request(self, method, url, **kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                calls.append(url)
            try:
                return http_response(url, body=image, content_type="image/png")
            finally:
                with lock:
                    active -= 1

    assets = [
        dict(
            kind="figure",
            source_ref=f"f{i}",
            heading=f"Figure {i}",
            url=f"https://cdn.example.test/{i}.png",
            section="body",
        )
        for i in range(4)
    ]
    plan = BrowserAssetDownloadPlan(
        article_id="10.1088/test",
        output_dir=tmp_path,
        asset_profile="body",
        body_assets=assets,
        supplementary_assets=[],
        candidate_builder=lambda *_a, asset, **_k: [asset["url"]],
        figure_page_discovery=False,
        preview_fallback=False,
    )
    with RuntimeContext(env={}, asset_budget=budget) as context:
        result = run_browser_asset_download_attempt(
            plan,
            BrowserAssetRecoveryContext(
                runtime=None,
                provider="iop",
                user_agent="test",
                browser_context_seed={},
                browser_cookies=[],
                active_seed_urls=[],
                runtime_context=context,
            ),
            image_fetcher_factory=lambda **_k: None,
            file_fetcher_factory=lambda **_k: None,
            download_settings={
                "transport": Transport({}),
                "asset_download_concurrency": 4,
            },
            deps=browser_workflow_deps(),
        )
    assert peak == 1
    assert len(result.body_results) == (1 if max_files == 1 else 4)
    assert len(calls) == len(result.body_results)
    if max_files == 1:
        assert result.body_results[0]["source_ref"] == "f0"
        assert [failure["source_ref"] for failure in result.failures] == [
            "f1",
            "f2",
            "f3",
        ]
        assert all(
            failure["reason"] == "asset_file_limit_exceeded"
            for failure in result.failures
        )
    assert budget.snapshot()["reserved_files"] == 0
