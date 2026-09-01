from __future__ import annotations

import unittest
from unittest import mock

from paper_fetch import config
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
from paper_fetch.providers.browser_runtime.backends import camoufox as camoufox_backend

CAMOUFOX_ENV = {}
CAMOUFOX_DEPENDENCIES_READY = {
    "probe": "unit_test",
    "packages": {"playwright": True, "camoufox": True},
    "package_ready": True,
    "runtime_installed": True,
    "download_required": False,
}
CAMOUFOX_DEPENDENCIES_MISSING = {
    "probe": "unit_test",
    "packages": {"playwright": False, "camoufox": False},
    "package_ready": False,
    "runtime_installed": False,
    "download_required": False,
}


class DummyTransport:
    pass


class ProviderStatusTests(unittest.TestCase):
    def _browser_client(self, provider: str, env: dict[str, str]):
        if provider == "acs":
            return AcsClient(DummyTransport(), env)
        if provider == "aip":
            return AipClient(DummyTransport(), env)
        if provider == "ams":
            return AmsClient(DummyTransport(), env)
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

    def test_wiley_browser_runtime_ready_with_camoufox(self) -> None:
        with mock.patch.object(
            camoufox_backend,
            "_dependency_details",
            return_value=CAMOUFOX_DEPENDENCIES_READY,
        ):
            result = WileyClient(DummyTransport(), dict(CAMOUFOX_ENV)).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "ready")
        self.assertTrue(result.available)
        self.assertEqual(result.missing_env, [])
        self.assertEqual(checks["runtime_env"].status, "ok")
        self.assertEqual(checks["playwright_dependency"].status, "ok")
        self.assertEqual(checks["tdm_api_token"].status, "ok")

    def test_wiley_missing_runtime_and_token_is_not_configured_when_camoufox_is_missing(
        self,
    ) -> None:
        with mock.patch.object(
            camoufox_backend,
            "_dependency_details",
            return_value=CAMOUFOX_DEPENDENCIES_MISSING,
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
            camoufox_backend,
            "_dependency_details",
            return_value=CAMOUFOX_DEPENDENCIES_MISSING,
        ):
            result = WileyClient(
                DummyTransport(),
                {**CAMOUFOX_ENV, WILEY_TDM_CLIENT_TOKEN_ENV_VAR: "secret"},
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
        env = {**CAMOUFOX_ENV, WILEY_TDM_CLIENT_TOKEN_ENV_VAR: "secret"}
        with mock.patch.object(
            camoufox_backend,
            "_dependency_details",
            return_value=CAMOUFOX_DEPENDENCIES_READY,
        ):
            result = WileyClient(DummyTransport(), env).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "ready")
        self.assertTrue(result.available)
        self.assertTrue(all(check.status == "ok" for check in checks.values()))

    def test_browser_workflow_providers_are_ready_with_camoufox(self) -> None:
        for provider in (
            "science",
            "pnas",
            "acs",
            "aip",
            "ams",
            "royalsocietypublishing",
        ):
            with (
                self.subTest(provider=provider),
                mock.patch.object(
                    camoufox_backend,
                    "_dependency_details",
                    return_value=CAMOUFOX_DEPENDENCIES_READY,
                ),
            ):
                result = self._browser_client(
                    provider, dict(CAMOUFOX_ENV)
                ).probe_status()
                checks = {check.name: check for check in result.checks}

                self.assertEqual(result.status, "ready")
                self.assertTrue(result.available)
                self.assertEqual(result.missing_env, [])
                self.assertEqual(checks["runtime_env"].status, "ok")
                self.assertEqual(checks["playwright_dependency"].status, "ok")

    def test_ams_status_reports_browser_runtime_requirement(self) -> None:
        with mock.patch.object(
            camoufox_backend,
            "_dependency_details",
            return_value=CAMOUFOX_DEPENDENCIES_READY,
        ) as dependency:
            result = AmsClient(DummyTransport(), dict(CAMOUFOX_ENV)).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "ready")
        self.assertTrue(result.available)
        self.assertEqual(result.missing_env, [])
        self.assertEqual(checks["runtime_env"].status, "ok")
        self.assertEqual(checks["playwright_dependency"].status, "ok")
        dependency.assert_called_once()

    def test_browser_workflow_providers_missing_camoufox_are_not_configured(
        self,
    ) -> None:
        for provider in (
            "science",
            "pnas",
            "acs",
            "aip",
            "ams",
            "royalsocietypublishing",
        ):
            with (
                self.subTest(provider=provider),
                mock.patch.object(
                    camoufox_backend,
                    "_dependency_details",
                    return_value=CAMOUFOX_DEPENDENCIES_MISSING,
                ),
            ):
                result = self._browser_client(provider, {}).probe_status()
                checks = {check.name: check for check in result.checks}

                self.assertEqual(result.status, "not_configured")
                self.assertEqual(checks["runtime_env"].status, "not_configured")
                self.assertEqual(
                    checks["playwright_dependency"].status, "not_configured"
                )

    def test_browser_workflow_provider_rejects_invalid_camoufox_binary_path(
        self,
    ) -> None:
        env = {
            **CAMOUFOX_ENV,
            config.BROWSER_BINARY_PATH_ENV_VAR: "/definitely/missing/camoufox",
        }
        with mock.patch.object(
            camoufox_backend,
            "_dependency_details",
            return_value=CAMOUFOX_DEPENDENCIES_READY,
        ):
            result = ScienceClient(DummyTransport(), env).probe_status()
        checks = {check.name: check for check in result.checks}

        self.assertEqual(result.status, "not_configured")
        self.assertFalse(result.available)
        self.assertEqual(checks["runtime_env"].status, "not_configured")
        self.assertIn(config.BROWSER_BINARY_PATH_ENV_VAR, checks["runtime_env"].message)
        self.assertEqual(checks["playwright_dependency"].status, "ok")

    def test_browser_workflow_providers_ignore_unrelated_rate_limit_env(self) -> None:
        for provider in ("science", "pnas", "acs", "aip", "royalsocietypublishing"):
            with self.subTest(provider=provider):
                env = {
                    **CAMOUFOX_ENV,
                    "PAPER_FETCH_UNUSED_RATE_LIMIT_SECONDS": "60",
                }

                with mock.patch.object(
                    camoufox_backend,
                    "_dependency_details",
                    return_value=CAMOUFOX_DEPENDENCIES_READY,
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
                    camoufox_backend,
                    "_dependency_details",
                    return_value=CAMOUFOX_DEPENDENCIES_READY,
                ),
            ):
                result = self._browser_client(
                    provider, dict(CAMOUFOX_ENV)
                ).probe_status()

                self.assertEqual(result.status, "ready")
                self.assertTrue(result.available)
                self.assertTrue(all(check.status == "ok" for check in result.checks))


if __name__ == "__main__":
    unittest.main()
