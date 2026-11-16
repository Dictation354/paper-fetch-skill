"""Launch preferences for Camoufox's native macOS proxy boundary."""

from __future__ import annotations

import importlib
import re
import subprocess
import sys


def macos_proxy_preferences() -> dict[str, int]:
    """Use a direct connection only when macOS has no enabled system proxy.

    Camoufox beta.42 reads nsISystemProxySettings.PACURI outside its exception
    handler. macOS raises NS_ERROR_FAILURE when no PAC is configured, preventing
    Juggler from starting. An explicitly direct connection avoids that read.
    The preliminary GPU browser needs the same preference as the owned browser.
    """
    if sys.platform != "darwin":
        return {}
    try:
        settings = subprocess.run(
            ["/usr/sbin/scutil", "--proxy"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    if not settings.lstrip().startswith("<dictionary>") or re.search(
        r"^\s*\w*Enable\s*:\s*[1-9]\d*\s*$", settings, re.MULTILINE
    ):
        return {}
    rendering = importlib.import_module("camoufox.host_rendering")
    # Camoufox 0.5.9 filters the probe's preferences through GPU_PREFS. Extend
    # that module's filter so the probe follows an explicitly supplied proxy
    # preference. Other callers keep their own preferences and proxy settings.
    # Its package and browser cache remain intact.
    rendering.GPU_PREFS = {**rendering.GPU_PREFS, "network.proxy.type": 0}
    return {"network.proxy.type": 0}
