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
from tests.support.live_acceptance import catalog_acceptance_report
from tests.provider_benchmark_samples import iter_provider_benchmark_samples


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
    catalog_providers = [
        sample.provider for sample in iter_provider_benchmark_samples()
    ]
    report = catalog_acceptance_report(
        [
            {
                "provider": "elsevier",
                "acceptance": {"overall": "complete"},
                "terminal": {"status": "complete"},
            }
        ]
    )

    assert report["schema_version"] == 2
    assert report["summary"] == {
        "catalog_provider_count": len(catalog_providers),
        "recorded_provider_count": 1,
        "unrecorded_provider_count": len(catalog_providers) - 1,
        "unrecorded_providers": [
            provider for provider in catalog_providers if provider != "elsevier"
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
        mock.patch.object(_runtime_env, "require_camoufox_or_skip"),
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
        mock.patch.object(_runtime_env, "require_camoufox_or_skip"),
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
        mock.patch.object(_runtime_env, "require_camoufox_or_skip"),
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
        mock.patch.object(_runtime_env, "require_camoufox_or_skip"),
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


@pytest.mark.parametrize("skip", [False, True])
def test_live_report_keeps_actual_data_after_assertion_or_skip(tmp_path, skip):
    import json
    import time
    from tests.support.live_acceptance import preserve_terminal_record

    record = {
        "provider": "science",
        "source": "science_html",
        "source_trail": ["fulltext:science_html_ok"],
        "acceptance": {"overall": "degraded"},
        "asset_paths": ["figure.png"],
        "performance": {"fetch_wall_seconds": 1.25},
        "terminal": {"status": "failed", "reason_code": "validation_pending"},
    }
    with pytest.raises(pytest.skip.Exception if skip else AssertionError):
        with preserve_terminal_record(
            record, [record], tmp_path, time.monotonic() - 2, lambda *args: None
        ):
            if skip:
                pytest.skip("legal challenge")
            assert record["acceptance"]["overall"] == "complete"
    saved = json.loads((tmp_path / "live-acceptance.json").read_text())["providers"][0]
    assert saved["terminal"]["status"] == ("skipped" if skip else "failed")
    assert saved["acceptance"] == {"overall": "degraded"}
    assert saved["source"] == "science_html"
    assert saved["asset_paths"] == ["figure.png"]
    assert saved["performance"]["fetch_wall_seconds"] == 1.25
    assert saved["performance"]["total_seconds"] >= 2


def test_catalog_summary_requires_assertions_to_pass():
    report = catalog_acceptance_report(
        [
            {
                "provider": "science",
                "acceptance": {"overall": "complete"},
                "terminal": {"status": "failed", "reason_code": "assertion_failed"},
            }
        ]
    )
    assert report["summary"]["all_recorded_complete"] is False
    assert report["providers"][0]["acceptance"]["overall"] == "complete"


def test_live_report_redaction_keeps_json_quoting_valid(tmp_path):
    import json
    import time
    from tests.support.live_acceptance import preserve_terminal_record

    record = {
        "provider": "science",
        "acceptance": {"overall": "complete"},
        "terminal": {"status": "complete"},
        "reference": 'Quoted "https://example.test/source?api_key=private-test-token" study',
    }
    with preserve_terminal_record(
        record, [record], tmp_path, time.monotonic(), lambda *args: None
    ):
        pass
    saved = json.loads((tmp_path / "live-acceptance.json").read_text())
    assert "private-test-token" not in json.dumps(saved)
    assert "Quoted" in saved["providers"][0]["reference"]
