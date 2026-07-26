"""Shared Playwright helpers for browser-workflow provider access."""

from __future__ import annotations

import base64
import contextlib
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from collections.abc import Mapping

from bs4 import BeautifulSoup

from ..extraction.image_payloads import (
    image_dimensions_from_bytes,
    image_mime_type_from_bytes,
)
from ..http import RequestCancelledError
from ..extraction.html.signals import detect_html_block, summarize_html
from ..quality.html_availability import choose_parser, extract_page_title
from ..quality.html_signals import looks_like_abstract_redirect
from ..quality.reason_codes import REDIRECTED_TO_ABSTRACT
from ..runtime_browser import (
    ManagedBrowserError,
    browser_page_user_agent,
)
from ..reason_codes import (
    BROWSER_CONTEXT_CREATE_FAILED,
    BROWSER_PAGE_CREATE_FAILED,
)
from ..utils import normalize_text
from .browser_runtime.seed import (
    merge_browser_context_seeds,
)
from .browser_runtime.types import (
    BrowserFetchedHtml,
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
)
from .browser_runtime.context import open_browser_context
from .browser_workflow.fetchers.context import (
    _browser_response_headers,
    _browser_response_status,
)
from .browser_workflow.fetchers.readiness import wait_for_atypon_body_dom_ready
from .browser_workflow.fetchers.scripts import _LOADED_IMAGE_CANVAS_EXPORT_SCRIPT
from .browser_workflow.shared import BROWSER_HTML_BLOCKED_RESOURCE_TYPES

if TYPE_CHECKING:
    from ..runtime import RuntimeContext
    from .browser_runtime import BrowserImagePayload


def _runtime_paths():
    from .browser_runtime import paths as runtime_paths

    return runtime_paths


logger = logging.getLogger("paper_fetch.providers.playwright")

DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS = 120000
DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS = 8
DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS = 1
_IMAGE_PAYLOAD_MIN_IMAGE_DIMENSION = 1
_IMAGE_RESPONSE_BLOCKED_BY_HTML_WRAPPER = "image_response_blocked_by_html_wrapper"
_IMAGE_PAYLOAD_RESPONSE_ATTR = "_paper_fetch_top_level_response"
_IMAGE_PAYLOAD_TIMEOUT_ATTR = "_paper_fetch_image_payload_timeout_ms"
_IMAGE_PAYLOAD_FAILURE_ATTR = "_paper_fetch_image_payload_failure"

PlaywrightRuntimeConfig = BrowserRuntimeConfig
PlaywrightBrowserFailure = BrowserRuntimeFailure


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalized_content_type(value: str | None) -> str:
    return normalize_text(str(value or "")).split(";", 1)[0].lower()


def _response_body(response: Any) -> bytes | None:
    if response is None:
        return None
    try:
        body = response.body()
    except Exception:
        return None
    if not isinstance(body, (bytes, bytearray)) or not body:
        return None
    return bytes(body)


def _browser_image_payload_from_bytes(
    body: bytes | bytearray | None,
    *,
    content_type: str | None,
    url: str,
    status: int | None,
    width: int = 0,
    height: int = 0,
) -> BrowserImagePayload | None:
    if not isinstance(body, (bytes, bytearray)) or not body:
        return None
    payload_body = bytes(body)
    detected_type = image_mime_type_from_bytes(payload_body)
    if not detected_type:
        return None
    normalized_content_type = _normalized_content_type(content_type) or detected_type
    if not normalized_content_type.startswith("image/"):
        normalized_content_type = detected_type
    dimensions = image_dimensions_from_bytes(payload_body)
    if dimensions is not None:
        width = width or dimensions[0]
        height = height or dimensions[1]
    return {
        "bodyB64": base64.b64encode(payload_body).decode("ascii"),
        "contentType": normalized_content_type,
        "url": normalize_text(url),
        "status": status or 200,
        "width": max(0, _safe_int(width)),
        "height": max(0, _safe_int(height)),
    }


def _capture_expected_response(page: Any, request_url: str) -> Any:
    response = getattr(page, _IMAGE_PAYLOAD_RESPONSE_ATTR, None)
    if response is not None:
        return response
    timeout_ms = (
        _safe_int(getattr(page, _IMAGE_PAYLOAD_TIMEOUT_ATTR, None))
        or DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS
    )
    try:
        expected_response = page.expect_response(
            lambda response: (
                normalize_text(str(getattr(response, "url", "") or "")) == request_url
            ),
            timeout=timeout_ms,
        )
    except Exception:
        return None
    if not hasattr(expected_response, "__enter__"):
        return getattr(expected_response, "value", expected_response)
    try:
        with expected_response as response_info:
            pass
        return getattr(response_info, "value", None)
    except Exception:
        return None


def _image_element_has_loaded_natural_size(image_element: Any) -> bool | None:
    try:
        image_info = image_element.evaluate(
            """
            (image) => ({
              width: image.naturalWidth || 0,
              height: image.naturalHeight || 0,
              complete: !!image.complete,
            })
            """
        )
    except Exception:
        return None
    if not isinstance(image_info, Mapping):
        return None
    return (
        bool(image_info.get("complete", True))
        and _safe_int(image_info.get("width")) > 0
        and _safe_int(image_info.get("height")) > 0
    )


def _payload_from_canvas_export(
    rendered: Any,
    *,
    fallback_url: str,
    status: int | None,
) -> BrowserImagePayload | None:
    if not isinstance(rendered, Mapping) or not rendered.get("ok"):
        return None
    body_b64 = normalize_text(str(rendered.get("bodyB64") or ""))
    content_type = (
        _normalized_content_type(str(rendered.get("contentType") or "")) or "image/png"
    )
    data_url = normalize_text(
        str(rendered.get("dataURL") or rendered.get("dataUrl") or "")
    )
    if data_url.startswith("data:") and "," in data_url:
        metadata, body_b64 = data_url.split(",", 1)
        content_type = (
            _normalized_content_type(metadata.removeprefix("data:").split(";", 1)[0])
            or content_type
        )
    try:
        body = base64.b64decode(body_b64, validate=True)
    except Exception:
        return None
    return _browser_image_payload_from_bytes(
        body,
        content_type=content_type,
        url=fallback_url,
        status=status,
        width=_safe_int(rendered.get("width")),
        height=_safe_int(rendered.get("height")),
    )


def _clear_image_payload_failure(page: Any) -> None:
    with contextlib.suppress(Exception):
        delattr(page, _IMAGE_PAYLOAD_FAILURE_ATTR)


def _record_image_payload_failure(page: Any, values: Mapping[str, Any]) -> None:
    with contextlib.suppress(Exception):
        setattr(page, _IMAGE_PAYLOAD_FAILURE_ATTR, dict(values))


def _capture_image_payload(
    page: Any,
    *,
    request_url: str,
    final_url: str,
) -> BrowserImagePayload | None:
    _clear_image_payload_failure(page)
    normalized_request_url = normalize_text(request_url)
    normalized_final_url = normalize_text(final_url) or normalized_request_url
    response = _capture_expected_response(page, normalized_request_url)
    status = _browser_response_status(response, zero_as_none=False) or 200
    headers = _browser_response_headers(response)
    content_type = _normalized_content_type(headers.get("content-type"))

    if content_type.startswith("image/"):
        payload = _browser_image_payload_from_bytes(
            _response_body(response),
            content_type=content_type,
            url=normalized_final_url,
            status=status,
        )
        if payload is not None:
            return payload

    html = ""
    try:
        html = str(page.content() or "")
    except Exception:
        html = ""
    if _normalized_content_type(content_type) in {
        "image/svg+xml",
        "",
    } or normalize_text(html).startswith("<"):
        svg_payload = _browser_image_payload_from_bytes(
            html.encode("utf-8"),
            content_type="image/svg+xml",
            url=normalized_final_url,
            status=status,
        )
        if svg_payload is not None and svg_payload["contentType"] == "image/svg+xml":
            return svg_payload

    image_element = None
    try:
        image_element = page.query_selector("img")
    except Exception:
        image_element = None
    if image_element is not None:
        loaded = _image_element_has_loaded_natural_size(image_element)
        if loaded is not False:
            try:
                rendered = page.evaluate(
                    _LOADED_IMAGE_CANVAS_EXPORT_SCRIPT,
                    [
                        normalized_request_url,
                        _IMAGE_PAYLOAD_MIN_IMAGE_DIMENSION,
                        _IMAGE_PAYLOAD_MIN_IMAGE_DIMENSION,
                    ],
                )
            except Exception:
                rendered = None
            payload = _payload_from_canvas_export(
                rendered,
                fallback_url=normalized_final_url,
                status=status,
            )
            if payload is not None:
                return payload

    try:
        title = normalize_text(str(page.title() or ""))
    except Exception:
        title = ""
    if not title and html:
        try:
            title = extract_page_title(BeautifulSoup(html, choose_parser())) or ""
        except Exception:
            title = ""
    summary = summarize_html(html) if normalize_text(html) else ""
    detected = detect_html_block(title or "", summary, status)
    reason = (
        detected.reason
        if detected is not None
        else _IMAGE_RESPONSE_BLOCKED_BY_HTML_WRAPPER
    )
    _record_image_payload_failure(
        page,
        {
            "reason": reason,
            "url": normalized_final_url,
            "status": status,
            "content_type": content_type,
            "title": title,
            "summary": summary,
        },
    )
    return None


def _context_seed(
    context: Any, *, final_url: str, user_agent: str | None, backend: str
) -> dict[str, Any]:
    from .browser_runtime.seed import browser_context_seed_from_session

    return browser_context_seed_from_session(
        context,
        final_url=final_url,
        user_agent=user_agent,
        backend=backend,
    )


def _safe_close(value: Any) -> None:
    if value is None:
        return
    with contextlib.suppress(Exception):
        value.close()


def _raise_if_cancelled(runtime_context: RuntimeContext | None) -> None:
    cancel_check = getattr(runtime_context, "cancel_check", None)
    if callable(cancel_check) and cancel_check() is True:
        raise RequestCancelledError("Request cancelled.")


def _storage_state_path(config: PlaywrightRuntimeConfig) -> Path | None:
    return _runtime_paths().storage_state_path(config)


def _storage_context_options(config: PlaywrightRuntimeConfig) -> dict[str, Any]:
    return _runtime_paths().storage_context_options(config)


def _storage_origin_matches_url(origin: Mapping[str, Any], url: str | None) -> bool:
    return _runtime_paths().storage_origin_matches_url(origin, url)


def _filtered_storage_state_payload(
    context: Any, *, url: str
) -> Mapping[str, Any] | None:
    return _runtime_paths().filtered_storage_state_payload(context, url=url)


def _save_storage_state(
    context: Any,
    config: PlaywrightRuntimeConfig,
    *,
    filter_url: str | None = None,
) -> dict[str, Any]:
    result = _runtime_paths().save_storage_state(context, config, filter_url=filter_url)
    if result.get("attempted") and not result.get("saved"):
        logger.debug(
            "browser_storage_state provider=%s action=save_failed path=%s",
            config.provider,
            result.get("path"),
        )
    return result


def fetch_html_with_playwright(
    candidate_urls: list[str],
    *,
    publisher: str,
    config: PlaywrightRuntimeConfig,
    wait_seconds: int = DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS,
    warm_wait_seconds: int = DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS,
    max_timeout_ms: int | None = None,
    return_image_payload: bool = False,
    return_screenshot: bool = False,
    disable_media: bool = False,
    lightweight_seed_only: bool = False,
    runtime_context: RuntimeContext | None = None,
) -> BrowserFetchedHtml:
    del warm_wait_seconds
    if not candidate_urls:
        raise PlaywrightBrowserFailure(
            "empty_html_attempts", "No publisher HTML candidates were attempted."
        )
    if return_image_payload:
        disable_media = False

    last_failure: PlaywrightBrowserFailure | None = None
    latest_browser_context_seed: Mapping[str, Any] | None = None
    latest_storage_state_url: str | None = None
    timeout_ms = max_timeout_ms or config.timeout_ms
    backend_name = normalize_text(config.backend).lower()
    if backend_name != "camoufox":
        raise PlaywrightBrowserFailure(
            "browser_backend_invalid",
            f"Unsupported browser backend {config.backend!r}.",
        )
    artifact_dir = config.artifact_dir / backend_name
    configured_user_agent = normalize_text(config.user_agent)
    trace: dict[str, Any] = {
        "backend": backend_name,
        "candidate_count": len(candidate_urls),
        "candidates": [],
        "media_blocking": bool(disable_media),
        "return_image_payload": bool(return_image_payload),
        "return_screenshot": bool(return_screenshot),
        "lightweight_seed_only": bool(lightweight_seed_only),
        "external_cdp": bool(config.cdp_endpoint),
        "storage_state_path": str(_storage_state_path(config) or ""),
        "storage_state_write_enabled": config.persist_storage_state,
    }
    overall_started = time.monotonic()

    manager = None
    browser_context = None
    page = None
    try:
        _raise_if_cancelled(runtime_context)
        try:
            connect_started = time.monotonic()
            manager, browser_context = open_browser_context(
                config,
                runtime_context=runtime_context,
            )
            connect_seconds = round(time.monotonic() - connect_started, 3)
            trace["browser_connect_seconds"] = connect_seconds
            external_diagnostics = getattr(
                browser_context, "_paper_fetch_external_cdp_diagnostics", None
            )
            if isinstance(external_diagnostics, Mapping):
                trace["external_cdp_context"] = dict(external_diagnostics)
            elif config.cdp_endpoint:
                trace["external_cdp_context"] = {
                    "external_cdp": True,
                    "borrowed_existing_context": None,
                    "ignored_context_options": [],
                    "storage_state_cookie_count": None,
                }
        except ManagedBrowserError as exc:
            trace["browser_connect_seconds"] = round(
                time.monotonic() - connect_started, 3
            )
            trace["browser_failure"] = dict(exc.details)
            raise PlaywrightBrowserFailure(
                exc.code,
                exc.message,
                details={"trace": trace, "browser_failure": dict(exc.details)},
            ) from exc
        except Exception as exc:
            trace["browser_connect_seconds"] = round(
                time.monotonic() - connect_started, 3
            )
            message = normalize_text(str(exc)) or "Browser context creation failed."
            raise PlaywrightBrowserFailure(
                BROWSER_CONTEXT_CREATE_FAILED,
                message,
                details={
                    "trace": trace,
                    "browser_failure": {
                        "stage": "browser_context_create",
                        "code": BROWSER_CONTEXT_CREATE_FAILED,
                        "message": message,
                    },
                },
            ) from exc

        try:
            page = browser_context.new_page()
        except Exception as exc:
            message = normalize_text(str(exc)) or "Browser page creation failed."
            raise PlaywrightBrowserFailure(
                BROWSER_PAGE_CREATE_FAILED,
                message,
                details={
                    "trace": trace,
                    "browser_failure": {
                        "stage": "browser_page_create",
                        "code": BROWSER_PAGE_CREATE_FAILED,
                        "message": message,
                    },
                },
            ) from exc

        def route_handler(route: Any) -> None:
            try:
                resource_type = normalize_text(
                    str(route.request.resource_type or "")
                ).lower()
                blocked_types = (
                    {"media"}
                    if backend_name == "camoufox"
                    else BROWSER_HTML_BLOCKED_RESOURCE_TYPES
                )
                if disable_media and resource_type in blocked_types:
                    route.abort()
                    return
                route.continue_()
            except Exception:
                with contextlib.suppress(Exception):
                    route.continue_()

        if disable_media:
            with contextlib.suppress(Exception):
                page.route("**/*", route_handler)

        for url in candidate_urls:
            _raise_if_cancelled(runtime_context)
            normalized_url = normalize_text(url)
            if not normalized_url:
                continue
            candidate_trace: dict[str, Any] = {
                "url": normalized_url,
                "started_at": round(time.time(), 3),
            }
            trace["candidates"].append(candidate_trace)
            candidate_started = time.monotonic()
            try:
                logger.debug(
                    "browser_request backend=%s provider=%s action=request wait_seconds=%s url=%s",
                    backend_name,
                    publisher,
                    wait_seconds,
                    normalized_url,
                )
                request_started = time.monotonic()
                response = None
                top_level_response = None
                if return_image_payload:
                    with contextlib.suppress(Exception):
                        setattr(page, _IMAGE_PAYLOAD_TIMEOUT_ATTR, timeout_ms)
                    try:
                        with page.expect_response(
                            lambda candidate_response, normalized_url=normalized_url: (
                                normalize_text(
                                    str(getattr(candidate_response, "url", "") or "")
                                )
                                == normalized_url
                            ),
                            timeout=timeout_ms,
                        ) as response_info:
                            response = page.goto(
                                normalized_url,
                                wait_until="domcontentloaded",
                                timeout=timeout_ms,
                            )
                        try:
                            top_level_response = response_info.value
                        except Exception:
                            top_level_response = response
                    except Exception:
                        if response is None:
                            raise
                        top_level_response = response
                else:
                    response = page.goto(
                        normalized_url,
                        wait_until=(
                            "commit"
                            if backend_name == "camoufox"
                            else "domcontentloaded"
                        ),
                        timeout=timeout_ms,
                    )
                candidate_trace["navigation_seconds"] = round(
                    time.monotonic() - request_started, 3
                )
                if top_level_response is None:
                    top_level_response = response
                if return_image_payload:
                    with contextlib.suppress(Exception):
                        setattr(page, _IMAGE_PAYLOAD_RESPONSE_ATTR, top_level_response)
                if lightweight_seed_only:
                    final_url = (
                        normalize_text(str(getattr(page, "url", "") or ""))
                        or normalized_url
                    )
                    latest_storage_state_url = final_url
                    status = _browser_response_status(response, zero_as_none=False)
                    headers = _browser_response_headers(response)
                    candidate_trace["status"] = status
                    candidate_trace["final_url"] = final_url
                    browser_context_seed = _context_seed(
                        browser_context,
                        final_url=final_url,
                        user_agent=configured_user_agent
                        or browser_page_user_agent(page),
                        backend=backend_name,
                    )
                    browser_context_seed = merge_browser_context_seeds(
                        browser_context_seed,
                        {
                            "paper_fetch_html_fetcher": backend_name,
                            "diagnostics": {"browser_backend": backend_name},
                        },
                    )
                    if browser_context_seed.get(
                        "browser_cookies"
                    ) or browser_context_seed.get("browser_user_agent"):
                        latest_browser_context_seed = browser_context_seed
                    candidate_trace["duration_seconds"] = round(
                        time.monotonic() - candidate_started, 3
                    )
                    candidate_trace["result"] = "success"
                    return BrowserFetchedHtml(
                        source_url=normalized_url,
                        final_url=final_url,
                        html="",
                        response_status=status,
                        response_headers=headers,
                        title=None,
                        summary="",
                        browser_context_seed=browser_context_seed,
                        diagnostics={"browser_runtime_trace": trace},
                    )
                readiness = None
                if not return_image_payload:
                    _raise_if_cancelled(runtime_context)
                    remaining_timeout_seconds = max(
                        0.0,
                        (float(timeout_ms) / 1000.0)
                        - (time.monotonic() - request_started),
                    )
                    readiness_started = time.monotonic()
                    readiness = wait_for_atypon_body_dom_ready(
                        page,
                        publisher,
                        timeout_seconds=min(
                            max(float(wait_seconds), 20.0),
                            remaining_timeout_seconds,
                        ),
                    )
                    candidate_trace["dom_readiness_seconds"] = round(
                        time.monotonic() - readiness_started, 3
                    )
                    candidate_trace["dom_readiness_attempted"] = readiness.attempted
                    candidate_trace["dom_readiness_ready"] = readiness.ready
                if (readiness is None or not readiness.attempted) and wait_seconds > 0:
                    _raise_if_cancelled(runtime_context)
                    page.wait_for_timeout(max(0, int(wait_seconds)) * 1000)
                final_url = (
                    normalize_text(str(getattr(page, "url", "") or ""))
                    or normalized_url
                )
                latest_storage_state_url = final_url
                html = str(page.content() or "")
                title = normalize_text(str(page.title() or "")) or extract_page_title(
                    BeautifulSoup(html, choose_parser())
                )
                status = _browser_response_status(response, zero_as_none=False)
                headers = _browser_response_headers(response)
                candidate_trace["status"] = status
                candidate_trace["final_url"] = final_url
                summary = summarize_html(html)
                browser_context_seed = _context_seed(
                    browser_context,
                    final_url=final_url,
                    user_agent=configured_user_agent or browser_page_user_agent(page),
                    backend=backend_name,
                )
                browser_context_seed = merge_browser_context_seeds(
                    browser_context_seed,
                    {
                        "paper_fetch_html_fetcher": backend_name,
                        "diagnostics": {"browser_backend": backend_name},
                    },
                )
                if browser_context_seed.get(
                    "browser_cookies"
                ) or browser_context_seed.get("browser_user_agent"):
                    latest_browser_context_seed = browser_context_seed
                image_payload = None
                if return_image_payload:
                    try:
                        image_payload = _capture_image_payload(
                            page,
                            request_url=normalized_url,
                            final_url=final_url,
                        )
                    except Exception:
                        image_payload = None
                    image_failure = getattr(page, _IMAGE_PAYLOAD_FAILURE_ATTR, None)
                    if isinstance(image_failure, Mapping):
                        headers = dict(headers)
                        headers["x-paper-fetch-image-payload-failure-reason"] = (
                            normalize_text(str(image_failure.get("reason") or ""))
                        )
            except RequestCancelledError:
                candidate_trace["duration_seconds"] = round(
                    time.monotonic() - candidate_started,
                    3,
                )
                candidate_trace["error"] = "cancelled"
                raise
            except Exception as exc:
                candidate_trace["duration_seconds"] = round(
                    time.monotonic() - candidate_started,
                    3,
                )
                candidate_trace["error"] = (
                    normalize_text(str(exc)) or exc.__class__.__name__
                )
                if isinstance(exc, PlaywrightBrowserFailure):
                    last_failure = exc
                else:
                    last_failure = PlaywrightBrowserFailure(
                        f"{backend_name}_request_failed",
                        normalize_text(str(exc))
                        or f"{backend_name} page request failed.",
                        details={"trace": trace},
                    )
                continue

            if looks_like_abstract_redirect(normalized_url, final_url):
                candidate_trace["duration_seconds"] = round(
                    time.monotonic() - candidate_started, 3
                )
                candidate_trace["block_reason"] = REDIRECTED_TO_ABSTRACT
                last_failure = PlaywrightBrowserFailure(
                    REDIRECTED_TO_ABSTRACT,
                    "Publisher redirected the full-text URL to an abstract page.",
                    browser_context_seed=browser_context_seed,
                    details={"trace": trace},
                )
                continue

            detected = (
                None
                if readiness is not None and readiness.ready
                else detect_html_block(title or "", summary, status)
            )
            if detected is not None and not return_image_payload:
                candidate_trace["duration_seconds"] = round(
                    time.monotonic() - candidate_started, 3
                )
                candidate_trace["block_reason"] = detected.reason
                last_failure = PlaywrightBrowserFailure(
                    detected.reason,
                    detected.message,
                    browser_context_seed=browser_context_seed,
                    details={"trace": trace},
                )
                continue
            if not normalize_text(html) and image_payload is None:
                candidate_trace["duration_seconds"] = round(
                    time.monotonic() - candidate_started, 3
                )
                candidate_trace["block_reason"] = "empty_html_response"
                last_failure = PlaywrightBrowserFailure(
                    "empty_html_response",
                    f"{backend_name} returned empty publisher HTML.",
                    browser_context_seed=browser_context_seed,
                    details={"trace": trace},
                )
                continue

            screenshot_b64 = None
            if return_screenshot:
                try:
                    screenshot_payload = page.screenshot(type="png", timeout=timeout_ms)
                    if isinstance(screenshot_payload, bytes):
                        screenshot_b64 = base64.b64encode(screenshot_payload).decode(
                            "ascii"
                        )
                    elif isinstance(screenshot_payload, str):
                        screenshot_b64 = screenshot_payload
                except Exception:
                    screenshot_b64 = None
            candidate_trace["duration_seconds"] = round(
                time.monotonic() - candidate_started, 3
            )
            candidate_trace["result"] = "success"
            return BrowserFetchedHtml(
                source_url=normalized_url,
                final_url=final_url,
                html=html,
                response_status=status,
                response_headers=headers,
                title=title,
                summary=summary,
                browser_context_seed=browser_context_seed,
                screenshot_b64=screenshot_b64,
                image_payload=image_payload,
                diagnostics={"browser_runtime_trace": trace},
            )
    finally:
        if config.persist_storage_state:
            trace["storage_state_save"] = _save_storage_state(
                browser_context, config, filter_url=latest_storage_state_url
            )
        else:
            trace["storage_state_save"] = {
                "attempted": False,
                "saved": False,
                "path": str(_storage_state_path(config) or "") or None,
                "reason": "storage_state_write_disabled",
            }
        trace["duration_seconds"] = round(time.monotonic() - overall_started, 3)
        if runtime_context is not None and hasattr(
            runtime_context, "accumulate_stage_timing"
        ):
            with contextlib.suppress(Exception):
                runtime_context.accumulate_stage_timing(
                    "browser_seconds",
                    elapsed=time.monotonic() - overall_started,
                )
        _safe_close(page)
        _safe_close(browser_context)
        _safe_close(manager)

    if last_failure is None and latest_browser_context_seed is not None:
        last_failure = PlaywrightBrowserFailure(
            "empty_html_attempts",
            "No publisher HTML candidates were attempted.",
            browser_context_seed=latest_browser_context_seed,
            details={"trace": trace},
        )
    if last_failure is None:
        last_failure = PlaywrightBrowserFailure(
            "empty_html_attempts",
            "No publisher HTML candidates were attempted.",
            details={"trace": trace},
        )
    if artifact_dir:
        with contextlib.suppress(OSError):
            artifact_dir.mkdir(parents=True, exist_ok=True)
    raise last_failure


fetch_html_with_playwright.paper_fetch_html_fetcher_name = "camoufox"  # type: ignore[attr-defined]


def fetch_html_with_playwright_fast(*args: Any, **kwargs: Any) -> BrowserFetchedHtml:
    return fetch_html_with_playwright(*args, **kwargs)


fetch_html_with_playwright_fast.paper_fetch_html_fetcher_name = "camoufox_fast"  # type: ignore[attr-defined]


def warm_browser_context_with_playwright(
    candidate_urls: list[str],
    *,
    publisher: str,
    config: PlaywrightRuntimeConfig,
    browser_context_seed: Mapping[str, Any] | None = None,
    runtime_context: RuntimeContext | None = None,
    lightweight: bool = False,
) -> dict[str, Any]:
    merged_seed = merge_browser_context_seeds(browser_context_seed)
    if not candidate_urls:
        return merged_seed

    try:
        result = fetch_html_with_playwright(
            candidate_urls,
            publisher=publisher,
            config=config,
            runtime_context=runtime_context,
            lightweight_seed_only=lightweight,
        )
    except PlaywrightBrowserFailure as exc:
        return merge_browser_context_seeds(merged_seed, exc.browser_context_seed)
    return merge_browser_context_seeds(merged_seed, result.browser_context_seed)
