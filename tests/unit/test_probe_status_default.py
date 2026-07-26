from __future__ import annotations

import importlib.machinery
from typing import Any

from paper_fetch.provider_catalog import ProviderSpec
from paper_fetch.providers._registry import ProviderBundle
from paper_fetch.providers.base import ProviderClient
from paper_fetch.providers.browser_runtime.backends import camoufox as camoufox_backend
from paper_fetch.reason_codes import NOT_CONFIGURED, OK, READY


def _catalog(
    name: str,
    *,
    env_requirements: tuple[str, ...] = (),
    requires_playwright: bool = False,
    requires_browser_runtime: bool = False,
) -> ProviderSpec:
    return ProviderSpec(
        name=name,
        display_name=name.replace("_", " ").title(),
        official=True,
        domains=(),
        doi_prefixes=(),
        publisher_aliases=(),
        asset_default="none",
        probe_capability="routing_signal",
        provider_managed_abstract_only=False,
        client_factory_path="",
        status_order=999,
        env_requirements=env_requirements,
        requires_playwright=requires_playwright,
        requires_browser_runtime=requires_browser_runtime,
    )


def _install_catalog(monkeypatch: Any, catalog: ProviderSpec) -> None:
    bundle = ProviderBundle(catalog=catalog, sources=(catalog.name,))

    def fake_provider_bundle(name: str) -> ProviderBundle:
        assert name == catalog.name
        return bundle

    monkeypatch.setattr(
        "paper_fetch.providers._registry.provider_bundle", fake_provider_bundle
    )


def _client(catalog: ProviderSpec, env: dict[str, str] | None = None) -> ProviderClient:
    client = ProviderClient()
    client.name = catalog.name
    client.env = dict(env or {})
    return client


def test_default_probe_status_without_requirements_is_ready(monkeypatch: Any) -> None:
    catalog = _catalog("s10_plain")
    _install_catalog(monkeypatch, catalog)

    result = _client(
        catalog,
        env={"PAPER_FETCH_BROWSER_BACKEND": "camoufox"},
    ).probe_status()

    assert result.status == READY
    assert result.available is True
    assert result.missing_env == []
    assert [(check.name, check.status) for check in result.checks] == [
        ("local_requirements", OK)
    ]


def test_default_probe_status_reports_missing_env(monkeypatch: Any) -> None:
    catalog = _catalog("s10_env_missing", env_requirements=("S10_REQUIRED_TOKEN",))
    _install_catalog(monkeypatch, catalog)

    result = _client(
        catalog,
        env={"PAPER_FETCH_BROWSER_BACKEND": "camoufox"},
    ).probe_status()

    assert result.status == NOT_CONFIGURED
    assert result.available is False
    assert result.missing_env == ["S10_REQUIRED_TOKEN"]
    assert result.checks[0].name == "environment"
    assert result.checks[0].status == NOT_CONFIGURED


def test_default_probe_status_env_present_is_ready(monkeypatch: Any) -> None:
    catalog = _catalog("s10_env_ready", env_requirements=("S10_REQUIRED_TOKEN",))
    _install_catalog(monkeypatch, catalog)

    result = _client(
        catalog,
        env={"S10_REQUIRED_TOKEN": "configured"},
    ).probe_status()

    assert result.status == READY
    assert result.available is True
    assert result.missing_env == []
    assert result.checks[0].status == OK


def test_default_probe_status_checks_playwright_requirement(monkeypatch: Any) -> None:
    catalog = _catalog(
        "s10_playwright_requirement",
        requires_playwright=True,
    )
    _install_catalog(monkeypatch, catalog)
    find_spec_calls: list[str] = []

    def fake_find_spec(name: str):
        find_spec_calls.append(name)
        return importlib.machinery.ModuleSpec(name, loader=None)

    monkeypatch.setattr(
        "paper_fetch.providers.base.importlib.util.find_spec", fake_find_spec
    )
    result = _client(
        catalog,
        env={"PAPER_FETCH_BROWSER_BACKEND": "camoufox"},
    ).probe_status()

    checks = {check.name: check for check in result.checks}
    assert result.status == READY
    assert checks["playwright"].status == OK
    assert find_spec_calls[0] == "playwright.sync_api"


def test_default_probe_status_checks_browser_runtime_without_launch(
    monkeypatch: Any,
) -> None:
    catalog = _catalog(
        "s10_browser_runtime",
        requires_browser_runtime=True,
    )
    _install_catalog(monkeypatch, catalog)
    monkeypatch.setattr(
        camoufox_backend,
        "_dependency_details",
        lambda: {
            "probe": "unit_test",
            "packages": {"playwright": True, "camoufox": True},
        },
    )

    result = _client(
        catalog,
        env={"PAPER_FETCH_BROWSER_BACKEND": "camoufox"},
    ).probe_status()

    checks = {check.name: check for check in result.checks}
    assert result.status == READY
    assert checks["browser_runtime"].status == OK
    assert checks["browser_runtime"].details["probe"] == (
        "paper_fetch.providers.browser_runtime.probe_runtime_status"
    )
    assert [check["name"] for check in checks["browser_runtime"].details["checks"]] == [
        "runtime_env",
        "playwright_dependency",
    ]
