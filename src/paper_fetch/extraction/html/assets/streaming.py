"""HTTP streaming and atomic staging helpers for HTML asset downloads."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from ....asset_budget import AssetBudget, AssetBudgetExceeded
from ....http import (
    DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
    DEFAULT_TRANSIENT_RETRIES,
    HttpRequestPolicy,
    HttpStreamOptions,
    HttpTransport,
    RequestCancelledError,
    RequestFailure,
    is_retryable_network_error,
    is_transient_http_status,
    provider_request_policy,
    request_cancel_check,
)
from ....http.headers import header_value
from ....image_tools import convert_source_image_path_to_png
from ....reason_codes import (
    ASSET_BYTES_PER_ASSET_EXCEEDED,
    ASSET_BYTES_TOTAL_EXCEEDED,
)
from ....utils import normalize_text
from ...image_payloads import image_dimensions_from_path
from ._kind import AssetDownloadKind
from .requester import cookie_header_for_url as _cookie_header_for_url
from .state import AssetBinaryPayload, AssetFetchResponse

if TYPE_CHECKING:
    pass

AssetFetchPolicy = Literal["browser_first", "direct_then_browser", "browser_only"]


def with_asset_timing(
    response: AssetFetchResponse,
    phase: str,
    seconds: float,
) -> AssetFetchResponse:
    timed = response.copy()
    timed.timing[phase] = max(0.0, float(timed.timing.get(phase, 0.0))) + max(
        0.0, float(seconds)
    )
    return timed


@dataclass(frozen=True)
class AssetRequestContext:
    """Shared HTTP, staging, and budget parameters for resolving an asset."""

    headers: Mapping[str, str] | None
    user_agent: str
    browser_context_seed: Mapping[str, Any] | None
    browser_cookies: tuple[dict[str, Any], ...]
    fetch_policy: AssetFetchPolicy
    asset_budget: AssetBudget
    staging_dir: Path
    allowed_hosts: tuple[str, ...] | None = None
    candidate_headers_filter: (
        Callable[[str, Mapping[str, str]], Mapping[str, str]] | None
    ) = None
    sensitive_headers: tuple[str, ...] = ()
    provider_name: str | None = None
    route_name: str | None = None
    path_converter: Callable[..., Any] = convert_source_image_path_to_png

    def for_asset(
        self,
        kind: AssetDownloadKind,
        asset: Mapping[str, Any],
    ) -> AssetRequestContext:
        output_subdir = kind.output_subdir(asset)
        if output_subdir is None:
            return self
        return replace(self, staging_dir=self.staging_dir / output_subdir)


def unique_asset_staging_path(staging_dir: Path) -> Path:
    return staging_dir / f".paper-fetch-asset-{uuid.uuid4().hex}.part"


def rollback_response_reservation(response: AssetFetchResponse | None) -> None:
    if response is not None:
        response.rollback()


def _response_content_length(response: AssetFetchResponse) -> int | None:
    raw_value = header_value(response.get("headers"), "content-length")
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def stage_browser_response(
    kind: AssetDownloadKind,
    response: AssetFetchResponse,
    *,
    request_context: AssetRequestContext,
) -> AssetFetchResponse:
    """Apply the normal asset budget and atomic staging path to browser bytes."""

    from ....artifacts import ArtifactStore

    body = bytes(response.get("body") or b"")
    reservation = request_context.asset_budget.reserve()
    staging_path = unique_asset_staging_path(request_context.staging_dir)
    reservation.register_staging(staging_path)
    try:
        request_context.asset_budget.raise_if_cancelled()
        reservation.declare_content_length(_response_content_length(response))
        reservation.consume(len(body))
        reservation.reconcile_actual()
        ArtifactStore.from_download_dir(request_context.staging_dir).write_bytes_file(
            staging_path,
            body,
        )
        dimensions = (
            image_dimensions_from_path(staging_path) if kind.name == "figure" else None
        )
        if dimensions is not None:
            reservation.validate_pixels(*dimensions)
        request_context.asset_budget.raise_if_cancelled()
    except BaseException:
        reservation.rollback()
        raise

    staged = response.copy()
    staged.payload = AssetBinaryPayload(
        body=body[:8192],
        staging_path=staging_path,
        downloaded_bytes=len(body),
        reservation=reservation,
    )
    staged["body_preview"] = body[:8192]
    if dimensions is not None:
        staged["dimensions"] = {
            "width": dimensions[0],
            "height": dimensions[1],
        }
    return staged


def _cancellable_retry_sleep(
    seconds: float,
    *,
    asset_budget: AssetBudget,
) -> float:
    """Wait between transient stream retries while honoring cancellation."""

    started_at = time.monotonic()
    deadline = started_at + max(0.0, seconds)
    cancel_check = request_cancel_check.get()
    while True:
        asset_budget.raise_if_cancelled()
        if cancel_check is not None and cancel_check() is True:
            raise RequestCancelledError("Request cancelled.")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(remaining, 0.1))
    return max(0.0, time.monotonic() - started_at)


def stream_asset_candidate(
    kind: AssetDownloadKind,
    transport: HttpTransport,
    candidate_url: str,
    *,
    request_headers: Mapping[str, str],
    request_context: AssetRequestContext,
) -> AssetFetchResponse:
    last_failure: RequestFailure | None = None
    retry_wait_seconds = 0.0
    request_policy = HttpRequestPolicy(
        allowed_hosts=request_context.allowed_hosts,
        sensitive_headers=request_context.sensitive_headers,
        max_response_bytes=request_context.asset_budget.max_bytes_per_asset,
        max_compressed_response_bytes=request_context.asset_budget.max_bytes_per_asset,
        timeout_seconds=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
        retry_on_rate_limit=True,
        rate_limit_retries=1,
        max_rate_limit_wait_seconds=5,
        retry_on_transient=True,
        transient_retries=DEFAULT_TRANSIENT_RETRIES,
    )
    if request_context.provider_name and request_context.route_name:
        request_policy = provider_request_policy(
            request_context.provider_name,
            request_context.route_name,
            base=request_policy,
        )
    max_stream_attempts = (
        max(0, int(request_policy.transient_retries or 0)) + 1
        if request_policy.retry_on_transient
        else 1
    )
    for stream_attempt in range(max_stream_attempts):
        reservation = request_context.asset_budget.reserve()
        staging_path = unique_asset_staging_path(request_context.staging_dir)
        reservation.register_staging(staging_path)
        try:
            raw_response = transport.stream_to_file(
                "GET",
                candidate_url,
                staging_path,
                headers=request_headers,
                options=HttpStreamOptions(
                    # Transient retries live in this layer so partial-body retries
                    # receive a fresh exclusive staging path and reservation.
                    retry_on_transient=False,
                    transient_retries=0,
                    request_policy=request_policy,
                    on_content_length=reservation.declare_content_length,
                    on_chunk=reservation.consume,
                ),
            )
            dimensions = (
                image_dimensions_from_path(staging_path)
                if kind.name == "figure"
                else None
            )
            if dimensions is not None:
                reservation.validate_pixels(*dimensions)
            cleaned_response = {
                key: value
                for key, value in raw_response.items()
                if not str(key).startswith("_")
            }
            streamed = AssetFetchResponse.from_mapping(cleaned_response)
            transport_timings = next(
                (
                    value
                    for key, value in raw_response.items()
                    if str(key).endswith("timing_seconds")
                    and isinstance(value, Mapping)
                ),
                None,
            )
            streamed.timing = (
                {
                    str(phase): float(elapsed)
                    for phase, elapsed in transport_timings.items()
                    if isinstance(elapsed, int | float)
                }
                if transport_timings is not None
                else {}
            )
            streamed = with_asset_timing(
                streamed,
                "retry_wait",
                retry_wait_seconds,
            )
            # Only a fixed-size prefix is retained for signature/challenge
            # diagnostics. The binary remains solely in the staging file.
            streamed.payload = replace(
                streamed.payload,
                body=bytes(raw_response.get("body_preview") or b""),
                reservation=reservation,
            )
            if dimensions is not None:
                streamed["dimensions"] = {
                    "width": dimensions[0],
                    "height": dimensions[1],
                }
            return streamed
        except AssetBudgetExceeded:
            reservation.rollback()
            raise
        except RequestFailure as exc:
            reservation.rollback()
            last_failure = exc
            reason_code = normalize_text(str(getattr(exc, "reason_code", "") or ""))
            if reason_code in {
                ASSET_BYTES_PER_ASSET_EXCEEDED,
                ASSET_BYTES_TOTAL_EXCEEDED,
            }:
                request_context.asset_budget.cancel(
                    reason_code,
                    diagnostic={
                        "boundary": "asset_stream_transport",
                    },
                )
                raise
            retryable = is_retryable_network_error(exc) or is_transient_http_status(
                exc.status_code
            )
            if stream_attempt + 1 < max_stream_attempts and retryable:
                retry_wait_seconds += _cancellable_retry_sleep(
                    request_policy.transient_backoff_base_seconds * (2**stream_attempt),
                    asset_budget=request_context.asset_budget,
                )
                continue
            raise
        except BaseException:
            reservation.rollback()
            raise
    assert last_failure is not None
    raise last_failure


def request_asset_candidate(
    kind: AssetDownloadKind,
    transport: HttpTransport,
    candidate_url: str,
    *,
    request_context: AssetRequestContext,
) -> AssetFetchResponse:
    request_headers = kind.request_headers(
        request_context.headers,
        request_context.user_agent,
        request_context.browser_context_seed,
    )
    cookie_header = _cookie_header_for_url(
        list(request_context.browser_cookies), candidate_url
    )
    if cookie_header:
        request_headers["Cookie"] = cookie_header
    if request_context.candidate_headers_filter is not None:
        request_headers = dict(
            request_context.candidate_headers_filter(candidate_url, request_headers)
        )
    return stream_asset_candidate(
        kind,
        transport,
        candidate_url,
        request_headers=request_headers,
        request_context=request_context,
    )


__all__ = [
    "AssetFetchPolicy",
    "AssetRequestContext",
    "request_asset_candidate",
    "rollback_response_reservation",
    "stage_browser_response",
    "stream_asset_candidate",
    "unique_asset_staging_path",
    "with_asset_timing",
]
