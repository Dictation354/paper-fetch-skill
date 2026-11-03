"""Request-owned Chrome/FlareSolverr/CDP lifecycle and accepted JSON state."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import queue
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, cast
import urllib.request

from .chrome import SystemChrome, discover_chrome
from .flaresolverr_preparation import (
    PreparationBudget,
    cache_lock,
    prepare_source,
    prepare_driver,
)
from .paths import _filtered_storage_state_mapping, storage_state_path
from .types import BrowserRuntimeConfig, BrowserRuntimeFailure
from ...config import resolve_user_data_dir

PNAS_HOME_URL = "https://www.pnas.org/"
PROVIDER_HOME_URLS = {
    "pnas": PNAS_HOME_URL,
    "elsevier": "https://www.sciencedirect.com/",
}


def linux_launch_prefix(
    headless: bool, work_dir: Path, budget: PreparationBudget
) -> list[str]:
    if sys.platform != "linux" or not headless:
        return []
    if shutil.which("Xvfb") is None:
        raise BrowserRuntimeFailure(
            "flaresolverr_not_prepared",
            "Linux FlareSolverr headless requires Xvfb and Chrome's shared-library dependencies. Install Xvfb, then retry.",
        )
    sockets = Path("/tmp/.X11-unix")
    if not sockets.exists() or os.access(sockets, os.W_OK):
        return []
    bwrap = shutil.which("bwrap")
    if bwrap is None:
        raise BrowserRuntimeFailure(
            "flaresolverr_not_prepared",
            "Read-only /tmp/.X11-unix requires rootless bubblewrap with user/mount namespaces; WSLg mounts will not be modified.",
        )
    private = work_dir / "x11"
    private.mkdir(mode=0o1777)
    prefix = [
        bwrap,
        "--die-with-parent",
        "--unshare-user",
        "--unshare-pid",
        "--ro-bind",
        "/",
        "/",
        "--dev-bind",
        "/dev",
        "/dev",
        "--proc",
        "/proc",
        "--bind",
        "/tmp",
        "/tmp",
        "--bind",
        str(private),
        str(sockets),
    ]
    result = subprocess.run(
        [*prefix, "/bin/true"], capture_output=True, timeout=min(10, budget.remaining())
    )
    if result.returncode:
        raise BrowserRuntimeFailure(
            "flaresolverr_not_prepared",
            "Rootless bubblewrap namespaces are unavailable: "
            + result.stderr.decode(errors="replace").strip(),
        )
    return prefix


class FlareSolverrManager:
    def __init__(
        self,
        config: BrowserRuntimeConfig,
        *,
        runtime_context: Any = None,
        local_check: bool = False,
    ):
        self.config = config
        self.home_url = (
            PNAS_HOME_URL
            if config.provider == "pnas"
            else PROVIDER_HOME_URLS[config.provider]
        )
        self.runtime_context = runtime_context
        self.local_check = local_check
        self.budget = PreparationBudget(config.timeout_ms / 1000, runtime_context)
        self.context: Any = None
        self.browser: Any = None
        self.playwright: Any = None
        self.process: subprocess.Popen[bytes] | None = None
        self.job: Any = None
        self.work_dir: Path | None = None
        self.control: dict[str, Any] = {}
        self.token = secrets.token_urlsafe(32)
        self.diagnostics: dict[str, Any] = {
            "provider": config.provider,
            "backend": "flaresolverr",
            "context_reused": False,
        }
        self.metadata: dict[str, Any] = {}
        self.owner_thread = threading.get_ident()
        self._storage_origins: dict[str, Any] = {}

    def _check_owner(self):
        if threading.get_ident() != self.owner_thread:
            raise RuntimeError(
                "Publisher Chrome context must be used on its owning thread"
            )

    def new_context(
        self, *, prepared: tuple[SystemChrome, Path, Path, str] | None = None
    ):
        self._check_owner()
        if self.context is not None:
            self.budget.check()
            self.diagnostics["context_reused"] = True
            if not self.local_check:
                self.refresh()
            return self.context
        try:
            env = (
                self.runtime_context.env
                if self.runtime_context is not None
                else os.environ
            )
            chrome_env = {**(env or os.environ)}
            if self.config.chrome_binary_path:
                chrome_env["PAPER_FETCH_CHROME_BINARY_PATH"] = (
                    self.config.chrome_binary_path
                )
            chrome = (
                prepared[0]
                if prepared
                else discover_chrome(
                    chrome_env, timeout=min(10, self.budget.remaining())
                )
            )
            self.work_dir = Path(
                tempfile.mkdtemp(prefix=f"paper-fetch-{self.config.provider}-")
            )
            prefix = linux_launch_prefix(
                self.config.headless, self.work_dir, self.budget
            )
            if prepared:
                _, runtime, driver, driver_version = prepared
            else:
                cache = resolve_user_data_dir(env) / "flaresolverr"
                runtime = prepare_source(cache, self.budget)
                driver, driver_version = prepare_driver(
                    cache, chrome.version, self.budget
                )
            self.diagnostics.update(
                chrome_path=chrome.path,
                chrome_version=chrome.version,
                chromedriver_version=driver_version,
                flaresolverr_version="3.5.2",
            )
            settings = self.work_dir / "config.json"
            settings.write_text(
                json.dumps(
                    {
                        "work_dir": str(self.work_dir),
                        "runtime": str(runtime),
                        "driver": str(driver),
                        "chrome_path": chrome.path,
                        "chrome_version": chrome.version,
                        "headless": self.config.headless,
                        "local_check": self.local_check,
                        "token": self.token,
                    }
                )
            )
            settings.chmod(0o600)
            launcher = Path(__file__).with_name("flaresolverr_launcher.py")
            log = self.work_dir / "service.log"
            child_env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            with log.open("wb") as output:
                self.process = subprocess.Popen[bytes](
                    [*prefix, sys.executable, "-I", "-S", str(launcher), str(settings)],
                    stdout=output,
                    stderr=output,
                    env=child_env,
                    start_new_session=os.name != "nt",
                    **(
                        {"creationflags": cast(Any, subprocess).CREATE_NO_WINDOW}
                        if os.name == "nt"
                        else {}
                    ),
                )
            if os.name == "nt":
                from .windows_job import WindowsProcessJob

                self.job = WindowsProcessJob(self.process)
            (self.work_dir / "start").touch()
            while not (self.work_dir / "ready.json").exists():
                self.budget.check()
                if self.process.poll() is not None:
                    raise BrowserRuntimeFailure(
                        "flaresolverr_start_failed",
                        "Publisher browser startup failed: "
                        + log.read_text(errors="replace")[-6000:],
                    )
                time.sleep(min(0.05, self.budget.remaining()))
            self.control = json.loads((self.work_dir / "ready.json").read_text())
            from playwright.sync_api import sync_playwright

            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.connect_over_cdp(
                self.control["cdp"], timeout=int(self.budget.remaining() * 1000)
            )
            self.context = self.browser.contexts[0]
            self.context._paper_fetch_solver = self
            if not self.local_check:
                self._restore_state()
                self.refresh()
            return self.context
        except BaseException as exc:
            self.close()
            from ...http import RequestCancelledError

            if isinstance(exc, Exception) and not isinstance(
                exc, (BrowserRuntimeFailure, RequestCancelledError)
            ):
                raise BrowserRuntimeFailure(
                    "flaresolverr_preparation_failed",
                    f"Publisher browser preparation failed: {exc}",
                ) from exc
            raise

    def _restore_state(self):
        path = storage_state_path(self.config)
        if path is None or not path.is_file():
            return
        with cache_lock(path.with_suffix(path.suffix + ".lock"), self.budget):
            state = _filtered_storage_state_mapping(
                json.loads(path.read_text()),
                url=self.home_url,
                provider=self.config.provider,
            )
        if not state:
            return
        if state.get("cookies"):
            self.context.add_cookies(state["cookies"])
        self._storage_origins = {
            item["origin"]: item.get("localStorage", [])
            for item in state.get("origins", [])
        }
        self.diagnostics["state_restored"] = True

    def _request(self, payload, *, page=None):
        remaining = self.budget.remaining()
        result: queue.Queue[tuple[bool, Any]] = queue.Queue()
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.control['port']}/",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/json",
            },
        )

        def send():
            try:
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                    request, timeout=remaining
                ) as response:
                    result.put((True, json.load(response)))
            except BaseException as exc:
                result.put((False, exc))

        threading.Thread(target=send, daemon=True).start()
        while True:
            self.budget.check()
            if page is not None:
                # Route callbacks and response listeners must run while Selenium
                # navigates. This pumps events without issuing a second navigation.
                page.wait_for_timeout(min(20, self.budget.remaining() * 1000))
            try:
                ok, value = result.get(timeout=min(0.05, self.budget.remaining()))
                break
            except queue.Empty:
                pass
        if not ok:
            raise value
        if value.get("status") != "ok":
            raise BrowserRuntimeFailure(
                "flaresolverr_navigation_failed",
                value.get("message") or "Publisher navigation failed",
            )
        return value

    def navigate(self, page, url: str, timeout_ms: int):
        self._check_owner()
        cdp = self.context.new_cdp_session(page)
        try:
            target = cdp.send("Target.getTargetInfo")["targetInfo"]["targetId"]
        finally:
            cdp.detach()
        if not self.diagnostics.get("homepage_visited"):
            self._request(
                {
                    "action": "navigate",
                    "target": target,
                    "url": self.home_url,
                    "timeout_ms": min(timeout_ms, int(self.budget.remaining() * 1000)),
                },
                page=page,
            )
            origin = page.evaluate("() => location.origin")
            items = self._storage_origins.pop(origin, [])
            if items:
                page.evaluate(
                    "items => { for (const item of items) localStorage.setItem(item.name, item.value); }",
                    items,
                )
            self.diagnostics["homepage_visited"] = True
        if url == self.home_url:
            return None
        self._request(
            {
                "action": "navigate",
                "target": target,
                "url": url,
                "timeout_ms": min(timeout_ms, int(self.budget.remaining() * 1000)),
            },
            page=page,
        )
        # Pump the CDP event queue before inspecting actual document responses.
        page.wait_for_timeout(1)
        self.diagnostics["navigation_count"] = (
            self.diagnostics.get("navigation_count", 0) + 1
        )
        return None

    def refresh(self):
        if self.context is None:
            return None
        state = _filtered_storage_state_mapping(
            self.context.storage_state(),
            url=self.home_url,
            provider=self.config.provider,
        )
        digest = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
        self.diagnostics["state_sha256"] = digest
        if self.runtime_context is not None:
            self.runtime_context.record_browser_state_capability_use(
                provider=self.config.provider,
                backend="flaresolverr",
                storage_state_path=storage_state_path(self.config),
                content_sha256=digest,
            )
        return digest

    def note_json_export(self, path):
        self.refresh()

    def close(self):
        self._check_owner()
        for item in (self.browser, self.playwright):
            if item is not None:
                with contextlib.suppress(Exception):
                    item.close() if item is self.browser else item.stop()
        if self.job is not None:
            self.job.close()
        if self.process is not None:
            if os.name != "nt":
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(self.process.pid, signal.SIGTERM)
            elif self.process.poll() is None:
                self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                if os.name != "nt":
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(self.process.pid, signal.SIGKILL)
                else:
                    self.process.kill()
                self.process.wait(timeout=2)
        self.context = self.browser = self.playwright = self.process = self.job = None
        if self.work_dir is not None:
            shutil.rmtree(self.work_dir, ignore_errors=True)
            self.work_dir = None


def navigate_page(page, url: str, *, timeout_ms: int, **kwargs):
    solver = getattr(getattr(page, "context", None), "_paper_fetch_solver", None)
    if isinstance(solver, FlareSolverrManager):
        return solver.navigate(page, url, timeout_ms)
    return page.goto(url, timeout=timeout_ms, **kwargs)
