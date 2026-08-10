"""Request-local memoization for IEEE multimedia discovery."""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from ..http import redact_url_for_cache
from ..runtime import RuntimeContext
from ..utils import normalize_text


def cached_ieee_multimedia_assets(
    runtime_context: RuntimeContext | None,
    *,
    article_number: str,
    multimedia_url: str,
) -> list[dict[str, str]] | None:
    if runtime_context is None:
        return None
    cached = runtime_context.get_session_cache(
        _multimedia_cache_key(article_number, multimedia_url),
        copy_value=True,
    )
    if not isinstance(cached, list):
        return None
    return [dict(asset) for asset in cached if isinstance(asset, Mapping)]


def cache_ieee_multimedia_assets(
    runtime_context: RuntimeContext | None,
    *,
    article_number: str,
    multimedia_url: str,
    assets: list[dict[str, Any]],
) -> None:
    if runtime_context is None or not assets:
        return
    runtime_context.set_session_cache(
        _multimedia_cache_key(article_number, multimedia_url),
        [dict(asset) for asset in assets],
        copy_value=True,
    )


def ieee_asset_key(asset: Mapping[str, Any]) -> str:
    for field in (
        "full_size_url",
        "url",
        "download_url",
        "source_url",
        "preview_url",
        "original_url",
        "figure_page_url",
    ):
        if value := normalize_text(str(asset.get(field) or "")):
            return value
    return ""


def _multimedia_cache_key(article_number: str, multimedia_url: str) -> tuple[str, ...]:
    return (
        "ieee",
        "multimedia_assets",
        normalize_text(article_number),
        redact_url_for_cache(multimedia_url),
    )


__all__ = [
    "cache_ieee_multimedia_assets",
    "cached_ieee_multimedia_assets",
    "ieee_asset_key",
]
