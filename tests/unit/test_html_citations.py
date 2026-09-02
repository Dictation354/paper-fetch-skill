from __future__ import annotations

import unittest

from bs4 import BeautifulSoup

from paper_fetch.markdown.citations import (
    clean_citation_markers,
    is_citation_link,
    is_citation_text,
    make_numeric_citation_sentinel,
    numeric_citation_payload_from_html_node,
    normalize_inline_citation_markdown,
)
from paper_fetch.providers.html_springer_nature import (
    SPRINGER_NATURE_CITATION_LABEL_PATTERNS,
    SPRINGER_NATURE_FIGURE_LINE_PATTERNS,
    SPRINGER_NATURE_INLINE_LINK_UNWRAP_PATTERNS,
)


class HtmlCitationsTests(unittest.TestCase):
    def test_is_citation_text_only_accepts_true_numeric_citations(self) -> None:
        self.assertTrue(is_citation_text("1, 2-4"))
        self.assertTrue(is_citation_text("3–5"))
        self.assertFalse(is_citation_text("1901–2020"))
        self.assertFalse(is_citation_text("(2016)"))
        self.assertFalse(is_citation_text("Fig. 1"))

    def test_is_citation_link_recognizes_reference_anchors_without_matching_figure_links(
        self,
    ) -> None:
        self.assertTrue(is_citation_link("#ref-CR1", "1"))
        self.assertTrue(is_citation_link("#bib23", "23"))
        self.assertTrue(is_citation_link("#core-collateral-r5", "5"))
        self.assertFalse(is_citation_link("/articles/example", "1"))
        self.assertFalse(is_citation_link("#Fig1", "1"))
        self.assertFalse(is_citation_link("#references", "1"))
        self.assertFalse(is_citation_link("#gcb16414-bib-0007", "2019"))

    def test_numeric_citation_payload_from_html_node_handles_wrappers(self) -> None:
        soup = BeautifulSoup(
            """
<p>
  <i id="range"><a href="#core-collateral-R1" role="doc-biblioref">1</a>-<a href="#core-collateral-R3" role="doc-biblioref">3</a></i>
  <a id="bracketed" data-test="citation-ref" href="#ref-CR1">[1,2]</a>
  <sup id="bare">2</sup>
  <a id="figure" href="#Fig1">[1]</a>
  <a id="year" class="bibLink" href="#gcb16414-bib-0007">2019</a>
</p>
""",
            "html.parser",
        )

        self.assertEqual(
            numeric_citation_payload_from_html_node(
                soup.select_one("#range"),
                wrapper_tags=("sup", "i", "em"),
            ),
            "1–3",
        )
        self.assertEqual(
            numeric_citation_payload_from_html_node(soup.select_one("#bracketed")),
            "1, 2",
        )
        self.assertIsNone(
            numeric_citation_payload_from_html_node(soup.select_one("#bare"))
        )
        self.assertIsNone(
            numeric_citation_payload_from_html_node(soup.select_one("#figure"))
        )
        self.assertIsNone(
            numeric_citation_payload_from_html_node(soup.select_one("#year"))
        )

    def test_section_and_atypon_citation_payloads_match_for_italic_ranges(self) -> None:
        from paper_fetch.providers._html_section_markdown import (
            render_clean_text_from_html,
        )
        from paper_fetch.providers.atypon_browser_workflow.normalization import (
            _render_non_table_inline_node,
        )

        soup = BeautifulSoup(
            """
<p>Observed <i><a href="#core-collateral-R1" role="doc-biblioref">1</a> – <a href="#core-collateral-R3" role="doc-biblioref">3</a></i> in practice.</p>
""",
            "html.parser",
        )

        section = normalize_inline_citation_markdown(
            render_clean_text_from_html(soup.p)
        )
        atypon = normalize_inline_citation_markdown(
            _render_non_table_inline_node(soup.p)
        )

        self.assertEqual(section, "Observed<sup>1–3</sup> in practice.")
        self.assertEqual(atypon, section)

    def test_clean_citation_markers_preserves_year_ranges(self) -> None:
        cleaned = clean_citation_markers(
            "Rainfall totals 1901–2020. Growth 1981–2010. Stable ending."
        )

        self.assertEqual(
            cleaned, "Rainfall totals 1901–2020. Growth 1981–2010. Stable ending."
        )

    def test_clean_citation_markers_unwraps_inline_links_and_normalizes_labels(
        self,
    ) -> None:
        cleaned = clean_citation_markers(
            "See [details](/articles/example#ref-CR1) and Fig 1 for context.",
            unwrap_inline_links=True,
            inline_link_patterns=SPRINGER_NATURE_INLINE_LINK_UNWRAP_PATTERNS,
            normalize_labels=True,
        )

        self.assertEqual(cleaned, "See details and Fig1 for context.")

    def test_clean_citation_markers_keeps_extended_data_prefix_provider_specific(
        self,
    ) -> None:
        generic = clean_citation_markers(
            "Extended Data Fig 2 and Fig 1 are cited.",
            unwrap_inline_links=True,
            normalize_labels=True,
        )
        springer_nature = clean_citation_markers(
            "See [details](/articles/example#ref-CR1), Extended Data Fig 2 and Fig 1.",
            unwrap_inline_links=True,
            inline_link_patterns=SPRINGER_NATURE_INLINE_LINK_UNWRAP_PATTERNS,
            normalize_labels=True,
            label_patterns=SPRINGER_NATURE_CITATION_LABEL_PATTERNS,
        )

        self.assertEqual(generic, "Extended Data Fig2 and Fig1 are cited.")
        self.assertEqual(springer_nature, "See details, Extended Data Fig2 and Fig1.")

    def test_clean_citation_markers_drops_springer_figure_lines_when_requested(
        self,
    ) -> None:
        cleaned = clean_citation_markers(
            "Fig. 1: Caption that should be removed.\n\nSource data\n\n## Results",
            drop_figure_lines=True,
            figure_line_patterns=SPRINGER_NATURE_FIGURE_LINE_PATTERNS,
        )

        self.assertEqual(cleaned, "## Results")

    def test_normalize_inline_citation_markdown_renders_numeric_sentinels_as_superscripts(
        self,
    ) -> None:
        sentinel = make_numeric_citation_sentinel("2, 43")

        self.assertEqual(
            normalize_inline_citation_markdown(f"Example {sentinel}"),
            "Example<sup>2, 43</sup>",
        )

    def test_normalize_inline_citation_markdown_preserves_bare_ref_prefixes(
        self,
    ) -> None:
        normalized = normalize_inline_citation_markdown(
            "See ref. 21 and refs. 12-14 for details."
        )

        self.assertEqual(normalized, "See ref. 21 and refs. 12-14 for details.")

    def test_normalize_inline_citation_markdown_rewrites_marked_ref_prefixes(
        self,
    ) -> None:
        sentinel = make_numeric_citation_sentinel("21")

        normalized = normalize_inline_citation_markdown(
            f"See ref. {sentinel} for details."
        )

        self.assertEqual(normalized, "See<sup>21</sup> for details.")

    def test_normalize_inline_citation_markdown_preserves_non_citation_numeric_text(
        self,
    ) -> None:
        text = "Zhu et al. (2016) measured stations (9) using Eq. 8 from 1901–2020."

        self.assertEqual(normalize_inline_citation_markdown(text), text)

    def test_normalize_inline_citation_markdown_moves_sup_trailing_space_outside_tag(
        self,
    ) -> None:
        normalized = normalize_inline_citation_markdown(
            "Losses reached (10<sup>15 </sup>g)."
        )

        self.assertEqual(normalized, "Losses reached (10<sup>15</sup> g).")

    def test_normalize_inline_citation_markdown_preserves_isotope_superscript_spacing(
        self,
    ) -> None:
        self.assertEqual(
            normalize_inline_citation_markdown("gas of <sup>6</sup>Li atoms"),
            "gas of <sup>6</sup>Li atoms",
        )
        self.assertEqual(
            normalize_inline_citation_markdown("states of <sup>6</sup>Li"),
            "states of <sup>6</sup>Li",
        )

    def test_normalize_inline_citation_markdown_tightens_only_high_confidence_sup_sub_spacing(
        self,
    ) -> None:
        sentinel = make_numeric_citation_sentinel("17")

        self.assertEqual(
            normalize_inline_citation_markdown(f"Example {sentinel}"),
            "Example<sup>17</sup>",
        )
        self.assertEqual(
            normalize_inline_citation_markdown("[ <sup>17</sup>]"), "[<sup>17</sup>]"
        )
        self.assertEqual(
            normalize_inline_citation_markdown("m <sup>-2</sup>"), "m<sup>-2</sup>"
        )
        self.assertEqual(
            normalize_inline_citation_markdown("km <sup>2</sup>"), "km<sup>2</sup>"
        )
        self.assertEqual(
            normalize_inline_citation_markdown("CO <sub>2</sub>"), "CO<sub>2</sub>"
        )
        self.assertEqual(
            normalize_inline_citation_markdown("H <sub>2</sub>O"), "H<sub>2</sub>O"
        )
        self.assertEqual(
            normalize_inline_citation_markdown("kg <sup>-1</sup>"), "kg<sup>-1</sup>"
        )
        self.assertEqual(
            normalize_inline_citation_markdown("AB <sub>3</sub>"), "AB<sub>3</sub>"
        )
        self.assertEqual(
            normalize_inline_citation_markdown("x <sup>2</sup>"), "x<sup>2</sup>"
        )
        self.assertEqual(
            normalize_inline_citation_markdown("*h* <sub>0</sub>"), "*h*<sub>0</sub>"
        )
        self.assertEqual(
            normalize_inline_citation_markdown("number of <sup>6</sup>Li"),
            "number of <sup>6</sup>Li",
        )
        self.assertEqual(
            normalize_inline_citation_markdown("state of <sub>2</sub>"),
            "state of <sub>2</sub>",
        )

    def test_normalize_inline_citation_markdown_handles_legacy_science_italics(
        self,
    ) -> None:
        normalized = normalize_inline_citation_markdown(
            "The event is documented (*46, 55*, *56*)."
        )

        self.assertEqual(normalized, "The event is documented<sup>46, 55, 56</sup>.")

    def test_normalize_inline_citation_markdown_preserves_markdown_image_boundaries(
        self,
    ) -> None:
        normalized = normalize_inline_citation_markdown(
            "sentence.\n\n![Listing 1.](x)\n\ncaption"
        )

        self.assertEqual(normalized, "sentence.\n\n![Listing 1.](x)\n\ncaption")

    def test_normalize_inline_citation_markdown_still_trims_plain_exclamation_spacing(
        self,
    ) -> None:
        normalized = normalize_inline_citation_markdown("word !")

        self.assertEqual(normalized, "word!")


if __name__ == "__main__":
    unittest.main()
