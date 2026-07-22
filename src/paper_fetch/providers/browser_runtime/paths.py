"""Storage-state and profile paths for browser runtime backends."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from collections.abc import Mapping
from urllib.parse import urlparse

from filelock import FileLock

from ...config import (
    BROWSER_PROFILE_DIR_ENV_VAR,
    BROWSER_USER_DATA_DIR_ENV_VAR,
    CLOAKBROWSER_PROFILE_DIR_ENV_VAR,
    CLOAKBROWSER_USER_DATA_DIR_ENV_VAR,
    WILEY_PROFILE_DIR_ENV_VAR,
    WILEY_STORAGE_STATE_JSON_ENV_VAR,
    browser_env_value,
    resolve_user_data_dir,
)
from ...runtime_browser import is_borrowed_browser_context
from ...utils import normalize_text, sanitize_filename
from .seed import filter_browser_cookies_for_url
from .types import BrowserRuntimeConfig

STORAGE_STATE_FILENAME = "storage-state.json"
STORAGE_STATE_LOCK_SUFFIX = ".lock"
PROVIDER_PROFILE_DIR_ENV_VARS = {
    "wiley": WILEY_PROFILE_DIR_ENV_VAR,
}
PROVIDER_STORAGE_STATE_ENV_VARS = {
    "wiley": WILEY_STORAGE_STATE_JSON_ENV_VAR,
}


def default_provider_user_data_dir(
    env: Mapping[str, str], *, provider: str, backend: str
) -> Path:
    provider_key = sanitize_filename(normalize_text(provider).lower() or "browser")
    if normalize_text(backend).lower() == "camoufox":
        provider_key = f"{provider_key}-camoufox"
    return resolve_user_data_dir(env) / "publisher-browser-profiles" / provider_key


def provider_profile_env_var(provider: str) -> str | None:
    return PROVIDER_PROFILE_DIR_ENV_VARS.get(normalize_text(provider).lower())


def provider_storage_state_env_var(provider: str) -> str | None:
    return PROVIDER_STORAGE_STATE_ENV_VARS.get(normalize_text(provider).lower())


def configured_user_data_dir(env: Mapping[str, str], *, backend: str) -> Path | None:
    value = browser_env_value(
        env,
        BROWSER_USER_DATA_DIR_ENV_VAR,
        legacy_name=(
            CLOAKBROWSER_USER_DATA_DIR_ENV_VAR
            if normalize_text(backend).lower() == "cloakbrowser"
            else None
        ),
    )
    return Path(value).expanduser() if value else None


def configured_profile_dir(
    env: Mapping[str, str], *, provider: str, backend: str
) -> Path | None:
    generic_value = browser_env_value(env, BROWSER_PROFILE_DIR_ENV_VAR)
    if generic_value:
        return Path(generic_value).expanduser()
    provider_env_var = (
        provider_profile_env_var(provider)
        if normalize_text(backend).lower() == "cloakbrowser"
        else None
    )
    if provider_env_var is not None:
        provider_value = env.get(provider_env_var, "").strip()
        if provider_value:
            return Path(provider_value).expanduser()
    value = (
        env.get(CLOAKBROWSER_PROFILE_DIR_ENV_VAR, "").strip()
        if normalize_text(backend).lower() == "cloakbrowser"
        else ""
    )
    return Path(value).expanduser() if value else None


def configured_storage_state_path(
    env: Mapping[str, str], *, provider: str
) -> Path | None:
    env_var = provider_storage_state_env_var(provider)
    if env_var is None:
        return None
    value = env.get(env_var, "").strip()
    return Path(value).expanduser() if value else None


def runtime_with_default_storage_profile(
    runtime: BrowserRuntimeConfig,
    *,
    env: Mapping[str, str],
    provider: str,
) -> BrowserRuntimeConfig:
    if runtime.storage_state_path is not None:
        return runtime
    if runtime.profile_dir is not None or runtime.user_data_dir is not None:
        return runtime
    from dataclasses import replace

    return replace(
        runtime,
        user_data_dir=default_provider_user_data_dir(
            env, provider=provider, backend=runtime.backend
        ),
    )


def storage_state_path(config: BrowserRuntimeConfig) -> Path | None:
    if config.storage_state_path is not None:
        return Path(config.storage_state_path).expanduser()
    profile_dir = config.profile_dir or config.user_data_dir
    if profile_dir is None:
        return None
    return Path(profile_dir).expanduser() / STORAGE_STATE_FILENAME


def storage_context_options(config: BrowserRuntimeConfig) -> dict[str, Any]:
    path = storage_state_path(config)
    if path is None or not path.is_file():
        return {}
    return {"storage_state": str(path)}


def validate_storage_state_path(
    path: Path | None,
    *,
    provider: str,
    require_storage_state: bool,
) -> None:
    if path is None:
        return
    env_var = provider_storage_state_env_var(provider)
    if not path.is_file() and not require_storage_state:
        return
    label = env_var or "storage-state JSON"
    if not path.is_file():
        from ..base import ProviderFailure
        from ...reason_codes import NOT_CONFIGURED

        raise ProviderFailure(
            NOT_CONFIGURED,
            (
                f"{label} is set but does not point to a readable "
                f"storage-state JSON file: {path}"
            ),
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        from ..base import ProviderFailure
        from ...reason_codes import NOT_CONFIGURED

        raise ProviderFailure(
            NOT_CONFIGURED,
            f"{label} is not valid JSON: {path}",
        ) from exc
    if not isinstance(payload, Mapping):
        from ..base import ProviderFailure
        from ...reason_codes import NOT_CONFIGURED

        raise ProviderFailure(
            NOT_CONFIGURED,
            f"{label} must point to a JSON object: {path}",
        )


def storage_origin_matches_url(origin: Mapping[str, Any], url: str | None) -> bool:
    origin_url = normalize_text(str(origin.get("origin") or ""))
    target_url = normalize_text(url)
    if not origin_url or not target_url:
        return True
    try:
        origin_host = normalize_text(urlparse(origin_url).hostname or "").lower()
        target_host = normalize_text(urlparse(target_url).hostname or "").lower()
    except Exception:
        return True
    return bool(
        origin_host
        and target_host
        and (origin_host == target_host or target_host.endswith(f".{origin_host}"))
    )


def filtered_storage_state_payload(
    context: Any, *, url: str
) -> Mapping[str, Any] | None:
    try:
        payload = context.storage_state()
    except Exception:
        return None
    if not isinstance(payload, Mapping):
        return None
    filtered = dict(payload)
    payload_cookies = payload.get("cookies")
    cookies = payload_cookies if isinstance(payload_cookies, list) else []
    filtered["cookies"] = filter_browser_cookies_for_url(cookies, url)
    payload_origins = payload.get("origins")
    origins = payload_origins if isinstance(payload_origins, list) else []
    filtered["origins"] = [
        origin
        for origin in origins
        if isinstance(origin, Mapping) and storage_origin_matches_url(origin, url)
    ]
    return filtered


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.replace(path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        finally:
            raise


def save_storage_state(
    context: Any,
    config: BrowserRuntimeConfig,
    *,
    filter_url: str | None = None,
) -> dict[str, Any]:
    path = storage_state_path(config)
    result: dict[str, Any] = {
        "attempted": False,
        "saved": False,
        "path": str(path) if path is not None else None,
        "filtered": False,
        "borrowed_context": bool(is_borrowed_browser_context(context)),
    }
    if context is None or path is None:
        result["reason"] = "no_context_or_path"
        return result
    active_filter_url = normalize_text(filter_url)
    if result["borrowed_context"] and not active_filter_url:
        result["reason"] = "borrowed_context_without_filter_url"
        return result
    result["attempted"] = True
    lock = FileLock(str(path) + STORAGE_STATE_LOCK_SUFFIX)
    try:
        with lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            if active_filter_url:
                filtered_payload = filtered_storage_state_payload(
                    context, url=active_filter_url
                )
                if filtered_payload is not None:
                    _atomic_write_json(path, filtered_payload)
                    result["saved"] = True
                    result["filtered"] = True
                    result["cookie_count"] = len(filtered_payload.get("cookies") or [])
                    return result
                if result["borrowed_context"]:
                    result["reason"] = "borrowed_context_filter_unavailable"
                    return result
            try:
                payload = context.storage_state()
            except TypeError:
                payload = None
            if isinstance(payload, Mapping):
                _atomic_write_json(path, payload)
                result["cookie_count"] = len(payload.get("cookies") or [])
                result["saved"] = True
                return result
            context.storage_state(path=str(path))
            result["saved"] = True
            return result
    except Exception as exc:
        result["reason"] = "save_failed"
        result["error"] = normalize_text(str(exc)) or exc.__class__.__name__
        return result
