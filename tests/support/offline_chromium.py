"""Use the locally prepared browser in publisher integration contracts."""

import os
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from paper_fetch.providers.browser_runtime.api import load_runtime_config
from paper_fetch.providers.browser_runtime.context import browser_context
from paper_fetch.providers.browser_runtime.preparation import (
    BROWSER_PACKAGE_PINS,
    browser_cache_dir,
    inspect_chromium,
    package_versions,
)


def prepared_executable() -> Path:
    if package_versions() != BROWSER_PACKAGE_PINS:
        pytest.skip("requires the pinned Chromium browser packages")
    path, _, installed = inspect_chromium(browser_cache_dir(os.environ))
    if not installed:
        pytest.skip("requires a prepared Chromium executable")
    return path


@contextmanager
def prepared_browser(monkeypatch=None, *, headless=True, main_world_eval=False):
    del monkeypatch, main_world_eval
    if (
        sys.platform == "linux"
        and not headless
        and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    ):
        pytest.skip("headed Linux browser requires a display")
    with tempfile.TemporaryDirectory(prefix="paper-fetch-test-chromium-") as directory:
        config = load_runtime_config(
            {"PAPER_FETCH_BROWSER_BINARY_PATH": str(prepared_executable())},
            provider="pnas",
            doi="probe://browser/test",
        )
        with browser_context(
            replace(config, profile_dir=Path(directory), headless=headless)
        ) as session:
            yield session.context.browser
