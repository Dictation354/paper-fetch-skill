from __future__ import annotations

import importlib.util
import os
import tempfile
from pathlib import Path
from collections.abc import Mapping

from paper_fetch.browser_preflight import (
    BrowserPreflightResult,
    preflight_browser_provider,
    static_browser_capabilities,
)
from paper_fetch.config import (
    AMS_STORAGE_STATE_JSON_ENV_VAR,
    BROWSER_BINARY_PATH_ENV_VAR,
    BROWSER_PROFILE_DIR_ENV_VAR,
    BROWSER_USER_DATA_DIR_ENV_VAR,
    WILEY_PROFILE_DIR_ENV_VAR,
    WILEY_STORAGE_STATE_JSON_ENV_VAR,
    build_runtime_env,
    configured_browser_backend,
)
from paper_fetch.formula.paths import FORMULA_TOOLS_DIR_ENV_VAR
from tests._environment import (
    PRESERVED_CAMOUFOX_CACHE_HOME_ENV_VAR,
    PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR,
    PRESERVED_FORMULA_TOOLS_DIR_ENV_VAR,
)


def build_isolated_live_env(
    base_env: Mapping[str, str] | None = None,
) -> tuple[dict[str, str], tempfile.TemporaryDirectory]:
    tempdir = tempfile.TemporaryDirectory(prefix="paper-fetch-live-xdg-")
    env = build_runtime_env(base_env)
    isolated_root = Path(tempdir.name)
    env["XDG_DATA_HOME"] = str(isolated_root / "data")
    env["XDG_CACHE_HOME"] = str(isolated_root / "cache")
    env["XDG_RUNTIME_DIR"] = str(isolated_root / "runtime")
    for name in (
        BROWSER_PROFILE_DIR_ENV_VAR,
        BROWSER_USER_DATA_DIR_ENV_VAR,
        AMS_STORAGE_STATE_JSON_ENV_VAR,
        WILEY_PROFILE_DIR_ENV_VAR,
        WILEY_STORAGE_STATE_JSON_ENV_VAR,
    ):
        env.pop(name, None)
    preserved_executable = os.environ.get(
        PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR, ""
    ).strip()
    if preserved_executable and not env.get(BROWSER_BINARY_PATH_ENV_VAR, "").strip():
        env[BROWSER_BINARY_PATH_ENV_VAR] = preserved_executable
    preserved_camoufox_cache_home = os.environ.get(
        PRESERVED_CAMOUFOX_CACHE_HOME_ENV_VAR, ""
    ).strip()
    if preserved_executable and preserved_camoufox_cache_home:
        # Camoufox keeps immutable browser bundles, font resources, and default
        # addons under its package cache. Reuse that prepared dependency cache;
        # publisher profiles and storage state remain isolated under XDG data.
        env["XDG_CACHE_HOME"] = preserved_camoufox_cache_home
    preserved_formula_tools = os.environ.get(
        PRESERVED_FORMULA_TOOLS_DIR_ENV_VAR, ""
    ).strip()
    if preserved_formula_tools:
        env[FORMULA_TOOLS_DIR_ENV_VAR] = preserved_formula_tools
        # The global pytest safety policy deliberately shadows converter
        # executables so ordinary unit tests cannot launch them. A live run
        # with prepared tools must discover binaries from that directory.
        env.pop("TEXMATH_BIN", None)
        env.pop("MATHML_TO_LATEX_NODE_BIN", None)
    for name in ("XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR"):
        Path(env[name]).mkdir(parents=True, exist_ok=True)
    return env, tempdir


def require_selected_browser_or_skip(testcase, env: Mapping[str, str]) -> None:
    if importlib.util.find_spec("playwright.sync_api") is None:
        testcase.skipTest("Playwright Python package is not installed.")
    backend = configured_browser_backend(env)
    if importlib.util.find_spec(backend) is None:
        testcase.skipTest(f"Selected browser package {backend!r} is not installed.")


def preflight_selected_browser_or_skip(
    testcase,
    *,
    provider: str,
    env: Mapping[str, str],
    cache: dict[str, BrowserPreflightResult],
    artifact_root: Path | None = None,
) -> BrowserPreflightResult:
    """Run one provider preflight per shared live profile before its first fetch."""

    require_selected_browser_or_skip(testcase, env)
    static = static_browser_capabilities(env, provider=provider)
    runtime_capability = static.get("browser_runtime")
    if not isinstance(runtime_capability, Mapping):
        testcase.fail(
            f"{provider} static browser capability report is missing "
            "the browser_runtime object."
        )
        raise AssertionError("testcase.fail() unexpectedly returned")
    if not bool(runtime_capability.get("available")):
        reason = (
            runtime_capability.get("reason_code")
            or runtime_capability.get("status")
            or "not_configured"
        )
        notes = runtime_capability.get("notes")
        note_message = (
            "; ".join(str(note) for note in notes) if isinstance(notes, list) else ""
        )
        testcase.skipTest(
            f"{provider} browser runtime is unavailable ({reason}): "
            f"{runtime_capability.get('message') or note_message or 'missing local dependency'}"
        )
    result = cache.get(provider)
    if result is None:
        result = preflight_browser_provider(
            provider,
            env=env,
            # AIP's anti-bot cookies are tied to Camoufox's per-process
            # fingerprint. Persisting a successful probe into the acceptance
            # profile can turn the immediately following fresh launch into an
            # empty shell; its cold-start test covers the no-state path.
            save_storage_state=provider != "aip",
            download_dir=(
                artifact_root / provider if artifact_root is not None else None
            ),
            artifact_mode="all" if artifact_root is not None else "none",
        )
        cache[provider] = result
    if result.status in {"challenge", "auth_required"}:
        testcase.skipTest(
            f"{provider} preflight requires legal access setup "
            f"({result.reason_code}); next action: paper-fetch auth {provider}"
        )
    if result.status != "ready":
        diagnostic_path = str((result.diagnostics or {}).get("diagnostic_path") or "")
        if artifact_root is not None and result.status != "cancelled":
            if not diagnostic_path or not Path(diagnostic_path).is_file():
                testcase.fail(
                    f"{provider} preflight {result.status} did not preserve a readable "
                    f"diagnostic artifact (code={result.reason_code}, stage={result.stage})."
                )
        testcase.fail(
            f"{provider} preflight failed "
            f"({result.reason_code}, stage={result.stage}, diagnostic={diagnostic_path}): "
            f"{result.message}"
        )
    return result
