from __future__ import annotations

import os
from pathlib import Path

from paper_fetch.config import DEFAULT_USER_DATA_DIR


def test_unit_process_uses_isolated_user_and_browser_directories() -> None:
    isolated_values = {
        name: Path(os.environ[name])
        for name in (
            "XDG_DATA_HOME",
            "XDG_CACHE_HOME",
            "XDG_RUNTIME_DIR",
            "PAPER_FETCH_DOWNLOAD_DIR",
            "PAPER_FETCH_BROWSER_PROFILE_DIR",
            "PAPER_FETCH_BROWSER_USER_DATA_DIR",
        )
    }

    assert len(set(isolated_values.values())) == len(isolated_values)
    assert all(path.is_dir() for path in isolated_values.values())
    assert DEFAULT_USER_DATA_DIR.is_relative_to(isolated_values["XDG_DATA_HOME"])


def test_xdist_worker_gets_worker_named_isolation_root() -> None:
    data_home = Path(os.environ["XDG_DATA_HOME"])
    assert data_home.parent.name.startswith("paper-fetch-tests-")
