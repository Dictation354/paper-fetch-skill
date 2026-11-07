"""Exclusive, publisher-owned native profiles and credential-free state summaries."""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import json
import errno
import os
import threading
import time
from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout as FileLockTimeout

from .byparr_manager import ByparrManager
from .paths import (
    _atomic_write_json,
    _filtered_storage_state_mapping,
    storage_state_path,
)
from .types import BrowserRuntimeConfig, BrowserRuntimeFailure

METADATA_FILENAME = "paper-fetch-profile.json"
PROFILE_LOCK_FILENAME = ".paper-fetch-profile.lock"


def profile_path(config: BrowserRuntimeConfig) -> Path:
    path = config.profile_dir or config.user_data_dir
    if path is None:
        from .paths import default_provider_user_data_dir

        path = default_provider_user_data_dir(
            os.environ, provider=config.provider, backend=config.backend
        )
    return Path(path).expanduser().resolve()


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
        "cookies.sqlite",
        "cookies.sqlite-wal",
        "storage.sqlite",
        "storage",
        "webappsstore.sqlite",
        "sessionstore.jsonlz4",
        "sessionstore-backups",
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
    """Probe the native OS lock without unlinking Firefox's persistent lock files."""
    filename = path / ("parent.lock" if os.name == "nt" else ".parentlock")
    if not filename.exists():
        return False
    try:
        with filename.open("r+b") as handle:
            if os.name == "nt":
                msvcrt = importlib.import_module("msvcrt")
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.lockf(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.lockf(handle.fileno(), fcntl.LOCK_UN)
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EPERM}:
            return True
        raise
    return False


def trusted_profile_digest(
    path: Path,
    provider: str,
    *,
    locked: bool = False,
    explicit_state_path: Path | None = None,
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
        if explicit_state_path is not None:
            explicit = explicit_state_path.expanduser().resolve()
            imported = data.get("migrations", {}).get(str(explicit))
            if (
                explicit.is_file()
                and hashlib.sha256(explicit.read_bytes()).hexdigest() != imported
            ):
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
        self.manager: ByparrManager | None = None
        self.context: Any = None
        self.metadata: dict[str, Any] = {}
        self.diagnostics: dict[str, Any] = {
            "path": str(self.path),
            "provider": config.provider,
            "native_profile_loaded": False,
            "context_reused": False,
            "json_imported": False,
        }

    def _assert_owner(self) -> None:
        if threading.get_ident() != self.owner_thread:
            raise RuntimeError(
                "Publisher browser profile must be used and closed on its owning thread."
            )

    def _acquire(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.config.timeout_ms / 1000
        while True:
            if self.runtime_context is not None:
                self.runtime_context.raise_if_cancelled()
                remaining = self.runtime_context.remaining_seconds(
                    self.config.timeout_ms / 1000
                )
            else:
                remaining = self.config.timeout_ms / 1000
            if min(remaining, deadline - time.monotonic()) <= 0:
                raise BrowserRuntimeFailure(
                    "browser_profile_lock_timeout",
                    f"Timed out waiting for publisher profile: {self.path}",
                )
            try:
                self.lock.acquire(timeout=0)
                return
            except FileLockTimeout:
                time.sleep(min(0.05, remaining, max(0, deadline - time.monotonic())))

    def new_context(self) -> Any:
        self._assert_owner()
        if self.context is not None:
            self.diagnostics.update(
                context_reused=True, native_profile_loaded=False, json_imported=False
            )
            self.diagnostics.pop("json_import_path", None)
            self.diagnostics.pop("json_import_sha256", None)
            self.refresh()
            return self.context
        self._acquire()
        try:
            if self.runtime_context is not None:
                self.runtime_context.raise_if_cancelled()
            self.metadata = _metadata(self.path)
            owner = self.metadata.get("provider")
            if owner is not None and owner != self.config.provider:
                raise BrowserRuntimeFailure(
                    "browser_profile_provider_conflict",
                    f"Publisher profile {self.path} belongs to {owner}; cannot use it for {self.config.provider}.",
                )
            # Never remove Firefox's own locks; a live external owner must fail clearly.
            if _native_profile_occupied(self.path):
                raise BrowserRuntimeFailure(
                    "browser_profile_external_occupancy",
                    f"Native Firefox profile is externally occupied (or has a native lock): {self.path}",
                )
            native_exists = self.metadata.get(
                "native_initialized",
                any(
                    (self.path / name).exists()
                    for name in (
                        "prefs.js",
                        "cookies.sqlite",
                        "storage",
                        "compatibility.ini",
                    )
                ),
            )
            self.metadata.setdefault("native_initialized", bool(native_exists))
            self.metadata["provider"] = self.config.provider
            _atomic_write_json(self.path / METADATA_FILENAME, self.metadata)
            self.manager = ByparrManager(
                self.config,
                runtime_context=self.runtime_context,
                native_profile=self.path,
            )
            try:
                self.context = self.manager.new_context()
            except Exception as exc:
                from ...http import RequestCancelledError

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
            self._import_legacy(bool(native_exists))
            self.metadata["native_initialized"] = True
            self.refresh()
            return self.context
        except BaseException:
            self.close()
            raise

    def _import_legacy(self, native_exists: bool) -> None:
        path = storage_state_path(self.config)
        if path is None or not path.is_file():
            return
        explicit = self.config.storage_state_path is not None
        if native_exists and not explicit:
            return
        try:
            payload_bytes = path.read_bytes()
        except OSError as exc:
            raise BrowserRuntimeFailure(
                "browser_profile_json_import_failed",
                f"Cannot read legacy JSON {path}: {exc}",
                details={"stage": "json_import", "profile_dir": str(self.path)},
            ) from exc
        digest = hashlib.sha256(payload_bytes).hexdigest()
        key = str(path.expanduser().resolve())
        migrations = self.metadata.setdefault("migrations", {})
        if migrations.get(key) == digest:
            return
        from ...provider_catalog import provider_domains

        domains = provider_domains(self.config.provider)
        try:
            payload = _filtered_storage_state_mapping(
                json.loads(payload_bytes),
                url=f"https://{domains[0]}/" if domains else "",
                provider=self.config.provider,
            )
        except (ValueError, TypeError, AttributeError) as exc:
            raise BrowserRuntimeFailure(
                "browser_profile_json_import_failed",
                f"Cannot import legacy JSON {path}: {exc}",
                details={"stage": "json_import", "profile_dir": str(self.path)},
            ) from exc
        if payload is None:
            raise BrowserRuntimeFailure(
                "browser_profile_json_import_failed",
                f"Cannot import publisher JSON: {path}",
            )
        try:
            cookies = payload.get("cookies") or []
            if cookies:
                self.context.add_cookies(cookies)
            for origin in payload.get("origins") or []:
                page = self.context.new_page()
                try:
                    from .navigation import navigate_page

                    navigate_page(
                        page,
                        origin["origin"],
                        wait_until="domcontentloaded",
                        timeout_ms=self.config.timeout_ms,
                    )
                    page.evaluate(
                        "items => { for (const item of items) localStorage.setItem(item.name, item.value); }",
                        origin.get("localStorage") or [],
                    )
                finally:
                    page.close()
        except Exception as exc:
            raise BrowserRuntimeFailure(
                "browser_profile_json_import_failed",
                f"Legacy JSON import failed for {self.path}: {exc}",
            ) from exc
        migrations[key] = digest
        self.diagnostics.update(
            json_imported=True, json_import_path=key, json_import_sha256=digest
        )

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
                backend="byparr",
                storage_state_path=self.path,
                content_sha256=digest,
            )
        return digest

    def note_json_export(self, path: Path) -> None:
        """Our own explicit export must not be re-imported as an external change."""
        self._assert_owner()
        if self.config.storage_state_path is None:
            return
        canonical = path.expanduser().resolve()
        if canonical != self.config.storage_state_path.expanduser().resolve():
            return
        self.metadata.setdefault("migrations", {})[str(canonical)] = hashlib.sha256(
            canonical.read_bytes()
        ).hexdigest()
        _atomic_write_json(self.path / METADATA_FILENAME, self.metadata)

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
            self.manager = None
            self.context = None
            self.lock.release()
