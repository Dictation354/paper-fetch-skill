"""Native profile paths and in-memory browser state filtering."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ...config import (
    BROWSER_PROFILE_DIR_ENV_VAR,
    BROWSER_USER_DATA_DIR_ENV_VAR,
    resolve_user_data_dir,
)
from ...provider_catalog import (
    host_matches_domain,
    provider_domain_matches,
    provider_domains,
)
from ...utils import normalize_text, sanitize_filename
from .seed import filter_browser_cookies_for_url
from .types import BrowserRuntimeConfig


def default_provider_user_data_dir(env: Mapping[str, str], *, provider: str) -> Path:
    provider_key = sanitize_filename(normalize_text(provider).lower() or "browser")
    return (
        resolve_user_data_dir(env)
        / "publisher-browser-profiles"
        / provider_key
        / "chromium"
    )


def chromium_profile_dir(root: Path) -> Path:
    return root.expanduser() / "chromium"


def configured_user_data_dir(env: Mapping[str, str]) -> Path | None:
    value = str(env.get(BROWSER_USER_DATA_DIR_ENV_VAR, "")).strip()
    return chromium_profile_dir(Path(value)) if value else None


def configured_profile_dir(
    env: Mapping[str, str], *, provider: str | None = None
) -> Path | None:
    del provider
    generic_value = str(env.get(BROWSER_PROFILE_DIR_ENV_VAR, "")).strip()
    return chromium_profile_dir(Path(generic_value)) if generic_value else None


def runtime_with_default_profile(
    runtime: BrowserRuntimeConfig,
    *,
    env: Mapping[str, str],
    provider: str,
) -> BrowserRuntimeConfig:
    if runtime.profile_dir is not None or runtime.user_data_dir is not None:
        return runtime
    return replace(
        runtime,
        user_data_dir=default_provider_user_data_dir(
            env,
            provider=provider,
        ),
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
