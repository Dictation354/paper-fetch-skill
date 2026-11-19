"""Per-host concurrency semaphores and cross-worker rate/cooldown gates."""

from __future__ import annotations

import threading
import urllib.parse
from collections.abc import Callable


class RequestRateGate:
    """Manage per-host semaphores, Retry-After cooldowns, and QPS pacing."""

    def __init__(
        self,
        *,
        per_host_concurrency: int,
        clock: Callable[[], float],
        sleep: Callable[[float], None],
        has_cancel_hooks: Callable[[], bool],
        check_cancelled: Callable[[], None],
    ) -> None:
        self.per_host_concurrency = max(1, int(per_host_concurrency))
        self._clock = clock
        self._sleep = sleep
        self._has_cancel_hooks = has_cancel_hooks
        self._check_cancelled = check_cancelled
        self._host_semaphores: dict[str, threading.BoundedSemaphore] = {}
        self._host_semaphores_lock = threading.Lock()
        self._cooldown_until: dict[str, float] = {}
        self._rate_next_at: dict[str, float] = {}
        self._rate_start_gates: dict[str, threading.Lock] = {}
        self._cooldown_lock = threading.RLock()

    def host_semaphore_for_url(self, url: str) -> threading.BoundedSemaphore | None:
        hostname = urllib.parse.urlparse(url).hostname
        if not hostname:
            return None
        normalized = hostname.lower()
        with self._host_semaphores_lock:
            semaphore = self._host_semaphores.get(normalized)
            if semaphore is None:
                semaphore = threading.BoundedSemaphore(self.per_host_concurrency)
                self._host_semaphores[normalized] = semaphore
        return semaphore

    @staticmethod
    def cooldown_key_for_url(url: str, scope: str | None = None) -> str:
        if scope and str(scope).strip():
            return str(scope).strip().lower()
        return (urllib.parse.urlparse(url).hostname or "").lower()

    def set_cooldown(self, key: str, delay_seconds: float) -> None:
        if not key or delay_seconds <= 0:
            return
        with self._cooldown_lock:
            self._cooldown_until[key] = max(
                self._cooldown_until.get(key, 0.0),
                self._clock() + delay_seconds,
            )

    def sleep_without_host_slot(
        self,
        semaphore: threading.BoundedSemaphore | None,
        seconds: float,
    ) -> None:
        if seconds <= 0:
            return
        if semaphore is None:
            self._sleep(seconds)
            return
        semaphore.release()
        try:
            self._sleep(seconds)
        finally:
            semaphore.acquire()

    def wait_for_cooldown(
        self,
        key: str,
        semaphore: threading.BoundedSemaphore | None,
    ) -> None:
        while key:
            with self._cooldown_lock:
                cooldown_deadline = self._cooldown_until.get(key, 0.0)
                remaining = cooldown_deadline - self._clock()
                if remaining <= 0:
                    self._cooldown_until.pop(key, None)
                    return
            self.sleep_without_host_slot(semaphore, remaining)
            with self._cooldown_lock:
                if self._cooldown_until.get(key, 0.0) <= cooldown_deadline:
                    self._cooldown_until.pop(key, None)
                    return

    def wait_for_rate_slot(
        self,
        key: str,
        minimum_interval_seconds: float,
        semaphore: threading.BoundedSemaphore | None,
    ) -> None:
        interval = max(0.0, float(minimum_interval_seconds))
        if not key or interval <= 0:
            self.wait_for_cooldown(key, semaphore)
            return
        gate = self.rate_start_gate_for(key)
        self._acquire_rate_start_gate(gate, semaphore)
        try:
            while True:
                with self._cooldown_lock:
                    now = self._clock()
                    scheduled_at = max(
                        self._rate_next_at.get(key, 0.0),
                        self._cooldown_until.get(key, 0.0),
                    )
                self.sleep_without_host_slot(semaphore, max(0.0, scheduled_at - now))
                with self._cooldown_lock:
                    now = self._clock()
                    if now < max(
                        self._rate_next_at.get(key, 0.0),
                        self._cooldown_until.get(key, 0.0),
                    ):
                        continue
                    self._cooldown_until.pop(key, None)
                    self._rate_next_at[key] = now + interval
                    return
        finally:
            gate.release()

    def rate_start_gate_for(self, key: str) -> threading.Lock:
        with self._cooldown_lock:
            gate = self._rate_start_gates.get(key)
            if gate is None:
                gate = threading.Lock()
                self._rate_start_gates[key] = gate
            return gate

    def _acquire_rate_start_gate(
        self,
        gate: threading.Lock,
        semaphore: threading.BoundedSemaphore | None,
    ) -> None:
        if semaphore is not None:
            semaphore.release()
        try:
            if not self._has_cancel_hooks():
                gate.acquire()
                return
            while True:
                self._check_cancelled()
                if gate.acquire(timeout=0.05):
                    return
        finally:
            if semaphore is not None:
                semaphore.acquire()


__all__ = ["RequestRateGate"]
