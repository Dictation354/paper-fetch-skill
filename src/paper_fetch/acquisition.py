"""Exact, JSON-safe provenance for the final acquired paper content."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, cast

from .utils import normalize_text

AcquisitionRepresentation = Literal["metadata", "html", "xml", "pdf"]
AcquisitionTransport = Literal["api", "browser", "http"]

_ACQUISITION_REPRESENTATIONS = frozenset({"metadata", "html", "xml", "pdf"})
_ACQUISITION_TRANSPORTS = frozenset({"api", "browser", "http"})


@dataclass(frozen=True)
class AcquisitionProvenance:
    """Exact final content-acquisition route alongside the legacy source label."""

    provider: str
    route: str
    representation: AcquisitionRepresentation
    transport: AcquisitionTransport
    fallback_used: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or not isinstance(self.route, str):
            raise TypeError("Acquisition provider and route must be strings.")
        if not isinstance(self.fallback_used, bool):
            raise TypeError("Acquisition fallback_used must be a boolean.")
        provider = normalize_text(self.provider).lower()
        route = normalize_text(self.route).lower()
        if not provider or not route:
            raise ValueError("Acquisition provider and route are required.")
        if self.representation not in _ACQUISITION_REPRESENTATIONS:
            raise ValueError(
                f"Unsupported acquisition representation: {self.representation!r}"
            )
        if self.transport not in _ACQUISITION_TRANSPORTS:
            raise ValueError(f"Unsupported acquisition transport: {self.transport!r}")
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "route", route)


def coerce_acquisition_provenance(value: Any) -> AcquisitionProvenance | None:
    """Return a validated acquisition object from trusted or cached payload data."""

    if isinstance(value, AcquisitionProvenance):
        return value
    if not isinstance(value, Mapping):
        return None
    if (
        not isinstance(value.get("provider"), str)
        or not isinstance(value.get("route"), str)
        or not isinstance(value.get("fallback_used"), bool)
    ):
        return None
    representation = str(value.get("representation") or "")
    transport = str(value.get("transport") or "")
    if (
        representation not in _ACQUISITION_REPRESENTATIONS
        or transport not in _ACQUISITION_TRANSPORTS
    ):
        return None
    try:
        return AcquisitionProvenance(
            provider=value["provider"],
            route=value["route"],
            representation=cast(AcquisitionRepresentation, representation),
            transport=cast(AcquisitionTransport, transport),
            fallback_used=value["fallback_used"],
        )
    except (TypeError, ValueError):
        return None


__all__ = [
    "AcquisitionProvenance",
    "AcquisitionRepresentation",
    "AcquisitionTransport",
    "coerce_acquisition_provenance",
]
