"""Browser lifecycle manager."""

from __future__ import annotations

from contextlib import suppress
from collections import deque
from datetime import UTC, datetime
import errno
import json
import logging
import os
from pathlib import Path
import re
import socket
import subprocess
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from collections.abc import Mapping
from typing import Any

from filelock import FileLock, Timeout

from .config import resolve_user_data_dir
from .reason_codes import (
    BROWSER_CONTEXT_CREATE_FAILED,
    CDP_CONNECT_FAILED,
    MANAGED_CHROME_CDP_TIMEOUT,
    MANAGED_CHROME_EXITED_BEFORE_CDP,
    MANAGED_CHROME_PROFILE_IN_USE,
)

DEFAULT_BROWSER_LOCALE = "en-US"
DEFAULT_BROWSER_VIEWPORT = {"width": 1440, "height": 1600}
DEFAULT_CDP_STARTUP_TIMEOUT_SECONDS = 30.0
DEFAULT_PROFILE_LOCK_TIMEOUT_SECONDS = 30.0
PROFILE_LOCK_FILENAME = ".paper-fetch-profile.lock"
CHROMIUM_SINGLETON_FILENAMES = (
    "SingletonLock",
    "SingletonSocket",
    "SingletonCookie",
)
BROWSER_DIAGNOSTIC_DIRNAME = ".paper-fetch-browser-diagnostics"
DEFAULT_BROWSER_STDERR_TAIL_BYTES = 64 * 1024
DEFAULT_BROWSER_ERROR_SUMMARY_CHARS = 2048
logger = logging.getLogger("paper_fetch.runtime_browser")


class ManagedBrowserError(RuntimeError):
    """A managed/external CDP lifecycle failure with a stable stage code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        stage: str,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        safe_message = _redact_diagnostic_text(str(message), max_chars=4096)
        safe_details = _redact_diagnostic_value(dict(details or {}))
        super().__init__(safe_message)
        self.code = code
        self.message = safe_message
        self.stage = stage
        self.details = {
            "stage": stage,
            "code": code,
            **safe_details,
        }


@dataclass(frozen=True)
class ChromiumSingletonInspection:
    state: str
    reason: str
    details: Mapping[str, Any]


class _BoundedStderrCapture:
    """Drain a child pipe without allowing diagnostic memory to grow unbounded."""

    def __init__(self, max_bytes: int = DEFAULT_BROWSER_STDERR_TAIL_BYTES) -> None:
        self._max_bytes = max(1, int(max_bytes))
        self._chunks: deque[bytes] = deque()
        self._size = 0
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self, stream: Any) -> None:
        def drain() -> None:
            try:
                while True:
                    chunk = stream.read(4096)
                    if not chunk:
                        break
                    if isinstance(chunk, str):
                        chunk = chunk.encode("utf-8", errors="replace")
                    self._append(bytes(chunk))
            except Exception:
                logger.debug("managed_chrome_stderr_drain_failed", exc_info=True)
            finally:
                with suppress(Exception):
                    stream.close()

        self._thread = threading.Thread(
            target=drain,
            name="paper-fetch-chrome-stderr",
            daemon=True,
        )
        self._thread.start()

    def _append(self, chunk: bytes) -> None:
        if len(chunk) >= self._max_bytes:
            chunk = chunk[-self._max_bytes :]
        with self._lock:
            self._chunks.append(chunk)
            self._size += len(chunk)
            while self._chunks and self._size > self._max_bytes:
                overflow = self._size - self._max_bytes
                first = self._chunks[0]
                if len(first) <= overflow:
                    self._chunks.popleft()
                    self._size -= len(first)
                    continue
                self._chunks[0] = first[overflow:]
                self._size -= overflow

    def finish(self, timeout: float = 2.0) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout=max(0.0, timeout))

    def tail_text(self) -> str:
        with self._lock:
            payload = b"".join(self._chunks)
        return payload.decode("utf-8", errors="replace")


_SENSITIVE_DIAGNOSTIC_VALUE_RE = re.compile(
    r"(?i)\b(authorization|cookie|password|secret|token|api[_-]?key)"
    r"(\s*[:=]\s*)([^\s;,]+)"
)
_SENSITIVE_QUERY_VALUE_RE = re.compile(
    r"(?i)([?&](?:access_token|api[_-]?key|key|password|secret|token)=)[^&\s]+"
)


def _redact_diagnostic_text(text: str, *, max_chars: int | None = None) -> str:
    redacted = _SENSITIVE_DIAGNOSTIC_VALUE_RE.sub(r"\1\2[REDACTED]", text)
    redacted = _SENSITIVE_QUERY_VALUE_RE.sub(r"\1[REDACTED]", redacted)
    if max_chars is not None and max_chars <= 0:
        return ""
    if max_chars is not None and len(redacted) > max_chars:
        if max_chars <= 3:
            return redacted[-max_chars:]
        redacted = "..." + redacted[-(max_chars - 3) :]
    return redacted


def _redact_diagnostic_value(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_diagnostic_text(value)
    if isinstance(value, Mapping):
        return {str(key): _redact_diagnostic_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_diagnostic_value(item) for item in value]
    return value


def _local_hostname_aliases() -> set[str]:
    aliases: set[str] = set()
    for candidate in (socket.gethostname(), socket.getfqdn()):
        normalized = str(candidate or "").strip().lower().rstrip(".")
        if not normalized:
            continue
        aliases.add(normalized)
        aliases.add(normalized.split(".", 1)[0])
    return aliases


def _parse_singleton_lock_target(target: str) -> tuple[str, int] | None:
    host, separator, raw_pid = str(target or "").strip().rpartition("-")
    if not separator or not host or not raw_pid.isdigit():
        return None
    pid = int(raw_pid)
    return (host, pid) if pid > 0 else None


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        return exc.errno == errno.EPERM
    return True


def _process_cmdline(pid: int) -> str | None:
    proc_cmdline = Path(f"/proc/{pid}/cmdline")
    if not proc_cmdline.is_file():
        return None
    try:
        return (
            proc_cmdline.read_bytes()
            .replace(b"\0", b" ")
            .decode("utf-8", errors="replace")
            .strip()
        )
    except OSError:
        return None


def _cmdline_matches_managed_profile(cmdline: str, profile_dir: Path) -> bool:
    normalized = str(cmdline or "").strip()
    if not normalized:
        return False
    lowered = normalized.lower()
    browser_named = any(token in lowered for token in ("chrome", "chromium"))
    profile_tokens = {
        f"--user-data-dir={profile_dir}",
        f"--user-data-dir={profile_dir.resolve(strict=False)}",
    }
    return browser_named and any(token in normalized for token in profile_tokens)


def _unix_socket_responds(path: Path) -> bool | None:
    if not hasattr(socket, "AF_UNIX"):
        return None
    if not path.exists():
        return False
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(0.2)
    try:
        client.connect(str(path))
    except OSError as exc:
        if exc.errno in {
            errno.ENOENT,
            errno.ECONNREFUSED,
            errno.ENOTSOCK,
        }:
            return False
        return None
    finally:
        client.close()
    return True


def inspect_chromium_singletons(profile_dir: Path) -> ChromiumSingletonInspection:
    """Conservatively classify Chromium singleton state for a managed profile."""

    profile_dir = Path(profile_dir).expanduser()
    if os.name != "posix":
        return ChromiumSingletonInspection(
            state="clean",
            reason="singleton_inspection_not_required",
            details={"supported": False},
        )

    paths = {name: profile_dir / name for name in CHROMIUM_SINGLETON_FILENAMES}
    existing = {
        name: path for name, path in paths.items() if path.exists() or path.is_symlink()
    }
    if not existing:
        return ChromiumSingletonInspection(
            state="clean",
            reason="singleton_files_absent",
            details={"supported": True, "files": []},
        )

    current_uid = os.geteuid()
    owners: dict[str, int | None] = {}
    for name, path in existing.items():
        try:
            owners[name] = path.lstat().st_uid
        except OSError:
            owners[name] = None
    if any(owner != current_uid for owner in owners.values()):
        return ChromiumSingletonInspection(
            state="in_use",
            reason="singleton_owner_mismatch",
            details={"files": sorted(existing), "owners": owners},
        )

    lock_path = paths["SingletonLock"]
    if not lock_path.is_symlink():
        return ChromiumSingletonInspection(
            state="in_use",
            reason="singleton_lock_unverifiable",
            details={"files": sorted(existing), "owners": owners},
        )
    try:
        lock_target = os.readlink(lock_path)
    except OSError:
        lock_target = ""
    parsed_lock = _parse_singleton_lock_target(lock_target)
    if parsed_lock is None:
        return ChromiumSingletonInspection(
            state="in_use",
            reason="singleton_lock_target_invalid",
            details={"files": sorted(existing), "lock_target": lock_target},
        )
    lock_host, lock_pid = parsed_lock
    if lock_host.strip().lower().rstrip(".") not in _local_hostname_aliases():
        return ChromiumSingletonInspection(
            state="in_use",
            reason="singleton_lock_remote_host",
            details={
                "files": sorted(existing),
                "lock_host": lock_host,
                "lock_pid": lock_pid,
            },
        )

    process_exists = _process_exists(lock_pid)
    process_cmdline = _process_cmdline(lock_pid) if process_exists else None
    socket_path = paths["SingletonSocket"]
    socket_target = ""
    socket_responds: bool | None = False
    if socket_path.is_symlink():
        try:
            socket_target = os.readlink(socket_path)
        except OSError:
            socket_target = ""
        if socket_target:
            socket_target_path = Path(socket_target)
            if not socket_target_path.is_absolute():
                socket_target_path = socket_path.parent / socket_target_path
            if socket_target_path.exists():
                try:
                    socket_owner = socket_target_path.stat().st_uid
                except OSError:
                    socket_owner = None
                if socket_owner != current_uid:
                    return ChromiumSingletonInspection(
                        state="in_use",
                        reason="singleton_socket_owner_mismatch",
                        details={
                            "files": sorted(existing),
                            "socket_target": socket_target,
                            "socket_owner": socket_owner,
                        },
                    )
            socket_responds = _unix_socket_responds(socket_target_path)
    elif socket_path.exists():
        socket_responds = _unix_socket_responds(socket_path)

    process_profile_match = (
        _cmdline_matches_managed_profile(process_cmdline, profile_dir)
        if process_cmdline is not None
        else None
    )
    details: dict[str, Any] = {
        "files": sorted(existing),
        "owners": owners,
        "lock_target": lock_target,
        "lock_host": lock_host,
        "lock_pid": lock_pid,
        "process_exists": process_exists,
        "process_cmdline": process_cmdline,
        "process_profile_match": process_profile_match,
        "socket_target": socket_target or None,
        "socket_responds": socket_responds,
    }
    if socket_responds is True:
        return ChromiumSingletonInspection(
            state="in_use",
            reason="singleton_socket_active",
            details=details,
        )
    if process_exists and process_profile_match is True:
        return ChromiumSingletonInspection(
            state="in_use",
            reason="singleton_pid_active_for_profile",
            details=details,
        )
    if process_exists and process_profile_match is None:
        return ChromiumSingletonInspection(
            state="in_use",
            reason="singleton_pid_unverifiable",
            details=details,
        )
    if process_exists:
        return ChromiumSingletonInspection(
            state="in_use",
            reason="singleton_pid_exists_for_other_process",
            details=details,
        )
    if socket_responds is None:
        return ChromiumSingletonInspection(
            state="in_use",
            reason="singleton_socket_unverifiable",
            details=details,
        )
    return ChromiumSingletonInspection(
        state="stale",
        reason="singleton_pid_missing_and_socket_inactive",
        details=details,
    )


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part_path = path.with_suffix(path.suffix + ".part")
    try:
        part_path.write_text(
            json.dumps(dict(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        part_path.replace(path)
    except Exception:
        with suppress(OSError):
            part_path.unlink(missing_ok=True)
        raise


def _chromium_singleton_snapshot(
    profile_dir: Path,
) -> dict[str, tuple[Any, ...] | None]:
    snapshot: dict[str, tuple[Any, ...] | None] = {}
    for name in CHROMIUM_SINGLETON_FILENAMES:
        path = profile_dir / name
        try:
            stat_result = path.lstat()
        except OSError:
            snapshot[name] = None
            continue
        link_target: str | None = None
        if path.is_symlink():
            try:
                link_target = os.readlink(path)
            except OSError:
                link_target = None
        snapshot[name] = (
            stat_result.st_dev,
            stat_result.st_ino,
            stat_result.st_mode,
            stat_result.st_uid,
            link_target,
        )
    return snapshot


def recover_stale_chromium_singletons(
    profile_dir: Path,
    inspection: ChromiumSingletonInspection,
) -> Path:
    if inspection.state != "stale":
        raise ValueError("only confirmed stale Chromium singletons may be recovered")
    profile_dir = Path(profile_dir).expanduser()
    confirmed = inspect_chromium_singletons(profile_dir)
    if confirmed.state != "stale":
        raise RuntimeError(
            "Chromium singleton state changed before stale recovery; no files were moved"
        )
    expected_snapshot = _chromium_singleton_snapshot(profile_dir)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    diagnostic_dir = (
        profile_dir
        / BROWSER_DIAGNOSTIC_DIRNAME
        / f"singleton-recovery-{timestamp}-{os.getpid()}"
    )
    diagnostic_dir.mkdir(parents=True, exist_ok=False)
    moved: list[str] = []
    move_order = ("SingletonCookie", "SingletonSocket", "SingletonLock")
    try:
        for name in move_order:
            if inspect_chromium_singletons(profile_dir).state != "stale":
                raise RuntimeError(
                    "Chromium singleton state changed during stale recovery"
                )
            expected_current = {
                key: None if key in moved else value
                for key, value in expected_snapshot.items()
            }
            if _chromium_singleton_snapshot(profile_dir) != expected_current:
                raise RuntimeError(
                    "Chromium singleton state changed during stale recovery"
                )
            if expected_snapshot[name] is None:
                continue
            (profile_dir / name).replace(diagnostic_dir / name)
            moved.append(name)
        _atomic_write_json(
            diagnostic_dir / "recovery.json",
            {
                "status": "recovered",
                "reason": confirmed.reason,
                "moved": moved,
                "inspection": _redact_diagnostic_value(dict(confirmed.details)),
            },
        )
    except Exception:
        for name in reversed(moved):
            source = profile_dir / name
            archived = diagnostic_dir / name
            if source.exists() or source.is_symlink():
                continue
            with suppress(OSError):
                archived.replace(source)
        with suppress(OSError):
            (diagnostic_dir / "recovery.json.part").unlink(missing_ok=True)
        with suppress(OSError):
            diagnostic_dir.rmdir()
        raise
    logger.warning(
        "managed_chrome_stale_singletons_recovered profile=%s diagnostic_dir=%s files=%s",
        profile_dir,
        diagnostic_dir,
        ",".join(moved),
    )
    return diagnostic_dir


def browser_context_options(
    *,
    user_agent: str | None = None,
    locale: str = DEFAULT_BROWSER_LOCALE,
    viewport: dict[str, int] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    options: dict[str, Any] = {
        "locale": locale,
        "viewport": dict(DEFAULT_BROWSER_VIEWPORT if viewport is None else viewport),
        "service_workers": "block",
    }
    active_user_agent = str(user_agent or "").strip()
    if active_user_agent:
        options["user_agent"] = active_user_agent
    options.update(extra)
    return options


def browser_page_user_agent(page: Any) -> str | None:
    try:
        user_agent = page.evaluate("() => navigator.userAgent")
    except Exception:
        return None
    normalized = str(user_agent or "").strip()
    return normalized or None


def connect_browser_over_cdp(endpoint: str) -> Any:
    """Connect to an already-running Chromium browser over CDP."""

    from playwright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.connect_over_cdp(endpoint)
    except Exception:
        playwright.stop()
        raise

    original_close = browser.close

    def _close_with_cleanup() -> None:
        try:
            original_close()
        finally:
            playwright.stop()

    browser.close = _close_with_cleanup
    return browser


def _unused_tcp_port() -> int:
    # The socket is closed before Chrome binds the port, so startup can still
    # fail if another process claims it first. The CDP readiness check reports
    # that race as a normal managed-browser startup failure.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _resolve_browser_binary(binary_path: str | None = None) -> str:
    active_binary = str(binary_path or "").strip()
    if active_binary:
        path = Path(active_binary).expanduser()
        if not path.is_file():
            raise RuntimeError(
                f"Configured browser binary does not point to a file: {path}"
            )
        return str(path)

    try:
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        try:
            path = Path(playwright.chromium.executable_path)
        finally:
            playwright.stop()
    except Exception as exc:
        raise RuntimeError(
            f"Playwright Chromium binary could not be resolved: {exc}"
        ) from exc
    if not path.is_file():
        raise RuntimeError(
            "Playwright Chromium is not installed; install the browser extra and run "
            "`playwright install chromium`, or configure a browser binary explicitly."
        )
    return str(path)


def _build_managed_chrome_args(
    *,
    headless: bool,
    profile_dir: Path,
    port: int,
) -> list[str]:
    args = [
        f"--user-data-dir={profile_dir}",
        "--remote-debugging-address=127.0.0.1",
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    args.append(f"--lang={DEFAULT_BROWSER_LOCALE}")
    if headless:
        args.append("--headless=new")
    return args


def _wait_for_cdp_endpoint(
    *,
    process: subprocess.Popen[Any],
    port: int,
    timeout_seconds: float = DEFAULT_CDP_STARTUP_TIMEOUT_SECONDS,
) -> str:
    deadline = time.monotonic() + timeout_seconds
    url = f"http://127.0.0.1:{port}/json/version"
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ManagedBrowserError(
                MANAGED_CHROME_EXITED_BEFORE_CDP,
                f"Managed Chrome exited before the CDP endpoint was ready (exit {process.returncode}).",
                stage="managed_chrome_startup",
                details={"exit_code": process.returncode, "port": port},
            )
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
            endpoint = str(payload.get("webSocketDebuggerUrl") or "").strip()
            if endpoint:
                return endpoint
        except Exception as exc:
            last_error = exc
        if time.monotonic() < deadline:
            time.sleep(0.25)

    message = f"Managed Chrome did not expose a CDP endpoint on 127.0.0.1:{port}"
    if last_error is not None:
        message = f"{message}: {last_error}"
    raise ManagedBrowserError(
        MANAGED_CHROME_CDP_TIMEOUT,
        message,
        stage="managed_chrome_startup",
        details={"exit_code": process.poll(), "port": port},
    )


def _terminate_process(process: subprocess.Popen[Any] | None) -> None:
    if process is None or process.poll() is not None:
        return
    with suppress(Exception):
        process.terminate()
    try:
        process.wait(timeout=5)
    except Exception:
        with suppress(Exception):
            process.kill()
        with suppress(Exception):
            process.wait(timeout=5)


def _profile_lock_for_dir(profile_dir: Path) -> FileLock:
    return FileLock(str(profile_dir / PROFILE_LOCK_FILENAME))


def _browser_diagnostic_dir(profile_dir: Path, *, label: str) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    path = (
        profile_dir / BROWSER_DIAGNOSTIC_DIRNAME / f"{label}-{timestamp}-{os.getpid()}"
    )
    path.mkdir(parents=True, exist_ok=False)
    return path


def _write_browser_failure_diagnostic(
    profile_dir: Path,
    *,
    error: ManagedBrowserError,
    stderr_tail: str,
) -> tuple[Path | None, str | None]:
    redacted_tail = _redact_diagnostic_text(stderr_tail)
    summary = (
        _redact_diagnostic_text(
            redacted_tail,
            max_chars=DEFAULT_BROWSER_ERROR_SUMMARY_CHARS,
        )
        or None
    )
    try:
        diagnostic_dir = _browser_diagnostic_dir(
            profile_dir, label=error.code.replace("_", "-")
        )
        if redacted_tail:
            stderr_path = diagnostic_dir / "chrome-stderr.log"
            stderr_path.write_text(redacted_tail, encoding="utf-8")
        _atomic_write_json(
            diagnostic_dir / "diagnostic.json",
            {
                "code": error.code,
                "stage": error.stage,
                "message": _redact_diagnostic_text(error.message),
                "details": _redact_diagnostic_value(dict(error.details)),
                "stderr_summary": summary,
            },
        )
        return diagnostic_dir, summary
    except Exception:
        logger.warning(
            "managed_chrome_diagnostic_write_failed profile=%s code=%s",
            profile_dir,
            error.code,
            exc_info=True,
        )
        return None, summary


def _storage_state_payload(storage_state: Any) -> Mapping[str, Any] | None:
    if isinstance(storage_state, Mapping):
        return storage_state
    storage_state_path = str(storage_state or "").strip()
    if not storage_state_path:
        return None
    try:
        payload = json.loads(
            Path(storage_state_path).expanduser().read_text(encoding="utf-8")
        )
    except Exception:
        return None
    return payload if isinstance(payload, Mapping) else None


def _storage_state_cookies(storage_state: Any) -> list[dict[str, Any]]:
    payload = _storage_state_payload(storage_state)
    if payload is None:
        return []
    raw_cookies = payload.get("cookies")
    if not isinstance(raw_cookies, list):
        return []
    return [dict(cookie) for cookie in raw_cookies if isinstance(cookie, Mapping)]


def _apply_storage_state_cookies(context: Any, storage_state: Any) -> int:
    cookies = _storage_state_cookies(storage_state)
    if not cookies:
        return 0
    context.add_cookies(cookies)
    return len(cookies)


class _BorrowedBrowserContext:
    """Wrap an externally-owned browser context without closing it."""

    def __init__(self, context: Any, browser: Any | None = None) -> None:
        self._context = context
        self._browser = browser
        self._paper_fetch_borrowed_context = True
        self._paper_fetch_external_cdp_diagnostics: dict[str, Any] = {}
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        _safe_close(self._browser)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._context, name)


class _OwnedBrowserContext:
    """Close a thread-owned CDP connection when the context is closed."""

    def __init__(self, context: Any, browser: Any) -> None:
        self._context = context
        self._browser = browser
        self._paper_fetch_external_cdp_diagnostics: dict[str, Any] = {}
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            _safe_close(self._context)
        finally:
            _safe_close(self._browser)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._context, name)


def is_borrowed_browser_context(context: Any) -> bool:
    return bool(getattr(context, "_paper_fetch_borrowed_context", False))


def _safe_close(value: Any) -> None:
    if value is None:
        return
    with suppress(Exception):
        value.close()


@dataclass
class BrowserContextManager:
    """Owns a shared CDP browser connection for one fetch runtime."""

    binary_path: str | None = None
    cdp_endpoint: str | None = None
    external_new_context: bool = False
    profile_dir: Path | None = None
    user_data_dir: Path | None = None
    profile_lock_timeout_seconds: float = DEFAULT_PROFILE_LOCK_TIMEOUT_SECONDS
    _lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False
    )
    _browser: Any | None = field(default=None, init=False, repr=False)
    _headless: bool | None = field(default=None, init=False, repr=False)
    _managed_process: subprocess.Popen[Any] | None = field(
        default=None, init=False, repr=False
    )
    _managed_cdp_endpoint: str | None = field(default=None, init=False, repr=False)
    _using_external_endpoint: bool = field(default=False, init=False, repr=False)
    _profile_lock: FileLock | None = field(default=None, init=False, repr=False)
    _managed_stderr_capture: _BoundedStderrCapture | None = field(
        default=None, init=False, repr=False
    )
    _singleton_recovery_paths: list[Path] = field(
        default_factory=list, init=False, repr=False
    )

    def _managed_profile_dir(self) -> Path:
        profile_dir = self.profile_dir or self.user_data_dir
        if profile_dir is not None:
            return Path(profile_dir).expanduser()
        return resolve_user_data_dir() / "chromium-cdp-profile"

    def _ensure_managed_cdp_endpoint(self, *, headless: bool) -> str:
        if (
            self._managed_cdp_endpoint
            and self._managed_process is not None
            and self._managed_process.poll() is None
        ):
            return self._managed_cdp_endpoint

        self._managed_cdp_endpoint = None
        self._stop_managed_process()
        self._release_profile_lock()

        binary_path = _resolve_browser_binary(self.binary_path)
        profile_dir = self._managed_profile_dir()
        profile_dir.mkdir(parents=True, exist_ok=True)
        self._acquire_profile_lock(profile_dir)
        self._singleton_recovery_paths = []
        try:
            recovered_before_launch = self._prepare_managed_profile(profile_dir)
        except Exception:
            self._release_profile_lock()
            raise

        launch_attempt = 0
        while True:
            try:
                endpoint = self._launch_managed_chrome(
                    binary_path=binary_path,
                    profile_dir=profile_dir,
                    headless=headless,
                )
                self._managed_cdp_endpoint = endpoint
                return endpoint
            except Exception as exc:
                error = (
                    exc
                    if isinstance(exc, ManagedBrowserError)
                    else ManagedBrowserError(
                        MANAGED_CHROME_EXITED_BEFORE_CDP,
                        str(exc) or exc.__class__.__name__,
                        stage="managed_chrome_startup",
                    )
                )
                error = self._finalize_managed_failure(
                    profile_dir=profile_dir,
                    error=error,
                )
                if launch_attempt == 0 and not recovered_before_launch:
                    inspection = inspect_chromium_singletons(profile_dir)
                    if inspection.state == "stale":
                        recovery_path = recover_stale_chromium_singletons(
                            profile_dir, inspection
                        )
                        self._singleton_recovery_paths.append(recovery_path)
                        launch_attempt += 1
                        continue
                self._managed_cdp_endpoint = None
                self._release_profile_lock()
                raise error from exc

    def _prepare_managed_profile(self, profile_dir: Path) -> bool:
        inspection = inspect_chromium_singletons(profile_dir)
        if inspection.state == "clean":
            return False
        if inspection.state == "stale":
            recovery_path = recover_stale_chromium_singletons(profile_dir, inspection)
            self._singleton_recovery_paths.append(recovery_path)
            return True
        raise ManagedBrowserError(
            MANAGED_CHROME_PROFILE_IN_USE,
            (
                "Managed Chrome profile is active or could not be proven stale: "
                f"{inspection.reason}."
            ),
            stage="managed_chrome_profile",
            details={
                "profile_dir": str(profile_dir),
                "singleton_state": inspection.state,
                "singleton_reason": inspection.reason,
                "singleton": dict(inspection.details),
            },
        )

    def _launch_managed_chrome(
        self,
        *,
        binary_path: str,
        profile_dir: Path,
        headless: bool,
    ) -> str:
        port = _unused_tcp_port()
        args = _build_managed_chrome_args(
            headless=headless,
            profile_dir=profile_dir,
            port=port,
        )
        command = [binary_path, *args, "about:blank"]
        creationflags = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        )
        capture = _BoundedStderrCapture()
        try:
            self._managed_process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
            )
            stderr_stream = getattr(self._managed_process, "stderr", None)
            if stderr_stream is not None:
                capture.start(stderr_stream)
            self._managed_stderr_capture = capture
            return _wait_for_cdp_endpoint(
                process=self._managed_process,
                port=port,
            )
        except ManagedBrowserError:
            raise
        except Exception as exc:
            raise ManagedBrowserError(
                MANAGED_CHROME_EXITED_BEFORE_CDP,
                f"Managed Chrome could not be started: {exc}",
                stage="managed_chrome_startup",
                details={"exit_code": None, "port": port},
            ) from exc

    def _stop_managed_process(self) -> str:
        process = self._managed_process
        capture = self._managed_stderr_capture
        self._managed_process = None
        self._managed_stderr_capture = None
        _terminate_process(process)
        if capture is None:
            return ""
        capture.finish()
        return capture.tail_text()

    def _finalize_managed_failure(
        self,
        *,
        profile_dir: Path,
        error: ManagedBrowserError,
    ) -> ManagedBrowserError:
        exit_code = (
            self._managed_process.poll()
            if self._managed_process is not None
            else error.details.get("exit_code")
        )
        stderr_tail = self._stop_managed_process()
        diagnostic_path, stderr_summary = _write_browser_failure_diagnostic(
            profile_dir,
            error=error,
            stderr_tail=stderr_tail,
        )
        details = {
            **dict(error.details),
            "exit_code": exit_code,
            "profile_dir": str(profile_dir),
            "diagnostic_path": str(diagnostic_path) if diagnostic_path else None,
            "stderr_summary": stderr_summary,
            "singleton_recovery_paths": [
                str(path) for path in self._singleton_recovery_paths
            ],
        }
        return ManagedBrowserError(
            error.code,
            error.message,
            stage=error.stage,
            details=details,
        )

    def _managed_connection_failure(
        self,
        *,
        code: str,
        stage: str,
        exc: Exception,
    ) -> ManagedBrowserError:
        message = str(exc).strip() or exc.__class__.__name__
        error = ManagedBrowserError(code, message, stage=stage)
        if self._managed_process is None:
            return error
        finalized = self._finalize_managed_failure(
            profile_dir=self._managed_profile_dir(),
            error=error,
        )
        self._managed_cdp_endpoint = None
        self._release_profile_lock()
        return finalized

    def _acquire_profile_lock(self, profile_dir: Path) -> None:
        if self._profile_lock is not None:
            return
        lock = _profile_lock_for_dir(profile_dir)
        try:
            lock.acquire(timeout=self.profile_lock_timeout_seconds)
        except Timeout as exc:
            raise ManagedBrowserError(
                MANAGED_CHROME_PROFILE_IN_USE,
                (
                    "Timed out waiting for managed Chrome profile lock: "
                    f"{profile_dir / PROFILE_LOCK_FILENAME}"
                ),
                stage="managed_chrome_profile",
                details={"profile_dir": str(profile_dir)},
            ) from exc
        self._profile_lock = lock

    def _release_profile_lock(self) -> None:
        lock = self._profile_lock
        self._profile_lock = None
        if lock is not None:
            with suppress(Exception):
                lock.release()

    def browser(self, *, headless: bool = True) -> Any:
        active_headless = bool(headless)
        with self._lock:
            endpoint = str(self.cdp_endpoint or "").strip()
            using_external_endpoint = bool(endpoint)
            if self._browser is not None:
                if using_external_endpoint:
                    self._using_external_endpoint = True
                    self._headless = active_headless
                    return self._browser
                if (
                    self._headless == active_headless
                    and self._managed_process is not None
                    and self._managed_process.poll() is None
                ):
                    self._using_external_endpoint = False
                    return self._browser
                self.close()

            if not endpoint:
                endpoint = self._ensure_managed_cdp_endpoint(headless=active_headless)
                using_external_endpoint = False
            self._using_external_endpoint = using_external_endpoint
            try:
                self._browser = connect_browser_over_cdp(endpoint)
            except Exception as exc:
                raise self._managed_connection_failure(
                    code=CDP_CONNECT_FAILED,
                    stage="cdp_connect",
                    exc=exc,
                ) from exc
            self._headless = active_headless
            return self._browser

    def new_context(self, *, headless: bool = True, **context_kwargs: Any) -> Any:
        with self._lock:
            endpoint = str(self.cdp_endpoint or "").strip()
            using_external_endpoint = bool(endpoint)
            active_headless = bool(headless)
            if not endpoint:
                if (
                    self._managed_process is not None
                    and self._managed_process.poll() is None
                    and self._headless != active_headless
                ):
                    self.close()
                endpoint = self._ensure_managed_cdp_endpoint(headless=active_headless)
                self._headless = active_headless

            try:
                browser = connect_browser_over_cdp(endpoint)
            except Exception as exc:
                raise self._managed_connection_failure(
                    code=CDP_CONNECT_FAILED,
                    stage="cdp_connect",
                    exc=exc,
                ) from exc
            if using_external_endpoint:
                contexts = list(getattr(browser, "contexts", []) or [])
                requires_isolated_context = (
                    context_kwargs.get("service_workers") == "block"
                )
                if (
                    contexts
                    and not self.external_new_context
                    and not requires_isolated_context
                ):
                    context = contexts[0]
                    storage_state = context_kwargs.get("storage_state")
                    cookie_count = 0
                    if storage_state is not None:
                        try:
                            cookie_count = _apply_storage_state_cookies(
                                context, storage_state
                            )
                            if cookie_count:
                                logger.debug(
                                    "cdp_external_context_applied_storage_state_cookies count=%s",
                                    cookie_count,
                                )
                        except Exception:
                            logger.debug(
                                "cdp_external_context_storage_state_cookie_injection_failed",
                                exc_info=True,
                            )
                    ignored_keys = sorted(
                        key for key in context_kwargs if key != "storage_state"
                    )
                    if ignored_keys:
                        logger.debug(
                            "cdp_external_context_ignored_options keys=%s",
                            ",".join(ignored_keys),
                        )
                    borrowed = _BorrowedBrowserContext(context, browser)
                    borrowed._paper_fetch_external_cdp_diagnostics = {
                        "external_cdp": True,
                        "borrowed_existing_context": True,
                        "ignored_context_options": ignored_keys,
                        "storage_state_cookie_count": cookie_count,
                    }
                    return borrowed
            try:
                context = browser.new_context(**context_kwargs)
            except Exception as exc:
                _safe_close(browser)
                raise ManagedBrowserError(
                    BROWSER_CONTEXT_CREATE_FAILED,
                    str(exc).strip() or exc.__class__.__name__,
                    stage="browser_context_create",
                    details={"external_cdp": using_external_endpoint},
                ) from exc
            owned = _OwnedBrowserContext(context, browser)
            if using_external_endpoint:
                owned._paper_fetch_external_cdp_diagnostics = {
                    "external_cdp": True,
                    "borrowed_existing_context": False,
                    "ignored_context_options": [],
                    "storage_state_cookie_count": None,
                }
            return owned

    def close(self) -> None:
        with self._lock:
            browser = self._browser
            managed_process = self._managed_process
            self._browser = None
            self._headless = None
            self._managed_process = None
            self._managed_cdp_endpoint = None
            if browser is not None:
                with suppress(Exception):
                    browser.close()
            self._managed_process = managed_process
            self._stop_managed_process()
            if managed_process is not None:
                profile_dir = self._managed_profile_dir()
                inspection = inspect_chromium_singletons(profile_dir)
                if inspection.state == "stale":
                    with suppress(Exception):
                        recover_stale_chromium_singletons(profile_dir, inspection)
            self._release_profile_lock()

    def __del__(
        self,
    ) -> None:  # pragma: no cover - defensive cleanup at GC/interpreter shutdown
        with suppress(Exception):
            self.close()


__all__ = [
    "BrowserContextManager",
    "ChromiumSingletonInspection",
    "ManagedBrowserError",
    "browser_context_options",
    "browser_page_user_agent",
    "connect_browser_over_cdp",
    "inspect_chromium_singletons",
    "is_borrowed_browser_context",
    "recover_stale_chromium_singletons",
]
