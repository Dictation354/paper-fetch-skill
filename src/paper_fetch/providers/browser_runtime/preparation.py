"""Read-only inspection of the Camoufox managed browser runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
import json
import os
from pathlib import Path
import stat
from typing import Any

from ...utils import normalize_text


@dataclass(frozen=True)
class CamoufoxRuntimeProbe:
    state: str
    installed: bool
    valid: bool
    runtime_path: Path | None = None
    executable_path: Path | None = None
    version: str | None = None
    active_spec: str | None = None
    managed_path_safe: bool = False
    message: str | None = None


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(os.path, "isjunction", None)
    if callable(is_junction) and is_junction(path):
        return True
    try:
        attributes = int(getattr(path.lstat(), "st_file_attributes", 0))
    except OSError:
        return False
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return bool(attributes & reparse_flag)


def _path_chain_has_link(root: Path, candidate: Path) -> bool:
    current = root
    if _is_link_or_reparse(current):
        return True
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return True
    for part in relative.parts:
        current = current / part
        if _is_link_or_reparse(current):
            return True
    return False


def _managed_candidate(
    install_dir: Path,
    active_spec: str,
) -> tuple[Path, bool]:
    relative_spec = Path(active_spec)
    candidate = install_dir / relative_spec
    if relative_spec.is_absolute() or ".." in relative_spec.parts:
        return candidate, False
    root = install_dir.resolve(strict=False)
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError:
        return candidate, False
    return candidate, not _path_chain_has_link(install_dir, candidate)


def probe_camoufox_managed_runtime() -> CamoufoxRuntimeProbe:
    """Inspect the active managed runtime without downloading or writing state."""

    pkgman = import_module("camoufox.pkgman")
    multiversion = import_module("camoufox.multiversion")
    install_dir = Path(pkgman.INSTALL_DIR)
    config_path = Path(multiversion.CONFIG_FILE)
    config: Mapping[str, Any] = {}
    if config_path.is_file():
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping):
                config = payload
        except (OSError, ValueError):
            return CamoufoxRuntimeProbe(
                state="corrupt",
                installed=True,
                valid=False,
                runtime_path=config_path.parent,
                message="Camoufox active-version configuration is unreadable.",
            )

    active_spec = normalize_text(str(config.get("active_version") or "")) or None
    managed_path_safe = False
    runtime_path: Path | None = None
    if active_spec:
        runtime_path, managed_path_safe = _managed_candidate(
            install_dir,
            active_spec,
        )
    elif (install_dir / "version.json").is_file():
        runtime_path = install_dir
        managed_path_safe = not _is_link_or_reparse(install_dir)

    if runtime_path is None or not runtime_path.is_dir():
        return CamoufoxRuntimeProbe(
            state="missing",
            installed=False,
            valid=False,
            runtime_path=runtime_path,
            active_spec=active_spec,
            managed_path_safe=managed_path_safe,
            message="Camoufox managed browser runtime is not installed.",
        )
    if not managed_path_safe:
        return CamoufoxRuntimeProbe(
            state="corrupt",
            installed=True,
            valid=False,
            runtime_path=runtime_path,
            active_spec=active_spec,
            managed_path_safe=False,
            message=(
                "Camoufox active runtime path is outside the managed cache or is a link."
            ),
        )

    try:
        version = pkgman.Version.from_path(runtime_path)
        version_text = normalize_text(version.full_string) or None
        if not version.is_supported():
            return CamoufoxRuntimeProbe(
                state="incompatible",
                installed=True,
                valid=False,
                runtime_path=runtime_path,
                version=version_text,
                active_spec=active_spec,
                managed_path_safe=True,
                message=(
                    "Camoufox managed browser runtime is incompatible with the "
                    "installed Python package."
                ),
            )
        executable = Path(pkgman.launch_path(runtime_path))
        if not executable.is_file():
            raise FileNotFoundError(str(executable))
    except Exception as exc:
        return CamoufoxRuntimeProbe(
            state="corrupt",
            installed=True,
            valid=False,
            runtime_path=runtime_path,
            version=locals().get("version_text"),
            active_spec=active_spec,
            managed_path_safe=True,
            message=normalize_text(str(exc))
            or "Camoufox managed runtime is incomplete.",
        )

    return CamoufoxRuntimeProbe(
        state="ready",
        installed=True,
        valid=True,
        runtime_path=runtime_path,
        executable_path=executable,
        version=version_text,
        active_spec=active_spec,
        managed_path_safe=True,
    )


__all__ = ["CamoufoxRuntimeProbe", "probe_camoufox_managed_runtime"]
