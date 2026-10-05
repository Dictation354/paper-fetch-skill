"""Read-only inspection and launch-time preparation of managed Camoufox."""

from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import dataclass
from importlib import import_module
import json
import os
from pathlib import Path
import stat
import shutil
import sys
from typing import Any

from filelock import FileLock

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
    if (
        not relative_spec.parts
        or relative_spec.is_absolute()
        or ".." in relative_spec.parts
    ):
        return candidate, False
    root = install_dir.resolve(strict=False)
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError:
        return candidate, False
    return candidate, not _path_chain_has_link(install_dir, candidate)


def _read_config(install_dir: Path, config_path: Path) -> dict[str, Any]:
    if _path_chain_has_link(install_dir, config_path):
        raise ValueError("Camoufox configuration path is unsafe.")
    if not config_path.exists():
        return {}
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or any(
        value is not None and not isinstance(value, str)
        for key, value in payload.items()
        if key in {"active_version", "channel", "pinned", "pinned_sha"}
    ):
        raise ValueError("Camoufox active-version configuration is invalid.")
    return payload


def _browser_pin(config: dict[str, Any]) -> Any:
    """Honor release pairing while retaining support for Camoufox 0.5.5/0.5.6."""
    try:
        browser_pin = import_module("camoufox.browser_pin")
    except ModuleNotFoundError as exc:
        if exc.name != "camoufox.browser_pin":
            raise
        return None
    return browser_pin.effective_pin(config)


def probe_camoufox_managed_runtime() -> CamoufoxRuntimeProbe:
    """Inspect the active managed runtime without downloading or writing state."""

    pkgman = import_module("camoufox.pkgman")
    multiversion = import_module("camoufox.multiversion")
    install_dir = Path(pkgman.INSTALL_DIR)
    config_path = Path(multiversion.CONFIG_FILE)
    try:
        config = _read_config(install_dir, config_path)
    except (OSError, ValueError) as exc:
        return CamoufoxRuntimeProbe(
            state="corrupt",
            installed=True,
            valid=False,
            runtime_path=config_path.parent,
            message=f"Camoufox active-version configuration is unreadable: {exc}",
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

    if runtime_path is not None and not managed_path_safe:
        return _probe_runtime(pkgman, runtime_path, active_spec, False)

    pin = _browser_pin(config)
    if pin is not None:
        # Upstream get_active_path may write config or select a different build.
        # Resolve the same pairing through local metadata without those writes.
        runtime_path, active_spec, managed_path_safe = None, None, False
        try:
            installed = multiversion.list_installed()
        except (OSError, ValueError, KeyError, TypeError):
            installed = []
        for item in installed:
            if item.repo_name == pin.repo_name and item.version.full_string == pin.spec:
                active_spec = item.relative_path
                runtime_path, managed_path_safe = _managed_candidate(
                    install_dir, active_spec
                )
                break

    return _probe_runtime(pkgman, runtime_path, active_spec, managed_path_safe)


def _probe_runtime(
    pkgman: Any,
    runtime_path: Path | None,
    active_spec: str | None,
    managed_path_safe: bool,
) -> CamoufoxRuntimeProbe:
    if runtime_path is not None and not managed_path_safe:
        return CamoufoxRuntimeProbe(
            state="corrupt",
            installed=runtime_path.exists(),
            valid=False,
            runtime_path=runtime_path,
            active_spec=active_spec,
            message="Camoufox active runtime path is outside the managed cache or is a link.",
        )
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
    try:
        if _path_chain_has_link(runtime_path, runtime_path / "version.json"):
            managed_path_safe = False
            raise ValueError("Camoufox version metadata path is unsafe.")
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
        if _path_chain_has_link(runtime_path, executable):
            managed_path_safe = False
            raise ValueError("Camoufox executable path is unsafe.")
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
            managed_path_safe=managed_path_safe,
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


def prepare_camoufox_managed_runtime() -> CamoufoxRuntimeProbe:
    """Prepare only a validated version directory, preserving a usable active runtime.

    Camoufox's installer writes shared active config and removes its target on
    failure. A cache-scoped file lock protects these operations across processes.
    Never call camoufox_path here: even its no-download mode can erase old caches.
    """
    pkgman = import_module("camoufox.pkgman")
    multiversion = import_module("camoufox.multiversion")
    root = Path(pkgman.INSTALL_DIR)
    config_path = Path(multiversion.CONFIG_FILE)
    lock_path = root / ".paper-fetch-prepare.lock"
    flag = Path(multiversion.COMPAT_FLAG)
    for path in (config_path, lock_path, flag, Path(multiversion.BROWSERS_DIR)):
        if _path_chain_has_link(root, path):
            raise RuntimeError(
                "Camoufox browser preparation failed: unsafe managed cache path."
            )
    root.mkdir(parents=True, exist_ok=True)
    with FileLock(lock_path), redirect_stdout(sys.stderr):
        try:
            config = _read_config(root, config_path)
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"Camoufox browser preparation failed: {exc}") from exc
        previous = probe_camoufox_managed_runtime()
        if previous.runtime_path is not None and not previous.managed_path_safe:
            raise RuntimeError(
                f"Camoufox browser preparation failed: {previous.message}"
            )
        release_pin = _browser_pin(config)
        channel = config.get("channel") or multiversion.get_default_channel()
        parts = channel.lower().split("/")
        repo_name, channel_type = parts if len(parts) == 2 else (parts[0], "stable")
        if release_pin is not None:
            repo_name = release_pin.repo_name
        repo = pkgman.RepoConfig.find_by_name(repo_name)
        if (
            len(parts) > 2
            or channel_type not in {"stable", "prerelease"}
            or repo is None
        ):
            raise RuntimeError(
                "Camoufox browser preparation failed: invalid configured channel."
            )
        pinned = release_pin.spec if release_pin is not None else config.get("pinned")
        pinned_sha = None if release_pin is not None else config.get("pinned_sha")

        # A package pairing, like a user pin, reuses its local build without a query.
        if pinned:
            try:
                installed = multiversion.list_installed()
            except (OSError, ValueError, KeyError, TypeError):
                # Broken local metadata must not prevent repair of the pinned target.
                installed = []
            for item in installed:
                if (
                    item.repo_name == repo_name
                    and item.version.full_string == pinned
                    and (
                        release_pin is not None
                        or item.is_prerelease == (channel_type == "prerelease")
                    )
                    and (not pinned_sha or item.sha256 == pinned_sha)
                ):
                    path, safe = _managed_candidate(root, item.relative_path)
                    probe = _probe_runtime(pkgman, path, item.relative_path, safe)
                    if not probe.managed_path_safe:
                        raise RuntimeError(
                            "Camoufox browser preparation failed: unsafe pinned path."
                        )
                    if probe.valid:
                        if config.get("active_version") != item.relative_path:
                            multiversion.set_active(item.relative_path)
                        flag.touch()
                        return probe

        try:
            print(
                f"Checking Camoufox runtime: {channel}{'/' + pinned if pinned else ''}",
                file=sys.stderr,
            )
            versions = pkgman.list_available_versions(
                repo,
                include_prerelease=release_pin is not None
                or channel_type == "prerelease",
            )
            selected = next(
                (
                    v
                    for v in versions
                    if (
                        release_pin is not None
                        or v.is_prerelease == (channel_type == "prerelease")
                    )
                    and v.version.is_supported()
                    and (not pinned or v.version.full_string == pinned)
                    and (not pinned_sha or v.sha256 == pinned_sha)
                ),
                None,
            )
            if selected is None:
                raise RuntimeError(
                    "No compatible Camoufox version is available for the configured channel/pin."
                )
            fetcher = pkgman.CamoufoxFetcher(
                repo_config=repo, selected_version=selected
            )
        except Exception as exc:
            if previous.valid and not pinned:
                flag.touch()
                print(
                    f"Camoufox update failed; using local {previous.version}: {exc}",
                    file=sys.stderr,
                )
                return previous
            raise RuntimeError(f"Camoufox browser preparation failed: {exc}") from exc

        folder = multiversion.version_folder_name(
            fetcher.version, fetcher.build, selected.sha8
        )
        target_repo = multiversion.get_repo_name(fetcher.github_repo)
        spec = f"browsers/{target_repo}/{folder}"
        target, safe = _managed_candidate(root, spec)
        if (
            not safe
            or len(Path(spec).parts) != 3
            or target_repo != repo_name
            or target != Path(multiversion.BROWSERS_DIR) / target_repo / folder
        ):
            raise RuntimeError(
                "Camoufox browser preparation failed: unsafe target version path."
            )
        probe = _probe_runtime(pkgman, target, spec, safe)
        if not probe.managed_path_safe:
            raise RuntimeError(f"Camoufox browser preparation failed: {probe.message}")
        try:
            if not probe.valid or probe.version != selected.version.full_string:
                if previous.valid and target == previous.runtime_path:
                    raise RuntimeError(
                        "Target metadata differs from the release; preserving the validated active runtime."
                    )
                # Only this validated target can be removed; never purge the cache.
                if target.exists():
                    shutil.rmtree(target)
                print(
                    f"Preparing Camoufox {selected.version.full_string}",
                    file=sys.stderr,
                )
                multiversion.install_versioned(fetcher)
                probe = _probe_runtime(pkgman, target, spec, safe)
                if not probe.valid or probe.version != selected.version.full_string:
                    raise RuntimeError(
                        probe.message or "Installed Camoufox runtime failed validation."
                    )
            if multiversion.load_config().get("active_version") != spec:
                multiversion.set_active(spec)
            # Prevent upstream launch-time legacy cache cleanup, including on reuse.
            flag.touch()
            return probe
        except Exception as exc:
            multiversion.save_config(config)
            restored = probe_camoufox_managed_runtime()
            if restored.valid and not pinned:
                flag.touch()
                print(
                    f"Camoufox update failed; using local {restored.version}: {exc}",
                    file=sys.stderr,
                )
                return restored
            raise RuntimeError(f"Camoufox browser preparation failed: {exc}") from exc


__all__ = [
    "CamoufoxRuntimeProbe",
    "prepare_camoufox_managed_runtime",
    "probe_camoufox_managed_runtime",
]
