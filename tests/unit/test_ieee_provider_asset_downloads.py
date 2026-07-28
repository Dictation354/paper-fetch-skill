# ruff: noqa: F403,F405
from __future__ import annotations

from paper_fetch.providers import _ieee_asset_recovery
from paper_fetch.providers import _ieee_supplementary

from ._ieee_provider_support import *


class IeeeProviderAssetDownloadTests(unittest.TestCase):
    def test_ieee_article_seed_waits_for_title_and_latest_cookies(self) -> None:
        class Page:
            def __init__(self) -> None:
                self.polls = 0

            def title(self) -> str:
                return "IEEE article" if self.polls >= 2 else ""

            def wait_for_timeout(self, _milliseconds: int) -> None:
                self.polls += 1

        class Context:
            def __init__(self, page: Page) -> None:
                self.page = page

            def cookies(self, _urls) -> list[dict[str, str]]:
                if self.page.polls < 2:
                    return []
                return [
                    {
                        "name": "ieee_session",
                        "value": "latest",
                        "domain": ".ieeexplore.ieee.org",
                        "path": "/",
                    }
                ]

        page = Page()
        self.assertTrue(
            _ieee_asset_recovery._ieee_article_seed_page_is_ready(
                page,
                Context(page),
                "https://ieeexplore.ieee.org/document/10772041/",
            )
        )
        self.assertEqual(page.polls, 2)

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
        mocked_download.assert_called_once()
        self.assertIs(
            mocked_download.call_args.args[0], _ieee_supplementary.FIGURE_KIND
        )
        self.assertEqual(mocked_download.call_args.kwargs["seed_urls"], [landing_url])
        self.assertEqual(
            mocked_download.call_args.kwargs["headers"]["Referer"], landing_url
        )
        passed_assets = mocked_download.call_args.kwargs["assets"]
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
            with (
                mock.patch.object(
                    html_assets, "_build_cookie_seeded_opener", return_value=object()
                ) as mocked_opener,
                mock.patch.object(
                    html_assets, "_request_with_opener", side_effect=opener_requester
                ) as mocked_request,
            ):
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
        self.assertEqual(mocked_request.call_count, 4)
        self.assertTrue(
            any(
                call.kwargs["headers"].get("Referer") == landing_url
                for call in mocked_opener.call_args_list
            )
        )

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
            with (
                mock.patch.object(
                    html_assets, "_build_cookie_seeded_opener", return_value=object()
                ) as mocked_opener,
                mock.patch.object(
                    html_assets, "_request_with_opener", side_effect=opener_requester
                ) as mocked_request,
            ):
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
        self.assertEqual(mocked_request.call_count, 2)
        self.assertEqual(mocked_opener.call_args.args[0], [landing_url])
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
            with (
                mock.patch.object(
                    html_assets, "_build_cookie_seeded_opener", return_value=object()
                ),
                mock.patch.object(
                    html_assets, "_request_with_opener", side_effect=opener_requester
                ),
            ):
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
                item.get("content_type") == "text/html; charset=utf-8"
                for item in result["asset_failures"]
            )
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
