"""CLI progress reporting and cooperative cancellation channels."""

from __future__ import annotations

import contextlib
import json
import signal
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import paper_fetch.cli as cli_pkg

from ..manifest import ManifestRecord
from ..manifest_writer import serialize_manifest_record
from ..models import TRUNCATION_WARNING


class FetchProgress:
    """CLI JSONL/text events and the opt-in stdin control channel (protocol 1)."""

    def __init__(
        self, mode: str, run_id: UUID, count: int, *, receipt_dir: Path | None = None
    ) -> None:
        self.mode = (
            ("text" if cli_pkg.sys.stderr.isatty() else "none")
            if mode == "auto"
            else mode
        )
        self.run_id = str(run_id)
        self.cancel_all = threading.Event()
        self.cancelled: set[int] = set()
        self.terminal: dict[int, ManifestRecord] = {}
        self.count = count
        # Control and completion must agree on exactly one terminal outcome.
        # The same lock keeps concurrent stderr events whole and flushed.
        self.lock = threading.RLock()
        self.last_assets: dict[int, float] = {}
        self.receipt_dir = receipt_dir
        self.emit("run_started", 0, total=count)
        for index in range(1, count + 1):
            self.emit("stage", index, stage="queued")

    def emit(self, event: str, index: int, **data: Any) -> None:
        with self.lock:
            if index in self.terminal and event not in {"terminal", "cancel_response"}:
                return
            if self.mode == "jsonl":
                cli_pkg.sys.stderr.write(
                    json.dumps(
                        {
                            "paper_fetch_progress": True,
                            "protocol_version": 1,
                            "run_id": self.run_id,
                            "index": index,
                            "type": event,
                            **data,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                cli_pkg.sys.stderr.flush()
            elif self.mode == "text":
                if event == "assets":
                    current = cli_pkg.time.monotonic()
                    counts = data["counts"]
                    if current - self.last_assets.get(index, 0) < 0.2:
                        return
                    self.last_assets[index] = current
                    detail = ", ".join(
                        f"{c['kind']} {c['completed']}/{c['total'] if c['total'] is not None else '?'} (failed {c['failed']})"
                        for c in counts
                    )
                elif event == "terminal":
                    record = data["record"]
                    acceptance = record["acceptance"]
                    content = acceptance["content"]
                    scope = (
                        "fulltext"
                        if content["has_fulltext"]
                        else "abstract_only"
                        if content["has_abstract"]
                        else "metadata_only"
                    )
                    detail = f"{record['record_status']} acceptance={acceptance['overall']} scope={scope}"
                    if TRUNCATION_WARNING in record["warnings"]:
                        detail += " truncated"
                    if record.get("error"):
                        detail += ": " + str(record["error"].get("reason", ""))
                else:
                    detail = str(data.get("stage") or data.get("status") or event)
                    if event == "run_started" and self.receipt_dir is not None:
                        detail += f" receipts={self.receipt_dir}"
                    if detail in {"executing_browser", "browser_finished"}:
                        if "queue_seconds" in data:
                            detail += f" queue={data['queue_seconds']:.3f}s"
                        if "execution_seconds" in data:
                            detail += f" execution={data['execution_seconds']:.3f}s"
                print(
                    f"[{index}/{self.count}] {detail}",
                    file=cli_pkg.sys.stderr,
                    flush=True,
                )

    def is_cancelled(self, index: int) -> bool:
        with self.lock:
            return self.cancel_all.is_set() or index in self.cancelled

    def complete(
        self, index: int, build: Callable[[bool], ManifestRecord]
    ) -> ManifestRecord:
        with self.lock:
            if index in self.terminal:
                return self.terminal[index]
            record = build(self.is_cancelled(index))
            if index not in self.terminal:
                self.terminal[index] = record
                self.emit(
                    "terminal",
                    index,
                    record=json.loads(serialize_manifest_record(record)),
                )
            return record

    def control(self, value: object) -> None:
        with self.lock:
            if not isinstance(value, dict):
                self.emit("cancel_response", 0, status="invalid_command")
                return
            index = value.get("index")
            if (
                type(value.get("protocol_version")) is not int
                or value.get("protocol_version") != 1
                or "index" not in value
                or value.get("command") != "cancel"
                or (
                    index is not None
                    and (type(index) is not int or not 1 <= index <= self.count)
                )
            ):
                self.emit("cancel_response", 0, status="invalid_command")
                return
            if value.get("run_id") != self.run_id:
                self.emit("cancel_response", index or 0, status="stale_run")
                return
            if index in self.terminal or len(self.terminal) == self.count:
                self.emit("cancel_response", index or 0, status="already_finished")
                return
            if index is None:
                self.cancel_all.set()
            else:
                self.cancelled.add(index)
            self.emit("cancel_response", index or 0, status="cancelling")

    def read_control(self) -> None:
        try:
            discarding = False
            for line in iter(lambda: cli_pkg.sys.stdin.readline(16_385), ""):
                if len(line) > 16_384 or discarding:
                    if not discarding:
                        self.emit("cancel_response", 0, status="invalid_command")
                    discarding = not line.endswith("\n")
                    continue
                try:
                    self.control(json.loads(line))
                except (ValueError, TypeError):
                    self.emit("cancel_response", 0, status="invalid_command")
        except OSError:
            pass
        finally:
            with self.lock:
                if len(self.terminal) != self.count:
                    self.cancel_all.set()

    def start_control(self) -> None:
        threading.Thread(
            target=self.read_control, name="paper-fetch-control", daemon=True
        ).start()


@contextlib.contextmanager
def _cooperative_batch_cancel(
    cancel_event: threading.Event,
    close_active_contexts: Callable[[], None],
) -> Iterator[None]:
    if threading.current_thread() is not threading.main_thread() or not hasattr(
        signal, "SIGINT"
    ):
        yield
        return

    signals = [signal.SIGINT]
    if hasattr(signal, "SIGTERM"):
        signals.append(signal.SIGTERM)
    previous_handlers = {number: signal.getsignal(number) for number in signals}

    def handle_interrupt(_signum: int, _frame: Any) -> None:
        if cancel_event.is_set():
            close_active_contexts()
            raise KeyboardInterrupt
        cancel_event.set()
        print(
            "Cancellation requested; waiting for active batch workers to stop. "
            "Press Ctrl-C again to force browser shutdown.",
            file=cli_pkg.sys.stderr,
        )

    for number in signals:
        signal.signal(number, handle_interrupt)
    try:
        yield
    finally:
        for number, handler in previous_handlers.items():
            signal.signal(number, handler)
