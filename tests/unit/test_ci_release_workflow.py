from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
SETUP_ACTION = REPO_ROOT / ".github" / "actions" / "setup-python-deps" / "action.yml"


def _workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _workflow_text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_workflows_are_split_by_operational_boundary() -> None:
    assert {path.name for path in WORKFLOWS.glob("*.yml")} == {
        "ci.yml",
        "dependency-refresh.yml",
        "live.yml",
        "offline.yml",
        "release.yml",
        "rolling-release.yml",
    }
    assert "workflow_call" in _workflow_text("offline.yml")
    assert "uses: ./.github/workflows/offline.yml" in _workflow_text("release.yml")


def test_regular_ci_runs_complete_unit_coverage_and_devtools() -> None:
    workflow = _workflow_text("ci.yml")
    assert "pytest tests/unit -q" in workflow
    assert "--cov-branch" in workflow
    assert "pytest tests/integration -q" in workflow
    assert "pytest tests/devtools -q" in workflow
    assert "tests/live" not in workflow


def test_ci_protects_minimum_and_maximum_python_core_and_full_installs() -> None:
    workflow = _workflow_text("ci.yml")
    assert 'python-version: ["3.11", "3.14"]' in workflow
    assert 'install: ["core", "full"]' in workflow
    assert "tests/unit/test_provider_catalog.py" in workflow
    assert '"$wheel[full]"' in workflow
    assert '"$wheel"' in workflow


def test_quality_gate_uses_whole_package_typing_complexity_and_locked_audit() -> None:
    workflow = _workflow_text("ci.yml")
    assert "mypy src/paper_fetch" in workflow
    assert "scripts/check_complexity_budget.py" in workflow
    assert "scripts/check_provider_governance.py" in workflow
    assert "scripts/audit_dependencies.py" in workflow
    assert "scripts/sync_version.py --check" in workflow
    assert "uv sync --frozen" in SETUP_ACTION.read_text(encoding="utf-8")


def test_live_external_state_is_scheduled_low_frequency_and_serial() -> None:
    workflow = _workflow_text("live.yml")
    assert "workflow_dispatch" in workflow
    assert "schedule:" in workflow
    assert '"17 3 * * 2"' in workflow
    assert '"41 4 1,15 * *"' in workflow
    assert "tests/live/test_live_publishers.py" in workflow
    assert "tests/live/test_live_mcp.py" in workflow
    assert "tests/live/test_live_ieee_protected.py" not in workflow
    assert "-q -n 0" in workflow
    assert "--force-enable-socket" not in workflow
    assert "--junitxml=artifacts/live-publishers.xml" in workflow
    assert "junit_family=legacy" in workflow
    assert "artifacts/live-publishers/live-acceptance.json" not in workflow
    assert "artifacts/live-publishers" in workflow
    assert "install-formula-tools.sh" in workflow
    assert "tests/integration/test_golden_corpus.py -q" in workflow
    assert "python -m camoufox fetch" in workflow
    assert "GITHUB_TOKEN: ${{ github.token }}" in workflow
    assert "scripts/run_provider_drift_report.py" in workflow
    assert "provider-drift-report.json" in workflow


def test_offline_builds_full_extra_for_supported_python_matrix() -> None:
    workflow = _workflow_text("offline.yml")
    for version in ("3.11", "3.12", "3.13", "3.14"):
        assert version in workflow
    assert 'full: "true"' in workflow
    assert "build-offline-package.sh" in workflow
    assert "build-offline-package-windows.ps1" in workflow
    assert "posix_tooling_ref" in workflow
    assert "windows_tooling_ref" in workflow
    assert "path: .posix-release-tooling" in workflow
    assert ".posix-release-tooling/scripts/build-offline-package.sh" in workflow
    assert ".posix-release-tooling/install-offline.sh" in workflow
    assert ".posix-release-tooling/scripts/verify-offline-package.sh" in workflow
    assert ".posix-release-tooling/src/paper_fetch/formula/install.py" not in workflow
    assert "working-directory: .posix-release-tooling" in workflow
    assert "Validate immutable source macOS adaptation contract" in workflow
    assert "posix_tooling_ref must be an immutable 40-character commit SHA" in workflow
    assert "PAPER_FETCH_OFFLINE_TOOLING_REVISION" in workflow
    assert (
        'git show "$TOOLING_REF:scripts/build-offline-package-windows.ps1"' in workflow
    )
    assert 'git show "$TOOLING_REF:src/paper_fetch/formula/install.py"' not in workflow
    assert "haskell-actions/setup@cd0d9bdd65b20557f41bea4dbe43d0b5fbbfe553" in workflow
    assert 'ghc-version: "9.10.3"' in workflow
    assert 'cabal-version: "3.12.1.0"' in workflow
    assert "ghc-9.10.3-texmath-0.13.2" in workflow
    assert "frozen_dependencies" in workflow
    assert "dependency_tooling_ref" in workflow
    assert "dependency-snapshot-${{ matrix.target }}" in workflow
    assert "scripts/resolve_offline_dependencies.py verify" in workflow
    assert "PIP_NO_INDEX" in workflow
    assert "PIP_FIND_LINKS" in workflow


def test_offline_windows_tooling_ref_is_immutable_and_provenanced() -> None:
    workflow = _workflow_text("offline.yml")
    windows_job = workflow.index("  windows:")
    source_setup = workflow.index(
        "- uses: ./.github/actions/setup-python-deps",
        windows_job,
    )
    source_contract = workflow.index(
        "- name: Validate immutable source macOS adaptation contract",
        windows_job,
    )
    validation = workflow.index("- name: Validate trusted Windows tooling revision")
    overlay = workflow.index("- name: Overlay trusted Windows release tooling")
    fetch = workflow.index('git fetch --no-tags --depth=1 origin "$TOOLING_REF"')
    show = workflow.index(
        'git show "$TOOLING_REF:scripts/build-offline-package-windows.ps1"'
    )
    build = workflow.index("- name: Build Windows full offline installer")

    assert windows_job < source_setup < source_contract < validation
    assert validation < overlay < fetch < show < build
    assert (
        "windows_tooling_ref must be an immutable 40-character commit SHA" in workflow
    )
    assert 'if [[ ! "$TOOLING_REF" =~ ^[0-9a-fA-F]{40}$ ]]' in workflow
    assert (
        "PAPER_FETCH_OFFLINE_TOOLING_REVISION: ${{ inputs.windows_tooling_ref }}"
    ) in workflow


def test_offline_workflow_verifies_macos_packages_on_pinned_arm64_runner() -> None:
    workflow = _workflow_text("offline.yml")

    assert workflow.count("os: macos-15") == 4
    for tag in ("cp311", "cp312", "cp313", "cp314"):
        assert f"target: macos-arm64-{tag}" in workflow
    assert "macos-latest" not in workflow
    assert "uv run python scripts/validate_macos_adaptation.py" in workflow
    assert "uv run --project .. python scripts/validate_macos_adaptation.py" in workflow
    assert 'MACOSX_DEPLOYMENT_TARGET: "15.0"' in workflow
    assert "packages=(dist/*.tar.gz)" in workflow
    assert "packages=(dist/*.sh)" in workflow
    assert 'if [ "${#packages[@]}" -ne 1 ]' in workflow
    assert 'scripts/verify-offline-package.sh "${packages[0]}"' in workflow
    assert 'PAPER_FETCH_OFFLINE_SKIP_FETCH_SMOKE: "1"' in workflow
    assert "if-no-files-found: error" in workflow


def test_regular_ci_includes_native_macos_offline_gate() -> None:
    workflow = _workflow_text("ci.yml")

    assert "macos-contract-portable:" in workflow
    assert "os: [ubuntu-latest, windows-latest]" in workflow
    assert "scripts/test-macos-contract.sh" in workflow
    assert (
        "scripts/test-macos-contract.ps1 -Python .venv/Scripts/python.exe" in workflow
    )
    assert "macos-native:" in workflow
    assert "runs-on: macos-15" in workflow
    assert 'python-version: "3.14"' in workflow
    assert "uv run python scripts/validate_macos_adaptation.py" in workflow
    assert 'test "$(uname -m)" = "arm64"' in workflow
    assert "uv run python -m camoufox fetch official/152.0.4-beta.28" in workflow
    assert "GITHUB_TOKEN: ${{ github.token }}" in workflow
    assert 'PAPER_FETCH_RUN_NATIVE_CAMOUFOX_TEST: "1"' in workflow
    assert "tests/integration/test_camoufox_native_macos.py -q -n 0" in workflow
    assert "test_cache_scope_accepts_equivalent_filesystem_alias_for_root" in workflow
    assert "haskell-actions/setup@cd0d9bdd65b20557f41bea4dbe43d0b5fbbfe553" in workflow
    assert 'MACOSX_DEPLOYMENT_TARGET: "15.0"' in workflow
    assert "scripts/build-offline-package.sh --output-dir dist" in workflow
    assert "scripts/verify-offline-package.sh" in workflow
    assert "paper-fetch-skill-offline-macos-arm64-cp314.tar.gz" in workflow
    assert 'PAPER_FETCH_OFFLINE_SKIP_FETCH_SMOKE: "1"' in workflow


def test_release_emits_sbom_checksums_and_build_provenance() -> None:
    workflow = _workflow_text("release.yml")
    assert "Existing immutable v* tag to release" in workflow
    assert "ref: ${{ needs.verify-tag.outputs.tag }}" in workflow
    assert "paper-fetch-sbom.cdx.json" in workflow
    assert "SHA256SUMS" in workflow
    assert "actions/attest-build-provenance@" in workflow
    assert "attestations: write" in workflow
    assert "id-token: write" in workflow
    assert (
        "posix_tooling_ref: ${{ github.event_name == 'workflow_dispatch' && github.sha || '' }}"
        in workflow
    )
    assert (
        "windows_tooling_ref: ${{ github.event_name == 'workflow_dispatch' && github.sha || '' }}"
        in workflow
    )


def test_releases_publish_only_chinese_release_notes() -> None:
    stable = _workflow_text("release.yml")
    rolling = _workflow_text("rolling-release.yml")

    assert "Write Chinese stable release notes" in stable
    assert "CHANGELOG_CN.md > release-notes.md" in stable
    assert "--notes-file release-notes.md" in stable
    assert "--generate-notes" not in stable
    assert "Write Chinese rolling release notes" in rolling
    assert "## English" not in rolling
    assert "Stable source:" not in rolling


def test_actions_are_pinned_to_full_commit_shas() -> None:
    texts = [
        path.read_text(encoding="utf-8")
        for path in [*WORKFLOWS.glob("*.yml"), SETUP_ACTION]
    ]
    for text in texts:
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("uses: ") or stripped.startswith("uses: ./"):
                continue
            reference = stripped.split("#", 1)[0].strip().split("@", 1)[-1]
            assert len(reference) == 40
            assert all(character in "0123456789abcdef" for character in reference)


def test_dependency_refresh_resolves_latest_compatible_graph_without_commit() -> None:
    workflow = _workflow_text("dependency-refresh.yml")
    assert "uv lock --upgrade" in workflow
    assert "scripts/audit_dependencies.py" in workflow
    assert "pytest tests/unit -q" in workflow
    assert "git push" not in workflow


def test_rolling_release_restores_frozen_full_dependency_updates() -> None:
    workflow = _workflow_text("rolling-release.yml")
    assert 'cron: "17 19 * * *"' in workflow
    assert "force_refresh" in workflow
    assert "repos/$GITHUB_REPOSITORY/releases/latest" in workflow
    assert "dependency-latest is immutable" in workflow
    assert "frozen_dependencies: true" in workflow
    assert "uses: ./.github/workflows/offline.yml" in workflow
    for target in (
        "linux-x86_64-cp311",
        "linux-x86_64-cp312",
        "linux-x86_64-cp313",
        "linux-x86_64-cp314",
        "macos-arm64-cp311",
        "macos-arm64-cp312",
        "macos-arm64-cp313",
        "macos-arm64-cp314",
        "windows-x86_64-cp313",
    ):
        assert target in workflow
    assert "ROLLING_RELEASE_TOKEN" in workflow
    assert "--clobber" in workflow
    assert "-F prerelease=true" in workflow
    assert "-f make_latest=false" in workflow
    assert "--latest=false" in workflow
    assert "Remove stale rolling release assets" in workflow
    assert "Verify published rolling prerelease" in workflow
    assert "Write Chinese rolling release notes" in workflow
