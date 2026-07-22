from __future__ import annotations

import base64
from dataclasses import FrozenInstanceError
from pathlib import Path
import threading
import tempfile
from types import SimpleNamespace
from unittest import TestCase, mock

from paper_fetch.extraction.html.assets import (
    FIGURE_KIND,
    SUPPLEMENTARY_KIND,
    browser_asset_recovery_allowed,
    download_assets,
)
from paper_fetch.http import RequestFailure
from paper_fetch.providers.browser_workflow import assets as browser_workflow_assets
from paper_fetch.providers.browser_workflow.fetchers import (
    image as browser_image_fetcher,
)
from paper_fetch.providers.browser_workflow.asset_download import (
    BrowserAssetDownloadPlan,
    BrowserAssetDownloadResult,
    BrowserAssetRecoveryContext,
    plan_browser_asset_download,
    retry_failed_browser_assets,
    run_browser_asset_download_attempt,
)
from tests.unit._atypon_browser_workflow_provider_support import png_header
from tests.unit._browser_workflow_deps import browser_workflow_deps


class BrowserWorkflowAssetDownloadTests(TestCase):
    def test_direct_then_browser_uses_direct_success_without_browser(self) -> None:
        url = "https://example.test/figure.png"
        transport = mock.Mock()
        transport.request.return_value = {
            "status_code": 200,
            "headers": {"content-type": "image/png"},
            "body": png_header(640, 480),
            "url": url,
        }
        browser_fetcher = mock.Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_assets(
                FIGURE_KIND,
                transport,
                article_id="10.1109/example",
                assets=[{"kind": "figure", "url": url, "heading": "Figure 1"}],
                output_dir=Path(tmpdir),
                user_agent="test-agent",
                asset_profile="body",
                image_document_fetcher=browser_fetcher,
                fetch_policy="direct_then_browser",
            )

        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(result["assets"][0]["final_fetcher"], "direct_http")
        transport.request.assert_called_once()
        browser_fetcher.assert_not_called()

    def test_direct_then_browser_recovers_401_403_and_html_challenge(self) -> None:
        url = "https://example.test/figure.png"
        for direct_response in (
            RequestFailure(
                401,
                "unauthorized",
                headers={"content-type": "text/html"},
                url=url,
            ),
            RequestFailure(
                403,
                "forbidden",
                headers={"content-type": "text/html"},
                url=url,
            ),
            {
                "status_code": 200,
                "headers": {"content-type": "text/html"},
                "body": b"<html><title>Access denied</title></html>",
                "url": url,
            },
        ):
            with self.subTest(direct_response=type(direct_response).__name__):
                transport = mock.Mock()
                if isinstance(direct_response, Exception):
                    transport.request.side_effect = direct_response
                else:
                    transport.request.return_value = direct_response
                browser_fetcher = mock.Mock(
                    return_value={
                        "status_code": 200,
                        "headers": {"content-type": "image/png"},
                        "body": png_header(640, 480),
                        "url": url,
                    }
                )
                browser_fetcher.browser_backend = "camoufox"

                with tempfile.TemporaryDirectory() as tmpdir:
                    result = download_assets(
                        FIGURE_KIND,
                        transport,
                        article_id="10.1109/example",
                        assets=[{"kind": "figure", "url": url, "heading": "Figure 1"}],
                        output_dir=Path(tmpdir),
                        user_agent="test-agent",
                        asset_profile="body",
                        image_document_fetcher=browser_fetcher,
                        fetch_policy="direct_then_browser",
                    )

                self.assertEqual(len(result["assets"]), 1)
                self.assertEqual(result["asset_failures"], [])
                self.assertEqual(
                    [
                        attempt["stage"]
                        for attempt in result["assets"][0]["recovery_attempts"]
                    ],
                    ["direct", "browser"],
                )
                self.assertEqual(
                    result["assets"][0]["browser_backend"], "camoufox"
                )
                self.assertEqual(
                    result["assets"][0]["final_fetcher"], "camoufox"
                )
                transport.request.assert_called_once()
                browser_fetcher.assert_called_once()

    def test_direct_then_browser_does_not_recover_404_410_or_429(self) -> None:
        for status in (404, 410, 429):
            with self.subTest(status=status):
                url = f"https://example.test/figure-{status}.png"
                transport = mock.Mock()
                transport.request.side_effect = RequestFailure(
                    status,
                    f"HTTP {status}",
                    headers={"content-type": "text/html"},
                    url=url,
                )
                browser_fetcher = mock.Mock()

                with tempfile.TemporaryDirectory() as tmpdir:
                    result = download_assets(
                        FIGURE_KIND,
                        transport,
                        article_id="10.1109/example",
                        assets=[{"kind": "figure", "url": url, "heading": "Figure 1"}],
                        output_dir=Path(tmpdir),
                        user_agent="test-agent",
                        asset_profile="body",
                        image_document_fetcher=browser_fetcher,
                        fetch_policy="direct_then_browser",
                    )

                self.assertEqual(result["assets"], [])
                self.assertEqual(len(result["asset_failures"]), 1)
                browser_fetcher.assert_not_called()

    def test_direct_then_browser_does_not_recover_invalid_scheme(self) -> None:
        browser_fetcher = mock.Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_assets(
                FIGURE_KIND,
                mock.Mock(),
                article_id="10.1109/example",
                assets=[
                    {
                        "kind": "figure",
                        "url": "file:///tmp/not-an-http-asset.png",
                        "heading": "Figure 1",
                    }
                ],
                output_dir=Path(tmpdir),
                user_agent="test-agent",
                asset_profile="body",
                image_document_fetcher=browser_fetcher,
                fetch_policy="direct_then_browser",
            )

        self.assertEqual(result["assets"], [])
        self.assertEqual(len(result["asset_failures"]), 1)
        browser_fetcher.assert_not_called()

    def test_direct_then_browser_falls_back_to_direct_preview_after_browser_failure(
        self,
    ) -> None:
        full_url = "https://example.test/figure-large.png"
        preview_url = "https://example.test/figure-preview.png"
        transport = mock.Mock()

        def direct_request(_method, url, **_kwargs):
            if url == full_url:
                raise RequestFailure(
                    403,
                    "forbidden",
                    headers={"content-type": "text/html"},
                    url=url,
                )
            self.assertEqual(url, preview_url)
            return {
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": png_header(320, 240),
                "url": url,
            }

        transport.request.side_effect = direct_request
        browser_fetcher = mock.Mock(return_value=None)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_assets(
                FIGURE_KIND,
                transport,
                article_id="10.1109/example",
                assets=[
                    {
                        "kind": "figure",
                        "url": preview_url,
                        "full_size_url": full_url,
                        "preview_url": preview_url,
                        "heading": "Figure 1",
                    }
                ],
                output_dir=Path(tmpdir),
                user_agent="test-agent",
                asset_profile="body",
                candidate_builder=lambda *_args, **_kwargs: [full_url, preview_url],
                image_document_fetcher=browser_fetcher,
                fetch_policy="direct_then_browser",
            )

        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(result["assets"][0]["download_tier"], "preview")
        self.assertEqual(result["assets"][0]["final_fetcher"], "direct_http")
        browser_fetcher.assert_called_once_with(full_url, mock.ANY)

    def test_direct_then_browser_uses_file_fetcher_for_supplementary(self) -> None:
        url = "https://example.test/supplement.mp4"
        transport = mock.Mock()
        transport.request.side_effect = RequestFailure(
            403,
            "forbidden",
            headers={"content-type": "text/html"},
            url=url,
        )
        file_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "video/mp4"},
                "body": b"\x00\x00\x00\x18ftypmp42supplementary-video",
                "url": url,
            }
        )
        file_fetcher.browser_backend = "camoufox"

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_assets(
                SUPPLEMENTARY_KIND,
                transport,
                article_id="10.1109/example",
                assets=[
                    {
                        "kind": "supplementary",
                        "source_url": url,
                        "heading": "Supplementary video",
                        "section": "supplementary",
                    }
                ],
                output_dir=Path(tmpdir),
                user_agent="test-agent",
                asset_profile="all",
                file_document_fetcher=file_fetcher,
                fetch_policy="direct_then_browser",
            )

        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(result["assets"][0]["content_type"], "video/mp4")
        self.assertEqual(result["assets"][0]["browser_backend"], "camoufox")
        file_fetcher.assert_called_once_with(url, mock.ANY)

    def test_browser_recovery_predicate_rejects_local_failures(self) -> None:
        for reason in (
            "Unsupported asset URL scheme for file:///tmp/asset.png",
            "image_conversion_failed: missing ghostscript",
            "invalid asset URL",
        ):
            with self.subTest(reason=reason):
                self.assertFalse(
                    browser_asset_recovery_allowed(status=None, reason=reason)
                )

        for error_category in (
            "network_error",
            "timeout",
            "tls_error",
            "dns_error",
            "connection_reset",
            "connection_closed",
        ):
            with self.subTest(error_category=error_category):
                self.assertTrue(
                    browser_asset_recovery_allowed(
                        status=None,
                        error_category=error_category,
                    )
                )

    def test_browser_workflow_image_candidates_prefer_download_url(self) -> None:
        download_url = "https://example.test/images/full-figure-from-download-url.jpg"
        full_size_url = "https://example.test/images/full-figure.jpg"
        preview_url = "https://example.test/skin/site/img/Blank.svg"

        candidates = (
            browser_workflow_assets._browser_workflow_image_download_candidates(
                None,
                asset={
                    "kind": "figure",
                    "download_url": download_url,
                    "full_size_url": full_size_url,
                    "url": preview_url,
                    "preview_url": preview_url,
                },
                user_agent="test-agent",
            )
        )

        self.assertEqual(candidates, [download_url, full_size_url, preview_url])

    def test_browser_image_payload_rejects_blank_placeholder_url(self) -> None:
        body = png_header(640, 480)
        payload = {
            "status": 200,
            "contentType": "image/png",
            "bodyB64": base64.b64encode(body).decode("ascii"),
            "url": "https://journals.ametsoc.org/skin/site/img/Blank.svg",
            "width": 2387,
            "height": 1153,
        }

        result = browser_image_fetcher._payload_from_browser_image_payload(
            payload,
            fallback_url="https://journals.ametsoc.org/view/journals/hydr/20/1/images/full-jhm-d-18-0159_1-f1.jpg",
        )

        self.assertIsNone(result)

    def test_plan_browser_asset_download_splits_assets_and_freezes_fields(self) -> None:
        figure_asset = {
            "kind": "figure",
            "heading": "Figure 1",
            "url": "https://example.test/figure.png",
            "section": "body",
        }
        supplementary_asset = {
            "kind": "supplementary",
            "heading": "Supplement",
            "source_url": "https://example.test/supplement.pdf",
            "section": "supplementary",
        }

        plan = plan_browser_asset_download(
            article_id="10.5555/example",
            output_dir=Path("/tmp/browser-assets"),
            html_text="<html></html>",
            source_url="https://example.test/article",
            profile={
                "asset_profile": "all",
                "assets": [figure_asset, supplementary_asset],
            },
            deps=browser_workflow_deps(),
        )

        self.assertIsInstance(plan, BrowserAssetDownloadPlan)
        self.assertEqual(plan.article_id, "10.5555/example")
        self.assertEqual(plan.asset_profile, "all")
        self.assertEqual(plan.body_assets, [figure_asset])
        self.assertEqual(plan.supplementary_assets, [supplementary_asset])
        with self.assertRaises(FrozenInstanceError):
            plan.article_id = "changed"  # type: ignore[misc]

    def test_run_browser_asset_download_attempt_injects_fetchers_and_patch_points(
        self,
    ) -> None:
        plan = BrowserAssetDownloadPlan(
            article_id="10.5555/example",
            output_dir=Path("/tmp/browser-assets"),
            asset_profile="all",
            body_assets=[
                {
                    "kind": "figure",
                    "heading": "Figure 1",
                    "url": "https://example.test/figure.png",
                    "section": "body",
                }
            ],
            supplementary_assets=[
                {
                    "kind": "supplementary",
                    "heading": "Supplement",
                    "source_url": "https://example.test/supplement.pdf",
                    "section": "supplementary",
                }
            ],
        )
        recovery = BrowserAssetRecoveryContext(
            runtime=SimpleNamespace(
                backend="cloakbrowser",
                headless=False,
                cdp_endpoint="ws://127.0.0.1:9222/devtools/browser/test",
            ),
            provider="science",
            user_agent="test-agent",
            browser_context_seed={
                "browser_cookies": [{"name": "sid", "value": "one"}],
                "browser_user_agent": "seed-agent",
                "browser_final_url": "https://example.test/final",
            },
            browser_cookies=[{"name": "sid", "value": "one"}],
            active_seed_urls=["https://example.test/article"],
        )
        image_fetcher = mock.Mock()
        image_fetcher.close = mock.Mock()
        file_fetcher = mock.Mock()
        file_fetcher.close = mock.Mock()
        image_fetcher_factory = mock.Mock(return_value=image_fetcher)
        file_fetcher_factory = mock.Mock(return_value=file_fetcher)
        opener_requester = mock.Mock()
        figure_page_fetcher_factory = mock.Mock(side_effect=lambda fetcher: fetcher)
        body_result = {
            "assets": [{"kind": "figure", "download_url": "figure.png"}],
            "asset_failures": [{"kind": "figure", "reason": "preview_failed"}],
        }
        supplementary_result = {
            "assets": [{"kind": "supplementary", "download_url": "supplement.pdf"}],
            "asset_failures": [],
        }

        mocked_download_assets = mock.Mock(
            side_effect=lambda kind, *_args, **_kwargs: (
                body_result if kind is FIGURE_KIND else supplementary_result
            )
        )
        deps = browser_workflow_deps(download_assets=mocked_download_assets)

        result = run_browser_asset_download_attempt(
            plan,
            recovery,
            image_fetcher_factory=image_fetcher_factory,
            file_fetcher_factory=file_fetcher_factory,
            opener_requester={
                "transport": object(),
                "asset_download_concurrency": 3,
                "figure_page_fetcher_factory": figure_page_fetcher_factory,
                "opener_requester": opener_requester,
            },
            deps=deps,
        )

        self.assertEqual(result.body_results, body_result["assets"])
        self.assertEqual(result.supplementary_results, supplementary_result["assets"])
        self.assertEqual(result.failures, body_result["asset_failures"])
        image_fetcher_factory.assert_called_once()
        file_fetcher_factory.assert_called_once()
        self.assertEqual(
            image_fetcher_factory.call_args.kwargs["attempt_body_assets"],
            plan.body_assets,
        )
        self.assertEqual(
            file_fetcher_factory.call_args.kwargs["attempt_supplementary_assets"],
            plan.supplementary_assets,
        )
        self.assertEqual(
            image_fetcher_factory.call_args.kwargs["cdp_endpoint"],
            "ws://127.0.0.1:9222/devtools/browser/test",
        )
        self.assertEqual(
            file_fetcher_factory.call_args.kwargs["cdp_endpoint"],
            "ws://127.0.0.1:9222/devtools/browser/test",
        )
        self.assertEqual(mocked_download_assets.call_count, 2)
        calls_by_kind = {
            call.args[0]: call for call in mocked_download_assets.call_args_list
        }
        figure_call = calls_by_kind[FIGURE_KIND]
        supplementary_call = calls_by_kind[SUPPLEMENTARY_KIND]
        self.assertIs(figure_call.args[0], FIGURE_KIND)
        self.assertIs(figure_call.kwargs["image_document_fetcher"], image_fetcher)
        self.assertEqual(figure_call.kwargs["asset_download_concurrency"], 3)
        self.assertEqual(
            figure_call.kwargs["browser_context_seed"],
            {
                "browser_cookies": [
                    {
                        "name": "sid",
                        "value": "one",
                        "url": "https://example.test/final",
                    }
                ],
                "browser_user_agent": "seed-agent",
                "browser_final_url": "https://example.test/final",
            },
        )
        self.assertEqual(
            figure_call.kwargs["seed_urls"],
            ["https://example.test/article", "https://example.test/final"],
        )
        self.assertEqual(
            figure_call.kwargs["headers"],
            {"Referer": "https://example.test/final"},
        )
        self.assertEqual(figure_call.kwargs["user_agent"], "test-agent")
        self.assertIs(supplementary_call.args[0], SUPPLEMENTARY_KIND)
        self.assertIs(
            supplementary_call.kwargs["file_document_fetcher"],
            file_fetcher,
        )
        self.assertIs(
            supplementary_call.kwargs["opener_requester"],
            opener_requester,
        )
        self.assertEqual(
            supplementary_call.kwargs["seed_urls"],
            ["https://example.test/article", "https://example.test/final"],
        )
        self.assertEqual(
            supplementary_call.kwargs["headers"],
            {"Referer": "https://example.test/final"},
        )
        image_fetcher.close.assert_called_once()
        file_fetcher.close.assert_called_once()

    def test_camoufox_http_assets_reuse_generated_firefox_user_agent(self) -> None:
        plan = BrowserAssetDownloadPlan(
            article_id="10.5555/example",
            output_dir=Path("/tmp/browser-assets"),
            asset_profile="body",
            body_assets=[
                {
                    "kind": "figure",
                    "url": "https://example.test/figure.png",
                    "section": "body",
                }
            ],
            supplementary_assets=[],
        )
        recovery = BrowserAssetRecoveryContext(
            runtime=SimpleNamespace(backend="camoufox", headless=True),
            provider="annualreviews",
            user_agent="Chrome fallback",
            browser_context_seed={
                "browser_user_agent": "Mozilla/5.0 Firefox/152.0",
                "browser_final_url": "https://example.test/article",
            },
            browser_cookies=[],
            active_seed_urls=["https://example.test/article"],
        )
        download_assets = mock.Mock(return_value={"assets": [], "asset_failures": []})

        run_browser_asset_download_attempt(
            plan,
            recovery,
            image_fetcher_factory=mock.Mock(return_value=None),
            file_fetcher_factory=mock.Mock(return_value=None),
            opener_requester={"transport": object()},
            deps=browser_workflow_deps(download_assets=download_assets),
        )

        self.assertEqual(
            download_assets.call_args.kwargs["user_agent"],
            "Mozilla/5.0 Firefox/152.0",
        )

    def test_run_browser_asset_download_attempt_parallelizes_body_and_supplementary(
        self,
    ) -> None:
        plan = BrowserAssetDownloadPlan(
            article_id="10.5555/example",
            output_dir=Path("/tmp/browser-assets"),
            asset_profile="all",
            body_assets=[
                {
                    "kind": "figure",
                    "heading": "Figure 1",
                    "url": "https://example.test/figure.png",
                    "section": "body",
                }
            ],
            supplementary_assets=[
                {
                    "kind": "supplementary",
                    "heading": "Supplement",
                    "source_url": "https://example.test/supplement.pdf",
                    "section": "supplementary",
                }
            ],
        )
        recovery = BrowserAssetRecoveryContext(
            runtime=SimpleNamespace(backend="cloakbrowser", headless=True),
            provider="science",
            user_agent="test-agent",
            browser_context_seed={"browser_final_url": "https://example.test/final"},
            browser_cookies=[],
            active_seed_urls=["https://example.test/article"],
        )
        body_started = threading.Event()
        supplementary_started = threading.Event()

        def download_assets(kind, *_args, **_kwargs):
            if kind is FIGURE_KIND:
                body_started.set()
                self.assertTrue(supplementary_started.wait(1))
                return {
                    "assets": [{"kind": "figure", "download_url": "figure.png"}],
                    "asset_failures": [],
                }
            supplementary_started.set()
            self.assertTrue(body_started.wait(1))
            return {
                "assets": [{"kind": "supplementary", "download_url": "supplement.pdf"}],
                "asset_failures": [],
            }

        result = run_browser_asset_download_attempt(
            plan,
            recovery,
            image_fetcher_factory=mock.Mock(return_value=None),
            file_fetcher_factory=mock.Mock(return_value=None),
            opener_requester={},
            deps=browser_workflow_deps(download_assets=download_assets),
        )

        self.assertEqual(
            result.body_results,
            [{"kind": "figure", "download_url": "figure.png"}],
        )
        self.assertEqual(
            result.supplementary_results,
            [{"kind": "supplementary", "download_url": "supplement.pdf"}],
        )

    def test_run_browser_asset_download_attempt_serializes_browser_assets_when_requested(
        self,
    ) -> None:
        plan = BrowserAssetDownloadPlan(
            article_id="10.5555/example",
            output_dir=Path("/tmp/browser-assets"),
            asset_profile="all",
            body_assets=[
                {
                    "kind": "figure",
                    "heading": "Figure 1",
                    "url": "https://example.test/figure.png",
                    "section": "body",
                }
            ],
            supplementary_assets=[
                {
                    "kind": "supplementary",
                    "heading": "Supplement",
                    "source_url": "https://example.test/supplement.pdf",
                    "section": "supplementary",
                }
            ],
        )
        recovery = BrowserAssetRecoveryContext(
            runtime=SimpleNamespace(backend="cloakbrowser", headless=True),
            provider="science",
            user_agent="test-agent",
            browser_context_seed={"browser_final_url": "https://example.test/final"},
            browser_cookies=[],
            active_seed_urls=["https://example.test/article"],
        )
        call_order: list[object] = []

        def download_assets(kind, *_args, **_kwargs):
            call_order.append(kind)
            if kind is FIGURE_KIND:
                return {
                    "assets": [{"kind": "figure", "download_url": "figure.png"}],
                    "asset_failures": [],
                }
            self.assertEqual(call_order, [FIGURE_KIND, SUPPLEMENTARY_KIND])
            return {
                "assets": [{"kind": "supplementary", "download_url": "supplement.pdf"}],
                "asset_failures": [],
            }

        result = run_browser_asset_download_attempt(
            plan,
            recovery,
            image_fetcher_factory=mock.Mock(return_value=None),
            file_fetcher_factory=mock.Mock(return_value=None),
            opener_requester={"serial_browser_assets": True},
            deps=browser_workflow_deps(download_assets=download_assets),
        )

        self.assertEqual(call_order, [FIGURE_KIND, SUPPLEMENTARY_KIND])
        self.assertEqual(
            result.body_results,
            [{"kind": "figure", "download_url": "figure.png"}],
        )
        self.assertEqual(
            result.supplementary_results,
            [{"kind": "supplementary", "download_url": "supplement.pdf"}],
        )

    def test_run_browser_asset_download_attempt_serializes_caller_thread_fetchers(
        self,
    ) -> None:
        plan = BrowserAssetDownloadPlan(
            article_id="10.5555/example",
            output_dir=Path("/tmp/browser-assets"),
            asset_profile="all",
            body_assets=[
                {
                    "kind": "figure",
                    "heading": "Figure 1",
                    "url": "https://example.test/figure.png",
                    "section": "body",
                }
            ],
            supplementary_assets=[
                {
                    "kind": "supplementary",
                    "heading": "Supplement",
                    "source_url": "https://example.test/supplement.pdf",
                    "section": "supplementary",
                }
            ],
        )
        recovery = BrowserAssetRecoveryContext(
            runtime=SimpleNamespace(backend="cloakbrowser", headless=True),
            provider="science",
            user_agent="test-agent",
            browser_context_seed={"browser_final_url": "https://example.test/final"},
            browser_cookies=[],
            active_seed_urls=["https://example.test/article"],
        )
        main_thread_id = threading.get_ident()
        call_order: list[object] = []
        image_fetcher = mock.Mock()
        image_fetcher.requires_caller_thread = True

        def download_assets(kind, *_args, **_kwargs):
            self.assertEqual(threading.get_ident(), main_thread_id)
            call_order.append(kind)
            if kind is FIGURE_KIND:
                return {
                    "assets": [{"kind": "figure", "download_url": "figure.png"}],
                    "asset_failures": [],
                }
            self.assertEqual(call_order, [FIGURE_KIND, SUPPLEMENTARY_KIND])
            return {
                "assets": [{"kind": "supplementary", "download_url": "supplement.pdf"}],
                "asset_failures": [],
            }

        result = run_browser_asset_download_attempt(
            plan,
            recovery,
            image_fetcher_factory=mock.Mock(return_value=image_fetcher),
            file_fetcher_factory=mock.Mock(return_value=None),
            opener_requester={},
            deps=browser_workflow_deps(download_assets=download_assets),
        )

        self.assertEqual(call_order, [FIGURE_KIND, SUPPLEMENTARY_KIND])
        self.assertEqual(
            result.body_results,
            [{"kind": "figure", "download_url": "figure.png"}],
        )
        self.assertEqual(
            result.supplementary_results,
            [{"kind": "supplementary", "download_url": "supplement.pdf"}],
        )

    def test_direct_then_browser_keeps_direct_concurrency_and_browser_on_caller_thread(
        self,
    ) -> None:
        figure_url = "https://example.test/figure.png"
        figure = {
            "kind": "figure",
            "heading": "Figure 1",
            "url": figure_url,
            "section": "body",
        }
        plan = BrowserAssetDownloadPlan(
            article_id="10.1109/example",
            output_dir=Path("/tmp/browser-assets"),
            asset_profile="body",
            body_assets=[figure],
            supplementary_assets=[],
            fetch_policy="direct_then_browser",
            candidate_builder=lambda *_args, **_kwargs: [figure_url],
        )
        recovery = BrowserAssetRecoveryContext(
            runtime=SimpleNamespace(backend="camoufox", headless=True),
            provider="ieee",
            user_agent="test-agent",
            browser_context_seed={},
            browser_cookies=[],
            active_seed_urls=["https://example.test/article"],
        )
        image_fetcher = mock.Mock()
        image_fetcher.requires_caller_thread = True
        image_fetcher.close = mock.Mock()
        main_thread_id = threading.get_ident()
        calls: list[dict[str, object]] = []

        def mocked_download_assets(_kind, *_args, **kwargs):
            self.assertEqual(threading.get_ident(), main_thread_id)
            calls.append(kwargs)
            if len(calls) == 1:
                return {
                    "assets": [],
                    "asset_failures": [
                        {
                            "kind": "figure",
                            "heading": "Figure 1",
                            "source_url": figure_url,
                            "section": "body",
                            "status": 403,
                            "content_type": "text/html",
                            "reason": "cloudflare_challenge",
                        }
                    ],
                }
            return {
                "assets": [
                    {
                        **figure,
                        "download_url": figure_url,
                        "source_url": figure_url,
                        "content_type": "image/png",
                        "browser_backend": "camoufox",
                        "final_fetcher": "camoufox",
                    }
                ],
                "asset_failures": [],
            }

        result = run_browser_asset_download_attempt(
            plan,
            recovery,
            image_fetcher_factory=mock.Mock(return_value=image_fetcher),
            file_fetcher_factory=mock.Mock(return_value=None),
            opener_requester={
                "transport": object(),
                "asset_download_concurrency": 4,
                "serial_browser_assets": True,
            },
            deps=browser_workflow_deps(download_assets=mocked_download_assets),
        )

        self.assertEqual(len(calls), 2)
        self.assertIsNone(calls[0]["image_document_fetcher"])
        self.assertEqual(calls[0]["asset_download_concurrency"], 4)
        self.assertEqual(calls[0]["fetch_policy"], "direct_then_browser")
        self.assertIs(calls[1]["image_document_fetcher"], image_fetcher)
        self.assertEqual(calls[1]["asset_download_concurrency"], 1)
        self.assertEqual(calls[1]["fetch_policy"], "browser_first")
        self.assertEqual(
            [attempt["stage"] for attempt in result.body_results[0]["recovery_attempts"]],
            ["direct", "browser"],
        )
        image_fetcher.close.assert_called_once()

    def test_browser_workflow_asset_retry_policy_skips_deterministic_failures(
        self,
    ) -> None:
        asset = {
            "kind": "figure",
            "heading": "Figure 1",
            "url": "https://example.test/figure.png",
            "section": "body",
        }

        self.assertEqual(
            browser_workflow_assets._assets_matching_download_failures(
                [asset],
                [
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "source_url": "https://example.test/figure.png",
                        "section": "body",
                        "status": 404,
                        "reason": "not_found",
                    }
                ],
                retry_scope="body",
            ),
            [],
        )
        self.assertEqual(
            browser_workflow_assets._assets_matching_download_failures(
                [asset],
                [
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "source_url": "https://example.test/figure.png",
                        "section": "body",
                        "status": 404,
                        "reason": "image_fetch_error",
                    }
                ],
                retry_scope="body",
            ),
            [],
        )
        self.assertEqual(
            browser_workflow_assets._assets_matching_download_failures(
                [asset],
                [
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "source_url": "https://example.test/figure.png",
                        "section": "body",
                        "reason": "non_image_response",
                    }
                ],
                retry_scope="body",
            ),
            [],
        )

    def test_browser_workflow_asset_retry_policy_keeps_transient_failures(
        self,
    ) -> None:
        asset = {
            "kind": "figure",
            "heading": "Figure 1",
            "url": "https://example.test/figure.png",
            "section": "body",
        }

        self.assertEqual(
            browser_workflow_assets._assets_matching_download_failures(
                [asset],
                [
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "source_url": "https://example.test/figure.png",
                        "section": "body",
                        "reason": "image_fetch_timeout",
                    }
                ],
                retry_scope="body",
            ),
            [asset],
        )
        self.assertEqual(
            browser_workflow_assets._assets_matching_download_failures(
                [asset],
                [
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "source_url": "https://example.test/figure.png",
                        "section": "body",
                        "status": 403,
                        "reason": "cloudflare_challenge",
                    }
                ],
                retry_scope="body",
            ),
            [asset],
        )

    def test_retry_failed_browser_assets_retries_matching_failures_and_merges(
        self,
    ) -> None:
        failed_figure = {
            "kind": "figure",
            "heading": "Figure 1",
            "url": "https://example.test/figure1.png",
            "section": "body",
        }
        saved_figure = {
            "kind": "figure",
            "heading": "Figure 2",
            "url": "https://example.test/figure2.png",
            "section": "body",
        }
        supplementary_asset = {
            "kind": "supplementary",
            "heading": "Supplement",
            "source_url": "https://example.test/supplement.pdf",
            "section": "supplementary",
        }
        plan = BrowserAssetDownloadPlan(
            article_id="10.5555/example",
            output_dir=Path("/tmp/browser-assets"),
            asset_profile="all",
            body_assets=[failed_figure, saved_figure],
            supplementary_assets=[supplementary_asset],
        )
        previous = BrowserAssetDownloadResult(
            body_results=[
                {
                    "kind": "figure",
                    "heading": "Figure 2",
                    "download_url": "https://example.test/figure2.png",
                    "section": "body",
                }
            ],
            supplementary_results=[
                {
                    "kind": "supplementary",
                    "heading": "Supplement",
                    "download_url": "https://example.test/supplement.pdf",
                    "section": "supplementary",
                }
            ],
            failures=[
                {
                    "kind": "figure",
                    "heading": "Figure 1",
                    "source_url": "https://example.test/figure1.png",
                    "section": "body",
                    "reason": "cloudflare_challenge",
                }
            ],
        )
        recovery = BrowserAssetRecoveryContext(
            runtime=SimpleNamespace(backend="cloakbrowser", headless=True),
            provider="pnas",
            user_agent="test-agent",
            browser_context_seed={"browser_final_url": "https://example.test/article"},
            browser_cookies=[],
            active_seed_urls=["https://example.test/article"],
        )
        retry_body_result = {
            "assets": [
                {
                    "kind": "figure",
                    "heading": "Figure 1",
                    "download_url": "https://example.test/figure1.png",
                    "section": "body",
                }
            ],
            "asset_failures": [],
        }

        mocked_warm = mock.Mock(
            return_value={"browser_final_url": "https://example.test/refreshed"}
        )
        mocked_download_assets = mock.Mock(return_value=retry_body_result)
        deps = browser_workflow_deps(
            refresh_browser_context_seed=mocked_warm,
            download_assets=mocked_download_assets,
        )

        result = retry_failed_browser_assets(
            plan,
            previous,
            recovery,
            image_fetcher_factory=mock.Mock(return_value=None),
            file_fetcher_factory=mock.Mock(return_value=None),
            opener_requester={"transport": object()},
            deps=deps,
        )

        mocked_warm.assert_called_once()
        mocked_download_assets.assert_called_once()
        self.assertIs(mocked_download_assets.call_args.args[0], FIGURE_KIND)
        self.assertEqual(
            mocked_download_assets.call_args.kwargs["assets"], [failed_figure]
        )
        self.assertEqual(
            sorted(asset["download_url"] for asset in result.body_results),
            [
                "https://example.test/figure1.png",
                "https://example.test/figure2.png",
            ],
        )
        self.assertEqual(
            [asset["download_url"] for asset in result.supplementary_results],
            ["https://example.test/supplement.pdf"],
        )
        self.assertEqual(result.failures, [])

    def test_retry_failed_browser_assets_skips_refresh_without_runtime(self) -> None:
        failed_figure = {
            "kind": "figure",
            "heading": "Figure 1",
            "url": "https://example.test/figure1.png",
            "section": "body",
        }
        plan = BrowserAssetDownloadPlan(
            article_id="10.5555/example",
            output_dir=Path("/tmp/browser-assets"),
            asset_profile="all",
            body_assets=[failed_figure],
            supplementary_assets=[],
        )
        previous = BrowserAssetDownloadResult(
            body_results=[],
            supplementary_results=[],
            failures=[
                {
                    "kind": "figure",
                    "heading": "Figure 1",
                    "source_url": "https://example.test/figure1.png",
                    "section": "body",
                    "reason": "image_conversion_failed: missing ghostscript",
                }
            ],
        )
        recovery = BrowserAssetRecoveryContext(
            runtime=None,
            provider="ams",
            user_agent="test-agent",
            browser_context_seed={
                "browser_final_url": "https://example.test/article",
                "paper_fetch_html_fetcher": "direct_http",
            },
            browser_cookies=[],
            active_seed_urls=["https://example.test/article"],
        )
        mocked_warm = mock.Mock()
        mocked_download_assets = mock.Mock()
        deps = browser_workflow_deps(
            refresh_browser_context_seed=mocked_warm,
            download_assets=mocked_download_assets,
        )

        result = retry_failed_browser_assets(
            plan,
            previous,
            recovery,
            image_fetcher_factory=mock.Mock(return_value=None),
            file_fetcher_factory=mock.Mock(return_value=None),
            opener_requester={"transport": object()},
            deps=deps,
        )

        self.assertIs(result, previous)
        mocked_warm.assert_not_called()
        mocked_download_assets.assert_not_called()
