"""Platform package markers and selected-engine dependency boundaries."""

import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest
from packaging.requirements import Requirement

from paper_fetch import browser_runtime_policy as policy
from paper_fetch.providers.browser_runtime import preparation

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("extra", ["browser", "full"])
@pytest.mark.parametrize("python", ["3.11", "3.12", "3.13", "3.14"])
@pytest.mark.parametrize(
    "system,machine",
    [
        (system, machine)
        for system, machines in (
            ("linux", ("x86_64", "AMD64", "amd64", "arm64", "aarch64")),
            ("win32", ("AMD64", "amd64", "x86_64", "arm64", "aarch64")),
            ("darwin", ("arm64", "aarch64", "x86_64")),
        )
        for machine in machines
    ],
)
def test_supported_platforms_use_pinned_chromium_packages(
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
    assert policy.supported_platform()
    assert policy.engine_name() == "chromium"
    for name, version in preparation.BROWSER_PACKAGE_PINS.items():
        assert str(active[name].specifier) == f"=={version}"
        assert active[name].marker is None
    assert active["scrapling"].extras == {"fetchers"}
    assert {"camoufox", "invisible-playwright", "invisible-core"}.isdisjoint(active)
