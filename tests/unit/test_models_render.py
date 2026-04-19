from __future__ import annotations

import unittest

from paper_fetch import service as paper_fetch
from paper_fetch.models import (
    Asset,
    ArticleModel,
    Metadata,
    Quality,
    Reference,
    RenderOptions,
    Section,
    TokenEstimateBreakdown,
    article_from_markdown,
    article_from_structure,
    estimate_tokens,
    metadata_only_article,
    normalize_markdown_text,
)

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

    def test_article_from_markdown_preserves_code_fences_and_ascii_tables(self) -> None:
        article = article_from_markdown(
            source="html_generic",
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
            source="html_generic",
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
            source="html_generic",
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

    def test_article_from_markdown_keeps_data_availability_without_counting_it_as_fulltext(self) -> None:
        article = article_from_markdown(
            source="html_generic",
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
        self.assertEqual(len(article.sections), 1)
        self.assertEqual(article.sections[0].kind, "data_availability")
        rendered = article.to_ai_markdown(max_tokens="full_text")
        self.assertIn("## Data Availability", rendered)
        self.assertIn("The data are available from the corresponding author", rendered)

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

    def test_article_from_markdown_moves_abstract_into_metadata_and_excludes_abstract_sections(self) -> None:
        article = article_from_markdown(
            source="html_generic",
            metadata={"title": "Markdown Article"},
            doi="10.1000/markdown",
            markdown_text="# Markdown Article\n\n## Abstract\n\nShort abstract.\n\n## Results\n\nBody text lives here.",
        )

        self.assertEqual(article.metadata.abstract, "Short abstract.")
        self.assertEqual(article.quality.content_kind, "fulltext")
        self.assertTrue(article.quality.has_abstract)
        self.assertFalse(any(section.kind == "abstract" for section in article.sections))

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
            source="html_generic",
            metadata={"title": "Markdown Article"},
            doi="10.1000/markdown",
            markdown_text="# Markdown Article\n\n## Abstract\n\nShort abstract.",
        )

        self.assertEqual(article.metadata.abstract, "Short abstract.")
        self.assertEqual(article.sections, [])
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
