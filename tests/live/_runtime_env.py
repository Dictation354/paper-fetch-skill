from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
from collections.abc import Mapping

from paper_fetch.config import build_runtime_env
from paper_fetch.config import configured_browser_backend


def build_isolated_live_env(
    base_env: Mapping[str, str] | None = None,
) -> tuple[dict[str, str], tempfile.TemporaryDirectory]:
    tempdir = tempfile.TemporaryDirectory(prefix="paper-fetch-live-xdg-")
    env = build_runtime_env(base_env)
    env["XDG_DATA_HOME"] = tempdir.name
    Path(tempdir.name).mkdir(parents=True, exist_ok=True)
    return env, tempdir


def require_selected_browser_or_skip(testcase, env: Mapping[str, str]) -> None:
    if importlib.util.find_spec("playwright.sync_api") is None:
        testcase.skipTest("Playwright Python package is not installed.")
    backend = configured_browser_backend(env)
    if importlib.util.find_spec(backend) is None:
        testcase.skipTest(f"Selected browser package {backend!r} is not installed.")


def require_cloakbrowser_or_skip(testcase) -> None:
    """Compatibility helper for older live modules with explicit CloakBrowser cases."""

    require_selected_browser_or_skip(
        testcase, {"PAPER_FETCH_BROWSER_BACKEND": "cloakbrowser"}
    )
