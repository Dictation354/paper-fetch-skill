"""Launch the prepared Camoufox bundle without probing or downloading a runtime."""

from contextlib import contextmanager
import json
import os
from pathlib import Path

import pytest

from tests._environment import PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR


@contextmanager
def prepared_browser(monkeypatch, *, headless=True):
    executable = os.environ.get(PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR)
    if not executable or not Path(executable).is_file():
        pytest.skip("requires the existing local Camoufox executable")
    if not headless and not os.environ.get("DISPLAY"):
        pytest.skip("headed Linux browser requires a display")
    camoufox = pytest.importorskip("camoufox.sync_api")
    from camoufox import DefaultAddons, utils

    version_file = next(
        parent / "version.json"
        for parent in Path(executable).parents
        if (parent / "version.json").is_file()
    )
    monkeypatch.setattr(
        utils,
        "installed_verstr",
        lambda: json.loads(version_file.read_text())["version"],
    )
    monkeypatch.setattr(utils, "get_path", lambda file: str(version_file.parent / file))
    with camoufox.Camoufox(
        headless=headless,
        executable_path=executable,
        exclude_addons=list(DefaultAddons),
    ) as browser:
        yield browser
