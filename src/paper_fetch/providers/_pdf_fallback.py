"""PDF fallback helpers for browser-workflow and direct-HTTP providers."""

from __future__ import annotations

import math
import os
import shutil
import tempfile
import time
import urllib.parse
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from collections.abc import Callable, Mapping

from ..http import (
    DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
    HttpRequestPolicy,
    HttpStreamOptions,
    HttpTransport,
    PDF_ACCEPT_HEADER,
    RequestCancelledError,
    RequestFailure,
    diagnostic_url_payload,
    provider_request_policy,
    redact_text_for_diagnostics,
    redact_url_for_diagnostics,
)
from ..artifacts import ArtifactStore
from ..http.headers import header_value
from ..extraction.html.assets.requester import (
    build_cookie_seeded_opener as _build_cookie_seeded_opener,
    cookie_header_for_url as _cookie_header_for_url,
    request_with_opener as _request_with_opener,
)
from ..extraction.html.shared import html_text_snippet, html_title_snippet
from ..extraction.html.signals import detect_html_block, summarize_html
from ..runtime import RuntimeContext
from ..provider_catalog import compile_route_execution_policy_for_kind
from ..utils import normalize_text
from ._pdf_candidates import extract_pdf_candidate_urls_from_html
from ._pdf_common import (
    PdfAssetProfile,
    PdfFetchFailure,
    PdfFetchResult,
    filename_from_headers,
    looks_like_pdf_payload,
    pdf_fetch_result_from_bytes,
    pdf_max_bytes,
    sanitize_storage_state,
)
from .browser_runtime.seed import filter_browser_cookies_for_url
from .browser_runtime.context import open_browser_context
from .browser_runtime.types import BrowserRuntimeConfig
import contextlib

PdfFallbackResult = PdfFetchResult
PdfFallbackFailure = PdfFetchFailure

DEFAULT_BROWSER_NAVIGATION_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
)
MAX_PDF_FAILURE_ARTIFACTS = 5
MAX_PDF_FAILURE_SCREENSHOT_BYTES = 16 * 1024 * 1024


def _transport_cancelled(transport: HttpTransport) -> bool:
    cancel_check = getattr(transport, "_cancel_check", None)
    return bool(callable(cancel_check) and cancel_check())


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
        if self.fetcher is not None and self.fetcher is not fetch_pdf_over_http:
            return self.fetcher(
                self.transport,
                candidate_urls,
                headers=self.headers,
                artifact_dir=self.artifact_dir,
                asset_profile=self.asset_profile,
                asset_output_dir=self.asset_output_dir,
                seed_urls=self.seed_urls,
                browser_cookies=self.browser_cookies,
                allow_pdf_only=self.allow_pdf_only,
                timeout=self.timeout,
                expected_identity=self.expected_identity,
                context=self.context,
            )
        try:
            execution_policy = (
                compile_route_execution_policy_for_kind(
                    self.provider_name, "pdf", prefer_transport="http"
                )
                if self.provider_name
                else None
            )
        except ValueError:
            execution_policy = None
        # Provider-owned production routes are governed solely by the catalog
        # compiler. ``self.timeout`` remains the compatibility budget for an
        # injected/generic fetcher where no provider route can be identified.
        effective_timeout = (
            execution_policy.timeout_seconds
            if execution_policy is not None
            else self.timeout
        )
        return fetch_pdf_over_http(
            self.transport,
            candidate_urls,
            headers=self.headers,
            artifact_dir=self.artifact_dir,
            asset_profile=self.asset_profile,
            asset_output_dir=self.asset_output_dir,
            seed_urls=self.seed_urls,
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

    def with_deadline(self, deadline: float) -> PdfRequestContext:
        return replace(self, deadline_monotonic=deadline)

    def with_provider(self, provider_name: str | None) -> PdfRequestContext:
        normalized = normalize_text(provider_name).lower() or None
        return replace(self, provider_name=normalized)


@dataclass(frozen=True)
class _PdfBrowserRouteRequest:
    """Compiled browser route and deadline state for one PDF attempt."""

    provider_name: str
    timeout_seconds: float
    allowed_hosts: tuple[str, ...]
    request: PdfRequestContext
    started_monotonic: float
    deadline_monotonic: float


@dataclass(frozen=True)
class _PdfDirectRoutePolicy:
    """Compiled direct route values consumed by the shared PDF transport."""

    provider_name: str | None
    route_name: str | None
    request_policy: HttpRequestPolicy


def _prepare_pdf_browser_route_request(
    request: PdfRequestContext,
    *,
    browser_config: BrowserRuntimeConfig | None,
    provider_name: str | None,
) -> _PdfBrowserRouteRequest:
    """Compile route timeout and bind explicit host policy to the request."""

    active_provider_name = normalize_text(
        browser_config.provider
        if browser_config is not None
        else provider_name or request.provider_name or ""
    ).lower()
    timeout_seconds = (
        max(0.001, float(browser_config.timeout_ms) / 1000.0)
        if browser_config is not None
        else float(DEFAULT_FULLTEXT_TIMEOUT_SECONDS)
    )
    execution_policy = None
    if active_provider_name:
        with contextlib.suppress(ValueError):
            execution_policy = compile_route_execution_policy_for_kind(
                active_provider_name,
                "pdf",
                prefer_transport="browser",
            )
    if execution_policy is not None:
        timeout_seconds = min(
            timeout_seconds,
            float(execution_policy.timeout_seconds),
        )
    allowed_hosts = tuple(request.allowed_hosts or ())
    started_monotonic = time.monotonic()
    deadline_monotonic = request.deadline_monotonic or _pdf_deadline(
        request.runtime,
        timeout_seconds,
    )
    active_request = request.with_provider(active_provider_name).with_deadline(
        deadline_monotonic
    )
    return _PdfBrowserRouteRequest(
        provider_name=active_provider_name,
        timeout_seconds=timeout_seconds,
        allowed_hosts=allowed_hosts,
        request=active_request,
        started_monotonic=started_monotonic,
        deadline_monotonic=deadline_monotonic,
    )


def _compile_pdf_direct_route_policy(
    request: PdfRequestContext,
    *,
    maximum_pdf_bytes: int,
) -> _PdfDirectRoutePolicy:
    provider_name = normalize_text(request.provider_name).lower() or None
    route_name: str | None = None
    if provider_name:
        with contextlib.suppress(ValueError):
            route_name = compile_route_execution_policy_for_kind(
                provider_name,
                "pdf",
                prefer_transport="http",
            ).route
    generic_policy = HttpRequestPolicy(
        allowed_hosts=request.allowed_hosts,
        max_response_bytes=maximum_pdf_bytes,
        max_compressed_response_bytes=maximum_pdf_bytes,
        timeout_seconds=max(1, int(math.ceil(request.timeout_seconds))),
        retry_on_transient=True,
    )
    request_policy = (
        provider_request_policy(provider_name, route_name, base=generic_policy)
        if provider_name and route_name
        else generic_policy
    )
    return _PdfDirectRoutePolicy(
        provider_name=provider_name,
        route_name=route_name,
        request_policy=request_policy,
    )


@dataclass(frozen=True)
class _PdfBrowserLaunch:
    runtime: RuntimeContext | None
    browser_config: BrowserRuntimeConfig


def _open_pdf_browser_context(
    launch: _PdfBrowserLaunch,
    *,
    sanitized_storage_state_path: Path | None,
    capability_storage_state_path: Path | None = None,
) -> tuple[Any | None, Any]:
    active_config = replace(
        launch.browser_config,
        storage_state_path=sanitized_storage_state_path,
        persist_storage_state=False,
        capability_storage_state_path=(
            capability_storage_state_path
            or launch.browser_config.capability_storage_state_path
            or launch.browser_config.storage_state_path
        ),
    )
    return open_browser_context(
        active_config,
        runtime_context=launch.runtime,
    )


def _seed_pdf_browser_page(
    page: Any,
    seed_urls: list[str] | None,
    request: PdfRequestContext,
) -> PdfFallbackFailure | None:
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
                _remaining_pdf_timeout_seconds(
                    request.runtime,
                    deadline,
                    maximum=60,
                )
                * 1000
            )
            page.goto(
                seed_url,
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
        except PdfFallbackFailure as exc:
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
        request.runtime,
        deadline,
        maximum=browser_budget_seconds,
    )
    _write_pdf_failure_html(
        artifact_dir,
        html.encode("utf-8", errors="replace"),
        context=request.runtime,
        attempt_index=attempt_index,
    )
    try:
        _remaining_pdf_timeout_seconds(
            request.runtime,
            deadline,
            maximum=5,
        )
    except PdfFallbackFailure:
        return
    with contextlib.suppress(Exception):
        canonical_screenshot = artifact_dir / "pdf.failure.png"
        screenshot_path = artifact_dir / f"pdf.failure.{attempt_index + 1:02d}.png"
        if attempt_index < MAX_PDF_FAILURE_ARTIFACTS:
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
                        staging,
                        canonical_screenshot,
                        overwrite=False,
                    )
                finally:
                    staging.unlink(missing_ok=True)


def _pdf_deadline(
    context: RuntimeContext | None,
    timeout_seconds: int | float,
) -> float:
    timeout_value = max(0.0, float(timeout_seconds))
    if context is not None:
        return context.initialize_deadline(timeout_value)
    return time.monotonic() + timeout_value


def _remaining_pdf_timeout_seconds(
    context: RuntimeContext | None,
    deadline: float,
    *,
    maximum: int | float,
) -> int:
    if context is not None:
        context.raise_if_cancelled()
    remaining = max(0.0, deadline - time.monotonic())
    if context is not None:
        remaining = min(remaining, context.remaining_seconds(float(maximum)))
    else:
        remaining = min(remaining, max(0.0, float(maximum)))
    if remaining <= 0:
        raise PdfFallbackFailure(
            "pdf_fallback_timeout",
            "PDF fallback request deadline was exhausted.",
            details={"remaining_ms": 0},
        )
    return max(1, int(math.ceil(remaining)))


def _pdf_cancelled(
    context: RuntimeContext | None,
    transport: HttpTransport,
) -> bool:
    return bool(
        (context is not None and context.cancelled) or _transport_cancelled(transport)
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
    body_bytes = bytes(body or b"") if isinstance(body, (bytes, bytearray)) else b""
    content_type = header_value(headers, "content-type")
    title = html_title_snippet(body_bytes)
    summary = html_text_snippet(body_bytes)
    details: dict[str, Any] = {
        "candidate_url": redact_url_for_diagnostics(source_url),
        "source_url": redact_url_for_diagnostics(source_url),
        "final_url": redact_url_for_diagnostics(final_url),
        "candidate_url_sha256": diagnostic_url_payload(source_url).get("url_sha256"),
        "final_url_sha256": diagnostic_url_payload(final_url).get("url_sha256"),
        "host": diagnostic_url_payload(final_url or source_url).get("host"),
        "path": diagnostic_url_payload(final_url or source_url).get("path"),
        "status": status,
        "content_type": content_type,
        "error_category": normalize_text(error_category),
        "title_snippet": redact_text_for_diagnostics(title),
        "body_snippet": redact_text_for_diagnostics(summary),
    }
    detected = detect_html_block(title, summary, status)
    if detected is not None:
        details["reason"] = detected.reason
        details["block_message"] = detected.message
    elif title or summary:
        lowered = normalize_text(" ".join([title, summary])).lower()
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
    if artifact_dir is None or not isinstance(body, (bytes, bytearray)) or not body:
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
    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        canonical_path = artifact_dir / "pdf.failure.html"
        if not canonical_path.exists():
            canonical_path.write_text(text, encoding="utf-8")
        if attempt_index is not None and 0 <= attempt_index < MAX_PDF_FAILURE_ARTIFACTS:
            (artifact_dir / f"pdf.failure.{attempt_index + 1:02d}.html").write_text(
                text,
                encoding="utf-8",
            )
    except OSError:
        return


def _same_origin(left: str | None, right: str | None) -> bool:
    left_url = normalize_text(left)
    right_url = normalize_text(right)
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


def _default_port(scheme: str | None) -> int | None:
    normalized = normalize_text(scheme).lower()
    if normalized == "http":
        return 80
    if normalized == "https":
        return 443
    return None


def _response_content_length(headers: Mapping[str, Any] | None) -> int | None:
    raw_value = header_value(headers, "content-length")
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _browser_navigation_pdf_headers(
    *,
    user_agent: str | None,
    referer: str | None,
    target_url: str | None,
) -> dict[str, str]:
    """Return browser-navigation headers for direct public PDF requests."""

    active_user_agent = (
        normalize_text(user_agent) or DEFAULT_BROWSER_NAVIGATION_USER_AGENT
    )
    headers = {
        "User-Agent": active_user_agent,
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
    response_headers = response.headers if response is not None else {}
    content_type = normalize_text(
        str(response_headers.get("content-type") or "")
    ).lower()
    maximum_pdf_bytes = pdf_max_bytes()
    declared_length = _response_content_length(response_headers)
    if declared_length is not None and declared_length > maximum_pdf_bytes:
        raise PdfFallbackFailure(
            "pdf_too_large",
            "Browser PDF response exceeded the configured PDF limit.",
            details={
                "source_url": redact_url_for_diagnostics(source_url),
                "final_url": redact_url_for_diagnostics(final_url),
                "declared_pdf_bytes": declared_length,
                "max_pdf_bytes": maximum_pdf_bytes,
            },
        )
    try:
        response_body = response.body()
    except Exception as exc:
        raise PdfFallbackFailure(
            "pdf_download_failed",
            f"Failed to read PDF fallback response body: {exc}",
            details={
                "source_url": redact_url_for_diagnostics(source_url),
                "final_url": redact_url_for_diagnostics(final_url),
            },
        ) from exc
    if not isinstance(response_body, (bytes, bytearray)):
        return None
    response_body = bytes(response_body)
    if len(response_body) > maximum_pdf_bytes:
        raise PdfFallbackFailure(
            "pdf_too_large",
            "Browser PDF response exceeded the configured PDF limit.",
            details={
                "source_url": redact_url_for_diagnostics(source_url),
                "final_url": redact_url_for_diagnostics(final_url),
                "pdf_bytes": len(response_body),
                "max_pdf_bytes": maximum_pdf_bytes,
            },
        )
    if not looks_like_pdf_payload(content_type, response_body, final_url):
        return None
    try:
        return pdf_fetch_result_from_bytes(
            artifact_dir=artifact_dir,
            asset_profile=asset_profile,
            asset_output_dir=asset_output_dir,
            source_url=source_url,
            final_url=final_url,
            pdf_bytes=response_body,
            suggested_filename=filename_from_headers(response_headers),
            allow_pdf_only=allow_pdf_only,
            expected_identity=request.expected_identity,
        )
    except PdfFallbackFailure as exc:
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
    normalized_final_url = normalize_text(final_url)
    if not normalized_final_url:
        return None
    parsed = urllib.parse.urlparse(normalized_final_url)
    normalized_path = normalize_text(parsed.path).lower()
    if not (
        normalized_path.endswith(".pdf")
        or "/doi/pdf/" in normalized_path
        or "/doi/epdf/" in normalized_path
        or "/pdf" in normalized_path
    ):
        return None
    try:
        timeout_ms = 60000
        if request.deadline_monotonic is not None:
            timeout_ms = (
                _remaining_pdf_timeout_seconds(
                    request.runtime,
                    request.deadline_monotonic,
                    maximum=60,
                )
                * 1000
            )
        response = page.request.get(normalized_final_url, timeout=timeout_ms)
        headers = {
            str(key).lower(): str(value)
            for key, value in (response.headers or {}).items()
        }
        maximum_pdf_bytes = pdf_max_bytes()
        declared_length = _response_content_length(headers)
        if declared_length is not None and declared_length > maximum_pdf_bytes:
            raise PdfFallbackFailure(
                "pdf_too_large",
                "Browser request-context PDF exceeded the configured PDF limit.",
                details={
                    "source_url": redact_url_for_diagnostics(source_url),
                    "final_url": redact_url_for_diagnostics(normalized_final_url),
                    "declared_pdf_bytes": declared_length,
                    "max_pdf_bytes": maximum_pdf_bytes,
                },
            )
        body = response.body()
    except PdfFallbackFailure:
        raise
    except Exception as exc:
        raise PdfFallbackFailure(
            "pdf_download_failed",
            f"Failed to refetch PDF fallback response from browser request context: {exc}",
            details={
                "source_url": redact_url_for_diagnostics(source_url),
                "final_url": redact_url_for_diagnostics(normalized_final_url),
            },
        ) from exc
    content_type = normalize_text(str(headers.get("content-type") or "")).lower()
    if len(body) > maximum_pdf_bytes:
        raise PdfFallbackFailure(
            "pdf_too_large",
            "Browser request-context PDF exceeded the configured PDF limit.",
            details={
                "source_url": redact_url_for_diagnostics(source_url),
                "final_url": redact_url_for_diagnostics(normalized_final_url),
                "pdf_bytes": len(body),
                "max_pdf_bytes": maximum_pdf_bytes,
            },
        )
    if not looks_like_pdf_payload(content_type, body, normalized_final_url):
        return None
    return pdf_fetch_result_from_bytes(
        artifact_dir=artifact_dir,
        asset_profile=asset_profile,
        asset_output_dir=asset_output_dir,
        source_url=source_url,
        final_url=normalized_final_url,
        pdf_bytes=body,
        suggested_filename=filename_from_headers(headers),
        allow_pdf_only=allow_pdf_only,
        expected_identity=request.expected_identity,
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
    try:
        download.save_as(str(download_path))
        try:
            downloaded_bytes = download_path.stat().st_size
        except OSError:
            downloaded_bytes = 0
        if downloaded_bytes > maximum_pdf_bytes:
            raise PdfFallbackFailure(
                "pdf_too_large",
                "Browser PDF download exceeded the configured PDF limit.",
                details={
                    "source_url": redact_url_for_diagnostics(source_url),
                    "final_url": redact_url_for_diagnostics(final_url),
                    "pdf_bytes": downloaded_bytes,
                    "max_pdf_bytes": maximum_pdf_bytes,
                },
            )
        return pdf_fetch_result_from_bytes(
            artifact_dir=artifact_dir,
            asset_profile=asset_profile,
            asset_output_dir=asset_output_dir,
            source_url=source_url,
            final_url=final_url,
            pdf_bytes=download_path.read_bytes(),
            suggested_filename=getattr(download, "suggested_filename", None),
            allow_pdf_only=allow_pdf_only,
            expected_identity=expected_identity,
        )
    finally:
        download_path.unlink(missing_ok=True)


def _playwright_pdf_error_types() -> tuple[Any, Any]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    except (
        Exception
    ) as exc:  # pragma: no cover - exercised by missing dependency integration tests
        raise PdfFallbackFailure(
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
) -> tuple[Any, PdfFallbackFailure | None]:
    if browser_cookies:
        try:
            browser_context.add_cookies(browser_cookies)
        except Exception as exc:
            raise PdfFallbackFailure(
                "invalid_browser_context_seed",
                f"Failed to seed browser-context PDF fallback with cookies: {exc}",
            ) from exc

    page = browser_context.new_page()
    return page, _seed_pdf_browser_page(page, seed_urls, request)


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
) -> PdfFallbackResult:
    context = request.runtime
    if context is not None:
        context.raise_if_cancelled()
    route_request = _prepare_pdf_browser_route_request(
        request,
        browser_config=browser_config,
        provider_name=request.provider_name,
    )
    browser_budget_seconds = route_request.timeout_seconds
    request_started_at = route_request.started_monotonic
    request_deadline = route_request.deadline_monotonic
    active_request = route_request.request
    if not candidate_urls:
        raise PdfFallbackFailure(
            "empty_pdf_attempts", "No PDF fallback candidates were attempted."
        )

    _remaining_pdf_timeout_seconds(
        context, request_deadline, maximum=browser_budget_seconds
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    last_failure: PdfFallbackFailure | None = None
    sanitized_storage_state_path: Path | None = None
    active_user_agent = normalize_text(browser_user_agent)
    normalized_seed_urls = [
        normalize_text(url) for url in seed_urls or [] if normalize_text(url)
    ]
    seeded_referer = normalize_text(referer) or (
        normalized_seed_urls[0] if normalized_seed_urls else ""
    )

    if browser_cookies or normalized_seed_urls:
        http_headers = _browser_navigation_pdf_headers(
            user_agent=active_user_agent,
            referer=seeded_referer,
            target_url=candidate_urls[0] if candidate_urls else None,
        )
        try:
            return fetch_pdf_over_http(
                context.transport
                if context is not None and context.transport is not None
                else HttpTransport(),
                candidate_urls,
                headers=http_headers,
                artifact_dir=artifact_dir,
                asset_profile=asset_profile,
                asset_output_dir=asset_output_dir,
                allow_pdf_only=allow_pdf_only,
                seed_urls=normalized_seed_urls,
                browser_cookies=list(browser_cookies or []),
                request=replace(
                    active_request,
                    timeout_seconds=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                ),
            )
        except PdfFallbackFailure as exc:
            last_failure = exc

    PlaywrightError, PlaywrightTimeoutError = _playwright_pdf_error_types()

    if browser_config.storage_state_path is not None:
        sanitized_storage_state_path = sanitize_storage_state(
            browser_config.storage_state_path
        )

    manager = None
    browser_context = None
    try:
        manager, browser_context = _open_pdf_browser_context(
            _PdfBrowserLaunch(
                runtime=context,
                browser_config=browser_config,
            ),
            sanitized_storage_state_path=sanitized_storage_state_path,
            capability_storage_state_path=browser_config.storage_state_path,
        )

        page, seed_failure = _initialize_pdf_browser_page(
            browser_context,
            browser_cookies=browser_cookies,
            seed_urls=normalized_seed_urls,
            request=active_request,
        )
        last_failure = seed_failure or last_failure
        for attempt_index, url in enumerate(candidate_urls):
            if context is not None:
                context.raise_if_cancelled()
            try:
                goto_timeout_ms = (
                    _remaining_pdf_timeout_seconds(
                        context, request_deadline, maximum=60
                    )
                    * 1000
                )
                download_timeout_ms = (
                    _remaining_pdf_timeout_seconds(
                        context, request_deadline, maximum=30
                    )
                    * 1000
                )
            except PdfFallbackFailure as exc:
                last_failure = exc
                break
            initial_response = None
            goto_kwargs: dict[str, Any] = {
                "wait_until": "domcontentloaded",
                "timeout": goto_timeout_ms,
            }
            active_referer = normalize_text(referer)
            if active_referer:
                goto_kwargs["referer"] = active_referer
            try:
                with page.expect_download(timeout=download_timeout_ms) as download_info:
                    try:
                        initial_response = page.goto(url, **goto_kwargs)
                    except PlaywrightError as exc:
                        if "Download is starting" not in str(exc):
                            raise
                download = download_info.value
            except PlaywrightTimeoutError:
                response = initial_response
                if response is None:
                    try:
                        goto_kwargs["timeout"] = (
                            _remaining_pdf_timeout_seconds(
                                context, request_deadline, maximum=60
                            )
                            * 1000
                        )
                        response = page.goto(url, **goto_kwargs)
                    except PdfFallbackFailure as exc:
                        last_failure = exc
                        break
                    except Exception:
                        response = None
                if response is not None:
                    try:
                        pdf_result = _response_to_pdf_result(
                            response,
                            artifact_dir=artifact_dir,
                            asset_profile=asset_profile,
                            asset_output_dir=asset_output_dir,
                            allow_pdf_only=allow_pdf_only,
                            source_url=url,
                            final_url=page.url,
                            page=page,
                            request=active_request,
                        )
                        if pdf_result is not None:
                            return pdf_result
                    except PdfFallbackFailure as exc:
                        last_failure = exc
                        continue
                title = normalize_text(page.title())
                html = page.content()
                current_url = normalize_text(page.url)
                html_base_url = current_url
                parsed_current_url = urllib.parse.urlparse(current_url)
                if parsed_current_url.scheme not in {
                    "http",
                    "https",
                } or not normalize_text(parsed_current_url.netloc):
                    html_base_url = url
                discovered = extract_pdf_candidate_urls_from_html(html, html_base_url)
                http_retry_candidates: list[str] = []
                for candidate in [
                    urllib.parse.urljoin(html_base_url or "", url),
                    *discovered,
                ]:
                    normalized_candidate = normalize_text(candidate)
                    if (
                        normalized_candidate
                        and normalized_candidate not in http_retry_candidates
                    ):
                        http_retry_candidates.append(normalized_candidate)
                if http_retry_candidates:
                    try:
                        context_cookies = browser_context.cookies([html_base_url])
                    except TypeError:
                        try:
                            context_cookies = browser_context.cookies()
                        except Exception:
                            context_cookies = list(browser_cookies or [])
                    except Exception:
                        context_cookies = list(browser_cookies or [])
                    context_cookies = filter_browser_cookies_for_url(
                        list(context_cookies or []),
                        html_base_url,
                    )
                    http_referer = normalize_text(referer) or normalize_text(
                        html_base_url
                    )
                    http_headers = _browser_navigation_pdf_headers(
                        user_agent=active_user_agent,
                        referer=http_referer,
                        target_url=http_retry_candidates[0],
                    )
                    try:
                        return fetch_pdf_over_http(
                            context.transport
                            if context is not None and context.transport is not None
                            else HttpTransport(),
                            http_retry_candidates,
                            headers=http_headers,
                            artifact_dir=artifact_dir,
                            asset_profile=asset_profile,
                            asset_output_dir=asset_output_dir,
                            allow_pdf_only=allow_pdf_only,
                            browser_cookies=context_cookies,
                            request=replace(
                                active_request,
                                timeout_seconds=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                            ),
                        )
                    except PdfFallbackFailure as exc:
                        last_failure = exc
                        if exc.kind == "pdf_fallback_timeout":
                            break
                if (
                    last_failure is not None
                    and last_failure.kind == "pdf_fallback_timeout"
                ):
                    break
                summary = summarize_html(html)
                response_status, response_headers = _browser_response_metadata(response)
                detected = detect_html_block(title, summary, response_status)
                try:
                    _capture_pdf_browser_failure(
                        page,
                        artifact_dir,
                        html,
                        attempt_index,
                        active_request,
                        browser_budget_seconds=browser_budget_seconds,
                    )
                except PdfFallbackFailure as exc:
                    last_failure = exc
                    break
                failure_details = _pdf_failure_details_from_response(
                    source_url=url,
                    final_url=page.url,
                    status=response_status,
                    headers=response_headers,
                    body=html.encode("utf-8", errors="replace"),
                )
                last_failure = PdfFallbackFailure(
                    detected.reason
                    if detected is not None
                    else "pdf_download_not_triggered",
                    detected.message
                    if detected is not None
                    else "Browser context did not trigger a PDF download.",
                    details=failure_details
                    or {
                        "source_url": redact_url_for_diagnostics(url),
                        "final_url": redact_url_for_diagnostics(page.url),
                    },
                )
                continue
            except Exception as exc:
                last_failure = PdfFallbackFailure(
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
                    context, request_deadline, maximum=browser_budget_seconds
                )
                result = _download_to_pdf_result(
                    download,
                    artifact_dir=artifact_dir,
                    asset_profile=asset_profile,
                    asset_output_dir=asset_output_dir,
                    allow_pdf_only=allow_pdf_only,
                    source_url=url,
                    final_url=page.url,
                    expected_identity=request.expected_identity,
                )
                return replace(
                    result,
                    diagnostics={
                        **dict(result.diagnostics),
                        "timeout_budget_ms": int(browser_budget_seconds * 1000),
                        "elapsed_ms": round(
                            (time.monotonic() - request_started_at) * 1000, 3
                        ),
                        "remaining_ms": max(
                            0,
                            int((request_deadline - time.monotonic()) * 1000),
                        ),
                    },
                )
            except PdfFallbackFailure as exc:
                last_failure = exc
                if exc.kind == "pdf_fallback_timeout":
                    break
                continue
    finally:
        if browser_context is not None:
            with contextlib.suppress(Exception):
                browser_context.close()
        if manager is not None:
            with contextlib.suppress(Exception):
                manager.close()
        if sanitized_storage_state_path is not None:
            sanitized_storage_state_path.unlink(missing_ok=True)

    if last_failure is None:
        last_failure = PdfFallbackFailure(
            "empty_pdf_attempts", "No PDF fallback candidates were attempted."
        )
    raise last_failure


def _stream_pdf_candidate(
    transport: HttpTransport,
    url: str,
    *,
    headers: Mapping[str, str],
    timeout: int,
    artifact_dir: Path | None,
    maximum_pdf_bytes: int,
    request_policy: HttpRequestPolicy,
) -> dict[str, Any]:
    """Bound direct PDF bytes while using the shared hostname connection pool."""

    temporary_dir = (
        tempfile.TemporaryDirectory(prefix="paper_fetch_pdf_stream_")
        if artifact_dir is None
        else None
    )
    staging_root = (
        Path(temporary_dir.name) if temporary_dir is not None else artifact_dir
    )
    assert staging_root is not None
    staging_root.mkdir(parents=True, exist_ok=True)
    staging_path = staging_root / f".paper-fetch-pdf-{uuid.uuid4().hex}.part"
    try:
        response = transport.stream_to_file(
            "GET",
            url,
            staging_path,
            headers=headers,
            options=HttpStreamOptions(
                timeout=timeout,
                retry_on_transient=True,
                request_policy=replace(
                    request_policy,
                    timeout_seconds=timeout,
                    max_response_bytes=maximum_pdf_bytes,
                    max_compressed_response_bytes=maximum_pdf_bytes,
                ),
            ),
        )
        # ``PdfFetchResult`` retains a bytes compatibility field.  This is the
        # only whole-file handoff, after Content-Length/chunk enforcement has
        # bounded the staging file to ``pdf_max_bytes()``.
        payload = staging_path.read_bytes()
        return {
            **dict(response),
            "body": payload,
        }
    finally:
        staging_path.unlink(missing_ok=True)
        if temporary_dir is not None:
            temporary_dir.cleanup()


def fetch_pdf_over_http(
    transport: HttpTransport,
    candidate_urls: list[str],
    *,
    headers: Mapping[str, str] | None = None,
    artifact_dir: Path | None = None,
    asset_profile: PdfAssetProfile = "none",
    asset_output_dir: Path | None = None,
    allow_pdf_only: bool = False,
    seed_urls: list[str] | None = None,
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
    last_failure: PdfFetchFailure | None = None

    def timeout_provider() -> int:
        return _remaining_pdf_timeout_seconds(
            context,
            request_deadline,
            maximum=timeout,
        )

    streaming = bool(
        getattr(transport, "_streaming_ready", False) is True
        and callable(getattr(transport, "stream_to_file", None))
    )
    route_policy = _compile_pdf_direct_route_policy(
        request,
        maximum_pdf_bytes=maximum_pdf_bytes,
    )
    opener = (
        None
        if streaming
        else _build_cookie_seeded_opener(
            seed_urls,
            headers=request_headers,
            timeout=timeout_provider(),
            timeout_provider=timeout_provider,
            browser_cookies=browser_cookies,
            cancel_check=lambda: _pdf_cancelled(context, transport),
        )
    )

    for attempt_index, url in enumerate(candidate_urls):
        try:
            active_timeout = timeout_provider()
        except PdfFetchFailure as exc:
            last_failure = exc
            break
        per_request_headers = dict(request_headers)
        cookie_header = _cookie_header_for_url(browser_cookies, url)
        if cookie_header:
            per_request_headers["Cookie"] = cookie_header
        try:
            response = (
                _stream_pdf_candidate(
                    transport,
                    url,
                    headers=per_request_headers,
                    timeout=active_timeout,
                    artifact_dir=artifact_dir,
                    maximum_pdf_bytes=maximum_pdf_bytes,
                    request_policy=route_policy.request_policy,
                )
                if streaming
                else _request_with_opener(
                    opener,
                    url,
                    headers=per_request_headers,
                    timeout=active_timeout,
                    failure_label="PDF fallback candidate",
                    max_response_bytes=maximum_pdf_bytes,
                    cancel_check=lambda: _pdf_cancelled(context, transport),
                )
                if opener is not None
                else transport.request(
                    "GET",
                    url,
                    headers=per_request_headers,
                    timeout=active_timeout,
                    # This branch is a compatibility path for explicitly
                    # injected, non-streaming transports. Identified provider
                    # routes still consume the exact compiled policy.
                    request_policy=route_policy.request_policy,
                )
            )
        except RequestFailure as exc:
            details = _pdf_failure_details_from_response(
                source_url=url,
                final_url=str(exc.url or url),
                status=exc.status_code,
                headers=exc.headers,
                body=exc.body,
                error_category=str(exc.error_category or ""),
            )
            _write_pdf_failure_html(
                artifact_dir,
                exc.body,
                context=context,
                attempt_index=attempt_index,
            )
            last_failure = PdfFetchFailure(
                "pdf_download_failed",
                f"Failed to download PDF fallback candidate: {exc}",
                details=details or {"source_url": url},
            )
            if time.monotonic() >= request_deadline:
                last_failure = PdfFetchFailure(
                    "pdf_fallback_timeout",
                    "PDF fallback request deadline was exhausted.",
                    details={
                        **dict(last_failure.details),
                        "timeout_budget_ms": int(timeout * 1000),
                        "elapsed_ms": round(
                            (time.monotonic() - request_started_at) * 1000, 3
                        ),
                        "remaining_ms": 0,
                    },
                )
                break
            continue

        try:
            timeout_provider()
        except PdfFallbackFailure as exc:
            last_failure = exc
            break
        final_url = str(response.get("url") or url)
        response_headers = response.get("headers") or {}
        pdf_bytes = response.get("body", b"")
        content_type = header_value(response_headers, "content-type")
        if not isinstance(pdf_bytes, (bytes, bytearray)) or not looks_like_pdf_payload(
            content_type,
            bytes(pdf_bytes),
            final_url,
        ):
            body_bytes = (
                bytes(pdf_bytes) if isinstance(pdf_bytes, (bytes, bytearray)) else b""
            )
            _write_pdf_failure_html(
                artifact_dir,
                body_bytes,
                context=context,
                attempt_index=attempt_index,
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
            result = pdf_fetch_result_from_bytes(
                artifact_dir=artifact_dir,
                asset_profile=asset_profile,
                asset_output_dir=asset_output_dir,
                source_url=url,
                final_url=final_url,
                pdf_bytes=bytes(pdf_bytes),
                suggested_filename=filename_from_headers(response_headers),
                allow_pdf_only=allow_pdf_only,
                expected_identity=request.expected_identity,
            )
            return replace(
                result,
                diagnostics={
                    **dict(result.diagnostics),
                    "timeout_budget_ms": int(timeout * 1000),
                    "elapsed_ms": round(
                        (time.monotonic() - request_started_at) * 1000, 3
                    ),
                    "remaining_ms": max(
                        0,
                        int((request_deadline - time.monotonic()) * 1000),
                    ),
                },
            )
        except PdfFetchFailure as exc:
            last_failure = exc
            if time.monotonic() >= request_deadline:
                last_failure = PdfFetchFailure(
                    "pdf_fallback_timeout",
                    "PDF fallback request deadline was exhausted.",
                    details={
                        **dict(exc.details),
                        "timeout_budget_ms": int(timeout * 1000),
                        "elapsed_ms": round(
                            (time.monotonic() - request_started_at) * 1000, 3
                        ),
                        "remaining_ms": 0,
                    },
                )
                break
            continue

    if last_failure is None:
        last_failure = PdfFetchFailure(
            "empty_pdf_attempts", "No PDF fallback candidates were attempted."
        )
    raise last_failure
