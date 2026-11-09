"""Native Invisible session and owner-thread execution of Byparr's solver.

Invisible 0.47 owns its Python protocol transport. No Node bridge or second
connection is used. The pinned async solver is compiled for the sync owner;
only async/await and import bindings change, preserving its polling algorithm.
"""

from __future__ import annotations

import ast
import contextlib
import logging
import os
from pathlib import Path
import time
from types import ModuleType
from urllib.parse import urlsplit

from .byparr_adapter import supported_challenge
from .byparr_preparation import PreparationBudget


class SyncCalls(ast.NodeTransformer):
    def visit_AsyncFunctionDef(self, node):
        self.generic_visit(node)
        return ast.FunctionDef(
            name=node.name,
            args=node.args,
            body=node.body,
            decorator_list=node.decorator_list,
            returns=node.returns,
            type_comment=node.type_comment,
        )

    def visit_Await(self, node):
        return self.visit(node.value)

    def visit_ImportFrom(self, node):
        if node.module in {
            "asyncio",
            "src.utils",
            "invisible_playwright.async_api",
        } or (node.module and node.module.startswith("playwright_captcha.")):
            return None
        return node


def load_solver(runtime: Path, wait):
    from invisible_playwright.sync_api import Error, TimeoutError

    bindings = {
        "__name__": "paper_fetch.byparr.upstream",
        "PlaywrightError": Error,
        "PlaywrightTimeoutError": TimeoutError,
        "sleep": wait,
        "logger": logging.getLogger("paper_fetch.byparr.upstream"),
    }
    for path in [
        runtime / "lib/playwright_captcha/solvers/click/cloudflare/utils/detection.py",
        runtime / "upstream/src/challenge.py",
    ]:
        tree = SyncCalls().visit(ast.parse(path.read_text()))
        tree.body.insert(
            0,
            ast.ImportFrom(
                module="__future__", names=[ast.alias(name="annotations")], level=0
            ),
        )
        ast.fix_missing_locations(tree)
        exec(compile(tree, str(path), "exec"), bindings)
    return ModuleTypeWithBindings(bindings)


class ModuleTypeWithBindings(ModuleType):
    def __init__(self, bindings):
        super().__init__("byparr_sync_challenge")
        self.__dict__.update(bindings)


def start(owner, binary, runtime):
    from invisible_playwright import InvisiblePlaywright

    # Follow upstream geo defaults; local installer validation never requires
    # an external timezone lookup. Explicit upstream settings remain available.
    env = owner.runtime_context.env if owner.runtime_context is not None else os.environ
    timezone = env.get("BROWSER_TIMEZONE", os.environ.get("BROWSER_TIMEZONE", "auto"))
    locale = env.get("BROWSER_LOCALE", os.environ.get("BROWSER_LOCALE", "auto"))
    if owner.local_check:
        timezone, locale = "UTC", "en-US"

    session = InvisiblePlaywright(
        binary_path=binary,
        headless=owner.config.headless,
        profile_dir=owner.native_profile,
        humanize=True,
        timezone=timezone,
        locale=locale,
        extra_prefs={
            "pdfjs.disabled": True,
            "devtools.jsonview.enabled": False,
            "browser.tabs.remote.useCrossOriginOpenerPolicy": False,
            "browser.tabs.remote.useCrossOriginEmbedderPolicy": False,
            "dom.security.https_first": False,
        },
    )
    owner._invisible_session = session
    if os.name != "nt":
        from invisible_core.juggler import connection
        from .byparr_posix import spawn

        connection._spawn_posix = spawn
    owner.browser = session.__enter__()
    owner.context = (
        owner.browser
        if owner.native_profile is not None
        else owner.browser.new_context(accept_downloads=True)
    )
    original_cookies = owner.context.add_cookies
    owner.context.add_cookies = lambda cookies: original_cookies(
        owner._cookie_parameters(cookies)
    )
    original_state = owner.context.storage_state

    def storage_state(*, path=None, **kwargs):
        import json

        state = original_state(**kwargs)
        origins = {}
        for page in owner.context.pages:
            try:
                if not page.url.startswith(
                    ("https://", "http://")
                ) or supported_challenge(title=page.title(), html=page.content()):
                    continue
                origin = page.evaluate(
                    "() => ({origin: location.origin, localStorage: Object.entries(localStorage).map(([name,value]) => ({name,value}))})"
                )
                origins[origin["origin"]] = origin
            except Exception:
                continue
        state["origins"] = list(origins.values())
        if path is not None:
            Path(path).write_text(json.dumps(state))
        return state

    owner.context.storage_state = storage_state
    owner.context._paper_fetch_navigator = owner
    owner._sync_operations = []
    owner._solver_runtime = runtime
    owner.diagnostics.update(
        engine="invisible",
        byparr_version="3.1.1",
        invisible_playwright_version="0.47.1",
    )
    if not owner.local_check and owner.native_profile is None:
        owner._restore_state()
        owner.refresh()
    return owner.context


class Operation:
    def __init__(self, owner, page, timeout_ms, mode="html", action="navigate"):
        import secrets

        self.owner, self.page = owner, page
        self.budget = PreparationBudget(timeout_ms / 1000, owner.runtime_context)
        self.operation = secrets.token_urlsafe(16)
        self.documents, self.events, self.responses = [], [], []
        self.downloads, self.pages, self.listeners = [], {page}, []
        self.processed = set()
        self.challenged_frames = {}
        self.solver = load_solver(owner._solver_runtime, self.wait)
        self.record("navigation_managed", mode=mode, action=action)
        self.listen(owner.context, "response", self.response_seen)
        self.listen(owner.context, "page", self.page_seen)
        self.page_seen(page)
        owner._sync_operations.append(self)

    def listen(self, target, event, callback):
        target.on(event, callback)
        self.listeners.append((target, event, callback))

    def page_seen(self, page):
        if page in getattr(self, "_attached", set()):
            return
        if not hasattr(self, "_attached"):
            self._attached = set()
        self._attached.add(page)
        self.listen(page, "download", self.download_seen)

    def download_seen(self, download):
        self.downloads.append(download)

    def owns(self, page):
        current = page
        while current is not None:
            if current in self.pages:
                self.pages.add(page)
                return True
            current = current.opener()
        return False

    def response_seen(self, response):
        try:
            if urlsplit(response.url).hostname == "challenges.cloudflare.com":
                return  # Widget responses do not prove publisher acceptance.
            if not response.request.is_navigation_request() or not self.owns(
                response.frame.page
            ):
                return
            self.responses.append(response)
            self.documents.append(
                {
                    "url": response.url,
                    "status": response.status,
                    "operation": self.operation,
                    "page": response.frame.page.url,
                    "frame": response.url,
                    "frame_id": response.frame._impl_obj._guid,
                    "sequence": len(self.documents) + 1,
                }
            )
        except Exception:
            return

    def record(self, kind, **fields):
        self.events.append(
            {
                "kind": kind,
                "operation": self.operation,
                "page": self.page.url,
                "sequence": len(self.events) + 1,
                **fields,
            }
        )

    def wait(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.budget.check()
            self.page.wait_for_timeout(min(20, max(1, (end - time.monotonic()) * 1000)))

    def navigate(self, url, wait_until, kwargs):
        # Pump the owner loop instead of blocking inside goto: cancellation can
        # close this same thread's session while a navigation is in flight.
        task = self.page._loop.create_task(
            self.page._impl_obj.goto(
                url,
                timeout=max(1, int(self.budget.remaining() * 1000)),
                waitUntil=wait_until,
                **kwargs,
            )
        )
        try:
            while not task.done():
                self.wait(0.02)
            try:
                result = task.result()
            except Exception as exc:
                if "Download is starting" not in str(exc):
                    raise
                result = None
        except BaseException:
            task.cancel()
            self.page.wait_for_timeout(1)
            raise
        else:
            from invisible_playwright._pw._impl._sync_base import mapping

            return mapping.from_maybe_impl(result)

    def finish(self):
        successful_documents = {}
        awaiting_response = set()
        solved_frames = set()
        while True:
            self.budget.check()
            pending = [r for r in self.responses if r not in self.processed]
            for response in pending:
                self.processed.add(response)
                frame = response.frame
                sequence = self.responses.index(response) + 1
                if "html" not in response.headers.get("content-type", "").lower():
                    if 200 <= response.status < 300:
                        successful_documents[frame] = sequence
                    continue
                try:
                    challenge = supported_challenge(
                        title=frame.title(),
                        html=frame.content(),
                        headers=response.headers,
                    )
                except Exception:
                    continue
                if not challenge:
                    if 200 <= response.status < 300:
                        successful_documents[frame] = sequence
                    continue
                self.challenged_frames[frame] = sequence
                awaiting_response.discard(frame)
                self.record(
                    "challenge_detected",
                    response_sequence=sequence,
                    challenge="cloudflare_interstitial",
                )
                self.wait(min(0.5, self.budget.remaining()))

            # Classify responses received during the automatic redirect wait
            # before probing the DOM or invoking the upstream handler.
            if any(r not in self.processed for r in self.responses):
                continue
            for frame, sequence in list(self.challenged_frames.items()):
                if self.downloads or successful_documents.get(frame, 0) > sequence:
                    self.record(
                        "challenge_result",
                        outcome="cleared"
                        if frame in solved_frames
                        else "auto_verified",
                    )
                    del self.challenged_frames[frame]
                    continue
                target = (
                    frame.page
                    if frame == frame.page.main_frame
                    else FrameWithMouse(frame)
                )
                if not self.solver.challenge_present(target):
                    if frame not in awaiting_response:
                        self.record("challenge_result", outcome="awaiting_response")
                        awaiting_response.add(frame)
                    continue
                awaiting_response.discard(frame)
                operation = self

                class Evidence(logging.Handler):
                    def emit(self, record, operation=operation):
                        message = record.getMessage()
                        operation.record("solver_log", message=message)
                        if message.startswith(
                            "Clicked the challenge checkbox (attempt "
                        ):
                            operation.record("solver_click")

                handler = Evidence()
                logger = self.solver.logger
                logger.setLevel(logging.DEBUG)
                logger.addHandler(handler)
                try:

                    class Timer:
                        def remaining(inner):
                            return self.budget.remaining()

                    self.record("solver_called")
                    solved_frames.add(frame)
                    self.solver.solve_challenge(target, Timer())
                    self.record("challenge_result", outcome="awaiting_response")
                    awaiting_response.add(frame)
                except BaseException:
                    self.record("challenge_result", outcome="deadline_exceeded")
                    raise
                finally:
                    logger.removeHandler(handler)
            if not self.challenged_frames:
                return
            if self.downloads or any(r not in self.processed for r in self.responses):
                continue
            self.wait(min(self.solver.POLL_INTERVAL, self.budget.remaining()))

    def close(self):
        if not self.listeners:
            return
        for target, event, callback in self.listeners:
            with contextlib.suppress(Exception):
                target.remove_listener(event, callback)
        self.listeners.clear()
        record = {
            "operation": self.operation,
            "documents": self.documents,
            "events": self.events,
        }
        self.owner.diagnostics.setdefault("byparr_navigations", []).append(record)
        if self.owner.work_dir is not None:
            import json

            with (self.owner.work_dir / "operations.jsonl").open("a") as f:
                f.write(json.dumps(record) + "\n")


class FrameWithMouse:
    def __init__(self, frame):
        self.frame, self.mouse = frame, frame.page.mouse

    def __getattr__(self, name):
        return getattr(self.frame, name)


class HttpResponse:
    def __init__(self, status, headers, url, body):
        self.status, self.headers, self.url, self._body = status, headers, url, body

    def body(self):
        return self._body

    def all_headers(self):
        return self.headers
