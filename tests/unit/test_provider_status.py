from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from paper_fetch.providers import _flaresolverr
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers.crossref import CrossrefClient
from paper_fetch.providers.elsevier import ElsevierClient
from paper_fetch.providers.pnas import PnasClient
from paper_fetch.providers.science import ScienceClient
from paper_fetch.providers.springer import SpringerClient
from paper_fetch.providers.wiley import WILEY_TDM_CLIENT_TOKEN_ENV_VAR, WileyClient

_WORKFLOW_FILES = (
    "setup_flaresolverr_source.sh",
    "start_flaresolverr_source.sh",
    "run_flaresolverr_source.sh",
    "stop_flaresolverr_source.sh",
    "flaresolverr_source_common.sh",
)


class DummyTransport:
    pass


class ProviderStatusTests(unittest.TestCase):
    def _browser_client(self, provider: str, env: dict[str, str]):
        if provider == "science":
            return ScienceClient(DummyTransport(), env)
        return PnasClient(DummyTransport(), env)

    def _browser_env(
        self,
        tmpdir: str,
        *,
        provider: str,
        create_env_file: bool = True,
        create_workflow: bool = False,
    ) -> dict[str, str]:
        tmp = Path(tmpdir)
        env_file = tmp / f".env.{provider}"
        if create_env_file:
            env_file.write_text('HEADLESS="true"\n', encoding="utf-8")
        source_dir = tmp / "vendor" / "flaresolverr"
        if create_workflow:
            source_dir.mkdir(parents=True, exist_ok=True)
            for name in _WORKFLOW_FILES:
                (source_dir / name).write_text("#!/bin/bash\n", encoding="utf-8")
        return {
            "FLARESOLVERR_ENV_FILE": str(env_file),
            "FLARESOLVERR_SOURCE_DIR": str(source_dir),
            "FLARESOLVERR_MIN_INTERVAL_SECONDS": "60",
            "FLARESOLVERR_MAX_REQUESTS_PER_HOUR": "1",
            "FLARESOLVERR_MAX_REQUESTS_PER_DAY": "20",
            "XDG_DATA_HOME": str(tmp / "xdg"),
        }

    def _rate_limit_file(self, env: dict[str, str]) -> Path:
        return Path(env["XDG_DATA_HOME"]) / "paper-fetch" / "publisher_browser_rate_limits.json"

    def test_crossref_without_mailto_is_ready_with_note(self) -> None:
        result = CrossrefClient(DummyTransport(), {}).probe_status()

        self.assertEqual(result.status, "ready")
        self.assertTrue(result.available)
        self.assertEqual(result.missing_env, [])
        self.assertIn("CROSSREF_MAILTO", result.notes[0])
        self.assertEqual(result.checks[0].name, "metadata_api")
        self.assertEqual(result.checks[0].status, "ok")

    def test_elsevier_missing_api_key_is_not_configured(self) -> None:
        result = ElsevierClient(DummyTransport(), {}).probe_status()

        self.assertEqual(result.status, "not_configured")
        self.assertFalse(result.available)
        self.assertIn("ELSEVIER_API_KEY", result.missing_env)
        self.assertIn("FLARESOLVERR_ENV_FILE", result.missing_env)
        self.assertEqual(result.checks[0].name, "fulltext_api")
        self.assertEqual(result.checks[0].status, "not_configured")

    def test_elsevier_status_is_partial_when_api_is_ready_but_browser_fallback_is_not(self) -> None:
        result = ElsevierClient(DummyTransport(), {"ELSEVIER_API_KEY": "secret"}).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "partial")
        self.assertTrue(result.available)
        self.assertEqual(checks["fulltext_api"].status, "ok")
        self.assertEqual(checks["runtime_env"].status, "not_configured")
        self.assertIn("FLARESOLVERR_ENV_FILE", result.missing_env)

    def test_elsevier_status_is_partial_when_browser_fallback_is_ready_but_api_is_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = self._browser_env(tmpdir, provider="elsevier", create_env_file=True, create_workflow=True)
            with mock.patch.object(_flaresolverr, "health_check", return_value=None):
                result = ElsevierClient(DummyTransport(), env).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "partial")
        self.assertTrue(result.available)
        self.assertEqual(checks["fulltext_api"].status, "not_configured")
        self.assertEqual(checks["runtime_env"].status, "ok")
        self.assertEqual(checks["repo_local_workflow"].status, "ok")
        self.assertEqual(checks["flaresolverr_health"].status, "ok")
        self.assertEqual(checks["rate_limit_window"].status, "ok")
        self.assertIn("ELSEVIER_API_KEY", result.missing_env)

    def test_elsevier_status_is_ready_when_api_and_browser_fallback_are_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {
                **self._browser_env(tmpdir, provider="elsevier", create_env_file=True, create_workflow=True),
                "ELSEVIER_API_KEY": "secret",
            }
            with mock.patch.object(_flaresolverr, "health_check", return_value=None):
                result = ElsevierClient(DummyTransport(), env).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "ready")
        self.assertTrue(result.available)
        self.assertEqual(checks["fulltext_api"].status, "ok")
        self.assertTrue(all(check.status == "ok" for check in result.checks))

    def test_springer_direct_html_route_is_ready_without_env(self) -> None:
        result = SpringerClient(DummyTransport(), {}).probe_status()

        self.assertEqual(result.status, "ready")
        self.assertTrue(result.available)
        self.assertEqual(result.missing_env, [])
        self.assertEqual(len(result.checks), 1)
        self.assertEqual(result.checks[0].name, "html_route")
        self.assertEqual(result.checks[0].status, "ok")

    def test_wiley_missing_runtime_and_token_is_not_configured(self) -> None:
        result = WileyClient(DummyTransport(), {}).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "not_configured")
        self.assertFalse(result.available)
        self.assertIn("FLARESOLVERR_ENV_FILE", result.missing_env)
        self.assertIn(WILEY_TDM_CLIENT_TOKEN_ENV_VAR, result.missing_env)
        self.assertEqual(checks["runtime_env"].status, "not_configured")
        self.assertEqual(checks["repo_local_workflow"].status, "not_configured")
        self.assertEqual(checks["flaresolverr_health"].status, "not_configured")
        self.assertEqual(checks["rate_limit_window"].status, "not_configured")
        self.assertEqual(checks["tdm_api_token"].status, "not_configured")

    def test_wiley_status_is_partial_when_only_tdm_token_is_configured(self) -> None:
        result = WileyClient(DummyTransport(), {WILEY_TDM_CLIENT_TOKEN_ENV_VAR: "secret"}).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "partial")
        self.assertTrue(result.available)
        self.assertEqual(checks["runtime_env"].status, "not_configured")
        self.assertEqual(checks["tdm_api_token"].status, "ok")
        self.assertIn("FLARESOLVERR_ENV_FILE", result.missing_env)

    def test_wiley_status_is_partial_when_only_html_runtime_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = self._browser_env(tmpdir, provider="wiley", create_env_file=True, create_workflow=True)
            with mock.patch.object(_flaresolverr, "health_check", return_value=None):
                result = WileyClient(DummyTransport(), env).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "partial")
        self.assertTrue(result.available)
        self.assertEqual(checks["runtime_env"].status, "ok")
        self.assertEqual(checks["repo_local_workflow"].status, "ok")
        self.assertEqual(checks["flaresolverr_health"].status, "ok")
        self.assertEqual(checks["rate_limit_window"].status, "ok")
        self.assertEqual(checks["tdm_api_token"].status, "not_configured")
        self.assertIn(WILEY_TDM_CLIENT_TOKEN_ENV_VAR, result.missing_env)

    def test_wiley_status_is_ready_when_html_runtime_and_tdm_token_are_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {
                **self._browser_env(tmpdir, provider="wiley", create_env_file=True, create_workflow=True),
                WILEY_TDM_CLIENT_TOKEN_ENV_VAR: "secret",
            }
            with mock.patch.object(_flaresolverr, "health_check", return_value=None):
                result = WileyClient(DummyTransport(), env).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "ready")
        self.assertTrue(result.available)
        self.assertTrue(all(check.status == "ok" for check in checks.values()))

    def test_browser_workflow_providers_missing_env_are_not_configured(self) -> None:
        for provider in ("science", "pnas"):
            with self.subTest(provider=provider):
                result = self._browser_client(provider, {}).probe_status()
                checks = {check.name: check for check in result.checks}

                self.assertEqual(result.status, "not_configured")
                self.assertFalse(result.available)
                self.assertIn("FLARESOLVERR_ENV_FILE", result.missing_env)
                self.assertEqual(checks["runtime_env"].status, "not_configured")
                self.assertEqual(checks["repo_local_workflow"].status, "not_configured")
                self.assertEqual(checks["flaresolverr_health"].status, "not_configured")
                self.assertEqual(checks["rate_limit_window"].status, "not_configured")

    def test_browser_workflow_providers_missing_repo_local_workflow_are_not_configured(self) -> None:
        for provider in ("science", "pnas"):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as tmpdir:
                env = self._browser_env(tmpdir, provider=provider, create_env_file=True, create_workflow=False)
                result = self._browser_client(provider, env).probe_status()
                checks = {check.name: check for check in result.checks}

                self.assertEqual(result.status, "not_configured")
                self.assertEqual(checks["runtime_env"].status, "ok")
                self.assertEqual(checks["repo_local_workflow"].status, "not_configured")
                self.assertEqual(checks["flaresolverr_health"].status, "not_configured")
                self.assertEqual(checks["rate_limit_window"].status, "not_configured")

    def test_browser_workflow_providers_health_failures_are_reported(self) -> None:
        for provider in ("science", "pnas"):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as tmpdir:
                env = self._browser_env(tmpdir, provider=provider, create_env_file=True, create_workflow=True)
                with mock.patch.object(
                    _flaresolverr,
                    "health_check",
                    side_effect=ProviderFailure("not_configured", "Local FlareSolverr is down."),
                ):
                    result = self._browser_client(provider, env).probe_status()
                checks = {check.name: check for check in result.checks}

                self.assertEqual(result.status, "not_configured")
                self.assertEqual(checks["runtime_env"].status, "ok")
                self.assertEqual(checks["repo_local_workflow"].status, "ok")
                self.assertEqual(checks["flaresolverr_health"].status, "not_configured")
                self.assertEqual(checks["rate_limit_window"].status, "not_configured")

    def test_browser_workflow_providers_rate_limits_are_reported_without_mutation(self) -> None:
        for provider in ("science", "pnas"):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as tmpdir:
                env = self._browser_env(tmpdir, provider=provider, create_env_file=True, create_workflow=True)
                rate_limit_file = self._rate_limit_file(env)
                rate_limit_file.parent.mkdir(parents=True, exist_ok=True)
                original_payload = {
                    provider: {
                        "last_request_at": time.time(),
                        "events": [time.time()],
                    }
                }
                rate_limit_file.write_text(json.dumps(original_payload, ensure_ascii=False, indent=2), encoding="utf-8")

                with mock.patch.object(_flaresolverr, "health_check", return_value=None):
                    result = self._browser_client(provider, env).probe_status()

                self.assertEqual(result.status, "rate_limited")
                self.assertFalse(result.available)
                checks = {check.name: check for check in result.checks}
                self.assertEqual(checks["rate_limit_window"].status, "rate_limited")
                current_payload = json.loads(rate_limit_file.read_text(encoding="utf-8"))
                self.assertEqual(current_payload, original_payload)

    def test_browser_workflow_providers_ready_status_checks_all_pass(self) -> None:
        for provider in ("science", "pnas"):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as tmpdir:
                env = self._browser_env(tmpdir, provider=provider, create_env_file=True, create_workflow=True)
                with mock.patch.object(_flaresolverr, "health_check", return_value=None):
                    result = self._browser_client(provider, env).probe_status()

                self.assertEqual(result.status, "ready")
                self.assertTrue(result.available)
                self.assertTrue(all(check.status == "ok" for check in result.checks))


if __name__ == "__main__":
    unittest.main()
