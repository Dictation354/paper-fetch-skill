from __future__ import annotations

import os
import unittest
from pathlib import Path

from paper_fetch.config import build_runtime_env, resolve_flaresolverr_source_dir, resolve_flaresolverr_url
from paper_fetch.http import HttpTransport
from paper_fetch.providers._flaresolverr import health_check
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.service import FetchStrategy, fetch_paper


RUN_LIVE = os.environ.get("PAPER_FETCH_RUN_LIVE") == "1"


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

    def test_elsevier_doi_live_fulltext(self) -> None:
        self._require_env("ELSEVIER_API_KEY", "CROSSREF_MAILTO")
        article = fetch_article(
            "10.1016/j.rse.2025.114648",
            allow_html_fallback=False,
            transport=HttpTransport(),
            env=self.env,
        )

        self.assertEqual(article.source, "elsevier_xml")
        self.assertTrue(article.quality.has_fulltext)
        self.assertGreater(len(article.sections), 0)

    def test_springer_doi_live_fulltext(self) -> None:
        self._require_env("CROSSREF_MAILTO")
        article = fetch_article(
            "10.1186/1471-2105-11-421",
            allow_html_fallback=False,
            transport=HttpTransport(),
            env=self.env,
        )

        self.assertEqual(article.source, "springer_html")
        self.assertTrue(article.quality.has_fulltext)
        self.assertGreater(len(article.sections), 0)

    def test_wiley_doi_live_fulltext(self) -> None:
        self._require_env("CROSSREF_MAILTO", "WILEY_TDM_CLIENT_TOKEN")
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
            "10.1111/j.1745-4506.1980.tb00241.x",
            allow_html_fallback=False,
            transport=HttpTransport(),
            env=wiley_env,
        )

        self.assertEqual(article.source, "wiley_browser")
        self.assertTrue(article.quality.has_fulltext)
        self.assertGreater(len(article.sections), 0)
        self.assertIn("fulltext:wiley_pdf_api_ok", article.quality.source_trail)
        self.assertIn("fulltext:wiley_pdf_fallback_ok", article.quality.source_trail)

    def test_elsevier_url_live_recovers_doi_and_uses_official_fulltext(self) -> None:
        self._require_env("ELSEVIER_API_KEY", "CROSSREF_MAILTO")
        article = fetch_article(
            "https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525",
            allow_html_fallback=False,
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

    def test_short_html_body_live_stays_on_springer_provider_waterfall(self) -> None:
        self._require_env("CROSSREF_MAILTO")
        article = fetch_article(
            "https://www.nature.com/articles/sj.bdj.2017.900",
            allow_html_fallback=True,
            transport=HttpTransport(),
            env=self.env,
        )

        self.assertEqual(article.doi, "10.1038/sj.bdj.2017.900")
        self.assertEqual(article.source, "springer_html")
        self.assertTrue(article.quality.has_fulltext)
        self.assertTrue(
            any(
                marker in article.quality.source_trail
                for marker in ("fulltext:springer_html_ok", "fulltext:springer_pdf_fallback_ok")
            )
        )
        self.assertNotIn("fallback:metadata_only", article.quality.source_trail)


if __name__ == "__main__":
    unittest.main()
