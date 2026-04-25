"""Shared provider client registry for the skill runtime."""

from __future__ import annotations

import importlib
from typing import Mapping

from ..config import build_runtime_env
from ..http import HttpTransport
from ..provider_catalog import ordered_provider_specs
from .base import ProviderClient


def _client_factory(factory_path: str):
    module_path, _, attribute = factory_path.partition(":")
    if not module_path or not attribute:
        raise ValueError(f"Invalid provider client factory path: {factory_path!r}")
    module = importlib.import_module(module_path)
    return getattr(module, attribute)


def build_clients(
    transport: HttpTransport | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, ProviderClient]:
    active_transport = transport if transport is not None else HttpTransport()
    active_env = env if env is not None else build_runtime_env()
    clients: dict[str, ProviderClient] = {}
    for spec in ordered_provider_specs():
        factory = _client_factory(spec.client_factory_path)
        clients[spec.name] = factory(active_transport, active_env)
    return clients
