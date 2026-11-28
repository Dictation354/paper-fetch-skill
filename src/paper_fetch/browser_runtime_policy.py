"""Read-only browser selection facts shared by static discovery and runtime."""

from __future__ import annotations

import contextlib
import platform
import sys
from collections.abc import Mapping
from importlib import metadata
from pathlib import Path


def selected_backend(env: Mapping[str, str], *, provider: str) -> str:
    del env, provider
    return "scrapling"


def engine_name() -> str:
    return "chromium"


def supported_platform() -> bool:
    machine = platform.machine().lower()
    return (
        sys.platform in {"win32", "linux"}
        and machine in {"amd64", "x86_64", "aarch64", "arm64"}
    ) or (sys.platform == "darwin" and machine in {"x86_64", "arm64", "aarch64"})


BROWSER_PACKAGE_PINS = {
    "scrapling": "0.5.1",
    "patchright": "1.62.1",
    "playwright": "1.62.0",
}


def package_versions(site_packages: str | Path | None = None) -> dict[str, str]:
    if site_packages is not None:
        return {
            distribution.metadata["Name"].lower(): distribution.version
            for distribution in metadata.distributions(path=[str(site_packages)])
            if distribution.metadata["Name"].lower() in BROWSER_PACKAGE_PINS
        }
    versions = {}
    for name in BROWSER_PACKAGE_PINS:
        with contextlib.suppress(metadata.PackageNotFoundError):
            versions[name] = metadata.version(name)
    return versions
