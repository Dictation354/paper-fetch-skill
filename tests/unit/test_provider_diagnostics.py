from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest
from pydantic import ValidationError

from paper_fetch import config
from paper_fetch.diagnostics import (
    doctor_payload,
    provider_status_payload,
    selected_provider_status_names,
)
from paper_fetch.http import HttpTransport
from paper_fetch.mcp.schemas import ProviderStatusRequest
from paper_fetch.provider_catalog import PROVIDER_CATALOG, provider_status_order
from paper_fetch.providers.base import (
    ProviderStatusResult,
    build_provider_status_check,
)


class _StaticClient:
    def __init__(self, provider: str, *, failure: Exception | None = None) -> None:
        self.provider = provider
        self.official_provider = PROVIDER_CATALOG[provider].official
        self.failure = failure
        self.calls = 0

    def probe_status(self) -> ProviderStatusResult:
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        return ProviderStatusResult(
            provider=self.provider,
            status="ready",
            available=True,
            official_provider=self.official_provider,
            checks=[
                build_provider_status_check(
                    "local_requirements",
                    "ok",
                    "Static requirements are ready.",
                )
            ],
        )


def _clients() -> dict[str, _StaticClient]:
    return {name: _StaticClient(name) for name in provider_status_order()}


def _payload(
    tmp_path: Path,
    *,
    clients: dict[str, _StaticClient] | None = None,
    **kwargs,
):
    active_clients = clients or _clients()
    with mock.patch.object(config, "DEFAULT_USER_ENV_FILE", tmp_path / "missing.env"):
        return provider_status_payload(
            **kwargs,
            build_runtime_env_fn=lambda env=None, **_kwargs: dict(env or {}),
            build_clients_fn=lambda **_kwargs: active_clients,
            image_probe_fn=lambda _env: {
                "ghostscript": {
                    "status": "ready",
                    "available": True,
                    "reason_code": "image_conversion_backend_ready",
                },
                "libvips": {
                    "status": "not_configured",
                    "available": False,
                    "reason_code": "image_conversion_backend_missing",
                },
            },
            browser_probe_fn=lambda _env, **_kwargs: {
                "diagnostic_scope": "static_configuration_and_local_dependencies",
                "live_checked": False,
            },
        )


def test_default_provider_status_preserves_full_all_provider_contract(
    tmp_path: Path,
) -> None:
    payload = _payload(tmp_path)

    assert payload["detail"] == "full"
    assert payload["live_network_checked"] is False
    assert payload["remote_publisher_health"] == "not_checked"
    assert [item["provider"] for item in payload["providers"]] == list(
        provider_status_order()
    )
    assert all(item["checks"] for item in payload["providers"])
    assert payload["configuration"]["precedence"] == [
        "process_env",
        "explicit_env_file",
        "env_var_file",
        "user_config",
        "default",
    ]
    assert payload["local_capabilities"]["browser"]["live_checked"] is False


def test_single_provider_compact_only_returns_routing_fields(tmp_path: Path) -> None:
    clients = _clients()

    payload = _payload(
        tmp_path,
        clients=clients,
        provider="wiley",
        detail="compact",
    )

    assert payload["provider_filter"] == "wiley"
    assert payload["providers"] == [
        {
            "provider": "wiley",
            "status": "ready",
            "reason_code": "static_requirements_ready",
            "reason": "Static configuration and local dependencies are ready; remote access was not checked.",
            "suggested_action": "paper-fetch browser-preflight --provider wiley",
        }
    ]
    assert "configuration" not in payload
    assert "local_capabilities" not in payload
    assert clients["wiley"].calls == 1
    assert sum(client.calls for client in clients.values()) == 1


def test_single_provider_status_only_constructs_selected_client(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}
    client = _StaticClient("wiley")

    def selected_clients(**kwargs):
        captured.update(kwargs)
        return {"wiley": client}

    with mock.patch.object(config, "DEFAULT_USER_ENV_FILE", tmp_path / "missing.env"):
        payload = provider_status_payload(
            provider="wiley",
            detail="compact",
            build_runtime_env_fn=lambda env=None, **_kwargs: dict(env or {}),
            build_clients_fn=selected_clients,
            image_probe_fn=lambda _env: {},
            browser_probe_fn=lambda _env, **_kwargs: {},
        )

    assert captured["provider_names"] == ("wiley",)
    assert [item["provider"] for item in payload["providers"]] == ["wiley"]


def test_browser_group_is_catalog_derived_and_filtered(tmp_path: Path) -> None:
    payload = _payload(tmp_path, group="browser", detail="compact")

    expected = [
        name
        for name in provider_status_order()
        if any(
            route.browser_required or route.browser_optional
            for route in PROVIDER_CATALOG[name].routes
        )
    ]
    assert [item["provider"] for item in payload["providers"]] == expected
    assert selected_provider_status_names(group="browser") == tuple(expected)


def test_provider_status_never_uses_the_network(tmp_path: Path) -> None:
    transport = HttpTransport()
    with (
        mock.patch.object(config, "DEFAULT_USER_ENV_FILE", tmp_path / "missing.env"),
        mock.patch.object(
            transport,
            "request",
            side_effect=AssertionError("provider_status must remain network-free"),
        ) as request,
    ):
        payload = provider_status_payload(
            detail="compact",
            env={},
            transport=transport,
            build_runtime_env_fn=lambda env=None, **_kwargs: dict(env or {}),
        )

    assert len(payload["providers"]) == len(provider_status_order())
    request.assert_not_called()


@pytest.mark.parametrize(
    "request_data",
    [
        {"provider": "unknown"},
        {"group": "unknown"},
        {"detail": "verbose"},
        {"provider": "crossref", "group": "browser"},
    ],
)
def test_invalid_provider_status_filters_fail_request_validation(
    request_data: dict[str, str],
) -> None:
    with pytest.raises(ValidationError):
        ProviderStatusRequest.model_validate(request_data)


def test_configuration_sources_never_expose_secret_values(tmp_path: Path) -> None:
    secret = "provider-secret-that-must-not-leak"
    clients = _clients()
    clients["elsevier"] = _StaticClient(
        "elsevier", failure=RuntimeError(f"unexpected {secret}")
    )

    payload = _payload(
        tmp_path,
        clients=clients,
        provider="elsevier",
        detail="full",
        env={"ELSEVIER_API_KEY": secret},
    )

    serialized = json.dumps(payload)
    assert secret not in serialized
    values = {item["name"]: item for item in payload["configuration"]["values"]}
    assert values["ELSEVIER_API_KEY"] == {
        "name": "ELSEVIER_API_KEY",
        "source": "process_env",
        "present": True,
        "uses_default": False,
        "sensitive": True,
    }
    assert payload["providers"][0]["checks"][0]["message"] == (
        "Provider diagnostics failed unexpectedly (RuntimeError)."
    )


def test_doctor_includes_install_provenance_without_live_checks(tmp_path: Path) -> None:
    provenance = {
        "status": "not_applicable",
        "reason_code": "source_development_without_offline_manifest",
    }
    with (
        mock.patch(
            "paper_fetch.diagnostics.provider_status_payload",
            return_value=_payload(tmp_path, provider="crossref", detail="compact"),
        ),
        mock.patch(
            "paper_fetch.diagnostics.install_provenance_payload",
            return_value=provenance,
        ) as build_provenance,
    ):
        report = doctor_payload(provider="crossref", detail="compact")

    assert report["status"] == "ready"
    assert report["live_network_checked"] is False
    assert report["install_provenance"] == provenance
    build_provenance.assert_called_once_with(install_root=None)


def test_doctor_promotes_provenance_drift_to_degraded(tmp_path: Path) -> None:
    with (
        mock.patch(
            "paper_fetch.diagnostics.provider_status_payload",
            return_value=_payload(tmp_path, provider="crossref", detail="compact"),
        ),
        mock.patch(
            "paper_fetch.diagnostics.install_provenance_payload",
            return_value={"status": "drift", "reason_code": "version_mismatch"},
        ),
    ):
        report = doctor_payload(
            provider="crossref",
            detail="compact",
            install_root=tmp_path,
        )

    assert report["status"] == "degraded"
