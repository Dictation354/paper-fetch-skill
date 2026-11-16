"""Launch preferences for Camoufox's native macOS proxy boundary."""

from __future__ import annotations

import importlib
from functools import wraps
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
    if not getattr(rendering._host_gpu, "_paper_fetch_proxy_startup", False):
        original_probe = rendering._host_gpu
        startup_env = importlib.import_module("camoufox.utils").get_pref_env_vars(
            {"network.proxy.type": 0}
        )

        @wraps(original_probe)
        def probe(executable_path, headless, env, prefs):
            # The plain Playwright probe applies firefox_user_prefs only after
            # Juggler starts. Reinsert the startup preference after Camoufox
            # filters CAMOU_* out of the probe's inherited environment.
            if dict(prefs).get("network.proxy.type") == 0:
                env = tuple(sorted({**dict(env), **startup_env}.items()))
            return original_probe(executable_path, headless, env, prefs)

        probe._paper_fetch_proxy_startup = True
        rendering._host_gpu = probe
    return {"network.proxy.type": 0}
