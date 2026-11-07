"""Provider-local browser backend selection without runtime preparation."""

from __future__ import annotations

from collections.abc import Mapping
import platform
import sys
from ..base import ProviderFailure
from ...reason_codes import NOT_CONFIGURED

PNAS_BACKEND_ENV = "PAPER_FETCH_PNAS_BROWSER_BACKEND"


def selected_backend(env: Mapping[str, str], *, provider: str) -> str:
    if env.get("PAPER_FETCH_CHROME_BINARY_PATH", "").strip():
        raise ProviderFailure(
            NOT_CONFIGURED,
            "PAPER_FETCH_CHROME_BINARY_PATH was removed with FlareSolverr; remove it and use PAPER_FETCH_BROWSER_BINARY_PATH for Camoufox/Byparr. See docs/browser-backends.md#migration.",
        )
    key = f"PAPER_FETCH_{provider.upper()}_BROWSER_BACKEND"
    value = env.get(key, "auto").strip().lower() or "auto"
    if value == "flaresolverr":
        raise ProviderFailure(
            NOT_CONFIGURED,
            f"{key}=flaresolverr was removed; use auto or byparr. See docs/browser-backends.md#migration.",
        )
    if value not in {"auto", "camoufox", "byparr"}:
        raise ProviderFailure(
            NOT_CONFIGURED, f"{key} must be auto, camoufox or byparr: {value}"
        )
    return "byparr"


def selected_state_mode(env: Mapping[str, str], *, provider: str) -> str:
    """Keep the pre-unification state owner and directory; never migrate it."""
    value = (
        env.get(f"PAPER_FETCH_{provider.upper()}_BROWSER_BACKEND", "auto")
        .strip()
        .lower()
    )
    legacy_json_platform = sys.platform in {
        "win32",
        "linux",
    } and platform.machine().lower() in {"amd64", "x86_64"}
    if (
        provider.lower() in {"pnas", "elsevier"}
        and legacy_json_platform
        and value != "camoufox"
    ):
        return "json"
    return "native"
