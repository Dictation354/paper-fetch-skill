# ruff: noqa: F403,F405
from __future__ import annotations

from paper_fetch.providers import _ieee_html, _ieee_metadata, _ieee_supplementary
from paper_fetch.providers._asset_retry import merge_asset_retry_results

from ._ieee_provider_support import *


class IeeeProviderAssetExtractionTests(unittest.TestCase):
    def test_ieee_supplementary_suffixes_reuse_generic_source_with_ieee_extras(
        self,
    ) -> None:
        self.assertTrue(
            _ieee_supplementary._has_ieee_supplementary_file_suffix(
                "https://example.test/supplement.csv"
            )
        )
        self.assertTrue(
            _ieee_supplementary._has_ieee_supplementary_file_suffix(
                "https://example.test/supplement.docx"
            )
        )
        self.assertTrue(
            _ieee_supplementary._has_ieee_supplementary_file_suffix(
                "https://example.test/archive.tar.gz"
            )
        )

    def test_ieee_figure_full_media_assets_are_body_assets(self) -> None:
        """rule: rule-ieee-mediastore-body-assets
        rule: rule-ieee-supplementary-scope
        rule: rule-supplementary-discovery-explicit-scope"""
        article_number = "10388355"
        rest_url = f"https://ieeexplore.ieee.org/rest/document/{article_number}/?logAccess=true"

        extraction = _ieee_html._extract_ieee_html(
            _dynamic_html_with_ieee_media_assets(article_number).decode("utf-8"),
            rest_url,
            metadata={"title": "IEEE Dynamic Article"},
        )

        body_assets = [
            item
            for item in extraction.extracted_assets
            if item.get("kind") in {"figure", "table"} and item.get("section") == "body"
        ]
        self.assertEqual(len(body_assets), 2)
        figure = next(item for item in body_assets if item["kind"] == "figure")
        table = next(item for item in body_assets if item["kind"] == "table")
        self.assertEqual(
            figure["url"],
            f"https://ieeexplore.ieee.org/mediastore/IEEE/content/media/{article_number}/{article_number}-fig-1-large.gif",
        )
        self.assertEqual(
            figure["preview_url"],
            f"https://ieeexplore.ieee.org/mediastore/IEEE/content/media/{article_number}/{article_number}-fig-1-small.gif",
        )
        self.assertEqual(figure["full_size_url"], figure["url"])
        self.assertEqual(figure["heading"], "Fig. 1.")
        self.assertIn("Example system overview", figure["caption"])
        self.assertEqual(
            table["url"],
            f"https://ieeexplore.ieee.org/mediastore/IEEE/content/media/{article_number}/{article_number}-table-1-large.gif",
        )
        self.assertEqual(table["full_size_url"], table["url"])
        self.assertEqual(table["heading"], "Table I.")
        self.assertIn("Comparison of methods", table["caption"])
        supplementary_assets = [
            item
            for item in extraction.extracted_assets
            if item.get("kind") == "supplementary"
            and item.get("section") == "supplementary"
        ]
        self.assertEqual(
            [item["url"] for item in supplementary_assets],
            [
                "https://ieeexplore.ieee.org/documents/supplementary.pdf",
                "https://ieeexplore.ieee.org/documents/multimedia.mp4",
            ],
        )
        self.assertNotIn(
            "/assets/img/icon.support.gif", json.dumps(extraction.extracted_assets)
        )
        self.assertNotIn("/assets/img/icon.support.gif", extraction.markdown_text)

    def test_ieee_supplementary_assets_ignore_unscoped_body_data_code_media_links(
        self,
    ) -> None:
        """rule: rule-ieee-supplementary-scope
        rule: rule-supplementary-discovery-explicit-scope"""
        article_number = "10388355"
        rest_url = f"https://ieeexplore.ieee.org/rest/document/{article_number}/?logAccess=true"
        paragraph = (
            "This IEEE body paragraph describes data, code, media, methods, "
            "and results across several experiments. "
        )
        html = (
            '<?xml version="1.0" encoding="UTF-8"?><response><accessType>Open Access</accessType>'
            '<div id="BodyWrapper"><div id="article">'
            '<div class="section" id="sec1"><h2>Data and Code Availability</h2><p>'
            + paragraph
            * 25
            + "</p><p>Project resources include "
            '<a href="/documents/data.csv">data</a>, '
            '<a href="/documents/code.zip">code</a>, and '
            '<a href="/documents/media.mp4">media</a> links in the body.</p></div>'
            '<div class="section" id="supplementary-materials"><h2>Supplementary Materials</h2>'
            '<a href="/documents/appendix.pdf">Supplementary appendix</a></div>'
            "</div></div></response>"
        )

        extraction = _ieee_html._extract_ieee_html(
            html,
            rest_url,
            metadata={"title": "IEEE Dynamic Article"},
        )

        supplementary_assets = [
            item
            for item in extraction.extracted_assets
            if item.get("kind") == "supplementary"
        ]
        self.assertEqual(
            [item["url"] for item in supplementary_assets],
            ["https://ieeexplore.ieee.org/documents/appendix.pdf"],
        )

    def test_ieee_support_icon_filter_uses_structure_and_section_marker_variants(
        self,
    ) -> None:
        rest_url = "https://ieeexplore.ieee.org/rest/document/10388355/?logAccess=true"
        paragraph = "This IEEE body paragraph has enough article words for extraction. "
        html = (
            '<?xml version="1.0" encoding="UTF-8"?><response><accessType>Open Access</accessType>'
            '<div id="BodyWrapper"><div id="article">'
            '<div class="section" id="sec1">'
            '<span class="kicker">Section 1</span><h2>Introduction</h2><p>'
            + paragraph
            * 20
            + '</p><figure><img src="/assets/img/icon.support-new.gif" alt="Support icon" width="16" height="16"></figure>'
            '</div><div id="supplementary-materials"><h2>Supplementary Materials</h2>'
            '<a href="/documents/extra.png">Supplementary image</a></div>'
            "</div></div></response>"
        )

        extraction = _ieee_html._extract_ieee_html(
            html, rest_url, metadata={"title": "IEEE Dynamic Article"}
        )

        self.assertNotIn("Section 1", extraction.markdown_text)
        self.assertNotIn(
            "icon.support-new.gif", json.dumps(extraction.extracted_assets)
        )
        self.assertIn(
            "https://ieeexplore.ieee.org/documents/extra.png",
            json.dumps(extraction.extracted_assets),
        )

    def test_real_ieee_multimedia_fixture_yields_supplementary_asset_from_explicit_scope(
        self,
    ) -> None:
        """rule: rule-ieee-supplementary-scope
        rule: rule-supplementary-discovery-explicit-scope"""
        fixture_root = (
            REPO_ROOT
            / "tests"
            / "fixtures"
            / "golden_criteria"
            / "10.1109_RITA.2026.3668995"
        )
        doi = "10.1109/RITA.2026.3668995"
        article_number = "11417163"
        document_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        multimedia_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/multimedia"
        )
        landing_html = (fixture_root / "landing.html").read_text(encoding="utf-8")
        landing_metadata = _ieee_metadata._parse_landing_metadata(landing_html)
        multimedia_body = (fixture_root / "multimedia.json").read_bytes()
        transport = RecordingTransport(
            {
                ("GET", multimedia_url): {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": multimedia_body,
                    "url": multimedia_url,
                }
            }
        )
        client = IeeeClient(transport, {})
        attempt = _ieee_metadata.IeeeLandingAttempt(
            normalized_doi=doi,
            landing_url=document_url,
            response_url=document_url,
            html_text=landing_html,
            merged_metadata={
                "doi": doi,
                "article_number": article_number,
                "articleNumber": article_number,
            },
            article_number=article_number,
            landing_metadata=landing_metadata,
        )

        self.assertTrue(
            _ieee_metadata._landing_metadata_has_multimedia_scope(landing_metadata)
        )
        self.assertEqual(landing_metadata["sections"]["multimedia"], "true")

        supplementary_assets = client._fetch_multimedia_assets(attempt)

        self.assertEqual(len(supplementary_assets), 1)
        asset = supplementary_assets[0]
        self.assertEqual(asset["kind"], "supplementary")
        self.assertEqual(asset["section"], "supplementary")
        self.assertEqual(asset["filename_hint"], "supp1-3668995.pdf")
        self.assertEqual(
            asset["url"],
            "https://ieeexplore.ieee.org/ielx8/6245520/11315891/11417163/supp1-3668995.pdf",
        )
        self.assertEqual(asset["doi"], "10.1109/rita.2026.3668995/mm1")
        self.assertIn("Computational Thinking in Rural Education", asset["heading"])
        self.assertIn("Pensamiento Computacional", asset["caption"])
        request = transport.calls[0]
        self.assertEqual(request["url"], multimedia_url)
        self.assertEqual(request["headers"]["Referer"], document_url)
        self.assertEqual(request["headers"]["X-Requested-With"], "XMLHttpRequest")

    def test_ieee_multimedia_discovery_memoizes_redacted_url_per_runtime(
        self,
    ) -> None:
        article_number = "10388355"
        document_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        first_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/multimedia"
            "?token=first-secret"
        )
        rotated_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/multimedia"
            "?token=rotated-secret"
        )
        payload = json.dumps(
            {
                "multimedia": [
                    {
                        "filePath": "/documents/supplement.zip",
                        "fileName": "supplement.zip",
                        "title": "Supplementary archive",
                    }
                ]
            }
        ).encode("utf-8")
        transport = RecordingTransport(
            {
                ("GET", first_url): {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": payload,
                    "url": first_url,
                }
            }
        )
        attempt = _ieee_metadata.IeeeLandingAttempt(
            normalized_doi="10.1109/ACCESS.2024.3352924",
            landing_url=document_url,
            response_url=document_url,
            html_text="",
            merged_metadata={"article_number": article_number},
            article_number=article_number,
            landing_metadata={"hasMultimedia": True},
        )

        with RuntimeContext(env={}, transport=transport) as runtime_context:
            first = _ieee_supplementary.fetch_ieee_multimedia_assets(
                transport,
                attempt,
                multimedia_url=first_url,
                headers={"Referer": document_url},
                runtime_context=runtime_context,
            )
            second = _ieee_supplementary.fetch_ieee_multimedia_assets(
                transport,
                attempt,
                multimedia_url=rotated_url,
                headers={"Referer": document_url},
                runtime_context=runtime_context,
            )
            cache_dump = repr(runtime_context.session_cache)

        self.assertEqual(first, second)
        self.assertEqual(len(transport.calls), 1)
        self.assertNotIn("first-secret", cache_dump)
        self.assertNotIn("rotated-secret", cache_dump)

    def test_ieee_html_payload_merges_multimedia_supplementary_assets_from_landing_scope(
        self,
    ) -> None:
        """rule: rule-ieee-supplementary-scope
        rule: rule-supplementary-discovery-explicit-scope"""
        fixture_root = (
            REPO_ROOT
            / "tests"
            / "fixtures"
            / "golden_criteria"
            / "10.1109_RITA.2026.3668995"
        )
        doi = "10.1109/RITA.2026.3668995"
        article_number = "11417163"
        document_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        rest_url = f"https://ieeexplore.ieee.org/rest/document/{article_number}/?logAccess=true"
        references_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/references"
        )
        multimedia_url = (
            f"https://ieeexplore.ieee.org/rest/document/{article_number}/multimedia"
        )
        transport = RecordingTransport(
            {
                ("GET", document_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html; charset=utf-8"},
                    "body": (fixture_root / "landing.html").read_bytes(),
                    "url": document_url,
                },
                ("GET", references_url): {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": b'{"references":[]}',
                    "url": references_url,
                },
                ("GET", rest_url): {
                    "status_code": 200,
                    "headers": {"content-type": "text/html;charset=utf-8"},
                    "body": (fixture_root / "original.html").read_bytes(),
                    "url": rest_url,
                },
                ("GET", multimedia_url): {
                    "status_code": 200,
                    "headers": {"content-type": "application/json"},
                    "body": (fixture_root / "multimedia.json").read_bytes(),
                    "url": multimedia_url,
                },
            }
        )
        client = IeeeClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(
            doi, {"doi": doi, "landing_page_url": document_url}
        )

        supplementary_assets = [
            item
            for item in (
                raw_payload.content.extracted_assets
                if raw_payload.content is not None
                else []
            )
            if item.get("kind") == "supplementary"
        ]
        self.assertEqual(
            [item["url"] for item in supplementary_assets],
            [
                "https://ieeexplore.ieee.org/ielx8/6245520/11315891/11417163/supp1-3668995.pdf"
            ],
        )
        self.assertIn(multimedia_url, [str(call["url"]) for call in transport.calls])

    def test_ieee_table_asset_wins_over_shared_formula_candidate(self) -> None:
        """rule: rule-ieee-mediastore-body-assets"""
        article_number = "10388355"
        rest_url = f"https://ieeexplore.ieee.org/rest/document/{article_number}/?logAccess=true"

        extraction = _ieee_html._extract_ieee_html(
            _dynamic_html_with_ieee_equation_alt_table_asset(article_number).decode(
                "utf-8"
            ),
            rest_url,
            metadata={"title": "IEEE Dynamic Article"},
        )

        body_assets = [
            item
            for item in extraction.extracted_assets
            if item.get("section") == "body"
            and item.get("kind") in {"figure", "table", "formula"}
        ]
        self.assertEqual(len(body_assets), 1)
        table = body_assets[0]
        self.assertEqual(table["kind"], "table")
        self.assertEqual(table["heading"], "Table I.")
        self.assertEqual(
            table["url"],
            f"https://ieeexplore.ieee.org/mediastore/IEEE/content/media/{article_number}/{article_number}-table-1-large.gif",
        )
        self.assertEqual(
            table["preview_url"],
            f"https://ieeexplore.ieee.org/mediastore/IEEE/content/media/{article_number}/{article_number}-table-1-small.gif",
        )
        self.assertNotIn("Formula 1", json.dumps(extraction.extracted_assets))

    def test_ieee_merge_prefers_table_download_when_formula_shares_preview_url(
        self,
    ) -> None:
        """rule: rule-ieee-mediastore-body-assets"""
        article_number = "10388355"
        large_url = f"https://ieeexplore.ieee.org/mediastore/IEEE/content/media/{article_number}/{article_number}-table-1-large.gif"
        small_url = f"https://ieeexplore.ieee.org/mediastore/IEEE/content/media/{article_number}/{article_number}-table-1-small.gif"
        extracted_assets = [
            {
                "kind": "table",
                "heading": "Table I.",
                "caption": "Equation comparison table.",
                "url": large_url,
                "full_size_url": large_url,
                "preview_url": small_url,
                "section": "body",
            },
            {
                "kind": "formula",
                "heading": "Formula 1",
                "caption": "",
                "url": small_url,
                "preview_url": small_url,
                "section": "body",
            },
        ]
        downloaded_assets = [
            {
                "kind": "table",
                "heading": "Table I.",
                "caption": "Equation comparison table.",
                "original_url": small_url,
                "download_url": large_url,
                "source_url": large_url,
                "path": "/tmp/ieee-table.gif",
                "content_type": "image/gif",
                "download_tier": "full_size",
                "section": "body",
            },
            {
                "kind": "formula",
                "heading": "Formula 1",
                "caption": "",
                "original_url": small_url,
                "download_url": small_url,
                "source_url": small_url,
                "path": "/tmp/ieee-formula.gif",
                "content_type": "image/gif",
                "download_tier": "preview",
                "section": "body",
            },
        ]

        merged = merge_asset_retry_results(
            _ieee_html._dedupe_ieee_assets_by_priority(
                [dict(item) for item in extracted_assets],
                merge_fields=_ieee_html.IEEE_ASSET_URL_FIELDS,
            ),
            _ieee_html._dedupe_ieee_assets_by_priority(
                [dict(item) for item in downloaded_assets],
                merge_fields=(
                    *_ieee_html.IEEE_ASSET_URL_FIELDS,
                    *_ieee_html.IEEE_DOWNLOAD_MERGE_FIELDS,
                ),
            ),
            policy=_ieee_html.IEEE_ASSET_RETRY_POLICY,
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["kind"], "table")
        self.assertEqual(merged[0]["heading"], "Table I.")
        self.assertEqual(merged[0]["caption"], "Equation comparison table.")
        self.assertEqual(merged[0]["path"], "/tmp/ieee-table.gif")
        self.assertEqual(merged[0]["download_url"], large_url)
        self.assertEqual(merged[0]["download_tier"], "full_size")
        self.assertNotEqual(merged[0]["path"], "/tmp/ieee-formula.gif")

    def test_ieee_relative_rest_response_url_is_canonicalized_for_asset_urls(
        self,
    ) -> None:
        doi = "10.1109/ACCESS.2024.3352924"
        article_number = "10388355"
        landing_url = f"https://ieeexplore.ieee.org/document/{article_number}/"
        rest_url = f"https://ieeexplore.ieee.org/rest/document/{article_number}/?logAccess=true"
        relative_rest_url = f"/rest/document/{article_number}/?logAccess=true"
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
                    "url": relative_rest_url,
                },
            }
        )
        client = IeeeClient(transport, {})

        raw_payload = client.fetch_raw_fulltext(
            doi, {"doi": doi, "landing_page_url": landing_url}
        )

        self.assertEqual(raw_payload.source_url, rest_url)
        self.assertEqual(raw_payload.content.source_url, rest_url)
        body_assets = [
            item
            for item in raw_payload.content.extracted_assets
            if item.get("kind") in {"figure", "table"} and item.get("section") == "body"
        ]
        self.assertEqual(len(body_assets), 2)
        for asset in body_assets:
            self.assertTrue(
                str(asset["url"]).startswith("https://ieeexplore.ieee.org/mediastore/")
            )
            self.assertTrue(
                str(asset["full_size_url"]).startswith(
                    "https://ieeexplore.ieee.org/mediastore/"
                )
            )
            self.assertTrue(
                str(asset["preview_url"]).startswith(
                    "https://ieeexplore.ieee.org/mediastore/"
                )
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(
                _ieee_supplementary,
                "download_assets",
                return_value={"assets": [], "asset_failures": []},
            ) as mocked_download:
                client.download_related_assets(
                    doi,
                    {"doi": doi, "landing_page_url": landing_url},
                    raw_payload,
                    Path(tmpdir),
                    asset_profile="body",
                )

        self.assertIs(
            mocked_download.call_args.args[0], _ieee_supplementary.FIGURE_KIND
        )
        passed_assets = mocked_download.call_args.kwargs["assets"]
        self.assertTrue(
            all(str(item["url"]).startswith("https://") for item in passed_assets)
        )
        self.assertTrue(
            all(
                str(item["full_size_url"]).startswith("https://")
                for item in passed_assets
            )
        )
        self.assertTrue(
            all(
                str(item["preview_url"]).startswith("https://")
                for item in passed_assets
            )
        )
