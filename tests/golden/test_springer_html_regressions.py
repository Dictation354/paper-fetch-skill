from __future__ import annotations
from paper_fetch.providers import springer as springer_provider
from tests.block_fixtures import block_asset
import re
import tempfile
from tests.support.captured_images import download_captured_images
import unittest
from pathlib import Path
from paper_fetch.artifacts import ArtifactStore
from paper_fetch.http import HttpTransport
from paper_fetch.providers import _springer_html as springer_html
from paper_fetch.quality.html_availability import assess_html_fulltext_availability
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.tracing import trace_from_markers
from paper_fetch.utils import normalize_text
from tests.golden_criteria import (
    golden_criteria_asset,
    golden_criteria_sample_for_doi,
)


class SpringerHtmlRegressionTests(unittest.TestCase):
    def _build_article_from_html(
        self,
        html_path: Path,
        source_url: str,
        *,
        doi: str,
        fake_downloaded_assets: bool = False,
        extracted_asset_profile: str = "body",
    ):
        html_text = html_path.read_text(encoding="utf-8", errors="ignore")
        base_metadata = {
            "doi": doi,
            "landing_page_url": source_url,
            "authors": [],
            "fulltext_links": [],
            "references": [],
        }
        html_metadata = springer_html.parse_html_metadata(html_text, source_url)
        merged_metadata = springer_html.merge_html_metadata(
            base_metadata, html_metadata
        )
        if not merged_metadata.get("doi"):
            merged_metadata["doi"] = doi
        extraction_payload = springer_html.extract_html_payload(
            html_text,
            source_url,
            title=str(merged_metadata.get("title") or ""),
        )
        extracted_assets = (
            []
            if extracted_asset_profile == "none"
            else springer_html.extract_html_assets(
                html_text,
                source_url,
                asset_profile=extracted_asset_profile,
            )
        )
        abstract_sections = list(extraction_payload["abstract_sections"])
        diagnostics = assess_html_fulltext_availability(
            extraction_payload["markdown_text"],
            merged_metadata,
            provider="springer",
            html_text=html_text,
            title=str(merged_metadata.get("title") or ""),
            final_url=source_url,
            section_hints=extraction_payload["section_hints"],
        )
        raw_payload = RawFulltextPayload(
            provider="springer",
            source_url=source_url,
            content_type="text/html",
            body=html_text.encode("utf-8"),
            content=ProviderContent(
                route_kind="html",
                source_url=source_url,
                content_type="text/html",
                body=html_text.encode("utf-8"),
                markdown_text=extraction_payload["markdown_text"],
                extracted_assets=extracted_assets,
                merged_metadata=merged_metadata,
                diagnostics={
                    "availability_diagnostics": diagnostics.to_dict(),
                    "extraction": {
                        "abstract_text": normalize_text(abstract_sections[0]["text"])
                        if abstract_sections
                        else None,
                        "abstract_sections": abstract_sections,
                        "section_hints": list(extraction_payload["section_hints"]),
                        "extracted_authors": list(
                            extraction_payload.get("extracted_authors") or []
                        ),
                        "references": list(extraction_payload.get("references") or []),
                    },
                },
            ),
            trace=trace_from_markers(["fulltext:springer_html_ok"]),
            merged_metadata=merged_metadata,
        )
        downloaded_assets = (
            self._fake_downloaded_assets(extracted_assets)
            if fake_downloaded_assets
            else None
        )
        article = springer_provider.SpringerClient(
            HttpTransport(), {}
        ).to_article_model(
            merged_metadata,
            raw_payload,
            downloaded_assets=downloaded_assets,
        )
        return article, extraction_payload, diagnostics, extracted_assets

    def _fake_downloaded_assets(
        self, assets: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        downloaded_assets: list[dict[str, str]] = []
        for index, asset in enumerate(assets, start=1):
            if normalize_text(asset.get("kind")).lower() != "figure":
                continue
            section = normalize_text(asset.get("section")).lower()
            if section in {"supplementary", "appendix"}:
                continue
            downloaded_asset = dict(asset)
            downloaded_asset["path"] = f"/tmp/fake-springer-figure-{index}.png"
            downloaded_assets.append(downloaded_asset)
        return downloaded_assets

    def test_springernature_fulltext_markdown_strips_ai_alt_disclaimer(self) -> None:
        sample = golden_criteria_sample_for_doi("10.1038/s44221-022-00024-x")
        doi = str(sample["doi"])
        source_url = str(sample["source_url"])

        article, extraction_payload, diagnostics, _ = self._build_article_from_html(
            golden_criteria_asset(doi, "original.html"),
            source_url,
            doi=doi,
        )

        self.assertEqual(diagnostics.content_kind, "fulltext")
        self.assertEqual(article.quality.content_kind, "fulltext")
        self.assertNotIn(
            "The alternative text for this image may have been generated using AI.",
            extraction_payload["markdown_text"],
        )
        self.assertNotIn(
            "The alternative text for this image may have been generated using AI.",
            article.to_ai_markdown(max_tokens="full_text"),
        )

    def test_nature_fixture_keeps_data_and_code_availability_sections(self) -> None:
        doi = "10.1038/s43247-024-01885-8"
        article, extraction_payload, diagnostics, _ = self._build_article_from_html(
            golden_criteria_asset(doi, "original.html"),
            "https://www.nature.com/articles/s43247-024-01885-8",
            doi=doi,
        )

        rendered = article.to_ai_markdown(max_tokens="full_text")
        section_pairs = [
            (section.heading, section.kind) for section in article.sections
        ]
        hint_pairs = [
            (item["heading"], item["kind"])
            for item in extraction_payload["section_hints"]
        ]

        self.assertEqual(diagnostics.content_kind, "fulltext")
        self.assertIn("## Data availability", rendered)
        self.assertIn("## Code availability", rendered)
        self.assertIn(("Data availability", "data_availability"), section_pairs)
        self.assertIn(("Code availability", "code_availability"), section_pairs)
        self.assertIn(("Data availability", "data_availability"), hint_pairs)
        self.assertIn(("Code availability", "code_availability"), hint_pairs)

    def test_real_nature_fixture_separates_source_data_from_supplementary_assets(
        self,
    ) -> None:
        source_url = "https://www.nature.com/articles/s41561-022-00912-7"
        html_text = golden_criteria_asset(
            "10.1038/s41561-022-00912-7", "original.html"
        ).read_text(encoding="utf-8")

        body_html, supplementary_html = springer_html.extract_asset_html_scopes(
            html_text, source_url
        )
        source_data_html = springer_html.extract_source_data_html_scope(
            html_text, source_url
        )
        assets = springer_html.extract_scoped_html_assets(
            body_html,
            source_url,
            asset_profile="all",
            supplementary_html_text=supplementary_html,
            source_data_html_text=source_data_html,
        )

        supplementary_assets = [
            asset
            for asset in assets
            if asset.get("kind") == "supplementary"
            and asset.get("asset_kind") != "source_data"
        ]
        source_data_assets = [
            asset for asset in assets if asset.get("asset_kind") == "source_data"
        ]

        self.assertIn("Extended data", supplementary_html)
        self.assertIn("Supplementary information", supplementary_html)
        self.assertNotIn("Source data", supplementary_html)
        self.assertIn("Source data", source_data_html)
        self.assertTrue(
            any(
                asset.get("url", "").endswith("MOESM1_ESM.pdf")
                for asset in supplementary_assets
            )
        )
        self.assertFalse(
            any("MOESM2_ESM" in asset.get("url", "") for asset in supplementary_assets)
        )
        self.assertTrue(
            any(
                asset.get("url", "").endswith("MOESM2_ESM.zip")
                for asset in source_data_assets
            )
        )
        self.assertTrue(
            any(
                asset.get("url", "").endswith("MOESM4_ESM.csv")
                for asset in source_data_assets
            )
        )

    def test_real_nature_fixture_resolves_source_data_links_from_extended_data_descriptions(
        self,
    ) -> None:
        source_url = "https://www.nature.com/articles/s41558-022-01584-2"
        html_text = golden_criteria_asset(
            "10.1038/s41558-022-01584-2", "original.html"
        ).read_text(encoding="utf-8")

        body_html, supplementary_html = springer_html.extract_asset_html_scopes(
            html_text, source_url
        )
        source_data_html = springer_html.extract_source_data_html_scope(
            html_text, source_url
        )
        assets = springer_html.extract_scoped_html_assets(
            body_html,
            source_url,
            asset_profile="all",
            supplementary_html_text=supplementary_html,
            source_data_html_text=source_data_html,
        )

        supplementary_assets = [
            asset
            for asset in assets
            if asset.get("kind") == "supplementary"
            and asset.get("asset_kind") != "source_data"
        ]
        source_data_assets = [
            asset for asset in assets if asset.get("asset_kind") == "source_data"
        ]

        self.assertTrue(
            any(
                asset.get("figure_page_url", "").endswith("/figures/5")
                and asset.get("kind") == "figure"
                and asset.get("section") == "supplementary"
                for asset in assets
            )
        )
        self.assertTrue(
            any(
                asset.get("url", "").endswith("MOESM5_ESM.xlsx")
                for asset in source_data_assets
            )
        )
        self.assertTrue(
            any(
                asset.get("url", "").endswith("MOESM13_ESM.xlsx")
                for asset in source_data_assets
            )
        )
        self.assertFalse(
            any(
                "MOESM5_ESM.xlsx" in asset.get("url", "")
                for asset in supplementary_assets
            )
        )

    def test_real_nature_fixture_skips_peer_review_files_from_supplementary_assets(
        self,
    ) -> None:
        source_url = "https://www.nature.com/articles/s43247-024-01270-5"
        html_text = golden_criteria_asset(
            "10.1038/s43247-024-01270-5", "original.html"
        ).read_text(encoding="utf-8")

        body_html, supplementary_html = springer_html.extract_asset_html_scopes(
            html_text, source_url
        )
        source_data_html = springer_html.extract_source_data_html_scope(
            html_text, source_url
        )
        assets = springer_html.extract_scoped_html_assets(
            body_html,
            source_url,
            asset_profile="all",
            supplementary_html_text=supplementary_html,
            source_data_html_text=source_data_html,
        )

        supplementary_headings = [
            normalize_text(str(asset.get("heading") or "")).lower()
            for asset in assets
            if asset.get("kind") == "supplementary"
            and asset.get("asset_kind") != "source_data"
        ]

        self.assertIn("supplementary information", supplementary_headings)
        self.assertFalse(
            any("peer review" in heading for heading in supplementary_headings)
        )

    def test_springer_html_route_saves_original_html_in_article_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir) / "10.1038_nature12915"
            download_dir.mkdir()
            content = ProviderContent(
                route_kind="html",
                source_url="https://www.nature.com/articles/nature12915",
                content_type="text/html; charset=utf-8",
                body=b"<html><body>fixture</body></html>",
            )

            warnings, trail = ArtifactStore.from_download_dir(
                download_dir
            ).save_provider_html_payload(
                "springer",
                content=content,
                doi="10.1038/nature12915",
                metadata={"title": "Example"},
            )

            self.assertEqual(warnings, [])
            self.assertIn("download:springer_html_saved", trail)
            saved_path = download_dir / "unknown_unknown_Example_original.html"
            self.assertTrue(saved_path.exists())
            self.assertEqual(saved_path.read_bytes(), content.body)

    def test_old_nature_fixture_keeps_single_methods_summary_and_methods_sections(
        self,
    ) -> None:
        html_path = golden_criteria_asset("10.1038/nature12915", "original.html")
        source_url = "https://www.nature.com/articles/nature12915"

        article, extraction_payload, diagnostics, extracted_assets = (
            self._build_article_from_html(
                html_path,
                source_url,
                doi="10.1038/nature12915",
            )
        )
        markdown_text = extraction_payload["markdown_text"]

        self.assertEqual(diagnostics.content_kind, "fulltext")
        self.assertEqual(article.quality.content_kind, "fulltext")
        self.assertEqual(
            [
                section.get("heading")
                for section in extraction_payload["abstract_sections"]
            ],
            ["Abstract"],
        )
        figure_assets = [
            asset
            for asset in extracted_assets
            if normalize_text(asset.get("kind")).lower() == "figure"
        ]
        formula_assets = [
            asset
            for asset in extracted_assets
            if normalize_text(asset.get("kind")).lower() == "formula"
        ]
        self.assertEqual(len(figure_assets), 3)
        self.assertGreater(len(formula_assets), 0)
        self.assertIn("_Equ1_HTML.jpg", markdown_text)
        self.assertIn("_Equ2_HTML.jpg", markdown_text)
        self.assertIn("![Formula](https://media.springernature.com/", markdown_text)
        self.assertTrue(
            any(
                "_Equ1_HTML.jpg" in normalize_text(asset.get("url"))
                for asset in formula_assets
            )
        )
        self.assertTrue(
            any(
                "_Equ2_HTML.jpg" in normalize_text(asset.get("url"))
                for asset in formula_assets
            )
        )
        self.assertFalse(
            any(
                "Fig1_HTML" in normalize_text(asset.get("url"))
                for asset in formula_assets
            )
        )
        self.assertNotIn("PowerPoint slide", markdown_text)
        self.assertNotIn("Full size image", markdown_text)
        for asset in figure_assets:
            self.assertNotIn("PowerPoint slide", str(asset.get("caption") or ""))
            self.assertNotIn("Full size image", str(asset.get("caption") or ""))
        self.assertEqual(
            len(re.findall(r"(?m)^## Methods Summary\s*$", markdown_text)), 1
        )
        self.assertEqual(len(re.findall(r"(?m)^## Methods\s*$", markdown_text)), 1)
        self.assertIn(
            "## Methods\n",
            article.to_ai_markdown(asset_profile="body", max_tokens="full_text"),
        )
        self.assertNotIn("## Online Methods", markdown_text)
        figure_index = markdown_text.find("**Figure 1.**")
        methods_summary_index = markdown_text.find("## Methods Summary")
        self.assertGreaterEqual(figure_index, 0)
        self.assertGreater(methods_summary_index, figure_index)

    def test_old_nature_fixture_preserves_inline_equation_images(self) -> None:
        html_path = golden_criteria_asset("10.1038/nature13376", "original.html")
        markdown_text = springer_html.extract_html_payload(
            html_path.read_text(encoding="utf-8", errors="ignore"),
            "https://www.nature.com/articles/nature13376",
        )["markdown_text"]

        self.assertIn("![Formula](https://media.springernature.com/", markdown_text)
        self.assertIn("_IEq1_HTML.jpg", markdown_text)

    def test_old_nature_downloaded_body_figures_inline_without_trailing_figures_block(
        self,
    ) -> None:
        html_path = golden_criteria_asset("10.1038/nature13376", "original.html")
        source_url = "https://www.nature.com/articles/nature13376"
        html_text = html_path.read_text(encoding="utf-8", errors="ignore")
        base_metadata = {
            "doi": "10.1038/nature13376",
            "landing_page_url": source_url,
            "authors": [],
            "fulltext_links": [],
            "references": [],
        }
        html_metadata = springer_html.parse_html_metadata(html_text, source_url)
        merged_metadata = springer_html.merge_html_metadata(
            base_metadata, html_metadata
        )
        extracted_assets = springer_html.extract_html_assets(
            html_text, source_url, asset_profile="body"
        )
        extraction_payload = springer_html.extract_html_payload(
            html_text,
            source_url,
            title=str(merged_metadata.get("title") or ""),
        )
        abstract_sections = list(extraction_payload["abstract_sections"])
        diagnostics = assess_html_fulltext_availability(
            extraction_payload["markdown_text"],
            merged_metadata,
            provider="springer",
            html_text=html_text,
            title=str(merged_metadata.get("title") or ""),
            final_url=source_url,
            section_hints=extraction_payload["section_hints"],
        )
        raw_payload = RawFulltextPayload(
            provider="springer",
            source_url=source_url,
            content_type="text/html",
            body=html_text.encode("utf-8"),
            content=ProviderContent(
                route_kind="html",
                source_url=source_url,
                content_type="text/html",
                body=html_text.encode("utf-8"),
                markdown_text=extraction_payload["markdown_text"],
                extracted_assets=extracted_assets,
                merged_metadata=merged_metadata,
                diagnostics={
                    "availability_diagnostics": diagnostics.to_dict(),
                    "extraction": {
                        "abstract_text": normalize_text(abstract_sections[0]["text"])
                        if abstract_sections
                        else None,
                        "abstract_sections": abstract_sections,
                        "section_hints": list(extraction_payload["section_hints"]),
                        "extracted_authors": list(
                            extraction_payload.get("extracted_authors") or []
                        ),
                    },
                },
            ),
            trace=trace_from_markers(["fulltext:springer_html_ok"]),
            merged_metadata=merged_metadata,
        )
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        figures = [a for a in extracted_assets if a["kind"] == "figure"]
        self.assertEqual(len(figures), 4)
        self.assertIn("The standard deviations", figures[0]["caption"])
        downloaded = download_captured_images("10.1038/nature13376", figures, directory)
        article = springer_provider.SpringerClient(
            HttpTransport(), {}
        ).to_article_model(
            merged_metadata,
            raw_payload,
            downloaded_assets=downloaded,
        )
        markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        for asset in downloaded:
            self.assertEqual(markdown.count(f"]({asset['path']})"), 1)
            self.assertLess(
                markdown.index(f"]({asset['path']})"),
                markdown.index(f"**{asset['heading']}.**"),
            )
        self.assertNotIn("\n## Figures\n", markdown)
        self.assertNotIn("PowerPoint slide", extraction_payload["markdown_text"])
        self.assertNotIn("Full size image", extraction_payload["markdown_text"])
        for asset in extracted_assets:
            self.assertNotIn("PowerPoint slide", str(asset.get("caption") or ""))
            self.assertNotIn("Full size image", str(asset.get("caption") or ""))

    def test_new_nature_downloaded_body_figures_inline_without_trailing_figures_block(
        self,
    ) -> None:
        sample = golden_criteria_sample_for_doi("10.1038/s43247-024-01295-w")
        doi = str(sample["doi"])
        source_url = str(sample["source_url"])
        title = str(sample["title"])
        html_text = golden_criteria_asset(doi, "original.html").read_text(
            encoding="utf-8", errors="ignore"
        )
        base_metadata = {
            "doi": doi,
            "landing_page_url": source_url,
            "authors": [],
            "fulltext_links": [],
            "references": [],
        }
        html_metadata = springer_html.parse_html_metadata(html_text, source_url)
        merged_metadata = springer_html.merge_html_metadata(
            base_metadata, html_metadata
        )
        extracted_assets = springer_html.extract_html_assets(
            html_text, source_url, asset_profile="body"
        )
        extraction_payload = springer_html.extract_html_payload(
            html_text,
            source_url,
            title=str(merged_metadata.get("title") or title),
        )
        abstract_sections = list(extraction_payload["abstract_sections"])
        diagnostics = assess_html_fulltext_availability(
            extraction_payload["markdown_text"],
            merged_metadata,
            provider="springer",
            html_text=html_text,
            title=str(merged_metadata.get("title") or title),
            final_url=source_url,
            section_hints=extraction_payload["section_hints"],
        )
        raw_payload = RawFulltextPayload(
            provider="springer",
            source_url=source_url,
            content_type="text/html",
            body=html_text.encode("utf-8"),
            content=ProviderContent(
                route_kind="html",
                source_url=source_url,
                content_type="text/html",
                body=html_text.encode("utf-8"),
                markdown_text=extraction_payload["markdown_text"],
                extracted_assets=extracted_assets,
                merged_metadata=merged_metadata,
                diagnostics={
                    "availability_diagnostics": diagnostics.to_dict(),
                    "extraction": {
                        "abstract_text": normalize_text(abstract_sections[0]["text"])
                        if abstract_sections
                        else None,
                        "abstract_sections": abstract_sections,
                        "section_hints": list(extraction_payload["section_hints"]),
                        "extracted_authors": list(
                            extraction_payload.get("extracted_authors") or []
                        ),
                    },
                },
            ),
            trace=trace_from_markers(["fulltext:springer_html_ok"]),
            merged_metadata=merged_metadata,
        )
        figures = [
            a for a in extracted_assets if a["kind"] == "figure" and a.get("url")
        ]
        self.assertEqual(len(figures), 5)
        tmpdir = self.enterContext(tempfile.TemporaryDirectory())
        downloaded = download_captured_images(doi, figures, Path(tmpdir))
        article = springer_provider.SpringerClient(
            HttpTransport(), {}
        ).to_article_model(
            merged_metadata,
            raw_payload,
            downloaded_assets=downloaded,
        )
        markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        self.assertIn("**Figure 1.**", extraction_payload["markdown_text"])
        for asset in downloaded:
            self.assertEqual(markdown.count(f"]({asset['path']})"), 1)
        self.assertNotIn("\n## Figures\n", markdown)

    def test_nature_matters_arising_fixture_keeps_main_content_before_reporting_summary(
        self,
    ) -> None:
        sample = golden_criteria_sample_for_doi("10.1038/s41586-020-1941-5")
        doi = str(sample["doi"])
        source_url = str(sample["source_url"])
        title = str(sample["title"])
        html_text = golden_criteria_asset(doi, "original.html").read_text(
            encoding="utf-8", errors="ignore"
        )

        extraction_payload = springer_html.extract_html_payload(
            html_text,
            source_url,
            title=title,
        )
        markdown_text = extraction_payload["markdown_text"]

        self.assertIn(
            "Planting and removal of forest affect average streamflow", markdown_text
        )
        self.assertIn(
            "The record length of the studies used by Evaristo and McDonnell",
            markdown_text,
        )
        self.assertIn("## Data availability", markdown_text)
        self.assertIn("Five-year-average water yield observations", markdown_text)
        self.assertIn("## Reporting summary", markdown_text)
        self.assertLess(
            markdown_text.index("Planting and removal"),
            markdown_text.index("## Reporting summary"),
        )
        self.assertEqual(markdown_text.count("## Data availability"), 1)

    def test_nature_asset_profile_none_keeps_remote_figure_links_without_downloads(
        self,
    ) -> None:
        sample = golden_criteria_sample_for_doi("10.1038/s41586-020-1941-5")
        doi = str(sample["doi"])
        source_url = str(sample["source_url"])
        article, extraction_payload, _diagnostics, extracted_assets = (
            self._build_article_from_html(
                golden_criteria_asset(doi, "original.html"),
                source_url,
                doi=doi,
                extracted_asset_profile="none",
            )
        )

        markdown = article.to_ai_markdown(asset_profile="none", max_tokens="full_text")

        self.assertEqual(extracted_assets, [])
        self.assertEqual(article.assets, [])
        self.assertIn(
            "![Figure 1](https://media.springernature.com/full/springer-static/image/"
            "art%3A10.1038%2Fs41586-020-1941-5/MediaObjects/41586_2020_1941_Fig1_HTML.png)",
            extraction_payload["markdown_text"],
        )
        self.assertIn(
            "![Figure 1](https://media.springernature.com/full/springer-static/image/"
            "art%3A10.1038%2Fs41586-020-1941-5/MediaObjects/41586_2020_1941_Fig1_HTML.png)",
            markdown,
        )
        self.assertNotIn("_assets/", markdown)

    def test_old_nature_reporting_within_methods_precedes_external_availability(
        self,
    ) -> None:
        doi = "10.1038/s41467-019-11472-7"
        source_url = "https://www.nature.com/articles/s41467-019-11472-7"
        html_path = golden_criteria_asset(
            doi, "acquisition/requested-templates-2026-09-16/article-response.html"
        )
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_path.read_bytes(), "lxml")
        main = soup.select_one(".main-content")
        methods = main.select_one('section[data-title="Methods"]')
        reporting = methods.find("h3", string="Reporting summary")
        self.assertIsNotNone(reporting)
        data = soup.select_one("#data-availability-section")
        self.assertNotIn(main, data.parents)
        reporting_text = normalize_text(
            reporting.find_next_sibling("p").get_text(" ", strip=True)
        )

        article, extraction, diagnostics, _ = self._build_article_from_html(
            html_path, source_url, doi=doi, extracted_asset_profile="none"
        )
        self.assertTrue(diagnostics.accepted)
        rendered = article.to_ai_markdown(asset_profile="none", max_tokens="full_text")
        for markdown in (extraction["markdown_text"], rendered):
            headings = ("## Methods", "### Reporting summary", "## Data availability")
            positions = []
            for heading in headings:
                self.assertEqual(markdown.count(heading + "\n"), 1)
                positions.append(markdown.index(heading + "\n"))
            self.assertEqual(positions, sorted(positions))
            self.assertEqual(normalize_text(markdown).count(reporting_text), 1)
            self.assertIn("https://figshare.com/s/56430026ba793775983f", markdown)
            self.assertIn("10.6084/m9.figshare.7054265", markdown)

    def test_drought_self_propagation_fixture_has_no_trailing_figures_block(
        self,
    ) -> None:
        sample = golden_criteria_sample_for_doi("10.1038/s41561-022-00912-7")
        doi = str(sample["doi"])
        source_url = str(sample["source_url"])
        article, extraction_payload, diagnostics, _ = self._build_article_from_html(
            golden_criteria_asset(doi, "original.html"),
            source_url,
            doi=doi,
            fake_downloaded_assets=True,
        )

        markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        self.assertEqual(diagnostics.content_kind, "fulltext")
        self.assertIn("**Figure 1.**", extraction_payload["markdown_text"])
        self.assertIn("![Figure 1](/tmp/fake-springer-figure-1.png)", markdown)
        self.assertNotIn("\n## Figures\n", markdown)
        self.assertLess(markdown.index("![Figure 4]"), markdown.index("## References"))

    def test_springer_bilingual_fixture_enters_body_without_duplicate_title_or_cta(
        self,
    ) -> None:
        path = golden_criteria_asset("10.1007/s13158-025-00473-x", "bilingual.html")
        article, _, _, _ = self._build_article_from_html(
            path,
            "https://link.springer.com/article/10.1007/s13158-025-00473-x",
            doi="10.1007/s13158-025-00473-x",
        )
        markdown = article.to_ai_markdown(max_tokens="full_text")

        self.assertIn("## Resumen", markdown)
        self.assertIn("## Results", markdown)
        self.assertLess(markdown.index("## Resumen"), markdown.index("## Results"))
        self.assertEqual(
            markdown.count(
                "# Stagnated Development of Home Language Vocabulary in Japanese–Chinese Bilingual Children at Risk for Autism Spectrum Disorder"
            ),
            1,
        )
        for chrome in (
            "Save article",
            "View saved research",
            "Aims and scope",
            "Submit manuscript",
        ):
            self.assertNotIn(chrome, markdown)

    def test_springer_paywall_article_markdown_strips_preview_sentence(self) -> None:
        doi = "10.1007/s00382-018-4286-0"
        source_url = f"https://link.springer.com/article/{doi}"
        html_path = block_asset(doi, "raw.html")

        article, extraction_payload, diagnostics, _ = self._build_article_from_html(
            html_path, source_url, doi=doi
        )

        self.assertEqual(diagnostics.content_kind, "abstract_only")
        self.assertEqual(article.quality.content_kind, "abstract_only")
        self.assertNotIn(
            "This is a preview of subscription content",
            extraction_payload["markdown_text"],
        )
        self.assertFalse(
            any(
                "This is a preview of subscription content"
                in str(section.get("text") or "")
                for section in extraction_payload["abstract_sections"]
            )
        )
        self.assertNotIn(
            "This is a preview of subscription content",
            article.to_ai_markdown(max_tokens="full_text"),
        )


if __name__ == "__main__":
    unittest.main()
