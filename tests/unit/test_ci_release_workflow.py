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
        "offline.yml",
        "package.yml",
        "provider-canary.yml",
        "release.yml",
        "rolling-release.yml",
        "verify.yml",
    }
    assert "workflow_call" in _workflow_text("offline.yml")
    assert "workflow_call" in _workflow_text("package.yml")
    assert "workflow_call" in _workflow_text("verify.yml")
    assert "uses: ./.github/workflows/verify.yml" in _workflow_text("ci.yml")
    assert "uses: ./.github/workflows/package.yml" in _workflow_text("verify.yml")
    assert "uses: ./.github/workflows/package.yml" in _workflow_text("release.yml")
    assert "uses: ./.github/workflows/verify.yml" not in _workflow_text("release.yml")
    assert "uses: ./.github/workflows/offline.yml" in _workflow_text("release.yml")


def test_regular_ci_runs_complete_unit_coverage_and_devtools() -> None:
    workflow = _workflow_text("verify.yml")
    assert "ref: ${{ github.sha }}" in _workflow_text("ci.yml")
    assert "pytest tests/unit -q" in workflow
    assert "--cov-branch" in workflow
    assert "scripts/report_coverage_focus.py" in workflow
    assert workflow.index("--cov-branch") < workflow.index(
        "scripts/report_coverage_focus.py"
    )
    assert "pytest tests/integration -q" in workflow
    assert "pytest tests/devtools -q" in workflow
    assert "tests/live" not in workflow


def test_reusable_verify_checks_out_only_the_requested_immutable_ref() -> None:
    workflow = _workflow("verify.yml")

    for job_name, job in workflow["jobs"].items():
        if "uses" in job:
            assert job_name == "package"
            assert job["uses"] == "./.github/workflows/package.yml"
            assert job["with"]["ref"] == "${{ inputs.ref }}"
            continue
        checkouts = [
            step
            for step in job["steps"]
            if str(step.get("uses") or "").startswith("actions/checkout@")
        ]
        assert checkouts, job_name
        for checkout in checkouts:
            assert checkout.get("with", {}).get("ref") == "${{ inputs.ref }}"
            assert checkout.get("with", {}).get("persist-credentials") is False


def test_reusable_package_requires_and_checks_out_an_immutable_commit() -> None:
    workflow_text = _workflow_text("package.yml")
    workflow = _workflow("package.yml")
    steps = workflow["jobs"]["package"]["steps"]
    checkout = next(
        step
        for step in steps
        if str(step.get("uses") or "").startswith("actions/checkout@")
    )

    assert "Immutable source commit to package" in workflow_text
    assert "required: true" in workflow_text
    assert '[[ ! "$SOURCE_REF" =~ ^[0-9a-f]{40}$ ]]' in workflow_text
    assert 'test "$(git rev-parse HEAD)" = "$SOURCE_REF"' in workflow_text
    assert checkout["with"]["ref"] == "${{ inputs.ref }}"
    assert checkout["with"]["persist-credentials"] is False


def test_ci_protects_minimum_and_maximum_python_core_and_full_installs() -> None:
    workflow_text = _workflow_text("verify.yml")
    workflow = _workflow("verify.yml")
    assert 'python-version: ["3.11", "3.14"]' in workflow_text
    assert 'install: ["core", "full"]' in workflow_text
    assert "tests/unit/test_provider_catalog.py" in workflow_text
    assert '"$wheel[full]"' in workflow_text
    assert '"$wheel"' in workflow_text
    setup = next(
        step
        for step in workflow["jobs"]["python-boundaries"]["steps"]
        if str(step.get("uses") or "").startswith("./.github/actions/setup-python-deps")
    )
    assert setup["with"]["full"] == "true"


def test_quality_gate_uses_whole_package_typing_complexity_and_locked_audit() -> None:
    workflow = _workflow_text("verify.yml")
    quality_steps = _workflow("verify.yml")["jobs"]["quality"]["steps"]
    assert [
        step for step in quality_steps if step.get("name") == "Check lockfile freshness"
    ] == [{"name": "Check lockfile freshness", "run": "uv lock --check"}]
    assert "mypy src/paper_fetch" in workflow
    assert "scripts/check_complexity_budget.py" in workflow
    assert "scripts/check_provider_governance.py" in workflow
    assert "scripts/audit_dependencies.py" in workflow
    assert "scripts/sync_version.py --check" in workflow
    assert "uv sync --frozen" in SETUP_ACTION.read_text(encoding="utf-8")


def test_live_and_full_golden_checks_are_local_only() -> None:
    workflow_text = "\n".join(
        path.read_text(encoding="utf-8") for path in WORKFLOWS.glob("*.yml")
    )
    for local_only_entry in (
        "tests/live/test_live_publishers.py",
        "tests/live/test_live_mcp.py",
        "tests/live/test_live_ieee_protected.py",
        "PAPER_FETCH_RUN_LIVE",
        "PAPER_FETCH_RUN_FULL_GOLDEN",
        "scripts/run_provider_drift_report.py",
    ):
        assert local_only_entry not in workflow_text

    for local_entry in (
        REPO_ROOT / "tests" / "live" / "test_live_publishers.py",
        REPO_ROOT / "tests" / "live" / "test_live_mcp.py",
        REPO_ROOT / "tests" / "live" / "test_live_ieee_protected.py",
        REPO_ROOT / "tests" / "integration" / "test_golden_corpus.py",
        REPO_ROOT / "scripts" / "run_provider_drift_report.py",
    ):
        assert local_entry.is_file()


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
    assert "haskell-actions/setup@6037f33647c3f17758a2356c80fc4a53d7e0685d" in workflow
    assert 'ghc-version: "9.10.3"' in workflow
    assert 'cabal-version: "3.12.1.0"' in workflow
    assert "ghc-9.10.3-texmath-0.13.2" in workflow
    assert "frozen_dependencies" in workflow
    assert "dependency_tooling_ref" in workflow
    assert "dependency-snapshot-${{ matrix.target }}" in workflow
    assert "scripts/resolve_offline_dependencies.py verify" in workflow
    assert "PIP_NO_INDEX" in workflow
    assert "PIP_FIND_LINKS" in workflow
    assert "PYTHON_BIN: .venv/bin/python" in workflow
    assert "-PythonBin .venv/Scripts/python.exe" in workflow


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
    trusted_tooling = (
        "scripts/build-offline-package-windows.ps1",
        "scripts/generate_offline_evidence.py",
        "scripts/verify-windows-installer-lifecycle.ps1",
        "scripts/windows-installer-helper.ps1",
        "installer/manifest.json",
        "installer/paper-fetch-skill.iss",
        "installer/vendor/uninsis/i386/UninsIS.dll",
        "installer/vendor/uninsis/LICENSE",
        "installer/vendor/uninsis/NOTICE.md",
    )
    for path in trusted_tooling:
        assert workflow.count(f'git show "$TOOLING_REF:{path}"') == 1
        assert workflow.count(f"> {path}") == 1
    assert workflow.index('git show "$TOOLING_REF:installer/manifest.json"') < build
    assert workflow.index('git show "$TOOLING_REF:installer/paper-fetch-skill.iss"') < (
        build
    )


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
    workflow = _workflow_text("verify.yml")

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
    assert "Verify provider page preparation on native macOS" in workflow
    assert (
        "test_camoufox_provider_page_preparation_runs_before_html_capture" in workflow
    )
    assert "test_tandf_browser_page_preparation_hydrates_official_csv_table" in workflow
    assert (
        "test_tandf_browser_page_preparation_uses_bounded_embedded_table_fallback"
        in workflow
    )
    assert "test_cache_scope_accepts_equivalent_filesystem_alias_for_root" in workflow
    assert "haskell-actions/setup@6037f33647c3f17758a2356c80fc4a53d7e0685d" in workflow
    assert 'MACOSX_DEPLOYMENT_TARGET: "15.0"' in workflow
    assert "PYTHON_BIN: .venv/bin/python" in workflow
    assert "scripts/build-offline-package.sh --output-dir dist" in workflow
    assert "scripts/verify-offline-package.sh" in workflow
    assert "paper-fetch-skill-offline-macos-arm64-cp314.tar.gz" in workflow
    assert 'PAPER_FETCH_OFFLINE_SKIP_FETCH_SMOKE: "1"' in workflow


def test_regular_ci_includes_non_science_browser_performance_regressions() -> None:
    workflow = _workflow_text("verify.yml")

    assert "Non-Science browser performance regressions" in workflow
    assert (
        "Verify non-Science browser performance boundaries on native macOS" in workflow
    )
    for node in (
        "tests/unit/test_browser_preflight_reuse_cache.py",
        "test_acs_and_aip_direct_asset_probe_use_twenty_second_zero_retry_policy",
        "test_browser_recovery_circuit_is_host_scoped_concurrent_and_article_local",
        "test_direct_then_browser_probes_first_and_shares_host_circuit_on_caller_thread",
        "test_direct_first_figure_policy_skips_viewer_when_download_url_exists",
        "test_silverchair_figure_page_resolution_stays_on_camoufox_owner_thread",
        "test_provider_resource_policy_blocks_only_configured_heavy_types",
        "test_pnas_body_readiness_uses_bounded_budget_and_keeps_final_html",
        "test_wiley_body_readiness_requires_two_identical_ready_fingerprints",
        "test_open_wiley_context_without_storage_state_has_no_state_capability_use",
        "test_wiley_403_confirmed_body_and_identity_preserves_status",
        "test_wiley_403_review_rejects_unconfirmed_candidate",
        "test_wiley_403_failure_advances_to_next_candidate",
        "test_wiley_all_http_status_candidates_fail_with_reviews",
        "test_wiley_confirmed_403_html_passes_markdown_and_availability",
        "test_wiley_confirmed_403_extraction_failure_continues_next_candidate",
        "test_wiley_http_access_status_review_is_allowlisted_and_secret_safe",
        "test_wiley_body_readiness_defers_login_navigation_paywall_text",
        "test_wiley_preflight_accepts_leading_login_navigation_after_body_readiness",
        "test_figure_page_fetches_reuse_one_runtime_context_and_page",
        "test_acs_asset_extraction_promotes_largest_srcset_rendition",
        "test_annualreviews_asset_extraction_promotes_largest_srcset_rendition",
        "test_aip_asset_extraction_prefers_largest_official_srcset_rendition",
        "test_html_route_upgrades_existing_preview_from_official_source_archive",
        "test_copernicus_promotes_official_original_and_audits_preview_only",
        "test_mdpi_empty_intermediate_candidate_retries_next_html_before_pdf",
        "test_iop_index_cache_dedupes_signed_indexes_and_attachment_signatures",
        "test_tandf_article_assets_keep_body_figures_and_scope_supplement",
        "test_tandf_batch_results_keep_input_order_and_failed_table_fallback",
        "test_tandf_table_preparation_obeys_exhausted_total_deadline",
        "test_ieee_multimedia_discovery_memoizes_redacted_url_per_runtime",
    ):
        assert workflow.count(node) >= 2


def test_regular_ci_targets_network_rollback_and_strict_asset_regressions() -> None:
    workflow = _workflow_text("verify.yml")

    assert "Network rollback and strict asset acceptance regressions" in workflow
    for node in (
        "test_safe_remote_url_policy.py",
        "test_browser_image_payload.py",
        "test_pdf_browser_owned_download_url_uses_saved_bytes_without_direct_replay",
        "test_html_asset_download_uses_one_browser_recovery_after_direct_403",
        "test_observed_734_byte_http_200_head_only_shell_is_classified",
        "test_empty_shell_retry_requires_changed_candidate_profile_or_storage",
        "test_strict_local_assets_degrade_acceptance_without_failing_fulltext",
        "test_strict_full_size_implies_local_and_rejects_accepted_preview",
        "test_cli_manifest_fingerprint_and_acceptance_include_strict_asset_flags",
        "test_artifact_secret_scan.py",
        "test_source_development_ignores_unrelated_distribution_and_path_cli",
    ):
        assert node in workflow


def test_release_emits_sbom_checksums_and_build_provenance() -> None:
    workflow = _workflow_text("release.yml")
    assert "Existing immutable v* tag to release" in workflow
    assert 'git rev-parse "refs/tags/$tag^{commit}"' in workflow
    assert "source_sha: ${{ steps.source.outputs.source_sha }}" in workflow
    assert "ref: ${{ needs.verify-tag.outputs.source_sha }}" in workflow
    assert "uses: ./.github/workflows/package.yml" in workflow
    assert "uses: ./.github/workflows/verify.yml" not in workflow
    assert "paper-fetch-evidence-" in _workflow_text("offline.yml")
    assert "actual-staged-target" not in workflow
    assert "uv export" not in workflow
    assert "SHA256SUMS" in workflow
    assert (
        workflow.count(
            "actions/attest-build-provenance@"
            "4d101475d8b20a2381f78447822ac1eab6504dd8 # v4.2.2"
        )
        == 1
    )
    assert "subject-path: release-assets/**/*" in workflow
    assert "attestations: write" in workflow
    assert "id-token: write" in workflow
    assert "posix_tooling_ref: ${{ needs.verify-tag.outputs.source_sha }}" in workflow
    assert "windows_tooling_ref: ${{ needs.verify-tag.outputs.source_sha }}" in workflow
    assert 'test "$(git rev-parse HEAD)" = "$SOURCE_SHA"' in workflow
    publish_step = workflow.split(
        "- name: Publish immutable release assets", maxsplit=1
    )[1]
    assert "--verify-tag" in publish_step
    assert '--target "$SOURCE_SHA"' not in publish_step


def test_stable_release_validates_and_flattens_the_exact_asset_set() -> None:
    workflow = _workflow_text("release.yml")

    assert "path: release-inputs/python" in workflow
    assert "path: release-inputs/offline" in workflow
    assert "path: release-inputs/dependencies" in workflow
    publish_job = workflow.split("\n  publish:", maxsplit=1)[1]
    assert "merge-multiple: true" not in publish_job
    assert "scripts/prepare_release_assets.py prepare-stable" in workflow
    assert "--input-root release-inputs" in workflow
    assert "--output-dir release-assets" in workflow
    assert '--version "$VERSION"' in workflow
    assert "find release-assets -maxdepth 1 -type f -print0" in workflow
    assert "find release-assets -type f ! -name SHA256SUMS" not in workflow

    rolling = _workflow_text("rolling-release.yml")
    assert "scripts/prepare_release_assets.py prepare-rolling" in rolling


def test_release_build_jobs_check_out_the_verified_tag_commit() -> None:
    workflow = _workflow("release.yml")
    expected_ref = "${{ needs.verify-tag.outputs.source_sha }}"

    for job_name in ("resolve-dependencies", "merge-dependencies", "publish"):
        checkouts = [
            step
            for step in workflow["jobs"][job_name]["steps"]
            if str(step.get("uses") or "").startswith("actions/checkout@")
        ]
        assert checkouts, job_name
        assert checkouts[0].get("with", {}).get("ref") == expected_ref
        assert checkouts[0].get("with", {}).get("persist-credentials") is False

    offline_inputs = workflow["jobs"]["offline"]["with"]
    assert offline_inputs["ref"] == expected_ref
    assert offline_inputs["posix_tooling_ref"] == expected_ref
    assert offline_inputs["windows_tooling_ref"] == expected_ref
    assert offline_inputs["dependency_tooling_ref"] == expected_ref
    package_job = workflow["jobs"]["package"]
    assert package_job["uses"] == "./.github/workflows/package.yml"
    assert package_job["with"]["ref"] == expected_ref


def test_rolling_publish_checks_out_the_triggering_workflow_tooling() -> None:
    steps = _workflow("rolling-release.yml")["jobs"]["publish"]["steps"]
    checkouts = [
        (index, step)
        for index, step in enumerate(steps)
        if str(step.get("uses") or "").startswith("actions/checkout@")
    ]
    script_steps = [
        index
        for index, step in enumerate(steps)
        if "scripts/" in str(step.get("run") or "")
    ]

    assert len(checkouts) == 1
    assert script_steps
    checkout_index, checkout = checkouts[0]
    assert checkout_index < min(script_steps)
    assert checkout["with"]["ref"] == "${{ github.sha }}"
    assert checkout["with"]["fetch-depth"] == 1
    assert checkout["with"]["persist-credentials"] is False


def test_stable_release_builds_only_artifacts_without_test_gates() -> None:
    workflow_text = _workflow_text("release.yml")
    jobs = _workflow("release.yml")["jobs"]

    assert "verify" not in jobs
    assert jobs["package"]["needs"] == "verify-tag"
    assert jobs["resolve-dependencies"]["needs"] == "verify-tag"
    assert jobs["offline"]["needs"] == ["verify-tag", "merge-dependencies"]
    assert jobs["publish"]["needs"] == [
        "verify-tag",
        "package",
        "merge-dependencies",
        "offline",
    ]
    for forbidden in (
        "uses: ./.github/workflows/verify.yml",
        "tests/unit",
        "python -m pytest",
        "--cov",
        "coverage",
        "golden-exact:",
        "python-boundaries:",
        "macos-contract-portable:",
        "macos-native:",
    ):
        assert forbidden not in workflow_text


def test_stable_release_freezes_all_nine_target_dependency_graphs() -> None:
    workflow = _workflow_text("release.yml")

    assert "frozen_dependencies: true" in workflow
    assert (
        "dependency_tooling_ref: ${{ needs.verify-tag.outputs.source_sha }}" in workflow
    )
    assert "scripts/resolve_offline_dependencies.py resolve" in workflow
    assert "scripts/resolve_offline_dependencies.py merge" in workflow
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


def test_python_distributions_get_exact_inventory_and_independent_smokes() -> None:
    workflow = _workflow_text("package.yml")

    assert "scripts/verify_python_distribution.py" in workflow
    assert "quality/python-distribution-inventory.json" in workflow
    assert "python-distribution-$kind" in workflow
    assert "for kind in wheel sdist" in workflow
    assert '"$venv/bin/paper-fetch" --version' in workflow
    assert 'build_server().name == "paper-fetch"' in workflow
    assert "mathml_to_latex_cli.mjs" in workflow
    assert "manifest-record-v2.schema.json" in workflow
    assert "references/tool-contract.md" in workflow


def test_windows_offline_job_runs_final_exe_lifecycle_serially() -> None:
    workflow = _workflow_text("offline.yml")
    verifier = (REPO_ROOT / "scripts/verify-windows-installer-lifecycle.ps1").read_text(
        encoding="utf-8"
    )

    assert (
        "Verify final EXE install, overwrite upgrade, and uninstall serially"
        in workflow
    )
    assert "verify-windows-installer-lifecycle.ps1" in workflow
    assert "-n 0 equivalent" in workflow
    assert "Silent install of final EXE" in verifier
    assert "In-place overwrite upgrade" in verifier
    assert "Silent uninstall of final EXE" in verifier
    assert "USER_LIFECYCLE_SENTINEL" in verifier
    assert "browser-preflight" in verifier
    assert '"-Action", "Smoke"' in verifier
    assert "Assert-ExactPreservedInstallTree" in verifier
    assert "Get-ChildItem -LiteralPath $InstallRoot -Recurse -Force" in verifier
    assert '"downloads/user-owned.txt"' in verifier
    assert '"offline.env"' in verifier
    assert "Compare-Object" in verifier
    assert "Wait-ForUninstallCompletion" in verifier
    assert "Uninstallation process succeeded." in verifier
    assert "$uninstallFiles.Count -eq 0" in verifier
    assert '-ne "unins000.exe"' in verifier
    assert "/LOG=$uninstallLog" in verifier
    assert '"install-helper.log"' not in verifier


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


def test_release_resolver_tooling_uses_rolling_compatible_ranges() -> None:
    expected_install = 'python -m pip install "pip>=26.1.2,<27" "packaging>=26.2,<27"'

    for workflow_name in ("release.yml", "rolling-release.yml"):
        workflow = _workflow_text(workflow_name)
        assert expected_install in workflow
        assert '"pip==' not in workflow
        assert '"packaging==' not in workflow


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
