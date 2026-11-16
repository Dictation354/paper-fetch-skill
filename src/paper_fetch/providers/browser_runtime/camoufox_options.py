"""Launch preferences for Camoufox's native macOS proxy boundary."""

from __future__ import annotations

from contextlib import contextmanager
import importlib
import re
import subprocess
import sys


@contextmanager
def macos_proxy_preferences():
    """Use a direct connection only when macOS has no enabled system proxy.

    Camoufox beta.42 reads nsISystemProxySettings.PACURI outside its exception
    handler. macOS raises NS_ERROR_FAILURE when no PAC is configured, preventing
    Juggler from starting. An explicitly direct connection avoids that read.
    The preliminary GPU browser needs the same preference as the owned browser.
    """
    if sys.platform != "darwin":
        yield {}
        return
    try:
        settings = subprocess.run(
            ["/usr/sbin/scutil", "--proxy"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        yield {}
        return
    if not settings.lstrip().startswith("<dictionary>") or re.search(
        r"^\s*\w*Enable\s*:\s*[1-9]\d*\s*$", settings, re.MULTILINE
    ):
        yield {}
        return
    rendering = importlib.import_module("camoufox.host_rendering")
    original = rendering.GPU_PREFS
    # Camoufox 0.5.9 filters the probe's preferences through GPU_PREFS. Extend
    # that filter in memory for this launch; leave its package and cache intact.
    rendering.GPU_PREFS = {**original, "network.proxy.type": 0}
    try:
        yield {"network.proxy.type": 0}
    finally:
        rendering.GPU_PREFS = original
