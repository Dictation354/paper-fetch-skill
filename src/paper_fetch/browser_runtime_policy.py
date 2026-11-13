"""Read-only browser selection facts shared by static discovery and runtime."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import platform
import sys

UPDATE_CHECK_INTERVAL_SECONDS = 86400
BYPARR_MANIFEST_PATH = (
    Path(__file__).parent / "providers" / "browser_runtime" / "byparr-manifest.json"
)


def selected_backend(env: Mapping[str, str], *, provider: str) -> str:
    return "byparr"


def engine_name() -> str:
    # Invisible's sealed release publishes these two native legs. Keep the
    # established Camoufox runtime on macOS and ARM rather than removing support.
    if sys.platform in {"linux", "win32"} and platform.machine().lower() in {
        "amd64",
        "x86_64",
    }:
        return "invisible"
    return "camoufox"
