"""Platform package markers and selected-engine dependency boundaries."""

import builtins
import json
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest
from packaging.requirements import Requirement

from paper_fetch import browser_runtime_policy as policy
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers.browser_runtime import byparr_engine, preparation
from paper_fetch.providers.browser_runtime.backends import byparr

_REAL_DETAILS = byparr._dependency_details
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("extra", ["browser", "full"])
@pytest.mark.parametrize("python", ["3.11", "3.12", "3.13", "3.14"])
@pytest.mark.parametrize(
    "system,machine",
    [
        (system, machine)
        for system, machines in (
            ("linux", ("x86_64", "AMD64", "amd64", "arm64", "aarch64")),
            ("win32", ("AMD64", "amd64", "x86_64")),
            ("darwin", ("arm64", "aarch64", "x86_64")),
        )
        for machine in machines
    ],
)
def test_platform_dependencies_are_exclusive(
    extra, python, system, machine, monkeypatch
):
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    env = {
        "sys_platform": system,
        "platform_machine": machine,
        "python_version": python,
        "python_full_version": python + ".0",
    }
    requirements = [
        Requirement(value)
        for value in project["project"]["optional-dependencies"][extra]
    ]
    active = {r.name: r for r in requirements if not r.marker or r.marker.evaluate(env)}
    monkeypatch.setattr(policy, "sys", SimpleNamespace(platform=system))
    monkeypatch.setattr(policy, "platform", SimpleNamespace(machine=lambda: machine))
    invisible = policy.engine_name() == "invisible"
    assert ("camoufox" in active) is not invisible
    assert ("invisible-playwright" in active) is invisible
    assert ("invisible-core" in active) is invisible
    assert ("1.65.2" in active["playwright"].specifier) is invisible
    assert "1.62.0" in active["playwright"].specifier
    shared = json.loads(policy.BYPARR_MANIFEST_PATH.read_text())
    shared_active = {
        r.name: r
        for r in map(Requirement, shared["shared_packages"])
        if not r.marker or r.marker.evaluate(env)
    }
    for name in ("camoufox", "invisible-playwright", "invisible-core", "playwright"):
        assert (name in shared_active) == (name in active)
        if name in active:
            assert shared_active[name].specifier == active[name].specifier


@pytest.mark.parametrize(
    "missing,version",
    [
        ("invisible_core", "61.62.0"),
        ("invisible_playwright", "0.49.1"),
        (None, "61.61.0"),
        (None, "61.62.0"),
    ],
)
def test_invisible_status_and_readiness_never_touch_camoufox(
    monkeypatch, tmp_path, missing, version
):
    from importlib import metadata, util

    monkeypatch.setattr(byparr_engine, "engine_name", lambda: "invisible")
    monkeypatch.setattr(byparr, "_dependency_details", _REAL_DETAILS)
    monkeypatch.setattr(
        byparr, "_camoufox_dependency_details", lambda: pytest.fail("Camoufox probe")
    )
    versions = {
        "playwright": "1.65.2",
        "invisible_core": version,
        "invisible_playwright": "0.49.1",
    }
    monkeypatch.setattr(metadata, "version", versions.__getitem__)
    monkeypatch.setattr(
        util, "find_spec", lambda name: None if name == missing else object()
    )
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        assert not (name == "camoufox" or name.startswith("camoufox."))
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    backend = byparr.DEFAULT_BYPARR_BACKEND
    config = backend.load_runtime_config(
        {"XDG_DATA_HOME": str(tmp_path)}, provider="pnas", doi="probe://deps"
    )
    result = backend.probe_runtime_status(
        {"XDG_DATA_HOME": str(tmp_path)}, provider="pnas"
    )
    check = next(c for c in result.checks if c.name == "playwright_dependency")
    ready = missing is None and version == "61.62.0"
    assert check.details["package_ready"] is ready
    assert "camoufox" not in check.details["packages"]
    assert "Invisible" in check.message
    if ready:
        backend.ensure_runtime_ready(config)
    else:
        with pytest.raises(ProviderFailure):
            backend.ensure_runtime_ready(config)


def test_invisible_preparation_skips_camoufox_packages_and_models(monkeypatch):
    monkeypatch.setattr(byparr_engine, "engine_name", lambda: "invisible")
    monkeypatch.setattr(
        preparation, "find_spec", lambda _: pytest.fail("Camoufox dependency lookup")
    )
    preparation.FetchBrowserPreparation().require()


@pytest.mark.parametrize("engine", ["invisible", "camoufox"])
def test_package_inventory_uses_target_directory_and_rejects_other_engine(
    monkeypatch, tmp_path, engine
):
    from importlib import metadata

    monkeypatch.setattr(byparr_engine, "engine_name", lambda: engine)
    inventory = {
        "playwright": "1.65.2",
        **(
            {"invisible-playwright": "0.49.1", "invisible-core": "61.62.0"}
            if engine == "invisible"
            else {"camoufox": "0.5.9"}
        ),
    }

    def distributions(*, path):
        assert path == [str(tmp_path)]
        return [
            SimpleNamespace(metadata={"Name": name}, version=value)
            for name, value in inventory.items()
        ]

    monkeypatch.setattr(metadata, "distributions", distributions)
    assert byparr_engine.engine_package_versions(tmp_path) == inventory
    inventory["camoufox" if engine == "invisible" else "invisible-core"] = "wrong"
    with pytest.raises(RuntimeError, match="Unexpected browser engine"):
        byparr_engine.engine_package_versions(tmp_path)
