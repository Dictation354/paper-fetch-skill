"""Publisher-specific provider clients."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from importlib import import_module
from pathlib import Path
import sys
import threading
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
_BUILTIN_PROVIDER_ENTRY_NAMES = {
    module_name.removeprefix(".") for module_name in _BUILTIN_PROVIDER_ENTRY_MODULES
}
_IMPORTED_PROVIDER_ENTRY_MODULES: set[str] = set()
_DISCOVERED_PROVIDER_ENTRY_MODULES_CACHE: dict[
    tuple[tuple[str, int, int], ...], tuple[str, ...]
] = {}


def _module_declares_provider_bundle(module_name: str) -> bool:
    module_path = None
    for root in __path__:
        candidate = Path(root) / f"{module_name}.py"
        if candidate.is_file():
            module_path = candidate
            break
    if module_path is None:
        return False
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "register_provider_bundle":
            return True
        if isinstance(func, ast.Attribute) and func.attr == "register_provider_bundle":
            return True
    return False


def _provider_entry_discovery_cache_key() -> tuple[tuple[str, int, int], ...]:
    entries: list[tuple[str, int, int]] = []
    for root in __path__:
        try:
            children = sorted(Path(root).glob("*.py"))
        except OSError:
            continue
        for child in children:
            if child.stem.startswith("_"):
                continue
            try:
                stat_result = child.stat()
            except OSError:
                continue
            entries.append(
                (str(child), int(stat_result.st_mtime_ns), int(stat_result.st_size))
            )
    return tuple(entries)


def _discover_provider_entry_modules() -> tuple[str, ...]:
    with _PROVIDER_ENTRY_DISCOVERY_LOCK:
        cache_key = _provider_entry_discovery_cache_key()
        cached = _DISCOVERED_PROVIDER_ENTRY_MODULES_CACHE.get(cache_key)
        if cached is not None:
            return cached
        discovered = list(_BUILTIN_PROVIDER_ENTRY_MODULES)
        seen: set[str] = set()
        for module_path, _, _ in cache_key:
            module_name = Path(module_path).stem
            if module_name in _BUILTIN_PROVIDER_ENTRY_NAMES or module_name.startswith(
                "_"
            ):
                continue
            if module_name in seen:
                continue
            seen.add(module_name)
            if _module_declares_provider_bundle(module_name):
                discovered.append(f".{module_name}")
        result = tuple(dict.fromkeys(discovered))
        _DISCOVERED_PROVIDER_ENTRY_MODULES_CACHE.clear()
        _DISCOVERED_PROVIDER_ENTRY_MODULES_CACHE[cache_key] = result
        return result


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
_PROVIDER_ENTRY_IMPORT_LOCK = threading.RLock()
_PROVIDER_ENTRY_DISCOVERY_LOCK = threading.RLock()


def import_provider_entry_modules() -> tuple[str, ...]:
    global _PROVIDER_ENTRY_IMPORTS_COMPLETE
    with _PROVIDER_ENTRY_IMPORT_LOCK:
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
