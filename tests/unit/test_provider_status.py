from __future__ import annotations

import unittest
from unittest import mock

from paper_fetch import config
from paper_fetch.providers import _cloakbrowser
from paper_fetch.providers.acs import AcsClient
from paper_fetch.providers.aip import AipClient
from paper_fetch.providers.ams import AmsClient
from paper_fetch.providers.arxiv import ArxivClient
from paper_fetch.providers.crossref import CrossrefClient
from paper_fetch.providers.elsevier import ElsevierClient
from paper_fetch.providers.ieee import IeeeClient
from paper_fetch.providers.pnas import PnasClient
from paper_fetch.providers.royalsocietypublishing import RoyalsocietypublishingClient
from paper_fetch.providers.science import ScienceClient
from paper_fetch.providers.springer import SpringerClient
from paper_fetch.providers.wiley import WILEY_TDM_CLIENT_TOKEN_ENV_VAR, WileyClient

CDP_ENV = {"CLOAKBROWSER_CDP_ENDPOINT": "ws://127.0.0.1:9222/devtools/browser/test"}


class DummyTransport:
    pass


class ProviderStatusTests(unittest.TestCase):
    def _browser_client(self, provider: str, env: dict[str, str]):
        if provider == "acs":
            return AcsClient(DummyTransport(), env)
        if provider == "aip":
            return AipClient(DummyTransport(), env)
        if provider == "science":
            return ScienceClient(DummyTransport(), env)
        if provider == "royalsocietypublishing":
            return RoyalsocietypublishingClient(DummyTransport(), env)
        return PnasClient(DummyTransport(), env)

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
        self.assertEqual(result.missing_env, ["ELSEVIER_API_KEY"])
        self.assertEqual(len(result.checks), 1)
        self.assertEqual(result.checks[0].name, "fulltext_api")
        self.assertEqual(result.checks[0].status, "not_configured")

    def test_elsevier_status_is_ready_when_api_is_configured(self) -> None:
        result = ElsevierClient(
            DummyTransport(), {"ELSEVIER_API_KEY": "secret"}
        ).probe_status()
        self.assertEqual(result.status, "ready")
        self.assertTrue(result.available)
        self.assertEqual(result.missing_env, [])
        self.assertEqual(len(result.checks), 1)
        self.assertEqual(result.checks[0].name, "fulltext_api")
        self.assertEqual(result.checks[0].status, "ok")
        self.assertEqual(result.checks[0].details, {})

    def test_springer_direct_html_route_is_ready_without_env(self) -> None:
        result = SpringerClient(DummyTransport(), {}).probe_status()

        self.assertEqual(result.status, "ready")
        self.assertTrue(result.available)
        self.assertEqual(result.missing_env, [])
        self.assertEqual(len(result.checks), 1)
        self.assertEqual(result.checks[0].name, "html_route")
        self.assertEqual(result.checks[0].status, "ok")

    def test_ieee_direct_html_and_pdf_routes_are_ready_without_env(self) -> None:
        result = IeeeClient(DummyTransport(), {}).probe_status()

        self.assertEqual(result.status, "ready")
        self.assertTrue(result.available)
        self.assertEqual(result.missing_env, [])
        checks = {check.name: check for check in result.checks}
        self.assertEqual(checks["html_route"].status, "ok")
        self.assertEqual(checks["pdf_fallback"].status, "ok")

    def test_arxiv_api_html_and_pdf_routes_are_ready_without_env(self) -> None:
        result = ArxivClient(DummyTransport(), {}).probe_status()

        self.assertEqual(result.status, "ready")
        self.assertTrue(result.available)
        self.assertEqual(result.missing_env, [])
        checks = {check.name: check for check in result.checks}
        self.assertEqual(checks["metadata_api"].status, "ok")
        self.assertEqual(checks["html_route"].status, "ok")
        self.assertEqual(checks["html_route"].details["mode"], "direct_http_html")
        self.assertEqual(checks["pdf_fallback"].status, "ok")
        self.assertEqual(checks["pdf_fallback"].details["mode"], "direct_http_pdf")
        self.assertEqual(set(checks), {"metadata_api", "html_route", "pdf_fallback"})

    def test_wiley_browser_runtime_ready_with_cdp_endpoint(self) -> None:
        with mock.patch.object(
            _cloakbrowser, "_dependency_available", return_value=True
        ):
            result = WileyClient(DummyTransport(), dict(CDP_ENV)).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "ready")
        self.assertTrue(result.available)
        self.assertEqual(result.missing_env, [])
        self.assertEqual(checks["runtime_env"].status, "ok")
        self.assertEqual(checks["playwright_dependency"].status, "ok")
        self.assertEqual(checks["tdm_api_token"].status, "ok")

    def test_wiley_missing_runtime_and_token_is_not_configured_when_cloakbrowser_is_missing(
        self,
    ) -> None:
        with mock.patch.object(
            _cloakbrowser, "_dependency_available", return_value=False
        ):
            result = WileyClient(DummyTransport(), {}).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "not_configured")
        self.assertFalse(result.available)
        self.assertIn(WILEY_TDM_CLIENT_TOKEN_ENV_VAR, result.missing_env)
        self.assertEqual(checks["runtime_env"].status, "not_configured")
        self.assertEqual(checks["playwright_dependency"].status, "not_configured")
        self.assertEqual(checks["tdm_api_token"].status, "not_configured")

    def test_wiley_status_is_partial_when_only_tdm_token_is_configured(self) -> None:
        with mock.patch.object(
            _cloakbrowser, "_dependency_available", return_value=False
        ):
            result = WileyClient(
                DummyTransport(), {**CDP_ENV, WILEY_TDM_CLIENT_TOKEN_ENV_VAR: "secret"}
            ).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "partial")
        self.assertTrue(result.available)
        self.assertEqual(checks["runtime_env"].status, "not_configured")
        self.assertEqual(checks["playwright_dependency"].status, "not_configured")
        self.assertEqual(checks["tdm_api_token"].status, "ok")

    def test_wiley_status_is_ready_when_html_runtime_and_tdm_token_are_ready(
        self,
    ) -> None:
        env = {**CDP_ENV, WILEY_TDM_CLIENT_TOKEN_ENV_VAR: "secret"}
        with mock.patch.object(
            _cloakbrowser, "_dependency_available", return_value=True
        ):
            result = WileyClient(DummyTransport(), env).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "ready")
        self.assertTrue(result.available)
        self.assertTrue(all(check.status == "ok" for check in checks.values()))

    def test_browser_workflow_providers_are_ready_with_cdp_endpoint(self) -> None:
        for provider in ("science", "pnas", "acs", "aip", "royalsocietypublishing"):
            with (
                self.subTest(provider=provider),
                mock.patch.object(
                    _cloakbrowser, "_dependency_available", return_value=True
                ),
            ):
                result = self._browser_client(provider, dict(CDP_ENV)).probe_status()
                checks = {check.name: check for check in result.checks}

                self.assertEqual(result.status, "ready")
                self.assertTrue(result.available)
                self.assertEqual(result.missing_env, [])
                self.assertEqual(checks["runtime_env"].status, "ok")
                self.assertEqual(checks["playwright_dependency"].status, "ok")

    def test_ams_status_has_no_browser_runtime_requirement(self) -> None:
        with mock.patch.object(_cloakbrowser, "_dependency_available") as dependency:
            result = AmsClient(DummyTransport(), dict(CDP_ENV)).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "ready")
        self.assertTrue(result.available)
        self.assertEqual(result.missing_env, [])
        self.assertEqual(list(checks), ["local_requirements"])
        self.assertEqual(checks["local_requirements"].status, "ok")
        dependency.assert_not_called()

    def test_browser_workflow_providers_missing_cloakbrowser_are_not_configured(
        self,
    ) -> None:
        for provider in (
            "science",
            "pnas",
            "acs",
            "aip",
            "royalsocietypublishing",
        ):
            with (
                self.subTest(provider=provider),
                mock.patch.object(
                    _cloakbrowser, "_dependency_available", return_value=False
                ),
            ):
                result = self._browser_client(provider, {}).probe_status()
                checks = {check.name: check for check in result.checks}

                self.assertEqual(result.status, "not_configured")
                self.assertEqual(checks["runtime_env"].status, "not_configured")
                self.assertEqual(
                    checks["playwright_dependency"].status, "not_configured"
                )

    def test_browser_workflow_provider_ignores_legacy_invalid_cloakbrowser_binary_path(
        self,
    ) -> None:
        env = {
            **CDP_ENV,
            config.CLOAKBROWSER_BINARY_PATH_ENV_VAR: "/definitely/missing/chrome",
        }
        with mock.patch.object(
            _cloakbrowser, "_dependency_available", return_value=True
        ):
            result = ScienceClient(DummyTransport(), env).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "ready")
        self.assertTrue(result.available)
        self.assertEqual(checks["runtime_env"].status, "ok")
        self.assertEqual(checks["runtime_env"].details["binary_path_configured"], True)
        self.assertEqual(checks["playwright_dependency"].status, "ok")

    def test_browser_workflow_provider_rejects_invalid_cloakbrowser_binary_path_for_managed_browser(
        self,
    ) -> None:
        env = {config.CLOAKBROWSER_BINARY_PATH_ENV_VAR: "/definitely/missing/chrome"}
        with mock.patch.object(
            _cloakbrowser, "_dependency_available", return_value=True
        ):
            result = ScienceClient(DummyTransport(), env).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "not_configured")
        self.assertFalse(result.available)
        self.assertEqual(checks["runtime_env"].status, "not_configured")
        self.assertIn("CLOAKBROWSER_BINARY_PATH", checks["runtime_env"].message)
        self.assertEqual(checks["runtime_env"].details["binary_path_configured"], True)
        self.assertEqual(checks["playwright_dependency"].status, "ok")

    def test_browser_workflow_provider_rejects_invalid_cdp_endpoint(self) -> None:
        env = {config.CLOAKBROWSER_CDP_ENDPOINT_ENV_VAR: "not-a-url"}
        with mock.patch.object(
            _cloakbrowser, "_dependency_available", return_value=True
        ):
            result = ScienceClient(DummyTransport(), env).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "not_configured")
        self.assertFalse(result.available)
        self.assertEqual(checks["runtime_env"].status, "not_configured")
        self.assertIn("CLOAKBROWSER_CDP_ENDPOINT", checks["runtime_env"].message)
        self.assertEqual(checks["runtime_env"].details["cdp_endpoint_configured"], True)
        self.assertEqual(checks["playwright_dependency"].status, "ok")

    def test_browser_workflow_providers_ignore_unrelated_rate_limit_env(self) -> None:
        for provider in ("science", "pnas", "acs", "aip", "royalsocietypublishing"):
            with self.subTest(provider=provider):
                env = {**CDP_ENV, "PAPER_FETCH_UNUSED_RATE_LIMIT_SECONDS": "60"}

                with mock.patch.object(
                    _cloakbrowser, "_dependency_available", return_value=True
                ):
                    result = self._browser_client(provider, env).probe_status()

                self.assertEqual(result.status, "ready")
                self.assertTrue(result.available)
                checks = {check.name: check for check in result.checks}
                self.assertNotIn("rate_limit_window", checks)

    def test_browser_workflow_providers_ready_status_checks_all_pass(self) -> None:
        for provider in ("science", "pnas", "acs", "aip", "royalsocietypublishing"):
            with (
                self.subTest(provider=provider),
                mock.patch.object(
                    _cloakbrowser, "_dependency_available", return_value=True
                ),
            ):
                result = self._browser_client(provider, dict(CDP_ENV)).probe_status()

                self.assertEqual(result.status, "ready")
                self.assertTrue(result.available)
                self.assertTrue(all(check.status == "ok" for check in result.checks))


if __name__ == "__main__":
    unittest.main()
