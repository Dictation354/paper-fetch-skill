"""Request-owned shared Camoufox/Byparr lifecycle and accepted JSON state."""

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

from .byparr_preparation import (
    PreparationBudget,
    cache_lock,
    prepare_components,
)
from .paths import _filtered_storage_state_mapping, storage_state_path
from .types import BrowserRuntimeConfig, BrowserRuntimeFailure
from ...config import resolve_user_data_dir


class ByparrManager:
    def __init__(
        self,
        config: BrowserRuntimeConfig,
        *,
        runtime_context: Any = None,
        local_check: bool = False,
        native_profile: Path | None = None,
    ):
        self.config = config
        from ...provider_catalog import PROVIDER_CATALOG

        self.home_url = PROVIDER_CATALOG[config.provider].browser_home_url
        self.runtime_context = runtime_context
        self.local_check = local_check
        self.native_profile = native_profile
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
            "backend": "byparr",
            "engine": "camoufox",
            "state_mode": config.state_mode,
            "context_reused": False,
        }
        self.metadata: dict[str, Any] = {}
        self.owner_thread = threading.get_ident()
        self._directory_lock: Any = None

    def _check_owner(self):
        if threading.get_ident() != self.owner_thread:
            raise RuntimeError(
                "Publisher Byparr context must be used on its owning thread"
            )

    def new_context(self, *, prepared: Path | None = None):
        self._check_owner()
        if self.context is not None:
            self.diagnostics["context_reused"] = True
            if not self.local_check:
                self.refresh()
            return self.context
        try:
            from .camoufox_manager import _launch_executable_path

            env = (
                self.runtime_context.env
                if self.runtime_context is not None
                else os.environ
            )
            binary = _launch_executable_path(self.config.binary_path)
            self.budget.check()
            cache = (
                self.config.component_cache_dir or resolve_user_data_dir(env) / "byparr"
            )
            runtime = prepared or prepare_components(cache, self.budget)
            if (
                not self.local_check
                and self.native_profile is None
                and self.config.user_data_dir is not None
            ):
                lease = cache_lock(
                    self.config.user_data_dir / ".byparr-session.lock", self.budget
                )
                lease.__enter__()
                self._directory_lock = lease
            self.work_dir = Path(
                tempfile.mkdtemp(prefix=f"paper-fetch-{self.config.provider}-byparr-")
            )
            self.diagnostics.update(
                byparr_version="2.1.0",
                camoufox_version="0.5.9",
                playwright_captcha_version="0.1.5",
            )
            settings = self.work_dir / "config.json"
            settings.write_text(
                json.dumps(
                    {
                        "work_dir": str(self.work_dir),
                        "runtime": str(runtime),
                        "binary_path": binary,
                        "site_paths": [str(Path(p).resolve()) for p in sys.path if p],
                        "server_script": str(
                            Path(__file__).with_name("byparr_server.cjs")
                        ),
                        "headless": self.config.headless,
                        "local_check": self.local_check,
                        "user_data_dir": str(self.native_profile)
                        if self.native_profile is not None
                        else None,
                        "token": self.token,
                    }
                )
            )
            settings.chmod(0o600)
            launcher = Path(__file__).with_name("byparr_launcher.py")
            log = self.work_dir / "service.log"
            child_env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            with log.open("wb") as output:
                self.process = subprocess.Popen[bytes](
                    [sys.executable, "-I", "-S", str(launcher), str(settings)],
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
                        "byparr_start_failed",
                        "Publisher browser startup failed: "
                        + log.read_text(errors="replace")[-6000:],
                    )
                time.sleep(min(0.05, self.budget.remaining()))
            self.control = json.loads((self.work_dir / "ready.json").read_text())
            from playwright.sync_api import sync_playwright

            self.playwright = sync_playwright().start()
            self.browser = self.playwright.firefox.connect(
                self.control["endpoint"], timeout=int(self.budget.remaining() * 1000)
            )
            self.context = (
                self.browser.contexts[0]
                if self.native_profile is not None
                else self.browser.new_context(accept_downloads=True)
            )
            self.context._paper_fetch_navigator = self
            if not self.local_check and self.native_profile is None:
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
                    "byparr_preparation_failed",
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
        origins = {
            item["origin"]: item.get("localStorage", [])
            for item in state.get("origins", [])
        }
        self.context.add_init_script(
            "const origins = "
            + json.dumps(origins)
            + "; for (const item of origins[location.origin] || []) localStorage.setItem(item.name, item.value);"
        )
        self.diagnostics["state_restored"] = True

    def _request(self, payload, *, page=None):
        budget = PreparationBudget(payload["timeout_ms"] / 1000, self.runtime_context)
        remaining = budget.remaining()
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
            budget.check()
            if page is not None:
                # Route callbacks and response listeners stay on the sync owner
                # thread while Byparr controls the same page asynchronously.
                page.wait_for_timeout(min(20, budget.remaining() * 1000))
            try:
                ok, value = result.get(timeout=min(0.05, budget.remaining()))
                break
            except queue.Empty:
                pass
        if not ok:
            raise value
        if payload.get("command") not in {"arm", "cancel"}:
            records = self.diagnostics.setdefault("byparr_navigations", [])
            entry = {
                "url": payload.get("url"),
                "operation": payload.get("operation"),
                "documents": value.get("documents", []),
                "events": value.get("events", []),
                "status": value.get("status"),
            }
            for previous in records:
                if previous.get("operation") == entry["operation"]:
                    previous.update(
                        {key: item for key, item in entry.items() if item is not None}
                    )
                    break
            else:
                records.append(entry)
        if value.get("status") != "ok":
            if value.get("error") in {"TimeoutError", "Error"}:
                from playwright.sync_api import Error, TimeoutError

                error = TimeoutError if value["error"] == "TimeoutError" else Error
                raise error(value.get("message") or "Publisher navigation timed out")
            raise BrowserRuntimeFailure(
                "byparr_navigation_failed",
                value.get("message") or "Publisher navigation failed",
            )
        return value

    def _operation_payload(self, page, timeout_ms, **kwargs):
        self._check_owner()
        budget = PreparationBudget(timeout_ms / 1000, self.runtime_context)
        identifier = secrets.token_urlsafe(24)
        page.evaluate("name => { window.name = name; }", identifier)
        return {
            "page": identifier,
            "operation": secrets.token_urlsafe(16),
            "timeout_ms": max(1, int(budget.remaining() * 1000)),
            "deadline": budget.deadline,
            **kwargs,
        }

    def navigate(
        self,
        page,
        url: str,
        timeout_ms: int,
        *,
        mode="html",
        wait_until="load",
        **kwargs,
    ):
        payload = self._operation_payload(
            page,
            timeout_ms,
            url=url,
            mode=mode,
            wait_until=wait_until,
            goto_options=kwargs,
        )
        responses = []

        def observe(response):
            if (
                response.request.is_navigation_request()
                and response.frame == page.main_frame
            ):
                responses.append(response)

        page.on("response", observe)
        try:
            self._request(payload, page=page)
            page.__dict__["_paper_fetch_operation"] = payload
            page.wait_for_timeout(1)
        except BaseException:
            # Propagate cancellation/deadline to the async controller without
            # spending another wait budget on the cancelled request.
            threading.Thread(
                target=self._cancel_remote, args=(payload,), daemon=True
            ).start()
            raise
        finally:
            page.remove_listener("response", observe)
        self.diagnostics["navigation_count"] = (
            self.diagnostics.get("navigation_count", 0) + 1
        )
        return responses[-1] if responses else None

    def _cancel_remote(self, payload):
        with contextlib.suppress(Exception):
            request = urllib.request.Request(
                f"http://127.0.0.1:{self.control['port']}/",
                data=json.dumps(
                    {**payload, "command": "cancel", "timeout_ms": 1000}
                ).encode(),
                headers={
                    "Authorization": "Bearer " + self.token,
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                request, timeout=1
            ) as response:
                response.read()

    def settle(self, page, *, timeout_ms):
        payload = page.__dict__.get("_paper_fetch_operation")
        if payload is None:
            return
        remaining = min(
            timeout_ms, int((payload["deadline"] - time.monotonic()) * 1000)
        )
        if remaining > 0:
            self._request(
                {**payload, "command": "finish", "timeout_ms": remaining}, page=page
            )

    @contextlib.contextmanager
    def action(self, page, *, timeout_ms, mode="file"):
        payload = self._operation_payload(
            page, timeout_ms, command="arm", action="click", mode=mode
        )
        self._request(payload, page=page)
        try:
            yield
        except BaseException:
            with contextlib.suppress(Exception):
                self._request(
                    {**payload, "command": "cancel", "timeout_ms": 1000}, page=page
                )
            raise
        else:
            remaining = payload["deadline"] - time.monotonic()
            if remaining <= 0:
                with contextlib.suppress(Exception):
                    self._request(
                        {**payload, "command": "cancel", "timeout_ms": 1000}, page=page
                    )
                raise BrowserRuntimeFailure(
                    "byparr_timeout", "Browser action deadline exhausted"
                )
            self._request(
                {
                    **payload,
                    "command": "finish",
                    "timeout_ms": max(1, int(remaining * 1000)),
                },
                page=page,
            )

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
                backend="byparr",
                storage_state_path=storage_state_path(self.config),
                content_sha256=digest,
            )
        return digest

    def note_json_export(self, path):
        self.refresh()

    def _save_service_evidence(self):
        store = getattr(self.runtime_context, "artifact_store", None)
        if (
            self.work_dir is None
            or store is None
            or not store.allows_auxiliary_artifacts
        ):
            return
        from ...logging_utils import redact_log_value
        from ...utils import sanitize_filename
        from ...http import RequestCancelledError

        documents = []
        path = self.work_dir / "operations.jsonl"
        if path.exists():
            for line in path.read_text().splitlines():
                with contextlib.suppress(ValueError):
                    documents.append(json.loads(line))
        documents = list({item["operation"]: item for item in documents}.values())
        log = self.work_dir / "service.log"
        events = (
            [{"message": line} for line in log.read_text(errors="replace").splitlines()]
            if log.exists()
            else []
        )
        destination = (
            store.download_dir
            / "diagnostics"
            / self.config.provider
            / sanitize_filename(self.config.doi)
            / "byparr-service.json"
        )
        with contextlib.suppress(OSError, RequestCancelledError):
            store.write_json_file(
                destination,
                redact_log_value(
                    {
                        "provider": self.config.provider,
                        "doi": self.config.doi,
                        "browser_backend": "byparr",
                        "operations": documents,
                        "documents": [
                            doc
                            for operation in documents
                            for doc in operation.get("documents", [])
                        ],
                        "events": [
                            event
                            for operation in documents
                            for event in operation.get("events", [])
                        ],
                        "service_log": events,
                    }
                ),
                overwrite=True,
            )
            self.runtime_context.diagnostic_artifacts.append(
                {
                    "path": str(destination),
                    "kind": "diagnostic",
                    "route": "browser_html",
                }
            )

    def close(self):
        self._check_owner()
        if self.process is not None:
            # Ask Node to close Firefox through Playwright before terminating the
            # process tree, so native cookies/localStorage reach the profile.
            if self.process.poll() is None and self.control.get("port"):
                with contextlib.suppress(Exception):
                    request = urllib.request.Request(
                        f"http://127.0.0.1:{self.control['port']}/",
                        data=json.dumps(
                            {"command": "shutdown", "timeout_ms": 2000}
                        ).encode(),
                        headers={
                            "Authorization": "Bearer " + self.token,
                            "Content-Type": "application/json",
                        },
                    )
                    with urllib.request.build_opener(
                        urllib.request.ProxyHandler({})
                    ).open(request, timeout=2) as response:
                        response.read()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    # Native Firefox profiles must finish their graceful close
                    # before the owned process group can be terminated.
                    self.process.wait(timeout=35 if self.native_profile else 5)
            if self.process.poll() is None:
                if os.name != "nt":
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(self.process.pid, signal.SIGTERM)
                else:
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
        if self.job is not None:
            self.job.close()
        self._save_service_evidence()
        # Terminate the owned server first: a shared-client disconnect can wait
        # on a pending route/download while the browser is still alive.
        for item in (self.browser, self.playwright):
            if item is not None:
                with contextlib.suppress(Exception):
                    item.close() if item is self.browser else item.stop()
        self.context = self.browser = self.playwright = self.process = self.job = None
        if self._directory_lock is not None:
            self._directory_lock.__exit__(None, None, None)
            self._directory_lock = None
        if self.work_dir is not None:
            shutil.rmtree(self.work_dir, ignore_errors=True)
            self.work_dir = None
