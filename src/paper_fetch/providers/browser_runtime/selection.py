"""Provider-local browser backend selection without runtime preparation."""

from __future__ import annotations

from collections.abc import Mapping
from .chrome import supported_platform
from ..base import ProviderFailure
from ...reason_codes import NOT_CONFIGURED, NOT_SUPPORTED

PNAS_BACKEND_ENV = "PAPER_FETCH_PNAS_BROWSER_BACKEND"


def selected_backend(env: Mapping[str, str], *, provider: str) -> str:
    if provider.lower() == "elsevier":
        if not supported_platform():
            raise ProviderFailure(
                NOT_SUPPORTED,
                "Elsevier browser routes require FlareSolverr on Windows/Linux x64.",
            )
        return "flaresolverr"
    if provider.lower() != "pnas":
        return "camoufox"
    value = env.get(PNAS_BACKEND_ENV, "auto").strip().lower() or "auto"
    if value not in {"auto", "flaresolverr", "camoufox"}:
        raise ProviderFailure(
            NOT_CONFIGURED,
            f"{PNAS_BACKEND_ENV} must be auto, flaresolverr or camoufox: {value}",
        )
    if value == "auto":
        return "flaresolverr" if supported_platform() else "camoufox"
    if value == "flaresolverr" and not supported_platform():
        raise ProviderFailure(
            NOT_CONFIGURED,
            "PNAS FlareSolverr requires Windows/Linux x64; use camoufox on this platform.",
        )
    return value
