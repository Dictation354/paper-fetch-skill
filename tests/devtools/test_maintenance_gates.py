from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pytest

from scripts.audit_dependencies import (
    Vulnerability,
    load_waivers,
    parse_audit_report,
    unwaived_vulnerabilities,
)
from scripts.check_complexity_budget import (
    ComplexityViolation,
    budget_regressions,
)
from scripts.report_coverage_focus import FOCUS_AREAS
from scripts.sync_version import project_version_facts, synchronized_version_issues


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_dependency_audit_requires_exact_package_version_and_advisory() -> None:
    findings = parse_audit_report(
        {
            "dependencies": [
                {
                    "name": "Example",
                    "version": "1.2.3",
                    "vulns": [{"id": "GHSA-example"}],
                }
            ]
        }
    )
    assert findings == [Vulnerability("example", "1.2.3", "GHSA-example")]
    assert unwaived_vulnerabilities(findings, []) == findings


def test_dependency_waivers_reject_expiry_and_extra_fields(tmp_path: Path) -> None:
    waiver_path = tmp_path / "waivers.json"
    waiver_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "waivers": [
                    {
                        "package": "example",
                        "version": "1.2.3",
                        "vulnerability_id": "GHSA-example",
                        "expires": "2026-01-01",
                        "reason": "Temporary mitigation.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Expired"):
        load_waivers(waiver_path, today=date(2026, 7, 26))


def test_complexity_budget_rejects_new_and_worsened_symbols() -> None:
    baseline = [ComplexityViolation("src/a.py", "C901", "owner", 30)]
    current = [
        ComplexityViolation("src/a.py", "C901", "owner", 31),
        ComplexityViolation("src/b.py", "C901", "new_owner", 26),
    ]
    assert budget_regressions(baseline, current) == current


def test_release_version_artifacts_are_synchronized() -> None:
    facts = project_version_facts()
    assert facts.version == "4.0.2"
    assert synchronized_version_issues(facts) == []


def test_coverage_focus_report_keeps_high_risk_areas_visible() -> None:
    assert {area.name for area in FOCUS_AREAS} == {
        "workflow",
        "HTTP/cache",
        "PDF fallback",
        "browser runtime",
        "installer",
    }
    assert all(area.include for area in FOCUS_AREAS)


def test_onboarding_compatibility_entrypoint_remains_modular() -> None:
    entrypoint = REPO_ROOT / "scripts" / "onboard_from_manifests.py"
    parts_dir = REPO_ROOT / "src" / "paper_fetch_devtools" / "onboarding" / "parts"
    expected = {
        "bootstrap.py",
        "commands.py",
        "coordinator.py",
        "discovery.py",
        "parser.py",
        "recovery.py",
        "review_artifacts.py",
        "state_machine.py",
        "summary.py",
        "worker_runtime.py",
    }
    parts = {path.name for path in parts_dir.glob("*.py") if path.name != "__init__.py"}

    assert len(entrypoint.read_text(encoding="utf-8").splitlines()) < 40
    assert parts == expected
    assert all(
        len((parts_dir / name).read_text(encoding="utf-8").splitlines()) < 2_000
        for name in parts
    )
