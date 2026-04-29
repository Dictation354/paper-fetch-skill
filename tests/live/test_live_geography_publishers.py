from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from paper_fetch_devtools.geography.live import (
    GEOGRAPHY_PROVIDER_ORDER,
    GEOGRAPHY_RESULT_STATUSES,
    run_geography_live_report,
)
from tests.live.geography_samples import all_geography_samples


RUN_LIVE = os.environ.get("PAPER_FETCH_RUN_LIVE") == "1"


class LiveGeographyPublisherReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not RUN_LIVE:
            raise unittest.SkipTest("Set PAPER_FETCH_RUN_LIVE=1 to run geography live report tests.")
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.json_path = Path(cls.tempdir.name) / "geography-live-report.json"
        cls.markdown_path = Path(cls.tempdir.name) / "geography-live-report.md"
        cls.report = run_geography_live_report(all_geography_samples(), per_provider=10)
        cls.report.write_json(cls.json_path)
        cls.report.write_markdown(cls.markdown_path)
        cls.report_payload = json.loads(cls.json_path.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        tempdir = getattr(cls, "tempdir", None)
        if tempdir is not None:
            tempdir.cleanup()

    def test_report_attempts_ten_samples_per_provider(self) -> None:
        self.assertEqual(self.report.total_attempts, 50)
        counts = {
            provider: sum(1 for item in self.report.results if item.provider == provider)
            for provider in GEOGRAPHY_PROVIDER_ORDER
        }
        self.assertEqual(counts, {provider: 10 for provider in GEOGRAPHY_PROVIDER_ORDER})

    def test_report_results_use_known_statuses_and_required_fields(self) -> None:
        allowed_statuses = set(GEOGRAPHY_RESULT_STATUSES)
        for result in self.report.results:
            with self.subTest(doi=result.doi):
                self.assertIn(result.status, allowed_statuses)
                self.assertTrue(result.provider)
                self.assertTrue(result.doi)
                self.assertTrue(result.title)
                self.assertIsInstance(result.warnings, list)
                self.assertIsInstance(result.source_trail, list)
                self.assertIsInstance(result.issue_flags, list)
                self.assertGreaterEqual(result.elapsed_seconds, 0.0)

    def test_report_json_and_markdown_include_summaries(self) -> None:
        self.assertTrue(self.json_path.exists())
        self.assertTrue(self.markdown_path.exists())
        self.assertEqual(self.report_payload["total_attempts"], 50)
        self.assertEqual(len(self.report_payload["summary_by_provider"]), 5)
        self.assertGreaterEqual(len(self.report_payload["analysis_notes"]), 4)
        markdown = self.markdown_path.read_text(encoding="utf-8")
        self.assertIn("## Provider Summary", markdown)
        self.assertIn("## Issue Summary", markdown)
        self.assertIn("## Analysis Notes", markdown)

    def test_report_analysis_notes_cover_expected_problem_families(self) -> None:
        note_keys = {item.key for item in self.report.analysis_notes}
        self.assertIn("precheck_gap", note_keys)
        self.assertIn("pnas_abstract_quality", note_keys)
        self.assertIn("wiley_reference_doi_normalization", note_keys)
        self.assertIn("source_trail_stability", note_keys)


if __name__ == "__main__":
    unittest.main()
