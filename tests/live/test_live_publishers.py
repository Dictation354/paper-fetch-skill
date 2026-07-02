from __future__ import annotations

import os
import tempfile
import unittest

from paper_fetch.http import HttpTransport
from paper_fetch.runtime import RuntimeContext
from paper_fetch.service import FetchStrategy, fetch_paper
from tests.live._runtime_env import (
    build_isolated_live_env,
    require_cloakbrowser_or_skip,
)
from tests.provider_benchmark_samples import (
    provider_benchmark_sample,
    source_trail_matches,
)


RUN_LIVE = os.environ.get("PAPER_FETCH_RUN_LIVE") == "1"
ELSEVIER_SAMPLE = provider_benchmark_sample("elsevier")
SPRINGER_SAMPLE = provider_benchmark_sample("springer")
WILEY_SAMPLE = provider_benchmark_sample("wiley")
SCIENCE_SAMPLE = provider_benchmark_sample("science")
PNAS_SAMPLE = provider_benchmark_sample("pnas")
IEEE_SAMPLE = provider_benchmark_sample("ieee")
ARXIV_SAMPLE = provider_benchmark_sample("arxiv")
AMS_SAMPLE = provider_benchmark_sample("ams")
COPERNICUS_SAMPLE = provider_benchmark_sample("copernicus")


def fetch_article(query: str, *, transport: HttpTransport, env: dict[str, str]):
    context = RuntimeContext(env=env, transport=transport, download_dir=None)
    try:
        envelope = fetch_paper(
            query,
            modes={"article"},
            strategy=FetchStrategy(
                allow_metadata_only_fallback=True,
            ),
            context=context,
        )
    finally:
        context.close()
    assert envelope.article is not None
    return envelope.article


class LivePublisherTests(unittest.TestCase):
    runtime_env_tempdir: tempfile.TemporaryDirectory | None = None

    @classmethod
    def setUpClass(cls) -> None:
        if not RUN_LIVE:
            raise unittest.SkipTest(
                "Set PAPER_FETCH_RUN_LIVE=1 to run live publisher smoke tests."
            )
        cls.env, cls.runtime_env_tempdir = build_isolated_live_env()

    @classmethod
    def tearDownClass(cls) -> None:
        runtime_env_tempdir = getattr(cls, "runtime_env_tempdir", None)
        if runtime_env_tempdir is not None:
            runtime_env_tempdir.cleanup()

    def _require_env(self, *keys: str) -> None:
        missing = [key for key in keys if not self.env.get(key, "").strip()]
        if missing:
            self.skipTest(
                f"Missing required environment variables for live test: {', '.join(missing)}"
            )

    def _assert_matches_sample(self, article, sample) -> None:
        self.assertEqual(article.source, sample.expected_source)
        self.assertTrue(article.quality.has_fulltext)
        self.assertGreater(len(article.sections), 0)
        self.assertTrue(
            source_trail_matches(
                article.quality.source_trail, sample.accepted_live_source_trail_groups
            ),
            article.quality.source_trail,
        )

    def test_elsevier_doi_live_fulltext(self) -> None:
        self._require_env(*ELSEVIER_SAMPLE.required_env)
        article = fetch_article(
            ELSEVIER_SAMPLE.doi,
            transport=HttpTransport(),
            env=self.env,
        )

        self._assert_matches_sample(article, ELSEVIER_SAMPLE)

    def test_springer_doi_live_fulltext(self) -> None:
        self._require_env(*SPRINGER_SAMPLE.required_env)
        article = fetch_article(
            SPRINGER_SAMPLE.doi,
            transport=HttpTransport(),
            env=self.env,
        )

        self._assert_matches_sample(article, SPRINGER_SAMPLE)

    def test_wiley_doi_live_fulltext(self) -> None:
        self._require_env(*WILEY_SAMPLE.required_env)
        require_cloakbrowser_or_skip(self)
        article = fetch_article(
            WILEY_SAMPLE.doi,
            transport=HttpTransport(),
            env=self.env,
        )

        self._assert_matches_sample(article, WILEY_SAMPLE)

    def test_science_doi_live_fulltext(self) -> None:
        self._require_env(*SCIENCE_SAMPLE.required_env)
        require_cloakbrowser_or_skip(self)
        article = fetch_article(
            SCIENCE_SAMPLE.doi,
            transport=HttpTransport(),
            env=self.env,
        )

        self._assert_matches_sample(article, SCIENCE_SAMPLE)

    def test_pnas_doi_live_fulltext(self) -> None:
        self._require_env(*PNAS_SAMPLE.required_env)
        require_cloakbrowser_or_skip(self)
        article = fetch_article(
            PNAS_SAMPLE.doi,
            transport=HttpTransport(),
            env=self.env,
        )

        self._assert_matches_sample(article, PNAS_SAMPLE)

    def test_ieee_doi_live_fulltext(self) -> None:
        require_cloakbrowser_or_skip(self)
        self._require_env(*IEEE_SAMPLE.required_env)
        article = fetch_article(
            IEEE_SAMPLE.doi,
            transport=HttpTransport(),
            env=self.env,
        )

        self._assert_matches_sample(article, IEEE_SAMPLE)

    def test_arxiv_doi_live_fulltext(self) -> None:
        self._require_env(*ARXIV_SAMPLE.required_env)
        article = fetch_article(
            ARXIV_SAMPLE.doi,
            transport=HttpTransport(),
            env=self.env,
        )

        self._assert_matches_sample(article, ARXIV_SAMPLE)

    def test_ams_doi_live_fulltext(self) -> None:
        self._require_env(*AMS_SAMPLE.required_env)
        require_cloakbrowser_or_skip(self)
        article = fetch_article(
            AMS_SAMPLE.doi,
            transport=HttpTransport(),
            env=self.env,
        )

        self._assert_matches_sample(article, AMS_SAMPLE)

    def test_copernicus_doi_live_fulltext(self) -> None:
        self._require_env(*COPERNICUS_SAMPLE.required_env)
        article = fetch_article(
            COPERNICUS_SAMPLE.doi,
            transport=HttpTransport(),
            env=self.env,
        )

        self._assert_matches_sample(article, COPERNICUS_SAMPLE)

    def test_elsevier_url_live_recovers_doi_and_uses_official_fulltext(self) -> None:
        self._require_env(*ELSEVIER_SAMPLE.required_env)
        article = fetch_article(
            ELSEVIER_SAMPLE.resolve_url,
            transport=HttpTransport(),
            env=self.env,
        )

        self.assertEqual(article.doi, ELSEVIER_SAMPLE.doi)
        self._assert_matches_sample(article, ELSEVIER_SAMPLE)
        self.assertIn("resolve:url", article.quality.source_trail)
        self.assertNotIn("fallback:metadata_only", article.quality.source_trail)

    def test_elsevier_old_doi_live_uses_official_pdf_fallback(self) -> None:
        self._require_env(*ELSEVIER_SAMPLE.required_env)
        article = fetch_article(
            "10.1016/0304-4165(96)00054-2",
            transport=HttpTransport(),
            env=self.env,
        )

        self.assertEqual(article.source, "elsevier_pdf")
        self.assertTrue(article.quality.has_fulltext)
        self.assertIn("fulltext:elsevier_xml_fail", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_pdf_api_ok", article.quality.source_trail)
        self.assertIn("fulltext:elsevier_pdf_fallback_ok", article.quality.source_trail)
        self.assertNotIn("fulltext:elsevier_html_ok", article.quality.source_trail)
        self.assertNotIn("fulltext:elsevier_html_fail", article.quality.source_trail)


if __name__ == "__main__":
    unittest.main()
