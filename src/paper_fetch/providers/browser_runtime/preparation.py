"""Inspect and prepare the Chromium revision pinned by Patchright."""

from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Mapping
from concurrent.futures import Future
from contextvars import ContextVar
from importlib import metadata
from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout

from ...browser_runtime_policy import BROWSER_PACKAGE_PINS as BROWSER_PACKAGE_PINS
from ...browser_runtime_policy import package_versions as package_versions
from ...config import BROWSER_BINARY_PATH_ENV_VAR
from ...http import RequestCancelledError
from ...http.transport import request_cancel_check
from ...reason_codes import NOT_CONFIGURED
from ..base import ProviderFailure
from .managed_process import ManagedProcess
from .types import BrowserRuntimeConfig, BrowserRuntimeFailure


class PreparationBudget:
    def __init__(self, seconds: float, runtime_context: Any = None):
        self.deadline = time.monotonic() + seconds
        self.context = runtime_context

    def remaining(self) -> float:
        if self.context is not None:
            self.context.raise_if_cancelled()
        else:
            preparation_cancel_check.get()()
            cancelled = request_cancel_check.get()
            if cancelled is not None and cancelled():
                raise RequestCancelledError("Chromium preparation or access cancelled.")
        remaining = self.deadline - time.monotonic()
        if self.context is not None:
            remaining = min(
                remaining, self.context.browser_remaining_seconds(remaining)
            )
        if remaining <= 0:
            raise BrowserRuntimeFailure(
                "scrapling_timeout",
                "Chromium preparation or access deadline exhausted.",
            )
        return remaining

    def check(self) -> None:
        self.remaining()


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
        # Explicit request preparation uses the same cache as the first launch.
        if (
            not str(env.get(BROWSER_BINARY_PATH_ENV_VAR, "")).strip()
            and package_versions() == BROWSER_PACKAGE_PINS
        ):
            from .api import load_runtime_config

            config = load_runtime_config(
                env, provider="pnas", doi="probe://browser/prepare"
            )
            token = preparation_cancel_check.set(cancel_check)
            try:
                prepare_chromium(config)
            finally:
                preparation_cancel_check.reset(token)


fetch_browser_preparation: ContextVar[FetchBrowserPreparation | None] = ContextVar(
    "fetch_browser_preparation", default=None
)


preparation_cancel_check: ContextVar[Callable[[], None]] = ContextVar(
    "preparation_cancel_check", default=lambda: None
)


def verify_package_installation() -> None:
    versions = package_versions()
    if versions != BROWSER_PACKAGE_PINS:
        raise ProviderFailure(
            NOT_CONFIGURED,
            f"Install paper-fetch-skill[browser] for the pinned browser packages. Expected {BROWSER_PACKAGE_PINS}, found {versions}.",
        )


def browser_cache_dir(env: Mapping[str, str]) -> Path:
    configured = env.get("PLAYWRIGHT_BROWSERS_PATH", "").strip()
    if configured == "0":
        driver = metadata.distribution("patchright").locate_file(
            "patchright/driver/package"
        )
        return Path(str(driver)) / ".local-browsers"
    if configured:
        return Path(configured).expanduser().resolve()
    if sys.platform == "win32":
        path = Path(
            env.get("LOCALAPPDATA")
            or os.environ.get("LOCALAPPDATA")
            or Path.home() / "AppData/Local"
        )
    elif sys.platform == "darwin":
        path = Path.home() / "Library/Caches"
    else:
        path = Path(env.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return (path / "ms-playwright").expanduser().resolve()


def inspect_chromium(cache: Path) -> tuple[Path, str, bool]:
    distribution = metadata.distribution("patchright")
    driver = distribution.locate_file("patchright/driver/package/browsers.json")
    manifest = json.loads(Path(str(driver)).read_text(encoding="utf-8"))
    browser = next(item for item in manifest["browsers"] if item["name"] == "chromium")
    arm64 = platform.machine().lower() in {"aarch64", "arm64"}
    if sys.platform == "win32":
        relative_path = Path("chrome-win64/chrome.exe")
    elif sys.platform == "darwin":
        architecture = "arm64" if arm64 else "x64"
        relative_path = (
            Path(f"chrome-mac-{architecture}")
            / "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
        )
    else:
        relative_path = Path(
            "chrome-linux/chrome" if arm64 else "chrome-linux64/chrome"
        )
    root = cache / f"chromium-{browser['revision']}"
    path = root / relative_path
    return (
        path,
        browser["browserVersion"],
        (
            path.is_file()
            and os.access(path, os.X_OK)
            and (root / "INSTALLATION_COMPLETE").is_file()
        ),
    )


def prepare_chromium(
    config: BrowserRuntimeConfig,
    *,
    runtime_context: Any = None,
    budget: PreparationBudget | None = None,
) -> Path:
    verify_package_installation()
    if config.binary_path:
        return Path(config.binary_path)
    budget = budget or PreparationBudget(config.timeout_ms / 1000, runtime_context)
    env = runtime_context.env if runtime_context is not None else os.environ
    cache = config.browser_cache_dir or browser_cache_dir(env)

    def prepare() -> Path:
        path, _, installed = inspect_chromium(cache)
        if installed:
            return path
        # Patchright owns layout, locking, completion markers and cache reuse.
        # Coordinate before starting its installer so cancelled waiters can exit.
        cache.mkdir(parents=True, exist_ok=True)
        lease = FileLock(str(cache / ".paper-fetch-chromium.lock"))
        while True:
            try:
                lease.acquire(timeout=min(0.05, budget.remaining()))
                break
            except Timeout:
                pass
        try:
            path, _, installed = inspect_chromium(cache)
            if installed:
                return path
            # The upstream installer skips an existing completion marker. An
            # incomplete copy of this revision must be repaired on retry.
            root = cache / path.relative_to(cache).parts[0]
            marker = root / "INSTALLATION_COMPLETE"
            if not root.is_symlink() and not marker.is_symlink():
                marker.unlink(missing_ok=True)
            with tempfile.TemporaryDirectory(
                prefix="paper-fetch-chromium-install-"
            ) as temporary:
                process = ManagedProcess(
                    Path(temporary),
                    {"install": True},
                    {**os.environ, **env, "PLAYWRIGHT_BROWSERS_PATH": str(cache)},
                )
                try:
                    while process.process.poll() is None:
                        time.sleep(min(0.05, budget.remaining()))
                    if process.process.returncode:
                        raise BrowserRuntimeFailure(
                            "scrapling_preparation_failed", process.error()
                        )
                finally:
                    process.close()
            path, _, installed = inspect_chromium(cache)
            if not installed:
                raise BrowserRuntimeFailure(
                    "scrapling_preparation_failed",
                    f"Patchright did not install Chromium at {path}.",
                )
            return path
        finally:
            lease.release()

    scope = fetch_browser_preparation.get()
    if scope is None:
        return prepare()
    return scope.run(
        str(cache), prepare, budget.check, valid=lambda _: inspect_chromium(cache)[2]
    )
