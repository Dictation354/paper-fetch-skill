from __future__ import annotations

import unittest

from paper_fetch.providers._html_access_signals import (
    detect_html_access_signals,
    detect_html_block,
    html_failure_message,
    summarize_html,
)


class HtmlAccessSignalsTests(unittest.TestCase):
    def test_detect_html_access_signals_reports_challenge_not_found_and_paywall(self) -> None:
        signals = detect_html_access_signals(
            "Example title",
            "Just a moment. Check access before continuing because the article was not found.",
            404,
        )

        self.assertEqual(
            signals,
            ["cloudflare_challenge", "publisher_not_found", "publisher_paywall"],
        )

    def test_detect_html_access_signals_honors_redirect_and_explicit_access_denied(self) -> None:
        signals = detect_html_access_signals(
            "Example title",
            "Full text unavailable.",
            200,
            redirected_to_abstract=True,
            explicit_no_access=True,
        )

        self.assertEqual(signals, ["redirected_to_abstract", "publisher_access_denied"])

    def test_detect_html_block_treats_check_access_as_paywall(self) -> None:
        failure = detect_html_block(
            "Example article",
            "Check access to the full text before continuing.",
            200,
        )

        self.assertIsNotNone(failure)
        assert failure is not None
        self.assertEqual(failure.reason, "publisher_paywall")
        self.assertEqual(failure.message, html_failure_message("publisher_paywall"))

    def test_summarize_html_extracts_readable_text(self) -> None:
        summary = summarize_html("<html><body><article><h1>Example</h1><p>Body text.</p></article></body></html>")

        self.assertEqual(summary, "Example Body text.")


if __name__ == "__main__":
    unittest.main()
