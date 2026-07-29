from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

import pytest

from paper_fetch.http import HttpTransport
from paper_fetch.provider_catalog import provider_has_browser_route
from paper_fetch.runtime import RuntimeContext
from paper_fetch.service import FetchStrategy, fetch_paper
from tests.live._runtime_env import (
    build_isolated_live_env,
    require_selected_browser_or_skip,
)
from tests.provider_benchmark_samples import (
    iter_provider_benchmark_samples,
    provider_benchmark_sample,
    source_trail_matches,
)


RUN_LIVE = os.environ.get("PAPER_FETCH_RUN_LIVE") == "1"
RUN_IEEE_BROWSER_LIVE = os.environ.get("PAPER_FETCH_RUN_IEEE_BROWSER_LIVE") == "1"
IEEE_BROWSER_ASSET_DOI = "10.1109/TIM.2024.3509573"
IEEE_BROWSER_ASSET_URL = (
    "https://ieeexplore.ieee.org/mediastore/IEEE/content/media/"
    "19/10764799/10772041/gu1-3509573-large.gif"
)
IEEE_BROWSER_BODY_ASSET_COUNT = 13
ELSEVIER_SAMPLE = provider_benchmark_sample("elsevier")
IEEE_SAMPLE = provider_benchmark_sample("ieee")


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


@pytest.fixture(scope="module")
def catalog_live_env():
    if not RUN_LIVE:
        pytest.skip("Set PAPER_FETCH_RUN_LIVE=1 to run live publisher smoke tests.")
    env, tempdir = build_isolated_live_env()
    try:
        yield env
    finally:
        tempdir.cleanup()


@pytest.mark.parametrize(
    "sample",
    iter_provider_benchmark_samples(),
    ids=lambda sample: sample.provider,
)
def test_catalog_provider_sample_live_fulltext(sample, catalog_live_env) -> None:
    missing = [
        key for key in sample.required_env if not catalog_live_env.get(key, "").strip()
    ]
    if missing:
        pytest.skip(
            "Missing required environment variables for live test: "
            + ", ".join(missing)
        )
    if provider_has_browser_route(sample.provider):

        class _PytestSkipper:
            @staticmethod
            def skipTest(message: str) -> None:
                pytest.skip(message)

        require_selected_browser_or_skip(_PytestSkipper(), catalog_live_env)

    article = fetch_article(
        sample.doi,
        transport=HttpTransport(),
        env=catalog_live_env,
    )

    assert article.source == sample.expected_source
    assert article.quality.has_fulltext
    assert article.sections
    assert source_trail_matches(
        article.quality.source_trail,
        sample.accepted_live_source_trail_groups,
    ), article.quality.source_trail


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

    def test_ieee_camoufox_recovers_known_large_gif_to_local_markdown(self) -> None:
        if not RUN_IEEE_BROWSER_LIVE:
            self.skipTest(
                "Set PAPER_FETCH_RUN_IEEE_BROWSER_LIVE=1 for the protected IEEE asset case."
            )
        require_selected_browser_or_skip(self, self.env)
        with tempfile.TemporaryDirectory(prefix="paper-fetch-ieee-live-") as tmpdir:
            context = RuntimeContext(
                env=self.env,
                transport=HttpTransport(),
                download_dir=Path(tmpdir),
                artifact_mode="all",
            )
            try:
                envelope = fetch_paper(
                    IEEE_BROWSER_ASSET_DOI,
                    modes={"article", "markdown"},
                    strategy=FetchStrategy(
                        allow_metadata_only_fallback=False,
                        preferred_providers=["ieee"],
                        asset_profile="body",
                    ),
                    context=context,
                )
            finally:
                context.close()

            self.assertIsNotNone(envelope.article)
            self.assertTrue(envelope.has_fulltext)
            matching_assets = [
                asset
                for asset in envelope.article.assets
                if IEEE_BROWSER_ASSET_URL
                in {
                    asset.url,
                    asset.download_url,
                    asset.original_url,
                    asset.source_url,
                }
            ]
            self.assertEqual(len(matching_assets), 1, envelope.article.assets)
            asset = matching_assets[0]
            self.assertTrue(asset.path)
            asset_path = Path(str(asset.path))
            self.assertTrue(asset_path.is_file(), asset_path)
            payload = asset_path.read_bytes()
            self.assertTrue(payload.startswith((b"GIF87a", b"GIF89a")))
            self.assertGreater(len(payload), 10)
            self.assertGreater(int.from_bytes(payload[6:8], "little"), 0)
            self.assertGreater(int.from_bytes(payload[8:10], "little"), 0)
            downloaded_body_assets = [
                candidate
                for candidate in envelope.article.assets
                if candidate.path
                and candidate.kind in {"figure", "table", "formula"}
                and "mediastore/IEEE/content/media/" in (candidate.original_url or "")
            ]
            self.assertEqual(
                len(downloaded_body_assets),
                IEEE_BROWSER_BODY_ASSET_COUNT,
                downloaded_body_assets,
            )
            self.assertTrue(
                all(
                    candidate.download_tier == "full_size"
                    for candidate in downloaded_body_assets
                ),
                downloaded_body_assets,
            )
            self.assertEqual(envelope.article.quality.asset_failures, [])
            self.assertIsNotNone(envelope.markdown)
            self.assertIn(asset_path.name, envelope.markdown)
            self.assertNotIn(IEEE_BROWSER_ASSET_URL, envelope.markdown)

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
