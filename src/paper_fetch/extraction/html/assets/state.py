"""Shared asset download state machine primitives."""

from __future__ import annotations

from concurrent.futures import as_completed, CancelledError, ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass
from typing import Any, TypeVar
from collections.abc import Callable, Mapping, Sequence

from ....asset_budget import AssetBudget, AssetBudgetExceeded, AssetReservation
from ....config import DEFAULT_ASSET_DOWNLOAD_CONCURRENCY
from ....reason_codes import ASSET_CANCELLED

AssetWorkItem = TypeVar("AssetWorkItem")


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


def resolve_asset_downloads_in_order(
    work_items: list[AssetWorkItem],
    *,
    resolver: Callable[[AssetWorkItem], AssetDownloadResolution | None],
    asset_download_concurrency: int | None,
    force_worker_thread: bool = False,
) -> list[AssetDownloadResolution | None]:
    if not work_items:
        return []
    max_workers = asset_download_worker_count(
        len(work_items), asset_download_concurrency
    )
    if max_workers <= 1 and not force_worker_thread:
        return [resolver(item) for item in work_items]
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(copy_context().run, resolver, item) for item in work_items
        ]
        return [future.result() for future in futures]


def collect_downloads_from_resolutions(
    resolutions: list[AssetDownloadResolution | None],
    *,
    saver: Callable[
        [AssetDownloadResolution], dict[str, Any] | AssetDownloadFailure | None
    ],
) -> dict[str, list[dict[str, Any]]]:
    downloads: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for resolved in resolutions:
        if resolved is None:
            continue
        if resolved.response is None:
            if resolved.failure is not None:
                failures.append(dict(resolved.failure.diagnostic))
            continue
        saved = saver(resolved)
        if isinstance(saved, AssetDownloadFailure):
            failures.append(dict(saved.diagnostic))
        elif saved is not None:
            downloads.append(saved)
    return {
        "assets": downloads,
        "asset_failures": failures,
    }


@dataclass
class _AssetCollectionState:
    resolver: Callable[[Any], AssetDownloadResolution | None]
    saver: Callable[
        [AssetDownloadResolution], dict[str, Any] | AssetDownloadFailure | None
    ]
    asset_budget: AssetBudget
    route_concurrency_cap: int | None
    outcomes: list[tuple[str, dict[str, Any]] | None]

    def resolve(self, item: Any) -> AssetDownloadResolution | None:
        with self.asset_budget.worker_slot(
            route_concurrency_cap=self.route_concurrency_cap
        ):
            return self.resolver(item)

    def consume(self, index: int, resolved: AssetDownloadResolution | None) -> None:
        if resolved is None:
            return
        if resolved.response is None:
            if resolved.reservation is not None:
                resolved.reservation.rollback()
            if resolved.failure is not None:
                self.outcomes[index] = (
                    "failure",
                    dict(resolved.failure.diagnostic),
                )
            return
        try:
            saved = self.saver(resolved)
        except BaseException:
            if resolved.reservation is not None:
                resolved.reservation.rollback()
            raise
        if isinstance(saved, AssetDownloadFailure):
            if resolved.reservation is not None:
                resolved.reservation.rollback()
            self.outcomes[index] = ("failure", dict(saved.diagnostic))
        elif saved is not None:
            self.outcomes[index] = ("asset", saved)
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
    state = _AssetCollectionState(
        resolver=resolver,
        saver=saver,
        asset_budget=asset_budget,
        route_concurrency_cap=route_concurrency_cap,
        outcomes=outcomes,
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
    "asset_download_worker_count",
    "asset_failure",
    "collect_downloads_from_resolutions",
    "resolution_from_attempt",
    "resolve_and_collect_downloads_as_completed",
    "resolve_asset_downloads_in_order",
]
