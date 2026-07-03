"""CloakBrowser helpers for browser-workflow provider access."""

from __future__ import annotations

import base64
import importlib
from importlib import metadata as importlib_metadata
from importlib import util as importlib_util
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from collections.abc import Mapping
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ..config import (
    CDP_EXTERNAL_NEW_CONTEXT_ENV_VAR,
    CLOAKBROWSER_BINARY_PATH_ENV_VAR,
    CLOAKBROWSER_CDP_ENDPOINT_ENV_VAR,
    CLOAKBROWSER_HEADLESS_ENV_VAR,
    CLOAKBROWSER_TIMEOUT_MS_ENV_VAR,
    build_browser_user_agent,
    env_flag_enabled,
    parse_positive_int_env,
    resolve_user_data_dir,
)
from ..extraction.image_payloads import (
    image_dimensions_from_bytes,
    image_mime_type_from_bytes,
)
from ..http import RequestCancelledError
from ..extraction.html.signals import detect_html_block, summarize_html
from ..quality.html_availability import choose_parser, extract_page_title
from ..quality.html_signals import looks_like_abstract_redirect
from ..quality.reason_codes import REDIRECTED_TO_ABSTRACT
from ..reason_codes import ERROR, NOT_CONFIGURED, OK, READY
from ..runtime_browser import (
    BrowserContextManager,
    browser_context_options,
    browser_page_user_agent,
)
from ..utils import normalize_text, provider_display_name, sanitize_filename
from .browser_runtime import paths as runtime_paths
from .browser_runtime.seed import (
    filter_browser_cookies_for_url,
    merge_browser_context_seeds,
    normalize_browser_cookies_for_playwright,
)
from .browser_runtime.types import (
    BrowserFetchedHtml,
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
)
from .base import (
    ProviderFailure,
    ProviderStatusResult,
    build_provider_status_check,
    provider_status_check_from_failure,
)
from .browser_workflow.fetchers.context import (
    _browser_response_headers,
    _browser_response_status,
)
from .browser_workflow.fetchers.readiness import wait_for_atypon_body_dom_ready
from .browser_workflow.fetchers.scripts import _LOADED_IMAGE_CANVAS_EXPORT_SCRIPT
from .browser_workflow.shared import BROWSER_HTML_BLOCKED_RESOURCE_TYPES
import contextlib

if TYPE_CHECKING:
    from ..runtime import RuntimeContext
    from .browser_runtime import BrowserImagePayload

logger = logging.getLogger("paper_fetch.providers.cloakbrowser")

DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS = 120000
DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS = 8
DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS = 1
DEFAULT_CLOAKBROWSER_TIMEOUT_MS = DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS
CLOAKBROWSER_STATUS_PROBE_ID = "probe://cloakbrowser/status"
_IMAGE_PAYLOAD_MIN_IMAGE_DIMENSION = 1
_IMAGE_RESPONSE_BLOCKED_BY_HTML_WRAPPER = "image_response_blocked_by_html_wrapper"
_IMAGE_PAYLOAD_RESPONSE_ATTR = "_paper_fetch_top_level_response"
_IMAGE_PAYLOAD_TIMEOUT_ATTR = "_paper_fetch_image_payload_timeout_ms"
_IMAGE_PAYLOAD_FAILURE_ATTR = "_paper_fetch_image_payload_failure"

CloakBrowserRuntimeConfig = BrowserRuntimeConfig
CloakBrowserFailure = BrowserRuntimeFailure


def _browser_workflow_label(provider: str) -> str:
    normalized = normalize_text(provider).lower()
    return f"{provider_display_name(normalized)} browser workflow"


def _dependency_available() -> bool:
    try:
        return (
            importlib_util.find_spec("playwright") is not None
            and importlib_util.find_spec("cloakbrowser") is not None
        )
    except (ModuleNotFoundError, ValueError):
        return False


def _dependency_details() -> dict[str, Any]:
    details: dict[str, Any] = {
        "probe": "importlib.find_spec",
        "packages": {
            "playwright": importlib_util.find_spec("playwright") is not None,
            "cloakbrowser": importlib_util.find_spec("cloakbrowser") is not None,
        },
    }
    for package, available in details["packages"].items():
        if not available:
            continue
        try:
            details[f"{package}_version"] = importlib_metadata.version(package)
        except importlib_metadata.PackageNotFoundError:
            details[f"{package}_version"] = None
    return details


def _import_cloakbrowser() -> Any:
    try:
        return importlib.import_module("cloakbrowser")
    except Exception as exc:
        raise ProviderFailure(
            NOT_CONFIGURED,
            f"CloakBrowser Python package is not importable: {exc}",
        ) from exc


def _env_flag_false(value: str | None) -> bool:
    return normalize_text(value).lower() in {"0", "false", "no", "off"}


def _configured_binary_path(env: Mapping[str, str]) -> str | None:
    value = env.get(CLOAKBROWSER_BINARY_PATH_ENV_VAR, "").strip()
    return value or None


def _configured_cdp_endpoint(env: Mapping[str, str]) -> str | None:
    value = env.get(CLOAKBROWSER_CDP_ENDPOINT_ENV_VAR, "").strip()
    return value or None


def _configured_user_data_dir(env: Mapping[str, str]) -> Path | None:
    return runtime_paths.configured_user_data_dir(env)


def _default_provider_user_data_dir(env: Mapping[str, str], *, provider: str) -> Path:
    return runtime_paths.default_provider_user_data_dir(env, provider=provider)


def _configured_profile_dir(env: Mapping[str, str], *, provider: str) -> Path | None:
    return runtime_paths.configured_profile_dir(env, provider=provider)


def _configured_storage_state_path(
    env: Mapping[str, str], *, provider: str
) -> Path | None:
    return runtime_paths.configured_storage_state_path(env, provider=provider)


def _validate_binary_path(
    binary_path: str | None, *, require_launch_binary: bool
) -> None:
    if not require_launch_binary or not binary_path:
        return
    path = Path(binary_path).expanduser()
    if not path.is_file():
        raise ProviderFailure(
            NOT_CONFIGURED,
            f"{CLOAKBROWSER_BINARY_PATH_ENV_VAR} is set but does not point to a file: {path}",
        )
    if os.name != "nt" and not os.access(path, os.X_OK):
        raise ProviderFailure(
            NOT_CONFIGURED,
            f"{CLOAKBROWSER_BINARY_PATH_ENV_VAR} is set but is not executable: {path}",
        )


def _validate_cdp_endpoint(endpoint: str | None, *, provider: str) -> None:
    normalized = normalize_text(endpoint)
    if not normalized:
        return
    parsed = urlparse(normalized)
    if parsed.scheme not in {"ws", "wss", "http", "https"} or not parsed.hostname:
        workflow_label = _browser_workflow_label(provider)
        raise ProviderFailure(
            NOT_CONFIGURED,
            (
                f"{workflow_label} has invalid {CLOAKBROWSER_CDP_ENDPOINT_ENV_VAR}: "
                "expected a ws://, wss://, http://, or https:// URL with a host."
            ),
        )


def _validate_storage_state_path(
    storage_state_path: Path | None,
    *,
    provider: str,
    require_storage_state: bool,
) -> None:
    runtime_paths.validate_storage_state_path(
        storage_state_path,
        provider=provider,
        require_storage_state=require_storage_state,
    )


def load_runtime_config(
    env: Mapping[str, str],
    *,
    provider: str,
    doi: str,
    require_storage_state: bool = False,
) -> CloakBrowserRuntimeConfig:
    headless = not _env_flag_false(env.get(CLOAKBROWSER_HEADLESS_ENV_VAR))
    artifact_dir = (
        resolve_user_data_dir(env)
        / "publisher-browser-artifacts"
        / provider
        / sanitize_filename(doi)
    )
    binary_path = _configured_binary_path(env)
    cdp_endpoint = _configured_cdp_endpoint(env)
    _validate_cdp_endpoint(cdp_endpoint, provider=provider)
    _validate_binary_path(binary_path, require_launch_binary=cdp_endpoint is None)
    profile_dir = _configured_profile_dir(env, provider=provider)
    user_data_dir = _configured_user_data_dir(env)
    if cdp_endpoint is None and profile_dir is None and user_data_dir is None:
        user_data_dir = _default_provider_user_data_dir(env, provider=provider)
    storage_state_path = _configured_storage_state_path(env, provider=provider)
    _validate_storage_state_path(
        storage_state_path,
        provider=provider,
        require_storage_state=require_storage_state,
    )
    return CloakBrowserRuntimeConfig(
        provider=provider,
        doi=doi,
        artifact_dir=artifact_dir,
        headless=headless,
        user_agent=build_browser_user_agent(env),
        timeout_ms=parse_positive_int_env(
            env,
            CLOAKBROWSER_TIMEOUT_MS_ENV_VAR,
            default=DEFAULT_CLOAKBROWSER_TIMEOUT_MS,
        ),
        binary_path=binary_path,
        cdp_endpoint=cdp_endpoint,
        external_new_context=env_flag_enabled(env, CDP_EXTERNAL_NEW_CONTEXT_ENV_VAR),
        profile_dir=profile_dir,
        user_data_dir=user_data_dir,
        storage_state_path=storage_state_path,
    )


def ensure_runtime_ready(config: CloakBrowserRuntimeConfig) -> None:
    del config
    if not _dependency_available():
        raise ProviderFailure(
            NOT_CONFIGURED,
            "Browser workflow requires the playwright and cloakbrowser Python packages.",
        )


def _runtime_probe_details(
    env: Mapping[str, str],
    *,
    provider: str,
    config: CloakBrowserRuntimeConfig | None = None,
) -> dict[str, Any]:
    storage_state_path = (
        config.storage_state_path
        if config is not None
        else _configured_storage_state_path(env, provider=provider)
    )
    details: dict[str, Any] = {
        "headless": (
            config.headless
            if config is not None
            else not _env_flag_false(env.get(CLOAKBROWSER_HEADLESS_ENV_VAR))
        ),
        "timeout_ms": config.timeout_ms
        if config is not None
        else parse_positive_int_env(
            env,
            CLOAKBROWSER_TIMEOUT_MS_ENV_VAR,
            default=DEFAULT_CLOAKBROWSER_TIMEOUT_MS,
        ),
        "binary_path_configured": bool(
            config.binary_path if config is not None else _configured_binary_path(env)
        ),
        "cdp_endpoint_configured": bool(
            config.cdp_endpoint if config is not None else _configured_cdp_endpoint(env)
        ),
        "cdp_external_new_context": (
            config.external_new_context
            if config is not None
            else env_flag_enabled(env, CDP_EXTERNAL_NEW_CONTEXT_ENV_VAR)
        ),
        "profile_dir_configured": bool(
            config.profile_dir
            if config is not None
            else _configured_profile_dir(env, provider=provider)
        ),
        "user_data_dir_configured": bool(
            config.user_data_dir
            if config is not None
            else _configured_user_data_dir(env)
        ),
        "storage_state_json_configured": bool(storage_state_path),
        "auto_cdp_browser_enabled": not bool(
            config.cdp_endpoint if config is not None else _configured_cdp_endpoint(env)
        ),
    }
    if storage_state_path is not None:
        details["storage_state_json_exists"] = storage_state_path.is_file()
    return details


def probe_runtime_status(
    env: Mapping[str, str],
    *,
    provider: str,
    doi: str = CLOAKBROWSER_STATUS_PROBE_ID,
) -> ProviderStatusResult:
    checks = []
    config: CloakBrowserRuntimeConfig | None = None
    runtime_details = _runtime_probe_details(env, provider=provider)
    dependency_available = _dependency_available()
    try:
        config = load_runtime_config(env, provider=provider, doi=doi)
        runtime_details = _runtime_probe_details(env, provider=provider, config=config)
        checks.append(
            build_provider_status_check(
                "runtime_env",
                OK if dependency_available else NOT_CONFIGURED,
                (
                    f"{provider} CDP browser runtime environment is configured."
                    if dependency_available
                    else f"{provider} CDP browser runtime requires the playwright and cloakbrowser Python packages."
                ),
                details=runtime_details,
            )
        )
    except ProviderFailure as exc:
        checks.append(
            provider_status_check_from_failure(
                "runtime_env", exc, details=runtime_details
            )
        )
    except Exception as exc:
        checks.append(
            build_provider_status_check(
                "runtime_env", ERROR, str(exc), details=runtime_details
            )
        )

    dependency_details = _dependency_details()
    if dependency_available:
        checks.append(
            build_provider_status_check(
                "playwright_dependency",
                OK,
                "Playwright and CloakBrowser Python packages are importable; CDP connection is not probed.",
                details=dependency_details,
            )
        )
    else:
        checks.append(
            build_provider_status_check(
                "playwright_dependency",
                NOT_CONFIGURED,
                "Playwright or CloakBrowser Python package is not installed.",
                details=dependency_details,
            )
        )

    missing_env: list[str] = []
    for check in checks:
        for name in check.missing_env:
            if name not in missing_env:
                missing_env.append(name)

    if any(check.status == ERROR for check in checks):
        status = ERROR
    elif all(check.status == OK for check in checks):
        status = READY
    else:
        status = NOT_CONFIGURED

    return ProviderStatusResult(
        provider=provider,
        status=status,
        available=status == READY,
        official_provider=True,
        missing_env=missing_env,
        notes=[],
        checks=list(checks),
    )


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
        or DEFAULT_CLOAKBROWSER_TIMEOUT_MS
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
    context: Any, *, final_url: str, user_agent: str | None
) -> dict[str, Any]:
    already_filtered = False
    try:
        cookies = context.cookies([final_url])
        already_filtered = True
    except TypeError:
        try:
            cookies = context.cookies()
        except Exception:
            cookies = []
    except Exception:
        cookies = []
    if not already_filtered:
        cookies = filter_browser_cookies_for_url(list(cookies or []), final_url)
    return {
        "browser_cookies": normalize_browser_cookies_for_playwright(
            cookies,
            fallback_url=final_url,
        ),
        "browser_user_agent": normalize_text(user_agent) or None,
        "browser_final_url": final_url,
    }


def _safe_close(value: Any) -> None:
    if value is None:
        return
    with contextlib.suppress(Exception):
        value.close()


def _raise_if_cancelled(runtime_context: RuntimeContext | None) -> None:
    cancel_check = getattr(runtime_context, "cancel_check", None)
    if callable(cancel_check) and cancel_check() is True:
        raise RequestCancelledError("Request cancelled.")


def _storage_state_path(config: CloakBrowserRuntimeConfig) -> Path | None:
    return runtime_paths.storage_state_path(config)


def _storage_context_options(config: CloakBrowserRuntimeConfig) -> dict[str, Any]:
    return runtime_paths.storage_context_options(config)


def _storage_origin_matches_url(origin: Mapping[str, Any], url: str | None) -> bool:
    return runtime_paths.storage_origin_matches_url(origin, url)


def _filtered_storage_state_payload(
    context: Any, *, url: str
) -> Mapping[str, Any] | None:
    return runtime_paths.filtered_storage_state_payload(context, url=url)


def _save_storage_state(
    context: Any,
    config: CloakBrowserRuntimeConfig,
    *,
    filter_url: str | None = None,
) -> dict[str, Any]:
    result = runtime_paths.save_storage_state(context, config, filter_url=filter_url)
    if result.get("attempted") and not result.get("saved"):
        logger.debug(
            "cloakbrowser_storage_state provider=%s action=save_failed path=%s",
            config.provider,
            result.get("path"),
        )
    return result


def fetch_html_with_cloakbrowser(
    candidate_urls: list[str],
    *,
    publisher: str,
    config: CloakBrowserRuntimeConfig,
    wait_seconds: int = DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS,
    warm_wait_seconds: int = DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS,
    max_timeout_ms: int | None = None,
    return_image_payload: bool = False,
    return_screenshot: bool = False,
    disable_media: bool = False,
    runtime_context: RuntimeContext | None = None,
) -> BrowserFetchedHtml:
    del warm_wait_seconds
    if not candidate_urls:
        raise CloakBrowserFailure(
            "empty_html_attempts", "No publisher HTML candidates were attempted."
        )
    if return_image_payload:
        disable_media = False

    last_failure: CloakBrowserFailure | None = None
    latest_browser_context_seed: Mapping[str, Any] | None = None
    latest_storage_state_url: str | None = None
    timeout_ms = max_timeout_ms or config.timeout_ms
    artifact_dir = config.artifact_dir / "cloakbrowser"
    configured_user_agent = normalize_text(config.user_agent)
    trace: dict[str, Any] = {
        "backend": "cloakbrowser",
        "candidate_count": len(candidate_urls),
        "candidates": [],
        "media_blocking": bool(disable_media),
        "return_image_payload": bool(return_image_payload),
        "return_screenshot": bool(return_screenshot),
        "external_cdp": bool(config.cdp_endpoint),
        "storage_state_path": str(_storage_state_path(config) or ""),
    }
    overall_started = time.monotonic()

    manager = None
    browser_context = None
    page = None
    try:
        _raise_if_cancelled(runtime_context)
        try:
            connect_started = time.monotonic()
            context_kwargs = browser_context_options(
                user_agent=configured_user_agent,
                **_storage_context_options(config),
            )
            if runtime_context is not None:
                from ..runtime import RuntimeContext

                if isinstance(runtime_context, RuntimeContext):
                    browser_context = runtime_context.new_browser_context_for_config(
                        headless=config.headless,
                        binary_path=config.binary_path,
                        cdp_endpoint=config.cdp_endpoint,
                        external_new_context=config.external_new_context,
                        profile_dir=config.profile_dir,
                        user_data_dir=config.user_data_dir,
                        **context_kwargs,
                    )
                else:
                    browser_context = runtime_context.new_browser_context(
                        headless=config.headless,
                        **context_kwargs,
                    )
            else:
                manager = BrowserContextManager(
                    binary_path=config.binary_path,
                    cdp_endpoint=config.cdp_endpoint,
                    external_new_context=config.external_new_context,
                    profile_dir=config.profile_dir,
                    user_data_dir=config.user_data_dir,
                )
                browser_context = manager.new_context(
                    headless=config.headless, **context_kwargs
                )
            trace["cdp_connect_seconds"] = round(time.monotonic() - connect_started, 3)
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
            page = browser_context.new_page()
        except Exception as exc:
            trace["cdp_connect_seconds"] = round(time.monotonic() - connect_started, 3)
            raise CloakBrowserFailure(
                "cdp_browser_connection_failed",
                normalize_text(str(exc)) or "CDP browser connection failed.",
                details={"trace": trace},
            ) from exc

        def route_handler(route: Any) -> None:
            try:
                resource_type = normalize_text(
                    str(route.request.resource_type or "")
                ).lower()
                if (
                    disable_media
                    and resource_type in BROWSER_HTML_BLOCKED_RESOURCE_TYPES
                ):
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
                    "cloakbrowser_request provider=%s action=request wait_seconds=%s url=%s",
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
                        wait_until="domcontentloaded",
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
                if isinstance(exc, CloakBrowserFailure):
                    last_failure = exc
                else:
                    last_failure = CloakBrowserFailure(
                        "cloakbrowser_request_failed",
                        normalize_text(str(exc)) or "CloakBrowser page request failed.",
                        details={"trace": trace},
                    )
                continue

            if looks_like_abstract_redirect(normalized_url, final_url):
                candidate_trace["duration_seconds"] = round(
                    time.monotonic() - candidate_started, 3
                )
                candidate_trace["block_reason"] = REDIRECTED_TO_ABSTRACT
                last_failure = CloakBrowserFailure(
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
                last_failure = CloakBrowserFailure(
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
                last_failure = CloakBrowserFailure(
                    "empty_html_response",
                    "CloakBrowser returned empty publisher HTML.",
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
        trace["storage_state_save"] = _save_storage_state(
            browser_context, config, filter_url=latest_storage_state_url
        )
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
        last_failure = CloakBrowserFailure(
            "empty_html_attempts",
            "No publisher HTML candidates were attempted.",
            browser_context_seed=latest_browser_context_seed,
            details={"trace": trace},
        )
    if last_failure is None:
        last_failure = CloakBrowserFailure(
            "empty_html_attempts",
            "No publisher HTML candidates were attempted.",
            details={"trace": trace},
        )
    if artifact_dir:
        with contextlib.suppress(OSError):
            artifact_dir.mkdir(parents=True, exist_ok=True)
    raise last_failure


fetch_html_with_cloakbrowser.paper_fetch_html_fetcher_name = "cloakbrowser"  # type: ignore[attr-defined]


def fetch_html_with_cloakbrowser_fast(*args: Any, **kwargs: Any) -> BrowserFetchedHtml:
    return fetch_html_with_cloakbrowser(*args, **kwargs)


fetch_html_with_cloakbrowser_fast.paper_fetch_html_fetcher_name = "cloakbrowser_fast"  # type: ignore[attr-defined]


def warm_browser_context_with_cloakbrowser(
    candidate_urls: list[str],
    *,
    publisher: str,
    config: CloakBrowserRuntimeConfig,
    browser_context_seed: Mapping[str, Any] | None = None,
    runtime_context: RuntimeContext | None = None,
) -> dict[str, Any]:
    merged_seed = merge_browser_context_seeds(browser_context_seed)
    if not candidate_urls:
        return merged_seed

    try:
        result = fetch_html_with_cloakbrowser(
            candidate_urls,
            publisher=publisher,
            config=config,
            runtime_context=runtime_context,
        )
    except CloakBrowserFailure as exc:
        return merge_browser_context_seeds(merged_seed, exc.browser_context_seed)
    return merge_browser_context_seeds(merged_seed, result.browser_context_seed)
