"""Provider-local browser backend selection without runtime preparation."""

from __future__ import annotations

from collections.abc import Mapping
from .chrome import supported_platform
from ..base import ProviderFailure
from ...reason_codes import NOT_CONFIGURED, NOT_SUPPORTED

PNAS_BACKEND_ENV = "PAPER_FETCH_PNAS_BROWSER_BACKEND"


def selected_backend(env: Mapping[str, str], *, provider: str) -> str:
    from ...provider_catalog import PROVIDER_CATALOG

    spec = PROVIDER_CATALOG.get(provider.lower())
    supported = spec.browser_backends if spec else ("camoufox",)
    key = f"PAPER_FETCH_{provider.upper()}_BROWSER_BACKEND"
    value = env.get(key, "auto").strip().lower() or "auto"
    if value not in {"auto", "camoufox", "flaresolverr"}:
        raise ProviderFailure(
            NOT_CONFIGURED, f"{key} must be auto, camoufox or flaresolverr: {value}"
        )
    if value == "auto":
        value = (
            (
                (spec.browser_default_x64 if supported_platform() else None)
                or spec.browser_default
            )
            if spec
            else "camoufox"
        )
    if value not in supported:
        raise ProviderFailure(
            NOT_CONFIGURED, f"{provider} does not support browser backend {value}."
        )
    if value == "flaresolverr" and not supported_platform():
        raise ProviderFailure(
            NOT_SUPPORTED if env.get(key, "auto") == "auto" else NOT_CONFIGURED,
            f"{provider} FlareSolverr requires Windows/Linux x64.",
        )
    return value
