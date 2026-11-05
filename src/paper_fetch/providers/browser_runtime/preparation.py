"""Read-only inspection and request/launch preparation of managed Camoufox."""

from __future__ import annotations

from contextlib import contextmanager, redirect_stdout, suppress
from contextvars import ContextVar
from concurrent.futures import Future
from dataclasses import dataclass, field, replace
from importlib import import_module
from importlib.metadata import version as distribution_version
from importlib.util import find_spec
from io import BytesIO
from collections.abc import Callable, Iterator, Mapping
import json
import math
import os
from pathlib import Path
import stat
import shutil
import sys
import threading
import time
from typing import Any
from urllib.parse import quote
from zipfile import ZipFile

from filelock import FileLock, Timeout as LockTimeout

from ...utils import normalize_text
from ...config import BROWSER_BINARY_PATH_ENV_VAR, browser_env_value
from ...http import RequestCancelledError
from .paths import _atomic_write_json

DEFAULT_CHANNEL = "official/prerelease"
UPDATE_CHECK_INTERVAL_SECONDS = 86400
UPDATE_CHECK_FILENAME = ".paper-fetch-update-check.json"


class FetchBrowserPreparation:
    """Share in-flight work and successful preparation across request/batch users."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._results: dict[str, Future[Any]] = {}
        self.error: Exception | None = None

    def run(
        self,
        component: str,
        prepare: Callable[[], Any],
        cancel_check: Callable[[], None] = lambda: None,
        *,
        valid: Callable[[Any], bool] | None = None,
    ) -> Any:
        cancel_check()
        with self._lock:
            future = self._results.get(component)
            if (
                future is not None
                and future.done()
                and valid is not None
                and not valid(future.result())
            ):
                self._results.pop(component, None)
                future = None
            owner = future is None
            if future is None:
                future = Future()
                self._results[component] = future
        if owner:
            try:
                token = preparation_cancel_check.set(cancel_check)
                try:
                    result = prepare()
                    cancel_check()
                finally:
                    preparation_cancel_check.reset(token)
            except BaseException as exc:
                with self._lock:
                    self._results.pop(component, None)
                future.set_exception(exc)
                raise
            else:
                if not getattr(result, "preparation_succeeded", True):
                    with self._lock:
                        self._results.pop(component, None)
                future.set_result(result)
        while not future.done():
            cancel_check()
            try:
                return future.result(timeout=0.05)
            except TimeoutError:
                if future.done():
                    raise
        cancel_check()
        return future.result()

    def prepare(self, env: Mapping[str, str], cancel_check: Callable[[], None]) -> None:
        if not browser_env_value(env, BROWSER_BINARY_PATH_ENV_VAR) and all(
            find_spec(name) is not None for name in ("camoufox", "playwright")
        ):
            self.run(
                "camoufox",
                prepare_camoufox_managed_runtime,
                cancel_check,
                valid=lambda probe: (
                    probe.runtime_path is None or probe_camoufox_managed_runtime().valid
                ),
            )

    def require(self) -> None:
        self.prepare({}, preparation_cancel_check.get())


fetch_browser_preparation: ContextVar[FetchBrowserPreparation | None] = ContextVar(
    "fetch_browser_preparation", default=None
)


preparation_cancel_check: ContextVar[Callable[[], None]] = ContextVar(
    "preparation_cancel_check", default=lambda: None
)


@contextmanager
def _preparation_lock(path: Path) -> Iterator[None]:
    lock = FileLock(path)
    check = preparation_cancel_check.get()
    while True:
        check()
        try:
            lock.acquire(timeout=0.05)
            break
        except LockTimeout:
            continue
    try:
        check()
        yield
    finally:
        lock.release()


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
    preparation_succeeded: bool = field(default=True, compare=False)


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


def _recent_update_check(path: Path, identity: Mapping[str, Any]) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(payload, dict)
            or payload.get("result") != "success"
            or payload.get("version") != 2
            or any(
                key not in payload or payload[key] != value
                for key, value in identity.items()
            )
        ):
            return False
        checked_at = payload.get("checked_at")
        if (
            isinstance(checked_at, bool)
            or not isinstance(checked_at, (int, float))
            or not math.isfinite(checked_at)
            or checked_at < 0
        ):
            return False
        return 0 <= time.time() - checked_at < UPDATE_CHECK_INTERVAL_SECONDS
    except (OSError, ValueError, OverflowError):
        return False


def _write_update_check(
    root: Path, path: Path, identity: Mapping[str, Any], *, result: str = "success"
) -> None:
    try:
        if _path_chain_has_link(root, path):
            raise ValueError("Camoufox update-check record path is unsafe.")
        previous = {}
        with suppress(OSError, ValueError):
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                previous = loaded
        success_at = time.time() if result == "success" else previous.get("checked_at")
        _atomic_write_json(
            path,
            {
                **identity,
                "version": 2,
                "result": result,
                "checked_at": success_at,
                "attempted_at": time.time(),
            },
        )
    except (OSError, ValueError) as exc:
        print(f"Could not save Camoufox update check: {exc}", file=sys.stderr)


@contextmanager
def _record_update_check(
    root: Path, path: Path, identity: Mapping[str, Any]
) -> Iterator[dict[str, str]]:
    outcome = {"result": "success"}
    try:
        yield outcome
    except BaseException as exc:
        _write_update_check(
            root,
            path,
            identity,
            result=(
                "cancelled"
                if isinstance(exc, (RequestCancelledError, KeyboardInterrupt))
                else "failed"
            ),
        )
        raise
    else:
        try:
            preparation_cancel_check.get()()
        except BaseException:
            _write_update_check(root, path, identity, result="cancelled")
            raise
        _write_update_check(root, path, identity, result=outcome["result"])


def prepare_camoufox_fingerprint_model() -> None:
    """Verify/prepare the model pinned by the installed Camoufox package."""
    from requests.exceptions import RequestException

    model = import_module("camoufox.fpgen_model")
    try:
        model.ensure_fpgen_model()
    except RequestException:
        preparation_cancel_check.get()()
        _install_camoufox_model_from_github(model)
        model.ensure_fpgen_model()


def _install_camoufox_model_from_github(model: Any) -> None:
    """Seed the same pinned model via GitHub's asset API, retaining all hashes."""
    import requests

    pkgman = import_module("camoufox.pkgman")
    pin = model.PIN
    release_path = f"repos/{pin['repo']}/releases"
    release = pkgman.github_api(f"{release_path}/tags/{quote(pin['tag'], safe='')}")
    asset = next(
        (
            item
            for item in release.get("assets", [])
            if item.get("name") == pin["asset"]
        ),
        None,
    )
    if asset is None:
        raise RuntimeError(f"Pinned fpgen model asset is missing: {pin['tag']}")
    preparation_cancel_check.get()()
    headers = {"Accept": "application/octet-stream"}
    if pkgman.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {pkgman.GITHUB_TOKEN}"
    print("Retrying pinned fpgen model download via GitHub API", file=sys.stderr)
    with requests.get(
        f"https://api.github.com/{release_path}/assets/{int(asset['id'])}",
        headers=headers,
        timeout=60,
    ) as response:
        response.raise_for_status()
        buffer = BytesIO(response.content)
    model.verify_sha256(buffer, pin["sha256"], "fpgen model")
    members = {}
    with ZipFile(buffer) as archive:
        if sorted(archive.namelist()) != sorted(pin["file_sha256"]):
            raise model.CorruptedDownload(
                "fpgen model archive members differ from the pin."
            )
        for name, digest in pin["file_sha256"].items():
            content = archive.read(name)
            model.verify_sha256(BytesIO(content), digest, f"fpgen model member {name}")
            members[name] = content
    preparation_cancel_check.get()()
    # Do not replace upstream's downloader globally: other threads may use it.
    # Verify every member before writing, with the same lock/atomic writes/mtime
    # as Camoufox. ensure_fpgen_model then rechecks and stamps the model itself.
    with model._LOCK:
        data_dir = model.fpgen_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / model.STAMP).unlink(missing_ok=True)
        for name, content in members.items():
            model.write_atomic(data_dir / name, content, mtime=model.PINNED_MTIME)


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
    check_path = root / UPDATE_CHECK_FILENAME
    for path in (
        config_path,
        lock_path,
        flag,
        check_path,
        Path(multiversion.BROWSERS_DIR),
    ):
        if _path_chain_has_link(root, path):
            raise RuntimeError(
                "Camoufox browser preparation failed: unsafe managed cache path."
            )
    root.mkdir(parents=True, exist_ok=True)
    with _preparation_lock(lock_path), redirect_stdout(sys.stderr):
        if _path_chain_has_link(root, check_path):
            raise RuntimeError(
                "Camoufox browser preparation failed: unsafe managed cache path."
            )
        try:
            config = _read_config(root, config_path)
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"Camoufox browser preparation failed: {exc}") from exc
        previous = probe_camoufox_managed_runtime()
        if previous.runtime_path is not None and not previous.managed_path_safe:
            raise RuntimeError(
                f"Camoufox browser preparation failed: {previous.message}"
            )
        channel = config.get("channel") or (
            multiversion.get_default_channel()
            if config.get("pinned")
            else DEFAULT_CHANNEL
        )
        parts = channel.lower().split("/")
        repo_name, channel_type = parts if len(parts) == 2 else (parts[0], "stable")
        repo = pkgman.RepoConfig.find_by_name(repo_name)
        if (
            len(parts) > 2
            or channel_type not in {"stable", "prerelease"}
            or repo is None
        ):
            raise RuntimeError(
                "Camoufox browser preparation failed: invalid configured channel."
            )
        pinned = config.get("pinned")
        pinned_sha = config.get("pinned_sha")
        include_prerelease = channel_type == "prerelease"
        if not config.get("channel") and not pinned:
            # Disable upstream's implicit package pairing before any later launch.
            config["channel"] = channel
            multiversion.save_config(config)

        identity = {
            "channel": channel,
            "pinned": pinned,
            "pinned_sha": pinned_sha,
            "python_package_version": distribution_version("camoufox"),
        }
        try:
            preparation_cancel_check.get()()
            prepare_camoufox_fingerprint_model()
            preparation_cancel_check.get()()
        except BaseException as exc:
            cancelled = isinstance(exc, (RequestCancelledError, KeyboardInterrupt))
            _write_update_check(
                root,
                check_path,
                identity,
                result="cancelled" if cancelled else "failed",
            )
            raise

        # An explicit pin reuses its local build without a query.
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
                    and (include_prerelease or not item.is_prerelease)
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

        if not pinned and previous.valid and _recent_update_check(check_path, identity):
            flag.touch()
            return previous

        with _record_update_check(root, check_path, identity) as outcome:
            try:
                print(
                    f"Checking Camoufox runtime: {channel}{'/' + pinned if pinned else ''}",
                    file=sys.stderr,
                )
                versions = pkgman.list_available_versions(
                    repo,
                    include_prerelease=include_prerelease,
                )
                selected = next(
                    (
                        v
                        for v in versions
                        if (include_prerelease or not v.is_prerelease)
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
            except RequestCancelledError:
                raise
            except Exception as exc:
                if previous.valid and not pinned:
                    outcome["result"] = "failed"
                    flag.touch()
                    print(
                        f"Camoufox update failed; using local {previous.version}: {exc}",
                        file=sys.stderr,
                    )
                    return replace(previous, preparation_succeeded=False)
                raise RuntimeError(
                    f"Camoufox browser preparation failed: {exc}"
                ) from exc

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
                raise RuntimeError(
                    f"Camoufox browser preparation failed: {probe.message}"
                )
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
                            probe.message
                            or "Installed Camoufox runtime failed validation."
                        )
                if multiversion.load_config().get("active_version") != spec:
                    multiversion.set_active(spec)
                # Prevent upstream launch-time legacy cache cleanup, including on reuse.
                flag.touch()
                return probe
            except RequestCancelledError:
                multiversion.save_config(config)
                raise
            except Exception as exc:
                multiversion.save_config(config)
                restored = probe_camoufox_managed_runtime()
                if restored.valid and not pinned:
                    outcome["result"] = "failed"
                    flag.touch()
                    print(
                        f"Camoufox update failed; using local {restored.version}: {exc}",
                        file=sys.stderr,
                    )
                    return replace(restored, preparation_succeeded=False)
                raise RuntimeError(
                    f"Camoufox browser preparation failed: {exc}"
                ) from exc


__all__ = [
    "CamoufoxRuntimeProbe",
    "prepare_camoufox_managed_runtime",
    "probe_camoufox_managed_runtime",
]
