from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch.config import AMS_STORAGE_STATE_JSON_ENV_VAR, XDG_DATA_HOME_ENV_VAR
from paper_fetch.providers import _playwright_browser, browser_runtime


class AtyponBrowserWorkflowBrowserRuntimeTests(unittest.TestCase):
    def _runtime_config(
        self,
        tmpdir: str,
        provider: str,
        doi: str,
    ) -> browser_runtime.BrowserRuntimeConfig:
        return browser_runtime.BrowserRuntimeConfig(
            provider=provider,
            doi=doi,
            artifact_dir=Path(tmpdir) / "artifacts",
            headless=True,
            user_agent="Mozilla/5.0",
        )

    def test_normalize_browser_cookie_for_playwright(self) -> None:
        cookie = browser_runtime.normalize_browser_cookie_for_playwright(
            {
                "name": "cf_clearance",
                "value": "secret",
                "domain": ".science.org",
                "path": "/",
                "secure": True,
                "httpOnly": True,
                "sameSite": "lax",
            }
        )

        self.assertIsNotNone(cookie)
        assert cookie is not None
        self.assertEqual(cookie["name"], "cf_clearance")
        self.assertEqual(cookie["domain"], ".science.org")
        self.assertEqual(cookie["sameSite"], "Lax")
        self.assertTrue(cookie["secure"])
        self.assertTrue(cookie["httpOnly"])

    def test_ams_browser_runtime_allows_missing_state_and_reuses_configured_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            state_path = tmp_path / "ams-state.json"
            state_path.write_text('{"cookies": [], "origins": []}', encoding="utf-8")
            default_runtime = browser_runtime.load_runtime_config(
                {XDG_DATA_HOME_ENV_VAR: str(tmp_path)},
                provider="ams",
                doi="10.1175/test",
            )
            configured_runtime = browser_runtime.load_runtime_config(
                {
                    XDG_DATA_HOME_ENV_VAR: str(tmp_path),
                    AMS_STORAGE_STATE_JSON_ENV_VAR: str(state_path),
                },
                provider="ams",
                doi="10.1175/test",
            )

        self.assertIsNone(default_runtime.storage_state_path)
        self.assertEqual(
            default_runtime.user_data_dir,
            tmp_path / "paper-fetch" / "publisher-browser-profiles" / "ams-camoufox",
        )
        self.assertEqual(configured_runtime.storage_state_path, state_path)

    def test_required_or_explicit_storage_state_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            missing_path = tmp_path / "missing-state.json"
            with self.assertRaisesRegex(Exception, "required"):
                browser_runtime.load_runtime_config(
                    {XDG_DATA_HOME_ENV_VAR: str(tmp_path)},
                    provider="ams",
                    doi="10.1175/test",
                    require_storage_state=True,
                )
            with self.assertRaisesRegex(Exception, "does not point"):
                browser_runtime.load_runtime_config(
                    {
                        XDG_DATA_HOME_ENV_VAR: str(tmp_path),
                        AMS_STORAGE_STATE_JSON_ENV_VAR: str(missing_path),
                    },
                    provider="ams",
                    doi="10.1175/test",
                )

    def test_storage_state_schema_is_validated(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            state_path = tmp_path / "ams-state.json"
            state_path.write_text(
                '{"cookies": [{"name": "sid"}], "origins": []}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(Exception, "invalid browser storage-state"):
                browser_runtime.load_runtime_config(
                    {
                        XDG_DATA_HOME_ENV_VAR: str(tmp_path),
                        AMS_STORAGE_STATE_JSON_ENV_VAR: str(state_path),
                    },
                    provider="ams",
                    doi="10.1175/test",
                )

    def test_merge_browser_context_seeds_prefers_latest_cookie_and_url(self) -> None:
        merged = browser_runtime.merge_browser_context_seeds(
            {
                "browser_cookies": [
                    {
                        "name": "cf_clearance",
                        "value": "old",
                        "domain": ".example.org",
                        "path": "/",
                    }
                ],
                "browser_user_agent": "UA/1",
                "browser_final_url": "https://example.org/article",
            },
            {
                "browser_cookies": [
                    {
                        "name": "cf_clearance",
                        "value": "new",
                        "domain": ".example.org",
                        "path": "/",
                    },
                    {
                        "name": "sessionid",
                        "value": "warm",
                        "domain": ".example.org",
                        "path": "/",
                    },
                ],
                "browser_final_url": "https://example.org/pdf",
            },
        )

        self.assertEqual(
            merged["browser_cookies"],
            [
                {
                    "name": "cf_clearance",
                    "value": "new",
                    "domain": ".example.org",
                    "path": "/",
                },
                {
                    "name": "sessionid",
                    "value": "warm",
                    "domain": ".example.org",
                    "path": "/",
                },
            ],
        )
        self.assertEqual(merged["browser_user_agent"], "UA/1")
        self.assertEqual(merged["browser_final_url"], "https://example.org/pdf")

    def test_merge_browser_context_seeds_preserves_fetcher_marker(self) -> None:
        merged = browser_runtime.merge_browser_context_seeds(
            {"paper_fetch_html_fetcher": "camoufox"},
            {"paper_fetch_html_fetcher": "direct_http"},
        )

        self.assertEqual(merged["paper_fetch_html_fetcher"], "direct_http")

    def test_warm_browser_context_merges_existing_and_preflight_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._runtime_config(tmpdir, "wiley", "10.1111/test")
            with mock.patch.object(
                _playwright_browser,
                "fetch_html_with_playwright",
                return_value=browser_runtime.BrowserFetchedHtml(
                    source_url="https://onlinelibrary.wiley.com/doi/epdf/10.1111/test",
                    final_url="https://onlinelibrary.wiley.com/doi/10.1111/test",
                    html="<html><body>pdf wrapper</body></html>",
                    response_status=200,
                    response_headers={"content-type": "text/html"},
                    title="PDF wrapper",
                    summary="PDF wrapper",
                    browser_context_seed={
                        "browser_cookies": [
                            {
                                "name": "sessionid",
                                "value": "warm",
                                "domain": ".wiley.com",
                                "path": "/",
                            }
                        ],
                        "browser_user_agent": "Mozilla/5.0",
                        "browser_final_url": "https://onlinelibrary.wiley.com/doi/10.1111/test",
                    },
                ),
            ):
                warmed = browser_runtime.warm_browser_context(
                    ["https://onlinelibrary.wiley.com/doi/epdf/10.1111/test"],
                    publisher="wiley",
                    config=config,
                    browser_context_seed={
                        "browser_cookies": [
                            {
                                "name": "cf_clearance",
                                "value": "seed",
                                "domain": ".wiley.com",
                                "path": "/",
                            }
                        ],
                        "browser_user_agent": "Mozilla/5.0",
                    },
                )

        self.assertEqual(
            warmed["browser_cookies"],
            [
                {
                    "name": "cf_clearance",
                    "value": "seed",
                    "domain": ".wiley.com",
                    "path": "/",
                },
                {
                    "name": "sessionid",
                    "value": "warm",
                    "domain": ".wiley.com",
                    "path": "/",
                },
            ],
        )
        self.assertEqual(
            warmed["browser_final_url"],
            "https://onlinelibrary.wiley.com/doi/10.1111/test",
        )


if __name__ == "__main__":
    unittest.main()
