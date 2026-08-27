# ruff: noqa: F403,F405
from __future__ import annotations

from dataclasses import replace

from ._atypon_browser_workflow_provider_support import *
from paper_fetch.runtime import RuntimeContext


class _ProviderFakePage:
    def close(self) -> None:
        return None

    def goto(self, *_args, **_kwargs) -> None:
        return None


class _ProviderFakeBrowserContext:
    def __init__(self) -> None:
        self.closed = False
        self.route_calls: list[tuple[str, object]] = []

    def route(self, pattern: str, handler: object) -> None:
        assert pattern == "**/*"
        self.route_calls.append((pattern, handler))

    def add_cookies(self, _cookies) -> None:
        return None

    def new_page(self) -> _ProviderFakePage:
        return _ProviderFakePage()

    def close(self) -> None:
        self.closed = True


class AtyponBrowserWorkflowProviderAssetDownloadTests(
    AtyponBrowserWorkflowProviderTestCase
):
    def test_ams_provider_download_related_assets_downloads_full_size_figure(
        self,
    ) -> None:
        """asset-download-contract: provider=ams"""

        landing_url = (
            "https://journals.ametsoc.org/view/journals/clim/37/24/JCLI-D-23-0738.1.xml"
        )
        figure_url = "https://journals.ametsoc.org/view/journals/clim/37/24/full-JCLI-D-23-0738.1-f1.jpg"
        preview_url = "https://journals.ametsoc.org/view/journals/clim/37/24/inline-JCLI-D-23-0738.1-f1.jpg"
        image_body = png_header(640, 480)
        html = f"""
<article>
  <section id="bodymatter">
    <h2>Results</h2>
    <p>{"Body text " * 80}</p>
    <p>Figure 1 summarizes the observed circulation response.</p>
    <figure>
      <a class="figure-link">
        <img data-image-src="{preview_url}" src="/skin/site/img/Blank.svg" alt="Fig. 1." />
      </a>
      <pf-box class="figure-popover">
        <img data-image-src="{figure_url}" src="/skin/site/img/Blank.svg" alt="Fig. 1." />
      </pf-box>
      <figcaption><b>Fig. 1.</b> Circulation response.</figcaption>
    </figure>
  </section>
</article>
"""
        transport = AssetTransport({})
        client = ams_provider.AmsClient(transport=transport, env={})
        shared_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": image_body,
                "url": figure_url,
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            cdp_endpoint = "ws://127.0.0.1:9222/devtools/browser/ams-assets"
            runtime = replace(
                self._runtime_config(tmpdir, "ams", "10.1175/jcli-d-23-0738.1"),
                cdp_endpoint=cdp_endpoint,
            )
            raw_payload = _typed_raw_payload(
                provider="ams",
                source_url=landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=(
                    "# AMS Figure\n\n## Results\n\n"
                    "Figure 1 summarizes the observed circulation response.\n\n"
                    f"![Figure 1]({figure_url})\n\n"
                    "**Figure 1.** Circulation response."
                ),
                browser_context_seed={},
            )
            mocked_builder = mock.Mock(return_value=shared_fetcher)
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                _build_shared_browser_image_fetcher=mocked_builder,
            )
            with (
                mock.patch.object(
                    html_assets, "_build_cookie_seeded_opener"
                ) as mocked_opener,
                mock.patch.object(
                    html_assets, "_request_with_opener"
                ) as mocked_request,
            ):
                result = client.download_related_assets(
                    "10.1175/jcli-d-23-0738.1",
                    {"doi": "10.1175/jcli-d-23-0738.1", "title": "AMS Figure"},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )
                saved_path = Path(result["assets"][0]["path"])
                saved_exists = saved_path.is_file()
                saved_bytes = saved_path.read_bytes()
                article = client.to_article_model(
                    {"doi": "10.1175/jcli-d-23-0738.1", "title": "AMS Figure"},
                    raw_payload,
                    downloaded_assets=result["assets"],
                    asset_failures=result["asset_failures"],
                )
                rendered = article.to_ai_markdown(
                    asset_profile="body", max_tokens="full_text"
                )

        mocked_builder.assert_called_once()
        self.assertEqual(mocked_builder.call_args.kwargs["cdp_endpoint"], cdp_endpoint)
        mocked_opener.assert_not_called()
        mocked_request.assert_not_called()
        shared_fetcher.assert_called_once()
        self.assertEqual(shared_fetcher.call_args.args[0], figure_url)
        self.assert_direct_asset_attempted(transport)
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["assets"][0]["kind"], "figure")
        self.assertEqual(result["assets"][0]["downloaded_bytes"], len(image_body))
        self.assertEqual(saved_bytes, image_body)
        self.assertTrue(saved_exists)
        self.assertIn(f"![Figure 1]({saved_path})", rendered)
        self.assertNotIn(figure_url, rendered)

    def test_acs_provider_download_related_assets_fetches_body_figure(self) -> None:
        """asset-download-contract: provider=acs"""

        landing_url = "https://pubs.acs.org/doi/10.1021/acsomega.4c03987"
        figure_page_url = (
            "https://pubs.acs.org/view-large/figure/1234567/ao4c03987_0001.tif"
        )
        figure_url = (
            "https://oup.silverchair-cdn.com/oup/backfile/Content_public/"
            "Journal/acsodf/9/30/10.1021_acsomega.4c03987/1/ao4c03987_0001.png"
        )
        preview_url = (
            "https://oup.silverchair-cdn.com/oup/backfile/Content_public/"
            "Journal/acsodf/9/30/10.1021_acsomega.4c03987/1/"
            "m_ao4c03987_0001.png"
        )
        image_body = png_header(640, 480)
        html = f"""
<div class="article-body">
  <div class="widget-ArticleFulltext">
    <div class="article-section-wrapper">
      <h2>Results</h2>
      <p>{"Body text " * 80}</p>
      <p>Figure 1 shows representative benzimidazole-based drug molecules.</p>
    </div>
    <div class="fig fig-section" id="fig1">
      <div class="fig-label">Figure 1</div>
      <a class="fig-view-orig" href="{figure_page_url}">
        View Large Image
      </a>
      <img src="{preview_url}" alt="Benzimidazole-based drug molecules." />
      <div class="caption">
        <p>Figure 1. Benzimidazole-based drug molecules.</p>
      </div>
    </div>
  </div>
</div>
"""
        transport = AssetTransport({})
        client = acs_provider.AcsClient(transport=transport, env={})
        shared_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": image_body,
                "url": figure_url,
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "acs", "10.1021/acsomega.4c03987")
            raw_payload = _typed_raw_payload(
                provider="acs",
                source_url=landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=(
                    "# ACS Figure\n\n## Results\n\n"
                    "Figure 1 shows representative benzimidazole-based drug molecules.\n\n"
                    f"![Figure 1]({figure_url})\n\n"
                    "**Figure 1.** Benzimidazole-based drug molecules."
                ),
                browser_context_seed={},
            )
            mocked_fetch = mock.Mock(
                return_value=browser_runtime.BrowserFetchedHtml(
                    source_url=figure_page_url,
                    final_url=figure_page_url,
                    html=(
                        "<html><head>"
                        f"<meta property='og:image' content='{figure_url}' />"
                        "</head><body></body></html>"
                    ),
                    response_status=200,
                    response_headers={"content-type": "text/html"},
                    title="Figure 1",
                    summary="Full-size ACS figure",
                    browser_context_seed={},
                )
            )
            mocked_builder = mock.Mock(return_value=shared_fetcher)
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mocked_fetch,
                _build_shared_browser_image_fetcher=mocked_builder,
            )
            with (
                mock.patch.object(
                    html_assets, "_build_cookie_seeded_opener"
                ) as mocked_opener,
                mock.patch.object(
                    html_assets, "_request_with_opener"
                ) as mocked_request,
            ):
                result = client.download_related_assets(
                    "10.1021/acsomega.4c03987",
                    {"doi": "10.1021/acsomega.4c03987", "title": "ACS Figure"},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )
                saved_path = Path(result["assets"][0]["path"])
                saved_exists = saved_path.is_file()
                saved_bytes = saved_path.read_bytes()
                article = client.to_article_model(
                    {"doi": "10.1021/acsomega.4c03987", "title": "ACS Figure"},
                    raw_payload,
                    downloaded_assets=result["assets"],
                    asset_failures=result["asset_failures"],
                )
                rendered = article.to_ai_markdown(
                    asset_profile="body", max_tokens="full_text"
                )

        mocked_fetch.assert_called_once()
        self.assertEqual(mocked_fetch.call_args.args[0], [figure_page_url])
        readiness = mocked_fetch.call_args.kwargs["readiness"]
        self.assertFalse(readiness.wait_for_article_body)
        self.assertEqual(
            readiness.selector,
            "img.content-image[src], img.content-image[data-src]",
        )
        self.assertEqual(mocked_fetch.call_args.kwargs["wait_seconds"], 2)
        self.assertTrue(mocked_fetch.call_args.kwargs["options"].reuse_runtime_page)
        mocked_builder.assert_called_once()
        mocked_opener.assert_not_called()
        mocked_request.assert_not_called()
        shared_fetcher.assert_called_once()
        self.assertEqual(shared_fetcher.call_args.args[0], figure_url)
        self.assert_direct_asset_attempted(transport)
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["assets"][0]["kind"], "figure")
        self.assertEqual(result["assets"][0]["section"], "body")
        self.assertEqual(result["assets"][0]["download_tier"], "full_size")
        self.assertEqual(result["assets"][0]["downloaded_bytes"], len(image_body))
        self.assertEqual(saved_bytes, image_body)
        self.assertTrue(saved_exists)
        self.assertIn(f"![Figure 1]({saved_path})", rendered)
        self.assertNotIn(figure_url, rendered)

    def test_science_provider_download_related_assets_body_profile_ignores_supplementary(
        self,
    ) -> None:
        """asset-download-contract: provider=science"""

        html = """
<article>
  <figure>
    <img src="https://www.science.org/images/large/figure1.png" alt="Figure 1 alt" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
  <section id="supplementary-materials" class="core-supplementary-materials">
    <h2>Supplementary Materials</h2>
    <a href="https://www.science.org/doi/suppl/10.1126/science.sample/suppl_file/appendix.pdf">Download</a>
  </section>
</article>
"""
        figure_url = "https://www.science.org/images/large/figure1.png"
        transport = AssetTransport({})
        client = science_provider.ScienceClient(transport=transport, env={})
        shared_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": png_header(640, 480),
                "url": figure_url,
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
                browser_context_seed={},
            )
            mocked_fetch = mock.Mock()
            mocked_builder = mock.Mock(return_value=shared_fetcher)
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mocked_fetch,
                _build_shared_browser_image_fetcher=mocked_builder,
            )
            with (
                mock.patch.object(
                    html_assets, "_build_cookie_seeded_opener"
                ) as mocked_opener,
                mock.patch.object(
                    html_assets, "_request_with_opener"
                ) as mocked_request,
            ):
                result = client.download_related_assets(
                    SCIENCE_SAMPLE.doi,
                    {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )
                saved_path = Path(result["assets"][0]["path"])
                saved_bytes = saved_path.read_bytes()

        mocked_fetch.assert_not_called()
        mocked_builder.assert_called_once()
        mocked_opener.assert_not_called()
        mocked_request.assert_not_called()
        self.assert_direct_asset_attempted(transport)
        shared_fetcher.assert_called_once()
        self.assertEqual(shared_fetcher.call_args.args[0], figure_url)
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["assets"][0]["kind"], "figure")
        self.assertEqual(result["assets"][0]["download_tier"], "full_size")
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(saved_bytes, png_header(640, 480))

    def test_science_provider_download_related_assets_all_profile_downloads_supplementary_via_file_fetcher(
        self,
    ) -> None:
        figure_url = "https://www.science.org/images/large/figure1.png"
        supplementary_url = "https://www.science.org/doi/suppl/10.1126/science.sample/suppl_file/appendix.pdf"
        html = f"""
<article>
  <figure>
    <img src="{figure_url}" alt="Figure 1 alt" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
  <section id="supplementary-materials" class="core-supplementary-materials">
    <h2>Supplementary Materials</h2>
    <a href="{supplementary_url}">Download</a>
  </section>
</article>
"""
        transport = AssetTransport({})
        client = science_provider.ScienceClient(transport=transport, env={})
        shared_image_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": png_header(640, 480),
                "url": figure_url,
            }
        )
        shared_file_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "application/pdf"},
                "body": b"%PDF-1.7 supplementary",
                "url": supplementary_url,
            }
        )
        challenge_html = {
            "status_code": 403,
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": (
                b"<html><head><title>Just a moment...</title></head>"
                b"<body>Checking your browser before accessing</body></html>"
            ),
            "url": supplementary_url,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            cdp_endpoint = "ws://127.0.0.1:9222/devtools/browser/science-assets"
            runtime = replace(
                self._runtime_config(tmpdir, "science", SCIENCE_SAMPLE.doi),
                cdp_endpoint=cdp_endpoint,
            )
            raw_payload = _typed_raw_payload(
                provider="science",
                source_url=SCIENCE_SAMPLE.landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=f"# {SCIENCE_SAMPLE.title}\n\n## Results\n\n"
                + ("Body text " * 120),
                browser_context_seed={},
            )
            mocked_image_builder = mock.Mock(return_value=shared_image_fetcher)
            mocked_file_builder = mock.Mock(return_value=shared_file_fetcher)
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                _build_shared_browser_image_fetcher=mocked_image_builder,
                _build_shared_browser_file_fetcher=mocked_file_builder,
            )
            with (
                mock.patch.object(
                    html_assets, "_build_cookie_seeded_opener", return_value=object()
                ) as mocked_opener,
                mock.patch.object(
                    html_assets, "_request_with_opener", return_value=challenge_html
                ) as mocked_request,
            ):
                result = client.download_related_assets(
                    SCIENCE_SAMPLE.doi,
                    {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="all",
                )

        # A direct 403 is followed by one real browser-byte recovery. The
        # cookie opener would repeat the same URL/session direct request and is
        # therefore intentionally skipped.
        mocked_opener.assert_not_called()
        mocked_request.assert_not_called()
        mocked_image_builder.assert_called_once()
        mocked_file_builder.assert_called_once()
        self.assertTrue(
            mocked_image_builder.call_args.kwargs["use_runtime_shared_browser"]
        )
        self.assertTrue(
            mocked_file_builder.call_args.kwargs["use_runtime_shared_browser"]
        )
        self.assertEqual(
            mocked_image_builder.call_args.kwargs["cdp_endpoint"], cdp_endpoint
        )
        self.assertEqual(
            mocked_file_builder.call_args.kwargs["cdp_endpoint"], cdp_endpoint
        )
        self.assertTrue(mocked_file_builder.call_args.kwargs["thread_local"])
        self.assert_direct_asset_attempted(transport)
        shared_image_fetcher.assert_called_once()
        shared_file_fetcher.assert_called_once()
        self.assertEqual(shared_file_fetcher.call_args.args[0], supplementary_url)
        self.assertEqual(
            [asset["kind"] for asset in result["assets"]],
            ["figure", "supplementary"],
        )
        self.assertEqual(result["assets"][1]["download_tier"], "supplementary_file")
        self.assertEqual(result["asset_failures"], [])

    def test_browser_asset_fetchers_reuse_runtime_keyed_browser_manager(self) -> None:
        figure_url = "https://www.science.org/images/large/figure1.png"
        supplementary_url = "https://www.science.org/doi/suppl/10.1126/science.sample/suppl_file/appendix.pdf"
        html = f"""
<article>
  <figure>
    <img src="{figure_url}" alt="Figure 1 alt" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
  <section id="supplementary-materials" class="core-supplementary-materials">
    <h2>Supplementary Materials</h2>
    <a href="{supplementary_url}">Download</a>
  </section>
</article>
"""
        transport = AssetTransport({})
        client = science_provider.ScienceClient(
            transport=transport,
            env={"PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY": "2"},
        )
        challenge_html = {
            "status_code": 403,
            "headers": {"content-type": "text/html; charset=utf-8"},
            "body": (
                b"<html><head><title>Just a moment...</title></head>"
                b"<body>Checking your browser before accessing</body></html>"
            ),
            "url": supplementary_url,
        }
        private_contexts: list[_ProviderFakeBrowserContext] = []

        def new_private_context(_manager, **_kwargs):
            private_context = _ProviderFakeBrowserContext()
            private_contexts.append(private_context)
            return private_context

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "science", SCIENCE_SAMPLE.doi)
            runtime_context = RuntimeContext(
                env={"PAPER_FETCH_ASSET_DOWNLOAD_CONCURRENCY": "2"},
                download_dir=Path(tmpdir),
            )
            runtime_context.new_browser_context = mock.Mock(
                side_effect=AssertionError("unkeyed runtime browser should not be used")
            )
            runtime_context.new_browser_context_for_runtime_config = mock.Mock(
                wraps=runtime_context.new_browser_context_for_runtime_config
            )
            raw_payload = _typed_raw_payload(
                provider="science",
                source_url=SCIENCE_SAMPLE.landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=f"# {SCIENCE_SAMPLE.title}\n\n## Results\n\n"
                + ("Body text " * 120),
                browser_context_seed={},
            )
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
            )
            with (
                mock.patch(
                    "paper_fetch.providers.browser_runtime.camoufox_manager.CamoufoxBrowserManager.new_context",
                    new=new_private_context,
                ),
                mock.patch.object(
                    browser_workflow._SharedBrowserImageDocumentFetcher,
                    "_fetch_with_page",
                    return_value={
                        "status_code": 200,
                        "headers": {"content-type": "image/png"},
                        "body": png_header(640, 480),
                        "url": figure_url,
                        "dimensions": {"width": 640, "height": 480},
                    },
                ),
                mock.patch.object(
                    browser_workflow._SharedBrowserFileDocumentFetcher,
                    "_fetch_with_context_request",
                    return_value={
                        "status_code": 200,
                        "headers": {"content-type": "application/pdf"},
                        "body": b"%PDF-1.7 supplementary",
                        "url": supplementary_url,
                    },
                ),
                mock.patch.object(
                    html_assets, "_build_cookie_seeded_opener", return_value=object()
                ),
                mock.patch.object(
                    html_assets, "_request_with_opener", return_value=challenge_html
                ),
            ):
                result = client.download_related_assets(
                    SCIENCE_SAMPLE.doi,
                    {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="all",
                    context=runtime_context,
                )

        runtime_context.new_browser_context.assert_not_called()
        self.assertEqual(
            runtime_context.new_browser_context_for_runtime_config.call_count, 2
        )
        self.assertEqual(len(runtime_context._camoufox_browser_managers), 1)
        self.assert_direct_asset_attempted(transport)
        self.assertEqual(
            [asset["kind"] for asset in result["assets"]],
            ["figure", "supplementary"],
        )
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(len(private_contexts), 2)
        self.assertTrue(all(context.route_calls == [] for context in private_contexts))
        self.assertTrue(all(context.closed for context in private_contexts))

    def test_pnas_provider_download_related_assets_uses_figure_page_and_falls_back_to_preview(
        self,
    ) -> None:
        figure_page_url = "https://www.pnas.org/figures/figure-1"
        preview_url = "https://www.pnas.org/images/preview/figure1.png"
        full_size_url = "https://www.pnas.org/images/original/figure1.png"
        html = f"""
<article>
  <figure>
    <a href="{figure_page_url}">View figure</a>
    <img src="{preview_url}" alt="Preview figure" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
</article>
"""
        transport = AssetTransport({})
        client = pnas_provider.PnasClient(transport=transport, env={})
        initial_seed = {
            "browser_cookies": [
                {
                    "name": "cf_clearance",
                    "value": "secret",
                    "domain": ".pnas.org",
                    "path": "/",
                }
            ],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": PNAS_SAMPLE.landing_url,
        }
        warmed_seed = {
            "browser_cookies": [
                {
                    "name": "sessionid",
                    "value": "warm",
                    "domain": ".pnas.org",
                    "path": "/",
                }
            ],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": figure_page_url,
        }
        shared_fetcher = mock.Mock(
            side_effect=[
                None,
                {
                    "status_code": 200,
                    "headers": {"content-type": "image/png"},
                    "body": png_header(320, 240),
                    "url": preview_url,
                },
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", PNAS_SAMPLE.doi)
            raw_payload = _typed_raw_payload(
                provider="pnas",
                source_url=PNAS_SAMPLE.landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=f"# {PNAS_SAMPLE.title}\n\n## Results\n\n"
                + ("Body text " * 120),
                browser_context_seed=initial_seed,
            )
            mocked_fetch = mock.Mock(
                return_value=browser_runtime.BrowserFetchedHtml(
                    source_url=figure_page_url,
                    final_url=figure_page_url,
                    html=(
                        "<html><head>"
                        f"<meta property='og:image' content='{full_size_url}' />"
                        "</head><body></body></html>"
                    ),
                    response_status=200,
                    response_headers={"content-type": "text/html"},
                    title="Figure page",
                    summary="Figure page summary",
                    browser_context_seed=warmed_seed,
                )
            )
            mocked_builder = mock.Mock(return_value=shared_fetcher)
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mocked_fetch,
                _build_shared_browser_image_fetcher=mocked_builder,
            )
            with (
                mock.patch.object(
                    html_assets, "_build_cookie_seeded_opener"
                ) as mocked_opener,
                mock.patch.object(
                    html_assets, "_request_with_opener"
                ) as mocked_request,
            ):
                result = client.download_related_assets(
                    PNAS_SAMPLE.doi,
                    {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )
                saved_path = Path(result["assets"][0]["path"])
                saved_bytes = saved_path.read_bytes()

        mocked_fetch.assert_called_once()
        self.assertEqual(mocked_fetch.call_args.args[0], [figure_page_url])
        mocked_builder.assert_called_once()
        mocked_opener.assert_not_called()
        mocked_request.assert_not_called()
        self.assert_direct_asset_attempted(transport)
        self.assertEqual(
            [call.args[0] for call in shared_fetcher.call_args_list],
            [full_size_url, preview_url],
        )
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(result["assets"][0]["download_tier"], "preview")
        self.assertEqual(saved_bytes, png_header(320, 240))

    def test_pnas_provider_download_related_assets_uses_shared_browser_primary_path_before_preview(
        self,
    ) -> None:
        """rule: rule-browser-primary-image-download-path
        asset-download-contract: provider=pnas
        """
        figure_page_url = "https://www.pnas.org/figures/figure-1"
        preview_url = "https://www.pnas.org/images/preview/figure1.png"
        full_size_url = "https://www.pnas.org/images/original/figure1.png"
        html = f"""
<article>
  <figure>
    <a href="{figure_page_url}">View figure</a>
    <img src="{preview_url}" alt="Preview figure" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
</article>
"""
        transport = AssetTransport({})
        client = pnas_provider.PnasClient(transport=transport, env={})
        initial_seed = {
            "browser_cookies": [
                {
                    "name": "cf_clearance",
                    "value": "secret",
                    "domain": ".pnas.org",
                    "path": "/",
                }
            ],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": PNAS_SAMPLE.landing_url,
        }
        shared_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/jpeg"},
                "body": b"\xff\xd8\xffprimary-image",
                "url": full_size_url,
                "dimensions": {"width": 1200, "height": 800},
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", PNAS_SAMPLE.doi)
            raw_payload = _typed_raw_payload(
                provider="pnas",
                source_url=PNAS_SAMPLE.landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=f"# {PNAS_SAMPLE.title}\n\n## Results\n\n"
                + ("Body text " * 120),
                browser_context_seed=initial_seed,
            )
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mock.Mock(
                    return_value=browser_runtime.BrowserFetchedHtml(
                        source_url=figure_page_url,
                        final_url=figure_page_url,
                        html=(
                            "<html><head>"
                            f"<meta property='og:image' content='{full_size_url}' />"
                            "</head><body></body></html>"
                        ),
                        response_status=200,
                        response_headers={"content-type": "text/html"},
                        title="Figure page",
                        summary="Figure page summary",
                        browser_context_seed=initial_seed,
                    )
                ),
                _build_shared_browser_image_fetcher=mock.Mock(
                    return_value=shared_fetcher
                ),
            )
            mocked_builder = client.deps._build_shared_browser_image_fetcher
            with (
                mock.patch.object(
                    html_assets, "_build_cookie_seeded_opener"
                ) as mocked_opener,
                mock.patch.object(
                    html_assets, "_request_with_opener"
                ) as mocked_request,
            ):
                result = client.download_related_assets(
                    PNAS_SAMPLE.doi,
                    {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )
                saved_path = Path(result["assets"][0]["path"])
                saved_bytes = saved_path.read_bytes()

        mocked_builder.assert_called_once()
        mocked_opener.assert_not_called()
        mocked_request.assert_not_called()
        self.assert_direct_asset_attempted(transport)
        shared_fetcher.assert_called_once()
        self.assertEqual(shared_fetcher.call_args.args[0], full_size_url)
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(result["assets"][0]["download_tier"], "full_size")
        self.assertEqual(saved_bytes, b"\xff\xd8\xffprimary-image")

    def test_pnas_provider_reuses_cached_figure_page_for_repeated_assets(self) -> None:
        figure_page_url = "https://www.pnas.org/figures/figure-1"
        preview_url_one = "https://www.pnas.org/images/preview/figure1-a.png"
        preview_url_two = "https://www.pnas.org/images/preview/figure1-b.png"
        full_size_url = "https://www.pnas.org/images/original/figure1.png"
        html = f"""
<article>
  <figure>
    <a href="{figure_page_url}">View figure</a>
    <img src="{preview_url_one}" alt="Preview figure one" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
  <figure>
    <a href="{figure_page_url}">View figure</a>
    <img src="{preview_url_two}" alt="Preview figure two" />
    <figcaption>Figure 2 caption</figcaption>
  </figure>
</article>
"""
        transport = AssetTransport({})
        client = pnas_provider.PnasClient(transport=transport, env={})
        seed = {
            "browser_cookies": [
                {
                    "name": "cf_clearance",
                    "value": "secret",
                    "domain": ".pnas.org",
                    "path": "/",
                }
            ],
            "browser_user_agent": "Mozilla/5.0",
            "browser_final_url": PNAS_SAMPLE.landing_url,
        }
        shared_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": png_header(640, 480),
                "url": full_size_url,
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = self._runtime_config(tmpdir, "pnas", PNAS_SAMPLE.doi)
            raw_payload = _typed_raw_payload(
                provider="pnas",
                source_url=PNAS_SAMPLE.landing_url,
                content_type="text/html",
                body=html.encode("utf-8"),
                route="html",
                markdown_text=f"# {PNAS_SAMPLE.title}\n\n## Results\n\n"
                + ("Body text " * 120),
                browser_context_seed=seed,
            )
            mocked_fetch = mock.Mock(
                return_value=browser_runtime.BrowserFetchedHtml(
                    source_url=figure_page_url,
                    final_url=figure_page_url,
                    html=(
                        "<html><head>"
                        f"<meta property='og:image' content='{full_size_url}' />"
                        "</head><body></body></html>"
                    ),
                    response_status=200,
                    response_headers={"content-type": "text/html"},
                    title="Figure page",
                    summary="Figure page summary",
                    browser_context_seed=seed,
                )
            )
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mocked_fetch,
                _build_shared_browser_image_fetcher=mock.Mock(
                    return_value=shared_fetcher
                ),
            )
            result = client.download_related_assets(
                PNAS_SAMPLE.doi,
                {"doi": PNAS_SAMPLE.doi, "title": PNAS_SAMPLE.title},
                raw_payload,
                Path(tmpdir),
                asset_profile="body",
            )

        self.assertEqual(mocked_fetch.call_count, 1)
        self.assertEqual(shared_fetcher.call_count, 1)
        self.assertEqual(len(result["assets"]), 2)
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(
            [asset["download_url"] for asset in result["assets"]],
            [full_size_url, full_size_url],
        )

    def test_science_provider_reuses_cached_image_candidate_for_repeated_assets(
        self,
    ) -> None:
        full_size_url = "https://www.science.org/images/original/figure1.png"
        preview_url_one = "https://www.science.org/images/preview/figure1-a.png"
        preview_url_two = "https://www.science.org/images/preview/figure1-b.png"
        html = "<article><p>Body text</p></article>"
        transport = AssetTransport({})
        client = science_provider.ScienceClient(transport=transport, env={})
        shared_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": png_header(640, 480),
                "url": full_size_url,
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
                browser_context_seed={},
            )
            mocked_fetch = mock.Mock()
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mocked_fetch,
                _build_shared_browser_image_fetcher=mock.Mock(
                    return_value=shared_fetcher
                ),
            )
            with (
                mock.patch.object(
                    atypon_browser_workflow_asset_scopes,
                    "extract_scoped_html_assets",
                    return_value=[
                        {
                            "kind": "figure",
                            "heading": "Figure 1",
                            "caption": "Figure 1 caption",
                            "url": full_size_url,
                            "preview_url": preview_url_one,
                            "full_size_url": full_size_url,
                            "section": "body",
                        },
                        {
                            "kind": "figure",
                            "heading": "Figure 2",
                            "caption": "Figure 2 caption",
                            "url": full_size_url,
                            "preview_url": preview_url_two,
                            "full_size_url": full_size_url,
                            "section": "body",
                        },
                    ],
                ),
            ):
                result = client.download_related_assets(
                    SCIENCE_SAMPLE.doi,
                    {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )

        mocked_fetch.assert_not_called()
        self.assertEqual(shared_fetcher.call_count, 1)
        self.assertEqual(len(result["assets"]), 2)
        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(
            [asset["download_url"] for asset in result["assets"]],
            [full_size_url, full_size_url],
        )

    def test_science_provider_records_preview_dimensions_and_acceptance(self) -> None:
        preview_url = "https://www.science.org/images/preview/figure1.png"
        html = f"""
<article>
  <figure>
    <img src="{preview_url}" alt="Preview figure" />
    <figcaption>Figure 1 caption</figcaption>
  </figure>
</article>
"""
        image_body = png_header(640, 480)
        transport = AssetTransport({})
        client = science_provider.ScienceClient(transport=transport, env={})
        shared_fetcher = mock.Mock(
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": image_body,
                "url": preview_url,
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
                browser_context_seed={},
            )
            mocked_fetch = mock.Mock()
            mocked_builder = mock.Mock(return_value=shared_fetcher)
            install_browser_workflow_deps(
                client,
                load_runtime_config=mock.Mock(return_value=runtime),
                ensure_runtime_ready=mock.Mock(),
                fetch_html_with_browser=mocked_fetch,
                _build_shared_browser_image_fetcher=mocked_builder,
            )
            with (
                mock.patch.object(
                    html_assets, "_build_cookie_seeded_opener"
                ) as mocked_opener,
                mock.patch.object(
                    html_assets, "_request_with_opener"
                ) as mocked_request,
            ):
                result = client.download_related_assets(
                    SCIENCE_SAMPLE.doi,
                    {"doi": SCIENCE_SAMPLE.doi, "title": SCIENCE_SAMPLE.title},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )

        mocked_fetch.assert_not_called()
        mocked_builder.assert_called_once()
        mocked_opener.assert_not_called()
        mocked_request.assert_not_called()
        self.assert_direct_asset_attempted(transport)
        shared_fetcher.assert_called_once()
        self.assertEqual(shared_fetcher.call_args.args[0], preview_url)
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["assets"][0]["download_tier"], "preview")
        self.assertEqual(result["assets"][0]["width"], 640)
        self.assertEqual(result["assets"][0]["height"], 480)
        self.assertTrue(result["assets"][0]["preview_accepted"])
