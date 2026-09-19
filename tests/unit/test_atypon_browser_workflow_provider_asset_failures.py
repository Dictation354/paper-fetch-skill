from __future__ import annotations
from paper_fetch.providers.browser_workflow import fetchers as browser_fetchers
from tests.support._atypon_browser_workflow_provider_support import *
# ruff: noqa: F403,F405


class AtyponBrowserWorkflowProviderAssetFailureTests(
    AtyponBrowserWorkflowProviderTestCase
):
    def test_science_svg_payload_storage_contract(self) -> None:
        svg_url = (
            "https://www.science.org/cms/10.1126/science.adz3492/asset/"
            "5b0bd6a0-ee3b-43af-aff8-6d8423ba4e21/assets/graphic/science.adz3492-f1.svg"
        )
        # Small protocol input; the original SVG now has its own golden replay.
        svg_body = b'<svg xmlns="http://www.w3.org/2000/svg" width="696" height="1069"><rect width="1" height="1"/></svg>'
        self.assertEqual(image_mime_type_from_bytes(svg_body), "image/svg+xml")

        asset = {
            "kind": "figure",
            "heading": "Inequalities in final energy consumption",
            "caption": "Area chart of final energy consumption distribution.",
            "url": svg_url,
            "preview_url": svg_url,
            "section": "body",
        }
        fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/svg+xml"},
                "body": svg_body,
                "url": svg_url,
                "dimensions": {"width": 696, "height": 1069},
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_assets(
                html_assets.FIGURE_KIND,
                AssetTransport({}),
                article_id="10.1126/science.adz3492",
                assets=[asset],
                output_dir=Path(tmpdir),
                user_agent="test-agent",
                asset_profile="body",
                options=html_assets.AssetDownloadOptions(
                    candidate_builder=lambda *_args, **_kwargs: [svg_url],
                    image_document_fetcher=fetcher,
                    asset_download_concurrency=1,
                ),
            )

            self.assertEqual(result["asset_failures"], [])
            self.assertEqual(len(result["assets"]), 1)
            downloaded = result["assets"][0]
            self.assertEqual(downloaded["content_type"], "image/svg+xml")
            self.assertEqual(downloaded["downloaded_bytes"], len(svg_body))
            self.assertEqual(downloaded["width"], 696)
            self.assertEqual(downloaded["height"], 1069)
            self.assertEqual(Path(downloaded["path"]).suffix, ".svg")
            self.assertEqual(Path(downloaded["path"]).read_bytes(), svg_body)
        self.assertEqual(fetcher.call_args.args[0], svg_url)

    def test_science_provider_records_asset_failure_when_shared_browser_preview_fails(
        self,
    ) -> None:
        preview_url = "https://www.science.org/images/preview/figure1.png"
        html = f"""
<article>
  <figure>
    <img src="{preview_url}" alt="Preview figure" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
</article>
"""
        transport = AssetTransport({})
        client = science_provider.ScienceClient(transport=transport, env={})
        seed = {
            "browser_cookies": [
                {
                    "name": "cf_clearance",
                    "value": "initial",
                    "domain": ".science.org",
                    "path": "/",
                }
            ],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": SCIENCE_SAMPLE.landing_url,
        }
        refreshed_seed = {
            "browser_cookies": [
                {
                    "name": "cf_clearance",
                    "value": "refreshed",
                    "domain": ".science.org",
                    "path": "/",
                }
            ],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": SCIENCE_SAMPLE.landing_url,
        }
        first_fetcher = mock.Mock(return_value=None)
        retry_fetcher = mock.Mock(return_value=None)
        first_fetcher.failure_for = mock.Mock(
            return_value={
                "status": 403,
                "content_type": "text/html; charset=UTF-8",
                "title_snippet": "Just a moment...",
                "body_snippet": "Just a moment...",
                "reason": "cloudflare_challenge",
            }
        )
        retry_fetcher.failure_for = mock.Mock(
            return_value={
                "status": 403,
                "content_type": "text/html; charset=UTF-8",
                "title_snippet": "Just a moment...",
                "body_snippet": "Just a moment...",
                "reason": "cloudflare_challenge",
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", SCIENCE_SAMPLE.doi)
            raw_payload = _typed_raw_payload(
                provider="science",
                source_url=SCIENCE_SAMPLE.landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=f"# {SCIENCE_SAMPLE.title}\n\n## Results\n\n"
                + ("Body text " * 120),
                browser_context_seed=seed,
            )
            mocked_warm = mock.Mock(return_value=refreshed_seed)
            mocked_builder = mock.Mock(side_effect=[first_fetcher, retry_fetcher])
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                refresh_browser_context_seed=mocked_warm,
                _build_shared_browser_image_fetcher=mocked_builder,
            )
            result = client.download_related_assets(
                SCIENCE_SAMPLE.doi,
                {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                raw_payload,
                Path(tmpdir),
                asset_profile="body",
            )

        self.assertEqual(mocked_builder.call_count, 2)
        mocked_warm.assert_called_once()
        self.assert_direct_asset_attempted(transport)
        self.assertEqual(result["assets"], [])
        self.assertEqual(len(result["asset_failures"]), 1)
        self.assertEqual(result["asset_failures"][0]["source_url"], preview_url)
        self.assertEqual(result["asset_failures"][0]["status"], 403)
        self.assertEqual(
            result["asset_failures"][0]["title_snippet"], "Just a moment..."
        )
        self.assertEqual(result["asset_failures"][0]["reason"], "cloudflare_challenge")
        self.assertNotIn("recovery_attempts", result["asset_failures"][0])

    def test_shared_browser_image_fetcher_records_cloudflare_challenge_without_recovery(
        self,
    ) -> None:
        image_url = "https://onlinelibrary.wiley.com/cms/asset/full/figure1.jpg"
        figure_page_url = "https://onlinelibrary.wiley.com/doi/figure/10.1111/example"
        fetcher = browser_fetchers._SharedBrowserImageDocumentFetcher(
            browser_context_seed_getter=lambda: {
                "browser_cookies": [
                    {
                        "name": "cf_clearance",
                        "value": "seed",
                        "domain": ".wiley.com",
                        "path": "/",
                    }
                ],
                "browser_user_agent": "Mozilla/5.0",
                "browser_final_url": figure_page_url,
            },
            seed_urls_getter=lambda: [figure_page_url],
            browser_user_agent="Mozilla/5.0",
        )
        fetcher._ensure_page = mock.Mock(return_value=object())
        fetcher._sync_context_cookies = mock.Mock()
        fetcher._warm_seed_urls = mock.Mock()

        def side_effect(
            current_url: str, *, allow_small_formula=False, require_target_match=False
        ):
            fetcher._record_failure(
                current_url,
                status=403,
                content_type="text/html; charset=UTF-8",
                title_snippet="Just a moment...",
                body_snippet="Just a moment...",
                reason="cloudflare_challenge",
            )
            return None

        fetcher._fetch_with_page = mock.Mock(side_effect=side_effect)

        try:
            result = fetcher(image_url, {"figure_page_url": figure_page_url})
        finally:
            fetcher.close()

        self.assertIsNone(result)
        self.assertEqual(
            fetcher._warm_seed_urls.call_args_list[0].kwargs["force"], False
        )
        self.assertEqual(
            fetcher._warm_seed_urls.call_args_list[1].kwargs["force"], True
        )
        self.assertEqual(fetcher._fetch_with_page.call_count, 2)
        failure = fetcher.failure_for(image_url)
        assert failure is not None
        self.assertEqual(failure["reason"], "cloudflare_challenge")
        self.assertNotIn("recovery_attempts", failure)
