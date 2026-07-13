from __future__ import annotations

from collections import Counter
import threading
import time

import pytest

from paper_fetch.http import RequestCancelledError
from paper_fetch.reason_codes import ERROR, RATE_LIMITED
from paper_fetch.workflow.batch_runner import (
    BatchCallbackFailure,
    BatchFailure,
    BatchItemStatus,
    BatchProgress,
    BatchRunner,
    run_batch,
)


def test_batch_runner_keeps_ordered_results_and_separate_completion_events() -> None:
    release_first = threading.Event()
    callback_items: list[str] = []
    progress: list[tuple[int, int, str]] = []

    def worker(item: str) -> str:
        if item == "first":
            assert release_first.wait(timeout=1)
            time.sleep(0.03)
        elif item == "second":
            release_first.set()
        return item.upper()

    def on_completion(event) -> None:
        callback_items.append(event.result.item)

    async def on_progress(snapshot: BatchProgress[str, str]) -> None:
        progress.append(
            (snapshot.terminal, snapshot.completed, snapshot.event.result.item)
        )

    result = run_batch(
        ["first", "second", "third"],
        worker,
        max_workers=2,
        completion_callback=on_completion,
        progress_callback=on_progress,
    )

    assert [item.item for item in result.results] == ["first", "second", "third"]
    assert [item.value for item in result.results] == ["FIRST", "SECOND", "THIRD"]
    completion_items = [event.result.item for event in result.completion_events]
    assert completion_items == callback_items
    assert completion_items[0] == "second"
    assert completion_items[-1] == "first"
    assert [item[:2] for item in progress] == [(1, 1), (2, 2), (3, 3)]


def test_batch_runner_enforces_global_and_per_lane_worker_limits() -> None:
    active = 0
    max_active = 0
    lane_active: Counter[str] = Counter()
    lane_max: Counter[str] = Counter()
    lock = threading.Lock()
    initial_workers = threading.Barrier(3)

    def worker(item: tuple[str, str]) -> str:
        nonlocal active, max_active
        lane, name = item
        with lock:
            active += 1
            lane_active[lane] += 1
            max_active = max(max_active, active)
            lane_max[lane] = max(lane_max[lane], lane_active[lane])
        try:
            if name in {"a-1", "b-1", "b-2"}:
                initial_workers.wait(timeout=1)
            time.sleep(0.01)
            return name
        finally:
            with lock:
                active -= 1
                lane_active[lane] -= 1

    result = run_batch(
        [("a", "a-1"), ("a", "a-2"), ("b", "b-1"), ("b", "b-2")],
        worker,
        max_workers=3,
        lane_key=lambda item: item[0],
        lane_limits={"a": 1, "b": 2},
    )

    assert all(item.status is BatchItemStatus.SUCCEEDED for item in result.results)
    assert max_active == 3
    assert lane_max == Counter({"b": 2, "a": 1})


def test_rate_limit_blocks_only_its_lane_and_records_retry_after_cooldown() -> None:
    seen: list[str] = []

    class RateLimitedError(Exception):
        code = RATE_LIMITED
        retry_after_seconds = 7

    def worker(item: tuple[str, str]) -> str:
        lane, name = item
        seen.append(name)
        if name == "limited":
            raise RateLimitedError("Slow down.")
        if name == "b-1":
            time.sleep(0.02)
        return f"{lane}:{name}"

    result = run_batch(
        [("a", "limited"), ("b", "b-1"), ("a", "must-not-start"), ("b", "b-2")],
        worker,
        max_workers=2,
        lane_key=lambda item: item[0],
        lane_limits=1,
        clock=lambda: 100.0,
    )

    assert "must-not-start" not in seen
    assert "b-2" in seen
    assert [item.status for item in result.results] == [
        BatchItemStatus.RATE_LIMITED,
        BatchItemStatus.SUCCEEDED,
        BatchItemStatus.NOT_SCHEDULED,
        BatchItemStatus.SUCCEEDED,
    ]
    cooldown = result.lane_cooldowns["a"]
    assert cooldown.reason_code == RATE_LIMITED
    assert cooldown.retry_after_seconds == 7
    assert cooldown.cooldown_seconds == 7
    assert cooldown.cooldown_until == 107
    assert result.results[2].failure is not None
    assert result.results[2].failure.rate_limited


def test_result_classifier_can_rate_limit_one_lane_without_an_exception() -> None:
    seen: list[str] = []

    def worker(item: tuple[str, str]) -> str:
        _lane, name = item
        seen.append(name)
        return name

    def classify(value: str) -> BatchFailure | None:
        if value != "limited-payload":
            return None
        return BatchFailure(
            reason_code=RATE_LIMITED,
            message="Structured result reported throttling.",
            retry_after_seconds=4,
            rate_limited=True,
        )

    result = run_batch(
        [
            ("a", "limited-payload"),
            ("b", "b-1"),
            ("a", "must-not-start"),
            ("b", "b-2"),
        ],
        worker,
        max_workers=1,
        lane_key=lambda item: item[0],
        result_classifier=classify,
        clock=lambda: 20.0,
    )

    assert seen == ["limited-payload", "b-1", "b-2"]
    assert [item.status for item in result.results] == [
        BatchItemStatus.RATE_LIMITED,
        BatchItemStatus.SUCCEEDED,
        BatchItemStatus.NOT_SCHEDULED,
        BatchItemStatus.SUCCEEDED,
    ]
    assert result.results[0].error is None
    assert result.results[0].value == "limited-payload"
    assert result.lane_cooldowns["a"].cooldown_until == 24


def test_cancel_event_terminalizes_cancelled_and_never_scheduled_items() -> None:
    cancel_event = threading.Event()
    completion_statuses: list[BatchItemStatus] = []

    def worker(item: str) -> str:
        cancel_event.set()
        raise RequestCancelledError(f"cancelled {item}")

    result = run_batch(
        ["first", "second", "third"],
        worker,
        max_workers=1,
        cancel_event=cancel_event,
        completion_callback=lambda event: completion_statuses.append(
            event.result.status
        ),
    )

    assert result.cancelled
    assert [item.status for item in result.results] == [
        BatchItemStatus.CANCELLED,
        BatchItemStatus.NOT_SCHEDULED,
        BatchItemStatus.NOT_SCHEDULED,
    ]
    assert [item.was_submitted for item in result.results] == [True, False, False]
    assert completion_statuses == [
        BatchItemStatus.CANCELLED,
        BatchItemStatus.NOT_SCHEDULED,
        BatchItemStatus.NOT_SCHEDULED,
    ]


def test_callback_can_cancel_before_the_next_incremental_submission() -> None:
    cancel_event = threading.Event()
    seen: list[str] = []

    def worker(item: str) -> str:
        seen.append(item)
        return item.upper()

    def on_completion(event) -> None:
        if event.sequence == 1:
            cancel_event.set()

    result = run_batch(
        ["first", "must-not-start", "also-must-not-start"],
        worker,
        max_workers=1,
        cancel_event=cancel_event,
        completion_callback=on_completion,
    )

    assert seen == ["first"]
    assert result.cancelled
    assert [item.status for item in result.results] == [
        BatchItemStatus.SUCCEEDED,
        BatchItemStatus.NOT_SCHEDULED,
        BatchItemStatus.NOT_SCHEDULED,
    ]
    assert all(
        item.failure is not None and item.failure.cancelled
        for item in result.results[1:]
    )
    assert [event.result.index for event in result.completion_events] == [0, 1, 2]


def test_callback_failures_are_ordered_and_do_not_corrupt_terminal_results() -> None:
    callback_order: list[tuple[str, int]] = []

    def on_completion(event) -> None:
        callback_order.append(("completion", event.result.index))
        if event.result.index == 0:
            raise RuntimeError("completion callback failed")

    async def on_progress(progress: BatchProgress[str, str]) -> None:
        index = progress.event.result.index
        callback_order.append(("progress", index))
        if index == 1:
            raise RuntimeError("progress callback failed")

    result = run_batch(
        ["first", "second"],
        str.upper,
        max_workers=1,
        completion_callback=on_completion,
        progress_callback=on_progress,
    )

    assert callback_order == [
        ("completion", 0),
        ("progress", 0),
        ("completion", 1),
        ("progress", 1),
    ]
    assert [item.status for item in result.results] == [
        BatchItemStatus.SUCCEEDED,
        BatchItemStatus.SUCCEEDED,
    ]
    assert result.callback_failures == (
        BatchCallbackFailure(
            callback="completion",
            source_index=0,
            message="completion callback failed",
        ),
        BatchCallbackFailure(
            callback="progress",
            source_index=1,
            message="progress callback failed",
        ),
    )


def test_worker_exception_and_stop_predicate_have_structured_terminal_states() -> None:
    def worker(item: str) -> str:
        if item == "broken":
            raise ValueError("worker exploded")
        return item

    result = run_batch(
        ["broken", "must-not-start"],
        worker,
        max_workers=1,
        stop_predicate=lambda item: item.status is BatchItemStatus.FAILED,
    )

    failure, not_scheduled = result.results
    assert result.stopped
    assert failure.status is BatchItemStatus.FAILED
    assert failure.failure == BatchFailure(
        reason_code=ERROR,
        message="worker exploded",
    )
    assert isinstance(failure.error, ValueError)
    assert not_scheduled.status is BatchItemStatus.NOT_SCHEDULED
    assert not_scheduled.failure is not None
    assert not_scheduled.failure.reason_code == ERROR
    assert not_scheduled.failure.details is failure


@pytest.mark.parametrize("workers", [0, 9, True])
def test_batch_runner_rejects_worker_limits_outside_public_range(
    workers: int,
) -> None:
    with pytest.raises((TypeError, ValueError), match="max_workers"):
        BatchRunner(lambda item: item, max_workers=workers)
