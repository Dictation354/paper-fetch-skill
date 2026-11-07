"""Platform boundary for the managed Byparr backend (stdlib only)."""

import platform
import sys


def supported_platform() -> bool:
    machine = platform.machine().lower()
    return (
        sys.platform in {"win32", "linux"}
        and machine in {"amd64", "x86_64", "aarch64", "arm64"}
    ) or (sys.platform == "darwin" and machine in {"x86_64", "arm64", "aarch64"})
