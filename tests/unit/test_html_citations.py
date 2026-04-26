from __future__ import annotations

import unittest

from paper_fetch.markdown.citations import (
    clean_citation_markers,
    is_citation_link,
    is_citation_text,
    make_numeric_citation_sentinel,
    normalize_inline_citation_markdown,
)


class HtmlCitationsTests(unittest.TestCase):
    def test_is_citation_text_only_accepts_true_numeric_citations(self) -> None:
        self.assertTrue(is_citation_text("1, 2-4"))
        self.assertTrue(is_citation_text("3–5"))
        self.assertFalse(is_citation_text("1901–2020"))
        self.assertFalse(is_citation_text("(2016)"))
        self.assertFalse(is_citation_text("Fig. 1"))

    def test_is_citation_link_recognizes_reference_anchors_without_matching_figure_links(self) -> None:
        self.assertTrue(is_citation_link("#ref-CR1", "1"))
        self.assertTrue(is_citation_link("#bib23", "23"))
        self.assertTrue(is_citation_link("#core-collateral-r5", "5"))
        self.assertFalse(is_citation_link("/articles/example", "1"))
        self.assertFalse(is_citation_link("#Fig1", "1"))
        self.assertFalse(is_citation_link("#gcb16414-bib-0007", "2019"))

    def test_clean_citation_markers_preserves_year_ranges(self) -> None:
        cleaned = clean_citation_markers("Rainfall totals 1901–2020. Growth 1981–2010. Stable ending.")

        self.assertEqual(cleaned, "Rainfall totals 1901–2020. Growth 1981–2010. Stable ending.")

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

    def test_normalize_inline_citation_markdown_renders_numeric_sentinels_as_superscripts(self) -> None:
        sentinel = make_numeric_citation_sentinel("2, 43")

        self.assertEqual(
            normalize_inline_citation_markdown(f"Example {sentinel}"),
            "Example<sup>2, 43</sup>",
        )

    def test_normalize_inline_citation_markdown_preserves_bare_ref_prefixes(self) -> None:
        normalized = normalize_inline_citation_markdown("See ref. 21 and refs. 12-14 for details.")

        self.assertEqual(normalized, "See ref. 21 and refs. 12-14 for details.")

    def test_normalize_inline_citation_markdown_rewrites_marked_ref_prefixes(self) -> None:
        sentinel = make_numeric_citation_sentinel("21")

        normalized = normalize_inline_citation_markdown(f"See ref. {sentinel} for details.")

        self.assertEqual(normalized, "See<sup>21</sup> for details.")

    def test_normalize_inline_citation_markdown_preserves_non_citation_numeric_text(self) -> None:
        text = "Zhu et al. (2016) measured stations (9) using Eq. 8 from 1901–2020."

        self.assertEqual(normalize_inline_citation_markdown(text), text)

    def test_normalize_inline_citation_markdown_moves_sup_trailing_space_outside_tag(self) -> None:
        normalized = normalize_inline_citation_markdown("Losses reached (10<sup>15 </sup>g).")

        self.assertEqual(normalized, "Losses reached (10<sup>15</sup> g).")

    def test_normalize_inline_citation_markdown_handles_legacy_science_italics(self) -> None:
        normalized = normalize_inline_citation_markdown("The event is documented (*46, 55*, *56*).")

        self.assertEqual(normalized, "The event is documented<sup>46, 55, 56</sup>.")


if __name__ == "__main__":
    unittest.main()
