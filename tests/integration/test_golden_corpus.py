from __future__ import annotations

from collections import Counter
import os
import unittest

from tests.golden_corpus import (
    build_article_from_fixture,
    expected_summary_from_article,
    iter_golden_corpus_fixtures,
    iter_golden_corpus_representative_fixtures,
    lightweight_positive_summary_from_fixture,
)


FULL_GOLDEN_ENV = "PAPER_FETCH_RUN_FULL_GOLDEN"
EXPECTED_PROVIDER_ROUTE_KINDS = {
    "elsevier": "official",
    "springer": "html",
    "science": "html",
    "wiley": "html",
    "pnas": "html",
}
EXPECTED_PROVIDER_CONTENT_PREFIXES = {
    "elsevier": "text/xml",
    "springer": "text/html",
    "science": "text/html",
    "wiley": "text/html",
    "pnas": "text/html",
}
EXPECTED_PROVIDER_SOURCES = {
    "elsevier": "elsevier_xml",
    "springer": "springer_html",
    "science": "science",
    "wiley": "wiley_browser",
    "pnas": "pnas",
}
EXPECTED_PROVIDER_PRIMARY_MARKERS = {
    "elsevier": "fulltext:elsevier_xml_ok",
    "springer": "fulltext:springer_html_ok",
    "science": "fulltext:science_html_ok",
    "wiley": "fulltext:wiley_html_ok",
    "pnas": "fulltext:pnas_html_ok",
}


class GoldenCorpusTests(unittest.TestCase):
    def test_golden_corpus_is_balanced_across_publishers(self) -> None:
        fixtures = iter_golden_corpus_fixtures()

        self.assertEqual(len(fixtures), 51)
        self.assertEqual(
            Counter(fixture.provider for fixture in fixtures),
            Counter({"elsevier": 10, "pnas": 10, "science": 10, "springer": 11, "wiley": 10}),
        )

    def test_golden_corpus_lightweight_contracts_hold_across_full_corpus(self) -> None:
        for fixture in iter_golden_corpus_fixtures():
            with self.subTest(provider=fixture.provider, doi=fixture.doi):
                expected = fixture.load_expected()
                actual = lightweight_positive_summary_from_fixture(fixture)

                self.assertEqual(fixture.route_kind, EXPECTED_PROVIDER_ROUTE_KINDS[fixture.provider])
                self.assertTrue(fixture.content_type.startswith(EXPECTED_PROVIDER_CONTENT_PREFIXES[fixture.provider]))
                self.assertTrue(fixture.source_url)
                self.assertEqual(actual["doi"], fixture.doi)

                for field_name in actual["validated_fields"]:
                    if expected["has"][field_name]:
                        self.assertTrue(actual["has"][field_name], msg=f"Expected {field_name} for {fixture.doi}")

                if fixture.provider in {"science", "pnas", "wiley"}:
                    self.assertEqual(
                        list(actual["blocking_fallback_signals"]),
                        [],
                        msg=f"Positive fixture leaked paywall signals for {fixture.doi}",
                    )
                    self.assertTrue(
                        actual["source_candidate_hit"],
                        msg=f"Expected generated HTML candidates to include source URL for {fixture.doi}",
                    )

    def test_golden_corpus_representative_fixtures_cover_primary_fulltext_paths(self) -> None:
        fixtures = iter_golden_corpus_representative_fixtures()

        self.assertEqual(len(fixtures), 5)
        self.assertEqual(
            Counter(fixture.provider for fixture in fixtures),
            Counter({"elsevier": 1, "pnas": 1, "science": 1, "springer": 1, "wiley": 1}),
        )

        for fixture in fixtures:
            with self.subTest(provider=fixture.provider, doi=fixture.doi):
                article = build_article_from_fixture(fixture)
                actual = expected_summary_from_article(article)
                expected = fixture.load_expected()

                self.assertEqual(article.source, EXPECTED_PROVIDER_SOURCES[fixture.provider])
                self.assertIn(EXPECTED_PROVIDER_PRIMARY_MARKERS[fixture.provider], article.quality.source_trail)
                self.assertEqual(article.quality.content_kind, "fulltext")
                self.assertEqual(actual["expected_content_kind"], "fulltext")
                self.assertEqual(expected["expected_content_kind"], "fulltext")

                for field_name, expected_present in expected["has"].items():
                    if expected_present:
                        self.assertTrue(actual["has"][field_name], msg=f"Expected {field_name} for {fixture.doi}")

                for count_name, expected_count in expected["counts"].items():
                    if expected_count > 0:
                        self.assertGreater(
                            actual["counts"][count_name],
                            0,
                            msg=f"Expected positive {count_name} count for {fixture.doi}",
                        )

    @unittest.skipUnless(
        os.environ.get(FULL_GOLDEN_ENV) == "1",
        f"Set {FULL_GOLDEN_ENV}=1 to run full 51-fixture golden corpus regression.",
    )
    def test_golden_corpus_expected_summaries_match_current_extractors(self) -> None:
        for fixture in iter_golden_corpus_fixtures():
            with self.subTest(provider=fixture.provider, doi=fixture.doi):
                article = build_article_from_fixture(fixture)
                actual = expected_summary_from_article(article)
                expected = fixture.load_expected()

                self.assertEqual(actual["expected_content_kind"], "fulltext")
                self.assertEqual(expected["expected_content_kind"], "fulltext")
                self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
