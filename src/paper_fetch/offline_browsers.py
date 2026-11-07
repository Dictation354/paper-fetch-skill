"""Shared post-install preparation for supported browser backends."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from . import offline_byparr as byparr
from . import offline_setup as wizard

if TYPE_CHECKING:
    from .offline_setup import Setup


def selected_backends(selection: str) -> tuple[str, ...]:
    return ("Byparr",) if selection in {"all", "camoufox", "byparr"} else ()


def prepare(setup: Setup, *, selection: str, interactive: bool) -> None:
    backends = selected_backends(selection)
    if not backends:
        setup.report("Byparr", "skipped", "Only Windows/Linux x64; macOS uses Camoufox")
        return
    if sys.platform == "linux":
        missing = {
            name: packages
            for name, packages in wizard.BROWSER_LIBRARIES.items()
            if wizard.library_status(name) == "missing"
        }
        for name in missing:
            setup.report(name, "missing")
        if missing and wizard.apt_supported():
            import shlex

            packages = [
                wizard.apt_package(candidates) for candidates in missing.values()
            ]
            command = [
                "sudo",
                "apt-get",
                "install",
                "--",
                *sorted({p for p in packages if p}),
            ]
            setup.report(
                "Browser libraries", "installation available", shlex.join(command)
            )
            if (
                len(command) > 4
                and interactive
                and wizard.confirm(
                    "Install browser system libraries? Network, system directories; sudo alone receives your password.\n"
                    + shlex.join(command)
                )
            ):
                setup.install_packages("Browser libraries", command)
        elif missing:
            setup.report(
                "Browser libraries",
                "missing",
                "Use your distribution's package manager to provide: "
                + ", ".join(missing),
            )
        if missing:
            for name in missing:
                setup.report(name, wizard.library_status(name))
            if all(wizard.library_status(name) == "ready" for name in missing):
                setup.report(
                    "Browser libraries", "ready", "System dependencies rechecked"
                )
    for backend in backends:
        if backend == "Byparr":
            setup.step(
                "Byparr",
                lambda: byparr.prepare(
                    setup, interactive=interactive, system_dependencies=False
                ),
            )
        else:
            setup.step("Camoufox", lambda: setup.browser(selected=True))
