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
    "CrossrefClient": (".crossref", "CrossrefClient"),
    "CopernicusClient": (".copernicus", "CopernicusClient"),
    "ElsevierClient": (".elsevier", "ElsevierClient"),
    "FrontiersClient": (".frontiers", "FrontiersClient"),
    "IeeeClient": (".ieee", "IeeeClient"),
    "PnasClient": (".pnas", "PnasClient"),
    "PlosClient": (".plos", "PlosClient"),
    "ScienceClient": (".science", "ScienceClient"),
    "SpringerClient": (".springer", "SpringerClient"),
    "TandfClient": (".tandf", "TandfClient"),
    "WileyClient": (".wiley", "WileyClient"),
    "build_elsevier_object_url": (".elsevier", "build_elsevier_object_url"),
    "download_elsevier_related_assets": (
        ".elsevier",
        "download_elsevier_related_assets",
    ),
    "elsevier_asset_priority": (".elsevier", "elsevier_asset_priority"),
    "extract_elsevier_asset_references": (
        ".elsevier",
        "extract_elsevier_asset_references",
    ),
    "first_xml_child_text": (".elsevier", "first_xml_child_text"),
    "infer_elsevier_asset_group_key": (".elsevier", "infer_elsevier_asset_group_key"),
    "xml_local_name": (".elsevier", "xml_local_name"),
}

_BUILTIN_PROVIDER_ENTRY_MODULES = (
    ".acs",
    ".aip",
    ".ams",
    ".annualreviews",
    ".arxiv",
    ".copernicus",
    ".crossref",
    ".elsevier",
    ".frontiers",
    ".ieee",
    ".iop",
    ".mdpi",
    ".oxfordacademic",
    ".plos",
    ".pnas",
    ".royalsocietypublishing",
    ".science",
    ".springer",
    ".tandf",
    ".wiley",
)


def load_builtin_provider_bundles() -> tuple[ProviderBundle, ...]:
    """Import the fixed built-in modules and return their exported bundles."""

    bundles = tuple(
        import_module(module_name, __name__).PROVIDER_BUNDLE
        for module_name in _BUILTIN_PROVIDER_ENTRY_MODULES
    )
    from ._registry import validate_provider_bundles

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
