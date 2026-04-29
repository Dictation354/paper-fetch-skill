from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from paper_fetch.extraction.html import _assets as html_assets
from paper_fetch.extraction.html import _metadata as html_metadata
from paper_fetch.extraction.html import _runtime as html_runtime
from paper_fetch.extraction.html import shared as html_shared
from paper_fetch.extraction.html.formula_rules import (
    formula_image_url_from_node,
    is_display_formula_node,
    looks_like_formula_image,
)
from paper_fetch.extraction.html.inline import normalize_html_inline_text
from paper_fetch.http import HttpTransport
from paper_fetch.providers import _science_pnas_html, _springer_html, _wiley_html
from tests.block_fixtures import block_asset
from tests.golden_criteria import golden_criteria_asset, golden_criteria_scenario_asset


class _DelayedAssetTransport(HttpTransport):
    def __init__(self, delays: dict[str, float]) -> None:
        self.delays = delays
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def request(self, method, url, **kwargs):
        del method, kwargs
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(self.delays.get(url, 0.0))
            return {
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": f"payload:{url}".encode("utf-8"),
                "url": url,
            }
        finally:
            with self.lock:
                self.active -= 1


class SharedHtmlHelperTests(unittest.TestCase):
    def test_shared_dom_helpers_normalize_common_tag_operations(self) -> None:
        soup = BeautifulSoup(
            """
<article class=" core-container  article ">
  <p>First <b>paragraph</b></p>
  <div><span>Nested</span></div>
</article>
""",
            "html.parser",
        )
        article = soup.find("article")
        assert article is not None

        children = html_shared.direct_child_tags(article)

        self.assertEqual([child.name for child in children], ["p", "div"])
        self.assertEqual(html_shared.class_tokens(article), {"core-container", "article"})
        self.assertEqual(html_shared.short_text(article.find("p")), "First paragraph")
        self.assertIs(html_shared.soup_root(article), soup)

        html_shared.append_text_block(article, "Appended text", tag_name="aside")

        appended = article.find("aside")
        self.assertIsNotNone(appended)
        self.assertEqual(appended.get_text(strip=True), "Appended text")

    def test_shared_payload_helpers_unescape_html_snippets_and_detect_images(self) -> None:
        body = b"<html><head><title>Sign&nbsp;in</title></head><body>A &amp; B</body></html>"

        self.assertEqual(html_shared.html_title_snippet(body), "Sign in")
        self.assertEqual(html_shared.html_text_snippet(body), "Sign in A & B")
        self.assertEqual(html_shared.image_magic_type(b"\x89PNG\r\n\x1a\npayload"), "image/png")

    def test_parse_html_metadata_reads_citation_fields(self) -> None:
        html = """
<html>
  <head>
    <meta name="citation_title" content="Example HTML Article" />
    <meta name="citation_author" content="Alice Example" />
    <meta name="citation_author" content="Bob Example" />
    <meta name="citation_doi" content="10.1234/example" />
    <meta name="citation_journal_title" content="Journal of HTML" />
    <meta name="citation_publication_date" content="2026-01-15" />
  </head>
</html>
"""

        metadata = html_metadata.parse_html_metadata(html, "https://example.test/article")

        self.assertEqual(metadata["title"], "Example HTML Article")
        self.assertEqual(metadata["authors"], ["Alice Example", "Bob Example"])
        self.assertEqual(metadata["doi"], "10.1234/example")
        self.assertEqual(metadata["journal_title"], "Journal of HTML")
        self.assertEqual(metadata["published"], "2026-01-15")

    def test_parse_html_metadata_does_not_treat_generic_description_as_abstract(self) -> None:
        """rule: rule-generic-metadata-boundaries"""
        html = golden_criteria_scenario_asset("generic_metadata_boundaries", "generic_description.html").read_text(
            encoding="utf-8"
        )

        metadata = html_metadata.parse_html_metadata(html, "https://www.pnas.org/doi/full/10.1073/pnas.2317456120")

        self.assertIsNone(metadata["abstract"])

    def test_parse_html_metadata_uses_redirect_stub_lookup_title(self) -> None:
        """rule: rule-generic-metadata-boundaries"""
        html = golden_criteria_scenario_asset("generic_metadata_boundaries", "redirect_stub.html").read_text(
            encoding="utf-8"
        )

        metadata = html_metadata.parse_html_metadata(html, "https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525")

        self.assertEqual(metadata["title"], "Stub Article Title")
        self.assertEqual(metadata["lookup_title"], "Stub Article Title")
        self.assertEqual(metadata["lookup_redirect_url"], "https://www.sciencedirect.com/science/article/pii/S0034425725000525")
        self.assertEqual(metadata["identifier_value"], "S0034425725000525")

    def test_extract_figure_assets_reads_generic_figure_blocks(self) -> None:
        html = """
<html>
  <body>
    <figure>
      <img src="/fig1.png" alt="Overview figure" />
      <figcaption>Figure 1. Overview figure.</figcaption>
    </figure>
  </body>
</html>
"""

        assets = html_assets.extract_figure_assets(html, "https://example.test/article")

        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["heading"], "Figure 1. Overview figure.")
        self.assertEqual(assets[0]["caption"], "Figure 1. Overview figure.")
        self.assertEqual(assets[0]["url"], "https://example.test/fig1.png")

    def test_extract_supplementary_assets_reads_supported_links(self) -> None:
        html = """
<html>
  <body>
    <a href="/supplement.pdf">Supplementary Data</a>
  </body>
</html>
"""

        assets = html_assets.extract_supplementary_assets(html, "https://example.test/article")

        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["heading"], "Supplementary Data")
        self.assertEqual(assets[0]["url"], "https://example.test/supplement.pdf")

    def test_extract_scoped_html_assets_uses_separate_body_and_supplementary_scopes(self) -> None:
        body_html = """
<html>
  <body>
    <figure>
      <img src="/fig1.png" alt="Overview figure" />
      <figcaption>Figure 1. Overview figure.</figcaption>
    </figure>
  </body>
</html>
"""
        supplementary_html = """
<html>
  <body>
    <a href="/supplement.pdf">Supplementary Data</a>
  </body>
</html>
"""

        assets = html_assets.extract_scoped_html_assets(
            body_html,
            "https://example.test/article",
            asset_profile="all",
            supplementary_html_text=supplementary_html,
        )

        self.assertEqual(
            [(asset["kind"], asset["section"]) for asset in assets],
            [("figure", "body"), ("supplementary", "supplementary")],
        )

    def test_wiley_asset_scopes_only_collect_supporting_information_downloads(self) -> None:
        """rule: rule-wiley-supporting-information-assets"""
        source_url = "https://onlinelibrary.wiley.com/doi/full/10.1111/example"
        html_text = """
<html>
  <body>
    <article lang="en">
      <section class="article-section article-section__full">
        <section class="article-section__content">
          <figure class="figure" id="example-fig-0001">
            <a href="/cms/asset/full/example-fig-0001.jpg">
              <img src="/cms/asset/preview/example-fig-0001.png" data-lg-src="/cms/asset/full/example-fig-0001.jpg" alt="Example figure" />
            </a>
            <figcaption>Figure 1. Example figure.</figcaption>
          </figure>
        </section>
      </section>
      <section class="article-section article-section__supporting" data-suppl="/doi/suppl/10.1111/example?onlyLog=true">
        <div class="accordion article-accordion">
          <h2>
            <a class="accordion__control" role="button" aria-controls="example-supInfo-0001" aria-expanded="false">
              <div tabindex="0" class="section__title" id="support-information-section"><span>Supporting Information</span></div>
            </a>
          </h2>
          <div class="accordion__content" role="region" aria-labelledby="support-information-section" id="example-supInfo-0001">
            <table class="support-info__table table article-section__table">
              <tbody>
                <tr>
                  <td headers="article-filename">
                    <a href="/action/downloadSupplement?doi=10.1111%2Fexample&amp;file=example-sup-0001-DataS1.docx">example-sup-0001-DataS1.docx</a>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </article>
  </body>
</html>
"""

        body_html, supplementary_html = _science_pnas_html.extract_browser_workflow_asset_html_scopes(
            html_text,
            source_url,
            "wiley",
        )
        assets = _wiley_html.extract_scoped_html_assets(
            body_html,
            source_url,
            asset_profile="all",
            supplementary_html_text=supplementary_html,
        )

        self.assertIn("downloadSupplement", supplementary_html)
        self.assertNotIn("downloadSupplement", body_html)
        self.assertEqual(
            [(asset["kind"], asset["section"]) for asset in assets],
            [("figure", "body"), ("supplementary", "supplementary")],
        )
        self.assertEqual(
            assets[1]["url"],
            "https://onlinelibrary.wiley.com/action/downloadSupplement?doi=10.1111%2Fexample&file=example-sup-0001-DataS1.docx",
        )
        self.assertEqual(assets[1]["filename_hint"], "example-sup-0001-DataS1.docx")
        self.assertFalse(any("fig-0001" in asset.get("url", "") for asset in assets if asset["kind"] == "supplementary"))

    def test_wiley_real_fixture_supporting_information_only_yields_true_supplementary_asset(self) -> None:
        """rule: rule-wiley-supporting-information-assets"""
        source_url = "https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16414"
        html_text = golden_criteria_asset("10.1111/gcb.16414", "original.html").read_text(encoding="utf-8")

        body_html, supplementary_html = _science_pnas_html.extract_browser_workflow_asset_html_scopes(
            html_text,
            source_url,
            "wiley",
        )
        assets = _wiley_html.extract_scoped_html_assets(
            body_html,
            source_url,
            asset_profile="all",
            supplementary_html_text=supplementary_html,
        )
        figure_assets = [asset for asset in assets if asset["kind"] == "figure"]
        supplementary_assets = [asset for asset in assets if asset["kind"] == "supplementary"]

        self.assertEqual(
            [asset["heading"] for asset in supplementary_assets],
            ["gcb16414-sup-0001-FigureS1.docx"],
        )
        self.assertEqual(
            [asset["url"] for asset in supplementary_assets],
            [
                "https://onlinelibrary.wiley.com/action/downloadSupplement?doi=10.1111%2Fgcb.16414&file=gcb16414-sup-0001-FigureS1.docx"
            ],
        )
        self.assertEqual(
            [asset["filename_hint"] for asset in supplementary_assets],
            ["gcb16414-sup-0001-FigureS1.docx"],
        )
        self.assertTrue(any("gcb16414-fig-0001-m.jpg" in asset.get("url", "") for asset in figure_assets))
        self.assertFalse(any("gcb16414-fig-" in asset.get("url", "") for asset in supplementary_assets))
        self.assertNotIn("gcb16414-sup-0001-FigureS1.docx", body_html)

    def test_download_supplementary_assets_uses_wiley_filename_hint_for_octet_stream(self) -> None:
        supplement_url = (
            "https://onlinelibrary.wiley.com/action/downloadSupplement?"
            "doi=10.1111%2Fgcb.16414&file=gcb16414-sup-0001-FigureS1.docx"
        )

        def opener_requester(opener, url, **kwargs):
            del opener, kwargs
            self.assertEqual(url, supplement_url)
            return {
                "status_code": 200,
                "headers": {"content-type": "application/octet-stream"},
                "body": b"supplementary-docx",
                "url": "https://onlinelibrary.wiley.com/action/downloadSupplement",
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_supplementary_assets(
                HttpTransport(),
                article_id="10.1111/gcb.16414",
                assets=[
                    {
                        "kind": "supplementary",
                        "heading": "gcb16414-sup-0001-FigureS1.docx",
                        "url": supplement_url,
                        "section": "supplementary",
                        "filename_hint": "gcb16414-sup-0001-FigureS1.docx",
                    }
                ],
                output_dir=Path(tmpdir),
                user_agent="paper-fetch-test",
                asset_profile="all",
                cookie_opener_builder=lambda *args, **kwargs: object(),
                opener_requester=opener_requester,
            )

        self.assertEqual(result["asset_failures"], [])
        self.assertEqual(Path(result["assets"][0]["path"]).name, "gcb16414-sup-0001-FigureS1.docx")

    def test_download_supplementary_assets_routes_source_data_into_subdirectory(self) -> None:
        """rule: rule-springer-supplementary-scope"""
        responses = {
            "https://example.test/supplement.pdf": {
                "status_code": 200,
                "headers": {"content-type": "application/pdf"},
                "body": b"supplementary-pdf",
                "url": "https://example.test/supplement.pdf",
            },
            "https://example.test/source-data.csv": {
                "status_code": 200,
                "headers": {"content-type": "text/plain"},
                "body": b"source-data",
                "url": "https://example.test/source-data.csv",
            },
        }

        def opener_requester(opener, url, **kwargs):
            del opener, kwargs
            return responses[url]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_supplementary_assets(
                HttpTransport(),
                article_id="10.1000/example",
                assets=[
                    {
                        "kind": "supplementary",
                        "heading": "Supplementary Information",
                        "url": "https://example.test/supplement.pdf",
                        "section": "supplementary",
                    },
                    {
                        "kind": "supplementary",
                        "heading": "Source Data Fig. 1",
                        "url": "https://example.test/source-data.csv",
                        "section": "supplementary",
                        "asset_kind": "source_data",
                    },
                ],
                output_dir=Path(tmpdir),
                user_agent="paper-fetch-test",
                asset_profile="all",
                cookie_opener_builder=lambda *args, **kwargs: object(),
                opener_requester=opener_requester,
            )

            asset_paths = [Path(asset["path"]) for asset in result["assets"]]

            self.assertEqual(result["asset_failures"], [])
            self.assertEqual(asset_paths[0].parent.name, "10.1000_example_assets")
            self.assertEqual(asset_paths[1].parent.name, "source_data")
            self.assertEqual(asset_paths[1].parent.parent.name, "10.1000_example_assets")

    def test_download_supplementary_assets_with_only_source_data_creates_only_source_data_subdirectory(self) -> None:
        """rule: rule-springer-supplementary-scope"""
        def opener_requester(opener, url, **kwargs):
            del opener, kwargs
            return {
                "status_code": 200,
                "headers": {"content-type": "text/csv"},
                "body": b"source-data-only",
                "url": url,
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = html_assets.download_supplementary_assets(
                HttpTransport(),
                article_id="10.1000/source-only",
                assets=[
                    {
                        "kind": "supplementary",
                        "heading": "Source Data Fig. 1",
                        "url": "https://example.test/source-data-only.csv",
                        "section": "supplementary",
                        "asset_kind": "source_data",
                    }
                ],
                output_dir=output_dir,
                user_agent="paper-fetch-test",
                asset_profile="all",
                cookie_opener_builder=lambda *args, **kwargs: object(),
                opener_requester=opener_requester,
            )

            asset_root = output_dir / "10.1000_source-only_assets"
            root_entries = sorted(path.name for path in asset_root.iterdir())

            self.assertEqual(result["asset_failures"], [])
            self.assertEqual(Path(result["assets"][0]["path"]).parent.name, "source_data")
            self.assertEqual(root_entries, ["source_data"])

    def test_wiley_body_figures_are_not_promoted_to_supplementary_without_supporting_information(self) -> None:
        """rule: rule-wiley-supporting-information-assets"""
        body_html = """
<section class="article-section__content">
  <figure class="figure" id="example-fig-0001">
    <a href="/cms/asset/full/example-fig-0001.jpg">
      <img src="/cms/asset/preview/example-fig-0001.png" data-lg-src="/cms/asset/full/example-fig-0001.jpg" alt="Example figure" />
    </a>
    <figcaption>Figure 1. Example figure.</figcaption>
  </figure>
</section>
"""

        assets = _wiley_html.extract_scoped_html_assets(
            body_html,
            "https://onlinelibrary.wiley.com/doi/full/10.1111/example",
            asset_profile="all",
            supplementary_html_text="",
        )

        self.assertEqual([asset["kind"] for asset in assets], ["figure"])
        self.assertFalse(any(asset["kind"] == "supplementary" for asset in assets))

    def test_extract_scoped_html_assets_empty_supplementary_scope_does_not_scan_body(self) -> None:
        """rule: rule-science-pnas-supplementary-sections"""
        body_html = """
<html>
  <body>
    <a href="https://example.test/data.csv">Data file, not supplementary material.</a>
  </body>
</html>
"""

        assets = html_assets.extract_scoped_html_assets(
            body_html,
            "https://example.test/article",
            asset_profile="all",
            supplementary_html_text="",
        )

        self.assertFalse(any(asset["kind"] == "supplementary" for asset in assets))

    def test_science_real_fixture_supplementary_comes_only_from_supplementary_section(self) -> None:
        """rule: rule-science-pnas-supplementary-sections"""
        source_url = "https://www.science.org/doi/full/10.1126/sciadv.adl6155"
        html_text = golden_criteria_asset("10.1126/sciadv.adl6155", "original.html").read_text(
            encoding="utf-8",
            errors="ignore",
        )

        body_html, supplementary_html = _science_pnas_html.extract_browser_workflow_asset_html_scopes(
            html_text,
            source_url,
            "science",
        )
        assets = _science_pnas_html.extract_scoped_html_assets(
            body_html,
            source_url,
            asset_profile="all",
            supplementary_html_text=supplementary_html,
        )
        supplementary_assets = [asset for asset in assets if asset["kind"] == "supplementary"]

        self.assertIn("co2_gr_mlo.txt", body_html)
        self.assertNotIn("co2_gr_mlo.txt", supplementary_html)
        self.assertIn("sciadv.adl6155_sm.pdf", supplementary_html)
        self.assertEqual(
            [asset["url"] for asset in supplementary_assets],
            [
                "https://www.science.org/doi/suppl/10.1126/sciadv.adl6155/suppl_file/sciadv.adl6155_sm.pdf"
            ],
        )

    def test_pnas_real_fixture_supplementary_ignores_body_anchor_to_section(self) -> None:
        """rule: rule-science-pnas-supplementary-sections"""
        source_url = "https://www.pnas.org/doi/full/10.1073/pnas.2509692123"
        html_text = block_asset("10.1073/pnas.2509692123", "raw.html").read_text(
            encoding="utf-8",
            errors="ignore",
        )

        body_html, supplementary_html = _science_pnas_html.extract_browser_workflow_asset_html_scopes(
            html_text,
            source_url,
            "pnas",
        )
        assets = _science_pnas_html.extract_scoped_html_assets(
            body_html,
            source_url,
            asset_profile="all",
            supplementary_html_text=supplementary_html,
        )
        supplementary_assets = [asset for asset in assets if asset["kind"] == "supplementary"]

        self.assertIn("#supplementary-materials", body_html)
        self.assertNotIn("#supplementary-materials", supplementary_html)
        self.assertIn("pnas.2509692123.sapp.pdf", supplementary_html)
        self.assertEqual(
            [asset["url"] for asset in supplementary_assets],
            [
                "https://www.pnas.org/doi/suppl/10.1073/pnas.2509692123/suppl_file/pnas.2509692123.sapp.pdf",
                "https://www.pnas.org/doi/suppl/10.1073/pnas.2509692123/suppl_file/pnas.2509692123.sd01.xlsx",
            ],
        )

    def test_supplementary_response_block_reason_detects_challenge_html(self) -> None:
        body = b"<html><head><title>Just a moment...</title></head><body>Checking your browser before accessing</body></html>"

        reason = html_assets.supplementary_response_block_reason("text/html; charset=utf-8", body)

        self.assertEqual(reason, "cloudflare_challenge")

    def test_figure_download_candidates_prefers_figure_page_full_size_url(self) -> None:
        candidates = html_assets.figure_download_candidates(
            HttpTransport(),
            asset={
                "figure_page_url": "https://example.test/article/figures/1",
                "url": "https://example.test/preview.png",
            },
            user_agent="paper-fetch-test",
            figure_page_fetcher=lambda url: (
                """
<html>
  <head>
    <meta name="twitter:image" content="https://example.test/full.png" />
  </head>
</html>
""",
                url,
            ),
        )

        self.assertEqual(candidates[0], "https://example.test/full.png")

    def test_download_figure_assets_resolves_http_candidates_in_parallel_but_writes_in_order(self) -> None:
        urls = [f"https://example.test/fig{i}.png" for i in range(4)]
        transport = _DelayedAssetTransport({url: 0.05 for url in urls})
        assets = [
            {"kind": "figure", "heading": f"Figure {index}", "caption": "", "url": url, "section": "body"}
            for index, url in enumerate(urls)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_figure_assets(
                transport,
                article_id="10.5555/parallel",
                assets=assets,
                output_dir=Path(tmpdir),
                user_agent="paper-fetch-test",
                asset_profile="all",
            )

        self.assertGreater(transport.max_active, 1)
        self.assertEqual([asset["heading"] for asset in result["assets"]], [asset["heading"] for asset in assets])
        self.assertEqual(result["asset_failures"], [])

    def test_download_figure_assets_respects_explicit_concurrency_limit(self) -> None:
        urls = [f"https://example.test/serial-fig{i}.png" for i in range(3)]
        transport = _DelayedAssetTransport({url: 0.01 for url in urls})
        assets = [
            {"kind": "figure", "heading": f"Figure {index}", "caption": "", "url": url, "section": "body"}
            for index, url in enumerate(urls)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_figure_assets(
                transport,
                article_id="10.5555/serial",
                assets=assets,
                output_dir=Path(tmpdir),
                user_agent="paper-fetch-test",
                asset_profile="all",
                asset_download_concurrency=1,
            )

        self.assertEqual(transport.max_active, 1)
        self.assertEqual([asset["heading"] for asset in result["assets"]], [asset["heading"] for asset in assets])

    def test_download_supplementary_assets_resolves_files_in_parallel_but_writes_in_order(self) -> None:
        urls = [f"https://example.test/supp{i}.pdf" for i in range(4)]
        state = {"active": 0, "max_active": 0}
        lock = threading.Lock()

        def opener_requester(opener, url, **kwargs):
            del opener, kwargs
            with lock:
                state["active"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
            try:
                time.sleep(0.05)
                return {
                    "status_code": 200,
                    "headers": {"content-type": "application/pdf"},
                    "body": f"payload:{url}".encode("utf-8"),
                    "url": url,
                }
            finally:
                with lock:
                    state["active"] -= 1

        assets = [
            {"kind": "supplementary", "heading": f"Supplement {index}", "url": url, "section": "supplementary"}
            for index, url in enumerate(urls)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_supplementary_assets(
                HttpTransport(),
                article_id="10.5555/parallel",
                assets=assets,
                output_dir=Path(tmpdir),
                user_agent="paper-fetch-test",
                asset_profile="all",
                cookie_opener_builder=lambda *args, **kwargs: object(),
                opener_requester=opener_requester,
            )

        self.assertGreater(state["max_active"], 1)
        self.assertEqual([asset["heading"] for asset in result["assets"]], [asset["heading"] for asset in assets])
        self.assertEqual(result["asset_failures"], [])

    def test_download_supplementary_assets_respects_explicit_concurrency_limit(self) -> None:
        urls = [f"https://example.test/serial-supp{i}.pdf" for i in range(3)]
        state = {"active": 0, "max_active": 0}
        lock = threading.Lock()

        def opener_requester(opener, url, **kwargs):
            del opener, kwargs
            with lock:
                state["active"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
            try:
                time.sleep(0.01)
                return {
                    "status_code": 200,
                    "headers": {"content-type": "application/pdf"},
                    "body": f"payload:{url}".encode("utf-8"),
                    "url": url,
                }
            finally:
                with lock:
                    state["active"] -= 1

        assets = [
            {"kind": "supplementary", "heading": f"Supplement {index}", "url": url, "section": "supplementary"}
            for index, url in enumerate(urls)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = html_assets.download_supplementary_assets(
                HttpTransport(),
                article_id="10.5555/serial",
                assets=assets,
                output_dir=Path(tmpdir),
                user_agent="paper-fetch-test",
                asset_profile="all",
                cookie_opener_builder=lambda *args, **kwargs: object(),
                opener_requester=opener_requester,
                asset_download_concurrency=1,
            )

        self.assertEqual(state["max_active"], 1)
        self.assertEqual([asset["heading"] for asset in result["assets"]], [asset["heading"] for asset in assets])

    def test_clean_html_for_extraction_removes_noise_but_keeps_sections(self) -> None:
        html = """
<html>
  <body>
    <nav>Skip to main content</nav>
    <article>
      <h2>Introduction</h2>
      <p>Important body text.</p>
    </article>
  </body>
</html>
"""

        cleaned = html_runtime.clean_html_for_extraction(html)

        self.assertIn("Introduction", cleaned)
        self.assertIn("Important body text.", cleaned)
        self.assertNotIn("Skip to main content", cleaned)

    def test_extract_html_section_hints_reads_structural_data_availability(self) -> None:
        html = """
<html>
  <body>
    <section class="data-availability">
      <h2>Availability Statement</h2>
      <p>Data are archived in a public repository.</p>
    </section>
  </body>
</html>
"""

        hints = html_runtime.extract_html_section_hints(html)

        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0]["heading"], "Availability Statement")
        self.assertEqual(hints[0]["kind"], "data_availability")

    def test_extract_html_section_hints_reads_structural_code_availability(self) -> None:
        html = """
<html>
  <body>
    <section id="code-availability">
      <h2>Availability Statement</h2>
      <p>Analysis code is archived in a public repository.</p>
    </section>
  </body>
</html>
"""

        hints = html_runtime.extract_html_section_hints(html)

        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0]["heading"], "Availability Statement")
        self.assertEqual(hints[0]["kind"], "code_availability")

    def test_extract_article_markdown_preserves_data_availability_section(self) -> None:
        html = """
<html>
  <body>
    <article>
      <h1>Example Article</h1>
      <h2>Results</h2>
      <p>Important body text that remains in the shared markdown output.</p>
      <h2>Data Availability</h2>
      <p>The data are available from the corresponding author on request.</p>
    </article>
  </body>
</html>
"""

        original_trafilatura = html_runtime.trafilatura
        try:
            html_runtime.trafilatura = None
            markdown = html_runtime.extract_article_markdown(html, "https://example.test/article")
        finally:
            html_runtime.trafilatura = original_trafilatura

        self.assertIn("## Results", markdown)
        self.assertIn("## Data Availability", markdown)
        self.assertIn("The data are available from the corresponding author on request.", markdown)

    def test_clean_markdown_pnas_alerts_require_pnas_profile(self) -> None:
        markdown = """
# Article

Sign up for PNAS alerts.

## Results

Important body text.
"""

        generic_cleaned = html_runtime.clean_markdown(markdown)
        pnas_cleaned = html_runtime.clean_markdown(markdown, noise_profile="pnas")

        self.assertIn("Sign up for PNAS alerts.", generic_cleaned)
        self.assertNotIn("Sign up for PNAS alerts.", pnas_cleaned)

    def test_real_nature_fixture_keeps_source_data_without_chrome_sections(self) -> None:
        source_data_html = golden_criteria_asset("10.1038/s41561-022-00912-7", "original.html").read_text(
            encoding="utf-8",
            errors="ignore",
        )
        self.assertTrue("source data fig." in source_data_html.casefold())

        source_data_markdown = _springer_html.extract_html_payload(
            source_data_html,
            "https://www.nature.com/articles/s41561-022-00912-7",
        )["markdown_text"]

        self.assertIn("Source data", source_data_markdown)

        chrome_html = golden_criteria_asset("10.1038/nature13376", "original.html").read_text(
            encoding="utf-8",
            errors="ignore",
        )
        chrome_html_text = chrome_html.casefold()
        self.assertTrue("rights and permissions" in chrome_html_text)
        self.assertTrue("open access" in chrome_html_text)

        chrome_markdown = _springer_html.extract_html_payload(
            chrome_html,
            "https://www.nature.com/articles/nature13376",
        )["markdown_text"]

        self.assertNotIn("## Permissions", chrome_markdown)
        self.assertNotIn("## Open Access", chrome_markdown)
        self.assertNotIn("## Rights and permissions", chrome_markdown)

    def test_inline_normalization_is_shared_for_body_heading_and_table_text(self) -> None:
        """rule: rule-preserve-inline-semantics-in-body-and-tables"""
        raw_text = "CO <sub> 2 </sub> emission </sup> +"

        self.assertEqual(normalize_html_inline_text("CO <sub> 2 </sub> emissions"), "CO<sub>2</sub> emissions")
        self.assertEqual(normalize_html_inline_text("m <sup> -2 </sup> )", policy="body"), "m<sup>-2</sup>)")
        self.assertEqual(
            normalize_html_inline_text("m <sup> -2 </sup> )", policy="table_cell"),
            "m<sup>-2</sup> )",
        )
        self.assertEqual(normalize_html_inline_text(raw_text, policy="heading"), "CO<sub>2</sub> emission</sup>+")

    def test_formula_rules_detect_real_formula_image_urls(self) -> None:
        """rule: rule-preserve-formula-image-fallbacks"""
        wiley_html = golden_criteria_asset("10.1111/gcb.15322", "original.html").read_text(
            encoding="utf-8",
            errors="ignore",
        )
        nature_html = golden_criteria_asset("10.1038/nature12915", "original.html").read_text(
            encoding="utf-8",
            errors="ignore",
        )
        wiley_soup = BeautifulSoup(wiley_html, "html.parser")
        nature_soup = BeautifulSoup(nature_html, "html.parser")
        image = wiley_soup.select_one(".inline-equation img")
        nature_display = nature_soup.select_one(".c-article-equation")
        nature_image = nature_soup.select_one("img[src*='_Equ1_HTML']")
        figure_image = nature_soup.select_one("img[src*='Fig1_HTML']")

        self.assertIn("gcb15322-math-0001.png", formula_image_url_from_node(image))
        self.assertTrue(looks_like_formula_image(image))
        self.assertTrue(is_display_formula_node(nature_display))
        self.assertIn("_Equ1_HTML.jpg", formula_image_url_from_node(nature_image))
        self.assertTrue(looks_like_formula_image(nature_image))
        self.assertFalse(looks_like_formula_image(figure_image))

    def test_extract_formula_assets_reuses_shared_formula_rules(self) -> None:
        html = golden_criteria_asset("10.1038/nature12915", "original.html").read_text(
            encoding="utf-8",
            errors="ignore",
        )

        assets = html_assets.extract_formula_assets(html, "https://www.nature.com/articles/nature12915")

        self.assertGreaterEqual(len(assets), 2)
        self.assertTrue(all(asset["kind"] == "formula" for asset in assets))
        self.assertTrue(any(asset["heading"] == "Equ1" and "_Equ1_HTML.jpg" in asset["url"] for asset in assets))
        self.assertTrue(any(asset["heading"] == "Equ2" and "_Equ2_HTML.jpg" in asset["url"] for asset in assets))
        self.assertFalse(any("Fig1_HTML" in asset["url"] for asset in assets))

    def test_clean_markdown_registers_springer_nature_profile(self) -> None:
        """rule: rule-springer-article-root-chrome-pruning"""
        markdown = """
# Article

Sign up for alerts

## Results

Important body text.
"""

        generic_cleaned = html_runtime.clean_markdown(markdown)
        springer_cleaned = html_runtime.clean_markdown(markdown, noise_profile="springer_nature")

        self.assertIn("Sign up for alerts", generic_cleaned)
        self.assertNotIn("Sign up for alerts", springer_cleaned)
