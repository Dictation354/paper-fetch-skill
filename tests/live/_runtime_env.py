from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
from collections.abc import Mapping

from paper_fetch.config import build_runtime_env


def build_isolated_live_env(
    base_env: Mapping[str, str] | None = None,
) -> tuple[dict[str, str], tempfile.TemporaryDirectory]:
    tempdir = tempfile.TemporaryDirectory(prefix="paper-fetch-live-xdg-")
    env = build_runtime_env(base_env)
    env["XDG_DATA_HOME"] = tempdir.name
    Path(tempdir.name).mkdir(parents=True, exist_ok=True)
    return env, tempdir


def require_cloakbrowser_or_skip(testcase) -> None:
    if importlib.util.find_spec("playwright.sync_api") is None:
        testcase.skipTest("Playwright Python package is not installed.")
    if importlib.util.find_spec("cloakbrowser") is None:
        testcase.skipTest("CloakBrowser Python package is not installed.")
