"""Storage-state and profile paths for browser runtime backends."""

from __future__ import annotations

import json
import os
import tempfile
import contextlib
from pathlib import Path
from typing import Any
from collections.abc import Mapping
from urllib.parse import urlparse

from filelock import FileLock
from filelock import Timeout as FileLockTimeout

from ...config import (
    AMS_STORAGE_STATE_JSON_ENV_VAR,
    BROWSER_PROFILE_DIR_ENV_VAR,
    BROWSER_USER_DATA_DIR_ENV_VAR,
    WILEY_PROFILE_DIR_ENV_VAR,
    WILEY_STORAGE_STATE_JSON_ENV_VAR,
    browser_env_value,
    resolve_user_data_dir,
)
from ...provider_catalog import (
    host_matches_domain,
    provider_domain_matches,
    provider_domains,
)
from ...utils import normalize_text, sanitize_filename
from .seed import filter_browser_cookies_for_url
from .types import BrowserRuntimeConfig, BrowserStagedStorageState

STORAGE_STATE_FILENAME = "storage-state.json"
STORAGE_STATE_LOCK_SUFFIX = ".lock"
PROVIDER_PROFILE_DIR_ENV_VARS = {
    "wiley": WILEY_PROFILE_DIR_ENV_VAR,
}
PROVIDER_STORAGE_STATE_ENV_VARS = {
    "ams": AMS_STORAGE_STATE_JSON_ENV_VAR,
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
    del backend
    value = browser_env_value(env, BROWSER_USER_DATA_DIR_ENV_VAR)
    return Path(value).expanduser() if value else None


def configured_profile_dir(
    env: Mapping[str, str], *, provider: str, backend: str
) -> Path | None:
    generic_value = browser_env_value(env, BROWSER_PROFILE_DIR_ENV_VAR)
    if generic_value:
        return Path(generic_value).expanduser()
    del backend
    provider_env_var = provider_profile_env_var(provider)
    if provider_env_var is not None:
        provider_value = env.get(provider_env_var, "").strip()
        if provider_value:
            return Path(provider_value).expanduser()
    return None


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
            env, provider=provider, backend="camoufox"
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
    explicit_path: bool = False,
) -> None:
    if path is None:
        if require_storage_state:
            from ..base import ProviderFailure
            from ...reason_codes import NOT_CONFIGURED

            env_var = provider_storage_state_env_var(provider)
            label = env_var or "storage-state JSON"
            raise ProviderFailure(
                NOT_CONFIGURED,
                f"{label} is required but no storage-state file is configured.",
            )
        return
    env_var = provider_storage_state_env_var(provider)
    if not path.is_file() and not (require_storage_state or explicit_path):
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
    schema_error = _storage_state_schema_error(payload)
    if schema_error:
        from ..base import ProviderFailure
        from ...reason_codes import NOT_CONFIGURED

        raise ProviderFailure(
            NOT_CONFIGURED,
            f"{label} has an invalid browser storage-state schema ({schema_error}): {path}",
        )


def _storage_state_schema_error(payload: Mapping[str, Any]) -> str | None:
    cookies = payload.get("cookies")
    origins = payload.get("origins")
    if not isinstance(cookies, list):
        return "cookies must be an array"
    if not isinstance(origins, list):
        return "origins must be an array"
    for index, cookie in enumerate(cookies):
        if not isinstance(cookie, Mapping):
            return f"cookies[{index}] must be an object"
        for key in ("name", "value", "domain", "path"):
            if not isinstance(cookie.get(key), str):
                return f"cookies[{index}].{key} must be a string"
        if not normalize_text(str(cookie.get("name") or "")):
            return f"cookies[{index}].name must not be empty"
        if not normalize_text(str(cookie.get("domain") or "")):
            return f"cookies[{index}].domain must not be empty"
        if not normalize_text(str(cookie.get("path") or "")):
            return f"cookies[{index}].path must not be empty"
    for index, origin in enumerate(origins):
        if not isinstance(origin, Mapping):
            return f"origins[{index}] must be an object"
        origin_url = origin.get("origin")
        if not isinstance(origin_url, str) or urlparse(origin_url).scheme not in {
            "http",
            "https",
        }:
            return f"origins[{index}].origin must be an HTTP(S) URL"
        local_storage = origin.get("localStorage", [])
        if not isinstance(local_storage, list):
            return f"origins[{index}].localStorage must be an array"
        for item_index, item in enumerate(local_storage):
            if not isinstance(item, Mapping) or not all(
                isinstance(item.get(key), str) for key in ("name", "value")
            ):
                return (
                    f"origins[{index}].localStorage[{item_index}] must contain "
                    "string name/value fields"
                )
    return None


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


def _storage_url_matches_provider(url: str, provider: str) -> bool:
    hostname = normalize_text(urlparse(url).hostname or "").lower()
    declared_domains = provider_domains(provider)
    return bool(
        hostname
        and (not declared_domains or provider_domain_matches(provider, hostname))
    )


def _cookie_matches_provider(cookie: Mapping[str, Any], provider: str) -> bool:
    cookie_domain = normalize_text(str(cookie.get("domain") or "")).lstrip(".").lower()
    domains = provider_domains(provider)
    return bool(
        cookie_domain
        and domains
        and any(host_matches_domain(cookie_domain, domain) for domain in domains)
    )


def _origin_matches_provider(origin: Mapping[str, Any], provider: str) -> bool:
    origin_url = normalize_text(str(origin.get("origin") or ""))
    hostname = normalize_text(urlparse(origin_url).hostname or "").lower()
    return bool(hostname and provider_domain_matches(provider, hostname))


def _filtered_storage_state_mapping(
    payload: Mapping[str, Any],
    *,
    url: str,
    provider: str | None = None,
) -> dict[str, Any] | None:
    active_provider = normalize_text(provider).lower()
    if active_provider and not _storage_url_matches_provider(url, active_provider):
        return None
    filtered = dict(payload)
    payload_cookies = payload.get("cookies")
    cookies = payload_cookies if isinstance(payload_cookies, list) else []
    if active_provider and provider_domains(active_provider):
        filtered["cookies"] = [
            dict(cookie)
            for cookie in cookies
            if isinstance(cookie, Mapping)
            and _cookie_matches_provider(cookie, active_provider)
        ]
    else:
        filtered["cookies"] = filter_browser_cookies_for_url(cookies, url)
    payload_origins = payload.get("origins")
    origins = payload_origins if isinstance(payload_origins, list) else []
    if active_provider and provider_domains(active_provider):
        filtered["origins"] = [
            dict(origin)
            for origin in origins
            if isinstance(origin, Mapping)
            and _origin_matches_provider(origin, active_provider)
        ]
    else:
        filtered["origins"] = [
            dict(origin)
            for origin in origins
            if isinstance(origin, Mapping) and storage_origin_matches_url(origin, url)
        ]
    return filtered


def filtered_storage_state_payload(
    context: Any, *, url: str, provider: str | None = None
) -> Mapping[str, Any] | None:
    try:
        payload = context.storage_state()
    except Exception:
        return None
    if not isinstance(payload, Mapping):
        return None
    return _filtered_storage_state_mapping(payload, url=url, provider=provider)


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


def stage_storage_state(
    context: Any,
    config: BrowserRuntimeConfig,
    *,
    filter_url: str | None,
) -> tuple[BrowserStagedStorageState | None, dict[str, Any]]:
    """Capture provider-scoped state without modifying the canonical state file."""

    path = storage_state_path(config)
    active_filter_url = normalize_text(filter_url)
    result: dict[str, Any] = {
        "attempted": False,
        "staged": False,
        "saved": False,
        "path": str(path) if path is not None else None,
        "filtered": False,
        "borrowed_context": False,
    }
    if context is None or path is None:
        result["reason"] = "no_context_or_path"
        return None, result
    if not active_filter_url:
        result["reason"] = "missing_filter_url"
        return None, result
    if not _storage_url_matches_provider(active_filter_url, config.provider):
        result["reason"] = "final_url_outside_provider"
        return None, result
    result["attempted"] = True
    try:
        filtered_payload = filtered_storage_state_payload(
            context,
            url=active_filter_url,
            provider=config.provider,
        )
    except Exception as exc:
        result["reason"] = "stage_failed"
        result["error"] = normalize_text(str(exc)) or exc.__class__.__name__
        return None, result
    if filtered_payload is None:
        result["reason"] = "provider_filter_unavailable"
        return None, result
    result.update(
        {
            "staged": True,
            "filtered": True,
            "cookie_count": len(filtered_payload.get("cookies") or []),
            "reason": "awaiting_provider_acceptance",
        }
    )
    return (
        BrowserStagedStorageState(
            path=path,
            provider=config.provider,
            filter_url=active_filter_url,
            payload=dict(filtered_payload),
        ),
        result,
    )


def _cookie_state_key(cookie: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        normalize_text(str(cookie.get("domain") or "")).lower(),
        normalize_text(str(cookie.get("path") or "/")),
        normalize_text(str(cookie.get("name") or "")),
    )


def _origin_state_key(origin: Mapping[str, Any]) -> str:
    return normalize_text(str(origin.get("origin") or "")).lower()


def _merge_storage_state_payloads(
    existing: Mapping[str, Any] | None,
    staged: Mapping[str, Any],
    *,
    provider: str,
    filter_url: str,
) -> dict[str, Any]:
    existing_scoped = (
        _filtered_storage_state_mapping(
            existing,
            url=filter_url,
            provider=provider,
        )
        if isinstance(existing, Mapping)
        else {}
    ) or {}
    merged = {**existing_scoped, **dict(staged)}
    cookies_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for payload in (existing_scoped, staged):
        for cookie in payload.get("cookies") or []:
            if isinstance(cookie, Mapping):
                cookies_by_key[_cookie_state_key(cookie)] = dict(cookie)
    origins_by_key: dict[str, dict[str, Any]] = {}
    for payload in (existing_scoped, staged):
        for origin in payload.get("origins") or []:
            if isinstance(origin, Mapping):
                origins_by_key[_origin_state_key(origin)] = dict(origin)
    merged["cookies"] = list(cookies_by_key.values())
    merged["origins"] = list(origins_by_key.values())
    return merged


def commit_staged_storage_state(
    stage: BrowserStagedStorageState | None,
    config: BrowserRuntimeConfig,
    *,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """Atomically merge an accepted stage into the provider state file."""

    expected_path = storage_state_path(config)
    result: dict[str, Any] = {
        "attempted": stage is not None,
        "staged": stage is not None,
        "saved": False,
        "path": str(expected_path) if expected_path is not None else None,
        "filtered": stage is not None,
    }
    if stage is None or expected_path is None:
        result["reason"] = "no_staged_state"
        return result
    if stage.path != expected_path or stage.provider != config.provider:
        result["reason"] = "staged_state_scope_mismatch"
        return result
    if not _storage_url_matches_provider(stage.filter_url, config.provider):
        result["reason"] = "staged_state_provider_mismatch"
        return result
    lock = FileLock(str(expected_path) + STORAGE_STATE_LOCK_SUFFIX)
    lock_timeout = max(0.001, config.timeout_ms / 1000.0)
    if runtime_context is not None:
        try:
            runtime_context.raise_if_cancelled()
            lock_timeout = max(
                0.001,
                float(runtime_context.remaining_seconds(lock_timeout)),
            )
        except AttributeError:
            pass
    try:
        with lock.acquire(timeout=lock_timeout):
            if runtime_context is not None:
                with contextlib.suppress(AttributeError):
                    runtime_context.raise_if_cancelled()
            existing: Mapping[str, Any] | None = None
            if expected_path.exists():
                decoded = json.loads(expected_path.read_text(encoding="utf-8"))
                if not isinstance(decoded, Mapping):
                    raise ValueError("existing storage state is not a JSON object")
                existing = decoded
            merged = _merge_storage_state_payloads(
                existing,
                stage.payload,
                provider=config.provider,
                filter_url=stage.filter_url,
            )
            _atomic_write_json(expected_path, merged)
        result.update(
            {
                "saved": True,
                "cookie_count": len(merged.get("cookies") or []),
                "reason": "provider_acceptance_committed",
            }
        )
        return result
    except FileLockTimeout:
        result["reason"] = "lock_timeout"
        result["lock_timeout_seconds"] = round(lock_timeout, 3)
        return result
    except Exception as exc:
        result["reason"] = "save_failed"
        result["error"] = normalize_text(str(exc)) or exc.__class__.__name__
        return result
