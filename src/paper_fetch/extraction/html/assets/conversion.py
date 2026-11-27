"""Staged vector/raster source conversion and atomic asset persistence."""

from __future__ import annotations

import contextlib
import time
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ....asset_budget import AssetBudget, AssetBudgetExceeded, AssetReservation
from ....http.headers import header_value
from ....image_tools import (
    ImageConversionFailure,
    convert_source_image_path_to_png,
    source_image_format_from_payload,
)
from ....reason_codes import ASSET_BYTES_PER_ASSET_EXCEEDED, ASSET_CANCELLED
from ....utils import build_asset_output_path, normalize_text
from ...image_payloads import image_dimensions_from_path
from ._kind import AssetDownloadKind
from .dom import (
    _response_dimensions,
    looks_like_full_size_asset_url,
    preview_dimensions_are_acceptable,
)
from .state import (
    AssetBinaryPayload,
    AssetDownloadAttempt,
    AssetDownloadCandidate,
    AssetDownloadFailure,
    AssetDownloadResolution,
    AssetFetchResponse,
    asset_failure,
)
from .streaming import (
    rollback_response_reservation,
    unique_asset_staging_path,
    with_asset_timing,
)

if TYPE_CHECKING:
    pass

_SUPPLEMENTARY_PASSTHROUGH_FIELDS = (
    "asset_type",
    "source_href",
    "source_page_url",
    "source_kind",
    "source_ref",
    "filename_hint",
    "attachment_type",
    "object_type",
    "category",
)
_FIGURE_PASSTHROUGH_FIELDS = (
    "asset_id",
    "asset_type",
    "source_kind",
    "source_ref",
    "filename_hint",
    "attachment_type",
    "object_type",
    "category",
)


def _convert_staged_figure_response(
    response: AssetFetchResponse,
    *,
    source_url: str,
    asset_budget: AssetBudget | None,
    path_converter: Callable[..., Any],
) -> tuple[AssetFetchResponse, str]:
    source_path = response.payload.staging_path
    source_reservation = response.payload.reservation
    if (
        source_path is None
        or not source_path.is_file()
        or not isinstance(source_reservation, AssetReservation)
        or asset_budget is None
    ):
        return response.copy(), ""
    try:
        with source_path.open("rb") as source_stream:
            source_prefix = source_stream.read(8192)
    except OSError:
        return response.copy(), ""

    content_type = header_value(response.get("headers"), "content-type")
    source_format = source_image_format_from_payload(
        source_prefix,
        content_type=content_type,
        source_url=source_url,
    )
    if source_format not in {"eps", "tiff"}:
        return response.copy(), ""

    converted_path = unique_asset_staging_path(source_path.parent)
    converted_reservation = asset_budget.reserve()
    converted_reservation.register_staging(converted_path)
    try:
        path_conversion = path_converter(
            source_path,
            converted_path,
            content_type=content_type,
            source_url=source_url,
            max_output_bytes=asset_budget.max_bytes_per_asset,
        )
        if path_conversion is None:
            converted_reservation.rollback()
            return response.copy(), ""
        converted_reservation.declare_content_length(path_conversion.output_bytes)
        converted_reservation.consume(path_conversion.output_bytes)
        dimensions = image_dimensions_from_path(converted_path)
        if dimensions is not None:
            converted_reservation.validate_pixels(*dimensions)
        with converted_path.open("rb") as converted_stream:
            preview = converted_stream.read(8192)
    except ImageConversionFailure as exc:
        converted_reservation.rollback()
        if exc.reason_code == ASSET_BYTES_PER_ASSET_EXCEEDED:
            diagnostic = {
                "max_bytes_per_asset": asset_budget.max_bytes_per_asset,
                "boundary": "image_conversion",
            }
            asset_budget.cancel(exc.reason_code, diagnostic=diagnostic)
            raise AssetBudgetExceeded(
                exc.reason_code,
                diagnostic=diagnostic,
                fatal=True,
            ) from exc
        raise
    except BaseException:
        converted_reservation.rollback()
        raise

    converted = response.copy()
    converted_headers = dict(response.get("headers") or {})
    converted_headers["content-type"] = path_conversion.content_type
    converted["headers"] = converted_headers
    converted.payload = AssetBinaryPayload(
        body=preview,
        staging_path=converted_path,
        downloaded_bytes=path_conversion.output_bytes,
        reservation=converted_reservation,
    )
    converted.original_payload = response.payload
    converted.original_content_type = content_type
    converted.source_format = path_conversion.source_format
    converted.conversion_tool = path_conversion.tool
    converted["body_preview"] = preview
    if dimensions is not None:
        converted["dimensions"] = {
            "width": dimensions[0],
            "height": dimensions[1],
        }
    return converted, path_conversion.source_format


def converted_figure_response(
    response: AssetFetchResponse,
    *,
    source_url: str,
    asset_budget: AssetBudget | None = None,
    path_converter: Callable[..., Any] = convert_source_image_path_to_png,
) -> tuple[AssetFetchResponse, str]:
    conversion_started_at = time.monotonic()
    converted, source_format = _convert_staged_figure_response(
        response,
        source_url=source_url,
        asset_budget=asset_budget,
        path_converter=path_converter,
    )
    return (
        with_asset_timing(
            converted,
            "conversion",
            time.monotonic() - conversion_started_at,
        ),
        source_format,
    )


def conversion_failure_attempt(
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    candidate: AssetDownloadCandidate,
    response: AssetFetchResponse,
    exc: ImageConversionFailure,
) -> AssetDownloadAttempt:
    rollback_response_reservation(response)
    return AssetDownloadAttempt(
        candidate=candidate,
        failure=asset_failure(
            kind.failure_template(
                asset,
                candidate.url,
                status=response.get("status_code"),
                content_type=header_value(response.get("headers"), "content-type"),
                final_url=normalize_text(str(response.get("url") or candidate.url)),
                reason=f"{exc.reason_code}: {exc}",
            ),
            timing=response.timing,
            started_at=response.started_at,
            route_diagnostics=response.route_diagnostics,
        ),
    )


def _response_final_url(response: AssetFetchResponse, source_url: str) -> str:
    response_url = normalize_text(str(response.get("url") or ""))
    return urllib.parse.urljoin(source_url, response_url or source_url)


def _asset_marks_preview_accepted(asset: Mapping[str, Any]) -> bool:
    value = asset.get("preview_accepted")
    if isinstance(value, bool):
        return value
    return normalize_text(str(value or "")).lower() in {"1", "true", "yes", "accepted"}


def _attach_response_diagnostics(
    download: dict[str, Any],
    response: AssetFetchResponse,
) -> None:
    browser_backend = normalize_text(response.browser_backend)
    final_fetcher = normalize_text(response.final_fetcher)
    if browser_backend:
        download["browser_backend"] = browser_backend
        final_fetcher = final_fetcher or browser_backend
    if final_fetcher:
        download["final_fetcher"] = final_fetcher

    normalized_attempts = [
        dict(attempt)
        for attempt in response.recovery_attempts
        if isinstance(attempt, Mapping)
    ]
    if normalized_attempts:
        download["recovery_attempts"] = normalized_attempts
        browser_attempt: dict[str, Any] = next(
            (
                attempt
                for attempt in reversed(normalized_attempts)
                if attempt.get("stage") == "browser"
            ),
            {},
        )
        if browser_attempt.get("browser_backend"):
            download["browser_backend"] = browser_attempt["browser_backend"]
        if browser_attempt.get("final_fetcher"):
            download["final_fetcher"] = browser_attempt["final_fetcher"]

    if response.route_diagnostics:
        download["asset_route"] = dict(response.route_diagnostics)


def _has_non_empty_staged_file(
    staging_path: Path | None,
    response: AssetFetchResponse,
) -> bool:
    if staging_path is None or int(response.get("downloaded_bytes") or 0) <= 0:
        return False
    try:
        return staging_path.stat().st_size > 0
    except OSError:
        return False


def _publish_staged_resolution(
    *,
    kind: AssetDownloadKind,
    asset: Mapping[str, Any],
    response: AssetFetchResponse,
    reservation: AssetReservation | None,
    staging_path: Path,
    source_url: str,
    final_url: str,
    content_type: str,
    target_asset_dir: Path,
    output_path: Path,
    used_names_by_dir: dict[Path, set[str]],
    artifact_store: Any | None,
) -> tuple[str, str] | AssetDownloadFailure:
    from ....artifacts import ArtifactStore

    store = (
        artifact_store
        if isinstance(artifact_store, ArtifactStore)
        else ArtifactStore.from_download_dir(target_asset_dir.parent)
    )
    if reservation is None:
        with contextlib.suppress(OSError):
            staging_path.unlink(missing_ok=True)
        return AssetDownloadFailure(
            kind.failure_template(
                asset,
                source_url,
                content_type=content_type,
                final_url=final_url,
                reason=ASSET_CANCELLED,
            ),
            route_diagnostics=response.route_diagnostics,
        )

    original_payload = response.original_payload
    original_staging_path = original_payload.staging_path if original_payload else None
    original_reservation = original_payload.reservation if original_payload else None
    original_output_path: Path | None = None
    if original_staging_path is not None and isinstance(
        original_reservation, AssetReservation
    ):
        original_output_path = build_asset_output_path(
            target_asset_dir,
            source_url,
            normalize_text(response.original_content_type),
            final_url,
            used_names_by_dir.setdefault(target_asset_dir, set()),
        )

    published_paths: list[Path] = []
    original_saved_path = ""
    try:
        with contextlib.ExitStack() as stack:
            stack.enter_context(reservation.commit_critical_section())
            if isinstance(original_reservation, AssetReservation):
                stack.enter_context(original_reservation.commit_critical_section())
            if original_output_path is not None and original_staging_path is not None:
                published_original = store.publish_staged_file(
                    original_staging_path,
                    original_output_path,
                )
                published_paths.append(published_original)
                original_saved_path = str(published_original)
            published = store.publish_staged_file(staging_path, output_path)
            published_paths.append(published)
            saved_path = str(published)
            reservation.unregister_staging(staging_path)
            if (
                isinstance(original_reservation, AssetReservation)
                and original_staging_path is not None
            ):
                original_reservation.unregister_staging(original_staging_path)
            reservation.commit()
            if isinstance(original_reservation, AssetReservation):
                original_reservation.commit()
    except BaseException:
        for published_path in reversed(published_paths):
            with contextlib.suppress(OSError):
                published_path.unlink(missing_ok=True)
        reservation.rollback()
        if isinstance(original_reservation, AssetReservation):
            original_reservation.rollback()
        raise

    return saved_path, original_saved_path


def _build_supplementary_entry(
    *,
    asset: Mapping[str, Any],
    response: AssetFetchResponse,
    source_url: str,
    final_url: str,
    content_type: str,
    saved_path: str,
) -> dict[str, Any]:
    download: dict[str, Any] = {
        "kind": "supplementary",
        "heading": asset.get("heading")
        or asset.get("filename_hint")
        or "Supplementary Material",
        "caption": asset.get("caption", ""),
        "download_url": source_url,
        "source_url": final_url,
        "content_type": content_type,
        "path": saved_path,
        "downloaded_bytes": int(response.get("downloaded_bytes") or 0),
        "section": "supplementary",
        "download_tier": "supplementary_file",
    }
    for key in _SUPPLEMENTARY_PASSTHROUGH_FIELDS:
        value = asset.get(key)
        if value:
            download[key] = value
    _attach_response_diagnostics(download, response)
    return download


def _build_figure_entry(
    *,
    resolved: AssetDownloadResolution,
    response: AssetFetchResponse,
    source_url: str,
    final_url: str,
    content_type: str,
    saved_path: str,
    original_saved_path: str,
) -> dict[str, Any]:
    asset = resolved.asset
    preview_url = normalize_text(resolved.preview_url)
    full_size_url = normalize_text(resolved.full_size_url)
    download_tier_override = normalize_text(resolved.download_tier_override)
    width, height = _response_dimensions(response) or (0, 0)
    download_tier = download_tier_override or (
        "preview"
        if preview_url
        and source_url == preview_url
        and source_url != full_size_url
        and not looks_like_full_size_asset_url(source_url.lower())
        else "full_size"
    )
    download: dict[str, Any] = {
        "kind": asset.get("kind", "figure"),
        "heading": asset.get("heading", "Figure"),
        "caption": asset.get("caption", ""),
        "url": asset.get("url", "") or full_size_url or preview_url,
        "original_url": full_size_url
        or normalize_text(str(asset.get("original_url") or ""))
        or source_url,
        "preview_url": preview_url,
        "full_size_url": full_size_url,
        "figure_page_url": asset.get("figure_page_url", ""),
        "download_url": source_url,
        "download_tier": download_tier,
        "source_url": final_url,
        "content_type": content_type,
        "path": saved_path,
        "downloaded_bytes": int(response.get("downloaded_bytes") or 0),
        "section": asset.get("section") or "body",
    }
    for key in _FIGURE_PASSTHROUGH_FIELDS:
        value = asset.get(key)
        if value:
            download[key] = value
    _attach_response_diagnostics(download, response)

    input_provenance = asset.get("provenance")
    inherited_provenance = (
        [
            normalize_text(str(item))
            for item in input_provenance
            if normalize_text(str(item))
        ]
        if isinstance(input_provenance, Sequence)
        and not isinstance(input_provenance, str | bytes | bytearray)
        else []
    )
    provenance = list(dict.fromkeys([*inherited_provenance, *resolved.provenance]))
    if provenance:
        download["provenance"] = provenance

    if original_saved_path:
        download["original_source_path"] = original_saved_path
        download["original_content_type"] = normalize_text(
            response.original_content_type
        )
        download["original_download_url"] = source_url
        download["conversion_source_format"] = normalize_text(response.source_format)
        download["conversion_output_format"] = "png"
        download["conversion_tool"] = normalize_text(response.conversion_tool)
        download["download_tier"] = "source_converted"
    if width > 0 and height > 0:
        download["width"] = width
        download["height"] = height
    if download_tier == "preview" and (
        _asset_marks_preview_accepted(asset)
        or preview_dimensions_are_acceptable(width, height)
    ):
        download["preview_accepted"] = True
    return download


def save_asset_resolution(
    kind: AssetDownloadKind,
    resolved: AssetDownloadResolution,
    *,
    asset_dir: Path,
    used_names_by_dir: dict[Path, set[str]],
    artifact_store: Any | None = None,
) -> dict[str, Any] | AssetDownloadFailure:
    asset = resolved.asset
    response = resolved.response or AssetFetchResponse()
    source_url = normalize_text(resolved.source_url)
    final_url = _response_final_url(response, source_url)
    content_type = header_value(response.get("headers"), "content-type")
    staging_path = response.payload.staging_path

    if not _has_non_empty_staged_file(staging_path, response):
        rollback_response_reservation(response)
        return AssetDownloadFailure(
            kind.failure_template(
                asset,
                source_url,
                status=response.get("status_code"),
                content_type=content_type,
                final_url=final_url,
                reason="empty_response_body",
            ),
            route_diagnostics=response.route_diagnostics,
        )
    assert staging_path is not None

    output_subdir = kind.output_subdir(asset)
    target_asset_dir = (
        asset_dir / output_subdir if output_subdir is not None else asset_dir
    )
    target_asset_dir.mkdir(parents=True, exist_ok=True)
    output_path = build_asset_output_path(
        target_asset_dir,
        source_url,
        content_type,
        final_url,
        used_names_by_dir.setdefault(target_asset_dir, set()),
        preferred_filename=(
            normalize_text(str(asset.get("filename_hint") or "")) or None
            if kind.name == "supplementary"
            else None
        ),
    )

    published = _publish_staged_resolution(
        kind=kind,
        asset=asset,
        response=response,
        reservation=resolved.reservation,
        staging_path=staging_path,
        source_url=source_url,
        final_url=final_url,
        content_type=content_type,
        target_asset_dir=target_asset_dir,
        output_path=output_path,
        used_names_by_dir=used_names_by_dir,
        artifact_store=artifact_store,
    )
    if isinstance(published, AssetDownloadFailure):
        return published
    saved_path, original_saved_path = published

    if kind.name == "supplementary":
        return _build_supplementary_entry(
            asset=asset,
            response=response,
            source_url=source_url,
            final_url=final_url,
            content_type=content_type,
            saved_path=saved_path,
        )
    return _build_figure_entry(
        resolved=resolved,
        response=response,
        source_url=source_url,
        final_url=final_url,
        content_type=content_type,
        saved_path=saved_path,
        original_saved_path=original_saved_path,
    )


__all__ = [
    "conversion_failure_attempt",
    "converted_figure_response",
    "save_asset_resolution",
]
