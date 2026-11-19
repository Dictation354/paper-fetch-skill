"""Publisher-specific provider clients."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ._registry import ProviderBundle

_EXPORTS: dict[str, tuple[str, str]] = {
    "AcsClient": (".acs", "AcsClient"),
    "AmsClient": (".ams", "AmsClient"),
    "ArxivClient": (".arxiv", "ArxivClient"),
    "CopernicusClient": (".copernicus", "CopernicusClient"),
    "CrossrefClient": (".crossref", "CrossrefClient"),
    "ElsevierClient": (".elsevier", "ElsevierClient"),
    "FrontiersClient": (".frontiers", "FrontiersClient"),
    "IeeeClient": (".ieee", "IeeeClient"),
    "PlosClient": (".plos", "PlosClient"),
    "PnasClient": (".pnas", "PnasClient"),
    "ScienceClient": (".science", "ScienceClient"),
    "SpringerClient": (".springer", "SpringerClient"),
    "TandfClient": (".tandf", "TandfClient"),
    "WileyClient": (".wiley", "WileyClient"),
}


def load_builtin_provider_bundles() -> tuple[ProviderBundle, ...]:
    """Explicitly load and validate all built-in runtime implementations."""
    from ._definitions import BUILTIN_PROVIDER_DEFINITIONS
    from ._registry import provider_bundle, validate_provider_bundles

    bundles = tuple(
        provider_bundle(definition.catalog.name)
        for definition in BUILTIN_PROVIDER_DEFINITIONS
    )
    validate_provider_bundles(bundles)
    return bundles


__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    module = import_module(module_name, __name__)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
