"""Interactive authentication helpers for publisher browser workflows."""

from __future__ import annotations

import contextlib
import time
import urllib.parse
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from collections.abc import Callable, Mapping

from .config import (
    BROWSER_HEADLESS_ENV_VAR,
    BROWSER_TIMEOUT_MS_ENV_VAR,
    BROWSER_USER_AGENT_ENV_VAR,
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
from .providers.browser_runtime.api import ensure_runtime_ready, load_runtime_config
from .providers.browser_runtime.types import BrowserRuntimeConfig
from .providers.browser_runtime.paths import (
    runtime_with_default_profile,
)
from .providers.browser_runtime.profile import PublisherProfileManager, profile_path
from .providers.base import ProviderFailure
from .failure import FailureDiagnostics
from .http import RequestCancelledError
from .reason_codes import (
    AUTH_FINAL_URL_INVALID,
    AUTH_REPLAY_FAILED,
    AUTH_STATE_SAVE_FAILED,
    AUTH_REQUIRED,
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


@dataclass(frozen=True)
class AuthResult:
    provider: str
    profile_dir: Path | None
    verified: bool
    final_url: str | None
    title: str | None


class AuthCancelledError(ProviderFailure, RequestCancelledError):
    def __init__(self, message: str, *, provider: str, stage: str):
        super().__init__(
            "request_cancelled",
            message,
            diagnostics=FailureDiagnostics(
                provider=provider, stage=stage, retryable=False
            ),
        )


def ams_profile_path(env: Mapping[str, str]) -> Path:
    runtime = load_runtime_config(env, provider="ams", doi=AUTH_TARGETS["ams"].doi)
    return profile_path(_runtime_with_auth_profile(runtime, env=env, provider="ams"))


def has_verified_ams_profile(env: Mapping[str, str]) -> bool:
    from .providers.browser_runtime.profile import _metadata
    from .providers.browser_runtime.types import BrowserRuntimeFailure

    try:
        data = _metadata(ams_profile_path(env))
    except (OSError, BrowserRuntimeFailure):
        return False
    auth = data.get("auth")
    # Fetches refresh the current summary as cookies change. The auth digest is
    # evidence of the successful reopen, not a pin on the current cookie values.
    return bool(
        data.get("provider") == "ams"
        and data.get("native_initialized")
        and data.get("state_sha256")
        and isinstance(auth, dict)
        and auth.get("native_profile_verified") is True
        and auth.get("state_replay_verified") is True
        and auth.get("state_sha256")
    )


def require_ams_auth(env: Mapping[str, str], *, provider: str) -> None:
    """Python acquisition boundaries report requirements without opening a window."""
    if provider == "ams" and not has_verified_ams_profile(env):
        raise ProviderFailure(
            AUTH_REQUIRED,
            "AMS requires a verified native profile; run `paper-fetch auth ams`.",
            diagnostics=FailureDiagnostics(
                provider="ams", stage="auth_preflight", retryable=False
            ),
        )


@contextlib.contextmanager
def ams_auth_coordination(env: Mapping[str, str], *, cancel: Callable[[], None]):
    """Coordinate CLI authentication separately from the browser profile lease."""
    from filelock import FileLock, Timeout

    path = ams_profile_path(env)
    path.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path / ".paper-fetch-auth.lock"))
    try:
        while True:
            cancel()
            try:
                lock.acquire(timeout=0)
                break
            except Timeout:
                time.sleep(0.05)
        cancel()
        yield
    finally:
        if lock.is_locked:
            lock.release()


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
) -> str:
    lines = [
        f"{provider_label} authentication browser is open.",
        f"URL: {url}",
    ]
    if profile_dir is not None:
        lines.append(f"Profile directory: {profile_dir}")
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
    confirm: Callable[[str], object] | None,
) -> None:
    if confirm is None:
        return
    prompt = _manual_auth_prompt(
        provider_label=provider_label,
        url=url,
        profile_dir=profile_dir,
    )
    try:
        confirm(prompt)
    except EOFError as exc:
        raise ProviderFailure(
            ERROR,
            f"{provider_label} authentication requires interactive stdin.",
        ) from exc


def _runtime_with_auth_profile(
    runtime: BrowserRuntimeConfig,
    *,
    env: Mapping[str, str],
    provider: str,
) -> BrowserRuntimeConfig:
    if runtime.profile_dir is None and runtime.user_data_dir is None:
        runtime = runtime_with_default_profile(
            runtime,
            env=env,
            provider=provider,
        )
    return runtime


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
            diagnostics=FailureDiagnostics(
                provider=provider,
                http_status=status,
                details={"challenge_reason": detected.reason},
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
    if timeout_ms is not None:
        runtime_env[BROWSER_TIMEOUT_MS_ENV_VAR] = str(timeout_ms)
    if browser_user_agent:
        runtime_env[BROWSER_USER_AGENT_ENV_VAR] = browser_user_agent

    runtime = load_runtime_config(
        runtime_env,
        provider=provider_key,
        doi=auth_target.doi,
    )
    runtime = _runtime_with_auth_profile(
        runtime,
        env=runtime_env,
        provider=provider_key,
    )
    ensure_runtime_ready(runtime)

    profile_dir = profile_path(runtime)
    manager: Any | None = None
    context = None
    page = None
    final_url: str | None = None
    title: str | None = None
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
        manager = PublisherProfileManager(runtime)
        context = manager.new_context()
        if provider_key == "ams":
            # A failed explicit reauthentication must not leave its changed
            # native state carrying the previous successful auth marker.
            manager.metadata.pop("auth", None)
            manager.refresh()
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
            confirm=confirm,
        )
        final_url, title = _require_accepted_auth_page(
            page,
            provider=provider_key,
            provider_label=provider_label,
            fallback_url=active_url,
        )
    except RequestCancelledError as exc:
        raise AuthCancelledError(
            str(exc), provider=provider_key, stage="auth_manual_check"
        ) from exc
    except ProviderFailure as error:
        error.diagnostics = error.diagnostics.with_updates(
            provider=provider_key,
            stage="auth_manual_check",
            details={
                **error.diagnostics.details,
                "headless": runtime.headless,
                "window_mode": "headless" if runtime.headless else "headed",
            },
        )
        raise
    except Exception as exc:
        message = normalize_text(str(exc)) or exc.__class__.__name__
        raise ProviderFailure(
            ERROR,
            f"{provider_label} authentication failed: {message}",
            diagnostics=FailureDiagnostics(
                provider=provider_key,
                stage="auth_manual_check",
                details={
                    "headless": runtime.headless,
                    "window_mode": "headless" if runtime.headless else "headed",
                },
            ),
        ) from exc
    finally:
        for value in (page, manager):
            try:
                if value is not None:
                    value.close()
            except Exception:
                pass

    # Verify authentication by reopening the same native profile.
    replay_runtime = replace(runtime, headless=fetch_headless)
    manager = None
    page = None
    try:
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
        if not digest:
            raise ProviderFailure(
                AUTH_STATE_SAVE_FAILED,
                f"{provider_label} native profile did not expose a saved state summary.",
            )
        manager.metadata["auth"] = {
            "native_profile_verified": True,
            "state_replay_verified": True,
            "headless": fetch_headless,
            "state_sha256": digest,
        }
    except RequestCancelledError as exc:
        raise AuthCancelledError(
            str(exc), provider=provider_key, stage="auth_profile_reopen"
        ) from exc
    except ProviderFailure as error:
        error.diagnostics = error.diagnostics.with_updates(
            provider=provider_key,
            stage="auth_profile_reopen",
            details={
                **error.diagnostics.details,
                "headless": replay_runtime.headless,
                "window_mode": "headless" if replay_runtime.headless else "headed",
            },
        )
        raise
    except Exception as exc:
        raise ProviderFailure(
            AUTH_REPLAY_FAILED,
            f"{provider_label} native profile replay failed: {exc}",
            diagnostics=FailureDiagnostics(
                provider=provider_key,
                stage="auth_profile_reopen",
                details={
                    "headless": replay_runtime.headless,
                    "window_mode": "headless" if replay_runtime.headless else "headed",
                },
            ),
        ) from exc
    finally:
        if page is not None:
            with contextlib.suppress(Exception):
                page.close()
        if manager is not None:
            manager.close()

    return AuthResult(
        provider=provider_key,
        profile_dir=profile_dir,
        verified=True,
        final_url=final_url,
        title=title,
    )
