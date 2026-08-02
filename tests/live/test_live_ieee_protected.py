from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest

from paper_fetch.http import HttpTransport
from paper_fetch.runtime import RuntimeContext
from paper_fetch.service import FetchStrategy, fetch_paper
from paper_fetch.workflow.acceptance import (
    OverallAcceptanceStatus,
    evaluate_fetch_acceptance,
)
from tests.live._runtime_env import (
    build_isolated_live_env,
    preflight_selected_browser_or_skip,
)


RUN_IEEE_BROWSER_LIVE = os.environ.get("PAPER_FETCH_RUN_IEEE_BROWSER_LIVE") == "1"
IEEE_BROWSER_ASSET_DOI = "10.1109/TIM.2024.3509573"
IEEE_BROWSER_ASSET_URL = (
    "https://ieeexplore.ieee.org/mediastore/IEEE/content/media/"
    "19/10764799/10772041/gu1-3509573-large.gif"
)
IEEE_BROWSER_BODY_ASSET_COUNT = 13


def _ieee_live_artifact_root() -> Path:
    configured = os.environ.get("PAPER_FETCH_LIVE_ARTIFACT_DIR", "").strip()
    root = (
        Path(configured)
        if configured
        else Path(".paper-fetch-runs/live-ieee-protected")
    )
    root.mkdir(parents=True, exist_ok=True)
    return root


@unittest.skipUnless(
    RUN_IEEE_BROWSER_LIVE,
    "Set PAPER_FETCH_RUN_IEEE_BROWSER_LIVE=1 on an authorized runner.",
)
class LiveIeeeProtectedAssetTests(unittest.TestCase):
    runtime_env_tempdir: tempfile.TemporaryDirectory | None = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.env, cls.runtime_env_tempdir = build_isolated_live_env()
        cls.preflight_cache = {}

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.runtime_env_tempdir is not None:
            cls.runtime_env_tempdir.cleanup()

    def test_camoufox_recovers_known_large_gif_to_local_markdown(self) -> None:
        artifact_root = _ieee_live_artifact_root()
        output_dir = Path(
            tempfile.mkdtemp(prefix="run-", dir=str(artifact_root.resolve()))
        )
        try:
            preflight_selected_browser_or_skip(
                self,
                provider="ieee",
                env=self.env,
                cache=self.preflight_cache,
                artifact_root=output_dir / "preflight",
            )
            context = RuntimeContext(
                env=self.env,
                transport=HttpTransport(),
                download_dir=output_dir,
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
            acceptance = evaluate_fetch_acceptance(
                envelope,
                asset_profile="body",
                requested_outputs={"article", "markdown"},
                expected_doi=IEEE_BROWSER_ASSET_DOI,
            )
            self.assertEqual(
                acceptance.overall,
                OverallAcceptanceStatus.COMPLETE,
                acceptance.to_json(),
            )
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
            self.assertIn(asset.final_fetcher, {"direct_http", "camoufox"})
            if asset.final_fetcher == "camoufox":
                self.assertEqual(asset.browser_backend, "camoufox")
                self.assertEqual(
                    [attempt.get("stage") for attempt in asset.recovery_attempts],
                    ["direct", "browser"],
                )
                self.assertEqual(asset.recovery_attempts[0].get("status"), 403)
            else:
                self.assertIsNone(asset.browser_backend)
                self.assertEqual(asset.recovery_attempts, [])
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
            hash_records = []
            for candidate in downloaded_body_assets:
                candidate_path = Path(str(candidate.path))
                candidate_payload = candidate_path.read_bytes()
                hash_records.append(
                    {
                        "heading": candidate.heading,
                        "path": str(candidate_path.resolve()),
                        "download_tier": candidate.download_tier,
                        "browser_backend": candidate.browser_backend,
                        "final_fetcher": candidate.final_fetcher,
                        "recovery_attempts": candidate.recovery_attempts,
                        "size": len(candidate_payload),
                        "sha256": sha256(candidate_payload).hexdigest(),
                    }
                )
            (output_dir / "asset-hashes.json").write_text(
                json.dumps(
                    {
                        "doi": IEEE_BROWSER_ASSET_DOI,
                        "acceptance": acceptance.model_dump(mode="json"),
                        "target_asset_sha256": sha256(payload).hexdigest(),
                        "target_final_fetcher": asset.final_fetcher,
                        "target_browser_backend": asset.browser_backend,
                        "target_recovery_attempts": asset.recovery_attempts,
                        "asset_count": len(hash_records),
                        "assets": hash_records,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception:
            self._test_artifact_dir = str(output_dir)
            raise


if __name__ == "__main__":
    unittest.main()
