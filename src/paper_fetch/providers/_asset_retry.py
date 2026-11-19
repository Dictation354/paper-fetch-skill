"""Shared asset retry and merge policy helpers."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..utils import normalize_text
from ._retry_categories import (
    DEFAULT_RETRYABLE_ASSET_ERROR_CATEGORIES,
    NETWORK_RETRYABLE_REASON_TOKENS,
)


@dataclass(frozen=True)
class AssetRetryPolicy:
    name: str
    key_fn: Callable[[Mapping[str, Any]], tuple[Any, ...]]
    retryable_failure: Callable[[Mapping[str, Any]], bool]
    failure_match: Callable[[Mapping[str, Any], Mapping[str, Any]], bool] | None = None


def _has_key_value(key: tuple[Any, ...]) -> bool:
    return any(value not in (None, "") for value in key)


def _matches_failure(
    asset: Mapping[str, Any],
    failure: Mapping[str, Any],
    *,
    policy: AssetRetryPolicy,
) -> bool:
    if policy.failure_match is not None:
        return policy.failure_match(asset, failure)
    asset_key = policy.key_fn(asset)
    failure_key = policy.key_fn(failure)
    return _has_key_value(asset_key) and asset_key == failure_key


def is_retryable_asset_failure(
    failure: Mapping[str, Any],
    *,
    retryable_error_categories: Collection[
        str
    ] = DEFAULT_RETRYABLE_ASSET_ERROR_CATEGORIES,
    retryable_reason_tokens: Sequence[str] = NETWORK_RETRYABLE_REASON_TOKENS,
    non_retryable_reason_tokens: Sequence[str] = ("unsupported asset url scheme",),
) -> bool:
    if failure.get("status") is not None:
        return False
    error_category = normalize_text(str(failure.get("error_category") or "")).lower()
    if error_category:
        return error_category in retryable_error_categories
    reason = normalize_text(str(failure.get("reason") or "")).lower()
    if not reason or any(token in reason for token in non_retryable_reason_tokens):
        return False
    return any(token in reason for token in retryable_reason_tokens)


def merge_asset_retry_results(
    previous: Sequence[Mapping[str, Any]],
    retry: Sequence[Mapping[str, Any]],
    *,
    policy: AssetRetryPolicy,
) -> list[dict[str, Any]]:
    """Merge asset results with retry values taking precedence by policy key."""
    merged: list[dict[str, Any]] = []
    by_key: dict[tuple[Any, ...], int] = {}

    for item in previous:
        asset = dict(item)
        key = policy.key_fn(asset)
        existing_index = by_key.get(key) if _has_key_value(key) else None
        if existing_index is not None:
            merged[existing_index] = {**merged[existing_index], **asset}
            continue
        if _has_key_value(key):
            by_key[key] = len(merged)
        merged.append(asset)

    for item in retry:
        asset = dict(item)
        key = policy.key_fn(asset)
        existing_index = by_key.get(key) if _has_key_value(key) else None
        if existing_index is None:
            if _has_key_value(key):
                by_key[key] = len(merged)
            merged.append(asset)
            continue
        merged[existing_index] = {**merged[existing_index], **asset}
    return merged


def assets_for_network_retry(
    assets: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    *,
    policy: AssetRetryPolicy,
) -> list[dict[str, Any]]:
    """Return original assets corresponding to retryable failures."""
    retry_assets: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    retry_failures = [
        failure for failure in failures if policy.retryable_failure(failure)
    ]
    for asset in assets:
        if not any(
            _matches_failure(asset, failure, policy=policy)
            for failure in retry_failures
        ):
            continue
        key = policy.key_fn(asset)
        if _has_key_value(key):
            if key in seen:
                continue
            seen.add(key)
        retry_assets.append(dict(asset))
    return retry_assets


def merge_asset_failures(
    previous_failures: Sequence[Mapping[str, Any]],
    retry_failures: Sequence[Mapping[str, Any]],
    *,
    policy: AssetRetryPolicy,
    retried_assets: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Merge asset failures with retry failures taking precedence by policy key."""
    merged: list[dict[str, Any]] = []
    by_key: dict[tuple[Any, ...], int] = {}
    retried_asset_list = list(retried_assets or [])

    for item in previous_failures:
        failure = dict(item)
        if policy.retryable_failure(failure) and any(
            _matches_failure(asset, failure, policy=policy)
            for asset in retried_asset_list
        ):
            continue
        key = policy.key_fn(failure)
        existing_index = by_key.get(key) if _has_key_value(key) else None
        if existing_index is not None:
            merged[existing_index] = failure
            continue
        if _has_key_value(key):
            by_key[key] = len(merged)
        merged.append(failure)

    for item in retry_failures:
        failure = dict(item)
        key = policy.key_fn(failure)
        existing_index = by_key.get(key) if _has_key_value(key) else None
        if existing_index is None:
            if _has_key_value(key):
                by_key[key] = len(merged)
            merged.append(failure)
            continue
        merged[existing_index] = failure
    return merged
