from __future__ import annotations

import unittest
from types import SimpleNamespace

from paper_fetch.providers._html_availability import (
    assess_html_fulltext_availability,
    assess_plain_text_fulltext_availability,
    assess_structured_article_fulltext_availability,
)



class HtmlAvailabilityTests(unittest.TestCase):
    def test_assess_html_fulltext_accepts_body_sufficient_html_without_figures(self) -> None:
        markdown = "# Example Article\n\n## Results\n\n" + ("Body text " * 120)
        diagnostics = assess_html_fulltext_availability(
            markdown,
            {"title": "Example Article", "doi": "10.1000/example"},
            provider="html_generic",
            html_text="<html><body><article><div property='articleBody'>Body</div></article></body></html>",
            title="Example Article",
        )

        self.assertTrue(diagnostics.accepted)
        self.assertEqual(diagnostics.reason, "body_sufficient")
        self.assertEqual(diagnostics.figure_count, 0)

    def test_assess_html_fulltext_rejects_figure_only_teaser(self) -> None:
        diagnostics = assess_html_fulltext_availability(
            "# Example Article\n\nFigure teaser only.",
            {"title": "Example Article", "doi": "10.1000/example"},
            provider="html_generic",
            html_text=(
                "<html><body><article>"
                "<figure><img src='/fig1.png' /><figcaption>Teaser figure.</figcaption></figure>"
                "</article></body></html>"
            ),
            title="Example Article",
        )

        self.assertFalse(diagnostics.accepted)
        self.assertEqual(diagnostics.reason, "insufficient_body")
        self.assertEqual(diagnostics.figure_count, 1)
        self.assertIn("has_figures", diagnostics.soft_positive_signals)

    def test_assess_html_fulltext_ignores_paywall_text_outside_body_container(self) -> None:
        body_text = " ".join(["Important body text with enough detail."] * 30)
        html = (
            "<html><body>"
            "<aside>Access through your institution. Purchase access.</aside>"
            "<article><section id='bodymatter' property='articleBody'>"
            "<h1>Example Article</h1>"
            "<h2>Abstract</h2><p>Short abstract.</p>"
            "<h2>Discussion</h2><p>"
            f"{body_text}"
            "</p></section></article>"
            "</body></html>"
        )
        diagnostics = assess_html_fulltext_availability(
            "# Example Article\n\n## Abstract\n\nShort abstract.\n\n## Discussion\n\n" + body_text,
            {"title": "Example Article", "doi": "10.1000/example"},
            provider="html_generic",
            html_text=html,
            title="Example Article",
            final_url="https://example.test/article",
        )

        self.assertTrue(diagnostics.accepted)
        self.assertEqual(diagnostics.reason, "body_sufficient")
        self.assertNotIn("publisher_paywall", diagnostics.hard_negative_signals)
        self.assertIn("explicit_body_container", diagnostics.strong_positive_signals)

    def test_assess_html_fulltext_accepts_narrative_review_without_imrad_headings(self) -> None:
        paragraph = "This review paragraph provides enough narrative detail. It contains multiple sentences for structure. "
        html = (
            "<html><body><article>"
            "<h1>Review Example</h1>"
            f"<p>{paragraph * 2}</p>"
            f"<p>{paragraph * 2}</p>"
            "</article></body></html>"
        )
        diagnostics = assess_html_fulltext_availability(
            "# Review Example\n\n" + (paragraph * 2) + "\n\n" + (paragraph * 2),
            {"title": "Review Example", "doi": "10.1000/review", "article_type": "Review"},
            provider="html_generic",
            html_text=html,
            title="Review Example",
        )

        self.assertTrue(diagnostics.accepted)
        self.assertIn("narrative_article_type", diagnostics.soft_positive_signals)
        self.assertEqual(diagnostics.body_metrics["body_run_paragraph_count"], 2)

    def test_assess_html_fulltext_rejects_access_gate_without_body_run(self) -> None:
        diagnostics = assess_html_fulltext_availability(
            "# Example Article\n\nCheck access to continue.\n\nPurchase access.",
            {"title": "Example Article", "doi": "10.1000/example"},
            provider="html_generic",
            html_text=(
                "<html><body><article><h1>Example Article</h1>"
                "<div class='access-widget'>Check access to continue. Purchase access.</div>"
                "</article></body></html>"
            ),
            title="Example Article",
            final_url="https://example.test/article/access",
        )

        self.assertFalse(diagnostics.accepted)
        self.assertEqual(diagnostics.reason, "publisher_paywall")

    def test_assess_html_fulltext_rejects_references_only_page(self) -> None:
        diagnostics = assess_html_fulltext_availability(
            "# Example Article\n\n## References\n\n1. Example cited work.",
            {"title": "Example Article", "doi": "10.1000/example"},
            provider="html_generic",
            html_text=(
                "<html><body><article><h1>Example Article</h1><h2>References</h2>"
                "<ol class='references'><li>Example cited work. Another sentence.</li></ol>"
                "</article></body></html>"
            ),
            title="Example Article",
        )

        self.assertFalse(diagnostics.accepted)
        self.assertEqual(diagnostics.reason, "insufficient_body")

    def test_assess_plain_text_accepts_short_editorial_when_marked_narrative(self) -> None:
        paragraph = "This editorial paragraph is concise but still carries full narrative meaning. It has a second sentence. "
        diagnostics = assess_plain_text_fulltext_availability(
            "# Editorial Example\n\nBy Alice Example\n\n" + (paragraph * 2) + "\n\n" + (paragraph * 2),
            {"title": "Editorial Example", "article_type": "Editorial"},
            title="Editorial Example",
        )

        self.assertTrue(diagnostics.accepted)
        self.assertIn("narrative_article_type", diagnostics.soft_positive_signals)
        self.assertEqual(diagnostics.body_metrics["body_run_paragraph_count"], 2)

    def test_assess_plain_text_rejects_abstract_only_without_metadata_abstract(self) -> None:
        abstract_text = (
            "This abstract remains long enough to look substantial, but it is still only abstract prose. "
            "It adds a second sentence so the detector sees more than a stub. "
        )
        diagnostics = assess_plain_text_fulltext_availability(
            "# Abstract Example\n\n## Abstract\n\n" + (abstract_text * 3),
            {"title": "Abstract Example"},
            title="Abstract Example",
        )

        self.assertFalse(diagnostics.accepted)
        self.assertEqual(diagnostics.content_kind, "abstract_only")
        self.assertEqual(diagnostics.reason, "abstract_only")
        self.assertEqual(diagnostics.body_metrics["word_count"], 0)

    def test_assess_html_rejects_abstract_only_when_metadata_differs_only_by_punctuation(self) -> None:
        abstract_markdown = (
            "This abstract has line breaks and punctuation differences, but no article body survives filtering.\n"
            "A second sentence keeps it looking substantial."
        )
        diagnostics = assess_html_fulltext_availability(
            "# Abstract Example\n\n" + abstract_markdown,
            {
                "title": "Abstract Example",
                "abstract": "This abstract has line breaks and punctuation differences but no article body survives filtering. A second sentence keeps it looking substantial!",
                "citation_abstract_html_url": "https://example.test/article-abstract",
            },
            provider="html_generic",
            html_text=(
                "<html><head><meta name='WT.z_cg_type' content='Abstract' /></head>"
                "<body><article><p>"
                "This abstract has line breaks and punctuation differences, but no article body survives filtering. "
                "A second sentence keeps it looking substantial."
                "</p></article></body></html>"
            ),
            title="Abstract Example",
            final_url="https://example.test/article-abstract",
        )

        self.assertFalse(diagnostics.accepted)
        self.assertEqual(diagnostics.content_kind, "abstract_only")
        self.assertEqual(diagnostics.reason, "abstract_only")
        self.assertIn("citation_abstract_html_url", diagnostics.soft_positive_signals)

    def test_assess_html_accepts_single_long_body_block_without_headings(self) -> None:
        paragraph = (
            "This narrative body paragraph is long enough to count as full text even without section headings. "
            "It includes a second sentence for prose structure. "
        )
        diagnostics = assess_html_fulltext_availability(
            "# Narrative Example\n\n" + (paragraph * 8),
            {"title": "Narrative Example", "doi": "10.1000/narrative"},
            provider="html_generic",
            html_text="<html><body><article><p>" + (paragraph * 8) + "</p></article></body></html>",
            title="Narrative Example",
        )

        self.assertTrue(diagnostics.accepted)
        self.assertEqual(diagnostics.content_kind, "fulltext")
        self.assertEqual(diagnostics.reason, "body_sufficient")

    def test_assess_structured_article_accepts_single_narrative_body_section(self) -> None:
        article = SimpleNamespace(
            quality=SimpleNamespace(has_fulltext=True),
            sections=[
                SimpleNamespace(kind="abstract", text="Abstract only."),
                SimpleNamespace(
                    kind="commentary",
                    text=(
                        "This perspective section contains enough narrative detail to count as body text. "
                        "It includes a second sentence so the structure detector treats it as substantial prose."
                    ),
                ),
            ],
            assets=[],
            metadata=SimpleNamespace(title="Structured Narrative Example"),
        )

        diagnostics = assess_structured_article_fulltext_availability(article, title="Structured Narrative Example")

        self.assertTrue(diagnostics.accepted)
        self.assertEqual(diagnostics.reason, "structured_body_sections")



if __name__ == "__main__":
    unittest.main()
