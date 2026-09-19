from __future__ import annotations
from paper_fetch.models import (
    article_from_markdown,
)
import unittest
from paper_fetch.providers import _springer_html as springer_html
from tests.golden_criteria import golden_criteria_asset


class ModelsRenderTests(unittest.TestCase):
    def test_article_from_markdown_promotes_repeated_methods_summary_to_methods(
        self,
    ) -> None:
        html = golden_criteria_asset("10.1038/nature12915", "original.html").read_text(
            encoding="utf-8",
            errors="ignore",
        )
        extraction_payload = springer_html.extract_html_payload(
            html,
            "https://www.nature.com/articles/nature12915",
        )
        article = article_from_markdown(
            source="springer_html",
            metadata={
                "title": "Accelerated increase in vegetation carbon sequestration in tropical forests"
            },
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
        self.assertEqual(
            [section.heading for section in methods_sections],
            ["Methods Summary", "Methods"],
        )
        methods_section = methods_sections[1]
        self.assertEqual(methods_section.text, "")

        markdown = article.to_ai_markdown(max_tokens="full_text")

        self.assertEqual(markdown.count("## Methods Summary"), 1)
        self.assertEqual(markdown.count("\n## Methods\n"), 1)
        self.assertNotIn("## Online Methods", markdown)

    def test_article_from_real_nature_markdown_keeps_methods_summary_without_structure_hints(
        self,
    ) -> None:
        html = golden_criteria_asset("10.1038/nature12915", "original.html").read_text(
            encoding="utf-8",
            errors="ignore",
        )
        extraction_payload = springer_html.extract_html_payload(
            html,
            "https://www.nature.com/articles/nature12915",
        )
        article = article_from_markdown(
            source="springer_html",
            metadata={
                "title": "Accelerated increase in vegetation carbon sequestration in tropical forests"
            },
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
