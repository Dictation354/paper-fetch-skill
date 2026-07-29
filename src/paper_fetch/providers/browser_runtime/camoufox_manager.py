"""Thread-affine lifecycle manager for native Camoufox browsers."""

from __future__ import annotations

import importlib
import threading
from typing import Any


def _launch_executable_path(binary_path: str | None) -> str:
    if binary_path:
        return binary_path
    pkgman = importlib.import_module("camoufox.pkgman")
    runtime_path = pkgman.camoufox_path(download_if_missing=False)
    return str(pkgman.launch_path(runtime_path))


class CamoufoxBrowserManager:
    """Reuse one native Firefox/Juggler process and create isolated contexts."""

    def __init__(
        self,
        *,
        binary_path: str | None = None,
        headless: bool = True,
    ) -> None:
        self.binary_path = str(binary_path or "").strip() or None
        self.headless = bool(headless)
        self._owner_thread_id: int | None = None
        self._playwright: Any | None = None
        self._browser: Any | None = None

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
        sync_api = importlib.import_module("camoufox.sync_api")
        playwright_api = importlib.import_module("playwright.sync_api")
        self._playwright = playwright_api.sync_playwright().start()
        try:
            launch_kwargs: dict[str, Any] = {
                "headless": self.headless,
                "executable_path": _launch_executable_path(self.binary_path),
            }
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
        return sync_api.NewContext(self.browser(), **context_kwargs)

    def close(self) -> None:
        if self._browser is None and self._playwright is None:
            return
        self._assert_owner_thread()
        browser, playwright = self._browser, self._playwright
        self._browser = None
        self._playwright = None
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
    ) -> None:
        self.user_data_dir = user_data_dir
        self.binary_path = str(binary_path or "").strip() or None
        self.headless = bool(headless)
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
        sync_api = importlib.import_module("camoufox.sync_api")
        playwright_api = importlib.import_module("playwright.sync_api")
        self._playwright = playwright_api.sync_playwright().start()
        try:
            launch_kwargs: dict[str, Any] = {
                "headless": self.headless,
                "user_data_dir": self.user_data_dir,
                "executable_path": _launch_executable_path(self.binary_path),
            }
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
