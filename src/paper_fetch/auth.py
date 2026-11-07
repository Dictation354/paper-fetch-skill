"""Interactive authentication helpers for publisher browser workflows."""

from __future__ import annotations

import contextlib
import urllib.parse
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from collections.abc import Callable, Mapping

from .config import (
    AMS_STORAGE_STATE_JSON_ENV_VAR,
    BROWSER_HEADLESS_ENV_VAR,
    BROWSER_TIMEOUT_MS_ENV_VAR,
    BROWSER_USER_AGENT_ENV_VAR,
    WILEY_STORAGE_STATE_JSON_ENV_VAR,
    build_runtime_env,
    browser_env_value,
)
from .extraction.html.signals import detect_html_block, summarize_html
from .provider_catalog import (
    ordered_provider_specs,
    provider_supports_auth,
    provider_domain_matches,
    provider_domains,
)
from .providers.browser_runtime import (
    BrowserRuntimeConfig,
    BrowserStagedStorageState,
    ensure_runtime_ready,
    load_runtime_config,
    storage_state_path,
)
from .providers.browser_runtime.paths import (
    commit_staged_storage_state,
    configured_storage_state_path,
    runtime_with_default_storage_profile,
    stage_storage_state,
)
from .providers.browser_runtime.profile import PublisherProfileManager, profile_path
from .providers.base import ProviderFailure
from .reason_codes import (
    AUTH_FINAL_URL_INVALID,
    AUTH_REPLAY_FAILED,
    ERROR,
)
from .utils import normalize_text, provider_display_name


@dataclass(frozen=True)
class AuthTarget:
    doi: str
    url: str


AUTH_TARGETS: Mapping[str, AuthTarget] = {
    "elsevier": AuthTarget(
        doi="10.1016/j.agrformet.2024.109975",
        url="https://www.sciencedirect.com/science/article/pii/S016819232400090X",
    ),
    "ams": AuthTarget(
        doi="10.1175/jcli-d-23-0738.1",
        url="https://journals.ametsoc.org/view/journals/clim/37/24/JCLI-D-23-0738.1.xml",
    ),
    "wiley": AuthTarget(
        doi="10.1111/gcb.15322",
        url="https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.15322",
    ),
    "science": AuthTarget(
        doi="10.1126/science.adz3492",
        url="https://www.science.org/doi/full/10.1126/science.adz3492",
    ),
    "pnas": AuthTarget(
        doi="10.1073/pnas.2406303121",
        url="https://www.pnas.org/doi/full/10.1073/pnas.2406303121",
    ),
    "mdpi": AuthTarget(
        doi="10.3390/membranes15030093",
        url="https://www.mdpi.com/2077-0375/15/3/93",
    ),
    "royalsocietypublishing": AuthTarget(
        doi="10.1098/rsos.201200",
        url="https://royalsocietypublishing.org/doi/10.1098/rsos.201200",
    ),
    "annualreviews": AuthTarget(
        doi="10.1146/annurev-control-030123-013355",
        url="https://www.annualreviews.org/content/journals/10.1146/annurev-control-030123-013355",
    ),
    "acs": AuthTarget(
        doi="10.1021/acsomega.4c03987",
        url="https://pubs.acs.org/doi/10.1021/acsomega.4c03987",
    ),
    "iop": AuthTarget(
        doi="10.1088/1748-9326/ab7d02",
        url="https://iopscience.iop.org/article/10.1088/1748-9326/ab7d02",
    ),
    "ieee": AuthTarget(
        doi="10.1109/TIM.2024.3509573",
        url="https://ieeexplore.ieee.org/document/10772041/",
    ),
    "aip": AuthTarget(
        doi="10.1063/5.0129134",
        url="https://pubs.aip.org/aip/adv/article/12/12/125205/2820011/On-chip-on-demand-delivery-of-K-for-in-vitro",
    ),
    "tandf": AuthTarget(
        doi="10.1080/15481603.2026.2667034",
        url="https://www.tandfonline.com/doi/full/10.1080/15481603.2026.2667034",
    ),
}

_LEGACY_AUTH_STORAGE_STATE_ENV_VARS = {
    "ams": AMS_STORAGE_STATE_JSON_ENV_VAR,
    "wiley": WILEY_STORAGE_STATE_JSON_ENV_VAR,
}


@dataclass(frozen=True)
class AuthResult:
    provider: str
    storage_state_path: Path
    profile_dir: Path | None
    verified: bool
    final_url: str | None
    title: str | None
    json_export: Mapping[str, Any] | None = None


def browser_auth_provider_names() -> tuple[str, ...]:
    return tuple(
        spec.name
        for spec in ordered_provider_specs()
        if provider_supports_auth(spec.name)
    )


def _require_browser_auth_provider(provider: str) -> str:
    provider_key = normalize_text(provider).lower()
    if not provider_key:
        raise ProviderFailure(ERROR, "Auth provider is required.")
    if provider_key not in browser_auth_provider_names():
        supported = ", ".join(browser_auth_provider_names())
        raise ProviderFailure(
            ERROR,
            f"Unsupported auth provider {provider!r}; supported browser providers: {supported}.",
        )
    return provider_key


def _auth_target_for_provider(
    provider_key: str, *, target_url: str | None
) -> AuthTarget:
    auth_target = AUTH_TARGETS.get(provider_key)
    if auth_target is not None:
        return auth_target
    if target_url:
        return AuthTarget(doi=provider_key, url=target_url)
    raise ProviderFailure(
        ERROR,
        (
            f"No built-in auth sample URL is configured for provider {provider_key!r}; "
            "rerun with --url pointing to a publisher article page."
        ),
    )


def _provider_label(provider: str) -> str:
    return provider_display_name(provider)


def _manual_auth_prompt(
    *,
    provider_label: str,
    url: str,
    profile_dir: Path | None,
    storage_state_path: Path | None,
) -> str:
    lines = [
        f"{provider_label} authentication browser is open.",
        f"URL: {url}",
    ]
    if profile_dir is not None:
        lines.append(f"Profile directory: {profile_dir}")
    if storage_state_path is not None:
        lines.append(f"Storage-state JSON: {storage_state_path}")
    lines.extend(
        [
            "Complete any publisher login or verification in the browser.",
            "Press Enter here when finished to close and verify the same native profile.",
        ]
    )
    return "\n".join(lines) + "\n"


def _wait_for_manual_completion(
    *,
    provider_label: str,
    url: str,
    profile_dir: Path | None,
    storage_state_path: Path | None,
    confirm: Callable[[str], object] | None,
) -> None:
    if confirm is None:
        return
    prompt = _manual_auth_prompt(
        provider_label=provider_label,
        url=url,
        profile_dir=profile_dir,
        storage_state_path=storage_state_path,
    )
    try:
        confirm(prompt)
    except EOFError as exc:
        raise ProviderFailure(
            ERROR,
            f"{provider_label} authentication requires interactive stdin.",
        ) from exc


def _runtime_with_auth_storage(
    runtime: BrowserRuntimeConfig,
    *,
    env: Mapping[str, str],
    provider: str,
    storage_state_path: Path | None = None,
) -> BrowserRuntimeConfig:
    if runtime.profile_dir is None and runtime.user_data_dir is None:
        runtime = runtime_with_default_storage_profile(
            runtime,
            env=env,
            provider=provider,
        )
    if storage_state_path is None:
        return runtime
    return replace(
        runtime,
        storage_state_path=storage_state_path.expanduser().resolve(),
    )


def _browser_page_snapshot(
    page: Any,
    *,
    fallback_url: str,
) -> tuple[str, str | None, str, int | None]:
    final_url = normalize_text(str(getattr(page, "url", "") or "")) or fallback_url
    try:
        title = normalize_text(str(page.title() or "")) or None
    except Exception:
        title = None
    try:
        html = str(page.content() or "")
    except Exception:
        html = ""
    response_status = None
    return final_url, title, html, response_status


def _require_accepted_auth_page(
    page: Any,
    *,
    provider: str,
    provider_label: str,
    fallback_url: str,
) -> tuple[str, str | None]:
    final_url, title, html, status = _browser_page_snapshot(
        page,
        fallback_url=fallback_url,
    )
    try:
        hostname = normalize_text(
            urllib.parse.urlparse(final_url).hostname or ""
        ).lower()
    except Exception:
        hostname = ""
    fallback_hostname = normalize_text(
        urllib.parse.urlparse(fallback_url).hostname or ""
    ).lower()
    accepted_host = bool(
        hostname
        and (
            provider_domain_matches(provider, hostname)
            or (not provider_domains(provider) and hostname == fallback_hostname)
        )
    )
    if not accepted_host:
        raise ProviderFailure(
            AUTH_FINAL_URL_INVALID,
            (
                f"{provider_label} authentication did not return to an accepted "
                f"provider host ({hostname or 'unknown host'})."
            ),
        )
    detected = detect_html_block(title or "", summarize_html(html), status)
    if detected is not None:
        raise ProviderFailure(
            AUTH_FINAL_URL_INVALID,
            (
                f"{provider_label} authentication is still blocked "
                f"({detected.reason}): {detected.message}"
            ),
        )
    if not title and not normalize_text(html):
        raise ProviderFailure(
            AUTH_FINAL_URL_INVALID,
            f"{provider_label} authentication page did not expose usable content.",
        )
    return final_url, title


def authenticate_provider_profile(
    *,
    provider: str,
    target_url: str | None = None,
    timeout_ms: int | None = None,
    browser_user_agent: str | None = None,
    confirm: Callable[[str], object] | None = input,
    env: Mapping[str, str] | None = None,
) -> AuthResult:
    provider_key = _require_browser_auth_provider(provider)
    provider_label = _provider_label(provider_key)
    auth_target = _auth_target_for_provider(provider_key, target_url=target_url)
    active_url = target_url or auth_target.url

    runtime_env = build_runtime_env() if env is None else build_runtime_env(env)
    fetch_headless = normalize_text(
        browser_env_value(runtime_env, BROWSER_HEADLESS_ENV_VAR)
    ).lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    runtime_env[BROWSER_HEADLESS_ENV_VAR] = "0"
    explicit_storage_path = configured_storage_state_path(
        runtime_env, provider=provider_key
    )
    legacy_storage_env_var = _LEGACY_AUTH_STORAGE_STATE_ENV_VARS.get(provider_key)
    if legacy_storage_env_var is not None:
        runtime_env.pop(legacy_storage_env_var, None)
    if timeout_ms is not None:
        runtime_env[BROWSER_TIMEOUT_MS_ENV_VAR] = str(timeout_ms)
    if browser_user_agent:
        runtime_env[BROWSER_USER_AGENT_ENV_VAR] = browser_user_agent

    runtime = load_runtime_config(
        runtime_env,
        provider=provider_key,
        doi=auth_target.doi,
    )
    runtime = _runtime_with_auth_storage(
        runtime,
        env=runtime_env,
        provider=provider_key,
        storage_state_path=explicit_storage_path,
    )
    ensure_runtime_ready(runtime)

    profile_dir = profile_path(runtime)
    resolved_storage_state_path = storage_state_path(runtime)
    manager: Any | None = None
    context = None
    page = None
    final_url: str | None = None
    title: str | None = None
    staged_state: BrowserStagedStorageState | None = None
    try:
        if browser_user_agent:
            raise ProviderFailure(
                ERROR,
                "--browser-user-agent cannot be used with Camoufox because it would make the generated Firefox fingerprint inconsistent.",
            )
        if profile_dir is None:
            raise ProviderFailure(
                ERROR,
                "Camoufox authentication requires a provider profile directory.",
            )
        profile_dir.mkdir(parents=True, exist_ok=True)
        if runtime.state_mode == "json":
            from .providers.browser_runtime.byparr_manager import (
                ByparrManager,
            )

            manager = ByparrManager(runtime)
        else:
            manager = PublisherProfileManager(runtime)
        context = manager.new_context()
        page = context.new_page()
        from .providers.browser_runtime.navigation import navigate_page

        navigate_page(
            page,
            active_url,
            wait_until="domcontentloaded",
            timeout_ms=runtime.timeout_ms,
        )
        _wait_for_manual_completion(
            provider_label=provider_label,
            url=active_url,
            profile_dir=profile_dir,
            storage_state_path=resolved_storage_state_path,
            confirm=confirm,
        )
        final_url, title = _require_accepted_auth_page(
            page,
            provider=provider_key,
            provider_label=provider_label,
            fallback_url=active_url,
        )
        if runtime.state_mode == "json":
            staged_state, stage_result = stage_storage_state(
                context, runtime, filter_url=final_url
            )
            if staged_state is None or not commit_staged_storage_state(
                staged_state, runtime
            ).get("saved"):
                raise ProviderFailure(
                    ERROR,
                    f"Cannot save accepted {provider_label} browser authentication state.",
                )
    except ProviderFailure:
        raise
    except Exception as exc:
        message = normalize_text(str(exc)) or exc.__class__.__name__
        raise ProviderFailure(
            ERROR, f"{provider_label} authentication failed: {message}"
        ) from exc
    finally:
        for value in (page, manager):
            try:
                if value is not None:
                    value.close()
            except Exception:
                pass

    # Native replay is the auth condition; JSON export is an auxiliary snapshot.
    replay_runtime = replace(runtime, headless=fetch_headless)
    manager = None
    page = None
    try:
        if replay_runtime.state_mode == "json":
            from .providers.browser_runtime.byparr_manager import (
                ByparrManager,
            )

            manager = ByparrManager(replay_runtime)
        else:
            manager = PublisherProfileManager(replay_runtime)
        context = manager.new_context()
        page = context.new_page()
        from .providers.browser_runtime.navigation import navigate_page

        navigate_page(
            page,
            active_url,
            wait_until="domcontentloaded",
            timeout_ms=runtime.timeout_ms,
        )
        final_url, title = _require_accepted_auth_page(
            page,
            provider=provider_key,
            provider_label=provider_label,
            fallback_url=active_url,
        )
        digest = manager.refresh()
        manager.metadata["auth"] = {
            "native_profile_verified": runtime.state_mode == "native",
            "state_replay_verified": True,
            "headless": fetch_headless,
            "state_sha256": digest,
        }
        try:
            staged_state, stage_result = stage_storage_state(
                context, runtime, filter_url=final_url
            )
            if staged_state is None:
                save_result = {**stage_result, "saved": False}
            else:
                save_result = commit_staged_storage_state(staged_state, runtime)
                if save_result.get("saved"):
                    manager.note_json_export(staged_state.path)
        except Exception as exc:
            save_result = {
                "attempted": True,
                "saved": False,
                "reason": "export_failed",
                "error": normalize_text(str(exc)),
            }
    except ProviderFailure:
        raise
    except Exception as exc:
        raise ProviderFailure(
            AUTH_REPLAY_FAILED, f"{provider_label} native profile replay failed: {exc}"
        ) from exc
    finally:
        if page is not None:
            with contextlib.suppress(Exception):
                page.close()
        if manager is not None:
            manager.close()

    return AuthResult(
        provider=provider_key,
        storage_state_path=resolved_storage_state_path,
        profile_dir=profile_dir,
        verified=True,
        final_url=final_url,
        title=title,
        json_export=save_result,
    )
