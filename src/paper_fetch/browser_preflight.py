"""Serial browser preflight for browser-backed providers."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, replace
from importlib import util as importlib_util
from pathlib import Path
from typing import Any
from collections.abc import Callable, Iterable, Mapping

from .auth import AUTH_TARGETS, AuthTarget
from .config import (
    BROWSER_TIMEOUT_MS_ENV_VAR,
    BROWSER_USER_AGENT_ENV_VAR,
    build_runtime_env,
    configured_browser_backend,
)
from .http import RequestCancelledError
from .publisher_identity import extract_doi, extract_doi_from_url
from .provider_catalog import browser_preflight_provider_names
from .providers.base import ProviderFailure
from .providers.browser_runtime import (
    BrowserHtmlReadiness,
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
    ensure_runtime_ready,
    fetch_html_with_browser,
    load_runtime_config,
    probe_runtime_status,
    storage_state_path as runtime_storage_state_path,
)
from .providers.browser_runtime.paths import runtime_with_default_storage_profile
from .providers.browser_runtime.paths import commit_staged_storage_state
from .providers.browser_workflow.client import BrowserWorkflowClient
from .providers.browser_workflow.shared import (
    BrowserWorkflowDeps,
    default_browser_workflow_deps,
)
from .providers.registry import build_clients
from .reason_codes import ERROR
from .runtime import RuntimeContext
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
    storage_state_path: Path | None = None,
    save_storage_state: bool = True,
) -> BrowserRuntimeConfig:
    if storage_state_path is not None:
        runtime = replace(
            runtime,
            storage_state_path=storage_state_path.expanduser(),
            profile_dir=None,
            user_data_dir=None,
        )
    else:
        runtime = runtime_with_default_storage_profile(
            runtime,
            env=env,
            provider=provider,
        )
    return replace(
        runtime,
        persist_storage_state=save_storage_state,
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
        runtime_env[BROWSER_TIMEOUT_MS_ENV_VAR] = str(timeout_ms)
    normalized_user_agent = normalize_text(browser_user_agent)
    if normalized_user_agent:
        if configured_browser_backend(runtime_env) == "camoufox":
            raise ProviderFailure(
                ERROR,
                "--browser-user-agent cannot be used with Camoufox because it would make the generated Firefox fingerprint inconsistent.",
            )
        runtime_env[BROWSER_USER_AGENT_ENV_VAR] = normalized_user_agent
    return runtime_env


def static_browser_capabilities(
    env: Mapping[str, str],
    *,
    provider: str | None = None,
) -> dict[str, object]:
    """Describe local browser dependencies/config without opening a browser."""

    browser_providers = browser_preflight_provider_names()
    provider_key = normalize_text(provider).lower()
    if provider is not None and provider_key not in browser_providers:
        return {
            "diagnostic_scope": "static_configuration_and_local_dependencies",
            "provider_context": provider_key or None,
            "status": "not_applicable",
            "available": False,
            "reason_code": "browser_route_not_applicable",
            "message": "This provider does not declare a browser-backed route.",
            "live_checked": False,
            "publisher_page_checked": False,
        }
    if provider_key not in browser_providers:
        provider_key = browser_providers[0]
    result = probe_runtime_status(env, provider=provider_key)
    checks = {check.name: check for check in result.checks}
    dependency_check = checks.get("playwright_dependency")
    dependency_details = (
        dependency_check.details
        if dependency_check is not None
        and isinstance(dependency_check.details, Mapping)
        else {}
    )
    packages = dependency_details.get("packages")
    package_states = packages if isinstance(packages, Mapping) else {}
    selected_backend = configured_browser_backend(env)

    def package_capability(package: str) -> dict[str, object]:
        available = bool(
            package_states.get(package)
            if package in package_states
            else importlib_util.find_spec(package) is not None
        )
        return {
            "status": "ready" if available else "not_configured",
            "available": available,
            "reason_code": (
                "local_dependency_ready"
                if available
                else f"{package}_dependency_missing"
            ),
            "message": (
                f"{package} Python package is importable."
                if available
                else f"{package} Python package is not importable."
            ),
        }

    runtime_check = checks.get("runtime_env")
    runtime_details = (
        runtime_check.details
        if runtime_check is not None and isinstance(runtime_check.details, Mapping)
        else {}
    )
    safe_runtime_details = {
        key: value
        for key, value in runtime_details.items()
        if key
        in {
            "headless",
            "timeout_ms",
            "binary_path_configured",
            "cdp_endpoint_configured",
            "cdp_external_new_context",
            "profile_dir_configured",
            "user_data_dir_configured",
            "storage_state_json_configured",
            "storage_state_json_exists",
            "auto_cdp_browser_enabled",
            "backend",
            "browser_user_agent_ignored",
            "storage_state_path",
        }
    }
    runtime_status = (
        runtime_check.status if runtime_check is not None else result.status
    )
    if runtime_status == ERROR:
        chrome_cdp = {
            "status": "error",
            "available": False,
            "reason_code": "browser_runtime_configuration_error",
            "message": "Local browser runtime configuration could not be validated.",
        }
    elif runtime_status == "not_configured":
        chrome_cdp = {
            "status": "not_configured",
            "available": False,
            "reason_code": "browser_runtime_not_configured",
            "message": "Local browser runtime configuration is incomplete.",
        }
    elif bool(runtime_details.get("cdp_endpoint_configured")):
        chrome_cdp = {
            "status": "configured",
            "available": True,
            "reason_code": "cdp_endpoint_configured_not_probed",
            "message": "A CDP endpoint is configured; the connection was not opened.",
        }
    elif bool(runtime_details.get("binary_path_configured")):
        chrome_cdp = {
            "status": "configured",
            "available": True,
            "reason_code": "chrome_binary_configured_not_launched",
            "message": "A local Chrome binary is configured; it was not launched.",
        }
    else:
        chrome_cdp = {
            "status": "not_checked",
            "available": False,
            "reason_code": "managed_chrome_not_probed",
            "message": "Managed Chrome may be prepared on demand; no browser was launched.",
        }
    chrome_cdp["details"] = safe_runtime_details
    chrome_cdp["connection_checked"] = False
    chrome_cdp["launch_checked"] = False

    return {
        "diagnostic_scope": "static_configuration_and_local_dependencies",
        "provider_context": provider_key,
        "selected_backend": selected_backend,
        "live_checked": False,
        "publisher_page_checked": False,
        "playwright": package_capability("playwright"),
        "camoufox": package_capability("camoufox"),
        "chrome_cdp": chrome_cdp,
        "browser_runtime": {
            "backend": selected_backend,
            "status": runtime_status,
            "available": runtime_status not in {ERROR, "not_configured"},
            "notes": list(result.notes),
            "details": safe_runtime_details,
        },
    }


def _unsupported_provider_failure(provider: str) -> ProviderFailure:
    supported = ", ".join(browser_preflight_provider_names())
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


def _preflight_generic_browser_route(
    provider_key: str,
    target: AuthTarget,
    *,
    env: Mapping[str, str],
    storage_state_path: Path | None,
    save_storage_state: bool,
    cancel_check: Callable[[], bool] | None,
) -> BrowserPreflightResult:
    """Preflight an optional browser recovery route without requiring its client
    to inherit the browser-workflow provider base class.
    """

    runtime = load_runtime_config(env, provider=provider_key, doi=target.doi)
    runtime = _runtime_with_preflight_storage(
        runtime,
        env=env,
        provider=provider_key,
        storage_state_path=storage_state_path,
        save_storage_state=save_storage_state,
    )
    ensure_runtime_ready(runtime)
    context = RuntimeContext(env=dict(env), cancel_check=cancel_check)
    try:
        html_result = fetch_html_with_browser(
            [target.url],
            publisher=provider_key,
            config=runtime,
            readiness=BrowserHtmlReadiness(
                wait_for_article_body=False,
                selector="#article" if provider_key == "ieee" else None,
            ),
            wait_seconds=2,
            runtime_context=context,
        )
        diagnostics = dict(html_result.diagnostics or {})
        if save_storage_state and html_result.staged_storage_state is not None:
            save_result = commit_staged_storage_state(
                html_result.staged_storage_state,
                runtime,
                runtime_context=context,
            )
            diagnostics["storage_state_save"] = save_result
            if not save_result.get("saved"):
                return _failure_result(
                    provider_key,
                    target_url=target.url,
                    storage_state_path=_storage_state_path(runtime),
                    reason="state_save_failed",
                    message=(
                        "Publisher page passed preflight, but the accepted browser "
                        "storage state could not be saved."
                    ),
                    diagnostics=diagnostics,
                )
        return BrowserPreflightResult(
            provider=provider_key,
            provider_label=provider_display_name(provider_key),
            ok=True,
            target_url=target.url,
            final_url=html_result.final_url,
            title=html_result.title,
            storage_state_path=_storage_state_path(runtime),
            diagnostics=diagnostics,
        )
    finally:
        context.close()


def _preflight_metadata(target: AuthTarget) -> dict[str, Any]:
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


def _preflight_storage_state_save(
    raw_payload: Any,
) -> Mapping[str, Any] | None:
    content = getattr(raw_payload, "content", None)
    diagnostics = getattr(content, "diagnostics", None)
    runtime_trace = (
        diagnostics.get("browser_runtime_trace")
        if isinstance(diagnostics, Mapping)
        else None
    )
    save_result = (
        runtime_trace.get("storage_state_save")
        if isinstance(runtime_trace, Mapping)
        else None
    )
    return save_result if isinstance(save_result, Mapping) else None


def _preflight_deps(
    env: Mapping[str, str],
    *,
    storage_path: dict[str, Path | None],
    explicit_storage_state_path: Path | None = None,
    save_storage_state: bool = True,
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
            storage_state_path=explicit_storage_state_path,
            save_storage_state=save_storage_state,
        )
        storage_path["value"] = _storage_state_path(runtime)
        return runtime

    return replace(
        base_deps,
        load_runtime_config=load_preflight_runtime_config,
        ensure_runtime_ready=ensure_runtime_ready,
        fetch_html_with_browser=fetch_html_with_browser,
    )


def _preflight_target(provider_key: str, target_url: str | None) -> AuthTarget | None:
    default_target = AUTH_TARGETS.get(provider_key)
    normalized_url = normalize_text(target_url)
    if not normalized_url:
        return default_target
    doi = (
        extract_doi_from_url(normalized_url)
        or extract_doi(normalized_url)
        or getattr(default_target, "doi", None)
    )
    if not doi:
        return None
    return AuthTarget(doi=doi, url=normalized_url)


def preflight_browser_provider(
    provider: str,
    *,
    env: Mapping[str, str],
    target_url: str | None = None,
    storage_state_path: Path | None = None,
    save_storage_state: bool = True,
    cancel_check: Callable[[], bool] | None = None,
) -> BrowserPreflightResult:
    provider_key = normalize_text(provider).lower()
    if provider_key not in browser_preflight_provider_names():
        raise _unsupported_provider_failure(provider)

    target = _preflight_target(provider_key, target_url)
    if target is None:
        return _failure_result(
            provider_key,
            reason=ERROR,
            message=(
                f"No built-in browser preflight URL or usable custom URL/DOI is "
                f"configured for {provider_display_name(provider_key)}."
            ),
        )

    storage_path: dict[str, Path | None] = {"value": None}
    context: RuntimeContext | None = None
    try:
        if provider_key == "ieee":
            return _preflight_generic_browser_route(
                provider_key,
                target,
                env=env,
                storage_state_path=storage_state_path,
                save_storage_state=save_storage_state,
                cancel_check=cancel_check,
            )
        client = _provider_client(provider_key, env=env)
        deps = _preflight_deps(
            env,
            storage_path=storage_path,
            explicit_storage_state_path=storage_state_path,
            save_storage_state=save_storage_state,
        )
        context = RuntimeContext(env=dict(env), cancel_check=cancel_check)
        bootstrap = deps.bootstrap_browser_workflow(
            client,
            target.doi,
            _preflight_metadata(target),
            context=context,
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
                diagnostics=bootstrap.html_failure_diagnostics,
            )
        save_result = _preflight_storage_state_save(raw_payload)
        if (
            save_storage_state
            and save_result is not None
            and not save_result.get("saved")
        ):
            return _failure_result(
                provider_key,
                target_url=target.url,
                storage_state_path=storage_path["value"],
                reason="state_save_failed",
                message=(
                    "Publisher page passed preflight, but the accepted browser "
                    "storage state could not be saved."
                ),
                diagnostics={"storage_state_save": dict(save_result)},
            )
    except RequestCancelledError:
        raise
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
    finally:
        if context is not None:
            with contextlib.suppress(Exception):
                context.close()

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
    target_url: str | None = None,
    storage_state_path: Path | None = None,
    save_storage_state: bool = True,
    cancel_as_result: bool = False,
    on_result: Callable[[BrowserPreflightResult, int, int], None] | None = None,
) -> list[BrowserPreflightResult]:
    runtime_env = _runtime_env(
        env,
        timeout_ms=timeout_ms,
        browser_user_agent=browser_user_agent,
    )
    selected_providers = (
        _dedupe_providers(providers)
        if providers is not None
        else browser_preflight_provider_names()
    )
    if (target_url is not None or storage_state_path is not None) and len(
        selected_providers
    ) != 1:
        raise ProviderFailure(
            ERROR,
            "target_url and storage_state_path require exactly one preflight provider.",
        )
    results: list[BrowserPreflightResult] = []
    total = len(selected_providers)
    for provider in selected_providers:
        if cancel_check is not None and cancel_check():
            if not cancel_as_result:
                raise RequestCancelledError("Request cancelled.")
            result = _failure_result(
                provider,
                target_url=target_url,
                reason="request_cancelled",
                message="Browser preflight was cancelled before this provider ran.",
            )
            results.append(result)
            if on_result is not None:
                on_result(result, len(results), total)
            break
        try:
            result = preflight_browser_provider(
                provider,
                env=runtime_env,
                target_url=target_url,
                storage_state_path=storage_state_path,
                save_storage_state=save_storage_state,
                cancel_check=cancel_check,
            )
        except RequestCancelledError:
            if not cancel_as_result:
                raise
            result = _failure_result(
                provider,
                target_url=target_url,
                storage_state_path=storage_state_path,
                reason="request_cancelled",
                message="Browser preflight was cancelled while this provider ran.",
            )
            results.append(result)
            if on_result is not None:
                on_result(result, len(results), total)
            break
        results.append(result)
        if on_result is not None:
            on_result(result, len(results), total)
    return results
