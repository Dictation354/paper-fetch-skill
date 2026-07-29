"""PDF fallback helpers for browser-workflow and direct-HTTP providers."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import math
import time
import urllib.parse
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from collections.abc import Callable, Mapping

from ..http import (
    DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
    HttpRequestPolicy,
    HttpTransport,
    PDF_ACCEPT_HEADER,
    RequestCancelledError,
    RequestFailure,
    diagnostic_url_payload,
    redact_text_for_diagnostics,
    redact_url_for_diagnostics,
)
from ..http.headers import header_value
from ..extraction.html.assets.requester import (
    build_cookie_seeded_opener as _build_cookie_seeded_opener,
    cookie_header_for_url as _cookie_header_for_url,
    request_with_opener as _request_with_opener,
)
from ..extraction.html.shared import html_text_snippet, html_title_snippet
from ..extraction.html.signals import detect_html_block, summarize_html
from ..runtime import RuntimeContext
from ..runtime_browser import browser_context_options
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


def _raise_if_cancelled(context: RuntimeContext | None) -> None:
    cancel_check = getattr(context, "cancel_check", None)
    if callable(cancel_check) and cancel_check() is True:
        raise RequestCancelledError("Request cancelled.")


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
                timeout_seconds=self.timeout,
                expected_identity=self.expected_identity,
                runtime=self.context,
            ),
        )


@dataclass(frozen=True)
class PdfRequestContext:
    """Shared deadline, identity, and runtime state for one PDF request."""

    timeout_seconds: int | float = DEFAULT_FULLTEXT_TIMEOUT_SECONDS
    expected_identity: Mapping[str, Any] | None = None
    runtime: RuntimeContext | None = None
    deadline_monotonic: float | None = None

    def with_deadline(self, deadline: float) -> PdfRequestContext:
        return replace(self, deadline_monotonic=deadline)


@dataclass(frozen=True)
class _PdfBrowserLaunch:
    runtime: RuntimeContext | None
    browser_config: BrowserRuntimeConfig | None
    use_runtime_browser: bool
    headless: bool
    binary_path: str | None
    cdp_endpoint: str | None
    external_new_context: bool
    profile_dir: Path | str | None
    user_data_dir: Path | str | None


def _open_pdf_browser_context(
    launch: _PdfBrowserLaunch,
    context_kwargs: Mapping[str, Any],
    *,
    sanitized_storage_state_path: Path | None,
) -> tuple[Any | None, Any]:
    if launch.browser_config is not None:
        active_config = replace(
            launch.browser_config,
            storage_state_path=sanitized_storage_state_path,
            persist_storage_state=False,
        )
        return open_browser_context(
            active_config,
            runtime_context=launch.runtime if launch.use_runtime_browser else None,
        )
    if launch.runtime is not None and launch.use_runtime_browser:
        configured_paths = (
            launch.binary_path,
            launch.cdp_endpoint,
            launch.profile_dir,
            launch.user_data_dir,
        )
        if isinstance(launch.runtime, RuntimeContext) and any(
            value is not None for value in configured_paths
        ):
            return None, launch.runtime.new_browser_context_for_config(
                headless=launch.headless,
                binary_path=launch.binary_path,
                cdp_endpoint=launch.cdp_endpoint,
                external_new_context=launch.external_new_context,
                profile_dir=launch.profile_dir,
                user_data_dir=launch.user_data_dir,
                **dict(context_kwargs),
            )
        return None, launch.runtime.new_browser_context(
            headless=launch.headless,
            **dict(context_kwargs),
        )

    from ..runtime_browser import BrowserContextManager

    active_profile_dir = normalize_text(str(launch.profile_dir or ""))
    active_user_data_dir = normalize_text(str(launch.user_data_dir or ""))
    manager = BrowserContextManager(
        binary_path=normalize_text(launch.binary_path) or None,
        cdp_endpoint=normalize_text(launch.cdp_endpoint) or None,
        external_new_context=launch.external_new_context,
        profile_dir=(
            Path(active_profile_dir).expanduser() if active_profile_dir else None
        ),
        user_data_dir=(
            Path(active_user_data_dir).expanduser() if active_user_data_dir else None
        ),
    )
    return manager, manager.new_context(
        headless=launch.headless,
        **dict(context_kwargs),
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
        _raise_if_cancelled(request.runtime)
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
            if not canonical_screenshot.exists():
                canonical_screenshot.write_bytes(screenshot_path.read_bytes())


def _pdf_deadline(
    context: RuntimeContext | None,
    timeout_seconds: int | float,
) -> float:
    timeout_value = max(0.0, float(timeout_seconds))
    if context is not None:
        return context.ensure_deadline(timeout_value)
    return time.monotonic() + timeout_value


def _remaining_pdf_timeout_seconds(
    context: RuntimeContext | None,
    deadline: float,
    *,
    maximum: int | float,
) -> int:
    _raise_if_cancelled(context)
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
        body = response.body()
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
    maximum_pdf_bytes = pdf_max_bytes()
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
    download_path = artifact_dir / "downloaded.pdf"
    download.save_as(str(download_path))
    maximum_pdf_bytes = pdf_max_bytes()
    try:
        downloaded_bytes = download_path.stat().st_size
    except OSError:
        downloaded_bytes = 0
    if downloaded_bytes > maximum_pdf_bytes:
        download_path.unlink(missing_ok=True)
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


def _running_asyncio_loop_active() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def fetch_pdf_with_browser(
    candidate_urls: list[str],
    *,
    artifact_dir: Path,
    asset_profile: PdfAssetProfile = "none",
    asset_output_dir: Path | None = None,
    browser_cookies: list[dict[str, Any]] | None = None,
    browser_user_agent: str | None = None,
    headless: bool = True,
    referer: str | None = None,
    binary_path: str | None = None,
    cdp_endpoint: str | None = None,
    external_new_context: bool = False,
    profile_dir: Path | str | None = None,
    user_data_dir: Path | str | None = None,
    storage_state_path: Path | None = None,
    browser_config: BrowserRuntimeConfig | None = None,
    seed_urls: list[str] | None = None,
    allow_pdf_only: bool = False,
    request: PdfRequestContext = PdfRequestContext(),
    _allow_thread_handoff: bool = True,
    _use_runtime_browser: bool = True,
) -> PdfFallbackResult:
    context = request.runtime
    _raise_if_cancelled(context)
    browser_budget_seconds = (
        max(0.001, float(browser_config.timeout_ms) / 1000.0)
        if browser_config is not None
        else float(DEFAULT_FULLTEXT_TIMEOUT_SECONDS)
    )
    request_started_at = time.monotonic()
    request_deadline = request.deadline_monotonic or _pdf_deadline(
        context, browser_budget_seconds
    )
    active_request = request.with_deadline(request_deadline)
    if (
        _allow_thread_handoff
        and _running_asyncio_loop_active()
        and not (browser_config is not None and browser_config.backend == "camoufox")
    ):
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(
                fetch_pdf_with_browser,
                candidate_urls,
                artifact_dir=artifact_dir,
                asset_profile=asset_profile,
                asset_output_dir=asset_output_dir,
                browser_cookies=browser_cookies,
                browser_user_agent=browser_user_agent,
                headless=headless,
                referer=referer,
                binary_path=binary_path,
                cdp_endpoint=cdp_endpoint,
                external_new_context=external_new_context,
                profile_dir=profile_dir,
                user_data_dir=user_data_dir,
                storage_state_path=storage_state_path,
                browser_config=browser_config,
                seed_urls=seed_urls,
                allow_pdf_only=allow_pdf_only,
                request=active_request,
                _allow_thread_handoff=False,
                _use_runtime_browser=False,
            ).result()

    if not candidate_urls:
        raise PdfFallbackFailure(
            "empty_pdf_attempts", "No PDF fallback candidates were attempted."
        )

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

    _remaining_pdf_timeout_seconds(
        context, request_deadline, maximum=browser_budget_seconds
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    last_failure: PdfFallbackFailure | None = None
    sanitized_storage_state_path: Path | None = None
    if browser_config is not None:
        headless = browser_config.headless
        binary_path = browser_config.binary_path
        cdp_endpoint = browser_config.cdp_endpoint
        external_new_context = browser_config.external_new_context
        profile_dir = browser_config.profile_dir
        user_data_dir = browser_config.user_data_dir
        storage_state_path = storage_state_path or browser_config.storage_state_path
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

    context_kwargs: dict[str, Any] = browser_context_options(
        user_agent=active_user_agent,
        accept_downloads=True,
    )
    if storage_state_path is not None:
        sanitized_storage_state_path = sanitize_storage_state(storage_state_path)
        context_kwargs["storage_state"] = str(sanitized_storage_state_path)

    manager = None
    browser_context = None
    try:
        manager, browser_context = _open_pdf_browser_context(
            _PdfBrowserLaunch(
                runtime=context,
                browser_config=browser_config,
                use_runtime_browser=_use_runtime_browser,
                headless=headless,
                binary_path=binary_path,
                cdp_endpoint=cdp_endpoint,
                external_new_context=external_new_context,
                profile_dir=profile_dir,
                user_data_dir=user_data_dir,
            ),
            context_kwargs,
            sanitized_storage_state_path=sanitized_storage_state_path,
        )

        if browser_cookies:
            try:
                browser_context.add_cookies(browser_cookies)
            except Exception as exc:
                raise PdfFallbackFailure(
                    "invalid_browser_context_seed",
                    f"Failed to seed browser-context PDF fallback with cookies: {exc}",
                ) from exc

        page = browser_context.new_page()
        seed_failure = _seed_pdf_browser_page(page, seed_urls, active_request)
        if seed_failure is not None:
            last_failure = seed_failure
        for attempt_index, url in enumerate(candidate_urls):
            _raise_if_cancelled(context)
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


fetch_pdf_with_playwright = fetch_pdf_with_browser


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

    opener = _build_cookie_seeded_opener(
        seed_urls,
        headers=request_headers,
        timeout=timeout_provider(),
        timeout_provider=timeout_provider,
        browser_cookies=browser_cookies,
        cancel_check=lambda: _pdf_cancelled(context, transport),
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
                _request_with_opener(
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
                    retry_on_transient=True,
                    request_policy=HttpRequestPolicy(
                        max_response_bytes=maximum_pdf_bytes,
                        max_compressed_response_bytes=maximum_pdf_bytes,
                    ),
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
