"""Publisher-specific provider clients."""

from __future__ import annotations

from collections.abc import Iterator
from importlib import import_module
from importlib import util as importlib_util
from pathlib import Path
import pkgutil
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

_PROVIDER_BUNDLE_REGISTRATION_TOKEN = "register_provider_bundle("
_IMPORTED_PROVIDER_ENTRY_MODULES: set[str] = set()


def _module_declares_provider_bundle(module_name: str) -> bool:
    qualified_name = f"{__name__}.{module_name}"
    spec = importlib_util.find_spec(qualified_name)
    origin = getattr(spec, "origin", None)
    if not origin:
        return False
    path = Path(origin)
    if path.suffix != ".py" or not path.is_file():
        return False
    return _PROVIDER_BUNDLE_REGISTRATION_TOKEN in path.read_text(
        encoding="utf-8",
        errors="ignore",
    )


def _discover_provider_entry_modules() -> tuple[str, ...]:
    discovered: list[str] = []
    seen: set[str] = set()
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.ispkg or module_info.name.startswith("_"):
            continue
        if module_info.name in seen:
            continue
        seen.add(module_info.name)
        if _module_declares_provider_bundle(module_info.name):
            discovered.append(f".{module_info.name}")
    return tuple(sorted(discovered))


class _ProviderEntryModules:
    def __iter__(self) -> Iterator[str]:
        return iter(_discover_provider_entry_modules())

    def __len__(self) -> int:
        return len(_discover_provider_entry_modules())

    def __contains__(self, module_name: object) -> bool:
        return module_name in _discover_provider_entry_modules()

    def __repr__(self) -> str:
        return repr(_discover_provider_entry_modules())


_PROVIDER_ENTRY_MODULES = _ProviderEntryModules()
_PROVIDER_ENTRY_IMPORTS_COMPLETE = False


def import_provider_entry_modules() -> tuple[str, ...]:
    global _PROVIDER_ENTRY_IMPORTS_COMPLETE
    imported: list[str] = []
    for module_name in _discover_provider_entry_modules():
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


import_provider_entry_modules()

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
