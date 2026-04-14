"""FlareSolverr helpers for Science/PNAS provider access."""

from __future__ import annotations

import atexit
import base64
import json
import logging
import math
import os
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import urllib3

from ..config import (
    FLARESOLVERR_MAX_REQUESTS_PER_DAY_ENV_VAR,
    FLARESOLVERR_MAX_REQUESTS_PER_HOUR_ENV_VAR,
    FLARESOLVERR_MIN_INTERVAL_SECONDS_ENV_VAR,
    configured_int_env,
    load_env_file,
    resolve_flaresolverr_env_file,
    resolve_flaresolverr_source_dir,
    resolve_flaresolverr_url,
    resolve_user_data_dir,
)
from ..utils import normalize_text, sanitize_filename
from .base import ProviderFailure
from ._science_pnas_html import (
    choose_parser,
    detect_html_block,
    extract_page_title,
    looks_like_abstract_redirect,
    summarize_html,
)

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    BeautifulSoup = None

CLOUDFLARE_COOKIE_NAMES = {
    "_cfuvid",
    "__cf_bm",
    "cf_clearance",
}
DEFAULT_FLARESOLVERR_WAIT_SECONDS = 8
DEFAULT_FLARESOLVERR_WARM_WAIT_SECONDS = 1
DEFAULT_FLARESOLVERR_MAX_TIMEOUT_MS = 120000

logger = logging.getLogger("paper_fetch.providers.flaresolverr")


@dataclass
class FlareSolverrSessionState:
    session_id: str
    created_at: float
    last_used_at: float
    warm: bool = False


_SESSION_REGISTRY: dict[tuple[str, str], FlareSolverrSessionState] = {}
_SESSION_LOCKS: dict[tuple[str, str], threading.RLock] = {}
_SESSION_REGISTRY_LOCK = threading.RLock()
_RATE_LIMIT_LOCK = threading.RLock()


@dataclass(frozen=True)
class FlareSolverrRuntimeConfig:
    provider: str
    doi: str
    url: str
    env_file: Path
    source_dir: Path
    artifact_dir: Path
    headless: bool
    min_interval_seconds: int
    max_requests_per_hour: int
    max_requests_per_day: int
    rate_limit_file: Path
    required_files: tuple[str, ...] = field(
        default=(
            "setup_flaresolverr_source.sh",
            "start_flaresolverr_source.sh",
            "run_flaresolverr_source.sh",
            "stop_flaresolverr_source.sh",
            "flaresolverr_source_common.sh",
        )
    )


@dataclass(frozen=True)
class FetchedPublisherHtml:
    source_url: str
    final_url: str
    html: str
    response_status: int | None
    response_headers: Mapping[str, str]
    title: str | None
    summary: str
    browser_context_seed: Mapping[str, Any]


class FlareSolverrFailure(Exception):
    def __init__(
        self,
        kind: str,
        message: str,
        *,
        browser_context_seed: Mapping[str, Any] | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.browser_context_seed = dict(browser_context_seed or {})
        self.details = dict(details or {})


def load_runtime_config(env: Mapping[str, str], *, provider: str, doi: str) -> FlareSolverrRuntimeConfig:
    source_dir = resolve_flaresolverr_source_dir(env)
    env_file = resolve_flaresolverr_env_file(env)
    if env_file is None:
        raise ProviderFailure(
            "not_configured",
            (
                "Science/PNAS requires FLARESOLVERR_ENV_FILE pointing at a repo-local vendor/flaresolverr preset. "
                "Start the service with ./scripts/flaresolverr-up <preset> first."
            ),
        )
    if not env_file.exists():
        raise ProviderFailure("not_configured", f"Configured FLARESOLVERR_ENV_FILE does not exist: {env_file}")

    min_interval_seconds = configured_int_env(FLARESOLVERR_MIN_INTERVAL_SECONDS_ENV_VAR, env)
    max_requests_per_hour = configured_int_env(FLARESOLVERR_MAX_REQUESTS_PER_HOUR_ENV_VAR, env)
    max_requests_per_day = configured_int_env(FLARESOLVERR_MAX_REQUESTS_PER_DAY_ENV_VAR, env)
    missing = [
        name
        for name, value in (
            (FLARESOLVERR_MIN_INTERVAL_SECONDS_ENV_VAR, min_interval_seconds),
            (FLARESOLVERR_MAX_REQUESTS_PER_HOUR_ENV_VAR, max_requests_per_hour),
            (FLARESOLVERR_MAX_REQUESTS_PER_DAY_ENV_VAR, max_requests_per_day),
        )
        if value is None
    ]
    if missing:
        raise ProviderFailure(
            "not_configured",
            "Science/PNAS requires explicit local rate-limit settings: " + ", ".join(missing),
        )

    env_values = load_env_file(env_file)
    headless = normalize_text(env_values.get("HEADLESS", "true")).lower() != "false"
    artifact_dir = resolve_user_data_dir(env) / "science-pnas-artifacts" / provider / sanitize_filename(doi)
    rate_limit_file = resolve_user_data_dir(env) / "science_pnas_rate_limits.json"
    return FlareSolverrRuntimeConfig(
        provider=provider,
        doi=doi,
        url=resolve_flaresolverr_url(env),
        env_file=env_file,
        source_dir=source_dir,
        artifact_dir=artifact_dir,
        headless=headless,
        min_interval_seconds=int(min_interval_seconds or 0),
        max_requests_per_hour=int(max_requests_per_hour or 0),
        max_requests_per_day=int(max_requests_per_day or 0),
        rate_limit_file=rate_limit_file,
    )


def ensure_runtime_ready(config: FlareSolverrRuntimeConfig) -> None:
    if not config.source_dir.exists():
        raise ProviderFailure(
            "not_configured",
            (
                "Science/PNAS support is repo-local only. Missing vendor/flaresolverr under the current checkout: "
                f"{config.source_dir}"
            ),
        )
    missing_files = [name for name in config.required_files if not (config.source_dir / name).exists()]
    if missing_files:
        raise ProviderFailure(
            "not_configured",
            (
                "Science/PNAS support requires the repo-local vendor/flaresolverr workflow. "
                f"Missing files: {', '.join(missing_files)}"
            ),
        )
    health_check(config.url)


def health_check(url: str) -> None:
    try:
        payload = post_to_flaresolverr(url, {"cmd": "sessions.list"}, timeout_seconds=10.0)
    except FlareSolverrFailure as exc:
        raise ProviderFailure(
            "not_configured",
            (
                "Science/PNAS requires a running local FlareSolverr service. "
                f"Health check failed for {url}: {exc.message}. Start it with ./scripts/flaresolverr-up <preset>."
            ),
        ) from exc
    if normalize_text(str(payload.get("status") or "")).lower() not in {"", "ok"}:
        raise ProviderFailure(
            "not_configured",
            (
                "Science/PNAS requires a running local FlareSolverr service. "
                f"Health check returned status={payload.get('status')!r} message={payload.get('message')!r}. "
                "Start it with ./scripts/flaresolverr-up <preset>."
            ),
        )


def enforce_rate_limits(config: FlareSolverrRuntimeConfig) -> None:
    with _RATE_LIMIT_LOCK:
        data_path = config.rate_limit_file
        data_path.parent.mkdir(parents=True, exist_ok=True)
        state: dict[str, Any] = {}
        if data_path.exists():
            try:
                state = json.loads(data_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                state = {}

        provider_state = state.get(config.provider)
        if not isinstance(provider_state, dict):
            provider_state = {}
        now = time.time()
        recorded = [float(item) for item in provider_state.get("events", []) or [] if isinstance(item, (int, float))]
        recorded = [item for item in recorded if now - item < 86400]
        last_request_at = float(provider_state.get("last_request_at") or 0.0)
        hourly = [item for item in recorded if now - item < 3600]

        if last_request_at and config.min_interval_seconds > 0 and (now - last_request_at) < config.min_interval_seconds:
            retry_after = max(1, math.ceil(config.min_interval_seconds - (now - last_request_at)))
            raise ProviderFailure(
                "rate_limited",
                (
                    f"{config.provider} requests must be spaced by at least {config.min_interval_seconds} seconds. "
                    f"Retry in about {retry_after} seconds."
                ),
                retry_after_seconds=retry_after,
            )
        if config.max_requests_per_hour > 0 and len(hourly) >= config.max_requests_per_hour:
            retry_after = max(1, math.ceil(3600 - (now - min(hourly))))
            raise ProviderFailure(
                "rate_limited",
                f"{config.provider} hourly request cap reached ({config.max_requests_per_hour}/hour).",
                retry_after_seconds=retry_after,
            )
        if config.max_requests_per_day > 0 and len(recorded) >= config.max_requests_per_day:
            retry_after = max(1, math.ceil(86400 - (now - min(recorded))))
            raise ProviderFailure(
                "rate_limited",
                f"{config.provider} daily request cap reached ({config.max_requests_per_day}/day).",
                retry_after_seconds=retry_after,
            )

        recorded.append(now)
        state[config.provider] = {
            "last_request_at": now,
            "events": recorded,
        }
        fd, temp_path = tempfile.mkstemp(prefix="science_pnas_rate_limits_", suffix=".json")
        temp_file = Path(temp_path)
        try:
            os.close(fd)
            temp_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_file.replace(data_path)
        finally:
            temp_file.unlink(missing_ok=True)


def normalize_browser_cookie_for_playwright(
    cookie: dict[str, Any],
    fallback_url: str | None = None,
) -> dict[str, Any] | None:
    name = normalize_text(str(cookie.get("name") or ""))
    if not name:
        return None

    normalized: dict[str, Any] = {
        "name": name,
        "value": str(cookie.get("value") or ""),
    }
    domain = normalize_text(str(cookie.get("domain") or ""))
    path = normalize_text(str(cookie.get("path") or "")) or "/"
    if domain:
        normalized["domain"] = domain
        normalized["path"] = path
    elif fallback_url:
        normalized["url"] = fallback_url
    else:
        return None

    if cookie.get("secure") is not None:
        normalized["secure"] = bool(cookie.get("secure"))
    if cookie.get("httpOnly") is not None:
        normalized["httpOnly"] = bool(cookie.get("httpOnly"))

    expires_value = cookie.get("expiry")
    if expires_value is None:
        expires_value = cookie.get("expires")
    if expires_value is not None:
        try:
            normalized["expires"] = float(expires_value)
        except (TypeError, ValueError):
            pass

    same_site = normalize_text(str(cookie.get("sameSite") or ""))
    canonical_same_site = {
        "lax": "Lax",
        "strict": "Strict",
        "none": "None",
    }.get(same_site.lower())
    if canonical_same_site:
        normalized["sameSite"] = canonical_same_site
    return normalized


def normalize_browser_cookies_for_playwright(
    cookies: list[dict[str, Any]] | None,
    fallback_url: str | None = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for cookie in cookies or []:
        if not isinstance(cookie, dict):
            continue
        normalized_cookie = normalize_browser_cookie_for_playwright(cookie, fallback_url=fallback_url)
        if normalized_cookie is not None:
            normalized.append(normalized_cookie)
    return normalized


def extract_flaresolverr_browser_context_seed(solution: dict[str, Any]) -> dict[str, Any]:
    final_url = solution.get("url") if isinstance(solution.get("url"), str) else None
    return {
        "browser_cookies": normalize_browser_cookies_for_playwright(
            solution.get("cookies") if isinstance(solution.get("cookies"), list) else None,
            fallback_url=final_url,
        ),
        "browser_user_agent": normalize_text(str(solution.get("userAgent") or "")) or None,
        "browser_final_url": final_url,
    }


def redact_flaresolverr_response_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted_payload = json.loads(json.dumps(payload, ensure_ascii=False))
    solution = redacted_payload.get("solution")
    if not isinstance(solution, dict):
        return redacted_payload
    cookies = solution.get("cookies")
    if not isinstance(cookies, list):
        return redacted_payload

    redacted_cookies: list[dict[str, Any]] = []
    for cookie in cookies:
        if not isinstance(cookie, dict):
            continue
        redacted_cookie = dict(cookie)
        if "value" in redacted_cookie:
            redacted_cookie["value"] = "[redacted]"
        redacted_cookies.append(redacted_cookie)
    solution["cookies"] = redacted_cookies
    return redacted_payload


def save_flaresolverr_failure_artifacts(
    artifact_dir: Path,
    *,
    html: str | None = None,
    screenshot_b64: str | None = None,
    response_payload: dict[str, Any] | None = None,
) -> dict[str, str]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_paths: dict[str, str] = {}

    if html:
        html_path = artifact_dir / "html.failure.html"
        html_path.write_text(html, encoding="utf-8")
        artifact_paths["html_path"] = str(html_path)

    if screenshot_b64:
        screenshot_path = artifact_dir / "html.failure.png"
        try:
            screenshot_path.write_bytes(decode_base64_blob(screenshot_b64))
            artifact_paths["screenshot_path"] = str(screenshot_path)
        except Exception:
            pass

    if response_payload is not None:
        response_path = artifact_dir / "html.failure.response.json"
        response_path.write_text(
            json.dumps(redact_flaresolverr_response_payload(response_payload), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        artifact_paths["response_path"] = str(response_path)
    return artifact_paths


def decode_base64_blob(data: str) -> bytes:
    payload = data or ""
    if "," in payload and payload.lower().startswith("data:"):
        payload = payload.split(",", 1)[1]
    return base64.b64decode(payload)


def build_local_service_pool() -> urllib3.PoolManager:
    return urllib3.PoolManager()


def _session_registry_key(config: FlareSolverrRuntimeConfig) -> tuple[str, str]:
    return (config.url.rstrip("/"), config.provider)


def _session_lock_for(config: FlareSolverrRuntimeConfig) -> threading.RLock:
    key = _session_registry_key(config)
    with _SESSION_REGISTRY_LOCK:
        lock = _SESSION_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _SESSION_LOCKS[key] = lock
        return lock


def _destroy_remote_session(
    base_url: str,
    session_id: str,
    *,
    pool: urllib3.PoolManager | None = None,
) -> None:
    try:
        response = post_to_flaresolverr(
            base_url,
            {"cmd": "sessions.destroy", "session": session_id},
            timeout_seconds=30.0,
            pool=pool,
        )
    except FlareSolverrFailure:
        return
    message = normalize_text(str(response.get("message") or ""))
    status = normalize_text(str(response.get("status") or "")).lower()
    if status not in {"", "ok"} and not is_invalid_session_message(message):
        logger.debug(
            "flaresolverr_session provider=%s action=destroy_failed session_id=%s message=%s",
            "unknown",
            session_id,
            message or response.get("status"),
        )


def _create_registered_session(
    config: FlareSolverrRuntimeConfig,
    *,
    pool: urllib3.PoolManager,
    action: str,
) -> FlareSolverrSessionState:
    session_id = f"{sanitize_filename(config.provider)}-{uuid.uuid4().hex[:12]}"
    create_response = post_to_flaresolverr(
        config.url,
        {"cmd": "sessions.create", "session": session_id},
        timeout_seconds=30.0,
        pool=pool,
    )
    if normalize_text(str(create_response.get("status") or "")).lower() not in {"", "ok"}:
        raise FlareSolverrFailure(
            "flaresolverr_session_create_failed",
            normalize_text(str(create_response.get("message") or "")) or "FlareSolverr refused to create a session.",
            details={"response": create_response},
        )
    now = time.time()
    session_state = FlareSolverrSessionState(
        session_id=session_id,
        created_at=now,
        last_used_at=now,
        warm=False,
    )
    with _SESSION_REGISTRY_LOCK:
        _SESSION_REGISTRY[_session_registry_key(config)] = session_state
    logger.debug(
        "flaresolverr_session provider=%s action=%s session_id=%s warm=%s",
        config.provider,
        action,
        session_id,
        session_state.warm,
    )
    return session_state


def _acquire_registered_session(
    config: FlareSolverrRuntimeConfig,
    *,
    pool: urllib3.PoolManager,
    recreate: bool = False,
) -> FlareSolverrSessionState:
    key = _session_registry_key(config)
    with _SESSION_REGISTRY_LOCK:
        session_state = _SESSION_REGISTRY.get(key)
        if session_state is not None and not recreate:
            session_state.last_used_at = time.time()
            logger.debug(
                "flaresolverr_session provider=%s action=reuse session_id=%s warm=%s",
                config.provider,
                session_state.session_id,
                session_state.warm,
            )
            return session_state
    return _create_registered_session(config, pool=pool, action="recreate" if recreate else "create")


def _mark_registered_session_used(config: FlareSolverrRuntimeConfig, session_state: FlareSolverrSessionState) -> None:
    with _SESSION_REGISTRY_LOCK:
        registered = _SESSION_REGISTRY.get(_session_registry_key(config))
        if registered is None or registered.session_id != session_state.session_id:
            return
        registered.last_used_at = time.time()
        registered.warm = True


def _evict_registered_session(
    config: FlareSolverrRuntimeConfig,
    *,
    pool: urllib3.PoolManager,
    reason: str,
) -> FlareSolverrSessionState | None:
    key = _session_registry_key(config)
    with _SESSION_REGISTRY_LOCK:
        session_state = _SESSION_REGISTRY.pop(key, None)
    if session_state is None:
        return None
    logger.debug(
        "flaresolverr_session provider=%s action=evict reason=%s session_id=%s",
        config.provider,
        reason,
        session_state.session_id,
    )
    _destroy_remote_session(config.url, session_state.session_id, pool=pool)
    return session_state


def _wait_seconds_for_session(
    session_state: FlareSolverrSessionState,
    *,
    cold_wait_seconds: int,
    warm_wait_seconds: int,
) -> tuple[int, str]:
    if session_state.warm:
        return warm_wait_seconds, "warm"
    return cold_wait_seconds, "cold"


def is_invalid_session_message(message: str | None) -> bool:
    normalized = normalize_text(message or "").lower()
    if "session" not in normalized:
        return False
    return any(
        pattern in normalized
        for pattern in (
            "session not found",
            "invalid session",
            "unknown session",
            "session does not exist",
            "session doesn't exist",
            "session not exists",
            "no such session",
        )
    )


def reset_session_registry_for_tests() -> None:
    with _SESSION_REGISTRY_LOCK:
        _SESSION_REGISTRY.clear()
        _SESSION_LOCKS.clear()


def _destroy_registered_sessions_at_exit() -> None:
    with _SESSION_REGISTRY_LOCK:
        registered = list(_SESSION_REGISTRY.items())
        _SESSION_REGISTRY.clear()
    for (base_url, provider), session_state in registered:
        try:
            logger.debug(
                "flaresolverr_session provider=%s action=destroy_at_exit session_id=%s",
                provider,
                session_state.session_id,
            )
            _destroy_remote_session(base_url, session_state.session_id)
        except Exception:
            continue


atexit.register(_destroy_registered_sessions_at_exit)


def post_to_flaresolverr(
    base_url: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
    pool: urllib3.PoolManager | None = None,
) -> dict[str, Any]:
    client = pool or build_local_service_pool()
    try:
        response = client.request(
            "POST",
            base_url.rstrip("/"),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            body=json.dumps(payload).encode("utf-8"),
            timeout=urllib3.Timeout(connect=timeout_seconds, read=timeout_seconds),
            retries=False,
        )
    except urllib3.exceptions.ReadTimeoutError as exc:
        raise FlareSolverrFailure("flaresolverr_timeout", f"Timed out while calling FlareSolverr: {exc}") from exc
    except urllib3.exceptions.HTTPError as exc:
        raise FlareSolverrFailure("flaresolverr_transport_error", f"Failed to call FlareSolverr: {exc}") from exc

    try:
        payload_json = json.loads(response.data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FlareSolverrFailure(
            "invalid_flaresolverr_response",
            f"FlareSolverr returned non-JSON content: {exc}",
        ) from exc
    if not isinstance(payload_json, dict):
        raise FlareSolverrFailure(
            "invalid_flaresolverr_response",
            "FlareSolverr returned a non-object JSON payload.",
        )
    return payload_json


def fetch_html_with_flaresolverr(
    candidate_urls: list[str],
    *,
    publisher: str,
    config: FlareSolverrRuntimeConfig,
    wait_seconds: int = DEFAULT_FLARESOLVERR_WAIT_SECONDS,
    warm_wait_seconds: int = DEFAULT_FLARESOLVERR_WARM_WAIT_SECONDS,
    max_timeout_ms: int = DEFAULT_FLARESOLVERR_MAX_TIMEOUT_MS,
) -> FetchedPublisherHtml:
    if not candidate_urls:
        raise FlareSolverrFailure("empty_html_attempts", "No publisher HTML candidates were attempted.")

    last_failure: FlareSolverrFailure | None = None
    latest_browser_context_seed: Mapping[str, Any] | None = None
    pool = build_local_service_pool()
    artifact_dir = config.artifact_dir / "flaresolverr"
    session_lock = _session_lock_for(config)

    with session_lock:
        enforce_rate_limits(config)
        session_state = _acquire_registered_session(config, pool=pool)

        for url in candidate_urls:
            challenge_retried = False
            session_recreated = False
            force_cold_retry = False

            while True:
                if session_state is None:
                    session_state = _acquire_registered_session(config, pool=pool)

                effective_wait_seconds = wait_seconds
                wait_mode = "cold"
                if not force_cold_retry:
                    effective_wait_seconds, wait_mode = _wait_seconds_for_session(
                        session_state,
                        cold_wait_seconds=wait_seconds,
                        warm_wait_seconds=warm_wait_seconds,
                    )
                logger.debug(
                    "flaresolverr_request provider=%s action=request session_id=%s wait_mode=%s wait_seconds=%s url=%s",
                    publisher,
                    session_state.session_id,
                    wait_mode,
                    effective_wait_seconds,
                    url,
                )
                request_payload = {
                    "cmd": "request.get",
                    "url": url,
                    "session": session_state.session_id,
                    "returnScreenshot": True,
                    "waitInSeconds": effective_wait_seconds,
                    "maxTimeout": max_timeout_ms,
                }
                try:
                    request_response = post_to_flaresolverr(
                        config.url,
                        request_payload,
                        timeout_seconds=(max_timeout_ms / 1000.0) + 45.0,
                        pool=pool,
                    )
                except FlareSolverrFailure as exc:
                    last_failure = exc
                    break

                top_level_status = normalize_text(str(request_response.get("status") or "")).lower()
                if top_level_status and top_level_status != "ok":
                    message = normalize_text(str(request_response.get("message") or ""))
                    if is_invalid_session_message(message):
                        _evict_registered_session(config, pool=pool, reason="invalid_session")
                        session_state = None
                        if not session_recreated:
                            session_recreated = True
                            session_state = _acquire_registered_session(config, pool=pool, recreate=True)
                            force_cold_retry = True
                            continue
                        last_failure = FlareSolverrFailure(
                            "flaresolverr_session_invalid",
                            message or "FlareSolverr session became invalid.",
                            details={"response": request_response},
                        )
                        save_flaresolverr_failure_artifacts(artifact_dir, response_payload=request_response)
                        break
                    error_kind = "flaresolverr_timeout" if "timeout" in message.lower() else "flaresolverr_request_failed"
                    last_failure = FlareSolverrFailure(
                        error_kind,
                        message or "FlareSolverr request.get failed.",
                        details={"response": request_response},
                    )
                    save_flaresolverr_failure_artifacts(artifact_dir, response_payload=request_response)
                    break

                solution = request_response.get("solution") or {}
                html = str(solution.get("response") or "")
                final_url = str(solution.get("url") or url)
                response_status = parse_optional_int(solution.get("status"))
                response_headers = solution.get("headers") if isinstance(solution.get("headers"), dict) else {}
                if BeautifulSoup is not None:
                    title = extract_page_title(BeautifulSoup(html, choose_parser()))
                else:
                    title = None
                summary = summarize_html(html)
                browser_context_seed = extract_flaresolverr_browser_context_seed(solution)
                if browser_context_seed.get("browser_cookies") or browser_context_seed.get("browser_user_agent"):
                    latest_browser_context_seed = browser_context_seed
                _mark_registered_session_used(config, session_state)
                force_cold_retry = False

                if looks_like_abstract_redirect(url, final_url):
                    last_failure = FlareSolverrFailure(
                        "redirected_to_abstract",
                        "Publisher redirected the full-text URL to an abstract page.",
                        browser_context_seed=browser_context_seed,
                    )
                    save_flaresolverr_failure_artifacts(
                        artifact_dir,
                        html=html,
                        screenshot_b64=solution.get("screenshot"),
                        response_payload=request_response,
                    )
                    break

                detected = detect_html_block(title or "", summary, response_status)
                if detected is not None:
                    if detected.reason == "cloudflare_challenge" and wait_mode == "warm" and not challenge_retried:
                        challenge_retried = True
                        force_cold_retry = True
                        logger.debug(
                            "flaresolverr_request provider=%s action=retry_challenge session_id=%s wait_mode=cold url=%s",
                            publisher,
                            session_state.session_id,
                            url,
                        )
                        continue
                    last_failure = FlareSolverrFailure(
                        detected.reason,
                        detected.message,
                        browser_context_seed=browser_context_seed,
                    )
                    save_flaresolverr_failure_artifacts(
                        artifact_dir,
                        html=html,
                        screenshot_b64=solution.get("screenshot"),
                        response_payload=request_response,
                    )
                    break

                return FetchedPublisherHtml(
                    source_url=url,
                    final_url=final_url,
                    html=html,
                    response_status=response_status,
                    response_headers=response_headers,
                    title=title,
                    summary=summary,
                    browser_context_seed=browser_context_seed,
                )

    if last_failure is None and latest_browser_context_seed is not None:
        last_failure = FlareSolverrFailure(
            "empty_html_attempts",
            "No publisher HTML candidates were attempted.",
            browser_context_seed=latest_browser_context_seed,
        )
    if last_failure is None:
        last_failure = FlareSolverrFailure("empty_html_attempts", "No publisher HTML candidates were attempted.")
    raise last_failure


def parse_optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
