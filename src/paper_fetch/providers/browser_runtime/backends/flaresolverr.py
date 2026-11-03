"""Publisher FlareSolverr + system Chrome backend."""

from __future__ import annotations

from dataclasses import replace
from importlib.util import find_spec

from .camoufox import CamoufoxBackend
from ..chrome import CHROME_ENV, discover_chrome
from .. import paths
from ..flaresolverr_preparation import runtime_location, valid_cache
from ...base import ProviderFailure, ProviderStatusResult, build_provider_status_check
from ....config import (
    resolve_user_data_dir,
    BROWSER_BINARY_PATH_ENV_VAR,
    BROWSER_PROFILE_DIR_ENV_VAR,
    BROWSER_USER_DATA_DIR_ENV_VAR,
)
from ....reason_codes import NOT_CONFIGURED, OK, READY


class FlareSolverrBackend(CamoufoxBackend):
    name = "flaresolverr"

    def load_runtime_config(self, env, *, provider, doi, require_storage_state=False):
        # Camoufox executable/profile settings retain their Firefox-only meaning.
        isolated = {
            key: value
            for key, value in env.items()
            if key
            not in {
                BROWSER_BINARY_PATH_ENV_VAR,
                BROWSER_PROFILE_DIR_ENV_VAR,
                BROWSER_USER_DATA_DIR_ENV_VAR,
            }
        }
        config = super().load_runtime_config(
            isolated,
            provider=provider,
            doi=doi,
            require_storage_state=require_storage_state,
        )
        return replace(
            config,
            backend=self.name,
            binary_path=None,
            chrome_binary_path=env.get(CHROME_ENV, "").strip() or None,
            profile_dir=None,
            user_data_dir=paths.default_provider_user_data_dir(
                env, provider=provider, backend=self.name
            ),
        )

    def ensure_runtime_ready(self, config):
        if find_spec("playwright") is None:
            raise ProviderFailure(
                NOT_CONFIGURED, f"{config.provider} FlareSolverr requires Playwright."
            )
        # This is a use-time prerequisite check; it never downloads a runtime.
        try:
            discover_chrome(
                {CHROME_ENV: config.chrome_binary_path}
                if config.chrome_binary_path
                else None
            )
        except ValueError as exc:
            raise ProviderFailure(NOT_CONFIGURED, str(exc)) from exc

    def probe_runtime_status(
        self, env, *, provider, doi="probe://browser/status", deep=False
    ):
        checks = []
        try:
            config = self.load_runtime_config(env, provider=provider, doi=doi)
            chrome = discover_chrome(env)
            root, _, identity = runtime_location(
                resolve_user_data_dir(env) / "flaresolverr"
            )
            installed = valid_cache(root, identity)
            available = find_spec("playwright") is not None
            checks.append(
                build_provider_status_check(
                    "runtime_env",
                    OK if available else NOT_CONFIGURED,
                    "System Chrome configured; verified FlareSolverr cache is reused or prepared on demand.",
                    details={
                        "backend": self.name,
                        "headless": config.headless,
                        "chrome_path": chrome.path,
                        "chrome_version": chrome.version,
                        "runtime_installed": installed,
                        "download_required": not installed,
                        "storage_state_path": str(paths.storage_state_path(config)),
                    },
                )
            )
            checks.append(
                build_provider_status_check(
                    "playwright_dependency",
                    OK if available else NOT_CONFIGURED,
                    "Playwright dependency probe; no browser launched.",
                    details={"packages": {"playwright": available}},
                )
            )
            if deep:
                from ..context import open_browser_context

                manager, _ = open_browser_context(config)
                if manager is not None:
                    manager.close()
        except (ProviderFailure, ValueError) as exc:
            checks.append(
                build_provider_status_check(
                    "runtime_env",
                    NOT_CONFIGURED,
                    str(exc),
                    details={"backend": self.name},
                )
            )
        ready = all(check.status == OK for check in checks)
        return ProviderStatusResult(
            provider=provider,
            status=READY if ready else NOT_CONFIGURED,
            available=ready,
            official_provider=True,
            missing_env=[],
            notes=[],
            checks=checks,
        )


DEFAULT_FLARESOLVERR_BACKEND = FlareSolverrBackend()
