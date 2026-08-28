"""Serial browser preflight for browser-backed providers."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, replace
from importlib import util as importlib_util
from pathlib import Path
import re
from typing import Any, Literal
from collections.abc import Callable, Iterable, Mapping

from .auth import AUTH_TARGETS, AuthTarget
from .artifacts import ArtifactMode
from .config import (
    BROWSER_TIMEOUT_MS_ENV_VAR,
    BROWSER_USER_AGENT_ENV_VAR,
    build_runtime_env,
    configured_browser_backend,
)
from .http import RequestCancelledError, diagnostic_url_payload
from .page_diagnostics import PageDiagnosticRequest, capture_page_diagnostic
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
from .providers.browser_runtime.preparation import (
    browser_runtime_preparation_scope,
)
from .providers.browser_workflow.client import BrowserWorkflowClient
from .providers.browser_workflow.shared import (
    BrowserWorkflowDeps,
    default_browser_workflow_deps,
)
from .providers.browser_workflow.reuse_cache import (
    mark_browser_preflight_producer,
)
from .providers.registry import build_clients
from .reason_codes import (
    BROWSER_CONTEXT_CREATE_FAILED,
    BROWSER_PAGE_CREATE_FAILED,
    BROWSER_RUNTIME_PREPARE_CANCELLED,
    BROWSER_RUNTIME_PREPARE_FAILED,
    BROWSER_RUNTIME_PREPARE_TIMEOUT,
    BROWSER_RUNTIME_REPAIR_FAILED,
    CDP_CONNECT_FAILED,
    ERROR,
    MANAGED_CHROME_CDP_TIMEOUT,
    MANAGED_CHROME_EXITED_BEFORE_CDP,
    MANAGED_CHROME_PROFILE_IN_USE,
)
from .runtime import RuntimeContext
from .utils import normalize_text, provider_display_name


BrowserPreflightStatus = Literal[
    "ready",
    "challenge",
    "auth_required",
    "network_timeout",
    "extraction_error",
    "runtime_error",
    "cancelled",
]
BROWSER_PREFLIGHT_STATUSES: tuple[BrowserPreflightStatus, ...] = (
    "ready",
    "challenge",
    "auth_required",
    "network_timeout",
    "extraction_error",
    "runtime_error",
    "cancelled",
)

_CHALLENGE_REASON_CODES = frozenset(
    {
        "aws_waf_challenge",
        "cloudflare_challenge",
        "iop_captcha_challenge",
        "iop_radware_challenge",
    }
)
_AUTH_REQUIRED_REASON_CODES = frozenset(
    {
        "abstract_only",
        "no_access",
        "publisher_access_denied",
        "publisher_paywall",
        "redirected_to_abstract",
    }
)
_NETWORK_TIMEOUT_REASON_CODES = frozenset(
    {
        "timeout",
        "pool_timeout",
        "browser_connect_timeout",
        "browser_navigation_timeout",
        "browser_rest_wait_timeout",
    }
)
_EXTRACTION_REASON_CODES = frozenset(
    {
        "article_container_not_found",
        "browser_article_not_ready",
        "empty_article_shell",
        "insufficient_body",
        "structured_article_not_fulltext",
        "structured_missing_body_sections",
        "publisher_not_found",
    }
)
IEEE_PREFLIGHT_READINESS_WAIT_SECONDS = 15
_CANCELLED_REASON_CODES = frozenset(
    {
        BROWSER_RUNTIME_PREPARE_CANCELLED,
        "cancelled",
        "request_cancelled",
    }
)
_RUNTIME_REASON_CODES = frozenset(
    {
        BROWSER_CONTEXT_CREATE_FAILED,
        BROWSER_PAGE_CREATE_FAILED,
        BROWSER_RUNTIME_PREPARE_FAILED,
        BROWSER_RUNTIME_PREPARE_TIMEOUT,
        BROWSER_RUNTIME_REPAIR_FAILED,
        CDP_CONNECT_FAILED,
        MANAGED_CHROME_CDP_TIMEOUT,
        MANAGED_CHROME_EXITED_BEFORE_CDP,
        MANAGED_CHROME_PROFILE_IN_USE,
        "browser_backend_invalid",
        "browser_dependency_missing",
        "browser_runtime_configuration_error",
        "state_save_failed",
    }
)


@dataclass(frozen=True)
class BrowserPreflightResult:
    provider: str
    provider_label: str
    status: BrowserPreflightStatus
    reason_code: str
    stage: str | None = None
    message: str | None = None
    target_url: str | None = None
    final_url: str | None = None
    title: str | None = None
    storage_state_path: Path | None = None
    diagnostics: dict[str, Any] | None = None

    @property
    def ready(self) -> bool:
        return self.status == "ready"


@dataclass(frozen=True)
class BrowserPreflightRuntimeOptions:
    env: Mapping[str, str] | None = None
    download_dir: Path | None = None
    artifact_mode: ArtifactMode = "none"


def classify_browser_preflight_failure(
    reason_code: str | None,
    *,
    stage: str | None = None,
    diagnostics: Mapping[str, Any] | None = None,
) -> BrowserPreflightStatus:
    """Classify one stable failure code without inspecting message text."""

    code = normalize_text(reason_code).lower() or ERROR
    if code in _CANCELLED_REASON_CODES:
        return "cancelled"
    if code in _CHALLENGE_REASON_CODES:
        return "challenge"
    if code in _AUTH_REQUIRED_REASON_CODES:
        return "auth_required"
    if code in _NETWORK_TIMEOUT_REASON_CODES:
        return "network_timeout"
    if code in _EXTRACTION_REASON_CODES:
        return "extraction_error"
    if code in _RUNTIME_REASON_CODES:
        return "runtime_error"

    details = diagnostics if isinstance(diagnostics, Mapping) else {}
    normalized_stage = normalize_text(stage).lower()
    page_reached = bool(
        details.get("final_url")
        or details.get("response_status")
        or details.get("readiness")
        or details.get("extraction")
        or normalized_stage
        in {
            "availability",
            "dom_readiness",
            "extraction",
            "html_extraction",
            "page",
        }
    )
    return "extraction_error" if page_reached else "runtime_error"


def browser_preflight_next_action(provider: str, status: BrowserPreflightStatus) -> str:
    if status == "ready":
        return "run the requested fetch"
    if status in {"challenge", "auth_required"}:
        return f"paper-fetch auth {provider}"
    if status == "network_timeout":
        return f"retry browser-preflight or fetch for {provider}"
    if status == "extraction_error":
        return f"inspect page diagnostics and selectors for {provider}"
    if status == "cancelled":
        return f"rerun browser-preflight for {provider}"
    return f"inspect provider_status for {provider} and fix the local runtime"


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
            "auto_prepare",
            "download_required",
            "runtime_state",
            "runtime_version",
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
    final_url: str | None = None,
    title: str | None = None,
    storage_state_path: Path | None = None,
    reason_code: str | None = None,
    stage: str | None = None,
    message: str | None = None,
    diagnostics: Mapping[str, Any] | None = None,
    diagnostic_context: RuntimeContext | None = None,
) -> BrowserPreflightResult:
    normalized_reason = normalize_text(reason_code).lower() or ERROR
    normalized_stage = normalize_text(stage) or None
    diagnostic_payload = dict(diagnostics or {})
    existing_page_diagnostic = diagnostic_payload.get("failure_diagnostic")
    has_captured_page_diagnostic = bool(
        isinstance(existing_page_diagnostic, Mapping)
        and (
            existing_page_diagnostic.get("raw_html") is not None
            or existing_page_diagnostic.get("html_shape") is not None
            or normalize_text(
                str(existing_page_diagnostic.get("diagnostic_path") or "")
            )
        )
    )
    if (
        diagnostic_context is not None
        and not normalize_text(str(diagnostic_payload.get("diagnostic_path") or ""))
        and not has_captured_page_diagnostic
    ):
        diagnostic_backend = None
        with contextlib.suppress(Exception):
            diagnostic_backend = configured_browser_backend(
                diagnostic_context.env or {}
            )
        failure_diagnostic = capture_page_diagnostic(
            diagnostic_context,
            PageDiagnosticRequest(
                provider=provider,
                route="preflight",
                attempt=1,
                failure_code=normalized_reason,
                stage=normalized_stage or "preflight",
                html_text=None,
                doi=extract_doi(target_url or "") or None,
                target_url=target_url,
                final_url=final_url,
                backend=diagnostic_backend,
                details=diagnostic_payload,
            ),
        )
        diagnostic_payload["failure_diagnostic"] = failure_diagnostic
        if diagnostic_path := normalize_text(
            str(failure_diagnostic.get("diagnostic_path") or "")
        ):
            diagnostic_payload["diagnostic_path"] = diagnostic_path
    if target_url:
        diagnostic_payload.setdefault(
            "target_url",
            diagnostic_url_payload(target_url),
        )
    if final_url:
        diagnostic_payload.setdefault(
            "final_url",
            diagnostic_url_payload(final_url),
        )
    return BrowserPreflightResult(
        provider=provider,
        provider_label=provider_display_name(provider),
        status=classify_browser_preflight_failure(
            normalized_reason,
            stage=normalized_stage,
            diagnostics=diagnostic_payload,
        ),
        reason_code=normalized_reason,
        stage=normalized_stage,
        message=normalize_text(message) or "Browser preflight failed.",
        target_url=diagnostic_url_payload(target_url).get("url")
        if target_url
        else None,
        final_url=diagnostic_url_payload(final_url).get("url") if final_url else None,
        title=normalize_text(title) or None,
        storage_state_path=storage_state_path,
        diagnostics=diagnostic_payload,
    )


def _ready_result(
    provider: str,
    *,
    target_url: str | None,
    final_url: str | None,
    title: str | None,
    storage_state_path: Path | None,
    diagnostics: Mapping[str, Any] | None,
) -> BrowserPreflightResult:
    diagnostic_payload = dict(diagnostics or {})
    if target_url:
        diagnostic_payload.setdefault(
            "target_url",
            diagnostic_url_payload(target_url),
        )
    if final_url:
        diagnostic_payload.setdefault(
            "final_url",
            diagnostic_url_payload(final_url),
        )
    return BrowserPreflightResult(
        provider=provider,
        provider_label=provider_display_name(provider),
        status="ready",
        reason_code="browser_preflight_ready",
        stage="complete",
        message="Publisher browser HTML preflight completed successfully.",
        target_url=diagnostic_url_payload(target_url).get("url")
        if target_url
        else None,
        final_url=diagnostic_url_payload(final_url).get("url") if final_url else None,
        title=title,
        storage_state_path=storage_state_path,
        diagnostics=diagnostic_payload,
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
    download_dir: Path | None,
    artifact_mode: ArtifactMode,
) -> BrowserPreflightResult:
    """Preflight an optional browser recovery route without requiring its client
    to inherit the browser-workflow provider base class.
    """

    context = RuntimeContext(
        env=dict(env),
        cancel_check=cancel_check,
        download_dir=download_dir,
        artifact_mode=artifact_mode,
    )
    runtime: BrowserRuntimeConfig | None = None
    try:
        runtime = load_runtime_config(env, provider=provider_key, doi=target.doi)
        runtime = _runtime_with_preflight_storage(
            runtime,
            env=env,
            provider=provider_key,
            storage_state_path=storage_state_path,
            save_storage_state=save_storage_state,
        )
        ensure_runtime_ready(runtime)
        ieee_article_match = (
            re.search(r"/document/([^/?#]+)", target.url)
            if provider_key == "ieee"
            else None
        )
        ieee_article_number = normalize_text(
            ieee_article_match.group(1) if ieee_article_match else ""
        )
        html_result = fetch_html_with_browser(
            [target.url],
            publisher=provider_key,
            config=runtime,
            readiness=BrowserHtmlReadiness(
                wait_for_article_body=False,
                selector="#article" if provider_key == "ieee" else None,
                selector_text=ieee_article_number or None,
                require_selector=provider_key == "ieee",
            ),
            wait_seconds=(
                IEEE_PREFLIGHT_READINESS_WAIT_SECONDS if provider_key == "ieee" else 2
            ),
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
            runtime_trace = diagnostics.get("browser_runtime_trace")
            runtime_trace = (
                dict(runtime_trace) if isinstance(runtime_trace, Mapping) else {}
            )
            runtime_trace["storage_state_save"] = dict(save_result)
            diagnostics["browser_runtime_trace"] = runtime_trace
            if not save_result.get("saved"):
                return _failure_result(
                    provider_key,
                    target_url=target.url,
                    final_url=html_result.final_url,
                    storage_state_path=_storage_state_path(runtime),
                    reason_code="state_save_failed",
                    stage="storage_state_save",
                    message=(
                        "Publisher page passed preflight, but the accepted browser "
                        "storage state could not be saved."
                    ),
                    diagnostics=diagnostics,
                    diagnostic_context=context,
                )
            html_result = replace(
                html_result,
                diagnostics=diagnostics,
                staged_storage_state=None,
            )
        return _ready_result(
            provider_key,
            target_url=target.url,
            final_url=html_result.final_url,
            title=html_result.title,
            storage_state_path=_storage_state_path(runtime),
            diagnostics=diagnostics,
        )
    except RequestCancelledError:
        raise
    except BrowserRuntimeFailure as exc:
        final_url_value = exc.details.get("final_url")
        final_url = (
            normalize_text(str(final_url_value.get("url") or ""))
            if isinstance(final_url_value, Mapping)
            else normalize_text(str(final_url_value or ""))
        )
        return _failure_result(
            provider_key,
            target_url=target.url,
            final_url=final_url or None,
            title=normalize_text(str(exc.details.get("title_summary") or "")) or None,
            storage_state_path=(
                _storage_state_path(runtime)
                if runtime is not None
                else storage_state_path
            ),
            reason_code=exc.kind,
            stage=normalize_text(str(exc.details.get("stage") or "")) or None,
            message=exc.message,
            diagnostics=exc.details,
            diagnostic_context=context,
        )
    except ProviderFailure as exc:
        return _failure_result(
            provider_key,
            target_url=target.url,
            storage_state_path=(
                _storage_state_path(runtime)
                if runtime is not None
                else storage_state_path
            ),
            reason_code=exc.code,
            stage=exc.stage,
            message=exc.message,
            diagnostics=exc.details,
            diagnostic_context=context,
        )
    except Exception as exc:  # noqa: BLE001 - preserve one provider result.
        return _failure_result(
            provider_key,
            target_url=target.url,
            storage_state_path=(
                _storage_state_path(runtime)
                if runtime is not None
                else storage_state_path
            ),
            reason_code=ERROR,
            stage="preflight",
            message=normalize_text(str(exc)) or exc.__class__.__name__,
            diagnostic_context=context,
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
    download_dir: Path | None = None,
    artifact_mode: ArtifactMode = "none",
) -> BrowserPreflightResult:
    provider_key = normalize_text(provider).lower()
    if provider_key not in browser_preflight_provider_names():
        raise _unsupported_provider_failure(provider)

    target = _preflight_target(provider_key, target_url)
    if target is None:
        return _failure_result(
            provider_key,
            reason_code=ERROR,
            stage="target_resolution",
            message=(
                f"No built-in browser preflight URL or usable custom URL/DOI is "
                f"configured for {provider_display_name(provider_key)}."
            ),
        )

    # AIP's Camoufox cookies are bound to the generated runtime fingerprint.
    # A distinct preflight RuntimeContext must not publish those cookies for a
    # later context to consume.
    effective_save_storage_state = bool(save_storage_state and provider_key != "aip")

    storage_path: dict[str, Path | None] = {"value": None}
    context: RuntimeContext | None = None
    try:
        if provider_key == "ieee":
            return _preflight_generic_browser_route(
                provider_key,
                target,
                env=env,
                storage_state_path=storage_state_path,
                save_storage_state=effective_save_storage_state,
                cancel_check=cancel_check,
                download_dir=download_dir,
                artifact_mode=artifact_mode,
            )
        client = _provider_client(provider_key, env=env)
        deps = _preflight_deps(
            env,
            storage_path=storage_path,
            explicit_storage_state_path=storage_state_path,
            save_storage_state=effective_save_storage_state,
        )
        context = RuntimeContext(
            env=dict(env),
            cancel_check=cancel_check,
            download_dir=download_dir,
            artifact_mode=artifact_mode,
        )
        mark_browser_preflight_producer(
            context,
            target_url=target.url,
            save_storage_state=effective_save_storage_state,
        )
        bootstrap = deps.bootstrap_browser_workflow(
            client,
            target.doi,
            _preflight_metadata(target),
            context=context,
            deps=deps,
        )
        if bootstrap.runtime is not None:
            storage_path["value"] = _storage_state_path(bootstrap.runtime)
        raw_payload = bootstrap.html_payload
        if raw_payload is None:
            failure_diagnostics = dict(bootstrap.html_failure_diagnostics or {})
            page_diagnostic = failure_diagnostics.get("page_diagnostic")
            if not isinstance(page_diagnostic, Mapping):
                page_diagnostic = {}
            final_diagnostic = page_diagnostic.get("final")
            if not isinstance(final_diagnostic, Mapping):
                final_diagnostic = {}
            browser_failure = failure_diagnostics.get("browser_failure")
            if not isinstance(browser_failure, Mapping):
                browser_failure = {}
            failure_stage = (
                normalize_text(str(failure_diagnostics.get("stage") or ""))
                or normalize_text(str(browser_failure.get("stage") or ""))
                or "html_extraction"
            )
            return _failure_result(
                provider_key,
                target_url=target.url,
                final_url=normalize_text(str(final_diagnostic.get("url") or ""))
                or None,
                title=normalize_text(str(page_diagnostic.get("title_summary") or ""))
                or None,
                storage_state_path=storage_path["value"],
                reason_code=bootstrap.html_failure_reason,
                stage=failure_stage,
                message=bootstrap.html_failure_message,
                diagnostics=failure_diagnostics,
                diagnostic_context=context,
            )
        save_result = _preflight_storage_state_save(raw_payload)
        if (
            effective_save_storage_state
            and save_result is not None
            and not save_result.get("saved")
        ):
            return _failure_result(
                provider_key,
                target_url=target.url,
                storage_state_path=storage_path["value"],
                reason_code="state_save_failed",
                stage="storage_state_save",
                message=(
                    "Publisher page passed preflight, but the accepted browser "
                    "storage state could not be saved."
                ),
                diagnostics={"storage_state_save": dict(save_result)},
                diagnostic_context=context,
            )
    except RequestCancelledError:
        raise
    except BrowserRuntimeFailure as exc:
        return _failure_result(
            provider_key,
            target_url=target.url,
            storage_state_path=storage_path["value"],
            reason_code=exc.kind,
            stage=normalize_text(str(exc.details.get("stage") or "")) or None,
            message=exc.message,
            diagnostics=getattr(exc, "details", None),
            diagnostic_context=context,
        )
    except ProviderFailure as exc:
        return _failure_result(
            provider_key,
            target_url=target.url,
            storage_state_path=storage_path["value"],
            reason_code=exc.code,
            stage=exc.stage,
            message=exc.message,
            diagnostics=exc.details,
            diagnostic_context=context,
        )
    except Exception as exc:  # noqa: BLE001 - preflight records per-provider failures.
        message = normalize_text(str(exc)) or exc.__class__.__name__
        return _failure_result(
            provider_key,
            target_url=target.url,
            storage_state_path=storage_path["value"],
            reason_code=ERROR,
            stage="preflight",
            message=message,
            diagnostic_context=context,
        )
    finally:
        if context is not None:
            with contextlib.suppress(Exception):
                context.close()

    return _ready_result(
        provider_key,
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
    cancel_check: Callable[[], bool] | None = None,
    target_url: str | None = None,
    storage_state_path: Path | None = None,
    save_storage_state: bool = True,
    cancel_as_result: bool = False,
    on_result: Callable[[BrowserPreflightResult, int, int], None] | None = None,
    runtime_options: BrowserPreflightRuntimeOptions | None = None,
) -> list[BrowserPreflightResult]:
    active_runtime_options = runtime_options or BrowserPreflightRuntimeOptions()
    runtime_env = _runtime_env(
        active_runtime_options.env,
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
                reason_code="request_cancelled",
                stage="not_started",
                message="Browser preflight was cancelled before this provider ran.",
            )
            results.append(result)
            if on_result is not None:
                on_result(result, len(results), total)
            break
        try:
            with browser_runtime_preparation_scope(cancel_check=cancel_check):
                result = preflight_browser_provider(
                    provider,
                    env=runtime_env,
                    target_url=target_url,
                    storage_state_path=storage_state_path,
                    save_storage_state=save_storage_state,
                    cancel_check=cancel_check,
                    download_dir=active_runtime_options.download_dir,
                    artifact_mode=active_runtime_options.artifact_mode,
                )
        except RequestCancelledError:
            if not cancel_as_result:
                raise
            result = _failure_result(
                provider,
                target_url=target_url,
                storage_state_path=storage_state_path,
                reason_code="request_cancelled",
                stage="preflight",
                message="Browser preflight was cancelled while this provider ran.",
            )
            results.append(result)
            if on_result is not None:
                on_result(result, len(results), total)
            break
        results.append(result)
        if on_result is not None:
            on_result(result, len(results), total)
        if result.status == "cancelled":
            break
    return results
