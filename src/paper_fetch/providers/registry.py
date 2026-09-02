"""Shared provider client registry for the skill runtime."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ..config import build_runtime_env
from ..failure import FailureDiagnostics
from ..http import HttpTransport
from ..provider_catalog import PROVIDER_BUNDLES
from ..reason_codes import ERROR
from .base import (
    ProviderClient,
    ProviderFailure,
    ProviderStatusResult,
    build_provider_status_check,
)


class FailedProviderClient(ProviderClient):
    """Structured placeholder isolating one provider factory failure."""

    def __init__(
        self,
        *,
        name: str,
        official_provider: bool,
        error: Exception,
    ) -> None:
        self.name = name
        self.official_provider = official_provider
        self.error_type = error.__class__.__name__

    def probe_status(self) -> ProviderStatusResult:
        return ProviderStatusResult(
            provider=self.name,
            status=ERROR,
            available=False,
            official_provider=self.official_provider,
            notes=[],
            checks=[
                build_provider_status_check(
                    "client_factory",
                    ERROR,
                    (f"{self.name} client factory failed ({self.error_type})."),
                )
            ],
        )

    def _raise(self) -> None:
        raise ProviderFailure(
            ERROR,
            f"{self.name} client factory failed ({self.error_type}).",
            diagnostics=FailureDiagnostics(
                provider=self.name,
                stage="client_factory",
                details={"exception_type": self.error_type},
            ),
        )

    def fetch_metadata(self, query):
        del query
        self._raise()

    def fetch_raw_fulltext(self, doi, metadata, *, context=None):
        del doi, metadata, context
        self._raise()


def build_clients(
    transport: HttpTransport | None = None,
    env: Mapping[str, str] | None = None,
    *,
    provider_names: Iterable[str] | None = None,
) -> dict[str, ProviderClient]:
    active_transport = transport if transport is not None else HttpTransport()
    active_env = env if env is not None else build_runtime_env()
    bundles = PROVIDER_BUNDLES
    selected = (
        None
        if provider_names is None
        else {
            str(name or "").strip().lower()
            for name in provider_names
            if str(name or "").strip()
        }
    )
    known = {bundle.catalog.name for bundle in bundles}
    unknown = sorted((selected or set()) - known)
    if unknown:
        raise ValueError(f"Unknown provider client(s): {', '.join(unknown)}")
    clients: dict[str, ProviderClient] = {}
    for bundle in bundles:
        spec = bundle.catalog
        if selected is not None and spec.name not in selected:
            continue
        try:
            clients[spec.name] = bundle.client_factory(active_transport, active_env)
        except Exception as exc:  # noqa: BLE001 - isolate one provider factory.
            clients[spec.name] = FailedProviderClient(
                name=spec.name,
                official_provider=spec.official,
                error=exc,
            )
    return clients


__all__ = ["FailedProviderClient", "build_clients"]
