"""Shared asset download state machine primitives."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, TypeVar
from collections.abc import Callable, Mapping

from ....config import DEFAULT_ASSET_DOWNLOAD_CONCURRENCY

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


@dataclass(frozen=True)
class AssetDownloadResolution:
    asset: dict[str, Any]
    response: Mapping[str, Any] | None = None
    source_url: str = ""
    failure: AssetDownloadFailure | None = None
    preview_url: str = ""
    full_size_url: str = ""
    download_tier_override: str = ""


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
) -> AssetDownloadResolution:
    if attempt is None:
        return AssetDownloadResolution(
            asset=dict(asset),
            preview_url=preview_url,
            full_size_url=full_size_url,
        )
    return AssetDownloadResolution(
        asset=dict(asset),
        response=attempt.response,
        source_url=attempt.source_url or attempt.candidate.url,
        failure=attempt.failure,
        preview_url=preview_url,
        full_size_url=full_size_url,
        download_tier_override=attempt.download_tier_override,
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
        futures = [executor.submit(resolver, item) for item in work_items]
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


__all__ = [
    "AssetDownloadAttempt",
    "AssetDownloadCandidate",
    "AssetDownloadFailure",
    "AssetDownloadResolution",
    "asset_download_worker_count",
    "asset_failure",
    "collect_downloads_from_resolutions",
    "resolution_from_attempt",
    "resolve_asset_downloads_in_order",
]
