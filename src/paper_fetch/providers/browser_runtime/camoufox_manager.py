"""Thread-affine lifecycle manager for native Camoufox browsers."""

from __future__ import annotations

from contextlib import redirect_stdout
from pathlib import Path
import importlib
import sys
import threading
from typing import Any
from collections.abc import Callable


def _launch_executable_path(binary_path: str | None) -> str | None:
    if binary_path:
        return binary_path
    pkgman = importlib.import_module("camoufox.pkgman")
    # Keep the no-download guard, but let Camoufox resolve its managed bundle.
    # On macOS, passing Contents/MacOS/camoufox as a custom executable makes
    # Camoufox look beside it for metadata stored under Contents/Resources.
    pkgman.camoufox_path(download_if_missing=False)
    return None


def _launch_firefox_major_version(executable_path: str) -> int | None:
    """Read Camoufox's own version metadata beside a prepared executable."""

    pkgman = importlib.import_module("camoufox.pkgman")
    executable = Path(executable_path).resolve()
    for candidate in (executable.parent, executable.parent.parent):
        try:
            version = pkgman.Version.from_path(candidate)
            major = int(str(version.version or "").split(".", 1)[0])
        except (AttributeError, LookupError, OSError, TypeError, ValueError):
            continue
        if major > 0:
            return major
    return None


def _prepare_managed_runtime_if_enabled(
    *,
    binary_path: str | None,
    auto_prepare: bool,
    cancel_check: Callable[[], bool] | None,
) -> None:
    if binary_path is not None or not auto_prepare:
        return
    from .preparation import (
        browser_runtime_preparation_scope,
        ensure_camoufox_managed_runtime,
    )

    if cancel_check is None:
        ensure_camoufox_managed_runtime()
        return
    with browser_runtime_preparation_scope(cancel_check=cancel_check):
        ensure_camoufox_managed_runtime()


class CamoufoxBrowserManager:
    """Reuse one native Firefox/Juggler process and create isolated contexts."""

    def __init__(
        self,
        *,
        binary_path: str | None = None,
        headless: bool = True,
        auto_prepare: bool = False,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        self.binary_path = str(binary_path or "").strip() or None
        self.headless = bool(headless)
        self.auto_prepare = bool(auto_prepare)
        self.cancel_check = cancel_check
        self._owner_thread_id: int | None = None
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._firefox_major_version: int | None = None

    def _assert_owner_thread(self) -> None:
        thread_id = threading.get_ident()
        if self._owner_thread_id is None:
            self._owner_thread_id = thread_id
            return
        if self._owner_thread_id != thread_id:
            raise RuntimeError(
                "Camoufox sync runtime must be used and closed on its owning thread."
            )

    def browser(self) -> Any:
        self._assert_owner_thread()
        if self._browser is not None:
            return self._browser
        _prepare_managed_runtime_if_enabled(
            binary_path=self.binary_path,
            auto_prepare=self.auto_prepare,
            cancel_check=self.cancel_check,
        )
        sync_api = importlib.import_module("camoufox.sync_api")
        playwright_api = importlib.import_module("playwright.sync_api")
        self._playwright = playwright_api.sync_playwright().start()
        try:
            executable_path = _launch_executable_path(self.binary_path)
            self._firefox_major_version = (
                _launch_firefox_major_version(executable_path)
                if executable_path is not None
                else None
            )
            launch_kwargs: dict[str, Any] = {
                "headless": self.headless,
            }
            if executable_path is not None:
                launch_kwargs["executable_path"] = executable_path
            if self._firefox_major_version is not None:
                launch_kwargs["ff_version"] = self._firefox_major_version
                launch_kwargs["i_know_what_im_doing"] = True
            # MCP reserves stdout exclusively for JSON-RPC. Camoufox may emit
            # first-run addon extraction progress while building launch options,
            # so route third-party startup output to stderr at this boundary.
            with redirect_stdout(sys.stderr):
                self._browser = sync_api.NewBrowser(
                    self._playwright,
                    persistent_context=False,
                    **launch_kwargs,
                )
        except Exception:
            self._playwright.stop()
            self._playwright = None
            raise
        return self._browser

    def new_context(self, **context_kwargs: Any) -> Any:
        self._assert_owner_thread()
        sync_api = importlib.import_module("camoufox.sync_api")
        browser = self.browser()
        if self._firefox_major_version is not None:
            context_kwargs.setdefault("ff_version", str(self._firefox_major_version))
        return sync_api.NewContext(browser, **context_kwargs)

    def close(self) -> None:
        if self._browser is None and self._playwright is None:
            return
        self._assert_owner_thread()
        browser, playwright = self._browser, self._playwright
        self._browser = None
        self._playwright = None
        self._firefox_major_version = None
        try:
            if browser is not None:
                browser.close()
        finally:
            if playwright is not None:
                playwright.stop()


class CamoufoxPersistentContextManager:
    """Own one headed persistent Camoufox context for interactive auth."""

    def __init__(
        self,
        *,
        user_data_dir: str,
        binary_path: str | None = None,
        headless: bool = False,
        auto_prepare: bool = False,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        self.user_data_dir = user_data_dir
        self.binary_path = str(binary_path or "").strip() or None
        self.headless = bool(headless)
        self.auto_prepare = bool(auto_prepare)
        self.cancel_check = cancel_check
        self._owner_thread_id: int | None = None
        self._playwright: Any | None = None
        self._context: Any | None = None

    def new_context(self) -> Any:
        thread_id = threading.get_ident()
        if self._owner_thread_id not in {None, thread_id}:
            raise RuntimeError(
                "Camoufox sync runtime must be used on its owning thread."
            )
        self._owner_thread_id = thread_id
        if self._context is not None:
            return self._context
        _prepare_managed_runtime_if_enabled(
            binary_path=self.binary_path,
            auto_prepare=self.auto_prepare,
            cancel_check=self.cancel_check,
        )
        sync_api = importlib.import_module("camoufox.sync_api")
        playwright_api = importlib.import_module("playwright.sync_api")
        self._playwright = playwright_api.sync_playwright().start()
        try:
            executable_path = _launch_executable_path(self.binary_path)
            firefox_major_version = (
                _launch_firefox_major_version(executable_path)
                if executable_path is not None
                else None
            )
            launch_kwargs: dict[str, Any] = {
                "headless": self.headless,
                "user_data_dir": self.user_data_dir,
            }
            if executable_path is not None:
                launch_kwargs["executable_path"] = executable_path
            if firefox_major_version is not None:
                launch_kwargs["ff_version"] = firefox_major_version
                launch_kwargs["i_know_what_im_doing"] = True
            with redirect_stdout(sys.stderr):
                self._context = sync_api.NewBrowser(
                    self._playwright,
                    persistent_context=True,
                    **launch_kwargs,
                )
        except Exception:
            self._playwright.stop()
            self._playwright = None
            raise
        return self._context

    def close(self) -> None:
        if self._context is None and self._playwright is None:
            return
        thread_id = threading.get_ident()
        if self._owner_thread_id not in {None, thread_id}:
            raise RuntimeError(
                "Camoufox sync runtime must be closed on its owning thread."
            )
        context, playwright = self._context, self._playwright
        self._context = None
        self._playwright = None
        try:
            if context is not None:
                context.close()
        finally:
            if playwright is not None:
                playwright.stop()
