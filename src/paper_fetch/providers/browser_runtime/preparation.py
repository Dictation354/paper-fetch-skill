"""Policy-controlled preparation of the Camoufox managed browser runtime."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from importlib import import_module
import json
import logging
import os
from pathlib import Path
import queue
import stat
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any
from collections.abc import Callable, Iterator, Mapping

from filelock import FileLock, Timeout as FileLockTimeout

from ...failure import FailureDiagnostics
from ...logging_utils import emit_structured_log
from ..base import ProviderFailure
from ...reason_codes import (
    BROWSER_RUNTIME_PREPARE_CANCELLED,
    BROWSER_RUNTIME_PREPARE_FAILED,
    BROWSER_RUNTIME_PREPARE_TIMEOUT,
    BROWSER_RUNTIME_REPAIR_FAILED,
)
from ...utils import normalize_text

DEFAULT_PREPARE_TIMEOUT_SECONDS = 900.0
UPDATE_INTERVAL_SECONDS = 24 * 60 * 60
UPDATE_FAILURE_BACKOFF_SECONDS = 60 * 60
REQUIRED_FAILURE_COOLDOWN_SECONDS = 60
LOCK_POLL_SECONDS = 0.1
STATE_SCHEMA_VERSION = 1
_MAX_OUTPUT_LINE_CHARS = 1_000
_MAX_OUTPUT_TAIL_LINES = 20

logger = logging.getLogger("paper_fetch.browser_runtime")
_scope = threading.local()


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


@dataclass(frozen=True)
class CamoufoxPreparationOutcome:
    action: str
    attempted: bool
    ready: bool
    version_before: str | None
    version_after: str | None
    waited_for_lock: bool = False
    warning: str | None = None


@contextmanager
def browser_runtime_preparation_scope(
    *,
    cancel_check: Callable[[], bool] | None = None,
) -> Iterator[None]:
    """Attach cooperative cancellation to preparation on the current thread."""

    previous = getattr(_scope, "cancel_check", None)
    _scope.cancel_check = cancel_check
    try:
        yield
    finally:
        _scope.cancel_check = previous


def _cancelled() -> bool:
    check = getattr(_scope, "cancel_check", None)
    if not callable(check):
        return False
    try:
        return bool(check())
    except Exception:
        return False


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
    """Inspect the active managed runtime without downloading anything."""

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
            message="Camoufox active runtime path is outside the managed cache or is a link.",
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
                message="Camoufox managed browser runtime is incompatible with the installed Python package.",
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


def _coordinator_paths() -> tuple[Path, Path]:
    pkgman = import_module("camoufox.pkgman")
    install_dir = Path(pkgman.INSTALL_DIR)
    parent = install_dir.parent
    stem = f".{install_dir.name}.paper-fetch-runtime"
    return parent / f"{stem}.lock", parent / f"{stem}.json"


def _read_state(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != STATE_SCHEMA_VERSION
    ):
        return {}
    return payload


def _write_state(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"schema_version": STATE_SCHEMA_VERSION, **dict(payload)}
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(data, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            temporary_path = Path(handle.name)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _emit(
    stage: str,
    message: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    emit_structured_log(
        logger,
        level,
        "camoufox_runtime_prepare",
        stage=stage,
        message=normalize_text(message),
        **fields,
    )


def _failure_details(
    *,
    action: str,
    probe: CamoufoxRuntimeProbe,
    output_tail: list[str] | None = None,
) -> FailureDiagnostics:
    return FailureDiagnostics(
        stage="browser_runtime_prepare",
        retryable=True,
        details={
            "action": action,
            "runtime_state": probe.state,
            "runtime_installed": probe.installed,
            "runtime_valid": probe.valid,
            "version": probe.version,
            "output_tail": list(output_tail or [])[-_MAX_OUTPUT_TAIL_LINES:],
        },
    )


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _read_process_output(
    stream: Any,
    messages: queue.Queue[str | None],
) -> None:
    try:
        for raw_line in iter(stream.readline, ""):
            messages.put(raw_line)
    finally:
        messages.put(None)


def _run_camoufox_command(
    arguments: list[str],
    *,
    action: str,
    deadline: float,
    clock: Callable[[], float],
) -> tuple[int, list[str]]:
    command = [sys.executable, "-X", "utf8", "-m", "camoufox", *arguments]
    try:
        process = subprocess.Popen(  # noqa: S603 - fixed interpreter/module command.
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except OSError as exc:
        raise ProviderFailure(
            BROWSER_RUNTIME_PREPARE_FAILED,
            f"Could not start the official Camoufox package manager: {exc}",
            diagnostics=FailureDiagnostics(
                stage="browser_runtime_prepare",
                retryable=True,
                details={"action": action, "command": command[:4]},
            ),
        ) from exc
    assert process.stdout is not None
    messages: queue.Queue[str | None] = queue.Queue()
    reader = threading.Thread(
        target=_read_process_output,
        args=(process.stdout, messages),
        name="paper-fetch-camoufox-output",
        daemon=True,
    )
    reader.start()
    output_tail: list[str] = []
    reader_finished = False
    try:
        while process.poll() is None:
            if _cancelled():
                _terminate_process(process)
                raise ProviderFailure(
                    BROWSER_RUNTIME_PREPARE_CANCELLED,
                    "Camoufox runtime preparation was cancelled.",
                    diagnostics=_failure_details(
                        action=action,
                        probe=probe_camoufox_managed_runtime(),
                        output_tail=output_tail,
                    ),
                )
            if clock() >= deadline:
                _terminate_process(process)
                raise ProviderFailure(
                    BROWSER_RUNTIME_PREPARE_TIMEOUT,
                    "Camoufox runtime preparation exceeded its 900-second budget.",
                    diagnostics=_failure_details(
                        action=action,
                        probe=probe_camoufox_managed_runtime(),
                        output_tail=output_tail,
                    ),
                )
            try:
                raw_line = messages.get(timeout=LOCK_POLL_SECONDS)
            except queue.Empty:
                continue
            if raw_line is None:
                reader_finished = True
                continue
            line = normalize_text(raw_line)[:_MAX_OUTPUT_LINE_CHARS]
            if line:
                output_tail.append(line)
                output_tail = output_tail[-_MAX_OUTPUT_TAIL_LINES:]
                _emit("command_output", line, action=action)
        if not reader_finished:
            reader.join(timeout=1)
        while True:
            try:
                raw_line = messages.get_nowait()
            except queue.Empty:
                break
            if raw_line is None:
                continue
            line = normalize_text(raw_line)[:_MAX_OUTPUT_LINE_CHARS]
            if line:
                output_tail.append(line)
                output_tail = output_tail[-_MAX_OUTPUT_TAIL_LINES:]
                _emit("command_output", line, action=action)
        return int(process.returncode or 0), output_tail
    except KeyboardInterrupt:
        _terminate_process(process)
        raise
    finally:
        process.stdout.close()


def _command_failed(return_code: int, output_tail: list[str]) -> bool:
    if return_code != 0:
        return True
    lowered = [line.casefold() for line in output_tail]
    return any(
        "error:" in line
        or ("not found" in line and "version" in line)
        or "run 'camoufox sync'" in line
        for line in lowered
    )


def _acquire_lock(
    lock: FileLock,
    *,
    deadline: float,
    clock: Callable[[], float],
) -> bool:
    waited = False
    while True:
        if _cancelled():
            raise ProviderFailure(
                BROWSER_RUNTIME_PREPARE_CANCELLED,
                "Camoufox runtime preparation was cancelled while waiting for another process.",
                diagnostics=FailureDiagnostics(
                    stage="browser_runtime_prepare",
                    retryable=True,
                    details={"action": "wait_for_lock"},
                ),
            )
        if clock() >= deadline:
            raise ProviderFailure(
                BROWSER_RUNTIME_PREPARE_TIMEOUT,
                "Timed out waiting for another Camoufox runtime preparation process.",
                diagnostics=FailureDiagnostics(
                    stage="browser_runtime_prepare",
                    retryable=True,
                    details={"action": "wait_for_lock"},
                ),
            )
        try:
            lock.acquire(timeout=0)
            return waited
        except FileLockTimeout:
            if not waited:
                _emit(
                    "waiting_for_lock",
                    "Waiting for another process to finish preparing Camoufox.",
                )
                waited = True
            time.sleep(LOCK_POLL_SECONDS)


def _update_due(state: Mapping[str, Any], *, now: float) -> bool:
    last_success = state.get("last_successful_check_at")
    if (
        isinstance(last_success, (int, float))
        and now - float(last_success) < UPDATE_INTERVAL_SECONDS
    ):
        return False
    last_failure = state.get("last_update_failure_at")
    return not (
        isinstance(last_failure, (int, float))
        and now - float(last_failure) < UPDATE_FAILURE_BACKOFF_SECONDS
    )


def _required_failure_in_cooldown(state: Mapping[str, Any], *, now: float) -> bool:
    last_failure = state.get("last_required_failure_at")
    return bool(
        isinstance(last_failure, (int, float))
        and now - float(last_failure) < REQUIRED_FAILURE_COOLDOWN_SECONDS
    )


def _repair_managed_runtime(
    probe: CamoufoxRuntimeProbe,
    *,
    deadline: float,
    clock: Callable[[], float],
) -> tuple[CamoufoxRuntimeProbe, list[str]]:
    if not probe.active_spec or not probe.managed_path_safe:
        raise ProviderFailure(
            BROWSER_RUNTIME_REPAIR_FAILED,
            "The damaged Camoufox runtime could not be mapped to one safe managed version; no files were removed.",
            diagnostics=_failure_details(action="repair", probe=probe),
        )
    _emit(
        "repairing",
        "Removing the exact damaged Camoufox managed version before reinstalling it.",
        action="repair",
    )
    remove_code, remove_output = _run_camoufox_command(
        ["remove", probe.active_spec, "--yes"],
        action="repair_remove",
        deadline=deadline,
        clock=clock,
    )
    if _command_failed(remove_code, remove_output):
        raise ProviderFailure(
            BROWSER_RUNTIME_REPAIR_FAILED,
            "Camoufox could not remove its damaged managed version.",
            diagnostics=_failure_details(
                action="repair_remove",
                probe=probe,
                output_tail=remove_output,
            ),
        )
    fetch_code, fetch_output = _run_camoufox_command(
        ["fetch"],
        action="repair_fetch",
        deadline=deadline,
        clock=clock,
    )
    repaired = probe_camoufox_managed_runtime()
    if _command_failed(fetch_code, fetch_output) or not repaired.valid:
        raise ProviderFailure(
            BROWSER_RUNTIME_REPAIR_FAILED,
            "Camoufox runtime repair did not produce a valid browser executable.",
            diagnostics=_failure_details(
                action="repair_fetch",
                probe=repaired,
                output_tail=fetch_output,
            ),
        )
    return repaired, [*remove_output, *fetch_output][-_MAX_OUTPUT_TAIL_LINES:]


def _ensure_camoufox_managed_runtime(
    *,
    timeout_seconds: float = DEFAULT_PREPARE_TIMEOUT_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    wall_clock: Callable[[], float] = time.time,
) -> CamoufoxPreparationOutcome:
    """Install, repair, or periodically update the managed runtime once."""

    before = probe_camoufox_managed_runtime()
    lock_path, state_path = _coordinator_paths()
    now = wall_clock()
    state = _read_state(state_path)
    required = not before.valid
    if not required and not _update_due(state, now=now):
        return CamoufoxPreparationOutcome(
            action="none",
            attempted=False,
            ready=True,
            version_before=before.version,
            version_after=before.version,
        )
    if required and _required_failure_in_cooldown(state, now=now):
        raise ProviderFailure(
            BROWSER_RUNTIME_PREPARE_FAILED,
            "A recent Camoufox runtime preparation failed; retry shortly or run `python -m camoufox fetch` explicitly.",
            diagnostics=_failure_details(action="cooldown", probe=before),
        )

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(lock_path))
    deadline = clock() + max(1.0, float(timeout_seconds))
    waited = _acquire_lock(lock, deadline=deadline, clock=clock)
    try:
        current = probe_camoufox_managed_runtime()
        state = _read_state(state_path)
        now = wall_clock()
        required = not current.valid
        if not required and not _update_due(state, now=now):
            return CamoufoxPreparationOutcome(
                action="wait" if waited else "none",
                attempted=False,
                ready=True,
                version_before=before.version,
                version_after=current.version,
                waited_for_lock=waited,
            )

        action = (
            "install" if not current.installed else ("repair" if required else "update")
        )
        _emit(
            "starting",
            f"Starting Camoufox runtime {action}.",
            action=action,
            version_before=current.version,
        )
        try:
            return_code, output_tail = _run_camoufox_command(
                ["fetch"],
                action=action,
                deadline=deadline,
                clock=clock,
            )
        except ProviderFailure as exc:
            if exc.code == BROWSER_RUNTIME_PREPARE_CANCELLED:
                raise
            fallback = probe_camoufox_managed_runtime()
            if current.valid and fallback.valid:
                warning = (
                    "Camoufox update check failed; continuing with the existing "
                    "valid runtime."
                )
                _write_state(
                    state_path,
                    {
                        **state,
                        "last_update_failure_at": wall_clock(),
                        "last_action": action,
                        "version": fallback.version,
                    },
                )
                _emit(
                    "update_warning",
                    warning,
                    level=logging.WARNING,
                    action=action,
                    version_after=fallback.version,
                    reason_code=exc.code,
                )
                return CamoufoxPreparationOutcome(
                    action=action,
                    attempted=True,
                    ready=True,
                    version_before=before.version,
                    version_after=fallback.version,
                    waited_for_lock=waited,
                    warning=warning,
                )
            _write_state(
                state_path,
                {
                    **state,
                    "last_required_failure_at": wall_clock(),
                    "last_action": action,
                },
            )
            raise
        after = probe_camoufox_managed_runtime()

        command_failed = _command_failed(return_code, output_tail)
        if required and not after.valid:
            if current.installed:
                try:
                    after, repair_output = _repair_managed_runtime(
                        current,
                        deadline=deadline,
                        clock=clock,
                    )
                    output_tail = [*output_tail, *repair_output][
                        -_MAX_OUTPUT_TAIL_LINES:
                    ]
                    return_code = 0
                    command_failed = False
                except ProviderFailure as exc:
                    if exc.code != BROWSER_RUNTIME_PREPARE_CANCELLED:
                        _write_state(
                            state_path,
                            {
                                **state,
                                "last_required_failure_at": wall_clock(),
                                "last_action": action,
                            },
                        )
                    raise
            if not after.valid:
                _write_state(
                    state_path,
                    {
                        **state,
                        "last_required_failure_at": wall_clock(),
                        "last_action": action,
                    },
                )
                raise ProviderFailure(
                    BROWSER_RUNTIME_PREPARE_FAILED,
                    "Camoufox runtime preparation did not produce a valid browser executable.",
                    diagnostics=_failure_details(
                        action=action,
                        probe=after,
                        output_tail=output_tail,
                    ),
                )

        if not required and (command_failed or not after.valid):
            fallback = probe_camoufox_managed_runtime()
            warning = "Camoufox update check failed; continuing with the existing valid runtime."
            if not fallback.valid:
                raise ProviderFailure(
                    BROWSER_RUNTIME_PREPARE_FAILED,
                    "Camoufox update failed and no valid managed runtime remains available.",
                    diagnostics=_failure_details(
                        action=action,
                        probe=fallback,
                        output_tail=output_tail,
                    ),
                )
            _write_state(
                state_path,
                {
                    **state,
                    "last_update_failure_at": wall_clock(),
                    "last_action": action,
                    "version": fallback.version,
                },
            )
            _emit(
                "update_warning",
                warning,
                level=logging.WARNING,
                action=action,
                version_after=fallback.version,
            )
            return CamoufoxPreparationOutcome(
                action=action,
                attempted=True,
                ready=True,
                version_before=before.version,
                version_after=fallback.version,
                waited_for_lock=waited,
                warning=warning,
            )

        readiness_warning: str | None = None
        if command_failed:
            readiness_warning = (
                "Camoufox became usable, but its repository or optional-component "
                "update reported an error; the next update check will retry later."
            )
            _write_state(
                state_path,
                {
                    "last_update_failure_at": wall_clock(),
                    "last_action": action,
                    "version": after.version,
                },
            )
            _emit(
                "prepare_warning",
                readiness_warning,
                level=logging.WARNING,
                action=action,
                version_after=after.version,
            )
        else:
            _write_state(
                state_path,
                {
                    "last_successful_check_at": wall_clock(),
                    "last_action": action,
                    "version": after.version,
                },
            )
        _emit(
            "ready",
            "Camoufox managed runtime is ready.",
            action=action,
            version_after=after.version,
        )
        return CamoufoxPreparationOutcome(
            action=action,
            attempted=True,
            ready=True,
            version_before=before.version,
            version_after=after.version,
            waited_for_lock=waited,
            warning=readiness_warning,
        )
    finally:
        lock.release()


def ensure_camoufox_managed_runtime(
    *,
    timeout_seconds: float = DEFAULT_PREPARE_TIMEOUT_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    wall_clock: Callable[[], float] = time.time,
) -> CamoufoxPreparationOutcome:
    """Prepare the managed runtime and normalize local coordinator failures."""

    try:
        return _ensure_camoufox_managed_runtime(
            timeout_seconds=timeout_seconds,
            clock=clock,
            wall_clock=wall_clock,
        )
    except ProviderFailure:
        raise
    except Exception as exc:
        raise ProviderFailure(
            BROWSER_RUNTIME_PREPARE_FAILED,
            f"Camoufox runtime preparation could not access its managed state: {exc}",
            diagnostics=FailureDiagnostics(
                stage="browser_runtime_prepare",
                retryable=True,
                details={"exception_type": exc.__class__.__name__},
            ),
        ) from exc


__all__ = [
    "CamoufoxPreparationOutcome",
    "CamoufoxRuntimeProbe",
    "browser_runtime_preparation_scope",
    "ensure_camoufox_managed_runtime",
    "probe_camoufox_managed_runtime",
]
