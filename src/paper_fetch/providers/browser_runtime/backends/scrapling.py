"""Own a Scrapling Chromium subprocess and attach Playwright on the caller thread."""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from ....http import RequestCancelledError
from ....logging_utils import redact_log_value
from ....utils import sanitize_filename
from ..managed_process import ManagedProcess
from ..paths import _atomic_write_json
from ..preparation import PreparationBudget, package_versions, prepare_chromium
from ..types import BrowserRuntimeConfig, BrowserRuntimeFailure


class ScraplingManager:
    def __init__(
        self,
        config: BrowserRuntimeConfig,
        *,
        native_profile: Path,
        runtime_context: Any = None,
    ) -> None:
        self.config = config
        self.native_profile = native_profile
        self.runtime_context = runtime_context
        self.owner_thread = threading.get_ident()
        self.work_dir: tempfile.TemporaryDirectory[str] | None = None
        self.process: ManagedProcess | None = None
        self.context: Any = None
        self.browser: Any = None
        self.playwright: Any = None
        self.sequence = 0
        self.active_navigation: dict[Any, dict] = {}
        self.active_actions: dict[Any, tuple[PreparationBudget, dict]] = {}
        self.diagnostics: dict[str, Any] = {
            "provider": config.provider,
            "doi": config.doi,
            "backend": config.backend,
            "browser_backend": config.backend,
            "engine": "chromium",
            "headless": config.headless,
            "context_reused": False,
            "navigations": [],
        }

    def _check_owner(self) -> None:
        if threading.get_ident() != self.owner_thread:
            raise RuntimeError("Chromium must be used on its owning thread.")

    def _budget(self, timeout_ms: float) -> PreparationBudget:
        return PreparationBudget(timeout_ms / 1000, self.runtime_context)

    def new_context(self) -> Any:
        self._check_owner()
        if self.context is not None:
            self.diagnostics["context_reused"] = True
            return self.context

        stage = "chromium_preparation"
        budget = self._budget(self.config.timeout_ms)
        try:
            executable = prepare_chromium(
                self.config, runtime_context=self.runtime_context, budget=budget
            )
            self.diagnostics.update(
                {
                    f"{name}_version": version
                    for name, version in package_versions().items()
                }
            )
            stage = "chromium_launch"
            self.work_dir = tempfile.TemporaryDirectory(prefix="paper-fetch-chromium-")
            root = Path(self.work_dir.name)
            self.process = ManagedProcess(
                root,
                {
                    "profile": str(self.native_profile),
                    "headless": self.config.headless,
                    "executable_path": str(executable),
                    "timeout_ms": max(1, int(budget.remaining() * 1000)),
                },
                dict(os.environ),
            )
            ready = root / "ready.json"
            self._wait_for(ready, budget)
            self.process.track_process_groups()
            stage = "cdp_connect"
            from playwright.sync_api import sync_playwright

            self.playwright = sync_playwright().start()
            downloads = root / "downloads"
            downloads.mkdir()
            self.browser = self.playwright.chromium.connect_over_cdp(
                json.loads(ready.read_text(encoding="utf-8"))["endpoint"],
                timeout=max(1, int(budget.remaining() * 1000)),
                is_local=True,
                artifacts_dir=downloads,
            )
            budget.check()
            self.context = self.browser.contexts[0]
            self.context._paper_fetch_navigator = self
            self.context.on("response", self._response)
            self.context.on("page", self._watch_page)
            for page in self.context.pages:
                self._watch_page(page)
            self.diagnostics["chromium_version"] = self.browser.version
            return self.context
        except BaseException as exc:
            self.diagnostics.update(failure_stage=stage, error=str(exc))
            self.close()
            if not isinstance(exc, Exception) or isinstance(exc, RequestCancelledError):
                raise
            if isinstance(exc, BrowserRuntimeFailure):
                kind = exc.kind
            else:
                kind = "browser_context_create_failed"
            raise BrowserRuntimeFailure(
                kind,
                str(exc),
                details={"stage": stage, "scrapling": dict(self.diagnostics)},
            ) from exc

    def _watch_page(self, page: Any) -> None:
        def closed() -> None:
            self.active_navigation.pop(page, None)
            self.active_actions.pop(page, None)

        page.on("close", closed)
        page.on("download", lambda download: self._download(page, download))

    def _record_for(self, page: Any) -> dict | None:
        entry = self.active_navigation.get(page)
        if entry is not None:
            return entry
        if not self.active_actions:
            return None
        owner = page
        while owner is not None:
            action = self.active_actions.get(owner)
            if action is not None:
                budget, record = action
                if time.monotonic() < budget.deadline:
                    return record
                self.active_actions.pop(owner, None)
                return None
            if owner.is_closed():
                break
            owner = owner.opener()
        return None

    def _response(self, response: Any) -> None:
        if not response.request.is_navigation_request():
            return
        try:
            frame = response.frame
        except Exception:
            # Chromium may report a popup navigation before assigning its frame.
            return
        page = frame.page
        record = self._record_for(page)
        if record is None:
            return
        main_frame = frame == page.main_frame
        record.setdefault("documents", []).append(
            {"url": response.url, "status": response.status, "main_frame": main_frame}
        )
        if main_frame:
            record.update(response_status=response.status, final_url=response.url)

    def _download(self, page: Any, download: Any) -> None:
        record = self._record_for(page)
        if record is not None:
            record.update(download_started=True, download_url=download.url)

    def _wait_for(
        self, path: Path, budget: PreparationBudget, page: Any = None
    ) -> None:
        assert self.process is not None
        while not path.is_file():
            wait = min(0.02, budget.remaining())
            if self.process.process.poll() is not None:
                raise BrowserRuntimeFailure(
                    "browser_context_create_failed",
                    self.process.error() or "Scrapling Chromium subprocess exited.",
                )
            if page is None:
                time.sleep(wait)
            else:
                # The sync owner services routes and response/download callbacks
                # while the child operates on the same Chromium target.
                page.wait_for_timeout(wait * 1000)
        budget.check()

    def _operation(
        self, page: Any, budget: PreparationBudget, operation: dict, record: dict
    ) -> None:
        assert self.work_dir is not None
        self._check_owner()
        root = Path(self.work_dir.name)
        self.sequence += 1
        name = f"operation-{self.sequence:08}"
        request = root / f"{name}.json"
        result = root / f"{name}.result"
        cdp = self.context.new_cdp_session(page)
        try:
            target = cdp.send("Target.getTargetInfo")["targetInfo"]["targetId"]
        finally:
            cdp.detach()
        _atomic_write_json(
            request,
            {
                **operation,
                "target_id": target,
                "timeout_ms": max(1, int(budget.remaining() * 1000)),
            },
        )
        try:
            self._wait_for(result, budget, page)
            payload = json.loads(result.read_text(encoding="utf-8"))
            if payload.get("stage") == "cdp_target" and "error" not in payload:
                payload.pop("stage")
            record.update(payload)
            if "error" in payload:
                kind = (
                    "scrapling_timeout"
                    if payload["error_type"] == "TimeoutError"
                    else "scrapling_navigation_failed"
                )
                raise BrowserRuntimeFailure(kind, payload["error"])
            page.wait_for_timeout(1)  # Drain already queued network events.
        except BaseException as exc:
            if not result.exists():
                (root / f"{name}.cancel").touch()
            record.update(failure_stage=record["stage"], error=str(exc))
            if isinstance(exc, BrowserRuntimeFailure):
                exc.details.update(stage=record["stage"], scrapling=dict(record))
            raise
        finally:
            result.unlink(missing_ok=True)

    def navigate(
        self, page: Any, url: str, timeout_ms: int, *, mode: str = "html", **kwargs: Any
    ) -> Any:
        record: dict[str, Any] = {
            "url": url,
            "mode": mode,
            "stage": "navigation",
            "response_status": None,
        }
        self.diagnostics["navigations"].append(record)
        self.active_actions.pop(page, None)
        self.active_navigation[page] = record
        responses = []

        def observe(response: Any) -> None:
            if not response.request.is_navigation_request():
                return
            try:
                if response.frame == page.main_frame:
                    responses.append(response)
            except Exception:
                pass

        page.on("response", observe)
        try:
            self._operation(
                page,
                self._budget(timeout_ms),
                {"command": "navigate", "url": url, "mode": mode, "options": kwargs},
                record,
            )
        finally:
            page.remove_listener("response", observe)
        return responses[-1] if responses else None

    def settle(self, page: Any, *, timeout_ms: int) -> None:
        if page.is_closed() or page.url == "about:blank":
            return
        record = self._record_for(page)
        if record is None:
            record = {"mode": "html", "stage": "navigation", "url": page.url}
            self.diagnostics["navigations"].append(record)
        self._operation(page, self._budget(timeout_ms), {"command": "settle"}, record)

    @contextlib.contextmanager
    def action(self, page: Any, *, timeout_ms: int, mode: str = "file"):
        budget = self._budget(timeout_ms)
        record = {
            "mode": mode,
            "stage": "click",
            "url": page.url,
            "response_status": None,
        }
        self.diagnostics["navigations"].append(record)
        self.active_navigation.pop(page, None)
        self.active_actions[page] = (budget, record)
        try:
            yield
            budget.check()
        except BaseException as exc:
            record.update(failure_stage="click", error=str(exc))
            self.active_actions.pop(page, None)
            raise

    def close(self) -> None:
        self._check_owner()
        if self.work_dir is None:
            if "failure_stage" in self.diagnostics:
                self._write_diagnostics()
            return
        try:
            if self.process is not None:
                self.process.close(graceful=True)
                self.diagnostics["session_closed"] = True
        finally:
            if self.browser is not None:
                with contextlib.suppress(Exception):
                    self.browser.close()
            if self.playwright is not None:
                with contextlib.suppress(Exception):
                    self.playwright.stop()
            self.context = self.browser = self.playwright = self.process = None
            self.active_navigation.clear()
            self.active_actions.clear()
            self.work_dir.cleanup()
            self.work_dir = None
            self._write_diagnostics()

    def _write_diagnostics(self) -> None:
        runtime = self.runtime_context
        store = getattr(runtime, "artifact_store", None)
        if store is None or not store.allows_auxiliary_artifacts or runtime.cancelled:
            return
        path = (
            store.download_dir
            / "diagnostics"
            / self.config.provider
            / sanitize_filename(self.config.doi)
            / "scrapling.json"
        )
        with contextlib.suppress(OSError, RequestCancelledError):
            store.write_json_file(
                path, redact_log_value(self.diagnostics), overwrite=True
            )
            artifact = {
                "path": str(path),
                "kind": "diagnostic",
                "route": "browser_html",
            }
            if artifact not in runtime.diagnostic_artifacts:
                runtime.diagnostic_artifacts.append(artifact)
