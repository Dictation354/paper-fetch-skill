from __future__ import annotations

import unittest

from paper_fetch.providers._science_pnas_html import (
    SciencePnasHtmlFailure,
    build_html_candidates,
    build_pdf_candidates,
    extract_science_pnas_markdown,
    preferred_html_candidate_from_landing_page,
)
from tests.paths import FIXTURE_DIR


class SciencePnasHtmlTests(unittest.TestCase):
    def test_science_fixture_extracts_fulltext_markdown(self) -> None:
        html = (FIXTURE_DIR / "science_10.1126_science.ady3136.html").read_text(encoding="utf-8")

        markdown, info = extract_science_pnas_markdown(
            html,
            "https://www.science.org/doi/full/10.1126/science.ady3136",
            "science",
            metadata={"doi": "10.1126/science.ady3136"},
        )

        self.assertEqual(info["container_tag"], "main")
        self.assertIn("# Hyaluronic acid and tissue mechanics orchestrate mammalian digit tip regeneration", markdown)
        self.assertIn("Structured Abstract", markdown)
        self.assertIn("Discussion", markdown)
        self.assertIn("Materials and methods", markdown)

    def test_pnas_abstract_fixture_is_rejected(self) -> None:
        html = (FIXTURE_DIR / "pnas_10.1073_pnas.81.23.7500.abstract.html").read_text(encoding="utf-8")

        with self.assertRaises(SciencePnasHtmlFailure) as ctx:
            extract_science_pnas_markdown(
                html,
                "https://www.pnas.org/doi/full/10.1073/pnas.81.23.7500",
                "pnas",
                metadata={"doi": "10.1073/pnas.81.23.7500"},
            )

        self.assertEqual(ctx.exception.reason, "insufficient_paragraphs")

    def test_candidate_builders_match_expected_priority(self) -> None:
        self.assertEqual(
            build_html_candidates("science", "10.1126/science.ady3136")[:2],
            [
                "https://www.science.org/doi/full/10.1126/science.ady3136",
                "https://www.science.org/doi/10.1126/science.ady3136",
            ],
        )
        self.assertEqual(
            build_pdf_candidates("pnas", "10.1073/pnas.81.23.7500", None)[:2],
            [
                "https://www.pnas.org/doi/pdf/10.1073/pnas.81.23.7500?download=true",
                "https://www.pnas.org/doi/pdf/10.1073/pnas.81.23.7500",
            ],
        )

    def test_html_candidates_prioritize_matching_landing_page_url(self) -> None:
        candidates = build_html_candidates(
            "science",
            "10.1126/science.ady3136",
            landing_page_url="https://science.org/doi/10.1126/science.ady3136",
        )

        self.assertEqual(candidates[0], "https://science.org/doi/10.1126/science.ady3136")
        self.assertEqual(
            preferred_html_candidate_from_landing_page(
                "science",
                "10.1126/science.ady3136",
                "https://science.org/doi/10.1126/science.ady3136",
            ),
            "https://science.org/doi/10.1126/science.ady3136",
        )
        self.assertEqual(
            candidates[1:3],
            [
                "https://www.science.org/doi/full/10.1126/science.ady3136",
                "https://www.science.org/doi/10.1126/science.ady3136",
            ],
        )

    def test_html_candidates_ignore_non_matching_landing_page_url(self) -> None:
        candidates = build_html_candidates(
            "pnas",
            "10.1073/pnas.81.23.7500",
            landing_page_url="https://example.com/doi/10.1073/pnas.81.23.7500",
        )

        self.assertIsNone(
            preferred_html_candidate_from_landing_page(
                "pnas",
                "10.1073/pnas.81.23.7500",
                "https://example.com/doi/10.1073/pnas.81.23.7500",
            )
        )
        self.assertEqual(
            candidates[:2],
            [
                "https://www.pnas.org/doi/10.1073/pnas.81.23.7500",
                "https://www.pnas.org/doi/full/10.1073/pnas.81.23.7500",
            ],
        )


if __name__ == "__main__":
    unittest.main()
