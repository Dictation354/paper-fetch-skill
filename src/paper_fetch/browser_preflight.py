"""Serial browser preflight for browser-backed providers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from collections.abc import Iterable, Mapping

from .auth import AUTH_TARGETS, browser_auth_provider_names
from .config import (
    BROWSER_USER_AGENT_ENV_VAR,
    CLOAKBROWSER_TIMEOUT_MS_ENV_VAR,
    build_runtime_env,
    resolve_user_data_dir,
)
from .providers.base import ProviderFailure
from .providers.browser_runtime import (
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
    ensure_runtime_ready,
    fetch_html_with_browser,
    load_runtime_config,
)
from .reason_codes import ERROR
from .utils import normalize_text, provider_display_name, sanitize_filename


@dataclass(frozen=True)
class BrowserPreflightResult:
    provider: str
    provider_label: str
    ok: bool
    target_url: str | None = None
    final_url: str | None = None
    title: str | None = None
    storage_state_path: Path | None = None
    reason: str | None = None
    message: str | None = None


def _default_provider_user_data_dir(env: Mapping[str, str], *, provider: str) -> Path:
    provider_key = sanitize_filename(normalize_text(provider).lower() or "browser")
    return resolve_user_data_dir(env) / "publisher-browser-profiles" / provider_key


def _runtime_with_preflight_storage(
    runtime: BrowserRuntimeConfig,
    *,
    env: Mapping[str, str],
    provider: str,
) -> BrowserRuntimeConfig:
    if runtime.storage_state_path is not None:
        return runtime
    if runtime.profile_dir is not None or runtime.user_data_dir is not None:
        return runtime
    return replace(
        runtime,
        user_data_dir=_default_provider_user_data_dir(env, provider=provider),
    )


def _storage_state_path(runtime: BrowserRuntimeConfig) -> Path | None:
    if runtime.storage_state_path is not None:
        return Path(runtime.storage_state_path).expanduser()
    profile_dir = runtime.profile_dir or runtime.user_data_dir
    if profile_dir is None:
        return None
    return Path(profile_dir).expanduser() / "storage-state.json"


def _dedupe_providers(providers: Iterable[str]) -> tuple[str, ...]:
    deduped: list[str] = []
    for provider in providers:
        normalized = normalize_text(provider).lower()
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return tuple(deduped)


def _runtime_env(
    env: Mapping[str, str] | None,
    *,
    timeout_ms: int | None,
    browser_user_agent: str | None,
) -> dict[str, str]:
    runtime_env = build_runtime_env(env)
    if timeout_ms is not None:
        runtime_env[CLOAKBROWSER_TIMEOUT_MS_ENV_VAR] = str(timeout_ms)
    normalized_user_agent = normalize_text(browser_user_agent)
    if normalized_user_agent:
        runtime_env[BROWSER_USER_AGENT_ENV_VAR] = normalized_user_agent
    return runtime_env


def _unsupported_provider_failure(provider: str) -> ProviderFailure:
    supported = ", ".join(browser_auth_provider_names())
    return ProviderFailure(
        ERROR,
        f"Unsupported browser preflight provider {provider!r}; supported providers: {supported}.",
    )


def _failure_result(
    provider: str,
    *,
    target_url: str | None = None,
    storage_state_path: Path | None = None,
    reason: str | None = None,
    message: str | None = None,
) -> BrowserPreflightResult:
    return BrowserPreflightResult(
        provider=provider,
        provider_label=provider_display_name(provider),
        ok=False,
        target_url=target_url,
        storage_state_path=storage_state_path,
        reason=normalize_text(reason) or ERROR,
        message=normalize_text(message) or "Browser preflight failed.",
    )


def preflight_browser_provider(
    provider: str,
    *,
    env: Mapping[str, str],
) -> BrowserPreflightResult:
    provider_key = normalize_text(provider).lower()
    if provider_key not in browser_auth_provider_names():
        raise _unsupported_provider_failure(provider)

    target = AUTH_TARGETS.get(provider_key)
    if target is None:
        return _failure_result(
            provider_key,
            reason=ERROR,
            message=(
                f"No built-in browser preflight URL is configured for "
                f"{provider_display_name(provider_key)}."
            ),
        )

    runtime: BrowserRuntimeConfig | None = None
    storage_path: Path | None = None
    try:
        runtime = load_runtime_config(env, provider=provider_key, doi=target.doi)
        runtime = _runtime_with_preflight_storage(
            runtime,
            env=env,
            provider=provider_key,
        )
        storage_path = _storage_state_path(runtime)
        ensure_runtime_ready(runtime)
        fetched = fetch_html_with_browser(
            [target.url],
            publisher=provider_key,
            config=runtime,
        )
    except BrowserRuntimeFailure as exc:
        return _failure_result(
            provider_key,
            target_url=target.url,
            storage_state_path=storage_path,
            reason=exc.kind,
            message=exc.message,
        )
    except ProviderFailure as exc:
        return _failure_result(
            provider_key,
            target_url=target.url,
            storage_state_path=storage_path,
            reason=exc.code,
            message=exc.message,
        )
    except Exception as exc:  # noqa: BLE001 - preflight records per-provider failures.
        message = normalize_text(str(exc)) or exc.__class__.__name__
        return _failure_result(
            provider_key,
            target_url=target.url,
            storage_state_path=storage_path,
            reason=ERROR,
            message=message,
        )

    return BrowserPreflightResult(
        provider=provider_key,
        provider_label=provider_display_name(provider_key),
        ok=True,
        target_url=target.url,
        final_url=normalize_text(fetched.final_url) or None,
        title=normalize_text(fetched.title) or None,
        storage_state_path=storage_path,
    )


def run_browser_provider_preflight(
    *,
    providers: Iterable[str] | None = None,
    timeout_ms: int | None = None,
    browser_user_agent: str | None = None,
    env: Mapping[str, str] | None = None,
) -> list[BrowserPreflightResult]:
    runtime_env = _runtime_env(
        env,
        timeout_ms=timeout_ms,
        browser_user_agent=browser_user_agent,
    )
    selected_providers = (
        _dedupe_providers(providers)
        if providers is not None
        else browser_auth_provider_names()
    )
    return [
        preflight_browser_provider(provider, env=runtime_env)
        for provider in selected_providers
    ]
