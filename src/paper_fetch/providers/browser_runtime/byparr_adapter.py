"""Private adapter for locked Byparr 3.1.1; never fabricates HTTP success.

Upstream's Cloudflare interstitial solver is reused without its unconditional
networkidle wait or second navigation. Each operation retains its original
page, descendants, responses and deadline across automatic redirects.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from urllib.parse import urlsplit

try:
    from .byparr_engine import playwright_api
except ImportError:  # Request-owned controller imports this file directly.
    import byparr_engine

    playwright_api = byparr_engine.playwright_api


def supported_challenge(*, title="", html="", headers=None) -> bool:
    headers = {str(k).lower(): str(v).lower() for k, v in (headers or {}).items()}
    text = html.lower()
    marker = any(
        s in text
        for s in (
            'id="challenge-running"',
            "cf_chl_opt",
            'id="challenge-form"',
        )
    )
    return (
        headers.get("cf-mitigated") == "challenge"
        or title.strip().lower() == "just a moment..."
        or marker
    )


class SolverFrame:
    """A publisher iframe keeps its own locators and its page's input device."""

    def __init__(self, frame):
        self.frame = frame
        self.mouse = frame.page.mouse

    def __getattr__(self, name):
        return getattr(self.frame, name)


class ManagedOperation:
    def __init__(self, page, payload, solver_lock, write_evidence):
        self.runner = asyncio.current_task()
        self.page = page
        self.context = page.context
        self.payload = payload
        self.id = payload["operation"]
        self.deadline = min(
            payload.get("deadline", float("inf")),
            time.monotonic() + payload["timeout_ms"] / 1000,
        )
        self.solver_lock = solver_lock
        self.write_evidence = write_evidence
        self.pages = {page}
        self.downloads = []
        self.response_times = {}
        self.tasks = {}
        self.response_received = asyncio.Event()
        self.documents = []
        self.events = []
        self.listeners = []
        self.closed = False
        self.expiry = asyncio.get_running_loop().call_later(
            max(0, self.deadline - time.monotonic()),
            lambda: asyncio.create_task(self.close()),
        )
        self.record(
            "navigation_managed",
            page=page,
            mode=payload.get("mode", "html"),
            action=payload.get("action", "navigate"),
        )
        self.listen(self.context, "response", self.response_seen)
        self.listen(page, "popup", self.popup_seen)
        self.listen(page, "download", self.download_seen)

    def record(self, kind, *, page=None, **fields):
        event = {
            "kind": kind,
            "operation": self.id,
            "page_id": getattr(
                getattr(page or self.page, "_impl_obj", None),
                "_guid",
                self.payload["page"],
            ),
            "page": str(getattr(page or self.page, "url", "")),
            "sequence": len(self.events) + 1,
            **fields,
        }
        self.events.append(event)
        if kind in {"challenge_detected", "solver_click", "challenge_result"}:
            self.save_evidence()
        return event

    def listen(self, owner, event, handler):
        owner.on(event, handler)
        self.listeners.append((owner, event, handler))

    def download_seen(self, download):
        self.downloads.append((time.monotonic(), download.url))
        self.record("download_observed", url=download.url)

    def popup_seen(self, page):
        if page not in self.pages:
            self.pages.add(page)
            self.listen(page, "popup", self.popup_seen)
            self.listen(page, "download", self.download_seen)

    def response_seen(self, response):
        if (
            self.closed
            or time.monotonic() >= self.deadline
            or not response.request.is_navigation_request()
        ):
            return
        self.response_received.set()
        key = response.request._impl_obj._guid
        if key not in self.tasks:
            self.response_times[key] = time.monotonic()
            self.tasks[key] = asyncio.create_task(self.inspect_response(response))
            self.tasks[key].add_done_callback(
                lambda task: task.exception() if not task.cancelled() else None
            )

    async def owns(self, page):
        current = page
        while current is not None:
            if current in self.pages:
                self.popup_seen(page)
                return True
            current = await current.opener()
        return False

    async def snapshot(self, frame):
        Error = playwright_api(asynchronous=True).Error

        while True:
            try:
                return await frame.title(), await frame.content()
            except Error:
                if frame.is_detached() or frame.page.is_closed():
                    return "", ""
                if time.monotonic() >= self.deadline:
                    raise
                await asyncio.sleep(0.02)

    async def inspect_response(self, response):
        async with asyncio.timeout(max(0, self.deadline - time.monotonic())):
            try:
                frame = response.frame
                page = frame.page
            except Exception:
                return  # Download ownership/bytes are established by the sync owner.
            if not await self.owns(page):
                # Shared clients can receive a popup response before its opener
                # relationship. Let the already-installed popup listener attach it.
                await response.finished()
                for _ in range(10):
                    if await self.owns(page):
                        break
                    await asyncio.sleep(0.01)
                else:
                    return
            if (
                frame != page.main_frame
                and urlsplit(response.url).hostname == "challenges.cloudflare.com"
            ):
                return  # Solver widget, not a publisher navigation/challenge.
            document = {
                "url": response.url,
                "status": response.status,
                "operation": self.id,
                "page": page.url,
                "frame": response.url,
                "frame_id": getattr(
                    getattr(frame, "_impl_obj", None), "_guid", str(id(frame))
                ),
                "sequence": len(self.documents) + 1,
            }
            self.documents.append(document)
            self.save_evidence()
            headers = response.headers
            mime = headers.get("content-type", "").lower()
            if "html" not in mime and not supported_challenge(headers=headers):
                return
            await response.finished()
            with contextlib.suppress(Exception):
                await frame.wait_for_load_state(
                    "domcontentloaded",
                    timeout=max(1, (self.deadline - time.monotonic()) * 1000),
                )
            title, html = await self.snapshot(frame)
            current = supported_challenge(title=title, html=html)
            if not current and not supported_challenge(headers=headers):
                return
            response_at = self.response_times[response.request._impl_obj._guid]
            detected_at = time.monotonic()
            self.record(
                "challenge_detected",
                page=page,
                frame=frame.url,
                response_sequence=document["sequence"],
                challenge="cloudflare_interstitial",
            )
            async with self.solver_lock:
                # A response can already have automatically passed validation,
                # or another observation of this frame can have solved it.
                await asyncio.sleep(min(0.5, max(0, self.deadline - time.monotonic())))
                title, html = await self.snapshot(frame)
                if not supported_challenge(title=title, html=html) or any(
                    when >= response_at for when, url in self.downloads
                ):
                    self.record(
                        "challenge_result",
                        page=page,
                        outcome="already_cleared"
                        if getattr(self.solver_lock, "cleared_frames", {}).get(frame, 0)
                        >= detected_at
                        else "auto_verified",
                        response_sequence=document["sequence"],
                    )
                    return
                from byparr_challenge import solve_challenge
                from byparr_upstream import TimeoutTimer, logger

                operation = self

                class Evidence(logging.Handler):
                    def emit(self, record):
                        message = record.getMessage()
                        operation.record("solver_log", page=page, message=message)
                        if message.startswith(
                            "Clicked the challenge checkbox (attempt "
                        ):
                            operation.record(
                                "solver_click",
                                page=page,
                                response_sequence=document["sequence"],
                            )

                handler = Evidence()
                logger.setLevel(logging.DEBUG)
                logger.addHandler(handler)
                try:
                    self.record(
                        "solver_called",
                        page=page,
                        response_sequence=document["sequence"],
                    )
                    await solve_challenge(
                        page if frame == page.main_frame else SolverFrame(frame),
                        TimeoutTimer(deadline=self.deadline),
                    )
                    # The upstream solver confirms absence twice across navigation;
                    # only a real document/download proves publisher acceptance.
                    real_success = any(
                        item["frame_id"] == document["frame_id"]
                        and item["sequence"] > document["sequence"]
                        and 200 <= item["status"] < 300
                        for item in self.documents
                    ) or any(when >= response_at for when, _ in self.downloads)
                    self.record(
                        "challenge_result",
                        page=page,
                        outcome="cleared" if real_success else "awaiting_response",
                        response_sequence=document["sequence"],
                    )
                except asyncio.CancelledError:
                    self.record(
                        "challenge_result",
                        page=page,
                        outcome="deadline_exceeded"
                        if time.monotonic() >= self.deadline
                        else "cancelled",
                        response_sequence=document["sequence"],
                    )
                    raise
                except Exception as exc:
                    # Leave classification to the real page/response consumers.
                    self.record(
                        "challenge_result",
                        page=page,
                        outcome="solver_failed",
                        error=type(exc).__name__,
                        response_sequence=document["sequence"],
                    )
                finally:
                    logger.removeHandler(handler)

    async def navigate(self):
        Error = playwright_api(asynchronous=True).Error

        try:
            await self.page.goto(
                self.payload["url"],
                wait_until=self.payload.get("wait_until", "load"),
                timeout=max(1, (self.deadline - time.monotonic()) * 1000),
                **self.payload.get("goto_options", {}),
            )
        except Error as exc:
            if "Download is starting" not in str(exc):
                raise
            self.record("download_started")
        return await self.finish()

    async def finish(self, *, retain=True):
        try:
            async with asyncio.timeout(max(0, self.deadline - time.monotonic())):
                # Response callbacks may append redirect/iframe tasks while the
                # original challenge task is running. Drain all of them once.
                if self.payload.get("command") == "arm" and not self.tasks:
                    await self.response_received.wait()
                completed: set[asyncio.Task[None]] = set()
                while pending := set(self.tasks.values()) - completed:
                    await asyncio.gather(*pending)
                    completed.update(pending)
            return {
                "status": "ok",
                "documents": self.documents,
                "events": self.events,
                "operation": self.id,
            }
        finally:
            self.save_evidence()
            if not retain:
                await self.close()

    def save_evidence(self):
        self.write_evidence(
            {"operation": self.id, "documents": self.documents, "events": self.events}
        )

    async def close(self):
        if self.closed:
            return
        self.closed = True
        self.expiry.cancel()
        if (
            self.runner is not None
            and self.runner is not asyncio.current_task()
            and not self.runner.done()
        ):
            self.runner.cancel()
        for owner, event, handler in self.listeners:
            owner.remove_listener(event, handler)
        self.listeners.clear()
        pending = [task for task in self.tasks.values() if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self.write_evidence(
            {"operation": self.id, "documents": self.documents, "events": self.events}
        )
