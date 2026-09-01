#!/usr/bin/env python3
"""Validate the compact macOS support and evidence contract against its owners."""

from __future__ import annotations

import argparse
import json
import re
import runpy
import sys
import tomllib
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "docs" / "macos-adaptation-contract.toml"


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _workflow(name: str, *, repo_root: Path) -> dict[str, Any]:
    payload = yaml.safe_load(
        (repo_root / ".github" / "workflows" / name).read_text(encoding="utf-8")
    )
    return payload if isinstance(payload, dict) else {}


def _macos_release_matrix(*, repo_root: Path) -> list[dict[str, str]]:
    workflow = _workflow("offline.yml", repo_root=repo_root)
    include = (
        workflow.get("jobs", {})
        .get("posix", {})
        .get("strategy", {})
        .get("matrix", {})
        .get("include", [])
    )
    return [
        {str(key): str(value) for key, value in item.items()}
        for item in include
        if isinstance(item, dict) and str(item.get("target", "")).startswith("macos-")
    ]


def _release_owner_facts() -> tuple[list[str], list[str], list[str]]:
    namespace = runpy.run_path(str(REPO_ROOT / "scripts" / "prepare_release_assets.py"))
    TARGET_ARTIFACTS = namespace["TARGET_ARTIFACTS"]
    targets = [target for target, _artifact, _installer in TARGET_ARTIFACTS]
    macos_targets = [target for target in targets if target.startswith("macos-")]
    macos_installers = [
        installer
        for target, _artifact, installer in TARGET_ARTIFACTS
        if target.startswith("macos-")
    ]
    return targets, macos_targets, macos_installers


def validate_contract(
    contract: dict[str, Any], *, repo_root: Path = REPO_ROOT
) -> list[str]:
    errors: list[str] = []
    if contract.get("schema_version") != 3:
        errors.append("schema_version must be 3")
    if contract.get("contract_id") != "paper-fetch/macos":
        errors.append("contract_id must be paper-fetch/macos")
    if contract.get("platform") != "macos":
        errors.append("platform must be macos")

    project = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    project_python = project.get("project", {}).get("requires-python")
    online = contract.get("support", {}).get("online", {})
    if online.get("python_spec") != project_python:
        errors.append(
            "support.online.python_spec must match project.requires-python "
            f"({project_python!r})"
        )

    offline = contract.get("support", {}).get("offline", {})
    matrix = _macos_release_matrix(repo_root=repo_root)
    matrix_versions = [item.get("python-version", "") for item in matrix]
    matrix_runners = sorted({item.get("os", "") for item in matrix})
    matrix_targets = [item.get("target", "") for item in matrix]
    _all_targets, owner_targets, owner_installers = _release_owner_facts()
    owner_versions = [f"3.{target.rsplit('cp', 1)[1][-2:]}" for target in owner_targets]
    owner_architectures = sorted(
        {target.removeprefix("macos-").rsplit("-cp", 1)[0] for target in owner_targets}
    )
    if offline.get("status") != "supported":
        errors.append("support.offline.status must be supported")
    if offline.get("minimum_os_version") != "15.0":
        errors.append("support.offline.minimum_os_version must be '15.0'")
    if offline.get("python_implementation") != "CPython":
        errors.append("support.offline.python_implementation must be CPython")
    if (
        offline.get("python_versions") != matrix_versions
        or matrix_versions != owner_versions
    ):
        errors.append(
            "support.offline.python_versions must match the offline workflow and release asset owner"
        )
    if offline.get("architectures") != owner_architectures:
        errors.append(
            "support.offline.architectures must match the release asset owner"
        )
    if matrix_runners != [offline.get("runner")]:
        errors.append("support.offline.runner must match the offline workflow")
    if matrix_targets != owner_targets:
        errors.append(
            "offline workflow macOS targets must match the release asset owner"
        )

    installer = json.loads(
        (repo_root / "installer" / "manifest.json").read_text(encoding="utf-8")
    )
    prefix = installer.get("packages", {}).get("macos_offline_name_prefix")
    if not isinstance(prefix, str) or any(
        not name.startswith(f"{prefix}-") for name in owner_installers
    ):
        errors.append(
            "release asset owner macOS filenames must use installer manifest prefix"
        )

    verify = _workflow("verify.yml", repo_root=repo_root).get("jobs", {})
    native = verify.get("macos-native", {})
    native_contract = contract.get("evidence", {}).get("native", {})
    if native_contract.get("runner") != native.get("runs-on"):
        errors.append("evidence.native.runner must match verify workflow")
    native_text = (repo_root / ".github" / "workflows" / "verify.yml").read_text(
        encoding="utf-8"
    )
    native_job_text = native_text.split("\n  macos-native:", 1)[-1]
    native_job_text = re.split(r"\n  [A-Za-z0-9_-]+:", native_job_text, maxsplit=1)[0]
    if (
        f'python-version: "{native_contract.get("python_version")}"'
        not in native_job_text
    ):
        errors.append("evidence.native.python_version must match verify workflow")

    safety = contract.get("safety", {})
    for key, enabled in safety.items():
        if enabled is not True:
            errors.append(f"safety.{key} must be true")
    required_safety = {
        "standard_gil_cpython",
        "target_architecture_match",
        "owned_staging_cleanup",
        "atomic_release_publish",
        "quarantine_fail_closed",
        "exact_payload_inventory",
        "reject_symlinks",
        "validated_purge_paths",
    }
    missing_safety = required_safety - set(safety)
    if missing_safety:
        errors.append(f"safety is missing: {sorted(missing_safety)!r}")

    browser = contract.get("browser", {})
    for key in (
        "runtime_bundle_built_in",
        "install_downloads_runtime",
        "managed_runtime_preparation",
    ):
        if browser.get(key) is not False:
            errors.append(f"browser.{key} must be false")
    for key in ("native_bundle_gate",):
        if browser.get(key) is not True:
            errors.append(f"browser.{key} must be true")

    release = contract.get("release", {})
    if release.get("installer_manifest") != "installer/manifest.json":
        errors.append("release.installer_manifest must identify the installer owner")
    if release.get("asset_owner") != "scripts/prepare_release_assets.py":
        errors.append("release.asset_owner must identify the release asset owner")
    if release.get("single_source_revision") is not True:
        errors.append("release.single_source_revision must be true")
    if release.get("public_assets_are_installers_only") is not True:
        errors.append("release.public_assets_are_installers_only must be true")
    if release.get("build_evidence_is_not_public") is not True:
        errors.append("release.build_evidence_is_not_public must be true")
    return errors


def validate_repository(
    *, contract_path: Path = CONTRACT_PATH, repo_root: Path = REPO_ROOT
) -> list[str]:
    try:
        contract = load_contract(contract_path)
        return validate_contract(contract, repo_root=repo_root)
    except (OSError, ValueError, KeyError, tomllib.TOMLDecodeError) as exc:
        return [f"cannot validate macOS adaptation contract: {exc}"]


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        description="Validate the machine-readable macOS adaptation contract."
    ).parse_args(argv)
    errors = validate_repository()
    if errors:
        print("macOS adaptation contract validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    contract = load_contract()
    _targets, macos_targets, _installers = _release_owner_facts()
    print(
        f"macOS adaptation contract OK: {contract['contract_id']}; "
        f"{len(macos_targets)} native package targets"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
