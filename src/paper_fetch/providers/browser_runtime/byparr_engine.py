"""Engine and protocol pairing for the pinned Byparr source adapter."""

from __future__ import annotations

import importlib
import importlib.metadata

from paper_fetch.browser_runtime_policy import engine_name as engine_name


def playwright_api(*, asynchronous: bool = False):
    # Extraction and async management use one exact host protocol installation.
    package = "playwright"
    return importlib.import_module(
        package + (".async_api" if asynchronous else ".sync_api")
    )


def prepare_executable(binary_path: str | None = None) -> str | None:
    if engine_name() == "invisible":
        from invisible_playwright._engine import resolve_executable

        return str(resolve_executable(binary_path))
    from .preparation import _launch_executable_path

    return _launch_executable_path(binary_path)


def engine_package_versions(site_packages=None) -> dict[str, str]:
    """Read the selected engine from the actual installed distribution inventory."""
    inventory = {
        str(dist.metadata["Name"]).lower().replace("_", "-"): dist.version
        for dist in (
            importlib.metadata.distributions(path=[str(site_packages)])
            if site_packages
            else importlib.metadata.distributions()
        )
    }
    names = (
        ("invisible-playwright", "invisible-core")
        if engine_name() == "invisible"
        else ("camoufox",)
    )
    excluded = (
        ("camoufox",)
        if engine_name() == "invisible"
        else ("invisible-playwright", "invisible-core")
    )
    if any(name in inventory for name in excluded):
        raise RuntimeError(f"Unexpected browser engine packages: {excluded}")
    return {name: inventory[name] for name in (*names, "playwright")}


def verify_package_installation() -> None:
    """Installer smoke: verify selected packages without downloading a browser."""
    engine_package_versions()
    from .backends.byparr import DEFAULT_BYPARR_BACKEND

    config = DEFAULT_BYPARR_BACKEND.load_runtime_config(
        {}, provider="pnas", doi="probe://install"
    )
    DEFAULT_BYPARR_BACKEND.ensure_runtime_ready(config)
    importlib.import_module(
        "invisible_playwright" if engine_name() == "invisible" else "camoufox"
    )
