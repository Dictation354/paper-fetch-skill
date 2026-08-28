"""Shared incremental batch scheduling with provider-aware lanes."""

from __future__ import annotations

import asyncio
from contextvars import copy_context
from collections import Counter
from collections.abc import Awaitable, Callable, Hashable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
import contextlib
from dataclasses import dataclass
from enum import StrEnum
import inspect
import math
import threading
import time
from typing import Generic, TypeVar, cast

from ..http import RequestCancelledError
from ..reason_codes import ERROR, RATE_LIMITED

ItemT = TypeVar("ItemT")
ResultT = TypeVar("ResultT")
LaneKey = Hashable

MIN_BATCH_WORKERS = 1
MAX_BATCH_WORKERS = 8
DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 60.0


class BatchItemStatus(StrEnum):
    """Terminal status for one input item."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RATE_LIMITED = RATE_LIMITED
    CANCELLED = "cancelled"
    NOT_SCHEDULED = "not_scheduled"


@dataclass(frozen=True, slots=True)
class BatchFailure:
    """Structured failure facts supplied by an adapter or derived from an error."""

    reason_code: str
    message: str
    retry_after_seconds: float | None = None
    rate_limited: bool = False
    cancelled: bool = False
    details: object | None = None


@dataclass(frozen=True, slots=True)
class BatchItemResult(Generic[ItemT, ResultT]):
    """One terminal result; collections of these retain input order."""

    index: int
    item: ItemT
    lane_key: LaneKey
    status: BatchItemStatus
    value: ResultT | None
    failure: BatchFailure | None
    error: Exception | None
    submitted_at: float | None
    finished_at: float

    @property
    def was_submitted(self) -> bool:
        return self.submitted_at is not None


@dataclass(frozen=True, slots=True)
class BatchCompletionEvent(Generic[ItemT, ResultT]):
    """A terminal event in observation order, separate from ordered results."""

    sequence: int
    result: BatchItemResult[ItemT, ResultT]


@dataclass(frozen=True, slots=True)
class BatchProgress(Generic[ItemT, ResultT]):
    """Progress snapshot emitted after an item reaches a terminal state."""

    total: int
    terminal: int
    completed: int
    succeeded: int
    failed: int
    rate_limited: int
    cancelled: int
    not_scheduled: int
    in_flight: int
    event: BatchCompletionEvent[ItemT, ResultT]


@dataclass(frozen=True, slots=True)
class BatchLaneCooldown:
    """Rate-limit state recorded for a provider/resource lane."""

    lane_key: LaneKey
    reason_code: str
    source_index: int
    retry_after_seconds: float | None
    cooldown_seconds: float
    limited_at: float
    cooldown_until: float


@dataclass(frozen=True, slots=True)
class BatchCallbackFailure:
    """A callback failure retained without corrupting batch terminal states."""

    callback: str
    source_index: int
    message: str


@dataclass(frozen=True, slots=True)
class BatchRunResult(Generic[ItemT, ResultT]):
    """Ordered terminal results plus independently ordered completion events."""

    results: tuple[BatchItemResult[ItemT, ResultT], ...]
    completion_events: tuple[BatchCompletionEvent[ItemT, ResultT], ...]
    lane_cooldowns: Mapping[LaneKey, BatchLaneCooldown]
    callback_failures: tuple[BatchCallbackFailure, ...]
    stopped: bool
    cancelled: bool

    @property
    def aborted(self) -> bool:
        return self.stopped or self.cancelled or bool(self.lane_cooldowns)


LaneLimit = int | Mapping[LaneKey, int] | Callable[[LaneKey], int]
CompletionCallback = Callable[
    [BatchCompletionEvent[ItemT, ResultT]], Awaitable[None] | None
]
ProgressCallback = Callable[[BatchProgress[ItemT, ResultT]], Awaitable[None] | None]
FailureClassifier = Callable[[Exception], BatchFailure]
ResultClassifier = Callable[[ResultT], BatchFailure | None]
StopPredicate = Callable[[BatchItemResult[ItemT, ResultT]], bool]
CancelEscalationCallback = Callable[[], None]


def _validate_worker_limit(value: int, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")
    if not MIN_BATCH_WORKERS <= value <= MAX_BATCH_WORKERS:
        raise ValueError(
            f"{name} must be between {MIN_BATCH_WORKERS} and {MAX_BATCH_WORKERS}."
        )
    return value


def _default_failure_classifier(error: Exception) -> BatchFailure:
    cancelled = isinstance(error, RequestCancelledError)
    reason_code = str(
        ("request_cancelled" if cancelled else None)
        or getattr(error, "code", None)
        or getattr(error, "status", None)
        or getattr(error, "error_category", None)
        or ERROR
    )
    retry_after_value = getattr(error, "retry_after_seconds", None)
    retry_after_seconds = (
        float(retry_after_value)
        if isinstance(retry_after_value, (int, float))
        and not isinstance(retry_after_value, bool)
        else None
    )
    http_status = getattr(error, "status_code", None)
    rate_limited = (
        reason_code == RATE_LIMITED
        or http_status == 429
        or retry_after_seconds is not None
    )
    return BatchFailure(
        reason_code=reason_code,
        message=str(error),
        retry_after_seconds=retry_after_seconds,
        rate_limited=rate_limited,
        cancelled=cancelled,
    )


def _cancellation_isolation_due(
    *,
    escalated: bool,
    escalated_at: float | None,
    clock: Callable[[], float],
    poll_interval_seconds: float,
) -> bool:
    return bool(
        escalated
        and escalated_at is not None
        and clock() - escalated_at >= poll_interval_seconds
    )


async def _isolate_pending_workers(
    pending: dict[asyncio.Future[ResultT], tuple[int, LaneKey, float]],
    lane_in_flight: Counter[LaneKey],
    item_values: tuple[ItemT, ...],
    *,
    clock: Callable[[], float],
    record_result: Callable[
        [BatchItemResult[ItemT, ResultT]],
        Awaitable[None],
    ],
) -> None:
    isolated = list(pending.items())
    pending.clear()
    for future, (index, key, submitted_at) in isolated:
        future.cancel()
        lane_in_flight[key] -= 1
        await record_result(
            BatchItemResult(
                index=index,
                item=item_values[index],
                lane_key=key,
                status=BatchItemStatus.CANCELLED,
                value=None,
                failure=BatchFailure(
                    reason_code="request_cancelled",
                    message=(
                        "Batch worker did not converge within the cancellation "
                        "grace period and was isolated from further commits."
                    ),
                    cancelled=True,
                ),
                error=None,
                submitted_at=submitted_at,
                finished_at=clock(),
            )
        )


async def _settle_pending_after_task_cancellation(
    pending: Mapping[asyncio.Future[ResultT], object],
    *,
    grace_period_seconds: float,
    escalation_callback: CancelEscalationCallback | None,
    already_escalated: bool,
) -> bool:
    active_futures = tuple(pending)
    remaining_futures: set[asyncio.Future[ResultT]] = set(active_futures)
    if active_futures and grace_period_seconds > 0:
        _done, remaining_futures = await asyncio.wait(
            active_futures,
            timeout=grace_period_seconds,
        )
    if not remaining_futures:
        return True
    if not already_escalated and escalation_callback is not None:
        with contextlib.suppress(Exception):
            escalation_callback()
    for future in remaining_futures:
        future.cancel()
    return False


def _effective_lane_limit(
    configured: LaneLimit | None,
    key: LaneKey,
    *,
    max_workers: int,
) -> int:
    if configured is None:
        return max_workers
    if isinstance(configured, int):
        return configured
    value = configured(key) if callable(configured) else configured.get(key, max_workers)
    return _validate_worker_limit(value, name=f"lane limit for {key!r}")


def _status_for_failure(failure: BatchFailure) -> BatchItemStatus:
    if failure.cancelled:
        return BatchItemStatus.CANCELLED
    if failure.rate_limited:
        return BatchItemStatus.RATE_LIMITED
    return BatchItemStatus.FAILED


def _classify_result(
    value: ResultT,
    classifier: ResultClassifier[ResultT] | None,
) -> tuple[BatchItemStatus, BatchFailure | None]:
    if classifier is None:
        return BatchItemStatus.SUCCEEDED, None
    failure = classifier(value)
    if failure is None:
        return BatchItemStatus.SUCCEEDED, None
    return _status_for_failure(failure), failure


def _cooldown_duration(failure: BatchFailure, *, default_seconds: float) -> float:
    retry_after = failure.retry_after_seconds
    if retry_after is None or not math.isfinite(retry_after) or retry_after < 0:
        return default_seconds
    return retry_after


def _record_lane_cooldown(
    lane_cooldowns: dict[LaneKey, BatchLaneCooldown],
    result: BatchItemResult[ItemT, ResultT],
    *,
    default_seconds: float,
) -> None:
    failure = result.failure
    if failure is None or not failure.rate_limited:
        return
    duration = _cooldown_duration(failure, default_seconds=default_seconds)
    candidate = BatchLaneCooldown(
        lane_key=result.lane_key,
        reason_code=failure.reason_code,
        source_index=result.index,
        retry_after_seconds=failure.retry_after_seconds,
        cooldown_seconds=duration,
        limited_at=result.finished_at,
        cooldown_until=result.finished_at + duration,
    )
    existing = lane_cooldowns.get(result.lane_key)
    if existing is None or candidate.cooldown_until > existing.cooldown_until:
        lane_cooldowns[result.lane_key] = candidate


class BatchRunner(Generic[ItemT, ResultT]):
    """Run a bounded batch with one incremental scheduling state machine."""

    def __init__(
        self,
        worker: Callable[[ItemT], ResultT],
        *,
        max_workers: int = 1,
        lane_key: Callable[[ItemT], LaneKey] | None = None,
        lane_limits: LaneLimit | None = None,
        completion_callback: CompletionCallback[ItemT, ResultT] | None = None,
        progress_callback: ProgressCallback[ItemT, ResultT] | None = None,
        stop_predicate: StopPredicate[ItemT, ResultT] | None = None,
        cancel_event: threading.Event | None = None,
        clock: Callable[[], float] = time.monotonic,
        failure_classifier: FailureClassifier = _default_failure_classifier,
        result_classifier: ResultClassifier[ResultT] | None = None,
        default_rate_limit_cooldown_seconds: float = (
            DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS
        ),
        cancel_poll_interval_seconds: float = 0.05,
        cancel_grace_period_seconds: float = 10.0,
        cancel_escalation_callback: CancelEscalationCallback | None = None,
    ) -> None:
        self._worker = worker
        self._max_workers = _validate_worker_limit(max_workers, name="max_workers")
        self._lane_key = lane_key or (lambda _item: None)
        self._lane_limits = lane_limits
        if isinstance(lane_limits, int):
            _validate_worker_limit(lane_limits, name="lane_limits")
        self._completion_callback = completion_callback
        self._progress_callback = progress_callback
        self._stop_predicate = stop_predicate
        self._cancel_event = cancel_event or threading.Event()
        self._clock = clock
        self._failure_classifier = failure_classifier
        self._result_classifier = result_classifier
        if (
            not math.isfinite(default_rate_limit_cooldown_seconds)
            or default_rate_limit_cooldown_seconds < 0
        ):
            raise ValueError(
                "default_rate_limit_cooldown_seconds must be a finite, "
                "non-negative number."
            )
        self._default_rate_limit_cooldown_seconds = float(
            default_rate_limit_cooldown_seconds
        )
        if (
            not math.isfinite(cancel_poll_interval_seconds)
            or cancel_poll_interval_seconds <= 0
        ):
            raise ValueError(
                "cancel_poll_interval_seconds must be a finite, positive number."
            )
        self._cancel_poll_interval_seconds = float(cancel_poll_interval_seconds)
        if (
            not math.isfinite(cancel_grace_period_seconds)
            or cancel_grace_period_seconds < 0
        ):
            raise ValueError(
                "cancel_grace_period_seconds must be a finite, non-negative number."
            )
        self._cancel_grace_period_seconds = float(cancel_grace_period_seconds)
        self._cancel_escalation_callback = cancel_escalation_callback

    def run(self, items: Sequence[ItemT]) -> BatchRunResult[ItemT, ResultT]:
        """Run synchronously; callers already in an event loop should use run_async."""

        return asyncio.run(self.run_async(items))

    async def run_async(self, items: Sequence[ItemT]) -> BatchRunResult[ItemT, ResultT]:
        """Run asynchronously while workers execute in a bounded thread pool."""

        item_values = tuple(items)
        lane_keys = tuple(self._lane_key(item) for item in item_values)
        for key in lane_keys:
            hash(key)

        total = len(item_values)
        ordered_results: list[BatchItemResult[ItemT, ResultT] | None] = [None] * total
        completion_events: list[BatchCompletionEvent[ItemT, ResultT]] = []
        callback_failures: list[BatchCallbackFailure] = []
        lane_cooldowns: dict[LaneKey, BatchLaneCooldown] = {}
        status_counts: Counter[BatchItemStatus] = Counter()
        lane_in_flight: Counter[LaneKey] = Counter()
        remaining = list(range(total))
        pending: dict[asyncio.Future[ResultT], tuple[int, LaneKey, float]] = {}
        stopped_by: BatchItemResult[ItemT, ResultT] | None = None
        cancellation_observed = self._cancel_event.is_set()
        cancellation_started_at = self._clock() if cancellation_observed else None
        cancellation_escalated = False
        cancellation_escalated_at: float | None = None

        loop = asyncio.get_running_loop()
        executor = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="paper-fetch-batch",
        )
        shutdown_wait = True

        async def invoke_callback(
            callback_name: str,
            callback: Callable[[object], Awaitable[None] | None] | None,
            argument: object,
            *,
            source_index: int,
        ) -> None:
            if callback is None:
                return
            try:
                callback_result = callback(argument)
                if inspect.isawaitable(callback_result):
                    await cast(Awaitable[None], callback_result)
            except Exception as error:
                callback_failures.append(
                    BatchCallbackFailure(
                        callback=callback_name,
                        source_index=source_index,
                        message=str(error),
                    )
                )

        async def record_result(
            result: BatchItemResult[ItemT, ResultT],
        ) -> None:
            ordered_results[result.index] = result
            status_counts[result.status] += 1
            event = BatchCompletionEvent(
                sequence=len(completion_events) + 1,
                result=result,
            )
            completion_events.append(event)
            await invoke_callback(
                "completion",
                cast(
                    Callable[[object], Awaitable[None] | None] | None,
                    self._completion_callback,
                ),
                event,
                source_index=result.index,
            )
            progress = BatchProgress(
                total=total,
                terminal=len(completion_events),
                completed=sum(
                    count
                    for status, count in status_counts.items()
                    if status is not BatchItemStatus.NOT_SCHEDULED
                ),
                succeeded=status_counts[BatchItemStatus.SUCCEEDED],
                failed=status_counts[BatchItemStatus.FAILED],
                rate_limited=status_counts[BatchItemStatus.RATE_LIMITED],
                cancelled=status_counts[BatchItemStatus.CANCELLED],
                not_scheduled=status_counts[BatchItemStatus.NOT_SCHEDULED],
                in_flight=len(pending),
                event=event,
            )
            await invoke_callback(
                "progress",
                cast(
                    Callable[[object], Awaitable[None] | None] | None,
                    self._progress_callback,
                ),
                progress,
                source_index=result.index,
            )

        def cancellation_requested() -> bool:
            nonlocal cancellation_observed, cancellation_started_at
            if self._cancel_event.is_set():
                cancellation_observed = True
                if cancellation_started_at is None:
                    cancellation_started_at = self._clock()
            return cancellation_observed

        def maybe_escalate_cancellation() -> None:
            nonlocal cancellation_escalated, cancellation_escalated_at
            if (
                not cancellation_requested()
                or cancellation_escalated
                or not pending
                or cancellation_started_at is None
                or self._clock() - cancellation_started_at
                < self._cancel_grace_period_seconds
            ):
                return
            cancellation_escalated = True
            cancellation_escalated_at = self._clock()
            callback = self._cancel_escalation_callback
            if callback is None:
                return
            try:
                callback()
            except Exception as error:
                callback_failures.append(
                    BatchCallbackFailure(
                        callback="cancel_escalation",
                        source_index=-1,
                        message=str(error),
                    )
                )

        def find_eligible_position() -> int | None:
            if cancellation_requested() or stopped_by is not None:
                return None
            for position, index in enumerate(remaining):
                key = lane_keys[index]
                if key in lane_cooldowns:
                    continue
                if lane_in_flight[key] < _effective_lane_limit(
                    self._lane_limits,
                    key,
                    max_workers=self._max_workers,
                ):
                    return position
            return None

        def fill_available_slots() -> None:
            while len(pending) < self._max_workers:
                position = find_eligible_position()
                if position is None:
                    return
                index = remaining.pop(position)
                key = lane_keys[index]
                submitted_at = self._clock()
                worker_context = copy_context()
                future = loop.run_in_executor(
                    executor,
                    worker_context.run,
                    self._worker,
                    item_values[index],
                )
                pending[future] = (index, key, submitted_at)
                lane_in_flight[key] += 1

        try:
            fill_available_slots()
            while pending:
                cancellation_requested()
                maybe_escalate_cancellation()
                done, _ = await asyncio.wait(
                    pending,
                    timeout=self._cancel_poll_interval_seconds,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not done:
                    if _cancellation_isolation_due(
                        escalated=cancellation_escalated,
                        escalated_at=cancellation_escalated_at,
                        clock=self._clock,
                        poll_interval_seconds=self._cancel_poll_interval_seconds,
                    ):
                        shutdown_wait = False
                        await _isolate_pending_workers(
                            pending,
                            lane_in_flight,
                            item_values,
                            clock=self._clock,
                            record_result=record_result,
                        )
                    continue

                for future in done:
                    index, key, submitted_at = pending.pop(future)
                    lane_in_flight[key] -= 1
                    finished_at = self._clock()
                    value: ResultT | None = None
                    failure: BatchFailure | None = None
                    error: Exception | None = None
                    try:
                        value = future.result()
                        status, failure = _classify_result(
                            value,
                            self._result_classifier,
                        )
                    except asyncio.CancelledError:
                        status = BatchItemStatus.CANCELLED
                        failure = BatchFailure(
                            reason_code="request_cancelled",
                            message="Batch worker was cancelled.",
                            cancelled=True,
                        )
                    except Exception as worker_error:
                        error = worker_error
                        failure = self._failure_classifier(worker_error)
                        status = _status_for_failure(failure)

                    result = BatchItemResult(
                        index=index,
                        item=item_values[index],
                        lane_key=key,
                        status=status,
                        value=value,
                        failure=failure,
                        error=error,
                        submitted_at=submitted_at,
                        finished_at=finished_at,
                    )
                    if status is BatchItemStatus.CANCELLED:
                        cancellation_observed = True
                        self._cancel_event.set()
                    _record_lane_cooldown(
                        lane_cooldowns,
                        result,
                        default_seconds=(
                            self._default_rate_limit_cooldown_seconds
                        ),
                    )
                    await record_result(result)

                    if self._stop_predicate is not None and stopped_by is None:
                        try:
                            should_stop = self._stop_predicate(result)
                        except Exception as predicate_error:
                            callback_failures.append(
                                BatchCallbackFailure(
                                    callback="stop_predicate",
                                    source_index=index,
                                    message=str(predicate_error),
                                )
                            )
                            should_stop = True
                        if should_stop:
                            stopped_by = result

                if not cancellation_requested() and stopped_by is None:
                    fill_available_slots()
        except asyncio.CancelledError:
            self._cancel_event.set()
            shutdown_wait = await _settle_pending_after_task_cancellation(
                pending,
                grace_period_seconds=self._cancel_grace_period_seconds,
                escalation_callback=self._cancel_escalation_callback,
                already_escalated=cancellation_escalated,
            )
            raise
        finally:
            executor.shutdown(
                wait=shutdown_wait,
                cancel_futures=not shutdown_wait,
            )

        cancellation_requested()
        for index in remaining:
            key = lane_keys[index]
            cooldown = lane_cooldowns.get(key)
            if cancellation_observed:
                failure = BatchFailure(
                    reason_code="request_cancelled",
                    message="Item was not scheduled because the batch was cancelled.",
                    cancelled=True,
                )
            elif cooldown is not None:
                failure = BatchFailure(
                    reason_code=cooldown.reason_code,
                    message=(
                        "Item was not scheduled because its provider/resource lane "
                        "was rate limited."
                    ),
                    retry_after_seconds=cooldown.retry_after_seconds,
                    rate_limited=True,
                    details=cooldown,
                )
            else:
                stopped_failure = stopped_by.failure if stopped_by is not None else None
                failure = BatchFailure(
                    reason_code=(
                        stopped_failure.reason_code
                        if stopped_failure is not None
                        else ERROR
                    ),
                    message="Item was not scheduled because the stop predicate fired.",
                    details=stopped_by,
                )
            await record_result(
                BatchItemResult(
                    index=index,
                    item=item_values[index],
                    lane_key=key,
                    status=BatchItemStatus.NOT_SCHEDULED,
                    value=None,
                    failure=failure,
                    error=None,
                    submitted_at=None,
                    finished_at=self._clock(),
                )
            )

        if any(result is None for result in ordered_results):
            raise RuntimeError("Batch runner failed to terminalize every input item.")

        return BatchRunResult(
            results=tuple(
                cast(BatchItemResult[ItemT, ResultT], result)
                for result in ordered_results
            ),
            completion_events=tuple(completion_events),
            lane_cooldowns=dict(lane_cooldowns),
            callback_failures=tuple(callback_failures),
            stopped=stopped_by is not None,
            cancelled=cancellation_observed,
        )


def run_batch(
    items: Sequence[ItemT],
    worker: Callable[[ItemT], ResultT],
    *,
    max_workers: int = 1,
    lane_key: Callable[[ItemT], LaneKey] | None = None,
    lane_limits: LaneLimit | None = None,
    completion_callback: CompletionCallback[ItemT, ResultT] | None = None,
    progress_callback: ProgressCallback[ItemT, ResultT] | None = None,
    stop_predicate: StopPredicate[ItemT, ResultT] | None = None,
    cancel_event: threading.Event | None = None,
    clock: Callable[[], float] = time.monotonic,
    failure_classifier: FailureClassifier = _default_failure_classifier,
    result_classifier: ResultClassifier[ResultT] | None = None,
    default_rate_limit_cooldown_seconds: float = (DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS),
    cancel_grace_period_seconds: float = 10.0,
    cancel_escalation_callback: CancelEscalationCallback | None = None,
) -> BatchRunResult[ItemT, ResultT]:
    """Convenience wrapper around :class:`BatchRunner.run`."""

    from ..runtime import close_shared_browser_managers, retain_shared_browser_managers

    escalation_callback = cancel_escalation_callback or close_shared_browser_managers

    with retain_shared_browser_managers():
        return BatchRunner(
            worker,
            max_workers=max_workers,
            lane_key=lane_key,
            lane_limits=lane_limits,
            completion_callback=completion_callback,
            progress_callback=progress_callback,
            stop_predicate=stop_predicate,
            cancel_event=cancel_event,
            clock=clock,
            failure_classifier=failure_classifier,
            result_classifier=result_classifier,
            default_rate_limit_cooldown_seconds=(default_rate_limit_cooldown_seconds),
            cancel_grace_period_seconds=cancel_grace_period_seconds,
            cancel_escalation_callback=escalation_callback,
        ).run(items)


async def run_batch_async(
    items: Sequence[ItemT],
    worker: Callable[[ItemT], ResultT],
    *,
    max_workers: int = 1,
    lane_key: Callable[[ItemT], LaneKey] | None = None,
    lane_limits: LaneLimit | None = None,
    completion_callback: CompletionCallback[ItemT, ResultT] | None = None,
    progress_callback: ProgressCallback[ItemT, ResultT] | None = None,
    stop_predicate: StopPredicate[ItemT, ResultT] | None = None,
    cancel_event: threading.Event | None = None,
    clock: Callable[[], float] = time.monotonic,
    failure_classifier: FailureClassifier = _default_failure_classifier,
    result_classifier: ResultClassifier[ResultT] | None = None,
    default_rate_limit_cooldown_seconds: float = (DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS),
    cancel_grace_period_seconds: float = 10.0,
    cancel_escalation_callback: CancelEscalationCallback | None = None,
) -> BatchRunResult[ItemT, ResultT]:
    """Convenience wrapper around :class:`BatchRunner.run_async`."""

    from ..runtime import close_shared_browser_managers, retain_shared_browser_managers

    escalation_callback = cancel_escalation_callback or close_shared_browser_managers

    with retain_shared_browser_managers():
        return await BatchRunner(
            worker,
            max_workers=max_workers,
            lane_key=lane_key,
            lane_limits=lane_limits,
            completion_callback=completion_callback,
            progress_callback=progress_callback,
            stop_predicate=stop_predicate,
            cancel_event=cancel_event,
            clock=clock,
            failure_classifier=failure_classifier,
            result_classifier=result_classifier,
            default_rate_limit_cooldown_seconds=(default_rate_limit_cooldown_seconds),
            cancel_grace_period_seconds=cancel_grace_period_seconds,
            cancel_escalation_callback=escalation_callback,
        ).run_async(items)


__all__ = [
    "DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS",
    "MAX_BATCH_WORKERS",
    "MIN_BATCH_WORKERS",
    "BatchCallbackFailure",
    "BatchCompletionEvent",
    "BatchFailure",
    "BatchItemResult",
    "BatchItemStatus",
    "BatchLaneCooldown",
    "BatchProgress",
    "BatchRunResult",
    "BatchRunner",
    "CancelEscalationCallback",
    "run_batch",
    "run_batch_async",
]
