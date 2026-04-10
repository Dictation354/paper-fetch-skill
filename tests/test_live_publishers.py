from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from fetch_common import HttpTransport, build_runtime_env
from paper_fetch import fetch_paper_model


RUN_LIVE = os.environ.get("PAPER_FETCH_RUN_LIVE") == "1"


class LivePublisherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not RUN_LIVE:
            raise unittest.SkipTest("Set PAPER_FETCH_RUN_LIVE=1 to run live publisher smoke tests.")
        cls.env = build_runtime_env()

    def _require_env(self, *keys: str) -> None:
        missing = [key for key in keys if not self.env.get(key, "").strip()]
        if missing:
            self.skipTest(f"Missing required environment variables for live test: {', '.join(missing)}")

    def test_elsevier_doi_live_fulltext(self) -> None:
        self._require_env("ELSEVIER_API_KEY", "CROSSREF_MAILTO")
        article = fetch_paper_model(
            "10.1016/j.rse.2025.114648",
            allow_html_fallback=False,
            allow_downloads=False,
            transport=HttpTransport(),
            env=self.env,
        )

        self.assertEqual(article.source, "elsevier_xml")
        self.assertTrue(article.quality.has_fulltext)
        self.assertGreater(len(article.sections), 0)

    def test_springer_doi_live_fulltext(self) -> None:
        self._require_env("SPRINGER_META_API_KEY", "SPRINGER_OPENACCESS_API_KEY", "CROSSREF_MAILTO")
        article = fetch_paper_model(
            "10.1186/1471-2105-11-421",
            allow_html_fallback=False,
            allow_downloads=False,
            transport=HttpTransport(),
            env=self.env,
        )

        self.assertEqual(article.source, "springer_xml")
        self.assertTrue(article.quality.has_fulltext)
        self.assertGreater(len(article.sections), 0)

    def test_wiley_doi_live_fulltext(self) -> None:
        self._require_env("WILEY_TDM_URL_TEMPLATE", "WILEY_TDM_TOKEN", "CROSSREF_MAILTO")
        article = fetch_paper_model(
            "10.1002/ece3.9361",
            allow_html_fallback=False,
            allow_downloads=False,
            transport=HttpTransport(),
            env=self.env,
        )

        self.assertEqual(article.source, "wiley")
        self.assertTrue(article.quality.has_fulltext)
        self.assertGreater(len(article.sections), 0)
        self.assertTrue(any("extracted from PDF" in warning for warning in article.quality.warnings))

    def test_elsevier_url_live_recovers_doi_and_uses_official_fulltext(self) -> None:
        self._require_env("ELSEVIER_API_KEY", "CROSSREF_MAILTO")
        article = fetch_paper_model(
            "https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525",
            allow_html_fallback=False,
            allow_downloads=False,
            transport=HttpTransport(),
            env=self.env,
        )

        self.assertEqual(article.doi, "10.1016/j.rse.2025.114648")
        self.assertEqual(article.source, "elsevier_xml")
        self.assertTrue(article.quality.has_fulltext)
        self.assertGreater(len(article.sections), 0)
        self.assertIn("resolve:url", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_article_ok", article.quality.source_trail)
        self.assertNotIn("fallback:metadata_only", article.quality.source_trail)

    def test_short_html_body_live_falls_back_to_html_generic(self) -> None:
        self._require_env("SPRINGER_META_API_KEY", "SPRINGER_OPENACCESS_API_KEY", "CROSSREF_MAILTO")
        article = fetch_paper_model(
            "https://www.nature.com/articles/sj.bdj.2017.900",
            allow_downloads=False,
            transport=HttpTransport(),
            env=self.env,
        )

        self.assertEqual(article.doi, "10.1038/sj.bdj.2017.900")
        self.assertEqual(article.source, "html_generic")
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("fallback:html_ok", article.quality.source_trail)
        self.assertNotIn("fallback:metadata_only", article.quality.source_trail)


if __name__ == "__main__":
    unittest.main()
