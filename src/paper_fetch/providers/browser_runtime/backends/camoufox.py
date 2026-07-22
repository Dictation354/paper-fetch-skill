"""Native Firefox/Juggler Camoufox backend."""

from __future__ import annotations

import importlib
from importlib import metadata as importlib_metadata
from importlib import util as importlib_util
import json
import os
from pathlib import Path
import time
from typing import Any
from collections.abc import Mapping

from ....config import (
    BROWSER_BINARY_PATH_ENV_VAR,
    BROWSER_HEADLESS_ENV_VAR,
    BROWSER_TIMEOUT_MS_ENV_VAR,
    BROWSER_USER_AGENT_ENV_VAR,
    browser_env_value,
    parse_positive_int_env,
    resolve_user_data_dir,
)
from ....reason_codes import ERROR, NOT_CONFIGURED, OK, READY
from ....utils import normalize_text, sanitize_filename
from ... import _cloakbrowser
from ...base import (
    ProviderFailure,
    ProviderStatusResult,
    build_provider_status_check,
    provider_status_check_from_failure,
)
from .. import paths as runtime_paths
from ..context import open_browser_context
from ..types import BrowserFetchedHtml, BrowserRuntimeConfig

CAMOUFOX_STATUS_PROBE_ID = "probe://camoufox/status"


def _env_flag_false(value: str | None) -> bool:
    return normalize_text(value).lower() in {"0", "false", "no", "off"}


def _dependency_details() -> dict[str, Any]:
    packages = {
        name: importlib_util.find_spec(name) is not None
        for name in ("playwright", "camoufox")
    }
    details: dict[str, Any] = {"probe": "importlib.find_spec", "packages": packages}
    for package, available in packages.items():
        if not available:
            continue
        try:
            details[f"{package}_version"] = importlib_metadata.version(package)
        except importlib_metadata.PackageNotFoundError:
            details[f"{package}_version"] = None
    if packages["camoufox"]:
        try:
            pkgman = importlib.import_module("camoufox.pkgman")
            multiversion = importlib.import_module("camoufox.multiversion")
            config_path = Path(multiversion.CONFIG_FILE)
            config_payload = (
                json.loads(config_path.read_text(encoding="utf-8"))
                if config_path.is_file()
                else {}
            )
            active_version = normalize_text(
                str(
                    config_payload.get("active_version")
                    if isinstance(config_payload, Mapping)
                    else ""
                )
            )
            runtime_path = (
                Path(pkgman.INSTALL_DIR) / active_version if active_version else None
            )
            details["runtime_path"] = (
                str(runtime_path) if runtime_path is not None else None
            )
            details["runtime_installed"] = bool(
                runtime_path is not None and runtime_path.is_dir()
            )
        except Exception as exc:
            details["runtime_path"] = None
            details["runtime_installed"] = False
            details["runtime_probe_error"] = normalize_text(str(exc))
    return details


class CamoufoxBackend:
    name = "camoufox"

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
        runtime_paths.validate_storage_state_path(
            storage_state_path,
            provider=provider,
            require_storage_state=require_storage_state,
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
                default=_cloakbrowser.DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS,
            ),
            binary_path=binary_path,
            profile_dir=profile_dir,
            user_data_dir=user_data_dir,
            storage_state_path=storage_state_path,
            backend=self.name,
        )

    def ensure_runtime_ready(self, config: BrowserRuntimeConfig) -> None:
        del config
        details = _dependency_details()
        packages = details["packages"]
        if not packages["playwright"] or not packages["camoufox"]:
            raise ProviderFailure(
                NOT_CONFIGURED,
                "Camoufox browser workflow requires compatible camoufox and playwright packages.",
            )

    def probe_runtime_status(
        self,
        env: Mapping[str, str],
        *,
        provider: str,
        doi: str = CAMOUFOX_STATUS_PROBE_ID,
        deep: bool = False,
    ) -> ProviderStatusResult:
        checks = []
        config: BrowserRuntimeConfig | None = None
        details = _dependency_details()
        available = all(details["packages"].values())
        try:
            config = self.load_runtime_config(env, provider=provider, doi=doi)
            checks.append(
                build_provider_status_check(
                    "runtime_env",
                    OK if available else NOT_CONFIGURED,
                    (
                        f"{provider} Camoufox runtime environment is configured."
                        if available
                        else f"{provider} requires compatible camoufox and playwright packages."
                    ),
                    details={
                        "backend": self.name,
                        "headless": config.headless,
                        "timeout_ms": config.timeout_ms,
                        "binary_path_configured": bool(config.binary_path),
                        "profile_dir_configured": bool(config.profile_dir),
                        "user_data_dir_configured": bool(config.user_data_dir),
                        "storage_state_path": str(
                            runtime_paths.storage_state_path(config) or ""
                        ),
                        "browser_user_agent_ignored": bool(
                            normalize_text(env.get(BROWSER_USER_AGENT_ENV_VAR))
                        ),
                    },
                )
            )
        except ProviderFailure as exc:
            checks.append(provider_status_check_from_failure("runtime_env", exc))
        except Exception as exc:
            checks.append(build_provider_status_check("runtime_env", ERROR, str(exc)))
        checks.append(
            build_provider_status_check(
                "playwright_dependency",
                OK if available else NOT_CONFIGURED,
                (
                    "Camoufox and Playwright Python packages are importable; no browser is launched."
                    if available
                    else "Camoufox or Playwright Python package is not installed."
                ),
                details=details,
            )
        )

        if deep and config is not None and available:
            manager = context = None
            started = time.monotonic()
            try:
                self.ensure_runtime_ready(config)
                manager, context = open_browser_context(config)
                deep_check = build_provider_status_check(
                    "browser_context",
                    OK,
                    "Native Camoufox browser context can be created.",
                    details={"duration_seconds": round(time.monotonic() - started, 3)},
                )
            except Exception as exc:
                deep_check = build_provider_status_check(
                    "browser_context",
                    ERROR,
                    normalize_text(str(exc)) or exc.__class__.__name__,
                    details={"duration_seconds": round(time.monotonic() - started, 3)},
                )
            finally:
                for value in (context, manager):
                    try:
                        if value is not None:
                            value.close()
                    except Exception:
                        pass
            checks.append(deep_check)

        if any(check.status == ERROR for check in checks):
            status = ERROR
        elif all(check.status == OK for check in checks):
            status = READY
        else:
            status = NOT_CONFIGURED
        missing_env = list(
            dict.fromkeys(name for check in checks for name in check.missing_env)
        )
        return ProviderStatusResult(
            provider=provider,
            status=status,
            available=status == READY,
            official_provider=True,
            missing_env=missing_env,
            notes=[],
            checks=checks,
        )

    def fetch_html(
        self,
        candidate_urls: list[str],
        *,
        publisher: str,
        config: BrowserRuntimeConfig,
        **kwargs: Any,
    ) -> BrowserFetchedHtml:
        return _cloakbrowser.fetch_html_with_cloakbrowser(
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
    ) -> dict[str, Any]:
        return _cloakbrowser.warm_browser_context_with_cloakbrowser(
            candidate_urls,
            publisher=publisher,
            config=config,
            browser_context_seed=browser_context_seed,
            runtime_context=runtime_context,
            lightweight=lightweight,
        )

    def storage_state_path(self, config: BrowserRuntimeConfig) -> Path | None:
        return runtime_paths.storage_state_path(config)

    def save_storage_state(
        self,
        context: Any,
        config: BrowserRuntimeConfig,
        *,
        filter_url: str | None = None,
    ) -> Mapping[str, Any]:
        return runtime_paths.save_storage_state(context, config, filter_url=filter_url)


DEFAULT_CAMOUFOX_BACKEND = CamoufoxBackend()
