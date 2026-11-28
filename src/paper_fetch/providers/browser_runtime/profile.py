"""Exclusive, publisher-owned native profiles and credential-free state summaries."""

from __future__ import annotations

import contextlib
import errno
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from filelock import FileLock
from filelock import Timeout as FileLockTimeout

from ...http import RequestCancelledError
from ...http.transport import request_cancel_check
from .backends.scrapling import ScraplingManager
from .paths import _atomic_write_json, default_provider_user_data_dir
from .types import BrowserRuntimeConfig, BrowserRuntimeFailure

METADATA_FILENAME = "paper-fetch-profile.json"
PROFILE_LOCK_FILENAME = ".paper-fetch-profile.lock"


def profile_path(config: BrowserRuntimeConfig) -> Path:
    path = config.profile_dir or config.user_data_dir
    if path is None:
        path = default_provider_user_data_dir(os.environ, provider=config.provider)
    return Path(os.path.normcase(str(Path(path).expanduser().resolve())))


def _metadata(path: Path) -> dict[str, Any]:
    file = path / METADATA_FILENAME
    if not file.exists():
        return {}
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("expected an object")
        return data
    except (OSError, ValueError) as exc:
        raise BrowserRuntimeFailure(
            "browser_profile_metadata_invalid",
            f"Invalid native profile metadata: {file}: {exc}",
        ) from exc


def _native_stamp(path: Path) -> str:
    """Detect native state changes made outside the context that produced a summary."""
    facts = []
    for name in (
        "Default/Cookies",
        "Default/Cookies-journal",
        "Default/Network/Cookies",
        "Default/Network/Cookies-journal",
        "Default/Local Storage",
        "Default/IndexedDB",
    ):
        root = path / name
        candidates = [root, *root.rglob("*")] if root.is_dir() else [root]
        for candidate in candidates:
            try:
                stat = candidate.stat()
            except FileNotFoundError:
                continue
            facts.append(
                (str(candidate.relative_to(path)), stat.st_size, stat.st_mtime_ns)
            )
    return hashlib.sha256(json.dumps(sorted(facts)).encode()).hexdigest()


def _native_profile_occupied(path: Path) -> bool:
    """Check Chromium's singleton ownership without modifying native locks."""
    if os.name == "nt":
        try:
            with (path / "lockfile").open("r+b"):
                return False
        except FileNotFoundError:
            return False
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EPERM}:
                return True
            raise
    import socket

    native_socket = path / "SingletonSocket"
    if not native_socket.exists():
        return False
    try:
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(0.1)
            connection.connect(str(native_socket.resolve()))
        return True
    except (FileNotFoundError, ConnectionRefusedError):
        return False


def trusted_profile_digest(
    path: Path,
    provider: str,
    *,
    locked: bool = False,
) -> str | None:
    """Read only an idle, unchanged profile summary, or our own locked profile."""
    path = path.expanduser().resolve()
    if not path.is_dir():
        return None
    lock = FileLock(str(path / PROFILE_LOCK_FILENAME), thread_local=False)
    try:
        if not locked:
            lock.acquire(timeout=0)
        if not locked and _native_profile_occupied(path):
            return None
        data = _metadata(path)
        if data.get("provider") != provider or not data.get("state_sha256"):
            return None
        if not locked and data.get("native_stamp") != _native_stamp(path):
            return None
        return str(data["state_sha256"])
    except (FileLockTimeout, OSError, BrowserRuntimeFailure):
        return None
    finally:
        if not locked and lock.is_locked:
            lock.release()


class PublisherProfileManager:
    """Hold the directory lease until its native context has been closed."""

    def __init__(
        self, config: BrowserRuntimeConfig, *, runtime_context: Any = None
    ) -> None:
        self.config = config
        self.path = profile_path(config)
        self.runtime_context = runtime_context
        self.owner_thread = threading.get_ident()
        self.lock = FileLock(str(self.path / PROFILE_LOCK_FILENAME), thread_local=False)
        self.manager: ScraplingManager | None = None
        self.context: Any = None
        self.execution_started_at: float | None = None
        self.metadata: dict[str, Any] = {}
        self.diagnostics: dict[str, Any] = {
            "path": str(self.path),
            "provider": config.provider,
            "native_profile_loaded": False,
            "context_reused": False,
        }

    def _assert_owner(self) -> None:
        if threading.get_ident() != self.owner_thread:
            raise RuntimeError(
                "Publisher browser profile must be used and closed on its owning thread."
            )

    def _acquire(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
        from ...workflow.execution_slots import profile_wait

        started = time.monotonic()
        if self.runtime_context is not None:
            self.runtime_context.report_progress(
                "stage", stage="waiting_profile", profile=str(self.path)
            )
        with profile_wait(
            self.runtime_context.raise_if_cancelled
            if self.runtime_context is not None
            else None
        ):
            while True:
                if self.runtime_context is not None:
                    self.runtime_context.raise_if_cancelled()
                else:
                    cancelled = request_cancel_check.get()
                    if cancelled is not None and cancelled():
                        raise RequestCancelledError(
                            "Request cancelled while waiting for profile."
                        )
                try:
                    self.lock.acquire(timeout=0)
                    break
                except FileLockTimeout:
                    time.sleep(0.05)
        waited = time.monotonic() - started
        self.diagnostics["profile_queue_seconds"] = waited
        self.execution_started_at = time.monotonic()
        if self.runtime_context is not None:
            if self.runtime_context.browser_deadline_monotonic is not None:
                self.runtime_context.browser_deadline_monotonic += waited
            self.runtime_context.start_browser_budget(self.config.timeout_ms / 1000)
            self.runtime_context.report_progress(
                "stage",
                stage="executing_browser",
                profile=str(self.path),
                queue_seconds=waited,
            )

    def new_context(self) -> Any:
        self._assert_owner()
        if self.context is not None:
            self.diagnostics.update(context_reused=True, native_profile_loaded=False)
            self.manager.diagnostics["context_reused"] = True
            self.refresh()
            return self.context
        try:
            self._acquire()
            if self.runtime_context is not None:
                self.runtime_context.raise_if_cancelled()
            self.metadata = _metadata(self.path)
            owner = self.metadata.get("provider")
            if owner is not None and owner != self.config.provider:
                raise BrowserRuntimeFailure(
                    "browser_profile_provider_conflict",
                    f"Publisher profile {self.path} belongs to {owner}; cannot use it for {self.config.provider}.",
                )
            # Never remove Chromium's own locks; a live external owner must fail clearly.
            if _native_profile_occupied(self.path):
                raise BrowserRuntimeFailure(
                    "browser_profile_external_occupancy",
                    f"Native Chromium profile is externally occupied (or has a native lock): {self.path}",
                )
            self.diagnostics["native_profile_reopened"] = self.metadata.get(
                "native_initialized",
                any(
                    (self.path / name).exists()
                    for name in (
                        "Local State",
                        "Default/Preferences",
                    )
                ),
            )
            self.metadata.setdefault(
                "native_initialized", self.diagnostics["native_profile_reopened"]
            )
            self.metadata["provider"] = self.config.provider
            _atomic_write_json(self.path / METADATA_FILENAME, self.metadata)
            self.manager = ScraplingManager(
                self.config,
                runtime_context=self.runtime_context,
                native_profile=self.path,
            )
            try:
                self.context = self.manager.new_context()
            except Exception as exc:
                if isinstance(exc, (BrowserRuntimeFailure, RequestCancelledError)):
                    raise
                raise BrowserRuntimeFailure(
                    "browser_profile_load_failed",
                    f"Failed to load native publisher profile {self.path}: {exc}",
                    details={
                        "stage": "native_profile_load",
                        "profile_dir": str(self.path),
                        "provider": self.config.provider,
                    },
                ) from exc
            self.diagnostics["native_profile_loaded"] = True
            self.metadata["native_initialized"] = True
            self.refresh()
            return self.context
        except BaseException:
            self.close()
            raise

    def refresh(self) -> str | None:
        self._assert_owner()
        if self.manager is not None:
            self.diagnostics.update(
                {
                    key: value
                    for key, value in getattr(self.manager, "diagnostics", {}).items()
                    if key != "context_reused"
                }
            )
        if self.context is None:
            return None
        try:
            if not self.metadata.get("native_initialized"):
                raise ValueError("native profile initialization did not complete")
            state = self.context.storage_state()
            if (
                not isinstance(state, dict)
                or not isinstance(state.get("cookies"), list)
                or not isinstance(state.get("origins"), list)
            ):
                raise ValueError("context did not expose a storage-state summary")
            # Canonical ordering avoids cache churn from cookie enumeration order.
            state = dict(state)
            state["cookies"] = sorted(
                state["cookies"], key=lambda item: json.dumps(item, sort_keys=True)
            )
            state["origins"] = sorted(
                state["origins"], key=lambda item: json.dumps(item, sort_keys=True)
            )
            digest = hashlib.sha256(
                json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            self.metadata["state_sha256"] = digest
            self.metadata["native_stamp"] = _native_stamp(self.path)
            _atomic_write_json(self.path / METADATA_FILENAME, self.metadata)
        except Exception:
            digest = None
            self.metadata.pop("state_sha256", None)
            with contextlib.suppress(OSError):
                _atomic_write_json(self.path / METADATA_FILENAME, self.metadata)
        if self.runtime_context is not None:
            self.runtime_context.record_browser_state_capability_use(
                provider=self.config.provider,
                backend=self.config.backend,
                profile_dir=self.path,
                content_sha256=digest,
            )
        return digest

    def close(self) -> None:
        self._assert_owner()
        try:
            if self.context is not None:
                self.refresh()
            if self.manager is not None:
                self.manager.close()
            if self.context is not None:
                self.metadata["native_stamp"] = _native_stamp(self.path)
                _atomic_write_json(self.path / METADATA_FILENAME, self.metadata)
        finally:
            try:
                if self.execution_started_at is not None:
                    elapsed = time.monotonic() - self.execution_started_at
                    self.diagnostics["browser_execution_seconds"] = elapsed
                    if self.runtime_context is not None:
                        self.runtime_context.report_progress(
                            "stage",
                            stage="browser_finished",
                            execution_seconds=elapsed,
                            queue_seconds=self.diagnostics.get(
                                "profile_queue_seconds", 0
                            ),
                        )
                    self.execution_started_at = None
            finally:
                self.manager = None
                self.context = None
                self.lock.release()
