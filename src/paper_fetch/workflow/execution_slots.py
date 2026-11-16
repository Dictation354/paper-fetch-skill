"""Let profile waiters yield batch execution capacity while retaining thread affinity."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import threading
from collections import Counter

current_slots: ContextVar[ExecutionSlots | None] = ContextVar(
    "execution_slots", default=None
)


class ExecutionSlots:
    def __init__(self, count: int):
        self.permits = threading.Semaphore(count)
        self.lock = threading.Lock()
        self.waiting = 0
        self.local = threading.local()
        self.waiting_by_lane: Counter[object] = Counter()

    def run(self, worker, item, lane=None):
        self.permits.acquire()
        self.local.held = True
        self.local.lane = lane
        token = current_slots.set(self)
        try:
            return worker(item)
        finally:
            current_slots.reset(token)
            if self.local.held:
                self.permits.release()

    @contextmanager
    def suspend(self, cancel_check=None):
        with self.lock:
            self.waiting += 1
            self.waiting_by_lane[self.local.lane] += 1
        self.permits.release()
        self.local.held = False
        try:
            yield
        finally:
            try:
                while not self.permits.acquire(timeout=0.05):
                    if cancel_check is not None:
                        cancel_check()
                self.local.held = True
            finally:
                with self.lock:
                    self.waiting -= 1
                    self.waiting_by_lane[self.local.lane] -= 1


@contextmanager
def profile_wait(cancel_check=None):
    slots = current_slots.get()
    if slots is None:
        yield
    else:
        with slots.suspend(cancel_check):
            yield
