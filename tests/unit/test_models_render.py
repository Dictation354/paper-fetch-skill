from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from paper_fetch import service as paper_fetch
from paper_fetch.models import (
    Asset,
    ArticleModel,
    EXTRACTION_REVISION,
    Metadata,
    Quality,
    QUALITY_FLAG_ACCESS_GATE_DETECTED,
    QUALITY_FLAG_WEAK_BODY_STRUCTURE,
    Reference,
    RenderOptions,
    Section,
    SectionHint,
    TokenEstimateBreakdown,
    article_from_markdown,
    article_from_structure,
    estimate_tokens,
    metadata_only_article,
    normalize_markdown_text,
)
from paper_fetch.providers import _springer_html
from tests.golden_criteria import golden_criteria_asset, golden_criteria_scenario_asset

from ._paper_fetch_support import sample_article


class ModelsRenderTests(unittest.TestCase):
    def test_token_budget_truncates_lower_priority_sections(self) -> None:
        article = sample_article()
        article.metadata.abstract = "Abstract text " * 20
        article.sections = [
            Section(heading="Introduction", level=2, kind="body", text="Intro " * 150),
            Section(heading="Methods", level=2, kind="body", text="Methods " * 150),
            Section(heading="Discussion", level=2, kind="body", text="Discussion " * 150),
        ]
        markdown = article.to_ai_markdown(max_tokens=450)

        self.assertIn("**Abstract.**", markdown)
        self.assertIn("## Introduction", markdown)
        self.assertNotIn("## Discussion", markdown)
        self.assertNotIn("Output truncated to satisfy token budget.", article.quality.warnings)

    def test_to_ai_markdown_omits_blank_frontmatter_and_does_not_mutate_warnings(self) -> None:
        article = ArticleModel(
            doi=None,
            source="crossref_meta",
            metadata=Metadata(),
            sections=[Section(heading="Introduction", level=2, kind="body", text="Intro " * 200)],
            references=[],
            assets=[],
            quality=Quality(
                has_fulltext=True,
                token_estimate=200,
                warnings=["Existing warning"],
                token_estimate_breakdown=TokenEstimateBreakdown(body=200),
            ),
        )

        markdown = article.to_ai_markdown(max_tokens=60)

        self.assertNotIn('title: ""', markdown)
        self.assertNotIn("authors:", markdown)
        self.assertNotIn("journal:", markdown)
        self.assertNotIn("published:", markdown)
        self.assertIn("# Untitled Article", markdown)
        self.assertEqual(article.quality.warnings, ["Existing warning"])

    def test_to_ai_markdown_defaults_to_captions_only_without_supplementary_links(self) -> None:
        article = sample_article()
        article.assets = [
            Asset(kind="figure", heading="Figure 1", caption="Overview figure.", url="downloads/figure-1.png"),
            Asset(kind="supplementary", heading="Supplementary Data", caption="Raw measurements.", url="downloads/supplement.csv"),
        ]

        markdown = article.to_ai_markdown()

        self.assertIn("## Figures", markdown)
        self.assertIn("- Figure 1: Overview figure.", markdown)
        self.assertNotIn("![Figure 1](downloads/figure-1.png)", markdown)
        self.assertNotIn("## Supplementary Materials", markdown)
        self.assertNotIn("[Supplementary Data](downloads/supplement.csv)", markdown)

    def test_to_ai_markdown_body_profile_renders_body_assets_only(self) -> None:
        article = sample_article()
        article.assets = [
            Asset(kind="figure", heading="Figure 1", caption="Body figure.", path="downloads/figure-1.png", section="body"),
            Asset(kind="figure", heading="Figure A1", caption="Appendix figure.", path="downloads/figure-a1.png", section="appendix"),
            Asset(kind="table", heading="Table 1", caption="Body table.", path="downloads/table-1.png", section="body"),
            Asset(kind="supplementary", heading="Supplementary Data", caption="Raw measurements.", path="downloads/supplement.csv"),
        ]

        markdown = article.to_ai_markdown(asset_profile="body")

        self.assertIn("![Figure 1](downloads/figure-1.png)", markdown)
        self.assertIn("## Tables", markdown)
        self.assertIn("![Table 1](downloads/table-1.png)", markdown)
        self.assertNotIn("Figure A1", markdown)
        self.assertNotIn("## Supplementary Materials", markdown)

    def test_to_ai_markdown_skips_inline_assets_and_labels_additional_tables(self) -> None:
        """rule: rule-elsevier-consumed-figure-table-dedup"""
        article = sample_article()
        article.assets = [
            Asset(kind="table", heading="Table 1", caption="Inline table.", path="downloads/table-1.png", section="body", render_state="inline"),
            Asset(kind="table", heading="Table 2", caption="Floating table.", path="downloads/table-2.png", section="body", render_state="appendix"),
        ]

        markdown = article.to_ai_markdown(asset_profile="body")

        self.assertNotIn("Table 1", markdown)
        self.assertIn("## Additional Tables", markdown)
        self.assertIn("![Table 2](downloads/table-2.png)", markdown)

    def test_to_ai_markdown_full_text_defaults_to_all_references(self) -> None:
        article = sample_article()
        article.references = [
            Reference(raw="Reference 1"),
            Reference(raw="Reference 2"),
            Reference(raw="Reference 3"),
        ]

        markdown = article.to_ai_markdown()

        self.assertIn("## References (3 total, showing 3)", markdown)
        self.assertIn("- Reference 3", markdown)

    def test_to_ai_markdown_preserves_numbered_reference_lines(self) -> None:
        article = sample_article()
        article.references = [
            Reference(raw="1. Numbered reference one"),
            Reference(raw="2. Numbered reference two"),
        ]

        markdown = article.to_ai_markdown()

        self.assertIn("1. Numbered reference one", markdown)
        self.assertIn("2. Numbered reference two", markdown)
        self.assertNotIn("- 1. Numbered reference one", markdown)

    def test_to_ai_markdown_full_text_respects_explicit_include_refs(self) -> None:
        article = sample_article()
        article.references = [Reference(raw=f"Reference {index}") for index in range(1, 13)]

        markdown = article.to_ai_markdown(include_refs="top10")

        self.assertIn("## References (12 total, showing 10)", markdown)
        self.assertIn("- Reference 10", markdown)
        self.assertNotIn("- Reference 11", markdown)

    def test_to_ai_markdown_full_text_matches_large_budget_rendering(self) -> None:
        article = sample_article()
        article.references = [Reference(raw=f"Reference {index}") for index in range(1, 4)]
        article.assets = [
            Asset(kind="figure", heading="Figure 1", caption="Overview figure.", path="downloads/figure-1.png", section="body"),
            Asset(kind="supplementary", heading="Supplementary Data", caption="Raw measurements.", path="downloads/supplement.csv"),
        ]

        full_text_markdown = article.to_ai_markdown(include_refs="all", asset_profile="all", max_tokens="full_text")
        large_budget_markdown = article.to_ai_markdown(include_refs="all", asset_profile="all", max_tokens=100000)

        self.assertEqual(full_text_markdown, large_budget_markdown)

    def test_to_ai_markdown_preserves_significance_before_abstract_and_body(self) -> None:
        article = sample_article()
        article.metadata.abstract = "Abstract summary stays distinct from the significance statement."
        article.sections = [
            Section(
                heading="Significance",
                level=2,
                kind="body",
                text="Significance summary should remain first in the rendered markdown.",
            ),
            Section(
                heading="Results and Discussion",
                level=2,
                kind="body",
                text="Body text should appear after the front-matter summaries.",
            ),
        ]

        markdown = article.to_ai_markdown(max_tokens="full_text")

        self.assertIn("## Significance", markdown)
        self.assertIn("## Abstract", markdown)
        self.assertNotIn("**Abstract.**", markdown)
        self.assertLess(markdown.index("## Significance"), markdown.index("## Abstract"))
        self.assertLess(markdown.index("## Abstract"), markdown.index("## Results and Discussion"))

    def test_to_ai_markdown_inline_figures_fall_back_to_captions_without_links(self) -> None:
        article = sample_article()
        article.assets = [
            Asset(kind="figure", heading="Figure 1", caption="Overview figure."),
        ]

        markdown = article.to_ai_markdown(include_figures="inline", max_tokens=600)

        self.assertIn("## Figures", markdown)
        self.assertIn("- Figure 1: Overview figure.", markdown)
        self.assertNotIn("![Figure 1]", markdown)

    def test_to_ai_markdown_suppresses_trailing_figures_for_body_figures_already_inline(self) -> None:
        """rule: rule-no-trailing-figures-appendix"""
        article = sample_article()
        article.sections = [
            Section(
                heading="Results",
                level=2,
                kind="body",
                text="\n".join(
                    [
                        "Body text lives here.",
                        "",
                        "![Figure 1](/tmp/figure-1.png)",
                        "",
                        "**Figure 1.** Inline caption text.",
                    ]
                ),
            )
        ]
        article.assets = [
            Asset(kind="figure", heading="Figure 1", caption="Inline caption text.", path="/tmp/figure-1.png", section="body"),
            Asset(kind="figure", heading="Figure A1", caption="Appendix figure.", path="/tmp/figure-a1.png", section="appendix"),
        ]

        markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        self.assertIn("![Figure 1](/tmp/figure-1.png)", markdown)
        self.assertNotIn("## Figures", markdown)
        self.assertNotIn("- Figure 1: Inline caption text.", markdown)
        self.assertNotIn("Figure A1", markdown)

    def test_to_ai_markdown_suppresses_trailing_figures_for_inline_relative_asset_suffix(self) -> None:
        article = sample_article()
        article.sections = [
            Section(
                heading="Results",
                level=2,
                kind="body",
                text="\n".join(
                    [
                        "Science body text lives here.",
                        "",
                        "![Figure 1](body_assets/aax6869-f1.jpeg)",
                        "",
                        "**Figure 1.** Inline science caption text.",
                    ]
                ),
            )
        ]
        article.assets = [
            Asset(
                kind="figure",
                heading="Figure 1",
                caption="Inline science caption text.",
                path="/tmp/paper-fetch/10.1126_sciadv.aax6869/body_assets/aax6869-f1.jpeg",
                section="body",
            ),
        ]

        markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        self.assertEqual(markdown.count("![Figure 1]"), 1)
        self.assertIn("![Figure 1](body_assets/aax6869-f1.jpeg)", markdown)
        self.assertNotIn("## Figures", markdown)
        self.assertNotIn("- Figure 1: Inline science caption text.", markdown)

    def test_to_ai_markdown_keeps_unmatched_body_figures_in_trailing_fallback_block(self) -> None:
        article = sample_article()
        article.sections = [
            Section(
                heading="Results",
                level=2,
                kind="body",
                text="\n".join(
                    [
                        "Body text lives here.",
                        "",
                        "![Figure 1](/tmp/figure-1.png)",
                        "",
                        "**Figure 1.** Inline caption text.",
                    ]
                ),
            )
        ]
        article.assets = [
            Asset(kind="figure", heading="Figure 1", caption="Inline caption text.", path="/tmp/figure-1.png", section="body"),
            Asset(kind="figure", heading="Figure 2", caption="Unmatched caption text.", path="/tmp/figure-2.png", section="body"),
        ]

        markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        self.assertIn("![Figure 1](/tmp/figure-1.png)", markdown)
        self.assertIn("## Figures", markdown)
        self.assertNotIn("- Figure 1: Inline caption text.", markdown)
        self.assertIn("![Figure 2](/tmp/figure-2.png)", markdown)

    def test_to_ai_markdown_skips_table_like_pseudo_figures_from_trailing_figures_block(self) -> None:
        article = sample_article()
        article.sections = [
            Section(
                heading="Results",
                level=2,
                kind="body",
                text="\n".join(
                    [
                        "Body text lives here.",
                        "",
                        "![Figure 1](/tmp/figure-1.png)",
                        "",
                        "**Figure 1.** Inline caption text.",
                        "",
                        "**Table 1.** Inline table caption.",
                        "",
                        "| col_a | col_b |",
                        "| --- | --- |",
                        "| 1 | 2 |",
                    ]
                ),
            )
        ]
        article.assets = [
            Asset(kind="figure", heading="Figure 1", caption="Inline caption text.", path="/tmp/figure-1.png", section="body"),
            Asset(
                kind="figure",
                heading="Table 1 Performance summary",
                caption="Table 1 Performance summary",
                section="body",
            ),
        ]

        markdown = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        self.assertIn("![Figure 1](/tmp/figure-1.png)", markdown)
        self.assertIn("**Table 1.** Inline table caption.", markdown)
        self.assertNotIn("## Figures", markdown)

    def test_build_fetch_envelope_default_markdown_uses_captions_only_and_no_supplementary_links(self) -> None:
        article = sample_article()
        article.assets = [
            Asset(kind="figure", heading="Figure 1", caption="Overview figure.", url="downloads/figure-1.png"),
            Asset(kind="supplementary", heading="Supplementary Data", caption="Raw measurements.", url="downloads/supplement.csv"),
        ]

        envelope = paper_fetch.build_fetch_envelope(article, modes={"article", "markdown"}, render=RenderOptions())

        assert envelope.markdown is not None
        self.assertIn("- Figure 1: Overview figure.", envelope.markdown)
        self.assertNotIn("![Figure 1](downloads/figure-1.png)", envelope.markdown)
        self.assertNotIn("[Supplementary Data](downloads/supplement.csv)", envelope.markdown)
        self.assertEqual(envelope.quality.extraction_revision, EXTRACTION_REVISION)
        self.assertEqual(envelope.quality.content_kind, article.quality.content_kind)

    def test_article_from_markdown_preserves_code_fences_and_ascii_tables(self) -> None:
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Structured Article"},
            doi="10.1000/test",
            markdown_text="\n".join(
                [
                    "# Structured Article",
                    "",
                    "## Methods",
                    "",
                    "```python",
                    "if  value:",
                    "    print('kept')",
                    "```",
                    "",
                    "| col_a | col_b |",
                    "| --- | --- |",
                    "| 1 | 2 |",
                ]
            ),
        )

        self.assertEqual(article.sections[0].heading, "Methods")
        self.assertIn("```python", article.sections[0].text)
        self.assertIn("    print('kept')", article.sections[0].text)
        self.assertIn("| col_a | col_b |", article.sections[0].text)

    def test_article_from_markdown_normalizes_blank_asset_fields_to_none(self) -> None:
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Structured Article"},
            doi="10.1000/test",
            markdown_text="## Results\n\nBody text",
            assets=[
                {
                    "kind": "figure",
                    "heading": "Figure 1",
                    "caption": "",
                    "path": "",
                    "url": "https://example.test/figure.png",
                }
            ],
        )

        self.assertIsNone(article.assets[0].caption)
        self.assertIsNone(article.assets[0].path)
        self.assertIsNone(article.assets[0].url)

    def test_article_from_markdown_preserves_empty_body_parent_headings(self) -> None:
        """rule: rule-keep-semantic-parent-heading"""
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Structured Article"},
            doi="10.1000/empty-parent",
            markdown_text=(
                "# Structured Article\n\n"
                "## Results\n\n"
                "### Primary outcome\n\n"
                "The primary outcome text is renderable."
            ),
        )

        self.assertEqual([section.heading for section in article.sections], ["Results", "Primary outcome"])
        rendered = article.to_ai_markdown(max_tokens="full_text")
        self.assertIn("## Results\n\n### Primary outcome", rendered)

    def test_front_matter_unescapes_structured_metadata_strings(self) -> None:
        article = article_from_markdown(
            source="springer_html",
            metadata={
                "title": "Hydrology &amp; Ecology",
                "authors": ["Jane &amp; John"],
                "journal": "Communications Earth &amp; Environment",
            },
            doi="10.1000/entities",
            markdown_text="## Results\n\nBody text lives here.",
        )

        rendered = article.to_ai_markdown(max_tokens="full_text")
        self.assertIn('title: "Hydrology & Ecology"', rendered)
        self.assertIn('authors: "Jane & John"', rendered)
        self.assertIn('journal: "Communications Earth & Environment"', rendered)
        self.assertNotIn("&amp;", rendered)

    def test_normalize_markdown_text_separates_adjacent_block_images(self) -> None:
        normalized = normalize_markdown_text(
            "### Vocabulary Development![Figure 1](figure-1.png)\n"
            "Body text![Figure 2](figure-2.png)\n"
            "$$![Figure 3](figure-3.png)"
        )

        self.assertIn("### Vocabulary Development\n\n![Figure 1](figure-1.png)", normalized)
        self.assertIn("Body text\n\n![Figure 2](figure-2.png)", normalized)
        self.assertIn("$$\n\n![Figure 3](figure-3.png)", normalized)
        self.assertNotIn("Development![Figure", normalized)

    def test_to_ai_markdown_separates_adjacent_section_images_after_asset_rewrites(self) -> None:
        article = sample_article()
        article.sections = [
            Section(
                heading="Results",
                level=2,
                kind="body",
                text="**Figure 1.** Caption text.![Figure 2](/tmp/figure-2.png)",
            )
        ]
        article.assets = [
            Asset(kind="figure", heading="Figure 2", path="/tmp/figure-2.png", section="body"),
        ]

        rendered = article.to_ai_markdown(asset_profile="body", max_tokens="full_text")

        self.assertIn("**Figure 1.** Caption text.\n\n![Figure 2](/tmp/figure-2.png)", rendered)
        self.assertNotIn("text.![Figure", rendered)

    def test_article_from_markdown_rewrites_inline_asset_urls_to_downloaded_paths(self) -> None:
        """rule: rule-preserve-formula-image-fallbacks"""
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Structured Article"},
            doi="10.1000/asset-rewrite",
            markdown_text=(
                "## Results\n\n"
                "The rendered equation is ![Formula](https://media.example.test/math/IEq1_HTML.jpg)."
            ),
            assets=[
                {
                    "kind": "formula",
                    "heading": "Formula 1",
                    "url": "https://media.example.test/math/IEq1_HTML.jpg",
                    "path": "/tmp/downloads/IEq1_HTML.jpg",
                }
            ],
        )

        self.assertIn("![Formula](/tmp/downloads/IEq1_HTML.jpg)", article.sections[0].text)
        self.assertNotIn("https://media.example.test/math/IEq1_HTML.jpg", article.sections[0].text)

    def test_article_from_markdown_normalizes_after_inline_asset_url_rewrite(self) -> None:
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Structured Article"},
            doi="10.1000/asset-rewrite-boundary",
            markdown_text=(
                "## Results\n\n"
                "### Vocabulary Development![Figure 1](https://media.example.test/Fig1_HTML.png)"
            ),
            assets=[
                {
                    "kind": "figure",
                    "heading": "Figure 1",
                    "url": "https://media.example.test/Fig1_HTML.png",
                    "path": "/tmp/downloads/Fig1_HTML.png",
                }
            ],
        )

        rendered_sections = "\n".join(
            f"{section.heading}\n{section.text}" for section in article.sections
        )
        self.assertIn("Vocabulary Development\n![Figure 1](/tmp/downloads/Fig1_HTML.png)", rendered_sections)
        self.assertNotIn("Development![Figure", rendered_sections)

    def test_metadata_only_article_populates_token_breakdown(self) -> None:
        article = metadata_only_article(
            source="crossref_meta",
            metadata={
                "title": "Metadata Only",
                "abstract": "Abstract summary text.",
                "references": ["Reference 1", "Reference 2"],
            },
            doi="10.1000/meta",
        )

        self.assertEqual(article.quality.token_estimate_breakdown.abstract, estimate_tokens("Abstract summary text."))
        self.assertEqual(article.quality.token_estimate_breakdown.body, 0)
        self.assertEqual(article.quality.token_estimate_breakdown.refs, estimate_tokens("Reference 1\nReference 2"))
        self.assertEqual(article.quality.token_estimate, estimate_tokens("Abstract summary text."))
        self.assertEqual(article.quality.confidence, "low")
        self.assertEqual(article.quality.extraction_revision, EXTRACTION_REVISION)

    def test_article_from_structure_populates_token_breakdown(self) -> None:
        article = article_from_structure(
            source="elsevier_xml",
            metadata={"title": "Structured", "abstract": "Abstract words here.", "references": ["Reference 1"]},
            doi="10.1000/structured",
            abstract_lines=[],
            body_lines=["## Results", "", "Result text lives here."],
            figure_entries=[],
            table_entries=[],
            supplement_entries=[],
            conversion_notes=[],
        )

        self.assertEqual(article.quality.token_estimate_breakdown.abstract, estimate_tokens("Abstract words here."))
        self.assertEqual(article.quality.token_estimate_breakdown.body, estimate_tokens("Result text lives here."))
        self.assertEqual(article.quality.token_estimate_breakdown.refs, estimate_tokens("Reference 1"))
        self.assertEqual(
            article.quality.token_estimate,
            estimate_tokens("Abstract words here.") + estimate_tokens("Result text lives here."),
        )

    def test_article_from_markdown_populates_token_breakdown(self) -> None:
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Markdown Article", "references": ["Reference 1", "Reference 2"]},
            doi="10.1000/markdown",
            markdown_text="# Markdown Article\n\n## Abstract\n\nShort abstract.\n\n## Results\n\nBody text lives here.",
        )

        self.assertEqual(article.quality.token_estimate_breakdown.abstract, estimate_tokens("Short abstract."))
        self.assertEqual(article.quality.token_estimate_breakdown.body, estimate_tokens("Body text lives here."))
        self.assertEqual(article.quality.token_estimate_breakdown.refs, estimate_tokens("Reference 1\nReference 2"))
        self.assertEqual(
            article.quality.token_estimate,
            estimate_tokens("Short abstract.") + estimate_tokens("Body text lives here."),
        )

    def test_article_from_markdown_prefixes_reference_labels_from_metadata(self) -> None:
        article = article_from_markdown(
            source="springer_html",
            metadata={
                "title": "Markdown Article",
                "references": [
                    {"label": "1", "raw": "First numbered reference."},
                    {"label": "2.", "raw": "Second numbered reference."},
                ],
            },
            doi="10.1000/markdown-labeled-refs",
            markdown_text="# Markdown Article\n\n## Results\n\nBody text lives here.",
        )

        self.assertEqual([reference.raw for reference in article.references], ["1. First numbered reference.", "2. Second numbered reference."])

    def test_article_from_markdown_skips_parsed_abstract_sections_when_explicit_abstracts_exist(self) -> None:
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Nature Article"},
            doi="10.1000/nature-abstract",
            markdown_text=(
                "# Nature Article\n\n"
                "## Abstract\n\n"
                "Large interannual variations in the measured growth rate of atmospheric carbon dioxide (CO2) "
                "originate primarily from fluctuations in carbon uptake by land ecosystems.\n\n"
                "## Results\n\n"
                "Body text lives here."
            ),
            abstract_sections=[
                {
                    "heading": "Abstract",
                    "text": (
                        "Large interannual variations in the measured growth rate of atmospheric carbon dioxide "
                        "(CO 2 ) originate primarily from fluctuations in carbon uptake by land ecosystems 1 , 2 ."
                    ),
                }
            ],
        )

        self.assertEqual([section.heading for section in article.sections if section.kind == "abstract"], ["Abstract"])
        rendered = article.to_ai_markdown(max_tokens="full_text")
        self.assertEqual(rendered.count("## Abstract"), 1)
        self.assertIn("## Results", rendered)

    def test_article_from_markdown_keeps_data_availability_without_counting_it_as_fulltext(self) -> None:
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Markdown Article"},
            doi="10.1000/data-availability",
            markdown_text=(
                "# Markdown Article\n\n"
                "## Abstract\n\n"
                "Short abstract.\n\n"
                "## Data Availability\n\n"
                "The data are available from the corresponding author on reasonable request."
            ),
        )

        self.assertEqual(article.quality.content_kind, "abstract_only")
        self.assertEqual([section.kind for section in article.sections], ["abstract", "data_availability"])
        rendered = article.to_ai_markdown(max_tokens="full_text")
        self.assertIn("## Abstract", rendered)
        self.assertIn("## Data Availability", rendered)
        self.assertIn("The data are available from the corresponding author", rendered)

    def test_article_from_markdown_keeps_code_availability_without_counting_it_as_fulltext(self) -> None:
        """rule: rule-availability-excluded-from-body-metrics"""
        markdown_text = golden_criteria_scenario_asset("availability_body_metrics", "code_availability.md").read_text(
            encoding="utf-8"
        )
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Markdown Article"},
            doi="10.1000/code-availability",
            markdown_text=markdown_text,
        )

        self.assertEqual(article.quality.content_kind, "abstract_only")
        self.assertEqual([section.kind for section in article.sections], ["abstract", "code_availability"])
        rendered = article.to_ai_markdown(max_tokens="full_text")
        self.assertIn("## Abstract", rendered)
        self.assertIn("## Code Availability", rendered)
        self.assertIn("The analysis code is archived", rendered)

    def test_article_from_markdown_preserves_inline_figure_links_without_counting_them_as_body_text(self) -> None:
        article = article_from_markdown(
            source="pnas",
            metadata={"title": "Markdown Article"},
            doi="10.1000/markdown-figures",
            markdown_text="\n".join(
                [
                    "# Markdown Article",
                    "",
                    "## Results",
                    "",
                    "Body text lives here.",
                    "",
                    "![Figure 1](https://example.test/figure-1.png)",
                    "",
                    "**Figure 1.** Figure caption text.",
                ]
            ),
        )

        self.assertIn("![Figure 1](https://example.test/figure-1.png)", article.sections[0].text)
        self.assertIn("![Figure 1](https://example.test/figure-1.png)", article.to_ai_markdown())
        self.assertEqual(
            article.quality.token_estimate_breakdown.body,
            estimate_tokens("Body text lives here.\n\n**Figure 1.** Figure caption text."),
        )

    def test_article_from_markdown_moves_abstract_into_metadata_and_preserves_abstract_sections(self) -> None:
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Markdown Article"},
            doi="10.1000/markdown",
            markdown_text="# Markdown Article\n\n## Abstract\n\nShort abstract.\n\n## Results\n\nBody text lives here.",
        )

        self.assertEqual(article.metadata.abstract, "Short abstract.")
        self.assertEqual(article.quality.content_kind, "fulltext")
        self.assertTrue(article.quality.has_abstract)
        self.assertEqual(article.sections[0].kind, "abstract")
        self.assertEqual(article.sections[0].heading, "Abstract")
        self.assertEqual(article.sections[0].text, "Short abstract.")
        self.assertEqual(article.sections[1].heading, "Results")
        self.assertEqual(article.quality.confidence, "medium")
        self.assertIn(QUALITY_FLAG_WEAK_BODY_STRUCTURE, article.quality.flags)

    def test_article_from_markdown_keeps_headingless_body_flat_without_synthetic_heading(self) -> None:
        """rule: rule-keep-headingless-body-flat"""
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Headingless Article"},
            doi="10.1000/headingless-markdown",
            markdown_text=(
                "# Headingless Article\n\n"
                "This article starts directly with body prose and never introduces a body subsection heading.\n\n"
                "A second paragraph keeps the body long enough to behave like real article text."
            ),
        )

        self.assertEqual(len(article.sections), 1)
        self.assertEqual(article.sections[0].heading, "")
        self.assertEqual(article.sections[0].kind, "body")
        self.assertEqual(article.quality.content_kind, "fulltext")
        self.assertEqual(
            article.quality.token_estimate_breakdown.body,
            estimate_tokens(article.sections[0].text),
        )
        rendered = article.to_ai_markdown(max_tokens="full_text")
        self.assertIn("# Headingless Article", rendered)
        self.assertNotIn("## Headingless Article", rendered)
        self.assertNotIn("## Full Text", rendered)

    def test_article_from_structure_keeps_headingless_body_flat_without_synthetic_heading(self) -> None:
        article = article_from_structure(
            source="elsevier_xml",
            metadata={"title": "Structured Headingless"},
            doi="10.1000/headingless-structure",
            abstract_lines=[],
            body_lines=[
                "This XML-derived article starts directly with body prose.",
                "",
                "A second paragraph keeps the structured body stable without requiring a fake heading.",
            ],
            figure_entries=[],
            table_entries=[],
            supplement_entries=[],
            conversion_notes=[],
        )

        self.assertEqual(len(article.sections), 1)
        self.assertEqual(article.sections[0].heading, "")
        self.assertEqual(article.sections[0].kind, "body")
        self.assertEqual(article.quality.content_kind, "fulltext")
        self.assertEqual(
            article.quality.token_estimate_breakdown.body,
            estimate_tokens(article.sections[0].text),
        )
        rendered = article.to_ai_markdown(max_tokens="full_text")
        self.assertIn("# Structured Headingless", rendered)
        self.assertNotIn("## Structured Headingless", rendered)
        self.assertNotIn("## Full Text", rendered)

    def test_article_from_markdown_splits_leading_inline_abstract_from_main_text(self) -> None:
        article = article_from_markdown(
            source="science",
            metadata={
                "title": "Markdown Article",
                "abstract": "Incorrect provider abstract that should be replaced.",
            },
            doi="10.1000/inline-abstract",
            markdown_text=(
                "# Markdown Article\n\n"
                "**Abstract.** Short abstract summary stays in metadata only.\n\n"
                "This lead body paragraph should remain in the article body instead of inflating the abstract.\n\n"
                "## Results\n\n"
                "Body text lives here."
            ),
        )

        self.assertEqual(article.metadata.abstract, "Short abstract summary stays in metadata only.")
        self.assertEqual(article.sections[0].heading, "Main Text")
        self.assertIn("lead body paragraph", article.sections[0].text)
        self.assertEqual(article.sections[1].heading, "Results")

    def test_article_from_markdown_treats_single_inline_abstract_block_as_abstract_only(self) -> None:
        article = article_from_markdown(
            source="science",
            metadata={"title": "Markdown Article"},
            doi="10.1000/inline-abstract-only",
            markdown_text="# Markdown Article\n\n**Abstract.** Only the abstract is available in this markdown sample.",
        )

        self.assertEqual(article.metadata.abstract, "Only the abstract is available in this markdown sample.")
        self.assertEqual(article.sections, [])
        self.assertEqual(article.quality.content_kind, "abstract_only")
        self.assertEqual(article.quality.confidence, "low")

    def test_article_from_markdown_downgrades_when_provider_diagnostics_explicitly_reject_body(self) -> None:
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Diagnostic Article", "abstract": "Short abstract."},
            doi="10.1000/diagnostic",
            markdown_text=(
                "# Diagnostic Article\n\n"
                "## Abstract\n\n"
                "Short abstract.\n\n"
                "## Results\n\n"
                "Teaser paragraph that should not survive an explicit access-gated downgrade."
            ),
            availability_diagnostics={
                "accepted": False,
                "reason": "publisher_paywall",
                "content_kind": "abstract_only",
                "hard_negative_signals": ["publisher_paywall"],
                "soft_positive_signals": ["citation_abstract_html_url"],
                "body_metrics": {
                    "char_count": 74,
                    "word_count": 12,
                    "body_block_count": 1,
                    "body_heading_count": 1,
                    "body_to_abstract_ratio": 1.0,
                    "explicit_body_container": False,
                    "post_abstract_body_run": False,
                },
                "figure_count": 0,
            },
            allow_downgrade_from_diagnostics=True,
        )

        self.assertEqual(article.quality.content_kind, "abstract_only")
        self.assertEqual([section.kind for section in article.sections], ["abstract"])
        self.assertEqual(article.quality.confidence, "low")
        self.assertIn(QUALITY_FLAG_ACCESS_GATE_DETECTED, article.quality.flags)

    def test_article_from_markdown_downgrades_when_blocking_fallback_signals_are_present(self) -> None:
        article = article_from_markdown(
            source="wiley_browser",
            metadata={"title": "Blocking Article", "abstract": "Short abstract."},
            doi="10.1000/blocking",
            markdown_text=(
                "# Blocking Article\n\n"
                "## Abstract\n\n"
                "Short abstract.\n\n"
                "## Results\n\n"
                "This teaser paragraph should not survive a blocking-fallback downgrade."
            ),
            availability_diagnostics={
                "accepted": False,
                "reason": "abstract_only",
                "content_kind": "abstract_only",
                "blocking_fallback_signals": ["wiley_access_no", "wiley_format_viewed_abstract"],
                "hard_negative_signals": [],
                "soft_positive_signals": ["selected_article_container"],
                "body_metrics": {
                    "char_count": 67,
                    "word_count": 10,
                    "body_block_count": 1,
                    "body_heading_count": 1,
                    "body_to_abstract_ratio": 1.0,
                    "explicit_body_container": False,
                    "post_abstract_body_run": False,
                },
                "figure_count": 0,
            },
            allow_downgrade_from_diagnostics=True,
        )

        self.assertEqual(article.quality.content_kind, "abstract_only")
        self.assertEqual([section.kind for section in article.sections], ["abstract"])
        self.assertIn(QUALITY_FLAG_ACCESS_GATE_DETECTED, article.quality.flags)

    def test_article_from_markdown_does_not_treat_positive_access_signals_as_access_gate(self) -> None:
        article = article_from_markdown(
            source="science",
            metadata={"title": "Accessible Science Article", "abstract": "Short abstract."},
            doi="10.1000/science-access-positive",
            markdown_text=(
                "# Accessible Science Article\n\n"
                "## Abstract\n\n"
                "Short abstract.\n\n"
                "## Results\n\n"
                + ("Body text " * 120)
            ),
            availability_diagnostics={
                "accepted": True,
                "reason": "body_sufficient",
                "content_kind": "fulltext",
                "hard_negative_signals": [],
                "soft_positive_signals": ["selected_article_container"],
                "strong_positive_signals": [
                    "body_sufficient",
                    "explicit_body_container",
                    "post_abstract_body_run",
                    "aaas_user_entitled",
                    "aaas_user_access_yes",
                ],
                "body_metrics": {
                    "char_count": 1400,
                    "word_count": 240,
                    "body_block_count": 1,
                    "body_heading_count": 1,
                    "body_to_abstract_ratio": 20.0,
                    "explicit_body_container": True,
                    "post_abstract_body_run": True,
                },
                "figure_count": 1,
            },
            allow_downgrade_from_diagnostics=True,
        )

        self.assertEqual(article.quality.content_kind, "fulltext")
        self.assertEqual(article.quality.confidence, "high")
        self.assertNotIn(QUALITY_FLAG_ACCESS_GATE_DETECTED, article.quality.flags)

    def test_article_from_markdown_merges_sparse_provider_body_metrics_with_article_structure(self) -> None:
        article = article_from_markdown(
            source="elsevier_xml",
            metadata={"title": "Structured Elsevier Article", "abstract": "Short abstract."},
            doi="10.1000/elsevier-metrics-merge",
            markdown_text=(
                "# Structured Elsevier Article\n\n"
                "## Introduction\n\n"
                + ("Intro text " * 80)
                + "\n\n## Results\n\n"
                + ("Results text " * 80)
            ),
            assets=[
                {
                    "kind": "figure",
                    "heading": "Figure 1",
                    "caption": "Example figure.",
                    "section": "body",
                }
            ],
            availability_diagnostics={
                "accepted": True,
                "reason": "body_sufficient",
                "content_kind": "fulltext",
                "hard_negative_signals": [],
                "soft_positive_signals": [],
                "strong_positive_signals": ["body_sufficient"],
                "body_metrics": {
                    "char_count": 19,
                    "word_count": 2,
                    "body_block_count": 0,
                    "body_heading_count": 0,
                    "body_to_abstract_ratio": 0.1,
                    "explicit_body_container": False,
                    "post_abstract_body_run": False,
                },
                "figure_count": 0,
            },
            allow_downgrade_from_diagnostics=True,
        )

        self.assertEqual(article.quality.content_kind, "fulltext")
        self.assertEqual(article.quality.confidence, "high")
        self.assertNotIn(QUALITY_FLAG_WEAK_BODY_STRUCTURE, article.quality.flags)
        self.assertEqual(article.quality.body_metrics.body_block_count, 2)
        self.assertEqual(article.quality.body_metrics.body_heading_count, 2)
        self.assertEqual(article.quality.body_metrics.figure_count, 1)
        self.assertGreater(article.quality.body_metrics.word_count, 100)

    def test_article_from_markdown_preserves_explicit_multilingual_abstract_sections(self) -> None:
        """rule: rule-keep-parallel-multilingual-abstracts"""
        article = article_from_markdown(
            source="wiley_browser",
            metadata={"title": "Markdown Article"},
            doi="10.1000/multilingual-abstract",
            markdown_text=(
                "# Markdown Article\n\n"
                "## Results\n\n"
                "Body text lives here with enough prose to remain classified as main text."
            ),
            abstract_sections=[
                {
                    "heading": "Abstract",
                    "text": "English abstract text remains available as the primary abstract.",
                    "language": "en",
                    "kind": "abstract",
                    "order": 0,
                },
                {
                    "heading": "Resumo",
                    "text": "Resumo em portugues permanece como uma segunda secao de resumo.",
                    "language": "pt",
                    "kind": "abstract",
                    "order": 1,
                },
            ],
        )

        self.assertEqual(article.metadata.abstract, "English abstract text remains available as the primary abstract.")
        self.assertEqual([section.heading for section in article.sections[:2]], ["Abstract", "Resumo"])
        self.assertTrue(all(section.kind == "abstract" for section in article.sections[:2]))
        rendered = article.to_ai_markdown(max_tokens="full_text")
        self.assertIn("## Abstract", rendered)
        self.assertIn("## Resumo", rendered)
        self.assertIn("## Results", rendered)

    def test_article_from_markdown_uses_section_hints_for_nonliteral_data_availability(self) -> None:
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Markdown Article"},
            doi="10.1000/section-hints",
            markdown_text=(
                "# Markdown Article\n\n"
                "## Availability Statement\n\n"
                "Data are archived in a public repository.\n\n"
                "## Results\n\n"
                "Body text lives here with enough prose to remain classified as main text."
            ),
            section_hints=[
                {
                    "heading": "Availability Statement",
                    "level": 2,
                    "kind": "data_availability",
                    "order": 0,
                },
                {
                    "heading": "Results",
                    "level": 2,
                    "kind": "body",
                    "order": 1,
                },
            ],
        )

        self.assertEqual([section.kind for section in article.sections], ["data_availability", "body"])
        self.assertEqual(article.quality.content_kind, "fulltext")

    def test_article_from_markdown_coerces_dict_object_and_section_hint_in_declared_order(self) -> None:
        """rule: rule-section-hints-normalize-availability"""
        markdown_text = golden_criteria_scenario_asset("section_hints_availability", "article.md").read_text(
            encoding="utf-8"
        )
        hint_payloads = json.loads(
            golden_criteria_scenario_asset("section_hints_availability", "section_hints.json").read_text(
                encoding="utf-8"
            )
        )
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Markdown Article"},
            doi="10.1000/mixed-section-hints",
            markdown_text=markdown_text,
            section_hints=[
                SimpleNamespace(**hint_payloads[0]),
                hint_payloads[1],
                hint_payloads[2],
                SectionHint(**hint_payloads[3]),
            ],
        )

        self.assertEqual(
            [(section.heading, section.kind) for section in article.sections],
            [
                ("Results", "body"),
                ("Data archive", "data_availability"),
                ("Code archive", "code_availability"),
            ],
        )

    def test_article_from_markdown_uses_section_hints_for_nonliteral_code_availability(self) -> None:
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Markdown Article"},
            doi="10.1000/code-section-hints",
            markdown_text=(
                "# Markdown Article\n\n"
                "## Availability Statement\n\n"
                "Analysis code is archived in a public repository.\n\n"
                "## Results\n\n"
                "Body text lives here with enough prose to remain classified as main text."
            ),
            section_hints=[
                {
                    "heading": "Availability Statement",
                    "level": 2,
                    "kind": "code_availability",
                    "order": 0,
                },
                {
                    "heading": "Results",
                    "level": 2,
                    "kind": "body",
                    "order": 1,
                },
            ],
        )

        self.assertEqual([section.kind for section in article.sections], ["code_availability", "body"])
        self.assertEqual(article.quality.content_kind, "fulltext")

    def test_article_from_markdown_keeps_heading_fallback_without_section_hints(self) -> None:
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Markdown Article"},
            doi="10.1000/section-hints-fallback",
            markdown_text=(
                "# Markdown Article\n\n"
                "## Availability Statement\n\n"
                "Data are archived in a public repository."
            ),
        )

        self.assertEqual(len(article.sections), 1)
        self.assertEqual(article.sections[0].heading, "Availability Statement")
        self.assertEqual(article.sections[0].kind, "body")

    def test_article_from_markdown_does_not_duplicate_explicit_abstract_when_section_hints_are_present(self) -> None:
        """rule: rule-stable-frontmatter-order"""
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Markdown Article"},
            doi="10.1000/section-hints-abstract",
            markdown_text=(
                "# Markdown Article\n\n"
                "## Abstract\n\n"
                "Explicit abstract block should not duplicate.\n\n"
                "## Results\n\n"
                "Body text lives here with enough prose to remain classified as main text."
            ),
            abstract_sections=[
                {
                    "heading": "Abstract",
                    "text": "Explicit abstract block should not duplicate.",
                    "kind": "abstract",
                    "order": 0,
                }
            ],
            section_hints=[
                {
                    "heading": "Results",
                    "level": 2,
                    "kind": "body",
                    "order": 0,
                }
            ],
        )

        self.assertEqual([section.heading for section in article.sections], ["Abstract", "Results"])
        self.assertEqual(len([section for section in article.sections if section.kind == "abstract"]), 1)
        self.assertEqual(article.metadata.abstract, "Explicit abstract block should not duplicate.")

    def test_article_from_markdown_deduplicates_near_matching_explicit_abstract_sections(self) -> None:
        base_abstract = (
            "Identifying droughts and accurately evaluating drought impacts on vegetation growth are crucial to understanding "
            "the terrestrial carbon balance across China. However, few studies have identified the critical drought thresholds "
            "that impact China's vegetation growth, leading to large uncertainty in assessing the ecological consequences of "
            "droughts. In this study, we utilize gridded surface soil moisture data and satellite-observed normalized difference "
            "vegetation index (NDVI) to assess vegetation response to droughts in China during 2001-2018. Based on the nonlinear "
            "relationship between changing drought stress and the coincident anomalies of NDVI during the growing season, we derive "
            "the spatial patterns of satellite-based drought thresholds."
        )
        explicit_abstract = base_abstract + (
            " Additional supporting context keeps the abstract long enough to trigger near-duplicate matching without changing the "
            "heading or the overall meaning of the section."
            * 8
        )
        parsed_abstract = explicit_abstract.replace(" during 2001-2018.", " during.")
        article = article_from_markdown(
            source="wiley_browser",
            metadata={"title": "Markdown Article"},
            doi="10.1000/near-duplicate-abstract",
            markdown_text=(
                "# Markdown Article\n\n"
                "## Abstract\n\n"
                f"{parsed_abstract}\n\n"
                "## Results\n\n"
                "Body text lives here with enough prose to remain classified as main text."
            ),
            abstract_sections=[
                {
                    "heading": "Abstract",
                    "text": explicit_abstract,
                    "kind": "abstract",
                    "order": 0,
                }
            ],
            section_hints=[
                {
                    "heading": "Results",
                    "level": 2,
                    "kind": "body",
                    "order": 0,
                }
            ],
        )

        self.assertEqual([section.heading for section in article.sections], ["Abstract", "Results"])
        self.assertEqual(len([section for section in article.sections if section.kind == "abstract"]), 1)
        self.assertEqual(article.metadata.abstract, explicit_abstract)

    def test_article_from_markdown_promotes_repeated_methods_summary_to_methods(self) -> None:
        """rule: rule-springer-methods-summary"""
        html = golden_criteria_asset("10.1038/nature12915", "original.html").read_text(
            encoding="utf-8",
            errors="ignore",
        )
        extraction_payload = _springer_html.extract_html_payload(
            html,
            "https://www.nature.com/articles/nature12915",
        )
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Accelerated increase in vegetation carbon sequestration in tropical forests"},
            doi="10.1038/nature12915",
            markdown_text=extraction_payload["markdown_text"],
            abstract_sections=extraction_payload["abstract_sections"],
            section_hints=extraction_payload["section_hints"],
        )

        methods_sections = [
            section
            for section in article.sections
            if section.heading in {"Methods Summary", "Methods", "Online Methods"}
        ]
        self.assertEqual([section.heading for section in methods_sections], ["Methods Summary", "Methods"])
        methods_section = methods_sections[1]
        self.assertEqual(methods_section.text, "")

        markdown = article.to_ai_markdown(max_tokens="full_text")

        self.assertEqual(markdown.count("## Methods Summary"), 1)
        self.assertEqual(markdown.count("\n## Methods\n"), 1)
        self.assertNotIn("## Online Methods", markdown)

    def test_article_from_real_nature_markdown_keeps_methods_summary_without_structure_hints(self) -> None:
        html = golden_criteria_asset("10.1038/nature12915", "original.html").read_text(
            encoding="utf-8",
            errors="ignore",
        )
        extraction_payload = _springer_html.extract_html_payload(
            html,
            "https://www.nature.com/articles/nature12915",
        )
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Accelerated increase in vegetation carbon sequestration in tropical forests"},
            doi="10.1038/nature12915",
            markdown_text=extraction_payload["markdown_text"],
            abstract_sections=extraction_payload["abstract_sections"],
        )

        methods_headings = [
            section.heading
            for section in article.sections
            if section.heading in {"Methods Summary", "Methods", "Online Methods"}
        ]
        self.assertEqual(methods_headings, ["Methods Summary", "Methods"])
        markdown = article.to_ai_markdown(max_tokens="full_text")

        self.assertIn("## Methods Summary", markdown)
        self.assertNotIn("## Online Methods", markdown)

    def test_metadata_abstract_strips_redundant_heading_prefix(self) -> None:
        article = metadata_only_article(
            source="wiley_browser",
            metadata={
                "title": "Metadata Article",
                "abstract": "Abstract The abstract text should not keep the duplicated heading prefix.",
            },
            doi="10.1000/abstract-prefix",
        )

        self.assertEqual(
            article.metadata.abstract,
            "The abstract text should not keep the duplicated heading prefix.",
        )
        self.assertNotIn("**Abstract.** Abstract", article.to_ai_markdown(max_tokens="full_text"))

    def test_article_from_markdown_classifies_abstract_only_when_no_body_sections_remain(self) -> None:
        article = article_from_markdown(
            source="springer_html",
            metadata={"title": "Markdown Article"},
            doi="10.1000/markdown",
            markdown_text="# Markdown Article\n\n## Abstract\n\nShort abstract.",
        )

        self.assertEqual(article.metadata.abstract, "Short abstract.")
        self.assertEqual(len(article.sections), 1)
        self.assertEqual(article.sections[0].kind, "abstract")
        self.assertEqual(article.quality.content_kind, "abstract_only")
        self.assertFalse(article.quality.has_fulltext)
        self.assertTrue(article.quality.has_abstract)

    def test_normalize_markdown_text_collapses_padding_inside_display_math(self) -> None:
        normalized = normalize_markdown_text(
            "Before\n\n$$\n\n\\begin{matrix} a \\\\ b \\end{matrix}\n\n$$\n\nAfter"
        )

        self.assertIn("$$\n\\begin{matrix} a \\\\ b \\end{matrix}\n$$", normalized)
        self.assertNotIn("$$\n\n\\begin{matrix}", normalized)
        self.assertNotIn("\\end{matrix}\n\n$$", normalized)
