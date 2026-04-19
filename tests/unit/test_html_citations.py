from __future__ import annotations

import unittest

from paper_fetch.providers._html_citations import (
    clean_citation_markers,
    is_citation_link,
    is_citation_text,
)


class HtmlCitationsTests(unittest.TestCase):
    def test_is_citation_text_recognizes_numeric_superscripts(self) -> None:
        self.assertTrue(is_citation_text("1, 2-4"))
        self.assertTrue(is_citation_text("3–5"))
        self.assertFalse(is_citation_text("Fig. 1"))

    def test_is_citation_link_recognizes_reference_anchors(self) -> None:
        self.assertTrue(is_citation_link("#ref-CR1", "1"))
        self.assertTrue(is_citation_link("#bib23", "23"))
        self.assertTrue(is_citation_link("#cite-note", "5"))
        self.assertFalse(is_citation_link("/articles/example", "1"))

    def test_clean_citation_markers_removes_reference_ranges_and_lists(self) -> None:
        cleaned = clean_citation_markers("Rainfall totals1-3. Growth3,4. Stable ending.")

        self.assertEqual(cleaned, "Rainfall totals. Growth. Stable ending.")

    def test_clean_citation_markers_unwraps_inline_links_and_normalizes_labels(self) -> None:
        cleaned = clean_citation_markers(
            "See [details](/articles/example#ref-CR1) and Fig 1 for context.",
            unwrap_inline_links=True,
            normalize_labels=True,
        )

        self.assertEqual(cleaned, "See details and Fig1 for context.")

    def test_clean_citation_markers_drops_springer_figure_lines_when_requested(self) -> None:
        cleaned = clean_citation_markers(
            "Fig. 1: Caption that should be removed.\n\nSource data\n\n## Results",
            drop_figure_lines=True,
        )

        self.assertEqual(cleaned, "## Results")


if __name__ == "__main__":
    unittest.main()
