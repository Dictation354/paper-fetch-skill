# ruff: noqa: F403,F405
from __future__ import annotations

from paper_fetch.providers import _ieee_asset_identity
from paper_fetch.providers import _ieee_asset_recovery
from paper_fetch.providers import _ieee_supplementary
from paper_fetch.providers.browser_workflow.asset_download import (
    BrowserAssetDownloadPlan,
    BrowserAssetRecoveryContext,
    run_browser_asset_download_attempt,
)
from tests.unit._atypon_browser_workflow_provider_support import png_header
from tests.unit._browser_workflow_deps import browser_workflow_deps

from ._ieee_provider_support import *


class IeeeProviderAssetDownloadTests(unittest.TestCase):
    def test_ieee_reconciliation_overlays_large_recovery_on_one_logical_figure(
        self,
    ) -> None:
        small = (
            "https://ieeexplore.ieee.org/mediastore/IEEE/content/media/"
            "19/10764799/10772041/gu1-3509573-small.gif?token=small"
        )
        large = (
            "https://ieeexplore.ieee.org/mediastore/IEEE/content/media/"
            "19/10764799/10772041/gu1-3509573-large.gif?token=large"
        )
        extracted = [
            {
                "kind": "figure",
                "heading": "Fig. 1",
                "caption": "Original logical caption.",
                "anchor_key": "fig1",
                "url": small,
            },
            {
                "kind": "figure",
                "heading": "Figure 1",
                "url": large,
            },
        ]
        downloaded = [
            {
                "kind": "figure",
                "heading": "Fig. 1",
                "source_url": small,
                "original_url": large,
                "download_url": small,
                "path": "/tmp/gu1-3509573-small.gif",
                "content_type": "image/gif",
                "width": 640,
                "height": 480,
                "download_tier": "preview",
                "downloaded_bytes": 4096,
                "preview_accepted": True,
                "browser_backend": "camoufox",
                "final_fetcher": "camoufox",
                "recovery_attempts": [
                    {"stage": "direct", "status": 403},
                    {"stage": "preview_fallback", "reason": "recovered"},
                ],
                "provenance": ["ieee_browser_recovery"],
                "asset_route": {
                    "host": "ieeexplore.ieee.org",
                    "route": "browser",
                    "probe": True,
                },
                "asset_timing": {
                    "candidate_resolution_ms": 1.25,
                    "browser_recovery_ms": 12.5,
                    "total_ms": 14.0,
                    "status": "downloaded",
                },
            }
        ]

        reconciled = _ieee_asset_identity.reconcile_ieee_downloaded_assets(
            extracted,
            downloaded,
        )

        self.assertEqual(len(reconciled), 1)
        figure = reconciled[0]
        self.assertEqual(figure["caption"], "Original logical caption.")
        self.assertEqual(figure["anchor_key"], "fig1")
        self.assertEqual(figure["path"], "/tmp/gu1-3509573-small.gif")
        self.assertEqual(figure["original_url"], large)
        self.assertTrue(figure["preview_accepted"])
        self.assertEqual(figure["browser_backend"], "camoufox")
        self.assertEqual(figure["final_fetcher"], "camoufox")
        self.assertEqual(figure["recovery_attempts"][0]["status"], 403)
        self.assertEqual(figure["asset_route"]["route"], "browser")
        self.assertEqual(figure["asset_timing"]["candidate_resolution_ms"], 1.25)
        self.assertEqual(
            _ieee_asset_identity.ieee_asset_identity_key({"url": small}),
            _ieee_asset_identity.ieee_asset_identity_key({"url": large}),
        )

    def test_ieee_article_seed_waits_for_matching_article_dom(self) -> None:
        class Page:
            def __init__(self) -> None:
                self.polls = 0

            def title(self) -> str:
                return "IEEE article" if self.polls >= 2 else ""

            def content(self) -> str:
                if self.polls < 2:
                    return (
                        "<html><head><script src='https://example.token.awswaf.com/"
                        "challenge.js'></script></head><body>"
                        "<div id='challenge-container'></div>"
                        "<noscript>JavaScript is disabled. Verify you're not a robot."
                        "</noscript></body></html>"
                    )
                return (
                    '<html><body><article id="article">10772041</article></body></html>'
                )

            def evaluate(self, *_args):
                return {
                    "articlePresent": self.polls >= 2,
                    "articleMatches": self.polls >= 2,
                    "restDocumentSeen": True,
                }

            def wait_for_timeout(self, _milliseconds: int) -> None:
                self.polls += 1

        class Context:
            pass

        page = Page()
        self.assertTrue(
            _ieee_asset_recovery._ieee_article_seed_page_is_ready(
                page,
                Context(),
                "https://ieeexplore.ieee.org/document/10772041/",
            )
        )
        self.assertEqual(page.polls, 2)

    def test_ieee_large_browser_recovery_warms_preview_before_full_size(self) -> None:
        preview_url = "https://ieeexplore.ieee.org/figure-small.png"
        large_url = "https://ieeexplore.ieee.org/figure-large.png"
        calls: list[str] = []
        preview_warmed = False

        class BrowserFetcher:
            browser_backend = "camoufox"
            requires_caller_thread = True

            def __call__(self, url, _asset):
                nonlocal preview_warmed
                calls.append(url)
                if url == preview_url:
                    preview_warmed = True
                if url == large_url and not preview_warmed:
                    return None
                return {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": png_header(640, 480),
                    "url": url,
                    "dimensions": {"width": 640, "height": 480},
                }

            def failure_for(self, _url):
                return None

            def close(self):
                return None

        fetcher = _ieee_asset_recovery._IeeePreviewWarmImageFetcher(
            _ieee_asset_recovery._MemoizedImageDocumentFetcher(BrowserFetcher())
        )
        transport = mock.Mock()
        transport.request.side_effect = RequestFailure(
            403,
            "forbidden",
            headers={"content-type": "text/html"},
            url=large_url,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_assets(
                html_assets.FIGURE_KIND,
                transport,
                article_id="10.1109/example",
                assets=[
                    {
                        "kind": "figure",
                        "heading": "Figure 1",
                        "url": preview_url,
                        "preview_url": preview_url,
                        "full_size_url": large_url,
                        "section": "body",
                    }
                ],
                output_dir=Path(tmpdir),
                user_agent="test-agent",
                asset_profile="body",
                options=html_assets.AssetDownloadOptions(
                    candidate_builder=lambda *_args, **_kwargs: [large_url],
                    image_document_fetcher=fetcher,
                    fetch_policy="direct_then_browser",
                ),
            )

        self.assertEqual(calls, [preview_url, large_url])
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["assets"][0]["download_tier"], "full_size")
        self.assertEqual(
            [attempt["stage"] for attempt in result["assets"][0]["recovery_attempts"]],
            ["direct", "browser"],
        )

    def test_ieee_preview_warm_occurs_once_for_thirteen_large_assets(self) -> None:
        calls: list[str] = []

        class BrowserFetcher:
            browser_backend = "camoufox"
            requires_caller_thread = True

            def __call__(self, url, _asset):
                calls.append(url)
                return {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": png_header(640, 480),
                    "url": url,
                }

            def failure_for(self, _url):
                return None

            def close(self):
                return None

        fetcher = _ieee_asset_recovery._IeeePreviewWarmImageFetcher(
            _ieee_asset_recovery._MemoizedImageDocumentFetcher(BrowserFetcher())
        )
        for index in range(13):
            preview_url = f"https://ieeexplore.ieee.org/figure-{index}-small.png"
            large_url = f"https://ieeexplore.ieee.org/figure-{index}-large.png"
            self.assertIsNotNone(
                fetcher(
                    large_url,
                    {
                        "url": preview_url,
                        "preview_url": preview_url,
                        "full_size_url": large_url,
                    },
                )
            )

        self.assertEqual(len(calls), 14)
        self.assertEqual(
            [url for url in calls if "-small.png" in url],
            ["https://ieeexplore.ieee.org/figure-0-small.png"],
        )

    def test_ieee_large_failure_reuses_warmed_preview_with_full_recovery_trace(
        self,
    ) -> None:
        preview_url = "https://ieeexplore.ieee.org/figure-small.png"
        large_url = "https://ieeexplore.ieee.org/figure-large.png"
        calls: list[str] = []

        class BrowserFetcher:
            browser_backend = "camoufox"
            requires_caller_thread = True

            def __call__(self, url, _asset):
                calls.append(url)
                if url == large_url:
                    return None
                return {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": png_header(640, 480),
                    "url": url,
                    "dimensions": {"width": 640, "height": 480},
                }

            def failure_for(self, url):
                if url != large_url:
                    return None
                return {
                    "source_url": url,
                    "status": 403,
                    "content_type": "text/html",
                    "reason": "image_fetch_error",
                }

            def close(self):
                return None

        image_fetcher = _ieee_asset_recovery._IeeePreviewWarmImageFetcher(
            _ieee_asset_recovery._MemoizedImageDocumentFetcher(BrowserFetcher())
        )
        transport = mock.Mock()
        transport.request.side_effect = RequestFailure(
            403,
            "forbidden",
            headers={"content-type": "text/html"},
            url=large_url,
        )
        asset = {
            "kind": "figure",
            "heading": "Figure 1",
            "url": preview_url,
            "preview_url": preview_url,
            "full_size_url": large_url,
            "section": "body",
        }
        recovery = BrowserAssetRecoveryContext(
            runtime=mock.Mock(backend="camoufox", headless=True),
            provider="ieee",
            user_agent="test-agent",
            browser_context_seed={},
            browser_cookies=[],
            active_seed_urls=["https://ieeexplore.ieee.org/document/123/"],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            plan = BrowserAssetDownloadPlan(
                article_id="10.1109/example",
                output_dir=Path(tmpdir),
                asset_profile="body",
                body_assets=[asset],
                supplementary_assets=[],
                fetch_policy="direct_then_browser",
                candidate_builder=lambda *_args, **_kwargs: [
                    large_url,
                    preview_url,
                ],
            )
            result = run_browser_asset_download_attempt(
                plan,
                recovery,
                image_fetcher_factory=mock.Mock(return_value=image_fetcher),
                file_fetcher_factory=mock.Mock(return_value=None),
                download_settings={
                    "transport": transport,
                    "asset_download_concurrency": 4,
                    "serial_browser_assets": True,
                },
                deps=browser_workflow_deps(),
            )

        self.assertEqual(calls, [preview_url, large_url])
        self.assertEqual(result.failures, [])
        self.assertEqual(len(result.body_results), 1)
        downloaded = result.body_results[0]
        self.assertEqual(downloaded["download_tier"], "preview")
        self.assertEqual(downloaded["browser_backend"], "camoufox")
        self.assertEqual(downloaded["final_fetcher"], "camoufox")
        self.assertEqual(
            [attempt["stage"] for attempt in downloaded["recovery_attempts"]],
            ["direct", "browser", "preview_fallback"],
        )
        self.assertEqual(downloaded["recovery_attempts"][0]["status"], 403)
        self.assertEqual(downloaded["recovery_attempts"][1]["status"], 403)

    def test_ieee_article_seed_rejects_challenge_even_with_article_dom(self) -> None:
        page = mock.Mock()
        page.title.return_value = "Just a moment..."
        page.content.return_value = (
            '<html><body><article id="article">10772041</article>'
            "Checking your browser before accessing IEEE Xplore.</body></html>"
        )
        page.locator.return_value.count.return_value = 1
        page.evaluate.return_value = False

        self.assertFalse(
            _ieee_asset_recovery._ieee_article_seed_page_is_ready(
                page,
                mock.Mock(),
                "https://ieeexplore.ieee.org/document/10772041/",
            )
        )

    def test_ieee_download_related_assets_body_profile_passes_figure_table_and_formula(
        self,
    ) -> None:
        doi = "10.1109/ACCESS.2024.3352924"
        article_number = "10388355"
        landing_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        rest_url = f"https://ieeexplore.ieee.org/rest/document/{article_number}/?logAccess=true"
        transport = RecordingTransport(
            {
                ("GET", landing_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": _landing_html(doi=doi, article_number=article_number),
                    "url": landing_url,
                },
                ("GET", rest_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": _dynamic_html_with_ieee_media_assets(article_number),
                    "url": rest_url,
                },
            }
        )
        client = IeeeClient(transport, {})
        raw_payload = client.fetch_raw_fulltext(
            doi, {"doi": doi, "landing_page_url": landing_url}
        )
        assert raw_payload.content is not None
        raw_payload.content.extracted_assets.append(
            {
                "kind": "formula",
                "heading": "Formula 1",
                "url": f"https://ieeexplore.ieee.org/mediastore/IEEE/content/media/{article_number}/{article_number}-formula-1.gif",
                "section": "body",
            }
        )
        raw_payload.content.merged_metadata["landing_page_url"] = (
            f"https://doi.org/{doi}"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(
                _ieee_supplementary,
                "download_assets",
                return_value={"assets": [], "asset_failures": []},
            ) as mocked_download:
                result = client.download_related_assets(
                    doi,
                    {"doi": doi, "landing_page_url": landing_url},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )

        self.assertEqual(result, {"assets": [], "asset_failures": []})
        self.assertEqual(mocked_download.call_count, 2)
        self.assertTrue(
            all(
                call.args[0] is _ieee_supplementary.FIGURE_KIND
                for call in mocked_download.call_args_list
            )
        )
        self.assertEqual(
            mocked_download.call_args_list[0].kwargs["options"].headers["Referer"],
            landing_url,
        )
        passed_assets = [
            asset
            for call in mocked_download.call_args_list
            for asset in call.kwargs["assets"]
        ]
        self.assertEqual(
            [item["kind"] for item in passed_assets],
            ["figure", "table", "formula"],
        )
        self.assertTrue(all(item["section"] == "body" for item in passed_assets))
        self.assertNotIn("supplementary", {item.get("kind") for item in passed_assets})

    def test_ieee_download_related_assets_all_profile_downloads_supplementary_files(
        self,
    ) -> None:
        doi = "10.1109/ACCESS.2024.3352924"
        article_number = "10388355"
        landing_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        rest_url = f"https://ieeexplore.ieee.org/rest/document/{article_number}/?logAccess=true"
        figure_large_url = f"https://ieeexplore.ieee.org/mediastore/IEEE/content/media/{article_number}/{article_number}-fig-1-large.gif"
        table_large_url = f"https://ieeexplore.ieee.org/mediastore/IEEE/content/media/{article_number}/{article_number}-table-1-large.gif"
        supplementary_pdf_url = (
            "https://ieeexplore.ieee.org/documents/supplementary.pdf"
        )
        supplementary_mp4_url = "https://ieeexplore.ieee.org/documents/multimedia.mp4"
        gif_payload = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        transport = RecordingTransport(
            {
                ("GET", landing_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": _landing_html(doi=doi, article_number=article_number),
                    "url": landing_url,
                },
                ("GET", rest_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": _dynamic_html_with_ieee_media_assets(article_number),
                    "url": rest_url,
                },
                ("GET", figure_large_url): {
                    "status_code": 200,
                    "headers": {"content-type": "image/gif"},
                    "body": gif_payload,
                    "url": figure_large_url,
                },
                ("GET", table_large_url): {
                    "status_code": 200,
                    "headers": {"content-type": "image/gif"},
                    "body": gif_payload,
                    "url": table_large_url,
                },
                ("GET", supplementary_pdf_url): {
                    "status_code": 200,
                    "headers": {"content-type": "application/pdf"},
                    "body": b"%PDF-1.7 supplementary",
                    "url": supplementary_pdf_url,
                },
                ("GET", supplementary_mp4_url): {
                    "status_code": 200,
                    "headers": {"content-type": "video/mp4"},
                    "body": b"\x00\x00\x00\x18ftypmp42supplementary-video",
                    "url": supplementary_mp4_url,
                },
            }
        )
        client = IeeeClient(transport, {})
        raw_payload = client.fetch_raw_fulltext(
            doi, {"doi": doi, "landing_page_url": landing_url}
        )
        self.assertEqual(
            raw_payload.content.markdown_text.count(
                f"{article_number}-fig-1-large.gif"
            ),
            1,
        )
        self.assertNotIn(
            f"{article_number}-fig-1-small.gif",
            raw_payload.content.markdown_text,
        )

        def opener_requester(opener, url, **kwargs):
            del opener
            headers = kwargs["headers"]
            self.assertEqual(headers["User-Agent"], client.user_agent)
            if url in {figure_large_url, table_large_url}:
                return {
                    "status_code": 200,
                    "headers": {"content-type": "image/gif"},
                    "body": gif_payload,
                    "url": url,
                }
            self.assertEqual(headers["Referer"], landing_url)
            if url == supplementary_pdf_url:
                return {
                    "status_code": 200,
                    "headers": {"content-type": "application/pdf"},
                    "body": b"%PDF-1.7 supplementary",
                    "url": url,
                }
            if url == supplementary_mp4_url:
                return {
                    "status_code": 200,
                    "headers": {"content-type": "video/mp4"},
                    "body": b"\x00\x00\x00\x18ftypmp42supplementary-video",
                    "url": url,
                }
            raise AssertionError(f"Unexpected supplementary request: {url}")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = client.download_related_assets(
                doi,
                {"doi": doi, "landing_page_url": landing_url},
                raw_payload,
                Path(tmpdir),
                asset_profile="all",
            )
            downloaded_paths_exist = all(
                Path(item["path"]).is_file() for item in result["assets"]
            )

        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(
            [item["kind"] for item in result["assets"]],
            ["figure", "table", "supplementary", "supplementary"],
        )
        self.assertEqual(result["assets"][2]["section"], "supplementary")
        self.assertEqual(result["assets"][2]["download_tier"], "supplementary_file")
        self.assertEqual(result["assets"][2]["content_type"], "application/pdf")
        self.assertEqual(result["assets"][3]["download_tier"], "supplementary_file")
        self.assertEqual(result["assets"][3]["content_type"], "video/mp4")
        self.assertTrue(downloaded_paths_exist)

    def test_ieee_download_related_assets_downloads_mediastore_gifs_without_support_icon_failure(
        self,
    ) -> None:
        """asset-download-contract: provider=ieee"""

        doi = "10.1109/ACCESS.2024.3352924"
        article_number = "10388355"
        landing_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        rest_url = f"https://ieeexplore.ieee.org/rest/document/{article_number}/?logAccess=true"
        figure_large_url = f"https://ieeexplore.ieee.org/mediastore/IEEE/content/media/{article_number}/{article_number}-fig-1-large.gif"
        table_large_url = f"https://ieeexplore.ieee.org/mediastore/IEEE/content/media/{article_number}/{article_number}-table-1-large.gif"
        gif_payload = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        transport = RecordingTransport(
            {
                ("GET", landing_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": _landing_html(doi=doi, article_number=article_number),
                    "url": landing_url,
                },
                ("GET", rest_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": _dynamic_html_with_ieee_media_assets(article_number),
                    "url": rest_url,
                },
                ("GET", figure_large_url): {
                    "status_code": 200,
                    "headers": {"content-type": "image/gif"},
                    "body": gif_payload,
                    "url": figure_large_url,
                },
                ("GET", table_large_url): {
                    "status_code": 200,
                    "headers": {"content-type": "image/gif"},
                    "body": gif_payload,
                    "url": table_large_url,
                },
            }
        )
        client = IeeeClient(transport, {})
        raw_payload = client.fetch_raw_fulltext(
            doi, {"doi": doi, "landing_page_url": landing_url}
        )

        def opener_requester(opener, url, **kwargs):
            del opener, kwargs
            if url in {figure_large_url, table_large_url}:
                return {
                    "status_code": 200,
                    "headers": {"content-type": "image/gif"},
                    "body": gif_payload,
                    "url": url,
                }
            raise AssertionError(f"Unexpected asset request: {url}")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = client.download_related_assets(
                doi,
                {"doi": doi, "landing_page_url": landing_url},
                raw_payload,
                Path(tmpdir),
                asset_profile="body",
                context=RuntimeContext(
                    env={"PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY": "1"}
                ),
            )
            self.assertTrue(
                all(Path(item["path"]).is_file() for item in result["assets"])
            )

        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(len(result["assets"]), 2)
        self.assertEqual(
            {item["kind"] for item in result["assets"]}, {"figure", "table"}
        )
        self.assertTrue(
            all(item["download_tier"] == "full_size" for item in result["assets"])
        )
        self.assertFalse(
            any(
                "/assets/img/icon.support.gif" in str(call["url"])
                for call in transport.calls
            )
        )
        article = client.to_article_model(
            {"doi": doi},
            raw_payload,
            downloaded_assets=result["assets"],
            asset_failures=result["asset_failures"],
        )
        body_article_assets = [
            asset for asset in article.assets if asset.kind in {"figure", "table"}
        ]
        self.assertEqual(len(body_article_assets), 2)
        self.assertTrue(all(asset.path for asset in body_article_assets))
        self.assertTrue(
            all(asset.download_tier == "full_size" for asset in body_article_assets)
        )

    def test_ieee_supplementary_download_failure_does_not_discard_body_assets(
        self,
    ) -> None:
        doi = "10.1109/ACCESS.2024.3352924"
        article_number = "10388355"
        landing_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        rest_url = f"https://ieeexplore.ieee.org/rest/document/{article_number}/?logAccess=true"
        figure_large_url = f"https://ieeexplore.ieee.org/mediastore/IEEE/content/media/{article_number}/{article_number}-fig-1-large.gif"
        table_large_url = f"https://ieeexplore.ieee.org/mediastore/IEEE/content/media/{article_number}/{article_number}-table-1-large.gif"
        supplementary_pdf_url = (
            "https://ieeexplore.ieee.org/documents/supplementary.pdf"
        )
        supplementary_mp4_url = "https://ieeexplore.ieee.org/documents/multimedia.mp4"
        gif_payload = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        transport = RecordingTransport(
            {
                ("GET", landing_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": _landing_html(doi=doi, article_number=article_number),
                    "url": landing_url,
                },
                ("GET", rest_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": _dynamic_html_with_ieee_media_assets(article_number),
                    "url": rest_url,
                },
                ("GET", figure_large_url): {
                    "status_code": 200,
                    "headers": {"content-type": "image/gif"},
                    "body": gif_payload,
                    "url": figure_large_url,
                },
                ("GET", table_large_url): {
                    "status_code": 200,
                    "headers": {"content-type": "image/gif"},
                    "body": gif_payload,
                    "url": table_large_url,
                },
                ("GET", supplementary_pdf_url): RequestFailure(
                    403,
                    "HTTP 403 for IEEE supplementary PDF",
                    body=b"<html>Access denied</html>",
                    headers={"content-type": "text/html; charset=utf-8"},
                    url=supplementary_pdf_url,
                ),
                ("GET", supplementary_mp4_url): RequestFailure(
                    403,
                    "HTTP 403 for IEEE supplementary video",
                    body=b"<html>Access denied</html>",
                    headers={"content-type": "text/html; charset=utf-8"},
                    url=supplementary_mp4_url,
                ),
            }
        )
        client = IeeeClient(transport, {})
        raw_payload = client.fetch_raw_fulltext(
            doi, {"doi": doi, "landing_page_url": landing_url}
        )

        challenge_html = {
            "status_code": 403,
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": (
                b"<html><head><title>Access denied</title></head>"
                b"<body>Please sign in to download this file.</body></html>"
            ),
            "url": "https://ieeexplore.ieee.org/documents/supplementary.pdf",
        }

        def opener_requester(opener, url, **kwargs):
            del opener, kwargs
            if url in {figure_large_url, table_large_url}:
                return {
                    "status_code": 200,
                    "headers": {"content-type": "image/gif"},
                    "body": gif_payload,
                    "url": url,
                }
            return {**challenge_html, "url": url}

        runtime_context = RuntimeContext(
            env={"PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY": "1"}
        )
        runtime_context.new_browser_context_for_runtime_config = mock.Mock(
            side_effect=RuntimeError("browser unavailable in unit test")
        )
        self.addCleanup(runtime_context.close)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = client.download_related_assets(
                doi,
                {"doi": doi, "landing_page_url": landing_url},
                raw_payload,
                Path(tmpdir),
                asset_profile="all",
                context=runtime_context,
            )

        self.assertEqual(
            [item["kind"] for item in result["assets"]], ["figure", "table"]
        )
        self.assertEqual(len(result["asset_failures"]), 2)
        self.assertTrue(
            all(item["kind"] == "supplementary" for item in result["asset_failures"])
        )
        self.assertTrue(all(item["reason"] for item in result["asset_failures"]))
        self.assertTrue(
            all(
                item["reason"] == "browser_context_error"
                and item["error_type"] == "RuntimeError"
                for item in result["asset_failures"]
            )
        )
        self.assertTrue(
            all("content_type" not in item for item in result["asset_failures"])
        )
        self.assertFalse(
            any(
                "/assets/img/icon.support.gif" in json.dumps(item)
                for item in result["asset_failures"]
            )
        )
        article = client.to_article_model(
            {"doi": doi},
            raw_payload,
            downloaded_assets=result["assets"],
            asset_failures=result["asset_failures"],
        )
        self.assertEqual(len(article.quality.asset_failures), 2)
