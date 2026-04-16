"""Shared provider client registry for the skill runtime."""

from __future__ import annotations

from typing import Mapping

from ..config import build_runtime_env
from ..http import HttpTransport
from .base import ProviderClient
from .crossref import CrossrefClient
from .elsevier import ElsevierClient
from .pnas import PnasClient
from .science import ScienceClient
from .springer import SpringerClient
from .wiley import WileyClient


def build_clients(
    transport: HttpTransport | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, ProviderClient]:
    active_transport = transport if transport is not None else HttpTransport()
    active_env = env if env is not None else build_runtime_env()
    return {
        "crossref": CrossrefClient(active_transport, active_env),
        "elsevier": ElsevierClient(active_transport, active_env),
        "pnas": PnasClient(active_transport, active_env),
        "science": ScienceClient(active_transport, active_env),
        "springer": SpringerClient(active_transport, active_env),
        "wiley": WileyClient(active_transport, active_env),
    }
