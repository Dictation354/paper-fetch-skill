"""Publisher Byparr backend using the selected platform engine."""

from __future__ import annotations

import contextlib
import os
import time
from collections.abc import Mapping
from dataclasses import replace
from importlib import metadata as importlib_metadata
from importlib import util as importlib_util
from pathlib import Path
from typing import Any

from ....config import (
    BROWSER_BINARY_PATH_ENV_VAR,
    BROWSER_HEADLESS_ENV_VAR,
    BROWSER_TIMEOUT_MS_ENV_VAR,
    BROWSER_USER_AGENT_ENV_VAR,
    parse_positive_int_env,
    resolve_user_data_dir,
)
from ....logging_utils import redact_log_value
from ....reason_codes import ERROR, NOT_CONFIGURED, OK, READY
from ....utils import normalize_text, sanitize_filename
from ...base import (
    ProviderFailure,
    ProviderStatusResult,
    build_provider_status_check,
    provider_status_check_from_failure,
)
from .. import byparr_engine, html_fetcher
from .. import paths as runtime_paths
from ..byparr_preparation import (
    PreparationBudget,
    bundled_component_root,
    prepare_components,
    runtime_location,
    valid_cache,
)
from ..context import open_browser_context
from ..preparation import probe_camoufox_managed_runtime
from ..profile import PublisherProfileManager
from ..types import (
    DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS,
    BrowserFetchedHtml,
    BrowserRuntimeConfig,
    BrowserWarmResult,
)

BROWSER_STATUS_PROBE_ID = "probe://browser/status"
_EXPECTED_PACKAGE_VERSIONS = {
    "invisible_playwright": "0.49.1",
    "invisible_core": "61.62.0",
    "camoufox": "0.5.9",
}


def _env_flag_false(value: str | None) -> bool:
    return normalize_text(value).lower() in {"0", "false", "no", "off"}


def _camoufox_dependency_details() -> dict[str, Any]:
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
        "runtime_valid": False,
        "download_required": package_ready,
    }
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


def _dependency_details() -> dict[str, Any]:
    engine = byparr_engine.engine_name()
    if engine != "invisible":
        details = _camoufox_dependency_details()
    else:
        packages = {
            name: importlib_util.find_spec(name) is not None
            for name in ("playwright", "invisible_playwright", "invisible_core")
        }
        details = {
            "probe": "importlib.find_spec",
            "packages": packages,
            "runtime_installed": False,
            "runtime_valid": False,
            "runtime_path": None,
        }
    packages = details["packages"]
    errors: list[str] = []
    for package, present in packages.items():
        if not present:
            errors.append(f"{package} Python package is not installed")
            continue
        try:
            value = importlib_metadata.version(package)
            details[f"{package}_version"] = value
            if package == "playwright":
                pair = tuple(int(p) for p in value.split(".")[:2])
                upper = (2, 0) if engine == "invisible" else (1, 63)
                if not (1, 58) <= pair < upper:
                    required = ">=1.58,<2" if engine == "invisible" else ">=1.58,<1.63"
                    errors.append(f"Playwright {required} required; found {value}")
            elif package in _EXPECTED_PACKAGE_VERSIONS:
                expected = _EXPECTED_PACKAGE_VERSIONS[package]
                if value != expected:
                    errors.append(f"{package} requires {expected}; found {value}")
        except (importlib_metadata.PackageNotFoundError, ValueError):
            errors.append(f"Cannot determine compatible {package} version")
    ready = all(packages.values()) and not errors
    details.update(
        package_ready=ready,
        compatibility_errors=errors,
        engine=engine,
        download_required=ready and not details.get("runtime_valid", False),
    )
    if engine == "invisible" and ready:
        try:
            from invisible_core.download import cache_dir_for_seal, engine_status
            from invisible_core.seal import active_seal

            installed, message = engine_status()
            details.update(
                runtime_installed=installed,
                runtime_valid=installed,
                runtime_path=str(cache_dir_for_seal()),
                runtime_version=active_seal().tag,
                runtime_probe_message=message,
                download_required=not installed,
            )
        except Exception as exc:
            details["runtime_probe_error"] = str(exc)
    return details


def _package_ready(details: Mapping[str, Any]) -> bool:
    packages = details.get("packages")
    if not isinstance(packages, Mapping):
        return False
    return bool(
        details.get("package_ready", all(bool(value) for value in packages.values()))
    )


def _runtime_installed(details: Mapping[str, Any]) -> bool:
    return bool(details.get("runtime_valid"))


class ByparrBackend:
    name = "byparr"

    def dependency_details(self) -> dict[str, Any]:
        return _dependency_details()

    def engine_label(self) -> str:
        return "Invisible" if byparr_engine.engine_name() == "invisible" else "Camoufox"

    def load_runtime_config(
        self,
        env: Mapping[str, str],
        *,
        provider: str,
        doi: str,
    ) -> BrowserRuntimeConfig:
        binary_value = str(env.get(BROWSER_BINARY_PATH_ENV_VAR, "")).strip()
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

        profile_dir = runtime_paths.configured_profile_dir(env, provider=provider)
        user_data_dir = runtime_paths.configured_user_data_dir(env)
        if profile_dir is None and user_data_dir is None:
            user_data_dir = runtime_paths.default_provider_user_data_dir(
                env, provider=provider
            )
        component_cache_raw = str(
            env.get("PAPER_FETCH_BROWSER_COMPONENT_CACHE", "")
        ).strip()
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
                str(env.get(BROWSER_HEADLESS_ENV_VAR, "")).strip()
            ),
            user_agent=None,
            timeout_ms=parse_positive_int_env(
                env,
                BROWSER_TIMEOUT_MS_ENV_VAR,
                default=DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS,
            ),
            binary_path=binary_path,
            profile_dir=profile_dir,
            user_data_dir=user_data_dir,
            backend=self.name,
            component_cache_dir=(
                Path(component_cache_raw).expanduser() if component_cache_raw else None
            ),
        )

    def ensure_runtime_ready(self, config: BrowserRuntimeConfig) -> None:
        del config
        details = self.dependency_details()
        if not _package_ready(details):
            suffix = "; ".join(details.get("compatibility_errors", []))
            message = f"Byparr requires compatible {self.engine_label()} and Playwright packages."
            if suffix:
                message = f"{message} {suffix}"
            raise ProviderFailure(NOT_CONFIGURED, message)

    def prepare(
        self, config: BrowserRuntimeConfig, *, runtime_context: Any = None
    ) -> Path:
        byparr_engine.prepare_executable(config.binary_path)
        env = runtime_context.env if runtime_context is not None else os.environ
        return prepare_components(
            config.component_cache_dir or resolve_user_data_dir(env) / "byparr",
            PreparationBudget(config.timeout_ms / 1000, runtime_context),
        )

    def create_manager(
        self, config: BrowserRuntimeConfig, *, runtime_context: Any = None
    ) -> PublisherProfileManager:
        return PublisherProfileManager(
            replace(config, backend=self.name),
            runtime_context=runtime_context,
        )

    def probe_runtime_status(
        self,
        env: Mapping[str, str],
        *,
        provider: str,
        doi: str = BROWSER_STATUS_PROBE_ID,
        deep: bool = False,
    ) -> ProviderStatusResult:
        checks = []
        engine = self.engine_label()
        active_engine = byparr_engine.engine_name()
        config: BrowserRuntimeConfig | None = None
        details = self.dependency_details()
        package_ready = _package_ready(details)
        runtime_installed = _runtime_installed(details)
        available = False
        bundle_damaged = False
        try:
            config = self.load_runtime_config(env, provider=provider, doi=doi)
            available = package_ready and bool(config.binary_path or runtime_installed)
            root, _, identity = runtime_location(
                config.component_cache_dir or resolve_user_data_dir(env) / "byparr"
            )
            component_installed = valid_cache(root, identity)
            bundle_damaged = (
                bundled_component_root() is not None and not component_installed
            )
            env_status = (
                NOT_CONFIGURED
                if bundle_damaged
                else (OK if available else NOT_CONFIGURED)
            )
            env_message = (
                "Bundled Byparr is missing or damaged; reinstall the offline package."
                if bundle_damaged
                else (
                    f"{provider} {engine} runtime environment is configured."
                    if available
                    else f"{provider} requires compatible {engine} and playwright packages."
                )
            )
            checks.append(
                build_provider_status_check(
                    "runtime_env",
                    env_status,
                    env_message,
                    details={
                        "backend": self.name,
                        "engine": active_engine,
                        "headless": config.headless,
                        "timeout_ms": config.timeout_ms,
                        "binary_path_configured": bool(config.binary_path),
                        "profile_dir_configured": bool(config.profile_dir),
                        "user_data_dir_configured": bool(config.user_data_dir),
                        "profile_dir": str(
                            (config.profile_dir or config.user_data_dir) or ""
                        ),
                        "browser_user_agent_ignored": bool(
                            normalize_text(env.get(BROWSER_USER_AGENT_ENV_VAR))
                        ),
                        "package_ready": package_ready,
                        "runtime_installed": runtime_installed,
                        "component_installed": component_installed,
                        "download_required": (
                            package_ready
                            and not bool(config.binary_path or runtime_installed)
                        )
                        or not component_installed,
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
                    f"{engine} and Playwright Python packages are compatible; no browser is launched."
                    if package_ready
                    else f"{engine} or Playwright Python package is missing or incompatible."
                ),
                details=details,
            )
        )
        checks.append(
            build_provider_status_check(
                "browser_runtime",
                OK if available else NOT_CONFIGURED,
                (
                    f"{engine} browser runtime is installed or an explicit executable is configured."
                    if available
                    else (
                        f"{engine} Python packages are installed, but the browser runtime "
                        "will be prepared automatically when a browser session is first needed."
                        if package_ready
                        else f"{engine} browser runtime cannot be used until its Python packages are installed."
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
                    "prepare_command": (
                        'python -c "from paper_fetch.providers.browser_runtime.byparr_engine import prepare_executable; prepare_executable()"'
                        if engine == "Invisible"
                        else (
                            'python -c "from paper_fetch.providers.browser_runtime.preparation '
                            "import prepare_camoufox_managed_runtime; "
                            "from camoufox.fpgen_model import ensure_fpgen_model; "
                            'prepare_camoufox_managed_runtime(); ensure_fpgen_model()"'
                        )
                    ),
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
                    f"Native {engine} browser context can be created.",
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
                    if value is not None:
                        with contextlib.suppress(Exception):
                            value.close()
            checks.append(deep_check)

        if bundle_damaged:
            status = NOT_CONFIGURED
        elif any(check.status == ERROR for check in checks):
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
        config = replace(config, backend=self.name)
        result = html_fetcher.fetch_browser_html(
            candidate_urls,
            publisher=publisher,
            config=config,
            **kwargs,
        )
        runtime_context = kwargs.get("runtime_context")
        store = getattr(runtime_context, "artifact_store", None)
        if (
            runtime_context is not None
            and store is not None
            and store.allows_auxiliary_artifacts
        ):
            path = (
                store.download_dir
                / "diagnostics"
                / config.provider
                / sanitize_filename(config.doi)
                / "byparr.json"
            )
            store.write_json_file(
                path,
                redact_log_value(
                    {
                        "provider": config.provider,
                        "doi": config.doi,
                        "browser_backend": self.name,
                        "response_status": result.response_status,
                        "final_url": result.final_url,
                        "diagnostics": result.diagnostics,
                    }
                ),
                overwrite=True,
            )
            runtime_context.diagnostic_artifacts.append(
                {"path": str(path), "kind": "diagnostic", "route": "browser_html"}
            )
        return result

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
        return html_fetcher.warm_browser_html_context(
            candidate_urls,
            publisher=publisher,
            config=replace(config, backend=self.name),
            browser_context_seed=browser_context_seed,
            runtime_context=runtime_context,
            lightweight=lightweight,
        )


DEFAULT_BYPARR_BACKEND = ByparrBackend()
