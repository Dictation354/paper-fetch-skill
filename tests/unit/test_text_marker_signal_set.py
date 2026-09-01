from __future__ import annotations

import unittest

from paper_fetch.quality.html_signals import (
    TextMarkerRule,
    TextMarkerSignalSet,
    evaluate_text_marker_blocking_signals,
    evaluate_text_marker_positive_signals,
)


class TextMarkerSignalSetTests(unittest.TestCase):
    def test_blocking_rule_triggers_from_substring(self) -> None:
        signal_set = TextMarkerSignalSet(
            blocking_rules=(TextMarkerRule("purchase access", "purchase_wall"),)
        )

        self.assertEqual(
            evaluate_text_marker_blocking_signals(
                "<html>Purchase access to continue.</html>",
                signal_set,
            ),
            ["purchase_wall"],
        )

    def test_negated_rule_triggers_when_substring_is_absent(self) -> None:
        signal_set = TextMarkerSignalSet(
            soft_rules=(TextMarkerRule("abstract only", "not_abstract", negate=True),)
        )

        _strong, soft, _abstract_only = evaluate_text_marker_positive_signals(
            "<article>Full article body.</article>",
            signal_set,
        )

        self.assertIn("not_abstract", soft)

    def test_contains_context_must_also_match(self) -> None:
        signal_set = TextMarkerSignalSet(
            blocking_rules=(
                TextMarkerRule(
                    "access",
                    "institutional_access_wall",
                    contains=("institutional", "sign in"),
                ),
            )
        )

        self.assertEqual(
            evaluate_text_marker_blocking_signals(
                "Institutional sign in is required for access.",
                signal_set,
            ),
            ["institutional_access_wall"],
        )
        self.assertEqual(
            evaluate_text_marker_blocking_signals("Open access article.", signal_set),
            [],
        )

    def test_access_gate_context_requires_registered_gate_phrase(self) -> None:
        signal_set = TextMarkerSignalSet(
            blocking_rules=(
                TextMarkerRule(
                    "check access",
                    "registered_gate",
                    access_gate_context=True,
                ),
                TextMarkerRule(
                    "made up gate",
                    "unregistered_gate",
                    access_gate_context=True,
                ),
            )
        )

        self.assertEqual(
            evaluate_text_marker_blocking_signals(
                "Check access before continuing. Made up gate.",
                signal_set,
            ),
            ["registered_gate"],
        )


if __name__ == "__main__":
    unittest.main()
