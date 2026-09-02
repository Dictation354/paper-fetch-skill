"""Shared asset download state machine primitives."""

from __future__ import annotations

from concurrent.futures import as_completed, CancelledError, ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass, replace
import threading
import time
from typing import Any, TypeVar
import urllib.parse
from collections.abc import Callable, Mapping, Sequence

from ....asset_budget import AssetBudget, AssetBudgetExceeded, AssetReservation
from ....config import DEFAULT_ASSET_DOWNLOAD_CONCURRENCY
from ....reason_codes import ASSET_CANCELLED

AssetWorkItem = TypeVar("AssetWorkItem")
_ASSET_TIMING_INTERNAL_KEY = "_paper_fetch_asset_timing_seconds"
_ASSET_STARTED_INTERNAL_KEY = "_paper_fetch_asset_started_monotonic"
_ASSET_TIMING_PHASES = (
    ("queue", "queue_ms"),
    ("candidate_resolution", "candidate_resolution_ms"),
    ("dns_policy_validation", "dns_policy_validation_ms"),
    ("connect_to_headers", "connect_to_headers_ttfb_ms"),
    ("body_stream", "body_stream_ms"),
    ("browser_recovery", "browser_recovery_ms"),
    ("retry_wait", "retry_wait_ms"),
    ("conversion", "conversion_ms"),
    ("save", "save_ms"),
)


@dataclass(frozen=True)
class AssetHostRouteDecision:
    """One per-host route decision for an article-local asset fetch."""

    host: str
    route: str
    probe: bool = False


class AssetHostRecoveryCircuit:
    """Coordinate one direct probe and browser-route recovery per asset host.

    The instance is deliberately scoped to one runtime/fetch session.  The
    first caller for a host owns the direct probe while concurrent callers
    wait.  Once browser recovery succeeds, later assets from the same host
    skip direct HTTP and use that already-verified path.
    """

    def __init__(self) -> None:
        self._condition = threading.Condition(threading.RLock())
        self._routes: dict[str, str] = {}

    @staticmethod
    def host_for_url(url: str) -> str:
        parsed = urllib.parse.urlsplit(str(url or ""))
        return str(parsed.hostname or "").strip().lower().rstrip(".")

    def begin(self, url: str) -> AssetHostRouteDecision:
        host = self.host_for_url(url)
        if not host:
            return AssetHostRouteDecision(host="", route="direct")
        with self._condition:
            while self._routes.get(host) == "probing":
                self._condition.wait()
            route = self._routes.get(host)
            if route in {"direct", "browser"}:
                return AssetHostRouteDecision(host=host, route=route)
            self._routes[host] = "probing"
            return AssetHostRouteDecision(host=host, route="direct", probe=True)

    def observe(
        self,
        decision: AssetHostRouteDecision,
        *,
        browser_recovery_succeeded: bool,
    ) -> None:
        if not decision.host:
            return
        with self._condition:
            current = self._routes.get(decision.host)
            if browser_recovery_succeeded:
                self._routes[decision.host] = "browser"
            elif decision.probe and current == "probing":
                self._routes[decision.host] = "direct"
            self._condition.notify_all()

    def abandon(self, decision: AssetHostRouteDecision) -> None:
        """Release probe waiters when resolution exits unexpectedly."""

        if not decision.host or not decision.probe:
            return
        with self._condition:
            if self._routes.get(decision.host) == "probing":
                self._routes[decision.host] = "direct"
            self._condition.notify_all()

    def route_for_url(self, url: str) -> str | None:
        host = self.host_for_url(url)
        if not host:
            return None
        with self._condition:
            route = self._routes.get(host)
            return route if route in {"direct", "browser"} else None


def _timed_mapping(
    payload: Mapping[str, Any],
    *,
    queued_at: float,
    queue_seconds: float,
) -> dict[str, Any]:
    timed = dict(payload)
    raw = payload.get(_ASSET_TIMING_INTERNAL_KEY)
    timings = dict(raw) if isinstance(raw, Mapping) else {}
    timings["queue"] = max(0.0, float(timings.get("queue", 0.0))) + max(
        0.0, queue_seconds
    )
    timed[_ASSET_TIMING_INTERNAL_KEY] = timings
    timed[_ASSET_STARTED_INTERNAL_KEY] = queued_at
    return timed


def _timed_resolution(
    resolved: AssetDownloadResolution | None,
    *,
    queued_at: float,
    queue_seconds: float,
) -> AssetDownloadResolution | None:
    if resolved is None:
        return None
    if isinstance(resolved.response, Mapping):
        return replace(
            resolved,
            response=_timed_mapping(
                resolved.response,
                queued_at=queued_at,
                queue_seconds=queue_seconds,
            ),
        )
    if resolved.failure is not None:
        return replace(
            resolved,
            failure=AssetDownloadFailure(
                _timed_mapping(
                    resolved.failure.diagnostic,
                    queued_at=queued_at,
                    queue_seconds=queue_seconds,
                )
            ),
        )
    return resolved


def _finalize_asset_timing(
    payload: Mapping[str, Any],
    *,
    status: str,
    save_seconds: float = 0.0,
) -> dict[str, Any]:
    finalized = dict(payload)
    raw = finalized.pop(_ASSET_TIMING_INTERNAL_KEY, None)
    started_at = finalized.pop(_ASSET_STARTED_INTERNAL_KEY, None)
    timings = dict(raw) if isinstance(raw, Mapping) else {}
    timings["save"] = max(0.0, float(timings.get("save", 0.0))) + max(0.0, save_seconds)
    total_seconds = (
        max(0.0, time.monotonic() - float(started_at))
        if isinstance(started_at, int | float)
        else sum(max(0.0, float(value or 0.0)) for value in timings.values())
    )
    finalized["asset_timing"] = {
        public_name: round(max(0.0, float(timings.get(phase, 0.0))) * 1000, 3)
        for phase, public_name in _ASSET_TIMING_PHASES
    }
    finalized["asset_timing"].update(
        {
            "total_ms": round(total_seconds * 1000, 3),
            "status": status,
        }
    )
    return finalized


@dataclass(frozen=True)
class AssetDownloadCandidate:
    url: str


@dataclass(frozen=True)
class AssetDownloadFailure:
    diagnostic: dict[str, Any]


@dataclass(frozen=True)
class AssetDownloadAttempt:
    candidate: AssetDownloadCandidate
    response: Mapping[str, Any] | None = None
    source_url: str = ""
    failure: AssetDownloadFailure | None = None
    download_tier_override: str = ""
    reservation: AssetReservation | None = None


@dataclass(frozen=True)
class AssetDownloadResolution:
    asset: dict[str, Any]
    response: Mapping[str, Any] | None = None
    source_url: str = ""
    failure: AssetDownloadFailure | None = None
    preview_url: str = ""
    full_size_url: str = ""
    download_tier_override: str = ""
    provenance: tuple[str, ...] = ()
    reservation: AssetReservation | None = None


def asset_download_worker_count(total: int, configured_concurrency: int | None) -> int:
    if total <= 0:
        return 0
    try:
        concurrency = int(configured_concurrency or DEFAULT_ASSET_DOWNLOAD_CONCURRENCY)
    except (TypeError, ValueError):
        concurrency = DEFAULT_ASSET_DOWNLOAD_CONCURRENCY
    return min(max(1, concurrency), total)


def asset_failure(diagnostic: Mapping[str, Any] | None) -> AssetDownloadFailure | None:
    if not diagnostic:
        return None
    return AssetDownloadFailure(dict(diagnostic))


def resolution_from_attempt(
    *,
    asset: Mapping[str, Any],
    attempt: AssetDownloadAttempt | None,
    preview_url: str = "",
    full_size_url: str = "",
    provenance: Sequence[str] = (),
) -> AssetDownloadResolution:
    if attempt is None:
        return AssetDownloadResolution(
            asset=dict(asset),
            preview_url=preview_url,
            full_size_url=full_size_url,
            provenance=tuple(dict.fromkeys(provenance)),
        )
    response_reservation = (
        attempt.response.get("_paper_fetch_asset_reservation")
        if isinstance(attempt.response, Mapping)
        else None
    )
    return AssetDownloadResolution(
        asset=dict(asset),
        response=attempt.response,
        source_url=attempt.source_url or attempt.candidate.url,
        failure=attempt.failure,
        preview_url=preview_url,
        full_size_url=full_size_url,
        download_tier_override=attempt.download_tier_override,
        provenance=tuple(dict.fromkeys(provenance)),
        reservation=(
            attempt.reservation
            if attempt.reservation is not None
            else response_reservation
            if isinstance(response_reservation, AssetReservation)
            else None
        ),
    )


@dataclass
class _AssetCollectionState:
    resolver: Callable[[Any], AssetDownloadResolution | None]
    saver: Callable[
        [AssetDownloadResolution], dict[str, Any] | AssetDownloadFailure | None
    ]
    asset_budget: AssetBudget
    route_concurrency_cap: int | None
    outcomes: list[tuple[str, dict[str, Any]] | None]
    queued_at_by_id: dict[int, float]

    def resolve(self, item: Any) -> AssetDownloadResolution | None:
        queued_at = self.queued_at_by_id.get(id(item), time.monotonic())
        with self.asset_budget.worker_slot(
            route_concurrency_cap=self.route_concurrency_cap
        ):
            resolver_started_at = time.monotonic()
            resolved = self.resolver(item)
            return _timed_resolution(
                resolved,
                queued_at=queued_at,
                queue_seconds=resolver_started_at - queued_at,
            )

    def consume(self, index: int, resolved: AssetDownloadResolution | None) -> None:
        if resolved is None:
            return
        if resolved.response is None:
            if resolved.reservation is not None:
                resolved.reservation.rollback()
            if resolved.failure is not None:
                self.outcomes[index] = (
                    "failure",
                    _finalize_asset_timing(
                        resolved.failure.diagnostic,
                        status="failed",
                    ),
                )
            return
        save_started_at = time.monotonic()
        try:
            saved = self.saver(resolved)
        except BaseException:
            if resolved.reservation is not None:
                resolved.reservation.rollback()
            raise
        if isinstance(saved, AssetDownloadFailure):
            if resolved.reservation is not None:
                resolved.reservation.rollback()
            timed_failure = dict(saved.diagnostic)
            if isinstance(resolved.response, Mapping):
                for key in (_ASSET_TIMING_INTERNAL_KEY, _ASSET_STARTED_INTERNAL_KEY):
                    if key in resolved.response:
                        timed_failure[key] = resolved.response[key]
            self.outcomes[index] = (
                "failure",
                _finalize_asset_timing(
                    timed_failure,
                    status="failed",
                    save_seconds=time.monotonic() - save_started_at,
                ),
            )
        elif saved is not None:
            timed_asset = dict(saved)
            if isinstance(resolved.response, Mapping):
                for key in (_ASSET_TIMING_INTERNAL_KEY, _ASSET_STARTED_INTERNAL_KEY):
                    if key in resolved.response:
                        timed_asset[key] = resolved.response[key]
            self.outcomes[index] = (
                "asset",
                _finalize_asset_timing(
                    timed_asset,
                    status="saved",
                    save_seconds=time.monotonic() - save_started_at,
                ),
            )
        elif resolved.reservation is not None:
            resolved.reservation.rollback()


def _resolve_asset_collection_serially(
    state: _AssetCollectionState,
    work_items: Sequence[Any],
) -> None:
    try:
        for index, item in enumerate(work_items):
            if state.asset_budget.cancelled:
                if state.asset_budget.internally_cancelled:
                    break
                state.asset_budget.raise_if_cancelled()
            state.consume(index, state.resolve(item))
    except BaseException:
        state.asset_budget.cancel(
            ASSET_CANCELLED,
            diagnostic={"boundary": "asset_worker"},
        )
        state.asset_budget.rollback_active()
        raise


def _resolve_asset_collection_in_parallel(
    state: _AssetCollectionState,
    work_items: Sequence[Any],
    *,
    max_workers: int,
) -> None:
    executor = ThreadPoolExecutor(max_workers=max_workers)
    futures = {
        executor.submit(copy_context().run, state.resolve, item): index
        for index, item in enumerate(work_items)
    }
    try:
        for future in as_completed(futures):
            index = futures[future]
            try:
                resolved = future.result()
            except CancelledError:
                continue
            except AssetBudgetExceeded as exc:
                if exc.fatal and state.asset_budget.internally_cancelled:
                    continue
                raise
            state.consume(index, resolved)
            if not state.asset_budget.cancelled:
                continue
            if not state.asset_budget.internally_cancelled:
                state.asset_budget.raise_if_cancelled()
            for pending in futures:
                if not pending.done():
                    pending.cancel()
            break
    except BaseException:
        state.asset_budget.cancel(
            ASSET_CANCELLED,
            diagnostic={"boundary": "asset_worker"},
        )
        for pending in futures:
            if not pending.done():
                pending.cancel()
        raise
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
        if state.asset_budget.cancelled:
            state.asset_budget.rollback_active()


def resolve_and_collect_downloads_as_completed(
    work_items: list[AssetWorkItem],
    *,
    resolver: Callable[[AssetWorkItem], AssetDownloadResolution | None],
    saver: Callable[
        [AssetDownloadResolution], dict[str, Any] | AssetDownloadFailure | None
    ],
    asset_download_concurrency: int | None,
    asset_budget: AssetBudget,
    force_worker_thread: bool = False,
    route_concurrency_cap: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Persist each completed asset immediately, then restore input order."""

    if not work_items:
        return {"assets": [], "asset_failures": []}
    configured_workers = asset_download_worker_count(
        len(work_items), asset_download_concurrency
    )
    max_workers = asset_budget.effective_concurrency(
        configured_workers,
        route_concurrency_cap=route_concurrency_cap,
    )
    outcomes: list[tuple[str, dict[str, Any]] | None] = [None] * len(work_items)
    queued_at = time.monotonic()
    state = _AssetCollectionState(
        resolver=resolver,
        saver=saver,
        asset_budget=asset_budget,
        route_concurrency_cap=route_concurrency_cap,
        outcomes=outcomes,
        queued_at_by_id={id(item): queued_at for item in work_items},
    )

    if max_workers <= 1 and not force_worker_thread:
        _resolve_asset_collection_serially(state, work_items)
    else:
        _resolve_asset_collection_in_parallel(
            state,
            work_items,
            max_workers=max_workers,
        )

    return {
        "assets": [
            payload
            for outcome in outcomes
            if outcome is not None and outcome[0] == "asset"
            for payload in [outcome[1]]
        ],
        "asset_failures": [
            payload
            for outcome in outcomes
            if outcome is not None and outcome[0] == "failure"
            for payload in [outcome[1]]
        ],
    }


__all__ = [
    "AssetDownloadAttempt",
    "AssetDownloadCandidate",
    "AssetDownloadFailure",
    "AssetDownloadResolution",
    "AssetHostRecoveryCircuit",
    "AssetHostRouteDecision",
    "asset_download_worker_count",
    "asset_failure",
    "resolution_from_attempt",
    "resolve_and_collect_downloads_as_completed",
]
