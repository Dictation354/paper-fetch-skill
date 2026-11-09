"""Engine and protocol pairing for the pinned Byparr source adapter."""

from __future__ import annotations

import importlib
import platform
import sys


def engine_name() -> str:
    # Invisible's sealed release publishes these two native legs. Keep the
    # established Camoufox runtime on macOS and ARM rather than removing support.
    if sys.platform in {"linux", "win32"} and platform.machine().lower() in {
        "amd64",
        "x86_64",
    }:
        return "invisible"
    return "camoufox"


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
    from .camoufox_manager import _launch_executable_path

    return _launch_executable_path(binary_path)
