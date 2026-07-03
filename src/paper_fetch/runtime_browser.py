"""Browser lifecycle manager."""

from __future__ import annotations

from contextlib import suppress
import json
import logging
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from collections.abc import Mapping
from typing import Any

from filelock import FileLock, Timeout

from ._cloakbrowser_runtime import import_cloakbrowser
from .config import resolve_user_data_dir

DEFAULT_BROWSER_LOCALE = "en-US"
DEFAULT_BROWSER_VIEWPORT = {"width": 1440, "height": 1600}
DEFAULT_CDP_STARTUP_TIMEOUT_SECONDS = 30.0
DEFAULT_PROFILE_LOCK_TIMEOUT_SECONDS = 30.0
PROFILE_LOCK_FILENAME = ".paper-fetch-profile.lock"
logger = logging.getLogger("paper_fetch.runtime_browser")


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


def _resolve_cloakbrowser_binary(binary_path: str | None = None) -> str:
    active_binary = str(binary_path or "").strip()
    if active_binary:
        path = Path(active_binary).expanduser()
        if not path.is_file():
            raise RuntimeError(
                f"CLOAKBROWSER_BINARY_PATH is set but does not point to a file: {path}"
            )
        return str(path)

    try:
        cloakbrowser = import_cloakbrowser()
    except Exception as exc:
        raise RuntimeError(
            f"CloakBrowser Python package is not importable: {exc}"
        ) from exc

    try:
        return str(cloakbrowser.ensure_binary())
    except Exception as exc:
        raise RuntimeError(
            f"CloakBrowser Chrome binary is not available: {exc}"
        ) from exc


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
    try:
        import cloakbrowser

        built_args = list(
            cloakbrowser.build_args(
                True,
                args,
                locale=DEFAULT_BROWSER_LOCALE,
                headless=headless,
            )
        )
        has_headless_flag = any(
            arg == "--headless" or arg.startswith("--headless=") for arg in built_args
        )
        if headless and not has_headless_flag:
            built_args.append("--headless=new")
        return built_args
    except Exception:
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
            raise RuntimeError(
                f"Managed Chrome exited before CDP endpoint was ready: {process.returncode}"
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
    raise RuntimeError(message)


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

    def _managed_profile_dir(self) -> Path:
        profile_dir = self.profile_dir or self.user_data_dir
        if profile_dir is not None:
            return Path(profile_dir).expanduser()
        return resolve_user_data_dir() / "cloakbrowser-cdp-profile"

    def _ensure_managed_cdp_endpoint(self, *, headless: bool) -> str:
        if (
            self._managed_cdp_endpoint
            and self._managed_process is not None
            and self._managed_process.poll() is None
        ):
            return self._managed_cdp_endpoint

        self._managed_cdp_endpoint = None
        _terminate_process(self._managed_process)
        self._managed_process = None
        self._release_profile_lock()

        binary_path = _resolve_cloakbrowser_binary(self.binary_path)
        profile_dir = self._managed_profile_dir()
        profile_dir.mkdir(parents=True, exist_ok=True)
        self._acquire_profile_lock(profile_dir)
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
        try:
            self._managed_process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            self._managed_cdp_endpoint = _wait_for_cdp_endpoint(
                process=self._managed_process,
                port=port,
            )
            return self._managed_cdp_endpoint
        except Exception:
            _terminate_process(self._managed_process)
            self._managed_process = None
            self._managed_cdp_endpoint = None
            self._release_profile_lock()
            raise

    def _acquire_profile_lock(self, profile_dir: Path) -> None:
        if self._profile_lock is not None:
            return
        lock = _profile_lock_for_dir(profile_dir)
        try:
            lock.acquire(timeout=self.profile_lock_timeout_seconds)
        except Timeout as exc:
            raise RuntimeError(
                "Timed out waiting for managed Chrome profile lock: "
                f"{profile_dir / PROFILE_LOCK_FILENAME}"
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
            except Exception:
                if not using_external_endpoint:
                    _terminate_process(self._managed_process)
                    self._managed_process = None
                    self._managed_cdp_endpoint = None
                    self._release_profile_lock()
                raise
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
            except Exception:
                if not using_external_endpoint:
                    _terminate_process(self._managed_process)
                    self._managed_process = None
                    self._managed_cdp_endpoint = None
                    self._release_profile_lock()
                raise
            if using_external_endpoint:
                contexts = list(getattr(browser, "contexts", []) or [])
                if contexts and not self.external_new_context:
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
            except Exception:
                _safe_close(browser)
                raise
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
            _terminate_process(managed_process)
            self._release_profile_lock()

    def __del__(
        self,
    ) -> None:  # pragma: no cover - defensive cleanup at GC/interpreter shutdown
        with suppress(Exception):
            self.close()


__all__ = [
    "BrowserContextManager",
    "browser_context_options",
    "browser_page_user_agent",
    "connect_browser_over_cdp",
    "is_borrowed_browser_context",
]
