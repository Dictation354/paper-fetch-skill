from __future__ import annotations

import unittest

from paper_fetch.extraction.html.signals import (
    ACCESS_GATE_LABELS,
    ACCESS_GATE_PATTERNS,
    ASSET_ACCESS_BLOCK_LABELS,
    MARKDOWN_ACCESS_NOISE_LABELS,
    detect_html_access_signals,
    detect_html_block,
    html_failure_message,
    matched_access_gate_patterns,
    summarize_html,
)
from paper_fetch.quality.html_signals import (
    AAAS_DATALAYER_PATTERN,
    DATALAYER_SCHEMAS,
    WILEY_SIGNAL_SET,
    authorless_heading_signatures_for_provider,
    evaluate_datalayer_blocking_signals,
    load_provider_datalayer,
)
from paper_fetch.providers import _science_html


class HtmlAccessSignalsTests(unittest.TestCase):
    def test_detect_html_access_signals_reports_challenge_not_found_and_paywall(
        self,
    ) -> None:
        signals = detect_html_access_signals(
            "Example title",
            "Just a moment. Check access before continuing because the article was not found.",
            404,
        )

        self.assertEqual(
            signals,
            ["cloudflare_challenge", "publisher_not_found", "publisher_paywall"],
        )

    def test_detect_html_access_signals_honors_redirect_and_explicit_access_denied(
        self,
    ) -> None:
        signals = detect_html_access_signals(
            "Example title",
            "Full text unavailable.",
            200,
            redirected_to_abstract=True,
            explicit_no_access=True,
        )

        self.assertEqual(signals, ["redirected_to_abstract", "publisher_access_denied"])

    def test_detect_html_access_signals_classifies_aws_waf_202_page_as_challenge(
        self,
    ) -> None:
        text = (
            "JavaScript is disabled. Please enable JavaScript to verify that "
            "you're not a robot and reload the page."
        )

        self.assertEqual(
            detect_html_access_signals("", text, 202),
            ["cloudflare_challenge"],
        )

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

    def test_access_gate_patterns_are_ordered_and_include_atypon_browser_workflow_phrases(
        self,
    ) -> None:
        self.assertIsInstance(ACCESS_GATE_PATTERNS, tuple)
        self.assertEqual(
            matched_access_gate_patterns(
                "Purchase digital access to this article. Sign in to access. "
                "View access options. Institutional login."
            ),
            [
                "purchase digital access to this article",
                "sign in to access",
                "view access options",
                "institutional login",
            ],
        )
        self.assertEqual(
            matched_access_gate_patterns(
                "Purchase access. Access through your institution. Sign in to access. "
                "View access options."
            ),
            [
                "purchase access",
                "access through your institution",
                "sign in to access",
                "view access options",
            ],
        )

    def test_access_provided_by_is_markdown_noise_not_access_gate(self) -> None:
        text = "Access provided by: Peking University"

        self.assertEqual(matched_access_gate_patterns(text), [])
        self.assertIsNone(detect_html_block("Example article", text, 200))
        self.assertIn("access provided by", ACCESS_GATE_LABELS)
        self.assertIn("access provided by", MARKDOWN_ACCESS_NOISE_LABELS)
        self.assertNotIn("access provided by", ACCESS_GATE_PATTERNS)

    def test_access_gate_labels_feed_markdown_noise_and_asset_blocking_vocabularies(
        self,
    ) -> None:
        self.assertIn("access provided by", ACCESS_GATE_LABELS)
        self.assertIn("access provided by", MARKDOWN_ACCESS_NOISE_LABELS)
        self.assertIn("view access options", MARKDOWN_ACCESS_NOISE_LABELS)
        self.assertIn("access denied", ASSET_ACCESS_BLOCK_LABELS)

    def test_summarize_html_extracts_readable_text(self) -> None:
        summary = summarize_html(
            "<html><body><article><h1>Example</h1><p>Body text.</p></article></body></html>"
        )

        self.assertEqual(summary, "Example Body text.")

    def test_provider_datalayer_schema_normalizes_wiley_alias_fields(self) -> None:
        html = """
        <html><script>
        window.adobeDataLayer.push({
          "content": {"item": {"access": "no", "format_viewed": "abstract"}},
          "page": {"tertiary_section": "abs"}
        });
        </script></html>
        """

        datalayer = load_provider_datalayer(html, DATALAYER_SCHEMAS["wiley"])

        self.assertIsNotNone(datalayer)
        assert datalayer is not None
        self.assertEqual(datalayer.lowered("format_viewed"), "abstract")
        self.assertEqual(
            evaluate_datalayer_blocking_signals(html, WILEY_SIGNAL_SET),
            [
                "wiley_access_no",
                "wiley_format_viewed_abstract",
                "wiley_page_tertiary_abs",
            ],
        )

    def test_provider_datalayer_schema_decodes_balanced_assignment_payload(
        self,
    ) -> None:
        html = """
        <html><script>
        AAASdataLayer = {
          "page": {"pageInfo": {"pageType": "journal-article-full-text", "viewType": "full"}},
          "user": {"entitled": "true", "access": "yes"}
        };
        dataLayer.push({"event": "article", "authors": ["Ada Lovelace"]});
        </script></html>
        """

        datalayer = load_provider_datalayer(html, DATALAYER_SCHEMAS["science"])

        self.assertIsNotNone(datalayer)
        assert datalayer is not None
        self.assertEqual(datalayer.lowered("page_type"), "journal-article-full-text")
        self.assertEqual(datalayer.lowered("view_type"), "full")

    def test_science_provider_reuses_quality_datalayer_pattern(self) -> None:
        self.assertIs(_science_html.AAAS_DATALAYER_PATTERN, AAAS_DATALAYER_PATTERN)

    def test_authorless_quality_signatures_are_provider_owned(self) -> None:
        springer_signatures = authorless_heading_signatures_for_provider("springer")
        wiley_signatures = authorless_heading_signatures_for_provider("wiley")

        self.assertTrue(springer_signatures)
        self.assertIn("the question", springer_signatures[0])
        self.assertEqual(wiley_signatures, ())


if __name__ == "__main__":
    unittest.main()
