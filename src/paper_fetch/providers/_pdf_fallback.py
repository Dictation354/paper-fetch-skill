"""PDF fallback helpers for browser-workflow and direct-HTTP providers."""

from __future__ import annotations

import contextlib
import math
import os
import shutil
import time
import urllib.parse
import uuid
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal, TypeAlias

from ..artifacts import ArtifactStore
from ..extraction.html.assets.requester import (
    cookie_header_for_url as _cookie_header_for_url,
)
from ..extraction.html.shared import html_text_snippet, html_title_snippet
from ..extraction.html.signals import detect_html_block, summarize_html
from ..http import (
    DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
    PDF_ACCEPT_HEADER,
    HttpRequestPolicy,
    HttpTransport,
    RequestCancelledError,
    RequestFailure,
    diagnostic_url_payload,
    provider_request_policy,
    redact_text_for_diagnostics,
    redact_url_for_diagnostics,
)
from ..http.headers import header_value
from ..provider_catalog import compile_route_execution_policy_for_kind
from ..quality.access_boundary import (
    propagate_paywall,
    raise_for_api_entitlement,
    raise_for_paywall,
)
from ..runtime import RuntimeContext
from ..utils import normalize_text
from ._ieee_pdf import navigate_stamp_pdf, stamp_article_number
from ._pdf_candidates import extract_pdf_candidate_urls_from_html
from ._pdf_common import (
    PdfAssetProfile,
    PdfFetchFailure,
    PdfFetchResult,
    filename_from_headers,
    looks_like_pdf_payload,
    pdf_fetch_result_from_bytes,
    pdf_max_bytes,
)
from .browser_runtime.context import open_browser_context
from .browser_runtime.navigation import (
    context_get,
    navigate_page,
    refetch_browser_response,
)
from .browser_runtime.seed import filter_browser_cookies_for_url
from .browser_runtime.types import BrowserRuntimeConfig, BrowserRuntimeFailure

PdfBytesTransport: TypeAlias = Literal["http", "browser_response", "browser_download"]

DEFAULT_BROWSER_NAVIGATION_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
)
MAX_PDF_FAILURE_ARTIFACTS = 5
MAX_PDF_FAILURE_SCREENSHOT_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class PdfFallbackStrategy:
    transport: HttpTransport
    headers: Mapping[str, str] | None = None
    timeout: int = DEFAULT_FULLTEXT_TIMEOUT_SECONDS
    artifact_dir: Path | None = None
    asset_profile: PdfAssetProfile = "none"
    asset_output_dir: Path | None = None
    seed_urls: list[str] | None = None
    browser_cookies: list[dict[str, Any]] | None = None
    allow_pdf_only: bool = True
    expected_identity: Mapping[str, Any] | None = None
    context: RuntimeContext | None = None
    provider_name: str | None = None
    fetcher: Callable[..., PdfFetchResult] | None = None

    def fetch(self, candidate_urls: list[str]) -> PdfFetchResult:
        execution_policy = None
        if self.provider_name:
            with contextlib.suppress(ValueError):
                execution_policy = compile_route_execution_policy_for_kind(
                    self.provider_name, "pdf", prefer_transport="http"
                )
        effective_timeout = (
            execution_policy.timeout_seconds
            if execution_policy is not None
            else self.timeout
        )
        active_fetcher = self.fetcher or fetch_pdf_over_http
        return active_fetcher(
            self.transport,
            candidate_urls,
            headers=self.headers,
            artifact_dir=self.artifact_dir,
            asset_profile=self.asset_profile,
            asset_output_dir=self.asset_output_dir,
            browser_cookies=self.browser_cookies,
            allow_pdf_only=self.allow_pdf_only,
            request=PdfRequestContext(
                timeout_seconds=effective_timeout,
                expected_identity=self.expected_identity,
                runtime=self.context,
                provider_name=self.provider_name,
            ),
        )


@dataclass(frozen=True)
class PdfRequestContext:
    """Shared deadline, identity, and runtime state for one PDF request."""

    timeout_seconds: int | float = DEFAULT_FULLTEXT_TIMEOUT_SECONDS
    expected_identity: Mapping[str, Any] | None = None
    runtime: RuntimeContext | None = None
    deadline_monotonic: float | None = None
    provider_name: str | None = None
    allowed_hosts: tuple[str, ...] | None = None
    browser_only: bool = False

    def with_deadline(self, deadline: float) -> PdfRequestContext:
        return replace(self, deadline_monotonic=deadline)

    def with_provider(self, provider_name: str | None) -> PdfRequestContext:
        return replace(
            self, provider_name=normalize_text(provider_name).lower() or None
        )


@dataclass(frozen=True)
class _PdfBrowserRouteRequest:
    provider_name: str
    timeout_seconds: float
    allowed_hosts: tuple[str, ...]
    request: PdfRequestContext
    started_monotonic: float
    deadline_monotonic: float


@dataclass(frozen=True)
class _PdfDirectRoutePolicy:
    provider_name: str | None
    route_name: str | None
    request_policy: HttpRequestPolicy


def _prepare_pdf_browser_route_request(
    request: PdfRequestContext,
    *,
    browser_config: BrowserRuntimeConfig | None,
    provider_name: str | None,
) -> _PdfBrowserRouteRequest:
    active_provider = normalize_text(
        browser_config.provider
        if browser_config is not None
        else provider_name or request.provider_name or ""
    ).lower()
    timeout_seconds = (
        max(0.001, float(browser_config.timeout_ms) / 1000.0)
        if browser_config is not None
        else float(DEFAULT_FULLTEXT_TIMEOUT_SECONDS)
    )
    if active_provider:
        with contextlib.suppress(ValueError):
            compiled = compile_route_execution_policy_for_kind(
                active_provider, "pdf", prefer_transport="browser"
            )
            timeout_seconds = min(timeout_seconds, float(compiled.timeout_seconds))
    started = time.monotonic()
    deadline = (
        (
            request.runtime.browser_deadline_monotonic
            if request.runtime is not None
            else None
        )
        or request.deadline_monotonic
        or (started + timeout_seconds)
    )
    return _PdfBrowserRouteRequest(
        provider_name=active_provider,
        timeout_seconds=timeout_seconds,
        allowed_hosts=tuple(request.allowed_hosts or ()),
        request=request.with_provider(active_provider).with_deadline(deadline),
        started_monotonic=started,
        deadline_monotonic=deadline,
    )


def _compile_pdf_direct_route_policy(
    request: PdfRequestContext, *, maximum_pdf_bytes: int
) -> _PdfDirectRoutePolicy:
    provider_name = normalize_text(request.provider_name).lower() or None
    route_name: str | None = None
    if provider_name:
        with contextlib.suppress(ValueError):
            route_name = compile_route_execution_policy_for_kind(
                provider_name, "pdf", prefer_transport="http"
            ).route
    generic_policy = HttpRequestPolicy(
        allowed_hosts=request.allowed_hosts,
        max_response_bytes=maximum_pdf_bytes,
        max_compressed_response_bytes=maximum_pdf_bytes,
        timeout_seconds=max(1, int(math.ceil(request.timeout_seconds))),
        retry_on_transient=True,
    )
    return _PdfDirectRoutePolicy(
        provider_name=provider_name,
        route_name=route_name,
        request_policy=(
            provider_request_policy(provider_name, route_name, base=generic_policy)
            if provider_name and route_name
            else generic_policy
        ),
    )


def _open_pdf_browser_context(
    browser_config: BrowserRuntimeConfig, *, runtime: RuntimeContext | None = None
) -> tuple[Any | None, Any]:
    return open_browser_context(replace(browser_config), runtime_context=runtime)


def _seed_pdf_browser_page(
    page: Any, seed_urls: list[str] | None, request: PdfRequestContext
) -> PdfFetchFailure | None:
    deadline = request.deadline_monotonic
    if deadline is None:
        return None
    for seed_url in [
        normalize_text(url) for url in seed_urls or [] if normalize_text(url)
    ]:
        if request.runtime is not None:
            request.runtime.raise_if_cancelled()
        try:
            timeout_ms = (
                _remaining_pdf_timeout_seconds(request.runtime, deadline, maximum=60)
                * 1000
            )
            navigate_page(
                page,
                seed_url,
                wait_until="domcontentloaded",
                timeout_ms=timeout_ms,
                mode="file",
            )
        except RequestCancelledError:
            raise
        except BrowserRuntimeFailure as exc:
            return PdfFetchFailure(exc.kind, exc.message, details=exc.details)
        except PdfFetchFailure as exc:
            return exc
        except Exception:
            continue
    return None


def _browser_response_metadata(
    response: Any | None,
) -> tuple[int | None, Mapping[str, Any]]:
    if response is None:
        return None, {}
    try:
        status = int(response.status)
    except (AttributeError, TypeError, ValueError):
        status = None
    return status, getattr(response, "headers", {}) or {}


def _capture_pdf_browser_failure(
    page: Any,
    artifact_dir: Path,
    html: str,
    attempt_index: int,
    request: PdfRequestContext,
    *,
    browser_budget_seconds: float,
) -> None:
    deadline = request.deadline_monotonic
    if deadline is None:
        return
    _remaining_pdf_timeout_seconds(
        request.runtime, deadline, maximum=browser_budget_seconds
    )
    _write_pdf_failure_html(
        artifact_dir,
        html.encode("utf-8", errors="replace"),
        context=request.runtime,
        attempt_index=attempt_index,
    )
    try:
        _remaining_pdf_timeout_seconds(request.runtime, deadline, maximum=5)
    except PdfFetchFailure:
        return
    with contextlib.suppress(Exception):
        if attempt_index >= MAX_PDF_FAILURE_ARTIFACTS:
            return
        canonical_screenshot = artifact_dir / "pdf.failure.png"
        screenshot_path = artifact_dir / f"pdf.failure.{attempt_index + 1:02d}.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        if screenshot_path.stat().st_size > MAX_PDF_FAILURE_SCREENSHOT_BYTES:
            screenshot_path.unlink(missing_ok=True)
            return
        if not canonical_screenshot.exists():
            staging = artifact_dir / f".pdf.failure.{uuid.uuid4().hex}.part"
            try:
                shutil.copyfile(screenshot_path, staging)
                with staging.open("rb+") as copied:
                    os.fsync(copied.fileno())
                runtime_store = (
                    request.runtime.artifact_store
                    if request.runtime is not None
                    else None
                )
                store = (
                    runtime_store
                    if isinstance(runtime_store, ArtifactStore)
                    else ArtifactStore.from_download_dir(artifact_dir.parent)
                )
                store.publish_staged_file(
                    staging, canonical_screenshot, overwrite=False
                )
            finally:
                staging.unlink(missing_ok=True)


def _pdf_deadline(
    context: RuntimeContext | None, timeout_seconds: int | float
) -> float:
    timeout_value = max(0.0, float(timeout_seconds))
    return (
        context.initialize_deadline(timeout_value)
        if context is not None
        else time.monotonic() + timeout_value
    )


def _remaining_pdf_timeout_seconds(
    context: RuntimeContext | None, deadline: float, *, maximum: int | float
) -> int:
    if context is not None:
        context.raise_if_cancelled()
    remaining = max(0.0, deadline - time.monotonic())
    if context is not None:
        clock = (
            context.browser_remaining_seconds
            if context.browser_deadline_monotonic == deadline
            else context.remaining_seconds
        )
        remaining = min(remaining, clock(float(maximum)))
    else:
        remaining = min(remaining, max(0.0, float(maximum)))
    if remaining <= 0:
        raise PdfFetchFailure(
            "pdf_fallback_timeout",
            "PDF fallback request deadline was exhausted.",
            details={"remaining_ms": 0},
        )
    return max(1, int(math.ceil(remaining)))


def _pdf_timeout_failure(
    timeout_seconds: int | float,
    started_at: float,
    base_details: Mapping[str, Any] | None = None,
) -> PdfFetchFailure:
    return PdfFetchFailure(
        "pdf_fallback_timeout",
        "PDF fallback request deadline was exhausted.",
        details={
            **dict(base_details or {}),
            "timeout_budget_ms": int(timeout_seconds * 1000),
            "elapsed_ms": round((time.monotonic() - started_at) * 1000, 3),
            "remaining_ms": 0,
        },
    )


def _with_timing_diagnostics(
    result: PdfFetchResult,
    *,
    budget_seconds: int | float,
    started_at: float,
    deadline: float,
    extra: Mapping[str, Any] | None = None,
) -> PdfFetchResult:
    return replace(
        result,
        diagnostics={
            **dict(result.diagnostics),
            **dict(extra or {}),
            "timeout_budget_ms": int(budget_seconds * 1000),
            "elapsed_ms": round((time.monotonic() - started_at) * 1000, 3),
            "remaining_ms": max(0, int((deadline - time.monotonic()) * 1000)),
        },
    )


def _pdf_failure_details_from_response(
    *,
    source_url: str,
    final_url: str,
    status: int | None,
    headers: Mapping[str, Any] | None,
    body: bytes | bytearray | None,
    error_category: str | None = None,
) -> dict[str, Any]:
    body_bytes = bytes(body or b"") if isinstance(body, bytes | bytearray) else b""
    title = html_title_snippet(body_bytes)
    summary = html_text_snippet(body_bytes)
    source_diag = diagnostic_url_payload(source_url)
    final_diag = diagnostic_url_payload(final_url)
    target_diag = diagnostic_url_payload(final_url or source_url)
    details: dict[str, Any] = {
        "candidate_url": redact_url_for_diagnostics(source_url),
        "source_url": redact_url_for_diagnostics(source_url),
        "final_url": redact_url_for_diagnostics(final_url),
        "candidate_url_sha256": source_diag.get("url_sha256"),
        "final_url_sha256": final_diag.get("url_sha256"),
        "host": target_diag.get("host"),
        "path": target_diag.get("path"),
        "status": status,
        "content_type": header_value(headers, "content-type"),
        "error_category": normalize_text(error_category),
        "title_snippet": redact_text_for_diagnostics(title),
        "body_snippet": redact_text_for_diagnostics(summary),
    }
    detected = detect_html_block(title, summary, status)
    if detected is not None:
        details["reason"] = detected.reason
        details["block_message"] = detected.message
    elif title or summary:
        lowered = normalize_text(f"{title} {summary}").lower()
        if "temporarily unavailable" in lowered or "temporary unavailable" in lowered:
            details["reason"] = "publisher_temporary_unavailable"
        elif "application performance management" in lowered or "apm" in lowered:
            details["reason"] = "publisher_access_challenge"
        else:
            details["reason"] = "non_pdf_html"
    return {key: value for key, value in details.items() if value not in (None, "")}


def _write_pdf_failure_html(
    artifact_dir: Path | None,
    body: bytes | bytearray | None,
    *,
    context: RuntimeContext | None = None,
    attempt_index: int | None = None,
) -> None:
    if artifact_dir is None or not isinstance(body, bytes | bytearray) or not body:
        return
    if context is not None:
        try:
            context.raise_if_cancelled()
            if (
                context.deadline_monotonic is not None
                and context.remaining_seconds() <= 0
            ):
                return
        except (RequestCancelledError, TimeoutError):
            return
    text = bytes(body).decode("utf-8", errors="replace")
    if "<html" not in text.lower() and "<!doctype html" not in text.lower():
        return
    with contextlib.suppress(OSError):
        artifact_dir.mkdir(parents=True, exist_ok=True)
        canonical_path = artifact_dir / "pdf.failure.html"
        if not canonical_path.exists():
            canonical_path.write_text(text, encoding="utf-8")
        if attempt_index is not None and 0 <= attempt_index < MAX_PDF_FAILURE_ARTIFACTS:
            (artifact_dir / f"pdf.failure.{attempt_index + 1:02d}.html").write_text(
                text, encoding="utf-8"
            )


def _default_port(scheme: str | None) -> int | None:
    normalized = normalize_text(scheme).lower()
    return 80 if normalized == "http" else 443 if normalized == "https" else None


def _same_origin(left: str | None, right: str | None) -> bool:
    left_url, right_url = normalize_text(left), normalize_text(right)
    if not left_url or not right_url:
        return False
    left_parsed = urllib.parse.urlparse(left_url)
    right_parsed = urllib.parse.urlparse(right_url)
    return (
        left_parsed.scheme.lower() == right_parsed.scheme.lower()
        and normalize_text(left_parsed.hostname).lower()
        == normalize_text(right_parsed.hostname).lower()
        and (left_parsed.port or _default_port(left_parsed.scheme))
        == (right_parsed.port or _default_port(right_parsed.scheme))
    )


def _response_content_length(headers: Mapping[str, Any] | None) -> int | None:
    try:
        parsed = int(header_value(headers, "content-length"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _browser_navigation_pdf_headers(
    *, user_agent: str | None, referer: str | None, target_url: str | None
) -> dict[str, str]:
    headers = {
        "User-Agent": normalize_text(user_agent)
        or DEFAULT_BROWSER_NAVIGATION_USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
        "Upgrade-Insecure-Requests": "1",
    }
    active_referer = normalize_text(referer)
    if active_referer:
        headers["Referer"] = active_referer
        headers["Sec-Fetch-Site"] = (
            "same-origin" if _same_origin(target_url, active_referer) else "cross-site"
        )
    else:
        headers["Sec-Fetch-Site"] = "none"
    return headers


def _enforce_pdf_byte_limit(
    byte_count: int,
    maximum_pdf_bytes: int,
    *,
    message: str,
    source_url: str,
    final_url: str,
    size_field: str = "pdf_bytes",
) -> None:
    if byte_count <= maximum_pdf_bytes:
        return
    raise PdfFetchFailure(
        "pdf_too_large",
        message,
        details={
            "source_url": redact_url_for_diagnostics(source_url),
            "final_url": redact_url_for_diagnostics(final_url),
            size_field: byte_count,
            "max_pdf_bytes": maximum_pdf_bytes,
        },
    )


def _finalize_pdf_bytes_result(
    *,
    pdf_bytes: bytes,
    bytes_transport: PdfBytesTransport | None,
    artifact_dir: Path | None,
    asset_profile: PdfAssetProfile = "none",
    asset_output_dir: Path | None = None,
    source_url: str,
    final_url: str,
    suggested_filename: str | None = None,
    allow_pdf_only: bool = False,
    expected_identity: Mapping[str, Any] | None = None,
    too_large_message: str = "PDF response exceeded the configured PDF limit.",
    maximum_pdf_bytes: int | None = None,
) -> PdfFetchResult:
    """Validate PDF byte ceiling once and delegate conversion/identity checks."""

    limit = pdf_max_bytes() if maximum_pdf_bytes is None else maximum_pdf_bytes
    _enforce_pdf_byte_limit(
        len(pdf_bytes),
        limit,
        message=too_large_message,
        source_url=source_url,
        final_url=final_url,
    )
    return pdf_fetch_result_from_bytes(
        artifact_dir=artifact_dir,
        asset_profile=asset_profile,
        asset_output_dir=asset_output_dir,
        source_url=source_url,
        final_url=final_url,
        pdf_bytes=pdf_bytes,
        bytes_transport=bytes_transport,
        suggested_filename=suggested_filename,
        allow_pdf_only=allow_pdf_only,
        expected_identity=expected_identity,
    )


def _response_to_pdf_result(
    response: Any,
    *,
    artifact_dir: Path,
    asset_profile: PdfAssetProfile = "none",
    asset_output_dir: Path | None = None,
    allow_pdf_only: bool = False,
    source_url: str,
    final_url: str,
    page: Any | None = None,
    request: PdfRequestContext = PdfRequestContext(),
) -> PdfFetchResult | None:
    if response is None:
        return None
    response_headers = response.headers or {}
    maximum_pdf_bytes = pdf_max_bytes()
    too_large_message = "Browser PDF response exceeded the configured PDF limit."
    declared_length = _response_content_length(response_headers)
    if declared_length is not None:
        _enforce_pdf_byte_limit(
            declared_length,
            maximum_pdf_bytes,
            message=too_large_message,
            source_url=source_url,
            final_url=final_url,
            size_field="declared_pdf_bytes",
        )
    try:
        response_body = response.body()
    except Exception as exc:
        raise PdfFetchFailure(
            "pdf_download_failed",
            f"Failed to read PDF fallback response body: {exc}",
            details={
                "source_url": redact_url_for_diagnostics(source_url),
                "final_url": redact_url_for_diagnostics(final_url),
            },
        ) from exc
    if not isinstance(response_body, bytes | bytearray):
        return None
    pdf_bytes = bytes(response_body)
    _enforce_pdf_byte_limit(
        len(pdf_bytes),
        maximum_pdf_bytes,
        message=too_large_message,
        source_url=source_url,
        final_url=final_url,
    )
    content_type = normalize_text(
        header_value(response_headers, "content-type")
    ).lower()
    if not looks_like_pdf_payload(content_type, pdf_bytes, final_url):
        return None
    resolved_final = (
        normalize_text(str(getattr(response, "url", "") or "")) or final_url
    )
    try:
        return _finalize_pdf_bytes_result(
            pdf_bytes=pdf_bytes,
            bytes_transport="browser_response",
            artifact_dir=artifact_dir,
            asset_profile=asset_profile,
            asset_output_dir=asset_output_dir,
            source_url=source_url,
            final_url=resolved_final,
            suggested_filename=filename_from_headers(response_headers),
            allow_pdf_only=allow_pdf_only,
            expected_identity=request.expected_identity,
            too_large_message=too_large_message,
            maximum_pdf_bytes=maximum_pdf_bytes,
        )
    except PdfFetchFailure as exc:
        propagate_paywall(exc)
        if exc.kind != "downloaded_file_not_pdf" or page is None:
            raise
        refetched = _refetch_pdf_with_browser_request(
            page,
            artifact_dir=artifact_dir,
            asset_profile=asset_profile,
            asset_output_dir=asset_output_dir,
            allow_pdf_only=allow_pdf_only,
            source_url=source_url,
            final_url=final_url,
            request=request,
        )
        if refetched is not None:
            return refetched
        raise


def _refetch_pdf_with_browser_request(
    page: Any,
    *,
    artifact_dir: Path,
    asset_profile: PdfAssetProfile = "none",
    asset_output_dir: Path | None = None,
    allow_pdf_only: bool = False,
    source_url: str,
    final_url: str,
    request: PdfRequestContext = PdfRequestContext(),
) -> PdfFetchResult | None:
    normalized_final = normalize_text(final_url)
    if not normalized_final:
        return None
    normalized_path = normalize_text(
        urllib.parse.urlparse(normalized_final).path
    ).lower()
    if not (
        normalized_path.endswith(".pdf")
        or "/doi/pdf/" in normalized_path
        or "/doi/epdf/" in normalized_path
        or "/pdf" in normalized_path
    ):
        return None

    maximum_pdf_bytes = pdf_max_bytes()
    too_large_message = "Browser request-context PDF exceeded the configured PDF limit."
    try:
        timeout_ms = (
            _remaining_pdf_timeout_seconds(
                request.runtime, request.deadline_monotonic, maximum=60
            )
            * 1000
            if request.deadline_monotonic is not None
            else 60000
        )
        response = context_get(
            page.context, normalized_final, timeout=timeout_ms, page=page
        )
        normalized_final = (
            normalize_text(str(getattr(response, "url", "") or "")) or normalized_final
        )
        headers = {
            str(key).lower(): str(value)
            for key, value in (response.headers or {}).items()
        }
        declared_length = _response_content_length(headers)
        if declared_length is not None:
            _enforce_pdf_byte_limit(
                declared_length,
                maximum_pdf_bytes,
                message=too_large_message,
                source_url=source_url,
                final_url=normalized_final,
                size_field="declared_pdf_bytes",
            )
        body = bytes(response.body())
    except PdfFetchFailure:
        raise
    except Exception as exc:
        propagate_paywall(exc)
        raise PdfFetchFailure(
            "pdf_download_failed",
            f"Failed to refetch PDF fallback response from browser request context: {exc}",
            details={
                "source_url": redact_url_for_diagnostics(source_url),
                "final_url": redact_url_for_diagnostics(normalized_final),
            },
        ) from exc

    _enforce_pdf_byte_limit(
        len(body),
        maximum_pdf_bytes,
        message=too_large_message,
        source_url=source_url,
        final_url=normalized_final,
    )
    content_type = normalize_text(headers.get("content-type")).lower()
    if not looks_like_pdf_payload(content_type, body, normalized_final):
        return None
    return _finalize_pdf_bytes_result(
        pdf_bytes=body,
        bytes_transport="browser_response",
        artifact_dir=artifact_dir,
        asset_profile=asset_profile,
        asset_output_dir=asset_output_dir,
        source_url=source_url,
        final_url=normalized_final,
        suggested_filename=filename_from_headers(headers),
        allow_pdf_only=allow_pdf_only,
        expected_identity=request.expected_identity,
        too_large_message=too_large_message,
        maximum_pdf_bytes=maximum_pdf_bytes,
    )


def _download_to_pdf_result(
    download: Any,
    *,
    artifact_dir: Path,
    asset_profile: PdfAssetProfile = "none",
    asset_output_dir: Path | None = None,
    allow_pdf_only: bool = False,
    source_url: str,
    final_url: str,
    expected_identity: Mapping[str, Any] | None = None,
) -> PdfFetchResult:
    download_path = artifact_dir / f".paper-fetch-browser-pdf-{uuid.uuid4().hex}.part"
    maximum_pdf_bytes = pdf_max_bytes()
    too_large_message = "Browser PDF download exceeded the configured PDF limit."
    try:
        download.save_as(str(download_path))
        try:
            downloaded_bytes = download_path.stat().st_size
        except OSError:
            downloaded_bytes = 0
        _enforce_pdf_byte_limit(
            downloaded_bytes,
            maximum_pdf_bytes,
            message=too_large_message,
            source_url=source_url,
            final_url=final_url,
        )
        resolved_final = (
            normalize_text(str(getattr(download, "url", "") or "")) or final_url
        )
        return _finalize_pdf_bytes_result(
            pdf_bytes=download_path.read_bytes(),
            bytes_transport="browser_download",
            artifact_dir=artifact_dir,
            asset_profile=asset_profile,
            asset_output_dir=asset_output_dir,
            source_url=source_url,
            final_url=resolved_final,
            suggested_filename=getattr(download, "suggested_filename", None),
            allow_pdf_only=allow_pdf_only,
            expected_identity=expected_identity,
            too_large_message=too_large_message,
            maximum_pdf_bytes=maximum_pdf_bytes,
        )
    finally:
        download_path.unlink(missing_ok=True)


def _playwright_pdf_error_types() -> tuple[Any, Any]:
    try:
        from playwright.sync_api import (
            Error as PlaywrightError,
        )
        from playwright.sync_api import (
            TimeoutError as PlaywrightTimeoutError,
        )
    except Exception as exc:  # pragma: no cover - missing dependency integration tests
        raise PdfFetchFailure(
            "missing_browser_runtime",
            "browser runtime is not installed; cannot use PDF fallback.",
        ) from exc
    return PlaywrightError, PlaywrightTimeoutError


def _initialize_pdf_browser_page(
    browser_context: Any,
    *,
    browser_cookies: list[dict[str, Any]] | None,
    seed_urls: list[str],
    request: PdfRequestContext,
) -> tuple[Any, PdfFetchFailure | None]:
    if browser_cookies:
        try:
            browser_context.add_cookies(browser_cookies)
        except Exception as exc:
            raise PdfFetchFailure(
                "invalid_browser_context_seed",
                f"Failed to seed browser-context PDF fallback with cookies: {exc}",
            ) from exc
    page = browser_context.new_page()
    try:
        return page, _seed_pdf_browser_page(page, seed_urls, request)
    except BaseException:
        with contextlib.suppress(Exception):
            page.close()
        raise


@dataclass(frozen=True)
class _BrowserPdfRun:
    candidate_urls: tuple[str, ...]
    artifact_dir: Path
    browser_config: BrowserRuntimeConfig
    asset_profile: PdfAssetProfile
    asset_output_dir: Path | None
    browser_cookies: list[dict[str, Any]]
    user_agent: str
    referer: str
    seed_urls: list[str]
    allow_pdf_only: bool
    request: PdfRequestContext
    started_monotonic: float
    budget_seconds: float
    expected_identity: Mapping[str, Any] | None

    @property
    def runtime(self) -> RuntimeContext | None:
        return self.request.runtime

    @property
    def deadline(self) -> float:
        assert self.request.deadline_monotonic is not None
        return self.request.deadline_monotonic

    def transport_or_default(self) -> HttpTransport:
        if self.runtime is not None and self.runtime.transport is not None:
            return self.runtime.transport
        return HttpTransport()

    def with_deadline(self, deadline: float) -> _BrowserPdfRun:
        return replace(self, request=self.request.with_deadline(deadline))


@dataclass(frozen=True)
class _BrowserPdfSession:
    browser_context: Any
    page: Any
    run: _BrowserPdfRun
    seed_failure: PdfFetchFailure | None


@dataclass(frozen=True)
class _IeeeStampOutcome:
    handled: bool = False
    initial_response: Any = None
    result: PdfFetchResult | None = None
    download: Any = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


def _try_seeded_http_pdf_preflight(
    run: _BrowserPdfRun,
) -> tuple[PdfFetchResult | None, PdfFetchFailure | None]:
    """Stage 1: Attempt direct browser-like HTTP PDF fetch before launching browser."""

    if (
        run.request.browser_only
        or not (run.browser_cookies or run.seed_urls)
        or run.browser_config.provider == "elsevier"
    ):
        return None, None
    seeded_referer = run.referer or (run.seed_urls[0] if run.seed_urls else "")
    http_headers = _browser_navigation_pdf_headers(
        user_agent=run.user_agent,
        referer=seeded_referer,
        target_url=run.candidate_urls[0] if run.candidate_urls else None,
    )
    try:
        result = fetch_pdf_over_http(
            run.transport_or_default(),
            list(run.candidate_urls),
            headers=http_headers,
            artifact_dir=run.artifact_dir,
            asset_profile=run.asset_profile,
            asset_output_dir=run.asset_output_dir,
            allow_pdf_only=run.allow_pdf_only,
            browser_cookies=list(run.browser_cookies),
            request=replace(
                run.request, timeout_seconds=DEFAULT_FULLTEXT_TIMEOUT_SECONDS
            ),
        )
        return result, None
    except PdfFetchFailure as exc:
        propagate_paywall(exc)
        return None, exc


@contextlib.contextmanager
def _pdf_browser_session(run: _BrowserPdfRun) -> Iterator[_BrowserPdfSession]:
    """Stage 2: Open browser context, warm ``seed_urls``, and own spawned pages."""

    manager = browser_context = page = None
    initial_pages: list[Any] = []
    try:
        remaining_seconds = _remaining_pdf_timeout_seconds(
            None, run.deadline, maximum=run.budget_seconds
        )
        launch_config = replace(
            run.browser_config, timeout_ms=max(1, int(remaining_seconds * 1000))
        )
        manager, browser_context = _open_pdf_browser_context(
            launch_config, runtime=run.runtime
        )
        active_deadline = (
            run.runtime.start_browser_budget(run.budget_seconds)
            if run.runtime is not None
            else time.monotonic() + run.budget_seconds
        )
        active_run = run.with_deadline(active_deadline)
        existing_pages = getattr(browser_context, "pages", None)
        if isinstance(existing_pages, list):
            initial_pages = list(existing_pages)

        page, seed_failure = _initialize_pdf_browser_page(
            browser_context,
            browser_cookies=active_run.browser_cookies,
            seed_urls=active_run.seed_urls,
            request=active_run.request,
        )
        yield _BrowserPdfSession(
            browser_context=browser_context,
            page=page,
            run=active_run,
            seed_failure=seed_failure,
        )
    finally:
        owned_pages = [page] if page is not None else []
        with contextlib.suppress(Exception):
            active_pages = getattr(browser_context, "pages", None)
            if isinstance(active_pages, list):
                owned_pages.extend(
                    candidate
                    for candidate in active_pages
                    if candidate is not page
                    and all(candidate is not previous for previous in initial_pages)
                )
        for owned_page in owned_pages:
            with contextlib.suppress(Exception):
                owned_page.close()
        if manager is not None:
            with contextlib.suppress(Exception):
                manager.close()


def _try_ieee_stamp_pdf_hook(
    run: _BrowserPdfRun,
    page: Any,
    url: str,
    *,
    goto_kwargs: Mapping[str, Any],
    download_timeout_ms: int,
    playwright_timeout_error: Any,
) -> _IeeeStampOutcome:
    """Stage 3: Resolve IEEE ``stamp.jsp`` wrapper iframe when applicable."""

    if run.browser_config.provider != "ieee" or not stamp_article_number(url):
        return _IeeeStampOutcome()

    diagnostics: dict[str, Any] = {}
    initial_response, iframe_response, download = navigate_stamp_pdf(
        page,
        url,
        goto_kwargs=dict(goto_kwargs),
        timeout_ms=download_timeout_ms,
        expected_identity=run.request.expected_identity,
        check_cancelled=(
            run.runtime.raise_if_cancelled if run.runtime is not None else None
        ),
        diagnostics=diagnostics,
    )
    if iframe_response is not None:

        def read_result(candidate: Any) -> PdfFetchResult | None:
            return _response_to_pdf_result(
                candidate,
                artifact_dir=run.artifact_dir,
                asset_profile=run.asset_profile,
                asset_output_dir=run.asset_output_dir,
                allow_pdf_only=run.allow_pdf_only,
                source_url=iframe_response.url,
                final_url=iframe_response.url,
                request=run.request,
            )

        _remaining_pdf_timeout_seconds(
            run.runtime, run.deadline, maximum=run.budget_seconds
        )
        try:
            result = read_result(iframe_response)
        except PdfFetchFailure as failure:
            if "Network.getResponseBody" not in str(failure.__cause__):
                raise
            timeout_ms = (
                _remaining_pdf_timeout_seconds(
                    run.runtime, run.deadline, maximum=run.budget_seconds
                )
                * 1000
            )
            with refetch_browser_response(
                page.context, iframe_response, timeout_ms=timeout_ms
            ) as refreshed:
                _remaining_pdf_timeout_seconds(
                    run.runtime, run.deadline, maximum=run.budget_seconds
                )
                result = read_result(refreshed)
                diagnostics["browser_pdf_refetched"] = True
        if result is not None:
            enriched = replace(
                result,
                diagnostics={
                    **dict(result.diagnostics),
                    "browser_pdf_response": (
                        "ieee_stamp_direct"
                        if iframe_response is initial_response
                        else "ieee_stamp_iframe"
                    ),
                    "wrapper_url": redact_url_for_diagnostics(url),
                    "iframe_url": redact_url_for_diagnostics(iframe_response.url),
                    "response_status": iframe_response.status,
                    **diagnostics,
                },
            )
            return _IeeeStampOutcome(
                handled=True,
                initial_response=initial_response,
                result=enriched,
                diagnostics=diagnostics,
            )
    if download is None:
        raise playwright_timeout_error("IEEE stamp iframe did not return a PDF.")
    return _IeeeStampOutcome(
        handled=True,
        initial_response=initial_response,
        download=download,
        diagnostics=diagnostics,
    )


def _await_browser_pdf_download(
    page: Any,
    url: str,
    *,
    goto_kwargs: Mapping[str, Any],
    download_timeout_ms: int,
    playwright_error: Any,
) -> tuple[Any, Any]:
    """Stage 4: Navigate to candidate URL while capturing browser download event."""

    initial_response = None
    with page.expect_download(timeout=download_timeout_ms) as download_info:
        try:
            initial_response = navigate_page(page, url, **goto_kwargs, mode="file")
        except playwright_error as exc:
            if "Download is starting" not in str(exc):
                raise
    return initial_response, download_info.value


def _export_context_cookies_for_url(
    browser_context: Any, base_url: str, fallback_cookies: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    try:
        context_cookies = browser_context.cookies([base_url])
    except TypeError:
        try:
            context_cookies = browser_context.cookies()
        except Exception:
            context_cookies = list(fallback_cookies)
    except Exception:
        context_cookies = list(fallback_cookies)
    return filter_browser_cookies_for_url(list(context_cookies or []), base_url)


def _recover_pdf_after_download_timeout(
    run: _BrowserPdfRun,
    browser_context: Any,
    page: Any,
    url: str,
    *,
    attempt_index: int,
    initial_response: Any,
    goto_kwargs: Mapping[str, Any],
) -> tuple[PdfFetchResult | None, PdfFetchFailure | None, bool]:
    """Stage 5: Recover via inline response/request refetch or exported-cookie HTTP."""

    response = initial_response
    if response is None:
        try:
            retry_timeout = (
                _remaining_pdf_timeout_seconds(run.runtime, run.deadline, maximum=60)
                * 1000
            )
            response = navigate_page(
                page,
                url,
                **{**dict(goto_kwargs), "timeout": retry_timeout},
                mode="file",
            )
        except PdfFetchFailure as exc:
            return None, exc, True
        except RequestCancelledError:
            raise
        except Exception:
            response = None

    if response is not None:
        try:
            pdf_result = _response_to_pdf_result(
                response,
                artifact_dir=run.artifact_dir,
                asset_profile=run.asset_profile,
                asset_output_dir=run.asset_output_dir,
                allow_pdf_only=run.allow_pdf_only,
                source_url=url,
                final_url=page.url,
                page=page,
                request=run.request,
            )
            if pdf_result is not None:
                return pdf_result, None, False
        except PdfFetchFailure as exc:
            propagate_paywall(exc)
            return None, exc, False

    title = normalize_text(page.title())
    html = page.content()
    raise_for_paywall(
        html,
        metadata=run.request.expected_identity,
        source_url=page.url,
        provider=run.request.provider_name,
    )

    current_url = normalize_text(page.url)
    parsed_current = urllib.parse.urlparse(current_url)
    html_base_url = (
        current_url
        if parsed_current.scheme in {"http", "https"}
        and normalize_text(parsed_current.netloc)
        else url
    )
    if not run.request.browser_only and run.browser_config.provider != "elsevier":
        http_retry_candidates = list(
            dict.fromkeys(
                normalized
                for candidate in [
                    urllib.parse.urljoin(html_base_url, url),
                    *extract_pdf_candidate_urls_from_html(html, html_base_url),
                ]
                if (normalized := normalize_text(candidate))
            )
        )
        context_cookies = _export_context_cookies_for_url(
            browser_context, html_base_url, run.browser_cookies
        )
        http_headers = _browser_navigation_pdf_headers(
            user_agent=run.user_agent,
            referer=run.referer or normalize_text(html_base_url),
            target_url=http_retry_candidates[0],
        )
        try:
            recovered = fetch_pdf_over_http(
                run.transport_or_default(),
                http_retry_candidates,
                headers=http_headers,
                artifact_dir=run.artifact_dir,
                asset_profile=run.asset_profile,
                asset_output_dir=run.asset_output_dir,
                allow_pdf_only=run.allow_pdf_only,
                browser_cookies=context_cookies,
                request=replace(
                    run.request, timeout_seconds=DEFAULT_FULLTEXT_TIMEOUT_SECONDS
                ),
            )
            return recovered, None, False
        except PdfFetchFailure as exc:
            propagate_paywall(exc)
            if exc.kind == "pdf_fallback_timeout":
                return None, exc, True

    summary = summarize_html(html)
    response_status, response_headers = _browser_response_metadata(response)
    detected = detect_html_block(title, summary, response_status)
    try:
        _capture_pdf_browser_failure(
            page,
            run.artifact_dir,
            html,
            attempt_index,
            run.request,
            browser_budget_seconds=run.budget_seconds,
        )
    except PdfFetchFailure as exc:
        return None, exc, True

    failure_details = _pdf_failure_details_from_response(
        source_url=url,
        final_url=page.url,
        status=response_status,
        headers=response_headers,
        body=html.encode("utf-8", errors="replace"),
    )
    failure = PdfFetchFailure(
        detected.reason if detected is not None else "pdf_download_not_triggered",
        (
            detected.message
            if detected is not None
            else "Browser context did not trigger a PDF download."
        ),
        details=failure_details
        or {
            "source_url": redact_url_for_diagnostics(url),
            "final_url": redact_url_for_diagnostics(page.url),
        },
    )
    return None, failure, False


def fetch_pdf_with_browser(
    candidate_urls: list[str],
    *,
    artifact_dir: Path,
    browser_config: BrowserRuntimeConfig,
    asset_profile: PdfAssetProfile = "none",
    asset_output_dir: Path | None = None,
    browser_cookies: list[dict[str, Any]] | None = None,
    browser_user_agent: str | None = None,
    referer: str | None = None,
    seed_urls: list[str] | None = None,
    allow_pdf_only: bool = False,
    request: PdfRequestContext = PdfRequestContext(),
) -> PdfFetchResult:
    if request.runtime is not None:
        request.runtime.raise_if_cancelled()
    route_request = _prepare_pdf_browser_route_request(
        request,
        browser_config=browser_config,
        provider_name=request.provider_name,
    )
    if not candidate_urls:
        raise PdfFetchFailure(
            "empty_pdf_attempts", "No PDF fallback candidates were attempted."
        )

    budget_seconds = route_request.timeout_seconds
    initial_deadline = time.monotonic() + budget_seconds
    _remaining_pdf_timeout_seconds(None, initial_deadline, maximum=budget_seconds)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    run = _BrowserPdfRun(
        candidate_urls=tuple(candidate_urls),
        artifact_dir=artifact_dir,
        browser_config=browser_config,
        asset_profile=asset_profile,
        asset_output_dir=asset_output_dir,
        browser_cookies=list(browser_cookies or []),
        user_agent=normalize_text(browser_user_agent),
        referer=normalize_text(referer),
        seed_urls=[
            normalize_text(url) for url in seed_urls or [] if normalize_text(url)
        ],
        allow_pdf_only=allow_pdf_only,
        request=route_request.request.with_deadline(initial_deadline),
        started_monotonic=route_request.started_monotonic,
        budget_seconds=budget_seconds,
        expected_identity=request.expected_identity,
    )

    preflight_result, last_failure = _try_seeded_http_pdf_preflight(run)
    if preflight_result is not None:
        return preflight_result

    run = run.with_deadline(time.monotonic() + budget_seconds)
    playwright_error, playwright_timeout_error = _playwright_pdf_error_types()

    with _pdf_browser_session(run) as session:
        active_run, page = session.run, session.page
        last_failure = session.seed_failure or last_failure

        for attempt_index, url in enumerate(active_run.candidate_urls):
            if active_run.runtime is not None:
                active_run.runtime.raise_if_cancelled()
            try:
                goto_timeout_ms = (
                    _remaining_pdf_timeout_seconds(
                        active_run.runtime, active_run.deadline, maximum=60
                    )
                    * 1000
                )
                download_timeout_ms = (
                    _remaining_pdf_timeout_seconds(
                        active_run.runtime, active_run.deadline, maximum=30
                    )
                    * 1000
                )
            except PdfFetchFailure as exc:
                last_failure = exc
                break

            goto_kwargs: dict[str, Any] = {
                "wait_until": "domcontentloaded",
                "timeout": goto_timeout_ms,
                **({"referer": active_run.referer} if active_run.referer else {}),
            }
            initial_response = None
            try:
                stamp_outcome = _try_ieee_stamp_pdf_hook(
                    active_run,
                    page,
                    url,
                    goto_kwargs=goto_kwargs,
                    download_timeout_ms=download_timeout_ms,
                    playwright_timeout_error=playwright_timeout_error,
                )
                if stamp_outcome.result is not None:
                    return stamp_outcome.result
                initial_response = stamp_outcome.initial_response
                if stamp_outcome.handled:
                    download = stamp_outcome.download
                    extra_diagnostics = stamp_outcome.diagnostics
                else:
                    initial_response, download = _await_browser_pdf_download(
                        page,
                        url,
                        goto_kwargs=goto_kwargs,
                        download_timeout_ms=download_timeout_ms,
                        playwright_error=playwright_error,
                    )
                    extra_diagnostics = {}
            except playwright_timeout_error:
                recovered, failure, should_stop = _recover_pdf_after_download_timeout(
                    active_run,
                    session.browser_context,
                    page,
                    url,
                    attempt_index=attempt_index,
                    initial_response=initial_response,
                    goto_kwargs=goto_kwargs,
                )
                if recovered is not None:
                    return recovered
                if failure is not None:
                    last_failure = failure
                if should_stop:
                    break
                continue
            except PdfFetchFailure as exc:
                propagate_paywall(exc)
                last_failure = exc
                if exc.kind == "pdf_fallback_timeout":
                    break
                continue
            except RequestCancelledError:
                raise
            except Exception as exc:
                propagate_paywall(exc)
                last_failure = PdfFetchFailure(
                    "pdf_download_failed",
                    f"Failed to trigger PDF fallback download: {exc}",
                    details={
                        "source_url": redact_url_for_diagnostics(url),
                        "source_url_sha256": diagnostic_url_payload(url).get(
                            "url_sha256"
                        ),
                    },
                )
                continue

            try:
                _remaining_pdf_timeout_seconds(
                    active_run.runtime,
                    active_run.deadline,
                    maximum=active_run.budget_seconds,
                )
                result = _download_to_pdf_result(
                    download,
                    artifact_dir=active_run.artifact_dir,
                    asset_profile=active_run.asset_profile,
                    asset_output_dir=active_run.asset_output_dir,
                    allow_pdf_only=active_run.allow_pdf_only,
                    source_url=download.url if extra_diagnostics else url,
                    final_url=download.url if extra_diagnostics else page.url,
                    expected_identity=active_run.expected_identity,
                )
                return _with_timing_diagnostics(
                    result,
                    budget_seconds=active_run.budget_seconds,
                    started_at=active_run.started_monotonic,
                    deadline=active_run.deadline,
                    extra=extra_diagnostics,
                )
            except PdfFetchFailure as exc:
                propagate_paywall(exc)
                last_failure = exc
                if exc.kind == "pdf_fallback_timeout":
                    break
                continue

    if last_failure is None:
        last_failure = PdfFetchFailure(
            "empty_pdf_attempts", "No PDF fallback candidates were attempted."
        )
    raise last_failure


def fetch_pdf_over_http(
    transport: HttpTransport,
    candidate_urls: list[str],
    *,
    headers: Mapping[str, str] | None = None,
    artifact_dir: Path | None = None,
    asset_profile: PdfAssetProfile = "none",
    asset_output_dir: Path | None = None,
    allow_pdf_only: bool = False,
    browser_cookies: list[dict[str, Any]] | None = None,
    request: PdfRequestContext = PdfRequestContext(),
) -> PdfFetchResult:
    if not candidate_urls:
        raise PdfFetchFailure(
            "empty_pdf_attempts", "No PDF fallback candidates were attempted."
        )

    timeout = request.timeout_seconds
    context = request.runtime
    request_started_at = time.monotonic()
    request_deadline = _pdf_deadline(context, timeout)
    request_headers = {"Accept": PDF_ACCEPT_HEADER, **dict(headers or {})}
    maximum_pdf_bytes = pdf_max_bytes()
    route_policy = _compile_pdf_direct_route_policy(
        request, maximum_pdf_bytes=maximum_pdf_bytes
    )
    last_failure: PdfFetchFailure | None = None
    download_ns = 0

    for attempt_index, url in enumerate(candidate_urls):
        try:
            active_timeout = _remaining_pdf_timeout_seconds(
                context, request_deadline, maximum=timeout
            )
        except PdfFetchFailure as exc:
            last_failure = exc
            break
        per_request_headers = dict(request_headers)
        cookie_header = _cookie_header_for_url(browser_cookies, url)
        if cookie_header:
            per_request_headers["Cookie"] = cookie_header
        request_policy = replace(
            route_policy.request_policy,
            timeout_seconds=active_timeout,
            max_response_bytes=maximum_pdf_bytes,
            max_compressed_response_bytes=maximum_pdf_bytes,
        )
        download_started_at = time.perf_counter_ns()
        try:
            response = transport.request(
                "GET",
                url,
                headers=per_request_headers,
                timeout=active_timeout,
                retry_on_transient=True,
                request_policy=request_policy,
            )
        except RequestFailure as exc:
            download_ns += time.perf_counter_ns() - download_started_at
            error_url = str(exc.url or url)
            raise_for_api_entitlement(
                exc.body,
                source_url=error_url,
                provider=request.provider_name or "",
                headers=exc.headers,
            )
            raise_for_paywall(
                exc.body,
                metadata=request.expected_identity,
                source_url=error_url,
                provider=request.provider_name,
            )
            details = _pdf_failure_details_from_response(
                source_url=url,
                final_url=error_url,
                status=exc.status_code,
                headers=exc.headers,
                body=exc.body,
                error_category=str(exc.error_category or ""),
            )
            _write_pdf_failure_html(
                artifact_dir, exc.body, context=context, attempt_index=attempt_index
            )
            last_failure = PdfFetchFailure(
                "pdf_download_failed",
                f"Failed to download PDF fallback candidate: {exc}",
                details=details or {"source_url": url},
            )
            if time.monotonic() >= request_deadline:
                last_failure = _pdf_timeout_failure(
                    timeout, request_started_at, last_failure.details
                )
                break
            continue

        download_ns += time.perf_counter_ns() - download_started_at
        try:
            _remaining_pdf_timeout_seconds(context, request_deadline, maximum=timeout)
        except PdfFetchFailure as exc:
            last_failure = exc
            break

        final_url = str(response.get("url") or url)
        raw_body = response.get("body") or b""
        body_bytes = bytes(raw_body) if isinstance(raw_body, bytes | bytearray) else b""
        response_headers = response.get("headers") or {}
        if not body_bytes.startswith(b"%PDF-"):
            raise_for_api_entitlement(
                body_bytes,
                source_url=final_url,
                provider=request.provider_name or "",
                headers=response_headers,
            )
            raise_for_paywall(
                body_bytes,
                metadata=request.expected_identity,
                source_url=final_url,
                provider=request.provider_name,
            )

        content_type = header_value(response_headers, "content-type")
        if not isinstance(raw_body, bytes | bytearray) or not looks_like_pdf_payload(
            content_type, body_bytes, final_url
        ):
            _write_pdf_failure_html(
                artifact_dir, body_bytes, context=context, attempt_index=attempt_index
            )
            last_failure = PdfFetchFailure(
                "downloaded_file_not_pdf",
                "Direct PDF fallback candidate did not return a PDF file.",
                details=_pdf_failure_details_from_response(
                    source_url=url,
                    final_url=final_url,
                    status=int(response.get("status_code") or 0) or None,
                    headers=response_headers,
                    body=body_bytes,
                ),
            )
            continue

        try:
            result = _finalize_pdf_bytes_result(
                pdf_bytes=body_bytes,
                bytes_transport="http",
                artifact_dir=artifact_dir,
                asset_profile=asset_profile,
                asset_output_dir=asset_output_dir,
                source_url=url,
                final_url=final_url,
                suggested_filename=filename_from_headers(response_headers),
                allow_pdf_only=allow_pdf_only,
                expected_identity=request.expected_identity,
                maximum_pdf_bytes=maximum_pdf_bytes,
            )
            return _with_timing_diagnostics(
                result,
                budget_seconds=timeout,
                started_at=request_started_at,
                deadline=request_deadline,
                extra={"download_ms": round(download_ns / 1_000_000, 3)},
            )
        except PdfFetchFailure as exc:
            propagate_paywall(exc)
            last_failure = exc
            if time.monotonic() >= request_deadline:
                last_failure = _pdf_timeout_failure(
                    timeout, request_started_at, exc.details
                )
                break
            continue

    if last_failure is None:
        last_failure = PdfFetchFailure(
            "empty_pdf_attempts", "No PDF fallback candidates were attempted."
        )
    raise last_failure


__all__ = [
    "DEFAULT_BROWSER_NAVIGATION_USER_AGENT",
    "MAX_PDF_FAILURE_ARTIFACTS",
    "MAX_PDF_FAILURE_SCREENSHOT_BYTES",
    "PdfFallbackStrategy",
    "PdfFetchFailure",
    "PdfFetchResult",
    "PdfRequestContext",
    "fetch_pdf_over_http",
    "fetch_pdf_with_browser",
]
