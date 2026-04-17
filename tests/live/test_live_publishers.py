from __future__ import annotations

import os
import unittest
from pathlib import Path

from paper_fetch.config import build_runtime_env, resolve_flaresolverr_source_dir, resolve_flaresolverr_url
from paper_fetch.http import HttpTransport
from paper_fetch.providers._flaresolverr import health_check
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.service import FetchStrategy, fetch_paper
from tests.provider_benchmark_samples import provider_benchmark_sample, source_trail_matches


RUN_LIVE = os.environ.get("PAPER_FETCH_RUN_LIVE") == "1"
ELSEVIER_SAMPLE = provider_benchmark_sample("elsevier")
SPRINGER_SAMPLE = provider_benchmark_sample("springer")
WILEY_SAMPLE = provider_benchmark_sample("wiley")


def fetch_article(query: str, *, allow_html_fallback: bool, transport: HttpTransport, env: dict[str, str]):
    envelope = fetch_paper(
        query,
        modes={"article"},
        strategy=FetchStrategy(
            allow_html_fallback=allow_html_fallback,
            allow_metadata_only_fallback=True,
        ),
        download_dir=None,
        transport=transport,
        env=env,
    )
    assert envelope.article is not None
    return envelope.article


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

    def _require_flaresolverr(self) -> None:
        env_file = Path(self.env["FLARESOLVERR_ENV_FILE"]).expanduser()
        if not env_file.exists():
            self.skipTest(f"Configured FLARESOLVERR_ENV_FILE does not exist: {env_file}")
        source_dir = resolve_flaresolverr_source_dir(self.env)
        if not source_dir.exists():
            self.skipTest(f"Repo-local vendor/flaresolverr was not found: {source_dir}")
        try:
            health_check(resolve_flaresolverr_url(self.env))
        except ProviderFailure as exc:
            self.skipTest(f"Local FlareSolverr health check failed: {exc.message}")

    def _assert_matches_sample(self, article, sample) -> None:
        self.assertEqual(article.source, sample.expected_source)
        self.assertTrue(article.quality.has_fulltext)
        self.assertGreater(len(article.sections), 0)
        self.assertTrue(
            source_trail_matches(article.quality.source_trail, sample.accepted_live_source_trail_groups),
            article.quality.source_trail,
        )

    def test_elsevier_doi_live_fulltext(self) -> None:
        self._require_env(*ELSEVIER_SAMPLE.required_env)
        article = fetch_article(
            ELSEVIER_SAMPLE.doi,
            allow_html_fallback=False,
            transport=HttpTransport(),
            env=self.env,
        )

        self._assert_matches_sample(article, ELSEVIER_SAMPLE)

    def test_springer_doi_live_fulltext(self) -> None:
        self._require_env(*SPRINGER_SAMPLE.required_env)
        article = fetch_article(
            SPRINGER_SAMPLE.doi,
            allow_html_fallback=False,
            transport=HttpTransport(),
            env=self.env,
        )

        self._assert_matches_sample(article, SPRINGER_SAMPLE)

    def test_wiley_doi_live_fulltext(self) -> None:
        self._require_env(*WILEY_SAMPLE.required_env)
        wiley_env = {
            **self.env,
            "FLARESOLVERR_URL": "",
            "FLARESOLVERR_ENV_FILE": "",
            "FLARESOLVERR_SOURCE_DIR": "",
            "FLARESOLVERR_MIN_INTERVAL_SECONDS": "",
            "FLARESOLVERR_MAX_REQUESTS_PER_HOUR": "",
            "FLARESOLVERR_MAX_REQUESTS_PER_DAY": "",
        }
        article = fetch_article(
            WILEY_SAMPLE.doi,
            allow_html_fallback=False,
            transport=HttpTransport(),
            env=wiley_env,
        )

        self._assert_matches_sample(article, WILEY_SAMPLE)

    def test_elsevier_url_live_recovers_doi_and_uses_official_fulltext(self) -> None:
        self._require_env(*ELSEVIER_SAMPLE.required_env)
        article = fetch_article(
            ELSEVIER_SAMPLE.resolve_url,
            allow_html_fallback=False,
            transport=HttpTransport(),
            env=self.env,
        )

        self.assertEqual(article.doi, ELSEVIER_SAMPLE.doi)
        self._assert_matches_sample(article, ELSEVIER_SAMPLE)
        self.assertIn("resolve:url", article.quality.source_trail)
        self.assertNotIn("fallback:metadata_only", article.quality.source_trail)


if __name__ == "__main__":
    unittest.main()
