"""Shared post-install preparation for supported browser backends."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from . import offline_flaresolverr as flaresolverr
from . import offline_setup as wizard
from .providers.browser_runtime.chrome import supported_platform

if TYPE_CHECKING:
    from .offline_setup import Setup


def prepare(setup: Setup, *, selection: str, interactive: bool) -> None:
    backends = (
        (("camoufox", "flaresolverr") if supported_platform() else ("camoufox",))
        if selection == "all"
        else (selection,)
    )
    if sys.platform == "linux":
        libraries = {}
        if "camoufox" in backends:
            libraries.update(wizard.BROWSER_LIBRARIES)
        if "flaresolverr" in backends and supported_platform():
            libraries.update(flaresolverr.CHROME_LIBRARIES)
        missing = {
            name: packages
            for name, packages in libraries.items()
            if wizard.library_status(name) == "missing"
        }
        if "flaresolverr" in backends and supported_platform():
            missing.update(
                flaresolverr.linux_missing(setup, flaresolverr.headless_mode(setup.env))
            )
        flaresolverr.install_linux_dependencies(setup, missing, interactive=interactive)
    for backend in backends:
        if backend == "flaresolverr":
            setup.step(
                "FlareSolverr",
                lambda: (
                    flaresolverr.prepare(
                        setup, interactive=interactive, system_dependencies=False
                    )
                    if selection == "all"
                    else flaresolverr.prepare(setup, interactive=interactive)
                ),
            )
        else:
            setup.step("Camoufox", lambda: setup.browser(selected=True))
