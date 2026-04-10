"""Shared provider client registry for the skill runtime."""

from __future__ import annotations

from typing import Mapping

from fetch_common import HttpTransport, ProviderClient, build_runtime_env
from providers.crossref import CrossrefClient
from providers.elsevier import ElsevierClient
from providers.springer import SpringerClient
from providers.wiley import WileyClient


def build_clients(
    transport: HttpTransport | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, ProviderClient]:
    active_transport = transport or HttpTransport()
    active_env = env or build_runtime_env()
    return {
        "crossref": CrossrefClient(active_transport, active_env),
        "elsevier": ElsevierClient(active_transport, active_env),
        "springer": SpringerClient(active_transport, active_env),
        "wiley": WileyClient(active_transport, active_env),
    }
