from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest import mock

import pytest

from paper_fetch.browser_preflight import BrowserPreflightResult
from paper_fetch.config import BROWSER_BINARY_PATH_ENV_VAR
from paper_fetch.config import (
    AMS_STORAGE_STATE_JSON_ENV_VAR,
    BROWSER_PROFILE_DIR_ENV_VAR,
    BROWSER_USER_DATA_DIR_ENV_VAR,
    WILEY_PROFILE_DIR_ENV_VAR,
    WILEY_STORAGE_STATE_JSON_ENV_VAR,
)
from paper_fetch.providers.browser_runtime import (
    load_runtime_config,
    storage_state_path,
)
from paper_fetch.formula.paths import FORMULA_TOOLS_DIR_ENV_VAR
from tests._environment import (
    PRESERVED_CAMOUFOX_CACHE_HOME_ENV_VAR,
    PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR,
    PRESERVED_FORMULA_TOOLS_DIR_ENV_VAR,
)
from tests.live import _runtime_env
from tests.live.test_live_publishers import _catalog_acceptance_report


def _ready_preflight(provider: str = "wiley") -> BrowserPreflightResult:
    return BrowserPreflightResult(
        provider=provider,
        provider_label="Wiley",
        status="ready",
        reason_code="browser_preflight_ready",
    )


def test_isolated_live_env_reuses_prepared_camoufox_executable(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "camoufox"
    executable.touch()

    with mock.patch.dict(
        os.environ,
        {
            PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR: str(executable),
            PRESERVED_CAMOUFOX_CACHE_HOME_ENV_VAR: "",
        },
    ):
        env, tempdir = _runtime_env.build_isolated_live_env({})
        try:
            assert env[BROWSER_BINARY_PATH_ENV_VAR] == str(executable)
            for name in ("XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR"):
                assert Path(env[name]).is_relative_to(tempdir.name)
        finally:
            tempdir.cleanup()


def test_isolated_live_env_derives_unique_provider_storage_paths() -> None:
    overridden = {
        BROWSER_PROFILE_DIR_ENV_VAR: "/real/shared-profile",
        BROWSER_USER_DATA_DIR_ENV_VAR: "/real/shared-user-data",
        AMS_STORAGE_STATE_JSON_ENV_VAR: "/real/ams.json",
        WILEY_PROFILE_DIR_ENV_VAR: "/real/wiley-profile",
        WILEY_STORAGE_STATE_JSON_ENV_VAR: "/real/wiley.json",
    }
    env, tempdir = _runtime_env.build_isolated_live_env(overridden)
    try:
        for name in overridden:
            assert name not in env
        paths = {
            provider: storage_state_path(
                load_runtime_config(env, provider=provider, doi="10.1000/example")
            )
            for provider in ("science", "wiley", "ams")
        }
        assert len(set(paths.values())) == len(paths)
        for provider, path in paths.items():
            assert path is not None
            assert path.is_relative_to(tempdir.name)
            assert f"{provider}-camoufox" in path.parts
    finally:
        tempdir.cleanup()


def test_isolated_live_env_reuses_only_prepared_camoufox_dependency_cache(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "camoufox-cache" / "camoufox"
    executable.parent.mkdir()
    executable.touch()
    cache_home = tmp_path / "prepared-cache"
    cache_home.mkdir()

    with mock.patch.dict(
        os.environ,
        {
            PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR: str(executable),
            PRESERVED_CAMOUFOX_CACHE_HOME_ENV_VAR: str(cache_home),
        },
    ):
        env, tempdir = _runtime_env.build_isolated_live_env({})
        try:
            assert env["XDG_CACHE_HOME"] == str(cache_home)
            assert Path(env["XDG_DATA_HOME"]).is_relative_to(tempdir.name)
            assert Path(env["XDG_RUNTIME_DIR"]).is_relative_to(tempdir.name)
        finally:
            tempdir.cleanup()


def test_catalog_acceptance_report_does_not_hide_unrecorded_provider() -> None:
    report = _catalog_acceptance_report(
        [
            {
                "provider": "elsevier",
                "acceptance": {"overall": "complete"},
            }
        ]
    )

    assert report["schema_version"] == 2
    assert report["summary"] == {
        "catalog_provider_count": 19,
        "recorded_provider_count": 1,
        "unrecorded_provider_count": 18,
        "unrecorded_providers": [
            provider
            for provider in (
                "springer",
                "wiley",
                "science",
                "pnas",
                "ieee",
                "arxiv",
                "copernicus",
                "ams",
                "mdpi",
                "royalsocietypublishing",
                "annualreviews",
                "plos",
                "oxfordacademic",
                "acs",
                "iop",
                "aip",
                "frontiers",
                "tandf",
            )
        ],
        "overall": {"complete": 1},
        "all_recorded_complete": True,
        "all_catalog_providers_complete": False,
    }


def test_live_mcp_no_access_detection_requires_machine_readable_boundary() -> None:
    assert _runtime_env.is_machine_readable_no_access({"status": "no_access"})
    assert _runtime_env.is_machine_readable_no_access(
        {
            "status": "ok",
            "source_trail": ["route:provider_candidate_springer_access_boundary_stop"],
        }
    )
    assert not _runtime_env.is_machine_readable_no_access(
        {
            "status": "ok",
            "acceptance": {"content": "metadata_only"},
            "source_trail": ["fulltext:springer_fail_html"],
        }
    )


def test_isolated_live_env_reuses_explicit_formula_tools(tmp_path: Path) -> None:
    tools_dir = tmp_path / "formula-tools"
    tools_dir.mkdir()
    with mock.patch.dict(
        os.environ,
        {PRESERVED_FORMULA_TOOLS_DIR_ENV_VAR: str(tools_dir)},
    ):
        env, tempdir = _runtime_env.build_isolated_live_env(
            {
                "TEXMATH_BIN": "/isolated/unavailable-texmath",
                "MATHML_TO_LATEX_NODE_BIN": "/isolated/unavailable-node",
            }
        )
        try:
            assert env[FORMULA_TOOLS_DIR_ENV_VAR] == str(tools_dir)
            assert "TEXMATH_BIN" not in env
            assert "MATHML_TO_LATEX_NODE_BIN" not in env
        finally:
            tempdir.cleanup()


def test_live_preflight_uses_nested_browser_runtime_availability() -> None:
    cache: dict[str, BrowserPreflightResult] = {}
    result = _ready_preflight()

    with (
        mock.patch.object(_runtime_env, "require_selected_browser_or_skip"),
        mock.patch.object(
            _runtime_env,
            "static_browser_capabilities",
            return_value={
                "browser_runtime": {
                    "available": True,
                    "status": "ready",
                }
            },
        ),
        mock.patch.object(
            _runtime_env,
            "preflight_browser_provider",
            return_value=result,
        ) as preflight,
    ):
        actual = _runtime_env.preflight_selected_browser_or_skip(
            unittest.TestCase(),
            provider="wiley",
            env={},
            cache=cache,
        )

    assert actual is result
    assert cache == {"wiley": result}
    preflight.assert_called_once_with(
        "wiley",
        env={},
        save_storage_state=True,
        download_dir=None,
        artifact_mode="none",
    )


def test_live_aip_preflight_does_not_persist_fingerprint_bound_state() -> None:
    cache: dict[str, BrowserPreflightResult] = {}
    result = _ready_preflight("aip")

    with (
        mock.patch.object(_runtime_env, "require_selected_browser_or_skip"),
        mock.patch.object(
            _runtime_env,
            "static_browser_capabilities",
            return_value={"browser_runtime": {"available": True, "status": "ready"}},
        ),
        mock.patch.object(
            _runtime_env,
            "preflight_browser_provider",
            return_value=result,
        ) as preflight,
    ):
        actual = _runtime_env.preflight_selected_browser_or_skip(
            unittest.TestCase(),
            provider="aip",
            env={},
            cache=cache,
        )

    assert actual is result
    preflight.assert_called_once_with(
        "aip",
        env={},
        save_storage_state=False,
        download_dir=None,
        artifact_mode="none",
    )


def test_live_preflight_skips_nested_unavailable_browser_runtime() -> None:
    with (
        mock.patch.object(_runtime_env, "require_selected_browser_or_skip"),
        mock.patch.object(
            _runtime_env,
            "static_browser_capabilities",
            return_value={
                "browser_runtime": {
                    "available": False,
                    "status": "not_configured",
                    "notes": ["Camoufox runtime is unavailable."],
                }
            },
        ),
        mock.patch.object(_runtime_env, "preflight_browser_provider") as preflight,
        pytest.raises(unittest.SkipTest, match="Camoufox runtime is unavailable"),
    ):
        _runtime_env.preflight_selected_browser_or_skip(
            unittest.TestCase(),
            provider="wiley",
            env={},
            cache={},
        )

    preflight.assert_not_called()


def test_live_preflight_rejects_malformed_static_capability_report() -> None:
    with (
        mock.patch.object(_runtime_env, "require_selected_browser_or_skip"),
        mock.patch.object(
            _runtime_env,
            "static_browser_capabilities",
            return_value={"available": True},
        ),
        pytest.raises(AssertionError, match="missing the browser_runtime object"),
    ):
        _runtime_env.preflight_selected_browser_or_skip(
            unittest.TestCase(),
            provider="wiley",
            env={},
            cache={},
        )
