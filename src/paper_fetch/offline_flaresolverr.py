"""Post-install FlareSolverr preparation; system changes always require consent."""

from __future__ import annotations

from contextlib import suppress
from importlib.util import find_spec
import os
from pathlib import Path
import platform
import shlex
import shutil
import sys
import tempfile
from typing import TYPE_CHECKING

from . import offline_setup as wizard
from .config import BROWSER_HEADLESS_ENV_VAR, browser_env_value, resolve_user_data_dir
from .providers.browser_runtime import flaresolverr_preparation as preparation
from .providers.browser_runtime.chrome import (
    CHROME_DOWNLOAD_URL,
    CHROME_ENV,
    SystemChrome,
    discover_chrome,
    supported_platform,
)
from .providers.browser_runtime.flaresolverr_manager import (
    FlareSolverrManager,
    linux_launch_prefix,
)
from .providers.browser_runtime.types import BrowserRuntimeConfig, BrowserRuntimeFailure

if TYPE_CHECKING:
    from .offline_setup import Setup

CHROME_DEB_URL = (
    "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
)
# Reuse SONAME detection and APT candidate resolution without requiring Firefox-only libs.
CHROME_LIBRARIES = {
    name: packages
    for name, packages in wizard.BROWSER_LIBRARIES.items()
    if name not in {"libdbus-glib-1.so.2", "libXt.so.6"}
} | {
    "libnss3.so": ("libnss3",),
    "libnspr4.so": ("libnspr4",),
    "libatk-1.0.so.0": ("libatk1.0-0t64", "libatk1.0-0"),
    "libatk-bridge-2.0.so.0": ("libatk-bridge2.0-0t64", "libatk-bridge2.0-0"),
    "libcups.so.2": ("libcups2t64", "libcups2"),
    "libdrm.so.2": ("libdrm2",),
    "libgbm.so.1": ("libgbm1",),
    "libxkbcommon.so.0": ("libxkbcommon0",),
    "libpango-1.0.so.0": ("libpango-1.0-0",),
    "libudev.so.1": ("libudev1",),
}


def headless_mode(env: dict[str, str]) -> bool:
    return (
        browser_env_value(env, BROWSER_HEADLESS_ENV_VAR) or ""
    ).strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def linux_missing(setup: Setup, headless: bool) -> dict[str, tuple[str, ...]]:
    missing = {}
    for soname, packages in CHROME_LIBRARIES.items():
        state = wizard.library_status(soname)
        if state != "ready":
            setup.report(soname, state)
        if state == "missing":
            missing[soname] = packages
    if headless and shutil.which("Xvfb") is None:
        missing["Xvfb"] = ("xvfb",)
    sockets = Path("/tmp/.X11-unix")
    if headless and sockets.exists() and not os.access(sockets, os.W_OK):
        if shutil.which("bwrap") is None:
            missing["bubblewrap (read-only X11 sockets)"] = ("bubblewrap",)
    for name in missing:
        setup.report(name, "missing")
    return missing


def install_linux_dependencies(setup: Setup, missing, *, interactive: bool) -> None:
    if not missing:
        return
    if not wizard.apt_supported():
        setup.report(
            "FlareSolverr dependencies",
            "missing",
            "Use your distribution's package manager to provide: " + ", ".join(missing),
        )
        return
    packages = []
    for name, candidates in missing.items():
        package = wizard.apt_package(candidates)
        if package:
            packages.append(package)
        else:
            setup.report(
                name, "missing", "APT candidate unavailable: " + " / ".join(candidates)
            )
    if not packages:
        return
    command = ["sudo", "apt-get", "install", "--", *sorted(set(packages))]
    setup.report(
        "FlareSolverr dependencies", "installation available", shlex.join(command)
    )
    if interactive and wizard.confirm(
        "Install missing FlareSolverr system dependencies? Network, system directories; "
        "sudo alone receives your password.\n" + shlex.join(command)
    ):
        setup.install_packages("FlareSolverr dependencies", command)


def install_linux_chrome(setup: Setup, *, interactive: bool) -> None:
    if not wizard.apt_supported():
        setup.report(
            "Chrome",
            "missing",
            "Install Google Chrome 115+ with your distribution's "
            "package manager: " + CHROME_DOWNLOAD_URL,
        )
        return
    package = wizard.apt_package(("google-chrome-stable",))
    command = [
        "sudo",
        "apt-get",
        "install",
        "--",
        package or "<downloaded-google-chrome.deb>",
    ]
    detail = shlex.join(command)
    if not package:
        detail += "\nDownload official x86-64 deb: " + CHROME_DEB_URL
    setup.report("Chrome", "installation available", detail)
    if not interactive or not wizard.confirm(
        "Install Google Chrome? Network, system directories; sudo alone receives your password.\n"
        + detail
    ):
        return
    if package:
        setup.install_packages("Chrome", command)
    else:
        with tempfile.TemporaryDirectory(prefix="paper-fetch-chrome-") as directory:
            root = Path(directory)
            root.chmod(0o755)
            deb = root / "google-chrome-stable_current_amd64.deb"
            preparation.download(
                CHROME_DEB_URL, deb, preparation.PreparationBudget(600)
            )
            deb.chmod(0o644)
            setup.install_packages("Chrome", [*command[:-1], str(deb)])


def local_check(
    env: dict[str, str],
    chrome: SystemChrome,
    runtime: Path,
    driver: Path,
    version: str,
) -> None:
    """Launch the existing owner with temporary state and a separate two-minute budget."""
    with tempfile.TemporaryDirectory(
        prefix="paper-fetch-flaresolverr-check-"
    ) as directory:
        config = BrowserRuntimeConfig(
            provider="pnas",
            doi="check://installation",
            artifact_dir=Path(directory),
            headless=headless_mode(env),
            user_agent=None,
            timeout_ms=120000,
            storage_state_path=None,
            user_data_dir=Path(directory),
            persist_storage_state=False,
            backend="flaresolverr",
            chrome_binary_path=chrome.path,
        )
        manager = FlareSolverrManager(config, local_check=True)
        try:
            context = manager.new_context(prepared=(chrome, runtime, driver, version))
            context.route("**/*", lambda route: route.abort())
            page = context.new_page()
            page.goto("about:blank", timeout=int(manager.budget.remaining() * 1000))
            page.wait_for_function(
                "() => 1 + 1 === 2",
                timeout=max(1, int(manager.budget.remaining() * 1000)),
            )
            manager.budget.check()
        finally:
            manager.close()


def prepare(
    setup: Setup, *, interactive: bool, system_dependencies: bool = True
) -> None:
    try:
        _prepare(
            setup, interactive=interactive, system_dependencies=system_dependencies
        )
    except (KeyboardInterrupt, EOFError):
        setup.report(
            "FlareSolverr", "not ready", "Cancelled; core installation is preserved"
        )
    except BrowserRuntimeFailure as exc:
        setup.report(
            "FlareSolverr", "not ready", exc.kind + "; core installation is preserved"
        )
    except Exception as exc:
        setup.report(
            "FlareSolverr",
            "not ready",
            type(exc).__name__ + "; core installation is preserved",
        )


def _prepare(
    setup: Setup, *, interactive: bool, system_dependencies: bool = True
) -> None:
    if not supported_platform():
        setup.report(
            "FlareSolverr", "skipped", "Only Windows/Linux x64; macOS uses Camoufox"
        )
        return
    setup.report(
        "Python",
        "checking",
        f"{platform.python_implementation()} {platform.python_version()} ({sys.executable})",
    )
    if platform.python_implementation() != "CPython" or not (3, 11) <= sys.version_info[
        :2
    ] <= (3, 14):
        setup.report("FlareSolverr", "not ready", "Requires CPython 3.11–3.14")
        return
    if find_spec("playwright") is None or find_spec("playwright.sync_api") is None:
        setup.report(
            "FlareSolverr",
            "not ready",
            "Missing Playwright; reinstall paper-fetch-skill[full]",
        )
        return
    setup.report("Playwright", "ready")
    chrome = None
    try:
        chrome = discover_chrome(setup.env)
    except ValueError:
        if setup.env.get(CHROME_ENV, "").strip():
            setup.report(
                "FlareSolverr",
                "not ready",
                f"Correct explicit {CHROME_ENV} in {setup.env_file}",
            )
            return
        if sys.platform == "linux":
            install_linux_chrome(setup, interactive=interactive)
            with suppress(ValueError):
                chrome = discover_chrome(setup.env)
        else:
            setup.report(
                "Chrome",
                "missing",
                "Install Google Chrome 115+ from " + CHROME_DOWNLOAD_URL,
            )
    if sys.platform == "linux":
        headless = headless_mode(setup.env)
        missing = linux_missing(setup, headless)
        if system_dependencies:
            install_linux_dependencies(setup, missing, interactive=interactive)
        if missing and linux_missing(setup, headless):
            setup.report(
                "FlareSolverr", "not ready", "System dependencies remain missing"
            )
            return
        # Use the runtime's actual namespace probe, without starting a browser.
        with tempfile.TemporaryDirectory(prefix="paper-fetch-x11-check-") as directory:
            try:
                linux_launch_prefix(
                    headless, Path(directory), preparation.PreparationBudget(10)
                )
            except BrowserRuntimeFailure as exc:
                setup.report("FlareSolverr", "not ready", exc.message)
                return
    if chrome is None:
        setup.report(
            "FlareSolverr",
            "not ready",
            "Google Chrome is missing; install it and retry",
        )
        return
    setup.report("Chrome", "ready", f"{chrome.path} ({chrome.version})")
    cache = (
        Path(setup.env["PAPER_FETCH_BROWSER_COMPONENT_CACHE"]).expanduser()
        if setup.env.get("PAPER_FETCH_BROWSER_COMPONENT_CACHE")
        else resolve_user_data_dir(setup.env) / "flaresolverr"
    )
    setup.report(
        "FlareSolverr cache",
        "preparing",
        f"{cache}; verified files reused; download budget 10 minutes",
    )
    budget = preparation.PreparationBudget(600)
    runtime = preparation.prepare_source(cache, budget)
    driver, version = preparation.prepare_driver(cache, chrome.version, budget)
    setup.report(
        "FlareSolverr local launch",
        "checking",
        "CDP and about:blank only; budget 2 minutes",
    )
    local_check(setup.env, chrome, runtime, driver, version)
    setup.report(
        "FlareSolverr",
        "ready",
        f"Chrome {chrome.version}; ChromeDriver {version}; local script verified",
    )
