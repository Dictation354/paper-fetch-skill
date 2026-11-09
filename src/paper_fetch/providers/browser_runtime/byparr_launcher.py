"""Request-owned Byparr controller; launched with explicit shared package paths."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def main():
    settings = json.loads(Path(sys.argv[1]).read_text())
    root = Path(settings["work_dir"])
    while not (root / "start").exists():
        time.sleep(0.01)
    runtime = Path(settings["runtime"])
    sys.path[:0] = [
        str(runtime / "lib"),
        str(runtime / "upstream"),
        *settings["site_paths"],
        str(Path(__file__).parent),
    ]
    sys.dont_write_bytecode = True
    os.environ["VERSION"] = "3.1.1"
    os.environ["LOG_LEVEL"] = "DEBUG"
    from byparr_upstream import load_challenge

    sys.modules["byparr_challenge"] = load_challenge(runtime)
    from camoufox.utils import launch_options, spoofs_window_dimensions
    from playwright._impl._driver import compute_driver_executable

    options = launch_options(
        executable_path=settings.get("binary_path"),
        headless=settings["headless"],
        main_world_eval=True,
        locale="en-US",
        humanize=True,
        i_know_what_im_doing=True,
        disable_coop=True,
        firefox_user_prefs={"pdfjs.disabled": True},
    )
    if settings.get("user_data_dir"):
        # Preserve Camoufox NewBrowser's native-context defaults. The private
        # launchServer persistent entry accepts protocol keys (not JS API keys).
        options.update(
            colorScheme="no-override",
            reducedMotion="no-override",
            forcedColors="no-override",
            contrast="no-override",
        )
        if spoofs_window_dimensions(options):
            options["noDefaultViewport"] = True
    node, cli = compute_driver_executable()
    # launch_options uses Python spellings; launchServer consumes JS spellings.
    keys = {
        "executable_path": "executablePath",
        "firefox_user_prefs": "firefoxUserPrefs",
    }
    options = {keys.get(k, k): v for k, v in options.items()}
    options["env"] = {k: str(v) for k, v in options.get("env", os.environ).items()}
    settings.update(launch_options=options, playwright_package=str(Path(cli).parent))
    node_settings = root / "node.json"
    node_settings.write_text(json.dumps(settings))
    node_settings.chmod(0o600)
    node_process = subprocess.Popen(
        [str(node), settings["server_script"], str(node_settings)],
        stdin=subprocess.PIPE,
    )
    try:
        while not (root / "browser.json").exists():
            if node_process.poll() is not None:
                raise RuntimeError("Camoufox shared browser service exited")
            time.sleep(0.02)
        endpoint = json.loads((root / "browser.json").read_text())["endpoint"]
        asyncio.run(serve(settings, root, endpoint, node_process))
    finally:
        if settings.get("user_data_dir") and node_process.poll() is None:
            # The protocol disconnect can precede Firefox's process exit.
            # Let launchServer finish its 30-second graceful close so native
            # localStorage/cookies are flushed before terminating its owner.
            with contextlib.suppress(subprocess.TimeoutExpired):
                node_process.wait(timeout=30)
        if node_process.poll() is None:
            node_process.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            node_process.wait(timeout=2)
        if node_process.poll() is None:
            node_process.kill()
            node_process.wait(timeout=2)


async def serve(settings, root, endpoint, node_process):
    from playwright.async_api import BrowserContext, async_playwright
    from byparr_adapter import ManagedOperation

    async with async_playwright() as playwright:
        browser = await playwright.firefox.connect(endpoint)
        stopped = asyncio.Event()
        browser.on("disconnected", lambda _: stopped.set())
        loop = asyncio.get_running_loop()
        solver_locks: dict[BrowserContext, asyncio.Lock] = {}
        operations: dict[str, ManagedOperation] = {}

        def write_evidence(value):
            with (root / "operations.jsonl").open("a") as stream:
                stream.write(json.dumps(value) + "\n")

        async def dispatch(payload):
            if payload.get("command") == "shutdown":
                for operation in list(operations.values()):
                    await operation.close()
                node_process.stdin.write(b"close\n")
                node_process.stdin.flush()
                return {"status": "ok"}
            operation_id = payload["operation"]
            command = payload.get("command", "navigate")
            if command in {"finish", "cancel"}:
                operation = operations[operation_id]
                if command == "cancel":
                    operations.pop(operation_id, None)
                    await operation.close()
                    return {"status": "ok"}
                return await operation.finish()
            context = browser.contexts[0] if browser.contexts else None
            index = payload.get("page_index", -1)
            page = (
                context.pages[index]
                if context is not None and 0 <= index < len(context.pages)
                else None
            )
            if page is None:
                raise ValueError("Shared page identifier is unavailable")
            for key, previous in list(operations.items()):
                if previous.closed:
                    operations.pop(key, None)
                elif previous.page == page:
                    await previous.finish(retain=False)
                    operations.pop(key, None)
            operation = ManagedOperation(
                page,
                payload,
                solver_locks.setdefault(page.context, asyncio.Lock()),
                write_evidence,
            )
            operations[operation_id] = operation
            if command == "arm":
                return {"status": "ok", "operation": operation_id}
            try:
                return await operation.navigate()
            except BaseException:
                operations.pop(operation_id, None)
                await operation.close()
                raise

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                if self.headers.get("Authorization") != "Bearer " + settings["token"]:
                    self.send_error(403)
                    return
                try:
                    payload = json.loads(
                        self.rfile.read(int(self.headers.get("Content-Length", "0")))
                    )
                    future = asyncio.run_coroutine_threadsafe(dispatch(payload), loop)
                    value = future.result(timeout=payload["timeout_ms"] / 1000 + 1)
                except Exception as exc:
                    if "future" in locals():
                        future.cancel()
                    value = {
                        "status": "error",
                        "message": str(exc),
                        "error": type(exc).__name__,
                    }
                body = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                with contextlib.suppress(BrokenPipeError):
                    self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        ready = root / "ready.json"
        ready.with_suffix(".tmp").write_text(
            json.dumps({"endpoint": endpoint, "port": server.server_port})
        )
        ready.with_suffix(".tmp").replace(ready)
        try:
            await stopped.wait()
        finally:
            server.shutdown()
            server.server_close()
            with contextlib.suppress(Exception):
                await browser.close()


if __name__ == "__main__":
    if os.name != "nt":
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    main()
