"""Serial browser preflight for browser-backed providers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from collections.abc import Callable, Iterable, Mapping

from .auth import AUTH_TARGETS, browser_auth_provider_names
from .config import (
    BROWSER_USER_AGENT_ENV_VAR,
    CLOAKBROWSER_TIMEOUT_MS_ENV_VAR,
    build_runtime_env,
)
from .http import RequestCancelledError
from .providers.base import ProviderFailure
from .providers.browser_runtime import (
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
    ensure_runtime_ready,
    fetch_html_with_browser,
    load_runtime_config,
    storage_state_path as runtime_storage_state_path,
)
from .providers.browser_runtime.paths import runtime_with_default_storage_profile
from .providers.browser_workflow.client import BrowserWorkflowClient
from .providers.browser_workflow.shared import (
    BrowserWorkflowDeps,
    default_browser_workflow_deps,
)
from .providers.registry import build_clients
from .reason_codes import ERROR
from .utils import normalize_text, provider_display_name


@dataclass(frozen=True)
class BrowserPreflightResult:
    provider: str
    provider_label: str
    ok: bool
    target_url: str | None = None
    final_url: str | None = None
    title: str | None = None
    storage_state_path: Path | None = None
    diagnostics: dict[str, Any] | None = None
    reason: str | None = None
    message: str | None = None


def _runtime_with_preflight_storage(
    runtime: BrowserRuntimeConfig,
    *,
    env: Mapping[str, str],
    provider: str,
) -> BrowserRuntimeConfig:
    return runtime_with_default_storage_profile(
        runtime,
        env=env,
        provider=provider,
    )


def _storage_state_path(runtime: BrowserRuntimeConfig) -> Path | None:
    return runtime_storage_state_path(runtime)


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
    diagnostics: Mapping[str, Any] | None = None,
) -> BrowserPreflightResult:
    return BrowserPreflightResult(
        provider=provider,
        provider_label=provider_display_name(provider),
        ok=False,
        target_url=target_url,
        storage_state_path=storage_state_path,
        diagnostics=dict(diagnostics or {}),
        reason=normalize_text(reason) or ERROR,
        message=normalize_text(message) or "Browser preflight failed.",
    )


def _provider_client(
    provider_key: str,
    *,
    env: Mapping[str, str],
) -> BrowserWorkflowClient:
    client = build_clients(env=env).get(provider_key)
    if isinstance(client, BrowserWorkflowClient):
        return client
    raise ProviderFailure(
        ERROR,
        f"{provider_display_name(provider_key)} does not expose a browser workflow client.",
    )


def _preflight_metadata(target: Any) -> dict[str, Any]:
    return {
        "doi": target.doi,
        "landing_page_url": target.url,
    }


def _preflight_title_from_payload(raw_payload: Any) -> str | None:
    content = getattr(raw_payload, "content", None)
    diagnostics = getattr(content, "diagnostics", None)
    extraction = (
        diagnostics.get("extraction") if isinstance(diagnostics, Mapping) else None
    )
    if isinstance(extraction, Mapping):
        title = normalize_text(str(extraction.get("title") or ""))
        if title:
            return title
    return None


def _preflight_deps(
    env: Mapping[str, str],
    *,
    storage_path: dict[str, Path | None],
) -> BrowserWorkflowDeps:
    base_deps = default_browser_workflow_deps()

    def load_preflight_runtime_config(
        runtime_env: Mapping[str, str], *, provider: str, doi: str
    ) -> BrowserRuntimeConfig:
        runtime = load_runtime_config(runtime_env, provider=provider, doi=doi)
        runtime = _runtime_with_preflight_storage(
            runtime,
            env=env,
            provider=provider,
        )
        storage_path["value"] = _storage_state_path(runtime)
        return runtime

    return replace(
        base_deps,
        load_runtime_config=load_preflight_runtime_config,
        ensure_runtime_ready=ensure_runtime_ready,
        fetch_html_with_browser=fetch_html_with_browser,
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

    storage_path: dict[str, Path | None] = {"value": None}
    try:
        client = _provider_client(provider_key, env=env)
        deps = _preflight_deps(env, storage_path=storage_path)
        bootstrap = deps.bootstrap_browser_workflow(
            client,
            target.doi,
            _preflight_metadata(target),
            deps=deps,
        )
        raw_payload = bootstrap.html_payload
        if raw_payload is None:
            return _failure_result(
                provider_key,
                target_url=target.url,
                storage_state_path=storage_path["value"],
                reason=bootstrap.html_failure_reason,
                message=bootstrap.html_failure_message,
            )
    except BrowserRuntimeFailure as exc:
        return _failure_result(
            provider_key,
            target_url=target.url,
            storage_state_path=storage_path["value"],
            reason=exc.kind,
            message=exc.message,
            diagnostics=getattr(exc, "details", None),
        )
    except ProviderFailure as exc:
        return _failure_result(
            provider_key,
            target_url=target.url,
            storage_state_path=storage_path["value"],
            reason=exc.code,
            message=exc.message,
        )
    except Exception as exc:  # noqa: BLE001 - preflight records per-provider failures.
        message = normalize_text(str(exc)) or exc.__class__.__name__
        return _failure_result(
            provider_key,
            target_url=target.url,
            storage_state_path=storage_path["value"],
            reason=ERROR,
            message=message,
        )

    return BrowserPreflightResult(
        provider=provider_key,
        provider_label=provider_display_name(provider_key),
        ok=True,
        target_url=target.url,
        final_url=normalize_text(raw_payload.source_url) or None,
        title=_preflight_title_from_payload(raw_payload),
        storage_state_path=storage_path["value"],
        diagnostics=dict(
            getattr(getattr(raw_payload, "content", None), "diagnostics", {}) or {}
        ),
    )


def run_browser_provider_preflight(
    *,
    providers: Iterable[str] | None = None,
    timeout_ms: int | None = None,
    browser_user_agent: str | None = None,
    env: Mapping[str, str] | None = None,
    cancel_check: Callable[[], bool] | None = None,
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
    results: list[BrowserPreflightResult] = []
    for provider in selected_providers:
        if cancel_check is not None and cancel_check():
            raise RequestCancelledError("Request cancelled.")
        results.append(preflight_browser_provider(provider, env=runtime_env))
    return results
