"""Shared asset download state machine primitives."""

from __future__ import annotations

import threading
import time
import urllib.parse
from collections.abc import Callable, Iterator, Mapping, MutableMapping, Sequence
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from contextvars import copy_context
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, TypeVar

from ....asset_budget import AssetBudget, AssetBudgetExceeded, AssetReservation
from ....config import DEFAULT_ASSET_DOWNLOAD_CONCURRENCY
from ....reason_codes import ASSET_CANCELLED

AssetWorkItem = TypeVar("AssetWorkItem")
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


def empty_asset_timing(*, status: str = "failed") -> dict[str, Any]:
    """Build a zeroed public ``asset_timing`` payload from canonical phases."""

    timing: dict[str, Any] = {
        public_name: 0.0 for _phase, public_name in _ASSET_TIMING_PHASES
    }
    timing["total_ms"] = 0.0
    timing["status"] = status
    return timing


def _merge_phase_timings(
    base: Mapping[str, float] | None,
    extra: Mapping[str, float] | None,
) -> dict[str, float]:
    merged: dict[str, float] = {
        str(key): max(0.0, float(value))
        for key, value in (base or {}).items()
        if isinstance(value, int | float)
    }
    for key, value in (extra or {}).items():
        if isinstance(value, int | float):
            merged[str(key)] = merged.get(str(key), 0.0) + max(0.0, float(value))
    return merged


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
    wait.  When caller-thread browser recovery is required, a failed direct
    probe transitions the host to ``pending_browser`` so concurrent HTTP
    workers immediately defer to the caller-thread stage instead of issuing
    redundant failing direct requests.  Once browser recovery succeeds, later
    assets from the same host skip direct HTTP and reuse that verified path.
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
            if route in {"direct", "browser", "pending_browser"}:
                return AssetHostRouteDecision(host=host, route=route)
            self._routes[host] = "probing"
            return AssetHostRouteDecision(host=host, route="direct", probe=True)

    def defer_to_browser(self, decision: AssetHostRouteDecision) -> None:
        """Release concurrent HTTP waiters into Stage 2 caller-thread recovery."""

        if not decision.host:
            return
        with self._condition:
            if decision.probe and self._routes.get(decision.host) == "probing":
                self._routes[decision.host] = "pending_browser"
            self._condition.notify_all()

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
            elif decision.probe and current in {"probing", "pending_browser"}:
                self._routes[decision.host] = "direct"
            self._condition.notify_all()

    def abandon(self, decision: AssetHostRouteDecision) -> None:
        """Release probe waiters when resolution exits unexpectedly."""

        if not decision.host or not decision.probe:
            return
        with self._condition:
            if self._routes.get(decision.host) in {"probing", "pending_browser"}:
                self._routes[decision.host] = "direct"
            self._condition.notify_all()

    def route_for_url(self, url: str) -> str | None:
        host = self.host_for_url(url)
        if not host:
            return None
        with self._condition:
            route = self._routes.get(host)
            return route if route in {"direct", "browser"} else None


def _finalize_asset_timing(
    payload: Mapping[str, Any],
    *,
    status: str,
    timings: Mapping[str, float] | None = None,
    started_at: float | None = None,
    save_seconds: float = 0.0,
) -> dict[str, Any]:
    finalized = dict(payload)
    merged_timings = dict(timings or {})
    merged_timings["save"] = max(0.0, float(merged_timings.get("save", 0.0))) + max(
        0.0, save_seconds
    )
    total_seconds = (
        max(0.0, time.monotonic() - float(started_at))
        if isinstance(started_at, int | float)
        else sum(max(0.0, float(value or 0.0)) for value in merged_timings.values())
    )
    asset_timing: dict[str, Any] = {
        public_name: round(max(0.0, float(merged_timings.get(phase, 0.0))) * 1000, 3)
        for phase, public_name in _ASSET_TIMING_PHASES
    }
    asset_timing["total_ms"] = round(total_seconds * 1000, 3)
    asset_timing["status"] = status
    finalized["asset_timing"] = asset_timing
    return finalized


@dataclass(frozen=True)
class AssetBinaryPayload:
    """Binary ownership: either complete bytes or a staged file plus a prefix."""

    body: bytes = b""
    staging_path: Path | None = None
    downloaded_bytes: int = 0
    reservation: AssetReservation | None = None

    def rollback(self) -> None:
        if self.reservation is not None:
            self.reservation.rollback()


@dataclass
class AssetFetchResponse(MutableMapping[str, Any]):
    """Typed asset response with a mapping view for HTTP fields.

    Reservations, converted source ownership, browser backend/fetcher identity,
    recovery attempts, and route diagnostics always travel as explicit typed
    fields rather than magic dictionary keys.
    """

    payload: AssetBinaryPayload = field(default_factory=AssetBinaryPayload)
    original_payload: AssetBinaryPayload | None = None
    original_content_type: str = ""
    source_format: str = ""
    conversion_tool: str = ""
    browser_backend: str = ""
    final_fetcher: str = ""
    recovery_attempts: list[dict[str, Any]] = field(default_factory=list)
    route_diagnostics: dict[str, Any] = field(default_factory=dict)
    timing: dict[str, float] = field(default_factory=dict)
    started_at: float | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
    filename_hint: str = ""

    @classmethod
    def from_mapping(cls, response: Mapping[str, Any]) -> AssetFetchResponse:
        if isinstance(response, cls):
            return response
        fields = dict(response)
        raw_body = fields.pop("body", b"")
        body = bytes(raw_body) if isinstance(raw_body, bytes | bytearray) else b""
        staging = fields.pop("staging_path", None)
        size = int(fields.pop("downloaded_bytes", 0) or len(body))
        return cls(
            payload=AssetBinaryPayload(
                body=body,
                staging_path=Path(staging) if staging else None,
                downloaded_bytes=size,
            ),
            diagnostics=fields,
        )

    def copy(self) -> AssetFetchResponse:
        return replace(
            self,
            recovery_attempts=[dict(item) for item in self.recovery_attempts],
            route_diagnostics=dict(self.route_diagnostics),
            timing=dict(self.timing),
            diagnostics=dict(self.diagnostics),
        )

    def __getitem__(self, key: str) -> Any:
        if key == "body":
            return self.payload.body
        if key == "downloaded_bytes":
            return self.payload.downloaded_bytes
        if key == "staging_path":
            return str(self.payload.staging_path) if self.payload.staging_path else None
        return self.diagnostics[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key == "body":
            self.payload = replace(self.payload, body=bytes(value))
        elif key == "downloaded_bytes":
            self.payload = replace(self.payload, downloaded_bytes=int(value))
        elif key == "staging_path":
            self.payload = replace(
                self.payload, staging_path=Path(value) if value else None
            )
        else:
            self.diagnostics[key] = value

    def __delitem__(self, key: str) -> None:
        del self.diagnostics[key]

    def __iter__(self) -> Iterator[str]:
        return iter(("body", "downloaded_bytes", "staging_path", *self.diagnostics))

    def __len__(self) -> int:
        return 3 + len(self.diagnostics)

    def rollback(self) -> None:
        self.payload.rollback()
        if self.original_payload is not None:
            self.original_payload.rollback()


@dataclass(frozen=True)
class AssetDownloadCandidate:
    url: str


@dataclass(frozen=True)
class AssetDownloadFailure:
    diagnostic: dict[str, Any]
    timing: dict[str, float] = field(default_factory=dict)
    started_at: float | None = None
    route_diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AssetDownloadAttempt:
    candidate: AssetDownloadCandidate
    response: AssetFetchResponse | None = None
    source_url: str = ""
    failure: AssetDownloadFailure | None = None
    download_tier_override: str = ""
    reservation: AssetReservation | None = None

    def __post_init__(self) -> None:
        if self.response is not None:
            response = AssetFetchResponse.from_mapping(self.response)
            if self.reservation is not None and response.payload.reservation is None:
                response = response.copy()
                response.payload = replace(
                    response.payload, reservation=self.reservation
                )
            object.__setattr__(self, "response", response)
            object.__setattr__(self, "reservation", response.payload.reservation)


@dataclass(frozen=True)
class AssetDeferredBrowserWork:
    """Typed handoff from an HTTP worker thread to caller-thread browser recovery."""

    candidate_urls: tuple[str, ...]
    candidate_index: int
    candidate_seconds: float = 0.0
    direct_attempt: AssetDownloadAttempt | None = None
    decision: AssetHostRouteDecision | None = None
    conversion_degraded: bool = False
    full_size_access_failed: bool = False
    timing: dict[str, float] = field(default_factory=dict)
    started_at: float | None = None


@dataclass(frozen=True)
class AssetDownloadResolution:
    asset: dict[str, Any]
    response: AssetFetchResponse | None = None
    source_url: str = ""
    failure: AssetDownloadFailure | None = None
    preview_url: str = ""
    full_size_url: str = ""
    download_tier_override: str = ""
    provenance: tuple[str, ...] = ()
    reservation: AssetReservation | None = None
    deferred_browser: AssetDeferredBrowserWork | None = None

    def __post_init__(self) -> None:
        if self.response is not None:
            response = AssetFetchResponse.from_mapping(self.response)
            if self.reservation is not None and response.payload.reservation is None:
                response = response.copy()
                response.payload = replace(
                    response.payload, reservation=self.reservation
                )
            object.__setattr__(self, "response", response)
            object.__setattr__(self, "reservation", response.payload.reservation)

    def rollback(self) -> None:
        if self.response is not None:
            self.response.rollback()
        elif self.reservation is not None:
            self.reservation.rollback()


def _timed_resolution(
    resolved: AssetDownloadResolution | None,
    *,
    queued_at: float,
    queue_seconds: float,
) -> AssetDownloadResolution | None:
    if resolved is None:
        return None
    clamped_queue = max(0.0, queue_seconds)
    if resolved.deferred_browser is not None:
        deferred_timing = dict(resolved.deferred_browser.timing)
        deferred_timing["queue"] = (
            max(0.0, float(deferred_timing.get("queue", 0.0))) + clamped_queue
        )
        return replace(
            resolved,
            deferred_browser=replace(
                resolved.deferred_browser,
                timing=deferred_timing,
                started_at=queued_at,
            ),
        )
    if resolved.response is not None:
        response = resolved.response.copy()
        response.timing["queue"] = (
            max(0.0, response.timing.get("queue", 0.0)) + clamped_queue
        )
        response.started_at = queued_at
        return replace(resolved, response=response)
    if resolved.failure is not None:
        failure_timing = dict(resolved.failure.timing)
        failure_timing["queue"] = (
            max(0.0, float(failure_timing.get("queue", 0.0))) + clamped_queue
        )
        return replace(
            resolved,
            failure=replace(
                resolved.failure,
                timing=failure_timing,
                started_at=queued_at,
            ),
        )
    return resolved


def _merge_deferred_timing_into_resolution(
    resolved: AssetDownloadResolution | None,
    deferred: AssetDeferredBrowserWork,
) -> AssetDownloadResolution | None:
    if resolved is None:
        return None
    if resolved.response is not None:
        response = resolved.response.copy()
        response.timing = _merge_phase_timings(deferred.timing, response.timing)
        if deferred.started_at is not None:
            response.started_at = deferred.started_at
        return replace(resolved, response=response)
    if resolved.failure is not None:
        return replace(
            resolved,
            failure=replace(
                resolved.failure,
                timing=_merge_phase_timings(deferred.timing, resolved.failure.timing),
                started_at=(
                    deferred.started_at
                    if deferred.started_at is not None
                    else resolved.failure.started_at
                ),
            ),
        )
    return resolved


def asset_download_worker_count(total: int, configured_concurrency: int | None) -> int:
    if total <= 0:
        return 0
    try:
        concurrency = int(configured_concurrency or DEFAULT_ASSET_DOWNLOAD_CONCURRENCY)
    except (TypeError, ValueError):
        concurrency = DEFAULT_ASSET_DOWNLOAD_CONCURRENCY
    return min(max(1, concurrency), total)


def asset_failure(
    diagnostic: Mapping[str, Any] | None,
    *,
    timing: Mapping[str, float] | None = None,
    started_at: float | None = None,
    route_diagnostics: Mapping[str, Any] | None = None,
) -> AssetDownloadFailure | None:
    if not diagnostic:
        return None
    return AssetDownloadFailure(
        diagnostic=dict(diagnostic),
        timing=dict(timing) if timing else {},
        started_at=started_at,
        route_diagnostics=dict(route_diagnostics) if route_diagnostics else {},
    )


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
    return AssetDownloadResolution(
        asset=dict(asset),
        response=attempt.response,
        source_url=attempt.source_url or attempt.candidate.url,
        failure=attempt.failure,
        preview_url=preview_url,
        full_size_url=full_size_url,
        download_tier_override=attempt.download_tier_override,
        provenance=tuple(dict.fromkeys(provenance)),
        reservation=attempt.reservation,
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
    completion_callback: Callable[[int, bool], None] | None = None
    caller_thread_resolver: (
        Callable[[AssetDownloadResolution], AssetDownloadResolution | None] | None
    ) = None
    deferred_items: list[tuple[int, AssetDownloadResolution]] = field(
        default_factory=list
    )

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
        if (
            resolved is not None
            and resolved.deferred_browser is not None
            and self.caller_thread_resolver is not None
        ):
            if self.asset_budget.internally_cancelled:
                resolved.rollback()
                return
            self.deferred_items.append((index, resolved))
            return
        self._consume(index, resolved)
        outcome = self.outcomes[index]
        if outcome is not None and self.completion_callback is not None:
            self.completion_callback(index, outcome[0] == "asset")

    def _consume(self, index: int, resolved: AssetDownloadResolution | None) -> None:
        if resolved is None:
            return
        if self.asset_budget.internally_cancelled:
            resolved.rollback()
            return
        if resolved.response is None:
            resolved.rollback()
            if resolved.failure is not None:
                diagnostic = dict(resolved.failure.diagnostic)
                if resolved.failure.route_diagnostics:
                    diagnostic["asset_route"] = dict(resolved.failure.route_diagnostics)
                self.outcomes[index] = (
                    "failure",
                    _finalize_asset_timing(
                        diagnostic,
                        status="failed",
                        timings=resolved.failure.timing,
                        started_at=resolved.failure.started_at,
                    ),
                )
            return
        save_started_at = time.monotonic()
        try:
            saved = self.saver(resolved)
        except AssetBudgetExceeded as exc:
            resolved.rollback()
            if exc.fatal and self.asset_budget.internally_cancelled:
                return
            raise
        except BaseException:
            resolved.rollback()
            raise
        if isinstance(saved, AssetDownloadFailure):
            resolved.rollback()
            if self.asset_budget.internally_cancelled and saved.diagnostic.get(
                "reason"
            ) in {ASSET_CANCELLED, "empty_response_body"}:
                return
            failure_diagnostic = dict(saved.diagnostic)
            route_diagnostics = (
                saved.route_diagnostics or resolved.response.route_diagnostics
            )
            if route_diagnostics:
                failure_diagnostic["asset_route"] = dict(route_diagnostics)
            self.outcomes[index] = (
                "failure",
                _finalize_asset_timing(
                    failure_diagnostic,
                    status="failed",
                    timings=_merge_phase_timings(
                        resolved.response.timing, saved.timing
                    ),
                    started_at=resolved.response.started_at,
                    save_seconds=time.monotonic() - save_started_at,
                ),
            )
        elif saved is not None:
            self.outcomes[index] = (
                "asset",
                _finalize_asset_timing(
                    saved,
                    status="saved",
                    timings=resolved.response.timing,
                    started_at=resolved.response.started_at,
                    save_seconds=time.monotonic() - save_started_at,
                ),
            )
        else:
            resolved.rollback()


def _resolve_deferred_browser_items_on_caller_thread(
    state: _AssetCollectionState,
) -> None:
    if not state.deferred_items or state.caller_thread_resolver is None:
        return
    ordered_items = sorted(
        state.deferred_items,
        key=lambda entry: (
            0
            if (
                entry[1].deferred_browser is not None
                and entry[1].deferred_browser.decision is not None
                and entry[1].deferred_browser.decision.probe
            )
            else 1,
            entry[0],
        ),
    )
    state.deferred_items.clear()
    try:
        for index, deferred_res in ordered_items:
            deferred = deferred_res.deferred_browser
            assert deferred is not None
            if state.asset_budget.cancelled:
                if state.asset_budget.internally_cancelled:
                    break
                state.asset_budget.raise_if_cancelled()
            try:
                with state.asset_budget.worker_slot(
                    route_concurrency_cap=state.route_concurrency_cap
                ):
                    resolved = state.caller_thread_resolver(deferred_res)
            except AssetBudgetExceeded as exc:
                if exc.fatal and state.asset_budget.internally_cancelled:
                    continue
                raise
            merged = _merge_deferred_timing_into_resolution(resolved, deferred)
            state.consume(index, merged)
    except BaseException:
        state.asset_budget.cancel(
            ASSET_CANCELLED,
            diagnostic={"boundary": "asset_browser_recovery"},
        )
        state.asset_budget.rollback_active()
        raise


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
    completion_callback: Callable[[int, bool], None] | None = None,
    caller_thread_resolver: (
        Callable[[AssetDownloadResolution], AssetDownloadResolution | None] | None
    ) = None,
    force_worker_thread: bool = False,
    route_concurrency_cap: int | None = None,
    terminal_failure_factory: (
        Callable[[AssetWorkItem, Mapping[str, Any]], dict[str, Any]] | None
    ) = None,
) -> dict[str, list[dict[str, Any]]]:
    """Persist completed HTTP assets concurrently, then run caller-thread recovery."""

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
        completion_callback=completion_callback,
        caller_thread_resolver=caller_thread_resolver,
    )

    if max_workers <= 1 and not force_worker_thread:
        _resolve_asset_collection_serially(state, work_items)
    else:
        _resolve_asset_collection_in_parallel(
            state,
            work_items,
            max_workers=max_workers,
        )

    if state.deferred_items and not asset_budget.internally_cancelled:
        _resolve_deferred_browser_items_on_caller_thread(state)

    if asset_budget.internally_cancelled:
        diagnostic = asset_budget.diagnostic
        reason = str(diagnostic.get("reason") or ASSET_CANCELLED)
        for index, (item, outcome) in enumerate(zip(work_items, outcomes, strict=True)):
            if outcome is not None:
                continue
            failure = (
                terminal_failure_factory(item, diagnostic)
                if terminal_failure_factory is not None
                else {"reason": reason, **diagnostic}
            )
            queued = state.queued_at_by_id.get(id(item), queued_at)
            outcomes[index] = (
                "failure",
                _finalize_asset_timing(
                    failure,
                    status="failed",
                    timings={"queue": max(0.0, time.monotonic() - queued)},
                    started_at=queued,
                ),
            )

    return {
        "assets": [
            outcome[1]
            for outcome in outcomes
            if outcome is not None and outcome[0] == "asset"
        ],
        "asset_failures": [
            outcome[1]
            for outcome in outcomes
            if outcome is not None and outcome[0] == "failure"
        ],
    }


__all__ = [
    "AssetBinaryPayload",
    "AssetDeferredBrowserWork",
    "AssetDownloadAttempt",
    "AssetDownloadCandidate",
    "AssetDownloadFailure",
    "AssetDownloadResolution",
    "AssetFetchResponse",
    "AssetHostRecoveryCircuit",
    "AssetHostRouteDecision",
    "asset_download_worker_count",
    "asset_failure",
    "empty_asset_timing",
    "resolution_from_attempt",
    "resolve_and_collect_downloads_as_completed",
]
