"""Publisher Byparr backend using the shared managed Camoufox runtime."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .camoufox import CamoufoxBackend
from . import camoufox
from .. import paths
from ..byparr_preparation import bundled_component_root, runtime_location, valid_cache
from ...base import ProviderFailure
from ....config import (
    BROWSER_PROFILE_DIR_ENV_VAR,
    BROWSER_USER_DATA_DIR_ENV_VAR,
    resolve_user_data_dir,
)
from ....reason_codes import NOT_CONFIGURED


def _dependency_details():
    return camoufox._dependency_details()


class ByparrBackend(CamoufoxBackend):
    name = "byparr"

    def prepare(self, config, *, runtime_context=None):
        import os
        from ..byparr_preparation import PreparationBudget, prepare_components

        from ..camoufox_manager import _launch_executable_path

        _launch_executable_path(config.binary_path)
        env = runtime_context.env if runtime_context is not None else os.environ
        return prepare_components(
            config.component_cache_dir or resolve_user_data_dir(env) / "byparr",
            PreparationBudget(config.timeout_ms / 1000, runtime_context),
        )

    def fetch_html(self, candidate_urls, *, publisher, config, **kwargs):
        config = replace(config, backend=self.name)
        result = super().fetch_html(
            candidate_urls, publisher=publisher, config=config, **kwargs
        )
        runtime_context = kwargs.get("runtime_context")
        store = getattr(runtime_context, "artifact_store", None)
        if store is not None and store.allows_auxiliary_artifacts:
            from ....logging_utils import redact_log_value
            from ....utils import sanitize_filename

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

    def create_manager(self, config, *, runtime_context=None):
        config = replace(config, backend=self.name)
        if config.state_mode == "native":
            from ..profile import PublisherProfileManager

            return PublisherProfileManager(config, runtime_context=runtime_context)
        from ..byparr_manager import ByparrManager

        return ByparrManager(config, runtime_context=runtime_context)

    def load_runtime_config(self, env, *, provider, doi, require_storage_state=False):
        from ..selection import selected_state_mode

        state_mode = selected_state_mode(env, provider=provider)
        isolated = {
            k: v
            for k, v in env.items()
            if state_mode == "native"
            or k
            not in {
                BROWSER_PROFILE_DIR_ENV_VAR,
                BROWSER_USER_DATA_DIR_ENV_VAR,
            }
        }
        # The shared config loader still resolves the legacy native directory.
        from .camoufox import DEFAULT_CAMOUFOX_BACKEND

        config = DEFAULT_CAMOUFOX_BACKEND.load_runtime_config(
            isolated,
            provider=provider,
            doi=doi,
            require_storage_state=require_storage_state,
        )
        return replace(
            config,
            backend=self.name,
            state_mode=state_mode,
            component_cache_dir=Path(
                env["PAPER_FETCH_BROWSER_COMPONENT_CACHE"]
            ).expanduser()
            if env.get("PAPER_FETCH_BROWSER_COMPONENT_CACHE")
            else None,
            profile_dir=config.profile_dir if state_mode == "native" else None,
            user_data_dir=config.user_data_dir
            if state_mode == "native"
            else paths.default_provider_user_data_dir(
                env, provider=provider, backend=self.name
            ),
        )

    def ensure_runtime_ready(self, config):
        details = _dependency_details()
        if not all(details["packages"].values()):
            raise ProviderFailure(
                NOT_CONFIGURED,
                "Byparr requires compatible camoufox and playwright packages.",
            )
        from importlib.metadata import version

        major, minor = (int(p) for p in version("playwright").split(".")[:2])
        if (major, minor) < (1, 58) or (major, minor) >= (1, 64):
            raise ProviderFailure(
                NOT_CONFIGURED,
                "Byparr requires Playwright >=1.58,<1.64 for shared browser connections.",
            )

    def probe_runtime_status(
        self, env, *, provider, doi="probe://browser/status", deep=False
    ):
        # Retain the existing package/browser checks and status schema. The
        # component cache is prepared on demand, except in a damaged offline bundle.
        result = super().probe_runtime_status(
            env, provider=provider, doi=doi, deep=deep
        )
        try:
            config = self.load_runtime_config(env, provider=provider, doi=doi)
        except ProviderFailure:
            return result
        root, _, identity = runtime_location(
            config.component_cache_dir or resolve_user_data_dir(env) / "byparr"
        )
        installed = valid_cache(root, identity)
        for check in result.checks:
            if check.name == "runtime_env":
                check.details.update(
                    backend=self.name,
                    engine="camoufox",
                    state_mode=config.state_mode,
                    component_installed=installed,
                    download_required=bool(check.details.get("download_required"))
                    or not installed,
                )
                if bundled_component_root() is not None and not installed:
                    return replace(
                        result,
                        status=NOT_CONFIGURED,
                        available=False,
                        checks=[
                            replace(
                                item,
                                status=NOT_CONFIGURED,
                                message="Bundled Byparr is missing or damaged; reinstall the offline package.",
                            )
                            if item is check
                            else item
                            for item in result.checks
                        ],
                    )
        return result


DEFAULT_BYPARR_BACKEND = ByparrBackend()
