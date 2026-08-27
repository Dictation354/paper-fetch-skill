"""IEEE logical asset identity, deduplication, and download reconciliation."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any
from collections.abc import Mapping

from ..extraction.html.asset_fields import DEFAULT_ASSET_URL_FIELDS
from ..utils import normalize_text
from ._asset_retry import AssetRetryPolicy, is_retryable_asset_failure
from ._ieee_url import IEEE_MEDIASTORE_PATH_PREFIX

IEEE_ASSET_KIND_PRIORITY = {"formula": 10, "figure": 20, "table": 30}
IEEE_ASSET_URL_FIELDS = (*DEFAULT_ASSET_URL_FIELDS, "download_url", "figure_page_url")
IEEE_STRONG_ASSET_IDENTITY_FIELDS = tuple(
    field
    for field in IEEE_ASSET_URL_FIELDS
    if field in {"download_url", "source_url", "full_size_url", "url"}
)
IEEE_WEAK_ASSET_IDENTITY_FIELDS = tuple(
    field
    for field in IEEE_ASSET_URL_FIELDS
    if field not in IEEE_STRONG_ASSET_IDENTITY_FIELDS
)
IEEE_DOWNLOAD_MERGE_FIELDS = (
    "path",
    "download_url",
    "source_url",
    "original_url",
    "figure_page_url",
    "content_type",
    "width",
    "height",
    "download_tier",
    "downloaded_bytes",
    "preview_accepted",
    "browser_backend",
    "final_fetcher",
    "recovery_attempts",
    "provenance",
    "asset_route",
    "asset_timing",
)
IEEE_ASSET_RETRY_KEY_FIELDS = (
    "download_url",
    "source_url",
    "full_size_url",
    "url",
    "original_url",
    "preview_url",
    "figure_page_url",
    "path",
    "link",
)

_IEEE_MEDIA_TIER_SUFFIX_PATTERN = re.compile(
    r"-(?:small|large|full|thumb|thumbnail|preview)(?=\.[^./]+$)",
    flags=re.IGNORECASE,
)
_IEEE_ASSET_LABEL_PATTERN = re.compile(
    r"\b(fig(?:ure)?|table|equation|formula)\s*\.?\s*([a-z]?\d+[a-z]?)\b",
    flags=re.IGNORECASE,
)


def _ieee_asset_kind(asset: Mapping[str, Any]) -> str:
    return normalize_text(
        str(asset.get("kind") or asset.get("asset_type") or "")
    ).lower()


def _canonical_ieee_mediastore_path(url: str) -> str:
    normalized = normalize_text(url)
    if not normalized:
        return ""
    path = urllib.parse.unquote(urllib.parse.urlsplit(normalized).path)
    if not path.lower().startswith(IEEE_MEDIASTORE_PATH_PREFIX.lower()):
        return ""
    return _IEEE_MEDIA_TIER_SUFFIX_PATTERN.sub("", path).lower()


def _ieee_asset_label(asset: Mapping[str, Any]) -> str:
    for field in ("heading", "caption", "label", "title", "alt"):
        value = normalize_text(str(asset.get(field) or ""))
        match = _IEEE_ASSET_LABEL_PATTERN.search(value)
        if not match:
            continue
        raw_kind = match.group(1).lower()
        label_kind = (
            "figure"
            if raw_kind.startswith("fig")
            else "formula"
            if raw_kind in {"equation", "formula"}
            else raw_kind
        )
        return f"{label_kind}:{match.group(2).lower()}"
    return ""


def ieee_asset_identity_key(asset: Mapping[str, Any]) -> str:
    """Return IEEE's canonical logical body-asset identity."""

    for field in IEEE_ASSET_RETRY_KEY_FIELDS:
        path = _canonical_ieee_mediastore_path(
            normalize_text(str(asset.get(field) or ""))
        )
        if path:
            return f"mediastore:{path}"
    anchor = normalize_text(
        str(asset.get("anchor_key") or asset.get("key") or "")
    ).lower()
    if anchor:
        return f"anchor:{anchor}"
    label = _ieee_asset_label(asset)
    if label:
        kind = _ieee_asset_kind(asset) or label.split(":", 1)[0]
        return f"label:{kind}:{label.split(':', 1)[1]}"
    return ""


def _ieee_asset_retry_key(asset: Mapping[str, Any]) -> tuple[Any, ...]:
    identity = ieee_asset_identity_key(asset)
    if identity:
        return (identity,)
    for field in IEEE_ASSET_RETRY_KEY_FIELDS:
        value = normalize_text(str(asset.get(field) or ""))
        if not value:
            continue
        parsed = urllib.parse.urlsplit(value)
        if parsed.scheme and parsed.netloc:
            value = urllib.parse.urlunsplit(
                (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", "")
            )
        return (value,)
    return ("",)


IEEE_ASSET_RETRY_POLICY = AssetRetryPolicy(
    name="ieee",
    key_fn=_ieee_asset_retry_key,
    retryable_failure=is_retryable_asset_failure,
)


def _ieee_asset_priority(asset: Mapping[str, Any]) -> int:
    return IEEE_ASSET_KIND_PRIORITY.get(_ieee_asset_kind(asset), 0)


def _ieee_asset_field_has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return bool(normalize_text(str(value)))


def _merge_ieee_missing_asset_fields(
    target: dict[str, Any], source: Mapping[str, Any], fields: tuple[str, ...]
) -> None:
    for field in fields:
        if not _ieee_asset_field_has_value(
            target.get(field)
        ) and _ieee_asset_field_has_value(source.get(field)):
            target[field] = source[field]


def _unique_ieee_assets(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[int] = set()
    for asset in assets:
        identity = id(asset)
        if identity not in seen:
            seen.add(identity)
            unique.append(asset)
    return unique


def _ieee_asset_values_for_fields(
    asset: Mapping[str, Any], fields: tuple[str, ...]
) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for field in fields:
        value = normalize_text(str(asset.get(field) or ""))
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return values


def _ieee_asset_identity_values(asset: Mapping[str, Any]) -> list[str]:
    values = _ieee_asset_values_for_fields(
        asset, (*IEEE_ASSET_URL_FIELDS, "path", "link")
    )
    identity = ieee_asset_identity_key(asset)
    return [identity, *values] if identity else values


def _ieee_asset_identity_index(
    assets: list[dict[str, Any]],
    *,
    fields: tuple[str, ...] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for asset in assets:
        values = (
            _ieee_asset_values_for_fields(asset, fields)
            if fields is not None
            else _ieee_asset_identity_values(asset)
        )
        for value in values:
            bucket = index.setdefault(value, [])
            if all(existing is not asset for existing in bucket):
                bucket.append(asset)
    return index


def _ieee_index_matches(
    index: Mapping[str, list[dict[str, Any]]], values: list[str]
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    seen: set[int] = set()
    for value in values:
        for asset in index.get(value, []):
            identity = id(asset)
            if identity not in seen:
                seen.add(identity)
                matches.append(asset)
    return matches


def _select_ieee_asset_survivor(
    candidates: list[dict[str, Any]], current_assets: list[dict[str, Any]]
) -> dict[str, Any]:
    current_order = {id(asset): index for index, asset in enumerate(current_assets)}
    fallback_order = len(current_assets)
    return max(
        candidates,
        key=lambda asset: (
            _ieee_asset_priority(asset),
            -current_order.get(id(asset), fallback_order),
        ),
    )


def _asset_identity_index_in_list(
    assets: list[dict[str, Any]], target: dict[str, Any]
) -> int | None:
    for index, asset in enumerate(assets):
        if asset is target:
            return index
    return None


def _merge_ieee_asset_group(
    current_assets: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    merge_fields: tuple[str, ...],
) -> dict[str, Any]:
    candidates = _unique_ieee_assets(candidates)
    survivor = _select_ieee_asset_survivor(candidates, current_assets)
    existing_positions = [
        position
        for position in (
            _asset_identity_index_in_list(current_assets, candidate)
            for candidate in candidates
        )
        if position is not None
    ]
    insert_at = min(existing_positions) if existing_positions else len(current_assets)
    for candidate in candidates:
        if candidate is not survivor:
            _merge_ieee_missing_asset_fields(survivor, candidate, merge_fields)
    survivor_position = _asset_identity_index_in_list(current_assets, survivor)
    for index in range(len(current_assets) - 1, -1, -1):
        asset = current_assets[index]
        if (
            any(asset is candidate for candidate in candidates)
            and asset is not survivor
        ):
            del current_assets[index]
    if survivor_position is None:
        current_assets.insert(min(insert_at, len(current_assets)), survivor)
    return survivor


def _dedupe_ieee_assets_by_priority(
    assets: list[dict[str, Any]],
    *,
    merge_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    for asset in assets:
        identity_index = _ieee_asset_identity_index(deduped)
        overlaps = _ieee_index_matches(
            identity_index, _ieee_asset_identity_values(asset)
        )
        if overlaps:
            _merge_ieee_asset_group(
                deduped, [*overlaps, asset], merge_fields=merge_fields
            )
            continue
        deduped.append(asset)
    return deduped


def reconcile_ieee_downloaded_assets(
    extracted_assets: list[dict[str, Any]],
    downloaded_assets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Overlay recovered download facts onto the original logical records."""

    reconciled = _dedupe_ieee_assets_by_priority(
        [dict(item) for item in extracted_assets],
        merge_fields=IEEE_ASSET_URL_FIELDS,
    )
    downloaded = _dedupe_ieee_assets_by_priority(
        [dict(item) for item in downloaded_assets],
        merge_fields=(*IEEE_ASSET_URL_FIELDS, *IEEE_DOWNLOAD_MERGE_FIELDS),
    )
    for downloaded_asset in downloaded:
        identity = ieee_asset_identity_key(downloaded_asset)
        existing_index = next(
            (
                index
                for index, existing in enumerate(reconciled)
                if identity and ieee_asset_identity_key(existing) == identity
            ),
            None,
        )
        if existing_index is None:
            kind = _ieee_asset_kind(downloaded_asset)
            section = normalize_text(str(downloaded_asset.get("section") or "")).lower()
            if kind == "supplementary" or section == "supplementary" or identity:
                reconciled.append(downloaded_asset)
            continue
        survivor = reconciled[existing_index]
        _merge_ieee_missing_asset_fields(
            survivor, downloaded_asset, IEEE_ASSET_URL_FIELDS
        )
        for field in IEEE_DOWNLOAD_MERGE_FIELDS:
            if field in downloaded_asset and _ieee_asset_field_has_value(
                downloaded_asset.get(field)
            ):
                survivor[field] = downloaded_asset[field]
    identities = [
        ieee_asset_identity_key(asset)
        for asset in reconciled
        if ieee_asset_identity_key(asset) and _ieee_asset_kind(asset) != "supplementary"
    ]
    if len(identities) != len(set(identities)):
        raise AssertionError("IEEE body asset identities must be unique")
    return reconciled


__all__ = [
    "IEEE_ASSET_RETRY_POLICY",
    "IEEE_ASSET_URL_FIELDS",
    "IEEE_DOWNLOAD_MERGE_FIELDS",
    "IEEE_STRONG_ASSET_IDENTITY_FIELDS",
    "IEEE_WEAK_ASSET_IDENTITY_FIELDS",
    "_dedupe_ieee_assets_by_priority",
    "ieee_asset_identity_key",
    "reconcile_ieee_downloaded_assets",
]
