from __future__ import annotations

import unittest

from paper_fetch.providers._science_pnas_html import (
    SciencePnasHtmlFailure,
    build_html_candidates,
    build_pdf_candidates,
    extract_pdf_url_from_crossref,
    extract_science_pnas_markdown,
    preferred_html_candidate_from_landing_page,
)
from tests.provider_benchmark_samples import provider_benchmark_sample
from tests.paths import FIXTURE_DIR


SCIENCE_SAMPLE = provider_benchmark_sample("science")
WILEY_SAMPLE = provider_benchmark_sample("wiley")
PNAS_SAMPLE = provider_benchmark_sample("pnas")


class SciencePnasHtmlTests(unittest.TestCase):
    def test_science_fixture_extracts_fulltext_markdown(self) -> None:
        html = (FIXTURE_DIR / SCIENCE_SAMPLE.fixture_name).read_text(encoding="utf-8")

        markdown, info = extract_science_pnas_markdown(
            html,
            SCIENCE_SAMPLE.landing_url,
            "science",
            metadata={"doi": SCIENCE_SAMPLE.doi},
        )

        self.assertEqual(info["container_tag"], "main")
        self.assertIn("# Hyaluronic acid and tissue mechanics orchestrate mammalian digit tip regeneration", markdown)
        self.assertIn("Structured Abstract", markdown)
        self.assertIn("Discussion", markdown)
        self.assertIn("Materials and methods", markdown)

    def test_pnas_abstract_fixture_is_rejected(self) -> None:
        html = (FIXTURE_DIR / "pnas_10.1073_pnas.2406303121.abstract.html").read_text(encoding="utf-8")

        with self.assertRaises(SciencePnasHtmlFailure) as ctx:
            extract_science_pnas_markdown(
                html,
                PNAS_SAMPLE.landing_url,
                "pnas",
                metadata={"doi": PNAS_SAMPLE.doi},
            )

        self.assertEqual(ctx.exception.reason, "insufficient_paragraphs")

    def test_candidate_builders_match_expected_priority(self) -> None:
        self.assertEqual(
            build_html_candidates("science", SCIENCE_SAMPLE.doi)[:2],
            [
                f"https://www.science.org/doi/full/{SCIENCE_SAMPLE.doi}",
                f"https://www.science.org/doi/{SCIENCE_SAMPLE.doi}",
            ],
        )
        self.assertEqual(
            build_pdf_candidates("science", SCIENCE_SAMPLE.doi, None)[:3],
            [
                f"https://www.science.org/doi/epdf/{SCIENCE_SAMPLE.doi}",
                f"https://www.science.org/doi/pdf/{SCIENCE_SAMPLE.doi}",
                f"https://www.science.org/doi/pdf/{SCIENCE_SAMPLE.doi}?download=true",
            ],
        )
        self.assertEqual(
            build_pdf_candidates("pnas", PNAS_SAMPLE.doi, None)[:3],
            [
                f"https://www.pnas.org/doi/epdf/{PNAS_SAMPLE.doi}",
                f"https://www.pnas.org/doi/pdf/{PNAS_SAMPLE.doi}?download=true",
                f"https://www.pnas.org/doi/pdf/{PNAS_SAMPLE.doi}",
            ],
        )
        self.assertEqual(
            build_pdf_candidates("wiley", WILEY_SAMPLE.doi, None)[:4],
            [
                f"https://onlinelibrary.wiley.com/doi/epdf/{WILEY_SAMPLE.doi}",
                f"https://onlinelibrary.wiley.com/doi/pdf/{WILEY_SAMPLE.doi}",
                f"https://onlinelibrary.wiley.com/doi/pdfdirect/{WILEY_SAMPLE.doi}",
                f"https://onlinelibrary.wiley.com/wol1/doi/{WILEY_SAMPLE.doi}/fullpdf",
            ],
        )

    def test_extract_pdf_url_from_crossref_recognizes_wiley_fullpdf_links(self) -> None:
        crossref_pdf_url = extract_pdf_url_from_crossref(
            {
                "fulltext_links": [
                    {
                        "url": f"http://onlinelibrary.wiley.com/wol1/doi/{WILEY_SAMPLE.doi}/fullpdf",
                        "content_type": "unspecified",
                    }
                ]
            }
        )

        self.assertEqual(
            crossref_pdf_url,
            f"http://onlinelibrary.wiley.com/wol1/doi/{WILEY_SAMPLE.doi}/fullpdf",
        )
        self.assertEqual(
            build_pdf_candidates("wiley", WILEY_SAMPLE.doi, crossref_pdf_url)[:5],
            [
                f"https://onlinelibrary.wiley.com/doi/epdf/{WILEY_SAMPLE.doi}",
                f"http://onlinelibrary.wiley.com/wol1/doi/{WILEY_SAMPLE.doi}/fullpdf",
                f"https://onlinelibrary.wiley.com/doi/pdf/{WILEY_SAMPLE.doi}",
                f"https://onlinelibrary.wiley.com/doi/pdfdirect/{WILEY_SAMPLE.doi}",
                f"https://onlinelibrary.wiley.com/wol1/doi/{WILEY_SAMPLE.doi}/fullpdf",
            ],
        )

    def test_html_candidates_prioritize_matching_landing_page_url(self) -> None:
        candidates = build_html_candidates(
            "science",
            SCIENCE_SAMPLE.doi,
            landing_page_url=f"https://science.org/doi/{SCIENCE_SAMPLE.doi}",
        )

        self.assertEqual(candidates[0], f"https://science.org/doi/{SCIENCE_SAMPLE.doi}")
        self.assertEqual(
            preferred_html_candidate_from_landing_page(
                "science",
                SCIENCE_SAMPLE.doi,
                f"https://science.org/doi/{SCIENCE_SAMPLE.doi}",
            ),
            f"https://science.org/doi/{SCIENCE_SAMPLE.doi}",
        )
        self.assertEqual(
            candidates[1:3],
            [
                f"https://science.org/doi/full/{SCIENCE_SAMPLE.doi}",
                f"https://www.science.org/doi/full/{SCIENCE_SAMPLE.doi}",
            ],
        )

    def test_html_candidates_ignore_non_matching_landing_page_url(self) -> None:
        candidates = build_html_candidates(
            "pnas",
            PNAS_SAMPLE.doi,
            landing_page_url=f"https://example.com/doi/{PNAS_SAMPLE.doi}",
        )

        self.assertIsNone(
            preferred_html_candidate_from_landing_page(
                "pnas",
                PNAS_SAMPLE.doi,
                f"https://example.com/doi/{PNAS_SAMPLE.doi}",
            )
        )
        self.assertEqual(
            candidates[:2],
            [
                f"https://www.pnas.org/doi/{PNAS_SAMPLE.doi}",
                f"https://www.pnas.org/doi/full/{PNAS_SAMPLE.doi}",
            ],
        )


if __name__ == "__main__":
    unittest.main()
