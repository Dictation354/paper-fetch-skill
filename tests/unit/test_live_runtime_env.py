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
from tests.provider_benchmark_samples import (
    iter_provider_benchmark_samples,
    provider_benchmark_sample,
)


def _ready_preflight(provider: str = "wiley") -> BrowserPreflightResult:
    return BrowserPreflightResult(
        provider=provider,
        provider_label="Wiley",
        status="ready",
        reason_code="browser_preflight_ready",
    )


def test_isolated_live_env_reuses_prepared_camoufox_executable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.byparr_engine.engine_name",
        lambda: "camoufox",
    )
    executable = tmp_path / "byparr"
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
    executable = tmp_path / "camoufox-cache" / "byparr"
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
    assert cache == {("wiley", "byparr"): result}
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


def test_live_local_browser_check_never_visits_publisher(monkeypatch):
    monkeypatch.setattr(_runtime_env, "require_browser_or_skip", lambda *a, **kw: None)
    monkeypatch.setattr(
        _runtime_env,
        "static_browser_capabilities",
        lambda *a, **kw: {"browser_runtime": {"available": True}},
    )
    monkeypatch.setattr(
        _runtime_env,
        "preflight_browser_provider",
        lambda *a, **kw: pytest.fail("unexpected network preflight"),
    )
    _runtime_env.require_local_browser_or_skip(unittest.TestCase(), {}, provider="pnas")


def test_live_fetch_diagnostics_come_from_own_saved_artifact(tmp_path):
    import json
    from tests.support.live_acceptance import fetch_browser_diagnostics

    path = tmp_path / "diagnostics" / "pnas" / "10.1073_test" / "byparr.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "doi": "10.1073/test",
                "diagnostics": {
                    "browser_runtime_trace": {
                        "navigation_count": 1,
                        "candidates": [
                            {
                                "navigation_seconds": 2.5,
                                "dom_readiness_seconds": 0.75,
                                "dom_readiness_result": "ready",
                            }
                        ],
                    }
                },
            }
        )
    )
    trace = fetch_browser_diagnostics(tmp_path, provider="pnas", doi="10.1073/test")
    assert trace["browser_navigation_count"] == 1
    assert trace["navigation_seconds"] == 2.5
    assert trace["dom_readiness_seconds"] == 0.75
    assert trace["diagnostics"][0]["path"] == str(path)
    assert (
        fetch_browser_diagnostics(tmp_path, provider="pnas", doi="10.1073/other")[
            "diagnostics"
        ]
        == []
    )


@pytest.mark.parametrize("status", ["no_access", "extraction_error"])
def test_catalog_fetch_never_preflights_and_preserves_actual_failure(
    monkeypatch, tmp_path, status
):
    from tests.live import test_live_publishers as live
    from paper_fetch.workflow.types import PaperFetchFailure
    from paper_fetch.failure import FailureDiagnostics
    import json

    sample = provider_benchmark_sample("pnas")
    records = []
    monkeypatch.setattr(live, "require_local_browser_or_skip", lambda *a, **kw: None)
    monkeypatch.setattr(
        _runtime_env,
        "preflight_browser_provider",
        lambda *a, **kw: pytest.fail("unexpected network preflight"),
    )

    def fetch(*a, **kw):
        kw["telemetry"]["fetch_wall_seconds"] = 1.5
        raise PaperFetchFailure(
            status=status,
            reason="actual fetch failure",
            diagnostics=FailureDiagnostics(
                stage="fetching", details={"retained": True}
            ),
        )

    monkeypatch.setattr(live, "fetch_envelope", fetch)
    with pytest.raises(
        pytest.skip.Exception if status == "no_access" else PaperFetchFailure
    ):
        live.test_catalog_provider_sample_live_body_acceptance(
            sample, "byparr", {}, tmp_path, records, lambda *a: None
        )
    saved = json.loads((tmp_path / "byparr" / "live-acceptance.json").read_text())[
        "providers"
    ][0]
    assert saved["preflight"] is None
    assert saved["performance"]["preflight_seconds"] == 0
    assert saved["performance"]["fetch_wall_seconds"] == 1.5
    assert saved["terminal"]["reason_code"] == status
    assert saved["failure_details"] == {"retained": True}


@pytest.mark.parametrize("fetch_error", [False, True])
def test_mcp_fetch_calls_only_fetch_and_preserves_per_case_evidence(
    monkeypatch, tmp_path, fetch_error
):
    import asyncio
    import json
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from tests.live import test_live_mcp as live

    calls = []

    @asynccontextmanager
    async def client(*args, **kwargs):
        kwargs["errlog"].write("subprocess diagnostic")
        yield None, None

    class Session:
        async def initialize(self):
            pass

        async def call_tool(self, name, args, **kwargs):
            calls.append(name)
            assert name == "fetch_paper"
            if fetch_error:
                raise RuntimeError("actual subprocess fetch failure")
            return SimpleNamespace(
                structured_content={"status": "no_access"}, is_error=True
            )

    @asynccontextmanager
    async def session(*args, **kwargs):
        yield Session()

    monkeypatch.setenv("PAPER_FETCH_LIVE_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setattr(live, "stdio_client", client)
    monkeypatch.setattr(live, "ClientSession", session)
    outputs = []
    for name in ("camoufox", "byparr"):
        case = live.LiveMcpServerTests(
            methodName=f"test_pnas_{name}_live_via_mcp_reports_progress_and_logs"
        )
        case.env = {}
        if fetch_error:
            with pytest.raises(RuntimeError, match="actual subprocess fetch failure"):
                asyncio.run(case._call_fetch(query="10.1073/test", provider="pnas"))
        else:
            asyncio.run(case._call_fetch(query="10.1073/test", provider="pnas"))
        outputs.append(case.fetch_output_dir)
        saved = json.loads((case.fetch_output_dir / "fetch-result.json").read_text())
        assert saved["preflight"] is None
        assert saved["preflight_seconds"] == 0
        assert saved["is_error"] is True
        assert (
            case.fetch_output_dir / "stderr.log"
        ).read_text() == "subprocess diagnostic"
    assert calls == ["fetch_paper", "fetch_paper"]
    assert outputs[0] != outputs[1]
    assert all((output / "fetch-result.json").exists() for output in outputs)
