"""Publisher-specific provider clients."""

from __future__ import annotations

from importlib import import_module
import sys
from typing import Any

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
_IMPORTED_PROVIDER_ENTRY_MODULES: set[str] = set()
_PROVIDER_ENTRY_MODULES = _BUILTIN_PROVIDER_ENTRY_MODULES
_PROVIDER_ENTRY_IMPORTS_COMPLETE = False


def import_provider_entry_modules() -> tuple[str, ...]:
    global _PROVIDER_ENTRY_IMPORTS_COMPLETE
    imported: list[str] = []
    for module_name in _PROVIDER_ENTRY_MODULES:
        if module_name in _IMPORTED_PROVIDER_ENTRY_MODULES:
            continue
        import_module(module_name, __name__)
        _IMPORTED_PROVIDER_ENTRY_MODULES.add(module_name)
        imported.append(module_name)
    if imported:
        provider_catalog = sys.modules.get("paper_fetch.provider_catalog")
        if provider_catalog is not None:
            provider_catalog.__dict__["_PROVIDER_CATALOG_CACHE"] = None
            provider_catalog.__dict__["_SOURCE_PROVIDER_MAP_CACHE"] = None
    _PROVIDER_ENTRY_IMPORTS_COMPLETE = True
    return tuple(imported)


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
