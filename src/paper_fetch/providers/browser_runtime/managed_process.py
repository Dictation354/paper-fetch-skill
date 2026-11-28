"""Own a browser subprocess and all of its drivers and browser children."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from .paths import _atomic_write_json


class ManagedProcess:
    def __init__(self, root: Path, settings: dict[str, Any], env: dict[str, str]):
        self.root = root
        self.log = root / "service.log"
        self.job = None
        self.groups: set[int] = set()
        config = root / "config.json"
        _atomic_write_json(
            config,
            {
                **settings,
                "site_paths": [str(Path(path).resolve()) for path in sys.path if path],
            },
        )
        launcher = Path(__file__).with_name("chromium_launcher.py")
        with self.log.open("wb") as stream:
            self.process = subprocess.Popen(
                [sys.executable, "-I", "-S", str(launcher), str(config)],
                stdout=stream,
                stderr=stream,
                env=env,
                start_new_session=os.name != "nt",
                creationflags=(
                    cast(Any, subprocess).CREATE_NO_WINDOW if os.name == "nt" else 0
                ),
            )
        try:
            if os.name == "nt":
                from .windows_job import WindowsProcessJob

                self.job = WindowsProcessJob(self.process)
            (root / "start").touch()
        except BaseException:
            self.close()
            raise

    def error(self) -> str:
        return self.log.read_text(encoding="utf-8", errors="replace")[-6000:].strip()

    def track_process_groups(self) -> None:
        if os.name == "nt" or self.process.poll() is not None:
            return
        # Patchright's driver can start Chromium as a detached process-group
        # leader. Retain its group while the controller still owns the tree.
        try:
            table = subprocess.check_output(
                ["/bin/ps", "-axo", "pid=,ppid=,pgid="], text=True, timeout=2
            )
        except (OSError, subprocess.SubprocessError):
            return
        children: dict[int, list[tuple[int, int]]] = {}
        for row in table.strip().splitlines():
            pid, parent, group = map(int, row.split())
            children.setdefault(parent, []).append((pid, group))
        pending = [self.process.pid]
        while pending:
            for pid, group in children.get(pending.pop(), ()):
                if pid == group:
                    self.groups.add(group)
                pending.append(pid)

    def close(self, *, graceful: bool = False) -> None:
        self.track_process_groups()
        try:
            if graceful and self.process.poll() is None:
                (self.root / "shutdown").touch()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    self.process.wait(timeout=5)
        finally:
            if self.job is not None:
                self.job.close()
            elif os.name != "nt":
                # The group can still contain a browser/driver after the leader exits.
                for group in self.groups | {self.process.pid}:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(group, signal.SIGKILL)
            elif self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=5)
