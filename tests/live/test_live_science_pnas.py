from __future__ import annotations

import os
import unittest
from pathlib import Path

from paper_fetch.config import build_runtime_env, resolve_flaresolverr_source_dir, resolve_flaresolverr_url
from paper_fetch.http import HttpTransport
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers._flaresolverr import health_check
from paper_fetch.service import FetchStrategy, fetch_paper


RUN_LIVE = os.environ.get("PAPER_FETCH_RUN_LIVE") == "1"


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

    def test_science_doi_live_fulltext_via_html(self) -> None:
        self._require_env(
            "CROSSREF_MAILTO",
            "FLARESOLVERR_ENV_FILE",
            "FLARESOLVERR_MIN_INTERVAL_SECONDS",
            "FLARESOLVERR_MAX_REQUESTS_PER_HOUR",
            "FLARESOLVERR_MAX_REQUESTS_PER_DAY",
        )
        self._require_flaresolverr()

        article = fetch_article(
            "10.1126/science.ady3136",
            transport=HttpTransport(),
            env=self.env,
        )

        self.assertEqual(article.source, "science")
        self.assertTrue(article.quality.has_fulltext)
        self.assertGreater(len(article.sections), 0)
        self.assertIn("fulltext:science_html_ok", article.quality.source_trail)

    def test_pnas_doi_live_fulltext_via_pdf_fallback(self) -> None:
        self._require_env(
            "CROSSREF_MAILTO",
            "FLARESOLVERR_ENV_FILE",
            "FLARESOLVERR_MIN_INTERVAL_SECONDS",
            "FLARESOLVERR_MAX_REQUESTS_PER_HOUR",
            "FLARESOLVERR_MAX_REQUESTS_PER_DAY",
        )
        self._require_flaresolverr()

        article = fetch_article(
            "10.1073/pnas.81.23.7500",
            transport=HttpTransport(),
            env=self.env,
        )

        self.assertEqual(article.source, "pnas")
        self.assertTrue(article.quality.has_fulltext)
        self.assertGreater(len(article.sections), 0)
        self.assertIn("fulltext:pnas_pdf_fallback_ok", article.quality.source_trail)


if __name__ == "__main__":
    unittest.main()
