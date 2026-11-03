"""Private subprocess entry point. Run with the host interpreter's -I -S flags."""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


def main():
    settings = json.loads(Path(sys.argv[1]).read_text())
    root = Path(settings["work_dir"])
    while not (root / "start").exists():
        time.sleep(0.01)
    runtime = Path(settings["runtime"])
    sys.path[:0] = [str(runtime / "lib"), str(runtime / "upstream/src")]
    os.environ["HEADLESS"] = str(settings["headless"]).lower()
    sys.dont_write_bytecode = True
    import utils
    import undetected_chromedriver as uc
    import flaresolverr_service as service
    from dtos import V1RequestBase

    utils.CHROME_EXE_PATH = settings["chrome_path"]
    utils.CHROME_MAJOR_VERSION = settings["chrome_version"].split(".")[0]
    utils.PLATFORM_VERSION = os.name
    driver_path = root / ("chromedriver.exe" if os.name == "nt" else "chromedriver")
    shutil.copy2(settings["driver"], driver_path)
    utils.PATCHED_DRIVER_PATH = str(driver_path)
    uc.Patcher.data_path = str(root / "patcher")
    original_chrome = uc.Chrome

    def chrome(*args, **kwargs):
        options = kwargs["options"]
        options.arguments[:] = [
            arg
            for arg in options.arguments
            if not arg.startswith(
                ("--ignore-certificate-errors", "--ignore-ssl-errors")
            )
        ]
        options.set_capability("acceptInsecureCerts", False)
        if settings.get("local_check"):
            # Chrome otherwise opens a network-backed new tab before CDP attaches.
            for argument in (
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-sync",
                "--proxy-server=direct://",
                "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost",
                "about:blank",
            ):
                options.add_argument(argument)
            kwargs["user_data_dir"] = tempfile.mkdtemp(prefix="chrome-", dir=root)
        # Chrome's inline PDF viewer hides attachment bytes from download events.
        options.add_experimental_option(
            "prefs", {"plugins.always_open_pdf_externally": True}
        )
        kwargs.update(
            browser_executable_path=settings["chrome_path"],
            driver_executable_path=str(driver_path),
            use_subprocess=True,
        )
        return original_chrome(*args, **kwargs)

    uc.Chrome = chrome
    session_id = "paper-fetch-owned"
    server = None
    if os.name != "nt":

        def terminate(_signal, _frame):
            raise SystemExit(0)

        signal.signal(signal.SIGTERM, terminate)
    try:
        # Keep upstream's standard version/browser/User-Agent initialization.
        # It primes the headless UA before creating the request-owned session.
        service.test_browser_installation()
        session, _ = service.SESSIONS_STORAGE.create(session_id)
        address = session.driver.capabilities["goog:chromeOptions"]["debuggerAddress"]
        host, port = address.rsplit(":", 1)
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise RuntimeError("Owned Chrome returned a non-loopback CDP address")

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                if self.headers.get("Authorization") != "Bearer " + settings["token"]:
                    self.send_error(403)
                    return
                try:
                    request = json.loads(
                        self.rfile.read(int(self.headers["Content-Length"]))
                    )
                    if request["action"] != "navigate":
                        raise ValueError("Unknown private control action")
                    driver = service.SESSIONS_STORAGE.sessions[session_id].driver
                    driver.switch_to.window(request["target"])
                    driver.set_page_load_timeout(request["timeout_ms"] / 1000)
                    response = service.controller_v1_endpoint(
                        V1RequestBase(
                            {
                                "cmd": "request.get",
                                "session": session_id,
                                "url": request["url"],
                                "maxTimeout": request["timeout_ms"],
                            }
                        )
                    )
                    payload = {"status": response.status, "message": response.message}
                except Exception as exc:
                    payload = {"status": "error", "message": str(exc)}
                data = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                    self.wfile.write(data)

        server = HTTPServer(("127.0.0.1", 0), Handler)
        ready = root / "ready.json"
        staged = root / "ready.tmp"
        staged.write_text(
            json.dumps({"port": server.server_port, "cdp": f"http://{host}:{port}"})
        )
        staged.replace(ready)
        server.serve_forever()
    finally:
        for key in service.SESSIONS_STORAGE.session_ids():
            with contextlib.suppress(Exception):
                service.SESSIONS_STORAGE.destroy(key)
        if utils.XVFB_DISPLAY is not None:
            with contextlib.suppress(Exception):
                utils.XVFB_DISPLAY.stop()
        if server is not None:
            server.server_close()


if __name__ == "__main__":
    main()
