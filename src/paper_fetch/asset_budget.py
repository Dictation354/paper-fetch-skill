"""Thread-safe per-article resource budget for binary assets."""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from pathlib import Path
import threading
from typing import Any

from .reason_codes import (
    ASSET_BYTES_PER_ASSET_EXCEEDED,
    ASSET_BYTES_TOTAL_EXCEEDED,
    ASSET_CANCELLED,
    ASSET_FILE_LIMIT_EXCEEDED,
    ASSET_PIXEL_LIMIT_EXCEEDED,
)

DEFAULT_ASSET_MAX_FILES: int | None = None
DEFAULT_ASSET_MAX_BYTES_PER_ASSET = 32 * 1024 * 1024
DEFAULT_ASSET_MAX_BYTES_TOTAL = 256 * 1024 * 1024
DEFAULT_ASSET_MAX_PIXELS = 64_000_000
DEFAULT_ASSET_MAX_CONCURRENCY = 4


class AssetBudgetExceeded(RuntimeError):
    """A stable, machine-readable asset resource boundary was exceeded."""

    def __init__(
        self,
        reason_code: str,
        *,
        diagnostic: Mapping[str, Any] | None = None,
        fatal: bool = False,
    ) -> None:
        self.reason_code = str(reason_code)
        self.diagnostic = {
            "reason": self.reason_code,
            **dict(diagnostic or {}),
        }
        self.fatal = bool(fatal)
        super().__init__(self.reason_code)


@dataclass
class _ReservationState:
    allocated_bytes: int = 0
    actual_bytes: int = 0
    counts_file: bool = True
    staging_paths: set[Path] = field(default_factory=set)


class AssetReservation:
    """One candidate's rollback-safe claim on the shared article budget."""

    def __init__(self, budget: AssetBudget, token: int) -> None:
        self._budget = budget
        self._token = token
        self._finished = False

    def declare_content_length(self, declared_bytes: int | None) -> None:
        if declared_bytes is None:
            return
        self._budget._declare(self._token, int(declared_bytes))

    def consume(self, chunk_bytes: int) -> None:
        self._budget._consume(self._token, int(chunk_bytes))

    def register_staging(self, path: Path) -> None:
        self._budget._register_staging(self._token, Path(path))

    def unregister_staging(self, path: Path) -> None:
        self._budget._unregister_staging(self._token, Path(path))

    def validate_pixels(self, width: int, height: int) -> None:
        self._budget._validate_pixels(int(width), int(height))

    def promote_file(self) -> None:
        """Turn a transient staging reservation into one retained asset."""

        self._budget._promote_file(self._token)

    def reconcile_actual(self) -> None:
        """Release an over-reserved Content-Length claim after a complete stream."""

        self._budget._reconcile_actual(self._token)

    @contextlib.contextmanager
    def commit_critical_section(self) -> Iterator[None]:
        with self._budget._commit_critical_section(self._token):
            yield

    @property
    def actual_bytes(self) -> int:
        return self._budget._reservation_actual_bytes(self._token)

    def commit(self) -> None:
        if self._finished:
            return
        self._budget._commit(self._token)
        self._finished = True

    def rollback(self) -> None:
        if self._finished:
            return
        self._budget._rollback(self._token)
        self._finished = True

    def __enter__(self) -> AssetReservation:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if not self._finished:
            self.rollback()


class AssetBudget:
    """Per-article file/byte/pixel/concurrency boundary shared by all routes."""

    def __init__(
        self,
        *,
        max_files: int | None = DEFAULT_ASSET_MAX_FILES,
        max_bytes_per_asset: int = DEFAULT_ASSET_MAX_BYTES_PER_ASSET,
        max_bytes_total: int = DEFAULT_ASSET_MAX_BYTES_TOTAL,
        max_pixels: int = DEFAULT_ASSET_MAX_PIXELS,
        max_concurrency: int = DEFAULT_ASSET_MAX_CONCURRENCY,
        route_concurrency_cap: int | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        self.max_files = None if max_files is None else max(0, int(max_files))
        self.max_bytes_per_asset = max(0, int(max_bytes_per_asset))
        self.max_bytes_total = max(0, int(max_bytes_total))
        self.max_pixels = max(0, int(max_pixels))
        requested_concurrency = max(1, int(max_concurrency))
        self.max_concurrency = min(
            requested_concurrency,
            (
                max(1, int(route_concurrency_cap))
                if route_concurrency_cap is not None
                else requested_concurrency
            ),
        )
        self.route_concurrency_cap = route_concurrency_cap
        self._cancel_check = cancel_check
        self._lock = threading.RLock()
        self._worker_slots = threading.BoundedSemaphore(self.max_concurrency)
        self._route_worker_slots: dict[int, threading.BoundedSemaphore] = {}
        self._stop_event = threading.Event()
        self._stop_diagnostic: dict[str, Any] = {}
        self._next_token = 0
        self._reservations: dict[int, _ReservationState] = {}
        self._retained_files = 0
        self._retained_bytes = 0
        self._admitted_work: dict[str, int] = {}
        self._admitted_file_count = 0

    @property
    def cancelled(self) -> bool:
        return self._stop_event.is_set() or bool(
            self._cancel_check is not None and self._cancel_check()
        )

    @property
    def internally_cancelled(self) -> bool:
        """Whether this budget itself recorded a terminal resource stop.

        This deliberately excludes the RuntimeContext cancellation callback.
        Coordinators may coalesce duplicate worker exceptions only for a
        resource failure already linearized by :meth:`cancel`; an external
        cancellation must keep propagating to the caller.
        """

        return self._stop_event.is_set()

    @property
    def diagnostic(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._stop_diagnostic)

    def snapshot(self) -> dict[str, int | bool | str | None]:
        with self._lock:
            return {
                "max_files": self.max_files,
                "max_bytes_per_asset": self.max_bytes_per_asset,
                "max_bytes_total": self.max_bytes_total,
                "max_pixels": self.max_pixels,
                "max_concurrency": self.max_concurrency,
                "retained_files": self._retained_files,
                "retained_bytes": self._retained_bytes,
                "reserved_files": len(self._reservations),
                "reserved_bytes": sum(
                    state.allocated_bytes for state in self._reservations.values()
                ),
                "cancelled": self.cancelled,
                "reason": str(self._stop_diagnostic.get("reason") or ""),
            }

    def effective_concurrency(
        self,
        configured_concurrency: int | None,
        *,
        route_concurrency_cap: int | None = None,
    ) -> int:
        configured = (
            self.max_concurrency
            if configured_concurrency is None
            else max(1, int(configured_concurrency))
        )
        caps = [DEFAULT_ASSET_MAX_CONCURRENCY, self.max_concurrency, configured]
        if route_concurrency_cap is not None:
            caps.append(max(1, int(route_concurrency_cap)))
        return min(caps)

    def admit_work(self, keys: Sequence[str]) -> list[bool]:
        """Bound scheduled logical files while allowing retries of the same key."""

        admitted: list[bool] = []
        occurrences: dict[str, int] = {}
        with self._lock:
            for raw_key in keys:
                key = str(raw_key)
                occurrence = occurrences.get(key, 0) + 1
                occurrences[key] = occurrence
                if occurrence <= self._admitted_work.get(key, 0):
                    admitted.append(True)
                    continue
                if (
                    self.max_files is not None
                    and self._admitted_file_count >= self.max_files
                ):
                    admitted.append(False)
                    continue
                self._admitted_work[key] = occurrence
                self._admitted_file_count += 1
                admitted.append(True)
        return admitted

    @contextlib.contextmanager
    def worker_slot(
        self, *, route_concurrency_cap: int | None = None
    ) -> Iterator[None]:
        route_slot: threading.BoundedSemaphore | None = None
        if route_concurrency_cap is not None:
            cap = max(1, min(self.max_concurrency, int(route_concurrency_cap)))
            with self._lock:
                route_slot = self._route_worker_slots.setdefault(
                    cap, threading.BoundedSemaphore(cap)
                )
        while not self._worker_slots.acquire(timeout=0.05):
            self.raise_if_cancelled()
        route_slot_acquired = False
        try:
            if route_slot is not None:
                while not route_slot.acquire(timeout=0.05):
                    self.raise_if_cancelled()
                route_slot_acquired = True
            self.raise_if_cancelled()
            yield
        finally:
            if route_slot is not None and route_slot_acquired:
                route_slot.release()
            self._worker_slots.release()

    def reserve(
        self,
        *,
        declared_bytes: int | None = None,
        transient: bool = False,
    ) -> AssetReservation:
        self.raise_if_cancelled()
        diagnostic: dict[str, Any] | None = None
        with self._lock:
            reserved_files = sum(
                1 for state in self._reservations.values() if state.counts_file
            )
            if (
                not transient
                and self.max_files is not None
                and self._retained_files + reserved_files >= self.max_files
            ):
                diagnostic = {
                    "max_files": self.max_files,
                    "retained_files": self._retained_files,
                }
            else:
                self._next_token += 1
                token = self._next_token
                self._reservations[token] = _ReservationState(counts_file=not transient)
        if diagnostic is not None:
            self.cancel(ASSET_FILE_LIMIT_EXCEEDED, diagnostic=diagnostic)
            raise AssetBudgetExceeded(
                ASSET_FILE_LIMIT_EXCEEDED,
                diagnostic=diagnostic,
                fatal=True,
            )
        reservation = AssetReservation(self, token)
        try:
            reservation.declare_content_length(declared_bytes)
        except BaseException:
            reservation.rollback()
            raise
        return reservation

    def reserve_transient(
        self, *, declared_bytes: int | None = None
    ) -> AssetReservation:
        """Reserve temporary decoded/staging bytes without claiming an output file."""

        return self.reserve(declared_bytes=declared_bytes, transient=True)

    def raise_if_cancelled(self) -> None:
        if not self.cancelled:
            return
        diagnostic = self.diagnostic or {"reason": ASSET_CANCELLED}
        raise AssetBudgetExceeded(
            str(diagnostic.get("reason") or ASSET_CANCELLED),
            diagnostic=diagnostic,
            fatal=True,
        )

    def cancel(
        self,
        reason_code: str = ASSET_CANCELLED,
        *,
        diagnostic: Mapping[str, Any] | None = None,
    ) -> None:
        paths: set[Path] = set()
        with self._lock:
            if not self._stop_event.is_set():
                self._stop_diagnostic = {
                    "reason": reason_code,
                    **dict(diagnostic or {}),
                }
                self._stop_event.set()
            for state in self._reservations.values():
                paths.update(state.staging_paths)
        for path in paths:
            with contextlib.suppress(OSError):
                path.unlink(missing_ok=True)

    def rollback_active(self) -> None:
        """Release every remaining reservation after workers have stopped."""

        with self._lock:
            states = tuple(self._reservations.values())
            self._reservations.clear()
        for state in states:
            for path in state.staging_paths:
                with contextlib.suppress(OSError):
                    path.unlink(missing_ok=True)

    def _state(self, token: int) -> _ReservationState:
        state = self._reservations.get(token)
        if state is None:
            raise RuntimeError("Asset budget reservation is no longer active.")
        return state

    def _total_allocated_unlocked(self) -> int:
        return self._retained_bytes + sum(
            state.allocated_bytes for state in self._reservations.values()
        )

    def _declare(self, token: int, declared_bytes: int) -> None:
        if declared_bytes < 0:
            return
        if declared_bytes > self.max_bytes_per_asset:
            diagnostic = {
                "declared_bytes": declared_bytes,
                "max_bytes_per_asset": self.max_bytes_per_asset,
                "boundary": "content_length",
            }
            self.cancel(ASSET_BYTES_PER_ASSET_EXCEEDED, diagnostic=diagnostic)
            raise AssetBudgetExceeded(
                ASSET_BYTES_PER_ASSET_EXCEEDED,
                diagnostic=diagnostic,
                fatal=True,
            )
        with self._lock:
            state = self._state(token)
            delta = max(0, declared_bytes - state.allocated_bytes)
            if self._total_allocated_unlocked() + delta > self.max_bytes_total:
                diagnostic = {
                    "declared_bytes": declared_bytes,
                    "max_bytes_total": self.max_bytes_total,
                    "retained_bytes": self._retained_bytes,
                    "boundary": "content_length",
                }
            else:
                state.allocated_bytes += delta
                return
        self.cancel(ASSET_BYTES_TOTAL_EXCEEDED, diagnostic=diagnostic)
        raise AssetBudgetExceeded(
            ASSET_BYTES_TOTAL_EXCEEDED,
            diagnostic=diagnostic,
            fatal=True,
        )

    def _consume(self, token: int, chunk_bytes: int) -> None:
        if chunk_bytes <= 0:
            return
        self.raise_if_cancelled()
        with self._lock:
            state = self._state(token)
            new_actual = state.actual_bytes + chunk_bytes
            if new_actual > self.max_bytes_per_asset:
                diagnostic = {
                    "actual_bytes": new_actual,
                    "max_bytes_per_asset": self.max_bytes_per_asset,
                    "boundary": "stream",
                }
                self.cancel(ASSET_BYTES_PER_ASSET_EXCEEDED, diagnostic=diagnostic)
                raise AssetBudgetExceeded(
                    ASSET_BYTES_PER_ASSET_EXCEEDED,
                    diagnostic=diagnostic,
                    fatal=True,
                )
            delta = max(0, new_actual - state.allocated_bytes)
            if self._total_allocated_unlocked() + delta > self.max_bytes_total:
                diagnostic = {
                    "actual_bytes": new_actual,
                    "max_bytes_total": self.max_bytes_total,
                    "retained_bytes": self._retained_bytes,
                    "boundary": "stream",
                }
            else:
                state.actual_bytes = new_actual
                state.allocated_bytes += delta
                return
        self.cancel(ASSET_BYTES_TOTAL_EXCEEDED, diagnostic=diagnostic)
        raise AssetBudgetExceeded(
            ASSET_BYTES_TOTAL_EXCEEDED,
            diagnostic=diagnostic,
            fatal=True,
        )

    def _validate_pixels(self, width: int, height: int) -> None:
        pixels = max(0, width) * max(0, height)
        if pixels > self.max_pixels:
            diagnostic = {
                "width": width,
                "height": height,
                "pixels": pixels,
                "max_pixels": self.max_pixels,
            }
            self.cancel(ASSET_PIXEL_LIMIT_EXCEEDED, diagnostic=diagnostic)
            raise AssetBudgetExceeded(
                ASSET_PIXEL_LIMIT_EXCEEDED,
                diagnostic=diagnostic,
                fatal=True,
            )

    def _promote_file(self, token: int) -> None:
        diagnostic: dict[str, Any] | None = None
        with self._lock:
            state = self._state(token)
            if state.counts_file:
                return
            reserved_files = sum(
                1 for item in self._reservations.values() if item.counts_file
            )
            if (
                self.max_files is not None
                and self._retained_files + reserved_files >= self.max_files
            ):
                diagnostic = {
                    "max_files": self.max_files,
                    "retained_files": self._retained_files,
                }
            else:
                state.counts_file = True
                return
        self.cancel(ASSET_FILE_LIMIT_EXCEEDED, diagnostic=diagnostic)
        raise AssetBudgetExceeded(
            ASSET_FILE_LIMIT_EXCEEDED,
            diagnostic=diagnostic,
            fatal=True,
        )

    def _register_staging(self, token: int, path: Path) -> None:
        with self._lock:
            self._state(token).staging_paths.add(path)

    def _unregister_staging(self, token: int, path: Path) -> None:
        with self._lock:
            state = self._reservations.get(token)
            if state is not None:
                state.staging_paths.discard(path)

    def _reservation_actual_bytes(self, token: int) -> int:
        with self._lock:
            return self._state(token).actual_bytes

    def _reconcile_actual(self, token: int) -> None:
        with self._lock:
            state = self._state(token)
            state.allocated_bytes = state.actual_bytes

    def _commit(self, token: int) -> None:
        with self._lock:
            state = self._state(token)
            if not state.counts_file:
                raise RuntimeError("Transient asset reservation cannot be committed.")
            self._retained_files += 1
            self._retained_bytes += state.actual_bytes
            self._reservations.pop(token, None)

    @contextlib.contextmanager
    def _commit_critical_section(self, token: int) -> Iterator[None]:
        with self._lock:
            self.raise_if_cancelled()
            self._state(token)
            yield

    def _rollback(self, token: int) -> None:
        with self._lock:
            state = self._reservations.pop(token, None)
        if state is None:
            return
        for path in state.staging_paths:
            with contextlib.suppress(OSError):
                path.unlink(missing_ok=True)


_ACTIVE_ASSET_BUDGET: ContextVar[AssetBudget | None] = ContextVar(
    "paper_fetch_asset_budget",
    default=None,
)


def current_asset_budget() -> AssetBudget | None:
    return _ACTIVE_ASSET_BUDGET.get()


@contextlib.contextmanager
def use_asset_budget(budget: AssetBudget | None) -> Iterator[AssetBudget | None]:
    token: Token[AssetBudget | None] = _ACTIVE_ASSET_BUDGET.set(budget)
    try:
        yield budget
    finally:
        _ACTIVE_ASSET_BUDGET.reset(token)


__all__ = [
    "DEFAULT_ASSET_MAX_BYTES_PER_ASSET",
    "DEFAULT_ASSET_MAX_BYTES_TOTAL",
    "DEFAULT_ASSET_MAX_CONCURRENCY",
    "DEFAULT_ASSET_MAX_FILES",
    "DEFAULT_ASSET_MAX_PIXELS",
    "AssetBudget",
    "AssetBudgetExceeded",
    "AssetReservation",
    "current_asset_budget",
    "use_asset_budget",
]
