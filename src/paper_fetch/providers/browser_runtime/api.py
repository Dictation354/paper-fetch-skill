"""Publisher browser runtime configuration, preparation and status."""

from __future__ import annotations

import os
import tempfile
import time
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from ...browser_runtime_policy import engine_name, selected_backend
from ...config import (
    BROWSER_BINARY_PATH_ENV_VAR,
    BROWSER_HEADLESS_ENV_VAR,
    BROWSER_TIMEOUT_MS_ENV_VAR,
    BROWSER_USER_AGENT_ENV_VAR,
    parse_positive_int_env,
    resolve_user_data_dir,
)
from ...reason_codes import ERROR, NOT_CONFIGURED, OK, READY
from ...utils import normalize_text, sanitize_filename
from ..base import (
    ProviderFailure,
    ProviderStatusResult,
    build_provider_status_check,
    provider_status_check_from_failure,
)
from . import paths
from .preparation import (
    BROWSER_PACKAGE_PINS,
    browser_cache_dir,
    inspect_chromium,
    package_versions,
    prepare_chromium,
    verify_package_installation,
)
from .profile import PublisherProfileManager, profile_path
from .types import (
    DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS as DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS,
)
from .types import (
    DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS as DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS,
)
from .types import (
    DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS as DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS,
)
from .types import BrowserFetchedHtml, BrowserRuntimeConfig, BrowserWarmResult


def load_runtime_config(
    env: Mapping[str, str], *, provider: str, doi: str
) -> BrowserRuntimeConfig:
    binary = str(env.get(BROWSER_BINARY_PATH_ENV_VAR, "")).strip()
    path = Path(binary).expanduser().resolve() if binary else None
    if path is not None and (not path.is_file() or not os.access(path, os.X_OK)):
        raise ProviderFailure(
            NOT_CONFIGURED,
            f"{BROWSER_BINARY_PATH_ENV_VAR} is not an executable file: {path}",
        )
    profile_dir = paths.configured_profile_dir(env)
    user_data_dir = paths.configured_user_data_dir(env)
    if profile_dir is None and user_data_dir is None:
        user_data_dir = paths.default_provider_user_data_dir(env, provider=provider)
    cache = None
    if path is None:
        try:
            cache = browser_cache_dir(env)
        except Exception as exc:
            raise ProviderFailure(
                NOT_CONFIGURED, f"Chromium cache configuration failed: {exc}"
            ) from exc
    return BrowserRuntimeConfig(
        provider=provider,
        doi=doi,
        artifact_dir=(
            resolve_user_data_dir(env)
            / "publisher-browser-artifacts"
            / provider
            / sanitize_filename(doi)
        ),
        headless=normalize_text(env.get(BROWSER_HEADLESS_ENV_VAR)).lower()
        not in {"0", "false", "no", "off"},
        user_agent=None,
        timeout_ms=parse_positive_int_env(
            env,
            BROWSER_TIMEOUT_MS_ENV_VAR,
            default=DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS,
        ),
        binary_path=str(path) if path is not None else None,
        profile_dir=profile_dir,
        user_data_dir=user_data_dir,
        browser_cache_dir=cache,
    )


def ensure_runtime_ready(config: BrowserRuntimeConfig) -> None:
    verify_package_installation()


def create_runtime_manager(
    config: BrowserRuntimeConfig, *, runtime_context: Any = None
) -> PublisherProfileManager:
    return PublisherProfileManager(config, runtime_context=runtime_context)


def prepare_runtime(
    config: BrowserRuntimeConfig, *, runtime_context: Any = None
) -> Path:
    return prepare_chromium(config, runtime_context=runtime_context)


def probe_runtime_status(
    env: Mapping[str, str],
    *,
    provider: str,
    doi: str = "probe://browser/status",
    deep: bool = False,
) -> ProviderStatusResult:
    checks = []
    backend = selected_backend(env, provider=provider)
    engine = engine_name()
    versions = package_versions()
    package_ready = versions == BROWSER_PACKAGE_PINS
    details = {
        "backend": backend,
        "engine": engine,
        "packages": {name: name in versions for name in BROWSER_PACKAGE_PINS},
        "package_versions": versions,
        "required_versions": BROWSER_PACKAGE_PINS,
        "package_ready": package_ready,
    }
    config = None
    available = False
    runtime_details: dict[str, Any] = {"backend": backend, "engine": engine}
    try:
        config = load_runtime_config(env, provider=provider, doi=doi)
        path, version, installed = config.binary_path, None, bool(config.binary_path)
        if config.browser_cache_dir is not None and package_ready:
            executable, version, installed = inspect_chromium(config.browser_cache_dir)
            path = str(executable)
        available = package_ready and installed
        runtime_details.update(
            headless=config.headless,
            timeout_ms=config.timeout_ms,
            binary_path_configured=bool(config.binary_path),
            profile_dir_configured=bool(config.profile_dir),
            user_data_dir_configured=bool(paths.configured_user_data_dir(env)),
            profile_dir=str(profile_path(config)),
            browser_user_agent_ignored=bool(
                normalize_text(env.get(BROWSER_USER_AGENT_ENV_VAR))
            ),
            package_ready=package_ready,
            runtime_installed=installed,
            runtime_path=path,
            runtime_version=version,
            runtime_state="ready" if installed else "missing",
            download_required=package_ready and not installed,
        )
        checks.append(
            build_provider_status_check(
                "runtime_env",
                OK if available else NOT_CONFIGURED,
                "Scrapling Chromium is configured."
                if available
                else "Scrapling Chromium dependencies or executable are missing.",
                details=runtime_details,
            )
        )
    except ProviderFailure as exc:
        checks.append(provider_status_check_from_failure("runtime_env", exc))
    except (OSError, ValueError, LookupError) as exc:
        checks.append(build_provider_status_check("runtime_env", ERROR, str(exc)))

    checks.extend(
        [
            build_provider_status_check(
                "playwright_dependency",
                OK if package_ready else NOT_CONFIGURED,
                "Pinned browser Python packages are installed."
                if package_ready
                else "Install the pinned browser Python packages with paper-fetch-skill[browser].",
                details=details,
            ),
            build_provider_status_check(
                "browser_runtime",
                OK if available else NOT_CONFIGURED,
                "Chromium executable is installed."
                if available
                else "First browser use prepares the Patchright Chromium executable when the Python packages are installed.",
                details=runtime_details,
            ),
        ]
    )
    if deep and config is not None and available:
        started = time.monotonic()
        with tempfile.TemporaryDirectory(
            prefix="paper-fetch-chromium-probe-"
        ) as directory:
            manager = create_runtime_manager(
                replace(config, profile_dir=Path(directory), headless=True)
            )
            try:
                manager.new_context()
                check = build_provider_status_check(
                    "browser_context",
                    OK,
                    "Scrapling Chromium context opened.",
                    details={
                        **manager.diagnostics,
                        "duration_seconds": round(time.monotonic() - started, 3),
                    },
                )
            except Exception as exc:
                check = build_provider_status_check(
                    "browser_context",
                    ERROR,
                    str(exc),
                    details=getattr(exc, "details", {}),
                )
            finally:
                manager.close()
        checks.append(check)
    status = (
        ERROR
        if any(check.status == ERROR for check in checks)
        else READY
        if all(check.status == OK for check in checks)
        else NOT_CONFIGURED
    )
    return ProviderStatusResult(
        provider=provider,
        status=status,
        available=status == READY,
        official_provider=True,
        missing_env=[],
        notes=[],
        checks=checks,
    )


def fetch_html_with_browser(
    candidate_urls: list[str],
    *,
    publisher: str,
    config: BrowserRuntimeConfig,
    **kwargs: Any,
) -> BrowserFetchedHtml:
    from .html_fetcher import fetch_browser_html

    kwargs.pop("warm_wait_seconds", None)
    return fetch_browser_html(
        candidate_urls, publisher=publisher, config=config, **kwargs
    )


fetch_html_with_browser.paper_fetch_html_fetcher_name = "scrapling"  # type: ignore[attr-defined]


def warm_browser_context(
    candidate_urls: list[str],
    *,
    publisher: str,
    config: BrowserRuntimeConfig,
    browser_context_seed: Mapping[str, Any] | None = None,
    runtime_context: Any | None = None,
    lightweight: bool = False,
) -> BrowserWarmResult:
    from .html_fetcher import warm_browser_html_context

    return warm_browser_html_context(
        candidate_urls,
        publisher=publisher,
        config=config,
        browser_context_seed=browser_context_seed,
        runtime_context=runtime_context,
        lightweight=lightweight,
    )
