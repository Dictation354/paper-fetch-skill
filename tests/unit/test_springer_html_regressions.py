from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from paper_fetch.http import HttpTransport
from paper_fetch.providers import _springer_html, html_springer_nature, springer as springer_provider
from paper_fetch.markdown.citations import normalize_inline_citation_markdown
from paper_fetch.quality.html_availability import assess_html_fulltext_availability
from paper_fetch.providers._html_references import extract_numbered_references_from_html
from paper_fetch.providers._html_section_markdown import render_clean_text_from_html
from paper_fetch.providers.base import ProviderContent, RawFulltextPayload
from paper_fetch.tracing import trace_from_markers
from paper_fetch.utils import normalize_text
from paper_fetch.workflow.fulltext import maybe_save_provider_html_payload
from tests.block_fixtures import block_asset
from tests.golden_criteria import (
    golden_criteria_asset,
    golden_criteria_sample_for_doi,
    golden_criteria_scenario_asset,
)


class SpringerHtmlRegressionTests(unittest.TestCase):
    def test_extract_numbered_references_from_springer_html_preserves_labels(self) -> None:
        html = """
        <section aria-labelledby="Bib1" data-title="References">
          <div class="c-article-section__content">
            <div data-container-section="references">
              <ol class="c-article-references">
                <li class="c-article-references__item" data-counter="1.">
                  <p class="c-article-references__text" id="ref-CR1">First numbered reference.</p>
                </li>
                <li class="c-article-references__item" data-counter="2.">
                  <p class="c-article-references__text" id="ref-CR2">Second numbered reference.</p>
                </li>
              </ol>
            </div>
          </div>
        </section>
        """

        references = extract_numbered_references_from_html(html)

        self.assertEqual(
            references,
            [
                {"label": "1.", "raw": "First numbered reference.", "doi": None, "year": None},
                {"label": "2.", "raw": "Second numbered reference.", "doi": None, "year": None},
            ],
        )

    def test_springer_payload_keeps_multi_reference_superscripts_when_titles_contain_related(self) -> None:
        html = """
        <html>
          <body>
            <article>
              <h1>Example Article</h1>
              <div class="c-article-body">
                <div class="main-content">
                  <section data-title="Main">
                    <div class="c-article-section__content">
                      <p>
                        Bootstrap resampling<sup><a data-test="citation-ref" href="#ref-CR55" title="First citation">55</a>,<a data-test="citation-ref" href="#ref-CR56" title="Interdecadal modulation of ENSO-related spring rainfall over South China">56</a>,<a data-test="citation-ref" href="#ref-CR57" title="Droughts related to quasi-global oscillations">57</a></sup> was employed.
                      </p>
                    </div>
                  </section>
                </div>
              </div>
            </article>
          </body>
        </html>
        """

        payload = _springer_html.extract_html_payload(
            html,
            "https://www.nature.com/articles/example-article",
        )

        self.assertIn(
            "Bootstrap resampling<sup>55, 56, 57</sup> was employed.",
            payload["markdown_text"],
        )

    def test_section_aware_html_preserves_units_year_ranges_and_numeric_citations(self) -> None:
        soup = BeautifulSoup(
            """
            <section>
              <p>Severe losses reached 2.2 PgC (10<sup>15</sup> g) in 2005 and 2010.</p>
              <p>Warm extremes during 1981–2020 were defined as the period above TX90 ref. <sup><a data-test="citation-ref" href="#ref-CR21">21</a></sup>.</p>
              <p>The dataset CRUNCEP<sup><a data-test="citation-ref" href="#ref-CR24">24</a></sup> spans 1981–2016 and 1981–2010 baselines.</p>
              <p>These effects covered &gt;10<sup>6</sup> km<sup>2</sup> and another 22,500 km<sup>2</sup>.</p>
            </section>
            """,
            "html.parser",
        )

        rendered = render_clean_text_from_html(soup.section)
        normalized = normalize_inline_citation_markdown(rendered)

        self.assertIn("10<sup>15</sup> g", normalized)
        self.assertIn("1981–2020", normalized)
        self.assertIn("1981–2010", normalized)
        self.assertIn("TX90<sup>21</sup>", normalized)
        self.assertIn("CRUNCEP<sup>24</sup>", normalized)
        self.assertIn(">10<sup>6</sup> km<sup>2</sup>", normalized)
        self.assertIn("22,500 km<sup>2</sup>", normalized)

    def test_merge_springer_assets_reuses_html_asset_identity_helper(self) -> None:
        merged = springer_provider._merge_springer_assets(
            [
                {
                    "kind": "figure",
                    "heading": "Figure 1",
                    "url": "https://media.springernature.com/full/example-figure-1.png",
                }
            ],
            [
                {
                    "kind": "figure",
                    "heading": "Figure 1",
                    "url": "https://media.springernature.com/full/example-figure-1.png",
                    "path": "/tmp/example-figure-1.png",
                }
            ],
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["path"], "/tmp/example-figure-1.png")

    def _build_article_from_html(
        self,
        html_path: Path,
        source_url: str,
        *,
        doi: str,
        fake_downloaded_assets: bool = False,
    ):
        html_text = html_path.read_text(encoding="utf-8", errors="ignore")
        base_metadata = {
            "doi": doi,
            "landing_page_url": source_url,
            "authors": [],
            "fulltext_links": [],
            "references": [],
        }
        html_metadata = _springer_html.parse_html_metadata(html_text, source_url)
        merged_metadata = _springer_html.merge_html_metadata(base_metadata, html_metadata)
        if not merged_metadata.get("doi"):
            merged_metadata["doi"] = doi
        extraction_payload = _springer_html.extract_html_payload(
            html_text,
            source_url,
            title=str(merged_metadata.get("title") or ""),
        )
        extracted_assets = _springer_html.extract_html_assets(
            html_text,
            source_url,
            asset_profile="body",
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
                        "abstract_text": normalize_text(abstract_sections[0]["text"]) if abstract_sections else None,
                        "abstract_sections": abstract_sections,
                        "section_hints": list(extraction_payload["section_hints"]),
                        "extracted_authors": list(extraction_payload.get("extracted_authors") or []),
                        "references": list(extraction_payload.get("references") or []),
                    },
                },
            ),
            trace=trace_from_markers(["fulltext:springer_html_ok"]),
            merged_metadata=merged_metadata,
        )
        downloaded_assets = self._fake_downloaded_assets(extracted_assets) if fake_downloaded_assets else None
        article = springer_provider.SpringerClient(HttpTransport(), {}).to_article_model(
            merged_metadata,
            raw_payload,
            downloaded_assets=downloaded_assets,
        )
        return article, extraction_payload, diagnostics, extracted_assets

    def _fake_downloaded_assets(self, assets: list[dict[str, str]]) -> list[dict[str, str]]:
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

    def test_springer_paywall_article_markdown_strips_preview_sentence(self) -> None:
        """rule: rule-springer-access-hint-disclaimer"""
        doi = "10.1007/s00382-018-4286-0"
        source_url = f"https://link.springer.com/article/{doi}"
        html_path = block_asset(doi, "raw.html")

        article, extraction_payload, diagnostics, _ = self._build_article_from_html(html_path, source_url, doi=doi)

        self.assertEqual(diagnostics.content_kind, "abstract_only")
        self.assertEqual(article.quality.content_kind, "abstract_only")
        self.assertNotIn("This is a preview of subscription content", extraction_payload["markdown_text"])
        self.assertFalse(
            any(
                "This is a preview of subscription content" in str(section.get("text") or "")
                for section in extraction_payload["abstract_sections"]
            )
        )
        self.assertNotIn("This is a preview of subscription content", article.to_ai_markdown(max_tokens="full_text"))

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
        """rule: rule-keep-data-availability-once"""
        doi = "10.1038/s43247-024-01885-8"
        article, extraction_payload, diagnostics, _ = self._build_article_from_html(
            golden_criteria_asset(doi, "original.html"),
            "https://www.nature.com/articles/s43247-024-01885-8",
            doi=doi,
        )

        rendered = article.to_ai_markdown(max_tokens="full_text")
        section_pairs = [(section.heading, section.kind) for section in article.sections]
        hint_pairs = [(item["heading"], item["kind"]) for item in extraction_payload["section_hints"]]

        self.assertEqual(diagnostics.content_kind, "fulltext")
        self.assertIn("## Data availability", rendered)
        self.assertIn("## Code availability", rendered)
        self.assertIn(("Data availability", "data_availability"), section_pairs)
        self.assertIn(("Code availability", "code_availability"), section_pairs)
        self.assertIn(("Data availability", "data_availability"), hint_pairs)
        self.assertIn(("Code availability", "code_availability"), hint_pairs)

    def test_extract_asset_html_scopes_limit_body_assets_to_main_content(self) -> None:
        source_url = "https://www.nature.com/articles/example"
        html_text = """
<html>
  <body>
    <article>
      <h1>Example Article</h1>
      <div class="c-article-body">
        <div class="main-content">
          <section data-title="Results">
            <figure>
              <img src="https://media.springernature.com/full/body-figure.png" alt="Body figure" />
              <figcaption>Figure 1. Body figure.</figcaption>
            </figure>
          </section>
        </div>
      </div>
      <section data-title="Supplementary information">
        <a href="https://static-content.springer.com/esm/supplement.pdf">Supplementary Information</a>
        <figure>
          <img src="https://media.springernature.com/full/supp-figure.png" alt="Supplementary figure" />
          <figcaption>Supplementary Fig. 1.</figcaption>
        </figure>
      </section>
    </article>
  </body>
</html>
"""

        body_html, supplementary_html = _springer_html.extract_asset_html_scopes(
            html_text,
            source_url,
            title="Example Article",
        )
        body_assets = _springer_html.extract_scoped_html_assets(
            body_html,
            source_url,
            asset_profile="body",
            supplementary_html_text=supplementary_html,
        )
        all_assets = _springer_html.extract_scoped_html_assets(
            body_html,
            source_url,
            asset_profile="all",
            supplementary_html_text=supplementary_html,
        )

        self.assertEqual(
            [asset.get("url") for asset in body_assets if normalize_text(asset.get("kind")).lower() == "figure"],
            ["https://media.springernature.com/full/body-figure.png"],
        )
        self.assertEqual(
            [asset.get("kind") for asset in all_assets],
            ["figure", "supplementary"],
        )

    def test_extract_asset_html_scopes_leave_empty_supplementary_scope_without_supplementary_sections(self) -> None:
        """rule: rule-springer-supplementary-scope"""
        source_url = "https://www.nature.com/articles/no-supplementary"
        html_text = """
<html>
  <body>
    <article>
      <h1>Example Article</h1>
      <div class="c-article-body">
        <div class="main-content">
          <section data-title="Results">
            <p>Only body content.</p>
            <a href="https://example.test/body-only.pdf">Body PDF</a>
          </section>
        </div>
      </div>
      <section data-title="Rights and permissions">
        <a href="https://example.test/citation.ris">Download citation</a>
      </section>
    </article>
  </body>
</html>
"""

        body_html, supplementary_html = _springer_html.extract_asset_html_scopes(
            html_text,
            source_url,
            title="Example Article",
        )
        source_data_html = _springer_html.extract_source_data_html_scope(
            html_text,
            source_url,
            title="Example Article",
        )
        all_assets = _springer_html.extract_scoped_html_assets(
            body_html,
            source_url,
            asset_profile="all",
            supplementary_html_text=supplementary_html,
            source_data_html_text=source_data_html,
        )

        self.assertIn("Only body content.", body_html)
        self.assertEqual(supplementary_html, "")
        self.assertEqual(source_data_html, "")
        self.assertFalse(any(asset.get("kind") == "supplementary" for asset in all_assets))

    def test_real_nature_fixture_separates_source_data_from_supplementary_assets(self) -> None:
        """rule: rule-springer-supplementary-scope"""
        source_url = "https://www.nature.com/articles/s41561-022-00912-7"
        html_text = golden_criteria_asset("10.1038/s41561-022-00912-7", "original.html").read_text(encoding="utf-8")

        body_html, supplementary_html = _springer_html.extract_asset_html_scopes(html_text, source_url)
        source_data_html = _springer_html.extract_source_data_html_scope(html_text, source_url)
        assets = _springer_html.extract_scoped_html_assets(
            body_html,
            source_url,
            asset_profile="all",
            supplementary_html_text=supplementary_html,
            source_data_html_text=source_data_html,
        )

        supplementary_assets = [
            asset for asset in assets if asset.get("kind") == "supplementary" and asset.get("asset_kind") != "source_data"
        ]
        source_data_assets = [asset for asset in assets if asset.get("asset_kind") == "source_data"]

        self.assertIn("Extended data", supplementary_html)
        self.assertIn("Supplementary information", supplementary_html)
        self.assertNotIn("Source data", supplementary_html)
        self.assertIn("Source data", source_data_html)
        self.assertTrue(any(asset.get("url", "").endswith("MOESM1_ESM.pdf") for asset in supplementary_assets))
        self.assertFalse(any("MOESM2_ESM" in asset.get("url", "") for asset in supplementary_assets))
        self.assertTrue(any(asset.get("url", "").endswith("MOESM2_ESM.zip") for asset in source_data_assets))
        self.assertTrue(any(asset.get("url", "").endswith("MOESM4_ESM.csv") for asset in source_data_assets))

    def test_real_nature_fixture_resolves_source_data_links_from_extended_data_descriptions(self) -> None:
        """rule: rule-springer-supplementary-scope"""
        source_url = "https://www.nature.com/articles/s41558-022-01584-2"
        html_text = golden_criteria_asset("10.1038/s41558-022-01584-2", "original.html").read_text(encoding="utf-8")

        body_html, supplementary_html = _springer_html.extract_asset_html_scopes(html_text, source_url)
        source_data_html = _springer_html.extract_source_data_html_scope(html_text, source_url)
        assets = _springer_html.extract_scoped_html_assets(
            body_html,
            source_url,
            asset_profile="all",
            supplementary_html_text=supplementary_html,
            source_data_html_text=source_data_html,
        )

        supplementary_assets = [
            asset for asset in assets if asset.get("kind") == "supplementary" and asset.get("asset_kind") != "source_data"
        ]
        source_data_assets = [asset for asset in assets if asset.get("asset_kind") == "source_data"]

        self.assertTrue(any(asset.get("url", "").endswith("/figures/5") for asset in supplementary_assets))
        self.assertTrue(any(asset.get("url", "").endswith("MOESM5_ESM.xlsx") for asset in source_data_assets))
        self.assertTrue(any(asset.get("url", "").endswith("MOESM13_ESM.xlsx") for asset in source_data_assets))
        self.assertFalse(any("MOESM5_ESM.xlsx" in asset.get("url", "") for asset in supplementary_assets))

    def test_real_nature_fixture_skips_peer_review_files_from_supplementary_assets(self) -> None:
        """rule: rule-springer-supplementary-scope"""
        source_url = "https://www.nature.com/articles/s43247-024-01270-5"
        html_text = golden_criteria_asset("10.1038/s43247-024-01270-5", "original.html").read_text(encoding="utf-8")

        body_html, supplementary_html = _springer_html.extract_asset_html_scopes(html_text, source_url)
        source_data_html = _springer_html.extract_source_data_html_scope(html_text, source_url)
        assets = _springer_html.extract_scoped_html_assets(
            body_html,
            source_url,
            asset_profile="all",
            supplementary_html_text=supplementary_html,
            source_data_html_text=source_data_html,
        )

        supplementary_headings = [
            normalize_text(str(asset.get("heading") or "")).lower()
            for asset in assets
            if asset.get("kind") == "supplementary" and asset.get("asset_kind") != "source_data"
        ]

        self.assertIn("supplementary information", supplementary_headings)
        self.assertFalse(any("peer review" in heading for heading in supplementary_headings))

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

            warnings, trail = maybe_save_provider_html_payload(
                "springer",
                content=content,
                download_dir=download_dir,
                doi="10.1038/nature12915",
                metadata={"title": "Example"},
            )

            self.assertEqual(warnings, [])
            self.assertIn("download:springer_html_saved", trail)
            saved_path = download_dir / "original.html"
            self.assertTrue(saved_path.exists())
            self.assertEqual(saved_path.read_bytes(), content.body)

    def test_old_nature_fixture_keeps_single_methods_summary_and_methods_sections(self) -> None:
        html_path = golden_criteria_asset("10.1038/nature12915", "original.html")
        source_url = "https://www.nature.com/articles/nature12915"

        article, extraction_payload, diagnostics, extracted_assets = self._build_article_from_html(
            html_path,
            source_url,
            doi="10.1038/nature12915",
        )
        markdown_text = extraction_payload["markdown_text"]

        self.assertEqual(diagnostics.content_kind, "fulltext")
        self.assertEqual(article.quality.content_kind, "fulltext")
        self.assertEqual([section.get("heading") for section in extraction_payload["abstract_sections"]], ["Abstract"])
        figure_assets = [asset for asset in extracted_assets if normalize_text(asset.get("kind")).lower() == "figure"]
        formula_assets = [asset for asset in extracted_assets if normalize_text(asset.get("kind")).lower() == "formula"]
        self.assertEqual(len(figure_assets), 3)
        self.assertGreater(len(formula_assets), 0)
        self.assertIn("_Equ1_HTML.jpg", markdown_text)
        self.assertIn("_Equ2_HTML.jpg", markdown_text)
        self.assertIn("![Formula](//media.springernature.com/", markdown_text)
        self.assertTrue(any("_Equ1_HTML.jpg" in normalize_text(asset.get("url")) for asset in formula_assets))
        self.assertTrue(any("_Equ2_HTML.jpg" in normalize_text(asset.get("url")) for asset in formula_assets))
        self.assertFalse(any("Fig1_HTML" in normalize_text(asset.get("url")) for asset in formula_assets))
        self.assertNotIn("PowerPoint slide", markdown_text)
        self.assertNotIn("Full size image", markdown_text)
        for asset in figure_assets:
            self.assertNotIn("PowerPoint slide", str(asset.get("caption") or ""))
            self.assertNotIn("Full size image", str(asset.get("caption") or ""))
        self.assertEqual(len(re.findall(r"(?m)^## Methods Summary\s*$", markdown_text)), 1)
        self.assertEqual(len(re.findall(r"(?m)^## Methods\s*$", markdown_text)), 1)
        self.assertIn("## Methods\n", article.to_ai_markdown(asset_profile="body", max_tokens="full_text"))
        self.assertNotIn("## Online Methods", markdown_text)
        figure_index = markdown_text.find("**Figure 1.**")
        methods_summary_index = markdown_text.find("## Methods Summary")
        self.assertGreaterEqual(figure_index, 0)
        self.assertGreater(methods_summary_index, figure_index)

    def test_old_nature_fixture_preserves_inline_equation_images(self) -> None:
        html_path = golden_criteria_asset("10.1038/nature13376", "original.html")
        markdown_text = _springer_html.extract_html_payload(
            html_path.read_text(encoding="utf-8", errors="ignore"),
            "https://www.nature.com/articles/nature13376",
        )["markdown_text"]

        self.assertIn("![Formula](//media.springernature.com/", markdown_text)
        self.assertIn("_IEq1_HTML.jpg", markdown_text)

    def test_old_nature_downloaded_body_figures_inline_without_trailing_figures_block(self) -> None:
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
        html_metadata = _springer_html.parse_html_metadata(html_text, source_url)
        merged_metadata = _springer_html.merge_html_metadata(base_metadata, html_metadata)
        extracted_assets = _springer_html.extract_html_assets(html_text, source_url, asset_profile="body")
        extraction_payload = _springer_html.extract_html_payload(
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
                        "abstract_text": normalize_text(abstract_sections[0]["text"]) if abstract_sections else None,
                        "abstract_sections": abstract_sections,
                        "section_hints": list(extraction_payload["section_hints"]),
                        "extracted_authors": list(extraction_payload.get("extracted_authors") or []),
                    },
                },
            ),
            trace=trace_from_markers(["fulltext:springer_html_ok"]),
            merged_metadata=merged_metadata,
        )
        article = springer_provider.SpringerClient(HttpTransport(), {}).to_article_model(
            merged_metadata,
            raw_payload,
            downloaded_assets=self._fake_downloaded_assets(extracted_assets),
        )
        markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        self.assertIn("![Figure 1](/tmp/fake-springer-figure-1.png)", markdown)
        self.assertNotIn("\n## Figures\n", markdown)
        self.assertNotIn("PowerPoint slide", extraction_payload["markdown_text"])
        self.assertNotIn("Full size image", extraction_payload["markdown_text"])
        for asset in extracted_assets:
            self.assertNotIn("PowerPoint slide", str(asset.get("caption") or ""))
            self.assertNotIn("Full size image", str(asset.get("caption") or ""))

    def test_new_nature_downloaded_body_figures_inline_without_trailing_figures_block(self) -> None:
        sample = golden_criteria_sample_for_doi("10.1038/s41561-022-00983-6")
        doi = str(sample["doi"])
        source_url = str(sample["source_url"])
        title = str(sample["title"])
        html_text = golden_criteria_asset(doi, "original.html").read_text(encoding="utf-8", errors="ignore")
        base_metadata = {
            "doi": doi,
            "landing_page_url": source_url,
            "authors": [],
            "fulltext_links": [],
            "references": [],
        }
        html_metadata = _springer_html.parse_html_metadata(html_text, source_url)
        merged_metadata = _springer_html.merge_html_metadata(base_metadata, html_metadata)
        extracted_assets = _springer_html.extract_html_assets(html_text, source_url, asset_profile="body")
        extraction_payload = _springer_html.extract_html_payload(
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
                        "abstract_text": normalize_text(abstract_sections[0]["text"]) if abstract_sections else None,
                        "abstract_sections": abstract_sections,
                        "section_hints": list(extraction_payload["section_hints"]),
                        "extracted_authors": list(extraction_payload.get("extracted_authors") or []),
                    },
                },
            ),
            trace=trace_from_markers(["fulltext:springer_html_ok"]),
            merged_metadata=merged_metadata,
        )
        article = springer_provider.SpringerClient(HttpTransport(), {}).to_article_model(
            merged_metadata,
            raw_payload,
            downloaded_assets=self._fake_downloaded_assets(extracted_assets),
        )
        markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        self.assertIn("**Figure 1.**", extraction_payload["markdown_text"])
        self.assertIn("![Figure 1](/tmp/fake-springer-figure-1.png)", markdown)
        self.assertNotIn("\n## Figures\n", markdown)

    def test_nature_matters_arising_fixture_keeps_main_content_before_reporting_summary(self) -> None:
        """rule: rule-springer-main-content-direct-children"""
        sample = golden_criteria_sample_for_doi("10.1038/s41586-020-1941-5")
        doi = str(sample["doi"])
        source_url = str(sample["source_url"])
        title = str(sample["title"])
        html_text = golden_criteria_asset(doi, "original.html").read_text(encoding="utf-8", errors="ignore")

        extraction_payload = _springer_html.extract_html_payload(
            html_text,
            source_url,
            title=title,
        )
        markdown_text = extraction_payload["markdown_text"]

        self.assertIn("Planting and removal of forest affect average streamflow", markdown_text)
        self.assertIn("The record length of the studies used by Evaristo and McDonnell", markdown_text)
        self.assertIn("## Data availability", markdown_text)
        self.assertIn("Five-year-average water yield observations", markdown_text)
        self.assertIn("## Reporting summary", markdown_text)
        self.assertLess(markdown_text.index("Planting and removal"), markdown_text.index("## Reporting summary"))
        self.assertEqual(markdown_text.count("## Data availability"), 1)

    def test_springer_main_content_scenario_keeps_direct_child_order(self) -> None:
        """rule: rule-springer-main-content-direct-children"""
        html_text = golden_criteria_scenario_asset(
            "springer_main_content_direct_children", "original.html"
        ).read_text(encoding="utf-8")

        extraction_payload = _springer_html.extract_html_payload(
            html_text,
            "https://www.nature.com/articles/springer-main-content-scenario",
            title="Springer Main Content Scenario",
        )
        markdown_text = extraction_payload["markdown_text"]

        self.assertIn("Direct child paragraph before reporting summary.", markdown_text)
        self.assertIn("## Data availability", markdown_text)
        self.assertIn("## Reporting summary", markdown_text)
        self.assertLess(markdown_text.index("Direct child paragraph"), markdown_text.index("## Reporting summary"))
        self.assertLess(markdown_text.index("## Data availability"), markdown_text.index("## Reporting summary"))

    def test_drought_self_propagation_fixture_has_no_trailing_figures_block(self) -> None:
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

    def test_springer_markdown_preserves_subscripts_in_section_headings(self) -> None:
        html = """
        <html>
          <body>
            <article>
              <h1>Trends in the sources and sinks of carbon dioxide</h1>
              <section data-title="Fossil fuel CO2 emissions">
                <div class="c-article-section">
                  <h2 class="c-article-section__title">Fossil fuel CO<sub>2</sub> emissions</h2>
                  <div class="c-article-section__content">
                    <p>Body paragraph for the section.</p>
                  </div>
                </div>
              </section>
            </article>
          </body>
        </html>
        """

        markdown = html_springer_nature.extract_springer_nature_markdown(
            html,
            "https://www.nature.com/articles/ngeo689",
        )

        self.assertIn("## Fossil fuel CO<sub>2</sub> emissions", markdown)
        self.assertNotIn("## Fossil fuel CO 2 emissions", markdown)

    def test_springer_markdown_spaces_numbered_inline_heading_spans(self) -> None:
        """rule: rule-springer-numbered-heading-spacing"""
        html = """
        <html>
          <body>
            <article>
              <h1>Numbered Heading Example</h1>
              <section>
                <h2><span>1</span><span>Introduction</span></h2>
                <p>Introductory body paragraph.</p>
                <section>
                  <h3><span>3.1</span><span>Glaciers</span></h3>
                  <p>Glacier body paragraph.</p>
                </section>
              </section>
            </article>
          </body>
        </html>
        """

        markdown = html_springer_nature.extract_springer_nature_markdown(
            html,
            "https://link.springer.com/article/10.1007/example",
        )

        self.assertIn("## 1 Introduction", markdown)
        self.assertIn("### 3.1 Glaciers", markdown)
        self.assertNotIn("## 1Introduction", markdown)
        self.assertNotIn("### 3.1Glaciers", markdown)

    def test_springer_mathjax_tex_normalizes_upgreek_macros(self) -> None:
        html = r"""
        <html>
          <body>
            <article>
              <h1>Math Example</h1>
              <div class="c-article-body">
                <div class="main-content">
                  <section data-title="Methods">
                    <h2 class="c-article-section__title">Methods</h2>
                    <div class="c-article-section__content">
                      <p>Inline <span class="mathjax-tex">\(\alpha _{i,t} = \updelta Q_{i,t}/E_{i,t}\)</span>.</p>
                      <div class="c-article-equation">
                        <div class="c-article-equation__content">
                          <span class="mathjax-tex">
                            $$\updelta Q_{i,t} = \alpha _{i,t}E_{{\mathrm{p}}(i,t)}S_{i,t}$$
                          </span>
                        </div>
                      </div>
                    </div>
                  </section>
                </div>
              </div>
            </article>
          </body>
        </html>
        """

        markdown = html_springer_nature.extract_springer_nature_markdown(
            html,
            "https://www.nature.com/articles/s41561-022-00912-7",
        )

        self.assertIn(r"\(\alpha _{i,t} = \delta Q_{i,t}/E_{i,t}\)", markdown)
        self.assertIn(r"$$\delta Q_{i,t} = \alpha _{i,t}E_{{\mathrm{p}}(i,t)}S_{i,t}$$", markdown)
        self.assertNotIn(r"\updelta", markdown)

    def test_springer_bilingual_fixture_enters_body_without_duplicate_title_or_cta(self) -> None:
        html = golden_criteria_asset("10.1007/s13158-025-00473-x", "bilingual.html").read_text(
            encoding="utf-8",
            errors="ignore",
        )

        markdown = _springer_html.extract_html_payload(
            html,
            "https://link.springer.com/article/10.1007/s13158-025-00473-x",
            title="Multilingual summaries in restoration field studies",
        )["markdown_text"]

        self.assertIn("## Resumen", markdown)
        self.assertIn("## Results", markdown)
        self.assertLess(markdown.index("## Resumen"), markdown.index("## Results"))
        self.assertEqual(markdown.count("# Multilingual summaries in restoration field studies"), 1)
        for chrome in ("Save article", "View saved research", "Aims and scope", "Submit manuscript"):
            self.assertNotIn(chrome, markdown)

    def test_springer_markdown_ignores_ai_alt_text_when_caption_exists(self) -> None:
        """rule: rule-springer-caption-precedence"""
        html = r"""
        <html>
          <body>
            <article>
              <h1>Figure Alt Example</h1>
              <div class="c-article-body">
                <div class="main-content">
                  <section data-title="Results">
                    <h2 class="c-article-section__title">Results</h2>
                    <div class="c-article-section__content">
                      <div
                        class="c-article-section__figure"
                        id="figure-2"
                        data-title="Variations in $${\gamma }_{{{{\rm{CGR}}}}}^{{{{\rm{T}}}}}$$ γ CGR T with varying dryness conditions."
                      >
                        <figure>
                          <figcaption>
                            <b class="c-article-section__figure-caption" id="Fig2">
                              Fig. 2: Variations in <span class="mathjax-tex">\({\gamma }_{{{{\rm{CGR}}}}}^{{{{\rm{T}}}}}\)</span> with varying dryness conditions.
                            </b>
                          </figcaption>
                          <div class="c-article-section__figure-content">
                            <div class="c-article-section__figure-item">
                              <img
                                alt="Fig. 2: Variations in $${\gamma }_{{{{\rm{CGR}}}}}^{{{{\rm{T}}}}}$$ γ CGR T with varying dryness conditions."
                                aria-describedby="figure-2-desc ai-alt-disclaimer-figure-2-1"
                                src="//media.springernature.com/lw685/example-figure-2.png"
                              />
                              <span class="u-visually-hidden" id="ai-alt-disclaimer-figure-2-1">
                                The alternative text for this image may have been generated using AI.
                              </span>
                            </div>
                            <div class="c-article-section__figure-description" id="figure-2-desc">
                              <p>Panel description text.</p>
                            </div>
                          </div>
                        </figure>
                      </div>
                    </div>
                  </section>
                </div>
              </div>
            </article>
          </body>
        </html>
        """

        markdown = html_springer_nature.extract_springer_nature_markdown(
            html,
            "https://www.nature.com/articles/s41467-023-36727-2",
        )

        self.assertIn("**Figure 2.** Variations in", markdown)
        self.assertIn("Panel description text.", markdown)
        self.assertNotIn("γ CGR T", markdown)
        self.assertNotIn("$$", markdown)
        self.assertEqual(markdown.count("with varying dryness conditions."), 1)


if __name__ == "__main__":
    unittest.main()
