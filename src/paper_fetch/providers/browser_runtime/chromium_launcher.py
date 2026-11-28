"""Run Patchright installation or a Scrapling session in the owned process."""

from __future__ import annotations

import asyncio
import contextlib
import json
import runpy
import sys
import time
from pathlib import Path
from typing import Any


async def _target_page(context: Any, target_id: str) -> Any:
    while True:
        for page in context.pages:
            session = await context.new_cdp_session(page)
            try:
                info = await session.send("Target.getTargetInfo")
                if info["targetInfo"]["targetId"] == target_id:
                    return page
            finally:
                await session.detach()
        await asyncio.sleep(0.01)


async def _execute(session: Any, payload: dict, record: dict) -> None:
    from patchright.async_api import Error

    page = await _target_page(session.context, payload["target_id"])
    timeout = payload["timeout_ms"]
    response = None
    if payload["command"] == "navigate":
        record["stage"] = "navigation"
        try:
            response = await page.goto(
                payload["url"], timeout=timeout, **payload["options"]
            )
        except Error as exc:
            if payload["mode"] != "file" or "Download is starting" not in str(exc):
                raise
            record["download_started"] = True
            return
        if response is None:
            return
        headers = response.headers
        if "html" not in headers.get("content-type", "").lower() and not headers.get(
            "cf-mitigated"
        ):
            return
        # Commit-mode requests must keep their fast path. The caller settles
        # after provider readiness and on later document responses.
        if not headers.get("cf-mitigated") and response.status < 400:
            return
        await page.wait_for_load_state("domcontentloaded", timeout=timeout)

    if session._detect_cloudflare(await page.content()) or (
        response is not None and response.headers.get("cf-mitigated") == "challenge"
    ):
        record["stage"] = "cloudflare_challenge"
        await session._cloudflare_solver(page)
        if session._detect_cloudflare(await page.content()):
            record["failure_stage"] = "cloudflare_challenge"


async def _operation(session: Any, path: Path, root: Path) -> None:
    from paper_fetch.providers.browser_runtime.paths import _atomic_write_json

    payload = json.loads(path.read_text(encoding="utf-8"))
    path.unlink()
    name = path.stem
    cancel = root / f"{name}.cancel"
    record = {"stage": "cdp_target"}
    task = asyncio.create_task(_execute(session, payload, record))
    deadline = time.monotonic() + payload["timeout_ms"] / 1000
    try:
        while not task.done():
            remaining = deadline - time.monotonic()
            if cancel.exists() or (root / "shutdown").exists():
                return
            if remaining <= 0:
                raise TimeoutError("Chromium operation deadline exhausted.")
            await asyncio.wait({task}, timeout=min(0.02, remaining))
        task.result()
    except Exception as exc:
        record.update(
            failure_stage=record["stage"], error=str(exc), error_type=type(exc).__name__
        )
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        cancel.unlink(missing_ok=True)
        _atomic_write_json(root / f"{name}.result", record)


async def _serve(root: Path, settings: dict) -> None:
    from scrapling.fetchers import AsyncStealthySession

    from paper_fetch.providers.browser_runtime.paths import _atomic_write_json

    profile = Path(settings["profile"])
    preferences = profile / "Default" / "Preferences"
    stored = (
        json.loads(preferences.read_text(encoding="utf-8"))
        if preferences.is_file()
        else {}
    )
    # Capture the publisher's PDF bytes through Chromium's native download event.
    stored.setdefault("plugins", {})["always_open_pdf_externally"] = True
    # Chromium restores session cookies when the last session is restored.
    stored.setdefault("session", {})["restore_on_startup"] = 1
    _atomic_write_json(preferences, stored)
    devtools = profile / "DevToolsActivePort"
    devtools.unlink(missing_ok=True)
    session = AsyncStealthySession(
        headless=settings["headless"],
        user_data_dir=str(profile),
        extra_flags=[
            "--remote-debugging-address=127.0.0.1",
            "--remote-debugging-port=0",
        ],
        additional_args={
            "executable_path": settings["executable_path"],
            "accept_downloads": True,
            "ignore_https_errors": False,
            "permissions": [],
            "timeout": settings["timeout_ms"],
        },
    )
    try:
        await session.start()
        port, socket_path = devtools.read_text(encoding="utf-8").splitlines()
        _atomic_write_json(
            root / "ready.json",
            {"endpoint": f"ws://127.0.0.1:{int(port)}{socket_path}"},
        )
        while not (root / "shutdown").exists():
            for path in sorted(root.glob("operation-*.json")):
                await _operation(session, path, root)
            await asyncio.sleep(0.01)
    finally:
        with contextlib.suppress(Exception):
            await session.close()


def main() -> None:
    config = Path(sys.argv[1])
    root = config.parent
    settings = json.loads(config.read_text(encoding="utf-8"))
    while not (root / "start").exists():
        time.sleep(0.01)
    sys.path[:0] = settings["site_paths"]
    sys.dont_write_bytecode = True
    if settings.get("install"):
        sys.argv = ["patchright", "install", "--no-shell", "chromium"]
        runpy.run_module("patchright", run_name="__main__", alter_sys=True)
    else:
        asyncio.run(_serve(root, settings))


if __name__ == "__main__":
    main()
