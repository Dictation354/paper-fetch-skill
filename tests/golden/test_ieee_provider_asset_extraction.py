from __future__ import annotations
from paper_fetch.providers import _ieee_metadata
from tests.support._ieee_provider_support import *

# ruff: noqa: F403,F405


class IeeeProviderAssetExtractionTests(unittest.TestCase):
    def test_ieee_html_payload_merges_multimedia_supplementary_assets_from_landing_scope(
        self,
    ) -> None:
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

    def test_real_ieee_multimedia_fixture_yields_supplementary_asset_from_explicit_scope(
        self,
    ) -> None:
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
