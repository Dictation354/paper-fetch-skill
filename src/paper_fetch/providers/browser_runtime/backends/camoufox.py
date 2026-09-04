"""Native Firefox/Juggler Camoufox backend."""

from __future__ import annotations

from importlib import metadata as importlib_metadata
from importlib import util as importlib_util
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
from ....failure import FailureDiagnostics
from ....reason_codes import ERROR, NOT_CONFIGURED, OK, READY
from ....utils import normalize_text, sanitize_filename
from ... import _playwright_browser
from ...base import (
    ProviderFailure,
    ProviderStatusResult,
    build_provider_status_check,
    provider_status_check_from_failure,
)
from .. import paths as runtime_paths
from ..context import open_browser_context
from ..preparation import probe_camoufox_managed_runtime
from ..types import BrowserFetchedHtml, BrowserRuntimeConfig, BrowserWarmResult

CAMOUFOX_STATUS_PROBE_ID = "probe://camoufox/status"


def _env_flag_false(value: str | None) -> bool:
    return normalize_text(value).lower() in {"0", "false", "no", "off"}


def _dependency_details() -> dict[str, Any]:
    packages = {
        name: importlib_util.find_spec(name) is not None
        for name in ("playwright", "camoufox")
    }
    package_ready = all(packages.values())
    details: dict[str, Any] = {
        "probe": "importlib.find_spec",
        "packages": packages,
        "package_ready": package_ready,
        "runtime_path": None,
        "runtime_installed": False,
        "download_required": package_ready,
    }
    for package, available in packages.items():
        if not available:
            continue
        try:
            details[f"{package}_version"] = importlib_metadata.version(package)
        except importlib_metadata.PackageNotFoundError:
            details[f"{package}_version"] = None
    if packages["camoufox"]:
        try:
            probe = probe_camoufox_managed_runtime()
            runtime_path = probe.runtime_path
            details["runtime_path"] = (
                str(runtime_path) if runtime_path is not None else None
            )
            details["runtime_installed"] = probe.installed
            details["runtime_valid"] = probe.valid
            details["runtime_state"] = probe.state
            details["runtime_version"] = probe.version
            details["download_required"] = not probe.valid
            if probe.message:
                details["runtime_probe_message"] = probe.message
        except Exception as exc:
            details["runtime_probe_error"] = normalize_text(str(exc))
    return details


def _package_ready(details: Mapping[str, Any]) -> bool:
    packages = details.get("packages")
    if not isinstance(packages, Mapping):
        return False
    return bool(
        details.get("package_ready", all(bool(value) for value in packages.values()))
    )


def _runtime_installed(details: Mapping[str, Any]) -> bool:
    # The fallback keeps third-party/test probes that predate the richer status
    # payload compatible. The production probe always supplies runtime_installed.
    if "runtime_valid" in details:
        return bool(details.get("runtime_valid"))
    if "runtime_installed" not in details:
        return _package_ready(details)
    return bool(details.get("runtime_installed"))


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
        storage_state_env_var = runtime_paths.provider_storage_state_env_var(provider)
        runtime_paths.validate_storage_state_path(
            storage_state_path,
            provider=provider,
            require_storage_state=require_storage_state,
            explicit_path=bool(
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

    def ensure_runtime_ready(self, config: BrowserRuntimeConfig) -> None:
        details = _dependency_details()
        if not _package_ready(details):
            raise ProviderFailure(
                NOT_CONFIGURED,
                "Camoufox browser workflow requires compatible camoufox and playwright packages.",
            )
        if not config.binary_path and not _runtime_installed(details):
            raise ProviderFailure(
                NOT_CONFIGURED,
                "Camoufox Python packages are installed, but the browser runtime is missing. "
                "Prepare it explicitly with `python -m camoufox fetch` before fetching.",
                diagnostics=FailureDiagnostics(
                    details={
                        "package_ready": True,
                        "runtime_installed": False,
                        "runtime_valid": False,
                        "download_required": True,
                        "prepare_command": "python -m camoufox fetch",
                    }
                ),
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
        package_ready = _package_ready(details)
        runtime_installed = _runtime_installed(details)
        available = False
        try:
            config = self.load_runtime_config(env, provider=provider, doi=doi)
            available = package_ready and bool(config.binary_path or runtime_installed)
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
                        "package_ready": package_ready,
                        "runtime_installed": runtime_installed,
                        "download_required": package_ready
                        and not bool(config.binary_path or runtime_installed),
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
                OK if package_ready else NOT_CONFIGURED,
                (
                    "Camoufox and Playwright Python packages are importable; no browser is launched."
                    if package_ready
                    else "Camoufox or Playwright Python package is not installed."
                ),
                details=details,
            )
        )
        checks.append(
            build_provider_status_check(
                "browser_runtime",
                OK if available else NOT_CONFIGURED,
                (
                    "Camoufox browser runtime is installed or an explicit executable is configured."
                    if available
                    else (
                        "Camoufox Python packages are installed, but the browser runtime "
                        "must be prepared explicitly before fetching."
                        if package_ready
                        else "Camoufox browser runtime cannot be used until its Python packages are installed."
                    )
                ),
                details={
                    "backend": self.name,
                    "package_ready": package_ready,
                    "runtime_installed": runtime_installed,
                    "binary_path_configured": bool(
                        config is not None and config.binary_path
                    ),
                    "download_required": package_ready and not available,
                    "runtime_path": details.get("runtime_path"),
                    "runtime_state": details.get("runtime_state"),
                    "runtime_version": details.get("runtime_version"),
                    "prepare_command": "python -m camoufox fetch",
                },
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


DEFAULT_CAMOUFOX_BACKEND = CamoufoxBackend()
