from __future__ import annotations

import json
from pathlib import Path

from scripts.run_public_direct_canary import load_canary_routes, run_canary
from scripts.update_provider_canary_state import update_state


REPO_ROOT = Path(__file__).resolve().parents[2]


def _report(*, passed: bool, reason: str = "network") -> dict[str, object]:
    return {
        "schema_version": 1,
        "results": [
            {
                "key": "plos:xml",
                "provider": "plos",
                "route": "xml",
                "passed": passed,
                "reason": reason,
            }
        ],
    }


def test_canary_config_contains_only_catalogued_public_direct_routes() -> None:
    routes = load_canary_routes()

    assert len(routes) == 4
    assert {f"{item['provider']}:{item['route']}" for item in routes} == {
        "arxiv:official_html",
        "copernicus:xml",
        "frontiers:xml",
        "plos:xml",
    }


def test_canary_collects_every_result_and_redacts_failures() -> None:
    routes = load_canary_routes()

    def runner(item: dict[str, str]) -> dict[str, object]:
        if item["provider"] == "plos":
            raise RuntimeError("https://example.test/file?api_key=do-not-log")
        return {"passed": True, "reason": "ok"}

    report = run_canary(routes, runner=runner)

    assert len(report["results"]) == len(routes)
    failed = report["results"][-1]
    assert failed["passed"] is False
    assert "do-not-log" not in json.dumps(failed)


def test_warning_starts_at_third_failure_and_success_resets() -> None:
    state: dict[str, object] = {"schema_version": 1, "routes": {}}
    for expected_count in (1, 2):
        state, warnings = update_state(state, _report(passed=False))
        assert warnings == ()
        assert state["routes"]["plos:xml"]["consecutive_failures"] == expected_count

    state, warnings = update_state(state, _report(passed=False))
    assert warnings == ("plos:xml failed 3 consecutive scheduled canaries",)

    state, warnings = update_state(state, _report(passed=True, reason="ok"))
    assert warnings == ()
    assert state["routes"]["plos:xml"] == {
        "consecutive_failures": 0,
        "last_passed": True,
        "last_reason": "ok",
    }


def test_scheduled_workflow_is_nonblocking_credentialless_and_preserves_state() -> None:
    workflow = (REPO_ROOT / ".github/workflows/provider-canary.yml").read_text(
        encoding="utf-8"
    )

    assert "schedule:" in workflow
    assert "continue-on-error: true" in workflow
    assert 'PAPER_FETCH_RUN_PUBLIC_CANARY: "1"' in workflow
    assert "actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9" in workflow
    assert (
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in workflow
    )
    assert "update_provider_canary_state.py" in workflow
    assert "${{ secrets." not in workflow
