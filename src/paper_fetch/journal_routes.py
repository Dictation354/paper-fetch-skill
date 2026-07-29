"""Load versioned journal routing data used by provider adapters."""

from __future__ import annotations

from functools import cache
from importlib.resources import files
import json
from types import MappingProxyType
from typing import Any
from collections.abc import Mapping


JOURNAL_ROUTES_SCHEMA_VERSION = 1
JOURNAL_ROUTES_RESOURCE = "journal-routes-v1.json"


@cache
def journal_routes() -> Mapping[str, Any]:
    resource = files("paper_fetch.resources.journal_routes").joinpath(
        JOURNAL_ROUTES_RESOURCE
    )
    payload = json.loads(resource.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != JOURNAL_ROUTES_SCHEMA_VERSION
    ):
        raise ValueError(
            f"Unsupported journal route resource schema: {JOURNAL_ROUTES_RESOURCE}"
        )
    return MappingProxyType(payload)


def provider_journal_mapping(provider: str, field: str) -> dict[str, str]:
    provider_payload = journal_routes().get(str(provider or "").strip().lower())
    if not isinstance(provider_payload, Mapping):
        raise KeyError(f"Journal route provider is not configured: {provider!r}")
    values = provider_payload.get(field)
    if not isinstance(values, Mapping):
        raise KeyError(f"Journal route mapping is not configured: {provider!r}.{field}")
    return {
        str(key).strip().lower(): str(value).strip()
        for key, value in values.items()
        if str(key).strip() and str(value).strip()
    }


__all__ = [
    "JOURNAL_ROUTES_RESOURCE",
    "JOURNAL_ROUTES_SCHEMA_VERSION",
    "journal_routes",
    "provider_journal_mapping",
]
