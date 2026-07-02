from __future__ import annotations

import unittest

from paper_fetch.extraction.html.section_scan import SectionScanState


class SectionScanStateTests(unittest.TestCase):
    def test_transition_enters_exclusive_sections(self) -> None:
        cases = [
            ("abstract", True, "in_abstract"),
            ("references_or_back_matter", True, "in_back_matter"),
            ("data_availability", True, "in_data_availability"),
            ("code_availability", True, "in_data_availability"),
            ("front_matter", True, "in_front_matter"),
        ]

        for category, is_heading, active_field in cases:
            with self.subTest(category=category):
                state = SectionScanState(
                    in_abstract=True,
                    in_back_matter=True,
                    in_front_matter=True,
                    in_data_availability=True,
                    in_auxiliary=True,
                )

                state.transition(category, is_heading=is_heading)

                self.assertEqual(state.in_abstract, active_field == "in_abstract")
                self.assertEqual(state.in_back_matter, active_field == "in_back_matter")
                self.assertEqual(
                    state.in_front_matter, active_field == "in_front_matter"
                )
                self.assertEqual(
                    state.in_data_availability,
                    active_field == "in_data_availability",
                )
                self.assertFalse(state.in_auxiliary)

    def test_abstract_transition_marks_abstract_seen(self) -> None:
        state = SectionScanState()

        state.transition("abstract", is_heading=True)

        self.assertTrue(state.in_abstract)
        self.assertTrue(state.abstract_seen)

    def test_front_matter_non_heading_clears_without_entering_front_matter(
        self,
    ) -> None:
        state = SectionScanState(in_abstract=True, in_front_matter=True)

        state.transition("front_matter", is_heading=False)

        self.assertFalse(state.in_skipped_section())

    def test_ancillary_without_auxiliary_only_clears_front_and_data_states(
        self,
    ) -> None:
        state = SectionScanState(
            in_abstract=True,
            in_back_matter=True,
            in_front_matter=True,
            in_data_availability=True,
        )

        state.transition("ancillary", is_heading=True)

        self.assertTrue(state.in_abstract)
        self.assertTrue(state.in_back_matter)
        self.assertFalse(state.in_front_matter)
        self.assertFalse(state.in_data_availability)
        self.assertFalse(state.in_auxiliary)

    def test_auxiliary_enabled_enters_auxiliary_and_clears_other_sections(self) -> None:
        state = SectionScanState(
            in_abstract=True,
            in_back_matter=True,
            enabled_states=frozenset(
                {
                    "body",
                    "abstract",
                    "back_matter",
                    "front_matter",
                    "data_availability",
                    "auxiliary",
                }
            ),
        )

        state.transition("auxiliary", is_heading=True)

        self.assertFalse(state.in_abstract)
        self.assertFalse(state.in_back_matter)
        self.assertTrue(state.in_auxiliary)
        self.assertTrue(state.in_skipped_section())

    def test_body_heading_clears_sections_and_records_post_abstract_heading(
        self,
    ) -> None:
        state = SectionScanState(in_abstract=True)
        state.abstract_seen = True

        state.transition("body_heading", is_heading=True)

        self.assertFalse(state.in_skipped_section())
        self.assertTrue(state.body_heading_after_abstract)

    def test_unknown_transition_leaves_state_unchanged(self) -> None:
        state = SectionScanState(in_abstract=True)

        state.transition("unknown", is_heading=False)

        self.assertTrue(state.in_abstract)
        self.assertFalse(state.body_heading_after_abstract)

    def test_body_run_records_max_run_and_total_paragraph_count(self) -> None:
        state = SectionScanState()

        state.record_body_paragraph(text_len=100)
        state.record_body_paragraph(text_len=50)
        state.reset_body_run()
        state.record_body_paragraph(text_len=10)

        self.assertEqual(state.body_paragraph_count, 3)
        self.assertEqual(state.body_run_paragraph_count, 2)
        self.assertEqual(state.body_run_char_count, 150)


if __name__ == "__main__":
    unittest.main()
