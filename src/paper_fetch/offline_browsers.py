"""Shared post-install preparation for supported browser backends."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from . import offline_flaresolverr as flaresolverr
from . import offline_setup as wizard
from .providers.browser_runtime.chrome import supported_platform

if TYPE_CHECKING:
    from .offline_setup import Setup


def selected_backends(selection: str) -> tuple[str, ...]:
    supported = ("Camoufox", "FlareSolverr") if supported_platform() else ("Camoufox",)
    return tuple(name for name in supported if selection in {"all", name.lower()})


def prepare(setup: Setup, *, selection: str, interactive: bool) -> None:
    backends = selected_backends(selection)
    if not backends:
        setup.report(
            "FlareSolverr", "skipped", "Only Windows/Linux x64; macOS uses Camoufox"
        )
        return
    if sys.platform == "linux":
        libraries = {}
        if "Camoufox" in backends:
            libraries.update(wizard.BROWSER_LIBRARIES)
        if "FlareSolverr" in backends:
            libraries.update(flaresolverr.CHROME_LIBRARIES)
        missing = {
            name: packages
            for name, packages in libraries.items()
            if wizard.library_status(name) == "missing"
        }
        for name in missing:
            setup.report(name, "missing")
        if "FlareSolverr" in backends:
            missing.update(
                flaresolverr.linux_missing(setup, flaresolverr.headless_mode(setup.env))
            )
        flaresolverr.install_linux_dependencies(setup, missing, interactive=interactive)
        remaining = {}
        if "FlareSolverr" in backends:
            remaining.update(
                flaresolverr.linux_missing(setup, flaresolverr.headless_mode(setup.env))
            )
        for name in missing:
            state = (
                wizard.library_status(name)
                if name in libraries
                else ("missing" if name in remaining else "ready")
            )
            setup.report(name, state)
            if state != "ready":
                remaining[name] = missing[name]
        if missing and not remaining:
            setup.report(
                "FlareSolverr dependencies", "ready", "System dependencies rechecked"
            )
    for backend in backends:
        if backend == "FlareSolverr":
            setup.step(
                "FlareSolverr",
                lambda: flaresolverr.prepare(
                    setup, interactive=interactive, system_dependencies=False
                ),
            )
        else:
            setup.step("Camoufox", lambda: setup.browser(selected=True))
