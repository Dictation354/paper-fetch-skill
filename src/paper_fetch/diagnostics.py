"""Shared static provider, configuration, and local capability diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from collections.abc import Callable, Mapping

from .browser_preflight import static_browser_capabilities
from .config import (
    AMS_STORAGE_STATE_JSON_ENV_VAR,
    BROWSER_BINARY_PATH_ENV_VAR,
    BROWSER_HEADLESS_ENV_VAR,
    BROWSER_PROFILE_DIR_ENV_VAR,
    BROWSER_TIMEOUT_MS_ENV_VAR,
    BROWSER_USER_DATA_DIR_ENV_VAR,
    BROWSER_USER_AGENT_ENV_VAR,
    DOWNLOAD_DIR_ENV_VAR,
    ENV_FILE_ENV_VAR,
    USER_AGENT_ENV_VAR,
    WILEY_PROFILE_DIR_ENV_VAR,
    WILEY_STORAGE_STATE_JSON_ENV_VAR,
    XDG_DATA_HOME_ENV_VAR,
    build_runtime_env,
    runtime_configuration_report,
)
from .http import HttpTransport
from .image_tools import probe_image_conversion_backends
from .image_tools.paths import (
    GHOSTSCRIPT_BIN_ENV_VAR,
    IMAGE_TOOLS_DIR_ENV_VAR,
    IMAGE_TOOL_TIMEOUT_SECONDS_ENV_VAR,
    VIPS_BIN_ENV_VAR,
)
from .provider_catalog import (
    PROVIDER_CATALOG,
    ProviderSpec,
    is_official_provider,
    provider_has_browser_route,
    provider_supports_browser_preflight,
    provider_status_order,
)
from .providers.base import (
    ProviderStatusResult,
    build_provider_status_check,
)
from .providers.registry import build_clients
from .redaction import is_sensitive_configuration_name
from .reason_codes import ERROR, NOT_CONFIGURED, PARTIAL, READY
from .utils import normalize_text

ProviderStatusDetail = Literal["full", "compact"]
ProviderStatusGroup = Literal["all", "official", "browser", "direct", "metadata"]

PROVIDER_STATUS_DETAILS: tuple[ProviderStatusDetail, ...] = ("full", "compact")
PROVIDER_STATUS_GROUPS: tuple[ProviderStatusGroup, ...] = (
    "all",
    "official",
    "browser",
    "direct",
    "metadata",
)

_STATIC_SCOPE = "static_configuration_and_local_dependencies"
_GLOBAL_CONFIGURATION_NAMES = {
    "CROSSREF_MAILTO",
    AMS_STORAGE_STATE_JSON_ENV_VAR,
    BROWSER_BINARY_PATH_ENV_VAR,
    BROWSER_HEADLESS_ENV_VAR,
    BROWSER_PROFILE_DIR_ENV_VAR,
    BROWSER_TIMEOUT_MS_ENV_VAR,
    BROWSER_USER_DATA_DIR_ENV_VAR,
    BROWSER_USER_AGENT_ENV_VAR,
    DOWNLOAD_DIR_ENV_VAR,
    ENV_FILE_ENV_VAR,
    GHOSTSCRIPT_BIN_ENV_VAR,
    IMAGE_TOOLS_DIR_ENV_VAR,
    IMAGE_TOOL_TIMEOUT_SECONDS_ENV_VAR,
    USER_AGENT_ENV_VAR,
    VIPS_BIN_ENV_VAR,
    "WILEY_TDM_CLIENT_TOKEN",
    WILEY_PROFILE_DIR_ENV_VAR,
    WILEY_STORAGE_STATE_JSON_ENV_VAR,
    XDG_DATA_HOME_ENV_VAR,
}
_DEFAULT_CONFIGURATION_NAMES = {
    BROWSER_BINARY_PATH_ENV_VAR,
    BROWSER_HEADLESS_ENV_VAR,
    BROWSER_PROFILE_DIR_ENV_VAR,
    BROWSER_TIMEOUT_MS_ENV_VAR,
    BROWSER_USER_DATA_DIR_ENV_VAR,
    BROWSER_USER_AGENT_ENV_VAR,
    DOWNLOAD_DIR_ENV_VAR,
    GHOSTSCRIPT_BIN_ENV_VAR,
    IMAGE_TOOLS_DIR_ENV_VAR,
    IMAGE_TOOL_TIMEOUT_SECONDS_ENV_VAR,
    USER_AGENT_ENV_VAR,
    VIPS_BIN_ENV_VAR,
    XDG_DATA_HOME_ENV_VAR,
}


def provider_status_provider_names() -> tuple[str, ...]:
    return provider_status_order()


def provider_status_group_names() -> tuple[str, ...]:
    return PROVIDER_STATUS_GROUPS


def normalize_provider_status_provider(value: object) -> str:
    provider = normalize_text(str(value or "")).lower()
    if provider not in PROVIDER_CATALOG:
        raise ValueError(
            f"unsupported provider {value!r}. Expected one of: "
            + ", ".join(provider_status_provider_names())
            + "."
        )
    return provider


def normalize_provider_status_group(value: object) -> str:
    group = normalize_text(str(value or "")).lower()
    if group not in PROVIDER_STATUS_GROUPS:
        raise ValueError(
            f"unsupported provider group {value!r}. Expected one of: "
            + ", ".join(PROVIDER_STATUS_GROUPS)
            + "."
        )
    return group


def normalize_provider_status_detail(value: object) -> str:
    detail = normalize_text(str(value or "")).lower()
    if detail not in PROVIDER_STATUS_DETAILS:
        raise ValueError(
            f"unsupported provider status detail {value!r}. Expected one of: "
            + ", ".join(PROVIDER_STATUS_DETAILS)
            + "."
        )
    return detail


def _provider_in_group(spec: ProviderSpec, group: str) -> bool:
    if group == "all":
        return True
    if group == "official":
        return spec.official
    if group == "browser":
        return provider_has_browser_route(spec.name)
    if group == "direct":
        return any(
            not route.browser_required and not route.browser_optional
            for route in spec.routes
        )
    return not spec.official


def selected_provider_status_names(
    *,
    provider: str | None = None,
    group: str | None = None,
) -> tuple[str, ...]:
    provider_key = (
        normalize_provider_status_provider(provider) if provider is not None else None
    )
    group_key = normalize_provider_status_group(group) if group is not None else "all"
    selected = tuple(
        name
        for name in provider_status_provider_names()
        if _provider_in_group(PROVIDER_CATALOG[name], group_key)
        and (provider_key is None or name == provider_key)
    )
    if provider_key is not None and not selected:
        raise ValueError(
            f"provider {provider_key!r} does not belong to group {group_key!r}."
        )
    return selected


def _provider_status_error_payload(
    provider: str,
    *,
    official_provider: bool,
    message: str,
) -> dict[str, Any]:
    return ProviderStatusResult(
        provider=provider,
        status=ERROR,
        available=False,
        official_provider=official_provider,
        notes=[],
        checks=[build_provider_status_check("diagnostics", ERROR, message)],
    ).to_dict()


def _provider_summary(
    payload: Mapping[str, Any],
    *,
    spec: ProviderSpec,
) -> dict[str, str]:
    status = normalize_text(str(payload.get("status") or ERROR)).lower()
    missing_env = [str(item) for item in payload.get("missing_env") or []]
    checks = payload.get("checks")
    check_items = checks if isinstance(checks, list) else []
    check_statuses = {
        normalize_text(str(item.get("name") or "")): normalize_text(
            str(item.get("status") or "")
        ).lower()
        for item in check_items
        if isinstance(item, Mapping)
    }
    if status == READY:
        reason_code = "static_requirements_ready"
        reason = "Static configuration and local dependencies are ready; remote access was not checked."
        suggested_action = (
            f"paper-fetch browser-preflight --provider {spec.name}"
            if provider_supports_browser_preflight(spec.name)
            else "run the requested fetch"
        )
    elif missing_env:
        reason_code = "provider_configuration_missing"
        reason = "Required provider configuration is missing."
        suggested_action = (
            "configure the reported environment keys and rerun provider_status"
        )
    elif status == PARTIAL:
        reason_code = "static_requirements_partial"
        reason = "Only part of the provider's local routes are ready."
        suggested_action = "inspect full checks before fetching"
    elif status == NOT_CONFIGURED and any(
        name in check_statuses
        for name in ("playwright", "browser_runtime", "playwright_dependency")
    ):
        reason_code = "browser_local_dependency_missing"
        reason = (
            "A browser runtime dependency or local browser configuration is missing."
        )
        suggested_action = (
            "prepare the local browser runtime, then run browser-preflight"
        )
    elif status == NOT_CONFIGURED:
        reason_code = "static_requirements_not_configured"
        reason = "Static provider requirements are not configured."
        suggested_action = "inspect full checks and configure local requirements"
    else:
        reason_code = "static_diagnostic_error"
        reason = "Static provider diagnostics could not be completed."
        suggested_action = "inspect full checks before retrying"
    return {
        "reason_code": reason_code,
        "reason": reason,
        "suggested_action": suggested_action,
    }


def _configuration_names(selected_names: tuple[str, ...]) -> set[str]:
    return {
        *_GLOBAL_CONFIGURATION_NAMES,
        *(
            name
            for provider in selected_names
            for name in PROVIDER_CATALOG[provider].env_requirements
        ),
    }


def _sensitive_configuration_names(names: set[str]) -> set[str]:
    return {name for name in names if is_sensitive_configuration_name(name)}


def _local_capability_error(component: str) -> dict[str, object]:
    return {
        "status": "error",
        "available": False,
        "reason_code": f"{component}_diagnostic_error",
        "message": f"{component} local diagnostics failed.",
    }


def provider_status_payload(
    *,
    provider: str | None = None,
    group: str | None = None,
    detail: str = "full",
    env: Mapping[str, str] | None = None,
    env_file: Path | None = None,
    transport: HttpTransport | None = None,
    build_runtime_env_fn: Callable[..., Mapping[str, str]] = build_runtime_env,
    build_clients_fn: Callable[..., Mapping[str, object]] = build_clients,
    image_probe_fn: Callable[
        [Mapping[str, str] | None], dict[str, dict[str, object]]
    ] = probe_image_conversion_backends,
    browser_probe_fn: Callable[..., dict[str, object]] = static_browser_capabilities,
) -> dict[str, Any]:
    """Build a filtered, network-free provider status report."""

    detail_key = normalize_provider_status_detail(detail)
    selected_names = selected_provider_status_names(provider=provider, group=group)
    runtime_env = (
        dict(build_runtime_env_fn(env, env_file=env_file))
        if env_file is not None
        else dict(build_runtime_env_fn(env))
    )
    active_transport = transport or HttpTransport()
    clients = build_clients_fn(
        transport=active_transport,
        env=runtime_env,
        provider_names=selected_names,
    )
    providers: list[dict[str, Any]] = []
    for provider_name in selected_names:
        client = clients.get(provider_name)
        if client is None:
            result = _provider_status_error_payload(
                provider_name,
                official_provider=is_official_provider(provider_name),
                message=f"{provider_name} is not registered in the provider client registry.",
            )
        else:
            try:
                result = client.probe_status().to_dict()  # type: ignore[attr-defined]
            except Exception as error:  # noqa: BLE001 - one provider must not hide peers.
                result = _provider_status_error_payload(
                    provider_name,
                    official_provider=bool(
                        getattr(
                            client,
                            "official_provider",
                            is_official_provider(provider_name),
                        )
                    ),
                    message=(
                        "Provider diagnostics failed unexpectedly "
                        f"({error.__class__.__name__})."
                    ),
                )
        summary = _provider_summary(result, spec=PROVIDER_CATALOG[provider_name])
        if detail_key == "compact":
            providers.append(
                {
                    "provider": provider_name,
                    "status": result.get("status", ERROR),
                    **summary,
                }
            )
        else:
            providers.append(
                {
                    **result,
                    **summary,
                    "diagnostic_scope": _STATIC_SCOPE,
                    "live_checked": False,
                }
            )

    payload: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_scope": _STATIC_SCOPE,
        "live_network_checked": False,
        "remote_publisher_health": "not_checked",
        "detail": detail_key,
        "provider_filter": normalize_text(provider).lower() or None,
        "group_filter": normalize_text(group).lower() or None,
        "providers": providers,
    }
    if detail_key == "full":
        configuration_names = _configuration_names(selected_names)
        payload["configuration"] = runtime_configuration_report(
            configuration_names,
            base_env=env,
            env_file=env_file,
            default_names=_DEFAULT_CONFIGURATION_NAMES,
            sensitive_names=_sensitive_configuration_names(configuration_names),
        )
        browser_provider = next(
            (name for name in selected_names if provider_has_browser_route(name)),
            selected_names[0] if len(selected_names) == 1 else None,
        )
        try:
            browser = browser_probe_fn(runtime_env, provider=browser_provider)
        except Exception:  # noqa: BLE001 - diagnostics stay structured and secret-free.
            browser = _local_capability_error("browser")
        try:
            image_conversion = image_probe_fn(runtime_env)
        except Exception:  # noqa: BLE001 - diagnostics stay structured and secret-free.
            image_conversion = {"diagnostics": _local_capability_error("image")}
        payload["local_capabilities"] = {
            "browser": browser,
            "image_conversion": image_conversion,
        }
    return payload


def doctor_payload(**kwargs: Any) -> dict[str, Any]:
    """Wrap static runtime and provider diagnostics for the CLI."""

    provider_report = provider_status_payload(**kwargs)
    statuses = {
        normalize_text(str(item.get("status") or ERROR)).lower()
        for item in provider_report.get("providers", [])
        if isinstance(item, Mapping)
    }
    if ERROR in statuses:
        status = ERROR
    elif statuses & {NOT_CONFIGURED, PARTIAL}:
        status = "degraded"
    else:
        status = READY
    return {
        "schema_version": 1,
        "status": status,
        "diagnostic_scope": _STATIC_SCOPE,
        "live_network_checked": False,
        "provider_status": provider_report,
    }


__all__ = [
    "PROVIDER_STATUS_DETAILS",
    "PROVIDER_STATUS_GROUPS",
    "ProviderStatusDetail",
    "ProviderStatusGroup",
    "doctor_payload",
    "is_sensitive_configuration_name",
    "normalize_provider_status_detail",
    "normalize_provider_status_group",
    "normalize_provider_status_provider",
    "provider_status_group_names",
    "provider_status_payload",
    "provider_status_provider_names",
    "selected_provider_status_names",
]
