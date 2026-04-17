from __future__ import annotations

import os
import unittest
from pathlib import Path

from paper_fetch.config import build_runtime_env, resolve_flaresolverr_source_dir, resolve_flaresolverr_url
from paper_fetch.http import HttpTransport
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers._flaresolverr import health_check
from paper_fetch.service import FetchStrategy, fetch_paper
from tests.provider_benchmark_samples import provider_benchmark_sample, source_trail_matches


RUN_LIVE = os.environ.get("PAPER_FETCH_RUN_LIVE") == "1"
SCIENCE_SAMPLE = provider_benchmark_sample("science")
PNAS_SAMPLE = provider_benchmark_sample("pnas")


def fetch_article(query: str, *, transport: HttpTransport, env: dict[str, str]):
    envelope = fetch_paper(
        query,
        modes={"article"},
        strategy=FetchStrategy(
            allow_html_fallback=False,
            allow_metadata_only_fallback=True,
        ),
        download_dir=None,
        transport=transport,
        env=env,
    )
    assert envelope.article is not None
    return envelope.article


class LiveSciencePnasTests(unittest.TestCase):
    needs_flaresolverr = True

    @classmethod
    def setUpClass(cls) -> None:
        if not RUN_LIVE:
            raise unittest.SkipTest("Set PAPER_FETCH_RUN_LIVE=1 to run live Science / PNAS smoke tests.")
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

    def test_science_doi_live_fulltext_via_html(self) -> None:
        self._require_env(*SCIENCE_SAMPLE.required_env)
        self._require_flaresolverr()

        article = fetch_article(
            SCIENCE_SAMPLE.doi,
            transport=HttpTransport(),
            env=self.env,
        )

        self._assert_matches_sample(article, SCIENCE_SAMPLE)

    def test_pnas_doi_live_fulltext_uses_a_stable_provider_path(self) -> None:
        self._require_env(*PNAS_SAMPLE.required_env)
        self._require_flaresolverr()

        article = fetch_article(
            PNAS_SAMPLE.doi,
            transport=HttpTransport(),
            env=self.env,
        )

        self._assert_matches_sample(article, PNAS_SAMPLE)


if __name__ == "__main__":
    unittest.main()
