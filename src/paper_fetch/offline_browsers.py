"""Shared post-install preparation for supported browser backends."""

from __future__ import annotations

import shlex
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from . import offline_setup as wizard

if TYPE_CHECKING:
    from .offline_setup import Setup


def prepare(setup: Setup, *, interactive: bool) -> None:
    if sys.platform == "linux":
        missing = {
            name: packages
            for name, packages in wizard.BROWSER_LIBRARIES.items()
            if wizard.library_status(name) == "missing"
        }
        for name in missing:
            setup.report(name, "missing")
        if missing and wizard.apt_supported():
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
    setup.step("Chromium", lambda: prepare_browser(setup))


def prepare_browser(setup: Setup) -> None:
    from .providers.browser_runtime.api import load_runtime_config, prepare_runtime
    from .providers.browser_runtime.context import browser_context

    setup.report(
        "Chromium", "preparing", "Using the Chromium revision pinned by Patchright"
    )
    config = load_runtime_config(
        setup.env, provider="pnas", doi="probe://browser/installation"
    )
    executable = prepare_runtime(replace(config, timeout_ms=600_000))
    with tempfile.TemporaryDirectory(prefix="paper-fetch-chromium-check-") as directory:
        with browser_context(
            replace(config, profile_dir=Path(directory), headless=True)
        ) as session:
            page = session.context.new_page()
            page.goto("about:blank")
            version = session.context.browser.version
    setup.report(
        "Chromium", "ready", f"Scrapling Chromium {version} launched: {executable}"
    )
