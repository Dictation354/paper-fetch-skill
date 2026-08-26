from __future__ import annotations

import json
import os
import shutil
import tomllib
from pathlib import Path

import pytest

from paper_fetch.config import DEFAULT_USER_AGENT
from paper_fetch.provenance import ProvenanceContext, install_provenance_payload
from paper_fetch.skill_integrity import (
    SkillManifestError,
    build_skill_bundle_manifest,
    require_valid_skill_bundle,
    verify_skill_bundle,
)
from tests.paths import SKILL_DIR
from tests.skill_bundle_links import (
    REQUIRED_REFERENCE_FILES,
    skill_bundle_link_issues,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _copy_host_skills(skill_dir: Path, home: Path) -> None:
    destinations = (
        home / ".codex" / "skills" / "paper-fetch-skill",
        home / ".claude" / "skills" / "paper-fetch-skill",
        home / ".gemini" / "antigravity-cli" / "skills" / "paper-fetch-skill",
    )
    for destination in destinations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skill_dir, destination)


def _create_install(
    root: Path,
    *,
    manifest_version: str = "5.5.0",
    runtime_version: str = "5.5.0",
    target_platform: str = "linux",
) -> tuple[Path, Path]:
    install_root = root / "install"
    home = root / "home"
    home.mkdir(parents=True)
    skill_dir = install_root / "skills" / "paper-fetch-skill"
    _write(skill_dir / "SKILL.md", "# Paper Fetch\n")
    _write(skill_dir / "references" / "workflow.md", "# Workflow\n")
    _write(skill_dir / "references" / "acceptance.md", "# Acceptance\n")

    if target_platform == "windows":
        site_packages = install_root / "runtime" / "Lib" / "site-packages"
        runtime_cli = install_root / "bin" / "paper-fetch.cmd"
        entrypoint = "paper-fetch-skill-windows-x86_64-setup.exe"
        python_tag = "cp313"
    else:
        site_packages = install_root / "runtime" / "site-packages"
        runtime_cli = install_root / "bin" / "paper-fetch"
        entrypoint = "install-offline.sh"
        python_tag = "cp311"
        _write(install_root / entrypoint, "#!/usr/bin/env bash\n")
    _write(site_packages / "paper_fetch" / "__init__.py")
    _write(
        site_packages / f"paper_fetch_skill-{runtime_version}.dist-info" / "METADATA",
        f"Metadata-Version: 2.1\nName: paper-fetch-skill\nVersion: {runtime_version}\n",
    )
    _write(
        runtime_cli, "@echo off\n" if target_platform == "windows" else "#!/bin/sh\n"
    )

    manifest = {
        "schema_version": 3,
        "name": f"paper-fetch-skill-offline-{target_platform}-x86_64",
        "project": "paper-fetch-skill",
        "version": manifest_version,
        "built_at_utc": "2026-07-13T00:00:00Z",
        "git_revision": "0123456789abcdef",
        "target": {
            "platform": target_platform,
            "arch": "x86_64",
            "python_tag": python_tag,
        },
        "entrypoint": entrypoint,
        "skill_bundle": build_skill_bundle_manifest(
            skill_dir,
            name="paper-fetch-skill",
            root="skills/paper-fetch-skill",
        ),
    }
    _write(
        install_root / "offline-manifest.json",
        json.dumps(manifest, indent=2) + "\n",
    )
    _copy_host_skills(skill_dir, home)
    return install_root, home


def _context(
    root: Path,
    home: Path,
    *,
    distribution_version: str = "5.5.0",
    cli_version: str = "5.5.0",
    cli_path: Path | None = None,
    source_root: Path | None = None,
    sys_prefix: Path | None = None,
    env: dict[str, str] | None = None,
) -> ProvenanceContext:
    distribution_root = root / "executing-environment" / "site-packages"
    metadata_path = (
        distribution_root
        / f"paper_fetch_skill-{distribution_version}.dist-info"
        / "METADATA"
    )
    _write(metadata_path, f"Version: {distribution_version}\n")
    effective_cli_path = cli_path or root / "install" / "bin" / "paper-fetch"
    return ProvenanceContext(
        module_file=root
        / "executing-environment"
        / "site-packages"
        / "paper_fetch"
        / "provenance.py",
        executable=root / "executing-environment" / "bin" / "python",
        sys_prefix=sys_prefix
        or (
            source_root / ".venv"
            if source_root is not None
            else root / "executing-environment"
        ),
        argv0=str(effective_cli_path),
        home=home,
        env=env or {},
        source_root=source_root,
        current_distribution={
            "status": "ready",
            "reason_code": "distribution_metadata_found",
            "name": "paper-fetch-skill",
            "version": distribution_version,
            "root": str(distribution_root),
            "metadata_path": str(metadata_path),
        },
        active_cli={
            "status": "ready",
            "reason_code": "path_cli_version_found",
            "path": str(effective_cli_path),
            "version": cli_version,
        },
    )


def _create_source_checkout(root: Path) -> Path:
    source_root = root / "source"
    _write(
        source_root / "pyproject.toml",
        (
            '[project]\nname = "paper-fetch-skill"\nversion = "5.5.0"\n'
            'dependencies = ["mcp>=2,<3"]\n'
        ),
    )
    _write(source_root / ".venv" / "bin" / "activate")
    shutil.copytree(SKILL_DIR, source_root / "skills" / "paper-fetch-skill")
    return source_root


@pytest.mark.parametrize("target_platform", ["linux", "windows"])
def test_consistent_posix_and_windows_install_provenance_is_ready(
    tmp_path: Path,
    target_platform: str,
) -> None:
    install_root, home = _create_install(
        tmp_path,
        target_platform=target_platform,
    )
    cli_name = "paper-fetch.cmd" if target_platform == "windows" else "paper-fetch"
    context = _context(
        tmp_path,
        home,
        cli_path=install_root / "bin" / cli_name,
    )

    report = install_provenance_payload(
        install_root=install_root,
        context=context,
    )

    assert report["status"] == "ready"
    assert report["consistency"] == {
        "expected_version": "5.5.0",
        "version_status": "ready",
        "version_drift": [],
        "issue_count": 0,
    }
    assert report["offline_manifest"]["schema_version"] == 3
    assert report["offline_manifest"]["git_revision"] == "0123456789abcdef"
    assert report["offline_manifest"]["target"]["python_tag"] in {"cp311", "cp313"}
    assert report["bundled_skill"]["expected_file_count"] == 3
    assert {item["host"] for item in report["host_skills"]} == {
        "codex",
        "claude",
        "antigravity",
    }
    assert all(item["status"] == "ready" for item in report["host_skills"])


def test_runtime_old_version_reports_exact_metadata_path(tmp_path: Path) -> None:
    install_root, home = _create_install(tmp_path, runtime_version="3.0.0")

    report = install_provenance_payload(
        install_root=install_root,
        context=_context(tmp_path, home),
    )

    assert report["status"] == "drift"
    [drift] = [
        item
        for item in report["consistency"]["version_drift"]
        if item["component"] == "installed_runtime"
    ]
    assert drift["expected"] == "5.5.0"
    assert drift["actual"] == "3.0.0"
    assert drift["path"].endswith("paper_fetch_skill-3.0.0.dist-info/METADATA")


def test_old_manifest_version_is_distinguished_from_current_runtime(
    tmp_path: Path,
) -> None:
    install_root, home = _create_install(tmp_path, manifest_version="3.0.0")

    report = install_provenance_payload(
        install_root=install_root,
        context=_context(tmp_path, home),
    )

    drift = report["consistency"]["version_drift"]
    assert report["status"] == "drift"
    assert {
        (item["component"], item["expected"], item["actual"]) for item in drift
    } == {("offline_manifest", "5.5.0", "3.0.0")}
    assert drift[0]["path"] == str(install_root / "offline-manifest.json")


def test_skill_hash_drift_and_missing_reference_are_structured(tmp_path: Path) -> None:
    install_root, home = _create_install(tmp_path)
    workflow = (
        install_root / "skills" / "paper-fetch-skill" / "references" / "workflow.md"
    )
    acceptance = (
        install_root / "skills" / "paper-fetch-skill" / "references" / "acceptance.md"
    )
    workflow.write_text("changed\n", encoding="utf-8")
    acceptance.unlink()

    report = install_provenance_payload(
        install_root=install_root,
        context=_context(tmp_path, home),
    )

    assert report["status"] == "drift"
    bundled = report["bundled_skill"]
    assert bundled["missing_files"] == ["references/acceptance.md"]
    assert [item["path"] for item in bundled["hash_mismatches"]] == [
        "references/workflow.md"
    ]


def test_source_development_without_manifest_is_not_applicable(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    _write(
        source_root / "pyproject.toml",
        '[project]\nname = "paper-fetch-skill"\nversion = "5.5.0"\n',
    )
    cli_path = source_root / ".venv" / "bin" / "paper-fetch"
    _write(cli_path)
    home = tmp_path / "home"
    home.mkdir()
    context = _context(
        tmp_path,
        home,
        cli_path=cli_path,
        source_root=source_root,
    )

    report = install_provenance_payload(context=context)

    assert report["status"] == "not_applicable"
    assert report["offline_manifest"]["status"] == "not_applicable"
    assert report["offline_manifest"]["reason_code"] == (
        "source_development_without_offline_manifest"
    )
    assert report["issues"] == []


def test_source_distribution_and_path_cli_drift_include_all_paths(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    _write(
        source_root / "pyproject.toml",
        '[project]\nname = "paper-fetch-skill"\nversion = "5.5.0"\n',
    )
    home = tmp_path / "home"
    home.mkdir()
    old_cli = tmp_path / "active-2.8.0" / "bin" / "paper-fetch"
    _write(old_cli)
    context = _context(
        tmp_path,
        home,
        distribution_version="3.0.0",
        cli_version="2.8.0",
        cli_path=old_cli,
        source_root=source_root,
    )

    report = install_provenance_payload(context=context)

    assert report["status"] == "drift"
    drifts = {
        item["component"]: item for item in report["consistency"]["version_drift"]
    }
    assert set(drifts) == {"current_distribution", "active_cli"}
    assert drifts["current_distribution"]["path"].endswith(
        "paper_fetch_skill-3.0.0.dist-info/METADATA"
    )
    assert drifts["active_cli"] == {
        "component": "active_cli",
        "expected": "5.5.0",
        "actual": "2.8.0",
        "path": str(old_cli),
    }
    assert report["offline_manifest"]["status"] == "not_applicable"


def test_source_checkout_reports_inactive_project_venv(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    _write(
        source_root / "pyproject.toml",
        (
            '[project]\nname = "paper-fetch-skill"\nversion = "5.5.0"\n'
            'dependencies = ["mcp>=2,<3"]\n'
        ),
    )
    _write(source_root / ".venv" / "bin" / "activate")
    home = tmp_path / "home"
    home.mkdir()

    report = install_provenance_payload(
        context=_context(
            tmp_path,
            home,
            source_root=source_root,
            sys_prefix=tmp_path / "system-python",
        )
    )

    environment = report["source_project_environment"]
    assert report["status"] == "drift"
    assert environment["status"] == "degraded"
    assert environment["project_venv_active"] is False
    assert environment["activation_command"] == (
        f"source {source_root / '.venv' / 'bin' / 'activate'}"
    )
    assert "source_checkout_project_venv_not_active" in {
        issue["reason_code"] for issue in report["issues"]
    }


def test_source_checkout_reports_incompatible_mcp_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    _write(
        source_root / "pyproject.toml",
        (
            '[project]\nname = "paper-fetch-skill"\nversion = "5.5.0"\n'
            'dependencies = ["mcp>=2,<3"]\n'
        ),
    )
    _write(source_root / ".venv" / "bin" / "activate")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(
        "paper_fetch.provenance.importlib.metadata.version", lambda _: "1.28.1"
    )

    report = install_provenance_payload(
        context=_context(tmp_path, home, source_root=source_root)
    )

    assert report["status"] == "drift"
    assert report["source_project_environment"]["mcp"] == {
        "status": "incompatible",
        "reason_code": "project_dependency_incompatible",
        "requirement": "mcp<3,>=2",
        "installed_version": "1.28.1",
        "pyproject_path": str(source_root / "pyproject.toml"),
    }


def test_offline_runtime_does_not_require_source_project_venv(
    tmp_path: Path,
) -> None:
    install_root, home = _create_install(tmp_path)

    report = install_provenance_payload(
        install_root=install_root,
        context=_context(tmp_path, home),
    )

    assert report["status"] == "ready"
    assert report["source_project_environment"]["status"] == "not_applicable"
    assert report["source_project_environment"]["issues"] == []


def test_skill_integrity_rejects_extra_files_and_symlinks(tmp_path: Path) -> None:
    install_root, _home = _create_install(tmp_path)
    manifest_path = install_root / "offline-manifest.json"
    skill_dir = install_root / "skills" / "paper-fetch-skill"
    _write(skill_dir / "extra.md", "extra\n")
    (skill_dir / "linked.md").symlink_to(skill_dir / "SKILL.md")

    report = verify_skill_bundle(manifest_path)

    assert report["status"] == "drift"
    assert report["unexpected_files"] == ["extra.md"]
    assert report["symlink_files"] == ["linked.md"]
    assert report["actual_content_sha256"] != report["expected_content_sha256"]
    with pytest.raises(SkillManifestError, match="integrity check failed"):
        require_valid_skill_bundle(manifest_path)


def test_skill_content_hash_is_stable_across_mtime_copy_and_order(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    _write(source / "references" / "second.md", "second\n")
    _write(source / "SKILL.md", "# Skill\n")
    _write(source / "references" / "first.md", "first\n")

    initial = build_skill_bundle_manifest(
        source,
        name="paper-fetch-skill",
        root="skills/paper-fetch-skill",
    )
    for index, path in enumerate(reversed(sorted(source.rglob("*")))):
        if path.is_file():
            os.utime(path, ns=(1_000_000_000 + index, 2_000_000_000 + index))
    copied = tmp_path / "copied"
    shutil.copytree(source, copied)
    rebuilt = build_skill_bundle_manifest(
        copied,
        name="paper-fetch-skill",
        root="skills/paper-fetch-skill",
    )

    assert rebuilt == initial
    assert initial["content_version"] == f"sha256:{initial['content_sha256']}"
    assert [item["path"] for item in initial["files"]] == sorted(
        item["path"] for item in initial["files"]
    )

    _write(copied / "references" / "first.md", "changed\n")
    changed = build_skill_bundle_manifest(
        copied,
        name="paper-fetch-skill",
        root="skills/paper-fetch-skill",
    )
    assert changed["content_sha256"] != initial["content_sha256"]
    assert changed["content_version"] != initial["content_version"]


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO requires POSIX")
def test_skill_integrity_rejects_special_files(tmp_path: Path) -> None:
    skill = tmp_path / "skill"
    _write(skill / "SKILL.md", "# Skill\n")
    bundle = build_skill_bundle_manifest(
        skill,
        name="paper-fetch-skill",
        root="skills/paper-fetch-skill",
    )
    manifest = tmp_path / "offline-manifest.json"
    _write(manifest, json.dumps({"skill_bundle": bundle}))
    fifo = skill / "special.fifo"
    os.mkfifo(fifo)

    with pytest.raises(SkillManifestError, match="only regular files"):
        build_skill_bundle_manifest(
            skill,
            name="paper-fetch-skill",
            root="skills/paper-fetch-skill",
        )
    report = verify_skill_bundle(manifest, skill_dir=skill)
    assert report["status"] == "drift"
    assert report["special_files"] == ["special.fifo"]


def test_source_doctor_reports_matching_codex_user_skill_ready(tmp_path: Path) -> None:
    source_root = _create_source_checkout(tmp_path)
    home = tmp_path / "home"
    codex_home = tmp_path / "custom-codex"
    home.mkdir()
    shutil.copytree(
        SKILL_DIR,
        codex_home / "skills" / "paper-fetch-skill",
    )

    report = install_provenance_payload(
        context=_context(
            tmp_path,
            home,
            source_root=source_root,
            env={"CODEX_HOME": str(codex_home)},
        )
    )

    assert report["status"] == "ready", report
    assert report["bundled_skill"]["actual_content_version"].startswith("sha256:")
    [active] = report["host_skills"]
    assert active["host"] == "codex"
    assert active["scope"] == "user"
    assert active["status"] == "ready"
    assert (
        active["actual_content_version"]
        == report["bundled_skill"]["expected_content_version"]
    )


def test_source_doctor_project_skill_wins_and_drift_is_diagnostic(
    tmp_path: Path,
) -> None:
    source_root = _create_source_checkout(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    shutil.copytree(
        SKILL_DIR,
        home / ".codex" / "skills" / "paper-fetch-skill",
    )
    project_skill = source_root / ".codex" / "skills" / "paper-fetch-skill"
    shutil.copytree(SKILL_DIR, project_skill)
    _write(project_skill / "SKILL.md", "drift\n")

    report = install_provenance_payload(
        context=_context(tmp_path, home, source_root=source_root)
    )

    assert report["status"] == "drift"
    [active] = report["host_skills"]
    assert active["scope"] == "project"
    assert active["status"] == "drift"
    assert active["hash_mismatches"][0]["path"] == "SKILL.md"
    assert any(issue["component"] == "host_skill.codex" for issue in report["issues"])


def test_source_doctor_reports_missing_active_codex_skill(tmp_path: Path) -> None:
    source_root = _create_source_checkout(tmp_path)
    home = tmp_path / "home"
    home.mkdir()

    report = install_provenance_payload(
        context=_context(tmp_path, home, source_root=source_root)
    )

    assert report["status"] == "drift"
    [active] = report["host_skills"]
    assert active["scope"] == "user"
    assert active["reason_code"] == "skill_bundle_missing"


def test_real_source_staging_and_temp_install_preserve_skill_and_version_provenance(
    tmp_path: Path,
) -> None:
    version = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]
    source_bundle = build_skill_bundle_manifest(
        SKILL_DIR,
        name="paper-fetch-skill",
        root="skills/paper-fetch-skill",
    )

    staging_root = tmp_path / "staging"
    staged_skill = staging_root / "skills" / "paper-fetch-skill"
    staged_skill.parent.mkdir(parents=True)
    shutil.copytree(SKILL_DIR, staged_skill)
    staged_bundle = build_skill_bundle_manifest(
        staged_skill,
        name="paper-fetch-skill",
        root="skills/paper-fetch-skill",
    )
    assert staged_bundle == source_bundle

    offline_manifest = {
        "schema_version": 3,
        "name": "paper-fetch-skill-offline-linux-x86_64",
        "project": "paper-fetch-skill",
        "version": version,
        "built_at_utc": "2026-07-13T00:00:00Z",
        "git_revision": "0123456789abcdef",
        "target": {
            "platform": "linux",
            "arch": "x86_64",
            "python_tag": "cp311",
        },
        "entrypoint": "install-offline.sh",
        "skill_bundle": staged_bundle,
    }
    staging_manifest = staging_root / "offline-manifest.json"
    _write(staging_manifest, json.dumps(offline_manifest, indent=2) + "\n")

    install_root = tmp_path / "install"
    installed_skill = install_root / "skills" / "paper-fetch-skill"
    installed_skill.parent.mkdir(parents=True)
    shutil.copytree(staged_skill, installed_skill)
    _write(
        install_root
        / "runtime"
        / "site-packages"
        / f"paper_fetch_skill-{version}.dist-info"
        / "METADATA",
        f"Metadata-Version: 2.1\nName: paper-fetch-skill\nVersion: {version}\n",
    )
    _write(install_root / "runtime" / "site-packages" / "paper_fetch" / "__init__.py")
    _write(install_root / "bin" / "paper-fetch", "#!/bin/sh\n")
    _write(install_root / "install-offline.sh", "#!/usr/bin/env bash\n")
    install_manifest = install_root / "offline-manifest.json"
    _write(install_manifest, json.dumps(offline_manifest, indent=2) + "\n")

    home = tmp_path / "home"
    home.mkdir()
    _copy_host_skills(installed_skill, home)
    installed_copies = (
        installed_skill,
        home / ".codex" / "skills" / "paper-fetch-skill",
        home / ".claude" / "skills" / "paper-fetch-skill",
        home / ".gemini" / "antigravity-cli" / "skills" / "paper-fetch-skill",
    )
    all_copies = (SKILL_DIR, staged_skill, *installed_copies)

    expected_references = {
        f"references/{filename}" for filename in REQUIRED_REFERENCE_FILES
    }
    manifested_paths = {item["path"] for item in source_bundle["files"]}
    assert expected_references <= manifested_paths
    for skill_dir in all_copies:
        assert skill_bundle_link_issues(skill_dir) == []
        assert (
            require_valid_skill_bundle(
                install_manifest if skill_dir != staged_skill else staging_manifest,
                skill_dir=skill_dir,
            )["status"]
            == "ready"
        )

    report = install_provenance_payload(
        install_root=install_root,
        context=_context(
            tmp_path,
            home,
            distribution_version=version,
            cli_version=version,
            cli_path=install_root / "bin" / "paper-fetch",
        ),
    )
    assert report["status"] == "ready", report
    assert report["consistency"]["expected_version"] == version
    assert report["consistency"]["version_drift"] == []
    assert report["bundled_skill"]["expected_file_count"] == len(source_bundle["files"])
    assert all(item["status"] == "ready" for item in report["host_skills"])


def test_release_version_sources_are_synchronized() -> None:
    pyproject = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    version = pyproject["project"]["version"]
    inno = (REPO_ROOT / "installer" / "paper-fetch-skill.iss").read_text(
        encoding="utf-8"
    )

    assert version == "5.5.0"
    assert DEFAULT_USER_AGENT == f"paper-fetch-skill/{version}"
    assert f'#define AppVersion "{version}"' in inno
    assert f"## {version} - 2026-08-25" in (REPO_ROOT / "CHANGELOG.md").read_text(
        encoding="utf-8"
    )
    assert f"## {version} - 2026-08-25" in (REPO_ROOT / "CHANGELOG_CN.md").read_text(
        encoding="utf-8"
    )
