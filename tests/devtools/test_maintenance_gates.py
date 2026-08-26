from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re

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
    update_budget,
)
from scripts.check_provider_governance import _validated_waiver_keys, collect_report
from scripts.report_coverage_focus import (
    FOCUS_AREAS,
    CoverageFocus,
    _matched_source_files,
    report_focus_areas,
)
from scripts.sync_version import project_version_facts, synchronized_version_issues


REPO_ROOT = Path(__file__).resolve().parents[2]


def _pytest_command_contract_files() -> list[Path]:
    files = {REPO_ROOT / "AGENTS.md"}
    scopes = (
        (REPO_ROOT / ".github" / "workflows", ("*.yml", "*.yaml")),
        (REPO_ROOT / "docs", ("*.md", "*.toml")),
        # Runtime state and evidence are historical records, not command templates.
        (REPO_ROOT / "onboarding", ("*.md",)),
        (REPO_ROOT / "src" / "paper_fetch_devtools", ("*.py",)),
        (
            REPO_ROOT / "skills" / "paper-fetch-skill" / "references",
            ("*.md",),
        ),
    )
    for root, patterns in scopes:
        for pattern in patterns:
            files.update(path for path in root.rglob(pattern) if path.is_file())
    return sorted(files)


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


def _provider_waiver(key: str, *, expires_at: str) -> dict[str, str]:
    return {
        "key": key,
        "owner": "provider-maintainers/example",
        "restriction": "source_stability",
        "reviewed_at": "2026-08-26",
        "expires_at": expires_at,
        "reason": "A stable authentic provider response is not yet available.",
        "evidence_plan": (
            "Capture the route-specific response and replay it through the current "
            "extractor with an exact expected contract."
        ),
    }


def test_provider_waivers_reject_batch_expiry_and_missing_ownership() -> None:
    errors: list[str] = []
    policy = {
        "route_family_waivers": [
            _provider_waiver("example:html", expires_at="2026-09-10"),
            _provider_waiver("example:pdf", expires_at="2026-09-10"),
        ]
    }

    keys = _validated_waiver_keys(
        policy,
        "route_family_waivers",
        errors,
        {},
    )

    assert keys == {"example:html"}
    assert any("batch-expiry waivers are forbidden" in error for error in errors)

    malformed = _provider_waiver("example:xml", expires_at="2026-09-17")
    malformed.pop("owner")
    errors = []
    keys = _validated_waiver_keys(
        {"route_family_waivers": [malformed]},
        "route_family_waivers",
        errors,
        {},
    )
    assert keys == set()
    assert any("missing=['owner']" in error for error in errors)


def test_complexity_budget_rejects_new_and_worsened_symbols() -> None:
    baseline = [ComplexityViolation("src/a.py", "C901", "owner", 30)]
    current = [
        ComplexityViolation("src/a.py", "C901", "owner", 31),
        ComplexityViolation("src/b.py", "C901", "new_owner", 26),
    ]
    assert budget_regressions(baseline, current) == current


def test_complexity_budget_update_is_monotonic(tmp_path: Path) -> None:
    budget = tmp_path / "complexity.json"
    baseline = [ComplexityViolation("src/a.py", "C901", "owner", 30)]
    assert update_budget(budget, baseline) == []
    before = budget.read_bytes()

    regression = [ComplexityViolation("src/a.py", "C901", "owner", 31)]
    assert update_budget(budget, regression) == regression
    assert budget.read_bytes() == before

    improvement = [ComplexityViolation("src/a.py", "C901", "owner", 29)]
    assert update_budget(budget, improvement) == []
    payload = json.loads(budget.read_text(encoding="utf-8"))
    assert payload["violations"][0]["value"] == 29


def test_release_version_artifacts_are_synchronized() -> None:
    facts = project_version_facts()
    assert facts.version == "5.5.0"
    assert synchronized_version_issues(facts) == []


def test_documented_and_generated_pytest_commands_use_locked_uv_runtime() -> None:
    forbidden = {
        "ambient python -m pytest": re.compile(
            r"(?<!uv run )\bpython(?:3(?:\.\d+)*)?\s+-m\s+pytest\b"
        ),
        "uv run pytest shortcut": re.compile(r"\buv\s+run\s+pytest\b"),
        "uv run python3 launcher": re.compile(
            r"\buv\s+run\s+python3(?:\.\d+)*\s+-m\s+pytest\b"
        ),
        "tokenized ambient launcher": re.compile(
            r'"PYTHONPATH=src",\s*"python3",\s*"-m",\s*"pytest"',
            re.DOTALL,
        ),
        "tokenized uv shortcut": re.compile(
            r'"PYTHONPATH=src",\s*"uv",\s*"run",\s*"pytest"',
            re.DOTALL,
        ),
    }
    failures: list[str] = []
    exact = "PYTHONPATH=src uv run python -m pytest"
    invocation = re.compile(r"\buv run python -m pytest\b")

    for path in _pytest_command_contract_files():
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(REPO_ROOT).as_posix()
        for label, pattern in forbidden.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                failures.append(f"{relative}:{line}: {label}")
        for match in invocation.finditer(text):
            prefix_start = match.start() - len("PYTHONPATH=src ")
            if prefix_start < 0 or text[prefix_start : match.end()] != exact:
                line = text.count("\n", 0, match.start()) + 1
                failures.append(f"{relative}:{line}: missing PYTHONPATH=src")

    bootstrap = (
        REPO_ROOT
        / "src"
        / "paper_fetch_devtools"
        / "onboarding"
        / "parts"
        / "bootstrap.py"
    ).read_text(encoding="utf-8")
    tokenized_prefix = re.compile(
        r'PYTEST_COMMAND_PREFIX\s*=\s*\(\s*"PYTHONPATH=src",\s*"uv",\s*'
        r'"run",\s*"python",\s*"-m",\s*"pytest",\s*\)',
        re.DOTALL,
    )
    assert tokenized_prefix.search(bootstrap), "devtools pytest prefix drifted"
    assert failures == []


def test_coverage_focus_report_keeps_high_risk_areas_visible() -> None:
    assert {area.name for area in FOCUS_AREAS} == {
        "security boundaries",
        "workflow",
        "HTTP/cache",
        "PDF fallback",
        "browser runtime",
        "installer",
    }
    assert all(area.include for area in FOCUS_AREAS)
    security = next(area for area in FOCUS_AREAS if area.name == "security boundaries")
    assert security.minimum_branch_percent == 90
    assert {area.name: area.minimum_branch_percent for area in FOCUS_AREAS} == {
        "security boundaries": 90,
        "workflow": 80,
        "HTTP/cache": 77,
        "PDF fallback": 64,
        "browser runtime": 66,
        "installer": 35,
    }
    browser_runtime = next(
        area for area in FOCUS_AREAS if area.name == "browser runtime"
    )
    assert (
        REPO_ROOT / "src/paper_fetch/providers/browser_runtime/backends/camoufox.py"
    ).resolve() in _matched_source_files(browser_runtime.include)


def test_coverage_focus_gate_fails_below_machine_readable_baseline(
    tmp_path: Path,
) -> None:
    from coverage import Coverage

    source = tmp_path / "branch_sample.py"
    source.write_text(
        "def choose(value):\n    if value:\n        return 'yes'\n    return 'no'\n",
        encoding="utf-8",
    )
    data_file = tmp_path / ".coverage"
    coverage = Coverage(data_file=str(data_file), branch=True, config_file=False)
    coverage.start()
    namespace: dict[str, object] = {}
    exec(compile(source.read_text(encoding="utf-8"), str(source), "exec"), namespace)
    namespace["choose"](True)  # type: ignore[operator]
    coverage.stop()
    coverage.save()

    [result] = report_focus_areas(
        data_file=data_file,
        areas=(
            CoverageFocus(
                name="sample",
                include=(str(source),),
                minimum_branch_percent=100,
            ),
        ),
        show_details=False,
    )

    assert result.branch_covered == 1
    assert result.branch_total == 2
    assert result.branch_percent == 50.0
    assert result.measured_branch_percent == 50
    assert result.measured_branch_percent < result.minimum_branch_percent
    assert not result.passed


def test_coverage_focus_gate_fails_closed_for_unmatched_and_unmeasured_files(
    tmp_path: Path,
) -> None:
    from coverage import Coverage

    measured = tmp_path / "measured.py"
    measured.write_text(
        "def choose(value):\n    if value:\n        return 'yes'\n    return 'no'\n",
        encoding="utf-8",
    )
    unmeasured = tmp_path / "unmeasured.py"
    unmeasured.write_text("if True:\n    value = 1\n", encoding="utf-8")
    data_file = tmp_path / ".coverage"
    coverage = Coverage(data_file=str(data_file), branch=True, config_file=False)
    coverage.start()
    namespace: dict[str, object] = {}
    exec(compile(measured.read_text(), str(measured), "exec"), namespace)
    namespace["choose"](True)  # type: ignore[operator]
    coverage.stop()
    coverage.save()

    with pytest.raises(ValueError, match="matched no files"):
        report_focus_areas(
            data_file=data_file,
            areas=(CoverageFocus("missing", (str(tmp_path / "missing*.py"),), 0),),
            show_details=False,
        )
    with pytest.raises(ValueError, match="has unmeasured files"):
        report_focus_areas(
            data_file=data_file,
            areas=(CoverageFocus("unmeasured", (str(unmeasured),), 0),),
            show_details=False,
        )


def test_coverage_focus_gate_fails_closed_for_branchless_area(tmp_path: Path) -> None:
    from coverage import Coverage

    branched = tmp_path / "branched.py"
    branched.write_text("if __name__:\n    value = 1\n", encoding="utf-8")
    branchless = tmp_path / "branchless.py"
    branchless.write_text("value = 1\n", encoding="utf-8")
    data_file = tmp_path / ".coverage"
    coverage = Coverage(data_file=str(data_file), branch=True, config_file=False)
    coverage.start()
    for source in (branched, branchless):
        exec(compile(source.read_text(), str(source), "exec"), {})
    coverage.stop()
    coverage.save()

    with pytest.raises(ValueError, match="has no measurable branches"):
        report_focus_areas(
            data_file=data_file,
            areas=(CoverageFocus("branchless", (str(branchless),), 0),),
            show_details=False,
        )


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


def test_provider_governance_keeps_routes_manifests_fixtures_docs_and_debt_synced() -> (
    None
):
    report = collect_report()

    assert report.errors == ()
    assert report.provider_count == 20
    assert report.route_count == 66
    assert report.route_family_count == 40
    assert report.waived_route_family_count == 10
    assert report.negative_coverage_count == 16
    assert report.waived_negative_coverage_count == 13
    assert report.executable_replay_count == 140
    assert report.synthetic_fixture_count == 2
    assert report.unit_only_fixture_count == 0
    assert report.manifest_only_fixture_count == 15
    assert report.unexecutable_fixture_count == 0
    assert report.negative_replay_count == 17
    assert report.complexity_violation_count <= 60
