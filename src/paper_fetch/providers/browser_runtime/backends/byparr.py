"""Publisher Byparr backend using the selected platform engine."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .camoufox import CamoufoxBackend
from . import camoufox
from ..byparr_preparation import bundled_component_root, runtime_location, valid_cache
from ...base import ProviderFailure
from ....config import (
    resolve_user_data_dir,
)
from ....reason_codes import NOT_CONFIGURED


def _dependency_details():
    from importlib import metadata, util
    from ..byparr_engine import engine_name

    if engine_name() != "invisible":
        details = camoufox._dependency_details()
    else:
        packages = {
            name: util.find_spec(name) is not None
            for name in ("playwright", "invisible_playwright", "invisible_core")
        }
        details = {
            "packages": packages,
            "runtime_installed": False,
            "runtime_valid": False,
            "runtime_path": None,
        }
    packages = details["packages"]
    errors = []
    for package, present in packages.items():
        if not present:
            errors.append(f"{package} Python package is not installed")
            continue
        try:
            value = metadata.version(package)
            details[f"{package}_version"] = value
            if package == "playwright":
                pair = tuple(int(p) for p in value.split(".")[:2])
                upper = (2, 0) if engine_name() == "invisible" else (1, 63)
                if not (1, 58) <= pair < upper:
                    required = (
                        ">=1.58,<2" if engine_name() == "invisible" else ">=1.58,<1.63"
                    )
                    errors.append(f"Playwright {required} required; found {value}")
            elif package in {"invisible_playwright", "invisible_core", "camoufox"}:
                expected = {
                    "invisible_playwright": "0.49.1",
                    "invisible_core": "61.62.0",
                    "camoufox": "0.5.9",
                }[package]
                if value != expected:
                    errors.append(f"{package} requires {expected}; found {value}")
        except (metadata.PackageNotFoundError, ValueError):
            errors.append(f"Cannot determine compatible {package} version")
    ready = all(packages.values()) and not errors
    details.update(
        package_ready=ready,
        compatibility_errors=errors,
        engine=engine_name(),
        download_required=ready and not details.get("runtime_valid", False),
    )
    if engine_name() == "invisible" and ready:
        try:
            from invisible_core.download import engine_status, cache_dir_for_seal
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


class ByparrBackend(CamoufoxBackend):
    name = "byparr"

    def prepare(self, config, *, runtime_context=None):
        import os
        from ..byparr_preparation import PreparationBudget, prepare_components

        from ..byparr_engine import prepare_executable

        prepare_executable(config.binary_path)
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
        if (
            runtime_context is not None
            and store is not None
            and store.allows_auxiliary_artifacts
        ):
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
        from ..profile import PublisherProfileManager

        return PublisherProfileManager(config, runtime_context=runtime_context)

    def load_runtime_config(self, env, *, provider, doi):
        config = super().load_runtime_config(env, provider=provider, doi=doi)
        return replace(
            config,
            backend=self.name,
            component_cache_dir=Path(
                env["PAPER_FETCH_BROWSER_COMPONENT_CACHE"]
            ).expanduser()
            if env.get("PAPER_FETCH_BROWSER_COMPONENT_CACHE")
            else None,
        )

    def dependency_details(self):
        return _dependency_details()

    def engine_label(self):
        from ..byparr_engine import engine_name

        return "Invisible" if engine_name() == "invisible" else "Camoufox"

    def ensure_runtime_ready(self, config):
        details = self.dependency_details()
        if not details.get("package_ready", all(details["packages"].values())):
            raise ProviderFailure(
                NOT_CONFIGURED,
                f"Byparr requires compatible {self.engine_label()} and Playwright packages. "
                + "; ".join(details.get("compatibility_errors", [])),
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
        from ..byparr_engine import engine_name

        root, _, identity = runtime_location(
            config.component_cache_dir or resolve_user_data_dir(env) / "byparr"
        )
        installed = valid_cache(root, identity)
        for check in result.checks:
            if check.name == "runtime_env":
                check.details.update(
                    backend=self.name,
                    engine=engine_name(),
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
