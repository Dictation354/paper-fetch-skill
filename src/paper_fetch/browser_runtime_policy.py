"""Read-only browser selection facts shared by static discovery and runtime."""

from __future__ import annotations

import platform
import sys
from collections.abc import Mapping
from pathlib import Path

UPDATE_CHECK_INTERVAL_SECONDS = 86400
BYPARR_MANIFEST_PATH = (
    Path(__file__).parent / "providers" / "browser_runtime" / "byparr-manifest.json"
)


def selected_backend(env: Mapping[str, str], *, provider: str) -> str:
    del env, provider
    return "byparr"


def engine_name() -> str:
    return "camoufox"


def supported_platform() -> bool:
    machine = platform.machine().lower()
    return (
        sys.platform in {"win32", "linux"}
        and machine in {"amd64", "x86_64", "aarch64", "arm64"}
    ) or (sys.platform == "darwin" and machine in {"x86_64", "arm64", "aarch64"})
