"""Shared Playwright configuration and page operations."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from collections.abc import Mapping

from ....config import (
    BROWSER_BINARY_PATH_ENV_VAR,
    BROWSER_HEADLESS_ENV_VAR,
    BROWSER_TIMEOUT_MS_ENV_VAR,
    browser_env_value,
    parse_positive_int_env,
    resolve_user_data_dir,
)
from ....reason_codes import NOT_CONFIGURED
from ....utils import normalize_text, sanitize_filename
from ... import _playwright_browser
from ...base import (
    ProviderFailure,
)
from .. import paths as runtime_paths
from ..types import BrowserFetchedHtml, BrowserRuntimeConfig, BrowserWarmResult


def _env_flag_false(value: str | None) -> bool:
    return normalize_text(value).lower() in {"0", "false", "no", "off"}


class PlaywrightBackend:
    name: str

    def load_runtime_config(
        self,
        env: Mapping[str, str],
        *,
        provider: str,
        doi: str,
        require_storage_state: bool = False,
    ) -> BrowserRuntimeConfig:
        binary_value = browser_env_value(env, BROWSER_BINARY_PATH_ENV_VAR)
        binary_path = binary_value or None
        if binary_path:
            path = Path(binary_path).expanduser()
            if not path.is_file():
                raise ProviderFailure(
                    NOT_CONFIGURED,
                    f"{BROWSER_BINARY_PATH_ENV_VAR} does not point to a file: {path}",
                )
            if os.name != "nt" and not os.access(path, os.X_OK):
                raise ProviderFailure(
                    NOT_CONFIGURED,
                    f"{BROWSER_BINARY_PATH_ENV_VAR} is not executable: {path}",
                )
            binary_path = str(path)

        profile_dir = runtime_paths.configured_profile_dir(
            env, provider=provider, backend=self.name
        )
        user_data_dir = runtime_paths.configured_user_data_dir(env, backend=self.name)
        if profile_dir is None and user_data_dir is None:
            user_data_dir = runtime_paths.default_provider_user_data_dir(
                env, provider=provider, backend=self.name
            )
        storage_state_path = runtime_paths.configured_storage_state_path(
            env, provider=provider
        )
        storage_state_env_var = runtime_paths.provider_storage_state_env_var(provider)
        native_dir = profile_dir or user_data_dir
        native_profile_present = native_dir is not None and any(
            (native_dir / name).is_file()
            for name in ("prefs.js", "cookies.sqlite", "compatibility.ini")
        )
        runtime_paths.validate_storage_state_path(
            storage_state_path,
            provider=provider,
            require_storage_state=require_storage_state and not native_profile_present,
            explicit_path=not native_profile_present
            and bool(
                (
                    env.get(storage_state_env_var, "") if storage_state_env_var else ""
                ).strip()
            ),
        )
        timeout_value = browser_env_value(env, BROWSER_TIMEOUT_MS_ENV_VAR)
        return BrowserRuntimeConfig(
            provider=provider,
            doi=doi,
            artifact_dir=(
                resolve_user_data_dir(env)
                / "publisher-browser-artifacts"
                / provider
                / sanitize_filename(doi)
            ),
            headless=not _env_flag_false(
                browser_env_value(env, BROWSER_HEADLESS_ENV_VAR)
            ),
            user_agent=None,
            timeout_ms=parse_positive_int_env(
                {BROWSER_TIMEOUT_MS_ENV_VAR: timeout_value},
                BROWSER_TIMEOUT_MS_ENV_VAR,
                default=_playwright_browser.DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS,
            ),
            binary_path=binary_path,
            profile_dir=profile_dir,
            user_data_dir=user_data_dir,
            storage_state_path=storage_state_path,
        )

    def fetch_html(
        self,
        candidate_urls: list[str],
        *,
        publisher: str,
        config: BrowserRuntimeConfig,
        **kwargs: Any,
    ) -> BrowserFetchedHtml:
        kwargs.pop("warm_wait_seconds", None)
        return _playwright_browser.fetch_html_with_playwright(
            candidate_urls,
            publisher=publisher,
            config=config,
            **kwargs,
        )

    def warm_context(
        self,
        candidate_urls: list[str],
        *,
        publisher: str,
        config: BrowserRuntimeConfig,
        browser_context_seed: Mapping[str, Any] | None = None,
        runtime_context: Any | None = None,
        lightweight: bool = False,
    ) -> BrowserWarmResult:
        return _playwright_browser.warm_browser_context_with_playwright(
            candidate_urls,
            publisher=publisher,
            config=config,
            browser_context_seed=browser_context_seed,
            runtime_context=runtime_context,
            lightweight=lightweight,
        )

    def storage_state_path(self, config: BrowserRuntimeConfig) -> Path | None:
        return runtime_paths.storage_state_path(config)
